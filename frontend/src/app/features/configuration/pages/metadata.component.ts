import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators, FormArray } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { ApiService } from '../../../core/services/api.service';

interface MetadataField {
  id: string;
  name: string;
  label: string;
  field_type: 'SELECT' | 'TEXT' | 'NUMBER';
  is_required: boolean;
  default_value?: string;
  sort_order: number;
  field_values?: Array<{ id: string; value: string; label: string; sort_order: number }>;
}

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule, ReactiveFormsModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule, MatCheckboxModule,
    MatProgressSpinnerModule, MatSnackBarModule, DragDropModule,
  ],
  template: `
    <div class="page-container">
      <section class="config-section">
        <div class="section-header">
          <div>
            <h2>Metadata Fields</h2>
            <p>Define custom fields to label and organize your creative assets</p>
          </div>
          <button mat-flat-button class="add-btn" (click)="openAddField()">
            <mat-icon>add</mat-icon> Add Field
          </button>
        </div>

        <!-- Field list -->
        <div *ngIf="!loading; else loadingTpl">
          <div
            cdkDropList
            [cdkDropListData]="fields"
            (cdkDropListDropped)="onDrop($event)"
            class="fields-list"
          >
            <div
              *ngFor="let field of fields; let i = index"
              cdkDrag
              class="field-row"
              [class.expanded]="expandedId === field.id"
            >
              <div class="field-header" (click)="toggleExpand(field.id)">
                <mat-icon cdkDragHandle class="drag-handle">drag_indicator</mat-icon>
                <div class="field-type-badge" [class]="'type-' + field.field_type.toLowerCase()">
                  {{ field.field_type }}
                </div>
                <div class="field-main">
                  <span class="field-label">{{ field.label }}</span>
                  <span class="field-name">{{ field.name }}</span>
                </div>
                <div class="field-flags">
                  <span class="required-flag" *ngIf="field.is_required">Required</span>
                  <span class="values-count" *ngIf="field.field_type === 'SELECT'">
                    {{ field.field_values?.length || 0 }} options
                  </span>
                </div>
                <div class="field-actions">
                  <button mat-icon-button (click)="editField(field, $event)">
                    <mat-icon>edit</mat-icon>
                  </button>
                  <button mat-icon-button (click)="deleteField(field, $event)">
                    <mat-icon>delete_outline</mat-icon>
                  </button>
                  <mat-icon class="expand-icon">{{ expandedId === field.id ? 'expand_less' : 'expand_more' }}</mat-icon>
                </div>
              </div>

              <!-- Expanded: SELECT options -->
              <div *ngIf="expandedId === field.id && field.field_type === 'SELECT'" class="field-options">
                <div class="options-header">
                  <span>Options</span>
                  <button mat-stroked-button class="add-option-btn" (click)="addOption(field)">
                    <mat-icon>add</mat-icon> Add Option
                  </button>
                </div>
                <div
                  cdkDropList
                  [cdkDropListData]="field.field_values"
                  (cdkDropListDropped)="onOptionDrop($event, field)"
                  class="options-list"
                >
                  <div *ngFor="let opt of field.field_values; let j = index" cdkDrag class="option-row">
                    <mat-icon cdkDragHandle class="drag-handle-sm">drag_indicator</mat-icon>
                    <input [(ngModel)]="opt.label" class="option-label-input" placeholder="Label" />
                    <input [(ngModel)]="opt.value" class="option-value-input" placeholder="Value (slug)" />
                    <button mat-icon-button (click)="removeOption(field, j)">
                      <mat-icon>close</mat-icon>
                    </button>
                  </div>
                  <div *ngIf="!field.field_values?.length" class="no-options">No options yet</div>
                </div>
                <div class="options-footer">
                  <button mat-flat-button class="save-options-btn" (click)="saveFieldValues(field)">
                    Save Options
                  </button>
                </div>
              </div>
            </div>

            <div *ngIf="fields.length === 0" class="empty-fields">
              <mat-icon>tune</mat-icon>
              <span>No metadata fields yet. Add your first field.</span>
            </div>
          </div>
        </div>

        <ng-template #loadingTpl>
          <div class="loading-row"><mat-spinner diameter="24"></mat-spinner></div>
        </ng-template>
      </section>

      <!-- Add/Edit Field Form -->
      <section class="config-section" *ngIf="showForm">
        <div class="section-header">
          <div>
            <h2>{{ editingField ? 'Edit Field' : 'New Metadata Field' }}</h2>
          </div>
          <button mat-icon-button (click)="cancelForm()"><mat-icon>close</mat-icon></button>
        </div>
        <div class="section-body" *ngIf="fieldForm">
          <form [formGroup]="fieldForm" (ngSubmit)="saveField()">
            <div class="form-row">
              <mat-form-field appearance="outline">
                <mat-label>Label (Display Name)</mat-label>
                <input matInput formControlName="label" (input)="autoFillName()" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Name (Slug)</mat-label>
                <input matInput formControlName="name" />
                <mat-hint>Lowercase, underscores only</mat-hint>
              </mat-form-field>
            </div>
            <div class="form-row">
              <mat-form-field appearance="outline">
                <mat-label>Field Type</mat-label>
                <mat-select formControlName="field_type">
                  <mat-option value="SELECT">Select (dropdown)</mat-option>
                  <mat-option value="TEXT">Text (free input)</mat-option>
                  <mat-option value="NUMBER">Number</mat-option>
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Default Value</mat-label>
                <input matInput formControlName="default_value" />
              </mat-form-field>
            </div>
            <div class="form-checkbox">
              <mat-checkbox formControlName="is_required">Required field</mat-checkbox>
            </div>
            <div class="form-actions">
              <button mat-stroked-button type="button" (click)="cancelForm()">Cancel</button>
              <button mat-flat-button type="submit" class="save-btn" [disabled]="fieldForm.invalid || saving">
                <mat-spinner *ngIf="saving" diameter="16"></mat-spinner>
                {{ saving ? 'Saving...' : (editingField ? 'Update' : 'Create Field') }}
              </button>
            </div>
          </form>
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

    .fields-list { }

    .field-row { border-bottom: 1px solid var(--border); &:last-child { border-bottom: none; } }

    .field-header {
      display: flex; align-items: center; gap: 12px; padding: 14px 20px;
      cursor: pointer; transition: background 0.1s;
      &:hover { background: var(--bg-secondary); }
    }

    .drag-handle { color: var(--text-muted); cursor: grab; font-size: 18px; }

    .field-type-badge {
      padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; text-transform: uppercase;
      &.type-select { background: rgba(66,133,244,0.15); color: var(--accent); }
      &.type-text { background: rgba(52,168,83,0.15); color: #34A853; }
      &.type-number { background: rgba(251,188,4,0.15); color: #F09300; }
    }

    .field-main { flex: 1; }
    .field-label { font-size: 14px; font-weight: 500; display: block; }
    .field-name { font-size: 11px; color: var(--text-muted); font-family: monospace; }

    .field-flags { display: flex; gap: 8px; align-items: center; }
    .required-flag { font-size: 11px; color: var(--error); background: rgba(234,67,53,0.1); padding: 2px 6px; border-radius: 4px; }
    .values-count { font-size: 11px; color: var(--text-secondary); }

    .field-actions { display: flex; align-items: center; gap: 4px; }
    .expand-icon { color: var(--text-muted); }

    /* Options */
    .field-options { border-top: 1px solid var(--border); padding: 16px 20px; background: var(--bg-secondary); }

    .options-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;
      span { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; color: var(--text-secondary); }
    }

    .add-option-btn { font-size: 12px; }

    .options-list { display: flex; flex-direction: column; gap: 6px; }

    .option-row {
      display: flex; align-items: center; gap: 8px; padding: 6px 8px;
      background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px;
    }

    .drag-handle-sm { font-size: 16px; color: var(--text-muted); cursor: grab; }

    .option-label-input, .option-value-input {
      flex: 1; padding: 4px 8px; background: none; border: 1px solid var(--border);
      border-radius: 4px; color: var(--text-primary); font-size: 13px;
      &:focus { outline: none; border-color: var(--accent); }
    }

    .no-options { font-size: 13px; color: var(--text-muted); text-align: center; padding: 12px; }

    .options-footer { margin-top: 12px; display: flex; justify-content: flex-end; }
    .save-options-btn { background: var(--accent) !important; color: white !important; }

    .empty-fields {
      display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 48px;
      color: var(--text-muted);
      mat-icon { font-size: 32px; opacity: 0.4; }
      span { font-size: 14px; }
    }

    .loading-row { display: flex; justify-content: center; padding: 32px; }

    .section-body { padding: 24px; }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
    .form-checkbox { margin-bottom: 16px; }
    .form-actions { display: flex; justify-content: flex-end; gap: 12px; }
    .save-btn { background: var(--accent) !important; color: white !important; display: flex; align-items: center; gap: 8px; }
  `],
})
export class MetadataComponent implements OnInit {
  fields: MetadataField[] = [];
  loading = true;
  saving = false;
  showForm = false;
  editingField: MetadataField | null = null;
  expandedId: string | null = null;
  fieldForm!: FormGroup;

  constructor(
    private api: ApiService,
    private fb: FormBuilder,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.loadFields();
  }

  loadFields(): void {
    this.api.get<MetadataField[]>('/assets/metadata/fields').subscribe({
      next: (fields) => { this.fields = fields; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  openAddField(): void {
    this.editingField = null;
    this.fieldForm = this.fb.group({
      label: ['', Validators.required],
      name: ['', [Validators.required, Validators.pattern(/^[a-z0-9_]+$/)]],
      field_type: ['SELECT', Validators.required],
      is_required: [false],
      default_value: [''],
    });
    this.showForm = true;
  }

  editField(field: MetadataField, event: Event): void {
    event.stopPropagation();
    this.editingField = field;
    this.fieldForm = this.fb.group({
      label: [field.label, Validators.required],
      name: [field.name, [Validators.required, Validators.pattern(/^[a-z0-9_]+$/)]],
      field_type: [field.field_type, Validators.required],
      is_required: [field.is_required],
      default_value: [field.default_value || ''],
    });
    this.showForm = true;
  }

  autoFillName(): void {
    if (this.editingField) return;
    const label: string = this.fieldForm.get('label')?.value || '';
    const name = label.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
    this.fieldForm.patchValue({ name }, { emitEvent: false });
  }

  saveField(): void {
    if (this.fieldForm.invalid) return;
    this.saving = true;
    const payload = this.fieldForm.value;

    const req = this.editingField
      ? this.api.patch(`/assets/metadata/fields/${this.editingField.id}`, payload)
      : this.api.post('/assets/metadata/fields', payload);

    req.subscribe({
      next: () => {
        this.saving = false;
        this.showForm = false;
        this.loadFields();
        this.snackBar.open(`Field ${this.editingField ? 'updated' : 'created'}`, '', { duration: 2000 });
        this.editingField = null;
      },
      error: () => { this.saving = false; },
    });
  }

  cancelForm(): void {
    this.showForm = false;
    this.editingField = null;
  }

  deleteField(field: MetadataField, event: Event): void {
    event.stopPropagation();
    if (!confirm(`Delete field "${field.label}"? This will remove all values from assets.`)) return;
    this.api.delete(`/assets/metadata/fields/${field.id}`).subscribe({
      next: () => {
        this.fields = this.fields.filter(f => f.id !== field.id);
        this.snackBar.open('Field deleted', '', { duration: 2000 });
      },
    });
  }

  toggleExpand(id: string): void {
    this.expandedId = this.expandedId === id ? null : id;
  }

  addOption(field: MetadataField): void {
    if (!field.field_values) field.field_values = [];
    field.field_values.push({ id: '', value: '', label: '', sort_order: field.field_values.length });
  }

  removeOption(field: MetadataField, index: number): void {
    field.field_values?.splice(index, 1);
  }

  saveFieldValues(field: MetadataField): void {
    const values = (field.field_values || []).filter(v => v.label.trim() && v.value.trim());
    this.api.put(`/assets/metadata/fields/${field.id}/values`, { values }).subscribe({
      next: () => { this.snackBar.open('Options saved', '', { duration: 2000 }); this.loadFields(); },
    });
  }

  onDrop(event: CdkDragDrop<MetadataField[]>): void {
    moveItemInArray(this.fields, event.previousIndex, event.currentIndex);
    // Update sort_order via API
    const order = this.fields.map((f, i) => ({ id: f.id, sort_order: i }));
    this.api.post('/assets/metadata/fields/reorder', { order }).subscribe();
  }

  onOptionDrop(event: CdkDragDrop<any[]>, field: MetadataField): void {
    if (field.field_values) {
      moveItemInArray(field.field_values, event.previousIndex, event.currentIndex);
    }
  }
}
