import { Injectable, NgZone, OnDestroy } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { ApiService } from './api.service';

export type SseStatus = 'live' | 'reconnecting' | 'disconnected';

export interface JobSnapshot {
  job_id: string;
  job_type: string;
  org_id: string;
  org_name: string | null;
  status: string;
  progress_current: number;
  progress_total: number | null;
  started_at: string | null;
  ended_at: string | null;
}

@Injectable({ providedIn: 'root' })
export class JobMonitorService implements OnDestroy {
  private jobMap = new Map<string, JobSnapshot>();
  private jobsSubject = new BehaviorSubject<JobSnapshot[]>([]);
  jobs$ = this.jobsSubject.asObservable();

  private statusSubject = new BehaviorSubject<SseStatus>('reconnecting');
  connectionStatus$ = this.statusSubject.asObservable();

  private eventSource: EventSource | null = null;
  private reconnectAttempts = 0;

  constructor(
    private ngZone: NgZone,
    private authService: AuthService,
    private api: ApiService,
  ) {}

  connect(): void {
    // BLOCKER-03: close any existing EventSource before opening a new one.
    // Must be FIRST so that a null-token early return still closes the old connection.
    this.eventSource?.close();
    this.eventSource = null;

    // BLOCKER-02: guard against null token (token expiry, clearJobs reconnect, test bypass).
    const token = this.authService.getAccessToken();
    if (!token) {
      this.statusSubject.next('disconnected');
      return;
    }

    // Reset error budget so a fresh connect() does not inherit a prior session's onerror count.
    this.reconnectAttempts = 0;

    const url = `/api/v1/jobs/stream?token=${token}`;
    this.eventSource = new EventSource(url);

    this.eventSource.addEventListener('job_update', (event: MessageEvent) => {
      this.ngZone.run(() => {
        try {
          const job: JobSnapshot = JSON.parse(event.data);
          this.jobMap.set(job.job_id, job);
          this.jobsSubject.next(Array.from(this.jobMap.values()));
        } catch {
          // Malformed SSE frame — discard silently; connection remains open.
        }
      });
    });

    this.eventSource.onopen = () => this.ngZone.run(() => {
      this.reconnectAttempts = 0;
      this.statusSubject.next('live');
    });

    this.eventSource.onerror = () => this.ngZone.run(() => {
      this.reconnectAttempts++;
      this.statusSubject.next(this.reconnectAttempts >= 3 ? 'disconnected' : 'reconnecting');
    });
  }

  disconnect(): void {
    this.eventSource?.close();
    this.eventSource = null;
  }

  clearJobMap(): void {
    this.jobMap.clear();
    this.jobsSubject.next([]);
  }

  getJobs(jobType?: string, status?: string, limit = 50, offset = 0): Observable<JobSnapshot[]> {
    let path = `/jobs?limit=${limit}&offset=${offset}`;
    if (jobType) { path += `&job_type=${encodeURIComponent(jobType)}`; }
    if (status) { path += `&status=${encodeURIComponent(status)}`; }
    return this.api.get<JobSnapshot[]>(path);
  }

  getJobDetail(jobId: string): Observable<any> {
    return this.api.get<any>(`/jobs/${jobId}`);
  }

  clearJobs(jobType: string, status: string): Observable<void> {
    return this.api.delete<void>(`/jobs?job_type=${encodeURIComponent(jobType)}&status=${encodeURIComponent(status)}`);
  }

  ngOnDestroy(): void {
    this.disconnect();
  }
}
