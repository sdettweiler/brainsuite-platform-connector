import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ApiService } from '../../core/services/api.service';

interface AssetDetail {
  id: string;
  ad_name: string;
  platform: string;
  asset_format: string;
  thumbnail_url: string;
  asset_url?: string;
  campaign_name: string;
  objective?: string;
  ace_score?: number;
  ace_score_confidence?: string;
  brainsuite_metadata?: Record<string, any>;
  timeseries: Array<{
    date: string;
    spend: number;
    impressions: number;
    clicks: number;
    ctr: number;
    cpm: number;
    video_views?: number;
    vtr?: number;
    conversions?: number;
    roas?: number;
  }>;
  totals: {
    spend: number;
    impressions: number;
    clicks: number;
    ctr: number;
    cpm: number;
    video_views?: number;
    vtr?: number;
    conversions?: number;
    roas?: number;
  };
}

interface KpiOption {
  key: string;
  label: string;
  format: 'currency' | 'number' | 'percent' | 'decimal';
}

const PLATFORM_COLORS: Record<string, string> = {
  META: '#1877F2',
  TIKTOK: '#010101',
  YOUTUBE: '#FF0000',
};

const CHART_COLORS = ['#4285F4', '#EA4335', '#FBBC04', '#34A853'];

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatButtonModule, MatIconModule,
    MatSelectModule, MatFormFieldModule, MatInputModule,
    MatDatepickerModule, MatNativeDateModule, MatTooltipModule, MatProgressSpinnerModule,
  ],
  template: `
    <div class="comparison-page">
      <!-- Page Header -->
      <div class="page-header">
        <div class="header-left">
          <button mat-icon-button (click)="goBack()">
            <mat-icon>arrow_back</mat-icon>
          </button>
          <div>
            <h1>Asset Comparison</h1>
            <p class="subtitle">{{ assets.length }} assets selected</p>
          </div>
        </div>
        <div class="header-right">
          <!-- Date range -->
          <div class="date-range">
            <mat-form-field appearance="outline" class="date-field">
              <mat-label>From</mat-label>
              <input matInput [matDatepicker]="dpFrom" [(ngModel)]="dateFrom" (dateChange)="reload()" />
              <mat-datepicker-toggle matSuffix [for]="dpFrom"></mat-datepicker-toggle>
              <mat-datepicker #dpFrom></mat-datepicker>
            </mat-form-field>
            <mat-form-field appearance="outline" class="date-field">
              <mat-label>To</mat-label>
              <input matInput [matDatepicker]="dpTo" [(ngModel)]="dateTo" (dateChange)="reload()" />
              <mat-datepicker-toggle matSuffix [for]="dpTo"></mat-datepicker-toggle>
              <mat-datepicker #dpTo></mat-datepicker>
            </mat-form-field>
          </div>
        </div>
      </div>

      <!-- KPI Selector for chart -->
      <div class="kpi-bar">
        <span class="kpi-label">Chart metric:</span>
        <div class="kpi-tabs">
          <button
            *ngFor="let k of kpiOptions"
            class="kpi-tab"
            [class.active]="selectedKpi === k.key"
            (click)="selectedKpi = k.key; renderChart()"
          >{{ k.label }}</button>
        </div>
      </div>

      <!-- Loading -->
      <div *ngIf="loading" class="loading-state">
        <mat-spinner diameter="40"></mat-spinner>
        <span>Loading comparison data...</span>
      </div>

      <!-- Main comparison grid -->
      <div *ngIf="!loading" class="comparison-content">
        <!-- Asset header cards -->
        <div class="asset-headers">
          <!-- Empty corner for labels column -->
          <div class="corner-cell"></div>

          <div *ngFor="let asset of assets; let i = index" class="asset-header-card">
            <div class="asset-color-bar" [style.background]="chartColors[i]"></div>
            <div class="asset-thumb-wrapper">
              <img
                *ngIf="asset.thumbnail_url; else noThumb"
                [src]="asset.thumbnail_url"
                [alt]="asset.ad_name"
                class="asset-thumb"
                (error)="onThumbError($event)"
              />
              <ng-template #noThumb>
                <div class="thumb-placeholder">
                  <mat-icon>image_not_supported</mat-icon>
                </div>
              </ng-template>
              <div class="platform-badge" [style.background]="getPlatformColor(asset.platform)">
                {{ asset.platform.substring(0, 2) }}
              </div>
            </div>
            <div class="asset-header-info">
              <p class="asset-name" [matTooltip]="asset.ad_name">{{ asset.ad_name }}</p>
              <p class="asset-meta">{{ asset.asset_format }} &middot; {{ asset.campaign_name }}</p>
              <div class="ace-badge" *ngIf="asset.ace_score" [class]="getAceClass(asset.ace_score)">
                ACE {{ asset.ace_score }}
              </div>
            </div>
            <button mat-icon-button class="remove-btn" (click)="removeAsset(asset.id)" [matTooltip]="'Remove from comparison'">
              <mat-icon>close</mat-icon>
            </button>
          </div>
        </div>

        <!-- Chart Section -->
        <div class="chart-section">
          <div class="chart-label-col">
            <span>Daily {{ getKpiLabel(selectedKpi) }}</span>
          </div>
          <div class="chart-area">
            <canvas #chartCanvas class="comparison-chart"></canvas>
            <div class="chart-placeholder" *ngIf="!chartReady">
              <mat-spinner diameter="24"></mat-spinner>
            </div>
          </div>
        </div>

        <!-- KPI Comparison Table -->
        <div class="kpi-table-section">
          <div class="section-title">Performance Summary</div>
          <div class="kpi-table">
            <div class="kpi-table-header">
              <div class="metric-col">Metric</div>
              <div *ngFor="let asset of assets; let i = index" class="value-col">
                <div class="col-indicator" [style.background]="chartColors[i]"></div>
                <span class="col-name">{{ truncateName(asset.ad_name, 20) }}</span>
              </div>
            </div>

            <div *ngFor="let row of kpiRows" class="kpi-table-row" [class.highlighted]="row.highlight">
              <div class="metric-col">{{ row.label }}</div>
              <div *ngFor="let asset of assets; let i = index" class="value-col">
                <span class="kpi-value" [class.best]="isBest(row.key, asset.id, row.higher)">
                  {{ formatValue(row.key, asset.totals) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Brainsuite KPIs -->
        <div class="brainsuite-section" *ngIf="hasBrainsuiteData()">
          <div class="section-title">
            Brainsuite Creative Effectiveness
            <span class="dummy-badge">Simulated Data</span>
          </div>
          <div class="kpi-table">
            <div class="kpi-table-header">
              <div class="metric-col">Score</div>
              <div *ngFor="let asset of assets; let i = index" class="value-col">
                <div class="col-indicator" [style.background]="chartColors[i]"></div>
                <span class="col-name">{{ truncateName(asset.ad_name, 20) }}</span>
              </div>
            </div>

            <div *ngFor="let row of brainsuiteRows" class="kpi-table-row">
              <div class="metric-col">{{ row.label }}</div>
              <div *ngFor="let asset of assets" class="value-col">
                <div class="bs-score-bar">
                  <div class="bar-fill" [style.width]="getBsScore(asset, row.key) + '%'"
                    [style.background]="getBsColor(getBsScore(asset, row.key))"></div>
                  <span class="bar-label">{{ getBsScore(asset, row.key) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .comparison-page { padding: 24px; display: flex; flex-direction: column; gap: 20px; }

    .page-header {
      display: flex; align-items: flex-start; justify-content: space-between;
      h1 { font-size: 22px; font-weight: 700; margin: 0; }
      .subtitle { font-size: 13px; color: var(--text-secondary); margin: 4px 0 0; }
    }

    .header-left { display: flex; align-items: flex-start; gap: 12px; }
    .header-right { display: flex; align-items: center; gap: 12px; }
    .date-range { display: flex; align-items: center; gap: 8px; }
    .date-field { width: 160px; }

    .kpi-bar {
      display: flex; align-items: center; gap: 12px;
      padding: 12px 16px; background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 8px;
    }
    .kpi-label { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
    .kpi-tabs { display: flex; flex-wrap: wrap; gap: 4px; }
    .kpi-tab {
      padding: 4px 12px; border: 1px solid var(--border); border-radius: 20px;
      background: none; cursor: pointer; font-size: 12px; transition: all 0.15s;
      &:hover { border-color: var(--accent); }
      &.active { background: var(--accent); color: white; border-color: var(--accent); }
    }

    .loading-state {
      display: flex; flex-direction: column; align-items: center; gap: 16px;
      padding: 80px; color: var(--text-secondary); font-size: 14px;
    }

    .comparison-content { display: flex; flex-direction: column; gap: 20px; }

    /* Asset headers */
    .asset-headers {
      display: grid;
      grid-template-columns: 160px repeat(auto-fill, minmax(220px, 1fr));
      gap: 12px;
    }

    .corner-cell { /* spacer */ }

    .asset-header-card {
      position: relative; background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 10px; overflow: hidden; padding: 0 0 16px;
    }

    .asset-color-bar { height: 4px; }

    .asset-thumb-wrapper {
      position: relative; height: 120px;
    }

    .asset-thumb { width: 100%; height: 100%; object-fit: cover; }

    .thumb-placeholder {
      width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
      background: var(--bg-secondary);
      mat-icon { font-size: 32px; color: var(--text-muted); }
    }

    .platform-badge {
      position: absolute; top: 8px; right: 8px; width: 24px; height: 24px;
      border-radius: 50%; display: flex; align-items: center; justify-content: center;
      font-size: 9px; font-weight: 700; color: white;
    }

    .asset-header-info { padding: 10px 12px 0; }
    .asset-name {
      font-size: 13px; font-weight: 600; margin: 0 0 4px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .asset-meta { font-size: 11px; color: var(--text-secondary); margin: 0 0 8px; }

    .ace-badge {
      display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;
      &.ace-high { background: rgba(52,168,83,0.15); color: #34A853; }
      &.ace-medium { background: rgba(251,188,4,0.15); color: #F09300; }
      &.ace-low { background: rgba(234,67,53,0.15); color: #EA4335; }
    }

    .remove-btn { position: absolute; top: 8px; right: 8px; z-index: 2; }

    /* Chart */
    .chart-section {
      display: grid; grid-template-columns: 160px 1fr;
      background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px;
      overflow: hidden;
    }

    .chart-label-col {
      display: flex; align-items: center; justify-content: center;
      padding: 20px; border-right: 1px solid var(--border);
      span { font-size: 12px; color: var(--text-secondary); writing-mode: vertical-rl; transform: rotate(180deg); }
    }

    .chart-area { position: relative; padding: 20px; min-height: 280px; }

    .comparison-chart { width: 100%; height: 100%; }

    .chart-placeholder {
      position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    }

    /* KPI table */
    .kpi-table-section, .brainsuite-section {
      background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
    }

    .section-title {
      padding: 16px 20px; font-size: 14px; font-weight: 600;
      border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 10px;
    }

    .dummy-badge {
      font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 500;
      background: rgba(251,188,4,0.15); color: #F09300;
    }

    .kpi-table { overflow-x: auto; }

    .kpi-table-header, .kpi-table-row {
      display: grid;
      grid-template-columns: 160px repeat(auto-fill, minmax(180px, 1fr));
    }

    .kpi-table-header {
      background: var(--bg-secondary); padding: 0;
      > div { padding: 10px 16px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; color: var(--text-secondary); }
    }

    .kpi-table-row {
      border-top: 1px solid var(--border);
      &:hover { background: var(--bg-secondary); }
      &.highlighted { background: var(--accent-light); }
      > div { padding: 10px 16px; font-size: 13px; }
    }

    .metric-col { color: var(--text-secondary); font-size: 12px !important; }

    .value-col { display: flex; align-items: center; gap: 6px; }

    .col-indicator { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .col-name { font-size: 11px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .kpi-value {
      font-weight: 500; font-size: 13px;
      &.best { color: #34A853; font-weight: 700; }
    }

    /* Brainsuite bars */
    .bs-score-bar {
      display: flex; align-items: center; gap: 8px; width: 100%;
    }

    .bar-fill {
      height: 6px; border-radius: 3px; transition: width 0.4s;
    }

    .bar-label { font-size: 12px; font-weight: 500; white-space: nowrap; }
  `],
})
export class ComparisonComponent implements OnInit {
  assetIds: string[] = [];
  assets: AssetDetail[] = [];
  loading = true;
  chartReady = false;

  dateFrom: Date;
  dateTo: Date;
  selectedKpi = 'spend';

  chartColors = CHART_COLORS;

  kpiOptions: KpiOption[] = [
    { key: 'spend', label: 'Spend', format: 'currency' },
    { key: 'impressions', label: 'Impressions', format: 'number' },
    { key: 'clicks', label: 'Clicks', format: 'number' },
    { key: 'ctr', label: 'CTR', format: 'percent' },
    { key: 'cpm', label: 'CPM', format: 'currency' },
    { key: 'video_views', label: 'Video Views', format: 'number' },
    { key: 'vtr', label: 'VTR', format: 'percent' },
  ];

  kpiRows = [
    { key: 'spend', label: 'Spend', format: 'currency', higher: false, highlight: true },
    { key: 'impressions', label: 'Impressions', format: 'number', higher: true },
    { key: 'clicks', label: 'Clicks', format: 'number', higher: true },
    { key: 'ctr', label: 'CTR', format: 'percent', higher: true, highlight: true },
    { key: 'cpm', label: 'CPM', format: 'currency', higher: false },
    { key: 'video_views', label: 'Video Views', format: 'number', higher: true },
    { key: 'vtr', label: 'VTR', format: 'percent', higher: true },
    { key: 'conversions', label: 'Conversions', format: 'number', higher: true },
    { key: 'roas', label: 'ROAS', format: 'decimal', higher: true, highlight: true },
  ];

  brainsuiteRows = [
    { key: 'ace_score', label: 'ACE Score' },
    { key: 'attention_score', label: 'Attention Score' },
    { key: 'brand_score', label: 'Brand Score' },
    { key: 'emotion_score', label: 'Emotion Score' },
    { key: 'message_clarity', label: 'Message Clarity' },
    { key: 'visual_impact', label: 'Visual Impact' },
  ];

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private api: ApiService,
  ) {
    const now = new Date();
    this.dateTo = now;
    this.dateFrom = new Date(now.getTime() - 29 * 24 * 60 * 60 * 1000);
  }

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      const ids = params['assetIds'];
      if (ids) {
        this.assetIds = ids.split(',').filter((id: string) => id.trim());
        this.loadComparison();
      } else {
        this.loading = false;
      }
    });
  }

  loadComparison(): void {
    if (this.assetIds.length < 2) { this.loading = false; return; }
    this.loading = true;
    const df = this.formatDate(this.dateFrom);
    const dt = this.formatDate(this.dateTo);

    this.api.post<AssetDetail[]>('/dashboard/compare', {
      asset_ids: this.assetIds,
      date_from: df,
      date_to: dt,
    }).subscribe({
      next: (data) => {
        this.assets = data;
        this.loading = false;
        setTimeout(() => this.renderChart(), 100);
      },
      error: () => { this.loading = false; },
    });
  }

  reload(): void {
    this.loadComparison();
  }

  removeAsset(id: string): void {
    this.assetIds = this.assetIds.filter(a => a !== id);
    this.assets = this.assets.filter(a => a.id !== id);
    if (this.assets.length < 2) {
      this.router.navigate(['/dashboard']);
      return;
    }
    this.router.navigate([], { queryParams: { assetIds: this.assetIds.join(',') }, replaceUrl: true });
    setTimeout(() => this.renderChart(), 100);
  }

  renderChart(): void {
    // Lightweight SVG chart (no external dependency needed for MVP)
    this.chartReady = true;
    // In a full implementation, use Chart.js or ng2-charts here.
    // For MVP, we render a simple SVG line chart inline.
    const canvas = document.querySelector('.comparison-chart') as HTMLCanvasElement;
    if (!canvas || this.assets.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement?.getBoundingClientRect();
    if (!rect) return;

    canvas.width = rect.width * dpr;
    canvas.height = 260 * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = '260px';
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = 260;
    const pad = { top: 20, right: 20, bottom: 40, left: 60 };

    ctx.clearRect(0, 0, W, H);

    // Gather all dates
    const allDates = [...new Set(this.assets.flatMap(a => a.timeseries.map(t => t.date)))].sort();
    if (allDates.length === 0) return;

    const maxVal = Math.max(...this.assets.flatMap(a =>
      a.timeseries.map(t => (t as any)[this.selectedKpi] || 0)
    ));

    const xScale = (i: number) => pad.left + (i / (allDates.length - 1 || 1)) * (W - pad.left - pad.right);
    const yScale = (v: number) => pad.top + (1 - v / (maxVal || 1)) * (H - pad.top - pad.bottom);

    // Grid lines
    ctx.strokeStyle = 'rgba(128,128,128,0.15)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (i / 4) * (H - pad.top - pad.bottom);
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
    }

    // Lines
    this.assets.forEach((asset, idx) => {
      const color = this.chartColors[idx] || '#999';
      const data = allDates.map(date => {
        const point = asset.timeseries.find(t => t.date === date);
        return point ? (point as any)[this.selectedKpi] || 0 : 0;
      });

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.beginPath();
      data.forEach((v, i) => {
        const x = xScale(i);
        const y = yScale(v);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Dots at last point
      const lastX = xScale(data.length - 1);
      const lastY = yScale(data[data.length - 1]);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
      ctx.fill();
    });

    // X axis labels (first / last)
    ctx.fillStyle = 'rgba(128,128,128,0.8)';
    ctx.font = '11px system-ui';
    ctx.textAlign = 'left';
    ctx.fillText(allDates[0], pad.left, H - 8);
    ctx.textAlign = 'right';
    ctx.fillText(allDates[allDates.length - 1], W - pad.right, H - 8);

    this.chartReady = true;
  }

  formatValue(key: string, totals: any): string {
    const v = totals?.[key];
    if (v === null || v === undefined) return '—';
    const opt = this.kpiOptions.find(k => k.key === key) || this.kpiRows.find(k => k.key === key) as any;
    const fmt = opt?.format || 'number';
    if (fmt === 'currency') return '$' + this.formatNum(v);
    if (fmt === 'percent') return (v * 100).toFixed(2) + '%';
    if (fmt === 'decimal') return Number(v).toFixed(2) + 'x';
    return this.formatNum(v);
  }

  formatNum(v: number): string {
    if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
    if (v >= 1_000) return (v / 1_000).toFixed(1) + 'K';
    return Number(v).toFixed(0);
  }

  isBest(key: string, assetId: string, higherIsBetter = true): boolean {
    const values = this.assets.map(a => (a.totals as any)[key] ?? (higherIsBetter ? -Infinity : Infinity));
    const best = higherIsBetter ? Math.max(...values) : Math.min(...values);
    const asset = this.assets.find(a => a.id === assetId);
    const val = asset ? (asset.totals as any)[key] : null;
    return val !== null && val !== undefined && val === best;
  }

  getBsScore(asset: AssetDetail, key: string): number {
    if (key === 'ace_score') return asset.ace_score || 0;
    return asset.brainsuite_metadata?.[key] || 0;
  }

  getBsColor(score: number): string {
    if (score >= 70) return '#34A853';
    if (score >= 45) return '#FBBC04';
    return '#EA4335';
  }

  hasBrainsuiteData(): boolean {
    return this.assets.some(a => a.ace_score || a.brainsuite_metadata);
  }

  getAceClass(score?: number): string {
    if (!score) return '';
    if (score >= 70) return 'ace-high';
    if (score >= 45) return 'ace-medium';
    return 'ace-low';
  }

  getPlatformColor(platform: string): string {
    return PLATFORM_COLORS[platform] || '#888';
  }

  getKpiLabel(key: string): string {
    return this.kpiOptions.find(k => k.key === key)?.label || key;
  }

  truncateName(name: string, len: number): string {
    return name.length > len ? name.substring(0, len) + '…' : name;
  }

  formatDate(d: Date): string {
    return d.toISOString().split('T')[0];
  }

  onThumbError(event: Event): void {
    (event.target as HTMLImageElement).style.display = 'none';
  }

  goBack(): void {
    this.router.navigate(['/dashboard']);
  }
}
