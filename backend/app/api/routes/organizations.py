from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.authorization import require_organization_member
from app.core.db import get_db
from app.domain.status import TaskPublicationStatus, TaskStatus
from app.models import Organization, OrganizationMember, OrganizationMemberRole, Task, User
from app.schemas.ownership import OrganizationCreate, OrganizationRead
from app.schemas.pagination import PaginatedResponse
from app.schemas.task import TaskRead

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Organization:
    organization = Organization(name=payload.name, slug=payload.slug)
    db.add(organization)
    db.add(OrganizationMember(organization=organization, user_id=user.id, role=OrganizationMemberRole.OWNER))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An organization with this slug already exists") from exc
    await db.refresh(organization)
    return organization


@router.get("/mine", response_model=list[OrganizationRead])
async def list_my_organizations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Organization]:
    result = await db.execute(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Organization.name, Organization.id)
    )
    return list(result.scalars().all())


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/{organization_id}/tasks", response_model=PaginatedResponse[TaskRead])
async def list_organization_tasks(
    organization_id: int,
    response: Response,
    q: str | None = Query(None, max_length=200),
    task_status: TaskStatus | None = Query(None, alias="status"),
    publication_status: TaskPublicationStatus | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("newest"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    organization = await db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    await require_organization_member(organization_id, user, db)
    response.headers["Cache-Control"] = "private, no-store"

    if sort not in {"newest", "oldest", "rating"}:
        raise HTTPException(status_code=422, detail="sort must be newest, oldest, or rating")
    filters = [Task.organization_id == organization_id]
    if task_status is not None:
        filters.append(Task.status == task_status)
    if publication_status is not None:
        filters.append(Task.publication_status == publication_status)
    normalized_q = (q or "").strip()
    if normalized_q:
        pattern = f"%{_escape_like(normalized_q)}%"
        filters.append(or_(
            Task.title.ilike(pattern, escape="\\"),
            Task.context.ilike(pattern, escape="\\"),
            Task.need.ilike(pattern, escape="\\"),
            Task.topic.ilike(pattern, escape="\\"),
        ))

    query = select(Task).where(*filters)
    if sort == "newest":
        query = query.order_by(Task.created_at.desc(), Task.id.desc())
    elif sort == "oldest":
        query = query.order_by(Task.created_at.asc(), Task.id.asc())
    else:
        query = query.order_by(Task.rating_score.desc(), Task.id.desc())

    total = await db.scalar(select(func.count()).select_from(Task).where(*filters)) or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return PaginatedResponse[TaskRead].build(list(result.scalars().all()), page, page_size, total)


@router.get("/{organization_id}", response_model=OrganizationRead)
async def get_organization(
    organization_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Organization:
    organization = await db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    await require_organization_member(organization_id, user, db)
    return organization
