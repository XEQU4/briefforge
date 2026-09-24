from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OrganizationMember, Task, TeamMember, User


async def require_organization_member(
    organization_id: int,
    user: User,
    db: AsyncSession,
) -> None:
    membership = await db.scalar(
        select(OrganizationMember.id).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization membership required")


async def require_task_organization_member(task: Task, user: User, db: AsyncSession) -> None:
    if task.organization_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Legacy tasks cannot be changed through product routes")
    await require_organization_member(task.organization_id, user, db)


async def require_team_member(team_id: int, user: User, db: AsyncSession) -> None:
    membership = await db.scalar(
        select(TeamMember.id).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Team membership required")
