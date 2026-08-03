from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. Every model module must import this so Alembic's
    autogenerate (app/db/session.py -> Base.metadata) sees the full schema."""
