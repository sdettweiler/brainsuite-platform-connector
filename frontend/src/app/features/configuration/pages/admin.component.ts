import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../../core/services/api.service';

interface CookieSlotHealth {
  status: 'valid' | 'expired' | 'missing';
}

interface CookieHealthResponse {
  primary: CookieSlotHealth;
  backup: CookieSlotHealth;
}

interface SuperAdminUser {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

interface OrgItem {
  id: string;
  name: string;
  slug: string;
  user_count: number;
  created_at: string;
}

interface OrgScoringItem {
  org_id: string;
  org_name: string;
  quota: number | null;
  scored_count: number;
  pending_count: number;
  editingQuota?: boolean;
  quotaDraft?: string | number;
  savingQuota?: boolean;
  resetting?: boolean;
}

interface ScoringConfigResponse {
  scoring_enabled: boolean;
  organizations: OrgScoringItem[];
}

interface ProxyConfigResponse {
  proxy_enabled: boolean;
  proxy_url_masked: string | null;
}

interface ProxyTestResult {
  success: boolean;
  latency_ms: number | null;
  error: string | null;
}

@Component({
  standalone: true,
  selector: 'app-admin',
  imports: [CommonModule, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatProgressSpinnerModule, MatSlideToggleModule, MatSnackBarModule],
  template: `
<div class="page-container">

  <!-- Section 1: Residential Proxy -->
  <section class="config-section">
    <div class="section-header">
      <div>
        <h2>Residential Proxy</h2>
        <p class="section-desc">Manage the system-wide residential proxy used for YouTube video creative downloads on production hosts.</p>
      </div>
      <div class="scoring-toggle-row">
        <div>
          <div class="proxy-toggle-label">Residential Proxy</div>
          <div class="proxy-toggle-hint">Routes all YouTube downloads through the configured residential proxy.</div>
        </div>
        <mat-slide-toggle
          aria-label="Residential proxy"
          [checked]="proxyConfig?.proxy_enabled || false"
          [disabled]="togglingProxy || loadingProxy"
          (change)="onProxyToggle($event.checked)">
          {{ proxyConfig?.proxy_enabled ? 'Enabled' : 'Disabled' }}
        </mat-slide-toggle>
      </div>
    </div>
    <div class="section-body">
      <div *ngIf="loadingProxy" class="skeleton-block"></div>
      <ng-container *ngIf="proxyConfig && !loadingProxy">
        <div class="proxy-url-card" [class.disabled]="!proxyConfig.proxy_enabled">
          <!-- State: No URL saved -->
          <div *ngIf="!proxyConfig.proxy_url_masked && !editingProxyUrl" class="url-missing">
            <span class="text-muted">No URL saved.</span>
            <button mat-stroked-button (click)="editingProxyUrl = true" [disabled]="!proxyConfig.proxy_enabled">Add URL</button>
          </div>
          <!-- State: URL configured -->
          <div *ngIf="proxyConfig.proxy_url_masked && !editingProxyUrl" class="url-display">
            <span class="masked" aria-label="Proxy URL configured, masked">{{ proxyConfig.proxy_url_masked }}</span>
            <button mat-stroked-button (click)="editingProxyUrl = true" [disabled]="!proxyConfig.proxy_enabled">Replace</button>
          </div>
          <!-- State: Edit mode -->
          <div *ngIf="editingProxyUrl" class="url-edit">
            <input type="text" [(ngModel)]="newProxyUrl" placeholder="http://user:pass@host:port" aria-label="Proxy URL">
            <div class="url-edit-actions cookie-edit-actions">
              <button mat-stroked-button (click)="discardProxyUrlEdit()" [disabled]="savingProxyUrl">Discard</button>
              <button mat-flat-button class="save-btn" (click)="saveProxyUrl()" [disabled]="!newProxyUrl.trim() || savingProxyUrl">
                <mat-spinner *ngIf="savingProxyUrl" diameter="14"></mat-spinner>
                {{ savingProxyUrl ? 'Saving...' : 'Save URL' }}
              </button>
            </div>
          </div>
        </div>
        <!-- Test Connection row (only when enabled AND URL configured) -->
        <div *ngIf="proxyConfig.proxy_enabled && proxyConfig.proxy_url_masked" class="test-section">
          <button mat-stroked-button (click)="testProxyConnection()" [disabled]="testingProxy">
            <span class="btn-inner">
              <mat-spinner *ngIf="testingProxy" diameter="14"></mat-spinner>
              {{ testingProxy ? 'Testing...' : 'Test Connection' }}
            </span>
          </button>
          <div *ngIf="testResult" class="test-result" role="status" [class.success]="testResult.success" [class.error]="!testResult.success">
            <span *ngIf="testResult.success">Reachable ({{ testResult.latency_ms }}ms)</span>
            <span *ngIf="!testResult.success">Failed: {{ testResult.error }}</span>
          </div>
        </div>
      </ng-container>
    </div>
  </section>

  <!-- Section 2: YouTube Cookies -->
  <section class="config-section">
    <div class="section-header">
      <div>
        <h2>YouTube Cookies</h2>
        <p class="section-desc">Manage system-wide DV360 cookie credentials used for video asset downloads.</p>
      </div>
    </div>
    <div class="section-body">
      <div *ngIf="loadingCookies" class="skeleton-block"></div>
      <div *ngIf="cookieError && !loadingCookies" class="error-text">Could not load cookie status. Refresh to retry.</div>

      <ng-container *ngIf="cookieHealth && !loadingCookies">
        <!-- Primary Cookie Card -->
        <div class="cookie-card">
          <div class="slot-header">
            <span>Primary Cookie</span>
            <span class="badge" [ngClass]="'badge-' + cookieHealth.primary.status">{{ cookieHealth.primary.status | uppercase }}</span>
          </div>

          <!-- State D: MISSING -->
          <div *ngIf="cookieHealth.primary.status === 'missing' && !editingPrimary" class="cookie-missing">
            <span class="text-muted">No cookie saved.</span>
            <button mat-stroked-button (click)="editingPrimary = true">Add Cookie</button>
          </div>

          <!-- State A: Masked (not missing, not editing) -->
          <div *ngIf="cookieHealth.primary.status !== 'missing' && !editingPrimary" class="cookie-display">
            <span class="masked">&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;</span>
            <button mat-stroked-button (click)="editingPrimary = true">Replace</button>
          </div>

          <!-- State C: Replace mode -->
          <div *ngIf="editingPrimary" class="cookie-edit">
            <textarea [(ngModel)]="newPrimaryCookie" placeholder="Paste Netscape cookie text here" rows="6" aria-label="Primary cookie content"></textarea>
            <div class="cookie-edit-actions">
              <button mat-stroked-button (click)="discardEdit('primary')">Discard</button>
              <button mat-flat-button class="save-btn" (click)="saveCookie('primary')" [disabled]="savingPrimary">
                <mat-spinner *ngIf="savingPrimary" diameter="16"></mat-spinner>
                {{ savingPrimary ? 'Saving...' : 'Save Cookie' }}
              </button>
            </div>
          </div>
        </div>

        <!-- Backup Cookie Card -->
        <div class="cookie-card">
          <div class="slot-header">
            <span>Backup Cookie</span>
            <span class="badge" [ngClass]="'badge-' + cookieHealth.backup.status">{{ cookieHealth.backup.status | uppercase }}</span>
          </div>

          <div *ngIf="cookieHealth.backup.status === 'missing' && !editingBackup" class="cookie-missing">
            <span class="text-muted">No cookie saved.</span>
            <button mat-stroked-button (click)="editingBackup = true">Add Cookie</button>
          </div>

          <div *ngIf="cookieHealth.backup.status !== 'missing' && !editingBackup" class="cookie-display">
            <span class="masked">&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;</span>
            <button mat-stroked-button (click)="editingBackup = true">Replace</button>
          </div>

          <div *ngIf="editingBackup" class="cookie-edit">
            <textarea [(ngModel)]="newBackupCookie" placeholder="Paste Netscape cookie text here" rows="6" aria-label="Backup cookie content"></textarea>
            <div class="cookie-edit-actions">
              <button mat-stroked-button (click)="discardEdit('backup')">Discard</button>
              <button mat-flat-button class="save-btn" (click)="saveCookie('backup')" [disabled]="savingBackup">
                <mat-spinner *ngIf="savingBackup" diameter="16"></mat-spinner>
                {{ savingBackup ? 'Saving...' : 'Save Cookie' }}
              </button>
            </div>
          </div>
        </div>
      </ng-container>
    </div>
  </section>

  <!-- Section 3: SuperAdmin Management -->
  <section class="config-section">
    <div class="section-header">
      <div>
        <h2>SuperAdmin Management</h2>
        <p class="section-desc">Manage platform administrators. SuperAdmins have access to system configuration.</p>
      </div>
    </div>
    <div class="section-body">
      <div *ngIf="superAdmins.length === 0 && !loadingAdmins" class="empty-state">
        <p>No SuperAdmins found. Use the form below to promote a user.</p>
      </div>
      <table *ngIf="superAdmins.length > 0" class="admin-table">
        <thead>
          <tr><th>Email</th><th style="width: 160px">Name</th><th style="width: 120px">Joined</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let admin of superAdmins">
            <td>{{ admin.email }}</td>
            <td>{{ admin.full_name }}</td>
            <td class="text-secondary">{{ admin.created_at | date:'mediumDate' }}</td>
          </tr>
        </tbody>
      </table>

      <div class="promote-row">
        <mat-form-field appearance="outline" class="promote-input">
          <mat-label>Email address to promote</mat-label>
          <input matInput type="email" [(ngModel)]="promoteEmail" (keyup.enter)="promoteUser()">
        </mat-form-field>
        <button mat-flat-button class="save-btn" (click)="promoteUser()" [disabled]="promotingUser || !promoteEmail.trim()">
          <mat-spinner *ngIf="promotingUser" diameter="16"></mat-spinner>
          {{ promotingUser ? 'Promoting...' : 'Promote to SuperAdmin' }}
        </button>
      </div>
    </div>
  </section>

  <!-- Section 4: Organizations (read-only) -->
  <section class="config-section">
    <div class="section-header">
      <div>
        <h2>Organizations</h2>
        <p class="section-desc">Read-only list of all organizations on the platform.</p>
      </div>
    </div>
    <div class="section-body">
      <div *ngIf="organizations.length === 0 && !loadingOrgs" class="empty-state">
        <p>No organizations found.</p>
      </div>
      <table *ngIf="organizations.length > 0" class="admin-table">
        <thead>
          <tr><th>Name</th><th style="width: 160px">Slug</th><th style="width: 80px; text-align: right">Users</th><th style="width: 120px">Created</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let org of organizations">
            <td>{{ org.name }}</td>
            <td><code class="slug-code">{{ org.slug }}</code></td>
            <td style="text-align: right">{{ org.user_count }}</td>
            <td class="text-secondary">{{ org.created_at | date:'mediumDate' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- Section 5: Scoring Controls -->
  <section class="config-section">
    <div class="section-header">
      <div>
        <h2>Scoring Controls</h2>
        <p class="section-desc">Manage auto-scoring globally and set per-org quotas. Reset assets back to unscored to retrigger scoring.</p>
      </div>
    </div>
    <div class="section-body">
      <div *ngIf="loadingScoring" class="skeleton-block"></div>

      <ng-container *ngIf="!loadingScoring && scoringConfig">
        <!-- Global toggle -->
        <div class="scoring-toggle-row">
          <div>
            <div class="scoring-toggle-label">Auto-scoring</div>
            <div class="scoring-toggle-hint">When disabled, the scoring batch job will not process any assets across all organizations.</div>
          </div>
          <mat-slide-toggle
            [checked]="scoringConfig.scoring_enabled"
            [disabled]="togglingScoring"
            (change)="toggleScoring($event.checked)">
            {{ scoringConfig.scoring_enabled ? 'Enabled' : 'Disabled' }}
          </mat-slide-toggle>
        </div>

        <!-- Per-org quota + reset table -->
        <table class="admin-table scoring-table" *ngIf="scoringConfig.organizations.length > 0">
          <thead>
            <tr>
              <th>Organization</th>
              <th style="width: 110px; text-align: right">Scored</th>
              <th style="width: 110px; text-align: right">Pending</th>
              <th style="width: 180px; text-align: right">Quota</th>
              <th style="width: 120px; text-align: right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let org of scoringConfig.organizations">
              <td>{{ org.org_name }}</td>
              <td style="text-align: right">{{ org.scored_count }}</td>
              <td style="text-align: right">{{ org.pending_count }}</td>
              <!-- Quota cell -->
              <td>
                <ng-container *ngIf="!org.editingQuota">
                  <div class="quota-view-row">
                    <span class="quota-display" [class.quota-unlimited]="org.quota === null">
                      {{ org.quota === null ? 'Unlimited' : org.quota }}
                    </span>
                    <button type="button" class="edit-quota-btn" title="Edit quota" (click)="startEditQuota(org)">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
                    </button>
                  </div>
                </ng-container>
                <ng-container *ngIf="org.editingQuota">
                  <div class="quota-edit-row">
                    <input class="quota-input" type="number" min="0" [(ngModel)]="org.quotaDraft" placeholder="e.g. 500">
                    <button type="button" class="save-quota-btn" title="Save" [disabled]="org.savingQuota" (click)="saveQuota(org)">
                      <mat-spinner *ngIf="org.savingQuota" diameter="14"></mat-spinner>
                      <svg *ngIf="!org.savingQuota" width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                    </button>
                    <button type="button" class="cancel-quota-btn" title="Cancel" (click)="cancelEditQuota(org)">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                    </button>
                  </div>
                </ng-container>
              </td>
              <!-- Reset cell -->
              <td style="text-align: right">
                <button mat-stroked-button class="reset-btn" [disabled]="org.resetting" (click)="resetOrg(org)">
                  <mat-spinner *ngIf="org.resetting" diameter="14"></mat-spinner>
                  {{ org.resetting ? 'Resetting...' : 'Reset Stuck' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div *ngIf="scoringConfig.organizations.length === 0" class="empty-state">
          <p>No organizations with BrainSuite configuration found.</p>
        </div>
      </ng-container>
    </div>
  </section>

</div>
  `,
  styles: [`
    .page-container {
      padding: 28px;
      max-width: 900px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .config-section {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }

    .section-header {
      padding: 24px;
      border-bottom: 1px solid var(--border);
      h2 { margin: 0 0 4px; font-size: 16px; font-weight: 600; }
      .section-desc { margin: 0; font-size: 13px; color: var(--text-secondary); }
    }

    .section-body { padding: 24px; }

    .cookie-card {
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
      margin-bottom: 12px;
    }

    .slot-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 600;
      margin-bottom: 8px;
    }

    .badge {
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 2px 8px;
      border-radius: 3px;
    }

    .badge-valid { background: rgba(46, 204, 113, 0.15); color: #2ECC71; }
    .badge-expired { background: rgba(243, 156, 18, 0.15); color: #F39C12; }
    .badge-missing { background: var(--border); color: var(--text-secondary); }

    .cookie-display {
      display: flex;
      gap: 8px;
      align-items: center;
    }

    .cookie-missing {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .masked {
      font-family: monospace;
      color: var(--text-muted);
      letter-spacing: 1px;
    }

    .cookie-edit {
      textarea {
        width: 100%;
        padding: 8px;
        border: 1px solid var(--border);
        border-radius: 8px;
        background: var(--bg-primary);
        color: var(--text-primary);
        font-family: monospace;
        font-size: 13px;
        resize: vertical;
      }
    }

    .cookie-edit-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 8px;
    }

    .save-btn {
      background: var(--accent) !important;
      color: white !important;
      display: inline-flex !important;
      align-items: center;
      gap: 8px;
    }

    .admin-table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 16px;
      thead { background: var(--bg-hover); }
      th, td { padding: 8px; text-align: left; border-bottom: 1px solid var(--border); font-size: 14px; }
      th { font-size: 13px; font-weight: 400; color: var(--text-secondary); }
    }

    .slug-code {
      font-family: monospace;
      color: var(--text-muted);
      font-size: 13px;
    }

    .text-secondary { color: var(--text-secondary); }
    .text-muted { color: var(--text-muted); }

    .promote-row {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      .promote-input { flex: 1; }
    }

    .empty-state {
      padding: 48px 0;
      text-align: center;
      color: var(--text-muted);
      font-size: 14px;
    }

    .skeleton-block {
      height: 120px;
      background: var(--bg-secondary);
      border-radius: 6px;
      animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }

    .error-text { color: var(--error); font-size: 14px; }

    .scoring-toggle-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 0 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 20px;
    }
    .scoring-toggle-label { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
    .scoring-toggle-hint { font-size: 13px; color: var(--text-secondary); max-width: 480px; }

    .scoring-table { margin-top: 0; td { vertical-align: middle; } }

    .quota-view-row {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 2px;
    }
    .quota-display { font-size: 14px; }
    .quota-unlimited { color: var(--text-muted); font-style: italic; }

    .edit-quota-btn, .save-quota-btn, .cancel-quota-btn {
      background: none; border: none; padding: 2px 3px; cursor: pointer;
      display: inline-flex; align-items: center; justify-content: center;
      color: var(--text-muted); border-radius: 3px;
      &:hover { color: var(--text-primary); background: var(--bg-hover); }
      &:disabled { opacity: 0.4; cursor: default; }
    }
    .save-quota-btn { color: var(--accent); }

    .quota-edit-row {
      display: inline-flex;
      align-items: center;
      gap: 2px;
    }
    .quota-input {
      width: 72px;
      padding: 2px 6px;
      border: 1px solid var(--border);
      border-radius: 4px;
      background: var(--bg-primary);
      color: var(--text-primary);
      font-size: 13px;
      text-align: right;
      &:focus { outline: none; border-color: var(--accent); }
    }
    .save-quota-btn { color: var(--accent); }

    .reset-btn {
      font-size: 12px;
      padding: 0 10px;
      height: 28px;
      line-height: 28px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .proxy-toggle-label { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
    .proxy-toggle-hint { font-size: 13px; color: var(--text-secondary); max-width: 480px; }

    .proxy-url-card {
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
      margin-bottom: 16px;
      transition: opacity 0.2s;
      &.disabled { opacity: 0.5; pointer-events: none; }
    }

    .url-missing, .url-display {
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
    }

    .url-edit {
      input {
        width: 100%;
        padding: 8px;
        border: 1px solid var(--border);
        border-radius: 6px;
        background: var(--bg-primary);
        color: var(--text-primary);
        font-family: monospace;
        font-size: 12px;
        &:focus { outline: none; border-color: var(--accent); }
      }
    }

    .test-section {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--border);

      .btn-inner {
        display: inline-flex;
        align-items: center;
        gap: 6px;
      }
    }

    .test-result {
      font-size: 13px;
      padding: 8px;
      border-radius: 4px;
      &.success { background: rgba(46, 204, 113, 0.1); color: var(--success); }
      &.error { background: rgba(231, 76, 60, 0.1); color: var(--error); }
    }
  `],
})
export class AdminComponent implements OnInit {
  cookieHealth: CookieHealthResponse | null = null;
  loadingCookies = true;
  cookieError = false;
  superAdmins: SuperAdminUser[] = [];
  loadingAdmins = true;
  organizations: OrgItem[] = [];
  loadingOrgs = true;

  editingPrimary = false;
  editingBackup = false;
  newPrimaryCookie = '';
  newBackupCookie = '';
  savingPrimary = false;
  savingBackup = false;

  promoteEmail = '';
  promotingUser = false;

  scoringConfig: ScoringConfigResponse | null = null;
  loadingScoring = true;
  togglingScoring = false;

  proxyConfig: ProxyConfigResponse | null = null;
  loadingProxy = true;
  togglingProxy = false;
  editingProxyUrl = false;
  newProxyUrl = '';
  savingProxyUrl = false;
  testingProxy = false;
  testResult: ProxyTestResult | null = null;

  constructor(
    private api: ApiService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.loadProxyConfig();
    this.loadCookieHealth();
    this.loadSuperAdmins();
    this.loadOrganizations();
    this.loadScoringConfig();
  }

  loadProxyConfig(): void {
    this.loadingProxy = true;
    this.api.get<ProxyConfigResponse>('/super-admin/proxy-config').subscribe({
      next: (data) => { this.proxyConfig = data; this.loadingProxy = false; },
      error: () => { this.loadingProxy = false; this.snackBar.open('Could not load proxy config. Refresh to retry.', 'Close'); },
    });
  }

  onProxyToggle(enabled: boolean): void {
    this.togglingProxy = true;
    this.api.put<ProxyConfigResponse>('/super-admin/proxy-config', { proxy_enabled: enabled }).subscribe({
      next: (data) => {
        this.proxyConfig = data;
        this.togglingProxy = false;
        if (!enabled) { this.testResult = null; }
        this.snackBar.open(`Proxy ${enabled ? 'enabled' : 'disabled'}.`, 'Close', { duration: 3000 });
      },
      error: () => {
        this.togglingProxy = false;
        this.snackBar.open('Failed to update proxy toggle.', 'Close');
      },
    });
  }

  saveProxyUrl(): void {
    if (!this.newProxyUrl.trim()) return;
    this.savingProxyUrl = true;
    this.api.put<ProxyConfigResponse>('/super-admin/proxy-config', { proxy_url: this.newProxyUrl.trim() }).subscribe({
      next: (data) => {
        this.proxyConfig = data;
        this.savingProxyUrl = false;
        this.editingProxyUrl = false;
        this.newProxyUrl = '';
        this.snackBar.open('Proxy URL saved.', 'Close', { duration: 3000 });
      },
      error: () => {
        this.savingProxyUrl = false;
        this.snackBar.open('Failed to save proxy URL. Check your connection and try again.', 'Close');
      },
    });
  }

  discardProxyUrlEdit(): void {
    this.editingProxyUrl = false;
    this.newProxyUrl = '';
  }

  testProxyConnection(): void {
    this.testingProxy = true;
    this.testResult = null;
    this.api.post<ProxyTestResult>('/super-admin/proxy-config/test', {}).subscribe({
      next: (data) => { this.testResult = data; this.testingProxy = false; },
      error: () => { this.testResult = { success: false, error: 'Test request failed.', latency_ms: null }; this.testingProxy = false; },
    });
  }

  loadCookieHealth(): void {
    this.loadingCookies = true;
    this.cookieError = false;
    this.api.get<CookieHealthResponse>('/super-admin/youtube-cookies').subscribe({
      next: (data) => { this.cookieHealth = data; this.loadingCookies = false; },
      error: () => { this.cookieError = true; this.loadingCookies = false; },
    });
  }

  loadSuperAdmins(): void {
    this.loadingAdmins = true;
    this.api.get<SuperAdminUser[]>('/super-admin/users').subscribe({
      next: (data) => { this.superAdmins = data; this.loadingAdmins = false; },
      error: () => { this.loadingAdmins = false; },
    });
  }

  loadOrganizations(): void {
    this.loadingOrgs = true;
    this.api.get<OrgItem[]>('/super-admin/organizations').subscribe({
      next: (data) => { this.organizations = data; this.loadingOrgs = false; },
      error: () => { this.loadingOrgs = false; },
    });
  }

  saveCookie(slot: 'primary' | 'backup'): void {
    const content = slot === 'primary' ? this.newPrimaryCookie : this.newBackupCookie;
    if (!content.trim()) return;

    const payload = slot === 'primary' ? { primary: content } : { backup: content };

    if (slot === 'primary') this.savingPrimary = true;
    else this.savingBackup = true;

    this.api.put<CookieHealthResponse>('/super-admin/youtube-cookies', payload).subscribe({
      next: (updated) => {
        this.cookieHealth = updated;
        if (slot === 'primary') { this.savingPrimary = false; this.editingPrimary = false; this.newPrimaryCookie = ''; }
        else { this.savingBackup = false; this.editingBackup = false; this.newBackupCookie = ''; }
        this.snackBar.open('Cookie updated successfully.', 'Close', { duration: 3000 });
      },
      error: () => {
        if (slot === 'primary') this.savingPrimary = false;
        else this.savingBackup = false;
        this.snackBar.open('Failed to save cookie. Check your connection and try again.', 'Close');
      },
    });
  }

  discardEdit(slot: 'primary' | 'backup'): void {
    if (slot === 'primary') { this.editingPrimary = false; this.newPrimaryCookie = ''; }
    else { this.editingBackup = false; this.newBackupCookie = ''; }
  }

  loadScoringConfig(): void {
    this.loadingScoring = true;
    this.api.get<ScoringConfigResponse>('/super-admin/scoring/config').subscribe({
      next: (data) => { this.scoringConfig = data; this.loadingScoring = false; },
      error: () => { this.loadingScoring = false; },
    });
  }

  toggleScoring(enabled: boolean): void {
    this.togglingScoring = true;
    this.api.put<{ scoring_enabled: boolean }>('/super-admin/scoring/config', { scoring_enabled: enabled }).subscribe({
      next: (data) => {
        if (this.scoringConfig) this.scoringConfig.scoring_enabled = data.scoring_enabled;
        this.togglingScoring = false;
        this.snackBar.open(`Auto-scoring ${data.scoring_enabled ? 'enabled' : 'disabled'}.`, 'Close', { duration: 3000 });
      },
      error: () => {
        this.togglingScoring = false;
        this.snackBar.open('Failed to update scoring toggle.', 'Close');
      },
    });
  }

  startEditQuota(org: OrgScoringItem): void {
    org.quotaDraft = org.quota !== null ? String(org.quota) : '';
    org.editingQuota = true;
  }

  cancelEditQuota(org: OrgScoringItem): void {
    org.editingQuota = false;
    org.quotaDraft = undefined;
  }

  saveQuota(org: OrgScoringItem): void {
    const raw = String(org.quotaDraft ?? '').trim();
    const quota = raw === '' ? null : parseInt(raw, 10);
    if (raw !== '' && (isNaN(quota!) || quota! < 0)) {
      this.snackBar.open('Quota must be a positive number or empty for unlimited.', 'Close');
      return;
    }
    org.savingQuota = true;
    const url = `/super-admin/scoring/orgs/${org.org_id}/quota`;
    this.api.put<{ org_id: string; quota: number | null }>(url, { quota }).subscribe({
      next: (data) => {
        org.quota = data.quota;
        org.editingQuota = false;
        org.savingQuota = false;
        org.quotaDraft = undefined;
        this.snackBar.open(quota === null ? 'Quota removed (unlimited).' : `Quota set to ${quota}.`, 'Close', { duration: 3000 });
      },
      error: (err) => {
        org.savingQuota = false;
        this.snackBar.open(`Failed: ${err?.error?.detail || err?.status || 'unknown error'}`, 'Close');
      },
    });
  }

  resetOrg(org: OrgScoringItem): void {
    org.resetting = true;
    this.api.post<{ reset_count: number }>(`/super-admin/scoring/orgs/${org.org_id}/reset`, { statuses: ['FAILED', 'PROCESSING', 'PENDING'] }).subscribe({
      next: (data) => {
        org.resetting = false;
        this.snackBar.open(`${data.reset_count} asset${data.reset_count !== 1 ? 's' : ''} reset to unscored.`, 'Close', { duration: 3000 });
        this.loadScoringConfig();
      },
      error: () => {
        org.resetting = false;
        this.snackBar.open('Failed to reset assets.', 'Close');
      },
    });
  }

  promoteUser(): void {
    if (!this.promoteEmail.trim()) return;
    this.promotingUser = true;

    this.api.post<SuperAdminUser>('/super-admin/users/promote', { email: this.promoteEmail }).subscribe({
      next: () => {
        this.snackBar.open('User promoted to SuperAdmin.', 'Close', { duration: 3000 });
        this.loadSuperAdmins();
        this.promoteEmail = '';
        this.promotingUser = false;
      },
      error: (err) => {
        this.promotingUser = false;
        const detail = err?.error?.detail;
        if (detail === 'User not found') {
          this.snackBar.open('No user found with that email address.', 'Close');
        } else if (detail === 'User is already a SuperAdmin') {
          this.snackBar.open('This user is already a SuperAdmin.', 'Close');
        } else {
          this.snackBar.open('Failed to promote user. Check your connection and try again.', 'Close');
        }
      },
    });
  }
}
