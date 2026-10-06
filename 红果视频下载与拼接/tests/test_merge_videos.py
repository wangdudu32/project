import shutil
import sys
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import merge_videos


class MergeVideosTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(__import__("tempfile").gettempdir()) / f"merge-videos-test-{uuid.uuid4().hex[:10]}"
        self.directory.mkdir()

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_episode_number_and_numeric_order(self):
        self.assertEqual(merge_videos.episode_number(Path("第2集.mp4")), 2)
        self.assertEqual(merge_videos.episode_number(Path("EP010-title.mkv")), 10)
        self.assertEqual(merge_videos.episode_number(Path("S02E003.mp4")), 3)
        self.assertEqual(merge_videos.episode_number(Path("001.mp4")), 1)

        for name in ("第10集.mp4", "第2集.mp4", "第1集.mp4"):
            (self.directory / name).write_bytes(b"placeholder")
        ordered = merge_videos.discover(self.directory)
        self.assertEqual([number for number, _ in ordered], [1, 2, 10])

    def test_duplicate_and_unrecognised_files_are_rejected(self):
        (self.directory / "第1集.mp4").write_bytes(b"x")
        (self.directory / "第01集.mkv").write_bytes(b"x")
        with self.assertRaises(merge_videos.MergeError) as duplicate:
            merge_videos.discover(self.directory)
        self.assertIn("重复", str(duplicate.exception))

        (self.directory / "第01集.mkv").unlink()
        (self.directory / "cover.mp4").write_bytes(b"x")
        with self.assertRaises(merge_videos.MergeError) as unknown:
            merge_videos.discover(self.directory)
        self.assertIn("无法识别集数", str(unknown.exception))

    def test_missing_ranges(self):
        self.assertEqual(merge_videos.missing_ranges([1, 2, 5, 8, 9]), ["3–4", "6–7"])
        self.assertEqual(merge_videos.missing_ranges([2, 4]), ["1", "3"])

    def test_output_is_ignored_when_discovering_again(self):
        (self.directory / "第1集.mp4").write_bytes(b"x")
        (self.directory / f"{self.directory.name}_全集.mp4").write_bytes(b"merged")
        self.assertEqual([number for number, _ in merge_videos.discover(self.directory)], [1])


if __name__ == "__main__":
    unittest.main()
