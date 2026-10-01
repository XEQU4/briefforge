"""Bounded image decoding and private, server-named avatar files."""
from io import BytesIO
import logging
from pathlib import Path
import re
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core import config


MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGE_EDGE = 8192
MIME_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
logger = logging.getLogger(__name__)


def normalize_avatar(data: bytes, content_type: str) -> bytes:
    if content_type not in MIME_FORMATS:
        raise HTTPException(415, "Unsupported image type. Use JPEG, PNG, or WebP.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image must be 2 MB or smaller.")
    try:
        with Image.open(BytesIO(data), formats=list(MIME_FORMATS.values())) as source:
            if source.format != MIME_FORMATS[content_type]:
                raise ValueError("Image format does not match content type")
            width, height = source.size
            if max(width, height) > MAX_IMAGE_EDGE or width * height > MAX_IMAGE_PIXELS:
                raise HTTPException(422, "Image dimensions are too large. Use an image up to 16 megapixels and 8192 pixels per side.")
            source.verify()
        with Image.open(BytesIO(data), formats=list(MIME_FORMATS.values())) as source:
            source.load()
            oriented = ImageOps.exif_transpose(source)
            mode = "RGBA" if "A" in oriented.getbands() or "transparency" in oriented.info else "RGB"
            side = min(512, *oriented.size)
            square = ImageOps.fit(oriented.convert(mode), (side, side), method=Image.Resampling.LANCZOS)
            # Start with fresh pixels: no EXIF, ICC, comments, or other metadata.
            clean = Image.new(mode, square.size)
            clean.paste(square)
            output = BytesIO()
            clean.save(output, format="WEBP", quality=85)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "Unable to read this image. Choose a valid JPEG, PNG, or WebP image.") from exc


def avatar_path(filename: str | None) -> Path | None:
    if not filename or re.fullmatch(r"[0-9a-f]{32}\.webp", filename) is None:
        return None
    directory = config.AVATAR_DIRECTORY.resolve()
    path = directory / filename
    # Never follow a symlink, even if a stored reference has been tampered with.
    if path.is_symlink() or path.resolve().parent != directory:
        return None
    return path


def store_avatar(data: bytes) -> str:
    config.AVATAR_DIRECTORY.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.webp"
    path = avatar_path(filename)
    if path is None:
        raise OSError("Invalid avatar destination")
    # Exclusive creation prevents overwriting an existing file.
    created = False
    try:
        with path.open("xb") as output:
            created = True
            output.write(data)
    except BaseException:
        if created:
            remove_avatar(filename)
        raise
    return filename


def remove_avatar(filename: str | None) -> None:
    path = avatar_path(filename)
    if path is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # The committed profile remains valid. Failed cleanup leaves an
            # unreachable file, never a broken reference or another user's file.
            logger.warning("Unable to remove an unused avatar file", exc_info=True)
