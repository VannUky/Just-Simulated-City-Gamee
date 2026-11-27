import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import (
    App, RestrictedSaveUnpickler, SAVE_FORMAT, SAVE_SCHEMA_VERSION,
)
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
