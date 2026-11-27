import pickle
import unittest
from unittest.mock import patch

from systems.agents.memory import EpisodicMemory, MemorySummary
from systems.ekonomi_core import World


class EpisodicMemoryTests(unittest.TestCase):
    def test_retrieval_prefers_matching_context_and_supports_time_filter(self):
        memory = EpisodicMemory()
        matching = memory.record(
            10, "investment", "sale", {"asset": "KOTA"},
            "loss realized", False, impact=0.8, value=-0.5,
        )
        memory.record(
            300, "investment", "sale", {"asset": "TEKA"},
            "profit realized", True, impact=0.4, value=0.2,
        )

        found = memory.retrieve(
            domain="investment", action="sale", context={"asset": "KOTA"},
            current_day=365,
        )

        self.assertEqual(found[0], matching)
        self.assertEqual(
            memory.retrieve(domain="investment", since_day=100, current_day=365),
            [memory.episodes[1]],
        )

    def test_repeated_episodes_are_summarized_with_bounded_source_references(self):
        memory = EpisodicMemory()
        for day in range(100):
            result = memory.record(
                day, "investment", "sale", {"asset": "KOTA"},
                "loss realized", False, impact=0.5, value=-0.25,
            )

        self.assertIsInstance(result, MemorySummary)
        self.assertEqual(result.source_count, 100)
        self.assertEqual(result.failure_count, 100)
        self.assertEqual(result.mean_value, -0.25)
        self.assertLessEqual(len(result.source_ids), 32)
        self.assertEqual(result.source_ids[-1], 100)

    def test_capacity_retains_important_episodes_and_bounds_both_collections(self):
        memory = EpisodicMemory()
        memory.record(
            0, "critical", "failure", {}, "major loss", False,
            impact=1.0, value=-1.0,
        )
        for day in range(100):
            memory.record(
                day + 1, f"routine-{day}", "observation", {},
                "low impact", True,
            )
        for group in range(20):
            for repetition in range(3):
                memory.record(
                    200 + group * 3 + repetition, "repeated", "sale",
                    {"asset": str(group)}, "small result", True,
                    impact=0.1, value=0.05,
                )

        self.assertLessEqual(len(memory.episodes), 64)
        self.assertLessEqual(len(memory.summaries), 16)
        self.assertTrue(any(item.domain == "critical" for item in memory.episodes))

    def test_memory_is_personal_and_persists_through_world_pickle(self):
        world = World(seed=51, n_pop=2)
        citizen = world.citizens[0]
        citizen.memory.record(
            world.day, "investment", "sale", {"asset": "KOTA"},
            "loss realized", False, impact=0.7, value=-0.4,
        )

        restored = pickle.loads(pickle.dumps(world, protocol=4))
        restored.migrate_save()

        self.assertEqual(
            restored.citizens[0].memory.retrieve(
                domain="investment", action="sale"
            )[0].value,
            -0.4,
        )
        self.assertEqual(restored.citizens[1].memory.episodes, [])

    def test_legacy_citizen_gets_memory_idempotently(self):
        world = World(seed=52, n_pop=1)
        del world.citizens[0].memory
        restored = pickle.loads(pickle.dumps(world, protocol=4))

        restored.migrate_save()
        memory = restored.citizens[0].memory
        restored.migrate_save()

        self.assertIs(restored.citizens[0].memory, memory)
        self.assertIsInstance(memory, EpisodicMemory)

    def test_sale_experience_changes_the_next_investment_decision(self):
        worlds = [World(seed=53, n_pop=1), World(seed=53, n_pop=1)]
        for world, historical_value in zip(worlds, (-0.8, 0.8)):
            citizen = world.citizens[0]
            asset = next(iter(world.market.assets.values()))
            world.market.assets = {asset.sym: asset}
            world.policy.deposit_rate = 0.05
            asset.vol = 0.0
            citizen.risk = 0.0
            citizen.herd = 0.0
            citizen.optimism = 0.5
            citizen.frugal = 0.0
            citizen.financial_literacy = 1.0
            citizen.est_exp = 1_000_000.0
            world.set_cash(citizen, 100_000_000.0)
            for _ in range(3):
                citizen.memory.record(
                    world.day, "investment", "sale", {"asset": asset.sym},
                    "historical result", historical_value > 0,
                    impact=abs(historical_value), value=historical_value,
                )

        for world in worlds:
            with patch.object(world.rng, "random", return_value=0.0):
                with patch.object(world.rng, "gauss", return_value=0.0):
                    world.finance(world.citizens[0])

        losing_investor, winning_investor = (
            world.citizens[0] for world in worlds
        )
        self.assertFalse(losing_investor.hold)
        self.assertTrue(winning_investor.hold)

    def test_asset_sales_record_realized_personal_experience(self):
        world = World(seed=54, n_pop=1)
        citizen = world.citizens[0]
        asset = next(iter(world.market.assets.values()))
        world.set_cash(citizen, 1_000_000.0)
        self.assertGreater(world.buy_asset(citizen, asset.sym, 200_000.0), 0)
        asset.price *= 0.5

        world.sell_asset(citizen, asset.sym)

        memories = citizen.memory.retrieve(
            domain="investment", action="sale",
            context={"asset": asset.sym}, current_day=world.day,
        )
        self.assertEqual(len(memories), 1)
        self.assertFalse(memories[0].success)
        self.assertLess(memories[0].value, 0)


if __name__ == "__main__":
    unittest.main()
