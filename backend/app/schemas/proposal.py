from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.status import ProposalStatus


class ProposalCreate(BaseModel):
    team_id: int
    idea: str = Field(min_length=1)
    plan: str | None = None
    deadline: str | None = None
    link: str | None = None

    @field_validator("idea")
    @classmethod
    def idea_must_contain_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idea cannot be empty")
        return value


class ProposalUpdate(BaseModel):
    status: ProposalStatus


class ProposalRead(ProposalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    status: ProposalStatus
    created_at: datetime | None = None
