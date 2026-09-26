from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.authorization import require_task_organization_member, require_team_member
from app.core.db import commit_or_rollback, get_db
from app.domain.status import ProposalStatus
from app.models import Proposal, Task, Team, User
from app.schemas import ProposalCreate, ProposalRead, ProposalUpdate
from app.schemas.pagination import PaginatedResponse
from app.services.lifecycle import InvalidTransition, transition_proposal
from app.services.publication import is_publicly_visible, load_task_for_update

router = APIRouter(tags=["proposals"])
legacy_list_router = APIRouter(tags=["proposals"])
versioned_list_router = APIRouter(tags=["proposals"])


@versioned_list_router.get("/proposals/mine", response_model=PaginatedResponse[ProposalRead])
async def list_my_proposals(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: ProposalStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "private, no-store"
    filters = [Proposal.submitted_by_user_id == user.id]
    if status_filter is not None:
        filters.append(Proposal.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(Proposal).where(*filters)) or 0
    result = await db.execute(
        select(Proposal)
        .where(*filters)
        .order_by(Proposal.created_at.desc(), Proposal.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return PaginatedResponse[ProposalRead].build(list(result.scalars().all()), page, page_size, total)


@router.post("/tasks/{task_id}/proposals", response_model=ProposalRead, status_code=201)
async def create_proposal(
    task_id: int,
    payload: ProposalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await load_task_for_update(db, task_id)
    if await db.get(Team, payload.team_id) is None:
        raise HTTPException(status_code=404, detail="Team not found")
    await require_team_member(payload.team_id, user, db)
    if not is_publicly_visible(task):
        raise HTTPException(status_code=409, detail="Proposals can only be submitted to published confirmed tasks")
    proposal = Proposal(task_id=task_id, submitted_by_user_id=user.id, **payload.model_dump())
    db.add(proposal)
    await commit_or_rollback(db)
    await db.refresh(
        proposal,
        attribute_names=["id", "task_id", "team_id", "idea", "plan", "deadline", "link", "status", "created_at"],
    )
    return proposal


async def _list_proposals(
    *,
    versioned: bool,
    task_id: int,
    page: int = 1,
    page_size: int = 20,
    status_filter: ProposalStatus | None = None,
    db: AsyncSession,
    user: User,
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await require_task_organization_member(task, user, db)
    filters = [Proposal.task_id == task_id]
    if status_filter is not None:
        filters.append(Proposal.status == status_filter)
    query = select(Proposal).where(*filters).order_by(Proposal.created_at, Proposal.id)
    if not versioned:
        result = await db.execute(query)
        return list(result.scalars().all())
    total = await db.scalar(select(func.count()).select_from(Proposal).where(*filters)) or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return PaginatedResponse[ProposalRead].build(list(result.scalars().all()), page, page_size, total)


@legacy_list_router.get("/tasks/{task_id}/proposals", response_model=list[ProposalRead])
async def list_proposals_legacy(
    task_id: int,
    status_filter: ProposalStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _list_proposals(
        versioned=False,
        task_id=task_id,
        status_filter=status_filter,
        db=db,
        user=user,
    )


@versioned_list_router.get("/tasks/{task_id}/proposals", response_model=PaginatedResponse[ProposalRead])
async def list_proposals_v1(
    task_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: ProposalStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _list_proposals(
        versioned=True,
        task_id=task_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        db=db,
        user=user,
    )


@router.patch("/proposals/{proposal_id}", response_model=ProposalRead)
async def update_proposal(
    proposal_id: int,
    payload: ProposalUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Proposal).options(selectinload(Proposal.task)).where(Proposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await require_task_organization_member(proposal.task, user, db)
    try:
        next_status = transition_proposal(proposal.status, payload.status)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail="Only pending proposals can be decided") from exc
    if next_status == proposal.status:
        return proposal
    proposal.status = next_status
    await commit_or_rollback(db)
    await db.refresh(
        proposal,
        attribute_names=["id", "task_id", "team_id", "idea", "plan", "deadline", "link", "status", "created_at"],
    )
    return proposal
