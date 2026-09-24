from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import commit_or_rollback, get_db
from app.api.dependencies.auth import get_current_user
from app.models import Team, TeamMember, TeamMemberRole, User
from app.schemas import TeamCreate, TeamRead

router = APIRouter(tags=["teams"])


@router.post("/teams", response_model=TeamRead, status_code=201)
async def create_team(
    payload: TeamCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    team = Team(**payload.model_dump())
    db.add(team)
    await db.flush()
    db.add(TeamMember(team_id=team.id, user_id=user.id, role=TeamMemberRole.OWNER))
    await commit_or_rollback(db)
    await db.refresh(team, attribute_names=["id", "name", "interests", "skills", "technologies"])
    return team


@router.get("/teams", response_model=list[TeamRead])
async def list_teams(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Team).order_by(Team.name))
    return list(result.scalars().all())
