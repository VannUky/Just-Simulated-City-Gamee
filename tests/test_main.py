import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import (
    App, RestrictedSaveUnpickler, SAVE_FORMAT, SAVE_SCHEMA_VERSION,
)
from systems.agents.goals import Belief, Goal, Intention
from systems.agents.experiments import ExperimentState, PriceExperiment
from systems.ekonomi_core import World


_UNPICKLE_EXECUTED = False


def _mark_unpickle_execution():
    global _UNPICKLE_EXECUTED
    _UNPICKLE_EXECUTED = True


class MaliciousSave:
    def __reduce__(self):
        return _mark_unpickle_execution, ()


class MessageScene:
    def __init__(self):
        self.messages = []

    def say(self, message):
        self.messages.append(message)


class AppSaveTests(unittest.TestCase):
    def make_app(self):
        app = App.__new__(App)
        app.scene = MessageScene()
        return app

    def test_save_is_atomic_and_reports_success(self):
        world = World(seed=42, n_pop=12)
        citizen = world.citizens[0]
        citizen.bdi.beliefs["test"] = Belief(
            "test", True, 1.0, "test_source", observed_day=world.day
        )
        citizen.bdi.desires = [
            Goal("test_goal", conditions={"ready": True}, priority=0.5)
        ]
        citizen.bdi.intention = Intention(
            "test_goal", ("test_action",), world.day
        )
        citizen.adaptive_learning.update(
            "test_context", "test_arm", -0.5, world.day
        )
        citizen.adaptive_learning.remember(
            "test_context", "test_arm", {"survival": 0.5},
            {"survival": 1.0}, world.day,
        )
        citizen.experiments = ExperimentState(
            active=PriceExperiment(
                id=1,
                business_id=3,
                product="retail_goods",
                hypothesis="A modest price change improves net sales.",
                baseline_multiplier=1.0,
                treatment_multiplier=1.05,
                uncertainty=0.5,
                expected_value_of_information=100_000.0,
                estimated_risk=20_000.0,
                risk_budget=30_000.0,
                started_day=world.day,
            ),
            next_experiment_id=2,
        )
        citizen.memory.record(
            world.day, "investment", "sale", {"asset": "KOTA"},
            "realized return -10.0%", False, impact=0.1, value=-0.1,
        )
        other_citizen = world.citizens[1]
        for _ in range(5):
            world.record_social_interaction(
                citizen, other_citizen, "worked_together", True,
                "saved relationship",
            )
        partnership_id = world.propose_partnership(citizen, other_citizen)
        self.assertTrue(
            world.respond_partnership(other_citizen, partnership_id, True)
        )
        for value in (-1.0, -0.5, 0.0, 0.5, 1.0):
            citizen.knowledge.observe(
                world.day, "personal_experience", f"sale:{value}",
                {"market_momentum": value, "realized_return": value},
                context={"asset": "KOTA"},
            )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saves" / "slot1.sav"
            with patch("main.SAVE_PATH", path):
                app = self.make_app()

                self.assertTrue(app.save_world(world))

                with path.open("rb") as save_file:
                    payload = RestrictedSaveUnpickler(save_file).load()
                self.assertEqual(payload["format"], SAVE_FORMAT)
                self.assertEqual(payload["schema_version"], SAVE_SCHEMA_VERSION)
                self.assertEqual(
                    payload["ledger_schema_version"],
                    world.ledger.schema_version,
                )
                saved_world = payload["world"]
                self.assertEqual(saved_world.seed, world.seed)
                self.assertEqual(
                    saved_world.social_relationship(
                        saved_world.citizens[0], saved_world.citizens[1]
                    )["status"],
                    "active",
                )
                self.assertEqual(
                    saved_world.family_partner(saved_world.citizens[0]).id,
                    saved_world.citizens[1].id,
                )
                self.assertEqual(
                    saved_world.citizens[0].bdi.beliefs["test"].source,
                    "test_source",
                )
                self.assertEqual(
                    saved_world.citizens[0].bdi.desires[0].id,
                    "test_goal",
                )
                self.assertEqual(
                    saved_world.citizens[0].bdi.intention.action_ids,
                    ("test_action",),
                )
                self.assertEqual(
                    saved_world.citizens[0].adaptive_learning.mean_reward(
                        "test_context", "test_arm"
                    ),
                    -0.5,
                )
                self.assertEqual(
                    saved_world.citizens[0].adaptive_learning.pending.arm,
                    "test_arm",
                )
                self.assertEqual(
                    saved_world.citizens[0].experiments.active.hypothesis,
                    "A modest price change improves net sales.",
                )
                self.assertEqual(
                    saved_world.citizens[0].memory.episodes[0].value,
                    -0.1,
                )
                self.assertEqual(
                    saved_world.citizens[0].knowledge.query(
                        concept="market_momentum",
                        other_concept="realized_return",
                        context={"asset": "KOTA"},
                        status="validated",
                    )[0].status,
                    "validated",
                )
                self.assertFalse(path.with_name(path.name + ".tmp").exists())
                self.assertIn("GAME TERSIMPAN", app.scene.messages)

    def test_failed_save_preserves_previous_save_and_reports_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "slot1.sav"
            path.write_bytes(b"previous save")
            with patch("main.SAVE_PATH", path), patch(
                    "main.pickle.dump", side_effect=pickle.PicklingError("test failure")):
                app = self.make_app()

                self.assertFalse(app.save_world(World(seed=7, n_pop=12)))

                self.assertEqual(path.read_bytes(), b"previous save")
                self.assertFalse(path.with_name(path.name + ".tmp").exists())
                self.assertIn("GAGAL MENYIMPAN", app.scene.messages[-1])

    def test_invalid_save_is_reported_without_replacing_current_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "slot1.sav"
            path.write_bytes(b"invalid save")
            with patch("main.SAVE_PATH", path):
                app = self.make_app()
                old_scene = app.scene

                self.assertFalse(app.load_game())

                self.assertIs(app.scene, old_scene)
                self.assertIn("GAGAL MEMUAT SAVE", app.scene.messages[-1])

    def test_save_loader_rejects_unapproved_globals_without_executing_them(self):
        global _UNPICKLE_EXECUTED
        _UNPICKLE_EXECUTED = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "slot1.sav"
            path.write_bytes(pickle.dumps(MaliciousSave(), protocol=4))
            with patch("main.SAVE_PATH", path):
                app = self.make_app()

                self.assertFalse(app.load_game())

                self.assertFalse(_UNPICKLE_EXECUTED)
                self.assertIn("GAGAL MEMUAT SAVE", app.scene.messages[-1])

    def test_valid_world_save_loads_into_game_scene(self):
        world = World(seed=19, n_pop=12)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "slot1.sav"
            with path.open("wb") as save_file:
                pickle.dump(world, save_file, protocol=4)

            def create_scene(app, loaded):
                scene = MessageScene()
                scene.world = loaded
                return scene

            with patch("main.SAVE_PATH", path), patch(
                    "main.GameScene", side_effect=create_scene):
                app = self.make_app()

                self.assertTrue(app.load_game())

                self.assertEqual(app.scene.world.seed, world.seed)
                self.assertTrue(hasattr(app.scene.world, "ledger"))
                self.assertIn("SAVE BERHASIL DIMUAT", app.scene.messages)

    def test_future_save_schema_is_rejected_without_replacing_scene(self):
        world = World(seed=23, n_pop=12)
        payload = {
            "format": SAVE_FORMAT,
            "schema_version": SAVE_SCHEMA_VERSION + 1,
            "world": world,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "slot1.sav"
            with path.open("wb") as save_file:
                pickle.dump(payload, save_file, protocol=4)

            with patch("main.SAVE_PATH", path):
                app = self.make_app()
                old_scene = app.scene

                self.assertFalse(app.load_game())

                self.assertIs(app.scene, old_scene)
                self.assertIn("Versi skema save tidak didukung", app.scene.messages[-1])

    def test_v1_save_schema_migrates_to_current_version(self):
        world = World(seed=24, n_pop=12)
        for citizen in world.citizens:
            del citizen.bdi
            del citizen.adaptive_learning
        payload = {
            "format": SAVE_FORMAT,
            "schema_version": 1,
            "world": world,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "slot1.sav"
            with path.open("wb") as save_file:
                pickle.dump(payload, save_file, protocol=4)

            def create_scene(app, loaded):
                scene = MessageScene()
                scene.world = loaded
                return scene

            with patch("main.SAVE_PATH", path), patch(
                    "main.GameScene", side_effect=create_scene):
                app = self.make_app()

                self.assertTrue(app.load_game())

                self.assertEqual(
                    app.scene.world.ledger.schema_version,
                    world.ledger.schema_version,
                )
                self.assertTrue(all(
                    hasattr(citizen, "bdi")
                    for citizen in app.scene.world.citizens
                ))
                self.assertTrue(all(
                    hasattr(citizen, "adaptive_learning")
                    for citizen in app.scene.world.citizens
                ))

    def test_ledger_schema_mismatch_is_rejected(self):
        world = World(seed=25, n_pop=12)
        payload = {
            "format": SAVE_FORMAT,
            "schema_version": SAVE_SCHEMA_VERSION,
            "ledger_schema_version": world.ledger.schema_version + 1,
            "world": world,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "slot1.sav"
            with path.open("wb") as save_file:
                pickle.dump(payload, save_file, protocol=4)

            with patch("main.SAVE_PATH", path):
                app = self.make_app()
                old_scene = app.scene

                self.assertFalse(app.load_game())

                self.assertIs(app.scene, old_scene)
                self.assertIn("versi ledger tidak cocok", app.scene.messages[-1])

    def test_restricted_loader_supports_business_and_loan_save_graphs(self):
        world = World(seed=20, n_pop=12)
        owner = world.citizens[0]
        world.set_cash(owner, 40_000_000)
        self.assertTrue(world.found_business(owner, "farm", force=True))
        world.make_loan(owner, 500_000, 0.1, 12, "personal")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "slot1.sav"
            with patch("main.SAVE_PATH", path):
                app = self.make_app()
                self.assertTrue(app.save_world(world))

                def create_scene(app, loaded):
                    scene = MessageScene()
                    scene.world = loaded
                    return scene

                with patch("main.GameScene", side_effect=create_scene):
                    self.assertTrue(app.load_game())

                loaded = app.scene.world
                self.assertEqual(loaded.citizens[0].business.kind, "farm")
                self.assertEqual(len(loaded.loans), len(world.loans))
                self.assertIs(loaded.citizens[0].business.owner, loaded.citizens[0])


if __name__ == "__main__":
    unittest.main()
