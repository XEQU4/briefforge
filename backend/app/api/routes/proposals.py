from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import commit_or_rollback, get_db
from app.models import Proposal, Task, Team
from app.schemas import ProposalCreate, ProposalRead, ProposalUpdate

router = APIRouter(tags=["proposals"])


@router.post("/tasks/{task_id}/proposals", response_model=ProposalRead, status_code=201)
async def create_proposal(task_id: int, payload: ProposalCreate, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "confirmed":
        raise HTTPException(status_code=409, detail="Proposals can only be submitted to confirmed catalog tasks")
    if await db.get(Team, payload.team_id) is None:
        raise HTTPException(status_code=404, detail="Team not found")
    proposal = Proposal(task_id=task_id, **payload.model_dump())
    db.add(proposal)
    await commit_or_rollback(db)
    await db.refresh(
        proposal,
        attribute_names=["id", "task_id", "team_id", "idea", "plan", "deadline", "link", "status", "created_at"],
    )
    return proposal


@router.get("/tasks/{task_id}/proposals", response_model=list[ProposalRead])
async def list_proposals(task_id: int, db: AsyncSession = Depends(get_db)):
    if await db.get(Task, task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    result = await db.execute(select(Proposal).where(Proposal.task_id == task_id).order_by(Proposal.created_at))
    return list(result.scalars().all())


@router.patch("/proposals/{proposal_id}", response_model=ProposalRead)
async def update_proposal(proposal_id: int, payload: ProposalUpdate, db: AsyncSession = Depends(get_db)):
    proposal = await db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status == "pending" and payload.status == "pending":
        return proposal
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending proposals can be decided")
    proposal.status = payload.status
    await commit_or_rollback(db)
    await db.refresh(
        proposal,
        attribute_names=["id", "task_id", "team_id", "idea", "plan", "deadline", "link", "status", "created_at"],
    )
    return proposal
