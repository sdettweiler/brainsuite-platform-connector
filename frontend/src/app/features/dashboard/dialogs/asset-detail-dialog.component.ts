import { Component, Inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatTabsModule } from '@angular/material/tabs';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { NgxEchartsDirective, provideEchartsCore } from 'ngx-echarts';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { ApiService } from '../../../core/services/api.service';
import { DateRangePickerComponent, DateRangeChange } from '../../../shared/components/date-range-picker.component';
import type { EChartsOption } from 'echarts';

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer]);

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatDialogModule, MatTabsModule, MatButtonModule, MatIconModule, MatTooltipModule,
    NgxEchartsDirective, DateRangePickerComponent,
  ],
  providers: [
    provideEchartsCore({ echarts }),
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
          <app-date-range-picker
            [dateFrom]="dateFrom"
            [dateTo]="dateTo"
            [selectedPreset]="selectedPreset"
            [dropUp]="false"
            (dateChange)="onDateRangeChange($event)"
          ></app-date-range-picker>
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
                  <div class="chart-container" *ngIf="chartOption">
                    <div echarts [options]="chartOption" [merge]="chartMerge" class="echart-box"></div>
                  </div>
                  <div class="chart-empty" *ngIf="!chartOption">
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
    :host { overflow: visible !important; }
    .detail-dialog { display: flex; flex-direction: column; height: 100%; background: var(--bg-card); overflow: visible; }

    .detail-header {
      display: flex; align-items: flex-start; gap: 16px;
      padding: 20px 24px; border-bottom: 1px solid var(--border); flex-shrink: 0;
      position: relative; z-index: 10; overflow: visible;
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

    .chart-container { background: var(--bg-hover); border-radius: 8px; overflow: hidden; }
    .echart-box { width: 100%; height: 260px; }

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
  selectedPreset = 'last30';

  selectedKpis = ['spend', 'ctr', 'roas'];
  activeOverlay = 'none';

  availableKpis = [
    { value: 'spend', label: 'Spend' },
    { value: 'impressions', label: 'Impressions' },
    { value: 'clicks', label: 'Clicks' },
    { value: 'ctr', label: 'CTR' },
    { value: 'cpm', label: 'CPM' },
    { value: 'roas', label: 'ROAS' },
    { value: 'conversions', label: 'Conversions' },
    { value: 'video_views', label: 'Video Views' },
    { value: 'vtr', label: 'VTR' },
    { value: 'cvr', label: 'CVR' },
  ];

  heatmapOverlays = [
    { key: 'none', label: 'Original' },
    { key: 'attention', label: 'Attention' },
    { key: 'heatmap', label: 'Heatmap' },
    { key: 'fog', label: 'Fog Map' },
  ];

  chartOption: EChartsOption | null = null;
  chartMerge: EChartsOption = {};

  private chartColors = ['#FF7700', '#5B8FF9', '#5AD8A6'];


  constructor(
    private api: ApiService,
    public dialogRef: MatDialogRef<AssetDetailDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { assetId: string; dateFrom: string; dateTo: string; selectedPreset?: string },
  ) {
    this.dateFrom = data.dateFrom;
    this.dateTo = data.dateTo;
    if (data.selectedPreset) {
      this.selectedPreset = data.selectedPreset;
    }
  }

  ngOnInit(): void {
    this.loadDetail();
  }

  ngOnDestroy(): void {}

  onDateRangeChange(event: DateRangeChange): void {
    this.dateFrom = event.dateFrom;
    this.dateTo = event.dateTo;
    this.selectedPreset = event.preset;
    this.loadDetail();
  }

  onKpiSelect(idx: number, value: string): void {
    this.selectedKpis = [...this.selectedKpis];
    this.selectedKpis[idx] = value;
    this.buildChart();
  }

  loadDetail(): void {
    const isFirstLoad = !this.detail;
    if (isFirstLoad) this.loading = true;
    this.api.get<any>(`/dashboard/assets/${this.data.assetId}`, {
      date_from: this.dateFrom,
      date_to: this.dateTo,
      kpis: 'spend,ctr,roas,cpm,video_views,vtr,conversions,cvr,impressions,clicks',
    }).subscribe({
      next: (d) => {
        this.detail = d;
        this.asset = d;
        this.loading = false;
        this.buildChart();
      },
      error: () => { this.loading = false; },
    });
  }

  private buildChart(): void {
    if (!this.detail?.timeseries) {
      this.chartOption = null;
      return;
    }

    const activeKpis = this.selectedKpis.filter(Boolean);
    if (activeKpis.length === 0) {
      this.chartOption = null;
      return;
    }

    const firstTs = this.detail.timeseries[activeKpis[0]];
    if (!firstTs || firstTs.length === 0) {
      this.chartOption = null;
      return;
    }

    const dates = firstTs.map((d: any) => {
      const dt = new Date(d.date + 'T00:00:00');
      return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    const yAxes: any[] = [];
    const series: any[] = [];

    activeKpis.forEach((kpi: string, idx: number) => {
      const ts = this.detail.timeseries[kpi];
      if (!ts) return;

      const kpiMeta = this.availableKpis.find(k => k.value === kpi);
      const label = kpiMeta?.label || kpi;
      const color = this.chartColors[idx % this.chartColors.length];

      yAxes.push({
        type: 'value',
        position: idx === 0 ? 'left' : 'right',
        offset: idx > 1 ? 60 : 0,
        show: idx <= 1,
        axisLine: { show: true, lineStyle: { color } },
        axisLabel: {
          color,
          fontSize: 10,
          formatter: (val: number) => this.formatKpiValue(kpi, val),
        },
        splitLine: { show: idx === 0, lineStyle: { color: 'rgba(128,128,128,0.15)' } },
      });

      series.push({
        name: label,
        type: 'line',
        yAxisIndex: idx,
        data: ts.map((d: any) => d.value),
        smooth: 0.3,
        symbol: ts.length > 30 ? 'none' : 'circle',
        symbolSize: 6,
        lineStyle: { color, width: 2 },
        itemStyle: { color },
        areaStyle: idx === 0 ? {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: color + '30' },
              { offset: 1, color: color + '05' },
            ],
          },
        } : undefined,
      });
    });

    const option: EChartsOption = {
      backgroundColor: 'transparent',
      grid: {
        left: 50, right: activeKpis.length > 1 ? 50 : 20,
        top: 30, bottom: activeKpis.length > 1 ? 50 : 30,
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1B1B1B',
        borderColor: '#333',
        textStyle: { color: '#fff', fontSize: 12, fontFamily: 'Nunito Sans' },
        formatter: (params: any) => {
          if (!Array.isArray(params)) return '';
          let html = `<div style="margin-bottom:4px;font-weight:600">${params[0].axisValue}</div>`;
          params.forEach((p: any) => {
            const kpiKey = activeKpis[p.seriesIndex];
            html += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
              <span>${p.seriesName}: <b>${this.formatKpiValue(kpiKey, p.value)}</b></span>
            </div>`;
          });
          return html;
        },
      },
      legend: {
        show: activeKpis.length > 1,
        bottom: 0,
        textStyle: { color: '#999', fontSize: 11, fontFamily: 'Nunito Sans' },
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: '#999', fontSize: 10, rotate: 0, interval: 'auto' },
        axisLine: { lineStyle: { color: 'rgba(128,128,128,0.2)' } },
        axisTick: { show: false },
      },
      yAxis: yAxes,
      series,
      dataZoom: firstTs.length > 30 ? [{
        type: 'inside',
        start: 0,
        end: 100,
      }] : [],
    };

    if (this.chartOption) {
      this.chartMerge = option;
    } else {
      this.chartOption = option;
    }
  }

  private formatKpiValue(kpi: string, val: number): string {
    if (val == null || isNaN(val)) return '—';
    if (kpi === 'spend') return '$' + val.toLocaleString('en-US', { maximumFractionDigits: 0 });
    if (kpi === 'cpm') return '$' + val.toFixed(2);
    if (kpi === 'ctr' || kpi === 'vtr' || kpi === 'cvr') return val.toFixed(2) + '%';
    if (kpi === 'roas') return val.toFixed(2) + 'x';
    if (kpi === 'impressions' || kpi === 'clicks' || kpi === 'conversions' || kpi === 'video_views') {
      return val.toLocaleString('en-US', { maximumFractionDigits: 0 });
    }
    return val.toFixed(2);
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
      { label: 'Impressions', value: p.impressions?.toLocaleString() || '0' },
      { label: 'Clicks', value: p.clicks?.toLocaleString() || '0' },
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
