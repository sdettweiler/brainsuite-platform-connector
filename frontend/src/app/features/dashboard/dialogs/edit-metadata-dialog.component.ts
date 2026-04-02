import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../../core/services/api.service';

interface MetadataField {
  id: string;
  name: string;
  label: string;
  field_type: 'SELECT' | 'TEXT' | 'NUMBER';
  is_required: boolean;
  default_value?: string | null;
  allowed_values?: { id: string; value: string; label: string }[];
  field_values?: { id: string; value: string; label: string }[];
}

interface EditMetadataDialogData {
  assetIds: string[];
  singleAssetName?: string;
  existingValues?: Record<string, string>;
}

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatDialogModule, MatButtonModule,
    MatInputModule, MatFormFieldModule, MatSelectModule, MatProgressSpinnerModule,
  ],
  template: `
    <div class="meta-dialog">
      <div class="dialog-header">
        <h2>Edit Metadata</h2>
        <button mat-icon-button (click)="close()"><i class="bi bi-x-lg"></i></button>
      </div>

      <div class="dialog-body">
        <p class="subtitle" *ngIf="data.assetIds.length > 1">
          <i class="bi bi-info-circle"></i>
          Editing {{ data.assetIds.length }} assets. Blank fields will not be changed.
        </p>
        <p class="subtitle single" *ngIf="data.assetIds.length === 1 && data.singleAssetName">
          {{ data.singleAssetName }}
        </p>

        <div *ngIf="loading" class="loading-state">
          <mat-spinner diameter="28"></mat-spinner>
        </div>

        <div *ngIf="!loading" class="fields-grid">
          <div *ngFor="let field of metadataFields" class="field-row">
            <label class="field-label">
              {{ field.label }}
              <span class="required-mark" *ngIf="field.is_required">*</span>
            </label>

            <mat-form-field appearance="outline" class="field-input compact-select" *ngIf="field.field_type === 'SELECT'">
              <mat-select [(ngModel)]="values[field.id]" [placeholder]="data.assetIds.length > 1 ? 'Leave blank to keep existing' : ''">
                <mat-option value="">-- Clear --</mat-option>
                <mat-option *ngFor="let opt of field.field_values" [value]="opt.value">
                  {{ opt.label }}
                </mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline" class="field-input" *ngIf="field.field_type === 'TEXT'">
              <input
                matInput
                [(ngModel)]="values[field.id]"
                [placeholder]="data.assetIds.length > 1 ? 'Leave blank to keep existing' : ''"
              />
            </mat-form-field>

            <mat-form-field appearance="outline" class="field-input" *ngIf="field.field_type === 'NUMBER'">
              <input
                matInput
                type="number"
                [(ngModel)]="values[field.id]"
                [placeholder]="data.assetIds.length > 1 ? 'Leave blank to keep existing' : ''"
              />
            </mat-form-field>
          </div>

          <div *ngIf="metadataFields.length === 0" class="empty-fields">
            <i class="bi bi-sliders"></i>
            <span>No metadata fields configured.</span>
            <span>Set them up in Configuration &rarr; Metadata.</span>
          </div>
        </div>
      </div>

      <div class="dialog-footer">
        <button mat-stroked-button (click)="close()">Cancel</button>
        <button
          mat-flat-button
          class="save-btn"
          [disabled]="saving || loading || metadataFields.length === 0"
          (click)="save()"
        >
          <mat-spinner *ngIf="saving" diameter="16"></mat-spinner>
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </div>
  `,
  styles: [`
    .meta-dialog { display: flex; flex-direction: column; }

    .dialog-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 20px 24px 16px; border-bottom: 1px solid var(--border);
      h2 { font-size: 18px; font-weight: 600; margin: 0; }
    }

    .dialog-body { padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; min-height: 200px; }

    .subtitle {
      display: flex; align-items: center; gap: 6px; margin: 0;
      font-size: 13px; color: var(--text-secondary);
      i.bi { font-size: 14px; }
      &.single { font-weight: 500; color: var(--text-primary); }
    }

    .loading-state { display: flex; justify-content: center; padding: 40px; }

    .fields-grid { display: flex; flex-direction: column; gap: 12px; }

    .field-row { display: flex; flex-direction: column; gap: 4px; }

    .field-label {
      font-size: 12px; font-weight: 500; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.4px;
    }

    .required-mark { color: var(--error); margin-left: 2px; }

    .field-input { width: 100%; }

    .empty-fields {
      display: flex; flex-direction: column; align-items: center; gap: 8px;
      padding: 40px; color: var(--text-muted); text-align: center;
      i.bi { font-size: 32px; opacity: 0.4; }
      span { font-size: 13px; }
    }

    .dialog-footer {
      display: flex; justify-content: flex-end; gap: 12px;
      padding: 16px 24px; border-top: 1px solid var(--border);
    }

    .save-btn {
      background: var(--accent) !important; color: white !important;
      display: flex; align-items: center; gap: 8px;
    }
  `],
})
export class EditMetadataDialogComponent implements OnInit {
  metadataFields: MetadataField[] = [];
  values: Record<string, string> = {};
  loading = true;
  saving = false;

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: EditMetadataDialogData,
    private dialogRef: MatDialogRef<EditMetadataDialogComponent>,
    private api: ApiService,
  ) {}

  ngOnInit(): void {
    this.api.get<MetadataField[]>('/assets/metadata/fields').subscribe({
      next: (fields) => {
        // Normalise allowed_values → field_values so the template works
        this.metadataFields = fields.map(f => ({
          ...f,
          field_values: f.allowed_values ?? f.field_values ?? [],
        }));
        // Start from existing asset values (keyed by field UUID)
        this.values = this.data.existingValues ? { ...this.data.existingValues } : {};
        // Fall back to default_value for any field not yet set on this asset
        for (const field of this.metadataFields) {
          if (!this.values[field.id] && field.default_value) {
            this.values[field.id] = field.default_value;
          }
        }
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  save(): void {
    this.saving = true;
    // Filter out blank values for bulk edit
    const payload: Record<string, string> = {};
    for (const [k, v] of Object.entries(this.values)) {
      if (v !== null && v !== undefined && v !== '') {
        payload[k] = String(v);
      }
    }

    const endpoint = this.data.assetIds.length === 1
      ? `/assets/${this.data.assetIds[0]}/metadata`
      : '/assets/bulk-metadata';

    const body = this.data.assetIds.length === 1
      ? { metadata: payload }
      : { asset_ids: this.data.assetIds, metadata: payload };

    this.api.patch(endpoint, body).subscribe({
      next: () => { this.dialogRef.close({ saved: true }); },
      error: () => { this.saving = false; },
    });
  }

  close(): void {
    this.dialogRef.close();
  }
}
