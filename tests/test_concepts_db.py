"""Isolated PostgreSQL checks for concept ownership, billing, and replica locks."""

import getpass
import hashlib
import io
import os
import socket
import subprocess
import tempfile
import threading
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from fastapi import HTTPException

from src import billing, concepts, creative_api, db


PG_BIN = next((Path(path) for path in (
    "/opt/homebrew/opt/postgresql/bin", "/usr/lib/postgresql/18/bin",
    "/usr/lib/postgresql/17/bin") if (Path(path) / "initdb").exists()), None)


@pytest.fixture(scope="module")
def concept_database():
    if PG_BIN is None:
        pytest.skip("Local PostgreSQL tools are unavailable")
    with tempfile.TemporaryDirectory(prefix="concept-pg-", dir="/tmp") as directory:
        root = Path(directory)
        cluster = root / "data"
        subprocess.run([str(PG_BIN / "initdb"), "-D", str(cluster), "-A", "trust", "--no-instructions"],
                       check=True, capture_output=True, timeout=40)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        subprocess.run([str(PG_BIN / "pg_ctl"), "-D", str(cluster), "-l", str(root / "server.log"),
                        "-o", f"-k {root} -p {port} -c fsync=off", "-w", "start"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=40)
        old_database_url = os.environ.get("DATABASE_URL")
        try:
            os.environ["DATABASE_URL"] = f"host={root} port={port} dbname=postgres user={getpass.getuser()}"
            db.initialize()
            creative_api.initialize()
            concepts.initialize()
            yield
        finally:
            if old_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = old_database_url
            subprocess.run([str(PG_BIN / "pg_ctl"), "-D", str(cluster), "-m", "immediate", "-w", "stop"],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=40)


def _seed_concept(concept_id=None, user_id=None):
    concept_id = concept_id or "con_" + uuid4().hex
    user_id = user_id or "test_" + uuid4().hex
    with db.connection() as conn:
        conn.execute("INSERT INTO credit_wallets (user_id,balance_cents) VALUES (%s,1000)", (user_id,))
        conn.execute("""INSERT INTO concepts (id,user_id,target_seconds,aspect,status)
            VALUES (%s,%s,5,'landscape','generating')""", (concept_id, user_id))
    return concept_id, user_id


def test_starter_credit_is_five_dollars_for_new_and_existing_users(concept_database, monkeypatch):
    calls = []
    monkeypatch.setattr(billing.clerk_credits, "adjust", lambda *args: calls.append(args))
    new_user = "user_" + uuid4().hex
    existing_user = "user_" + uuid4().hex
    with db.connection() as conn:
        conn.execute("INSERT INTO credit_wallets (user_id,balance_cents) VALUES (%s,105)",
                     (existing_user,))
        conn.execute("""INSERT INTO credit_ledger
            (user_id,operation_id,kind,amount_cents,balance_after_cents)
            VALUES (%s,%s,'starter_grant',200,200)""",
            (existing_user, f"starter:{existing_user}"))

    with db.connection() as conn:
        assert billing.balance(conn, new_user)["balance_cents"] == 500
        assert billing.balance(conn, existing_user)["balance_cents"] == 405
    with db.connection() as conn:
        assert billing.balance(conn, new_user)["balance_cents"] == 500
        assert billing.balance(conn, existing_user)["balance_cents"] == 405
        grants = conn.execute("""SELECT user_id,amount_cents FROM credit_ledger
            WHERE kind='starter_grant' AND user_id IN (%s,%s) ORDER BY id""",
            (new_user, existing_user)).fetchall()

    assert [(row["user_id"], row["amount_cents"]) for row in grants] == [
        (existing_user, 200), (new_user, 500), (existing_user, 300),
    ]
    assert [(call[0], call[1], call[2]) for call in calls] == [
        (new_user, 500, "increase"), (existing_user, 300, "increase"),
    ]


def test_concept_reads_are_owner_scoped(concept_database):
    concept_id, user_id = _seed_concept()
    with db.connection() as conn:
        assert concepts._owned(conn, concept_id, user_id)["id"] == concept_id
        with pytest.raises(HTTPException) as error:
            concepts._owned(conn, concept_id, "other_user")
    assert error.value.status_code == 404


def test_scene_clips_are_not_listed_as_separate_videos(concept_database):
    from src import api as api_module

    concept_id, user_id = _seed_concept()
    scene_job = "vid_" + uuid4().hex
    standalone_job = "vid_" + uuid4().hex
    with db.connection() as conn:
        for job_id in (scene_job, standalone_job):
            conn.execute("""INSERT INTO video_jobs
                (id,user_id,request_hash,mode,prompt,duration_seconds,resolution,seed)
                VALUES (%s,%s,'hash','t2v','A scene',5,'512p',1)""",
                (job_id, user_id))
        conn.execute("""INSERT INTO concept_scenes
            (concept_id,position,title,duration_seconds,image_prompt,motion_prompt,job_id,status)
            VALUES (%s,0,'Opening',5,'An image','A camera move',%s,'generating')""",
            (concept_id, scene_job))

    listed = api_module.list_videos(user_id=user_id)["videos"]
    assert [job["job_id"] for job in listed] == [standalone_job]


def test_scene_image_charge_recovers_after_saved_asset(concept_database, monkeypatch):
    concept_id, user_id = _seed_concept()
    scene = {"position": 0, "attempt": 0, "image_prompt": "A mountain lake"}
    concept = {"id": concept_id, "user_id": user_id, "aspect": "landscape", "title": "Lake"}
    identity = f"{user_id}:{concept_id}:0:0"
    digest = hashlib.sha256(identity.encode()).hexdigest()[:32]
    asset_id = "asset_" + digest
    operation_id = "concept_image_" + digest
    with db.connection() as conn:
        billing.reserve(conn, user_id, operation_id, 20, "image")
        conn.execute("""INSERT INTO video_assets (id,user_id,object_key,content_type)
            VALUES (%s,%s,%s,'image/jpeg')""", (asset_id, user_id, f"uploads/{user_id}/{asset_id}"))
    monkeypatch.setattr(concepts.creative, "create_image", lambda **_kwargs: pytest.fail("Image was regenerated"))
    assert concepts._prepared_image(concept, scene, None) == asset_id
    assert concepts._prepared_image(concept, scene, None) == asset_id
    with db.connection() as conn:
        wallet = conn.execute("SELECT balance_cents FROM credit_wallets WHERE user_id=%s", (user_id,)).fetchone()
        ledger = conn.execute("SELECT kind FROM credit_ledger WHERE operation_id=%s ORDER BY id", (operation_id,)).fetchall()
    assert wallet["balance_cents"] == 980
    assert [row["kind"] for row in ledger] == ["reserve", "capture"]


def test_scene_image_is_charged_once_after_success(concept_database, monkeypatch):
    concept_id, user_id = _seed_concept()
    image = io.BytesIO()
    Image.new("RGB", (640, 360), "blue").save(image, "JPEG")
    calls = []
    monkeypatch.setattr(concepts.creative, "create_image", lambda **_kwargs: ("image/jpeg", image.getvalue()))
    monkeypatch.setattr(concepts.storage, "bucket", lambda: "test-bucket")
    monkeypatch.setattr(concepts.storage, "client", lambda: type("S3", (), {
        "put_object": lambda self, **kwargs: calls.append(kwargs)})())
    concept = {"id": concept_id, "user_id": user_id, "aspect": "landscape", "title": "Lake"}
    scene = {"position": 0, "attempt": 0, "image_prompt": "A mountain lake"}
    first = concepts._prepared_image(concept, scene, None)
    assert concepts._prepared_image(concept, scene, None) == first
    assert len(calls) == 1
    with db.connection() as conn:
        balance = conn.execute("SELECT balance_cents FROM credit_wallets WHERE user_id=%s", (user_id,)).fetchone()
    assert balance["balance_cents"] == 980


def test_two_replicas_submit_one_scene(concept_database, monkeypatch):
    concept_id, user_id = _seed_concept()
    asset_id = "asset_" + "b" * 32
    with db.connection() as conn:
        conn.execute("INSERT INTO video_assets (id,user_id,object_key,content_type) VALUES (%s,%s,'test-key','image/jpeg')",
                     (asset_id, user_id))
        conn.execute("""INSERT INTO concept_scenes
            (concept_id,position,title,duration_seconds,image_prompt,motion_prompt,asset_id,status)
            VALUES (%s,0,'Opening',5,'Lake still','Camera pushes toward lake',%s,'image_ready')""", (concept_id, asset_id))

    entered = threading.Event()
    release = threading.Event()
    calls = []

    def fake_submit(_body, *, user_id, idempotency_key):
        calls.append(idempotency_key)
        entered.set()
        assert release.wait(5)
        job_id = "vid_" + "c" * 32
        with db.connection() as conn:
            conn.execute("""INSERT INTO video_jobs
                (id,user_id,idempotency_key,request_hash,mode,prompt,asset_id,duration_seconds,resolution,seed)
                VALUES (%s,%s,%s,'hash','i2v','Camera pushes toward lake',%s,5,'512p',1)
                ON CONFLICT (id) DO NOTHING""", (job_id, user_id, idempotency_key, asset_id))
        return {"job_id": job_id}

    from src import api as api_module
    monkeypatch.setattr(api_module, "submit_video", fake_submit)
    first = threading.Thread(target=concepts._advance, args=(concept_id,))
    second = threading.Thread(target=concepts._advance, args=(concept_id,))
    first.start()
    assert entered.wait(5)
    second.start()
    second.join(timeout=5)
    assert not second.is_alive()
    release.set()
    first.join(timeout=5)
    assert not first.is_alive()
    with db.connection() as conn:
        scene = conn.execute("SELECT job_id,status FROM concept_scenes WHERE concept_id=%s", (concept_id,)).fetchone()
    assert len(calls) == 1
    assert scene == {"job_id": "vid_" + "c" * 32, "status": "generating"}


def test_next_scene_uses_completed_clip_last_frame(concept_database, monkeypatch):
    concept_id, user_id = _seed_concept()
    first_asset = "asset_" + uuid4().hex
    first_job = "vid_" + uuid4().hex
    with db.connection() as conn:
        conn.execute("INSERT INTO video_assets (id,user_id,object_key,content_type) VALUES (%s,%s,'first-image','image/jpeg')",
                     (first_asset, user_id))
        conn.execute("""INSERT INTO video_jobs
            (id,user_id,request_hash,mode,prompt,asset_id,duration_seconds,resolution,seed,status,output_key)
            VALUES (%s,%s,'hash','i2v','Camera moves',%s,5,'512p',1,'succeeded','first-clip')""",
            (first_job, user_id, first_asset))
        conn.execute("""INSERT INTO concept_scenes
            (concept_id,position,title,duration_seconds,image_prompt,motion_prompt,asset_id,job_id,status)
            VALUES (%s,0,'Opening',5,'Lake','Camera moves',%s,%s,'succeeded')""",
            (concept_id, first_asset, first_job))
        conn.execute("""INSERT INTO concept_scenes
            (concept_id,position,title,duration_seconds,image_prompt,motion_prompt,status)
            VALUES (%s,1,'Ending',5,'Lake at dusk','Camera rises','pending')""", (concept_id,))

    reference = "asset_" + uuid4().hex
    with db.connection() as conn:
        conn.execute("INSERT INTO video_assets (id,user_id,object_key,content_type) VALUES (%s,%s,'last-frame','image/jpeg')",
                     (reference, user_id))
    seen = []
    monkeypatch.setattr(concepts.concept_media, "store_last_frame", lambda *args: reference)
    monkeypatch.setattr(concepts, "_prepared_image", lambda _concept, _scene, previous: seen.append(previous) or first_asset)
    from src import api as api_module
    monkeypatch.setattr(api_module, "submit_video", lambda *_args, **_kwargs: {"job_id": first_job})
    concepts._advance(concept_id)
    with db.connection() as conn:
        scene = conn.execute("SELECT reference_asset_id,reference_kind,status FROM concept_scenes WHERE concept_id=%s AND position=1",
                             (concept_id,)).fetchone()
    assert seen == [reference]
    assert scene == {"reference_asset_id": reference, "reference_kind": "last_frame", "status": "generating"}


def test_retry_reuses_clip_submitted_before_scene_link_was_saved(concept_database):
    concept_id, user_id = _seed_concept()
    asset_id = "asset_" + uuid4().hex
    job_id = "vid_" + uuid4().hex
    key = f"concept_{concept_id}_0_0"
    with db.connection() as conn:
        conn.execute("INSERT INTO video_assets (id,user_id,object_key,content_type) VALUES (%s,%s,'clip-image','image/jpeg')",
                     (asset_id, user_id))
        conn.execute("""INSERT INTO concept_scenes
            (concept_id,position,title,duration_seconds,image_prompt,motion_prompt,asset_id,status)
            VALUES (%s,0,'Opening',5,'Lake','Camera moves',%s,'image_ready')""", (concept_id, asset_id))
        conn.execute("""INSERT INTO video_jobs
            (id,user_id,idempotency_key,request_hash,mode,prompt,asset_id,duration_seconds,resolution,seed,status)
            VALUES (%s,%s,%s,'hash','i2v','Camera moves',%s,5,'512p',1,'queued')""",
            (job_id, user_id, key, asset_id))
        conn.execute("UPDATE concepts SET status='failed' WHERE id=%s", (concept_id,))

    router = concepts.create_router(lambda: user_id)
    retry_route = next(route for route in router.routes if route.path.endswith("/{concept_id}/retry"))
    result = retry_route.endpoint(concept_id, user_id)
    assert result["status"] == "generating"
    with db.connection() as conn:
        scene = conn.execute("SELECT attempt,asset_id FROM concept_scenes WHERE concept_id=%s", (concept_id,)).fetchone()
    assert scene == {"attempt": 0, "asset_id": asset_id}
