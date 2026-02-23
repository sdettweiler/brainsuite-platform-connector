import { Component, Inject, OnInit, OnDestroy, AfterViewInit, ViewChild, ElementRef, HostListener } from '@angular/core';
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
import { Chart, registerables } from 'chart.js';
import { format, subDays, startOfMonth, endOfMonth, subMonths, startOfYear, subYears } from 'date-fns';

Chart.register(...registerables);

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatDialogModule, MatTabsModule, MatButtonModule, MatIconModule,
    MatSelectModule, MatFormFieldModule, MatInputModule, MatTooltipModule,
  ],
  template: `
    <div class="detail-dialog">
      <div class="detail-header">
        <div class="detail-title-area">
          <div class="detail-platform">
            <img [src]="getPlatformIconUrl(asset?.platform)" [alt]="asset?.platform" class="platform-icon-img" *ngIf="asset?.platform" />
            <span>{{ asset?.platform }}</span>
          </div>
          <h2>{{ asset?.ad_name || 'Unnamed Ad' }}</h2>
          <div class="metadata-chips" *ngIf="asset">
            <span class="chip" *ngFor="let m of assetMetaList">
              <span class="chip-key">{{ m.label }}:</span> {{ m.value }}
            </span>
          </div>
        </div>

        <div class="detail-controls">
          <div class="detail-date-picker" #detailDateRef>
            <button class="date-range-btn" (click)="toggleDatePicker()">
              <mat-icon>calendar_today</mat-icon>
              <span class="date-range-label">{{ dateRangeLabel }}</span>
              <mat-icon class="date-range-chevron">expand_more</mat-icon>
            </button>
            <div class="date-range-dropdown" *ngIf="datePickerOpen">
              <div class="date-presets">
                <button
                  *ngFor="let preset of datePresets"
                  class="preset-btn"
                  [class.active]="selectedPreset === preset.key"
                  (click)="selectPreset(preset.key)"
                >{{ preset.label }}</button>
              </div>
              <div class="date-custom" *ngIf="selectedPreset === 'custom'">
                <div class="custom-date-row">
                  <label>From</label>
                  <input type="date" [(ngModel)]="customFrom" class="custom-date-input" />
                </div>
                <div class="custom-date-row">
                  <label>To</label>
                  <input type="date" [(ngModel)]="customTo" class="custom-date-input" />
                </div>
                <button class="apply-btn" (click)="applyCustomRange()">Apply</button>
              </div>
            </div>
          </div>
        </div>

        <button mat-icon-button (click)="dialogRef.close()">
          <mat-icon>close</mat-icon>
        </button>
      </div>

      <mat-tab-group class="detail-tabs" *ngIf="!loading && asset">
        <mat-tab label="Performance">
          <div class="tab-content">
            <div class="perf-layout">
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
                <div class="chart-area">
                  <div class="chart-controls">
                    <span class="section-label">Performance Over Time</span>
                    <div class="kpi-selectors">
                      <mat-form-field appearance="outline" class="kpi-select" *ngFor="let i of [0,1,2]">
                        <mat-select [(ngModel)]="selectedKpis[i]" (selectionChange)="onKpiChange()">
                          <mat-option value="">None</mat-option>
                          <mat-option *ngFor="let k of availableKpis" [value]="k.value">{{ k.label }}</mat-option>
                        </mat-select>
                      </mat-form-field>
                    </div>
                  </div>
                  <div class="chart-container">
                    <canvas #chartCanvas></canvas>
                  </div>
                </div>

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

        <mat-tab label="Creative Effectiveness">
          <div class="tab-content">
            <div class="ce-layout">
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
                  <img
                    *ngIf="activeOverlay !== 'none'"
                    src="/assets/images/heatmap_dummy.png"
                    class="heatmap-overlay"
                    alt="Heatmap"
                  />
                </div>
              </div>

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
    .detail-platform {
      display: flex; align-items: center; gap: 6px;
      font-size: 12px; color: var(--text-muted);
      margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;
    }
    .platform-icon-img { width: 18px; height: 18px; object-fit: contain; }
    .detail-title-area h2 { margin-bottom: 8px; }

    .metadata-chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .chip { background: var(--bg-hover); padding: 2px 10px; border-radius: 20px; font-size: 11px; color: var(--text-secondary); }
    .chip-key { color: var(--text-muted); }

    .detail-controls { display: flex; gap: 8px; }

    .detail-date-picker { position: relative; }

    .date-range-btn {
      display: flex; align-items: center; gap: 8px;
      padding: 6px 12px; border-radius: 8px;
      border: 1px solid var(--border); background: var(--bg-card);
      color: var(--text-primary); cursor: pointer;
      font-size: 13px; font-weight: 500; height: 36px;
      transition: all var(--transition); white-space: nowrap;
      mat-icon { font-size: 18px; width: 18px; height: 18px; color: var(--accent); }
      .date-range-chevron { font-size: 16px; width: 16px; height: 16px; color: var(--text-secondary); }
      &:hover { border-color: var(--accent); background: var(--bg-hover); }
    }

    .date-range-dropdown {
      position: absolute; top: calc(100% + 4px); right: 0; z-index: 100;
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 12px; box-shadow: var(--shadow-lg);
      min-width: 220px; overflow: hidden;
      animation: dropIn 0.15s ease-out;
    }

    @keyframes dropIn {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .date-presets { display: flex; flex-direction: column; padding: 6px; }

    .preset-btn {
      padding: 8px 14px; border: none; background: transparent;
      color: var(--text-primary); font-size: 13px; text-align: left;
      border-radius: 6px; cursor: pointer; transition: all var(--transition);
      &:hover { background: var(--bg-hover); }
      &.active { background: var(--accent-light); color: var(--accent); font-weight: 600; }
    }

    .date-custom {
      padding: 8px 14px 14px; border-top: 1px solid var(--border);
      display: flex; flex-direction: column; gap: 8px;
    }

    .custom-date-row {
      display: flex; align-items: center; gap: 8px;
      label { font-size: 12px; color: var(--text-secondary); min-width: 36px; }
    }

    .custom-date-input {
      flex: 1; padding: 6px 10px; border: 1px solid var(--border);
      border-radius: 6px; background: var(--bg-primary); color: var(--text-primary);
      font-size: 13px; font-family: inherit;
      &:focus { outline: none; border-color: var(--accent); }
    }

    .apply-btn {
      padding: 8px 16px; border: none; border-radius: 6px;
      background: var(--accent); color: white; font-size: 13px; font-weight: 600;
      cursor: pointer; transition: background var(--transition);
      &:hover { background: var(--accent-hover); }
    }

    .detail-tabs { flex: 1; overflow: hidden; }
    .tab-content { padding: 20px; overflow-y: auto; max-height: calc(85vh - 160px); }
    .perf-layout { display: grid; grid-template-columns: 280px 1fr; gap: 20px; margin-bottom: 20px; }

    .asset-preview {
      position: relative; border-radius: 8px; overflow: hidden; background: var(--bg-hover);
    }
    .asset-media { width: 100%; display: block; object-fit: cover; max-height: 320px; }
    .ace-badge {
      position: absolute; bottom: 8px; right: 8px;
      padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700;
      &.ace-high   { background: rgba(46,204,113,0.85); color: white; }
      &.ace-medium { background: rgba(243,156,18,0.85);  color: white; }
      &.ace-low    { background: rgba(231,76,60,0.85);   color: white; }
    }

    .section-label {
      font-size: 11px; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 12px;
      display: flex; align-items: center; gap: 8px;
    }

    .chart-controls { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
    .kpi-selectors { display: flex; gap: 6px; }
    .kpi-select { width: 120px; }
    .chart-container { background: var(--bg-hover); border-radius: 8px; padding: 16px; min-height: 200px; position: relative; }

    .kpi-table { margin-top: 16px; }
    .kpi-table table { width: 100%; }
    .kpi-table tr { border-bottom: 1px solid var(--border); }
    .kpi-name { padding: 8px 0; font-size: 12px; color: var(--text-secondary); }
    .kpi-val { padding: 8px 0; font-size: 13px; font-weight: 600; text-align: right; }

    .campaigns-section { border-top: 1px solid var(--border); padding-top: 16px; }
    .campaigns-list { display: flex; flex-direction: column; gap: 6px; }
    .campaign-row {
      display: flex; align-items: center; gap: 8px; padding: 8px;
      background: var(--bg-hover); border-radius: 6px; font-size: 13px;
      mat-icon { font-size: 16px; color: var(--text-muted); }
    }
    .campaign-spend { margin-left: auto; font-weight: 600; }

    .ce-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .heatmap-toggles { display: flex; gap: 6px; margin-bottom: 12px; }
    .overlay-btn {
      padding: 4px 12px; border-radius: 20px; border: 1px solid var(--border);
      background: transparent; color: var(--text-secondary); font-size: 12px;
      cursor: pointer; transition: all var(--transition);
      &.active { background: var(--accent); border-color: var(--accent); color: white; }
    }
    .heatmap-container { position: relative; border-radius: 8px; overflow: hidden; }
    .heatmap-overlay { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; mix-blend-mode: multiply; opacity: 0.7; }

    .bs-kpi-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .bs-kpi-card { background: var(--bg-hover); border-radius: 8px; padding: 16px; text-align: center; }
    .bs-kpi-value {
      font-size: 28px; font-weight: 700; margin-bottom: 4px;
      &.ace-high { color: var(--success); }
      &.ace-medium { color: var(--warning); }
      &.ace-low { color: var(--error); }
    }
    .bs-kpi-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }

    .loading-state { padding: 24px; }
  `],
})
export class AssetDetailDialogComponent implements OnInit, OnDestroy {
  asset: any = null;
  detail: any = null;
  loading = true;

  dateFrom: string;
  dateTo: string;
  datePickerOpen = false;
  selectedPreset = 'last30';
  customFrom: string;
  customTo: string;

  datePresets = [
    { key: 'last7', label: 'Last 7 days' },
    { key: 'last30', label: 'Last 30 days' },
    { key: 'last90', label: 'Last 90 days' },
    { key: 'thisMonth', label: 'This month' },
    { key: 'lastMonth', label: 'Last month' },
    { key: 'thisYear', label: 'This year' },
    { key: 'lastYear', label: 'Last year' },
    { key: 'lifetime', label: 'Lifetime' },
    { key: 'custom', label: 'Custom range' },
  ];

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

  private chart: Chart | null = null;
  private chartColors = ['#FF7700', '#0009BC', '#2ECC71'];

  @ViewChild('chartCanvas') chartCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('detailDateRef') detailDateRef!: ElementRef;

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent) {
    if (this.datePickerOpen && this.detailDateRef && !this.detailDateRef.nativeElement.contains(event.target)) {
      this.datePickerOpen = false;
    }
  }

  constructor(
    private api: ApiService,
    public dialogRef: MatDialogRef<AssetDetailDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { assetId: string; dateFrom: string; dateTo: string },
  ) {
    this.dateFrom = data.dateFrom;
    this.dateTo = data.dateTo;
    this.customFrom = data.dateFrom;
    this.customTo = data.dateTo;
  }

  ngOnInit(): void {
    this.loadDetail();
  }

  ngOnDestroy(): void {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }

  get dateRangeLabel(): string {
    const preset = this.datePresets.find(p => p.key === this.selectedPreset);
    if (preset && this.selectedPreset !== 'custom') return preset.label;
    const from = new Date(this.dateFrom + 'T00:00:00');
    const to = new Date(this.dateTo + 'T00:00:00');
    const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
    return `${from.toLocaleDateString('en-US', opts)} – ${to.toLocaleDateString('en-US', opts)}`;
  }

  toggleDatePicker(): void {
    this.datePickerOpen = !this.datePickerOpen;
  }

  selectPreset(key: string): void {
    this.selectedPreset = key;
    const today = new Date();
    const yesterday = subDays(today, 1);

    switch (key) {
      case 'last7':
        this.dateFrom = format(subDays(today, 7), 'yyyy-MM-dd');
        this.dateTo = format(yesterday, 'yyyy-MM-dd');
        break;
      case 'last30':
        this.dateFrom = format(subDays(today, 30), 'yyyy-MM-dd');
        this.dateTo = format(yesterday, 'yyyy-MM-dd');
        break;
      case 'last90':
        this.dateFrom = format(subDays(today, 90), 'yyyy-MM-dd');
        this.dateTo = format(yesterday, 'yyyy-MM-dd');
        break;
      case 'thisMonth':
        this.dateFrom = format(startOfMonth(today), 'yyyy-MM-dd');
        this.dateTo = format(yesterday, 'yyyy-MM-dd');
        break;
      case 'lastMonth':
        const lastM = subMonths(today, 1);
        this.dateFrom = format(startOfMonth(lastM), 'yyyy-MM-dd');
        this.dateTo = format(endOfMonth(lastM), 'yyyy-MM-dd');
        break;
      case 'thisYear':
        this.dateFrom = format(startOfYear(today), 'yyyy-MM-dd');
        this.dateTo = format(yesterday, 'yyyy-MM-dd');
        break;
      case 'lastYear':
        const lastY = subYears(today, 1);
        this.dateFrom = format(startOfYear(lastY), 'yyyy-MM-dd');
        this.dateTo = format(new Date(lastY.getFullYear(), 11, 31), 'yyyy-MM-dd');
        break;
      case 'lifetime':
        this.dateFrom = '2020-01-01';
        this.dateTo = format(yesterday, 'yyyy-MM-dd');
        break;
      case 'custom':
        this.customFrom = this.dateFrom;
        this.customTo = this.dateTo;
        return;
    }
    this.datePickerOpen = false;
    this.loadDetail();
  }

  applyCustomRange(): void {
    if (this.customFrom && this.customTo) {
      this.dateFrom = this.customFrom;
      this.dateTo = this.customTo;
      this.datePickerOpen = false;
      this.loadDetail();
    }
  }

  onKpiChange(): void {
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
        setTimeout(() => this.renderChart(), 100);
      },
      error: () => { this.loading = false; },
    });
  }

  private renderChart(): void {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }

    if (!this.chartCanvas || !this.detail?.timeseries) return;

    const canvas = this.chartCanvas.nativeElement;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const activeKpis = this.selectedKpis.filter(Boolean);
    if (activeKpis.length === 0) return;

    const firstKpi = activeKpis[0];
    const tsData = this.detail.timeseries[firstKpi];
    if (!tsData || tsData.length === 0) return;

    const labels = tsData.map((d: any) => {
      const dt = new Date(d.date + 'T00:00:00');
      return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    const datasets = activeKpis.map((kpi: string, idx: number) => {
      const kpiData = this.detail.timeseries[kpi] || [];
      const kpiMeta = this.availableKpis.find(k => k.value === kpi);
      return {
        label: kpiMeta?.label || kpi,
        data: kpiData.map((d: any) => d.value),
        borderColor: this.chartColors[idx % this.chartColors.length],
        backgroundColor: this.chartColors[idx % this.chartColors.length] + '20',
        borderWidth: 2,
        pointRadius: tsData.length > 30 ? 0 : 3,
        pointHoverRadius: 5,
        fill: activeKpis.length === 1,
        tension: 0.3,
        yAxisID: `y${idx}`,
      };
    });

    const scales: any = {};
    activeKpis.forEach((kpi: string, idx: number) => {
      scales[`y${idx}`] = {
        position: idx === 0 ? 'left' : 'right',
        display: idx <= 1,
        grid: { display: idx === 0, color: 'rgba(255,255,255,0.06)' },
        ticks: {
          color: this.chartColors[idx % this.chartColors.length],
          font: { size: 10 },
          callback: (val: number) => {
            if (kpi === 'spend' || kpi === 'cpm') return '$' + val.toFixed(0);
            if (kpi === 'ctr' || kpi === 'vtr' || kpi === 'cvr') return val.toFixed(1) + '%';
            if (kpi === 'roas') return val.toFixed(1) + 'x';
            return val.toFixed(0);
          },
        },
      };
    });

    this.chart = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: activeKpis.length > 1,
            labels: { color: '#999', font: { size: 11 }, usePointStyle: true, pointStyle: 'circle' },
          },
          tooltip: {
            backgroundColor: '#1B1B1B',
            titleFont: { size: 12 },
            bodyFont: { size: 11 },
            padding: 10,
            cornerRadius: 8,
          },
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,0.06)' },
            ticks: { color: '#666', font: { size: 10 }, maxTicksLimit: 12, maxRotation: 0 },
          },
          ...scales,
        },
      },
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

  getPlatformIconUrl(platform: string): string {
    const urls: Record<string, string> = {
      META: '/assets/images/platform-meta.svg',
      TIKTOK: '/assets/images/platform-tiktok.svg',
      YOUTUBE: '/assets/images/platform-youtube.svg',
    };
    return urls[platform] || '';
  }

  getAceClass(score: number | null): string {
    if (!score) return 'ace-low';
    if (score >= 70) return 'ace-high';
    if (score >= 45) return 'ace-medium';
    return 'ace-low';
  }
}
