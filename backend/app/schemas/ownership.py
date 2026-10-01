from datetime import datetime
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.organization_member import OrganizationMemberRole
from app.models.organization import normalize_slug
from app.models.team_member import TeamMemberRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    is_admin: bool = False
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def include_avatar_url(cls, value):
        if not isinstance(value, dict):
            filename = getattr(value, "avatar_filename", None)
            data = {key: getattr(value, key) for key in ("id", "email", "display_name", "is_admin", "created_at", "updated_at")}
            # An opaque revision changes the image src after replacement without
            # exposing the stored filename. The route always checks the session.
            revision = sha256(filename.encode()).hexdigest()[:16] if filename else None
            data["avatar_url"] = f"/api/v1/users/me/avatar?v={revision}" if revision else None
            return data
        return value


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120)

    @field_validator("slug")
    @classmethod
    def normalized_slug_must_fit_column(cls, value: str) -> str:
        value = normalize_slug(value)
        if len(value) > 120:
            raise ValueError("normalized slug must have at most 120 characters")
        return value

    @field_validator("name", "slug")
    @classmethod
    def values_must_not_be_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be whitespace only")
        return value


class OrganizationMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    user_id: int
    role: OrganizationMemberRole
    created_at: datetime


class TeamMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    user_id: int
    role: TeamMemberRole
    created_at: datetime
