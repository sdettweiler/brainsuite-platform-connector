import { Component, Inject, OnInit, OnDestroy, ViewChild, ElementRef, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatTabsModule } from '@angular/material/tabs';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../../core/services/api.service';
import { format, subDays, startOfMonth, endOfMonth, subMonths, startOfYear, subYears } from 'date-fns';

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatDialogModule, MatTabsModule, MatButtonModule, MatIconModule, MatTooltipModule,
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
                      <select class="kpi-native-select" *ngFor="let idx of [0,1,2]"
                        [ngModel]="selectedKpis[idx]"
                        (ngModelChange)="onKpiSelect(idx, $event)">
                        <option value="">None</option>
                        <option *ngFor="let k of availableKpis" [value]="k.value">{{ k.label }}</option>
                      </select>
                    </div>
                  </div>
                  <div class="chart-container" *ngIf="chartSeries.length > 0">
                    <svg [attr.viewBox]="'0 0 ' + chartWidth + ' ' + chartHeight" preserveAspectRatio="none" class="chart-svg">
                      <line *ngFor="let g of chartGridLines" [attr.x1]="0" [attr.y1]="g.y" [attr.x2]="chartWidth" [attr.y2]="g.y" class="chart-grid" />
                      <ng-container *ngFor="let series of chartSeries; let si = index">
                        <path *ngIf="si === 0" [attr.d]="series.areaPath" class="chart-area-fill" [style.fill]="series.color + '15'" />
                        <path [attr.d]="series.linePath" class="chart-line" [style.stroke]="series.color" />
                      </ng-container>
                    </svg>
                    <div class="chart-legend" *ngIf="chartSeries.length > 1">
                      <span *ngFor="let s of chartSeries" class="legend-item">
                        <span class="legend-dot" [style.background]="s.color"></span>
                        {{ s.label }}
                      </span>
                    </div>
                    <div class="chart-x-labels">
                      <span *ngFor="let lbl of chartXLabels" [style.left]="lbl.pct + '%'">{{ lbl.text }}</span>
                    </div>
                  </div>
                  <div class="chart-empty" *ngIf="chartSeries.length === 0">
                    No data available for this period
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
      display: flex; align-items: flex-start; gap: 16px;
      padding: 20px 24px; border-bottom: 1px solid var(--border); flex-shrink: 0;
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
    }
    .date-range-btn mat-icon { font-size: 18px; width: 18px; height: 18px; color: var(--accent); }
    .date-range-btn .date-range-chevron { font-size: 16px; width: 16px; height: 16px; color: var(--text-secondary); }
    .date-range-btn:hover { border-color: var(--accent); background: var(--bg-hover); }

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
    }
    .preset-btn:hover { background: var(--bg-hover); }
    .preset-btn.active { background: var(--accent-light); color: var(--accent); font-weight: 600; }

    .date-custom {
      padding: 8px 14px 14px; border-top: 1px solid var(--border);
      display: flex; flex-direction: column; gap: 8px;
    }
    .custom-date-row { display: flex; align-items: center; gap: 8px; }
    .custom-date-row label { font-size: 12px; color: var(--text-secondary); min-width: 36px; }
    .custom-date-input {
      flex: 1; padding: 6px 10px; border: 1px solid var(--border);
      border-radius: 6px; background: var(--bg-primary); color: var(--text-primary);
      font-size: 13px; font-family: inherit;
    }
    .custom-date-input:focus { outline: none; border-color: var(--accent); }

    .apply-btn {
      padding: 8px 16px; border: none; border-radius: 6px;
      background: var(--accent); color: white; font-size: 13px; font-weight: 600;
      cursor: pointer; transition: background var(--transition);
    }
    .apply-btn:hover { background: var(--accent-hover); }

    .detail-tabs { flex: 1; overflow: hidden; }
    .tab-content { padding: 20px; overflow-y: auto; max-height: calc(85vh - 160px); }
    .perf-layout { display: grid; grid-template-columns: 280px 1fr; gap: 20px; margin-bottom: 20px; }

    .asset-preview { position: relative; border-radius: 8px; overflow: hidden; background: var(--bg-hover); }
    .asset-media { width: 100%; display: block; object-fit: cover; max-height: 320px; }
    .ace-badge {
      position: absolute; bottom: 8px; right: 8px;
      padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700;
    }
    .ace-badge.ace-high   { background: rgba(46,204,113,0.85); color: white; }
    .ace-badge.ace-medium { background: rgba(243,156,18,0.85);  color: white; }
    .ace-badge.ace-low    { background: rgba(231,76,60,0.85);   color: white; }

    .section-label {
      font-size: 11px; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 12px;
      display: flex; align-items: center; gap: 8px;
    }

    .chart-controls { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
    .kpi-selectors { display: flex; gap: 6px; }
    .kpi-native-select {
      padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border);
      background: var(--bg-hover); color: var(--text-primary);
      font-size: 12px; font-family: inherit; cursor: pointer;
    }
    .kpi-native-select:focus { outline: none; border-color: var(--accent); }

    .chart-container {
      background: var(--bg-hover); border-radius: 8px; padding: 16px 16px 32px 40px;
      position: relative; height: 200px;
    }
    .chart-svg { width: 100%; height: 100%; display: block; }
    .chart-grid { stroke: rgba(255,255,255,0.06); stroke-width: 1; }
    .chart-area-fill { fill: rgba(255,119,0,0.1); }
    .chart-line { fill: none; stroke: #FF7700; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
    .chart-dot { fill: #FF7700; opacity: 0; }
    .chart-dot:hover { opacity: 1; }

    .chart-y-labels {
      position: absolute; left: 0; top: 16px; bottom: 32px; width: 36px;
      display: flex; flex-direction: column; justify-content: space-between;
    }
    .chart-y-labels span {
      font-size: 9px; color: var(--text-muted); text-align: right;
      position: absolute; right: 4px; transform: translateY(-50%);
    }

    .chart-x-labels {
      position: absolute; bottom: 8px; left: 40px; right: 16px; height: 16px;
    }
    .chart-x-labels span {
      position: absolute; font-size: 9px; color: var(--text-muted);
      transform: translateX(-50%); white-space: nowrap;
    }

    .chart-legend {
      display: flex; gap: 16px; justify-content: center; margin-top: 8px;
    }
    .legend-item { display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--text-secondary); }
    .legend-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

    .chart-empty {
      background: var(--bg-hover); border-radius: 8px; padding: 40px;
      text-align: center; color: var(--text-muted); font-size: 13px;
    }

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
    }
    .campaign-row mat-icon { font-size: 16px; color: var(--text-muted); }
    .campaign-spend { margin-left: auto; font-weight: 600; }

    .ce-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .heatmap-toggles { display: flex; gap: 6px; margin-bottom: 12px; }
    .overlay-btn {
      padding: 4px 12px; border-radius: 20px; border: 1px solid var(--border);
      background: transparent; color: var(--text-secondary); font-size: 12px;
      cursor: pointer; transition: all var(--transition);
    }
    .overlay-btn.active { background: var(--accent); border-color: var(--accent); color: white; }
    .heatmap-container { position: relative; border-radius: 8px; overflow: hidden; }
    .heatmap-overlay { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; mix-blend-mode: multiply; opacity: 0.7; }

    .bs-kpi-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .bs-kpi-card { background: var(--bg-hover); border-radius: 8px; padding: 16px; text-align: center; }
    .bs-kpi-value { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
    .bs-kpi-value.ace-high { color: var(--success); }
    .bs-kpi-value.ace-medium { color: var(--warning); }
    .bs-kpi-value.ace-low { color: var(--error); }
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

  chartWidth = 600;
  chartHeight = 160;
  chartSeries: { label: string; color: string; linePath: string; areaPath: string }[] = [];
  chartGridLines: { y: number; label: string }[] = [];
  chartXLabels: { pct: number; text: string }[] = [];
  private chartColors = ['#FF7700', '#0009BC', '#2ECC71'];

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

  ngOnDestroy(): void {}

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
      case 'lastMonth': {
        const lastM = subMonths(today, 1);
        this.dateFrom = format(startOfMonth(lastM), 'yyyy-MM-dd');
        this.dateTo = format(endOfMonth(lastM), 'yyyy-MM-dd');
        break;
      }
      case 'thisYear':
        this.dateFrom = format(startOfYear(today), 'yyyy-MM-dd');
        this.dateTo = format(yesterday, 'yyyy-MM-dd');
        break;
      case 'lastYear': {
        const lastY = subYears(today, 1);
        this.dateFrom = format(startOfYear(lastY), 'yyyy-MM-dd');
        this.dateTo = format(new Date(lastY.getFullYear(), 11, 31), 'yyyy-MM-dd');
        break;
      }
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

  loadDetail(): void {
    const isFirstLoad = !this.detail;
    if (isFirstLoad) this.loading = true;
    this.api.get<any>(`/dashboard/assets/${this.data.assetId}`, {
      date_from: this.dateFrom,
      date_to: this.dateTo,
      kpis: 'spend,ctr,roas,cpm,video_views,vtr,conversions',
    }).subscribe({
      next: (d) => {
        this.detail = d;
        this.asset = d;
        this.loading = false;
        this.buildChartData();
      },
      error: () => { this.loading = false; },
    });
  }

  onKpiSelect(idx: number, value: string): void {
    this.selectedKpis[idx] = value;
    this.buildChartData();
  }

  buildChartData(): void {
    this.chartSeries = [];
    this.chartGridLines = [];
    this.chartXLabels = [];

    if (!this.detail?.timeseries) return;

    const activeKpis = this.selectedKpis.filter(Boolean);
    if (activeKpis.length === 0) return;

    const firstTs = this.detail.timeseries[activeKpis[0]];
    if (!firstTs || firstTs.length === 0) return;

    const pad = 10;

    activeKpis.forEach((kpi: string, si: number) => {
      const ts = this.detail.timeseries[kpi];
      if (!ts || ts.length === 0) return;

      const values = ts.map((d: any) => d.value || 0);
      const maxVal = Math.max(...values, 0.001);
      const minVal = Math.min(...values, 0);
      const range = maxVal - minVal || 1;

      const points = values.map((v: number, i: number) => ({
        x: pad + (i / Math.max(ts.length - 1, 1)) * (this.chartWidth - pad * 2),
        y: pad + (1 - (v - minVal) / range) * (this.chartHeight - pad * 2),
      }));

      const linePath = 'M ' + points.map((p: any) => `${p.x},${p.y}`).join(' L ');
      const areaPath = linePath
        + ` L ${points[points.length - 1].x},${this.chartHeight - pad}`
        + ` L ${points[0].x},${this.chartHeight - pad} Z`;

      const kpiMeta = this.availableKpis.find(k => k.value === kpi);
      this.chartSeries.push({
        label: kpiMeta?.label || kpi,
        color: this.chartColors[si % this.chartColors.length],
        linePath,
        areaPath,
      });
    });

    const gridCount = 4;
    const primaryKpi = activeKpis[0];
    const primaryTs = this.detail.timeseries[primaryKpi];
    const primaryValues = primaryTs.map((d: any) => d.value || 0);
    const maxVal = Math.max(...primaryValues, 0.001);
    const minVal = Math.min(...primaryValues, 0);
    const range = maxVal - minVal || 1;

    for (let i = 0; i <= gridCount; i++) {
      const frac = i / gridCount;
      const y = pad + frac * (this.chartHeight - pad * 2);
      const val = maxVal - frac * range;
      let label = '';
      if (primaryKpi === 'spend' || primaryKpi === 'cpm') label = '$' + val.toFixed(0);
      else if (primaryKpi === 'ctr' || primaryKpi === 'vtr' || primaryKpi === 'cvr') label = val.toFixed(1) + '%';
      else if (primaryKpi === 'roas') label = val.toFixed(1) + 'x';
      else label = val.toFixed(0);
      this.chartGridLines.push({ y, label });
    }

    const labelCount = Math.min(firstTs.length, 6);
    const step = Math.max(1, Math.floor(firstTs.length / labelCount));
    for (let i = 0; i < firstTs.length; i += step) {
      const dt = new Date(firstTs[i].date + 'T00:00:00');
      this.chartXLabels.push({
        pct: (i / Math.max(firstTs.length - 1, 1)) * 100,
        text: dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      });
    }
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

  getPlatformIconUrl(platform: string): string {
    const urls: Record<string, string> = {
      META: '/assets/images/icon-meta.png',
      TIKTOK: '/assets/images/icon-tiktok.png',
      YOUTUBE: '/assets/images/icon-youtube.png',
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
