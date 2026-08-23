import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_token import ApiToken
from app.models.household import Household, HouseholdInvite, HouseholdMembership
from app.models.maintenance_record import MaintenanceRecord
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.sync_device import SyncDevice
from app.models.user import User


class UserOwnsHouseholdsError(Exception):
    """Raised instead of deleting when the user owns at least one household
    — deleting them would leave that household's owner_user_id dangling.
    Carries the household ids/names so the caller can surface a useful
    error rather than a bare 400."""

    def __init__(self, households: list[tuple[uuid.UUID, str]]) -> None:
        self.households = households
        super().__init__(f"User owns {len(households)} household(s)")


async def delete_user_data(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Hard-deletes a user (Vikunja #101's "purge" tool) and every row that
    exists only because of them — auth infrastructure (refresh/password-
    reset tokens, API tokens, paired sync devices) and their household
    memberships/created-invites. Does NOT touch household *data* (assets,
    fuel logs, etc.) — a user being removed says nothing about whether the
    household they belonged to should lose its data too; that's the
    separate delete_household_data/wipe_household_data path if a caller
    wants that as well.

    Raises UserOwnsHouseholdsError instead of proceeding if the user owns
    any household — deleting them would leave that household's
    owner_user_id pointing at nobody. The caller (an instance admin) needs
    to either delete/transfer that household first or choose to leave the
    user in place. Doesn't commit — that's left to the caller.
    """
    owned = (
        await db.execute(select(Household.id, Household.name).where(Household.owner_user_id == user_id))
    ).all()
    if owned:
        raise UserOwnsHouseholdsError([(household_id, name) for household_id, name in owned])

    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))
    await db.execute(delete(ApiToken).where(ApiToken.user_id == user_id))
    await db.execute(delete(SyncDevice).where(SyncDevice.user_id == user_id))
    await db.execute(delete(HouseholdInvite).where(HouseholdInvite.created_by_user_id == user_id))
    await db.execute(
        update(HouseholdMembership)
        .where(HouseholdMembership.invited_by_user_id == user_id)
        .values(invited_by_user_id=None)
    )
    await db.execute(
        update(MaintenanceRecord)
        .where(MaintenanceRecord.performed_by_user_id == user_id)
        .values(performed_by_user_id=None)
    )
    await db.execute(delete(HouseholdMembership).where(HouseholdMembership.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))
