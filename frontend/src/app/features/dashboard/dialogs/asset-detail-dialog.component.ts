import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatTabsModule } from '@angular/material/tabs';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../../core/services/api.service';

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatDialogModule, MatTabsModule, MatButtonModule, MatIconModule,
    MatSelectModule, MatFormFieldModule, MatInputModule, MatTooltipModule,
  ],
  template: `
    <div class="detail-dialog">
      <!-- Header -->
      <div class="detail-header">
        <div class="detail-title-area">
          <div class="detail-platform">
            <mat-icon [class]="'platform-' + asset?.platform?.toLowerCase()">{{ getPlatformIcon(asset?.platform) }}</mat-icon>
            <span>{{ asset?.platform }}</span>
          </div>
          <h2>{{ asset?.ad_name || 'Unnamed Ad' }}</h2>

          <!-- Metadata chips -->
          <div class="metadata-chips" *ngIf="asset">
            <span class="chip" *ngFor="let m of assetMetaList">
              <span class="chip-key">{{ m.label }}:</span> {{ m.value }}
            </span>
          </div>
        </div>

        <!-- Date range selector -->
        <div class="detail-controls">
          <mat-form-field appearance="outline" class="date-field">
            <mat-label>From</mat-label>
            <input matInput type="date" [(ngModel)]="dateFrom" (change)="loadDetail()" />
          </mat-form-field>
          <mat-form-field appearance="outline" class="date-field">
            <mat-label>To</mat-label>
            <input matInput type="date" [(ngModel)]="dateTo" (change)="loadDetail()" />
          </mat-form-field>
        </div>

        <button mat-icon-button (click)="dialogRef.close()">
          <mat-icon>close</mat-icon>
        </button>
      </div>

      <!-- Tabs -->
      <mat-tab-group class="detail-tabs" *ngIf="!loading && asset">
        <!-- Performance Tab -->
        <mat-tab label="Performance">
          <div class="tab-content">
            <div class="perf-layout">
              <!-- Asset preview -->
              <div class="asset-preview">
                <video
                  *ngIf="asset.asset_format === 'VIDEO' && asset.asset_url"
                  [src]="asset.asset_url"
                  controls
                  class="asset-media"
                ></video>
                <img
                  *ngIf="asset.asset_format !== 'VIDEO' || !asset.asset_url"
                  [src]="asset.asset_url || asset.thumbnail_url || '/assets/images/placeholder.svg'"
                  class="asset-media"
                  alt="Creative"
                />
                <div class="ace-badge" [class]="getAceClass(asset.ace_score)">
                  ACE: {{ asset.ace_score | number:'1.0-0' }}
                </div>
              </div>

              <div class="perf-right">
                <!-- KPI chart area -->
                <div class="chart-area">
                  <div class="chart-controls">
                    <span class="section-label">Performance Over Time</span>
                    <div class="kpi-selectors">
                      <mat-form-field appearance="outline" class="kpi-select" *ngFor="let i of [0,1,2]">
                        <mat-select [(ngModel)]="selectedKpis[i]" (selectionChange)="loadDetail()">
                          <mat-option value="">None</mat-option>
                          <mat-option *ngFor="let k of availableKpis" [value]="k.value">{{ k.label }}</mat-option>
                        </mat-select>
                      </mat-form-field>
                    </div>
                  </div>
                  <div class="chart-placeholder">
                    <canvas id="kpiChart" width="100%" height="200"></canvas>
                  </div>
                </div>

                <!-- KPI table -->
                <div class="kpi-table">
                  <div class="section-label">Performance Summary</div>
                  <table>
                    <tr *ngFor="let row of kpiRows">
                      <td class="kpi-name">{{ row.label }}</td>
                      <td class="kpi-val">{{ row.value }}</td>
                    </tr>
                  </table>
                </div>
              </div>
            </div>

            <!-- Campaigns -->
            <div class="campaigns-section" *ngIf="detail?.campaigns?.length">
              <div class="section-label">Used in {{ detail.campaigns_count }} Campaign(s)</div>
              <div class="campaigns-list">
                <div class="campaign-row" *ngFor="let c of detail.campaigns">
                  <mat-icon>campaign</mat-icon>
                  <span>{{ c.campaign_name || c.campaign_id }}</span>
                  <span class="campaign-spend">{{ c.spend | currency:'USD':'symbol':'1.0-0' }}</span>
                </div>
              </div>
            </div>
          </div>
        </mat-tab>

        <!-- Creative Effectiveness Tab -->
        <mat-tab label="Creative Effectiveness">
          <div class="tab-content">
            <div class="ce-layout">
              <!-- Asset with heatmap toggle -->
              <div class="ce-preview">
                <div class="heatmap-toggles">
                  <button
                    *ngFor="let overlay of heatmapOverlays"
                    class="overlay-btn"
                    [class.active]="activeOverlay === overlay.key"
                    (click)="activeOverlay = overlay.key"
                  >
                    {{ overlay.label }}
                  </button>
                </div>
                <div class="heatmap-container">
                  <video
                    *ngIf="asset.asset_format === 'VIDEO' && asset.asset_url && activeOverlay === 'none'"
                    [src]="asset.asset_url"
                    controls
                    class="asset-media"
                  ></video>
                  <img
                    *ngIf="asset.asset_format !== 'VIDEO' || !asset.asset_url || activeOverlay !== 'none'"
                    [src]="asset.asset_url || asset.thumbnail_url || '/assets/images/placeholder.svg'"
                    class="asset-media"
                    alt="Creative"
                  />
                  <!-- Dummy heatmap overlay -->
                  <img
                    *ngIf="activeOverlay !== 'none'"
                    src="/assets/images/heatmap_dummy.png"
                    class="heatmap-overlay"
                    alt="Heatmap"
                  />
                </div>
              </div>

              <!-- Brainsuite KPIs (dummy) -->
              <div class="brainsuite-kpis">
                <div class="section-label">Brainsuite Creative Scores <span class="badge badge-info">DUMMY DATA</span></div>
                <div class="bs-kpi-grid">
                  <div class="bs-kpi-card" *ngFor="let kpi of brainsuiteKpis">
                    <div class="bs-kpi-value" [class]="getAceClass(kpi.value)">{{ kpi.value | number:'1.0-0' }}</div>
                    <div class="bs-kpi-label">{{ kpi.label }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </mat-tab>
      </mat-tab-group>

      <!-- Loading state -->
      <div class="loading-state" *ngIf="loading">
        <div class="skeleton" style="height: 400px; border-radius: 8px;"></div>
      </div>
    </div>
  `,
  styles: [`
    .detail-dialog { display: flex; flex-direction: column; height: 100%; background: var(--bg-card); }

    .detail-header {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      padding: 20px 24px;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }

    .detail-title-area { flex: 1; }
    .detail-platform { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
    .detail-title-area h2 { margin-bottom: 8px; }

    .metadata-chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .chip { background: var(--bg-hover); padding: 2px 10px; border-radius: 20px; font-size: 11px; color: var(--text-secondary); }
    .chip-key { color: var(--text-muted); }

    .detail-controls { display: flex; gap: 8px; }
    .date-field { width: 130px; }

    .detail-tabs { flex: 1; overflow: hidden; }

    .tab-content { padding: 20px; overflow-y: auto; max-height: calc(85vh - 160px); }

    .perf-layout { display: grid; grid-template-columns: 280px 1fr; gap: 20px; margin-bottom: 20px; }

    .asset-preview {
      position: relative;
      border-radius: 8px;
      overflow: hidden;
      background: var(--bg-hover);
    }

    .asset-media { width: 100%; display: block; object-fit: cover; max-height: 320px; }

    .ace-badge {
      position: absolute; bottom: 8px; right: 8px;
      padding: 4px 10px; border-radius: 20px;
      font-size: 12px; font-weight: 700;
      &.ace-high   { background: rgba(46,204,113,0.85); color: white; }
      &.ace-medium { background: rgba(243,156,18,0.85);  color: white; }
      &.ace-low    { background: rgba(231,76,60,0.85);   color: white; }
    }

    .section-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }

    .chart-controls { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
    .kpi-selectors { display: flex; gap: 6px; }
    .kpi-select { width: 120px; }
    .chart-placeholder { background: var(--bg-hover); border-radius: 8px; padding: 16px; min-height: 160px; }

    .kpi-table { margin-top: 16px; }
    .kpi-table table { width: 100%; }
    .kpi-table tr { border-bottom: 1px solid var(--border); }
    .kpi-name { padding: 8px 0; font-size: 12px; color: var(--text-secondary); }
    .kpi-val { padding: 8px 0; font-size: 13px; font-weight: 600; text-align: right; }

    .campaigns-section { border-top: 1px solid var(--border); padding-top: 16px; }
    .campaigns-list { display: flex; flex-direction: column; gap: 6px; }
    .campaign-row { display: flex; align-items: center; gap: 8px; padding: 8px; background: var(--bg-hover); border-radius: 6px; font-size: 13px; mat-icon { font-size: 16px; color: var(--text-muted); } }
    .campaign-spend { margin-left: auto; font-weight: 600; }

    .ce-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .heatmap-toggles { display: flex; gap: 6px; margin-bottom: 12px; }
    .overlay-btn { padding: 4px 12px; border-radius: 20px; border: 1px solid var(--border); background: transparent; color: var(--text-secondary); font-size: 12px; cursor: pointer; transition: all var(--transition); &.active { background: var(--accent); border-color: var(--accent); color: white; } }
    .heatmap-container { position: relative; border-radius: 8px; overflow: hidden; }
    .heatmap-overlay { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; mix-blend-mode: multiply; opacity: 0.7; }

    .bs-kpi-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .bs-kpi-card { background: var(--bg-hover); border-radius: 8px; padding: 16px; text-align: center; }
    .bs-kpi-value { font-size: 28px; font-weight: 700; margin-bottom: 4px; &.ace-high { color: var(--success); } &.ace-medium { color: var(--warning); } &.ace-low { color: var(--error); } }
    .bs-kpi-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }

    .loading-state { padding: 24px; }
  `],
})
export class AssetDetailDialogComponent implements OnInit {
  asset: any = null;
  detail: any = null;
  loading = true;

  dateFrom: string;
  dateTo: string;

  selectedKpis = ['spend', 'ctr', 'roas'];
  activeOverlay = 'none';

  availableKpis = [
    { value: 'spend', label: 'Spend' },
    { value: 'ctr', label: 'CTR' },
    { value: 'roas', label: 'ROAS' },
    { value: 'cpm', label: 'CPM' },
    { value: 'video_views', label: 'Video Views' },
    { value: 'vtr', label: 'VTR' },
    { value: 'conversions', label: 'Conversions' },
  ];

  heatmapOverlays = [
    { key: 'none', label: 'Original' },
    { key: 'attention', label: 'Attention' },
    { key: 'heatmap', label: 'Heatmap' },
    { key: 'fog', label: 'Fog Map' },
  ];

  constructor(
    private api: ApiService,
    public dialogRef: MatDialogRef<AssetDetailDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { assetId: string; dateFrom: string; dateTo: string },
  ) {
    this.dateFrom = data.dateFrom;
    this.dateTo = data.dateTo;
  }

  ngOnInit(): void {
    this.loadDetail();
  }

  loadDetail(): void {
    this.loading = true;
    this.api.get<any>(`/dashboard/assets/${this.data.assetId}`, {
      date_from: this.dateFrom,
      date_to: this.dateTo,
      kpis: this.selectedKpis.filter(Boolean).join(','),
    }).subscribe({
      next: (d) => {
        this.detail = d;
        this.asset = d;
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  get assetMetaList(): { label: string; value: string }[] {
    if (!this.asset) return [];
    const items = [];
    if (this.asset.campaign_objective) items.push({ label: 'Objective', value: this.asset.campaign_objective });
    if (this.asset.campaign_name) items.push({ label: 'Campaign', value: this.asset.campaign_name });
    if (this.asset.asset_format) items.push({ label: 'Format', value: this.asset.asset_format });
    return items;
  }

  get kpiRows(): { label: string; value: string }[] {
    const p = this.detail?.performance;
    if (!p) return [];
    const fmt = (v: number | null, prefix = '', suffix = '', decimals = 0) =>
      v != null ? `${prefix}${v.toFixed(decimals)}${suffix}` : 'N/A';
    return [
      { label: 'Campaigns Used In', value: String(this.detail.campaigns_count || 0) },
      { label: 'ACE Score', value: this.asset.ace_score ? `${this.asset.ace_score.toFixed(1)} (dummy)` : 'N/A' },
      { label: 'Total Spend', value: fmt(p.spend, '$', '', 0) },
      { label: 'CPM', value: fmt(p.cpm, '$', '', 2) },
      { label: 'CTR', value: fmt(p.ctr, '', '%', 2) },
      ...(p.video_views ? [{ label: 'VTR', value: fmt(p.vtr, '', '%', 2) }] : []),
      ...(p.cvr ? [{ label: 'CVR', value: fmt(p.cvr, '', '%', 2) }] : []),
      ...(p.roas ? [{ label: 'ROAS', value: fmt(p.roas, '', 'x', 2) }] : []),
    ];
  }

  get brainsuiteKpis(): { label: string; value: number }[] {
    const bm = this.asset?.brainsuite_metadata || {};
    return [
      { label: 'ACE Score', value: this.asset?.ace_score || 0 },
      { label: 'Attention', value: bm.attention_score || 0 },
      { label: 'Brand Score', value: bm.brand_score || 0 },
      { label: 'Emotion Score', value: bm.emotion_score || 0 },
      { label: 'Message Clarity', value: bm.message_clarity || 0 },
      { label: 'Visual Impact', value: bm.visual_impact || 0 },
    ];
  }

  getPlatformIcon(platform: string): string {
    const icons: Record<string, string> = { META: 'facebook', TIKTOK: 'music_video', YOUTUBE: 'smart_display' };
    return icons[platform] || 'ads_click';
  }

  getAceClass(score: number | null): string {
    if (!score) return 'ace-low';
    if (score >= 70) return 'ace-high';
    if (score >= 45) return 'ace-medium';
    return 'ace-low';
  }
}
