"""
Creative asset management: projects, metadata, assignments, export.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid

from app.db.base import get_db
from app.models.user import User
from app.models.creative import CreativeAsset, Project, AssetProjectMapping, AssetMetadataValue
from app.models.metadata import MetadataField, MetadataFieldValue
from app.schemas.creative import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    MetadataFieldCreate, MetadataFieldResponse,
    AssetMetadataUpdate, ExportRequest,
)
from app.api.v1.deps import get_current_user, get_current_admin
from app.services.export_service import export_service

router = APIRouter()


# ─── Projects ────────────────────────────────────────────────────────────────

@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(
            Project.organization_id == current_user.organization_id,
            Project.is_active == True,
        )
    )
    projects = result.scalars().all()
    out = []
    for p in projects:
        count_result = await db.execute(
            select(AssetProjectMapping).where(AssetProjectMapping.project_id == p.id)
        )
        count = len(count_result.scalars().all())
        out.append(ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            created_at=p.created_at,
            asset_count=count,
        ))
    return out


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        organization_id=current_user.organization_id,
        created_by_user_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse(id=project.id, name=project.name, description=project.description,
                           created_at=project.created_at, asset_count=0)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project or project.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.add(project)
    await db.commit()
    return ProjectResponse(id=project.id, name=project.name, description=project.description,
                           created_at=project.created_at)


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project or project.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Project not found")
    project.is_active = False
    db.add(project)
    await db.commit()
    return {"detail": "Project deleted"}


@router.post("/projects/{project_id}/assets")
async def assign_assets_to_project(
    project_id: uuid.UUID,
    payload: dict,  # {"asset_ids": [...]}
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project or project.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Project not found")

    asset_ids = payload.get("asset_ids", [])
    for aid in asset_ids:
        asset = await db.get(CreativeAsset, uuid.UUID(str(aid)))
        if not asset or asset.organization_id != current_user.organization_id:
            continue
        # Check for existing mapping
        existing = await db.execute(
            select(AssetProjectMapping).where(
                AssetProjectMapping.asset_id == asset.id,
                AssetProjectMapping.project_id == project_id,
            )
        )
        if not existing.scalar_one_or_none():
            db.add(AssetProjectMapping(asset_id=asset.id, project_id=project_id))

    await db.commit()
    return {"detail": f"Assigned {len(asset_ids)} assets to project"}


# ─── Metadata Fields ─────────────────────────────────────────────────────────

@router.get("/metadata-fields", response_model=List[MetadataFieldResponse])
async def list_metadata_fields(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MetadataField).where(
            MetadataField.organization_id == current_user.organization_id,
            MetadataField.is_active == True,
        ).order_by(MetadataField.sort_order)
    )
    fields = result.scalars().all()
    out = []
    for f in fields:
        vals_result = await db.execute(
            select(MetadataFieldValue).where(
                MetadataFieldValue.field_id == f.id
            ).order_by(MetadataFieldValue.sort_order)
        )
        vals = [{"id": str(v.id), "value": v.value, "label": v.label} for v in vals_result.scalars().all()]
        out.append(MetadataFieldResponse(
            id=f.id,
            name=f.name,
            label=f.label,
            field_type=f.field_type,
            is_required=f.is_required,
            default_value=f.default_value,
            allowed_values=vals,
            created_at=f.created_at,
        ))
    return out


@router.post("/metadata-fields", response_model=MetadataFieldResponse, status_code=201)
async def create_metadata_field(
    payload: MetadataFieldCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    field = MetadataField(
        organization_id=current_user.organization_id,
        name=payload.name,
        label=payload.label,
        field_type=payload.field_type,
        is_required=payload.is_required,
        default_value=payload.default_value,
    )
    db.add(field)
    await db.flush()

    vals = []
    for i, v in enumerate(payload.allowed_values):
        fv = MetadataFieldValue(
            field_id=field.id,
            value=v["value"],
            label=v["label"],
            sort_order=i,
        )
        db.add(fv)
        vals.append({"id": str(fv.id), "value": v["value"], "label": v["label"]})

    await db.commit()
    return MetadataFieldResponse(
        id=field.id, name=field.name, label=field.label,
        field_type=field.field_type, is_required=field.is_required,
        default_value=field.default_value, allowed_values=vals,
        created_at=field.created_at,
    )


@router.delete("/metadata-fields/{field_id}")
async def delete_metadata_field(
    field_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    field = await db.get(MetadataField, field_id)
    if not field or field.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Field not found")
    field.is_active = False
    db.add(field)
    await db.commit()
    return {"detail": "Field deleted"}


# ─── Asset Metadata Values ───────────────────────────────────────────────────

@router.patch("/{asset_id}/metadata")
async def update_asset_metadata(
    asset_id: uuid.UUID,
    payload: AssetMetadataUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await db.get(CreativeAsset, asset_id)
    if not asset or asset.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    for field_id_str, value in payload.metadata.items():
        field_id = uuid.UUID(field_id_str)
        existing = await db.execute(
            select(AssetMetadataValue).where(
                AssetMetadataValue.asset_id == asset_id,
                AssetMetadataValue.field_id == field_id,
            )
        )
        rec = existing.scalar_one_or_none()
        if rec:
            rec.value = value
            db.add(rec)
        else:
            db.add(AssetMetadataValue(asset_id=asset_id, field_id=field_id, value=value))

    await db.commit()
    return {"detail": "Metadata updated"}


@router.patch("/bulk-metadata")
async def bulk_update_metadata(
    payload: dict,  # {"asset_ids": [...], "metadata": {...}}
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset_ids = [uuid.UUID(str(aid)) for aid in payload.get("asset_ids", [])]
    metadata = payload.get("metadata", {})

    for asset_id in asset_ids:
        asset = await db.get(CreativeAsset, asset_id)
        if not asset or asset.organization_id != current_user.organization_id:
            continue
        for field_id_str, value in metadata.items():
            field_id = uuid.UUID(field_id_str)
            existing = await db.execute(
                select(AssetMetadataValue).where(
                    AssetMetadataValue.asset_id == asset_id,
                    AssetMetadataValue.field_id == field_id,
                )
            )
            rec = existing.scalar_one_or_none()
            if rec:
                rec.value = value
                db.add(rec)
            else:
                db.add(AssetMetadataValue(asset_id=asset_id, field_id=field_id, value=value))

    await db.commit()
    return {"detail": f"Metadata updated for {len(asset_ids)} assets"}


# ─── Export ──────────────────────────────────────────────────────────────────

@router.get("/export/fields")
async def get_export_fields(current_user: User = Depends(get_current_user)):
    return export_service.get_available_fields()


@router.post("/export")
async def export_assets(
    payload: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date, timedelta
    from app.models.performance import HarmonizedPerformance
    from app.services.export_service import (
        SUMMABLE_INT_FIELDS, SUMMABLE_DECIMAL_FIELDS, RATIO_FORMULAS,
        WEIGHTED_AVG_FIELDS, _safe_div,
    )
    from sqlalchemy import func, case, cast, Float as SAFloat

    date_from = payload.date_from or (date.today() - timedelta(days=30))
    date_to = payload.date_to or (date.today() - timedelta(days=1))

    agg_cols = [HarmonizedPerformance.asset_id]
    for f in SUMMABLE_INT_FIELDS:
        col = getattr(HarmonizedPerformance, f, None)
        if col is not None:
            agg_cols.append(func.coalesce(func.sum(col), 0).label(f))
    for f in SUMMABLE_DECIMAL_FIELDS:
        col = getattr(HarmonizedPerformance, f, None)
        if col is not None:
            agg_cols.append(func.coalesce(func.sum(col), 0).label(f))
    for wf, (weight_field,) in WEIGHTED_AVG_FIELDS.items():
        col = getattr(HarmonizedPerformance, wf, None)
        weight_col = getattr(HarmonizedPerformance, weight_field, None)
        if col is not None and weight_col is not None:
            agg_cols.append(
                case(
                    (func.sum(weight_col) > 0,
                     func.sum(col * weight_col) / func.sum(weight_col)),
                    else_=None,
                ).label(wf)
            )
    for sf in ["quality_ranking", "engagement_rate_ranking", "conversion_rate_ranking", "creative_fatigue"]:
        col = getattr(HarmonizedPerformance, sf, None)
        if col is not None:
            agg_cols.append(func.max(col).label(sf))

    perf_subq = (
        select(*agg_cols)
        .where(
            HarmonizedPerformance.report_date >= date_from,
            HarmonizedPerformance.report_date <= date_to,
        )
        .group_by(HarmonizedPerformance.asset_id)
        .subquery()
    )

    query = (
        select(CreativeAsset, perf_subq)
        .outerjoin(perf_subq, perf_subq.c.asset_id == CreativeAsset.id)
        .where(CreativeAsset.organization_id == current_user.organization_id)
    )

    if payload.platforms:
        query = query.where(CreativeAsset.platform.in_(payload.platforms))
    if payload.asset_ids:
        query = query.where(CreativeAsset.id.in_(payload.asset_ids))

    result = await db.execute(query)

    assets_data = []
    for row in result.all():
        asset = row[0]

        sums = {}
        for f in SUMMABLE_INT_FIELDS:
            sums[f] = int(getattr(row, f, 0) or 0)
        for f in SUMMABLE_DECIMAL_FIELDS:
            sums[f] = float(getattr(row, f, 0) or 0)

        ratios = {}
        for key, formula in RATIO_FORMULAS.items():
            ratios[key] = round(formula(sums), 4)

        weighted = {}
        for wf in WEIGHTED_AVG_FIELDS:
            val = getattr(row, wf, None)
            weighted[wf] = round(float(val), 2) if val is not None else None

        rankings = {}
        for sf in ["quality_ranking", "engagement_rate_ranking", "conversion_rate_ranking", "creative_fatigue"]:
            rankings[sf] = getattr(row, sf, None)

        brainsuite = asset.brainsuite_metadata or {}

        entry = {
            "ad_name": asset.ad_name or "",
            "ad_id": asset.ad_id or "",
            "creative_id": asset.creative_id or "",
            "platform": asset.platform,
            "asset_format": asset.asset_format or "",
            "campaign_id": asset.campaign_id or "",
            "campaign_name": asset.campaign_name or "",
            "campaign_objective": asset.campaign_objective or "",
            "ad_set_id": asset.ad_set_id or "",
            "ad_set_name": asset.ad_set_name or "",
            "ad_account_id": asset.ad_account_id or "",
            "publisher_platform": "",
            "platform_position": "",
            "org_currency": "",
            "original_currency": "",
            **sums,
            **ratios,
            **weighted,
            **rankings,
            "ace_score": asset.ace_score,
            "attention_score": brainsuite.get("attention_score"),
            "brand_score": brainsuite.get("brand_score"),
            "emotion_score": brainsuite.get("emotion_score"),
            "message_clarity": brainsuite.get("message_clarity"),
            "visual_impact": brainsuite.get("visual_impact"),
        }
        assets_data.append(entry)

    rows = export_service.prepare_rows(assets_data, payload.fields, date_from, date_to)

    fmt = payload.format.lower()
    if fmt == "csv":
        content = export_service.generate_csv(rows)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=brainsuite_export.csv"},
        )
    elif fmt in ("excel", "xlsx"):
        content = export_service.generate_excel(rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=brainsuite_export.xlsx"},
        )
    elif fmt == "pdf":
        content = export_service.generate_pdf(rows)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=brainsuite_export.pdf"},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Invalid format: {payload.format}")


# ─── Metadata field path aliases (frontend uses /metadata/fields/...) ─────────

@router.get("/metadata/fields", response_model=List[MetadataFieldResponse])
async def list_metadata_fields_v2(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Alias for /metadata-fields for frontend compatibility."""
    result = await db.execute(
        select(MetadataField).where(
            MetadataField.organization_id == current_user.organization_id,
            MetadataField.is_active == True,
        ).order_by(MetadataField.sort_order)
    )
    fields = result.scalars().all()
    out = []
    for f in fields:
        vals_result = await db.execute(
            select(MetadataFieldValue).where(MetadataFieldValue.field_id == f.id).order_by(MetadataFieldValue.sort_order)
        )
        vals = [{"id": str(v.id), "value": v.value, "label": v.label, "sort_order": v.sort_order} for v in vals_result.scalars().all()]
        out.append(MetadataFieldResponse(
            id=f.id, name=f.name, label=f.label, field_type=f.field_type,
            is_required=f.is_required, default_value=f.default_value,
            allowed_values=vals, created_at=f.created_at,
        ))
    return out


@router.post("/metadata/fields", response_model=MetadataFieldResponse, status_code=201)
async def create_metadata_field_v2(
    payload: MetadataFieldCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    field = MetadataField(
        organization_id=current_user.organization_id,
        name=payload.name, label=payload.label,
        field_type=payload.field_type, is_required=payload.is_required,
        default_value=payload.default_value,
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return MetadataFieldResponse(id=field.id, name=field.name, label=field.label,
                                  field_type=field.field_type, is_required=field.is_required,
                                  default_value=field.default_value, allowed_values=[],
                                  created_at=field.created_at)


@router.patch("/metadata/fields/{field_id}", response_model=MetadataFieldResponse)
async def update_metadata_field_v2(
    field_id: uuid.UUID,
    payload: dict,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    field = await db.get(MetadataField, field_id)
    if not field or field.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Field not found")
    allowed = {"name", "label", "field_type", "is_required", "default_value"}
    for k, v in payload.items():
        if k in allowed:
            setattr(field, k, v)
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return MetadataFieldResponse(id=field.id, name=field.name, label=field.label,
                                  field_type=field.field_type, is_required=field.is_required,
                                  default_value=field.default_value, allowed_values=[],
                                  created_at=field.created_at)


@router.delete("/metadata/fields/{field_id}")
async def delete_metadata_field_v2(
    field_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    field = await db.get(MetadataField, field_id)
    if not field or field.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Field not found")
    field.is_active = False
    db.add(field)
    await db.commit()
    return {"detail": "Field deleted"}


@router.put("/metadata/fields/{field_id}/values")
async def update_field_values(
    field_id: uuid.UUID,
    payload: dict,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    field = await db.get(MetadataField, field_id)
    if not field or field.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Field not found")

    # Delete existing values
    await db.execute(delete(MetadataFieldValue).where(MetadataFieldValue.field_id == field_id))

    values = payload.get("values", [])
    for i, v in enumerate(values):
        db.add(MetadataFieldValue(
            field_id=field_id,
            value=v.get("value", ""),
            label=v.get("label", ""),
            sort_order=i,
        ))

    await db.commit()
    return {"detail": f"Saved {len(values)} options"}


@router.post("/metadata/fields/reorder")
async def reorder_metadata_fields(
    payload: dict,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    order = payload.get("order", [])
    for item in order:
        field = await db.get(MetadataField, uuid.UUID(item["id"]))
        if field and field.organization_id == current_user.organization_id:
            field.sort_order = item["sort_order"]
            db.add(field)
    await db.commit()
    return {"detail": "Order updated"}
