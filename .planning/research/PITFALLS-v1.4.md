# Pitfalls Research — v1.4 Feature Integration

**Domain:** Adding residential proxy + PO token plugin to stateless Cloud Run; dashboard filters recovered from git history; video duration backfill

**Researched:** 2026-05-14

---

## Critical Pitfalls

### Pitfall 1: bgutil Subprocess Lifecycle in Cloud Run Cold Starts

**What goes wrong:**
bgutil-ytdlp-pot-provider Node.js binary starts as a subprocess on first request. In Cloud Run's stateless architecture, every instance shutdown destroys the process. On next invocation (cold start), the subprocess restarts, incurring 500ms–2s overhead per cold start. If traffic is sparse, you pay this penalty repeatedly. The subprocess may also leak file handles or memory if not cleanly terminated during SIGTERM shutdown (10-second window).

**Why it happens:**
- Cloud Run scales to zero when idle, destroying container state between invocations
- bgutil has initialization overhead (BotGuard client setup, context loading)
- Script mode plugin executes binary per-token-request with no connection pooling
- Subprocess lifecycle not integrated with Cloud Run's SIGTERM handler

**Consequences:**
- Cold starts add 2–5 seconds to first video download (SLA miss)
- Memory bloat if 100+ requests per day with lingering subprocess handles
- Potential unclean shutdown causing temporary token provider unavailability
- Script mode (per-request subprocess) is slower than HTTP mode (persistent server)

**Prevention:**
1. **Choose HTTP mode over Script mode:** Deploy bgutil as persistent HTTP server in same container image via `Dockerfile` multi-stage build or sidecar process launcher. HTTP mode connection pools tokens across requests.
2. **Containerize bgutil:** Add `bgutil-ytdlp-pot-provider` start command to main startup, listen on localhost:4416, supervise with `supervisord` or shell trap to ensure clean shutdown on SIGTERM.
3. **Configure min-instances:** Set Cloud Run `--min-instances=1` to prevent scale-to-zero during testing, or accept cold start penalty and monitor.
4. **Add startup CPU boost:** Enable Cloud Run's `--cpu-boost-on-startup` feature to reduce initialization time from 2s to 500ms.
5. **Implement health check:** Cloud Run will restart container if health check fails — ensure bgutil subprocess is running before marking service ready.

**Detection:**
- Cloud Trace / Cloud Logging shows container startup > 3s, then yt-dlp subprocess calls add 1–2s
- Monitoring yt-dlp error logs for "token_provider unavailable" or timeout errors
- bgutil process not found in `ps aux` after cold start

**Phase to address:** **Phase 1 (setup)** — Choose HTTP vs Script mode, containerize bgutil, configure Cloud Run instance settings before any downloads run

---

### Pitfall 2: Proxy IP Rotation & Connection State in Stateless Container

**What goes wrong:**
Residential proxy provider (e.g., Bright Data, Smartproxy) assigns a new IP per request OR maintains session-pinning for X requests. In Cloud Run, each container instance might get a different proxy IP, leading to:
- **Inconsistent geo-blocking bypass:** First request proxies through NY, second through Singapore — YouTube rate-limits aggressively on IP switching
- **Session drop on container restart:** If proxy pins to container instance, shutdown loses the pin; next invocation gets new IP, breaking downstream authentication
- **Proxy credentials cached in wrong scope:** Store proxy URL in `SystemConfig` (shared), but if per-container caching occurs, multiple instances fight over same credentials

**Why it happens:**
- Residential proxy providers assign rotating IPs by default to avoid detection
- Cloud Run instances are ephemeral — proxy session affinity breaks on scale-up/down
- Proxy credentials stored centrally but consumed per-instance (no isolation)
- yt-dlp subprocess may cache proxy connection in memory — lost on container shutdown

**Consequences:**
- YouTube rate-limits or blocks video downloads mid-sync
- Unpredictable "HTTP 429 Too Many Requests" errors on second/third download
- Credentials leaked or rotated unnecessarily if multiple instances race to refresh
- Silent failures: video marked "no formats available" when actually proxy-blocked

**Prevention:**
1. **Use residential proxy with session pinning:** Configure proxy provider to pin session for 60–300s (depends on provider). Document pin duration in code comments.
2. **Store proxy URL encrypted in `SystemConfig`:** Use existing Fernet encryption (like cookies). Avoid plaintext in logs or error messages.
3. **Implement exponential backoff on 429:** yt-dlp will retry, but add manual retry loop with 2s–30s jitter between attempts in `_download_video_asset()`.
4. **No per-container caching:** Don't cache proxy credentials in module-level variables. Fetch from DB/encrypted config on every request.
5. **Monitor proxy IP distribution:** Log proxy IP changes; if same IP used 5+ downloads in a row, session is pinned (good); if IP changes per request, provider is rotating (risky).
6. **Set proxy timeout low:** Use `socket_timeout: 10` in yt-dlp opts. Datacenter proxies hang on blocked requests; residential proxies should respond quickly or fail cleanly.

**Detection:**
- yt-dlp logs show "Proxy error" or "Proxy connection refused"
- HTTP 429 / 403 responses from YouTube API
- Logs show different proxy IPs for sequential downloads
- Video downloads timeout after 60s despite 30s socket_timeout setting

**Phase to address:** **Phase 1 (proxy setup)** — Encrypt proxy URL, implement 429 backoff, test IP pinning behavior before production deployment

---

### Pitfall 3: Credentials Rotation & Secret Handling in Multi-Instance Deploy

**What goes wrong:**
Proxy URL and bgutil binary credentials must be stored encrypted (Fernet), fetched from DB, and passed to subprocess. Common mistakes:
- **Printing proxy URL in logs:** `logger.info(f"Using proxy: {proxy_url}")` leaks credentials
- **Storing plaintext in env vars:** `os.environ["PROXY_URL"]` during cold start — visible in Cloud Run logs
- **Race on credential refresh:** Two instances simultaneously refresh proxy token → inconsistent state
- **Old subprocess holds stale credentials:** bgutil subprocess started at container boot, credentials rotated in DB later → subprocess uses expired proxy token

**Why it happens:**
- Existing code stores YouTube cookies encrypted (T-14-10 mitigation) but proxy URL is new
- FastAPI multi-worker setup means multiple processes see same env vars
- Subprocess inherits credentials at startup, not dynamically refreshed

**Consequences:**
- Proxy credentials exposed in CloudLogging, audit trails, or error reports
- Sync fails intermittently when only some instances have refreshed credentials
- bgutil subprocess tries expired token → all downloads fail until container restart

**Prevention:**
1. **Never log proxy URL or credentials:** Use `logger.info("Using proxy: [REDACTED]")` pattern. Add `redact_credentials()` utility that strips URLs from error messages.
2. **Fetch credentials from DB every request:** Don't cache in memory or env vars. Use same pattern as `_get_cookies_from_db()` — fetch fresh decrypted value on each download.
3. **Pass credentials to subprocess as stdin, not args:** Subprocess args are visible in `ps aux`. Use stdin or environment inheritance (child sees parent env, but not exposed to sibling processes).
4. **Implement credential refresh without restarting subprocess:** If bgutil is persistent HTTP server, call refresh endpoint (if available) or restart cleanly via supervisor signal.
5. **Add credential rotation audit trail:** Log rotation events with timestamp, actor, reason (but not the credential itself).

**Detection:**
- `grep -r "proxy_url\|proxy://\|brightness\|smartproxy" /path/to/logs` returns matches
- CloudLogging shows raw proxy URLs in error messages
- Sync failures spike after credential rotation in admin UI
- bgutil logs show "authentication failed" or "token invalid"

**Phase to address:** **Phase 1 (security setup)** — Implement credential redaction, DB-per-request fetch, clean subprocess credential passing before any proxy integration

---

### Pitfall 4: Cherry-Pick Conflicts When Recovering Dashboard Filters from Git History

**What goes wrong:**
Dashboard filters existed in v1.1 but were removed / replaced in v1.2–v1.3. To recover, you cherry-pick commits from old branches (e.g., `feature/dashboard-filters`). Conflicts occur because:
- **Filter state management refactored:** v1.1 used `@Input/@Output`, v1.3 uses signals + reactive forms
- **API contract changed:** `/dashboard/assets?filter=X` becomes `/dashboard/assets?filters[]=X` 
- **Template structure different:** Old `<mat-select>` replaced with custom `tbd-trigger` pattern
- **Backend endpoint moved/renamed:** `/api/metadata-filters` → `/dashboard/metadata-filter-values`

**Why it happens:**
- v1.2/v1.3 refactored architecture significantly (signals, custom components, new endpoints)
- Old branch not rebased on current main — time divergence is 3+ months
- Cherry-pick only applies commit content, not the underlying structural changes it assumes

**Consequences:**
- Merge conflicts in 5–10 files (component, template, service, backend endpoint)
- Resolved conflicts introduce dead code paths (old API calls, unused signals)
- Missing test coverage for recovered features → regressions after merge
- Filter state doesn't sync with query params → back button breaks

**Prevention:**
1. **Don't cherry-pick; do surgical recovery:** Instead of cherry-picking old commits, manually re-implement filters using current v1.3 architecture. Reference old code in a side-by-side editor, not as commits.
2. **Document architecture assumptions:** Create `.planning/quick/filter-recovery/ASSUMPTIONS.md` listing signal-based state, reactive form structure, endpoint contracts before starting recovery.
3. **Test before merging:** Implement test file `filter-recovery.integration.spec.ts` with 5 test cases:
   - Filter state persists on page reload (query param round-trip)
   - Autocomplete calls backend endpoint with debounce
   - Multi-select serializes/deserializes correctly
   - Duration slider min/max values bound
   - Clearing filters resets to defaults
4. **Incrementally recover features:** Add one filter at a time (metadata → accounts → duration). Commit each, test end-to-end, then next.
5. **Use feature flags:** Wrap recovered filters in `if (featureFlags.dashboardFiltersV2)` so you can toggle off without rolling back.

**Detection:**
- `git status` shows 5+ files with merge conflict markers (`<<<<<<<` / `=======` / `>>>>>>>`)
- Template compilation fails: "component property 'filterForm' does not exist"
- API calls 404: "POST /api/metadata-filters not found"
- Filter state doesn't persist on reload; query params ignored

**Phase to address:** **Phase 2 (filter recovery)** — Plan architectural recovery, write integration tests, implement feature flag, recover one filter type, test fully before next filter

---

### Pitfall 5: Test Coverage Gaps When Recovering Lost Dashboard Filters

**What goes wrong:**
Old dashboard filter features (metadata autocomplete, account multi-select, duration range) have zero test coverage in v1.3. Cherry-picking reintroduces code with no tests. Result:
- **Backend:** No tests for `GET /dashboard/metadata-filter-values` endpoint — returns wrong data shape on edge cases
- **Frontend:** No unit tests for filter debounce logic — request spam on fast typing
- **Integration:** No e2e test for "filter state survives page reload" — query params ignored
- **Backfill:** Video duration added to creative sync — no migration test ensuring old assets get `duration=NULL` correctly

**Why it happens:**
- Original features developed without tests (v1.0–v1.1 pre-v1.3 testing culture)
- Removed in v1.2/v1.3 cleanup without extracting tests
- No one asked "are tests in the old branch" before cherry-picking

**Consequences:**
- Filter returns `{ label: string }` instead of `{ id, label, count }` → frontend breaks
- Autocomplete fires 50 requests on 5-character input → backend timeout
- Clearing filters works locally, but next page load filters reappear
- Video duration field is NULL for 10k existing assets, no way to fill retroactively

**Prevention:**
1. **Write tests before recovering code:** For each recovered feature, start with failing test, then implement:
   ```typescript
   // Before writing filter recovery code:
   describe('Dashboard Metadata Filter', () => {
     it('debounces API calls on autocomplete input', fakeAsync(() => {
       // Type 5 chars, advance 500ms, expect 1 API call (not 5)
     }));
     it('persists filter state in query params', () => {
       // Set filter, navigate away, back — filter still set
     }));
   });
   ```
2. **Test API response shape:** Mock backend endpoint, verify frontend expects correct shape:
   ```typescript
   it('handles metadata filter response { id, label, count }', () => {
     service.getMetadataFilterValues('brand').subscribe(values => {
       expect(values[0]).toHaveProperty('id');
       expect(values[0]).toHaveProperty('label');
     });
   });
   ```
3. **Backfill migration test:** Create `test_video_duration_backfill.py` that:
   - Creates 100 test assets with no duration
   - Runs migration script
   - Asserts some have duration > 0, some NULL (video not downloaded yet)
4. **Add e2e test for filter flow:** Playwright/Cypress test:
   - Load dashboard
   - Set metadata filter to "brand_values"
   - Verify grid updates
   - Reload page
   - Verify filter still set
5. **Measure coverage:** Target 80%+ for recovered features. Use `ng test --code-coverage` and `pytest --cov` to identify gaps.

**Detection:**
- `ng test --code-coverage` shows recovered filter feature at 20–40% coverage
- `pytest --cov backend/app/api/v1/endpoints` shows `/dashboard/metadata-filter-values` branch coverage < 50%
- First user report: "I cleared the filters, but they came back on reload"
- Autocomplete response times spike: 5s+ on 5-character input

**Phase to address:** **Phase 2 (filter recovery, parallel to pitfall #4)** — Write tests first, then implement recovery, verify coverage before merging

---

### Pitfall 6: Video Duration Backfill Strategy for Existing Assets

**What goes wrong:**
Dashboard filter adds `duration_min` / `duration_max` range slider. Video duration must be stored on every asset. For 10k+ existing DV360/Google Ads video assets with `duration = NULL`:
- **Add column with DEFAULT NULL:** Quick migration, but legacy assets unsearchable by duration
- **Backfill in single query:** `UPDATE creative_asset SET duration = 120 WHERE duration IS NULL` locks table for 5+ minutes → sync blocked
- **Batch backfill in Python:** Loop 100 assets/batch, fetch duration from MinIO video files, update DB. But if file missing → crashes, leaves some rows NULL
- **Re-download all videos to get duration:** 10k videos × 5 minutes each = 83 hours of compute

**Why it happens:**
- Duration comes from ffprobe during download, but only new assets get this
- Legacy assets lack file paths to re-read duration from
- Existing assets video_url points to CDN/MinIO — must read file to get duration
- No robust strategy chosen before adding the filter

**Consequences:**
- Duration field is NULL for 90% of assets → filter useless
- Filter query becomes slow: `WHERE duration BETWEEN 10 AND 60 OR duration IS NULL` (OR kills index usage)
- Dashboard shows partial results, users confused why assets missing from duration-filtered results
- Or: backfill locks database, sync fails, emergency rollback needed

**Prevention:**
1. **Accept NULL on legacy assets, document in UI:** Add help text: "Duration filter only available for assets synced after [date]. Older assets will not appear in duration-filtered results." Filter UI shows "Showing X of Y results."
2. **Async backfill in background:** Create one-time maintenance job:
   ```python
   async def backfill_video_durations():
       # Query creative_asset WHERE platform IN ('dv360', 'google_ads') AND duration IS NULL
       # For each batch of 50:
       #   - Read video from MinIO using asset_url
       #   - Run ffprobe to get duration
       #   - Update DB
       #   - Sleep 1s to avoid DB spike
   ```
3. **Graceful fallback for missing files:** If video missing from MinIO, log warning and skip:
   ```python
   try:
       duration = get_duration_from_video(url)
   except FileNotFoundError:
       logger.info(f"Video file missing, skipping backfill for asset {asset_id}")
       continue
   ```
4. **Batch size & timing:** Backfill 10k assets:
   - 100 assets/batch, 1s delay = ~2 hours of compute time
   - Schedule during low-traffic window (2–4 AM)
   - Monitor DB connection pool — don't exhaust with backfill queries
5. **Add backfill status tracking:** Create `backfill_job` record:
   ```python
   @dataclass
   class BackfillJob:
       id: UUID
       status: str  # pending / running / completed / failed
       total_count: int
       processed_count: int
       error_count: int
   ```
   Update UI: "Backfill in progress: 2,500 / 10,000 assets"

6. **Test migration:** In `test_video_duration_backfill.py`:
   - Create 100 test assets, half with duration, half NULL
   - Run backfill script
   - Assert NULL → filled with actual value
   - Assert already-filled → unchanged
   - Assert missing video → skipped with warning

**Detection:**
- Dashboard duration filter returns 0 results for any range (all NULL)
- Admin console shows "Backfill Job: 0% complete" after 24 hours
- Database query `SELECT COUNT(*) FROM creative_asset WHERE duration IS NULL` returns 9,800+ (90%+ NULL)
- ffprobe subprocess fails/hangs on legacy video files

**Phase to address:** **Phase 3 (backfill)** — Implement async backfill job with status tracking, run in production gradually, monitor for file-missing errors, update filter UI to show coverage percentage

---

## Moderate Pitfalls

### Pitfall 7: Angular Autocomplete Debounce & Request Cancellation Edge Cases

**What goes wrong:**
Metadata autocomplete calls backend on every keystroke. Without proper debounce + cancellation:
- **Request spam:** Typing "brand" (5 chars) → 5 API requests fire. 4 are stale.
- **Race condition:** Request 1 takes 2s, request 2 takes 500ms, returns first. UI shows stale results.
- **Memory leak:** Pending subscriptions pile up if component destroyed before response.
- **Empty input calls API:** Typing space alone triggers `/dashboard/metadata-filter-values?q=+` → wastes backend call.

**Why it happens:**
- Reactive forms `valueChanges` fires on every keystroke
- Debounce + switchMap easy to get wrong: debounce before filter vs after?
- Component destroyed before request completes → subscription lingers
- No filter on empty input

**Prevention:**
1. **Correct RxJS pipeline:**
   ```typescript
   // WRONG: debounce doesn't prevent stale request
   this.metadataCtrl.valueChanges.pipe(
     debounceTime(300),
     switchMap(q => this.api.getMetadataFilterValues(q))
   );
   // RIGHT: filter empty, debounce, switch to new request, unsubscribe on destroy
   this.metadataCtrl.valueChanges.pipe(
     filter(q => q && q.trim().length > 0),  // Skip empty
     debounceTime(500),
     distinctUntilChanged(),  // Skip duplicate values
     switchMap(q => this.api.getMetadataFilterValues(q)),  // Cancel prev request
     takeUntil(this.destroy$)  // Cleanup on component destroy
   );
   ```
2. **Test debounce behavior:**
   ```typescript
   it('debounces API calls and skips empty input', fakeAsync(() => {
     const apiSpy = spyOn(service, 'getMetadataFilterValues').and.returnValue(of([]));
     
     metadataCtrl.setValue('a');
     tick(100);
     metadataCtrl.setValue('ab');
     tick(100);
     metadataCtrl.setValue('abc');
     tick(600);  // Advance past 500ms debounce
     
     expect(apiSpy).toHaveBeenCalledTimes(1);
     expect(apiSpy).toHaveBeenCalledWith('abc');
   }));
   ```
3. **Handle slow responses:**
   - Set backend request timeout: `timeout(5000)` operator
   - Show "Searching..." spinner after 300ms (UX expectation)
   - If request > 2s, show "No results" vs waiting longer

**Detection:**
- Network tab shows 10 requests for "brand" (5 characters)
- Response time varies wildly (last request shows "stale" label)
- Component destroyed error: "Cannot subscribe to destroyed component"
- Typing space alone triggers API call in logs

**Phase to address:** **Phase 2 (autocomplete)** — Implement filter + debounce + switchMap + takeUntil, add unit test for debounce timing, monitor API call count in dev tools

---

### Pitfall 8: Query Param Serialization & Filter State Persistence

**What goes wrong:**
Dashboard filters must survive page reload via URL query params. Common mistakes:
- **Params not serialized:** Setting filter `{ metadata_id: 'abc', value: 'xyz' }` but not writing to `?metadata_id=abc&value=xyz`
- **Complex objects in URL:** Trying to encode entire filter object as JSON in query string → `?filter=%7B%22id%22%3A%22abc%22%7D` is fragile and long
- **Back button ignored:** User sets filter, URL updates, user clicks back → URL reverts but component filter state doesn't
- **Duplicate params:** `?ad_accounts=123&ad_accounts=456` not parsed correctly (expects array, gets string)

**Why it happens:**
- Angular Router doesn't automatically serialize form state to query params
- Must explicitly call `router.navigate([...], { queryParams: {...} })`
- No central "query param contract" defined — backend expects `ad_account_ids[]`, frontend encodes `adAccountIds`

**Prevention:**
1. **Define query param contract upfront:**
   ```typescript
   // Filter state contract with backend
   interface DashboardFilterParams {
     date_from: string;  // ISO 8601
     date_to: string;
     platforms: string;  // CSV: 'meta,tiktok,google_ads'
     ad_account_ids: string;  // CSV: '123,456,789'
     metadata_id: string;  // Single value
     metadata_value: string;
     duration_min: number;
     duration_max: number;
   }
   ```
2. **Serialize on filter change:**
   ```typescript
   onFilterChange() {
     const params: DashboardFilterParams = {
       ad_account_ids: this.selectedAccounts.join(','),
       metadata_value: this.metadataCtrl.value,
       duration_min: this.durationRange[0],
       duration_max: this.durationRange[1],
     };
     this.router.navigate([], { relativeTo: this.route, queryParams: params });
     this.loadAssets();
   }
   ```
3. **Deserialize on init & route param change:**
   ```typescript
   ngOnInit() {
     this.route.queryParams.subscribe(params => {
       this.selectedAccounts = params['ad_account_ids']?.split(',') || [];
       this.metadataCtrl.setValue(params['metadata_value'] || '');
       this.durationRange = [params['duration_min'] || 0, params['duration_max'] || 600];
       this.loadAssets();
     });
   }
   ```
4. **Back button support:** Router handles URL change; subscribe to `queryParams` to sync state

**Detection:**
- Set filter, reload page → filter gone (not in URL)
- Browser back button returns to previous URL but filter state doesn't change
- API call shows `?ad_account_ids=undefined` in query string
- Multiple accounts selected but URL shows `?ad_account_ids=123` (only last one)

**Phase to address:** **Phase 2 (filter recovery)** — Document query param contract, implement serialization/deserialization, test page reload and back button

---

## Minor Pitfalls

### Pitfall 9: Proxy Credential Leakage via Error Messages

**What goes wrong:**
yt-dlp error messages may include proxy URL: `"Failed to connect to proxy://user:pass@proxy.example.com:8080"`. If logged or sent to error tracking (Sentry), credentials exposed.

**Prevention:**
Create utility to redact credentials from error strings:
```python
def redact_credentials(msg: str) -> str:
    import re
    # Remove proxy://user:pass@host:port pattern
    msg = re.sub(r'proxy://[^@]+@[^/]+', 'proxy://[REDACTED]@[REDACTED]', msg)
    return msg

logger.warning(f"yt-dlp failed: {redact_credentials(error_msg)}")
```

**Detection:** Grep logs for patterns like `proxy://`, `bright`, `smartproxy`, credential-like strings

---

### Pitfall 10: bgutil Subprocess Orphan Processes on Container Crash

**What goes wrong:**
If bgutil subprocess starts but container is killed (OOM, SIGKILL), the subprocess continues running on the host, consuming resources and holding proxy connections.

**Prevention:**
Use process groups and supervisord:
```bash
# supervisord.conf
[program:bgutil]
command=/usr/local/bin/bgutil --http --port 4416
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
```
Ensures child process killed with parent.

---

### Pitfall 11: Video Duration Extraction Timeout in Edge Cases

**What goes wrong:**
ffprobe can hang on corrupted video files (infinite loops, unfinalized MP4). Set timeout to 15s, but video extraction may still timeout if file very large.

**Prevention:**
Add timeout to ffprobe call (already in codebase):
```python
result = subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file_path],
    capture_output=True, text=True, timeout=15,
)
```
Monitor for timeout exceptions; log and skip corrupted files.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| Proxy Setup (Phase 1) | bgutil subprocess not persistent; credential leakage | Containerize bgutil HTTP mode; implement credential redaction |
| Proxy Integration (Phase 1) | IP rotation breaks session; 429 rate limits | Use residential proxy with session pinning; add exponential backoff |
| Filter Recovery (Phase 2) | Cherry-pick conflicts; test coverage gaps | Manual surgical recovery using current architecture; write tests first |
| Filter State (Phase 2) | Query params not serialized; page reload loses state | Define query param contract; serialize on change; subscribe to route params |
| Autocomplete (Phase 2) | Request spam; race conditions; stale results | Use filter + debounce + switchMap + takeUntil; test debounce timing |
| Duration Backfill (Phase 3) | Locks database; missing video files; NULL for 90% assets | Async background job with batch processing; graceful file-missing handling |
| Backfill Testing (Phase 3) | Migration doesn't handle edge cases (missing files, partial updates) | Create test_video_duration_backfill.py; verify NULL → filled transition |

---

## Highest Risk Combination

**Residential proxy IP rotation + Cold start + Video download timeout:**
- Container cold starts, bgutil subprocess initializes (2s)
- First request gets proxy IP #1, downloads video (5s)
- Sync ends, instance scales to zero
- Second sync (next day), cold start again (2s)
- New instance gets proxy IP #2 → YouTube session lost
- Download fails with HTTP 403
- User sees "no formats available" — assumes video deleted, doesn't retry

**Mitigation:** Min-instances=1, residential proxy session pinning for 86400s (1 day), explicit retry logic with exponential backoff on 429/403.

---

## Sources

- [bgutil-ytdlp-pot-provider PyPI](https://pypi.org/project/bgutil-ytdlp-pot-provider/)
- [bgutil-ytdlp-pot-provider GitHub](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)
- [Cloud Run Cold Start Mitigation Strategies](https://omermahgoub.medium.com/mitigate-cloud-run-cold-startup-strategies-to-improve-response-time-cad5a6aea327)
- [Cloud Run Lifecycle Documentation](https://cloud.google.com/blog/topics/developers-practitioners/lifecycle-container-cloud-run)
- [Angular Debounce API Requests with RxJS](https://medium.com/@guilherme-de-oliveira/angular-15-debounce-api-request-with-rxjs-75b939aeb9ba)
- [Debounce Search Calls in Angular](https://www.damirscorner.com/blog/posts/20220408-DebounceSearchCallsInAngular.html)
- [Git Cherry-Pick Conflict Resolution](https://www.themoderncoder.com/fix-git-cherry-pick-merge-conflicts/)
- [Database Backfill Strategies at Scale](https://blog.logrocket.com/how-to-migrate-a-database-schema-at-scale/)
- [Zero-Downtime Migration with Backfill](https://medium.com/@developerawam/laravel-zero-downtime-migration-with-double-write-and-backfill-febf4c905ec6)
- [Proxy Configuration for yt-dlp](https://roundproxies.com/blog/yt-dlp/)
