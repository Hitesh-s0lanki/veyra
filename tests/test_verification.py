import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.verification import (
    SPEAKER_ID,
    TRIMMER_ID,
    build_report,
    get_challenge,
    validate_event_order,
)


class VerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.video = Path(cls.directory.name) / "vertical.mp4"
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                "color=c=black:s=144x256:r=1:d=25", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", str(cls.video),
            ],
            check=True,
        )
        cls.with_audio = Path(cls.directory.name) / "with-audio.mp4"
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                "color=c=black:s=144x256:r=1:d=25", "-f", "lavfi", "-i",
                "sine=frequency=440:sample_rate=16000:duration=25", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cls.with_audio),
            ],
            check=True,
        )
        cls.landscape = Path(cls.directory.name) / "landscape.mp4"
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                "color=c=black:s=256x144:r=1:d=35", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", str(cls.landscape),
            ],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_trimmer_report_checks_format_without_requiring_audio(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            report = build_report("test", get_challenge(TRIMMER_ID), "All Rounder Trimmer", self.video)
        self.assertEqual(report["decision"]["status"], "review")
        self.assertEqual([item["status"] for item in report["challenge_checks"][:2]], ["pass", "pass"])
        self.assertEqual(report["audio"]["mode"], "hygiene_only")
        self.assertEqual(report["audio"]["hygiene_checks"][0]["status"], "skipped")
        detailed = report["challenge_checks"] + report["audio"]["semantic_checks"] + report["audio"]["hygiene_checks"] + report["additional_checks"]
        expected = [{"id": item["id"], "status": item["status"], "reason": item["reason"]} for item in detailed if item["status"] in {"fail", "review"}]
        self.assertEqual(report["not_passed_checks"], expected)

    def test_speaker_without_audio_fails_music_requirement(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            report = build_report("test", get_challenge(SPEAKER_ID), "boAt Stone 358 Pro", self.video)
        self.assertEqual(report["audio"]["mode"], "checklist_required")
        self.assertEqual(report["audio"]["semantic_checks"][0]["status"], "fail")
        self.assertEqual(report["decision"]["status"], "fail")

    def test_landscape_and_long_video_fail_objective_rules(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            report = build_report("test", get_challenge(TRIMMER_ID), "All Rounder Trimmer", self.landscape)
        self.assertEqual(report["decision"]["status"], "fail")
        self.assertEqual([item["status"] for item in report["challenge_checks"][:2]], ["fail", "fail"])
        self.assertEqual(report["additional_checks"][0]["status"], "pass")

    def test_present_audio_gets_hygiene_check_without_speech_check(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            report = build_report("test", get_challenge(TRIMMER_ID), "All Rounder Trimmer", self.with_audio)
        self.assertTrue(report["media"]["has_audio"])
        self.assertEqual(report["audio"]["hygiene_checks"][0]["status"], "pass")
        self.assertEqual(report["audio"]["semantic_checks"], [])

    def test_unreadable_video_is_excluded(self):
        invalid = Path(self.directory.name) / "invalid.mp4"
        invalid.write_bytes(b"not a video")
        report = build_report("test", get_challenge(TRIMMER_ID), "All Rounder Trimmer", invalid)
        self.assertEqual(report["decision"]["status"], "excluded")
        self.assertEqual(report["additional_checks"][0]["policy_id"], "platform.video_fully_decodable")

    def test_model_pass_needs_distinct_timestamps(self):
        findings = {
            "two_to_three_trimming_shots": {
                "id": "two_to_three_trimming_shots", "status": "pass", "reason": "Two shots.",
                "evidence": [{"start_seconds": 5, "end_seconds": 7, "source": "video"}],
            }
        }
        validate_event_order(findings, TRIMMER_ID)
        self.assertEqual(findings["two_to_three_trimming_shots"]["status"], "review")


if __name__ == "__main__":
    unittest.main()
