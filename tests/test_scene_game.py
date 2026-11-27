import unittest
from types import SimpleNamespace

import pygame

from game.scene_game import GameScene
from systems.ekonomi_core import World


class CitizenDirectoryTests(unittest.TestCase):
    def test_directory_search_is_case_insensitive_and_keeps_wealth_order(self):
        world = World(seed=8, n_pop=12)
        rich, poor, unrelated = world.citizens[:3]
        rich.name = "Siti Rahma"
        poor.name = "Siti Aulia"
        unrelated.name = "Rama Putra"
        rich.cash = 2_000_000
        poor.cash = 1_000_000
        scene = object.__new__(GameScene)
        scene.world = world
        scene.people_query = "sItI"

        results = scene.citizen_directory()

        self.assertEqual(results, [rich, poor])
        scene.people_query = "rama"
        self.assertEqual(scene.citizen_directory(), [unrelated])

    def test_empty_query_lists_all_citizens_by_net_worth(self):
        world = World(seed=9, n_pop=12)
        scene = object.__new__(GameScene)
        scene.world = world
        scene.people_query = ""

        results = scene.citizen_directory()

        self.assertEqual(len(results), len(world.citizens))
        self.assertEqual(
            [citizen.networth for citizen in results],
            sorted((citizen.networth for citizen in world.citizens), reverse=True),
        )

    def test_search_keyboard_input_does_not_trigger_game_shortcuts(self):
        scene = object.__new__(GameScene)
        scene.prompt = None
        scene.sel = None
        scene.tab = 0
        scene.people_search_focus = True
        scene.people_query = ""

        scene.event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="s"))
        self.assertEqual(scene.people_query, "s")
        self.assertTrue(scene.people_search_focus)

        scene.event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode=""))
        self.assertEqual(scene.people_query, "")
        scene.event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r"))
        self.assertFalse(scene.people_search_focus)


class MapNavigationTests(unittest.TestCase):
    class ClickRecorder:
        def click(self, pos):
            return False

    def make_scene(self):
        scene = object.__new__(GameScene)
        scene.camera_x = 100
        scene.camera_y = 50
        scene.map_w = 1280
        scene.map_h = 800
        scene.pan_anchor = None
        scene.prompt = None
        scene.sel = None
        scene.tab = 0
        scene.profile_drag = None
        scene.people_search_focus = False
        scene.menu_open = False
        scene.window = None
        scene.ui = self.ClickRecorder()
        scene.map_clicks = []
        scene.click_map = scene.map_clicks.append
        return scene

    def test_camera_pans_and_clamps_both_axes(self):
        scene = self.make_scene()

        scene.pan_by(40, 30)
        self.assertEqual((scene.camera_x, scene.camera_y), (140, 80))
        scene.pan_by(10_000, 10_000)
        self.assertEqual((scene.camera_x, scene.camera_y),
                         (scene.map_w - 992, scene.map_h - 640))
        scene.pan_by(-10_000, -10_000)
        self.assertEqual((scene.camera_x, scene.camera_y), (0, 0))

    def test_left_drag_pans_horizontally_without_selecting_a_lot(self):
        scene = self.make_scene()

        scene.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(400, 200)))
        scene.event(pygame.event.Event(pygame.MOUSEMOTION, pos=(340, 230), rel=(-60, 30), buttons=(1, 0, 0)))
        scene.event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(340, 230)))

        self.assertEqual((scene.camera_x, scene.camera_y), (160, 20))
        self.assertEqual(scene.map_clicks, [])

    def test_left_click_without_drag_still_selects_map_target(self):
        scene = self.make_scene()
        pos = (400, 200)

        scene.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        scene.event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))

        self.assertEqual(scene.map_clicks, [(500, 214)])

    def test_dragging_open_citizen_profile_does_not_pan_map(self):
        scene = self.make_scene()
        scene.sel = object()
        scene.tab = 1
        scene.profile_pos = [200, 80]
        scene.profile_drag = None
        start_camera = (scene.camera_x, scene.camera_y)

        scene.event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=(240, 95)
        ))
        scene.event(pygame.event.Event(
            pygame.MOUSEMOTION, pos=(320, 105), rel=(80, 10), buttons=(1, 0, 0)
        ))
        scene.event(pygame.event.Event(
            pygame.MOUSEBUTTONUP, button=1, pos=(320, 105)
        ))

        self.assertEqual((scene.camera_x, scene.camera_y), start_camera)
        self.assertEqual(scene.profile_pos, [280, 90])


class CitizenProfileLayoutTests(unittest.TestCase):
    class RecordingUI:
        def __init__(self):
            self.screen = pygame.Surface((1280, 720))
            self.text_calls = []
            self.button_rects = []

        def shadow_panel(self, *args):
            pass

        def bmp(self, *args):
            pass

        def text(self, text, pos, *args):
            self.text_calls.append((text, pos))

        def button(self, rect, *args):
            self.button_rects.append(pygame.Rect(rect))

        def panel(self, *args):
            pass

        def bar(self, *args):
            pass

    def test_observation_text_stays_above_cash_buttons(self):
        world = World(seed=10, n_pop=1)
        scene = object.__new__(GameScene)
        scene.ui = self.RecordingUI()
        scene.world = world
        scene.sel = world.citizens[0]
        scene.profile_pos = [390, 60]
        scene.cv = SimpleNamespace(views={})

        scene.draw_citizen_profile()

        observation_positions = [
            pos[1] for text, pos in scene.ui.text_calls
            if text == "OBSERVASI AGEN" or text.startswith(("Tujuan:", "Niat:"))
            or "konteks ·" in text
        ]
        button_top = max(rect.top for rect in scene.ui.button_rects)
        self.assertLessEqual(max(observation_positions) + 12, button_top)


if __name__ == "__main__":
    unittest.main()
