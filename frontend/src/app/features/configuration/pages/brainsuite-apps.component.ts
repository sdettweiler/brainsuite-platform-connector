import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../../core/services/api.service';

interface BrainsuiteApp {
  id: string;
  name: string;
  app_type: 'VIDEO' | 'IMAGE' | 'MIXED';
  is_default_for_video: boolean;
  is_default_for_image: boolean;
  description?: string;
}

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule, ReactiveFormsModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule, MatCheckboxModule,
    MatProgressSpinnerModule, MatSnackBarModule,
  ],
  template: `
    <div class="page-container">
      <section class="config-section">
        <div class="section-header">
          <div>
            <h2>Brainsuite Apps</h2>
            <p>Manage which Brainsuite apps are used to score your creative assets</p>
          </div>
          <button mat-flat-button class="add-btn" (click)="openAdd()">
            <mat-icon>add</mat-icon> Add App
          </button>
        </div>

        <div *ngIf="!loading; else loadingTpl">
          <div *ngFor="let app of apps" class="app-row">
            <div class="app-icon">
              <mat-icon>psychology</mat-icon>
            </div>
            <div class="app-info">
              <span class="app-name">{{ app.name }}</span>
              <span class="app-type-badge" [class]="'type-' + app.app_type.toLowerCase()">{{ app.app_type }}</span>
              <span class="app-desc" *ngIf="app.description">{{ app.description }}</span>
            </div>
            <div class="app-defaults">
              <div class="default-flag" [class.active]="app.is_default_for_video">
                <mat-icon>videocam</mat-icon> Default for Video
              </div>
              <div class="default-flag" [class.active]="app.is_default_for_image">
                <mat-icon>image</mat-icon> Default for Image
              </div>
            </div>
            <div class="app-actions">
              <button mat-icon-button (click)="editApp(app)"><mat-icon>edit</mat-icon></button>
              <button mat-icon-button (click)="deleteApp(app)"><mat-icon>delete_outline</mat-icon></button>
            </div>
          </div>

          <div *ngIf="apps.length === 0" class="empty-apps">
            <mat-icon>psychology</mat-icon>
            <span>No Brainsuite apps configured</span>
            <p>Add a Brainsuite app to enable creative scoring</p>
          </div>
        </div>

        <ng-template #loadingTpl>
          <div class="loading-row"><mat-spinner diameter="24"></mat-spinner></div>
        </ng-template>
      </section>

      <!-- Add/Edit Form -->
      <section class="config-section" *ngIf="showForm">
        <div class="section-header">
          <div>
            <h2>{{ editingApp ? 'Edit App' : 'Add Brainsuite App' }}</h2>
          </div>
          <button mat-icon-button (click)="cancelForm()"><mat-icon>close</mat-icon></button>
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
              <mat-icon>info_outline</mat-icon>
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

      <!-- Info section -->
      <section class="config-section info-section">
        <div class="section-body">
          <div class="info-header">
            <mat-icon>help_outline</mat-icon>
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
      width: 40px; height: 40px; border-radius: 10px; background: rgba(66,133,244,0.1);
      display: flex; align-items: center; justify-content: center;
      mat-icon { color: var(--accent); }
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
      mat-icon { font-size: 14px; }
      &.active { color: #34A853; }
    }

    .app-actions { display: flex; gap: 4px; }

    .empty-apps {
      display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 48px;
      color: var(--text-muted);
      mat-icon { font-size: 36px; opacity: 0.4; }
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
      mat-icon { color: #F09300; flex-shrink: 0; margin-top: 2px; }
      p { font-size: 13px; color: var(--text-secondary); margin: 0 0 4px; &:last-child { margin: 0; } }
    }

    .info-section .section-body {
      p { font-size: 13px; color: var(--text-secondary); margin: 0 0 12px; }
      ul { padding-left: 20px; display: flex; flex-direction: column; gap: 6px;
        li { font-size: 13px; color: var(--text-secondary); } }
    }

    .info-header {
      display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
      mat-icon { color: var(--text-secondary); }
      h3 { font-size: 14px; font-weight: 600; margin: 0; }
    }
  `],
})
export class BrainsuiteAppsComponent implements OnInit {
  apps: BrainsuiteApp[] = [];
  loading = true;
  saving = false;
  showForm = false;
  editingApp: BrainsuiteApp | null = null;
  appForm?: FormGroup;

  constructor(
    private api: ApiService,
    private fb: FormBuilder,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.loadApps();
  }

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
}
