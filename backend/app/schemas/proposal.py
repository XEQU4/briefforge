from datetime import datetime
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.domain.status import ProposalStatus
from app.schemas.limits import ResourceId


class ProposalFields(BaseModel):
    team_id: int
    idea: str = Field(min_length=1)
    plan: str | None = None
    deadline: str | None = Field(default=None, max_length=100)
    link: str | None = Field(default=None, max_length=1000)

    @field_validator("idea")
    @classmethod
    def idea_must_contain_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idea cannot be empty")
        return value


class ProposalCreate(ProposalFields):
    team_id: ResourceId

    @field_validator("link")
    @classmethod
    def link_must_be_absolute_web_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        if (
            not re.match(r"^https?://", value, re.IGNORECASE)
            or re.search(r"[\x00-\x20\x7f\\]", value)
            or not urlsplit(value).netloc
        ):
            raise ValueError("link must be an absolute http or https URL")
        HttpUrl(value)
        return value


class ProposalUpdate(BaseModel):
    status: ProposalStatus


class ProposalRead(ProposalFields):
    # Existing links remain readable; URL validation applies to new submissions.
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    status: ProposalStatus
    created_at: datetime | None = None
