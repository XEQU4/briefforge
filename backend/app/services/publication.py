from enum import Enum

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.status import TaskPublicationStatus, TaskStatus
from app.models import Task


class PublicationAction(str, Enum):
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    ARCHIVE = "archive"


def is_publicly_visible(task: Task) -> bool:
    return task.status == TaskStatus.CONFIRMED and task.publication_status == TaskPublicationStatus.PUBLISHED


def public_visibility_filters():
    return (
        Task.status == TaskStatus.CONFIRMED,
        Task.publication_status == TaskPublicationStatus.PUBLISHED,
    )


def transition_publication(task: Task, action: PublicationAction) -> TaskPublicationStatus:
    current = TaskPublicationStatus(task.publication_status)
    if action == PublicationAction.PUBLISH:
        if task.status != TaskStatus.CONFIRMED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only confirmed tasks can be published")
        return TaskPublicationStatus.PUBLISHED
    if action == PublicationAction.UNPUBLISH:
        return TaskPublicationStatus.UNPUBLISHED
    if action == PublicationAction.ARCHIVE:
        return TaskPublicationStatus.ARCHIVED
    raise AssertionError(f"Unsupported publication action: {action}")


async def load_task_for_update(db: AsyncSession, task_id: int) -> Task:
    task = await db.scalar(select(Task).where(Task.id == task_id).with_for_update())
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task
