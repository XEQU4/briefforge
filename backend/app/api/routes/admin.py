"""Explicit operational reads and narrowly scoped user/session actions."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_admin
from app.core.db import get_db
from app.domain.status import ProposalStatus, TaskPublicationStatus, TaskStatus
from app.models import AuthSession, Organization, OrganizationMember, Proposal, Task, Team, TeamMember, User
from app.schemas.admin import (
    AdminOrganizationRead, AdminProposalDetail, AdminProposalRead, AdminSessionRead,
    AdminSummary, AdminTaskDetail, AdminTaskRead, AdminTeamRead, AdminUserDetail,
    AdminUserRead, AdminUserUpdate, RevokedSessions,
)
from app.schemas.pagination import PaginatedResponse
from app.schemas.limits import MAX_DATABASE_ID, MAX_PAGE, MAX_PAGE_SIZE, ResourceId
from app.services.auth_security import utcnow_naive


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
Page = Annotated[int, Query(ge=1, le=MAX_PAGE)]
PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Search = Annotated[str | None, Query(max_length=200)]
PositiveId = Annotated[int | None, Query(ge=1, le=MAX_DATABASE_ID)]
DateSort = Literal["newest", "oldest"]


def count_rows(model, *conditions):
    return select(func.count()).select_from(model).where(*conditions).scalar_subquery()


def search_fields(q, *columns):
    if not q or not q.strip():
        return []
    escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return [or_(*(column.ilike(f"%{escaped}%", escape="\\") for column in columns))]


def date_order(model, sort):
    column = getattr(model, "created_at", model.id)
    return (column.asc(), model.id.asc()) if sort == "oldest" else (column.desc(), model.id.desc())


async def paginate(db, query, schema, page, page_size):
    total = await db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).mappings().all()
    return PaginatedResponse[schema].build(list(rows), page, page_size, total)


async def detail(db, query):
    row = (await db.execute(query)).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Record not found")
    return row


def user_query():
    return select(
        User.id, User.email, User.display_name, User.is_active, User.is_admin,
        User.avatar_filename.is_not(None).label("has_avatar"),
        User.last_login_at, User.created_at, User.updated_at,
    )


def organization_query():
    return select(
        Organization.id, Organization.name, Organization.slug, Organization.created_at, Organization.updated_at,
        count_rows(OrganizationMember, OrganizationMember.organization_id == Organization.id).label("member_count"),
        count_rows(Task, Task.organization_id == Organization.id).label("task_count"),
    )


def team_query():
    return select(
        Team.id, Team.name, Team.interests, Team.skills, Team.technologies,
        count_rows(TeamMember, TeamMember.team_id == Team.id).label("member_count"),
        count_rows(Proposal, Proposal.team_id == Team.id).label("proposal_count"),
    )


def task_query():
    return select(*(getattr(Task, field) for field in AdminTaskRead.model_fields))


def proposal_query(schema=AdminProposalRead):
    return select(*(getattr(Proposal, field) for field in schema.model_fields))


def active_sessions(now):
    return (AuthSession.revoked_at.is_(None), AuthSession.expires_at > now)


@router.get("/summary", response_model=AdminSummary)
async def summary(db: AsyncSession = Depends(get_db)):
    now = utcnow_naive()
    return (await db.execute(select(
        count_rows(User).label("users"),
        count_rows(User, User.is_active.is_(True)).label("active_users"),
        count_rows(Organization).label("organizations"),
        count_rows(Team).label("teams"),
        count_rows(Task).label("tasks"),
        count_rows(Task, Task.publication_status == TaskPublicationStatus.PUBLISHED).label("published_tasks"),
        count_rows(Proposal).label("proposals"),
        count_rows(Proposal, Proposal.status == ProposalStatus.PENDING).label("pending_proposals"),
        count_rows(AuthSession, *active_sessions(now), AuthSession.user.has(User.is_active.is_(True))).label("active_sessions"),
    ))).mappings().one()


@router.get("/users", response_model=PaginatedResponse[AdminUserRead])
async def users(
    q: Search = None, is_active: bool | None = None, is_admin: bool | None = None,
    sort: Literal["newest", "oldest", "email"] = "newest",
    page: Page = 1, page_size: PageSize = 20, db: AsyncSession = Depends(get_db),
):
    query = user_query().where(*search_fields(q, User.email, User.display_name))
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if is_admin is not None:
        query = query.where(User.is_admin == is_admin)
    order = (User.email.asc(), User.id.asc()) if sort == "email" else date_order(User, sort)
    return await paginate(db, query.order_by(*order), AdminUserRead, page, page_size)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def user_detail(user_id: ResourceId, db: AsyncSession = Depends(get_db)):
    query = user_query().add_columns(
        count_rows(OrganizationMember, OrganizationMember.user_id == User.id).label("organization_membership_count"),
        count_rows(TeamMember, TeamMember.user_id == User.id).label("team_membership_count"),
        count_rows(Task, Task.created_by_user_id == User.id).label("created_task_count"),
        count_rows(Proposal, Proposal.submitted_by_user_id == User.id).label("submitted_proposal_count"),
        count_rows(AuthSession, AuthSession.user_id == User.id, *active_sessions(utcnow_naive()), User.is_active.is_(True)).label("active_session_count"),
    ).where(User.id == user_id)
    return await detail(db, query)


async def lock_action_users(db, actor, user_id):
    # Consistent row order prevents two admins deactivating one another at once
    # from leaving no active administrator. Recheck privileges after waiting.
    rows = (await db.scalars(
        select(User).where(User.id.in_([actor.id, user_id])).order_by(User.id)
        .with_for_update().execution_options(populate_existing=True)
    )).all()
    by_id = {user.id: user for user in rows}
    current = by_id.get(actor.id)
    if current is None or not current.is_active or not current.is_admin:
        raise HTTPException(403, "Admin access required")
    if user_id not in by_id:
        raise HTTPException(404, "User not found")
    return by_id[user_id]


async def revoke_active_sessions(db, user_id):
    now = utcnow_naive()
    result = await db.execute(
        update(AuthSession).where(AuthSession.user_id == user_id, *active_sessions(now)).values(revoked_at=now)
    )
    return result.rowcount


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def set_active(
    user_id: ResourceId, payload: AdminUserUpdate, actor: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    if user_id == actor.id and not payload.is_active:
        raise HTTPException(409, "You cannot deactivate your own account")
    target = await lock_action_users(db, actor, user_id)
    target.is_active = payload.is_active
    if not payload.is_active:
        await revoke_active_sessions(db, user_id)
    await db.commit()
    return await detail(db, user_query().where(User.id == user_id))


@router.post("/users/{user_id}/revoke-sessions", response_model=RevokedSessions)
async def revoke_sessions(user_id: ResourceId, actor: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if user_id == actor.id:
        raise HTTPException(409, "You cannot revoke your own sessions here")
    await lock_action_users(db, actor, user_id)
    revoked_count = await revoke_active_sessions(db, user_id)
    await db.commit()
    return {"revoked_count": revoked_count}


@router.get("/organizations", response_model=PaginatedResponse[AdminOrganizationRead])
async def organizations(q: Search = None, sort: DateSort = "newest", page: Page = 1, page_size: PageSize = 20, db: AsyncSession = Depends(get_db)):
    query = organization_query().where(*search_fields(q, Organization.name, Organization.slug)).order_by(*date_order(Organization, sort))
    return await paginate(db, query, AdminOrganizationRead, page, page_size)


@router.get("/organizations/{organization_id}", response_model=AdminOrganizationRead)
async def organization_detail(organization_id: ResourceId, db: AsyncSession = Depends(get_db)):
    return await detail(db, organization_query().where(Organization.id == organization_id))


@router.get("/teams", response_model=PaginatedResponse[AdminTeamRead])
async def teams(q: Search = None, sort: DateSort = "newest", page: Page = 1, page_size: PageSize = 20, db: AsyncSession = Depends(get_db)):
    query = team_query().where(*search_fields(q, Team.name, Team.interests, Team.skills, Team.technologies)).order_by(*date_order(Team, sort))
    return await paginate(db, query, AdminTeamRead, page, page_size)


@router.get("/teams/{team_id}", response_model=AdminTeamRead)
async def team_detail(team_id: ResourceId, db: AsyncSession = Depends(get_db)):
    return await detail(db, team_query().where(Team.id == team_id))


@router.get("/tasks", response_model=PaginatedResponse[AdminTaskRead])
async def tasks(
    q: Search = None, status: TaskStatus | None = None, publication_status: TaskPublicationStatus | None = None,
    organization_id: PositiveId = None, sort: Literal["newest", "oldest", "rating"] = "newest",
    page: Page = 1, page_size: PageSize = 20, db: AsyncSession = Depends(get_db),
):
    query = task_query().where(*search_fields(q, Task.title, Task.topic, Task.context, Task.need))
    for column, value in ((Task.status, status), (Task.publication_status, publication_status), (Task.organization_id, organization_id)):
        if value is not None:
            query = query.where(column == value)
    order = (Task.rating_score.desc(), Task.id.desc()) if sort == "rating" else date_order(Task, sort)
    return await paginate(db, query.order_by(*order), AdminTaskRead, page, page_size)


@router.get("/tasks/{task_id}", response_model=AdminTaskDetail)
async def task_detail(task_id: ResourceId, db: AsyncSession = Depends(get_db)):
    return await detail(db, select(*(getattr(Task, field) for field in AdminTaskDetail.model_fields)).where(Task.id == task_id))


@router.get("/proposals", response_model=PaginatedResponse[AdminProposalRead])
async def proposals(
    status: ProposalStatus | None = None, task_id: PositiveId = None, team_id: PositiveId = None,
    submitted_by_user_id: PositiveId = None, page: Page = 1, page_size: PageSize = 20, db: AsyncSession = Depends(get_db),
):
    query = proposal_query()
    for column, value in ((Proposal.status, status), (Proposal.task_id, task_id), (Proposal.team_id, team_id), (Proposal.submitted_by_user_id, submitted_by_user_id)):
        if value is not None:
            query = query.where(column == value)
    return await paginate(db, query.order_by(*date_order(Proposal, "newest")), AdminProposalRead, page, page_size)


@router.get("/proposals/{proposal_id}", response_model=AdminProposalDetail)
async def proposal_detail(proposal_id: ResourceId, db: AsyncSession = Depends(get_db)):
    return await detail(db, proposal_query(AdminProposalDetail).where(Proposal.id == proposal_id))


@router.get("/sessions", response_model=PaginatedResponse[AdminSessionRead])
async def sessions(
    q: Search = None, user_id: PositiveId = None,
    status: Literal["active", "revoked", "expired", "inactive"] | None = None,
    page: Page = 1, page_size: PageSize = 20, db: AsyncSession = Depends(get_db),
):
    session_status = case(
        (AuthSession.revoked_at.is_not(None), "revoked"),
        (AuthSession.expires_at <= utcnow_naive(), "expired"),
        (User.is_active.is_(False), "inactive"),
        else_="active",
    )
    query = select(
        AuthSession.id, AuthSession.user_id, User.email, User.display_name,
        AuthSession.created_at, AuthSession.expires_at, AuthSession.last_seen_at,
        AuthSession.revoked_at, session_status.label("status"),
    ).join(User, User.id == AuthSession.user_id).where(*search_fields(q, User.email, User.display_name))
    if user_id is not None:
        query = query.where(AuthSession.user_id == user_id)
    if status is not None:
        query = query.where(session_status == status)
    return await paginate(db, query.order_by(*date_order(AuthSession, "newest")), AdminSessionRead, page, page_size)
