from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import commit_or_rollback, get_db
from app.api.dependencies.auth import get_current_user
from app.models import Team, TeamMember, TeamMemberRole, User
from app.schemas import TeamCreate, TeamRead
from app.schemas.pagination import PaginatedResponse

router = APIRouter(tags=["teams"])
legacy_list_router = APIRouter(tags=["teams"])
versioned_list_router = APIRouter(tags=["teams"])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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


async def _list_teams(*, versioned: bool, q: str | None, page: int, page_size: int, db: AsyncSession):
    filters = []
    normalized_q = (q or "").strip()
    if normalized_q:
        pattern = f"%{_escape_like(normalized_q)}%"
        filters.append(or_(
            Team.name.ilike(pattern, escape="\\"),
            Team.interests.ilike(pattern, escape="\\"),
            Team.skills.ilike(pattern, escape="\\"),
            Team.technologies.ilike(pattern, escape="\\"),
        ))
    query = select(Team).where(*filters).order_by(Team.name, Team.id)
    if not versioned:
        result = await db.execute(query)
        return list(result.scalars().all())
    total = await db.scalar(select(func.count()).select_from(Team).where(*filters)) or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return PaginatedResponse[TeamRead].build(list(result.scalars().all()), page, page_size, total)


@legacy_list_router.get("/teams", response_model=list[TeamRead])
async def list_teams_legacy(
    q: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
):
    return await _list_teams(versioned=False, q=q, page=1, page_size=20, db=db)


@versioned_list_router.get("/teams", response_model=PaginatedResponse[TeamRead])
async def list_teams_v1(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
):
    return await _list_teams(versioned=True, q=q, page=page, page_size=page_size, db=db)


@router.get("/teams/{team_id}", response_model=TeamRead)
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    team = await db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team
