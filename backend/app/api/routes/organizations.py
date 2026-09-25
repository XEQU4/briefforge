from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.authorization import require_organization_member
from app.core.db import get_db
from app.models import Organization, OrganizationMember, OrganizationMemberRole, User
from app.schemas.ownership import OrganizationCreate, OrganizationRead

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
