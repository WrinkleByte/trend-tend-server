import uuid

from pydantic import BaseModel, EmailStr, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    household_name: str | None = None
    # When set, registration joins the invite's existing household (with its
    # role) instead of creating a new one — household_name is ignored in
    # that case. See app/api/v1/auth.py's register().
    invite_token: str | None = None

    @model_validator(mode="after")
    def _household_name_required_without_invite(self) -> "RegisterRequest":
        if self.invite_token is None and not self.household_name:
            raise ValueError("household_name is required unless invite_token is provided")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str

    model_config = {"from_attributes": True}


class SetupStatusResponse(BaseModel):
    # False only until the very first user ever registers — see
    # api/v1/auth.py's setup_status(). Web/mobile clients use this to show
    # a "Create Admin Account" screen instead of the normal login form on a
    # freshly-deployed, empty instance.
    setup_complete: bool


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
