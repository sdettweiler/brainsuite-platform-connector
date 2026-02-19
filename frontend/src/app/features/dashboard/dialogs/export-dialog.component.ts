import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../../core/services/api.service';

interface ExportField {
  key: string;
  label: string;
  category: 'dimension' | 'performance' | 'brainsuite';
}

interface ExportDialogData {
  dateFrom: string;
  dateTo: string;
  platforms: string[];
  format?: string;
  selectedAssetIds?: string[];
  totalAssets?: number;
}

@Component({
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  template: `
    <div class="export-dialog">
      <div class="dialog-header">
        <h2>Export Data</h2>
        <button mat-icon-button (click)="close()"><mat-icon>close</mat-icon></button>
      </div>

      <div class="dialog-body">
        <!-- Format Selection -->
        <div class="section">
          <h3 class="section-title">Format</h3>
          <div class="format-buttons">
            <button
              *ngFor="let f of formats"
              class="format-btn"
              [class.active]="selectedFormat === f.value"
              (click)="selectedFormat = f.value"
            >
              <mat-icon>{{ f.icon }}</mat-icon>
              <span>{{ f.label }}</span>
              <span class="format-ext">.{{ f.value }}</span>
            </button>
          </div>
        </div>

        <!-- Scope -->
        <div class="section">
          <h3 class="section-title">Scope</h3>
          <div class="scope-info">
            <mat-icon>info_outline</mat-icon>
            <span *ngIf="data.selectedAssetIds?.length">
              {{ data.selectedAssetIds!.length }} selected assets &middot; {{ data.dateFrom }} to {{ data.dateTo }}
            </span>
            <span *ngIf="!data.selectedAssetIds?.length">
              All filtered assets ({{ data.totalAssets || 0 }}) &middot; {{ data.dateFrom }} to {{ data.dateTo }}
            </span>
          </div>
        </div>

        <!-- Field Selection -->
        <div class="section fields-section">
          <h3 class="section-title">Fields</h3>

          <div class="fields-layout">
            <!-- Available -->
            <div class="field-panel">
              <div class="panel-header">
                <span>Available</span>
                <button class="link-btn" (click)="deselectAll()">Deselect all</button>
              </div>
              <div class="field-list">
                <ng-container *ngFor="let cat of categories">
                  <div class="category-label">{{ cat.label }}</div>
                  <div
                    *ngFor="let f of getAvailable(cat.key)"
                    class="field-item"
                    (click)="addField(f)"
                    draggable="true"
                    (dragstart)="onDragStart($event, f, 'available')"
                    (dragover)="$event.preventDefault()"
                    (drop)="onDropToSelected($event)"
                  >
                    <mat-icon class="drag-handle">drag_indicator</mat-icon>
                    <span>{{ f.label }}</span>
                    <mat-icon class="add-icon">add</mat-icon>
                  </div>
                </ng-container>
              </div>
            </div>

            <!-- Arrow -->
            <div class="arrow-col">
              <mat-icon>arrow_forward</mat-icon>
            </div>

            <!-- Selected -->
            <div class="field-panel selected-panel">
              <div class="panel-header">
                <span>Export columns ({{ selectedFields.length }})</span>
                <button class="link-btn" (click)="selectAll()">Select all</button>
              </div>
              <div
                class="field-list"
                (dragover)="$event.preventDefault()"
                (drop)="onDropToSelected($event)"
              >
                <div
                  *ngFor="let f of selectedFields; let i = index"
                  class="field-item selected"
                  draggable="true"
                  (dragstart)="onDragStart($event, f, 'selected', i)"
                  (dragover)="onDragOverSelected($event, i)"
                  (drop)="onDropReorder($event, i)"
                >
                  <mat-icon class="drag-handle">drag_indicator</mat-icon>
                  <span>{{ f.label }}</span>
                  <button mat-icon-button class="remove-btn" (click)="removeField(f)">
                    <mat-icon>close</mat-icon>
                  </button>
                </div>
                <div *ngIf="selectedFields.length === 0" class="empty-selected">
                  <mat-icon>add_circle_outline</mat-icon>
                  <span>Add fields from the left</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="dialog-footer">
        <div class="footer-left">
          <mat-icon>schedule</mat-icon>
          <span class="est-time">Est. export time: ~{{ estimatedTime }}</span>
        </div>
        <div class="footer-right">
          <button mat-stroked-button (click)="close()">Cancel</button>
          <button
            mat-flat-button
            class="export-btn"
            [disabled]="selectedFields.length === 0 || exporting"
            (click)="doExport()"
          >
            <mat-spinner *ngIf="exporting" diameter="16"></mat-spinner>
            <mat-icon *ngIf="!exporting">file_download</mat-icon>
            {{ exporting ? 'Exporting...' : 'Export' }}
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .export-dialog { display: flex; flex-direction: column; height: 100%; }

    .dialog-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 20px 24px 16px; border-bottom: 1px solid var(--border);
      h2 { font-size: 18px; font-weight: 600; margin: 0; }
    }

    .dialog-body { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 24px; }

    .section { display: flex; flex-direction: column; gap: 12px; }
    .section-title { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-secondary); margin: 0; }

    .format-buttons { display: flex; gap: 12px; }
    .format-btn {
      display: flex; flex-direction: column; align-items: center; gap: 4px;
      padding: 16px 24px; border: 1px solid var(--border); border-radius: 8px;
      background: var(--bg-card); cursor: pointer; transition: all 0.15s; min-width: 100px;
      mat-icon { font-size: 24px; color: var(--text-secondary); }
      span { font-size: 13px; font-weight: 500; }
      .format-ext { font-size: 11px; color: var(--text-muted); }
      &:hover { border-color: var(--accent); }
      &.active { border-color: var(--accent); background: rgba(66,133,244,0.08); mat-icon { color: var(--accent); } }
    }

    .scope-info {
      display: flex; align-items: center; gap: 8px;
      padding: 10px 14px; background: var(--bg-secondary); border-radius: 6px;
      mat-icon { font-size: 16px; color: var(--text-secondary); }
      span { font-size: 13px; color: var(--text-secondary); }
    }

    .fields-section { flex: 1; }

    .fields-layout { display: grid; grid-template-columns: 1fr auto 1fr; gap: 12px; align-items: start; }

    .field-panel {
      border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
      max-height: 320px; display: flex; flex-direction: column;
    }

    .panel-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 10px 12px; background: var(--bg-secondary); border-bottom: 1px solid var(--border);
      span { font-size: 12px; font-weight: 500; }
    }

    .link-btn { background: none; border: none; color: var(--accent); font-size: 12px; cursor: pointer; padding: 0; }

    .field-list { overflow-y: auto; flex: 1; padding: 4px 0; }

    .category-label {
      padding: 8px 12px 4px; font-size: 10px; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.5px; color: var(--text-muted);
    }

    .field-item {
      display: flex; align-items: center; gap: 8px; padding: 7px 12px;
      cursor: pointer; transition: background 0.1s; font-size: 13px;
      &:hover { background: var(--bg-secondary); }
      &.selected { cursor: default; }
      .drag-handle { font-size: 16px; color: var(--text-muted); cursor: grab; }
      .add-icon { font-size: 16px; color: var(--accent); margin-left: auto; opacity: 0; }
      &:hover .add-icon { opacity: 1; }
      .remove-btn { width: 24px; height: 24px; line-height: 24px; margin-left: auto;
        mat-icon { font-size: 14px; } }
    }

    .empty-selected {
      display: flex; flex-direction: column; align-items: center; gap: 8px;
      padding: 40px 16px; color: var(--text-muted); font-size: 13px;
      mat-icon { font-size: 32px; opacity: 0.4; }
    }

    .selected-panel { background: var(--bg-secondary); }

    .arrow-col { display: flex; align-items: center; padding-top: 48px; mat-icon { color: var(--text-muted); } }

    .dialog-footer {
      display: flex; align-items: center; justify-content: space-between;
      padding: 16px 24px; border-top: 1px solid var(--border);
    }

    .footer-left { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); font-size: 12px; mat-icon { font-size: 16px; } }
    .footer-right { display: flex; gap: 12px; }

    .export-btn {
      background: var(--accent) !important; color: white !important;
      display: flex; align-items: center; gap: 8px;
    }
  `],
})
export class ExportDialogComponent implements OnInit {
  formats = [
    { value: 'xlsx', label: 'Excel', icon: 'table_chart' },
    { value: 'csv', label: 'CSV', icon: 'description' },
    { value: 'pdf', label: 'PDF', icon: 'picture_as_pdf' },
  ];
  selectedFormat = 'xlsx';

  categories = [
    { key: 'dimension', label: 'Dimensions' },
    { key: 'performance', label: 'Performance KPIs' },
    { key: 'brainsuite', label: 'Brainsuite KPIs' },
  ];

  allFields: ExportField[] = [
    // Dimensions
    { key: 'ad_name', label: 'Ad Name', category: 'dimension' },
    { key: 'ad_id', label: 'Ad ID', category: 'dimension' },
    { key: 'platform', label: 'Platform', category: 'dimension' },
    { key: 'asset_format', label: 'Format', category: 'dimension' },
    { key: 'campaign_name', label: 'Campaign', category: 'dimension' },
    { key: 'ad_set_name', label: 'Ad Set', category: 'dimension' },
    { key: 'objective', label: 'Objective', category: 'dimension' },
    { key: 'report_date', label: 'Date', category: 'dimension' },
    // Performance
    { key: 'spend', label: 'Spend', category: 'performance' },
    { key: 'impressions', label: 'Impressions', category: 'performance' },
    { key: 'clicks', label: 'Clicks', category: 'performance' },
    { key: 'ctr', label: 'CTR', category: 'performance' },
    { key: 'cpm', label: 'CPM', category: 'performance' },
    { key: 'cpc', label: 'CPC', category: 'performance' },
    { key: 'reach', label: 'Reach', category: 'performance' },
    { key: 'conversions', label: 'Conversions', category: 'performance' },
    { key: 'roas', label: 'ROAS', category: 'performance' },
    { key: 'video_views', label: 'Video Views', category: 'performance' },
    { key: 'vtr', label: 'VTR', category: 'performance' },
    { key: 'video_completion_rate', label: 'Video Completion Rate', category: 'performance' },
    // Brainsuite
    { key: 'ace_score', label: 'ACE Score', category: 'brainsuite' },
    { key: 'attention_score', label: 'Attention Score', category: 'brainsuite' },
    { key: 'brand_score', label: 'Brand Score', category: 'brainsuite' },
    { key: 'emotion_score', label: 'Emotion Score', category: 'brainsuite' },
    { key: 'message_clarity', label: 'Message Clarity', category: 'brainsuite' },
    { key: 'visual_impact', label: 'Visual Impact', category: 'brainsuite' },
  ];

  selectedFields: ExportField[] = [];
  exporting = false;

  // Drag state
  private dragField: ExportField | null = null;
  private dragSource: 'available' | 'selected' = 'available';
  private dragSourceIndex = -1;

  get estimatedTime(): string {
    const count = this.data.totalAssets || 0;
    if (count < 1000) return '< 5s';
    if (count < 10000) return '~10s';
    return '~30s';
  }

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: ExportDialogData,
    private dialogRef: MatDialogRef<ExportDialogComponent>,
    private api: ApiService,
  ) {}

  ngOnInit(): void {
    // Default: select core fields
    const defaults = ['ad_name', 'platform', 'asset_format', 'spend', 'impressions', 'ctr', 'ace_score'];
    this.selectedFields = defaults.map(k => this.allFields.find(f => f.key === k)!).filter(Boolean);
  }

  getAvailable(category: string): ExportField[] {
    return this.allFields.filter(f => f.category === category && !this.selectedFields.find(s => s.key === f.key));
  }

  addField(f: ExportField): void {
    if (!this.selectedFields.find(s => s.key === f.key)) {
      this.selectedFields = [...this.selectedFields, f];
    }
  }

  removeField(f: ExportField): void {
    this.selectedFields = this.selectedFields.filter(s => s.key !== f.key);
  }

  selectAll(): void {
    this.selectedFields = [...this.allFields];
  }

  deselectAll(): void {
    this.selectedFields = [];
  }

  onDragStart(event: DragEvent, field: ExportField, source: 'available' | 'selected', index = -1): void {
    this.dragField = field;
    this.dragSource = source;
    this.dragSourceIndex = index;
    event.dataTransfer?.setData('text/plain', field.key);
  }

  onDropToSelected(event: DragEvent): void {
    event.preventDefault();
    if (this.dragField && this.dragSource === 'available') {
      this.addField(this.dragField);
    }
    this.dragField = null;
  }

  onDragOverSelected(event: DragEvent, index: number): void {
    event.preventDefault();
  }

  onDropReorder(event: DragEvent, targetIndex: number): void {
    event.preventDefault();
    if (this.dragField && this.dragSource === 'selected' && this.dragSourceIndex !== targetIndex) {
      const arr = [...this.selectedFields];
      arr.splice(this.dragSourceIndex, 1);
      arr.splice(targetIndex, 0, this.dragField);
      this.selectedFields = arr;
    }
    this.dragField = null;
  }

  async doExport(): Promise<void> {
    this.exporting = true;
    try {
      const payload = {
        date_from: this.data.dateFrom,
        date_to: this.data.dateTo,
        platforms: this.data.platforms,
        format: this.selectedFormat,
        fields: this.selectedFields.map(f => f.key),
        asset_ids: this.data.selectedAssetIds || [],
      };

      const blob = await this.api.exportData(payload);
      const ext = this.selectedFormat;
      const fileName = `brainsuite_export_${new Date().toISOString().split('T')[0]}.${ext}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
      this.dialogRef.close();
    } catch (e) {
      console.error('Export failed', e);
    } finally {
      this.exporting = false;
    }
  }

  close(): void {
    this.dialogRef.close();
  }
}
