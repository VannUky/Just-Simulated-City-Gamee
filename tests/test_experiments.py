import unittest
from unittest.mock import patch

from systems.agents.experiments import (
    begin_experiment_day, capture_experiment_market,
    finish_experiment_day, propose_price_experiment,
    start_price_experiment,
)
from systems.ekonomi_core import World


class PriceExperimentTests(unittest.TestCase):
    def make_world(self):
        world = World(seed=173, n_pop=4)
        owner, customer, recipient, untouched = world.citizens
        self.assertTrue(world.found_business(owner, "shop", force=True))
        business = owner.business
        business.cash = 20_000_000.0
        business.stock = 1_000.0
        business.cost_avg = 20_000.0
        business.price = 44_000.0
        business.daily_demand.clear()
        business.daily_demand.extend((0, 10, 0, 10, 0, 10, 0))
        business.soldout_hist.clear()
        business.soldout_hist.extend((True, True, True, True, True, False, False))
        business.over_hist.clear()
        business.over_hist.extend((False,) * 7)
        world.set_cash(customer, 10_000_000.0)
        world._initialize_ledger()
        return world, owner, customer, recipient, untouched, business

    @staticmethod
    def simulate_day(world, customer=None):
        begin_experiment_day(world)
        if customer is not None:
            world.buy_goods(customer, 1.0)
        capture_experiment_market(world)
        for business in world.businesses:
            business.demand_today = 0.0
            business.sold_today = 0.0
        finish_experiment_day(world)
        world.day += 1

    def test_proposal_uses_uncertainty_and_has_evsi_and_risk_gate(self):
        world, owner, _, _, _, business = self.make_world()
        starting_day = world.day
        starting_cash = business.cash

        proposal = propose_price_experiment(world, owner)

        self.assertIsNotNone(proposal)
        self.assertIn("harga", proposal.hypothesis.lower())
        self.assertEqual(proposal.variable, "shop_price_multiplier")
        self.assertEqual(proposal.treatment_days_required, 7)
        self.assertGreater(proposal.expected_value_of_information, proposal.estimated_risk)
        self.assertGreater(proposal.risk_budget, proposal.estimated_risk)
        self.assertGreaterEqual(business.cash, proposal.risk_budget)
        self.assertEqual(world.day, starting_day)
        self.assertEqual(business.cash, starting_cash)
        self.assertIsNone(owner.experiments.active)

    def test_idle_curious_owner_starts_a_valid_experiment(self):
        world, owner, _, _, _, _ = self.make_world()

        with patch("systems.ekonomi_core.available_actions", return_value=[]):
            started = world.agent_decision_cycle(owner)

        self.assertTrue(started)
        self.assertIsNotNone(owner.experiments.active)
        self.assertEqual(owner.experiments.active.phase, "baseline")

    def test_world_daily_records_the_active_experiment(self):
        world, owner, customer, _, _, _ = self.make_world()
        world.set_cash(customer, 0.0)
        proposal = propose_price_experiment(world, owner)
        self.assertTrue(
            start_price_experiment(
                world, owner, proposal, {"learning": 1.0}
            )
        )

        world.advance(24)

        self.assertEqual(owner.experiments.active.baseline_days, 1)

    def test_failed_test_costs_real_sales_and_is_shared_only_on_request(self):
        world, owner, customer, recipient, untouched, business = self.make_world()
        starting_customer_cash = customer.cash
        starting_business_cash = business.cash
        proposal = propose_price_experiment(world, owner)
        self.assertTrue(
            start_price_experiment(
                world, owner, proposal, {"learning": 1.0}
            )
        )

        for _ in range(7):
            self.simulate_day(world, customer)

        self.assertEqual(owner.experiments.active.phase, "treatment")
        self.assertAlmostEqual(business.price, 44_000.0 * 1.05)
        for _ in range(3):
            self.simulate_day(world)
            if owner.experiments.active is None:
                break

        result = owner.experiments.history[-1]
        self.assertEqual(result.status, "aborted")
        self.assertGreater(result.risk_used, 0.0)
        self.assertLess(result.demand_change, 0.0)
        self.assertEqual(business.innovation_price_multiplier, 1.0)
        self.assertAlmostEqual(business.price, 44_000.0)
        self.assertLess(customer.cash, starting_customer_cash)
        self.assertGreater(business.cash, starting_business_cash)
        self.assertEqual(len(owner.memory.episodes), 1)
        self.assertEqual(owner.knowledge.observations[-1].source_type, "personal_experience")
        self.assertTrue(owner.adaptive_learning.contexts)
        self.assertIsNone(propose_price_experiment(world, owner))

        self.assertEqual(recipient.knowledge.observations, [])
        self.assertEqual(untouched.knowledge.observations, [])
        world.share_experiment_result(owner, recipient, result.id)
        self.assertEqual(
            recipient.knowledge.observations[-1].source_type,
            "social_information",
        )
        self.assertEqual(untouched.knowledge.observations, [])

    def test_successful_test_adopts_strategy_only_after_real_improvement(self):
        world, owner, customer, _, _, business = self.make_world()
        proposal = propose_price_experiment(world, owner)
        self.assertTrue(
            start_price_experiment(
                world, owner, proposal, {"learning": 1.0}
            )
        )

        for _ in range(7):
            self.simulate_day(world)
        self.assertEqual(owner.experiments.active.phase, "treatment")

        for _ in range(7):
            self.simulate_day(world, customer)

        result = owner.experiments.history[-1]
        self.assertEqual(result.status, "adopted")
        self.assertGreater(result.treatment_profit_per_day, result.baseline_profit_per_day)
        self.assertEqual(business.innovation_price_multiplier, 1.05)
        self.assertAlmostEqual(business.price, 44_000.0 * 1.05)
        learning_context = next(iter(owner.adaptive_learning.contexts))
        self.assertEqual(
            owner.adaptive_learning.contexts[learning_context][
                f"experiment:price:{result.product}:up"
            ].count,
            1,
        )
        self.assertIsNone(propose_price_experiment(world, owner))

    def test_migration_adds_experiment_defaults_idempotently(self):
        world, owner, _, _, _, business = self.make_world()
        del owner.experiments
        del business.innovation_price_multiplier

        world.migrate_save()
        first_state = owner.experiments
        world.migrate_save()

        self.assertIs(owner.experiments, first_state)
        self.assertEqual(business.innovation_price_multiplier, 1.0)


if __name__ == "__main__":
    unittest.main()
