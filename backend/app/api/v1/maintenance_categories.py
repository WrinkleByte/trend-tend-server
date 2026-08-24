import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal, household_scoped_query
from app.db.session import get_db
from app.models.maintenance_category import MaintenanceCategory
from app.models.mixins import utcnow
from app.schemas.maintenance_category import (
    MaintenanceCategoryCreate,
    MaintenanceCategoryResponse,
    MaintenanceCategoryUpdate,
)

router = APIRouter(prefix="/maintenance-categories", tags=["maintenance-categories"])


@router.get("", response_model=list[MaintenanceCategoryResponse])
async def list_maintenance_categories(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[MaintenanceCategory]:
    query = household_scoped_query(MaintenanceCategory, principal)
    result = await db.execute(query.order_by(MaintenanceCategory.name))
    return list(result.scalars().all())


@router.post("", response_model=MaintenanceCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_maintenance_category(
    payload: MaintenanceCategoryCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceCategory:
    category = MaintenanceCategory(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        updated_by_device_id=principal.device_id,
        **payload.model_dump(),
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def _get_owned_maintenance_category(
    db: AsyncSession, principal: Principal, category_id: uuid.UUID
) -> MaintenanceCategory:
    query = household_scoped_query(MaintenanceCategory, principal).where(MaintenanceCategory.id == category_id)
    result = await db.execute(query)
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance category not found")
    return category


@router.get("/{category_id}", response_model=MaintenanceCategoryResponse)
async def get_maintenance_category(
    category_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceCategory:
    return await _get_owned_maintenance_category(db, principal, category_id)


@router.patch("/{category_id}", response_model=MaintenanceCategoryResponse)
async def update_maintenance_category(
    category_id: uuid.UUID,
    payload: MaintenanceCategoryUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceCategory:
    category = await _get_owned_maintenance_category(db, principal, category_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    category.updated_by_device_id = principal.device_id
    category.version += 1
    category.updated_at = utcnow()
    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_maintenance_category(
    category_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    category = await _get_owned_maintenance_category(db, principal, category_id)
    category.deleted_at = utcnow()
    category.updated_by_device_id = principal.device_id
    category.version += 1
    await db.commit()
