from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.ownership import UserRead


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str | None = Field(default=None, max_length=200)

    @field_validator("password")
    @classmethod
    def password_must_not_be_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("password must not be whitespace only")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserRead
