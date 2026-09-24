from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domain.status import TaskStatus


def _enum_values(enum_type):
    return [member.value for member in enum_type]


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    need: Mapped[str | None] = mapped_column(Text, nullable=True)
    users: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_materials: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact: Mapped[str | None] = mapped_column(String(500), nullable=True)
    interaction_format: Mapped[str | None] = mapped_column(String(500), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(
            TaskStatus,
            native_enum=False,
            create_constraint=False,
            values_callable=_enum_values,
            length=30,
        ),
        default=TaskStatus.DRAFT,
        nullable=False,
        index=True,
    )
    rating_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    rating_breakdown: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    readiness_level: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", name="fk_tasks_organization_id_organizations", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_tasks_created_by_user_id_users", ondelete="SET NULL"), nullable=True, index=True
    )

    questions: Mapped[list["ClarifyingQuestion"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="ClarifyingQuestion.order",
    )
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="task", passive_deletes="all")
    organization: Mapped["Organization | None"] = relationship(back_populates="tasks")
    created_by: Mapped["User | None"] = relationship(back_populates="created_tasks", foreign_keys=[created_by_user_id])


class ClarifyingQuestion(Base):
    __tablename__ = "clarifying_questions"
    __table_args__ = (
        UniqueConstraint("task_id", "order", name="uq_clarifying_questions_task_id_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    task: Mapped[Task] = relationship(back_populates="questions")
