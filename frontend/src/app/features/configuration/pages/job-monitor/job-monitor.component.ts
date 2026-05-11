import { Component, OnInit, OnDestroy, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject, forkJoin } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatChipsModule } from '@angular/material/chips';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { JobMonitorService, JobSnapshot, SseStatus } from '../../../../core/services/job-monitor.service';
// JobDetailPanelComponent imported here; its file does not exist yet — comment out temporarily if TS errors:
// import { JobDetailPanelComponent } from './job-detail-panel/job-detail-panel.component';

@Component({
  standalone: true,
  selector: 'app-job-monitor',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CommonModule,
    MatTabsModule,
    MatProgressBarModule,
    MatChipsModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    // JobDetailPanelComponent,  // uncomment after Plan 06
  ],
  templateUrl: './job-monitor.component.html',
  styleUrls: ['./job-monitor.component.scss'],
})
export class JobMonitorComponent implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();

  jobs$ = this.jobMonitorService.jobs$;
  connectionStatus$ = this.jobMonitorService.connectionStatus$;

  // Selected tab (0=Sync, 1=Download, 2=Autofill, 3=Scoring)
  activeTab = 0;
  // Per-tab status filter — null means 'All'
  selectedStatus: string | null = null;
  // Pagination
  currentOffset = 0;
  readonly PAGE_SIZE = 50;
  // Detail panel
  selectedJobId: string | null = null;

  // Tab type groups
  readonly TAB_TYPES = [
    ['sync_daily', 'sync_full', 'sync_initial', 'sync_historical'],
    ['download'],
    ['autofill'],
    ['scoring'],
  ];
  readonly TAB_LABELS = ['Sync', 'Download', 'Autofill', 'Scoring'];
  // For clear buttons — single canonical type label per tab
  readonly TAB_TYPE_LABEL = ['sync', 'download', 'autofill', 'scoring'];

  constructor(
    private jobMonitorService: JobMonitorService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.jobMonitorService.connect();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.jobMonitorService.disconnect();
  }

  // Returns jobs for the active tab's type(s), filtered by selectedStatus, sorted newest first
  getFilteredJobs(allJobs: JobSnapshot[]): JobSnapshot[] {
    const types = this.TAB_TYPES[this.activeTab];
    let filtered = allJobs.filter(j => types.includes(j.job_type));
    if (this.selectedStatus) {
      filtered = filtered.filter(j => j.status === this.selectedStatus);
    }
    // Sort newest first (started_at DESC)
    filtered = filtered.sort((a, b) => {
      const aT = a.started_at ? new Date(a.started_at).getTime() : 0;
      const bT = b.started_at ? new Date(b.started_at).getTime() : 0;
      return bT - aT;
    });
    // Pagination
    return filtered.slice(this.currentOffset, this.currentOffset + this.PAGE_SIZE);
  }

  getActiveCount(allJobs: JobSnapshot[], tabIndex: number): number {
    const types = this.TAB_TYPES[tabIndex];
    return allJobs.filter(j => types.includes(j.job_type) && (j.status === 'RUNNING' || j.status === 'PENDING')).length;
  }

  getTotalForTab(allJobs: JobSnapshot[]): number {
    const types = this.TAB_TYPES[this.activeTab];
    let filtered = allJobs.filter(j => types.includes(j.job_type));
    if (this.selectedStatus) filtered = filtered.filter(j => j.status === this.selectedStatus);
    return filtered.length;
  }

  onTabChange(index: number): void {
    this.activeTab = index;
    this.selectedStatus = null;
    this.currentOffset = 0;
    this.selectedJobId = null;
  }

  onStatusFilter(status: string | null): void {
    this.selectedStatus = status;
    this.currentOffset = 0;
  }

  onPrevPage(): void {
    if (this.currentOffset >= this.PAGE_SIZE) {
      this.currentOffset -= this.PAGE_SIZE;
    }
  }

  onNextPage(total: number): void {
    if (this.currentOffset + this.PAGE_SIZE < total) {
      this.currentOffset += this.PAGE_SIZE;
    }
  }

  selectJob(job: JobSnapshot): void {
    this.selectedJobId = job.job_id;
  }

  onPanelClosed(): void {
    this.selectedJobId = null;
  }

  hasJobsOfStatus(allJobs: JobSnapshot[], status: string): boolean {
    const types = this.TAB_TYPES[this.activeTab];
    return allJobs.some(j => types.includes(j.job_type) && j.status === status);
  }

  // D-07: clear ALL job types in the active tab's group, not just the first type.
  // For the Sync tab this means firing DELETE for sync_daily, sync_full, sync_initial,
  // and sync_historical simultaneously. forkJoin waits for all to complete.
  clearJobs(statusToClear: string, allJobs: JobSnapshot[]): void {
    const types = this.TAB_TYPES[this.activeTab];
    const count = allJobs.filter(j => types.includes(j.job_type) && j.status === statusToClear).length;
    const label = this.TAB_TYPE_LABEL[this.activeTab];

    const calls = types.map(t =>
      this.jobMonitorService.clearJobs(t, statusToClear)
    );

    forkJoin(calls)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          const statusLabel = statusToClear.toLowerCase();
          this.snackBar.open(`${count} ${statusLabel} ${label} jobs cleared.`, 'Close', { duration: 3000 });
          this.jobMonitorService.clearJobMap();
          this.jobMonitorService.connect();
        },
        error: () => {
          this.snackBar.open('Failed to clear jobs. Check your connection and try again.', 'Close');
        },
      });
  }

  getProgressMode(job: JobSnapshot): string {
    return (job.progress_total ?? 0) > 0 ? 'determinate' : 'indeterminate';
  }

  getProgressValue(job: JobSnapshot): number {
    if (!job.progress_total || job.progress_total === 0) return 0;
    return (job.progress_current / job.progress_total) * 100;
  }

  getDuration(job: JobSnapshot): string {
    if (!job.started_at) return '—';
    const start = new Date(job.started_at).getTime();
    const end = job.ended_at ? new Date(job.ended_at).getTime() : Date.now();
    return Math.round((end - start) / 1000) + 's';
  }

  formatDate(iso: string | null): string {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('en-GB', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  getOrgShort(orgId: string): string {
    return orgId.substring(0, 8);
  }

  showProgressBar(job: JobSnapshot): boolean {
    return job.status === 'RUNNING' || job.status === 'PENDING';
  }
}
