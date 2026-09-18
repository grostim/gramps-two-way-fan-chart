"""Regression tests for issue #103 GEN1 text-driven sector sizing."""

import unittest

from TwoWayFanChart.layout import layout_descendants
from TwoWayFanChart.model import ScenePathText, SceneSector

from tests.test_descendant_readability import a0_canvas, branch


class FirstGenerationTextDemandTests(unittest.TestCase):
    def test_longer_gen1_identity_gets_a_larger_sector(self):
        short = branch("short", 1)
        long = branch("long", 1)
        scene = layout_descendants(
            a0_canvas(descendant_generations=1),
            (short, long),
            name_lookup={
                "short": "A",
                "long": "Alexandre Théodore de la Rochefoucauld",
            }.__getitem__,
        )

        sectors = [node for node in scene.children if isinstance(node, SceneSector)]
        self.assertEqual(len(sectors), 2)
        self.assertGreater(max(node.sweep_angle for node in sectors), min(node.sweep_angle for node in sectors))

    def test_measured_sector_keeps_the_gen1_target_font_size(self):
        root = branch("root", 1)
        scene = layout_descendants(
            a0_canvas(descendant_generations=1),
            (root,),
            name_lookup=lambda _handle: "Alexandre Théodore de la Rochefoucauld",
        )

        labels = [
            node
            for node in scene.children
            if isinstance(node, ScenePathText)
            and node.content == "Alexandre Théodore de la Rochefoucauld"
        ]
        self.assertTrue(labels)
        self.assertGreaterEqual(labels[0].font_size, 5.4)


if __name__ == "__main__":
    unittest.main()
