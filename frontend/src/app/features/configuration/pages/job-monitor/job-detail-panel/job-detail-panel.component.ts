import {
  Component, Input, Output, EventEmitter,
  OnChanges, OnDestroy, OnInit, SimpleChanges, HostListener,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject } from 'rxjs';
import { filter, takeUntil } from 'rxjs/operators';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { JobMonitorService, JobSnapshot } from '../../../../../core/services/job-monitor.service';

// Full job detail shape returned by GET /jobs/{id}
interface JobDetail {
  id: string;
  job_id?: string;    // alias — the REST endpoint returns 'id'; use whichever is present
  job_type: string;
  org_id: string;
  status: string;
  progress_current: number;
  progress_total: number | null;
  started_at: string | null;
  ended_at: string | null;
  metadata_: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  error: { traceback?: string; message?: string } | null;
}

const TRACEBACK_MAX_BYTES = 10240;
const KNOWN_EXTERNAL_ID_KEYS = ['brainsuite_job_id', 'sync_job_id', 'platform_sync_run_id'];

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

  constructor(
    private jobMonitorService: JobMonitorService,
    private snackBar: MatSnackBar,
  ) {}

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.isOpen) this.closed.emit();
  }

  // Subscribe to jobs$ so the panel re-fetches when an SSE event updates the open job.
  // CONTEXT.md Specifics: panel should live-update for RUNNING jobs.
  ngOnInit(): void {
    this.jobMonitorService.jobs$
      .pipe(
        filter((jobs: JobSnapshot[]) => !!this.jobId && jobs.some(j => j.job_id === this.jobId)),
        takeUntil(this.destroy$),
      )
      .subscribe(() => {
        if (this.isOpen && this.jobId) {
          this.loadJobDetail();
        }
      });
  }

  ngOnChanges(changes: SimpleChanges): void {
    const openChange = changes['isOpen'];
    const idChange = changes['jobId'];
    if ((openChange?.currentValue || idChange) && this.isOpen && this.jobId) {
      this.loadJobDetail();
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

  private loadJobDetail(): void {
    this.loading = true;
    this.jobDetail = null;
    this.jobMonitorService.getJobDetail(this.jobId!)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (detail) => {
          this.jobDetail = detail;
          this.loading = false;
          if (detail.error?.traceback) {
            this.fullTraceback = detail.error.traceback;
          }
        },
        error: () => { this.loading = false; },
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
    return (this.jobDetail?.output as any)?.downloaded ?? [];
  }

  getFailedDownloads(): any[] {
    return (this.jobDetail?.output as any)?.failed ?? [];
  }

  getScoringAssets(): any[] {
    return (this.jobDetail?.output as any)?.assets ?? [];
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
  hasError(): boolean { return !!this.jobDetail?.error?.traceback; }
}
