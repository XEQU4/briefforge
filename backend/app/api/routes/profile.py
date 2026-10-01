from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.api.dependencies.auth import get_current_user
from app.core.db import get_db
from app.models import User
from app.schemas.ownership import UserRead
from app.schemas.profile import ProfileUpdate
from app.services import avatars


router = APIRouter(tags=["profile"])


async def locked_user(db: AsyncSession, user: User) -> User:
    # Serialize profile mutations and reload after waiting for a concurrent
    # replacement/delete, so only the actual previous file is removed.
    return await db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))


@router.patch("/profile", response_model=UserRead)
async def update_profile(payload: ProfileUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await locked_user(db, user)
    user.display_name = payload.display_name
    await db.commit()
    await db.refresh(user)
    return user


async def read_avatar(request: Request) -> bytes:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "multipart/form-data":
        raise HTTPException(422, "Send exactly one avatar file using multipart/form-data.")
    received = 0

    async def bounded_stream():
        nonlocal received
        async for chunk in request.stream():
            received += len(chunk)
            # Bound the entire body, including chunked uploads and framing.
            if received > avatars.MAX_UPLOAD_BYTES + 64 * 1024:
                # Parser closes its temporary files on MultiPartException.
                raise MultiPartException("Avatar request too large")
            yield chunk

    try:
        form = await MultiPartParser(request.headers, bounded_stream(), max_files=1, max_fields=0).parse()
    except MultiPartException as exc:
        if received > avatars.MAX_UPLOAD_BYTES + 64 * 1024:
            raise HTTPException(413, "Image must be 2 MB or smaller.") from exc
        raise HTTPException(422, "Send exactly one avatar file using multipart/form-data.") from exc
    try:
        file = form.get("file")
        if len(form.multi_items()) != 1 or not isinstance(file, UploadFile):
            raise HTTPException(422, "Send exactly one avatar file.")
        if file.content_type not in avatars.MIME_FORMATS:
            raise HTTPException(415, "Unsupported image type. Use JPEG, PNG, or WebP.")
        if file.size is not None and file.size > avatars.MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image must be 2 MB or smaller.")
        data = await file.read(avatars.MAX_UPLOAD_BYTES + 1)
        return await run_in_threadpool(avatars.normalize_avatar, data, file.content_type)
    finally:
        await form.close()


@router.post("/profile/avatar", response_model=UserRead, openapi_extra={
    "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["file"], "additionalProperties": False,
        "properties": {"file": {"type": "string", "format": "binary"}},
    }}}},
})
async def upload_avatar(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    normalized = await read_avatar(request)
    user = await locked_user(db, user)
    previous = user.avatar_filename
    try:
        filename = await run_in_threadpool(avatars.store_avatar, normalized)
    except OSError as exc:
        raise HTTPException(503, "Unable to store avatar. Please try again.") from exc
    try:
        user.avatar_filename = filename
        await db.commit()
    except BaseException:
        await db.rollback()
        await run_in_threadpool(avatars.remove_avatar, filename)
        raise
    await run_in_threadpool(avatars.remove_avatar, previous)
    await db.refresh(user)
    return user


@router.delete("/profile/avatar", response_model=UserRead)
async def delete_avatar(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await locked_user(db, user)
    previous = user.avatar_filename
    user.avatar_filename = None
    await db.commit()
    await run_in_threadpool(avatars.remove_avatar, previous)
    await db.refresh(user)
    return user


@router.get("/users/me/avatar", response_class=Response)
async def current_avatar(user: User = Depends(get_current_user)):
    path = avatars.avatar_path(user.avatar_filename)
    if path is None:
        raise HTTPException(404, "Avatar not found")
    try:
        # Read the small normalized file before responding, so replacement or
        # deletion cannot race a deferred FileResponse open.
        data = await run_in_threadpool(path.read_bytes)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Avatar not found") from exc
    return Response(data, media_type="image/webp", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
