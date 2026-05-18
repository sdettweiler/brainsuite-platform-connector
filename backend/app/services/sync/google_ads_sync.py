"""
Google Ads data sync service.
Uses Google Ads API v23 with GAQL (Google Ads Query Language).
All video ad performance data lives in Google Ads, not YouTube Data API.
"""
import asyncio
import glob
import httpx
import logging
import os
import secrets
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import GoogleAdsRawPerformance
from app.core.security import decrypt_token
from app.services.platform.google_ads_oauth import google_ads_oauth
from app.services.sync.dv360_sync import _CookiesExpiredError


logger = logging.getLogger(__name__)

GOOGLE_ADS_API_BASE = "https://googleads.googleapis.com/v23"


class GoogleAdsSyncService:

    async def sync_date_range(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        date_from: date,
        date_to: date,
        sync_job_id: Optional[str] = None,
    ) -> Dict[str, int]:
        access_token = await self._get_valid_token(db, connection)
        customer_id = connection.ad_account_id

        asset_map = await self._fetch_youtube_asset_map(access_token, customer_id)

        org_id = str(connection.organization_id)

        total_fetched = 0
        total_upserted = 0
        all_asset_queue: Dict[str, Dict[str, str]] = {}

        chunk_start = date_from
        while chunk_start <= date_to:
            chunk_end = min(chunk_start + timedelta(days=29), date_to)
            records = await self._fetch_video_ad_performance(
                access_token, customer_id, chunk_start, chunk_end
            )
            upserted, chunk_queue = await self._upsert_records(
                db, connection, records, sync_job_id, asset_map, org_id
            )
            all_asset_queue.update(chunk_queue)
            total_fetched += len(records)
            total_upserted += upserted
            chunk_start = chunk_end + timedelta(days=1)

        return {"fetched": total_fetched, "upserted": total_upserted, "_asset_queue": all_asset_queue}

    async def _fetch_youtube_asset_map(
        self, access_token: str, customer_id: str
    ) -> Dict[str, str]:
        """Build a map of asset resource name -> YouTube video ID."""
        from app.core.config import settings

        query = """
            SELECT asset.resource_name,
                   asset.youtube_video_asset.youtube_video_id
            FROM asset
            WHERE asset.type = 'YOUTUBE_VIDEO'
        """
        asset_map: Dict[str, str] = {}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/googleAds:search",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "developer-token": settings.GOOGLE_DEVELOPER_TOKEN or "",
                    "login-customer-id": customer_id,
                },
                json={"query": query},
            )
            if resp.status_code == 200:
                for r in resp.json().get("results", []):
                    asset = r.get("asset", {})
                    res_name = asset.get("resourceName", "")
                    yt_id = asset.get("youtubeVideoAsset", {}).get("youtubeVideoId", "")
                    if res_name and yt_id:
                        asset_map[res_name] = yt_id
            else:
                err_text = resp.text
                if "REQUESTED_METRICS_FOR_MANAGER" in err_text:
                    logger.warning(
                        "Google Ads: skipping asset map for customer %s — manager account "
                        "(REQUESTED_METRICS_FOR_MANAGER). Configure a client account instead.",
                        customer_id,
                    )
                else:
                    logger.warning(f"Failed to fetch YouTube assets: {resp.status_code}")

        logger.info(f"Built YouTube asset map with {len(asset_map)} entries for {customer_id}")
        return asset_map

    async def _get_valid_token(
        self, db: AsyncSession, connection: PlatformConnection
    ) -> str:
        """Refresh access token if needed."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        if connection.token_expiry and connection.token_expiry > now:
            return decrypt_token(connection.access_token_encrypted)

        refresh_token = decrypt_token(connection.refresh_token_encrypted)
        new_tokens = await google_ads_oauth.refresh_access_token(refresh_token)
        new_access = new_tokens.get("access_token")

        from app.core.security import encrypt_token
        from datetime import timedelta
        connection.access_token_encrypted = encrypt_token(new_access)
        connection.token_expiry = now + timedelta(seconds=new_tokens.get("expires_in", 3600))
        db.add(connection)
        await db.flush()

        return new_access

    async def _fetch_video_ad_performance(
        self,
        access_token: str,
        customer_id: str,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        """Fetch video ad performance via GAQL."""
        from app.core.config import settings

        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                campaign.advertising_channel_type,
                campaign.advertising_channel_sub_type,
                ad_group.id,
                ad_group.name,
                ad_group_ad.ad.id,
                ad_group_ad.ad.name,
                ad_group_ad.ad.type,
                ad_group_ad.ad.video_ad.video.asset,
                ad_group_ad.ad.video_responsive_ad.videos,
                segments.date,
                metrics.cost_micros,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpm,
                metrics.conversions,
                metrics.conversions_value,
                metrics.video_trueview_views,
                metrics.video_trueview_view_rate,
                metrics.video_quartile_p25_rate,
                metrics.video_quartile_p50_rate,
                metrics.video_quartile_p75_rate,
                metrics.video_quartile_p100_rate,
                metrics.engagements,
                metrics.engagement_rate
            FROM ad_group_ad
            WHERE
                segments.date BETWEEN '{date_from.strftime("%Y-%m-%d")}' AND '{date_to.strftime("%Y-%m-%d")}'
                AND campaign.advertising_channel_type IN ('VIDEO', 'DISPLAY', 'PERFORMANCE_MAX')
                AND ad_group_ad.status != 'REMOVED'
            ORDER BY segments.date DESC
        """

        records = []
        next_page_token = None

        async with httpx.AsyncClient(timeout=60) as client:
            while True:
                body = {"query": query}
                if next_page_token:
                    body["pageToken"] = next_page_token

                resp = await client.post(
                    f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/googleAds:search",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "developer-token": settings.GOOGLE_DEVELOPER_TOKEN or "",
                        "login-customer-id": customer_id,
                    },
                    json=body,
                )

                if resp.status_code != 200:
                    err_text = resp.text
                    if "REQUESTED_METRICS_FOR_MANAGER" in err_text:
                        logger.warning(
                            "Google Ads: skipping customer %s — manager account cannot return metrics "
                            "(REQUESTED_METRICS_FOR_MANAGER). Configure a client account instead.",
                            customer_id,
                        )
                        return []
                    logger.error(f"Google Ads API error {resp.status_code}: {err_text[:500]}")
                    break

                data = resp.json()
                results = data.get("results", [])
                if results:
                    logger.info(f"Fetched {len(results)} records for {customer_id} ({date_from} to {date_to})")
                else:
                    logger.info(f"No results for {customer_id} ({date_from} to {date_to})")
                records.extend(results)

                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break

        logger.info(f"Total records fetched for {customer_id}: {len(records)}")
        return records

    def _extract_youtube_id(
        self, ad: Dict[str, Any], asset_map: Dict[str, str]
    ) -> Optional[str]:
        video_ad = ad.get("videoAd", {})
        asset_ref = video_ad.get("video", {}).get("asset", "")
        if asset_ref and asset_ref in asset_map:
            return asset_map[asset_ref]

        responsive_ad = ad.get("videoResponsiveAd", {})
        videos = responsive_ad.get("videos", [])
        for v in videos:
            asset_ref = v.get("asset", "")
            if asset_ref and asset_ref in asset_map:
                return asset_map[asset_ref]

        return None

    async def _download_thumbnail(
        self,
        youtube_video_id: str,
        org_id: str,
        ad_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()

        filename = f"thumb_yt_{ad_id}.jpg"
        relative_path = f"creatives/{org_id}/{filename}"

        if obj_storage.file_exists(relative_path):
            return None, obj_storage.served_url(relative_path)

        thumb_candidates = [
            f"https://img.youtube.com/vi/{youtube_video_id}/maxresdefault.jpg",
            f"https://img.youtube.com/vi/{youtube_video_id}/sddefault.jpg",
            f"https://img.youtube.com/vi/{youtube_video_id}/hqdefault.jpg",
        ]
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = None
                for thumb_url in thumb_candidates:
                    resp = await client.get(thumb_url)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        break
                resp.raise_for_status()
            served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="image/jpeg")
            logger.info(f"  Downloaded YouTube thumbnail: {filename} ({len(resp.content)} bytes)")
            return None, served_url
        except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
            logger.warning("Failed to download YouTube thumbnail for ad %s (video %s): %s", ad_id, youtube_video_id, e, exc_info=True)
            return None, None

    async def _download_video(
        self,
        youtube_video_id: str,
        org_id: str,
        ad_id: str,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()

        filename = f"vid_yt_{ad_id}.mp4"
        relative_path = f"creatives/{org_id}/{filename}"

        if obj_storage.file_exists(relative_path):
            return None, obj_storage.served_url(relative_path), None

        url = f"https://www.youtube.com/watch?v={youtube_video_id}"

        # Load cookies as a list (primary → backup) — same logic as DV360.
        cookies: List[str] = []
        try:
            from app.db.base import get_session_factory as _gsf_yt
            from app.models.system_config import SystemConfig as _SC_yt
            from sqlalchemy import select as _sel_yt
            async with _gsf_yt()() as _yt_db:
                _cfg = (await _yt_db.execute(_sel_yt(_SC_yt).limit(1))).scalar_one_or_none()
                if _cfg:
                    if _cfg.youtube_cookies_encrypted:
                        try:
                            cookies.append(decrypt_token(_cfg.youtube_cookies_encrypted))
                        except Exception:
                            pass
                    if _cfg.youtube_cookies_backup_encrypted:
                        try:
                            cookies.append(decrypt_token(_cfg.youtube_cookies_backup_encrypted))
                        except Exception:
                            pass
        except Exception as _ck_err:
            logger.warning("Failed to read YT cookies from DB, falling back to env var: %s", _ck_err)
        if not cookies:
            env_primary = os.environ.get("YOUTUBE_COOKIES", "").strip()
            env_backup = os.environ.get("YOUTUBE_COOKIES_BACKUP", "").strip()
            if env_primary:
                cookies.append(env_primary)
            if env_backup:
                cookies.append(env_backup)

        # Load proxy config from shared cache (PERF-04, D-07)
        from app.services.sync.proxy_cache import get_proxy_config
        proxy_enabled, proxy_url = await get_proxy_config()
        if proxy_enabled and proxy_url:
            # Sticky session injection — IPRoyal only (user-session-ID format)
            # Other providers (DataImpulse etc.) use plain user:pass and reject the suffix
            _session_id = secrets.token_urlsafe(9)
            if "@" in proxy_url and "iproyal.com" in proxy_url:
                _user_part, _host_part = proxy_url.rsplit("@", 1)
                if "://" in _user_part:
                    _scheme_end = _user_part.index("://") + 3
                    _scheme = _user_part[:_scheme_end]
                    _creds = _user_part[_scheme_end:]
                    if ":" in _creds:
                        _username, _password = _creds.split(":", 1)
                        proxy_url = f"{_scheme}{_username}-session-{_session_id}:{_password}@{_host_part}"

        tmpdir = tempfile.mkdtemp()
        tmp_base = os.path.join(tmpdir, "video")
        loop = asyncio.get_running_loop()

        async def _extract_info() -> Optional[dict]:
            """Extract video metadata without proxy (PERF-01, D-01).

            Runs direct (no proxy) — only bytes are routed through proxy.
            If direct extraction fails, retries once with proxy as fallback
            for geo-restricted content.
            """
            import yt_dlp

            ydl_opts: dict = {
                "outtmpl": f"{tmp_base}.%(ext)s",
                "quiet": True,
                "socket_timeout": 10,
                "remote_components": ["ejs:github"],
                "ignore_no_formats_error": True,
            }

            def extract_sync() -> Optional[dict]:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            try:
                return await loop.run_in_executor(None, extract_sync)
            except Exception as _e1:
                logger.warning("  Google Ads: direct extraction failed (%s), retrying with proxy", type(_e1).__name__)
                if proxy_enabled and proxy_url:
                    ydl_opts["proxy"] = proxy_url

                    def extract_sync_proxy() -> Optional[dict]:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            return ydl.extract_info(url, download=False)

                    try:
                        return await loop.run_in_executor(None, extract_sync_proxy)
                    except Exception as _e2:
                        logger.warning("  Google Ads: proxy extraction also failed (%s)", type(_e2).__name__)
                return None

        async def _do_download(info_dict: dict, proxy: Optional[str], cookie_data: str) -> bool:
            """Download from pre-extracted info_dict (PERF-01, D-02).

            Uses process_ie_result() so no re-extraction per attempt.
            """
            import yt_dlp

            _expired = [False]

            def _redact(msg: str) -> str:
                """Redact proxy credentials from log/exception message (D-05).
                Pattern: "http://user:pass@geo.iproyal.com:12321" -> "[PROXY:geo.iproyal.com]"
                """
                if not proxy_url:
                    return msg
                import re as _re
                return _re.sub(r'https?://[^@/]+@([^/:]+)[^"\s]*', r'[PROXY:\1]', msg)

            class _YDLLogger:
                def debug(self, msg):
                    if msg.startswith("[debug] "):
                        logger.debug("yt-dlp: %s", _redact(msg))
                    else:
                        logger.info("yt-dlp: %s", _redact(msg))
                def info(self, msg): logger.info("yt-dlp: %s", _redact(msg))
                def warning(self, msg):
                    if "no longer valid" in msg:
                        _expired[0] = True
                    logger.warning("yt-dlp: %s", _redact(msg))
                def error(self, msg):
                    if "no longer valid" in msg:
                        _expired[0] = True
                    logger.error("yt-dlp: %s", _redact(msg))

            ydl_opts: dict = {
                "outtmpl": f"{tmp_base}.%(ext)s",
                "format": "best/b",
                "quiet": True,
                # no_warnings intentionally omitted: suppresses report_warning() even with
                # a custom logger, blocking "no longer valid" detection via warning().
                "socket_timeout": 10,
                "ignore_no_formats_error": True,
                "logger": _YDLLogger(),
                "remote_components": ["ejs:github"],
            }
            if proxy:
                ydl_opts["proxy"] = proxy
            cookie_file = None
            if cookie_data:
                cleaned = "\n".join(
                    line.lstrip() for line in cookie_data.splitlines()
                )
                cookie_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False
                )
                cookie_file.write(cleaned)
                cookie_file.close()
                ydl_opts["cookiefile"] = cookie_file.name

            # Make a deep copy of info_dict so each retry gets a clean copy
            import copy
            info_copy = copy.deepcopy(info_dict)

            def download_sync() -> None:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.process_ie_result(info_copy, download=True)

            try:
                await loop.run_in_executor(None, download_sync)
                if _expired[0]:
                    raise _CookiesExpiredError("YouTube cookies are no longer valid")
                return True
            except _CookiesExpiredError:
                raise
            except Exception as e:
                if _expired[0]:
                    raise _CookiesExpiredError("YouTube cookies are no longer valid") from e
                redacted_error = _redact(str(e))
                logger.error("yt-dlp exception: %s", redacted_error)
                raise
            finally:
                if cookie_file and os.path.exists(cookie_file.name):
                    os.remove(cookie_file.name)

        winning_slot: int | None = None
        try:
            # Extract info once (no proxy) — reused across all download attempts (PERF-01)
            info_dict = await _extract_info()
            if not info_dict:
                logger.warning("  Could not extract info for Google Ads video %s (ad=%s)", youtube_video_id, ad_id)
                return None, None, None

            # Build attempt list (D-04, PERF-03):
            # proxy off: [primary, backup] or [""] if no cookies (existing behavior preserved)
            # proxy on:  ["", primary, backup] — no-proxy/no-cookies first (PO-first)
            attempts = cookies if cookies else [""]
            if proxy_enabled and proxy_url:
                attempts = ["", *attempts]

            # Phase 25 (PERF-02): one semaphore slot per asset, shared across DV360 + Google Ads via proxy_cache
            from app.services.sync.proxy_cache import get_concurrency_semaphore
            semaphore = await get_concurrency_semaphore()
            async with semaphore:
                for i, cookie in enumerate(attempts):
                    if not cookie:
                        label = "no cookies"
                    elif cookies and cookie == cookies[0]:
                        label = "primary"
                    else:
                        label = "backup"
                    logger.info("  Attempting Google Ads video download: %s (ad=%s, cookies=%s)", youtube_video_id, ad_id, label)

                    # D-04: first attempt when proxy enabled = no-proxy/no-cookies (PO auto via bgutil)
                    # subsequent attempts route through proxy
                    if proxy_enabled and proxy_url and i == 0 and not cookie:
                        attempt_proxy: Optional[str] = None
                    else:
                        attempt_proxy = proxy_url if (proxy_enabled and proxy_url) else None

                    try:
                        await _do_download(info_dict, proxy=attempt_proxy, cookie_data=cookie)
                        if cookie and cookies and cookie in cookies:
                            winning_slot = cookies.index(cookie)
                        else:
                            winning_slot = None  # cookieless attempt won
                        break
                    except _CookiesExpiredError:
                        if i < len(attempts) - 1:
                            logger.warning("  Google Ads: cookie attempt %d failed (expired), trying next", i + 1)
                            continue
                        raise
                    except Exception as _attempt_err:
                        if i < len(attempts) - 1:
                            logger.warning("  Google Ads: cookie attempt %d failed (%s), trying next", i + 1, type(_attempt_err).__name__)
                            continue
                        raise

            matches = [m for m in glob.glob(f"{tmp_base}.*") if os.path.getsize(m) > 0]
            actual_path = matches[0] if matches else None
            if actual_path:
                size_mb = os.path.getsize(actual_path) / (1024 * 1024)
                served_url = obj_storage.upload_file(actual_path, relative_path, content_type="video/mp4")
                from app.services.sync.video_utils import get_video_duration as _get_dur
                yt_video_duration = await asyncio.get_event_loop().run_in_executor(None, _get_dur, actual_path)
                logger.info("  Downloaded Google Ads YouTube video: %s (%.1f MB, duration=%s)", filename, size_mb, yt_video_duration)
                try:
                    from sqlalchemy import update as _sa_update
                    from app.models.system_config import SystemConfig as _SC
                    from app.db.base import get_session_factory as _gsf
                    async with _gsf()() as _sc_db:
                        _upd_vals: dict = {"youtube_cookies_download_count": _SC.youtube_cookies_download_count + 1}
                        if winning_slot == 0:
                            _upd_vals["youtube_cookies_runtime_expired"] = False
                        elif winning_slot == 1:
                            _upd_vals["youtube_cookies_backup_runtime_expired"] = False
                        await _sc_db.execute(_sa_update(_SC).values(**_upd_vals))
                        await _sc_db.commit()
                except Exception as _cnt_err:
                    logger.debug("Could not increment YT download counter: %s", _cnt_err)
                from app.services.sync.thumbnail_utils import extract_first_frame_and_upload
                thumb_rel = f"creatives/{org_id}/thumb_yt_{ad_id}.jpg"
                frame_thumb = None
                if not obj_storage.file_exists(thumb_rel):
                    frame_thumb = await extract_first_frame_and_upload(actual_path, org_id, ad_id, "yt", obj_storage)
                return yt_video_duration, served_url, frame_thumb
            else:
                logger.warning("  yt-dlp finished but output file missing in %s", tmpdir)
                return None, None, None
        except _CookiesExpiredError:
            try:
                from app.services.notifications import create_superadmin_notification
                from app.models.system_config import SystemConfig as _SC3
                from app.db.base import get_session_factory as _gsf3
                from sqlalchemy import select as _sel3
                from datetime import datetime as _dt3, timezone as _tz3
                _dl_count, _days = 0, None
                try:
                    async with _gsf3()() as _stats_db:
                        _cfg = (await _stats_db.execute(_sel3(_SC3).limit(1))).scalar_one_or_none()
                        if _cfg:
                            _dl_count = _cfg.youtube_cookies_download_count or 0
                            if _cfg.youtube_cookies_refreshed_at:
                                _days = (_dt3.now(_tz3.utc) - _cfg.youtube_cookies_refreshed_at).days
                except Exception:
                    pass
                _stats = f"expired after {_dl_count} video{'s' if _dl_count != 1 else ''}"
                if _days is not None:
                    _stats += f" and {_days} day{'s' if _days != 1 else ''}"
                await create_superadmin_notification(
                    type="COOKIE_FAILED",
                    title="YouTube cookies expired",
                    message=f"yt-dlp download aborted — YouTube cookies are no longer valid. Update cookies in Admin settings. ({_stats})",
                    data={"deeplink": "/configuration/admin"},
                )
            except Exception as _notif_err:
                logger.warning("Failed to send COOKIE_FAILED notification: %s", _notif_err)
            raise
        except Exception as e:
            logger.warning("Failed to download Google Ads video for ad %s (video %s): %s: %s", ad_id, youtube_video_id, type(e).__name__, e, exc_info=True)
            return None, None, None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def _upsert_records(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        records: List[Dict[str, Any]],
        sync_job_id: Optional[str],
        asset_map: Optional[Dict[str, str]] = None,
        org_id: Optional[str] = None,
    ) -> Tuple[int, Dict[str, Dict[str, str]]]:
        if not records:
            return 0, {}

        asset_map = asset_map or {}
        asset_queue: Dict[str, Dict[str, str]] = {}

        rows = []
        for r in records:
            campaign = r.get("campaign", {})
            ad_group = r.get("adGroup", {})
            ad = r.get("adGroupAd", {}).get("ad", {})
            metrics = r.get("metrics", {})
            segments = r.get("segments", {})

            cost_micros = int(metrics.get("costMicros", 0) or 0)
            spend = Decimal(str(cost_micros / 1_000_000))
            impressions = int(metrics.get("impressions", 0) or 0)
            clicks = int(metrics.get("clicks", 0) or 0)
            conversions = float(metrics.get("conversions", 0) or 0)
            conversion_value = Decimal(str(metrics.get("conversionsValue", 0) or 0))

            roas = float(conversion_value / spend) if spend and conversion_value else None
            cvr = (conversions / clicks) if clicks else None

            report_date_str = segments.get("date", "")
            report_date = date.fromisoformat(report_date_str) if report_date_str else None

            youtube_video_id = self._extract_youtube_id(ad, asset_map)
            ad_id_str = str(ad.get("id", ""))

            if youtube_video_id and org_id and ad_id_str not in asset_queue:
                asset_queue[ad_id_str] = {"youtube_video_id": youtube_video_id, "org_id": org_id}

            rows.append({
                "platform_connection_id": connection.id,
                "sync_job_id": sync_job_id,
                "report_date": report_date,
                "ad_account_id": connection.ad_account_id,
                "campaign_id": str(campaign.get("id", "")),
                "campaign_name": campaign.get("name"),
                "campaign_objective": campaign.get("advertisingChannelSubType"),
                "ad_group_id": str(ad_group.get("id", "")),
                "ad_group_name": ad_group.get("name"),
                "ad_id": ad_id_str,
                "ad_name": ad.get("name"),
                "video_id": youtube_video_id,
                "video_url": None,
                "thumbnail_url": None,
                "placement_type": campaign.get("advertisingChannelType"),
                "currency": connection.currency,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": float(metrics.get("ctr", 0) or 0),
                "cpm": Decimal(str(float(metrics.get("averageCpm", 0) or 0) / 1_000_000)),
                "conversions": int(conversions),
                "conversion_value": conversion_value,
                "cvr": cvr,
                "roas": roas,
                "video_views": int(metrics.get("videoTrueviewViews", 0) or 0),
                "view_rate": float(metrics.get("videoTrueviewViewRate", 0) or 0),
                "video_view_through_rate": float(metrics.get("videoQuartileP100Rate", 0) or 0),
                "video_quartile_p25": float(metrics.get("videoQuartileP25Rate", 0) or 0),
                "video_quartile_p50": float(metrics.get("videoQuartileP50Rate", 0) or 0),
                "video_quartile_p75": float(metrics.get("videoQuartileP75Rate", 0) or 0),
                "video_quartile_p100": float(metrics.get("videoQuartileP100Rate", 0) or 0),
                "is_validated": True,
                "is_processed": False,
            })

        stmt = pg_insert(GoogleAdsRawPerformance).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_google_ads_daily_ad",
            set_={
                "spend": stmt.excluded.spend,
                "impressions": stmt.excluded.impressions,
                "clicks": stmt.excluded.clicks,
                "conversions": stmt.excluded.conversions,
                "conversion_value": stmt.excluded.conversion_value,
                "cvr": stmt.excluded.cvr,
                "roas": stmt.excluded.roas,
                "video_views": stmt.excluded.video_views,
                "view_rate": stmt.excluded.view_rate,
                "video_view_through_rate": stmt.excluded.video_view_through_rate,
                "video_quartile_p25": stmt.excluded.video_quartile_p25,
                "video_quartile_p50": stmt.excluded.video_quartile_p50,
                "video_quartile_p75": stmt.excluded.video_quartile_p75,
                "video_quartile_p100": stmt.excluded.video_quartile_p100,
                "video_id": stmt.excluded.video_id,
                # video_url / thumbnail_url intentionally omitted: preserve any
                # already-downloaded URLs on re-sync; post-commit task fills NULLs.
                "is_processed": False,
            }
        )
        await db.execute(stmt)
        return len(rows), asset_queue

    async def download_assets_post_commit(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        asset_queue: Dict[str, Dict[str, str]],
    ) -> Dict[str, Any]:
        """Download thumbnails + videos for queued ads and UPDATE rows. Called after sync commit."""
        from sqlalchemy import update as sa_update, text as _text
        # Pre-flight: skip all video downloads if cookies already flagged expired by a concurrent job
        cookies_expired = False
        try:
            _pre = (await db.execute(_text("SELECT youtube_cookies_runtime_expired FROM system_config LIMIT 1"))).first()
            if _pre and _pre[0]:
                cookies_expired = True
                logger.warning("Google Ads: YouTube cookies already flagged as expired — skipping video downloads")
        except Exception:
            pass
        video_failures: Dict[str, str] = {}
        video_successes: int = 0
        served_url: Optional[str] = None
        for ad_id, info in asset_queue.items():
            youtube_video_id = info.get("youtube_video_id")
            org_id = info.get("org_id")
            if not youtube_video_id or not org_id:
                continue

            # Thumbnail is a plain HTTP fetch from img.youtube.com — no cookies needed.
            # Always attempt independently so it lands even when video download fails.
            thumbnail_url: Optional[str] = None
            try:
                _, thumbnail_url = await self._download_thumbnail(youtube_video_id, org_id, ad_id)
            except Exception as e:
                logger.warning("Thumbnail download failed for ad %s: %s", ad_id, e)

            # Video download requires yt-dlp + cookies. On _CookiesExpiredError we abort
            # remaining video downloads but still persist the thumbnail we already have.
            video_url: Optional[str] = None
            frame_thumb: Optional[str] = None
            yt_duration: Optional[float] = None
            if not cookies_expired:
                try:
                    yt_duration, video_url, frame_thumb = await self._download_video(youtube_video_id, org_id, ad_id)
                    if video_url:
                        video_successes += 1
                        served_url = video_url
                    else:
                        video_failures[ad_id] = "yt-dlp returned no URL (silent download failure)"
                        logger.warning("Video download returned no URL for ad %s", ad_id)
                except _CookiesExpiredError:
                    cookies_expired = True
                    logger.warning("YouTube cookies expired — skipping video downloads for remaining ads in queue")
                except Exception as e:
                    video_failures[ad_id] = f"{type(e).__name__}: {e}"
                    logger.warning("Video download failed for ad %s: %s", ad_id, e)

            if not thumbnail_url and frame_thumb:
                thumbnail_url = frame_thumb

            update_vals: Dict[str, Any] = {}
            if video_url:
                update_vals["video_url"] = video_url
            if thumbnail_url:
                update_vals["thumbnail_url"] = thumbnail_url
            if update_vals:
                await db.execute(
                    sa_update(GoogleAdsRawPerformance)
                    .where(
                        GoogleAdsRawPerformance.ad_id == ad_id,
                        GoogleAdsRawPerformance.platform_connection_id == connection.id,
                    )
                    .values(**update_vals)
                )
            # Populate video_duration on CreativeAsset inline — no separate backfill needed.
            if yt_duration is not None:
                from app.models.creative import CreativeAsset
                await db.execute(
                    sa_update(CreativeAsset).where(
                        CreativeAsset.organization_id == connection.organization_id,
                        CreativeAsset.platform == "GOOGLE_ADS",
                        CreativeAsset.ad_id == ad_id,
                        CreativeAsset.video_duration.is_(None),
                    ).values(video_duration=yt_duration)
                )
        await db.commit()
        if cookies_expired:
            raise _CookiesExpiredError("YouTube cookies expired during asset download")
        if video_failures and video_successes == 0:
            raise Exception(
                f"{len(video_failures)} Google Ads video download(s) failed: "
                + "; ".join(f"{k}: {v}" for k, v in list(video_failures.items())[:3])
                + ("..." if len(video_failures) > 3 else "")
            )
        return {"video_url": served_url, "video_failures": video_failures}


google_ads_sync = GoogleAdsSyncService()
