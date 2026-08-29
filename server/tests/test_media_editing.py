import subprocess
import tempfile
import unittest
from pathlib import Path

from app.media_editing import edit_video


class VideoEditingTest(unittest.TestCase):
    def test_trim_crop_rotate_produces_expected_video(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=size=64x48:rate=10",
                    "-t",
                    "1",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(source),
                ],
                check=True,
            )
            result = edit_video(
                content=source.read_bytes(),
                filename="source.mp4",
                start_seconds=0.2,
                end_seconds=0.8,
                crop_x=4,
                crop_y=4,
                crop_width=40,
                crop_height=32,
                rotate=90,
            )

        self.assertEqual((result.width, result.height), (32, 40))
        self.assertAlmostEqual(result.duration, 0.6, delta=0.15)
        self.assertGreater(result.frame_count, 0)
        self.assertTrue(result.content.startswith(b"\x00\x00\x00"))


if __name__ == "__main__":
    unittest.main()
