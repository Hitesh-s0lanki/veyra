"""Checks the expensive boundaries of concept planning and clip assembly."""

import io
import json
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src import concept_media, concepts


def test_scene_plan_must_match_requested_length():
    plan = concepts.Plan(title="Journey", summary="A three-part journey", scenes=[
        concepts.Scene(title=f"Beat {index}", duration_seconds=20,
                       image_prompt="A mountain at dawn", motion_prompt="The camera moves toward the mountain")
        for index in range(3)
    ])
    concepts._validate_plan(plan, 60)
    with pytest.raises(HTTPException) as error:
        concepts._validate_plan(plan, 45)
    assert error.value.status_code == 422


def test_concept_reply_rejects_a_plan_with_wrong_total(monkeypatch):
    monkeypatch.setenv("CONCEPT_TEXT_PROVIDER", "openai")
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return json.dumps({"choices": [{"message": {"content": json.dumps({
                "reply": "Here is the plan", "ready": True, "title": "Journey", "summary": "A journey",
                "scenes": [{"title": "Opening", "duration_seconds": 20,
                            "image_prompt": "A mountain at dawn", "motion_prompt": "The camera moves"}],
            })}}]}).encode()

    monkeypatch.setattr(concepts, "require_env", lambda _name: "test-key")
    monkeypatch.setattr(concepts, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    with pytest.raises(HTTPException) as error:
        concepts._ask_text_model({"target_seconds": 60, "aspect": "landscape", "plan": None},
                                 [{"role": "user", "content": "A mountain journey"}])
    assert error.value.status_code == 502


def test_gemini_concept_reply_returns_valid_plan(monkeypatch):
    monkeypatch.setenv("CONCEPT_TEXT_PROVIDER", "gemini")
    monkeypatch.setenv("CONCEPT_GEMINI_API_KEY", "sandbox-key")
    content = json.dumps({"reply": "Here is your storyboard", "ready": True,
                          "title": "Lake", "summary": "A quiet sunrise",
                          "scenes": [{"title": "Dawn", "duration_seconds": 10,
                                      "image_prompt": "A mountain lake at dawn",
                                      "motion_prompt": "The camera glides over the water"}]})
    passed = {}

    def fake_generate(*_args, **kwargs):
        passed.update(kwargs)
        return {"parts": [{"text": content}]}

    monkeypatch.setattr(concepts.creative, "_generate", fake_generate)
    reply, plan, question = concepts._ask_text_model({"target_seconds": 10, "aspect": "landscape", "plan": None},
                                                     [{"role": "user", "content": "Mountain lake"}])
    assert reply == "Here is your storyboard"
    assert plan["scenes"][0]["duration_seconds"] == 10
    assert question is None
    assert passed["api_key"] == "sandbox-key"


def test_modal_concept_chat_uses_glm_endpoint_and_server_token(monkeypatch):
    monkeypatch.setenv("CONCEPT_TEXT_PROVIDER", "modal")
    monkeypatch.setenv("MODAL_PROXY_TOKEN_ID", "test-id")
    monkeypatch.setenv("MODAL_PROXY_TOKEN_SECRET", "test-secret")
    monkeypatch.delenv("MODAL_CONCEPT_BASE_URL", raising=False)
    monkeypatch.delenv("MODAL_CONCEPT_MODEL", raising=False)
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return json.dumps({"choices": [{"message": {"content": json.dumps({
                "reply": "Tell me about the setting.", "ready": False, "scenes": [],
                "question": {"prompt": "Where does it take place?", "options": [
                    {"label": "Forest"}, {"label": "City"}]},
            })}}]}).encode()

    def fake_urlopen(request, timeout):
        captured.update(url=request.full_url, authorization=request.get_header("Authorization"),
                        payload=json.loads(request.data), timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(concepts, "urlopen", fake_urlopen)
    reply, plan, question = concepts._ask_text_model(
        {"target_seconds": 10, "aspect": "landscape", "plan": None},
        [{"role": "user", "content": "A story in a changing landscape"}])
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["authorization"] == "Bearer test-id.test-secret"
    assert captured["payload"]["model"] == "zai-org/GLM-5.3-Flash"
    assert captured["payload"]["max_tokens"] == 8192
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert reply == "Tell me about the setting."
    assert plan is None
    assert question["options"][0]["label"] == "Forest"


def test_concept_clarification_returns_answer_choices(monkeypatch):
    monkeypatch.setenv("CONCEPT_TEXT_PROVIDER", "gemini")
    content = json.dumps({"reply": "The setting is clear.", "ready": False, "scenes": [],
                          "question": {"prompt": "Who is this for?", "options": [
                              {"label": "Young children", "description": "Playful and simple"},
                              {"label": "All ages", "description": "Broad family appeal"}]}})
    monkeypatch.setattr(concepts.creative, "_generate", lambda *_args, **_kwargs: {"parts": [{"text": content}]})
    reply, plan, question = concepts._ask_text_model(
        {"target_seconds": 45, "aspect": "landscape", "plan": None},
        [{"role": "user", "content": "A kite story"}])
    assert reply == "The setting is clear."
    assert plan is None
    assert question == {"prompt": "Who is this for?", "options": [
        {"label": "Young children", "description": "Playful and simple"},
        {"label": "All ages", "description": "Broad family appeal"}]}


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg unavailable")
def test_assembly_concatenates_mixed_audio_clips(monkeypatch, tmp_path: Path):
    clips = []
    for index in range(2):
        path = tmp_path / f"input-{index}.mp4"
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-f", "lavfi", "-i", f"color=c={'red' if index == 0 else 'blue'}:s=320x240:r=24:d=1"]
        if index == 0:
            command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1", "-shortest"]
        command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
        subprocess.run(command, check=True, capture_output=True, timeout=30)
        clips.append(path.read_bytes())

    class Body(io.BytesIO):
        def iter_chunks(self, chunk_size):
            while chunk := self.read(chunk_size):
                yield chunk

    uploaded = {}

    class FakeS3:
        def get_object(self, *, Key, **_kwargs):
            return {"Body": Body(clips[int(Key[-1])])}

        def upload_file(self, source, _bucket, key, ExtraArgs):
            uploaded["data"] = Path(source).read_bytes()
            uploaded["key"] = key
            assert ExtraArgs["ContentType"] == "video/mp4"

    @contextmanager
    def fake_connection():
        yield SimpleNamespace()

    monkeypatch.setattr(concepts.db, "connection", fake_connection)
    monkeypatch.setattr(concepts.db, "owned_job", lambda _conn, job_id, _user: {
        "status": "succeeded", "output_key": f"source-{job_id[-1]}"})
    monkeypatch.setattr(concepts.storage, "client", lambda: FakeS3())
    monkeypatch.setattr(concepts.storage, "bucket", lambda: "test-bucket")

    scenes = [{"position": index, "duration_seconds": 5, "job_id": f"job-{index}"} for index in range(2)]
    key = concept_media.assemble({"id": "con_test", "user_id": "user_test", "aspect": "landscape"}, scenes)
    assert key == "concepts/user_test/con_test/final.mp4"
    output = tmp_path / "result.mp4"
    output.write_bytes(uploaded["data"])
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-show_entries", "stream=codec_type", "-of", "json", str(output)],
                           check=True, capture_output=True, text=True, timeout=30)
    metadata = json.loads(probe.stdout)
    assert 9.5 <= float(metadata["format"]["duration"]) <= 10.5
    assert {stream["codec_type"] for stream in metadata["streams"]} == {"video", "audio"}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg unavailable")
def test_extract_last_frame(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=blue:s=320x568:r=24:d=1", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(source)], check=True, capture_output=True, timeout=30)

    class Body(io.BytesIO):
        def iter_chunks(self, chunk_size):
            while chunk := self.read(chunk_size):
                yield chunk

    monkeypatch.setattr(concept_media.storage, "client", lambda: SimpleNamespace(
        get_object=lambda **_kwargs: {"Body": Body(source.read_bytes())}))
    monkeypatch.setattr(concept_media.storage, "bucket", lambda: "test-bucket")
    from PIL import Image
    with Image.open(io.BytesIO(concept_media.extract_last_frame("clip.mp4"))) as frame:
        assert frame.size == (320, 568)
