from pydantic import BaseModel, ConfigDict, Field, field_validator


class TeamFields(BaseModel):
    name: str = Field(min_length=1)
    interests: str | None = None
    skills: str | None = None
    technologies: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_contain_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name cannot be empty")
        return value


class TeamCreate(TeamFields):
    pass


class TeamUpdate(BaseModel):
    name: str | None = None
    interests: str | None = None
    skills: str | None = None
    technologies: str | None = None


class TeamRead(TeamFields):
    model_config = ConfigDict(from_attributes=True)
    id: int
