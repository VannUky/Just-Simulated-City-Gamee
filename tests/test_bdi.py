import copy
import unittest
from unittest.mock import patch

from systems.agents.actions import (
    available_actions, execute_action, planning_state,
)
from systems.agents.goals import (
    BDIState, Goal, Intention, form_goals, update_beliefs,
)
from systems.agents.planner import BoundedPlanner, PlanningAction
from systems.ekonomi_core import World


class BDIPlannerTests(unittest.TestCase):
    def test_planner_finds_multistep_plan_without_mutating_world_state(self):
        state = {
            "facts": {"has_land": False, "owns_home": False},
            "resources": {"money": 50.0},
        }
        original = copy.deepcopy(state)
        actions = [
            PlanningAction(
                "buy_land",
                preconditions={"has_land": False},
                effects={"has_land": True},
                resource_costs={"money": 30.0},
            ),
            PlanningAction(
                "build_house",
                preconditions={"has_land": True},
                effects={"owns_home": True},
                resource_costs={"money": 20.0},
            ),
        ]
        goal = Goal("own_home", conditions={"owns_home": True})

        plan = BoundedPlanner(max_depth=2, max_expansions=8).plan(
            state, goal, actions
        )

        self.assertIsNotNone(plan)
        self.assertEqual(
            [action.action_id for action in plan.actions],
            ["buy_land", "build_house"],
        )
        self.assertEqual(state, original)
        self.assertTrue(plan.final_state["facts"]["owns_home"])

    def test_planner_rejects_resource_infeasible_plan(self):
        state = {
            "facts": {"has_land": False},
            "resources": {"money": 0.0},
        }
        goal = Goal("own_land", conditions={"has_land": True})
        action = PlanningAction(
            "buy_land",
            preconditions={"has_land": False},
            effects={"has_land": True},
            resource_costs={"money": 1.0},
        )

        self.assertIsNone(
            BoundedPlanner().plan(state, goal, [action])
        )

    def test_beliefs_include_personal_memory_and_validated_knowledge(self):
        world = World(seed=131, n_pop=1)
        citizen = world.citizens[0]
        citizen.memory.record(
            world.day, "investment", "sale", {"asset": "KOTA"},
            "realized loss", False, impact=0.4, value=-0.2,
        )
        for day, value in enumerate((-1, -0.5, 0, 0.5, 1)):
            citizen.knowledge.observe(
                day, "personal_experience", f"sale:{day}",
                {"market_momentum": value, "realized_return": value},
                context={"asset": "KOTA"},
            )
        world.day = 4
        state = BDIState()

        update_beliefs(world, citizen, state)

        self.assertEqual(
            state.beliefs["recent_investment_outcome"].source,
            "personal_memory",
        )
        self.assertTrue(any(
            belief.source == "knowledge_graph"
            for belief in state.beliefs.values()
        ))
        self.assertGreater(state.motivations["financial_security"], 0.0)

    def test_goal_priority_changes_with_financial_pressure(self):
        world = World(seed=135, n_pop=1)
        citizen = world.citizens[0]
        citizen.job = None
        citizen.business = None
        citizen.age = 35
        state = BDIState()

        world.set_cash(citizen, 0.0)
        update_beliefs(world, citizen, state)
        pressured = next(
            goal for goal in form_goals(world, citizen, state)
            if goal.id == "find_employment"
        )
        world.set_cash(citizen, 100_000_000.0)
        update_beliefs(world, citizen, state)
        secure = next(
            goal for goal in form_goals(world, citizen, state)
            if goal.id == "find_employment"
        )

        self.assertGreater(pressured.priority, secure.priority)

    def test_validated_negative_outlook_forms_risk_reduction_goal(self):
        world = World(seed=132, n_pop=1)
        citizen = world.citizens[0]
        asset = next(iter(world.market.assets.values()))
        citizen.hold[asset.sym] = [1.0, asset.price]
        for day, value in enumerate((-1, -0.5, 0, 0.5, 1)):
            citizen.knowledge.observe(
                day, "personal_experience", f"sale:{day}",
                {"market_momentum": value, "realized_return": value},
                context={"asset": asset.sym},
            )
        world.day = 4
        state = BDIState()
        update_beliefs(world, citizen, state)

        with patch.object(asset, "momentum", return_value=-0.25):
            with patch.object(asset, "change", return_value=0.0):
                goals = form_goals(world, citizen, state)

        self.assertIn(f"reduce_exposure:{asset.sym}", {
            goal.id for goal in goals
        })

    def test_home_intention_executes_land_then_house_via_world_apis(self):
        world = World(seed=133, n_pop=2)
        citizen, builder_owner = world.citizens
        world.set_cash(citizen, 100_000_000.0)
        world.set_cash(builder_owner, 100_000_000.0)
        if citizen.job is None:
            citizen.job = world.hall
            world.hall.workers.append(citizen)

        self.assertTrue(world.found_business(
            builder_owner, "builder", force=True
        ))
        builder = builder_owner.business
        builder.service_inventory["construction"] = 1.0
        world._initialize_ledger()

        state = planning_state(world, citizen)
        actions = available_actions(world, citizen, state)
        plan = BoundedPlanner(max_depth=3).plan(
            state,
            Goal("own_a_home", conditions={"owns_home": True}),
            actions,
        )
        self.assertIsNotNone(plan)
        self.assertEqual(citizen.cash, 100_000_000.0)
        self.assertFalse(any(lot.land_owner is citizen for lot in world.lots))

        self.assertTrue(world.agent_decision_cycle(citizen))
        self.assertTrue(any(
            lot.land_owner is citizen for lot in world.lots
        ))
        self.assertEqual(citizen.bdi.intention.next_step, 1)

        world.day += 7
        self.assertTrue(world.agent_decision_cycle(citizen))
        self.assertTrue(any(
            house.owner is citizen for house in citizen.houses
        ))
        self.assertEqual(
            sum(
                stats.count
                for arms in citizen.adaptive_learning.contexts.values()
                for stats in arms.values()
            ),
            1,
        )
        self.assertEqual(citizen.bdi.intention.status, "completed")
        self.assertEqual(world.reconcile_ledger(), {})

    def test_unfeasible_intention_is_cancelled(self):
        world = World(seed=136, n_pop=1)
        citizen = world.citizens[0]
        citizen.age = 60
        previous = Intention("own_a_home", ("buy_land",), world.day)
        citizen.bdi.intention = previous

        self.assertFalse(world.agent_decision_cycle(citizen))

        self.assertEqual(previous.status, "cancelled")
        self.assertIsNone(citizen.bdi.intention)

    def test_actions_revalidate_funds_before_buying_land(self):
        world = World(seed=134, n_pop=1)
        citizen = world.citizens[0]
        world.set_cash(citizen, 0.0)
        state = planning_state(world, citizen)
        actions = available_actions(world, citizen, state)
        buy_land = next(action for action in actions
                        if action.action_id == "buy_land")
        available_lot = next(
            lot for lot in world.lots
            if lot.kind == "biz" and lot.building is None
            and lot.land_owner is None
        )

        self.assertFalse(execute_action(world, citizen, buy_land))
        self.assertIsNone(available_lot.land_owner)


if __name__ == "__main__":
    unittest.main()
