import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { ApiService } from '../../../core/services/api.service';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { DisconnectDialogComponent, DisconnectDialogResult } from '../components/disconnect-dialog.component';
import { formatDistanceToNow } from 'date-fns';

type HealthState = 'connected' | 'token_expired' | 'sync_failed' | 'syncing';

interface OAuthAccount {
  id: string;
  name: string;
  currency?: string;
  timezone?: string;
  status?: string;
}

interface OAuthSessionResponse {
  session_id: string;
  platform: string;
  accounts: OAuthAccount[];
  ready: boolean;
  requires_manual_entry: boolean;
}

interface DV360LookupResponse {
  advertiser: OAuthAccount;
  accounts: OAuthAccount[];
}

interface PlatformConnection {
  id: string;
  platform: 'META' | 'TIKTOK' | 'GOOGLE_ADS' | 'DV360';
  ad_account_id: string;
  ad_account_name: string;
  currency: string;
  timezone: string;
  sync_status: 'ACTIVE' | 'EXPIRED' | 'ERROR' | 'PENDING';
  last_synced_at?: string;
  token_expiry?: string;
  initial_sync_completed: boolean;
  brainsuite_app_id?: string;
  brainsuite_app_id_image?: string;
  brainsuite_app_id_video?: string;
  default_metadata_values?: Record<string, string>;
}

interface ConnectionsResponse {
  items: PlatformConnection[];
  total: number;
  page: number;
  page_size: number;
  status_summary: Record<string, number>;
}

interface MetadataField {
  id: string;
  name: string;
  label: string;
  field_type: 'SELECT' | 'TEXT' | 'NUMBER';
  is_required: boolean;
  default_value?: string;
  sort_order: number;
  allowed_values?: Array<{ id: string; value: string; label: string; sort_order: number }>;
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
  { key: 'GOOGLE_ADS', label: 'Google Ads', color: '#4285F4', icon: 'assets/images/icon-google-ads.png', description: 'Search, Display & Video campaigns' },
  { key: 'DV360', label: 'DV360', color: '#00897B', icon: 'assets/images/icon-dv360.png', description: 'Display & Video 360' },
];

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatButtonModule, MatMenuModule,
    MatProgressSpinnerModule, MatSnackBarModule, MatSelectModule, MatCheckboxModule,
    MatFormFieldModule, MatInputModule, MatTooltipModule, MatDividerModule,
    MatDialogModule,
  ],
  template: `
    <div class="page-container">
      <section class="config-section">
        <div class="section-header">
          <div>
            <h2>Platform Connections</h2>
            <p>Manage your connected advertising accounts</p>
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
              <i class="bi bi-plus-lg" *ngIf="connecting !== p.key"></i>
              <span class="btn-label-full" *ngIf="connecting !== p.key">Connect Now</span>
              <span class="btn-label-mid" *ngIf="connecting !== p.key">Connect</span>
              <span *ngIf="connecting === p.key">Connecting...</span>
            </button>
          </div>
        </div>

        <!-- Status Summary Bar -->
        <div class="status-summary-bar" *ngIf="!loading">
          <span class="summary-total">{{ totalConnections }} total</span>
          <span class="summary-divider">·</span>
          <span class="summary-stat stat-active" (click)="toggleStatusFilter('ACTIVE')">
            <span class="stat-dot active"></span>{{ statusSummary['ACTIVE'] || 0 }} active
          </span>
          <span class="summary-stat stat-pending" (click)="toggleStatusFilter('PENDING')">
            <span class="stat-dot pending"></span>{{ statusSummary['PENDING'] || 0 }} pending
          </span>
          <span class="summary-stat stat-error" (click)="toggleStatusFilter('ERROR')">
            <span class="stat-dot error"></span>{{ statusSummary['ERROR'] || 0 }} errors
          </span>
          <span class="summary-stat stat-expired" (click)="toggleStatusFilter('EXPIRED')">
            <span class="stat-dot expired"></span>{{ statusSummary['EXPIRED'] || 0 }} expired
          </span>
        </div>

        <!-- Toolbar -->
        <div class="table-toolbar">
          <div class="toolbar-left">
            <div class="search-box">
              <i class="bi bi-search"></i>
              <input
                type="text"
                placeholder="Search accounts..."
                [ngModel]="searchTerm"
                (ngModelChange)="onSearchChange($event)"
              />
              <button *ngIf="searchTerm" class="clear-search" (click)="clearSearch()">
                <i class="bi bi-x-lg"></i>
              </button>
            </div>

            <div class="filter-chips">
              <button
                *ngFor="let p of platforms"
                class="filter-chip"
                [class.active]="platformFilters.includes(p.key)"
                (click)="togglePlatformFilter(p.key)"
              >
                <img [src]="p.icon" class="chip-icon" />
                {{ p.label }}
              </button>
            </div>

            <div class="status-filter">
              <mat-form-field appearance="outline" class="compact-select">
                <mat-label>Status</mat-label>
                <mat-select
                  [(ngModel)]="statusFilters"
                  multiple
                  (selectionChange)="onFiltersChanged()"
                >
                  <mat-option value="ACTIVE">Active</mat-option>
                  <mat-option value="PENDING">Pending</mat-option>
                  <mat-option value="ERROR">Error</mat-option>
                  <mat-option value="EXPIRED">Expired</mat-option>
                </mat-select>
              </mat-form-field>
            </div>
          </div>

          <div class="toolbar-right">
            <mat-form-field appearance="outline" class="compact-select sort-select">
              <mat-label>Sort by</mat-label>
              <mat-select [(ngModel)]="sortBy" (selectionChange)="onFiltersChanged()">
                <mat-option value="ad_account_name">Name</mat-option>
                <mat-option value="platform">Platform</mat-option>
                <mat-option value="status">Status</mat-option>
                <mat-option value="last_synced">Last Synced</mat-option>
                <mat-option value="currency">Currency</mat-option>
              </mat-select>
            </mat-form-field>
            <button mat-icon-button (click)="toggleSortOrder()" [matTooltip]="sortOrder === 'asc' ? 'Ascending' : 'Descending'">
              <i class="bi" [ngClass]="sortOrder === 'asc' ? 'bi-arrow-up' : 'bi-arrow-down'"></i>
            </button>
          </div>
        </div>

        <!-- Bulk Actions Bar -->
        <div class="bulk-actions-bar" *ngIf="selectedIds.size > 0">
          <div class="bulk-left">
            <mat-checkbox
              [checked]="allOnPageSelected()"
              [indeterminate]="selectedIds.size > 0 && !allOnPageSelected()"
              (change)="toggleSelectAll()"
            ></mat-checkbox>
            <span class="bulk-count">{{ selectedIds.size }} selected</span>
          </div>
          <div class="bulk-right">
            <button mat-stroked-button class="bulk-btn" (click)="bulkResync()">
              <i class="bi bi-arrow-repeat"></i> Resync
            </button>
            <button mat-stroked-button class="bulk-btn" [matMenuTriggerFor]="bulkAppMenu">
              <i class="bi bi-grid-3x3-gap"></i> Assign App
            </button>
            <button mat-stroked-button class="bulk-btn bulk-danger" (click)="bulkDisconnect()">
              <i class="bi bi-plug"></i> Disconnect
            </button>
          </div>
        </div>

        <mat-menu #bulkAppMenu="matMenu">
          <p class="menu-section-label">Assign Image App</p>
          <button mat-menu-item *ngFor="let app of brainsuiteApps" (click)="bulkAssignApp('assign_image_app', app.id)">
            {{ app.name }}
          </button>
          <mat-divider></mat-divider>
          <p class="menu-section-label">Assign Video App</p>
          <button mat-menu-item *ngFor="let app of brainsuiteApps" (click)="bulkAssignApp('assign_video_app', app.id)">
            {{ app.name }}
          </button>
        </mat-menu>

        <!-- Table -->
        <div class="table-wrapper" *ngIf="!loading; else loadingTpl">
          <table class="connections-table" *ngIf="connections.length > 0">
            <thead>
              <tr>
                <th class="col-check">
                  <mat-checkbox
                    [checked]="allOnPageSelected()"
                    [indeterminate]="selectedIds.size > 0 && !allOnPageSelected()"
                    (change)="toggleSelectAll()"
                  ></mat-checkbox>
                </th>
                <th class="col-platform">Platform</th>
                <th class="col-name">Account</th>
                <th class="col-health">Health</th>
                <th class="col-currency">Currency</th>
                <th class="col-tz">Timezone</th>
                <th class="col-sync">Last Synced</th>
                <th class="col-app">Image App</th>
                <th class="col-app">Video App</th>
                <th class="col-actions"></th>
              </tr>
            </thead>
            <tbody>
              <tr
                *ngFor="let conn of connections"
                [class.selected]="selectedIds.has(conn.id)"
              >
                <td class="col-check">
                  <mat-checkbox
                    [checked]="selectedIds.has(conn.id)"
                    (change)="toggleRowSelect(conn.id)"
                  ></mat-checkbox>
                </td>
                <td class="col-platform">
                  <div class="platform-badge">
                    <img [src]="getPlatformIcon(conn.platform)" [alt]="conn.platform" />
                    <span>{{ getPlatformLabel(conn.platform) }}</span>
                  </div>
                </td>
                <td class="col-name">
                  <span class="cell-name">{{ conn.ad_account_name }}</span>
                  <span class="cell-id">{{ conn.ad_account_id }}</span>
                </td>
                <td class="col-health">
                  <span [class]="getHealthBadgeClass(getHealthState(conn))">
                    {{ getHealthLabel(getHealthState(conn)) }}
                  </span>
                  <span class="sync-sub" *ngIf="!conn.initial_sync_completed">Syncing...</span>
                </td>
                <td class="col-currency">{{ conn.currency }}</td>
                <td class="col-tz" [matTooltip]="conn.timezone">{{ conn.timezone }}</td>
                <td class="col-sync">
                  <span [matTooltip]="conn.last_synced_at ? ((conn.last_synced_at | date:'MMM d, yyyy HH:mm') || '') : ''">
                    {{ getRelativeTime(conn.last_synced_at) }}
                  </span>
                </td>
                <td class="col-app">
                  <mat-form-field appearance="outline" class="inline-app-select">
                    <mat-select
                      [ngModel]="conn.brainsuite_app_id_image"
                      (ngModelChange)="assignApp(conn, 'brainsuite_app_id_image', $event)"
                    >
                      <mat-option value="">None</mat-option>
                      <mat-option *ngFor="let app of brainsuiteApps" [value]="app.id">
                        {{ app.name }}
                      </mat-option>
                    </mat-select>
                  </mat-form-field>
                </td>
                <td class="col-app">
                  <mat-form-field appearance="outline" class="inline-app-select">
                    <mat-select
                      [ngModel]="conn.brainsuite_app_id_video"
                      (ngModelChange)="assignApp(conn, 'brainsuite_app_id_video', $event)"
                    >
                      <mat-option value="">None</mat-option>
                      <mat-option *ngFor="let app of brainsuiteApps" [value]="app.id">
                        {{ app.name }}
                      </mat-option>
                    </mat-select>
                  </mat-form-field>
                </td>
                <td class="col-actions">
                  <button
                    *ngIf="needsReconnect(conn)"
                    mat-flat-button
                    class="reconnect-btn"
                    (click)="reconnect(conn); $event.stopPropagation()"
                  >
                    Reconnect Account
                  </button>
                  <button mat-icon-button [matMenuTriggerFor]="rowMenu" [matMenuTriggerData]="{conn: conn}">
                    <i class="bi bi-three-dots-vertical"></i>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>

          <div *ngIf="connections.length === 0" class="empty-connections">
            <i class="bi bi-plug" style="font-size: 32px;"></i>
            <span *ngIf="hasActiveFilters()">No connections match your filters</span>
            <span *ngIf="!hasActiveFilters()">No platforms connected yet</span>
            <p *ngIf="!hasActiveFilters()">Click "Connect New" above to add your first ad account</p>
            <button *ngIf="hasActiveFilters()" mat-stroked-button (click)="clearAllFilters()">Clear Filters</button>
          </div>
        </div>

        <ng-template #loadingTpl>
          <div class="loading-row"><mat-spinner diameter="24"></mat-spinner></div>
        </ng-template>

        <!-- Pagination -->
        <div class="pagination-bar" *ngIf="totalConnections > 0">
          <div class="page-size-ctrl">
            <span>Show</span>
            <mat-form-field appearance="outline" class="compact-select page-size-select">
              <mat-select [(ngModel)]="pageSize" (selectionChange)="onPageSizeChange()">
                <mat-option [value]="25">25</mat-option>
                <mat-option [value]="50">50</mat-option>
                <mat-option [value]="100">100</mat-option>
              </mat-select>
            </mat-form-field>
            <span>per page</span>
          </div>

          <div class="page-info">
            {{ (currentPage - 1) * pageSize + 1 }}–{{ currentPage * pageSize > totalConnections ? totalConnections : currentPage * pageSize }} of {{ totalConnections }}
          </div>

          <div class="page-nav">
            <button mat-icon-button [disabled]="currentPage <= 1" (click)="goToPage(1)" matTooltip="First page">
              <i class="bi bi-chevron-double-left"></i>
            </button>
            <button mat-icon-button [disabled]="currentPage <= 1" (click)="goToPage(currentPage - 1)" matTooltip="Previous">
              <i class="bi bi-chevron-left"></i>
            </button>
            <span class="page-number">{{ currentPage }} / {{ totalPages }}</span>
            <button mat-icon-button [disabled]="currentPage >= totalPages" (click)="goToPage(currentPage + 1)" matTooltip="Next">
              <i class="bi bi-chevron-right"></i>
            </button>
            <button mat-icon-button [disabled]="currentPage >= totalPages" (click)="goToPage(totalPages)" matTooltip="Last page">
              <i class="bi bi-chevron-double-right"></i>
            </button>
          </div>
        </div>
      </section>

      <mat-menu #rowMenu="matMenu">
        <ng-template matMenuContent let-conn="conn">
          <button mat-menu-item (click)="resync(conn)">
            <i class="bi bi-arrow-repeat" style="font-size: 18px; margin-right: 12px;"></i> Force Resync
          </button>
          <button mat-menu-item (click)="openMetadataPanel(conn)">
            <i class="bi bi-sliders" style="font-size: 18px; margin-right: 12px;"></i> Default Metadata
          </button>
          <button mat-menu-item class="delete-item" (click)="deleteConnection(conn)">
            <i class="bi bi-plug" style="font-size: 18px; margin-right: 12px;"></i> Disconnect
          </button>
        </ng-template>
      </mat-menu>
    </div>

    <!-- Backdrop -->
    <div
      class="slide-backdrop"
      [class.visible]="pendingAccounts.length > 0 || dv360ManualEntry || selectedConnection"
      (click)="closePanel()"
    ></div>

    <!-- Ad Account Selection Slide Panel -->
    <div class="slide-panel" [class.open]="pendingAccounts.length > 0 || dv360ManualEntry">
      <div class="panel-header">
        <div>
          <h2>Select Ad Accounts</h2>
          <p *ngIf="!dv360ManualEntry || pendingAccounts.length > 0">{{ pendingPlatform }} — {{ pendingAccounts.length }} account{{ pendingAccounts.length !== 1 ? 's' : '' }} available</p>
          <p *ngIf="dv360ManualEntry && pendingAccounts.length === 0">{{ pendingPlatform }} — Enter advertiser IDs manually</p>
        </div>
        <button mat-icon-button (click)="cancelPending()"><i class="bi bi-x-lg"></i></button>
      </div>

      <div class="dv360-manual-entry" *ngIf="dv360ManualEntry">
        <div class="manual-entry-hint">
          <i class="bi bi-info-circle"></i>
          <span>Your account has advertiser-level access. Enter your DV360 Advertiser ID(s) to add them.</span>
        </div>
        <div class="manual-entry-row">
          <input
            type="text"
            placeholder="Enter DV360 Advertiser ID"
            [(ngModel)]="dv360AdvertiserId"
            (keydown.enter)="lookupDv360Advertiser()"
            class="manual-entry-input"
          />
          <button
            mat-flat-button
            class="lookup-btn"
            [disabled]="!dv360AdvertiserId.trim() || dv360LookupLoading"
            (click)="lookupDv360Advertiser()"
          >
            <mat-spinner *ngIf="dv360LookupLoading" diameter="14"></mat-spinner>
            <span *ngIf="!dv360LookupLoading">Add</span>
          </button>
        </div>
        <div class="lookup-error" *ngIf="dv360LookupError">{{ dv360LookupError }}</div>
      </div>

      <div class="panel-toolbar" *ngIf="pendingAccounts.length > 0">
        <button mat-button class="select-toggle" (click)="toggleSelectAllAccounts()">
          <i class="bi" [ngClass]="selectedAccounts.length === pendingAccounts.length ? 'bi-dash-square' : 'bi-check2-square'"></i>
          {{ selectedAccounts.length === pendingAccounts.length ? 'Select None' : 'Select All' }}
        </button>
        <span class="select-count">{{ selectedAccounts.length }} of {{ pendingAccounts.length }} selected</span>
      </div>

      <div class="panel-body" *ngIf="pendingAccounts.length > 0">
        <div class="accounts-list">
          <div
            *ngFor="let acc of pendingAccounts"
            class="account-item"
            [class.selected]="selectedAccounts.includes(acc.id)"
            (click)="toggleAccount(acc.id)"
          >
            <div class="check-box">
              <i class="bi" [ngClass]="selectedAccounts.includes(acc.id) ? 'bi-check-square-fill' : 'bi-square'"></i>
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
        <button mat-icon-button (click)="selectedConnection = null"><i class="bi bi-x-lg"></i></button>
      </div>

      <div class="panel-body" *ngIf="selectedConnection">
        <div *ngIf="loadingMetaFields" class="loading-row">
          <mat-spinner diameter="24"></mat-spinner>
        </div>

        <div *ngIf="!loadingMetaFields && metadataFields.length === 0" class="empty-meta">
          <i class="bi bi-info-circle" style="font-size: 24px;"></i>
          <p>No metadata fields configured yet.</p>
          <p>Go to the <strong>Metadata Fields</strong> section to create fields first.</p>
        </div>

        <div *ngIf="!loadingMetaFields && metadataFields.length > 0" class="meta-defaults-form">
          <p class="meta-form-hint">Set default values that will be pre-filled when tagging new ads from this account.</p>

          <div *ngFor="let field of metadataFields" class="meta-default-field">
            <mat-form-field appearance="outline" class="full-width" *ngIf="field.field_type === 'SELECT'">
              <mat-label>{{ field.label }}</mat-label>
              <mat-select
                [value]="metadataDefaults[field.name] || ''"
                (selectionChange)="setMetadataDefault(field.name, $event.value)"
              >
                <mat-option value="">— No default —</mat-option>
                <mat-option *ngFor="let opt of field.allowed_values" [value]="opt.value">
                  {{ opt.label }}
                </mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width" *ngIf="field.field_type === 'TEXT'">
              <mat-label>{{ field.label }}</mat-label>
              <input
                matInput
                [value]="metadataDefaults[field.name] || ''"
                (blur)="setMetadataDefault(field.name, $any($event.target).value)"
              />
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width" *ngIf="field.field_type === 'NUMBER'">
              <mat-label>{{ field.label }}</mat-label>
              <input
                matInput
                type="number"
                [value]="metadataDefaults[field.name] || ''"
                (blur)="setMetadataDefault(field.name, $any($event.target).value)"
              />
            </mat-form-field>
          </div>
        </div>
      </div>

      <div class="panel-footer" *ngIf="selectedConnection && metadataFields.length > 0">
        <button mat-stroked-button (click)="selectedConnection = null">Cancel</button>
        <button
          mat-flat-button
          class="connect-selected-btn"
          [disabled]="savingDefaults"
          (click)="saveMetadataDefaults()"
        >
          <mat-spinner *ngIf="savingDefaults" diameter="16"></mat-spinner>
          {{ savingDefaults ? 'Saving...' : 'Save Defaults' }}
        </button>
      </div>
    </div>
  `,
  styleUrls: ['./platforms.component.scss'],
})
export class PlatformsComponent implements OnInit, OnDestroy {
  platforms = PLATFORMS;
  connections: PlatformConnection[] = [];
  brainsuiteApps: BrainsuiteApp[] = [];
  loading = true;
  connecting: string | null = null;
  connectingAccounts = false;

  totalConnections = 0;
  currentPage = 1;
  pageSize = 50;
  totalPages = 1;
  statusSummary: Record<string, number> = {};

  searchTerm = '';
  platformFilters: string[] = [];
  statusFilters: string[] = [];
  sortBy = 'ad_account_name';
  sortOrder = 'asc';

  selectedIds = new Set<string>();

  private searchSubject = new Subject<string>();

  pendingSessionId: string | null = null;
  pendingPlatform: string | null = null;
  pendingAccounts: OAuthAccount[] = [];
  selectedAccounts: string[] = [];
  dv360ManualEntry = false;
  dv360AdvertiserId = '';
  dv360LookupLoading = false;
  dv360LookupError = '';
  selectedConnection: PlatformConnection | null = null;
  metadataFields: MetadataField[] = [];
  metadataDefaults: Record<string, string> = {};
  savingDefaults = false;
  loadingMetaFields = false;

  private oauthWindow: Window | null = null;
  private oauthPollInterval: any;
  private syncStatusPollInterval: any;
  private boundOAuthMessage = this.onOAuthMessage.bind(this);

  constructor(
    private api: ApiService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog,
  ) {}

  ngOnInit(): void {
    this.loadData();
    window.addEventListener('message', this.boundOAuthMessage);
    this.searchSubject.pipe(
      debounceTime(300),
      distinctUntilChanged(),
    ).subscribe(() => {
      this.currentPage = 1;
      this.loadConnections();
    });
  }

  ngOnDestroy(): void {
    window.removeEventListener('message', this.boundOAuthMessage);
    if (this.oauthPollInterval) clearInterval(this.oauthPollInterval);
    if (this.syncStatusPollInterval) clearInterval(this.syncStatusPollInterval);
    this.searchSubject.complete();
  }

  onSearchChange(value: string): void {
    this.searchTerm = value;
    this.searchSubject.next(value);
  }

  clearSearch(): void {
    this.searchTerm = '';
    this.searchSubject.next('');
  }

  togglePlatformFilter(platform: string): void {
    const idx = this.platformFilters.indexOf(platform);
    if (idx >= 0) {
      this.platformFilters.splice(idx, 1);
    } else {
      this.platformFilters.push(platform);
    }
    this.currentPage = 1;
    this.loadConnections();
  }

  toggleStatusFilter(status: string): void {
    const idx = this.statusFilters.indexOf(status);
    if (idx >= 0) {
      this.statusFilters = this.statusFilters.filter(s => s !== status);
    } else {
      this.statusFilters = [status];
    }
    this.currentPage = 1;
    this.loadConnections();
  }

  onFiltersChanged(): void {
    this.currentPage = 1;
    this.loadConnections();
  }

  toggleSortOrder(): void {
    this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
    this.loadConnections();
  }

  hasActiveFilters(): boolean {
    return this.searchTerm.length > 0 || this.platformFilters.length > 0 || this.statusFilters.length > 0;
  }

  clearAllFilters(): void {
    this.searchTerm = '';
    this.platformFilters = [];
    this.statusFilters = [];
    this.currentPage = 1;
    this.loadConnections();
  }

  goToPage(page: number): void {
    if (page < 1 || page > this.totalPages) return;
    this.currentPage = page;
    this.loadConnections();
  }

  onPageSizeChange(): void {
    this.currentPage = 1;
    this.loadConnections();
  }

  toggleRowSelect(id: string): void {
    if (this.selectedIds.has(id)) {
      this.selectedIds.delete(id);
    } else {
      this.selectedIds.add(id);
    }
  }

  allOnPageSelected(): boolean {
    return this.connections.length > 0 && this.connections.every(c => this.selectedIds.has(c.id));
  }

  toggleSelectAll(): void {
    if (this.allOnPageSelected()) {
      this.connections.forEach(c => this.selectedIds.delete(c.id));
    } else {
      this.connections.forEach(c => this.selectedIds.add(c.id));
    }
  }

  bulkResync(): void {
    if (this.selectedIds.size === 0) return;
    this.api.post('/platforms/connections/bulk-action', {
      action: 'resync',
      connection_ids: Array.from(this.selectedIds),
    }).subscribe({
      next: (res: any) => {
        this.snackBar.open(res.detail, '', { duration: 3000 });
        this.selectedIds.clear();
      },
    });
  }

  bulkDisconnect(): void {
    if (this.selectedIds.size === 0) return;
    const ref = this.dialog.open(DisconnectDialogComponent, {
      data: { accountName: '', count: this.selectedIds.size },
      width: '500px',
    });
    ref.afterClosed().subscribe((result: DisconnectDialogResult | null) => {
      if (!result) return;
      const action = result.mode === 'purge' ? 'disconnect_purge' : 'disconnect';
      this.api.post('/platforms/connections/bulk-action', {
        action,
        connection_ids: Array.from(this.selectedIds),
      }).subscribe({
        next: (res: any) => {
          const msg = result.mode === 'purge'
            ? `${this.selectedIds.size} connection(s) and all data permanently deleted`
            : res.detail;
          this.snackBar.open(msg, '', { duration: 3000 });
          this.selectedIds.clear();
          this.loadConnections();
        },
      });
    });
  }

  bulkAssignApp(action: string, appId: string): void {
    if (this.selectedIds.size === 0) return;
    this.api.post('/platforms/connections/bulk-action', {
      action,
      connection_ids: Array.from(this.selectedIds),
      payload: { app_id: appId },
    }).subscribe({
      next: (res: any) => {
        this.snackBar.open(res.detail, '', { duration: 3000 });
        this.selectedIds.clear();
        this.loadConnections();
      },
    });
  }

  closePanel(): void {
    if (this.pendingAccounts.length > 0) {
      this.cancelPending();
    }
    if (this.selectedConnection) {
      this.selectedConnection = null;
      this.metadataDefaults = {};
    }
  }

  openMetadataPanel(conn: PlatformConnection): void {
    this.selectedConnection = conn;
    this.metadataDefaults = { ...(conn.default_metadata_values || {}) };
    this.loadMetadataFields();
  }

  private loadMetadataFields(): void {
    this.loadingMetaFields = true;
    this.api.get<MetadataField[]>('/assets/metadata/fields').subscribe({
      next: (fields) => {
        this.metadataFields = fields.sort((a, b) => a.sort_order - b.sort_order);
        this.loadingMetaFields = false;
      },
      error: () => {
        this.loadingMetaFields = false;
        this.snackBar.open('Failed to load metadata fields', '', { duration: 3000 });
      },
    });
  }

  setMetadataDefault(fieldId: string, value: string): void {
    if (value) {
      this.metadataDefaults[fieldId] = value;
    } else {
      delete this.metadataDefaults[fieldId];
    }
  }

  saveMetadataDefaults(): void {
    if (!this.selectedConnection) return;
    this.savingDefaults = true;
    this.api.patch(`/platforms/connections/${this.selectedConnection.id}`, {
      default_metadata_values: this.metadataDefaults,
    }).subscribe({
      next: () => {
        this.savingDefaults = false;
        if (this.selectedConnection) {
          this.selectedConnection.default_metadata_values = { ...this.metadataDefaults };
        }
        this.snackBar.open('Default metadata saved', '', { duration: 3000 });
        this.selectedConnection = null;
      },
      error: () => { this.savingDefaults = false; },
    });
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
    let params = `?page=${this.currentPage}&page_size=${this.pageSize}&sort_by=${this.sortBy}&sort_order=${this.sortOrder}`;
    if (this.searchTerm) params += `&search=${encodeURIComponent(this.searchTerm)}`;
    if (this.platformFilters.length > 0) params += `&platform=${this.platformFilters.join(',')}`;
    if (this.statusFilters.length > 0) params += `&status=${this.statusFilters.join(',')}`;

    this.api.get<ConnectionsResponse>(`/platforms/connections${params}`).subscribe({
      next: (res) => {
        this.connections = res.items;
        this.totalConnections = res.total;
        this.totalPages = Math.max(1, Math.ceil(res.total / this.pageSize));
        this.statusSummary = res.status_summary || {};
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
    this.api.get<OAuthSessionResponse>(`/platforms/oauth/session/${this.pendingSessionId}`).subscribe({
      next: (session) => {
        this.pendingAccounts = session.accounts || [];
        this.selectedAccounts = this.pendingAccounts.map((a: OAuthAccount) => a.id);
        if (session.requires_manual_entry) {
          this.dv360ManualEntry = true;
          this.dv360AdvertiserId = '';
          this.dv360LookupError = '';
        } else {
          this.dv360ManualEntry = false;
        }
      },
      error: () => {
        this.snackBar.open('OAuth failed. Please try again.', '', { duration: 4000 });
      },
    });
  }

  lookupDv360Advertiser(): void {
    if (!this.dv360AdvertiserId.trim() || !this.pendingSessionId) return;
    this.dv360LookupLoading = true;
    this.dv360LookupError = '';
    this.api.post<DV360LookupResponse>('/platforms/oauth/dv360-lookup', {
      session_id: this.pendingSessionId,
      advertiser_id: this.dv360AdvertiserId.trim(),
    }).subscribe({
      next: (res) => {
        this.dv360LookupLoading = false;
        this.pendingAccounts = res.accounts || [];
        this.selectedAccounts = this.pendingAccounts.map((a: OAuthAccount) => a.id);
        this.dv360AdvertiserId = '';
      },
      error: (err) => {
        this.dv360LookupLoading = false;
        this.dv360LookupError = err.error?.detail || 'Advertiser not found or not accessible';
      },
    });
  }

  toggleSelectAllAccounts(): void {
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
    this.dv360ManualEntry = false;
    this.dv360AdvertiserId = '';
    this.dv360LookupError = '';
    this.dv360LookupLoading = false;
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
      next: () => {
        conn.sync_status = 'PENDING';
        this.snackBar.open('Resync triggered', '', { duration: 2000 });
        this.startSyncStatusPolling();
      },
    });
  }

  private startSyncStatusPolling(): void {
    if (this.syncStatusPollInterval) return;
    this.syncStatusPollInterval = setInterval(() => {
      this.loadConnections();
      const stillPending = this.connections.some(c => c.sync_status === 'PENDING');
      if (!stillPending) {
        clearInterval(this.syncStatusPollInterval);
        this.syncStatusPollInterval = null;
      }
    }, 5000);
  }

  deleteConnection(conn: PlatformConnection): void {
    const ref = this.dialog.open(DisconnectDialogComponent, {
      data: { accountName: conn.ad_account_name },
      width: '500px',
    });
    ref.afterClosed().subscribe((result: DisconnectDialogResult | null) => {
      if (!result) return;
      const purgeParam = result.mode === 'purge' ? '?purge=true' : '';
      this.api.delete(`/platforms/connections/${conn.id}${purgeParam}`).subscribe({
        next: () => {
          this.loadConnections();
          const msg = result.mode === 'purge'
            ? 'Account and all data permanently deleted'
            : 'Account disconnected';
          this.snackBar.open(msg, '', { duration: 3000 });
        },
      });
    });
  }

  getHealthState(conn: PlatformConnection): HealthState {
    const now = new Date();
    if (conn.sync_status === 'EXPIRED') {
      return 'token_expired';
    }
    if (conn.sync_status === 'PENDING') {
      return 'syncing';
    }
    if (!conn.last_synced_at) {
      return 'sync_failed';
    }
    const hoursSinceSync = (now.getTime() - new Date(conn.last_synced_at).getTime()) / 3_600_000;
    if (hoursSinceSync > 48) {
      return 'sync_failed';
    }
    return 'connected';
  }

  getHealthLabel(state: HealthState): string {
    switch (state) {
      case 'connected': return 'Connected';
      case 'token_expired': return 'Token expired';
      case 'sync_failed': return 'Sync failed';
      case 'syncing': return 'Syncing…';
    }
  }

  getHealthBadgeClass(state: HealthState): string {
    switch (state) {
      case 'connected': return 'badge badge-success';
      case 'token_expired': return 'badge badge-warning';
      case 'sync_failed': return 'badge badge-error';
      case 'syncing': return 'badge badge-info';
    }
  }

  getRelativeTime(isoString: string | undefined): string {
    if (!isoString) return 'Never';
    return formatDistanceToNow(new Date(isoString), { addSuffix: true });
  }

  needsReconnect(conn: PlatformConnection): boolean {
    const state = this.getHealthState(conn);
    return state === 'token_expired' || state === 'sync_failed';
  }

  reconnect(conn: PlatformConnection): void {
    this.startOAuth(conn.platform);
  }

  getPlatformColor(platform: string): string {
    return PLATFORMS.find(p => p.key === platform)?.color || '#888';
  }

  getPlatformIcon(platform: string): string {
    return PLATFORMS.find(p => p.key === platform)?.icon || '';
  }

  getPlatformLabel(platform: string): string {
    return PLATFORMS.find(p => p.key === platform)?.label || platform;
  }
}
