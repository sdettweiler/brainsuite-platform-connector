import {
  Component,
  Input,
  Output,
  EventEmitter,
  OnChanges,
  SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  FormsModule,
  ReactiveFormsModule,
  FormBuilder,
  FormGroup,
  FormArray,
  Validators,
} from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../../core/services/api.service';

// ---------------------------------------------------------------------------
// Auto-match lookup (D-06) — client-side pre-fill, not persisted until Save
// ---------------------------------------------------------------------------
const AUTO_MATCH: Record<string, string> = {
  brandValues: 'brainsuite_brand_values',
  brandValuesLanguage: 'brainsuite_brand_values_language',
  assetLanguage: 'brainsuite_asset_language',
  voiceOverLanguage: 'brainsuite_voice_over_language',
  assetName: 'brainsuite_asset_name',
};

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

interface BrainsuiteApp {
  id: string;
  name: string;
  app_type: 'VIDEO' | 'IMAGE' | 'MIXED';
  is_default_for_video: boolean;
  is_default_for_image: boolean;
  description?: string;
  system_app_name?: string;
}

interface FieldMappingRow {
  api_field_name: string;
  metadata_field_id: string | null;
  is_mandatory: boolean;
  is_custom: boolean;
}

interface MetadataFieldOption {
  id: string;
  name: string;
  label: string;
  field_type: string;
}

interface FieldMappingApiResponse {
  app_id: string;
  app_name: string;
  app_type: string;
  standard_fields: FieldMappingRow[];
  custom_fields: FieldMappingRow[];
  metadata_options: MetadataFieldOption[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

@Component({
  standalone: true,
  selector: 'app-field-mappings-panel',
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatSlideToggleModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
  ],
  template: `
    <!-- Backdrop -->
    <div
      class="slide-panel-backdrop"
      [class.active]="isOpen"
      (click)="onBackdropClick()"
    ></div>

    <!-- Slide Panel -->
    <div class="slide-panel" [class.open]="isOpen" role="dialog" aria-modal="true">

      <!-- Header -->
      <div class="panel-header">
        <div class="header-title">
          <div class="header-title-row">
            <span class="app-title">{{ app?.name }}</span>
            <span
              class="app-type-badge"
              [class]="'type-' + (app?.app_type?.toLowerCase() ?? '')"
            >{{ app?.app_type }}</span>
          </div>
          <p class="panel-subtitle">Map metadata fields to BrainSuite API fields</p>
        </div>
        <button
          mat-icon-button
          class="close-btn"
          type="button"
          aria-label="Close panel"
          (click)="cancel()"
        >
          <i class="bi bi-x-lg"></i>
        </button>
      </div>

      <!-- Loading state -->
      <div *ngIf="loading" class="panel-loading">
        <mat-spinner diameter="28"></mat-spinner>
      </div>

      <!-- Body -->
      <div *ngIf="!loading && form" class="panel-body">

        <!-- Sticky column headers -->
        <div class="col-header-row">
          <div class="col-api-field">API Field</div>
          <div class="col-metadata-field">Metadata Field</div>
          <div class="col-mandatory">Mandatory</div>
        </div>

        <form [formGroup]="form">

          <!-- SECTION A: Standard Fields -->
          <div class="section-label">STANDARD FIELDS</div>

          <ng-container formArrayName="standardFields">
            <div
              *ngFor="let fieldGroup of standardFieldsArray.controls; let i = index"
              [formGroupName]="i"
              class="field-row"
              [class.field-row--mandatory]="fieldGroup.get('is_mandatory')?.value"
            >
              <!-- Col 1: API field name -->
              <div class="col-api-field field-name-cell">
                <i
                  *ngIf="fieldGroup.get('is_mandatory')?.value"
                  class="bi bi-asterisk mandatory-star"
                ></i>
                <span class="field-name-text">{{ fieldGroup.get('api_field_name')?.value }}</span>
              </div>

              <!-- Col 2: Metadata field dropdown -->
              <div class="col-metadata-field">
                <mat-select
                  formControlName="metadata_field_id"
                  class="compact-select"
                  panelClass="field-mapping-select-panel"
                >
                  <mat-option [value]="null">-- Unmapped --</mat-option>
                  <mat-option *ngFor="let opt of metadataOptions" [value]="opt.id">
                    {{ opt.label }}
                  </mat-option>
                </mat-select>
              </div>

              <!-- Col 3: Mandatory toggle -->
              <div class="col-mandatory">
                <mat-slide-toggle formControlName="is_mandatory" color="accent"></mat-slide-toggle>
              </div>
            </div>
          </ng-container>

          <!-- SECTION B: Custom Fields -->
          <div class="section-label section-label--custom">CUSTOM FIELDS</div>

          <ng-container formArrayName="customFields">
            <div
              *ngFor="let fieldGroup of customFieldsArray.controls; let i = index"
              [formGroupName]="i"
              class="field-row field-row--custom"
              [class.field-row--mandatory]="fieldGroup.get('is_mandatory')?.value"
            >
              <!-- Col 1: Editable API field name -->
              <div class="col-api-field">
                <mat-form-field appearance="outline" class="custom-name-field">
                  <input
                    matInput
                    formControlName="api_field_name"
                    placeholder="API field name"
                  />
                  <mat-error *ngIf="fieldGroup.get('api_field_name')?.hasError('required')">
                    API field name is required
                  </mat-error>
                </mat-form-field>
              </div>

              <!-- Col 2: Metadata field dropdown -->
              <div class="col-metadata-field">
                <mat-select
                  formControlName="metadata_field_id"
                  class="compact-select"
                  panelClass="field-mapping-select-panel"
                >
                  <mat-option [value]="null">-- Unmapped --</mat-option>
                  <mat-option *ngFor="let opt of metadataOptions" [value]="opt.id">
                    {{ opt.label }}
                  </mat-option>
                </mat-select>
              </div>

              <!-- Col 3: Mandatory toggle + delete -->
              <div class="col-mandatory col-actions">
                <mat-slide-toggle formControlName="is_mandatory" color="accent"></mat-slide-toggle>
                <button
                  mat-icon-button
                  type="button"
                  class="delete-field-btn"
                  aria-label="Delete field"
                  (click)="removeCustomField(i)"
                >
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </div>
          </ng-container>

          <!-- Empty custom fields state -->
          <p
            *ngIf="customFieldsArray.length === 0"
            class="empty-custom-fields"
          >
            No custom fields added. Use custom fields to send additional metadata to the BrainSuite API.
          </p>

          <!-- Add custom field button -->
          <div class="add-custom-row">
            <button
              mat-stroked-button
              type="button"
              class="add-custom-btn"
              (click)="addCustomField()"
            >
              <i class="bi bi-plus-lg"></i>
              Add custom field
            </button>
          </div>

        </form>
      </div>

      <!-- Footer -->
      <div class="panel-footer">
        <button
          mat-stroked-button
          type="button"
          class="discard-btn"
          (click)="cancel()"
          [disabled]="saving"
        >
          Discard Changes
        </button>
        <button
          mat-flat-button
          type="button"
          class="save-btn"
          (click)="save()"
          [disabled]="saving || loading"
        >
          <mat-spinner *ngIf="saving" diameter="16" class="save-spinner"></mat-spinner>
          {{ saving ? 'Saving...' : 'Save Mappings' }}
        </button>
      </div>

    </div>
  `,
  styles: [`
    /* -----------------------------------------------------------------------
       Backdrop
    ----------------------------------------------------------------------- */
    .slide-panel-backdrop {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      opacity: 0;
      transition: opacity 0.3s ease;
      z-index: 999;
      pointer-events: none;
    }
    .slide-panel-backdrop.active {
      opacity: 1;
      pointer-events: auto;
    }

    /* -----------------------------------------------------------------------
       Panel
    ----------------------------------------------------------------------- */
    .slide-panel {
      position: fixed;
      top: 0; right: 0;
      width: 600px;
      max-width: 90vw;
      height: 100vh;
      background: var(--bg-card);
      border-left: 1px solid var(--border);
      box-shadow: -4px 0 24px rgba(0, 0, 0, 0.18);
      z-index: 1000;
      display: flex;
      flex-direction: column;
      transform: translateX(100%);
      transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .slide-panel.open {
      transform: translateX(0);
    }

    /* -----------------------------------------------------------------------
       Header
    ----------------------------------------------------------------------- */
    .panel-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      padding: 20px 32px;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .header-title { flex: 1; min-width: 0; }
    .header-title-row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .app-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .app-type-badge {
      display: inline-block;
      padding: 1px 7px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      flex-shrink: 0;
    }
    .app-type-badge.type-video { background: rgba(234,67,53,0.12); color: #EA4335; }
    .app-type-badge.type-image { background: rgba(52,168,83,0.12); color: #34A853; }
    .app-type-badge.type-mixed { background: rgba(66,133,244,0.12); color: #4285F4; }
    .panel-subtitle {
      font-size: 13px;
      font-weight: 400;
      color: var(--text-secondary);
      margin: 4px 0 0;
    }
    .close-btn {
      color: var(--text-secondary);
      flex-shrink: 0;
    }
    .close-btn i { font-size: 16px; }

    /* -----------------------------------------------------------------------
       Loading
    ----------------------------------------------------------------------- */
    .panel-loading {
      display: flex;
      justify-content: center;
      align-items: center;
      flex: 1;
    }

    /* -----------------------------------------------------------------------
       Body
    ----------------------------------------------------------------------- */
    .panel-body {
      flex: 1;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
    }

    /* Sticky column header row */
    .col-header-row {
      display: grid;
      grid-template-columns: 1fr 1.5fr auto;
      gap: 12px;
      padding: 8px 32px;
      position: sticky;
      top: 0;
      background: var(--bg-secondary);
      z-index: 1;
      border-bottom: 1px solid var(--border);
    }
    .col-header-row > div {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
    }
    .col-mandatory { display: flex; align-items: center; gap: 4px; }

    /* Section labels */
    .section-label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      padding: 8px 32px;
    }
    .section-label--custom {
      padding-top: 16px;
    }

    /* -----------------------------------------------------------------------
       Field rows
    ----------------------------------------------------------------------- */
    .field-row {
      display: grid;
      grid-template-columns: 1fr 1.5fr auto;
      gap: 12px;
      align-items: center;
      padding: 8px 32px;
      transition: background 0.15s ease;
    }
    .field-row--mandatory {
      background: rgba(255, 119, 0, 0.06);
    }
    .field-row--custom {
      /* custom fields may have taller rows due to form-field */
      align-items: flex-start;
    }

    /* Col: API field name */
    .field-name-cell {
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
    }
    .mandatory-star {
      font-size: 12px;
      color: var(--accent);
      flex-shrink: 0;
    }
    .field-name-text {
      font-size: 13px;
      font-weight: 400;
      color: var(--text-primary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* Col: metadata select */
    .col-api-field { min-width: 0; }
    .col-metadata-field { min-width: 0; }
    .compact-select {
      width: 100%;
      font-size: 13px;
    }

    /* Col: mandatory + actions */
    .col-actions {
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .delete-field-btn {
      color: var(--error) !important;
      flex-shrink: 0;
    }
    .delete-field-btn i { font-size: 15px; }

    /* Custom field name input */
    .custom-name-field {
      width: 100%;
      font-size: 13px;
    }
    /* Compact mat-form-field height inside rows */
    .custom-name-field ::ng-deep .mat-mdc-form-field-infix {
      min-height: unset;
      height: 36px;
      padding-top: 0;
      padding-bottom: 0;
      display: flex;
      align-items: center;
    }
    .custom-name-field ::ng-deep .mdc-text-field--outlined {
      height: 36px;
    }
    .custom-name-field ::ng-deep .mat-mdc-text-field-wrapper {
      height: 36px;
      padding: 0 8px;
    }
    .custom-name-field ::ng-deep input.mat-mdc-input-element {
      height: 36px;
      line-height: 36px;
      padding: 0;
      margin: 0;
      box-sizing: border-box;
    }

    /* -----------------------------------------------------------------------
       Empty custom fields state
    ----------------------------------------------------------------------- */
    .empty-custom-fields {
      font-size: 13px;
      color: var(--text-muted);
      padding: 12px 24px 4px;
      margin: 0;
      font-style: italic;
    }

    /* Add custom field row */
    .add-custom-row {
      padding: 8px 24px 16px;
    }
    .add-custom-btn {
      color: var(--accent) !important;
      border-color: var(--accent) !important;
      font-size: 13px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .add-custom-btn i { font-size: 14px; }

    /* -----------------------------------------------------------------------
       Footer
    ----------------------------------------------------------------------- */
    .panel-footer {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      padding: 16px 24px;
      border-top: 1px solid var(--border);
      flex-shrink: 0;
    }
    .save-btn {
      background: var(--accent) !important;
      color: white !important;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .save-spinner {
      display: inline-flex;
      align-items: center;
      line-height: 0;
    }
  `],
})
export class FieldMappingsPanelComponent implements OnChanges {
  @Input() app: BrainsuiteApp | null = null;
  @Input() isOpen = false;

  @Output() closed = new EventEmitter<void>();
  @Output() saved = new EventEmitter<void>();

  form: FormGroup | null = null;
  metadataOptions: MetadataFieldOption[] = [];
  loading = false;
  saving = false;

  constructor(
    private fb: FormBuilder,
    private api: ApiService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    // Load field mappings whenever the panel opens (isOpen becomes true) and an app is selected
    const isOpenChange = changes['isOpen'];
    if (isOpenChange && this.isOpen && this.app) {
      this.loadFieldMappings();
    }
    // Also reload if the app changes while open (edge case)
    const appChange = changes['app'];
    if (appChange && this.isOpen && this.app) {
      this.loadFieldMappings();
    }
  }

  // -------------------------------------------------------------------------
  // FormArray accessors
  // -------------------------------------------------------------------------

  get standardFieldsArray(): FormArray {
    return this.form?.get('standardFields') as FormArray;
  }

  get customFieldsArray(): FormArray {
    return this.form?.get('customFields') as FormArray;
  }

  // -------------------------------------------------------------------------
  // Data loading
  // -------------------------------------------------------------------------

  private loadFieldMappings(): void {
    if (!this.app) return;
    this.loading = true;
    this.form = null;
    this.metadataOptions = [];

    this.api.get<FieldMappingApiResponse>(
      `/brainsuite-config/apps/${this.app.id}/field-mappings`
    ).subscribe({
      next: (response) => {
        this.metadataOptions = response.metadata_options || [];
        this.buildForm(response);
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.snackBar.open(
          'Failed to load field mappings — please try again.',
          'Close',
          { duration: 4000, panelClass: ['snack-error'] }
        );
        // Close the panel gracefully on load failure
        this.closed.emit();
      },
    });
  }

  private buildForm(response: FieldMappingApiResponse): void {
    const hasExistingMappings =
      response.standard_fields.some(f => f.metadata_field_id) ||
      response.custom_fields.length > 0;

    const standardGroups = response.standard_fields.map(field => {
      // D-06: Auto-match if no existing mapping saved
      let metadataFieldId = field.metadata_field_id;
      if (!hasExistingMappings && !metadataFieldId) {
        const matchSlug = AUTO_MATCH[field.api_field_name];
        if (matchSlug) {
          const matched = this.metadataOptions.find(opt => opt.name === matchSlug);
          if (matched) {
            metadataFieldId = matched.id;
          }
        }
      }
      return this.fb.group({
        api_field_name: [field.api_field_name],
        metadata_field_id: [metadataFieldId],
        is_mandatory: [field.is_mandatory],
      });
    });

    const customGroups = response.custom_fields.map(field =>
      this.fb.group({
        api_field_name: [field.api_field_name, [Validators.required, Validators.minLength(1)]],
        metadata_field_id: [field.metadata_field_id],
        is_mandatory: [field.is_mandatory],
      })
    );

    this.form = this.fb.group({
      standardFields: this.fb.array(standardGroups),
      customFields: this.fb.array(customGroups),
    });
  }

  // -------------------------------------------------------------------------
  // Custom field management
  // -------------------------------------------------------------------------

  addCustomField(): void {
    this.customFieldsArray.push(
      this.fb.group({
        api_field_name: ['', [Validators.required, Validators.minLength(1)]],
        metadata_field_id: [null],
        is_mandatory: [false],
      })
    );
  }

  removeCustomField(index: number): void {
    this.customFieldsArray.removeAt(index);
  }

  // -------------------------------------------------------------------------
  // Save
  // -------------------------------------------------------------------------

  save(): void {
    if (!this.form || !this.app) return;

    // Mark all custom field api_field_name controls as touched to show validation
    this.customFieldsArray.controls.forEach(ctrl => {
      ctrl.get('api_field_name')?.markAsTouched();
    });

    if (!this.form.valid) return;

    this.saving = true;

    const standardFields = this.standardFieldsArray.controls.map(ctrl => ({
      api_field_name: ctrl.get('api_field_name')?.value,
      metadata_field_id: ctrl.get('metadata_field_id')?.value ?? null,
      is_mandatory: ctrl.get('is_mandatory')?.value ?? false,
    }));

    const customFields = this.customFieldsArray.controls.map(ctrl => ({
      api_field_name: ctrl.get('api_field_name')?.value,
      metadata_field_id: ctrl.get('metadata_field_id')?.value ?? null,
      is_mandatory: ctrl.get('is_mandatory')?.value ?? false,
    }));

    const payload = { standard_fields: standardFields, custom_fields: customFields };

    this.api.put(
      `/brainsuite-config/apps/${this.app.id}/field-mappings`,
      payload
    ).subscribe({
      next: () => {
        this.saving = false;
        this.snackBar.open('Field mappings saved', '', { duration: 3000 });
        this.saved.emit();
        this.closed.emit();
      },
      error: () => {
        this.saving = false;
        this.snackBar.open(
          'Failed to save mappings — please try again.',
          'Close',
          { duration: 4000, panelClass: ['snack-error'] }
        );
      },
    });
  }

  // -------------------------------------------------------------------------
  // Cancel / close
  // -------------------------------------------------------------------------

  cancel(): void {
    this.closed.emit();
  }

  onBackdropClick(): void {
    this.cancel();
  }
}
