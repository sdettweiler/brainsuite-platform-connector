# Domain Pitfalls: Adding SSE, Job Tracking, and TikTok Download

**Domain:** Retrofitting real-time job streaming, PostgreSQL persistence, and TikTok asset download into existing production FastAPI + Angular 17 SaaS
**Researched:** 2026-05-07
**Confidence:** HIGH (verified with official docs, GitHub issues, multiple sources)

---

## Critical Pitfalls

These mistakes cause system rewrites, data loss, or unrecoverable production outages.

### Pitfall 1: SSE Connection Leaks Exhausting Worker Pool

**What goes wrong:**
FastAPI runs with limited worker processes (typically `2 × CPU_cores + 1`). Each SSE client holds one open connection. When clients don't explicitly close EventSource or connections aren't forcibly closed on route navigation, the worker pool fills up. New requests queue indefinitely, timeouts occur, and the service becomes unresponsive.

**Why it happens:**
- Angular EventSource stays open until explicitly `.close()` called — no automatic cleanup on route changes
- Browser keeps-alive on SSE streams consumes a worker slot for the lifetime of the browser tab
- Uvicorn's `--limit-concurrency` default is unbounded; under load, workers exhaust before connection count reaches OS limit
- Developers often test with 1-2 concurrent clients; production sees 50+ simultaneously

**Consequences:**
- Service becomes unresponsive under moderate monitoring load (50+ SuperAdmins)
- New sync jobs queue indefinitely, blocking all background work
- Worker restart required to free stuck connections
- Cascading failures: SSE endpoint degradation → admin can't see jobs → thinks system is broken → triggers manual restart

**Prevention:**
1. **Set uvicorn worker limits explicitly:**
   ```bash
   uvicorn main:app --workers 4 --limit-concurrency 100 --timeout-keep-alive 30
   ```
   - Keep `--timeout-keep-alive` short (30s) to auto-close idle connections
   - Set `--limit-concurrency` to reasonable value (e.g., max_workers × 25)

2. **Enforce EventSource cleanup on Angular component destroy:**
   ```typescript
   // In SuperAdmin monitoring component
   ngOnDestroy() {
     if (this.eventSource) {
       this.eventSource.close();  // MUST close explicitly
     }
   }
   ```

3. **Server-side: Close stale connections:**
   - Add heartbeat message every 30s (empty comment line to keep connection alive)
   - Browser/client timeout: if no message for 60s, server closes stream
   - Leverage Uvicorn's `timeout_keep_alive` to auto-close idle connections

4. **Monitor active SSE connections:**
   - Add Prometheus metric: `ssse_connections_active`
   - Alert if > 100 concurrent (or your capacity threshold)

5. **Test with realistic load:**
   - Simulate 50+ concurrent SuperAdmins before phase completion
   - Measure worker exhaustion time under load

**Detection:**
- Error logs: `asyncio.TimeoutError` or `OperationalError` on database operations
- Monitoring: Active worker count == configured worker count for >1 minute
- User reports: Monitoring page loads slowly, sync jobs don't update in real-time

**Phase concern:** Implement all 5 prevention steps in same phase as SSE endpoint.

---

### Pitfall 2: PostgreSQL Job Table Bloat from High-Frequency Writes

**What goes wrong:**
Every asset sync writes 1+ job status updates to the `background_jobs` table. A 1000-asset sync creates 5+ status updates = 5000+ writes over 30 minutes. Over months, the table grows to millions of rows. PostgreSQL's MVCC creates dead tuples that aren't reclaimed — autovacuum can't keep up. Sequential scans become 10× slower. Job status queries timeout. SSE streaming stalls.

**Why it happens:**
- `background_jobs` designed for persistence, not real-time status events
- Each background job makes independent writes
- No cleanup strategy for old completed jobs
- Autovacuum default settings assume moderate write patterns

**Consequences:**
- Query latency explodes after 100k rows (typical in 1-2 months)
- SSE status updates slow from <50ms to >2s (timeout)
- Job status queries block on vacuum, cascade to job table locks
- Disk space grows unbounded (2GB → 50GB in 6 months)

**Prevention:**
1. **Clean up old completed jobs (implement in same phase as job table creation):**
   ```python
   @scheduler.scheduled_job('cron', hour=2, minute=0)
   def cleanup_old_jobs():
       with Session() as session:
           cutoff = datetime.utcnow() - timedelta(days=30)
           session.execute(
               delete(BackgroundJob)
               .where(BackgroundJob.status == 'COMPLETE')
               .where(BackgroundJob.completed_at < cutoff)
           )
           session.commit()
   ```

2. **Tune autovacuum for high-update tables:**
   ```sql
   ALTER TABLE background_jobs SET (
       autovacuum_vacuum_scale_factor = 0.01,
       autovacuum_analyze_scale_factor = 0.005,
       autovacuum_vacuum_cost_delay = 2
   );
   ```

3. **Add partial index on active jobs:**
   ```sql
   CREATE INDEX idx_background_jobs_active 
   ON background_jobs(org_id, created_at DESC)
   WHERE status != 'COMPLETE';
   ```

4. **Monitor table size and alert on >1GB**

5. **Plan for pg_repack if bloat exceeds 50%**

**Detection:**
- SSE endpoint responses >1s; job status list slow; error logs show Query timeout

**Phase concern:** Cleanup must be implemented before phase is considered COMPLETE.

---

### Pitfall 3: SQLAlchemy Session Violations in APScheduler Job Tasks

**What goes wrong:**
APScheduler jobs run in separate threads/tasks. If a single SQLAlchemy Session is shared across multiple job tasks, or if sessions aren't properly committed/rolled back on error, you get race conditions where status writes fail silently and SSE never receives the update.

**Why it happens:**
- Session-per-operation pattern must be maintained inside job tasks too
- Temptation to pass a single "persistent" Session to avoid overhead
- APScheduler thread model not obvious: jobs run in thread pool
- Error handling missing: if write fails, exception swallowed by job executor

**Consequences:**
- SSE streams invalid/stale data to monitoring UI
- Admin can't trust job status
- Background jobs silently fail to persist state changes
- Cascading failures in dependent jobs

**Prevention:**
1. **Enforce session-per-operation inside all APScheduler job tasks:**
   ```python
   async def sync_dv360_accounts(org_id: int):
       # Session 1: Fetch config
       with Session() as session:
           org = session.query(Organization).get(org_id)
           config = org.dv360_config
       
       # Download (HTTP, no DB)
       assets = await download_dv360_assets(config)
       
       # Session 2: Write job_tracking
       with Session() as session:
           job = session.query(BackgroundJob).get(job_id)
           job.status = 'DOWNLOADING'
           session.commit()
       
       # Session 3: Score each asset
       for asset in assets:
           with Session() as session:
               score_asset(session, asset)
   ```

2. **Wrap job tasks with error handling and guaranteed status writes:**
   ```python
   def _do_sync_with_job_tracking(org_id: int, job_id: int):
       try:
           sync_dv360_accounts(org_id)
           with Session() as session:
               job = session.query(BackgroundJob).get(job_id)
               job.status = 'COMPLETE'
               session.commit()
       except Exception as e:
           with Session() as session:
               job = session.query(BackgroundJob).get(job_id)
               job.status = 'FAILED'
               job.error_message = str(e)
               session.commit()
           raise
   ```

3. **Never hold Session across yield points in async code**

4. **Test concurrent job execution with 10 simultaneous jobs**

**Detection:**
- SSE shows PROCESSING for 10+ minutes, then suddenly COMPLETE
- Error logs: database locked errors

**Phase concern:** Session handling must be verified before phase completes.

---

### Pitfall 4: Browser EventSource Memory Leak + Reconnect Storm on Server Restart

**What goes wrong:**
When FastAPI restarts, the browser's EventSource auto-reconnects with default 3-second retry. If 50 SuperAdmins' browsers all reconnect simultaneously, they send 50 requests in 1 second. The new worker process can't handle spike. Timeouts occur. Clients reconnect again. Recursive failure.

Additionally, if EventSource isn't closed when component is destroyed, the connection stays open in memory forever. Over time, navigating repeatedly leaks ~100KB per navigation.

**Why it happens:**
- Browser EventSource reconnects automatically — developers often unaware
- No exponential backoff; default 3s means 50 clients → 50 requests/second
- Angular change detection unaware of EventSource
- Mobile browsers kill background SSE after 30-60s anyway

**Consequences:**
- Server restart recovery takes 5-10 minutes
- Browser tab memory grows unbounded (sluggish after 1 hour)
- Staff fear restarts

**Prevention:**
1. **Implement exponential backoff on client side:**
   ```typescript
   class MonitoringService {
       private reconnectAttempts = 0;
       private maxReconnectDelay = 30000;
   
       private scheduleReconnect() {
           this.reconnectAttempts++;
           const delay = Math.min(
               1000 * Math.pow(2, this.reconnectAttempts - 1),
               this.maxReconnectDelay
           );
           setTimeout(() => this.connect(), delay);
       }
   }
   ```

2. **Force cleanup on component destroy:**
   ```typescript
   ngOnDestroy() {
       this.monitoring.disconnect();
   }
   ```

3. **Server-side: Send keep-alive heartbeat every 30s**

4. **Respect browser connection limits (max 6 per domain)**

5. **Test reconnection: stop FastAPI while 10 clients connected**

**Detection:**
- Browser console: repeated EventSource closed messages every 3s after restart
- Browser memory growth: +100KB per navigation
- Server logs: 50+ new GET requests within 1 second after restart

**Phase concern:** Exponential backoff + cleanup are prerequisites.

---

### Pitfall 5: TikTok Download Failure Blocking Entire Sync

**What goes wrong:**
yt-dlp download fails for one video (rate limit, timeout, platform change). The sync hangs waiting. Scoring job never fires. User sees PROCESSING for hours. yt-dlp outdated (browser impersonation headers change monthly) — no download occurs for any video, silently.

**Why it happens:**
- TikTok blocks automated downloaders; yt-dlp requires monthly maintenance
- Download timeouts not distinguished from permanent failures
- Retry logic missing
- yt-dlp version drift: `chrome-131` valid as of early 2026, but TikTok updates monthly

**Consequences:**
- TikTok sync appears to work but creates zero assets
- Users assume assets are syncing; in reality, download failed silently
- Scoring pipeline never fires
- Admin monitoring shows sync PROCESSING forever

**Prevention:**
1. **Separate download failures; retry transient errors:**
   ```python
   async def download_tiktok_asset(url: str, max_retries: int = 3):
       for attempt in range(max_retries):
           try:
               return _do_download_yt_dlp(url)
           except (TimeoutError, ConnectionError):
               if attempt < max_retries - 1:
                   await asyncio.sleep(2 ** attempt)
                   continue
               logger.warning(f"TikTok download failed after retries: {url}")
               return None
           except Exception as e:
               logger.error(f"TikTok permanent failure: {url}")
               return None
   
   # In sync job
   for video in tiktok_videos:
       asset_file = await download_tiktok_asset(video.url)
       if not asset_file:
           with Session() as session:
               asset = session.query(Asset).get(video.id)
               asset.status = 'DOWNLOAD_FAILED'
               session.commit()
           continue  # Don't block
   ```

2. **Keep yt-dlp updated; daily smoke test:**
   - `yt-dlp --impersonate chrome-131 [sample_url]`
   - Alert if fails

3. **Add timeout and size limits:**
   - `socket_timeout: 30`
   - Abort if > 500MB

4. **Monitor TikTok sync success rate:**
   - Alert if < 95% downloads succeed
   - Weekly report: failure reasons

**Detection:**
- TikTok sync shows 0 assets despite API returning videos
- Error logs: download failed but sync marked COMPLETE

**Phase concern:** Download failure recovery critical before TikTok production-ready.

---

## Moderate Pitfalls

### Pitfall 6: SSE Endpoint Returns Stale Data

**What goes wrong:**
SSE endpoint polls `background_jobs` table every 500ms. Meanwhile, APScheduler writes new status. If query runs between write and commit, it sees old state. UI shows DOWNLOADING when scoring started.

**Prevention:**
1. **Use Redis pub/sub instead of polling** (recommended)
2. **If polling required, add explicit commit coordination**
3. **Use READ_COMMITTED + explicit session.commit()**

---

### Pitfall 7: JSONB Field Size Explosion

**What goes wrong:**
`background_jobs.metadata` stores full Gemini response (5-10 KB per asset). 100K assets = 500MB-1GB JSONB. PostgreSQL TOAST kicks in: queries 2-10× slower. SSE query latency spikes from 50ms to 500ms.

**Prevention:**
1. **Extract essential fields only; store in separate columns**
2. **Monitor JSONB size; alert if avg > 2KB**
3. **Add partial index excluding metadata column**

---

### Pitfall 8: Angular Route Navigation Doesn't Cancel SSE

**What goes wrong:**
User navigates away while SSE buffering large update. Component destroyed, but EventSource still streaming, consuming memory. Repeated navigation leaks multiple instances.

**Prevention:**
1. **Explicit ngOnDestroy with eventSource.close()**
2. **Add 5-minute idle timeout**
3. **Server-side: Set explicit 5-minute timeout on connection**

---

## Minor Pitfalls

### Pitfall 9: Job Status Enum Mismatch

**What goes wrong:**
Backend defines status as UPPERCASE; frontend as lowercase. New status TIMEOUT added to backend, frontend crashes.

**Prevention:**
- Generate TypeScript enums from Python Pydantic model
- Auto-generate via datamodel-code-generator

---

### Pitfall 10: Redis Key Naming Collision

**What goes wrong:**
Multiple orgs publish `job_updates:123` (same job_id). SSE sees mixed events.

**Prevention:**
- Include org_id in Redis key: `job_updates:{org_id}:{job_id}`

---

### Pitfall 11: SSE Endpoint Missing Permission Check

**What goes wrong:**
`/api/jobs/stream` streams all platform jobs. User with multi-org access sees ALL orgs. Malicious user infers competitor scaling patterns.

**Prevention:**
- Filter by requesting user's org_id
- Subscribe to org-specific channels only

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| SSE endpoint | Connection leak | timeout_keep_alive=30, test 50 concurrent |
| Job table creation | Table bloat | Add cleanup immediately, tune autovacuum |
| APScheduler instrumentation | Session violations | Enforce session-per-operation, code review |
| Angular EventSource | Memory leak | ngOnDestroy cleanup, test navigation |
| TikTok download | Silent failures | Exponential retry, monitor 95%+ success |
| Multi-org visibility | Data leak | Filter by org_id, test multi-org users |
| DB polling for SSE | Stale data | Use Redis pub/sub, or explicit commit |
| Job monitoring | JSONB bloat | Extract essentials, monitor avg size |

---

## Sources

### FastAPI SSE & Worker Management
- [Top 7 Strategies to Master FastAPI Uvicorn Concurrency & Workers](https://www.techbuddies.io/2026/03/06/top-7-strategies-to-master-fastapi-uvicorn-concurrency-workers/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [Server-Sent Events with Python FastAPI](https://medium.com/@nandagopal05/server-sent-events-with-python-fastapi-f1960e0c8e4b)
- [Real-Time Notifications in Python: Using SSE with FastAPI](https://medium.com/@inandelibas/real-time-notifications-in-python-using-sse-with-fastapi-1c8c54746eb7)

### PostgreSQL & JSONB
- [How to Reduce Bloat in Large PostgreSQL Tables](https://www.tigerdata.com/learn/how-to-reduce-bloat-in-large-postgresql-tables)
- [PostgreSQL JSONB Size Limits to Prevent TOAST Slicing](https://dev.to/franckpachot/postgresql-jsonb-size-limits-to-prevent-toast-slicing-9e8)

### SQLAlchemy & Concurrency
- [SQLAlchemy Asynchronous I/O Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Using Python SQLAlchemy Session in Concurrent Threads or Tasks](https://copdips.com/2019/05/using-python-sqlalchemy-session-in-concurrent-threads-or-tasks.html)

### EventSource & Angular
- [Angular 19 SSE using EventSource](https://medium.com/@piyalidas.it/angular-19-sse-using-eventsource-ee770d18c7e4)
- [Memory Leak in Angular Router Issue #66087](https://github.com/angular/angular/issues/66087)

### Redis Pub/Sub
- [Server-Sent Events in FastAPI using Redis Pub/Sub](https://medium.com/deepdesk/server-sent-events-in-fastapi-using-redis-pub-sub-eba1dbfe8031)
- [Scaling WebSockets with PUB/SUB using Redis & FastAPI](https://medium.com/@nandagopal05/scaling-websockets-with-pub-sub-using-python-redis-fastapi-b16392ffe291)

### TikTok & yt-dlp
- [Every TikTok Downloader Quirk - Building dltkk.to](https://dev.to/john_jewskiz/every-tiktok-downloader-quirk-i-hit-building-dltkkto-and-how-i-fixed-them-909)
- [Engineering TikTok Downloaders: Overcoming Anti-Scraping](https://earezki.com/ai-news/2026-02-22-every-tiktok-downloader-quirk-i-hit-building-dltkkto-and-how-i-fixed-them/)

### MinIO
- [MinIO Concurrent Upload Issues #21646](https://github.com/minio/minio/issues/21646)
- [MinIO Large File Upload Timeouts #3223](https://github.com/minio/minio/issues/3223)

