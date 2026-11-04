import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input"
        self.source.mkdir()
        for index in [10, 2, 1]:
            image = Image.new("RGBA", (20, 20))
            image.paste((index * 20, 50, 100, 255), (5, 5, 15, 15))
            image.save(self.source / f"frame{index}.png")

    def build(self, **changes):
        spec = importlib.util.find_spec("frame_workbench.pipeline")
        self.assertIsNotNone(spec, "public pipeline build API must exist")
        from frame_workbench.pipeline import build

        config = {"source": {"type": "directory", "path": "input", "allow_gaps": True}, "canvas": [40, 20]}
        config.update(changes)
        path = self.root / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        output = self.root / "output"
        return build(path, output), output

    def test_natural_order_ratio_alpha_and_all_exports(self):
        manifest, output = self.build(exports=["png", "sheet", "gif", "webp", "ora"])
        self.assertEqual([f["source_name"] for f in manifest["frames"]], ["frame1.png", "frame2.png", "frame10.png"])
        with Image.open(output / "frames/0000.png") as image:
            self.assertEqual(image.size, (40, 20))
            self.assertEqual(image.getbbox(), (10, 0, 30, 20))
            self.assertEqual(image.getpixel((0, 0))[3], 0)
        for filename in [
            "sheet.png",
            "animation.gif",
            "animation.webp",
            "layers.ora",
            "manifest.json",
            "quality.json",
            "preview.html",
        ]:
            self.assertTrue((output / filename).is_file(), filename)
        self.assertIn("data:image/png;base64,", (output / "preview.html").read_text(encoding="utf-8"))
        with zipfile.ZipFile(output / "layers.ora") as archive:
            self.assertEqual(archive.read("mimetype"), b"image/openraster")

    def test_sequence_durations_and_per_frame_transform(self):
        manifest, output = self.build(
            sequence=[0, 1, 0], durations_ms=[80, 120, 200], frames={"1": {"scale": 0.5, "offset": [3, -2]}}
        )
        self.assertEqual([f["source_index"] for f in manifest["frames"]], [0, 1, 0])
        self.assertEqual([f["duration_ms"] for f in manifest["frames"]], [80, 120, 200])
        with Image.open(output / "frames/0001.png") as image:
            self.assertEqual(image.getbbox(), (18, 8, 28, 18))

    def test_analysis_patch_uses_source_indices_and_preserves_long_holds(self):
        manifest, output = self.build(sequence=[2, 2, 0], durations_ms=[60000, 10, 120], exports=["png"])
        report = json.loads((output / "quality.json").read_text())
        patch = report["analysis"]["duplicates"]["config_patch"]
        self.assertEqual(patch["sequence"], [2, 2, 0])
        self.assertEqual(sum(patch["durations_ms"]), 60130)
        self.assertTrue(all(10 <= value <= 60000 for value in patch["durations_ms"]))
        self.assertEqual(manifest["frame_count"], 3)
        self.assertEqual(json.loads((output / "suggested-config.json").read_text()), patch)

    def test_nearest_resampling_keeps_pixel_palette_and_analysis_can_be_disabled(self):
        _, output = self.build(resample="nearest", analysis={"enabled": False})
        report = json.loads((output / "quality.json").read_text())
        self.assertIsNone(report["analysis"])
        with Image.open(output / "frames/0000.png") as image:
            self.assertEqual(set(image.getchannel("A").tobytes()), {0, 255})
        self.assertFalse((output / "suggested-config.json").exists())

    def test_invalid_analysis_and_resample_options_are_rejected(self):
        for changes in [{"resample": "linear"}, {"analysis": True}, {"analysis": {"enabled": 1}},
                        {"analysis": {"duplicate_threshold": -1}}, {"analysis": {"typo": True}}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.build(**changes)

    def test_explicit_anchor_without_trim(self):
        _, output = self.build(trim=False, anchor=[0, 0], target_anchor=[0, 0], scale=0.5)
        with Image.open(output / "frames/0000.png") as image:
            self.assertEqual(image.size, (40, 20))
            self.assertGreater(image.getpixel((4, 4))[3], 240)

    def test_pixel_anchor_keeps_feet_fixed_when_arm_changes_bounds(self):
        image = Image.new("RGBA", (20, 20))
        image.paste((255, 0, 0, 255), (5, 5, 15, 15))
        image.paste((255, 0, 0, 255), (15, 5, 20, 7))
        image.save(self.source / "frame2.png")
        manifest, _ = self.build(source_anchor=[10, 15], canvas=[40, 40])
        for record in manifest["frames"]:
            crop = record["source_bounds"]
            sx = record["scaled_size"][0] / (crop[2] - crop[0])
            sy = record["scaled_size"][1] / (crop[3] - crop[1])
            self.assertAlmostEqual(record["placement"][0] + (10 - crop[0]) * sx, 20, delta=1)
            self.assertAlmostEqual(record["placement"][1] + (15 - crop[1]) * sy, 40, delta=1)

    def test_zip_and_sheet_import(self):
        archive = self.root / "input.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for path in self.source.glob("*.png"):
                zf.write(path, f"frames/{path.name}")
        result, output = self.build(source={"type": "zip", "path": "input.zip", "allow_gaps": True})
        self.assertEqual(len(result["frames"]), 3)
        import shutil

        shutil.rmtree(output)
        sheet = Image.new("RGBA", (40, 20))
        sheet.paste((255, 0, 0, 255), (0, 0, 20, 20))
        sheet.paste((0, 255, 0, 255), (20, 0, 40, 20))
        sheet.save(self.root / "sheet.png")
        result, _ = self.build(source={"type": "sheet", "path": "sheet.png", "cell": [20, 20], "count": 2})
        self.assertEqual(len(result["frames"]), 2)

    def test_invalid_sequence_never_publishes_output(self):
        with self.assertRaises(ValueError):
            self.build(sequence=[9])
        self.assertFalse((self.root / "output").exists())

    def test_refuses_existing_output_and_preserves_contents(self):
        output = self.root / "output"
        output.mkdir()
        (output / "keep").write_text("original")
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual((output / "keep").read_text(), "original")

    def test_rejects_traversal_zip_unknown_keys_and_huge_canvas(self):
        with zipfile.ZipFile(self.root / "bad.zip", "w") as archive:
            archive.writestr("../escape.png", b"bad")
        for changes in [{"source": {"type": "zip", "path": "bad.zip"}}, {"typo": True}, {"canvas": [99999, 99999]}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.build(**changes)
        self.assertFalse((self.root / "output").exists())

    def test_empty_frame_has_quality_warning(self):
        Image.new("RGBA", (20, 20)).save(self.source / "frame3.png")
        _, output = self.build()
        quality = json.loads((output / "quality.json").read_text())
        self.assertTrue(any("empty" in warning for warning in quality["warnings"]))

    def test_missing_number_rejected_unless_explicitly_allowed(self):
        with self.assertRaisesRegex(ValueError, "number"):
            self.build(source={"type": "directory", "path": "input"})
        self.assertFalse((self.root / "output").exists())

    def test_duplicate_number_rejected_even_when_gaps_allowed(self):
        Image.new("RGBA", (20, 20)).save(self.source / "frame01.png")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.build()

    def test_clipping_alpha_and_loop_diagnostics(self):
        Image.new("RGB", (20, 20), "red").save(self.source / "frame3.png")
        _, output = self.build(offset=[30, 0])
        quality = json.loads((output / "quality.json").read_text(encoding="utf-8"))
        self.assertGreater(quality["checks"]["clipped_frames"], 0)
        self.assertEqual(quality["checks"]["opaque_sources"], 1)
        self.assertIn("loop_rgba_mae", quality["metrics"])
        self.assertTrue(any("opaque" in warning for warning in quality["warnings"]))

    def test_corrupt_image_and_input_overlap_rejected(self):
        (self.source / "broken.png").write_bytes(b"not an image")
        with self.assertRaises(OSError):
            self.build()
        self.assertFalse((self.root / "output").exists())
        (self.source / "broken.png").unlink()
        from frame_workbench.pipeline import build

        config = self.root / "overlap.json"
        config.write_text(json.dumps({"source": {"type": "directory", "path": "input"}}))
        with self.assertRaisesRegex(ValueError, "overlap"):
            build(config, self.source / "output")

    def test_transient_windows_rename_lock_retries(self):
        import os
        from unittest.mock import patch

        original = os.rename
        calls = []

        def transient(source, target):
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError("transient antivirus lock")
            return original(source, target)

        with patch("frame_workbench.pipeline.os.rename", side_effect=transient):
            _, output = self.build()
        self.assertTrue(output.is_dir())
        self.assertEqual(len(calls), 2)

    def test_extreme_numeric_config_rejected_cleanly(self):
        with self.assertRaises(ValueError):
            self.build(scale=10**1000)

    def test_empty_frame_does_not_inherit_tiny_subject_resize(self):
        for file in self.source.glob("*.png"):
            file.unlink()
        image = Image.new("RGBA", (20, 20))
        image.putpixel((10, 10), (255, 0, 0, 255))
        image.save(self.source / "frame0.png")
        Image.new("RGBA", (20, 20)).save(self.source / "frame1.png")
        manifest, output = self.build(canvas=[256, 256])
        self.assertEqual(manifest["frame_count"], 2)
        with Image.open(output / "frames/0001.png") as empty:
            self.assertEqual(empty.size, (256, 256))
            self.assertIsNone(empty.getchannel("A").getbbox())

    def test_gif_merged_duration_limit_has_clean_cli_error(self):
        import contextlib
        import io
        from frame_workbench.cli import main

        with self.assertRaisesRegex(ValueError, "GIF"):
            self.build(sequence=[0] * 12, duration_ms=60000)
        self.assertFalse((self.root / "output").exists())
        self.assertEqual(list(self.root.glob(".output-*")), [])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["build", str(self.root / "config.json"), "--output", str(self.root / "output")])
        self.assertEqual(code, 2)
        self.assertIn("GIF", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_long_timeline_remains_supported_without_gif(self):
        manifest, _ = self.build(sequence=[0] * 12, duration_ms=60000, exports=["png", "webp"])
        self.assertEqual(manifest["total_duration_ms"], 720000)

    def test_action_id_and_once_policy_reach_manifest_and_encoders(self):
        manifest, output = self.build(action_id="wave-01", loop="once")
        self.assertEqual(manifest["action_id"], "wave-01")
        self.assertEqual(manifest["loop"], "once")
        with Image.open(output / "animation.gif") as image:
            self.assertNotIn("loop", image.info)
        with Image.open(output / "animation.webp") as image:
            self.assertEqual(image.info["loop"], 1)

    def test_infinite_policy_matches_gif_and_webp(self):
        manifest, output = self.build()
        self.assertEqual(manifest["loop"], "infinite")
        for filename in ["animation.gif", "animation.webp"]:
            with Image.open(output / filename) as image:
                self.assertEqual(image.info["loop"], 0)

    def test_rectangular_crop_preserves_original_pixel_anchor(self):
        manifest, output = self.build(crop=[8, 2, 18, 18], source_anchor=[10, 15], target_anchor=[0.5, 1], trim=False)
        record = manifest["frames"][0]
        self.assertEqual(record["crop_bounds"], [8, 2, 18, 18])
        self.assertAlmostEqual(record["placement"][0] + 2 * record["scaled_size"][0] / 10, 20, delta=0.6)
        self.assertAlmostEqual(record["placement"][1] + 13 * record["scaled_size"][1] / 16, 20, delta=0.6)
        with Image.open(output / "frames/0000.png") as image:
            self.assertLess(image.getchannel("A").getbbox()[2] - image.getchannel("A").getbbox()[0], 20)

    def test_preview_embeds_original_sequence_for_synchronized_comparison(self):
        import base64
        import io
        import re

        _, output = self.build(sequence=[2, 0, 2], loop="once")
        html = (output / "preview.html").read_text(encoding="utf-8")
        payload = json.loads(re.search(r"const data=(.*?);\n", html).group(1))
        self.assertEqual(payload["source_indices"], [2, 0, 2])
        self.assertEqual(payload["loop"], "once")
        with Image.open(io.BytesIO(base64.b64decode(payload["originals"][2].split(",")[1]))) as image:
            self.assertEqual(image.size, (20, 20))
            self.assertEqual(image.getpixel((6, 6)), (200, 50, 100, 255))
        self.assertIn('id="original"', html)

    def test_invalid_metadata_and_crop_rejected_without_output(self):
        for changes in [
            {"action_id": "../bad"},
            {"action_id": ""},
            {"loop": True},
            {"crop": [0, 0, 21, 20]},
            {"crop": [8, 8, 7, 12]},
            {"crop": [0, 0, 1.5, 5]},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.build(**changes)
        self.assertFalse((self.root / "output").exists())

    def test_export_failure_cleans_staging_and_preserves_inputs(self):
        from unittest.mock import patch

        def broken_export(output, *args):
            (output / "partial").write_text("partial")
            raise OSError("encoder failure")

        with patch("frame_workbench.pipeline.write", side_effect=broken_export):
            with self.assertRaises(OSError):
                self.build()
        self.assertFalse((self.root / "output").exists())
        self.assertEqual(list(self.root.glob(".output-*")), [])
        self.assertEqual(len(list(self.source.glob("*.png"))), 3)


if __name__ == "__main__":
    unittest.main()
