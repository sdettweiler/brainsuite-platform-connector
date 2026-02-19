import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { ApiService } from '../../../core/services/api.service';

interface PlatformConnection {
  id: string;
  platform: 'META' | 'TIKTOK' | 'YOUTUBE';
  ad_account_id: string;
  ad_account_name: string;
  currency: string;
  timezone: string;
  sync_status: 'ACTIVE' | 'EXPIRED' | 'ERROR' | 'PENDING';
  last_synced_at?: string;
  initial_sync_completed: boolean;
  brainsuite_app_id?: string;
  brainsuite_app_id_image?: string;
  brainsuite_app_id_video?: string;
}

interface BrainsuiteApp {
  id: string;
  name: string;
  app_type: string;
  is_default_for_image: boolean;
  is_default_for_video: boolean;
}

interface PlatformDef {
  key: string;
  label: string;
  color: string;
  icon: string;
  description: string;
}

const PLATFORMS: PlatformDef[] = [
  { key: 'META', label: 'Meta', color: '#1877F2', icon: 'assets/images/icon-meta.png', description: 'Facebook & Instagram Ads' },
  { key: 'TIKTOK', label: 'TikTok', color: '#010101', icon: 'assets/images/icon-tiktok.png', description: 'TikTok Ads Manager' },
  { key: 'YOUTUBE', label: 'YouTube / Google', color: '#FF0000', icon: 'assets/images/icon-youtube.png', description: 'Google Ads (YouTube)' },
];

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatButtonModule, MatIconModule, MatMenuModule,
    MatProgressSpinnerModule, MatSnackBarModule, MatSelectModule, MatCheckboxModule,
    MatFormFieldModule, MatInputModule,
  ],
  template: `
    <div class="page-container">
      <section class="config-section">
        <div class="section-header">
          <div>
            <h2>Platform Connections</h2>
            <p>{{ connections.length }} connected account{{ connections.length !== 1 ? 's' : '' }}</p>
          </div>
        </div>

        <div class="platform-connect-row">
          <div *ngFor="let p of platforms" class="platform-connect-card">
            <div class="platform-logo"><img [src]="p.icon" [alt]="p.label" /></div>
            <div class="platform-info">
              <span class="platform-name">{{ p.label }}</span>
              <span class="platform-desc">{{ p.description }}</span>
            </div>
            <button
              mat-flat-button
              class="connect-btn"
              [disabled]="connecting === p.key"
              (click)="startOAuth(p.key)"
            >
              <mat-spinner *ngIf="connecting === p.key" diameter="14"></mat-spinner>
              <mat-icon *ngIf="connecting !== p.key">add</mat-icon>
              {{ connecting === p.key ? 'Connecting...' : 'Connect' }}
            </button>
          </div>
        </div>

        <div *ngIf="!loading; else loadingTpl">
          <div *ngFor="let conn of connections" class="connection-row">
            <div class="conn-platform">
              <div class="platform-dot">
                <img [src]="getPlatformIcon(conn.platform)" [alt]="conn.platform" />
              </div>
              <div class="conn-info">
                <span class="conn-name">{{ conn.ad_account_name }}</span>
                <span class="conn-id">{{ conn.ad_account_id }}</span>
              </div>
            </div>

            <div class="conn-status">
              <span class="status-chip" [class]="'status-' + conn.sync_status.toLowerCase()">
                {{ conn.sync_status }}
              </span>
              <span class="sync-time" *ngIf="conn.last_synced_at">
                Last sync: {{ conn.last_synced_at | date:'short' }}
              </span>
              <span class="sync-time" *ngIf="!conn.initial_sync_completed">
                Initial sync in progress...
              </span>
            </div>

            <div class="conn-meta">
              <span class="meta-pill">{{ conn.currency }}</span>
              <span class="meta-pill">{{ conn.timezone }}</span>
            </div>

            <div class="conn-brainsuite">
              <mat-form-field appearance="outline" class="app-select">
                <mat-label>Images App</mat-label>
                <mat-select
                  [ngModel]="conn.brainsuite_app_id_image"
                  (ngModelChange)="assignApp(conn, 'brainsuite_app_id_image', $event)"
                >
                  <mat-option value="">-- None --</mat-option>
                  <mat-option *ngFor="let app of brainsuiteApps" [value]="app.id">
                    {{ app.name }}
                  </mat-option>
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline" class="app-select">
                <mat-label>Videos App</mat-label>
                <mat-select
                  [ngModel]="conn.brainsuite_app_id_video"
                  (ngModelChange)="assignApp(conn, 'brainsuite_app_id_video', $event)"
                >
                  <mat-option value="">-- None --</mat-option>
                  <mat-option *ngFor="let app of brainsuiteApps" [value]="app.id">
                    {{ app.name }}
                  </mat-option>
                </mat-select>
              </mat-form-field>
            </div>

            <div class="conn-actions">
              <button mat-icon-button [matMenuTriggerFor]="connMenu" [matMenuTriggerData]="{conn: conn}">
                <mat-icon>more_vert</mat-icon>
              </button>
            </div>
          </div>

          <div *ngIf="connections.length === 0" class="empty-connections">
            <mat-icon>link_off</mat-icon>
            <span>No platforms connected yet</span>
            <p>Click "Connect" above to add your first ad account</p>
          </div>
        </div>

        <ng-template #loadingTpl>
          <div class="loading-row"><mat-spinner diameter="24"></mat-spinner></div>
        </ng-template>
      </section>

      <mat-menu #connMenu="matMenu">
        <ng-template matMenuContent let-conn="conn">
          <button mat-menu-item (click)="resync(conn)">
            <mat-icon>sync</mat-icon> Force Resync
          </button>
          <button mat-menu-item (click)="selectedConnection = conn">
            <mat-icon>tune</mat-icon> Default Metadata
          </button>
          <button mat-menu-item class="delete-item" (click)="deleteConnection(conn)">
            <mat-icon>link_off</mat-icon> Disconnect
          </button>
        </ng-template>
      </mat-menu>
    </div>

    <!-- Backdrop -->
    <div
      class="slide-backdrop"
      [class.visible]="pendingAccounts.length > 0 || selectedConnection"
      (click)="closePanel()"
    ></div>

    <!-- Ad Account Selection Slide Panel -->
    <div class="slide-panel" [class.open]="pendingAccounts.length > 0">
      <div class="panel-header">
        <div>
          <h2>Select Ad Accounts</h2>
          <p>{{ pendingPlatform }} — {{ pendingAccounts.length }} account{{ pendingAccounts.length !== 1 ? 's' : '' }} available</p>
        </div>
        <button mat-icon-button (click)="cancelPending()"><mat-icon>close</mat-icon></button>
      </div>

      <div class="panel-toolbar">
        <button mat-button class="select-toggle" (click)="toggleSelectAll()">
          <mat-icon>{{ selectedAccounts.length === pendingAccounts.length ? 'deselect' : 'select_all' }}</mat-icon>
          {{ selectedAccounts.length === pendingAccounts.length ? 'Select None' : 'Select All' }}
        </button>
        <span class="select-count">{{ selectedAccounts.length }} of {{ pendingAccounts.length }} selected</span>
      </div>

      <div class="panel-body">
        <div class="accounts-list">
          <div
            *ngFor="let acc of pendingAccounts"
            class="account-item"
            [class.selected]="selectedAccounts.includes(acc.id)"
            (click)="toggleAccount(acc.id)"
          >
            <div class="check-box">
              <mat-icon *ngIf="selectedAccounts.includes(acc.id)">check_box</mat-icon>
              <mat-icon *ngIf="!selectedAccounts.includes(acc.id)">check_box_outline_blank</mat-icon>
            </div>
            <div class="acc-info">
              <span class="acc-name">{{ acc.name }}</span>
              <span class="acc-id">{{ acc.id }} &middot; {{ acc.currency }} &middot; {{ acc.timezone }}</span>
            </div>
            <span class="acc-status" *ngIf="acc.status">{{ acc.status }}</span>
          </div>
        </div>
      </div>

      <div class="panel-footer">
        <button mat-stroked-button (click)="cancelPending()">Cancel</button>
        <button
          mat-flat-button
          class="connect-selected-btn"
          [disabled]="selectedAccounts.length === 0 || connectingAccounts"
          (click)="connectSelectedAccounts()"
        >
          <mat-spinner *ngIf="connectingAccounts" diameter="16"></mat-spinner>
          {{ connectingAccounts ? 'Connecting...' : 'Connect ' + selectedAccounts.length + ' Account(s)' }}
        </button>
      </div>
    </div>

    <!-- Metadata Defaults Slide Panel -->
    <div class="slide-panel" [class.open]="selectedConnection">
      <div class="panel-header">
        <div>
          <h2>Default Metadata</h2>
          <p *ngIf="selectedConnection">{{ selectedConnection.ad_account_name }}</p>
        </div>
        <button mat-icon-button (click)="selectedConnection = null"><mat-icon>close</mat-icon></button>
      </div>

      <div class="panel-body">
        <p class="empty-meta">Configure metadata fields in the <strong>Metadata Fields</strong> section first.</p>
      </div>
    </div>
  `,
  styles: [`
    .page-container { padding: 28px; display: flex; flex-direction: column; gap: 24px; max-width: 1200px; }
    .config-section { background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
    .section-header {
      display: flex; align-items: flex-start; justify-content: space-between;
      padding: 20px 24px; border-bottom: 1px solid var(--border);
      h2 { font-size: 16px; font-weight: 600; margin: 0 0 4px; }
      p { font-size: 13px; color: var(--text-secondary); margin: 0; }
    }

    .platform-connect-row {
      display: flex; gap: 12px; padding: 16px 20px; border-bottom: 1px solid var(--border);
      flex-wrap: wrap;
    }

    .platform-connect-card {
      display: flex; align-items: center; gap: 12px; padding: 12px 16px;
      border: 1px solid var(--border); border-radius: 8px; flex: 1; min-width: 200px;
    }

    .platform-logo {
      width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center;
      justify-content: center; flex-shrink: 0; overflow: hidden;
      img { width: 100%; height: 100%; object-fit: contain; }
    }

    .platform-info { flex: 1; }
    .platform-name { font-size: 14px; font-weight: 500; display: block; }
    .platform-desc { font-size: 11px; color: var(--text-secondary); }

    .connect-btn {
      background: var(--accent) !important; color: white !important;
      display: flex; align-items: center; gap: 6px; font-size: 13px;
    }

    .connection-row {
      display: grid; grid-template-columns: 1fr 180px 140px auto 48px;
      align-items: center; padding: 14px 20px; border-bottom: 1px solid var(--border);
      gap: 12px;
      &:last-child { border-bottom: none; }
      &:hover { background: var(--bg-secondary); }
    }

    .conn-platform { display: flex; align-items: center; gap: 10px; }

    .platform-dot {
      width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center;
      justify-content: center; flex-shrink: 0; overflow: hidden;
      img { width: 100%; height: 100%; object-fit: contain; }
    }

    .conn-name { font-size: 14px; font-weight: 500; display: block; }
    .conn-id { font-size: 11px; color: var(--text-muted); font-family: monospace; }

    .conn-status { display: flex; flex-direction: column; gap: 3px; }

    .status-chip {
      display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;
      &.status-active { background: rgba(52,168,83,0.15); color: #34A853; }
      &.status-expired { background: rgba(234,67,53,0.15); color: #EA4335; }
      &.status-error { background: rgba(234,67,53,0.15); color: #EA4335; }
      &.status-pending { background: rgba(251,188,4,0.15); color: #F09300; }
    }

    .sync-time { font-size: 11px; color: var(--text-muted); }

    .conn-meta { display: flex; flex-wrap: wrap; gap: 4px; }
    .meta-pill {
      font-size: 10px; padding: 2px 6px; background: var(--bg-secondary);
      border-radius: 4px; color: var(--text-secondary);
    }

    .conn-brainsuite { display: flex; gap: 6px; }
    .app-select { width: 100%; }

    .empty-connections {
      display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 48px;
      color: var(--text-muted);
      mat-icon { font-size: 36px; opacity: 0.4; }
      span { font-size: 15px; font-weight: 500; }
      p { font-size: 13px; color: var(--text-muted); }
    }

    .loading-row { display: flex; justify-content: center; padding: 32px; }
    .delete-item { color: var(--error) !important; }

    /* ── Slide-in Panel ────────────────────────────────────── */
    .slide-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.5);
      z-index: 999;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.3s ease;
      &.visible {
        opacity: 1;
        pointer-events: all;
      }
    }

    .slide-panel {
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      width: 480px;
      max-width: 90vw;
      background: var(--bg-card);
      border-left: 1px solid var(--border);
      z-index: 1000;
      display: flex;
      flex-direction: column;
      transform: translateX(100%);
      transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: -4px 0 24px rgba(0, 0, 0, 0.3);
      &.open {
        transform: translateX(0);
      }
    }

    .panel-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      padding: 24px 24px 16px;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
      h2 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
      p { font-size: 13px; color: var(--text-secondary); margin: 0; }
    }

    .panel-body {
      flex: 1;
      overflow-y: auto;
      padding: 0;
    }

    .panel-footer {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      padding: 16px 24px;
      border-top: 1px solid var(--border);
      flex-shrink: 0;
    }

    /* Account selection inside panel */
    .accounts-list { }

    .account-item {
      display: flex; align-items: center; gap: 12px; padding: 14px 24px;
      cursor: pointer; border-bottom: 1px solid var(--border); transition: background 0.15s;
      &:last-child { border-bottom: none; }
      &:hover { background: var(--bg-secondary); }
      &.selected { background: var(--accent-light); }
    }

    .check-box { color: var(--accent); flex-shrink: 0; }

    .acc-info { flex: 1; min-width: 0; }
    .acc-name { font-size: 14px; font-weight: 500; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .acc-id { font-size: 11px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
    .acc-status { font-size: 11px; padding: 2px 6px; background: var(--bg-secondary); border-radius: 4px; flex-shrink: 0; }

    .connect-selected-btn {
      background: var(--accent) !important; color: white !important;
      display: flex; align-items: center; gap: 8px;
    }

    .panel-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 16px 8px 12px;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }

    .select-toggle {
      display: flex; align-items: center; gap: 6px;
      font-size: 13px; color: var(--accent);
    }

    .select-count {
      font-size: 12px; color: var(--text-secondary);
    }

    .empty-meta { font-size: 13px; color: var(--text-secondary); padding: 24px; }
  `],
})
export class PlatformsComponent implements OnInit, OnDestroy {
  platforms = PLATFORMS;
  connections: PlatformConnection[] = [];
  brainsuiteApps: BrainsuiteApp[] = [];
  loading = true;
  connecting: string | null = null;
  connectingAccounts = false;

  pendingSessionId: string | null = null;
  pendingPlatform: string | null = null;
  pendingAccounts: any[] = [];
  selectedAccounts: string[] = [];
  selectedConnection: PlatformConnection | null = null;

  private oauthWindow: Window | null = null;
  private oauthPollInterval: any;
  private boundOAuthMessage = this.onOAuthMessage.bind(this);

  constructor(
    private api: ApiService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.loadData();
    window.addEventListener('message', this.boundOAuthMessage);
  }

  ngOnDestroy(): void {
    window.removeEventListener('message', this.boundOAuthMessage);
    if (this.oauthPollInterval) clearInterval(this.oauthPollInterval);
  }

  closePanel(): void {
    if (this.pendingAccounts.length > 0) {
      this.cancelPending();
    }
    if (this.selectedConnection) {
      this.selectedConnection = null;
    }
  }

  loadData(): void {
    this.api.get<BrainsuiteApp[]>('/platforms/brainsuite-apps').subscribe({
      next: (apps) => {
        this.brainsuiteApps = apps;
        this.loadConnections();
      },
    });
  }

  private loadConnections(): void {
    this.api.get<PlatformConnection[]>('/platforms/connections').subscribe({
      next: (conns) => {
        this.connections = conns;
        this.loading = false;
        this.applyDefaultApps();
      },
      error: () => { this.loading = false; },
    });
  }

  private applyDefaultApps(): void {
    const defaultImage = this.brainsuiteApps.find(a => a.is_default_for_image);
    const defaultVideo = this.brainsuiteApps.find(a => a.is_default_for_video);

    for (const conn of this.connections) {
      const patch: any = {};
      if (!conn.brainsuite_app_id_image && defaultImage) {
        conn.brainsuite_app_id_image = defaultImage.id;
        patch.brainsuite_app_id_image = defaultImage.id;
      }
      if (!conn.brainsuite_app_id_video && defaultVideo) {
        conn.brainsuite_app_id_video = defaultVideo.id;
        patch.brainsuite_app_id_video = defaultVideo.id;
      }
      if (Object.keys(patch).length > 0) {
        this.api.patch(`/platforms/connections/${conn.id}`, patch).subscribe();
      }
    }
  }

  startOAuth(platform: string): void {
    this.connecting = platform;

    this.api.post<{ auth_url: string; session_id: string }>('/platforms/oauth/init', { platform }).subscribe({
      next: ({ auth_url, session_id }) => {
        this.pendingSessionId = session_id;
        this.pendingPlatform = platform;

        const w = 600, h = 700;
        const left = window.screenX + (window.outerWidth - w) / 2;
        const top = window.screenY + (window.outerHeight - h) / 2;
        this.oauthWindow = window.open(auth_url, 'oauth_popup', `width=${w},height=${h},left=${left},top=${top}`);

        this.oauthPollInterval = setInterval(() => {
          if (this.oauthWindow?.closed) {
            clearInterval(this.oauthPollInterval);
            this.connecting = null;
            this.checkOAuthSession();
          }
        }, 500);
      },
      error: () => { this.connecting = null; },
    });
  }

  onOAuthMessage(event: MessageEvent): void {
    if (event.data?.type === 'oauth_callback' && event.data.session_id === this.pendingSessionId) {
      clearInterval(this.oauthPollInterval);
      if (this.oauthWindow) this.oauthWindow.close();
      this.connecting = null;
      this.checkOAuthSession();
    }
  }

  checkOAuthSession(): void {
    if (!this.pendingSessionId) return;
    this.api.get<any>(`/platforms/oauth/session/${this.pendingSessionId}`).subscribe({
      next: (session) => {
        this.pendingAccounts = session.accounts || [];
        this.selectedAccounts = this.pendingAccounts.map((a: any) => a.id);
      },
      error: () => {
        this.snackBar.open('OAuth failed. Please try again.', '', { duration: 4000 });
      },
    });
  }

  toggleSelectAll(): void {
    if (this.selectedAccounts.length === this.pendingAccounts.length) {
      this.selectedAccounts = [];
    } else {
      this.selectedAccounts = this.pendingAccounts.map((a: any) => a.id);
    }
  }

  toggleAccount(id: string): void {
    if (this.selectedAccounts.includes(id)) {
      this.selectedAccounts = this.selectedAccounts.filter(a => a !== id);
    } else {
      this.selectedAccounts = [...this.selectedAccounts, id];
    }
  }

  connectSelectedAccounts(): void {
    if (!this.pendingSessionId || this.selectedAccounts.length === 0) return;
    this.connectingAccounts = true;

    const accounts = this.pendingAccounts.filter(a => this.selectedAccounts.includes(a.id));
    this.api.post('/platforms/oauth/connect', {
      session_id: this.pendingSessionId,
      account_ids: this.selectedAccounts,
    }).subscribe({
      next: () => {
        this.connectingAccounts = false;
        this.cancelPending();
        this.loadData();
        this.snackBar.open(`${accounts.length} account(s) connected. Initial sync starting...`, '', { duration: 5000 });
      },
      error: () => { this.connectingAccounts = false; },
    });
  }

  cancelPending(): void {
    this.pendingAccounts = [];
    this.pendingSessionId = null;
    this.pendingPlatform = null;
    this.selectedAccounts = [];
  }

  assignApp(conn: PlatformConnection, field: 'brainsuite_app_id_image' | 'brainsuite_app_id_video', appId: string): void {
    this.api.patch(`/platforms/connections/${conn.id}`, { [field]: appId || null }).subscribe({
      next: () => {
        (conn as any)[field] = appId || undefined;
        this.snackBar.open('App mapping updated', '', { duration: 2000 });
      },
    });
  }

  resync(conn: PlatformConnection): void {
    this.api.post(`/platforms/connections/${conn.id}/resync`, {}).subscribe({
      next: () => { this.snackBar.open('Resync triggered', '', { duration: 2000 }); },
    });
  }

  deleteConnection(conn: PlatformConnection): void {
    if (!confirm(`Disconnect "${conn.ad_account_name}"? All synced data will be retained.`)) return;
    this.api.delete(`/platforms/connections/${conn.id}`).subscribe({
      next: () => {
        this.connections = this.connections.filter(c => c.id !== conn.id);
        this.snackBar.open('Account disconnected', '', { duration: 2000 });
      },
    });
  }

  getPlatformColor(platform: string): string {
    return PLATFORMS.find(p => p.key === platform)?.color || '#888';
  }

  getPlatformIcon(platform: string): string {
    return PLATFORMS.find(p => p.key === platform)?.icon || '';
  }
}
