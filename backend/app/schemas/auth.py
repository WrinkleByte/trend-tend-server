import uuid
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, model_validator

# Password policy (2026-08-19 review, S4). Previously `password: str` with no
# constraint at all -- "a" was a valid password on both register and reset.
#
# Length-only, deliberately: NIST SP 800-63B advises *against* forced
# composition rules (mixed case / digits / symbols), which push people toward
# predictable mutations like "Password1!" without adding real entropy. Length
# is what actually helps, so that's what we require.
#
# The maximum is a denial-of-service bound rather than a security limit --
# Argon2 is intentionally slow, so accepting an unbounded password means
# accepting unbounded server-side work per login attempt.
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

Password = Annotated[
    str,
    Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description=f"At least {MIN_PASSWORD_LENGTH} characters.",
    ),
]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
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
    # Deliberately NOT the constrained Password type. Login must accept any
    # string and simply fail verification: accounts created before the policy
    # existed still have short passwords and must remain able to log in (and
    # then change it), and rejecting at the schema would tell an attacker the
    # policy's exact bounds for free.
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
    new_password: Password
