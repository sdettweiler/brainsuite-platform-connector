import { Component, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule } from '@angular/material/menu';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { Subject, debounceTime, takeUntil, forkJoin, interval, switchMap } from 'rxjs';
import { NgxSliderModule, Options } from '@angular-slider/ngx-slider';
import { NgxEchartsDirective, provideEchartsCore } from 'ngx-echarts';
import * as echarts from 'echarts/core';
import { LineChart, ScatterChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatIconModule } from '@angular/material/icon';
import { OverlayModule } from '@angular/cdk/overlay';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { DateRangePickerComponent, DateRangeChange } from '../../shared/components/date-range-picker.component';
import { format, subDays } from 'date-fns';

echarts.use([LineChart, ScatterChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer]);

interface AssetPerformance {
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
}

interface DashboardAsset {
  id: string;
  platform: string;
  ad_id: string;
  ad_name: string | null;
  campaign_name: string | null;
  campaign_objective: string | null;
  asset_format: string | null;
  thumbnail_url: string | null;
  asset_url: string | null;
  scoring_status: string | null;
  total_score: number | null;
  total_rating: string | null;
  is_active: boolean;
  performance: AssetPerformance | null;
  performer_tag: string | null;
}

interface DashboardAssetsResponse {
  items: DashboardAsset[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface StatsResponse {
  total_spend: number;
  total_impressions: number;
  avg_roas: number | null;
  total_active_assets: number;
  new_assets_in_period: number;
  prev_total_spend: number | null;
  prev_total_impressions: number | null;
  prev_avg_roas: number | null;
  prev_total_active_assets: number | null;
}

interface CorrelationAsset {
  id: string;
  ad_name: string | null;
  platform: string;
  thumbnail_url: string | null;
  total_score: number;
  roas: number | null;
  spend: number | null;
  ctr: number | null;
  vtr: number | null;
  cpm: number | null;
  cvr: number | null;
  cpc: number | null;
  conversions: number | null;
}

@Component({
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule, FormsModule, MatButtonModule,
    MatSelectModule, MatFormFieldModule, MatInputModule, MatMenuModule,
    MatDialogModule, MatTooltipModule, MatCheckboxModule, DateRangePickerComponent,
    MatProgressSpinnerModule, MatSnackBarModule,
    NgxSliderModule,
    NgxEchartsDirective,
    MatSidenavModule,
    MatIconModule,
    OverlayModule,
  ],
  providers: [
    provideEchartsCore({ echarts }),
  ],
  template: `
    <div class="page-enter dashboard-page">
      <!-- Toolbar -->
      <div class="toolbar card card-sm">
        <!-- Date range picker -->
        <app-date-range-picker
          [dateFrom]="dateFrom"
          [dateTo]="dateTo"
          [selectedPreset]="selectedPreset"
          (dateChange)="onDateRangeChange($event)"
        ></app-date-range-picker>

        <!-- Platform filter -->
        <div class="platform-filters">
          <button
            *ngFor="let p of platforms"
            class="platform-btn"
            [class.active]="isPlatformActive(p.key)"
            (click)="togglePlatform(p.key)"
            [matTooltip]="p.label"
          >
            <img [src]="p.iconUrl" [alt]="p.label" class="platform-icon" />
          </button>
        </div>

        <!-- Format filter -->
        <mat-form-field appearance="outline" class="filter-field compact-select">
          <mat-label>Format</mat-label>
          <mat-select [(ngModel)]="selectedFormat" (selectionChange)="onFilterChange()">
            <mat-option value="">All</mat-option>
            <mat-option value="IMAGE">Image</mat-option>
            <mat-option value="VIDEO">Video</mat-option>
            <mat-option value="CAROUSEL">Carousel</mat-option>
          </mat-select>
        </mat-form-field>

        <!-- Sort -->
        <mat-form-field appearance="outline" class="filter-field compact-select">
          <mat-label>Sort by</mat-label>
          <mat-select [(ngModel)]="sortBy" (selectionChange)="onFilterChange()">
            <mat-option value="spend">Spend</mat-option>
            <mat-option value="ctr">CTR</mat-option>
            <mat-option value="roas">ROAS</mat-option>
            <mat-option value="cpm">CPM</mat-option>
            <mat-option value="vtr">VTR</mat-option>
            <mat-option value="total_score">ACE Score</mat-option>
            <mat-option value="platform">Platform</mat-option>
            <mat-option value="format">Format</mat-option>
          </mat-select>
        </mat-form-field>

        <button
          class="sort-dir-btn"
          mat-icon-button
          (click)="toggleSortOrder()"
          [matTooltip]="sortOrder === 'desc' ? 'Descending' : 'Ascending'"
        >
          <i class="bi" [ngClass]="sortOrder === 'desc' ? 'bi-arrow-down' : 'bi-arrow-up'"></i>
        </button>

        <!-- Score range filter (per D-01, D-02, D-04) -->
        <div class="score-slider-wrapper" [matTooltip]="sliderDisabled ? 'No scored creatives yet' : ''">
          <span class="slider-label">Score range</span>
          <ngx-slider
            [(value)]="scoreMin"
            [(highValue)]="scoreMax"
            [options]="sliderOptions"
            (userChangeEnd)="onScoreChange()"
          ></ngx-slider>
          <span class="slider-values">{{ scoreMin }} - {{ scoreMax }}</span>
        </div>

        <!-- Duration range filter -->
        <div class="duration-slider-wrapper" [hidden]="!hasAnyVideo"
             matTooltip="Filter by video duration">
          <span class="slider-label">Duration</span>
          <ngx-slider
            [(value)]="durationMin"
            [(highValue)]="durationMax"
            [options]="durationSliderOptions"
            (userChangeEnd)="onDurationChange()"
          ></ngx-slider>
          <span class="slider-values">{{ formatDuration(durationMin) }} - {{ formatDuration(durationMax) }}</span>
        </div>

        <!-- Metadata filter -->
        <div class="metadata-filter-trigger" cdkOverlayOrigin #filterOrigin="cdkOverlayOrigin">
          <button mat-stroked-button class="add-filter-btn" (click)="openFilterPopover()">
            <i class="bi bi-funnel"></i> Add Filter
            <span *ngIf="activeMetadataFilters.size > 0" class="filter-badge">{{ activeMetadataFilters.size }}</span>
          </button>
        </div>

        <!-- Filter popover (connected overlay) -->
        <ng-template cdkConnectedOverlay
          [cdkConnectedOverlayOrigin]="filterOrigin"
          [cdkConnectedOverlayOpen]="filterPopoverOpen"
          (overlayOutsideClick)="filterPopoverOpen = false"
          [cdkConnectedOverlayHasBackdrop]="true"
          cdkConnectedOverlayBackdropClass="cdk-overlay-transparent-backdrop">
          <div class="filter-popover">
            <!-- Step 1: Pick field -->
            <div *ngIf="filterPopoverStep === 'field'" class="filter-step">
              <div class="filter-step-header">Select metadata field</div>
              <button *ngFor="let field of metadataFields"
                class="filter-field-option"
                (click)="selectFilterField(field)">
                {{ field.label }}
                <span *ngIf="activeMetadataFilters.has(field.id)" class="filter-active-dot"></span>
              </button>
              <div *ngIf="metadataFields.length === 0" class="filter-empty">No metadata fields configured</div>
            </div>

            <!-- Step 2: Search/select values -->
            <div *ngIf="filterPopoverStep === 'value'" class="filter-step">
              <div class="filter-step-header">
                <button mat-icon-button (click)="filterPopoverStep = 'field'" class="filter-back-btn">
                  <i class="bi bi-arrow-left"></i>
                </button>
                {{ selectedFilterField?.label }}
              </div>
              <input class="filter-search-input"
                placeholder="Search values..."
                [(ngModel)]="filterValueSearch"
                (ngModelChange)="onFilterValueSearch($event)" />
              <div class="filter-values-list">
                <label *ngFor="let v of filteredFilterValues" class="filter-value-option">
                  <mat-checkbox
                    [checked]="pendingFilterSelections.has(v.value)"
                    (change)="toggleFilterValue(v.value)">
                    {{ v.label || v.value }}
                  </mat-checkbox>
                </label>
                <div *ngIf="filteredFilterValues.length === 0" class="filter-empty">No matching values</div>
              </div>
              <button mat-flat-button color="primary" class="filter-apply-btn"
                [disabled]="pendingFilterSelections.size === 0"
                (click)="confirmFilterSelection()">
                Apply ({{ pendingFilterSelections.size }})
              </button>
            </div>
          </div>
        </ng-template>

        <div class="toolbar-spacer"></div>

        <!-- Export button -->
        <button mat-stroked-button (click)="openExport()">
          <i class="bi bi-download"></i>
          Export
        </button>
      </div>

      <!-- Active metadata filter chips -->
      <div class="metadata-filter-chips" *ngIf="activeMetadataFilters.size > 0">
        <span *ngFor="let entry of activeMetadataFilters | keyvalue" class="metadata-filter-chip">
          {{ entry.value.fieldLabel }}: {{ entry.value.values.join(', ') }}
          <button class="chip-remove" (click)="removeMetadataFilter(entry.key)">
            <i class="bi bi-x"></i>
          </button>
        </span>
        <a class="clear-all-link" (click)="clearAllMetadataFilters()">Clear all</a>
      </div>

      <!-- Aggregate Stats -->
      <div class="agg-stats" *ngIf="stats">
        <div class="agg-stat" *ngFor="let s of aggStats; trackBy: trackAggStat"
             [class.agg-stat-clickable]="s.clickable"
             (click)="onAggStatClick(s)"
             [matTooltip]="s.clickable ? 'Explore score vs. ROAS correlation' : ''">
          <div class="agg-value">{{ s.value }}</div>
          <div class="agg-label">
            {{ s.label }}
            <i *ngIf="s.icon" [class]="'bi ' + s.icon" style="font-size:12px;color:var(--text-muted);margin-left:4px"></i>
          </div>
          <div class="agg-change" [class]="s.changeClass" *ngIf="s.change !== null">
            <i class="bi" [ngClass]="s.changeDir === 'arrow_upward' ? 'bi-arrow-up' : 'bi-arrow-down'"></i>
            {{ s.change }}
          </div>
        </div>
      </div>

      <!-- Score Trend Panel -->
      <div class="score-trend-panel card" *ngIf="!scoreTrendError || scoreTrendLoading">
        <div class="score-trend-header" (click)="scoreTrendCollapsed = !scoreTrendCollapsed" style="cursor:pointer;">
          <h4>Average BrainSuite Score</h4>
          <i class="bi" [class.bi-chevron-up]="!scoreTrendCollapsed" [class.bi-chevron-down]="scoreTrendCollapsed"></i>
        </div>
        <div *ngIf="!scoreTrendCollapsed">
          <!-- Loading skeleton -->
          <div *ngIf="scoreTrendLoading" class="score-trend-skeleton skeleton" style="height: 200px;"></div>
          <!-- Chart (2+ data points) -->
          <div *ngIf="!scoreTrendLoading && scoreTrendDataPoints >= 2"
               echarts [options]="scoreTrendOptions" class="echart-box" style="height: 200px;"></div>
          <!-- Empty state (< 2 data points) -->
          <div *ngIf="!scoreTrendLoading && scoreTrendDataPoints < 2" class="score-trend-empty">
            <i class="bi bi-graph-up"></i>
            <p>Not enough data yet</p>
            <p class="text-sm">Score trend appears after the first two scoring runs</p>
          </div>
        </div>
      </div>
      <!-- Error state -->
      <div class="score-trend-panel card score-trend-error" *ngIf="scoreTrendError && !scoreTrendLoading">
        <p>Could not load score data. Refresh to try again.</p>
      </div>

      <!-- Asset grid -->
      <div class="assets-section">
        <!-- Loading skeletons -->
        <div class="assets-grid" *ngIf="loading">
          <div class="asset-tile skeleton-tile" *ngFor="let s of [1,2,3,4,5,6,7,8]">
            <div class="skeleton" style="height: 180px; border-radius: 8px 8px 0 0;"></div>
            <div class="tile-body">
              <div class="skeleton" style="height: 12px; width: 80%; margin-bottom: 8px;"></div>
              <div class="skeleton" style="height: 10px; width: 50%;"></div>
            </div>
          </div>
        </div>

        <!-- Asset grid -->
        <div
          class="assets-grid"
          *ngIf="!loading"
          (contextmenu)="$event.preventDefault()"
        >
          <div
            class="asset-tile"
            *ngFor="let asset of assets"
            [class.selected]="isSelected(asset.id)"
            (click)="selectAsset($event, asset)"
            (dblclick)="openAssetDetail(asset)"
            (contextmenu)="onRightClick($event, asset)"
          >
            <!-- Thumbnail -->
            <div class="tile-thumb" [class.video-no-thumb]="isVideoNoThumb(asset)">
              <img
                *ngIf="getTileThumbnail(asset) as thumb"
                [src]="thumb"
                [alt]="asset.ad_name"
                (error)="onImgError($event)"
              />
              <!-- Fallback for video with no thumbnail (D-06) -->
              <div *ngIf="isVideoNoThumb(asset)" class="video-fallback">
                <img [src]="getPlatformOverlayIcon(asset.platform)" class="video-fallback-icon" alt="" />
                <span class="video-tag">VIDEO</span>
              </div>
              <!-- Overlays -->
              <span class="overlay-format">{{ asset.asset_format }}</span>
              <span class="overlay-platform">
                <img [src]="getPlatformOverlayIcon(asset.platform)" [alt]="asset.platform" class="overlay-platform-img" />
              </span>
              <!-- Score badge overlay -->
              <ng-container [ngSwitch]="asset.scoring_status">
                <ng-container *ngSwitchCase="'COMPLETE'">
                  <div class="overlay-ace ace-score" [class]="getScoreBadgeClass(asset.total_rating)"
                    [matTooltip]="getScoreTooltip(asset.total_rating)"
                    [attr.aria-label]="'Score: ' + asset.total_score + ', ' + asset.total_rating">
                    {{ asset.total_score | number:'1.0-0' }}
                  </div>
                </ng-container>
                <ng-container *ngSwitchCase="'PENDING'">
                  <div class="overlay-ace overlay-ace-pending" aria-label="Scoring in progress" [matTooltip]="'Scoring in progress'">
                    <mat-spinner diameter="20"></mat-spinner>
                    <span class="scoring-label">Scoring…</span>
                  </div>
                </ng-container>
                <ng-container *ngSwitchCase="'PROCESSING'">
                  <div class="overlay-ace overlay-ace-pending" aria-label="Scoring in progress" [matTooltip]="'Scoring in progress'">
                    <mat-spinner diameter="20"></mat-spinner>
                    <span class="scoring-label">Scoring…</span>
                  </div>
                </ng-container>
                <ng-container *ngSwitchCase="'FAILED'">
                  <div class="overlay-ace overlay-ace-dash" [matTooltip]="'Scoring failed'" aria-label="Scoring failed">
                    <span class="score-dash">–</span>
                  </div>
                </ng-container>
                <ng-container *ngSwitchCase="'UNSUPPORTED'">
                  <div class="overlay-ace overlay-ace-dash" [matTooltip]="'Image scoring not supported for this platform'" aria-label="Image scoring not supported">
                    <span class="score-dash">–</span>
                  </div>
                </ng-container>
                <ng-container *ngSwitchDefault>
                  <div class="overlay-ace overlay-ace-dash" aria-label="Not yet scored">
                    <span class="score-dash">–</span>
                  </div>
                </ng-container>
              </ng-container>
              <!-- Performer badge overlay (bottom-left) -->
              <div class="tile-tag" [class]="getTagClass(asset.performer_tag)"
                   *ngIf="asset.performer_tag"
                   [matTooltip]="getPerformerTooltip(asset.performer_tag)">
                {{ asset.performer_tag }}
              </div>
            </div>

            <!-- Tile body -->
            <div class="tile-body">
              <div class="tile-objective">{{ asset.campaign_objective || 'No objective' }}</div>
              <div class="tile-name">{{ asset.ad_name || 'Unnamed Ad' }}</div>
              <div class="tile-metrics">
                <span>
                  <span class="metric-label">Spend</span>
                  <span class="metric-value">{{ asset.performance?.spend | currency:orgCurrency:'symbol':'1.0-0' }}</span>
                </span>
                <span>
                  <span class="metric-label">CTR</span>
                  <span class="metric-value">{{ ((asset.performance?.ctr || 0) | number:'1.1-1') }}%</span>
                </span>
              </div>
              <div class="tile-roas" *ngIf="asset.performance?.roas">
                ROAS: <strong>{{ asset.performance?.roas | number:'1.1-2' }}x</strong>
              </div>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div class="pagination" *ngIf="!loading && totalPages > 1">
          <button mat-icon-button [disabled]="page === 1" (click)="changePage(page - 1)">
            <i class="bi bi-chevron-left"></i>
          </button>
          <span class="page-info">Page {{ page }} of {{ totalPages }} · {{ total | number }} assets</span>
          <button mat-icon-button [disabled]="page === totalPages" (click)="changePage(page + 1)">
            <i class="bi bi-chevron-right"></i>
          </button>
          <mat-form-field appearance="outline" class="page-size-field compact-select">
            <mat-select [(ngModel)]="pageSize" (selectionChange)="onPageSizeChange()">
              <mat-option [value]="25">25 / page</mat-option>
              <mat-option [value]="50">50 / page</mat-option>
              <mat-option [value]="100">100 / page</mat-option>
              <mat-option [value]="250">250 / page</mat-option>
            </mat-select>
          </mat-form-field>
        </div>
      </div>

      <!-- Context menu (positioned via CSS) -->
      <div class="context-menu" *ngIf="contextMenu.visible" [style.top.px]="contextMenu.y" [style.left.px]="contextMenu.x">
        <button (click)="openAssetDetail(contextMenu.asset!)">
          <i class="bi bi-box-arrow-up-right"></i> Open Report
        </button>
        <button (click)="openAssignProject(contextMenu.asset!)">
          <i class="bi bi-folder"></i> Assign to Project
        </button>
        <button [disabled]="selectedAssets.length < 2 || selectedAssets.length > 4" (click)="compareSelected()">
          <i class="bi bi-arrow-left-right"></i> Compare ({{ selectedAssets.length }})
        </button>
        <button (click)="openEditMetadata(contextMenu.asset!)">
          <i class="bi bi-tag"></i> Edit Metadata
        </button>
        <button (click)="copyAssetId(contextMenu.asset!)">
          <i class="bi bi-clipboard"></i> Copy Asset ID
        </button>
        <hr class="context-divider" />
        <button (click)="rescoreAsset(contextMenu.asset)">
          <i class="bi bi-lightning-charge"></i> Score now
        </button>
      </div>

      <!-- Backdrop to close context menu -->
      <div class="context-backdrop" *ngIf="contextMenu.visible" (click)="contextMenu.visible = false"></div>

      <!-- Correlation drawer backdrop -->
      <div class="correlation-backdrop" *ngIf="correlationDrawerOpen" (click)="closeCorrelationDrawer()"></div>

      <!-- Correlation drawer (fixed position overlay) -->
      <div class="correlation-drawer" [class.correlation-drawer-open]="correlationDrawerOpen">
        <!-- Drawer header -->
        <div class="correlation-drawer-header">
          <div style="display:flex;align-items:center;gap:12px">
            <h4 style="margin:0;white-space:nowrap">Score vs.</h4>
            <mat-form-field appearance="outline" class="compact-select" style="width:150px;margin:0">
              <mat-select [(ngModel)]="selectedCorrelationMetric" (ngModelChange)="buildScatterChart()">
                <mat-option *ngFor="let m of correlationMetrics" [value]="m.key">{{ m.label }}</mat-option>
              </mat-select>
            </mat-form-field>
          </div>
          <button mat-icon-button (click)="closeCorrelationDrawer()" aria-label="Close correlation drawer">
            <i class="bi bi-x" style="font-size:20px"></i>
          </button>
        </div>

        <!-- Spend threshold -->
        <div class="correlation-spend-row">
          <div class="correlation-spend-header">
            <span class="correlation-spend-label">Min. spend</span>
            <span class="correlation-spend-value">\${{ correlationMinSpend | number }}</span>
          </div>
          <ngx-slider
            [(value)]="correlationMinSpend"
            [options]="correlationMinSpendOptions"
            (userChangeEnd)="onCorrelationMinSpendChange()"
          ></ngx-slider>
        </div>

        <!-- Chart loading -->
        <div *ngIf="correlationLoading" class="skeleton" style="height:420px;margin:0 24px"></div>

        <!-- Chart error -->
        <div *ngIf="correlationError && !correlationLoading" class="correlation-empty">
          <i class="bi bi-exclamation-triangle" style="font-size:48px;color:var(--text-muted)"></i>
          <p>Could not load correlation data. Refresh to try again.</p>
        </div>

        <!-- Chart empty state -->
        <div *ngIf="!correlationLoading && !correlationError && correlationEligibleCount === 0" class="correlation-empty">
          <i class="bi bi-scatter" style="font-size:48px;color:var(--text-muted)"></i>
          <h4>No qualifying creatives to correlate</h4>
          <p>No scored creatives with {{ selectedMetricLabel }} data meet the current filters. Try lowering the minimum spend threshold or broadening the date range.</p>
        </div>

        <!-- Chart -->
        <div *ngIf="!correlationLoading && !correlationError && correlationEligibleCount > 0"
             echarts [options]="scatterOptions" (chartClick)="onScatterClick($event)"
             class="echart-box" style="height:420px;margin:0 24px"></div>

        <!-- Legend -->
        <div *ngIf="!correlationLoading && !correlationError && correlationEligibleCount > 0"
             class="correlation-legend">
          <span class="correlation-legend-item"><span class="legend-dot" style="background:#FF7700"></span> Stars</span>
          <span class="correlation-legend-item"><span class="legend-dot" style="background:#F39C12"></span> Workhorses</span>
          <span class="correlation-legend-item"><span class="legend-dot" style="background:#4285F4"></span> Question Marks</span>
          <span class="correlation-legend-item"><span class="legend-dot" style="background:#707070"></span> Laggards</span>
        </div>

        <!-- 99th pct annotation -->
        <div *ngIf="!correlationLoading && !correlationError && correlationEligibleCount > 0"
             class="correlation-cap-note">{{ selectedMetricLabel }} capped at 99th pct.</div>
      </div>
    </div>
  `,
  styles: [`
    .dashboard-page { position: relative; }

    .toolbar {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 16px;
    }

    .toolbar-group { display: flex; align-items: center; gap: 8px; }
    .toolbar-spacer { flex: 1; }


    .apply-btn {
      padding: 8px 16px;
      border: none;
      border-radius: 6px;
      background: var(--accent);
      color: white;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: background var(--transition);
      &:hover { background: var(--accent-hover); }
    }

    .filter-field { width: 130px; }

    .platform-filters { display: flex; gap: 4px; }
    .platform-btn {
      width: 36px; height: 36px;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: transparent;
      display: flex; align-items: center; justify-content: center;
      cursor: pointer; transition: all var(--transition);
      padding: 6px;
      &:hover { background: var(--bg-hover); }
      &.active { background: var(--accent-light); border-color: var(--accent); }
    }

    .platform-icon {
      width: 22px;
      height: 22px;
      object-fit: contain;
    }

    .sort-dir-btn { color: var(--text-secondary); }

    .agg-stats {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 20px;
    }

    .agg-stat {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--border-radius);
      padding: 16px;
    }

    .agg-value { font-size: 20px; font-weight: 700; }
    .agg-label { font-size: 11px; color: var(--text-secondary); margin-top: 2px; text-transform: uppercase; letter-spacing: 0.5px; }
    .agg-change {
      display: flex;
      align-items: center;
      gap: 2px;
      font-size: 11px;
      margin-top: 4px;
      i.bi { font-size: 11px; }
    }

    .assets-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 16px;
    }

    .asset-tile {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--border-radius-lg);
      overflow: hidden;
      cursor: pointer;
      transition: all var(--transition);
      user-select: none;

      &:hover {
        border-color: var(--accent);
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
      }

      &.selected {
        border-color: var(--accent);
        box-shadow: 0 0 0 2px rgba(255,119,0,0.3);
      }
    }

    .tile-thumb {
      position: relative;
      height: 160px;
      background: var(--bg-hover);
      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
    }

    .overlay-format {
      position: absolute; top: 6px; left: 6px;
      background: rgba(0,0,0,0.65);
      color: white; font-size: 9px; font-weight: 700;
      padding: 2px 6px; border-radius: 4px;
      text-transform: uppercase;
    }

    .overlay-platform {
      position: absolute; top: 6px; right: 6px;
      background: rgba(0,0,0,0.5);
      border-radius: 6px;
      width: 26px; height: 26px;
      display: flex; align-items: center; justify-content: center;
      padding: 4px;
    }

    .overlay-platform-img {
      width: 100%; height: 100%; object-fit: contain;
    }

    .overlay-ace {
      position: absolute; bottom: 6px; right: 6px;
      width: 36px; height: 36px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 12px; font-weight: 700;
    }

    .overlay-ace-pending {
      position: absolute; bottom: 6px; right: 6px;
      display: flex; align-items: center; gap: 4px;
      background: rgba(0,0,0,0.6); border-radius: 20px;
      padding: 4px 8px; width: auto; height: auto;
    }

    .overlay-ace-dash {
      position: absolute; bottom: 6px; right: 6px;
      width: 36px; height: 36px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      background: rgba(0,0,0,0.5);
    }

    .context-divider {
      border: none;
      border-top: 1px solid var(--border);
      margin: 4px 0;
    }

    .tile-body { padding: 12px; }
    .tile-objective { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
    .tile-name { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 8px; }

    .tile-metrics {
      display: flex; justify-content: space-between;
      margin-bottom: 6px;
    }
    .metric-label { font-size: 10px; color: var(--text-muted); display: block; }
    .metric-value { font-size: 13px; font-weight: 600; }

    .tile-roas { font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }

    .tile-tag {
      position: absolute;
      bottom: 8px;
      left: 8px;
      font-size: 12px;
      font-weight: 600;
      padding: 4px 8px;
      border-radius: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      z-index: 2;
      &.tag-top {
        background: rgba(46, 204, 113, 0.55);
        color: #ffffff;
        text-shadow: 0 1px 2px rgba(0,0,0,0.3);
      }
      &.tag-below {
        background: rgba(231, 76, 60, 0.55);
        color: #ffffff;
        text-shadow: 0 1px 2px rgba(0,0,0,0.3);
      }
    }

    .pagination {
      display: flex; align-items: center; justify-content: center;
      gap: 12px; margin-top: 24px;
    }
    .page-info { font-size: 13px; color: var(--text-secondary); }
    .page-size-field { width: 120px; }

    .context-menu {
      position: fixed;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--border-radius);
      box-shadow: var(--shadow-lg);
      z-index: 1000;
      min-width: 180px;
      overflow: hidden;

      button {
        width: 100%;
        display: flex; align-items: center; gap: 8px;
        padding: 10px 16px;
        background: none;
        border: none;
        cursor: pointer;
        font-size: 13px;
        color: var(--text-primary);
        text-align: left;
        transition: background var(--transition);
        i.bi { font-size: 14px; color: var(--text-secondary); }
        &:hover { background: var(--bg-hover); }
        &:disabled { opacity: 0.4; cursor: not-allowed; }
      }
    }

    .context-backdrop {
      position: fixed; inset: 0; z-index: 999;
    }

    .skeleton-tile { pointer-events: none; }

    .score-slider-wrapper {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 280px;
      max-width: 380px;
      padding: 0 8px;

      .slider-label {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-muted);
        white-space: nowrap;
      }

      .slider-values {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
        white-space: nowrap;
        min-width: 50px;
        text-align: center;
      }

      ngx-slider {
        flex: 1;
      }
    }

    .duration-slider-wrapper {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 260px;
      max-width: 340px;
      padding: 0 8px;

      .slider-label {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-muted);
        white-space: nowrap;
      }

      .slider-values {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
        white-space: nowrap;
        min-width: 60px;
        text-align: center;
      }

      ngx-slider {
        flex: 1;
      }
    }

    ::ng-deep .ngx-slider {
      .ngx-slider-pointer {
        width: 14px !important;
        height: 14px !important;
        top: -5px !important;
        background-color: #FFFFFF !important;
        border: 2px solid var(--accent) !important;
        border-radius: 50% !important;

        &::after { display: none !important; }
      }
      .ngx-slider-selection {
        background: var(--accent) !important;
      }
      .ngx-slider-bar {
        background: var(--border) !important;
        height: 4px !important;
      }
      .ngx-slider-bubble {
        background: var(--bg-card) !important;
        color: var(--text-primary) !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-size: 11px !important;
      }
      &.ngx-slider-disabled {
        opacity: 0.4 !important;
      }
    }

    .video-no-thumb {
      background: #111 !important;
    }

    .video-fallback {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
    }

    .video-fallback-icon {
      width: 48px !important;
      height: 48px !important;
      opacity: 0.6;
      object-fit: contain !important;
    }

    .video-tag {
      position: absolute;
      bottom: 6px;
      right: 6px;
      background: rgba(0, 0, 0, 0.65);
      color: white;
      font-size: 9px;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
    }

    .score-trend-panel {
      background: var(--bg-card);
      border-radius: 8px;
      padding: 16px;
      border: 1px solid var(--border);
      margin-bottom: 24px;
    }
    .score-trend-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .score-trend-header h4 {
      font-size: 16px;
      font-weight: 600;
      margin: 0;
    }
    .score-trend-empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 120px;
      color: var(--text-muted);
    }
    .score-trend-empty i {
      font-size: 32px;
      margin-bottom: 8px;
    }
    .score-trend-empty p {
      margin: 0;
    }
    .score-trend-empty .text-sm {
      font-size: 12px;
      margin-top: 4px;
    }
    .score-trend-error {
      text-align: center;
      padding: 24px;
      color: var(--text-secondary);
    }
    .score-trend-skeleton {
      border-radius: 4px;
    }

    .agg-stat-clickable {
      cursor: pointer;
      transition: all var(--transition);
    }
    .agg-stat-clickable:hover {
      border-color: var(--accent);
      box-shadow: var(--shadow-sm);
    }

    .correlation-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.4);
      z-index: 1000;
    }

    .correlation-drawer {
      position: fixed;
      top: 0;
      right: 0;
      height: 100vh;
      width: 728px;
      background: var(--bg-card);
      border-left: 1px solid var(--border);
      box-shadow: var(--shadow-lg);
      z-index: 1001;
      overflow-y: auto;
      transform: translateX(100%);
      transition: transform 200ms cubic-bezier(0.4, 0, 0.2, 1);
    }
    .correlation-drawer.correlation-drawer-open {
      transform: translateX(0);
    }

    .correlation-drawer-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 24px;
      border-bottom: 1px solid var(--border);
    }
    .correlation-drawer-header h4 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
    }

    .correlation-spend-row {
      padding: 12px 24px 0;
    }
    .correlation-spend-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
    }
    .correlation-spend-label {
      font-size: 13px;
      color: var(--text-muted);
    }
    .correlation-spend-value {
      font-size: 13px;
      font-weight: 600;
      color: var(--text-primary, #fff);
    }

    .correlation-empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 420px;
      text-align: center;
      padding: 0 24px;
      color: var(--text-muted);
    }
    .correlation-empty h4 {
      margin: 16px 0 8px;
    }
    .correlation-empty p {
      max-width: 300px;
    }

    .correlation-legend {
      display: flex;
      gap: 16px;
      padding: 16px 24px;
      flex-wrap: wrap;
    }
    .correlation-legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      color: var(--text-secondary);
    }
    .legend-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
    }

    .correlation-cap-note {
      text-align: right;
      font-size: 11px;
      color: var(--text-muted);
      padding: 0 24px 16px;
    }

    .correlation-drawer-header .mat-mdc-form-field {
      font-size: 14px;
    }
    .correlation-drawer-header .mat-mdc-form-field .mat-mdc-select-value {
      font-weight: 600;
    }

    .add-filter-btn {
      display: flex; align-items: center; gap: 4px;
      font-size: 13px; height: 36px;
      border-color: var(--border); color: var(--text-secondary);
    }
    .add-filter-btn .filter-badge {
      background: var(--accent); color: #fff; border-radius: 50%;
      width: 18px; height: 18px; font-size: 11px;
      display: inline-flex; align-items: center; justify-content: center;
    }
    .filter-popover {
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,.12);
      width: 280px; max-height: 400px; overflow: hidden;
    }
    .filter-step { display: flex; flex-direction: column; }
    .filter-step-header {
      padding: 12px 16px; font-weight: 600; font-size: 13px;
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; gap: 8px;
    }
    .filter-back-btn { width: 28px; height: 28px; }
    .filter-field-option {
      padding: 10px 16px; border: none; background: none;
      text-align: left; cursor: pointer; font-size: 13px;
      color: var(--text-primary); display: flex; align-items: center; justify-content: space-between;
    }
    .filter-field-option:hover { background: var(--bg-hover); }
    .filter-active-dot {
      width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
    }
    .filter-search-input {
      margin: 8px 12px; padding: 8px 12px;
      border: 1px solid var(--border); border-radius: 6px;
      font-size: 13px; background: var(--bg-input, var(--bg-card));
      color: var(--text-primary); outline: none;
    }
    .filter-search-input:focus { border-color: var(--accent); }
    .filter-values-list {
      max-height: 240px; overflow-y: auto; padding: 4px 0;
    }
    .filter-value-option {
      display: block; padding: 4px 16px; font-size: 13px; cursor: pointer;
    }
    .filter-value-option:hover { background: var(--bg-hover); }
    .filter-apply-btn { margin: 8px 12px 12px; }
    .filter-empty { padding: 16px; text-align: center; color: var(--text-muted); font-size: 13px; }

    .metadata-filter-chips {
      display: flex; flex-wrap: wrap; gap: 8px; padding: 0 24px 16px;
      align-items: center;
    }
    .metadata-filter-chip {
      display: inline-flex; align-items: center; gap: 4px;
      background: var(--bg-hover, rgba(255,255,255,.06));
      border: 1px solid var(--border); border-radius: 16px;
      padding: 4px 8px 4px 12px; font-size: 12px; color: var(--text-secondary);
    }
    .chip-remove {
      border: none; background: none; cursor: pointer;
      color: var(--text-muted); padding: 0; line-height: 1;
      display: inline-flex; align-items: center;
    }
    .chip-remove:hover { color: var(--text-primary); }
    .clear-all-link {
      font-size: 12px; color: var(--accent); cursor: pointer;
      text-decoration: none;
    }
    .clear-all-link:hover { text-decoration: underline; }
  `],
})
export class DashboardComponent implements OnInit, OnDestroy {
  assets: DashboardAsset[] = [];
  stats: StatsResponse | null = null;
  loading = true;

  scoreTrendData: { date: string; avg_score: number }[] = [];
  scoreTrendDataPoints = 0;
  scoreTrendLoading = false;
  scoreTrendError = false;
  scoreTrendOptions: EChartsOption = {};
  scoreTrendCollapsed = false;

  private stopPolling$ = new Subject<void>();
  private pollingActive = false;

  selectedPreset = 'last30';
  dateFrom = format(subDays(new Date(), 30), 'yyyy-MM-dd');
  dateTo = format(subDays(new Date(), 1), 'yyyy-MM-dd');

  selectedPlatforms = new Set(['META', 'TIKTOK', 'GOOGLE_ADS', 'DV360']);
  selectedFormat = '';
  sortBy = 'spend';
  sortOrder = 'desc';
  page = 1;
  pageSize = 50;
  total = 0;
  totalPages = 1;

  // Metadata filter state
  metadataFields: any[] = [];
  activeMetadataFilters: Map<string, { fieldLabel: string; values: string[] }> = new Map();
  // Popover state
  filterPopoverOpen = false;
  filterPopoverStep: 'field' | 'value' = 'field';
  selectedFilterField: any = null;
  filterValues: { value: string; label: string; source: string }[] = [];
  filteredFilterValues: { value: string; label: string; source: string }[] = [];
  filterValueSearch = '';
  pendingFilterSelections: Set<string> = new Set();

  scoreMin = 0;
  scoreMax = 100;
  sliderOptions: Options = {
    floor: 0,
    ceil: 100,
    step: 1,
    noSwitching: true,
    disabled: true,
  };
  sliderDisabled = true;
  private hasAnyScored = false;
  private scoreChange$ = new Subject<void>();

  durationMin = 0;
  durationMax = 120;
  durationSliderOptions: Options = {
    floor: 0,
    ceil: 120,
    step: 1,
    noSwitching: true,
    translate: (value: number): string => {
      if (value >= 60) {
        const m = Math.floor(value / 60);
        const s = value % 60;
        return s > 0 ? `${m}m${s}s` : `${m}m`;
      }
      return `${value}s`;
    },
  };
  hasAnyVideo = false;
  private durationChange$ = new Subject<void>();

  selectedAssets: string[] = [];
  lastSelectedId: string | null = null;

  contextMenu = { visible: false, x: 0, y: 0, asset: null as DashboardAsset | null };

  private assetDetailCache = new Map<string, DashboardAsset>();

  platforms = [
    { key: 'META', label: 'Meta', icon: 'facebook', color: '#1877F2', iconUrl: '/assets/images/icon-meta.png' },
    { key: 'TIKTOK', label: 'TikTok', icon: 'music_video', color: '#FF0050', iconUrl: '/assets/images/icon-tiktok.png' },
    { key: 'GOOGLE_ADS', label: 'Google Ads', icon: 'google', color: '#4285F4', iconUrl: '/assets/images/icon-google-ads.png' },
    { key: 'DV360', label: 'DV360', icon: 'display', color: '#00897B', iconUrl: '/assets/images/icon-dv360.png' },
  ];

  private destroy$ = new Subject<void>();

  // Correlation drawer state
  correlationDrawerOpen = false;
  correlationLoading = false;
  correlationError = false;
  correlationAssets: CorrelationAsset[] = [];
  correlationMinSpend = 10;
  correlationMinSpendOptions: Options = {
    floor: 0,
    ceil: 1000,
    step: 10,
    showTicks: false,
    hideLimitLabels: true,
    hidePointerLabels: true,
  };
  scatterOptions: EChartsOption = {};

  readonly correlationMetrics: { key: string; label: string; format: (v: number) => string; suffix: string }[] = [
    { key: 'roas', label: 'ROAS', format: (v) => v.toFixed(2) + 'x', suffix: 'x' },
    { key: 'ctr', label: 'CTR', format: (v) => v.toFixed(2) + '%', suffix: '%' },
    { key: 'vtr', label: 'VTR', format: (v) => v.toFixed(2) + '%', suffix: '%' },
    { key: 'cpm', label: 'CPM', format: (v) => '$' + v.toFixed(2), suffix: '' },
    { key: 'cvr', label: 'CVR', format: (v) => v.toFixed(2) + '%', suffix: '%' },
    { key: 'cpc', label: 'CPC', format: (v) => '$' + v.toFixed(2), suffix: '' },
    { key: 'conversions', label: 'Conversions', format: (v) => v.toFixed(0), suffix: '' },
  ];
  selectedCorrelationMetric = 'roas';

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private dialog: MatDialog,
    private route: ActivatedRoute,
    private router: Router,
    private snackBar: MatSnackBar,
  ) {}

  get orgCurrency(): string {
    return this.auth.currentUser?.organization_currency || 'USD';
  }

  ngOnInit(): void {
    // Load metadata fields for filter popover
    this.api.get<any[]>('/assets/metadata-fields').subscribe({
      next: (fields) => this.metadataFields = fields,
    });

    // Debounced score filter
    this.scoreChange$.pipe(
      debounceTime(400),
      takeUntil(this.destroy$)
    ).subscribe(() => this.onFilterChange());

    // Debounced duration filter
    this.durationChange$.pipe(
      debounceTime(400),
      takeUntil(this.destroy$)
    ).subscribe(() => this.onFilterChange());

    // Handle query params (from homepage navigation or direct link)
    this.route.queryParams.pipe(takeUntil(this.destroy$)).subscribe(params => {
      if (params['platforms']) {
        this.selectedPlatforms = new Set([params['platforms'].toUpperCase()]);
      }
      this.loadData();
      this.loadScoreTrend();
      if (params['assetId']) {
        this.openAssetById(params['assetId']);
      }
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.stopPolling$.next();
    this.stopPolling$.complete();
  }

  get aggStats(): any[] {
    if (!this.stats) return [];
    const s = this.stats;
    return [
      {
        label: 'Total Spend',
        value: new Intl.NumberFormat('en-US', { style: 'currency', currency: this.orgCurrency, maximumFractionDigits: 0 }).format(s.total_spend || 0),
        change: this.pctChange(s.total_spend, s.prev_total_spend),
        changeClass: this.changeClass(s.total_spend, s.prev_total_spend),
        changeDir: (s.total_spend || 0) >= (s.prev_total_spend || 0) ? 'arrow_upward' : 'arrow_downward',
      },
      {
        label: 'Impressions',
        value: new Intl.NumberFormat('en-US', { notation: 'compact' }).format(s.total_impressions || 0),
        change: this.pctChange(s.total_impressions, s.prev_total_impressions),
        changeClass: this.changeClass(s.total_impressions, s.prev_total_impressions),
        changeDir: (s.total_impressions || 0) >= (s.prev_total_impressions || 0) ? 'arrow_upward' : 'arrow_downward',
      },
      {
        label: 'Avg ROAS',
        value: s.avg_roas ? `${s.avg_roas.toFixed(2)}x` : 'N/A',
        change: this.pctChange(s.avg_roas, s.prev_avg_roas),
        changeClass: this.changeClass(s.avg_roas, s.prev_avg_roas),
        changeDir: (s.avg_roas || 0) >= (s.prev_avg_roas || 0) ? 'arrow_upward' : 'arrow_downward',
        clickable: true,
        clickFn: () => this.openCorrelationDrawer(),
        icon: 'bi-bar-chart-line',
      },
      {
        label: 'Active Assets',
        value: new Intl.NumberFormat('en-US').format(s.total_active_assets || 0),
        change: `+${s.new_assets_in_period || 0} new`,
        changeClass: 'change-positive',
        changeDir: 'arrow_upward',
      },
    ];
  }

  get correlationEligibleCount(): number {
    return this.correlationAssets.filter(
      a => (a as any)[this.selectedCorrelationMetric] !== null && (a.spend ?? 0) >= this.correlationMinSpend
    ).length;
  }

  get selectedMetricLabel(): string {
    return this.correlationMetrics.find(m => m.key === this.selectedCorrelationMetric)?.label ?? '';
  }

  trackAggStat(_index: number, item: any): string { return item.label; }

  onAggStatClick(stat: any): void {
    if (stat.clickable) {
      this.openCorrelationDrawer();
    }
  }

  openCorrelationDrawer(): void {
    this.correlationDrawerOpen = true;
    this.loadCorrelationData();
  }

  closeCorrelationDrawer(): void {
    this.correlationDrawerOpen = false;
  }

  loadCorrelationData(): void {
    this.correlationLoading = true;
    this.correlationError = false;
    const params: any = {
      date_from: this.dateFrom,
      date_to: this.dateTo,
    };
    if (this.selectedPlatforms?.size) {
      params.platforms = [...this.selectedPlatforms].join(',');
    }
    this.api.get<CorrelationAsset[]>('/dashboard/correlation-data', params).subscribe({
      next: (assets) => {
        this.correlationAssets = assets;
        this.correlationLoading = false;
        this.buildScatterChart();
      },
      error: () => {
        this.correlationLoading = false;
        this.correlationError = true;
      },
    });
  }

  buildScatterChart(): void {
    const metric = this.correlationMetrics.find(m => m.key === this.selectedCorrelationMetric)!;
    const eligible = this.correlationAssets.filter(
      a => (a as any)[metric.key] !== null && (a.spend ?? 0) >= this.correlationMinSpend
    );

    if (eligible.length === 0) {
      this.scatterOptions = {};
      return;
    }

    const metricValues = eligible.map(a => (a as any)[metric.key] as number).sort((x, y) => x - y);
    const scoreValues = eligible.map(a => a.total_score).sort((x, y) => x - y);

    const metricCap = metricValues[Math.floor(metricValues.length * 0.99)] ?? metricValues[metricValues.length - 1] ?? 1;

    const median = (arr: number[]): number => {
      const mid = Math.floor(arr.length / 2);
      return arr.length % 2 !== 0 ? arr[mid] : (arr[mid - 1] + arr[mid]) / 2;
    };

    const medianScore = eligible.length === 1 ? eligible[0].total_score : median(scoreValues);
    const medianMetric = eligible.length === 1 ? ((eligible[0] as any)[metric.key] as number) : median(metricValues);

    const scatterData = eligible.map(a => [
      a.total_score,
      Math.min((a as any)[metric.key] as number, metricCap),
      a,
    ]);

    this.scatterOptions = {
      grid: { top: 40, right: 20, bottom: 50, left: 60 },
      xAxis: {
        name: 'ACE Score',
        min: 0,
        max: 100,
        nameLocation: 'center',
        nameGap: 30,
        axisLine: { lineStyle: { color: '#666666' } },
        axisTick: { lineStyle: { color: '#666666' } },
        axisLabel: { color: '#999999' },
        splitLine: { lineStyle: { color: '#555555', opacity: 0.5 } },
      },
      yAxis: {
        name: metric.label,
        min: 0,
        max: metricCap * 1.05,
        axisLine: { lineStyle: { color: '#666666' } },
        axisTick: { lineStyle: { color: '#666666' } },
        axisLabel: { color: '#999999' },
        splitLine: { lineStyle: { color: '#555555', opacity: 0.5 } },
      },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'var(--bg-card)',
        borderColor: 'var(--border)',
        borderRadius: 8,
        padding: 12,
        formatter: (params: any) => {
          const asset = params.data[2] as CorrelationAsset;
          const thumb = asset.thumbnail_url || '/assets/images/placeholder.svg';
          return `<div style="display:flex;gap:10px;align-items:flex-start;max-width:280px">
            <img src="${thumb}" style="width:48px;height:48px;object-fit:cover;border-radius:4px" />
            <div>
              <div style="font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px">${asset.ad_name || 'Untitled'}</div>
              <div style="font-size:14px;color:var(--text-secondary);margin-top:4px">
                Score: ${params.data[0]} &middot; ${metric.label}: ${metric.format(params.data[1] as number)} &middot; $${((asset.spend ?? 0) as number).toFixed(0)} &middot; ${asset.platform}
              </div>
            </div>
          </div>`;
        },
      },
      graphic: [
        { type: 'text', right: 30, top: 50, style: { text: 'Stars', fill: '#aaaaaa', fontSize: 11, fontWeight: '600' } },
        { type: 'text', left: 70, top: 50, style: { text: 'Workhorses', fill: '#aaaaaa', fontSize: 11, fontWeight: '600' } },
        { type: 'text', right: 30, bottom: 60, style: { text: 'Question Marks', fill: '#aaaaaa', fontSize: 11, fontWeight: '600' } },
        { type: 'text', left: 70, bottom: 60, style: { text: 'Laggards', fill: '#aaaaaa', fontSize: 11, fontWeight: '600' } },
      ],
      series: [{
        type: 'scatter',
        symbolSize: 12,
        data: scatterData,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#404040', type: 'dashed', width: 1 },
          label: { show: true, color: '#aaaaaa', fontSize: 11, borderWidth: 0, backgroundColor: 'transparent', position: 'insideStartTop' },
          data: [
            { xAxis: medianScore, label: { formatter: `Median Score: ${medianScore.toFixed(0)}` } },
            { yAxis: medianMetric, label: { formatter: `Median ${metric.label}: ${metric.format(medianMetric)}` } },
            { yAxis: metricCap, lineStyle: { color: 'rgba(255,119,0,0.4)', type: 'dashed' }, label: { formatter: `99th pct`, color: 'rgba(255,119,0,0.7)' } },
          ],
        },
        itemStyle: {
          color: (params: any) => {
            const [score, metricVal] = params.data;
            if (score >= medianScore && metricVal >= medianMetric) return '#FF7700';
            if (score < medianScore && metricVal >= medianMetric) return '#F39C12';
            if (score >= medianScore && metricVal < medianMetric) return '#4285F4';
            return '#707070';
          },
        },
        emphasis: { itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.3)' }, scale: 1.5 },
      }],
    } as any;
  }

  onScatterClick(params: any): void {
    if (params.componentType !== 'series' || params.componentSubType !== 'scatter') return;
    const asset = params.data[2] as CorrelationAsset;
    this.correlationDrawerOpen = false;
    setTimeout(() => this.openAssetDetail({ ...asset } as any), 200);
  }

  onCorrelationMinSpendChange(): void {
    this.buildScatterChart();
  }

  private pctChange(curr: number | null, prev: number | null): string | null {
    if (!prev || curr == null) return null;
    const pct = ((curr - prev) / prev * 100).toFixed(1);
    return `${pct}%`;
  }

  private changeClass(curr: number | null, prev: number | null): string {
    if (!prev || curr == null) return 'change-neutral';
    return curr >= prev ? 'change-positive' : 'change-negative';
  }

  loadData(): void {
    this.loading = true;
    const params: any = {
      date_from: this.dateFrom,
      date_to: this.dateTo,
      platforms: [...this.selectedPlatforms].join(','),
      sort_by: this.sortBy,
      sort_order: this.sortOrder,
      page: this.page,
      page_size: this.pageSize,
    };
    if (this.selectedFormat) params.formats = this.selectedFormat;
    if (this.scoreMin > 0) params['score_min'] = this.scoreMin;
    if (this.scoreMax < 100) params['score_max'] = this.scoreMax;
    if (this.durationMin > 0) params['duration_min'] = this.durationMin;
    if (this.durationMax < 120) params['duration_max'] = this.durationMax;
    if (this.activeMetadataFilters.size > 0) {
      params['meta_filters'] = [];
      this.activeMetadataFilters.forEach((filter, fieldId) => {
        params['meta_filters'].push(`${fieldId}:${filter.values.join(',')}`);
      });
    }

    this.api.get<DashboardAssetsResponse>('/dashboard/assets', params).subscribe({
      next: (d) => {
        this.assets = d.items;
        this.total = d.total;
        this.totalPages = d.total_pages;
        this.loading = false;
        // Only enable slider once we've seen scored assets — don't disable when filtered results are empty
        if (this.assets.some((a: any) => a.scoring_status === 'COMPLETE')) {
          this.hasAnyScored = true;
        }
        this.sliderDisabled = !this.hasAnyScored;
        this.sliderOptions = { ...this.sliderOptions, disabled: !this.hasAnyScored };
        // Duration slider: show when any video exists (sticky — never hides once shown)
        const videoAssets = d.items.filter((a: any) => a.asset_format === 'VIDEO' && a.video_duration != null);
        if (videoAssets.length > 0) {
          this.hasAnyVideo = true;
          const maxDur = Math.ceil(Math.max(...videoAssets.map((a: any) => a.video_duration)));
          const oldCeil = this.durationSliderOptions.ceil ?? 120;
          const newCeil = Math.max(maxDur, oldCeil);
          if (newCeil !== oldCeil) {
            // If durationMax was pinned to old ceil (meaning "no upper limit"), keep it pinned to new ceil
            if (this.durationMax === oldCeil) this.durationMax = newCeil;
            this.durationSliderOptions = { ...this.durationSliderOptions, ceil: newCeil };
          }
        }
        this.preloadAssetDetails();
        this.stopPolling$.next();
        this.pollingActive = false;
        this.startScoringPolling(this.assets);
      },
      error: () => { this.loading = false; },
    });

    this.api.get<StatsResponse>('/dashboard/stats', params).subscribe({
      next: (s) => this.stats = s,
    });
  }

  onFilterChange(): void {
    this.page = 1;
    this.loadData();
  }

  openFilterPopover(): void {
    this.filterPopoverOpen = true;
    this.filterPopoverStep = 'field';
    this.filterValueSearch = '';
    this.pendingFilterSelections = new Set();
    this.selectedFilterField = null;
  }

  selectFilterField(field: any): void {
    this.selectedFilterField = field;
    this.filterPopoverStep = 'value';
    this.filterValueSearch = '';
    // Pre-check values already active for this field
    const existing = this.activeMetadataFilters.get(field.id);
    this.pendingFilterSelections = existing ? new Set(existing.values) : new Set();
    // Load combined predefined + actual values
    this.api.get<{ value: string; label: string; source: string }[]>(
      '/assets/metadata-filter-values',
      { field_id: field.id }
    ).subscribe({
      next: (vals) => {
        this.filterValues = vals;
        this.filteredFilterValues = vals;
      },
    });
  }

  onFilterValueSearch(term: string): void {
    const t = term.toLowerCase();
    this.filteredFilterValues = this.filterValues.filter(
      v => v.label.toLowerCase().includes(t) || v.value.toLowerCase().includes(t)
    );
  }

  toggleFilterValue(value: string): void {
    if (this.pendingFilterSelections.has(value)) {
      this.pendingFilterSelections.delete(value);
    } else {
      this.pendingFilterSelections.add(value);
    }
    // Trigger change detection
    this.pendingFilterSelections = new Set(this.pendingFilterSelections);
  }

  confirmFilterSelection(): void {
    if (this.pendingFilterSelections.size > 0) {
      this.activeMetadataFilters.set(this.selectedFilterField.id, {
        fieldLabel: this.selectedFilterField.label,
        values: [...this.pendingFilterSelections],
      });
      this.activeMetadataFilters = new Map(this.activeMetadataFilters);
    }
    this.filterPopoverOpen = false;
    this.onFilterChange();
  }

  removeMetadataFilter(fieldId: string): void {
    this.activeMetadataFilters.delete(fieldId);
    this.activeMetadataFilters = new Map(this.activeMetadataFilters);
    this.onFilterChange();
  }

  clearAllMetadataFilters(): void {
    this.activeMetadataFilters = new Map();
    this.onFilterChange();
  }

  onScoreChange(): void {
    this.scoreChange$.next();
  }

  onDurationChange(): void {
    this.durationChange$.next();
  }

  formatDuration(seconds: number): string {
    if (seconds >= 60) {
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      return s > 0 ? `${m}m${s}s` : `${m}m`;
    }
    return `${seconds}s`;
  }

  onDateRangeChange(event: DateRangeChange): void {
    this.dateFrom = event.dateFrom;
    this.dateTo = event.dateTo;
    this.selectedPreset = event.preset;
    this.onFilterChange();
    this.loadScoreTrend();
  }

  loadScoreTrend(): void {
    this.scoreTrendLoading = true;
    this.scoreTrendError = false;
    const params: any = {
      date_from: this.dateFrom,
      date_to: this.dateTo,
    };
    if (this.selectedPlatforms?.size) {
      params.platforms = [...this.selectedPlatforms].join(',');
    }
    this.api.getScoreTrend(params).subscribe({
      next: (res: any) => {
        this.scoreTrendData = res.trend || [];
        this.scoreTrendDataPoints = res.data_points || 0;
        this.scoreTrendLoading = false;
        if (this.scoreTrendDataPoints >= 2) {
          this.scoreTrendOptions = {
            color: ['#FF7700'],
            xAxis: {
              type: 'category',
              data: this.scoreTrendData.map(d => d.date),
              axisLabel: { fontSize: 11, color: '#999' },
              axisLine: { lineStyle: { color: 'rgba(128,128,128,0.2)' } },
              axisTick: { show: false },
              splitLine: { show: false },
            },
            yAxis: {
              type: 'value',
              min: 0,
              max: 100,
              axisLabel: { fontSize: 11, color: '#999' },
              axisLine: { show: false },
              axisTick: { show: false },
              splitLine: { lineStyle: { color: 'rgba(128,128,128,0.15)' } },
            },
            series: [{
              type: 'line',
              data: this.scoreTrendData.map(d => d.avg_score),
              smooth: true,
              lineStyle: { width: 2 },
            }],
            tooltip: {
              trigger: 'axis',
              formatter: (params: any) => {
                const p = Array.isArray(params) ? params[0] : params;
                return `${p.axisValue}<br/>Score: ${p.value}`;
              },
            },
            grid: { left: 40, right: 20, top: 16, bottom: 32 },
          };
        }
      },
      error: () => {
        this.scoreTrendLoading = false;
        this.scoreTrendError = true;
      },
    });
  }

  togglePlatform(key: string): void {
    if (this.selectedPlatforms.has(key)) {
      if (this.selectedPlatforms.size > 1) this.selectedPlatforms.delete(key);
    } else {
      this.selectedPlatforms.add(key);
    }
    this.onFilterChange();
    this.loadScoreTrend();
  }

  isPlatformActive(key: string): boolean {
    return this.selectedPlatforms.has(key);
  }

  toggleSortOrder(): void {
    this.sortOrder = this.sortOrder === 'desc' ? 'asc' : 'desc';
    this.loadData();
  }

  changePage(p: number): void {
    this.page = p;
    this.loadData();
  }

  onPageSizeChange(): void {
    this.page = 1;
    this.loadData();
  }

  // Asset selection
  selectAsset(event: MouseEvent, asset: DashboardAsset): void {
    const id = asset.id;
    if (event.ctrlKey || event.metaKey) {
      if (this.selectedAssets.includes(id)) {
        this.selectedAssets = this.selectedAssets.filter(a => a !== id);
      } else {
        this.selectedAssets = [...this.selectedAssets, id];
      }
      this.lastSelectedId = id;
    } else if (event.shiftKey && this.lastSelectedId) {
      const ids = this.assets.map(a => a.id);
      const from = ids.indexOf(this.lastSelectedId);
      const to = ids.indexOf(id);
      const range = ids.slice(Math.min(from, to), Math.max(from, to) + 1);
      this.selectedAssets = [...new Set([...this.selectedAssets, ...range])];
    } else {
      this.selectedAssets = [id];
      this.lastSelectedId = id;
      // Double-click handled by dblclick event
    }
  }

  isSelected(id: string): boolean {
    return this.selectedAssets.includes(id);
  }

  onRightClick(event: MouseEvent, asset: DashboardAsset): void {
    event.preventDefault();
    if (!this.isSelected(asset.id)) {
      this.selectedAssets = [asset.id];
    }
    this.contextMenu = {
      visible: true,
      x: event.clientX,
      y: event.clientY,
      asset,
    };
  }

  private preloadAssetDetails(): void {
    this.assetDetailCache.clear();
    if (!this.assets?.length) return;

    const kpis = 'spend,ctr,roas,cpm,video_views,vtr,conversions,cvr,impressions,clicks';
    for (const asset of this.assets) {
      this.api.get<DashboardAsset>(`/dashboard/assets/${asset.id}`, {
        date_from: this.dateFrom,
        date_to: this.dateTo,
        kpis,
      }).subscribe({
        next: (d) => this.assetDetailCache.set(asset.id, d),
      });
    }
  }

  async openAssetDetail(asset: DashboardAsset): Promise<void> {
    this.contextMenu.visible = false;
    const { AssetDetailDialogComponent } = await import('../dashboard/dialogs/asset-detail-dialog.component');
    this.dialog.open(AssetDetailDialogComponent, {
      width: '96vw',
      maxWidth: '1800px',
      height: '92vh',
      data: {
        assetId: asset.id,
        dateFrom: this.dateFrom,
        dateTo: this.dateTo,
        selectedPreset: this.selectedPreset,
        preloaded: this.assetDetailCache.get(asset.id) || null,
      },
      panelClass: 'asset-detail-dialog',
    });
  }

  async openAssetById(assetId: string): Promise<void> {
    const { AssetDetailDialogComponent } = await import('../dashboard/dialogs/asset-detail-dialog.component');
    this.dialog.open(AssetDetailDialogComponent, {
      width: '96vw',
      maxWidth: '1800px',
      height: '92vh',
      data: {
        assetId,
        dateFrom: this.dateFrom,
        dateTo: this.dateTo,
        selectedPreset: this.selectedPreset,
        preloaded: this.assetDetailCache.get(assetId) || null,
      },
    });
  }

  async openExport(): Promise<void> {
    const { ExportDialogComponent } = await import('../dashboard/dialogs/export-dialog.component');
    this.dialog.open(ExportDialogComponent, {
      width: '720px',
      data: {
        dateFrom: this.dateFrom,
        dateTo: this.dateTo,
        platforms: [...this.selectedPlatforms],
        format: this.selectedFormat,
      },
    });
  }

  async openAssignProject(asset: DashboardAsset): Promise<void> {
    this.contextMenu.visible = false;
    const { AssignProjectDialogComponent } = await import('../dashboard/dialogs/assign-project-dialog.component');
    const assetIds = this.selectedAssets.length > 0 ? this.selectedAssets : [asset.id];
    this.dialog.open(AssignProjectDialogComponent, {
      width: '420px',
      data: { assetIds },
    });
  }

  async openEditMetadata(asset: DashboardAsset): Promise<void> {
    this.contextMenu.visible = false;
    const { EditMetadataDialogComponent } = await import('../dashboard/dialogs/edit-metadata-dialog.component');
    const assetIds = this.selectedAssets.length > 0 ? this.selectedAssets : [asset.id];

    if (assetIds.length === 1) {
      this.api.get<{ metadata_values?: Record<string, string> }>(`/dashboard/assets/${assetIds[0]}`, {
        date_from: this.dateFrom,
        date_to: this.dateTo,
      }).subscribe({
        next: (detail) => {
          this.dialog.open(EditMetadataDialogComponent, {
            width: '480px',
            data: {
              assetIds,
              singleAssetName: asset.ad_name || undefined,
              existingValues: detail.metadata_values || {},
            },
          });
        },
        error: () => {
          this.dialog.open(EditMetadataDialogComponent, {
            width: '480px',
            data: { assetIds, singleAssetName: asset.ad_name || undefined },
          });
        },
      });
    } else {
      this.dialog.open(EditMetadataDialogComponent, {
        width: '480px',
        data: { assetIds },
      });
    }
  }

  copyAssetId(asset: DashboardAsset): void {
    navigator.clipboard.writeText(asset.id);
    this.snackBar.open('Asset ID copied to clipboard', '', { duration: 2000 });
    this.contextMenu.visible = false;
  }

  compareSelected(): void {
    this.contextMenu.visible = false;
    if (this.selectedAssets.length >= 2 && this.selectedAssets.length <= 4) {
      this.router.navigate(['/comparison'], {
        queryParams: {
          assetIds: this.selectedAssets.join(','),
          dateFrom: this.dateFrom,
          dateTo: this.dateTo,
        },
      });
    }
  }

  getPlatformIcon(platform: string): string {
    const icons: Record<string, string> = {
      META: 'facebook',
      TIKTOK: 'music_video',
      GOOGLE_ADS: 'google',
      DV360: 'display',
    };
    return icons[platform] || 'ads_click';
  }

  getPlatformOverlayIcon(platform: string): string {
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

  getTagClass(tag: string | null): string {
    if (tag === 'Top Performer') return 'tile-tag tag-top';
    if (tag === 'Below Average') return 'tile-tag tag-below';
    return 'tile-tag';
  }

  getPerformerTooltip(tag: string | null): string {
    if (tag === 'Top Performer') return 'Top 10% of your scored creatives';
    if (tag === 'Below Average') return 'Bottom 10% of your scored creatives';
    return '';
  }

  getScoreBadgeClass(rating: string | null): string {
    switch (rating) {
      case 'positive': return 'ace-score ace-positive';
      case 'medium': return 'ace-score ace-medium';
      case 'negative': return 'ace-score ace-negative';
      default: return 'ace-score';
    }
  }

  getScoreTooltip(rating: string | null): string {
    switch (rating) {
      case 'positive': return 'Positive effectiveness';
      case 'medium': return 'Moderate effectiveness';
      case 'negative': return 'Low effectiveness';
      default: return 'Scoring failed';
    }
  }

  private startScoringPolling(assets: any[]): void {
    const pendingIds = assets
      .filter(a => a.scoring_status === 'PENDING' || a.scoring_status === 'PROCESSING')
      .map(a => a.id);

    if (pendingIds.length === 0 || this.pollingActive) return;
    this.pollingActive = true;

    interval(10000).pipe(
      takeUntil(this.stopPolling$),
      switchMap(() => this.api.getScoringStatus(pendingIds)),
    ).subscribe(statuses => {
      for (const status of statuses) {
        const asset = this.assets.find(a => a.id === status.asset_id);
        if (asset) {
          asset.scoring_status = status.scoring_status;
          asset.total_score = status.total_score;
          asset.total_rating = status.total_rating;
        }
      }
      const stillPending = statuses.filter(
        s => s.scoring_status === 'PENDING' || s.scoring_status === 'PROCESSING',
      );
      if (stillPending.length === 0) {
        this.stopPolling$.next();
        this.pollingActive = false;
      }
    });
  }

  rescoreAsset(asset: any): void {
    this.contextMenu.visible = false;
    this.api.rescoreAsset(asset.id).subscribe({
      next: () => {
        asset.scoring_status = 'PENDING';
        asset.total_score = null;
        asset.total_rating = null;
        if (!this.pollingActive) {
          this.startScoringPolling([asset]);
        }
        this.snackBar.open('Scoring queued — results in ~2 minutes', 'OK', { duration: 3000 });
      },
      error: () => {
        this.snackBar.open('Could not queue scoring. Try again.', 'OK', { duration: 3000 });
      },
    });
  }

  getTileThumbnail(asset: any): string | null {
    if (asset.asset_format === 'VIDEO') {
      // Video: use thumbnail_url if available, else null triggers CSS fallback (D-06)
      return asset.thumbnail_url || null;
    }
    // Image/Carousel: use asset_url (skip .mp4), then thumbnail, then placeholder (D-07)
    if (asset.asset_url && !asset.asset_url.endsWith('.mp4')) return asset.asset_url;
    if (asset.thumbnail_url) return asset.thumbnail_url;
    return '/assets/images/placeholder.svg';
  }

  isVideoNoThumb(asset: any): boolean {
    return asset.asset_format === 'VIDEO' && !asset.thumbnail_url;
  }

  onImgError(event: Event): void {
    (event.target as HTMLImageElement).src = '/assets/images/placeholder.svg';
  }
}
