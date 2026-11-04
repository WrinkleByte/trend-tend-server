# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import uuid

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

# Postgres RLS policies (see the "add row-level security" migration) key
# off these two session-local GUCs:
#   app.household_id          -- the caller's household, checked against
#                                 each row's household_id column.
#   app.bypass_household_rls  -- 'on' only for the narrow, explicitly-gated
#                                 code paths that are deliberately
#                                 cross-household (admin.py, test fixtures).
# Neither is ever read from client input -- both are set exactly once, from
# the already-authenticated Principal, by get_current_principal /
# require_instance_admin in app/api/deps.py.
_HOUSEHOLD_ID_GUC = "app.household_id"
_BYPASS_GUC = "app.bypass_household_rls"

_SET_GUCS_SQL = text(
    "SELECT set_config(:household_key, :household_val, true), "
    "set_config(:bypass_key, :bypass_val, true)"
)


def _guc_params(household_id: uuid.UUID | None, bypass: bool) -> dict:
    return {
        "household_key": _HOUSEHOLD_ID_GUC,
        "household_val": str(household_id) if household_id else "",
        "bypass_key": _BYPASS_GUC,
        "bypass_val": "on" if bypass else "off",
    }


async def set_rls_context(
    db: AsyncSession,
    household_id: uuid.UUID | None,
    *,
    bypass: bool = False,
) -> None:
    """Sets the two GUCs above for the rest of this request.

    set_config's third argument (is_local=true) makes each value scoped to
    the current transaction only -- exactly like SET LOCAL, but usable with
    a real bind parameter (SET LOCAL itself can't be parameterized; the
    value would have to be string-interpolated). That transaction-scoping
    matters because it means a value never survives past a commit and leak
    into a request that reuses the same pooled connection.

    The flip side: a transaction-scoped value doesn't survive an endpoint
    that commits partway through a request and then keeps querying (a new
    transaction auto-begins on the next statement, with the GUC reset to
    unset). The after_begin event below re-applies whatever was last set
    here to every subsequent transaction on this same Session, so that
    pattern -- which nothing does today, but nothing stops a future
    endpoint from doing either -- doesn't silently reopen the gap RLS
    exists to close.
    """
    db.sync_session.info["rls_household_id"] = household_id
    db.sync_session.info["rls_bypass"] = bypass
    await db.execute(_SET_GUCS_SQL, _guc_params(household_id, bypass))


@event.listens_for(Session, "after_begin")
def _reapply_rls_guc_on_new_transaction(session, transaction, connection) -> None:
    """Fires on every transaction this Session opens -- including ones after
    a mid-request commit, which is exactly the case set_rls_context's own
    per-call SET wouldn't otherwise cover. No-ops for any session that never
    called set_rls_context (e.g. an unauthenticated request never reaches
    get_current_principal) -- both GUCs simply stay unset, which the RLS
    policies treat as "show nothing," not "show everything."
    """
    info = session.info
    if "rls_household_id" not in info and "rls_bypass" not in info:
        return
    household_id = info.get("rls_household_id")
    bypass = info.get("rls_bypass", False)
    connection.execute(_SET_GUCS_SQL, _guc_params(household_id, bypass))
