from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(max_length=200)

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value
