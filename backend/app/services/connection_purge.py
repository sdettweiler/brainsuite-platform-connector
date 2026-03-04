import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def purge_connection_data(db: AsyncSession, connection_id: str, org_id: str) -> dict:
    conn_uuid = str(connection_id)
    summary = {}
    errors = []

    ownership = await db.execute(text(
        "SELECT id FROM platform_connections WHERE id = :cid AND organization_id = :oid"
    ), {"cid": conn_uuid, "oid": org_id})
    if not ownership.first():
        raise ValueError(f"Connection {conn_uuid} not found or does not belong to organization {org_id}")

    asset_urls = set()
    url_columns = [
        ("dv360_raw_performance", ["thumbnail_url", "asset_url", "video_url"]),
        ("meta_raw_performance", ["thumbnail_url", "asset_url"]),
        ("google_ads_raw_performance", ["thumbnail_url", "video_url"]),
        ("tiktok_raw_performance", ["thumbnail_url", "asset_url"]),
        ("creative_assets", ["thumbnail_url", "asset_url"]),
    ]
    for table, cols in url_columns:
        for col in cols:
            try:
                result = await db.execute(text(
                    f"SELECT DISTINCT {col} FROM {table} "
                    f"WHERE platform_connection_id = :cid AND {col} IS NOT NULL AND {col} != ''"
                ), {"cid": conn_uuid})
                for row in result:
                    url = row[0]
                    if url and url.startswith("/objects/creatives/"):
                        relative = url.replace("/objects/", "", 1)
                        asset_urls.add(relative)
            except Exception:
                pass

    creative_asset_ids = []
    try:
        result = await db.execute(text(
            "SELECT id FROM creative_assets WHERE platform_connection_id = :cid"
        ), {"cid": conn_uuid})
        creative_asset_ids = [str(row[0]) for row in result]
    except Exception:
        pass

    delete_steps = []

    if creative_asset_ids:
        placeholders = ",".join(f"'{aid}'" for aid in creative_asset_ids)
        delete_steps.append(("asset_metadata_values", f"DELETE FROM asset_metadata_values WHERE asset_id IN ({placeholders})"))
        delete_steps.append(("asset_project_mappings", f"DELETE FROM asset_project_mappings WHERE asset_id IN ({placeholders})"))

    delete_steps.append(("harmonized_performance", "DELETE FROM harmonized_performance WHERE platform_connection_id = :cid"))

    for table in ["meta_raw_performance", "tiktok_raw_performance", "google_ads_raw_performance", "dv360_raw_performance"]:
        delete_steps.append((table, f"DELETE FROM {table} WHERE platform_connection_id = :cid"))

    delete_steps.append(("creative_assets", "DELETE FROM creative_assets WHERE platform_connection_id = :cid"))
    delete_steps.append(("sync_jobs", "DELETE FROM sync_jobs WHERE platform_connection_id = :cid"))
    delete_steps.append(("platform_connections", "DELETE FROM platform_connections WHERE id = :cid"))

    for step_name, sql in delete_steps:
        try:
            r = await db.execute(text(sql), {"cid": conn_uuid})
            summary[step_name] = r.rowcount
        except Exception as e:
            err_msg = f"{step_name}: {type(e).__name__}: {e}"
            logger.error(f"Purge step failed — {err_msg}")
            errors.append(err_msg)
            summary[step_name] = 0
            await db.rollback()
            summary["errors"] = errors
            return summary

    await db.commit()

    try:
        from app.services.sync.scheduler import remove_connection_schedule
        remove_connection_schedule(conn_uuid)
    except Exception:
        pass

    deleted_assets = 0
    if asset_urls:
        try:
            from app.services.object_storage import get_object_storage
            obj = get_object_storage()
            for url in asset_urls:
                if obj.delete_blob(url):
                    deleted_assets += 1
        except Exception as e:
            logger.warning(f"Object storage cleanup failed: {type(e).__name__}: {e}")
    summary["object_storage_blobs"] = deleted_assets

    total_rows = sum(v for k, v in summary.items() if k != "object_storage_blobs")
    logger.info(
        f"Purged connection {conn_uuid}: {total_rows} DB rows deleted, "
        f"{deleted_assets} object storage blobs removed"
    )

    if errors:
        summary["errors"] = errors
    return summary
