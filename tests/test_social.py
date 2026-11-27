import pickle
import unittest

from systems.agents.social import (
    consider_organization, consider_social_action,
)
from systems.ekonomi_core import World


class SocialIntelligenceTests(unittest.TestCase):
    def make_trading_pair(self):
        world = World(seed=813, n_pop=4)
        buyer_owner, seller_owner, observer, extra = world.citizens
        self.assertTrue(world.found_business(buyer_owner, "shop", force=True))
        self.assertTrue(world.found_business(seller_owner, "farm", force=True))
        shop = buyer_owner.business
        farm = seller_owner.business
        shop.cash = 5_000_000.0
        shop.stock = 0.0
        shop.cost_avg = 20_000.0
        farm.cash = 1_000_000.0
        farm.stock = 500.0
        farm.price = 30_000.0
        world._initialize_ledger()
        for day in range(10):
            world.day = day
            shop.stock = 0.0
            world.shop_restock(shop)
        world._initialize_ledger()
        return world, buyer_owner, seller_owner, observer, extra, shop, farm

    def test_explicit_knowledge_share_is_limited_to_one_trusted_recipient(self):
        world = World(seed=31, n_pop=3)
        sender, recipient, untouched = world.citizens
        world.record_social_interaction(
            sender, recipient, "helped_with_work", True, "shared work"
        )
        observation = world.observe_social_action(
            sender, recipient, "reliable_supply",
            {"delivery_quality": 0.9},
        )

        shared = world.share_social_knowledge(
            sender, recipient, observation.id
        )

        self.assertEqual(shared.source_type, "social_information")
        self.assertEqual(len(recipient.knowledge.observations), 1)
        self.assertEqual(untouched.knowledge.observations, [])
        self.assertGreater(
            world.social_relationship(sender, recipient)["trust"], 0.5
        )
        self.assertEqual(len(sender.memory.episodes), 3)

    def test_trustworthy_trade_forms_a_voted_and_ledgered_cooperative(self):
        (world, buyer, seller, _, _, shop, farm) = self.make_trading_pair()
        edge = world.social_relationship(buyer, seller)
        self.assertGreaterEqual(edge["trust"], 0.65)
        self.assertGreaterEqual(edge["trade_days"], 3)

        organization_id = world.propose_social_organization(
            buyer, [seller], "Trusted Supply Co-op", 25_000.0
        )
        buyer_assets_before = buyer.assets
        self.assertTrue(
            world.respond_social_invitation(seller, organization_id, True)
        )
        organization = world.social_state["organizations"][str(organization_id)]
        self.assertEqual(organization["status"], "active")
        self.assertAlmostEqual(buyer.assets, buyer_assets_before)
        self.assertEqual(world.reconcile_ledger(), {})

        proposal_id = world.propose_organization_rule(
            buyer, organization_id, "brokerage_fee_rate", 0.02
        )
        self.assertEqual(
            world.vote_organization_rule(
                seller, organization_id, proposal_id, True
            ),
            "approved",
        )
        self.assertEqual(organization["rules"]["brokerage_fee_rate"], 0.02)

        offer_id = world.propose_cooperative_trade(
            buyer, seller, 2.0, farm.price * 0.97, organization_id
        )
        buyer_cash = shop.cash
        seller_cash = farm.cash
        buyer_stock = shop.stock
        seller_stock = farm.stock
        contract = world.respond_cooperative_trade(
            seller, offer_id, "accept"
        )

        self.assertEqual(contract["status"], "settled")
        self.assertAlmostEqual(farm.stock, seller_stock - 2.0)
        self.assertAlmostEqual(shop.stock, buyer_stock + 2.0)
        self.assertAlmostEqual(farm.cash, seller_cash + 2.0 * farm.price * 0.97)
        self.assertLess(shop.cash, buyer_cash)
        self.assertGreater(organization["fund"], 50_000.0)
        self.assertEqual(world.reconcile_ledger(), {})

        original_offer = world.propose_cooperative_trade(
            buyer, seller, 1.0, farm.price * 0.97, organization_id
        )
        counter_offer = world.respond_cooperative_trade(
            seller, original_offer, "counter", unit_price=farm.price * 0.96
        )
        self.assertEqual(
            world.social_state["offers"][str(original_offer)]["status"],
            "countered",
        )
        self.assertTrue(consider_social_action(world, buyer))
        self.assertEqual(
            world.social_state["offers"][str(counter_offer)]["status"],
            "settled",
        )
        self.assertEqual(world.reconcile_ledger(), {})

        organization["rules"]["monthly_maintenance_per_member"] = 0.0
        organization["rules"]["profit_share_rate"] = 0.5
        organization["fund"] = 200_000.0
        organization["undistributed_profit"] = 100_000.0
        world._initialize_ledger()
        before_distribution = shop.cash + farm.cash
        world.settle_social_organizations()
        self.assertAlmostEqual(shop.cash + farm.cash, before_distribution + 50_000.0)
        self.assertEqual(world.reconcile_ledger(), {})

        self.assertGreater(world.leave_social_organization(buyer, organization_id), 0)
        self.assertEqual(organization["status"], "dissolved")
        self.assertEqual(organization["fund"], 0.0)
        self.assertEqual(world.reconcile_ledger(), {})

    def test_organizations_need_trade_relationships_and_dissolve_after_failures(self):
        world = World(seed=47, n_pop=2)
        founder, invitee = world.citizens
        self.assertFalse(consider_organization(world, founder))
        world.social_state["organizations"]["1"] = {
            "id": 1,
            "name": "Small Co-op",
            "status": "active",
            "founder_id": founder.id,
            "members": {
                str(founder.id): {
                    "business_id": -1, "share": 0.5,
                },
                str(invitee.id): {
                    "business_id": -2, "share": 0.5,
                },
            },
            "fund": 1_000.0,
            "contributed_capital": 1_000.0,
            "undistributed_profit": 0.0,
            "maintenance_failures": 1,
            "reputation": 0.5,
            "rules": {
                "monthly_maintenance_per_member": 10_000.0,
                "reserve_months": 3,
                "profit_share_rate": 0.5,
            },
        }
        world._initialize_ledger()

        world.settle_social_organizations()

        organization = world.social_state["organizations"]["1"]
        self.assertEqual(organization["status"], "dissolved")
        self.assertEqual(organization["fund"], 0.0)
        self.assertEqual(world.reconcile_ledger(), {})

    def test_social_state_round_trips_and_legacy_world_migrates(self):
        world = World(seed=59, n_pop=2)
        actor, other = world.citizens
        world.record_social_interaction(
            actor, other, "trade", True, "successful"
        )

        restored = pickle.loads(pickle.dumps(world))
        restored.migrate_save()
        self.assertEqual(
            restored.social_relationship(actor, other)["interaction_count"],
            1,
        )
        del restored.social_state
        restored.migrate_save()
        self.assertEqual(restored.social_state["relationships"], {})


if __name__ == "__main__":
    unittest.main()
