import re
import unicodedata
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.db import Base


def normalize_slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value.strip()).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")
    if not slug:
        raise ValueError("slug must contain URL-safe characters")
    return slug


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    members: Mapped[list["OrganizationMember"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="organization", passive_deletes="all")

    @validates("slug")
    def normalize_organization_slug(self, _key: str, value: str) -> str:
        return normalize_slug(value)
