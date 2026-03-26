import { Component, Inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatTabsModule } from '@angular/material/tabs';
import { MatButtonModule } from '@angular/material/button';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDividerModule } from '@angular/material/divider';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { NgxEchartsDirective, provideEchartsCore } from 'ngx-echarts';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';
import { DateRangePickerComponent, DateRangeChange } from '../../../shared/components/date-range-picker.component';
import type { EChartsOption } from 'echarts';

interface AssetPerformanceDetail {
  spend: number | null;
  impressions: number | null;
  clicks: number | null;
  ctr: number | null;
  cpm: number | null;
  roas: number | null;
  video_views: number | null;
  vtr: number | null;
  conversions: number | null;
  cvr: number | null;
  reach: number | null;
  frequency: number | null;
  cpp: number | null;
  cpc: number | null;
  outbound_clicks: number | null;
  outbound_ctr: number | null;
  unique_clicks: number | null;
  unique_ctr: number | null;
  inline_link_clicks: number | null;
  inline_link_click_ctr: number | null;
  video_plays: number | null;
  video_3_sec_watched: number | null;
  video_30_sec_watched: number | null;
  video_p25: number | null;
  video_p50: number | null;
  video_p75: number | null;
  video_p100: number | null;
  video_completion_rate: number | null;
  cost_per_view: number | null;
  thruplay: number | null;
  cost_per_thruplay: number | null;
  focused_view: number | null;
  cost_per_focused_view: number | null;
  trueview_views: number | null;
  post_engagements: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  follows: number | null;
  conversion_value: number | null;
  cost_per_conversion: number | null;
  purchase_roas: number | null;
  purchases: number | null;
  purchase_value: number | null;
  leads: number | null;
  cost_per_lead: number | null;
  app_installs: number | null;
  cost_per_install: number | null;
  in_app_purchases: number | null;
  in_app_purchase_value: number | null;
  subscribe: number | null;
  offline_purchases: number | null;
  offline_purchase_value: number | null;
  messaging_conversations_started: number | null;
  estimated_ad_recallers: number | null;
  estimated_ad_recall_rate: number | null;
}

interface AssetTimeseriesPoint {
  date: string;
  value: number;
}

interface AssetBrainsuiteMetadata {
  attention_score?: number;
  brand_score?: number;
  emotion_score?: number;
  message_clarity?: number;
  visual_impact?: number;
}

interface AssetDetailResponse {
  id: string;
  platform: string;
  ad_id: string;
  ad_name: string | null;
  campaign_name: string | null;
  campaign_objective: string | null;
  asset_format: string | null;
  thumbnail_url: string | null;
  asset_url: string | null;
  total_score: number | null;
  total_rating: string | null;
  is_active: boolean;
  performance: AssetPerformanceDetail | null;
  performer_tag: string | null;
  campaigns_count: number;
  campaigns: Array<{ campaign_name?: string; campaign_id?: string; spend?: number }>;
  timeseries: Record<string, AssetTimeseriesPoint[]> | null;
  brainsuite_metadata?: AssetBrainsuiteMetadata;
}

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer]);

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatDialogModule, MatTabsModule, MatButtonModule, MatTooltipModule,
    MatProgressSpinnerModule, MatDividerModule, MatSnackBarModule,
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
            <img [src]="getPlatformIconUrl(asset!.platform)" [alt]="asset?.platform" class="platform-icon-img" *ngIf="asset?.platform" />
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
            <div class="perf-layout" #perfLayout>
              <div class="asset-col">
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
                  <div class="ace-badge" [class]="getAceClass(scoreDetail?.total_score)" *ngIf="scoreDetail?.total_score != null">
                    ACE: {{ scoreDetail.total_score | number:'1.0-0' }}
                  </div>
                </div>

                <div class="campaigns-section" *ngIf="detail?.campaigns?.length">
                  <div class="section-label">Used in {{ detail!.campaigns_count }} Campaign(s)</div>
                  <div class="campaigns-list">
                    <div class="campaign-row" *ngFor="let c of detail!.campaigns">
                      <i class="bi bi-megaphone" style="font-size: 14px;"></i>
                      <span>{{ c.campaign_name || c.campaign_id }}</span>
                      <span class="campaign-spend">{{ c.spend | currency:orgCurrency:'symbol':'1.0-0' }}</span>
                    </div>
                  </div>
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
                  <div class="kpi-scroll">
                    <ng-container *ngFor="let cat of kpiCategories">
                      <div class="kpi-category" *ngIf="cat.rows.length">
                        <div class="kpi-cat-label">{{ cat.label }}</div>
                        <table>
                          <tr *ngFor="let row of cat.rows">
                            <td class="kpi-name">{{ row.label }}</td>
                            <td class="kpi-val">{{ row.value }}</td>
                          </tr>
                        </table>
                      </div>
                    </ng-container>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </mat-tab>

        <mat-tab label="Creative Effectiveness">
          <div class="tab-content ce-tab">

            <!-- ── Loading spinner ── -->
            <div class="ce-state-center" *ngIf="scoreLoading">
              <mat-spinner diameter="32"></mat-spinner>
            </div>

            <!-- ── Pending / Processing ── -->
            <div class="ce-state-center"
              *ngIf="!scoreLoading && (scoreDetail?.scoring_status === 'PENDING' || scoreDetail?.scoring_status === 'PROCESSING')">
              <mat-spinner diameter="32"></mat-spinner>
              <p>BrainSuite is scoring this creative…</p>
            </div>

            <!-- ── Unscored / Failed ── -->
            <div class="ce-state-center"
              *ngIf="!scoreLoading && scoreDetail?.scoring_status !== 'COMPLETE' && scoreDetail?.scoring_status !== 'PENDING' && scoreDetail?.scoring_status !== 'PROCESSING'">
              <i class="bi bi-graph-up-arrow ce-empty-icon"></i>
              <ng-container *ngIf="scoreDetail?.scoring_status !== 'FAILED'">
                <h4>No score yet</h4>
                <p>This creative hasn't been scored. Click 'Score now' to send it to BrainSuite.</p>
              </ng-container>
              <ng-container *ngIf="scoreDetail?.scoring_status === 'FAILED'">
                <h4>Scoring failed</h4>
                <p>BrainSuite returned an error. Check your API credentials or try again.</p>
              </ng-container>
              <button mat-stroked-button color="primary" (click)="rescoreFromDialog()">Score now</button>
            </div>

            <!-- ══════════════════════════════════════════════════════
                 COMPLETE STATE — full ACE dashboard
            ══════════════════════════════════════════════════════ -->
            <ng-container *ngIf="!scoreLoading && scoreDetail?.scoring_status === 'COMPLETE'">

              <!-- ── Top action bar ── -->
              <div class="ce-action-bar">
                <span class="ce-scored-at" *ngIf="scoreDetail?.scored_at">
                  Scored {{ scoreDetail.scored_at | date:'MMM d, y' }}
                </span>
                <button class="ce-refetch-btn" (click)="refetchResults()" [disabled]="refetchLoading">
                  <mat-spinner *ngIf="refetchLoading" diameter="14" style="display:inline-block"></mat-spinner>
                  <i *ngIf="!refetchLoading" class="bi bi-arrow-clockwise"></i>
                  Re-fetch Results
                </button>
              </div>

              <!-- ── Section 1: ACE Score + Pillars ── -->
              <div class="ce-summary-row">

                <!-- ACE Donut -->
                <div class="ce-donut-panel">
                  <span class="ce-panel-label">Overall ACE Score</span>
                  <div class="ce-donut-wrap">
                    <svg class="ce-donut-svg" viewBox="0 0 120 120">
                      <circle class="donut-track" cx="60" cy="60" r="50"/>
                      <circle class="donut-fill"  cx="60" cy="60" r="50"
                        [style.stroke]="getScoreColor(scoreDetail.total_score, scoreDetail.total_rating)"
                        [style.stroke-dashoffset]="getDashOffset(scoreDetail.total_score)"/>
                    </svg>
                    <div class="donut-center">
                      <span class="donut-number">{{ scoreDetail.total_score | number:'1.0-0' }}</span>
                      <span class="donut-denom">/ 100</span>
                    </div>
                  </div>
                  <div class="ce-rating-badge"
                    [style.color]="getScoreColor(scoreDetail.total_score, scoreDetail.total_rating)"
                    [style.border-color]="getScoreColor(scoreDetail.total_score, scoreDetail.total_rating) + '40'">
                    <i class="bi" [ngClass]="getRatingIcon(scoreDetail.total_rating)"></i>
                    {{ formatRatingLabel(scoreDetail.total_rating) }}
                  </div>
                </div>

                <!-- 7 Pillar Cards -->
                <div class="ce-pillars-panel">
                  <span class="ce-panel-label">Effectiveness Pillars</span>
                  <div class="ce-pillars-grid">
                    <button class="ce-pillar-card"
                      *ngFor="let pillar of getCategories(); let i = index"
                      [class.ce-pillar-active]="selectedPillarIdx === i"
                      [class.ce-pillar-noclk]="isFormalMandatories(pillar.name)"
                      [style.--pillar-color]="getScoreColor(pillar.score, pillar.rating)"
                      (click)="onPillarClick(i, pillar.name)">
                      <div class="pillar-card-top">
                        <i class="bi" [ngClass]="getPillarIcon(pillar.name)"></i>
                        <span class="pillar-score"
                          [style.color]="getScoreColor(pillar.score, pillar.rating)">
                          {{ pillar.score != null ? (pillar.score | number:'1.0-0') : 'N/A' }}
                        </span>
                      </div>
                      <span class="pillar-name">{{ pillar.name }}</span>
                      <div class="pillar-bar-track">
                        <div class="pillar-bar-fill"
                          [style.width.%]="pillar.score ?? 0"
                          [style.background]="getScoreColor(pillar.score, pillar.rating)">
                        </div>
                      </div>
                    </button>
                  </div>
                </div>
              </div>

              <!-- ── Section 2: Video Preview + Active Pillar Panel ── -->
              <div class="ce-media-row" *ngIf="getCategories().length > 0">

                <!-- Video / Image Preview -->
                <div class="ce-media-panel">
                  <!-- View mode toggles -->
                  <div class="ce-viz-toggles">
                    <div class="ce-viz-toggle-group">
                      <button class="ce-viz-btn" [class.active]="ceVizMode === 'original'"
                        (click)="ceVizMode = 'original'">Original</button>
                      <ng-container *ngFor="let viz of getSelectedPillarVizModes(); trackBy: trackVizByKey">
                        <button class="ce-viz-btn" [class.active]="ceVizMode === viz.key"
                          (click)="ceVizMode = viz.key" [disabled]="!viz.url"
                          [class.ce-viz-disabled]="!viz.url"
                          [matTooltip]="viz.url ? '' : 'Visualization not available — click Re-fetch Results'">
                          {{ viz.label }}
                        </button>
                      </ng-container>
                    </div>
                  </div>

                  <!-- Media display -->
                  <div class="ce-media-container">
                    <!-- Original asset -->
                    <ng-container *ngIf="ceVizMode === 'original'">
                      <video *ngIf="assetIsVideo() && asset?.asset_url"
                        [src]="asset!.asset_url!" controls class="ce-media-asset"></video>
                      <img *ngIf="!assetIsVideo() || !asset?.asset_url"
                        [src]="asset?.asset_url || asset?.thumbnail_url || '/assets/images/placeholder.svg'"
                        class="ce-media-asset" alt="Creative"/>
                    </ng-container>
                    <!-- Visualization modes -->
                    <ng-container *ngIf="ceVizMode !== 'original'">
                      <ng-container *ngIf="getActiveViz() as viz">
                        <video *ngIf="viz.url && viz.type === 'video'" [src]="viz.url"
                          controls class="ce-media-asset"></video>
                        <img *ngIf="viz.url && viz.type !== 'video'" [src]="viz.url"
                          class="ce-media-asset" alt="Visualization"/>
                        <div *ngIf="!viz.url" class="ce-media-unavail">
                          <i class="bi bi-eye-slash"></i>
                          <p>Visualization not available</p>
                          <button mat-stroked-button (click)="refetchResults()">Re-fetch Results</button>
                        </div>
                      </ng-container>
                      <!-- Fallback if key not matched -->
                      <div *ngIf="!getActiveViz()" class="ce-media-unavail">
                        <i class="bi bi-eye-slash"></i>
                        <p>Visualization not available</p>
                      </div>
                    </ng-container>
                  </div>
                </div>

                <!-- Formal Mandatories Panel (fixed — does not change with pillar selection) -->
                <div class="ce-pillar-detail-panel" *ngIf="getFormalMandatoriesCategory() as fmPillar">
                  <div class="ce-pillar-detail-header">
                    <div class="ce-pillar-detail-mini-donut">
                      <svg viewBox="0 0 60 60" class="mini-donut-svg">
                        <circle class="donut-track" cx="30" cy="30" r="24"/>
                        <circle class="donut-fill" cx="30" cy="30" r="24"
                          [style.stroke]="getScoreColor(fmPillar.score, fmPillar.rating)"
                          [style.stroke-dasharray]="150.8"
                          [style.stroke-dashoffset]="getMiniDashOffset(fmPillar.score)"/>
                      </svg>
                      <div class="mini-donut-center">
                        <span [style.color]="getScoreColor(fmPillar.score, fmPillar.rating)">
                          {{ fmPillar.score != null ? (fmPillar.score | number:'1.0-0') : '—' }}
                        </span>
                      </div>
                    </div>
                    <div>
                      <div class="ce-pillar-detail-title">{{ fmPillar.name }}</div>
                      <div class="ce-pillar-detail-rating"
                        [style.color]="getScoreColor(fmPillar.score, fmPillar.rating)">
                        {{ formatRatingLabel(fmPillar.rating) }}
                      </div>
                    </div>
                  </div>

                  <!-- KPI quick list (always Formal Mandatories) -->
                  <div class="ce-kpi-quick-list">
                    <div class="ce-kpi-quick-item" *ngFor="let kpi of getFormalMandatoriesKpiList()">
                      <i class="bi ce-kpi-status-icon"
                        [ngClass]="getKpiStatusIcon(kpi.rating)"
                        [style.color]="getScoreColor(kpi.score, kpi.rating)"></i>
                      <span class="ce-kpi-quick-name">{{ kpi.name }}</span>
                      <span class="ce-kpi-quick-score"
                        [style.color]="getScoreColor(kpi.score, kpi.rating)">
                        {{ kpi.score != null ? (kpi.score | number:'1.0-0') : '—' }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- ── Section 3: KPI Detail Cards ── -->
              <div class="ce-kpi-section" *ngIf="getSelectedPillarKpiList().length > 0">
                <span class="ce-panel-label">
                  {{ getCategories()[selectedPillarIdx]?.name }} — Sub-KPI Analysis
                </span>
                <div class="ce-kpi-cards-grid">
                  <div class="ce-kpi-card"
                    *ngFor="let kpi of getSelectedPillarKpiList()"
                    [class.kpi-card-negative]="kpi.rating === 'negative'"
                    [class.kpi-card-na]="kpi.rating === 'notAvailable'">
                    <div class="kpi-card-top">
                      <div class="kpi-card-icon-wrap"
                        [style.background]="getScoreColor(kpi.score, kpi.rating) + '18'">
                        <i class="bi" [ngClass]="getKpiStatusIcon(kpi.rating)"
                          [style.color]="getScoreColor(kpi.score, kpi.rating)"></i>
                      </div>
                      <div class="kpi-card-score-wrap">
                        <span class="kpi-card-score"
                          [style.color]="kpi.rating === 'notAvailable' ? 'var(--text-muted)' : getScoreColor(kpi.score, kpi.rating)">
                          {{ kpi.score != null ? (kpi.score | number:'1.0-0') : '—' }}
                        </span>
                        <span class="kpi-card-status"
                          [style.color]="getScoreColor(kpi.score, kpi.rating)">
                          {{ formatRatingLabel(kpi.rating) }}
                        </span>
                      </div>
                    </div>
                    <span class="kpi-card-name">{{ kpi.name }}</span>
                  </div>
                </div>
              </div>

            </ng-container>
            <!-- /COMPLETE -->

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
    .tab-content { padding: 20px; overflow: hidden; height: calc(92vh - 160px); }
    .perf-tab { display: flex; flex-direction: column; }
    .perf-layout { display: grid; grid-template-columns: 280px 1fr; gap: 20px; flex: 1; min-height: 0; }
    .asset-col { display: flex; flex-direction: column; }
    .asset-preview { flex-shrink: 0; }
    .campaigns-section { margin-top: auto; padding-top: 16px; }
    .perf-right { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }

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

    .chart-area { flex-shrink: 0; }
    .kpi-table { margin-top: 16px; display: flex; flex-direction: column; flex: 1; min-height: 0; overflow: hidden; }
    .kpi-scroll {
      overflow-y: auto; flex: 1; min-height: 0;
      scrollbar-width: thin; scrollbar-color: var(--border) transparent;
    }
    .kpi-scroll::-webkit-scrollbar { width: 4px; }
    .kpi-scroll::-webkit-scrollbar-track { background: transparent; }
    .kpi-scroll::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
    .kpi-category { margin-bottom: 8px; }
    .kpi-cat-label {
      font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px;
      color: var(--text-muted); padding: 8px 0 4px; border-bottom: 1px solid var(--border);
    }
    .kpi-table table { width: 100%; }
    .kpi-table tr { border-bottom: 1px solid var(--border); }
    .kpi-name { padding: 6px 0; font-size: 12px; color: var(--text-secondary); }
    .kpi-val { padding: 6px 0; font-size: 13px; font-weight: 600; text-align: right; }

    .campaigns-list { display: flex; flex-direction: column; gap: 6px; }
    .campaign-row {
      display: flex; align-items: center; gap: 8px; padding: 8px;
      background: var(--bg-hover); border-radius: 6px; font-size: 13px;
    }
    .campaign-row i.bi { font-size: 14px; color: var(--text-muted); }
    .campaign-spend { margin-left: auto; font-weight: 600; }

    /* ─── CE tab shell ─── */
    .ce-tab {
      display: flex; flex-direction: column; gap: 16px;
      overflow-y: auto; height: calc(92vh - 160px);
      scrollbar-width: thin; scrollbar-color: var(--border) transparent;
    }
    .ce-tab::-webkit-scrollbar { width: 4px; }
    .ce-tab::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

    /* ─── State screens (loading / pending / empty) ─── */
    .ce-state-center {
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      flex: 1; min-height: 260px; gap: 16px; text-align: center; color: var(--text-secondary);
    }
    .ce-empty-icon { font-size: 36px; color: var(--text-muted); }

    /* ─── Action bar ─── */
    .ce-action-bar {
      display: flex; align-items: center; justify-content: flex-end; gap: 12px;
      flex-shrink: 0;
    }
    .ce-scored-at { font-size: 11px; color: var(--text-muted); margin-right: auto; }
    .ce-refetch-btn {
      display: flex; align-items: center; gap: 6px;
      padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border);
      background: var(--bg-hover); color: var(--text-secondary);
      font-size: 12px; font-weight: 600; cursor: pointer;
      transition: all var(--transition); font-family: inherit;
    }
    .ce-refetch-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
    .ce-refetch-btn:disabled { opacity: 0.5; cursor: default; }

    /* ─── Panel label ─── */
    .ce-panel-label {
      display: block; font-size: 10px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.6px; color: var(--text-muted); margin-bottom: 12px;
    }

    /* ─── Section 1: Summary row ─── */
    .ce-summary-row {
      display: grid; grid-template-columns: 200px 1fr; gap: 16px;
      flex-shrink: 0; background: var(--bg-hover); border-radius: 10px; padding: 16px;
    }

    /* Donut panel */
    .ce-donut-panel { display: flex; flex-direction: column; align-items: center; }
    .ce-donut-wrap { position: relative; width: 120px; height: 120px; margin: 8px 0; }
    .ce-donut-svg { width: 100%; height: 100%; transform: rotate(-90deg); }
    .donut-track {
      fill: none; stroke: var(--bg-card); stroke-width: 10;
    }
    .donut-fill {
      fill: none; stroke-width: 10; stroke-linecap: round;
      stroke-dasharray: 314.16; transition: stroke-dashoffset 0.6s ease, stroke 0.4s ease;
    }
    .donut-center {
      position: absolute; inset: 0; display: flex; flex-direction: column;
      align-items: center; justify-content: center; pointer-events: none;
    }
    .donut-number { font-size: 26px; font-weight: 800; line-height: 1; }
    .donut-denom { font-size: 10px; color: var(--text-muted); }
    .ce-rating-badge {
      display: flex; align-items: center; gap: 5px;
      padding: 3px 10px; border-radius: 20px; border: 1px solid;
      font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
      margin-top: 4px;
    }

    /* Pillars panel */
    .ce-pillars-panel { min-width: 0; }
    .ce-pillars-grid {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
    }
    .ce-pillar-card {
      background: var(--bg-card); border-radius: 8px; padding: 12px 10px;
      border: 1px solid var(--border); cursor: pointer; text-align: left;
      transition: all var(--transition); display: flex; flex-direction: column; gap: 8px;
      font-family: inherit;
    }
    .ce-pillar-card:hover { border-color: var(--pillar-color, var(--border)); background: var(--bg-primary); }
    .ce-pillar-card.ce-pillar-active {
      border-color: var(--accent); background: var(--bg-primary);
      box-shadow: 0 0 0 1px var(--accent);
    }
    .ce-pillar-card.ce-pillar-noclk { cursor: default; pointer-events: none; }
    .pillar-card-top {
      display: flex; justify-content: space-between; align-items: flex-start;
    }
    .pillar-card-top .bi { font-size: 17px; color: var(--text-muted); }
    .ce-pillar-active .pillar-card-top .bi { color: var(--accent); }
    .pillar-score { font-size: 21px; font-weight: 800; }
    .pillar-name { font-size: 11px; font-weight: 600; color: var(--text-secondary); line-height: 1.2; }
    .pillar-bar-track {
      height: 4px; background: var(--border); border-radius: 2px; overflow: hidden;
    }
    .pillar-bar-fill {
      height: 100%; border-radius: 2px; transition: width 0.5s ease;
    }

    /* ─── Section 2: Media + Active pillar ─── */
    .ce-media-row {
      display: grid; grid-template-columns: 1fr 260px; gap: 16px; flex-shrink: 0;
    }

    /* Media panel */
    .ce-media-panel {
      background: var(--bg-hover); border-radius: 10px; overflow: hidden;
      display: flex; flex-direction: column;
    }
    .ce-viz-toggles {
      padding: 8px 12px; display: flex; align-items: center; border-bottom: 1px solid var(--border);
    }
    .ce-viz-toggle-group { display: flex; gap: 4px; }
    .ce-viz-btn {
      padding: 4px 12px; border-radius: 20px; border: 1px solid transparent;
      background: transparent; color: var(--text-muted); font-size: 11px; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.4px; cursor: pointer;
      transition: all var(--transition); font-family: inherit;
    }
    .ce-viz-btn.active {
      background: rgba(255,119,0,0.15); border-color: rgba(255,119,0,0.4); color: var(--accent);
    }
    .ce-viz-btn.ce-viz-disabled { opacity: 0.4; cursor: not-allowed; }
    .ce-media-container {
      flex: 1; display: flex; align-items: center; justify-content: center;
      min-height: 200px; background: #111; position: relative;
    }
    .ce-media-asset {
      width: 100%; max-height: 390px; object-fit: contain; display: block;
    }
    .ce-media-unavail {
      display: flex; flex-direction: column; align-items: center; gap: 10px;
      color: var(--text-muted); font-size: 13px; padding: 24px; text-align: center;
    }
    .ce-media-unavail .bi { font-size: 28px; }

    /* Active pillar detail panel */
    .ce-pillar-detail-panel {
      background: var(--bg-hover); border-radius: 10px; padding: 14px;
      display: flex; flex-direction: column; gap: 12px; overflow: hidden;
    }
    .ce-pillar-detail-header { display: flex; align-items: center; gap: 12px; }
    .ce-pillar-detail-mini-donut { position: relative; width: 52px; height: 52px; flex-shrink: 0; }
    .mini-donut-svg { width: 100%; height: 100%; transform: rotate(-90deg); }
    .mini-donut-svg .donut-track { stroke-width: 6; }
    .mini-donut-svg .donut-fill  { stroke-width: 6; }
    .mini-donut-center {
      position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
      font-size: 13px; font-weight: 800;
    }
    .ce-pillar-detail-title { font-size: 13px; font-weight: 700; }
    .ce-pillar-detail-rating { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; margin-top: 2px; }

    .ce-kpi-quick-list { display: flex; flex-direction: column; gap: 6px; overflow-y: auto; flex: 1; }
    .ce-kpi-quick-item {
      display: flex; align-items: center; gap: 8px;
      padding: 6px 8px; background: var(--bg-card); border-radius: 6px;
    }
    .ce-kpi-status-icon { font-size: 13px; flex-shrink: 0; }
    .ce-kpi-quick-name { font-size: 11px; color: var(--text-secondary); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .ce-kpi-quick-score { font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; flex-shrink: 0; }

    /* ─── Section 3: KPI detail cards ─── */
    .ce-kpi-section { flex-shrink: 0; padding-bottom: 8px; }
    .ce-kpi-cards-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(161px, 1fr)); gap: 11px;
    }
    .ce-kpi-card {
      background: var(--bg-hover); border-radius: 9px; padding: 14px;
      border: 1px solid var(--border); display: flex; flex-direction: column; gap: 9px;
    }
    .ce-kpi-card.kpi-card-negative { border-color: rgba(231,76,60,0.25); }
    .ce-kpi-card.kpi-card-na { opacity: 0.55; }
    .kpi-card-top { display: flex; justify-content: space-between; align-items: flex-start; }
    .kpi-card-icon-wrap {
      width: 32px; height: 32px; border-radius: 7px;
      display: flex; align-items: center; justify-content: center;
    }
    .kpi-card-icon-wrap .bi { font-size: 16px; }
    .kpi-card-score-wrap { display: flex; flex-direction: column; align-items: flex-end; }
    .kpi-card-score { font-size: 21px; font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums; }
    .kpi-card-status { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; }
    .kpi-card-name {
      font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px;
      color: var(--text-secondary); line-height: 1.3;
    }

    .loading-state { padding: 24px; }
  `],
})
export class AssetDetailDialogComponent implements OnInit, OnDestroy {
  asset: AssetDetailResponse | null = null;
  detail: AssetDetailResponse | null = null;
  loading = true;

  scoreDetail: any = null;
  scoreLoading = true;

  dateFrom: string;
  dateTo: string;
  selectedPreset = 'last30';

  selectedKpis = ['spend', 'ctr', 'roas'];

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

  // CE tab state
  selectedPillarIdx = 0;
  ceVizMode = 'original';
  refetchLoading = false;

  chartOption: EChartsOption | null = null;
  chartMerge: EChartsOption = {};

  private chartColors = ['#FF7700', '#5B8FF9', '#5AD8A6'];


  get orgCurrency(): string {
    return this.auth.currentUser?.organization_currency || 'USD';
  }

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private snackBar: MatSnackBar,
    public dialogRef: MatDialogRef<AssetDetailDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { assetId: string; dateFrom: string; dateTo: string; selectedPreset?: string; preloaded?: AssetDetailResponse | null },
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
    this.loadScoreDetail();
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

    const timeseries = this.detail!.timeseries!;
    const firstTs = timeseries[activeKpis[0]];
    if (!firstTs || firstTs.length === 0) {
      this.chartOption = null;
      return;
    }

    const dates = firstTs.map((d: AssetTimeseriesPoint) => {
      const dt = new Date(d.date + 'T00:00:00');
      return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    const yAxes: any[] = [];
    const series: any[] = [];

    activeKpis.forEach((kpi: string, idx: number) => {
      const ts = timeseries[kpi];
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
        data: ts.map((d: AssetTimeseriesPoint) => d.value),
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

  get kpiCategories(): { label: string; rows: { label: string; value: string }[] }[] {
    const p = this.detail?.performance;
    if (!p) return [];

    const num = (v: any) => v != null && v !== undefined;
    const fmtInt = (v: any) => num(v) ? Number(v).toLocaleString() : null;
    const fmtDec = (v: any, d = 2) => num(v) ? Number(v).toFixed(d) : null;
    const fmtCur = (v: any, d = 2) => num(v) ? '$' + Number(v).toFixed(d) : null;
    const fmtPct = (v: any, d = 2) => num(v) ? Number(v).toFixed(d) + '%' : null;
    const fmtX = (v: any, d = 2) => num(v) ? Number(v).toFixed(d) + 'x' : null;

    const row = (label: string, value: string | null) => value ? { label, value } : null;

    const delivery = [
      row('Spend', fmtCur(p.spend, 0)),
      row('Impressions', fmtInt(p.impressions)),
      row('Reach', fmtInt(p.reach)),
      row('Frequency', fmtDec(p.frequency)),
      row('Clicks', fmtInt(p.clicks)),
      row('CTR', fmtPct(p.ctr)),
      row('CPM', fmtCur(p.cpm)),
      row('CPP', fmtCur(p.cpp)),
      row('CPC', fmtCur(p.cpc)),
      row('Outbound Clicks', fmtInt(p.outbound_clicks)),
      row('Outbound CTR', fmtPct(p.outbound_ctr)),
      row('Unique Clicks', fmtInt(p.unique_clicks)),
      row('Unique CTR', fmtPct(p.unique_ctr)),
      row('Inline Link Clicks', fmtInt(p.inline_link_clicks)),
      row('Inline Link Click CTR', fmtPct(p.inline_link_click_ctr)),
    ].filter(Boolean) as { label: string; value: string }[];

    const video = [
      row('Video Plays', fmtInt(p.video_plays)),
      row('Video Views', fmtInt(p.video_views)),
      row('VTR', fmtPct(p.vtr)),
      row('3-sec Watched', fmtInt(p.video_3_sec_watched)),
      row('30-sec Watched', fmtInt(p.video_30_sec_watched)),
      row('25% Watched', fmtInt(p.video_p25)),
      row('50% Watched', fmtInt(p.video_p50)),
      row('75% Watched', fmtInt(p.video_p75)),
      row('100% Watched', fmtInt(p.video_p100)),
      row('Completion Rate', fmtPct(p.video_completion_rate)),
      row('Cost per View', fmtCur(p.cost_per_view)),
      row('ThruPlay', fmtInt(p.thruplay)),
      row('Cost per ThruPlay', fmtCur(p.cost_per_thruplay)),
      row('Focused Views', fmtInt(p.focused_view)),
      row('Cost per Focused View', fmtCur(p.cost_per_focused_view)),
      row('TrueView Views', fmtInt(p.trueview_views)),
    ].filter(Boolean) as { label: string; value: string }[];

    const engagement = [
      row('Post Engagements', fmtInt(p.post_engagements)),
      row('Likes', fmtInt(p.likes)),
      row('Comments', fmtInt(p.comments)),
      row('Shares', fmtInt(p.shares)),
      row('Follows', fmtInt(p.follows)),
    ].filter(Boolean) as { label: string; value: string }[];

    const conversions = [
      row('Conversions', fmtInt(p.conversions)),
      row('Conversion Value', fmtCur(p.conversion_value)),
      row('CVR', fmtPct(p.cvr)),
      row('Cost per Conversion', fmtCur(p.cost_per_conversion)),
      row('ROAS', fmtX(p.roas)),
      row('Purchases', fmtInt(p.purchases)),
      row('Purchase Value', fmtCur(p.purchase_value)),
      row('Purchase ROAS', fmtX(p.purchase_roas)),
      row('Leads', fmtInt(p.leads)),
      row('Cost per Lead', fmtCur(p.cost_per_lead)),
      row('App Installs', fmtInt(p.app_installs)),
      row('Cost per Install', fmtCur(p.cost_per_install)),
      row('In-App Purchases', fmtInt(p.in_app_purchases)),
      row('In-App Purchase Value', fmtCur(p.in_app_purchase_value)),
      row('Subscribes', fmtInt(p.subscribe)),
      row('Offline Purchases', fmtInt(p.offline_purchases)),
      row('Offline Purchase Value', fmtCur(p.offline_purchase_value)),
      row('Messaging Conversations', fmtInt(p.messaging_conversations_started)),
    ].filter(Boolean) as { label: string; value: string }[];

    const quality = [
      row('Est. Ad Recallers', fmtInt(p.estimated_ad_recallers)),
      row('Est. Ad Recall Rate', fmtPct(p.estimated_ad_recall_rate)),
    ].filter(Boolean) as { label: string; value: string }[];

    return [
      { label: 'Delivery', rows: delivery },
      { label: 'Video', rows: video },
      { label: 'Engagement', rows: engagement },
      { label: 'Conversions', rows: conversions },
      { label: 'Quality & Recall', rows: quality },
    ];
  }

  loadScoreDetail(): void {
    this.scoreLoading = true;
    this.api.getScoreDetail(this.data.assetId).subscribe({
      next: (detail) => {
        this.scoreDetail = detail;
        this.scoreLoading = false;
      },
      error: () => {
        this.scoreLoading = false;
      },
    });
  }

  // ── CE: data helpers ──────────────────────────────────────────────────

  /** Fix data-path bug: score_dimensions IS the output object (legResults at root). */
  getCategories(): any[] {
    const legResults = this.scoreDetail?.score_dimensions?.legResults;
    if (!Array.isArray(legResults) || legResults.length === 0) return [];
    return legResults[0]?.executiveSummary?.categories ?? [];
  }

  /** KPIs for the selected pillar, filtered from legResults[0].kpis by category name. */
  getSelectedPillarKpiList(): any[] {
    const cat = this.getCategories()[this.selectedPillarIdx];
    if (!cat) return [];
    return this.getKpisForCategory(cat.name);
  }

  /** Returns the Formal Mandatories category object, or null if not present. */
  getFormalMandatoriesCategory(): any | null {
    return this.getCategories().find((c: any) =>
      this.isFormalMandatories(c.name)
    ) ?? null;
  }

  /** KPIs belonging to the Formal Mandatories category. */
  getFormalMandatoriesKpiList(): any[] {
    const cat = this.getFormalMandatoriesCategory();
    if (!cat) return [];
    return this.getKpisForCategory(cat.name);
  }

  private getKpisForCategory(catName: string): any[] {
    const allKpis = this.scoreDetail?.score_dimensions?.legResults?.[0]?.kpis;
    if (!allKpis || typeof allKpis !== 'object') return [];
    return (Object.values(allKpis) as any[]).filter(
      (kpi: any) => Array.isArray(kpi.categories) && kpi.categories.includes(catName)
    );
  }

  isFormalMandatories(name: string): boolean {
    const n = (name || '').toLowerCase();
    return n.includes('formal') || n.includes('mandator');
  }

  onPillarClick(i: number, name: string): void {
    if (this.isFormalMandatories(name)) return;
    this.selectedPillarIdx = i;
    this.ceVizMode = 'original';
  }

  /** Returns viz mode descriptors for the currently selected pillar's KPIs.
   *  Deduplicates by label — if the same label appears twice, only the last entry is kept.
   */
  getSelectedPillarVizModes(): { key: string; label: string; url: string | null; type: string }[] {
    const all: { key: string; label: string; url: string | null; type: string }[] = [];
    for (const kpi of this.getSelectedPillarKpiList()) {
      const vizs = kpi?.visualizations;
      if (!Array.isArray(vizs) || vizs.length === 0) continue;
      for (const vizItem of vizs) {
        if (all.length >= 8) break;
        all.push({
          key: `${kpi.name}_${vizItem?.type ?? 'viz'}_${all.length}`,
          label: kpi.name ?? 'View',
          url: vizItem?.url ?? null,
          type: vizItem?.type === 'movie' ? 'video' : (vizItem?.type ?? 'image'),
        });
      }
      if (all.length >= 8) break;
    }
    // Deduplicate by label — keep last occurrence (removes first duplicate)
    const seen = new Map<string, { key: string; label: string; url: string | null; type: string }>();
    for (const item of all) {
      seen.set(item.label, item);
    }
    const deduped = Array.from(seen.values());
    return deduped.slice(0, 4);
  }

  // ── CE: score color / formatting ───────────────────────────────────────

  getScoreColor(score: number | null, rating: string | null): string {
    const r = (rating || '').toLowerCase();
    if (r === 'positive') return 'var(--success)';
    if (r === 'medium')   return 'var(--warning)';
    if (r === 'negative') return 'var(--error)';
    // fallback by numeric score
    if (score == null) return 'var(--text-muted)';
    if (score >= 67) return 'var(--success)';
    if (score >= 34) return 'var(--warning)';
    return 'var(--error)';
  }

  formatRatingLabel(rating: string | null): string {
    switch ((rating || '').toLowerCase()) {
      case 'positive':     return 'Strong';
      case 'medium':       return 'Average';
      case 'negative':     return 'Needs work';
      case 'notavailable': return 'N/A';
      default:             return rating || '—';
    }
  }

  getRatingIcon(rating: string | null): string {
    switch ((rating || '').toLowerCase()) {
      case 'positive': return 'bi-check-circle-fill';
      case 'medium':   return 'bi-exclamation-circle-fill';
      case 'negative': return 'bi-x-circle-fill';
      default:         return 'bi-dash-circle';
    }
  }

  getKpiStatusIcon(rating: string | null): string {
    switch ((rating || '').toLowerCase()) {
      case 'positive': return 'bi-check-circle-fill';
      case 'negative': return 'bi-x-circle-fill';
      case 'medium':   return 'bi-dash-circle-fill';
      default:         return 'bi-dash-circle';
    }
  }

  getPillarIcon(name: string): string {
    const n = (name || '').toLowerCase();
    if (n.includes('formal') || n.includes('mandator')) return 'bi-exclamation-triangle-fill';
    if (n.includes('attention'))                          return 'bi-eye-fill';
    if (n.includes('brand'))                              return 'bi-tags-fill';
    if (n.includes('processing') || n.includes('ease'))  return 'bi-cpu-fill';
    if (n.includes('emotion') || n.includes('engagement')) return 'bi-heart-fill';
    if (n.includes('persuasion'))                         return 'bi-cart-fill';
    if (n.includes('strategic') || n.includes('fit'))    return 'bi-chat-quote-fill';
    return 'bi-bar-chart-fill';
  }

  /** Stroke-dashoffset for a 50r circle (circumference 314.16). */
  getDashOffset(score: number | null): number {
    const s = score ?? 0;
    return 314.16 * (1 - Math.min(Math.max(s, 0), 100) / 100);
  }

  /** Stroke-dashoffset for a 24r mini circle (circumference 150.8). */
  getMiniDashOffset(score: number | null): number {
    const s = score ?? 0;
    return 150.8 * (1 - Math.min(Math.max(s, 0), 100) / 100);
  }

  // ── CE: actions ────────────────────────────────────────────────────────

  rescoreFromDialog(): void {
    this.api.rescoreAsset(this.data.assetId).subscribe({
      next: () => {
        this.scoreDetail = { scoring_status: 'PENDING' };
        this.snackBar.open('Scoring queued — results in ~2 minutes', 'OK', { duration: 3000 });
      },
      error: () => {
        this.snackBar.open('Could not queue scoring. Try again.', 'OK', { duration: 3000 });
      },
    });
  }

  refetchResults(): void {
    this.refetchLoading = true;
    this.api.post<any>(`/scoring/${this.data.assetId}/refetch`, {}).subscribe({
      next: () => {
        this.refetchLoading = false;
        this.snackBar.open('Re-fetching results… check back in a moment.', 'OK', { duration: 4000 });
        // Poll once after 8 seconds to pick up fresh data
        setTimeout(() => this.loadScoreDetail(), 8000);
      },
      error: (err) => {
        this.refetchLoading = false;
        const msg = err?.error?.detail || 'Could not re-fetch. Try again.';
        this.snackBar.open(msg, 'OK', { duration: 4000 });
      },
    });
  }

  assetIsVideo(): boolean {
    const fmt = (this.asset?.asset_format || '').toUpperCase();
    return fmt === 'VIDEO' || fmt.includes('VIDEO');
  }

  getActiveViz(): { key: string; label: string; url: string | null; type: string } | null {
    return this.getSelectedPillarVizModes().find(v => v.key === this.ceVizMode) ?? null;
  }

  trackVizByKey(_: number, viz: { key: string }): string { return viz.key; }

  getBaseImage(): string {
    if (this.asset?.thumbnail_url) return this.asset.thumbnail_url;
    if (this.asset?.asset_format !== 'VIDEO' && this.asset?.asset_url) return this.asset.asset_url;
    return '/assets/images/placeholder.svg';
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
