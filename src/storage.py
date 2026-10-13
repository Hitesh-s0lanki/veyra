"""Private S3 object access."""

import io

import boto3
from PIL import Image, UnidentifiedImageError

from src.config import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS, require_env


def client():
    return boto3.client("s3")


def bucket() -> str:
    return require_env("S3_BUCKET")


def input_key(user_id: str, asset_id: str) -> str:
    return f"uploads/{user_id}/{asset_id}"


def output_key(user_id: str, job_id: str) -> str:
    return f"videos/{user_id}/{job_id}/output.mp4"


def upload_form(key: str, content_type: str) -> dict:
    return client().generate_presigned_post(
        bucket(), key,
        Fields={"Content-Type": content_type},
        Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, MAX_IMAGE_BYTES]],
        ExpiresIn=900,
    )


def download_url(key: str) -> str:
    return client().generate_presigned_url(
        "get_object", Params={"Bucket": bucket(), "Key": key}, ExpiresIn=900
    )


def validate_image(key: str) -> dict:
    obj = client().get_object(Bucket=bucket(), Key=key)
    length = obj.get("ContentLength", 0)
    if length < 1 or length > MAX_IMAGE_BYTES:
        raise ValueError("Image size must be 1–10 MB")
    data = obj["Body"].read(MAX_IMAGE_BYTES + 1)
    if len(data) != length or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Invalid image size")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Only JPEG, PNG, and WebP images are supported")
            width, height = image.size
            if width < 256 or height < 256 or width * height > MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions are outside supported limits")
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid image") from exc
    return {"bytes": length, "width": width, "height": height}
