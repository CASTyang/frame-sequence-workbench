import importlib
import math
import unittest

from PIL import Image, ImageDraw


class MotionAnalysisTests(unittest.TestCase):
    def module(self):
        return importlib.import_module('frame_workbench.analysis')

    def pose(self, x, y=12):
        image = Image.new('RGBA', (48, 48))
        ImageDraw.Draw(image).rectangle((x, y, x + 7, y + 7), fill=(80, 160, 220, 255))
        return image

    def test_hidden_rgb_does_not_change_visual_distance(self):
        analysis = self.module()
        a = Image.new('RGBA', (48, 48), (255, 0, 0, 0))
        b = Image.new('RGBA', (48, 48), (0, 0, 255, 0))
        self.assertEqual(analysis.visual_distance(a, b), 0)
        b.putpixel((24, 24), (255, 255, 255, 255))
        self.assertGreater(analysis.visual_distance(a, b), 0)

    def test_adjacent_proposal_preserves_duration_and_does_not_remove_later_return(self):
        report = self.module().analyze([self.pose(4), self.pose(4), self.pose(20), self.pose(4)], [80, 120, 100, 150])
        proposal = report['duplicates']
        self.assertEqual(proposal['keep_positions'], [0, 2, 3])
        self.assertEqual(proposal['durations_ms'], [200, 100, 150])
        self.assertEqual(sum(proposal['durations_ms']), 450)

    def test_static_frames_are_not_suggested_as_motion_loops(self):
        report = self.module().analyze([self.pose(4)] * 8, [100] * 8)
        self.assertEqual(report['loop_candidates'], [])

    def test_closed_orbit_ranks_a_moving_cycle(self):
        frames = [self.pose(round(18 + 10 * math.cos(i * math.tau / 8)),
                            round(18 + 10 * math.sin(i * math.tau / 8))) for i in range(16)]
        report = self.module().analyze(frames, [100] * 16)
        self.assertTrue(report['loop_candidates'])
        best = report['loop_candidates'][0]
        self.assertIn(best['end'] - best['start'] + 1, [8, 16])
        self.assertLess(best['seam_ratio'], 2)

    def test_translation_not_reported_as_good_loop(self):
        report = self.module().analyze([self.pose(x) for x in range(0, 32, 4)], [100] * 8)
        self.assertFalse(any(item['rating'] == 'good' for item in report['loop_candidates']))

    def test_opaque_background_does_not_hide_translating_subject(self):
        frames = []
        for x in range(0, 32, 4):
            frame = Image.new('RGBA', (48, 48), 'black')
            frame.alpha_composite(self.pose(x))
            frames.append(frame)
        report = self.module().analyze(frames, [100] * 8)
        self.assertFalse(any(item['rating'] == 'good' for item in report['loop_candidates']))

    def test_uniform_timing_scale_does_not_improve_seam_rating(self):
        frames = [self.pose(x) for x in range(0, 32, 4)]
        normal = self.module().analyze(frames, [100] * 8)['loop_candidates']
        slow = self.module().analyze(frames, [10000] * 8)['loop_candidates']
        self.assertEqual(normal, [dict(item, duration_ms=item['duration_ms'] // 100) for item in slow])

    def test_sampled_boundaries_use_actual_seam_neighbors(self):
        positions = [round(i * 511 / 127) for i in range(128)]
        frames = [self.pose(0, 0) for _ in range(512)]
        for j, position in enumerate(positions):
            frames[position] = self.pose(round(18 + 10 * math.cos(j * math.tau * 4 / 63)),
                                         round(18 + 10 * math.sin(j * math.tau * 4 / 63)))
        report = self.module().analyze(frames, [100] * 512)
        candidate = report['loop_candidates'][0]
        start, end = candidate['start'], candidate['end']
        frames[start + 1] = frames[end]
        frames[end - 1] = frames[start]
        updated = self.module().analyze(frames, [100] * 512)
        self.assertFalse(any(item['start'] == start and item['end'] == end and item['rating'] == 'good'
                             for item in updated['loop_candidates']))

    def test_input_contract_and_analysis_budget(self):
        analysis = self.module()
        for frames, durations in [([], []), ([self.pose(4)], []), ([self.pose(4)], [0])]:
            with self.assertRaises(ValueError):
                analysis.analyze(frames, durations)
        report = analysis.analyze([self.pose(i % 30) for i in range(140)], [100] * 140)
        self.assertLessEqual(report['coverage']['loop_samples'], 128)
        self.assertEqual(report['coverage']['input_frames'], 140)


if __name__ == '__main__':
    unittest.main()
