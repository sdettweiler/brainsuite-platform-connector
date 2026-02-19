import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../../core/services/api.service';

interface Project {
  id: string;
  name: string;
  asset_count?: number;
}

interface AssignProjectDialogData {
  assetIds: string[];
}

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatDialogModule, MatButtonModule,
    MatIconModule, MatInputModule, MatFormFieldModule, MatProgressSpinnerModule,
  ],
  template: `
    <div class="assign-dialog">
      <div class="dialog-header">
        <h2>Assign to Project</h2>
        <button mat-icon-button (click)="close()"><mat-icon>close</mat-icon></button>
      </div>

      <div class="dialog-body">
        <p class="subtitle">
          Assigning {{ data.assetIds.length }} asset{{ data.assetIds.length !== 1 ? 's' : '' }} to a project
        </p>

        <!-- Create New Project -->
        <div class="create-section">
          <div class="create-header" (click)="showCreate = !showCreate">
            <mat-icon>add_circle_outline</mat-icon>
            <span>Create new project</span>
            <mat-icon class="chevron" [class.open]="showCreate">expand_more</mat-icon>
          </div>
          <div class="create-form" *ngIf="showCreate">
            <mat-form-field appearance="outline" class="w-full">
              <mat-label>Project name</mat-label>
              <input matInput [(ngModel)]="newProjectName" (keyup.enter)="createAndAssign()" />
            </mat-form-field>
            <button
              mat-flat-button
              class="create-btn"
              [disabled]="!newProjectName.trim() || creating"
              (click)="createAndAssign()"
            >
              <mat-spinner *ngIf="creating" diameter="14"></mat-spinner>
              {{ creating ? 'Creating...' : 'Create & Assign' }}
            </button>
          </div>
        </div>

        <div class="divider"><span>or select existing</span></div>

        <!-- Existing Projects -->
        <div class="projects-list" *ngIf="!loading; else loadingTpl">
          <div
            *ngFor="let p of projects"
            class="project-row"
            [class.selected]="selectedProjectId === p.id"
            (click)="selectedProjectId = p.id"
          >
            <div class="project-radio">
              <div class="radio-dot" [class.active]="selectedProjectId === p.id"></div>
            </div>
            <div class="project-info">
              <span class="project-name">{{ p.name }}</span>
              <span class="project-count">{{ p.asset_count || 0 }} assets</span>
            </div>
          </div>
          <div *ngIf="projects.length === 0" class="empty-projects">
            <mat-icon>folder_open</mat-icon>
            <span>No projects yet</span>
          </div>
        </div>
        <ng-template #loadingTpl>
          <div class="loading-projects">
            <mat-spinner diameter="24"></mat-spinner>
          </div>
        </ng-template>
      </div>

      <div class="dialog-footer">
        <button mat-stroked-button (click)="close()">Cancel</button>
        <button
          mat-flat-button
          class="assign-btn"
          [disabled]="!selectedProjectId || assigning"
          (click)="assign()"
        >
          <mat-spinner *ngIf="assigning" diameter="16"></mat-spinner>
          {{ assigning ? 'Assigning...' : 'Assign' }}
        </button>
      </div>
    </div>
  `,
  styles: [`
    .assign-dialog { display: flex; flex-direction: column; }

    .dialog-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 20px 24px 16px; border-bottom: 1px solid var(--border);
      h2 { font-size: 18px; font-weight: 600; margin: 0; }
    }

    .dialog-body { padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }

    .subtitle { font-size: 13px; color: var(--text-secondary); margin: 0; }

    .create-section {
      border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
    }

    .create-header {
      display: flex; align-items: center; gap: 8px; padding: 12px 16px;
      cursor: pointer; background: var(--bg-secondary);
      mat-icon { font-size: 18px; color: var(--accent); }
      span { flex: 1; font-size: 14px; font-weight: 500; }
      .chevron { color: var(--text-muted); transition: transform 0.2s; &.open { transform: rotate(180deg); } }
    }

    .create-form {
      padding: 16px; display: flex; flex-direction: column; gap: 12px;
      border-top: 1px solid var(--border);
    }

    .w-full { width: 100%; }

    .create-btn {
      align-self: flex-end; background: var(--accent) !important; color: white !important;
      display: flex; align-items: center; gap: 8px;
    }

    .divider {
      display: flex; align-items: center; gap: 12px;
      span { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
      &::before, &::after { content: ''; flex: 1; height: 1px; background: var(--border); }
    }

    .projects-list { display: flex; flex-direction: column; gap: 4px; max-height: 240px; overflow-y: auto; }

    .project-row {
      display: flex; align-items: center; gap: 12px; padding: 10px 12px;
      border: 1px solid transparent; border-radius: 6px; cursor: pointer; transition: all 0.1s;
      &:hover { background: var(--bg-secondary); }
      &.selected { border-color: var(--accent); background: rgba(66,133,244,0.08); }
    }

    .radio-dot {
      width: 16px; height: 16px; border-radius: 50%; border: 2px solid var(--border);
      transition: all 0.15s; flex-shrink: 0;
      &.active { border-color: var(--accent); background: var(--accent); box-shadow: 0 0 0 3px rgba(66,133,244,0.2); }
    }

    .project-info { display: flex; flex-direction: column; gap: 2px; }
    .project-name { font-size: 14px; font-weight: 500; }
    .project-count { font-size: 12px; color: var(--text-secondary); }

    .empty-projects {
      display: flex; flex-direction: column; align-items: center; gap: 8px;
      padding: 32px; color: var(--text-muted); font-size: 13px;
      mat-icon { font-size: 28px; opacity: 0.4; }
    }

    .loading-projects { display: flex; justify-content: center; padding: 24px; }

    .dialog-footer {
      display: flex; justify-content: flex-end; gap: 12px;
      padding: 16px 24px; border-top: 1px solid var(--border);
    }

    .assign-btn {
      background: var(--accent) !important; color: white !important;
      display: flex; align-items: center; gap: 8px;
    }
  `],
})
export class AssignProjectDialogComponent implements OnInit {
  projects: Project[] = [];
  selectedProjectId: string | null = null;
  loading = true;
  assigning = false;
  creating = false;
  showCreate = false;
  newProjectName = '';

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: AssignProjectDialogData,
    private dialogRef: MatDialogRef<AssignProjectDialogComponent>,
    private api: ApiService,
  ) {}

  ngOnInit(): void {
    this.api.get<Project[]>('/assets/projects').subscribe({
      next: (projects) => { this.projects = projects; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  async createAndAssign(): Promise<void> {
    if (!this.newProjectName.trim()) return;
    this.creating = true;
    this.api.post<Project>('/assets/projects', { name: this.newProjectName.trim() }).subscribe({
      next: (project) => {
        this.selectedProjectId = project.id;
        this.creating = false;
        this.assign();
      },
      error: () => { this.creating = false; },
    });
  }

  assign(): void {
    if (!this.selectedProjectId) return;
    this.assigning = true;
    this.api.post(`/assets/projects/${this.selectedProjectId}/assets`, { asset_ids: this.data.assetIds }).subscribe({
      next: () => { this.dialogRef.close({ assigned: true, projectId: this.selectedProjectId }); },
      error: () => { this.assigning = false; },
    });
  }

  close(): void {
    this.dialogRef.close();
  }
}
