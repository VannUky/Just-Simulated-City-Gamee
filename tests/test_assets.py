import os
from pathlib import Path
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.assets import Assets


class AssetLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.display.quit()

    def test_loads_palette_from_atlas_metadata(self):
        root = Path(__file__).resolve().parents[1] / "assets"

        assets = Assets(root)

        self.assertEqual(assets.pal["O"], (30, 27, 46))
        self.assertEqual(assets.pal["W"], (248, 249, 250))
