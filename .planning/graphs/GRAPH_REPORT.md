# Graph Report - .  (2026-04-15)

## Corpus Check
- 141 files · ~236,810 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1512 nodes · 3418 edges · 77 communities detected
- Extraction: 53% EXTRACTED · 47% INFERRED · 0% AMBIGUOUS · INFERRED: 1620 edges (avg confidence: 0.64)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]

## God Nodes (most connected - your core abstractions)
1. `PlatformConnection` - 76 edges
2. `MetadataField` - 56 edges
3. `CreativeScoreResult` - 56 edges
4. `DashboardComponent` - 51 edges
5. `User` - 51 edges
6. `PlatformsComponent` - 50 edges
7. `CreativeAsset` - 50 edges
8. `AIInferenceTracking` - 47 edges
9. `AssetDetailDialogComponent` - 44 edges
10. `AssetMetadataValue` - 44 edges

## Surprising Connections (you probably didn't know these)
- `Tests for the admin backfill endpoint and run_backfill_task() background task.` --uses--> `User`  [INFERRED]
  backend/tests/test_backfill.py → backend/app/models/user.py
- `Return a mock get_session_factory() that returns scalars_result from execute().` --uses--> `User`  [INFERRED]
  backend/tests/test_backfill.py → backend/app/models/user.py
- `run_backfill_task queries only UNSCORED + VIDEO/STATIC_IMAGE rows.      Mock DB` --uses--> `User`  [INFERRED]
  backend/tests/test_backfill.py → backend/app/models/user.py
- `FAILED assets are not included — backfill only queries UNSCORED rows.      When` --uses--> `User`  [INFERRED]
  backend/tests/test_backfill.py → backend/app/models/user.py
- `When score_asset_now raises for the first asset, the loop continues to the secon` --uses--> `User`  [INFERRED]
  backend/tests/test_backfill.py → backend/app/models/user.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (147): AudioResult, AI metadata auto-fill service.  Triggered after asset binary is stored to MinIO, Entry point — called via asyncio.create_task() from sync services.      Wraps _a, 4-phase auto-fill: read → download → infer → write., Upsert AssetMetadataValue rows for the given asset., Open a new session, update tracking row status, commit., Vision inference: Gemini 2.5 Flash Lite, with GPT-4o fallback on failure., GPT-4o vision fallback. (+139 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (95): update_field_values(), get_redirect_uri_from_request(), purge_connection_data(), get_asset_detail(), get_current_user(), DV360OAuthHandler, DV360 (Display & Video 360) OAuth 2.0 handler.  Auth flow: 1. Generate authoriza, Fetch a single DV360 advertiser by ID.         Used for manual entry when partne (+87 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (94): run_autofill_for_asset(), _set_status(), debug_trigger_autofill(), redownload_asset(), _create_engine(), _create_session_factory(), get_engine(), get_session_factory() (+86 more)

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (13): ApiService, AssignProjectDialogComponent, authGuard(), authInterceptor(), AuthService, get_db(), DisconnectDialogComponent, Refresh an expired access token using refresh_token. (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (76): _autofill(), _compose_mood_board(), _downsample_image(), _extract_audio_bytes(), _extract_key_frames(), _run_audio(), _run_audio_openai(), _run_vision() (+68 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (43): register(), Base, CurrencyConverterService, Fetches and caches daily exchange rates. Primary: frankfurter.dev, Fallback: exc, HarmonizationService, _make_converter(), _safe_add_decimal(), Notification helper service for org-level event fan-out.  Provides a single asyn (+35 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (67): build_static_scoring_payload(), map_static_channel(), Map platform + placement to a BrainSuite Static API channel identifier.      For, Build the BrainSuite Static API announce payload for POST /announce.      The St, Enum, get_endpoint_type(), ScoringEndpointType — routing enum and lookup table for BrainSuite scoring endpo, Routing identifier for which BrainSuite scoring endpoint to use.      VIDEO (+59 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (42): BrainSuite5xxError, BrainSuiteJobError, BrainSuiteRateLimitError, Shared BrainSuite exception classes used by all BrainSuite service modules.  Cen, Raised when BrainSuite API responds with HTTP 429., Raised when BrainSuite API responds with a 5xx error., Raised when a BrainSuite job fails, goes stale, or times out., BrainSuiteScoreService (+34 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (32): Config, Config, _sanitize_for_filename(), v4 field reference expansion - all platforms  Revision ID: e6f7g8h9i0j1 Revises:, upgrade(), _background_startup(), lifespan(), _migrate_static_urls_to_objects() (+24 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (26): BaseSettings, ComparisonComponent, Settings, app(), async_client(), mock_redis(), mock_settings(), Shared pytest fixtures for the Phase 02 security hardening test suite.  Provides (+18 more)

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (1): DashboardComponent

### Community 11 - "Community 11"
Cohesion: 0.06
Nodes (1): AssetDetailDialogComponent

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (36): check_slug(), generate_slug(), get_me(), login(), refresh_token(), LoginComponent, create_access_token(), create_refresh_token() (+28 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (2): DateRangePickerComponent, HeaderComponent

### Community 14 - "Community 14"
Cohesion: 0.19
Nodes (34): BaseModel, AssetTimeseriesPoint, CreativeAssetSummary, PerformanceSummary, AdAccountSelectionRequest, AdAccountSetup, BrainsuiteApp, BrainsuiteAppBase (+26 more)

### Community 15 - "Community 15"
Cohesion: 0.08
Nodes (25): Phase 07 Plan 01 — PERCENT_RANK Performer Tag Tests.  Tests for: - _compute_perf, get_dashboard_assets must use func.percent_rank() window function., get_dashboard_assets must call _compute_performer_tag, not _get_performer_tag., GET /dashboard/assets/{id} response must include 'ad_account_id' field., ad_account_id in detail response must come from asset.ad_account_id., _compute_performer_tag must exist in dashboard module., _get_performer_tag must be removed — replaced by _compute_performer_tag., Given fewer than 3 scored assets, all performer_tag values are null.      _compu (+17 more)

### Community 16 - "Community 16"
Cohesion: 0.08
Nodes (23): Phase 07 Plan 01 — Score Trend Endpoint Tests.  Tests for: - GET /dashboard/scor, When no COMPLETE scores exist, returns {'trend': [], 'data_points': 0}.      Ver, Single data point is returned as-is (frontend handles < 2 as empty state)., Platform filter parameter is accepted and applied to the query., Org isolation: the query is restricted to current_user.organization_id., GET /dashboard/score-trend endpoint must exist in dashboard module., @router.get('/score-trend') must be registered on the router., Score trend response shape must include 'trend' and 'data_points' keys. (+15 more)

### Community 17 - "Community 17"
Cohesion: 0.1
Nodes (19): Phase 3 — BrainSuite Scoring Pipeline test scaffolds.  Test stubs for SCORE-01 t, 429 response triggers wait using x-ratelimit-reset header; 5xx triggers exponent, generate_signed_url called with raw S3 key, not /objects/ prefix.      Verifies:, Query returns at most 20 rows; only VIDEO assets selected.      Verifies:     -, New VIDEO asset gets UNSCORED row; existing COMPLETE row is NOT reset.      Veri, POST /api/v1/scoring/{id}/rescore returns 200 and sets status to UNSCORED., Stored score_dimensions JSONB has no `visualizations` keys.      Verifies:     -, GET /api/v1/scoring/status?asset_ids=... returns correct status for each asset. (+11 more)

### Community 18 - "Community 18"
Cohesion: 0.16
Nodes (19): _serialize_correlation_asset(), _mock_row(), TDD tests for GET /dashboard/correlation-data endpoint.  RED phase: These tests, The get_correlation_data function must be defined in the dashboard module., The _serialize_correlation_asset helper must be defined at module level., roas=0.0 must be returned as 0.0, not coerced to None by falsy check., roas=None must be returned as None — frontend handles exclusion., Positive roas values must pass through as floats. (+11 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (2): ChangeRoleDialogComponent, OrganizationComponent

### Community 20 - "Community 20"
Cohesion: 0.14
Nodes (1): HomeComponent

### Community 21 - "Community 21"
Cohesion: 0.23
Nodes (5): export_assets(), get_export_fields(), ExportService, _fmt(), Export service: generates PDF, Excel, and CSV exports from harmonized data.

### Community 22 - "Community 22"
Cohesion: 0.22
Nodes (2): AppComponent, ThemeService

### Community 23 - "Community 23"
Cohesion: 0.22
Nodes (1): BrainsuiteAppsComponent

### Community 24 - "Community 24"
Cohesion: 0.32
Nodes (7): _enclosing_function_names(), _find_broad_catches(), AST-based static analysis for QUAL-01: Broad except-Exception audit.  Scans all, Return the names of all function definitions that contain the target line., Scan all Python files for bare except Exception outside the allowed list., QUAL-01: No broad except Exception outside the allowed list.      Allowed locati, test_no_broad_except_exception()

### Community 25 - "Community 25"
Cohesion: 0.47
Nodes (5): _create_minio_bucket(), main(), prompt(), Create the MinIO bucket if the stack is already running., Prompt user for input with optional default and hidden input for secrets.      R

### Community 26 - "Community 26"
Cohesion: 0.4
Nodes (1): SidebarComponent

### Community 27 - "Community 27"
Cohesion: 0.83
Nodes (3): _get_sync_url(), run_migrations_offline(), run_migrations_online()

### Community 28 - "Community 28"
Cohesion: 0.5
Nodes (1): add image and video app mapping to platform connections  Revision ID: a2b3c4d5e6

### Community 29 - "Community 29"
Cohesion: 0.5
Nodes (1): add_dv360_raw_performance  Revision ID: b2c3d4e5f6g7 Revises: a1b2c3d4e5f6 Creat

### Community 30 - "Community 30"
Cohesion: 0.5
Nodes (1): dv360_add_new_cols_drop_deprecated  Revision ID: g8h9i0j1k2l3 Revises: b2c3d4e5f

### Community 31 - "Community 31"
Cohesion: 0.5
Nodes (1): Add AI auto-fill columns to metadata_fields, widen asset_metadata_values.value,

### Community 32 - "Community 32"
Cohesion: 0.5
Nodes (1): add notifications indexes  Revision ID: r9s0t1u2v3w4 Revises: q8r9s0t1u2v3 Creat

### Community 33 - "Community 33"
Cohesion: 0.5
Nodes (1): add dv360 cost_per_view column  Revision ID: k2l3m4n5o6p7 Revises: j1k2l3m4n5o6

### Community 34 - "Community 34"
Cohesion: 0.5
Nodes (1): add asset_url to meta_raw_performance  Revision ID: c4d5e6f7g8h9 Revises: b3c4d5

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (1): add dv360 video_skips column  Revision ID: j1k2l3m4n5o6 Revises: i0j1k2l3m4n5 Cr

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (1): initial  Revision ID: 41dcacc7071c Revises:  Create Date: 2026-02-19 09:28:42.43

### Community 37 - "Community 37"
Cohesion: 0.5
Nodes (1): Fix endpoint_type for existing image score rows backfilled incorrectly to VIDEO.

### Community 38 - "Community 38"
Cohesion: 0.5
Nodes (1): expand all raw performance models and harmonized model per field reference v3  R

### Community 39 - "Community 39"
Cohesion: 0.5
Nodes (1): add join requests and notifications tables  Revision ID: b3c4d5e6f7g8 Revises: a

### Community 40 - "Community 40"
Cohesion: 0.5
Nodes (1): widen harmonized publisher_platform and platform_position to 500  Revision ID: h

### Community 41 - "Community 41"
Cohesion: 0.5
Nodes (1): add pending_at and submitted_at to creative_score_results  Revision ID: p7q8r9s0

### Community 42 - "Community 42"
Cohesion: 0.5
Nodes (1): add_missing_youtube_columns  Revision ID: 09fdc18ec8e1 Revises: f7g8h9i0j1k2 Cre

### Community 43 - "Community 43"
Cohesion: 0.5
Nodes (1): add publisher_platform and platform_position to harmonized_performance  Revision

### Community 44 - "Community 44"
Cohesion: 0.5
Nodes (1): meta_breakdown_unique_constraint  Revision ID: 7a276d76fa12 Revises: e6f7g8h9i0j

### Community 45 - "Community 45"
Cohesion: 0.5
Nodes (1): rename_youtube_to_google_ads  Revision ID: a1b2c3d4e5f6 Revises: 09fdc18ec8e1 Cr

### Community 46 - "Community 46"
Cohesion: 0.5
Nodes (1): add creative_score_results table and drop ace_score columns  Revision ID: e1f2g3

### Community 47 - "Community 47"
Cohesion: 0.5
Nodes (1): add endpoint_type column to creative_score_results and add UNSUPPORTED scoring s

### Community 48 - "Community 48"
Cohesion: 0.5
Nodes (1): add width height to creative assets  Revision ID: q8r9s0t1u2v3 Revises: p7q8r9s0

### Community 49 - "Community 49"
Cohesion: 0.5
Nodes (1): drop_dv360_channel_cols  Revision ID: i0j1k2l3m4n5 Revises: h9i0j1k2l3m4 Create

### Community 50 - "Community 50"
Cohesion: 0.67
Nodes (1): AuthEffects

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): ConfigurationShellComponent

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (0): 

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (0): 

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (0): 

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (0): 

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (0): 

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (0): 

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (0): 

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (0): 

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (0): 

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (0): 

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (0): 

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): Return the OAuth callback URI using settings.BASE_URL only.          The ``reque

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (0): 

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (0): 

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (0): 

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (0): 

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (0): 

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (0): 

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (0): 

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (0): 

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (0): 

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (0): 

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **170 isolated node(s):** `ConfigurationShellComponent`, `Return the OAuth callback URI using settings.BASE_URL only.          The ``reque`, `Async Redis client singleton for session and cache storage.`, `Return a lazy-initialized async Redis client.      Uses settings.REDIS_URL (defa`, `Config` (+165 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 51`** (2 nodes): `initAuth()`, `app.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (2 nodes): `ConfigurationShellComponent`, `configuration-shell.component.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `main.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `app.routes.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `app.state.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `auth.reducer.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `auth.actions.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `auth.selectors.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `configuration.routes.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `auth.routes.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `environment.prod.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `environment.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `start_server.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `Return the OAuth callback URI using settings.BASE_URL only.          The ``reque`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DashboardComponent` connect `Community 10` to `Community 11`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `_serialize_correlation_asset()` connect `Community 18` to `Community 0`, `Community 2`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 90 inferred relationships involving `str` (e.g. with `register()` and `login()`) actually correct?**
  _`str` has 90 INFERRED edges - model-reasoned connections that need verification._
- **Are the 74 inferred relationships involving `PlatformConnection` (e.g. with `Base` and `Platform connection management endpoints. Handles OAuth flows, account listing,`) actually correct?**
  _`PlatformConnection` has 74 INFERRED edges - model-reasoned connections that need verification._
- **Are the 53 inferred relationships involving `MetadataField` (e.g. with `Base` and `Dashboard and performance data endpoints. All monetary values returned in organi`) actually correct?**
  _`MetadataField` has 53 INFERRED edges - model-reasoned connections that need verification._
- **Are the 53 inferred relationships involving `CreativeScoreResult` (e.g. with `Base` and `Scoring endpoints — rescore trigger, status polling, score detail, refetch.`) actually correct?**
  _`CreativeScoreResult` has 53 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConfigurationShellComponent`, `Return the OAuth callback URI using settings.BASE_URL only.          The ``reque`, `Async Redis client singleton for session and cache storage.` to the rest of the system?**
  _170 weakly-connected nodes found - possible documentation gaps or missing edges._