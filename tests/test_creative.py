"""Creative tools are tested without contacting Gemini or charging credits."""

import base64
import io

import pytest
from PIL import Image

from src import creative
from src.creative_api import DraftRequest, ImageRequest


@pytest.mark.parametrize("model_id,mode,duration", [
    ("ltx-2.3-distilled", "t2v", 10),
    ("ltx-2.3-distilled", "i2v", 5),
    ("wan-2.2", "t2v", 5),
    ("hunyuanvideo-1.5", "t2v", 5),
    ("cogvideox-1.5", "t2v", 5),
])
def test_draft_uses_supported_profile_and_guidance(monkeypatch, model_id, mode, duration):
    captured = {}

    def fake_generate(model, parts, **kwargs):
        captured.update(model=model, parts=parts, kwargs=kwargs)
        return {"parts": [{"text": '{"prompt":"A dancer turns as the camera moves closer.",'
                                    '"summary":"Clear action and camera motion."}'}]}

    monkeypatch.setattr(creative, "_generate", fake_generate)
    result = creative.optimize_prompt(model_id=model_id, mode=mode, idea="A dancer",
                                      duration_seconds=duration)
    assert result["model_id"] == model_id
    assert result["mode"] == mode
    assert result["resolution"]
    assert "MODEL GUIDANCE" in captured["parts"][0]["text"]
    if model_id == "ltx-2.3-distilled":
        assert "LTX-2.3 Prompting Guide" in captured["parts"][0]["text"]
    if model_id == "wan-2.2":
        assert "Wan 2.2 prompting" in captured["parts"][0]["text"]


def test_request_rejects_image_for_text_only_model():
    with pytest.raises(ValueError):
        DraftRequest(model_id="wan-2.2", mode="i2v", idea="Move", input_asset_id="asset_123")


def test_image_request_rejects_blank_prompt():
    with pytest.raises(ValueError):
        ImageRequest(prompt="   ")


def test_image_generation_uses_reference_and_returns_bytes(monkeypatch):
    output = io.BytesIO()
    Image.new("RGB", (256, 256), "blue").save(output, format="PNG")
    captured = {}

    def fake_generate(model, parts, **kwargs):
        captured.update(model=model, parts=parts, kwargs=kwargs)
        return {"parts": [{"inlineData": {"mimeType": "image/png",
                                          "data": base64.b64encode(output.getvalue()).decode()}}]}

    monkeypatch.setattr(creative, "_generate", fake_generate)
    mime, data = creative.create_image(prompt="A blue scene", source_image=("image/png", output.getvalue()))
    assert mime == "image/png"
    assert data == output.getvalue()
    assert captured["kwargs"]["image"] is True
    assert "inline_data" in captured["parts"][1]


def test_malformed_draft_is_not_returned(monkeypatch):
    monkeypatch.setattr(creative, "_generate", lambda *_args, **_kwargs: {"parts": [{"text": "no json"}]})
    with pytest.raises(creative.GeminiError):
        creative.optimize_prompt(model_id="ltx-2.3-distilled", mode="t2v",
                                 idea="A mountain", duration_seconds=10)
