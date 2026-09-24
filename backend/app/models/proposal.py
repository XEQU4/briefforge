from datetime import datetime

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domain.status import ProposalStatus


def _proposal_status_values(enum_type):
    return [member.value for member in enum_type]


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    idea: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[ProposalStatus] = mapped_column(
        SqlEnum(
            ProposalStatus,
            native_enum=False,
            create_constraint=False,
            values_callable=_proposal_status_values,
            length=20,
        ),
        default=ProposalStatus.PENDING,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    task: Mapped["Task"] = relationship(back_populates="proposals")
    team: Mapped["Team"] = relationship(back_populates="proposals")
