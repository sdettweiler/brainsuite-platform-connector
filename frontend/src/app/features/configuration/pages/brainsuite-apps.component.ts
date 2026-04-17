import { Component, OnInit, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, FormControl, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialogModule, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { ApiService } from '../../../core/services/api.service';

interface BrainsuiteApp {
  id: string;
  name: string;
  app_type: 'VIDEO' | 'IMAGE' | 'MIXED';
  is_default_for_video: boolean;
  is_default_for_image: boolean;
  description?: string;
  system_app_name?: string;  // NEW — Phase 12
}

@Component({
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatDialogModule],
  template: `
    <div class="rescore-dialog">
      <h3>Configuration changed</h3>
      <p>You've updated BrainSuite credentials or app names. Would you like to re-score all previously scored assets under the new configuration?</p>
      <p class="sub-note">Re-scoring queues all SCORED assets for the next 15-minute scoring cycle. This cannot be undone.</p>
      <div class="dialog-actions">
        <button mat-stroked-button (click)="dialogRef.close('keep')">Keep existing scores</button>
        <button mat-flat-button class="rescore-btn" (click)="dialogRef.close('rescore')">Re-score all assets</button>
      </div>
    </div>
  `,
  styles: [`
    .rescore-dialog { padding: 8px 4px; min-width: 260px; max-width: 440px; }
    .rescore-dialog h3 { font-size: 16px; font-weight: 600; margin: 0 0 12px; }
    .rescore-dialog p { font-size: 13px; color: var(--text-secondary); margin: 0 0 12px; }
    .rescore-dialog .sub-note { font-size: 13px; color: var(--text-secondary); }
    .dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
    .rescore-btn { background: var(--error) !important; color: white !important; }
  `],
})
export class RescoreDialogComponent {
  constructor(public dialogRef: MatDialogRef<RescoreDialogComponent>) {}
}

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule, ReactiveFormsModule, MatButtonModule,
    MatFormFieldModule, MatInputModule, MatSelectModule, MatCheckboxModule,
    MatProgressSpinnerModule, MatSnackBarModule, MatDialogModule,
  ],
  template: `
    <div class="page-container" (click)="onClickAway($event)">

      <!-- A. BrainSuite Credentials Section (NEW - Phase 12, D-01) -->
      <section class="config-section" *ngIf="credentials">

        <!-- Collapsed state (D-02) -->
        <div *ngIf="credentialsCollapsed && hasCredentials" class="credentials-summary">
          <i class="bi bi-check-circle summary-icon"></i>
          <span>Client ID: {{ credentials!.client_id?.substring(0, 8) }}... — Connection verified</span>
          <button mat-stroked-button class="edit-credentials-btn" (click)="expandCredentials()">Edit credentials</button>
        </div>

        <!-- Expanded state -->
        <ng-container *ngIf="!credentialsCollapsed || !hasCredentials">
          <div class="section-header">
            <div>
              <h2>BrainSuite Credentials</h2>
              <p>Connect your BrainSuite account to enable creative scoring</p>
            </div>
          </div>
          <div class="section-body">
            <form [formGroup]="credentialsForm!" (ngSubmit)="saveCredentials()">

              <!-- Client ID field -->
              <div class="form-full">
                <mat-form-field appearance="outline" class="w-full">
                  <mat-label>Client ID</mat-label>
                  <input matInput formControlName="client_id" />
                </mat-form-field>
              </div>

              <!-- Client Secret field with Change/Discard pattern (D-06) -->
              <div class="form-full">
                <div class="secret-field-row">
                  <mat-form-field appearance="outline" class="secret-input">
                    <mat-label>Client Secret</mat-label>
                    <input matInput
                      [type]="'password'"
                      formControlName="client_secret"
                      [readonly]="hasCredentials && !secretEditMode"
                      [placeholder]="hasCredentials && !secretEditMode ? '\u25CF\u25CF\u25CF\u25CF\u25CF\u25CF\u25CF\u25CF (saved)' : ''"
                    />
                  </mat-form-field>
                  <button *ngIf="hasCredentials && !secretEditMode"
                    mat-stroked-button type="button" class="change-secret-btn" (click)="enableSecretEdit()">
                    Change secret
                  </button>
                  <button *ngIf="secretEditMode"
                    mat-stroked-button type="button" class="change-secret-btn" (click)="cancelSecretEdit()">
                    Discard changes
                  </button>
                </div>
              </div>

              <!-- Save button -->
              <div class="form-actions">
                <button mat-flat-button type="submit" class="save-btn"
                  [disabled]="credentialsForm!.get('client_id')!.invalid || savingCredentials">
                  <mat-spinner *ngIf="savingCredentials" diameter="16"></mat-spinner>
                  {{ savingCredentials ? 'Saving...' : 'Save Credentials' }}
                </button>
              </div>
            </form>

            <!-- Test Connection (D-08, D-09, D-10) -->
            <div class="test-connection-row">
              <button mat-stroked-button type="button"
                [disabled]="!hasCredentials || testingConnection"
                (click)="testConnection()">
                <mat-spinner *ngIf="testingConnection" diameter="16"></mat-spinner>
                <i *ngIf="!testingConnection" class="bi bi-plug"></i>
                {{ testingConnection ? 'Testing...' : 'Test Connection' }}
              </button>
              <div *ngIf="testResult" class="test-result"
                [class.test-success]="testResult.success"
                [class.test-failure]="!testResult.success">
                <i class="bi" [class.bi-check-circle]="testResult.success" [class.bi-x-circle]="!testResult.success"></i>
                <span>{{ testResult.message }}</span>
              </div>
            </div>
          </div>
        </ng-container>
      </section>

      <!-- B. Brainsuite Apps Section (EXISTING — preserved, with accordion additions) -->
      <section class="config-section">
        <div class="section-header">
          <div>
            <h2>Brainsuite Apps</h2>
            <p>Manage which Brainsuite apps are used to score your creative assets</p>
          </div>
          <button mat-flat-button class="add-btn" (click)="openAdd()">
            <i class="bi bi-plus-lg"></i> Add App
          </button>
        </div>

        <div *ngIf="!loading; else loadingTpl">
          <ng-container *ngFor="let app of apps">
            <div class="app-row">
              <div class="app-icon">
                <i class="bi bi-cpu"></i>
              </div>
              <div class="app-info">
                <span class="app-name">{{ app.name }}</span>
                <span class="app-type-badge" [class]="'type-' + app.app_type.toLowerCase()">{{ app.app_type }}</span>
                <span class="app-desc" *ngIf="app.description">{{ app.description }}</span>
              </div>
              <div class="app-defaults">
                <div class="default-flag" [class.active]="app.is_default_for_video">
                  <i class="bi bi-camera-video"></i> Default for Video
                </div>
                <div class="default-flag" [class.active]="app.is_default_for_image">
                  <i class="bi bi-image"></i> Default for Image
                </div>
              </div>
              <div class="app-actions">
                <button mat-icon-button (click)="editApp(app)"><i class="bi bi-pencil"></i></button>
                <button mat-icon-button (click)="deleteApp(app)"><i class="bi bi-trash"></i></button>
                <button mat-icon-button (click)="toggleAccordion(app)"
                  [attr.aria-label]="expandedAppId === app.id ? 'Collapse app name settings' : 'Expand app name settings'">
                  <i class="bi" [class.bi-chevron-down]="expandedAppId !== app.id"
                    [class.bi-chevron-up]="expandedAppId === app.id"
                    [class.chevron-expanded]="expandedAppId === app.id"></i>
                </button>
              </div>
            </div>

            <!-- Accordion panel (D-04) -->
            <div *ngIf="expandedAppId === app.id" class="accordion-panel">
              <mat-form-field appearance="outline" class="w-full">
                <mat-label>BrainSuite API App Name</mat-label>
                <input matInput [formControl]="getAppNameControl(app.id)" />
              </mat-form-field>
              <p class="accordion-helper">e.g. ACE_VIDEO_SMV_API — the app name parameter used in BrainSuite scoring API calls</p>
              <div class="form-actions">
                <button mat-flat-button class="save-btn"
                  [disabled]="savingAppName[app.id]"
                  (click)="saveSystemAppName(app)">
                  <mat-spinner *ngIf="savingAppName[app.id]" diameter="16"></mat-spinner>
                  {{ savingAppName[app.id] ? 'Saving...' : 'Save App Name' }}
                </button>
              </div>
            </div>
          </ng-container>

          <div *ngIf="apps.length === 0" class="empty-apps">
            <i class="bi bi-cpu"></i>
            <span>No Brainsuite apps configured</span>
            <p>Add a Brainsuite app to enable creative scoring</p>
          </div>
        </div>

        <ng-template #loadingTpl>
          <div class="loading-row"><mat-spinner diameter="24"></mat-spinner></div>
        </ng-template>
      </section>

      <!-- C. Add/Edit Form (EXISTING — preserved verbatim) -->
      <section class="config-section" *ngIf="showForm">
        <div class="section-header">
          <div>
            <h2>{{ editingApp ? 'Edit App' : 'Add Brainsuite App' }}</h2>
          </div>
          <button mat-icon-button (click)="cancelForm()"><i class="bi bi-x-lg"></i></button>
        </div>
        <div class="section-body">
          <form [formGroup]="appForm!" (ngSubmit)="saveApp()">
            <div class="form-row">
              <mat-form-field appearance="outline">
                <mat-label>App Name</mat-label>
                <input matInput formControlName="name" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>App Type</mat-label>
                <mat-select formControlName="app_type">
                  <mat-option value="VIDEO">Video</mat-option>
                  <mat-option value="IMAGE">Image / Static</mat-option>
                  <mat-option value="MIXED">Mixed</mat-option>
                </mat-select>
              </mat-form-field>
            </div>
            <div class="form-full">
              <mat-form-field appearance="outline" class="w-full">
                <mat-label>Description (optional)</mat-label>
                <input matInput formControlName="description" />
              </mat-form-field>
            </div>
            <div class="form-checkboxes">
              <mat-checkbox formControlName="is_default_for_video">Set as default for VIDEO assets</mat-checkbox>
              <mat-checkbox formControlName="is_default_for_image">Set as default for IMAGE/CAROUSEL assets</mat-checkbox>
            </div>
            <div class="api-note">
              <i class="bi bi-info-circle"></i>
              <div>
                <p><strong>Note:</strong> Brainsuite app API credentials are configured server-side via environment variables.</p>
                <p>Contact your Brainsuite representative to obtain your App ID and API key.</p>
              </div>
            </div>
            <div class="form-actions">
              <button mat-stroked-button type="button" (click)="cancelForm()">Cancel</button>
              <button mat-flat-button type="submit" class="save-btn" [disabled]="appForm!.invalid || saving">
                <mat-spinner *ngIf="saving" diameter="16"></mat-spinner>
                {{ saving ? 'Saving...' : (editingApp ? 'Update' : 'Create App') }}
              </button>
            </div>
          </form>
        </div>
      </section>

      <!-- D. Info section (EXISTING — preserved verbatim) -->
      <section class="config-section info-section">
        <div class="section-body">
          <div class="info-header">
            <i class="bi bi-question-circle"></i>
            <h3>About Brainsuite Apps</h3>
          </div>
          <p>
            Brainsuite apps are creative intelligence tools that analyze your ad creative and provide
            effectiveness scores including attention, brand recall, emotion, and visual impact.
          </p>
          <ul>
            <li>Each app is optimized for a specific creative format (video or image)</li>
            <li>Default apps are automatically applied to new creative assets of the matching format</li>
            <li>You can override the app assignment at the platform connection level</li>
            <li>ACE Scores and Brainsuite KPIs shown in the dashboard are currently simulated data</li>
          </ul>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .page-container { padding: 28px; display: flex; flex-direction: column; gap: 24px; max-width: 900px; }
    .config-section { background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
    .section-header {
      display: flex; align-items: flex-start; justify-content: space-between;
      padding: 20px 24px; border-bottom: 1px solid var(--border);
      h2 { font-size: 16px; font-weight: 600; margin: 0 0 4px; }
      p { font-size: 13px; color: var(--text-secondary); margin: 0; }
    }

    .add-btn { background: var(--accent) !important; color: white !important; }

    .app-row {
      display: flex; align-items: center; gap: 16px; padding: 16px 24px;
      border-bottom: 1px solid var(--border);
      &:last-child { border-bottom: none; }
      &:hover { background: var(--bg-secondary); }
    }

    .app-icon {
      width: 40px; height: 40px; border-radius: 10px; background: var(--accent-light);
      display: flex; align-items: center; justify-content: center;
      i.bi { color: var(--accent); font-size: 20px; }
    }

    .app-info { flex: 1; display: flex; flex-direction: column; gap: 3px; }
    .app-name { font-size: 15px; font-weight: 600; }

    .app-type-badge {
      display: inline-block; padding: 1px 7px; border-radius: 4px; font-size: 10px; font-weight: 600;
      text-transform: uppercase; align-self: flex-start;
      &.type-video { background: rgba(234,67,53,0.12); color: #EA4335; }
      &.type-image { background: rgba(52,168,83,0.12); color: #34A853; }
      &.type-mixed { background: rgba(66,133,244,0.12); color: var(--accent); }
    }

    .app-desc { font-size: 12px; color: var(--text-secondary); }

    .app-defaults { display: flex; flex-direction: column; gap: 4px; }

    .default-flag {
      display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--text-muted);
      i.bi { font-size: 13px; }
      &.active { color: #34A853; }
    }

    .app-actions { display: flex; gap: 4px; }

    .empty-apps {
      display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 48px;
      color: var(--text-muted);
      i.bi { font-size: 36px; opacity: 0.4; }
      span { font-size: 15px; font-weight: 500; }
      p { font-size: 13px; }
    }

    .loading-row { display: flex; justify-content: center; padding: 32px; }

    .section-body { padding: 24px; }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
    .form-full { margin-bottom: 16px; }
    .w-full { width: 100%; }
    .form-checkboxes { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
    .form-actions { display: flex; justify-content: flex-end; gap: 12px; }
    .save-btn { background: var(--accent) !important; color: white !important; display: flex; align-items: center; gap: 8px; }

    .api-note {
      display: flex; gap: 10px; padding: 14px; background: rgba(251,188,4,0.06);
      border: 1px solid rgba(251,188,4,0.3); border-radius: 8px; margin-bottom: 20px;
      i.bi { color: #F09300; flex-shrink: 0; margin-top: 2px; font-size: 18px; }
      p { font-size: 13px; color: var(--text-secondary); margin: 0 0 4px; &:last-child { margin: 0; } }
    }

    .info-section .section-body {
      p { font-size: 13px; color: var(--text-secondary); margin: 0 0 12px; }
      ul { padding-left: 20px; display: flex; flex-direction: column; gap: 6px;
        li { font-size: 13px; color: var(--text-secondary); } }
    }

    .info-header {
      display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
      i.bi { color: var(--text-secondary); font-size: 16px; }
      h3 { font-size: 14px; font-weight: 600; margin: 0; }
    }

    /* Phase 12: Credentials section */
    .credentials-summary {
      display: flex; align-items: center; gap: 12px; padding: 12px 24px;
    }
    .credentials-summary .summary-icon { color: var(--success); font-size: 18px; }
    .credentials-summary span { flex: 1; font-size: 13px; color: var(--text-secondary); }
    .edit-credentials-btn { font-size: 13px; color: var(--accent) !important; }

    .secret-field-row { display: flex; align-items: flex-start; gap: 12px; }
    .secret-input { flex: 1; }
    .change-secret-btn { font-size: 12px; margin-top: 8px; }

    .test-connection-row { margin-top: 20px; display: flex; flex-direction: column; gap: 12px; }
    .test-connection-row button { align-self: flex-start; display: flex; align-items: center; gap: 8px; }

    .test-result {
      display: flex; align-items: center; gap: 8px; padding: 12px 16px;
      border-radius: 8px; font-size: 13px;
    }
    .test-success { background: rgba(46,204,113,0.15); color: var(--success); }
    .test-failure { background: rgba(231,76,60,0.15); color: var(--error); }

    /* Phase 12: Accordion */
    .accordion-panel {
      padding: 16px 24px; background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
    }
    .accordion-helper { font-size: 12px; color: var(--text-muted); margin: -8px 0 16px; }
    .chevron-expanded { color: var(--accent) !important; }
  `],
})
export class BrainsuiteAppsComponent implements OnInit {
  // Existing state
  apps: BrainsuiteApp[] = [];
  loading = true;
  saving = false;
  showForm = false;
  editingApp: BrainsuiteApp | null = null;
  appForm?: FormGroup;

  // Credentials section state (Phase 12)
  credentials: { client_id: string | null; has_secret: boolean; has_scored_assets: boolean } | null = null;
  credentialsForm?: FormGroup;
  credentialsCollapsed = false;
  secretEditMode = false;
  savingCredentials = false;
  testingConnection = false;
  testResult: { success: boolean; message: string } | null = null;

  // Accordion state (Phase 12)
  expandedAppId: string | null = null;
  appNameForms: Record<string, FormGroup> = {};
  savingAppName: Record<string, boolean> = {};

  constructor(
    private api: ApiService,
    private fb: FormBuilder,
    private snackBar: MatSnackBar,
    private dialog: MatDialog,
  ) {}

  ngOnInit(): void {
    this.loadApps();
    this.loadCredentials();
  }

  // --- Existing methods (preserved) ---

  loadApps(): void {
    this.api.get<BrainsuiteApp[]>('/platforms/brainsuite-apps').subscribe({
      next: (apps) => { this.apps = apps; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  openAdd(): void {
    this.editingApp = null;
    this.appForm = this.fb.group({
      name: ['', Validators.required],
      app_type: ['VIDEO', Validators.required],
      description: [''],
      is_default_for_video: [false],
      is_default_for_image: [false],
    });
    this.showForm = true;
  }

  editApp(app: BrainsuiteApp): void {
    this.editingApp = app;
    this.appForm = this.fb.group({
      name: [app.name, Validators.required],
      app_type: [app.app_type, Validators.required],
      description: [app.description || ''],
      is_default_for_video: [app.is_default_for_video],
      is_default_for_image: [app.is_default_for_image],
    });
    this.showForm = true;
  }

  saveApp(): void {
    if (this.appForm?.invalid) return;
    this.saving = true;
    const payload = this.appForm!.value;

    const req = this.editingApp
      ? this.api.patch(`/platforms/brainsuite-apps/${this.editingApp.id}`, payload)
      : this.api.post('/platforms/brainsuite-apps', payload);

    req.subscribe({
      next: () => {
        this.saving = false;
        this.showForm = false;
        this.editingApp = null;
        this.loadApps();
        this.snackBar.open(`App ${this.editingApp ? 'updated' : 'created'}`, '', { duration: 2000 });
      },
      error: () => { this.saving = false; },
    });
  }

  cancelForm(): void {
    this.showForm = false;
    this.editingApp = null;
  }

  deleteApp(app: BrainsuiteApp): void {
    if (!confirm(`Delete "${app.name}"?`)) return;
    this.api.delete(`/platforms/brainsuite-apps/${app.id}`).subscribe({
      next: () => {
        this.apps = this.apps.filter(a => a.id !== app.id);
        this.snackBar.open('App deleted', '', { duration: 2000 });
      },
    });
  }

  // --- Credentials section methods ---

  loadCredentials(): void {
    this.api.get<{ client_id: string | null; has_secret: boolean; has_scored_assets: boolean }>('/brainsuite-config/credentials').subscribe({
      next: (data) => {
        this.credentials = data;
        const hasCredentials = !!data.client_id && data.has_secret;
        // Restore collapsed state from localStorage if credentials exist
        if (hasCredentials) {
          const saved = localStorage.getItem('bs_credentials_collapsed');
          if (saved === 'true') {
            this.credentialsCollapsed = true;
          }
        }
        this.initCredentialsForm();
      },
      error: () => {
        this.credentials = { client_id: null, has_secret: false, has_scored_assets: false };
        this.initCredentialsForm();
      },
    });
  }

  initCredentialsForm(): void {
    this.credentialsForm = this.fb.group({
      client_id: [this.credentials?.client_id || '', Validators.required],
      client_secret: [''],
    });
    this.secretEditMode = false;
  }

  get hasCredentials(): boolean {
    return !!this.credentials?.client_id && !!this.credentials?.has_secret;
  }

  expandCredentials(): void {
    this.credentialsCollapsed = false;
    localStorage.removeItem('bs_credentials_collapsed');
  }

  enableSecretEdit(): void {
    this.secretEditMode = true;
    this.credentialsForm?.get('client_secret')?.setValue('');
  }

  cancelSecretEdit(): void {
    this.secretEditMode = false;
    this.credentialsForm?.get('client_secret')?.setValue('');
  }

  saveCredentials(): void {
    if (this.credentialsForm?.invalid) return;
    this.savingCredentials = true;
    const payload = this.credentialsForm!.value;
    this.api.put<{ changed: boolean; has_scored_assets: boolean }>('/brainsuite-config/credentials', payload).subscribe({
      next: (resp) => {
        this.savingCredentials = false;
        this.snackBar.open('Credentials saved', '', { duration: 3000 });
        this.loadCredentials();
        if (resp.changed && resp.has_scored_assets) {
          this.openRescoreDialog();
        }
      },
      error: () => { this.savingCredentials = false; },
    });
  }

  // --- Test Connection methods ---

  testConnection(): void {
    this.testingConnection = true;
    this.testResult = null;
    this.api.post<{ success: boolean; message: string }>('/brainsuite-config/test-connection', {}).subscribe({
      next: (result) => {
        this.testingConnection = false;
        this.testResult = result;
        if (result.success && this.hasCredentials) {
          this.credentialsCollapsed = true;
          localStorage.setItem('bs_credentials_collapsed', 'true');
        }
      },
      error: () => {
        this.testingConnection = false;
        this.testResult = { success: false, message: 'Could not reach BrainSuite — check your network connection' };
      },
    });
  }

  // --- Accordion methods ---

  toggleAccordion(app: BrainsuiteApp): void {
    if (this.expandedAppId === app.id) {
      this.expandedAppId = null;
    } else {
      this.expandedAppId = app.id;
      if (!this.appNameForms[app.id]) {
        this.appNameForms[app.id] = this.fb.group({
          system_app_name: [app.system_app_name || ''],
        });
      }
    }
  }

  getAppNameControl(appId: string): FormControl {
    return this.appNameForms[appId]?.get('system_app_name') as FormControl;
  }

  saveSystemAppName(app: BrainsuiteApp): void {
    const form = this.appNameForms[app.id];
    if (!form) return;
    this.savingAppName[app.id] = true;
    this.api.patch<{ changed: boolean; has_scored_assets: boolean }>(
      `/brainsuite-config/apps/${app.id}/system-app-name`,
      form.value,
    ).subscribe({
      next: (resp) => {
        this.savingAppName[app.id] = false;
        app.system_app_name = form.value.system_app_name;
        this.expandedAppId = null;
        this.snackBar.open('App name saved', '', { duration: 3000 });
        if (resp.changed && resp.has_scored_assets) {
          this.openRescoreDialog();
        }
      },
      error: () => { this.savingAppName[app.id] = false; },
    });
  }

  onClickAway(event: Event): void {
    if (this.expandedAppId) {
      const target = event.target as HTMLElement;
      if (!target.closest('.app-row') && !target.closest('.accordion-panel')) {
        this.expandedAppId = null;
      }
    }
  }

  // --- Re-score dialog ---

  openRescoreDialog(): void {
    const ref = this.dialog.open(RescoreDialogComponent, {
      width: '480px',
      maxWidth: '480px',
    });
    ref.afterClosed().subscribe((action: string) => {
      if (action === 'rescore') {
        this.api.post('/brainsuite-config/rescore-all', {}).subscribe({
          next: () => {
            this.snackBar.open('Assets queued for re-scoring', '', { duration: 4000 });
          },
        });
      }
    });
  }
}
