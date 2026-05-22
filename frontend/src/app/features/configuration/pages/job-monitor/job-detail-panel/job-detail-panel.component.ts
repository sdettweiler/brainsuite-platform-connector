import {
  ChangeDetectorRef,
  Component, Input, Output, EventEmitter,
  OnChanges, OnDestroy, OnInit, SimpleChanges, HostListener,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { filter, takeUntil } from 'rxjs/operators';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { JobMonitorService, JobSnapshot } from '../../../../../core/services/job-monitor.service';

// Full job detail shape returned by GET /jobs/{id}
interface JobDetail {
  id: string;
  job_id?: string;
  job_type: string;
  org_id: string;
  org_name: string | null;
  status: string;
  progress_current: number;
  progress_total: number | null;
  started_at: string | null;
  ended_at: string | null;
  metadata_: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  error: { traceback?: string; message?: string } | null;
  connection_name: string | null;
  platform_ad_account_id: string | null;
  asset_name: string | null;
  asset_url: string | null;
  asset_format: string | null;
  thumbnail_url: string | null;
}

const TRACEBACK_MAX_BYTES = 10240;
const KNOWN_EXTERNAL_ID_KEYS = ['brainsuite_job_id', 'sync_job_id'];

@Component({
  standalone: true,
  selector: 'app-job-detail-panel',
  imports: [CommonModule, MatButtonModule, MatProgressSpinnerModule, MatSnackBarModule],
  templateUrl: './job-detail-panel.component.html',
  styles: [`
    /* Exact match of field-mappings-panel slide-panel CSS */
    .slide-panel-backdrop {
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.5); opacity: 0;
      transition: opacity 0.3s ease; z-index: 999; pointer-events: none;
    }
    .slide-panel-backdrop.active { opacity: 1; pointer-events: auto; }
    .slide-panel {
      position: fixed; top: 0; right: 0; width: 600px; max-width: 90vw;
      height: 100vh; background: var(--bg-card);
      border-left: 1px solid var(--border);
      box-shadow: -4px 0 24px rgba(0,0,0,0.18);
      z-index: 1000; display: flex; flex-direction: column;
      transform: translateX(100%);
      transition: transform 0.3s cubic-bezier(0.4,0,0.2,1);
    }
    .slide-panel.open { transform: translateX(0); }
    .panel-header {
      display: flex; justify-content: space-between; align-items: flex-start;
      padding: 20px 32px; border-bottom: 1px solid var(--border); flex-shrink: 0;
    }
    .panel-body { flex: 1; overflow-y: auto; padding: 16px 32px; }
    .header-left { display: flex; flex-direction: column; gap: 6px; }
    .job-type-chip {
      display: inline-block; padding: 2px 8px; border-radius: 4px;
      font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
    }
    .chip-sync { background: rgba(66,133,244,0.12); color: #4285F4; }
    .chip-download { background: rgba(52,168,83,0.12); color: #34A853; }
    .chip-autofill { background: rgba(255,119,0,0.12); color: #FF7700; }
    .chip-scoring { background: rgba(234,67,53,0.12); color: #EA4335; }
    .job-id-row {
      display: flex; align-items: center; gap: 6px;
      font-family: monospace; font-size: 13px; color: var(--text-primary);
    }
    .copy-btn { cursor: pointer; background: none; border: none; color: var(--text-muted); padding: 2px 4px; font-size: 14px; }
    .copy-btn:hover { color: var(--accent); }
    .times-row { font-size: 13px; color: var(--text-secondary); }
    .section-label {
      font-size: 11px; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.5px; color: var(--text-muted); margin: 16px 0 8px;
    }
    .section-label-error { color: var(--error); }
    .ref-table, .detail-table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
    .ref-table td, .detail-table td { padding: 4px 0; font-size: 13px; vertical-align: top; }
    .ref-table td:first-child, .detail-table td:first-child { width: 160px; color: var(--text-secondary); }
    .ref-table td:last-child, .detail-table td:last-child { font-family: monospace; color: var(--text-primary); }
    .fields-table { width: 100%; border-collapse: collapse; }
    .fields-table th, .fields-table td { padding: 6px 8px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; }
    .fields-table th { font-weight: 400; color: var(--text-secondary); font-size: 12px; }
    .asset-list { list-style: none; padding: 0; margin: 0 0 16px; }
    .asset-list li { padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 13px; display: flex; gap: 12px; align-items: center; }
    .asset-id-mono { font-family: monospace; color: var(--text-secondary); }
    .asset-link { color: var(--accent); text-decoration: none; font-size: 13px; }
    .asset-link:hover { text-decoration: underline; }
    .asset-error-text { font-size: 13px; color: var(--error); font-style: italic; }
    .score-table { width: 100%; border-collapse: collapse; }
    .score-table th, .score-table td { padding: 6px 8px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; }
    .score-table th { font-weight: 400; color: var(--text-secondary); font-size: 12px; }
    .error-row td { padding: 0 8px 8px; color: var(--error); font-size: 13px; font-style: italic; }
    .traceback-block {
      font-family: monospace; font-size: 13px; color: var(--error);
      background: rgba(231,76,60,0.08); border: 1px solid rgba(231,76,60,0.2);
      border-radius: 6px; padding: 12px; max-height: 320px; overflow-y: auto;
      white-space: pre-wrap; word-break: break-word;
    }
    .spinner-center { display: flex; justify-content: center; align-items: center; height: 200px; }
    summary { cursor: pointer; font-size: 13px; color: var(--text-secondary); margin: 8px 0; }
    .download-stats-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 4px; }
    .stat-pill { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
    .stat-success { background: rgba(52,168,83,0.12); color: #34A853; }
    .stat-error { background: rgba(234,67,53,0.12); color: #EA4335; }
    .stat-muted { background: rgba(128,128,128,0.12); color: var(--text-secondary); }
    .org-row { display: flex; align-items: center; }
    .asset-name-text { font-size: 13px; color: var(--text-primary); font-weight: 500; }
    .asset-type-badge {
      display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px;
      font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px;
      background: rgba(66,133,244,0.1); color: #4285F4;
    }
    .asset-preview-header {
      display: flex; align-items: center; gap: 8px; margin-bottom: 8px; margin-top: 16px;
    }
    .asset-name-link {
      background: none; border: none; cursor: pointer; padding: 0;
      font-size: 14px; font-weight: 500; color: var(--accent); text-align: left;
    }
    .asset-name-link:hover { text-decoration: underline; }
    .asset-preview-wrap { margin-bottom: 16px; }
    .asset-preview-img {
      max-width: 100%; max-height: 240px; border-radius: 6px;
      border: 1px solid var(--border); display: block; object-fit: cover;
    }
    .asset-preview-video-wrap { position: relative; display: inline-block; }
    .video-badge {
      position: absolute; bottom: 8px; left: 8px;
      background: rgba(0,0,0,0.6); color: #fff; border-radius: 4px;
      font-size: 12px; padding: 2px 8px;
    }
    .close-btn { background: none; border: none; cursor: pointer; color: var(--text-secondary); font-size: 20px; padding: 4px; }
    .close-btn:hover { color: var(--text-primary); }
    a[target="_blank"] { color: var(--accent); }
  `],
})
export class JobDetailPanelComponent implements OnInit, OnChanges, OnDestroy {
  @Input() jobId: string | null = null;
  @Input() isOpen = false;
  @Output() closed = new EventEmitter<void>();

  jobDetail: JobDetail | null = null;
  loading = false;
  private fullTraceback: string = '';
  private destroy$ = new Subject<void>();
  private lastKnownSnapshot: JobSnapshot | null = null;

  constructor(
    private jobMonitorService: JobMonitorService,
    private snackBar: MatSnackBar,
    private cdr: ChangeDetectorRef,
    private router: Router,
  ) {}

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.isOpen) this.closed.emit();
  }

  // Subscribe to jobs$ and reload ONLY when the open job's own status or progress changes.
  // jobs$ emits the full job map on every SSE frame (any job update), so we must compare
  // against the last known snapshot to avoid reloading on unrelated events.
  ngOnInit(): void {
    this.jobMonitorService.jobs$
      .pipe(
        filter((jobs: JobSnapshot[]) => {
          if (!this.jobId || !this.isOpen) return false;
          const snapshot = jobs.find(j => j.job_id === this.jobId);
          if (!snapshot) return false;
          const changed = !this.lastKnownSnapshot
            || this.lastKnownSnapshot.status !== snapshot.status
            || this.lastKnownSnapshot.progress_current !== snapshot.progress_current;
          if (changed) this.lastKnownSnapshot = snapshot;
          return changed;
        }),
        takeUntil(this.destroy$),
      )
      .subscribe(() => {
        if (this.isOpen && this.jobId) {
          this.loadJobDetail(false);
        }
      });
  }

  ngOnChanges(changes: SimpleChanges): void {
    const openChange = changes['isOpen'];
    const idChange = changes['jobId'];
    if (idChange) {
      this.lastKnownSnapshot = null;  // reset when switching to a different job
    }
    if ((openChange?.currentValue || idChange) && this.isOpen && this.jobId) {
      this.loadJobDetail(true);
    }
    if (!this.isOpen) {
      this.jobDetail = null;
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  onBackdropClick(): void { this.closed.emit(); }
  onClose(): void { this.closed.emit(); }

  private loadJobDetail(clearFirst = false): void {
    if (clearFirst) {
      this.jobDetail = null;
    }
    this.loading = true;
    this.jobMonitorService.getJobDetail(this.jobId!)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (detail) => {
          this.jobDetail = detail;
          this.loading = false;
          if (detail.error?.traceback || detail.error?.message) {
            this.fullTraceback = detail.error.traceback || detail.error.message || '';
          }
          this.cdr.markForCheck();
        },
        error: () => {
          this.loading = false;
          this.cdr.markForCheck();
        },
      });
  }

  // Helpers for template
  getJobId(): string { return this.jobDetail?.id ?? ''; }

  getChipClass(jobType: string): string {
    if (jobType.startsWith('sync')) return 'chip-sync';
    if (jobType === 'download') return 'chip-download';
    if (jobType === 'autofill') return 'chip-autofill';
    if (jobType === 'scoring') return 'chip-scoring';
    return '';
  }

  getExternalIds(): Array<{key: string; value: string}> {
    if (!this.jobDetail?.metadata_) return [];
    return KNOWN_EXTERNAL_ID_KEYS
      .filter(k => (this.jobDetail!.metadata_ as any)[k])
      .map(k => ({ key: k, value: String((this.jobDetail!.metadata_ as any)[k]) }));
  }

  getAutofillFields(): any[] {
    return (this.jobDetail?.output as any)?.fields ?? [];
  }

  getWhisperTranscript(): string | null {
    return (this.jobDetail?.output as any)?.whisper_transcript ?? null;
  }

  getLanguage(): string | null {
    return (this.jobDetail?.output as any)?.language ?? null;
  }

  getDownloadedAssets(): any[] {
    const items: any[] = (this.jobDetail?.output as any)?.downloaded ?? [];
    // Filter out corrupted rows where asset_id is a dict key string rather than a real ID
    return items.filter(item => {
      const id: string = item?.asset_id ?? '';
      return id.length > 8 || item?.asset_name;
    });
  }

  hasCorruptedDownloads(): boolean {
    const items: any[] = (this.jobDetail?.output as any)?.downloaded ?? [];
    return items.some(item => {
      const id: string = item?.asset_id ?? '';
      return id.length > 0 && id.length <= 8 && !item?.asset_name;
    });
  }

  getFailedDownloads(): any[] {
    return (this.jobDetail?.output as any)?.failed ?? [];
  }

  humanizeDownloadError(error: string): string {
    const e = (error ?? '').toLowerCase();
    if (e.includes('cookies') || e.includes('authentication expired')) return 'YouTube authentication expired';
    if (e.includes('private')) return 'Video is private';
    if (e.includes('age') && (e.includes('restrict') || e.includes('confirm'))) return 'Age-restricted video';
    if ((e.includes('unavailable') || e.includes('deleted') || e.includes('removed')) && (e.includes('country') || e.includes('region'))) return 'Video unavailable in this region';
    if (e.includes('unavailable') || e.includes('deleted') || e.includes('removed')) return 'Video unavailable or deleted';
    if (e.includes('no video formats') || e.includes('requested format is not available') || e.includes('only images')) return 'No downloadable video format found';
    if (e.includes('invalid') && (e.includes('video id') || e.includes('youtube id') || e.includes('yt_video'))) return 'YouTube video ID invalid';
    if (e.includes('all attempts failed') || e.includes('no file produced')) return 'All download attempts failed (blocked)';
    if (e.includes('403') || e.includes('forbidden')) return 'All download attempts failed (blocked)';
    if (e.includes('429') || e.includes('too many requests')) return 'Rate limited — try again later';
    return 'Download failed';
  }

  getAllDownloadItems(): Array<{ asset_id: string; asset_name?: string; asset_format?: string; url?: string; failed: boolean; humanError?: string }> {
    const succeeded = this.getDownloadedAssets().map(item => ({ ...item, failed: false }));
    const failed = this.getFailedDownloads().map(item => ({
      asset_id: item.asset_id,
      failed: true,
      humanError: this.humanizeDownloadError(item.error ?? ''),
    }));
    return [...succeeded, ...failed];
  }

  getDownloadStats(): { succeeded: number; failed: number; notFound: number } | null {
    const out = this.jobDetail?.output as any;
    if (!out) return null;
    if (out.stats) {
      return { succeeded: out.stats.succeeded ?? 0, failed: out.stats.failed ?? 0, notFound: out.stats.not_found ?? 0 };
    }
    // Fallback: derive from arrays (completed jobs without stats key)
    const downloaded = Array.isArray(out.downloaded) ? out.downloaded.length : 0;
    const allFailed: any[] = Array.isArray(out.failed) ? out.failed : [];
    const notFound = allFailed.filter((f: any) => { const e = (f.error || '').toLowerCase(); return e.includes('unavailable') || e.includes('deleted') || e.includes('not found'); }).length;
    return { succeeded: downloaded, failed: allFailed.length - notFound, notFound };
  }

  getScoringAssets(): any[] {
    // Scoring jobs store a single-asset result (flat dict), not an assets array.
    // Normalise to a one-element array for the template.
    const out = this.jobDetail?.output as any;
    if (!out) return [];
    if (Array.isArray(out.assets)) return out.assets;
    if (out.score !== undefined || out.endpoint_type) {
      return [{
        asset_id: (this.jobDetail?.metadata_ as any)?.asset_id ?? null,
        asset_name: this.jobDetail?.asset_name ?? null,
        score: out.score ?? null,
        endpoint_type: out.endpoint_type ?? null,
        error: null,
      }];
    }
    return [];
  }

  getScoringDimensions(): Array<{name: string; score: number | null; rating: string | null}> {
    const legResults = (this.jobDetail?.output as any)?.dimensions?.legResults;
    if (!Array.isArray(legResults) || legResults.length === 0) return [];
    const categories = legResults[0]?.executiveSummary?.categories;
    if (!Array.isArray(categories)) return [];
    return categories.map((cat: any) => ({
      name: cat.name ?? '',
      score: cat.score ?? null,
      rating: cat.rating ?? null,
    }));
  }

  getAssetPreviewUrl(): string | null {
    return this.jobDetail?.asset_url ?? null;
  }

  getAssetThumbnailUrl(): string | null {
    return this.jobDetail?.thumbnail_url ?? this.jobDetail?.asset_url ?? null;
  }

  isVideoAsset(): boolean {
    return (this.jobDetail?.asset_format || '').toUpperCase() === 'VIDEO';
  }

  navigateToDashboard(): void {
    const assetId = (this.jobDetail?.metadata_ as any)?.asset_id;
    if (assetId) {
      this.router.navigate(['/dashboard'], { queryParams: { assetId } });
      this.closed.emit();
    }
  }

  getTruncatedTraceback(): string {
    if (!this.fullTraceback) return '';
    if (this.fullTraceback.length <= TRACEBACK_MAX_BYTES) return this.fullTraceback;
    return this.fullTraceback.substring(0, TRACEBACK_MAX_BYTES) + '\n... [truncated]';
  }

  copyJobId(): void {
    navigator.clipboard.writeText(this.getJobId())
      .then(() => this.snackBar.open('Job ID copied.', '', { duration: 3000 }));
  }

  copyTraceback(): void {
    navigator.clipboard.writeText(this.fullTraceback)
      .then(() => this.snackBar.open('Traceback copied.', '', { duration: 3000 }));
  }

  getDuration(): string {
    if (!this.jobDetail?.started_at) return '—';
    const start = new Date(this.jobDetail.started_at).getTime();
    const end = this.jobDetail.ended_at ? new Date(this.jobDetail.ended_at).getTime() : Date.now();
    return Math.round((end - start) / 1000) + 's';
  }

  formatDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
  }

  isSyncJob(): boolean { return !!this.jobDetail?.job_type?.startsWith('sync'); }
  isDownloadJob(): boolean { return this.jobDetail?.job_type === 'download'; }
  isAutofillJob(): boolean { return this.jobDetail?.job_type === 'autofill'; }
  isScoringJob(): boolean { return this.jobDetail?.job_type === 'scoring'; }
  hasError(): boolean { return !!(this.jobDetail?.error?.traceback || this.jobDetail?.error?.message); }
}
