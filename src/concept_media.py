"""Clip finishing and continuity frames for multi-scene concept videos."""

import hashlib
import io
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from src import db, storage


def _download(key: str, destination: Path):
    obj = storage.client().get_object(Bucket=storage.bucket(), Key=key)
    with destination.open("wb") as output:
        for chunk in obj["Body"].iter_chunks(chunk_size=1024 * 1024):
            output.write(chunk)


def extract_last_frame(video_key: str) -> bytes:
    """Decode the last available frame of an owned, completed scene clip."""
    with tempfile.TemporaryDirectory(prefix="veyra-frame-") as directory:
        clip = Path(directory) / "clip.mp4"
        frame = Path(directory) / "frame.jpg"
        _download(video_key, clip)
        for offset in ("-0.2", "-1"):
            attempt = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                      "-sseof", offset, "-i", str(clip), "-frames:v", "1",
                                      "-q:v", "2", str(frame)], capture_output=True, timeout=120)
            if attempt.returncode == 0 and frame.is_file() and frame.stat().st_size:
                with Image.open(frame) as image:
                    width, height = image.size
                    if width < 256 or height < 256:
                        raise ValueError("Scene frame is too small")
                    output = io.BytesIO()
                    image.convert("RGB").save(output, format="JPEG", quality=92)
                    return output.getvalue()
        raise ValueError("Could not extract the last scene frame")


def store_last_frame(user_id: str, concept_id: str, position: int, video_key: str) -> str:
    """Persist one deterministic transition asset so a restart can reuse it."""
    digest = hashlib.sha256(f"{user_id}:{concept_id}:{position}:last-frame".encode()).hexdigest()[:32]
    asset_id = "asset_" + digest
    with db.connection() as conn:
        row = conn.execute("SELECT id FROM video_assets WHERE id=%s AND user_id=%s", (asset_id, user_id)).fetchone()
    if row:
        return asset_id
    data = extract_last_frame(video_key)
    key = storage.input_key(user_id, asset_id)
    storage.client().put_object(Bucket=storage.bucket(), Key=key, Body=data, ContentType="image/jpeg")
    with db.connection() as conn:
        conn.execute("""INSERT INTO video_assets (id,user_id,object_key,content_type)
            VALUES (%s,%s,%s,'image/jpeg') ON CONFLICT (id) DO NOTHING""", (asset_id, user_id, key))
    return asset_id


def assemble(concept, scenes):
    """Normalize aspect, frame rate, sound and length; join scenes with straight cuts."""
    width, height = (832, 480) if concept["aspect"] == "landscape" else (480, 832)
    with tempfile.TemporaryDirectory(prefix="veyra-concept-") as directory:
        inputs = []
        for scene in scenes:
            with db.connection() as conn:
                job = db.owned_job(conn, scene["job_id"], concept["user_id"])
            if not job or job["status"] != "succeeded" or not job["output_key"]:
                raise ValueError("Scene clip is unavailable")
            path = Path(directory) / f"scene-{scene['position']}.mp4"
            _download(job["output_key"], path)
            inputs.append(path)
        arguments = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for path in inputs:
            arguments.extend(["-i", str(path)])
        audio_inputs = []
        for index, path in enumerate(inputs):
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                                    "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
                                   check=True, capture_output=True, text=True, timeout=30)
            if probe.stdout.strip():
                audio_inputs.append(index)
            else:
                audio_inputs.append(len(inputs) + sum(1 for item in audio_inputs if item >= len(inputs)))
                arguments.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"])
        filters = []
        for index, scene in enumerate(scenes):
            duration = scene["duration_seconds"]
            filters.append(f"[{index}:v:0]fps=24,scale={width}:{height}:force_original_aspect_ratio=decrease,"
                           f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
                           f"tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration},"
                           f"setpts=PTS-STARTPTS[v{index}]")
            filters.append(f"[{audio_inputs[index]}:a:0]aresample=48000,"
                           f"apad,atrim=duration={duration},asetpts=PTS-STARTPTS[a{index}]")
        labels = "".join(f"[v{index}][a{index}]" for index in range(len(scenes)))
        filters.append(f"{labels}concat=n={len(scenes)}:v=1:a=1[outv][outa]")
        result = Path(directory) / "final.mp4"
        arguments.extend(["-filter_complex", ";".join(filters), "-map", "[outv]", "-map", "[outa]",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                          "-movflags", "+faststart", str(result)])
        subprocess.run(arguments, check=True, capture_output=True, timeout=600)
        key = f"concepts/{concept['user_id']}/{concept['id']}/final.mp4"
        storage.client().upload_file(str(result), storage.bucket(), key, ExtraArgs={"ContentType": "video/mp4"})
        return key
