import { Component, Inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatTabsModule } from '@angular/material/tabs';
import { MatButtonModule } from '@angular/material/button';
import { MatTooltipModule } from '@angular/material/tooltip';
import { NgxEchartsDirective, provideEchartsCore } from 'ngx-echarts';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';
import { DateRangePickerComponent, DateRangeChange } from '../../../shared/components/date-range-picker.component';
import type { EChartsOption } from 'echarts';

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer]);

interface AssetDetailResponse {
  ad_account_id: string | null;
  platform: string;
  performer_tag: string | null;
  asset_format: string | null;
  video_duration: number | null;
  thumbnail_url: string | null;
  asset_url: string | null;
  ad_name: string | null;
  campaigns: { campaign_id: string; campaign_name: string; spend: number }[];
  campaigns_count: number;
  performance: any;
  timeseries: any;
  ace_score: number | null;
  brainsuite_metadata: any;
  campaign_objective: string | null;
  campaign_name: string | null;
  [key: string]: any;
}

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatDialogModule, MatTabsModule, MatButtonModule, MatTooltipModule,
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
            <img [src]="getPlatformIconUrl(asset?.platform || '')" [alt]="asset?.platform" class="platform-icon-img" *ngIf="asset?.platform" />
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
          <i class="bi bi-x-lg"></i>
        </button>
      </div>

      <mat-tab-group class="detail-tabs" *ngIf="!loading && asset">
        <mat-tab label="Performance">
          <div class="tab-content perf-tab">
            <div class="perf-tab-redesign">
              <!-- Top row: KPI chart tile + Creative Asset tile -->
              <div class="perf-top-row">
                <!-- KPI Trend Chart tile -->
                <div class="perf-kpi-tile">
                  <div class="chart-controls">
                    <h4>Performance Over Time</h4>
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

                <!-- Creative Asset tile -->
                <div class="perf-asset-tile">
                  <div class="perf-asset-header">
                    <span class="perf-asset-label">Creative Asset</span>
                    <span *ngIf="detail?.performer_tag" [class]="getPerformerTagClass(detail?.performer_tag || null)">
                      {{ detail?.performer_tag }}
                    </span>
                  </div>
                  <div class="perf-preview">
                    <img *ngIf="detail?.thumbnail_url" [src]="detail?.thumbnail_url" [alt]="detail?.ad_name || 'Asset'" />
                    <video *ngIf="!detail?.thumbnail_url && detail?.asset_url" [src]="detail?.asset_url" preload="metadata"></video>
                  </div>
                  <div class="perf-asset-meta">
                    <span class="perf-filename">{{ detail?.ad_name || 'Unnamed Asset' }}</span>
                    <span class="perf-duration" *ngIf="detail?.video_duration">
                      {{ detail?.video_duration | number:'1.0-0' }}s
                    </span>
                  </div>
                  <div class="perf-mini-tiles">
                    <div class="perf-mini-tile">
                      <span class="perf-mini-label">Spend</span>
                      <span class="perf-mini-value">{{ detail?.performance?.spend !== null && detail?.performance?.spend !== undefined ? ('$' + (detail?.performance?.spend | number:'1.2-2')) : '$0.00' }}</span>
                    </div>
                    <div class="perf-mini-tile">
                      <span class="perf-mini-label">Impressions</span>
                      <span class="perf-mini-value">{{ (detail?.performance?.impressions || 0) | number }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Performance Summary -->
              <div class="perf-summary">
                <h4>Performance Summary</h4>
                <ng-container *ngFor="let cat of metricCategories">
                  <div class="perf-summary-group" *ngIf="hasVisibleMetrics(cat)">
                    <div class="perf-category-header">
                      <i class="bi" [class]="cat.icon" [style.color]="cat.color"></i>
                      <span [style.color]="cat.color">{{ cat.name }}</span>
                    </div>
                    <div class="perf-metrics-grid">
                      <div class="perf-metric-row" *ngFor="let m of getVisibleMetrics(cat)">
                        <span class="metric-name">{{ m.label }}</span>
                        <span class="metric-value">{{ formatMetricValue(m.value, m.format) }}</span>
                      </div>
                    </div>
                  </div>
                </ng-container>
              </div>

              <!-- Campaigns section -->
              <div class="perf-campaigns" *ngIf="detail?.campaigns?.length">
                <h4>Used in {{ detail?.campaigns?.length }} campaign{{ detail?.campaigns?.length !== 1 ? 's' : '' }}</h4>
                <div class="perf-campaigns-list">
                  <div class="perf-campaign-row" *ngFor="let campaign of detail?.campaigns">
                    <span class="campaign-name">{{ campaign.campaign_name || 'Unknown Campaign' }}</span>
                    <a *ngIf="getCampaignUrl(campaign)"
                       [href]="getCampaignUrl(campaign)"
                       target="_blank" rel="noopener noreferrer"
                       [attr.aria-label]="'Open campaign in ' + detail?.platform + ' Ads Manager'"
                       class="campaign-link">
                      <i class="bi bi-box-arrow-up-right"></i>
                    </a>
                  </div>
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
                    *ngIf="activeOverlay !== 'none' || asset.asset_format !== 'VIDEO' || !asset.asset_url"
                    [src]="getBaseImage()"
                    class="asset-media"
                    alt="Creative"
                  />
                  <img
                    *ngIf="activeOverlay !== 'none'"
                    [src]="getOverlayImage()"
                    class="heatmap-overlay"
                    alt="Overlay"
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

    .detail-tabs { flex: 1; overflow: hidden; }
    .tab-content { padding: 20px; overflow-y: auto; height: calc(85vh - 160px); }
    .perf-tab { display: flex; flex-direction: column; }

    /* Performance tab redesign */
    .perf-tab-redesign {
      padding: 16px 0;
    }

    /* Top row: two-column grid */
    .perf-top-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 24px;
    }

    .perf-kpi-tile, .perf-asset-tile {
      background: var(--bg-card);
      border-radius: 8px;
      padding: 16px;
      border: 1px solid var(--border);
    }
    .perf-kpi-tile h4, .perf-asset-tile h4, .perf-summary h4, .perf-campaigns h4 {
      font-size: 16px;
      font-weight: 600;
      margin: 0 0 12px 0;
    }

    /* KPI tile */
    .chart-controls { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 8px; flex-wrap: wrap; gap: 8px; }
    .kpi-selectors { display: flex; gap: 6px; flex-wrap: wrap; }
    .kpi-native-select {
      padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border);
      background: var(--bg-hover); color: var(--text-primary);
      font-size: 12px; font-family: inherit; cursor: pointer;
    }
    .kpi-native-select:focus { outline: none; border-color: var(--accent); }

    .chart-container { background: var(--bg-hover); border-radius: 8px; overflow: hidden; }
    .echart-box { width: 100%; height: 200px; }

    .chart-empty {
      background: var(--bg-hover); border-radius: 8px; padding: 40px;
      text-align: center; color: var(--text-muted); font-size: 14px;
    }

    /* Creative Asset tile */
    .perf-asset-tile {
      padding: 12px;
    }
    .perf-asset-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    .perf-asset-label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .perf-asset-header .tile-tag {
      position: static;
      font-size: 12px;
      font-weight: 600;
      padding: 4px 8px;
      border-radius: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .perf-asset-header .tag-top {
      background: rgba(46, 204, 113, 0.15);
      color: #2ECC71;
    }
    .perf-asset-header .tag-below {
      background: rgba(231, 76, 60, 0.15);
      color: #E74C3C;
    }
    .perf-preview {
      margin-bottom: 8px;
    }
    .perf-preview img, .perf-preview video {
      width: 100%;
      max-height: 140px;
      object-fit: cover;
      border-radius: 4px;
    }
    .perf-asset-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    .perf-filename {
      font-size: 14px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 70%;
    }
    .perf-duration {
      font-size: 12px;
      color: var(--text-secondary);
    }
    .perf-mini-tiles {
      display: flex;
      gap: 12px;
    }
    .perf-mini-tile {
      flex: 1;
      background: var(--bg-primary);
      border-radius: 6px;
      padding: 8px;
    }
    .perf-mini-label {
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-secondary);
      text-transform: uppercase;
      margin-bottom: 4px;
    }
    .perf-mini-value {
      font-size: 14px;
      font-weight: 600;
    }

    /* Performance Summary */
    .perf-summary {
      margin-bottom: 24px;
    }
    .perf-summary-group {
      margin-bottom: 16px;
    }
    .perf-category-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
    .perf-category-header i {
      font-size: 16px;
    }
    .perf-category-header span {
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .perf-metrics-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
    }
    .perf-metric-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;
      border-bottom: 1px solid var(--border);
    }
    .perf-metric-row .metric-name {
      font-size: 14px;
      color: var(--text-secondary);
    }
    .perf-metric-row .metric-value {
      font-size: 14px;
      font-weight: 600;
    }

    /* Campaigns */
    .perf-campaigns {
      margin-top: 24px;
    }
    .perf-campaigns-list {
      display: flex;
      flex-direction: column;
    }
    .perf-campaign-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid var(--border);
    }
    .campaign-name {
      font-size: 14px;
    }
    .campaign-link {
      color: var(--text-secondary);
      font-size: 14px;
      text-decoration: none;
    }
    .campaign-link:hover {
      color: var(--accent);
    }

    /* Section label (used in CE tab) */
    .section-label {
      font-size: 11px; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 12px;
      display: flex; align-items: center; gap: 8px;
    }

    /* CE tab */
    .ce-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .heatmap-toggles { display: flex; gap: 6px; margin-bottom: 12px; }
    .overlay-btn {
      padding: 4px 12px; border-radius: 20px; border: 1px solid var(--border);
      background: transparent; color: var(--text-secondary); font-size: 12px;
      cursor: pointer; transition: all var(--transition);
    }
    .overlay-btn.active { background: var(--accent); border-color: var(--accent); color: white; }
    .heatmap-container { position: relative; border-radius: 8px; overflow: hidden; }
    .asset-media { width: 100%; display: block; object-fit: cover; max-height: 320px; }
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
  asset: AssetDetailResponse | null = null;
  detail: AssetDetailResponse | null = null;
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
    { key: 'none', label: 'Original', overlay: '' },
    { key: 'heatmap', label: 'Heatmap', overlay: '/assets/images/overlay_heatmap.png' },
    { key: 'fog', label: 'Fog Map', overlay: '/assets/images/overlay_fog.png' },
  ];

  chartOption: EChartsOption | null = null;
  chartMerge: EChartsOption = {};

  private chartColors = ['#FF7700', '#5B8FF9', '#5AD8A6'];

  readonly metricCategories: {
    name: string;
    icon: string;
    color: string;
    metrics: { key: string; label: string; format: 'currency' | 'number' | 'percent' | 'decimal' }[];
  }[] = [
    {
      name: 'Delivery',
      icon: 'bi-send',
      color: '#4285F4',
      metrics: [
        { key: 'spend', label: 'Spend', format: 'currency' },
        { key: 'impressions', label: 'Impressions', format: 'number' },
        { key: 'cpm', label: 'CPM', format: 'currency' },
        { key: 'reach', label: 'Reach', format: 'number' },
        { key: 'clicks', label: 'Clicks', format: 'number' },
        { key: 'frequency', label: 'Frequency', format: 'decimal' },
        { key: 'cpp', label: 'CPP', format: 'currency' },
        { key: 'cpc', label: 'CPC', format: 'currency' },
      ],
    },
    {
      name: 'Engagement',
      icon: 'bi-hand-thumbs-up',
      color: '#F39C12',
      metrics: [
        { key: 'ctr', label: 'CTR', format: 'percent' },
        { key: 'outbound_ctr', label: 'Outbound CTR', format: 'percent' },
        { key: 'unique_ctr', label: 'Unique CTR', format: 'percent' },
        { key: 'inline_link_click_ctr', label: 'Inline Link Click CTR', format: 'percent' },
        { key: 'outbound_clicks', label: 'Outbound Clicks', format: 'number' },
        { key: 'unique_clicks', label: 'Unique Clicks', format: 'number' },
        { key: 'inline_link_clicks', label: 'Inline Link Clicks', format: 'number' },
        { key: 'post_engagements', label: 'Post Engagements', format: 'number' },
        { key: 'likes', label: 'Likes', format: 'number' },
        { key: 'comments', label: 'Comments', format: 'number' },
        { key: 'shares', label: 'Shares', format: 'number' },
        { key: 'follows', label: 'Follows', format: 'number' },
      ],
    },
    {
      name: 'Conversions',
      icon: 'bi-arrow-repeat',
      color: '#2ECC71',
      metrics: [
        { key: 'roas', label: 'ROAS', format: 'decimal' },
        { key: 'purchase_roas', label: 'Purchase ROAS', format: 'decimal' },
        { key: 'cvr', label: 'CVR', format: 'percent' },
        { key: 'conversions', label: 'Conversions', format: 'number' },
        { key: 'cost_per_conversion', label: 'Cost per Result', format: 'currency' },
        { key: 'conversion_value', label: 'Conversion Value', format: 'currency' },
        { key: 'purchases', label: 'Purchases', format: 'number' },
        { key: 'purchase_value', label: 'Purchase Value', format: 'currency' },
        { key: 'leads', label: 'Leads', format: 'number' },
        { key: 'cost_per_lead', label: 'Cost per Lead', format: 'currency' },
        { key: 'app_installs', label: 'App Installs', format: 'number' },
        { key: 'cost_per_install', label: 'Cost per Install', format: 'currency' },
        { key: 'in_app_purchases', label: 'In-App Purchases', format: 'number' },
        { key: 'in_app_purchase_value', label: 'In-App Purchase Value', format: 'currency' },
      ],
    },
    {
      name: 'Video',
      icon: 'bi-play-circle',
      color: '#9C27B0',
      metrics: [
        { key: 'video_views', label: 'Video Views', format: 'number' },
        { key: 'vtr', label: 'VTR', format: 'percent' },
        { key: 'video_plays', label: 'Video Plays', format: 'number' },
        { key: 'video_3_sec_watched', label: '3-Sec Watched', format: 'number' },
        { key: 'video_30_sec_watched', label: '30-Sec Watched', format: 'number' },
        { key: 'video_p25', label: 'Video 25%', format: 'number' },
        { key: 'video_p50', label: 'Video 50%', format: 'number' },
        { key: 'video_p75', label: 'Video 75%', format: 'number' },
        { key: 'video_p100', label: 'Video 100%', format: 'number' },
        { key: 'video_completion_rate', label: 'Completion Rate', format: 'percent' },
        { key: 'thruplay', label: 'ThruPlay', format: 'number' },
        { key: 'cost_per_thruplay', label: 'Cost per ThruPlay', format: 'currency' },
        { key: 'trueview_views', label: 'TrueView Views', format: 'number' },
        { key: 'focused_view', label: 'Focused View', format: 'number' },
        { key: 'cost_per_focused_view', label: 'Cost per Focused View', format: 'currency' },
        { key: 'cost_per_view', label: 'Cost per View', format: 'currency' },
      ],
    },
    {
      name: 'Platform-Specific',
      icon: 'bi-grid',
      color: 'var(--text-secondary)',
      metrics: [
        { key: 'subscribe', label: 'Subscribe', format: 'number' },
        { key: 'offline_purchases', label: 'Offline Purchases', format: 'number' },
        { key: 'offline_purchase_value', label: 'Offline Purchase Value', format: 'currency' },
        { key: 'messaging_conversations_started', label: 'Messaging Conversations', format: 'number' },
        { key: 'estimated_ad_recallers', label: 'Estimated Ad Recallers', format: 'number' },
        { key: 'estimated_ad_recall_rate', label: 'Est. Ad Recall Rate', format: 'percent' },
      ],
    },
  ];

  get orgCurrency(): string {
    return this.auth.currentUser?.organization_currency || 'USD';
  }

  constructor(
    private api: ApiService,
    private auth: AuthService,
    public dialogRef: MatDialogRef<AssetDetailDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { assetId: string; dateFrom: string; dateTo: string; selectedPreset?: string; preloaded?: any },
  ) {
    this.dateFrom = data.dateFrom;
    this.dateTo = data.dateTo;
    if (data.selectedPreset) {
      this.selectedPreset = data.selectedPreset;
    }
  }

  ngOnInit(): void {
    if (this.data.preloaded) {
      this.detail = this.data.preloaded;
      this.asset = this.data.preloaded;
      this.loading = false;
      this.buildChart();
    } else {
      this.loadDetail();
    }
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
    this.api.get<AssetDetailResponse>(`/dashboard/assets/${this.data.assetId}`, {
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

  getVisibleMetrics(category: typeof this.metricCategories[0]): { key: string; label: string; format: string; value: any }[] {
    if (!this.detail?.performance) return [];
    return category.metrics
      .map(m => ({ ...m, value: (this.detail!.performance as any)[m.key] }))
      .filter(m => {
        // Zero spend is meaningful — show it
        if (m.key === 'spend') return m.value !== null && m.value !== undefined;
        // All other null/zero: omit
        return m.value !== null && m.value !== undefined && m.value !== 0;
      });
  }

  hasVisibleMetrics(category: typeof this.metricCategories[0]): boolean {
    return this.getVisibleMetrics(category).length > 0;
  }

  formatMetricValue(value: any, format: string): string {
    if (value === null || value === undefined) return '-';
    switch (format) {
      case 'currency':
        return '$' + Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      case 'number':
        return Number(value).toLocaleString('en-US');
      case 'percent':
        return Number(value).toFixed(1) + '%';
      case 'decimal':
        return Number(value).toFixed(2);
      default:
        return String(value);
    }
  }

  getCampaignUrl(campaign: any): string {
    const cid = campaign.campaign_id || '';
    const act = this.detail?.ad_account_id || '';
    switch ((this.detail?.platform || '').toLowerCase()) {
      case 'meta':
        return `https://www.facebook.com/adsmanager/manage/campaigns?act=${act}&campaign_ids=${cid}`;
      case 'tiktok':
        return `https://ads.tiktok.com/i18n/account/campaigns?keyword=${cid}`;
      case 'google_ads':
        return `https://ads.google.com/aw/campaigns?campaignId=${cid}`;
      case 'dv360':
        return `https://displayvideo.google.com/#ng_nav/p/${act}/c/${cid}`;
      default:
        return '';
    }
  }

  getPerformerTagClass(tag: string | null): string {
    if (tag === 'Top Performer') return 'tile-tag tag-top';
    if (tag === 'Below Average') return 'tile-tag tag-below';
    return '';
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
      const ts = this.detail!.timeseries[kpi];
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
          fontSize: 12,
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
        axisLabel: { color: '#999', fontSize: 12, rotate: 0, interval: 'auto' },
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

  getBaseImage(): string {
    if (this.asset?.thumbnail_url) return this.asset.thumbnail_url;
    if (this.asset?.asset_format !== 'VIDEO' && this.asset?.asset_url) return this.asset.asset_url;
    return '/assets/images/placeholder.svg';
  }

  getOverlayImage(): string {
    const match = this.heatmapOverlays.find(o => o.key === this.activeOverlay);
    return match?.overlay || '';
  }

  getPlatformIconUrl(platform: string): string {
    const urls: Record<string, string> = {
      META: '/assets/images/icon-meta.png',
      TIKTOK: '/assets/images/icon-tiktok.png',
      GOOGLE_ADS: '/assets/images/icon-google-ads.png',
      DV360: '/assets/images/icon-dv360.png',
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
