from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


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
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    rating_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating_breakdown: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    readiness_level: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    questions: Mapped[list["ClarifyingQuestion"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="ClarifyingQuestion.order",
    )
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class ClarifyingQuestion(Base):
    __tablename__ = "clarifying_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    task: Mapped[Task] = relationship(back_populates="questions")
