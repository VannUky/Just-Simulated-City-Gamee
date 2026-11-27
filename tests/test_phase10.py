import pickle
import time
import unittest
from pathlib import Path
import pygame

from main import SAVE_SCHEMA_VERSION, _migrate_save_v3_to_v4
from systems.ekonomi_core import World


class Phase10ObservationTests(unittest.TestCase):
    def test_agent_and_civilization_observations_are_read_only_and_complete(self):
        world = World(seed=1001, n_pop=8)
        citizen = world.citizens[0]

        snapshot = world.agent_observation(citizen)
        civilization = world.civilization_observation()

        self.assertEqual(snapshot["citizen_id"], citizen.id)
        self.assertIn("desires", snapshot)
        self.assertIn("motivations", snapshot)
        self.assertIn("beliefs", snapshot)
        self.assertIn("intention", snapshot)
        self.assertIn("memories", snapshot)
        self.assertIn("validated_claims", snapshot)
        self.assertIn("learning", snapshot)
        self.assertIn("experiment", snapshot)
        self.assertIn("social", snapshot)

        self.assertEqual(civilization["population"], 8)
        self.assertIn("adults", civilization)
        self.assertIn("children", civilization)
        self.assertIn("unemployment", civilization)
        self.assertIn("gini", civilization)
        self.assertIn("median_networth", civilization)
        self.assertIn("active_organizations", civilization)
        self.assertIn("knowledge_observations", civilization)
        self.assertIn("validated_claims", civilization)

    def test_multi_seed_simulations_produce_meaningful_variation(self):
        signatures = []
        for seed in (1101, 1102, 1103):
            world = World(seed=seed, n_pop=12)
            for _ in range(30):
                world.daily()
            civilization = world.civilization_observation()
            signatures.append((
                civilization["population"],
                civilization["unemployment"],
                civilization["gini"],
                civilization["median_networth"],
                civilization["active_organizations"],
                civilization["knowledge_observations"],
            ))

        self.assertEqual(len(signatures), 3)
        self.assertGreater(
            len(set(signatures)),
            1,
            "Seed berbeda harus menghasilkan jejak observasi yang berbeda.",
        )

    def test_same_seed_reproduces_civilization_signature(self):
        left = World(seed=1201, n_pop=12)
        right = World(seed=1201, n_pop=12)
        for _ in range(15):
            left.daily()
            right.daily()

        self.assertEqual(
            left.civilization_observation(),
            right.civilization_observation(),
        )

    def test_140_citizen_benchmark_runs_and_reconciles(self):
        world = World(seed=1301, n_pop=140)
        started = time.perf_counter()
        for _ in range(30):
            world.advance(24)
        elapsed = time.perf_counter() - started

        self.assertEqual(world.day, 30)
        self.assertLessEqual(len(world.citizens), world.max_population)
        self.assertEqual(world.reconcile_ledger(), {})
        self.assertGreaterEqual(world.civilization_observation()["population"], 1)
        self.assertGreaterEqual(elapsed, 0.0)

    def test_observability_save_round_trip_and_v3_migration_are_idempotent(self):
        world = World(seed=1401, n_pop=12)
        restored = pickle.loads(pickle.dumps(world))
        restored.migrate_save()
        first_observation = restored.agent_observation(restored.citizens[0])

        payload = {
            "format": "rupiahville-save",
            "schema_version": 3,
            "ledger_schema_version": restored.ledger.schema_version,
            "world": restored,
        }
        migrated = _migrate_save_v3_to_v4(payload)
        migrated_again = _migrate_save_v3_to_v4(migrated)

        self.assertEqual(migrated["schema_version"], SAVE_SCHEMA_VERSION)
        self.assertEqual(migrated_again["schema_version"], SAVE_SCHEMA_VERSION)
        self.assertEqual(restored.observability_schema_version, 1)
        self.assertEqual(
            migrated_again["world"].agent_observation(restored.citizens[0]),
            first_observation,
        )

    def test_house_sale_cooldown_and_construction_state(self):
        world = World(seed=1501, n_pop=2)
        seller, buyer = world.citizens
        house = world.houses[0]
        house.owner = seller
        seller.houses = [house]
        house.last_sale_day = world.day
        buyer.cash = 1_000_000_000.0
        world._initialize_ledger()

        self.assertFalse(world.buy_house(buyer, house))
        self.assertIs(house.owner, seller)

        house.last_sale_day = world.day - 30
        house.construction_until = world.day + 5
        self.assertFalse(world.buy_house(buyer, house))
        house.construction_until = -1
        self.assertTrue(world.buy_house(buyer, house))
        self.assertIs(house.owner, buyer)

    def test_pack3_building_and_vehicle_assets_are_loaded(self):
        from game.assets import Assets

        pygame.init()
        pygame.display.set_mode((1, 1))
        assets = Assets(Path(__file__).resolve().parents[1] / "assets")
        house = assets.building_pack("house_small", "active")
        truck = assets.vehicle_pack("delivery_truck", "right", (32, 32))
        construction = assets.building_pack("house_small", "constructing")

        self.assertIsNotNone(house)
        self.assertIsNotNone(truck)
        self.assertIsNotNone(construction)


if __name__ == "__main__":
    unittest.main()
