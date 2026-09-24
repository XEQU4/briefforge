from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.status import TaskStatus


class TaskFields(BaseModel):
    title: str | None = None
    context: str | None = None
    need: str | None = None
    users: str | None = None
    data_materials: str | None = None
    constraints: str | None = None
    expected_result: str | None = None
    success_criteria: str | None = None
    contact: str | None = None
    interaction_format: str | None = None
    topic: str | None = None


class TaskCreate(BaseModel):
    draft_text: str = Field(min_length=1)
    topic: str | None = None

    @field_validator("draft_text")
    @classmethod
    def draft_text_must_contain_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("draft_text cannot be empty")
        return value


class TaskUpdate(TaskFields):
    model_config = ConfigDict(extra="forbid")


class TaskRead(TaskFields):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: TaskStatus
    rating_score: int
    rating_breakdown: dict[str, Any]
    readiness_level: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    question_text: str
    answer_text: str | None = None
    order: int


class QuestionCreate(BaseModel):
    task_id: int
    question_text: str
    answer_text: str | None = None
    order: int


class QuestionUpdate(BaseModel):
    question_text: str | None = None
    answer_text: str | None = None
    order: int | None = None


class TaskWithQuestions(BaseModel):
    task: TaskRead
    questions: list[QuestionRead]


class AnswersSubmit(BaseModel):
    answers: list[str] | dict[str, str]
