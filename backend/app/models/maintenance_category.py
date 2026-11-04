# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import SyncedEntityMixin


class MaintenanceCategory(SyncedEntityMixin, Base):
    """A household's remembered custom service-type names -- picking one in
    the mobile app's category picker still writes the fixed "custom"
    sentinel + free text onto the MaintenanceRecord itself (unchanged), so
    this table is a pure remembered-name list for the picker, not a foreign
    key target. Renaming/deleting a row here never touches historical
    records' own text. Mirrors the mobile shared module's
    `maintenanceCategory` table (see WrinkleByte.sq in the companion mobile
    repo)."""

    __tablename__ = "maintenance_categories"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
