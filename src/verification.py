"""Local challenge verification and optional Gemini video review."""

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Literal
from urllib.request import urlopen

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
CHALLENGES_PATH = ROOT / "data" / "challenge.json"
PRODUCT_PATH = ROOT / "data" / "product.json"
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
PROMPT_VERSION = "1.0"

SPEAKER_ID = "challenge_3d9396a17afa47dc87f65f78bd289851"
TRIMMER_ID = "challenge_fe92f3bf36e841cca1d02fd1a8ac708f"

VISUAL_CRITERIA = {
    SPEAKER_ID: {
        "ordinary_moment_visible": "An ordinary moment is visible before music starts.",
        "speaker_clearly_visible": "The boAt Stone 358 Pro is clearly visible.",
        "speaker_interaction_visible": "The creator visibly turns on or interacts with the speaker.",
        "mood_changes_after_music": "The creator's activity or energy visibly changes after music starts.",
        "speaker_visible_during_activity": "The speaker remains visible during part of the activity.",
        "speaker_or_creator_and_speaker_in_ending": "The ending shows the speaker, or the creator with the speaker.",
    },
    TRIMMER_ID: {
        "beard_before_visible": "The beard is clearly shown before trimming.",
        "selected_trimmer_visible": "The selected listed trimmer is clearly visible.",
        "two_to_three_trimming_shots": "Two or three distinct real trimming segments are visible.",
        "final_beard_style_visible": "The final beard style is visible from the front or side.",
    },
}


class Evidence(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)


class ModelFinding(BaseModel):
    id: str
    status: Literal["pass", "fail", "review"]
    reason: str
    evidence: list[Evidence] = Field(default_factory=list)


class ExtraObservation(BaseModel):
    reason: str
    evidence: list[Evidence] = Field(default_factory=list)


class ModelResponse(BaseModel):
    findings: list[ModelFinding]
    extra_observations: list[ExtraObservation] = Field(default_factory=list)


def get_challenge(challenge_id: str) -> dict | None:
    data = json.loads(CHALLENGES_PATH.read_text())
    return next((item for item in data["data"] if item["id"] == challenge_id), None)


def product_options(challenge: dict) -> list[str]:
    return [option["name"] for option in challenge.get("product_options", [])]


def check(check_id: str, status: str, reason: str, method: str, evidence: list[dict] | None = None, **extra: object) -> dict:
    return {
        "id": check_id,
        "status": status,
        "reason": " ".join(reason.split()),
        "method": method,
        "evidence": evidence or [],
        **extra,
    }


def run_media_command(arguments: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, check=False)


def probe_media(video_path: Path) -> dict:
    result = run_media_command(
        ["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-of", "json", str(video_path)],
        timeout=30,
    )
    if result.returncode != 0:
        raise ValueError("The uploaded file cannot be read as media.")
    data = json.loads(result.stdout)
    video_stream = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"), None)
    if not video_stream:
        raise ValueError("The uploaded file has no video stream.")
    audio_stream = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"), None)
    duration = float(data.get("format", {}).get("duration") or video_stream.get("duration") or 0)
    width = int(video_stream["width"])
    height = int(video_stream["height"])
    rotation = int(video_stream.get("tags", {}).get("rotate", 0))
    for item in video_stream.get("side_data_list", []):
        if "rotation" in item:
            rotation = int(item["rotation"])
    if rotation % 180:
        width, height = height, width
    return {"duration_seconds": duration, "display_width": width, "display_height": height, "has_audio": audio_stream is not None}


def fully_decodable(video_path: Path) -> bool:
    result = run_media_command(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror", "-protocol_whitelist", "file,pipe", "-i", str(video_path), "-map", "0:v:0", "-f", "null", "-"],
    )
    return result.returncode == 0


def audio_hygiene(video_path: Path, has_audio: bool) -> list[dict]:
    if not has_audio:
        return [check("audio_track_decodable", "skipped", "No audio track is present.", "ffprobe")]
    try:
        result = run_media_command(
            ["ffmpeg", "-hide_banner", "-loglevel", "info", "-xerror", "-protocol_whitelist", "file,pipe", "-i", str(video_path), "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-"],
        )
    except subprocess.TimeoutExpired:
        return [check("audio_track_decodable", "review", "The audio check timed out.", "ffmpeg")]
    if result.returncode:
        return [check("audio_track_decodable", "review", "The audio track does not decode cleanly.", "ffmpeg")]
    checks = [check("audio_track_decodable", "pass", "The audio track decodes without an error.", "ffmpeg")]
    peak = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", result.stderr)
    if peak and float(peak.group(1)) <= -80:
        checks.append(check("audio_likely_silent", "review", "The audio level is extremely low and may be silent.", "ffmpeg"))
    return checks


def validate_event_order(findings: dict[str, dict], challenge_id: str) -> None:
    """Downgrade unsupported model passes; never create a fail from model output."""
    for finding in findings.values():
        if finding["status"] == "pass" and not finding["evidence"]:
            finding["status"] = "review"
            finding["reason"] = "The model reported a pass without timestamped evidence."

    if challenge_id == TRIMMER_ID:
        shots = findings.get("two_to_three_trimming_shots")
        if shots and shots["status"] == "pass":
            intervals = sorted(shots["evidence"], key=lambda item: item["start_seconds"])
            shots["evidence"] = intervals
            distinct = len(intervals) in {2, 3} and all(first["end_seconds"] < second["start_seconds"] for first, second in zip(intervals, intervals[1:]))
            if not distinct:
                shots["status"] = "review"
                shots["reason"] = "Two or three distinct trimming segments were not supported by the timestamps."
        before = findings.get("beard_before_visible")
        ending = findings.get("final_beard_style_visible")
        if before and shots and before["status"] == shots["status"] == "pass":
            if before["evidence"][0]["end_seconds"] >= shots["evidence"][0]["start_seconds"]:
                shots["status"] = "review"
                shots["reason"] = "The timestamps do not establish trimming after the before view."
        if ending and shots and ending["status"] == shots["status"] == "pass":
            if ending["evidence"][0]["start_seconds"] <= shots["evidence"][-1]["end_seconds"]:
                ending["status"] = "review"
                ending["reason"] = "The timestamps do not establish the final look after trimming."
    else:
        ordered_ids = ["ordinary_moment_visible", "speaker_interaction_visible", "music_starts", "mood_changes_after_music"]
        ordered = [findings.get(check_id) for check_id in ordered_ids]
        for first, second in zip(ordered, ordered[1:]):
            if first and second and first["status"] == second["status"] == "pass":
                if first["evidence"][0]["end_seconds"] >= second["evidence"][0]["start_seconds"]:
                    second["status"] = "review"
                    second["reason"] = "The timestamps do not establish the required event order."


def visual_review(video_path: Path, challenge: dict, selected_product: str | None, duration: float) -> tuple[dict[str, dict], list[dict], dict]:
    criteria = VISUAL_CRITERIA[challenge["id"]]
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return {}, [], {"used": False, "reason": "GEMINI_API_KEY is not configured.", "final_decision_by_llm": False}

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {}, [], {"used": False, "reason": "Install the optional llm dependency group.", "final_decision_by_llm": False}

    reference_image = None
    product_record = None
    if challenge["id"] == TRIMMER_ID:
        selected_option = next((option for option in challenge["product_options"] if option["name"] == selected_product), None)
        candidate = json.loads(PRODUCT_PATH.read_text())
        if selected_option and selected_option.get("buy_url") == candidate.get("product_url"):
            product_record = candidate
            image_url = candidate.get("image_url", "")
            if image_url.startswith("https://"):
                try:
                    with urlopen(image_url, timeout=10) as response:
                        mime_type = response.headers.get_content_type()
                        image_bytes = response.read(10_000_001)
                    if mime_type.startswith("image/") and len(image_bytes) <= 10_000_000:
                        reference_image = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                except (OSError, ValueError):
                    pass

    prompt = (
        "Review the uploaded creator video against ONLY the listed criteria. "
        "Return exactly one finding per criterion ID. Provide one short, single-line reason per finding. "
        "For visible events, provide timestamps in seconds. Use review when evidence is unclear. "
        "Do not claim to prove ownership, licensing, purchase, or exact SKU from appearance alone. "
        "A fail means you clearly observed a violation; uncertainty means review. "
        "Report any other concrete concern as an extra observation, not a new rule. "
        "Do not evaluate audio meaning unless an audio criterion is listed.\n"
        f"Challenge: {challenge['title']}\n"
        f"Selected product: {selected_product or challenge.get('product_name', '')}\n"
        f"Approved product record: {json.dumps({'name': product_record['name'], 'brand': product_record['brand']} if product_record else None)}\n"
        f"Reference product image attached: {reference_image is not None}\n"
        f"Criteria: {json.dumps(criteria, ensure_ascii=False)}"
    )
    if challenge["id"] == SPEAKER_ID:
        prompt += "\nAudio criterion: music_starts = Music audibly begins after the ordinary moment."

    client = genai.Client(api_key=api_key)
    uploaded = None
    try:
        uploaded = client.files.upload(file=str(video_path))
        for _ in range(30):
            state = getattr(getattr(uploaded, "state", None), "name", None)
            if state == "ACTIVE":
                break
            if state == "FAILED":
                raise ValueError("Model video processing failed.")
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
        else:
            raise TimeoutError("Model video processing timed out.")
        contents = [uploaded]
        if reference_image is not None:
            contents.append(reference_image)
        contents.append(prompt)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=ModelResponse),
        )
        parsed = ModelResponse.model_validate_json(response.text)
        allowed = set(criteria) | ({"music_starts"} if challenge["id"] == SPEAKER_ID else set())
        findings: dict[str, dict] = {}
        for finding in parsed.findings:
            if finding.id not in allowed or finding.id in findings:
                continue
            evidence = [
                {"start_seconds": item.start_seconds, "end_seconds": item.end_seconds, "source": "video"}
                for item in finding.evidence
                if item.start_seconds <= item.end_seconds <= duration
            ]
            status = "review" if finding.status == "fail" else finding.status
            reason = finding.reason if status == finding.status else f"Model suggests failure: {finding.reason} Human confirmation is required."
            if finding.id in {"selected_trimmer_visible", "speaker_clearly_visible"} and status == "pass" and reference_image is None:
                status = "review"
                reason = "Product is visible, but an approved reference image is unavailable for exact identification."
            findings[finding.id] = check(finding.id, status, reason, "llm_video", evidence)
        validate_event_order(findings, challenge["id"])
        extras = []
        for index, observation in enumerate(parsed.extra_observations, 1):
            evidence = [
                {"start_seconds": item.start_seconds, "end_seconds": item.end_seconds, "source": "video"}
                for item in observation.evidence
                if item.start_seconds <= item.end_seconds <= duration
            ]
            extras.append(check(f"model_observation_{index}", "review", observation.reason, "llm_video", evidence, policy_id=None))
        return findings, extras, {
            "used": True,
            "model": MODEL_NAME,
            "prompt_version": PROMPT_VERSION,
            "product_reference_image_used": reference_image is not None,
            "role": "propose_timestamped_visual_observations",
            "output_validation": "schema_and_timestamp_ranges_checked_by_code",
            "final_decision_by_llm": False,
        }
    except Exception as exc:
        return {}, [], {"used": False, "reason": f"Model analysis unavailable ({type(exc).__name__}).", "final_decision_by_llm": False}
    finally:
        if uploaded is not None:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass


def build_report(submission_id: str, challenge: dict, selected_product: str | None, video_path: Path) -> dict:
    challenge_checks: list[dict] = []
    additional_checks: list[dict] = []
    media: dict = {}
    model_findings: dict[str, dict] = {}
    llm_analysis: dict = {"used": False, "reason": "Video file did not pass technical validation.", "final_decision_by_llm": False}

    try:
        media = probe_media(video_path)
    except (ValueError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired):
        additional_checks.append(check("video_fully_decodable", "fail", "The uploaded file is unreadable or has no usable video stream.", "ffprobe", policy_id="platform.video_fully_decodable"))
    else:
        width, height = media["display_width"], media["display_height"]
        ratio = width / height if height else 0
        vertical = width < height and abs(ratio - 9 / 16) <= 0.02
        challenge_checks.append(check("vertical_9_by_16", "pass" if vertical else "fail", f"Displayed video dimensions are {width} by {height}." if vertical else f"Displayed video dimensions are {width} by {height}; 9:16 is required.", "ffprobe"))
        duration = media["duration_seconds"]
        in_range = 20 <= duration <= 30
        challenge_checks.append(check("duration_20_to_30_seconds", "pass" if in_range else "fail", f"The video is {duration:.1f} seconds long and meets the 20–30 second rule." if in_range else f"The video is {duration:.1f} seconds long; the allowed range is 20–30 seconds.", "ffprobe"))
        try:
            decodable = fully_decodable(video_path)
        except subprocess.TimeoutExpired:
            decodable = False
        additional_checks.append(check("video_fully_decodable", "pass" if decodable else "fail", "The video stream decodes fully." if decodable else "The video stream does not decode fully.", "ffmpeg", policy_id="platform.video_fully_decodable"))
        if decodable:
            model_findings, extras, llm_analysis = visual_review(video_path, challenge, selected_product, duration)
            additional_checks.extend(extras)

    for criterion_id in VISUAL_CRITERIA[challenge["id"]]:
        missing_reason = llm_analysis.get("reason", "The model did not return evidence for this criterion.")
        challenge_checks.append(model_findings.get(criterion_id) or check(criterion_id, "review", f"Visual evidence has not been verified: {missing_reason}", "llm_video"))
    if challenge["id"] == SPEAKER_ID:
        challenge_checks.append(check("footage_and_audio_rights", "review", "Video analysis cannot prove footage or audio usage rights.", "human_or_rights_records"))
    else:
        challenge_checks.append(check("footage_original_and_licensed", "review", "Video analysis cannot prove footage ownership or usage rights.", "human_or_rights_records"))

    has_audio = media.get("has_audio", False)
    audio = {
        "mode": "checklist_required" if challenge["id"] == SPEAKER_ID else "hygiene_only",
        "semantic_checks": [],
        "hygiene_checks": audio_hygiene(video_path, has_audio) if media else [check("audio_track_decodable", "skipped", "Audio cannot be checked in an unreadable video.", "ffprobe")],
    }
    if challenge["id"] == SPEAKER_ID:
        if media and not has_audio:
            audio["semantic_checks"].append(check("music_starts", "fail", "The video has no audio track, so music onset cannot be heard.", "ffprobe"))
        else:
            missing_reason = llm_analysis.get("reason", "The model did not return evidence for music onset.")
            audio["semantic_checks"].append(model_findings.get("music_starts") or check("music_starts", "review", f"Music onset has not been verified: {missing_reason}", "llm_video"))

    all_checks = challenge_checks + audio["semantic_checks"] + audio["hygiene_checks"] + additional_checks
    not_passed = [{"id": item["id"], "status": item["status"], "reason": item["reason"]} for item in all_checks if item["status"] in {"fail", "review"}]
    policy_fails = [item for item in additional_checks if item["status"] == "fail" and item.get("policy_id")]
    checklist_fails = [item for item in challenge_checks + audio["semantic_checks"] if item["status"] == "fail"]
    if policy_fails:
        decision_status = "excluded"
        basis = [item["id"] for item in policy_fails]
    elif checklist_fails:
        decision_status = "fail"
        basis = [item["id"] for item in checklist_fails]
    elif any(item["status"] == "review" for item in all_checks):
        decision_status = "review"
        basis = [item["id"] for item in all_checks if item["status"] == "review"]
    else:
        decision_status = "pass"
        basis = []
    if decision_status == "excluded":
        decision_reason = policy_fails[0]["reason"]
    elif decision_status == "fail":
        decision_reason = checklist_fails[0]["reason"]
    elif decision_status == "review":
        decision_reason = next(item["reason"] for item in all_checks if item["status"] == "review")
    else:
        decision_reason = "All required checks passed; human verification remains required."
    return {
        "schema_version": "1.0",
        "submission_id": submission_id,
        "challenge_id": challenge["id"],
        "selected_product": selected_product,
        "source_video": f"uploads/{video_path.name}",
        "processing_status": "complete",
        "decision": {"status": decision_status, "reason": decision_reason, "basis_check_ids": basis, "human_verification_required": bool(challenge.get("human_verification_enabled"))},
        "media": media,
        "challenge_checks": challenge_checks,
        "audio": audio,
        "additional_checks": additional_checks,
        "not_passed_checks": not_passed,
        "llm_analysis": llm_analysis,
    }
