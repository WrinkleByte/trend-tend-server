import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_current_principal, household_scoped_query
from app.db.session import get_db
from app.models.asset import Asset, EquipmentDetails, PropertyDetails, VehicleDetails
from app.models.attachment import Attachment
from app.models.mixins import utcnow
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate

router = APIRouter(prefix="/assets", tags=["assets"])


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name != "asset_id"}


async def _load_details(db: AsyncSession, asset: Asset) -> dict:
    extra: dict = {}
    if asset.asset_type == "vehicle":
        result = await db.execute(select(VehicleDetails).where(VehicleDetails.asset_id == asset.id))
        extra["vehicle_details"] = _row_to_dict(result.scalar_one_or_none())
    elif asset.asset_type == "equipment":
        result = await db.execute(select(EquipmentDetails).where(EquipmentDetails.asset_id == asset.id))
        extra["equipment_details"] = _row_to_dict(result.scalar_one_or_none())
    elif asset.asset_type in ("property", "home_system"):
        result = await db.execute(select(PropertyDetails).where(PropertyDetails.asset_id == asset.id))
        extra["property_details"] = _row_to_dict(result.scalar_one_or_none())
    return extra


def _to_response(asset: Asset, details: dict) -> AssetResponse:
    return AssetResponse.model_validate({**asset.__dict__, **details})


@router.get("", response_model=list[AssetResponse])
async def list_assets(
    principal: Principal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> list[AssetResponse]:
    result = await db.execute(household_scoped_query(Asset, principal).order_by(Asset.name))
    assets = result.scalars().all()
    responses = []
    for asset in assets:
        details = await _load_details(db, asset)
        responses.append(_to_response(asset, details))
    return responses


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AssetResponse:
    asset = Asset(
        id=uuid.uuid4(),
        household_id=principal.household_id,
        asset_type=payload.asset_type,
        name=payload.name,
        notes=payload.notes,
        purchase_date=payload.purchase_date,
        purchase_cost=payload.purchase_cost,
        updated_by_device_id=principal.device_id,
    )
    db.add(asset)
    await db.flush()

    if payload.vehicle_details:
        db.add(VehicleDetails(asset_id=asset.id, **payload.vehicle_details.model_dump()))
    if payload.equipment_details:
        db.add(EquipmentDetails(asset_id=asset.id, **payload.equipment_details.model_dump()))
    if payload.property_details:
        db.add(PropertyDetails(asset_id=asset.id, **payload.property_details.model_dump()))

    await db.commit()
    await db.refresh(asset)
    details = await _load_details(db, asset)
    return _to_response(asset, details)


async def _get_owned_asset(db: AsyncSession, principal: Principal, asset_id: uuid.UUID) -> Asset:
    result = await db.execute(household_scoped_query(Asset, principal).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    return asset


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AssetResponse:
    asset = await _get_owned_asset(db, principal, asset_id)
    details = await _load_details(db, asset)
    return _to_response(asset, details)


@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AssetResponse:
    asset = await _get_owned_asset(db, principal, asset_id)

    for field in ("name", "notes", "status", "purchase_date", "purchase_cost"):
        value = getattr(payload, field)
        if value is not None:
            setattr(asset, field, value)
    asset.updated_by_device_id = principal.device_id
    asset.version += 1
    asset.updated_at = utcnow()

    if payload.vehicle_details:
        await db.execute(
            VehicleDetails.__table__.delete().where(VehicleDetails.asset_id == asset.id)
        )
        db.add(VehicleDetails(asset_id=asset.id, **payload.vehicle_details.model_dump()))
    if payload.equipment_details:
        await db.execute(
            EquipmentDetails.__table__.delete().where(EquipmentDetails.asset_id == asset.id)
        )
        db.add(EquipmentDetails(asset_id=asset.id, **payload.equipment_details.model_dump()))
    if payload.property_details:
        await db.execute(
            PropertyDetails.__table__.delete().where(PropertyDetails.asset_id == asset.id)
        )
        db.add(PropertyDetails(asset_id=asset.id, **payload.property_details.model_dump()))

    await db.commit()
    await db.refresh(asset)
    details = await _load_details(db, asset)
    return _to_response(asset, details)


@router.delete("/{asset_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
async def remove_asset_photo(
    asset_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    asset = await _get_owned_asset(db, principal, asset_id)
    photo_attachment_id = asset.photo_attachment_id
    if photo_attachment_id is None:
        return
    asset.photo_attachment_id = None
    asset.updated_by_device_id = principal.device_id
    asset.version += 1
    asset.updated_at = utcnow()

    # Same soft-delete-metadata-only tradeoff as attachments.delete_attachment
    # -- the blob is left in place rather than adding cascade-delete logic.
    result = await db.execute(select(Attachment).where(Attachment.id == photo_attachment_id))
    attachment = result.scalar_one_or_none()
    if attachment is not None:
        attachment.deleted_at = utcnow()
        attachment.updated_by_device_id = principal.device_id
        attachment.version += 1

    await db.commit()


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    asset = await _get_owned_asset(db, principal, asset_id)
    asset.deleted_at = utcnow()
    asset.updated_by_device_id = principal.device_id
    asset.version += 1
    await db.commit()
