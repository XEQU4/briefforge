"""Request bounds compatible with PostgreSQL Integer columns and offsets."""
from typing import Annotated

from pydantic import Field


MAX_DATABASE_ID = 2_147_483_647
MAX_PAGE_SIZE = 100
# Even the largest allowed page_size must produce a signed 32-bit offset.
MAX_PAGE = MAX_DATABASE_ID // MAX_PAGE_SIZE + 1
ResourceId = Annotated[int, Field(ge=1, le=MAX_DATABASE_ID)]
