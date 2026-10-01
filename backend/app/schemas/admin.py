from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool

from app.domain.status import ProposalStatus, TaskPublicationStatus, TaskStatus
from app.schemas.task import TaskRead


class AdminSummary(BaseModel):
    users: int
    active_users: int
    organizations: int
    teams: int
    tasks: int
    published_tasks: int
    proposals: int
    pending_proposals: int
    active_sessions: int


class AdminUserRead(BaseModel):
    id: int
    email: str
    display_name: str | None
    is_active: bool
    is_admin: bool
    has_avatar: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminUserDetail(AdminUserRead):
    organization_membership_count: int
    team_membership_count: int
    created_task_count: int
    submitted_proposal_count: int
    active_session_count: int


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: StrictBool


class RevokedSessions(BaseModel):
    revoked_count: int


class AdminOrganizationRead(BaseModel):
    id: int
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime
    member_count: int
    task_count: int


class AdminTeamRead(BaseModel):
    id: int
    name: str
    interests: str | None
    skills: str | None
    technologies: str | None
    member_count: int
    proposal_count: int


class AdminTaskRead(BaseModel):
    id: int
    title: str | None
    organization_id: int | None
    created_by_user_id: int | None
    status: TaskStatus
    publication_status: TaskPublicationStatus
    rating_score: int
    readiness_level: str
    created_at: datetime
    updated_at: datetime


class AdminTaskDetail(TaskRead):
    organization_id: int | None
    created_by_user_id: int | None


class AdminProposalRead(BaseModel):
    id: int
    task_id: int
    team_id: int
    submitted_by_user_id: int | None
    idea: str
    status: ProposalStatus
    created_at: datetime


class AdminProposalDetail(AdminProposalRead):
    plan: str | None
    deadline: str | None
    link: str | None


class AdminSessionRead(BaseModel):
    id: int
    user_id: int
    email: str
    display_name: str | None
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None
    status: Literal["active", "revoked", "expired", "inactive"]
