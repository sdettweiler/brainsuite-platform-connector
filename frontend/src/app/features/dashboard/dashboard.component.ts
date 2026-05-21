import { Component, OnInit, OnDestroy, EventEmitter, signal, computed } from '@angular/core';
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
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatChipsModule } from '@angular/material/chips';
import { Subject, debounceTime, takeUntil, forkJoin, interval, switchMap, take, takeWhile, filter, map } from 'rxjs';
import { NgxSliderModule, Options } from '@angular-slider/ngx-slider';
import { NgxEchartsDirective, provideEchartsCore } from 'ngx-echarts';
import * as echarts from 'echarts/core';
import { LineChart, ScatterChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { MatSidenavModule } from '@angular/material/sidenav';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { JobMonitorService } from '../../core/services/job-monitor.service';
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
  null_duration_count?: number;  // Phase 23: returned by /dashboard/assets when duration filter active (D-07)
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
  total_rating: string | null;
  roas: number | null;
  ctr: number | null;
  cvr: number | null;
  vtr: number | null;
  cpm: number | null;
  cpa: number | null;
  spend: number | null;
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
    MatAutocompleteModule,
    MatChipsModule,
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
        <button class="tbd-trigger" [matMenuTriggerFor]="formatMenu">
          {{formatLabel}}<i class="bi bi-chevron-down tbd-arrow"></i>
        </button>
        <mat-menu #formatMenu="matMenu" class="tbd-menu">
          <button mat-menu-item (click)="selectedFormat = ''; onFilterChange()"><span class="tbd-check" [class.checked]="selectedFormat === ''">&#10003;</span>All Formats</button>
          <button mat-menu-item (click)="selectedFormat = 'IMAGE'; onFilterChange()"><span class="tbd-check" [class.checked]="selectedFormat === 'IMAGE'">&#10003;</span>Image</button>
          <button mat-menu-item (click)="selectedFormat = 'VIDEO'; onFilterChange()"><span class="tbd-check" [class.checked]="selectedFormat === 'VIDEO'">&#10003;</span>Video</button>
          <button mat-menu-item (click)="selectedFormat = 'CAROUSEL'; onFilterChange()"><span class="tbd-check" [class.checked]="selectedFormat === 'CAROUSEL'">&#10003;</span>Carousel</button>
        </mat-menu>

        <!-- Ad Account filter -->
        <ng-container *ngIf="adAccounts.length > 0">
          <button class="tbd-trigger" [matMenuTriggerFor]="accountMenu">
            {{selectedAdAccountIds.length === 0 ? 'All Accounts' : selectedAdAccountIds.length + ' Account' + (selectedAdAccountIds.length > 1 ? 's' : '')}}<i class="bi bi-chevron-down tbd-arrow"></i>
          </button>
          <mat-menu #accountMenu="matMenu" class="tbd-menu account-menu" (closed)="adAccountSearch = ''">
            <div mat-menu-item class="account-search-row" (click)="$event.stopPropagation()">
              <input [(ngModel)]="adAccountSearch" (click)="$event.stopPropagation()" (keydown)="$event.stopPropagation()" placeholder="Search accounts…" aria-label="Search ad accounts" autocomplete="off" class="account-search-input" />
            </div>
            <button mat-menu-item (click)="$event.stopPropagation(); selectedAdAccountIds = []; onFilterChange()" *ngIf="!adAccountSearch"><span class="tbd-check" [class.checked]="selectedAdAccountIds.length === 0">&#10003;</span>All Accounts</button>
            <ng-container *ngFor="let group of filteredGroupedAdAccounts; let last = last; trackBy: trackByPlatform">
              <button mat-menu-item disabled class="tbd-group-header-item" *ngIf="showPlatformGrouping" aria-disabled="true">{{ getPlatformDisplayName(group.platform) }}</button>
              <button mat-menu-item *ngFor="let acc of group.accounts; trackBy: trackByAccountId" (click)="$event.stopPropagation(); toggleAdAccount(acc.ad_account_id)">
                <span class="tbd-check" [class.checked]="selectedAdAccountIds.includes(acc.ad_account_id)">&#10003;</span>
                <span class="tbd-name">{{acc.ad_account_name}}</span>
                <span class="tbd-badge" *ngIf="!showPlatformGrouping">{{acc.platform}}</span>
              </button>
              <div class="tbd-group-divider" role="separator" *ngIf="showPlatformGrouping && !last"></div>
            </ng-container>
            <button mat-menu-item disabled *ngIf="adAccountSearch && filteredGroupedAdAccounts.length === 0"><span class="tbd-name muted">No accounts found</span></button>
          </mat-menu>
        </ng-container>

        <!-- Metadata filter -->
        <button class="tbd-trigger" [class.has-active-filters]="activeMetadataFilters.length > 0" [matMenuTriggerFor]="metadataMenu" aria-label="Metadata filter" aria-haspopup="true">{{ metadataButtonLabel }}<i class="bi bi-chevron-down tbd-arrow"></i></button>
        <mat-menu #metadataMenu="matMenu" class="tbd-menu metadata-menu">
          <!-- Step 1: Field selector -->
          <ng-container *ngIf="selectedMetadataFieldId === null">
            <button mat-menu-item disabled *ngIf="metadataFields.length === 0"><span class="tbd-name muted">No metadata fields configured</span></button>
            <button mat-menu-item *ngFor="let field of metadataFields" (click)="$event.stopPropagation(); selectMetadataField(field)">
              <span class="tbd-name">{{ field.label }}</span>
            </button>
          </ng-container>
          <!-- Step 2: Value autocomplete -->
          <ng-container *ngIf="selectedMetadataFieldId !== null">
            <button mat-menu-item (click)="$event.stopPropagation(); backToFieldList()" class="metadata-back-row">
              <i class="bi bi-arrow-left"></i><span class="tbd-name">&#8592; {{ selectedMetadataFieldLabel }}</span>
            </button>
            <div mat-menu-item class="metadata-input-row" (click)="$event.stopPropagation()">
              <input [(ngModel)]="metadataValueInput" (click)="$event.stopPropagation()" placeholder="Type to search…" [attr.aria-label]="'Search ' + selectedMetadataFieldLabel + ' values'" aria-autocomplete="list" autocomplete="off" class="metadata-input" />
            </div>
            <button mat-menu-item disabled *ngIf="metadataValuesLoading"><span class="tbd-name muted"><i class="bi bi-arrow-clockwise spin"></i> Loading…</span></button>
            <button mat-menu-item *ngIf="metadataValuesError && !metadataValuesLoading" (click)="$event.stopPropagation(); retryLoadMetadataValues()"><span class="tbd-name muted">Couldn't load values. Try again.</span></button>
            <button mat-menu-item *ngFor="let val of filteredMetadataValues" (click)="$event.stopPropagation(); selectMetadataValue(val)"><span class="tbd-check" [class.checked]="isMetadataValueSelected(val)">&#10003;</span><span class="tbd-name">{{ val }}</span></button>
            <button mat-menu-item disabled *ngIf="!metadataValuesLoading && !metadataValuesError && filteredMetadataValues.length === 0"><span class="tbd-name muted">No values found</span></button>
          </ng-container>
        </mat-menu>

        <!-- Sort -->
        <button class="tbd-trigger" [matMenuTriggerFor]="sortMenu">
          {{sortLabel}}<i class="bi bi-chevron-down tbd-arrow"></i>
        </button>
        <mat-menu #sortMenu="matMenu" class="tbd-menu">
          <button mat-menu-item *ngFor="let o of sortOptions" (click)="sortBy = o.value; onFilterChange()">
            <span class="tbd-check" [class.checked]="sortBy === o.value">&#10003;</span>{{o.label}}
          </button>
        </mat-menu>

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

        <!-- Phase 23 (DASH-03): Duration range filter — visible when VIDEO assets present (D-04) -->
        <div class="duration-slider-wrapper"
             *ngIf="hasVideoAssets"
             aria-label="Duration filter"
             [matTooltip]="loadingDurationBounds ? 'Loading duration data…' : ''">
          <span class="slider-label">Duration</span>
          <ngx-slider
            [(value)]="durationMin"
            [(highValue)]="durationMax"
            [options]="durationSliderOptions"
            [manualRefresh]="durationSliderRefresh"
            (userChangeEnd)="onFilterChange()"
          ></ngx-slider>
          <span class="slider-values">{{ formatDuration(durationMin) }} – {{ formatDuration(durationMax) }}</span>
        </div>

        <div class="toolbar-spacer"></div>

        <!-- Export button -->
        <button mat-stroked-button (click)="openExport()">
          <i class="bi bi-download"></i>
          Export
        </button>
      </div>

      <!-- Metadata filter chip row -->
      <div class="metadata-chip-row" *ngIf="activeMetadataFilters.length > 0 || isDurationFilterActive">
        <div class="metadata-chip" *ngFor="let f of activeMetadataFilters; let i = index" role="listitem">
          <span>{{ f.fieldLabel }}: {{ f.value }}</span>
          <button class="chip-dismiss" type="button" (click)="removeMetadataFilter(i)" [attr.aria-label]="'Remove ' + f.fieldLabel + ': ' + f.value + ' filter'" title="Remove filter"><i class="bi bi-x"></i></button>
        </div>
        <!-- Phase 23 (DASH-03): Duration filter chip — appears only when filter is active -->
        <div class="metadata-chip" *ngIf="isDurationFilterActive" role="listitem">
          <span>Duration: {{ formatDuration(durationMin) }} – {{ formatDuration(durationMax) }}</span>
          <button class="chip-dismiss" type="button" (click)="clearDurationFilter()" aria-label="Remove duration filter" title="Remove filter"><i class="bi bi-x"></i></button>
        </div>
        <button class="chip-clear-all" type="button" *ngIf="activeMetadataFilters.length >= 2" (click)="clearAllMetadataFilters()" aria-label="Clear all metadata filters">Clear all filters</button>
      </div>

      <!-- Phase 23 (DASH-03 D-06 D-07 D-08): NULL duration callout — below chip row, only when filter active and counts > 0 -->
      <div class="duration-null-callout"
           *ngIf="isDurationFilterActive && nullDurationCount > 0"
           role="status">
        <i class="bi bi-info-circle" aria-hidden="true"></i>
        <span>{{ nullDurationCount }} video{{ nullDurationCount !== 1 ? 's' : '' }} {{ nullDurationCount === 1 ? 'has' : 'have' }} no duration data and {{ nullDurationCount === 1 ? 'is' : 'are' }} excluded from this filter</span>
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
            <div class="tile-flip-inner" [class.tile-flipped]="flippedTiles.has(asset.id)">
              <!-- Front face -->
              <div class="tile-face tile-front">
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
                        matTooltip="Show score card"
                        [attr.aria-label]="'Score: ' + asset.total_score + ', ' + asset.total_rating"
                        (click)="onScoreCardClick($event, asset)">
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

              <!-- Back face — Score card -->
              <div class="tile-face tile-back" (click)="onFlipBack($event, asset)">
                <div class="sc-loading" *ngIf="tileScoreLoading.has(asset.id)">
                  <mat-spinner diameter="24"></mat-spinner>
                </div>
                <div class="sc-error" *ngIf="!tileScoreLoading.has(asset.id) && tileScoreError.has(asset.id)">
                  Could not load scores.
                </div>
                <ng-container *ngIf="!tileScoreLoading.has(asset.id) && !tileScoreError.has(asset.id)">
                  <div class="sc-header">
                    <div class="sc-header-main">
                      <div class="sc-label">BRAINSUITE SCORE</div>
                      <div class="sc-total">
                        <span class="sc-total-score" [style.borderColor]="getPillarColor(asset.total_rating)">{{ asset.total_score | number:'1.0-0' }}</span>
                      </div>
                    </div>
                    <div class="sc-thumb">
                      <img *ngIf="getTileThumbnail(asset) as thumb" [src]="thumb" [alt]="asset.ad_name" (error)="onImgError($event)" />
                      <img *ngIf="!getTileThumbnail(asset)" [src]="getPlatformOverlayIcon(asset.platform)" class="sc-thumb-icon" [alt]="asset.platform" />
                    </div>
                  </div>
                  <div class="sc-divider"></div>
                  <div class="sc-pillars">
                    <div class="sc-pillar-row" *ngFor="let pillar of tileScoreCache.get(asset.id) || []">
                      <span class="sc-pillar-name">{{ pillar.name }}</span>
                      <div class="sc-bar-track">
                        <div class="sc-bar-fill" [style.width.%]="pillar.score ?? 0" [style.background]="getPillarColor(pillar.rating)"></div>
                      </div>
                      <span class="sc-pillar-score">{{ pillar.score != null ? (pillar.score | number:'1.0-0') : '–' }}</span>
                    </div>
                  </div>
                  <div class="sc-back-hint"><i class="bi bi-arrow-counterclockwise"></i> tap to flip back</div>
                </ng-container>
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
          <mat-form-field appearance="outline" class="page-size-field">
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
        <hr class="context-divider" />
        <button (click)="rescoreAsset(contextMenu.asset)">
          <i class="bi bi-lightning-charge"></i> Score now
        </button>
        <button *ngIf="needsRedownload(contextMenu.asset)" (click)="redownloadAsset(contextMenu.asset)">
          <i class="bi bi-cloud-download"></i> Re-download asset
        </button>
        <button (click)="triggerAutofill(contextMenu.asset)">
          <i class="bi bi-stars"></i> Trigger autofill
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
          <h4>Score vs. {{ currentMetricOption.label }}</h4>
          <button mat-icon-button (click)="closeCorrelationDrawer()" aria-label="Close correlation drawer">
            <i class="bi bi-x" style="font-size:20px"></i>
          </button>
        </div>

        <!-- Metric selector -->
        <div class="correlation-metric-row">
          <button *ngFor="let opt of correlationMetricOptions"
            class="metric-btn"
            [class.metric-btn-active]="correlationMetric === opt.value"
            (click)="onCorrelationMetricChange(opt.value)">
            {{ opt.label }}
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
          <p>No scored creatives with ROAS data meet the current filters. Try lowering the minimum spend threshold or broadening the date range.</p>
        </div>

        <!-- Chart -->
        <div *ngIf="!correlationLoading && !correlationError && correlationEligibleCount > 0"
             echarts [options]="scatterOptions" (chartClick)="onScatterClick($event)"
             class="echart-box" style="height:420px;margin:0 24px"></div>

        <!-- Legend -->
        <div *ngIf="!correlationLoading && !correlationError && correlationEligibleCount > 0"
             class="correlation-legend">
          <span class="correlation-legend-item"><span class="legend-dot" style="background:#2ECC71"></span> Positive ACE</span>
          <span class="correlation-legend-item"><span class="legend-dot" style="background:#F39C12"></span> Moderate ACE</span>
          <span class="correlation-legend-item"><span class="legend-dot" style="background:#E74C3C"></span> Low ACE</span>
        </div>

        <!-- 99th pct annotation -->
        <div *ngIf="!correlationLoading && !correlationError && correlationEligibleCount > 0"
             class="correlation-cap-note">{{ currentMetricOption.label }} capped at 99th pct.</div>
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

    // Shared toolbar dropdown — used by Format, Account, Sort
    .tbd {
      position: relative;
      flex-shrink: 0;
    }
    .tbd-trigger {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-radius: 8px;
      border: 1px solid var(--border);
      outline: none;
      background: var(--bg-card);
      color: var(--text-primary);
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      height: 36px;
      white-space: nowrap;
      font-family: inherit;
      user-select: none;
      transition: all 0.15s;
      &:hover { border-color: var(--accent); background: var(--bg-hover); }
    }
    .tbd-arrow {
      font-size: 12px;
      color: var(--text-secondary);
      flex-shrink: 0;
    }
    .tbd-panel {
      position: absolute;
      top: calc(100% + 4px);
      left: 0;
      z-index: 1000;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 8px;
      min-width: 160px;
      max-height: 280px;
      overflow-y: auto;
      box-shadow: 0 4px 16px rgba(0,0,0,0.4);
      padding: 4px 0;
    }
    .tbd-option {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 7px 12px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      font-family: inherit;
      color: var(--text-primary);
      white-space: nowrap;
      &:hover { background: var(--accent-light); }
    }
    .tbd-check {
      width: 14px;
      text-align: center;
      color: transparent;
      font-size: 13px;
      flex-shrink: 0;
      &.checked { color: var(--accent); }
    }
    .tbd-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .tbd-badge {
      font-size: 9px;
      padding: 1px 4px;
      border-radius: 3px;
      background: rgba(255,255,255,0.1);
      color: var(--text-secondary);
      flex-shrink: 0;
    }

    // Phase 22 — Metadata filter + Ad Account platform grouping styles
    .tbd-trigger.has-active-filters { border-color: var(--accent); background: var(--accent-light); }
    .metadata-menu { min-width: 200px; }
    .metadata-back-row .bi-arrow-left { margin-right: 8px; }
    .metadata-input-row { padding: 4px 16px !important; }
    .metadata-input {
      width: 100%;
      padding: 8px 16px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--bg-hover);
      color: var(--text-primary);
      font-size: 13px;
      font-weight: 500;
      font-family: inherit;
      outline: none;
    }
    .metadata-input:focus { border-color: var(--accent); }
    .tbd-name.muted { color: var(--text-muted); }
    .spin { display: inline-block; animation: spin 1s linear infinite; }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    .metadata-chip-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-top: 8px;
      margin-bottom: 8px;
      padding: 0;
    }
    .metadata-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 8px;
      border-radius: 16px;
      background: var(--bg-card);
      border: 1px solid var(--border);
      font-size: 13px;
      font-weight: 500;
      color: var(--text-primary);
      white-space: nowrap;
      transition: background 0.15s, border-color 0.15s;
    }
    .metadata-chip:hover { background: var(--accent-light); border-color: var(--accent); }
    .metadata-chip:hover .chip-dismiss { color: var(--accent); }
    .metadata-chip:focus-within { outline: 2px solid var(--accent); outline-offset: 2px; }
    .chip-dismiss {
      background: none;
      border: none;
      padding: 0;
      margin-left: 2px;
      cursor: pointer;
      color: var(--text-secondary);
      font-size: 13px;
      line-height: 1;
      display: inline-flex;
      align-items: center;
    }
    .chip-dismiss:hover { color: var(--accent); }
    .chip-clear-all {
      background: none;
      border: none;
      padding: 4px 8px;
      color: var(--text-muted);
      font-size: 13px;
      font-weight: 500;
      font-family: inherit;
      cursor: pointer;
    }
    .chip-clear-all:hover { color: var(--accent); }
    .tbd-group-header {
      padding: 4px 8px;
      font-size: 9px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
      pointer-events: none;
      user-select: none;
    }
    .tbd-group-header-item.mat-mdc-menu-item[disabled] {
      padding: 0 8px;
      min-height: 24px;
      font-size: 9px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted) !important;
      opacity: 1 !important;
      cursor: default;
    }
    .tbd-group-divider { height: 1px; background: var(--border); margin: 4px 0; }
    .account-menu { min-width: 220px; }
    .account-search-row { padding: 4px 8px !important; }
    .account-search-input { width: 100%; padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-hover); color: var(--text-primary); font-size: 13px; font-weight: 500; font-family: inherit; outline: none; }
    .account-search-input:focus { border-color: var(--accent); }

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
      overflow: visible;
      cursor: pointer;
      transition: all var(--transition);
      user-select: none;
      perspective: 800px;

      &:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
        outline: 1px solid var(--accent);
      }

      &.selected {
        outline: 2px solid rgba(255,119,0,0.6);
        outline-offset: 1px;
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

    /* ─── Tile flip ─── */
    .tile-flip-inner {
      position: relative;
      transform-style: preserve-3d;
      transition: transform 0.45s cubic-bezier(0.4, 0, 0.2, 1);
      &.tile-flipped { transform: rotateY(180deg); }
    }
    .tile-face {
      backface-visibility: hidden;
      -webkit-backface-visibility: hidden;
    }
    .tile-front { border-radius: var(--border-radius-lg); overflow: hidden; }
    .tile-back {
      position: absolute; inset: 0;
      transform: rotateY(180deg);
      background: var(--bg-card);
      border-radius: var(--border-radius-lg);
      overflow: hidden;
      padding: 14px;
      display: flex; flex-direction: column;
      cursor: pointer;
    }
    .sc-loading, .sc-error {
      display: flex; align-items: center; justify-content: center;
      flex: 1; font-size: 12px; color: var(--text-muted);
    }
    .sc-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
    .sc-header-main { flex: 1; }
    .sc-thumb {
      width: 76px; height: 76px; border-radius: 8px; overflow: hidden;
      flex-shrink: 0; background: var(--bg-hover);
      img { width: 100%; height: 100%; object-fit: cover; }
      .sc-thumb-icon { padding: 12px; opacity: 0.5; object-fit: contain; }
    }
    .sc-label { font-size: 9px; font-weight: 700; letter-spacing: 1px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; }
    .sc-total { display: flex; align-items: center; }
    .sc-total-score {
      font-size: 22px; font-weight: 800; line-height: 1;
      width: 48px; height: 48px;
      display: flex; align-items: center; justify-content: center;
      border: 3px solid; border-radius: 50%;
    }
    .sc-divider { height: 1px; background: var(--border); margin: 6px 0; }
    .sc-pillars { flex: 1; display: flex; flex-direction: column; gap: 4px; }
    .sc-pillar-row { display: grid; grid-template-columns: 80px 1fr 24px; align-items: center; gap: 5px; }
    .sc-pillar-name { font-size: 10px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .sc-bar-track { height: 5px; background: var(--bg-hover); border-radius: 3px; overflow: hidden; }
    .sc-bar-fill { height: 100%; border-radius: 3px; }
    .sc-pillar-score { font-size: 10px; font-weight: 600; text-align: right; }
    .sc-back-hint { font-size: 9px; color: var(--text-muted); text-align: center; margin-top: 4px; display: flex; align-items: center; justify-content: center; gap: 3px; }

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
        background: rgba(46, 204, 113, 0.15);
        color: #2ECC71;
      }
      &.tag-below {
        background: rgba(231, 76, 60, 0.15);
        color: #E74C3C;
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

    /* Phase 23 (DASH-03): Duration filter — clone .score-slider-wrapper exactly */
    .duration-slider-wrapper {
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
        min-width: 70px;
        text-align: center;
      }

      ngx-slider {
        flex: 1;
      }
    }

    /* Phase 23 (DASH-03 D-08): NULL duration callout — small info text below chip row */
    .duration-null-callout {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 4px;
      margin-bottom: 4px;
      font-size: 13px;
      font-weight: 500;
      color: var(--text-secondary);

      .bi-info-circle {
        font-size: 13px;
        color: var(--accent);
        flex-shrink: 0;
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
      width: 560px;
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

    .correlation-metric-row {
      display: flex;
      gap: 6px;
      padding: 10px 24px;
      border-bottom: 1px solid var(--border);
    }
    .metric-btn {
      font-size: 12px;
      font-weight: 600;
      padding: 4px 12px;
      border-radius: 20px;
      border: 1px solid var(--border);
      background: transparent;
      color: var(--text-secondary);
      cursor: pointer;
      transition: all 0.15s;
      &:hover { border-color: var(--accent); color: var(--text-primary); }
    }
    .metric-btn-active {
      background: var(--accent);
      border-color: var(--accent);
      color: white;
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
  adAccounts: { ad_account_id: string; ad_account_name: string; platform: string }[] = [];
  groupedAdAccounts: Array<{platform: string; accounts: Array<{ad_account_id: string; ad_account_name: string; platform: string}>}> = [];
  showPlatformGrouping = false;
  adAccountSearch = '';
  selectedAdAccountIds: string[] = [];
  adAccountDropdownOpen = false;

  readonly trackByPlatform = (_: number, g: {platform: string}) => g.platform;
  readonly trackByAccountId = (_: number, a: {ad_account_id: string}) => a.ad_account_id;

  get filteredGroupedAdAccounts(): Array<{platform: string; accounts: Array<{ad_account_id: string; ad_account_name: string; platform: string}>}> {
    const q = this.adAccountSearch.toLowerCase();
    if (!q) return this.groupedAdAccounts;
    return this.groupedAdAccounts
      .map(g => ({...g, accounts: g.accounts.filter(a => a.ad_account_name.toLowerCase().includes(q))}))
      .filter(g => g.accounts.length > 0);
  }

  // Metadata filter state (Phase 22 DASH-01)
  metadataFields: Array<{id: string; name: string; label: string; field_type: string}> = [];
  selectedMetadataFieldId: string | null = null;
  selectedMetadataFieldName: string | null = null;
  selectedMetadataFieldLabel: string | null = null;
  metadataFieldValues: string[] = [];
  metadataValueInput = '';
  activeMetadataFilters: Array<{field: string; fieldLabel: string; value: string}> = [];
  metadataValuesLoading = false;
  metadataValuesError = false;

  formatDropdownOpen = false;
  sortDropdownOpen = false;

  sortOptions = [
    { value: 'spend', label: 'Spend' },
    { value: 'ctr', label: 'CTR' },
    { value: 'roas', label: 'ROAS' },
    { value: 'cpm', label: 'CPM' },
    { value: 'vtr', label: 'VTR' },
    { value: 'total_score', label: 'ACE Score' },
    { value: 'platform', label: 'Platform' },
    { value: 'format', label: 'Format' },
  ];

  get formatLabel(): string {
    const map: Record<string, string> = { '': 'All Formats', IMAGE: 'Image', VIDEO: 'Video', CAROUSEL: 'Carousel' };
    return map[this.selectedFormat] ?? this.selectedFormat;
  }

  get sortLabel(): string {
    return 'Sort: ' + (this.sortOptions.find(o => o.value === this.sortBy)?.label ?? this.sortBy);
  }

  get filteredMetadataValues(): string[] {
    const q = this.metadataValueInput.toLowerCase();
    return this.metadataFieldValues.filter(v => v.toLowerCase().startsWith(q));
  }

  private _buildGroupedAccounts(): void {
    const order = ['META', 'TIKTOK', 'GOOGLE_ADS', 'DV360'];
    const map = new Map<string, Array<{ad_account_id: string; ad_account_name: string; platform: string}>>();
    for (const acc of this.adAccounts) {
      if (!map.has(acc.platform)) map.set(acc.platform, []);
      map.get(acc.platform)!.push(acc);
    }
    const result: Array<{platform: string; accounts: Array<{ad_account_id: string; ad_account_name: string; platform: string}>}> = [];
    for (const platform of order) {
      if (map.has(platform)) result.push({platform, accounts: map.get(platform)!});
    }
    for (const [platform, accounts] of map) {
      if (!order.includes(platform)) result.push({platform, accounts});
    }
    this.groupedAdAccounts = result;
    this.showPlatformGrouping = map.size > 1;
  }

  get metadataButtonLabel(): string {
    return this.activeMetadataFilters.length === 0 ? 'Metadata' : `Metadata (${this.activeMetadataFilters.length})`;
  }

  /** True when duration filter handles have been moved from full bounds (D-06). */
  get isDurationFilterActive(): boolean {
    const floor = this.durationSliderOptions.floor ?? 0;
    const ceil = this.durationSliderOptions.ceil ?? 3600;
    return this.durationMin > floor || this.durationMax < ceil;
  }

  sortBy = 'spend';
  sortOrder = 'desc';
  page = 1;
  pageSize = 50;
  total = 0;
  totalPages = 1;

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

  // Phase 23: duration filter state (D-01 D-05 D-07)
  durationMin = 0;
  durationMax = 3600;
  hasVideoAssets = false;
  /** True when the bounds endpoint has returned real (non-default) duration data. */
  hasDurationData = false;
  readonly durationSliderRefresh = new EventEmitter<void>();
  nullDurationCount = 0;
  loadingDurationBounds = false;
  durationSliderOptions: Options = {
    floor: 0,
    ceil: 3600,
    step: 1,
    noSwitching: true,
    disabled: false,
    translate: (value: number) => this.formatDuration(value),
  };

  selectedAssets: string[] = [];
  lastSelectedId: string | null = null;

  contextMenu = { visible: false, x: 0, y: 0, asset: null as DashboardAsset | null };

  private assetDetailCache = new Map<string, DashboardAsset>();

  flippedTiles = new Set<string>();
  tileScoreCache = new Map<string, any[]>();
  tileScoreLoading = new Set<string>();
  tileScoreError = new Set<string>();

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
  correlationMinSpend = 0;
  correlationMinSpendOptions: Options = {
    floor: 0,
    ceil: 1000,
    step: 10,
    showTicks: false,
    hideLimitLabels: true,
    hidePointerLabels: true,
  };
  scatterOptions: EChartsOption = {};

  correlationMetric = 'roas';
  readonly correlationMetricOptions = [
    { value: 'roas', label: 'ROAS', yLabel: 'ROAS', format: (v: number) => `${v.toFixed(2)}x` },
    { value: 'ctr', label: 'CTR', yLabel: 'CTR (%)', format: (v: number) => `${v.toFixed(2)}%` },
    { value: 'cvr', label: 'CVR', yLabel: 'CVR (%)', format: (v: number) => `${v.toFixed(2)}%` },
    { value: 'vtr', label: 'VTR', yLabel: 'VTR (%)', format: (v: number) => `${v.toFixed(2)}%` },
    { value: 'cpm', label: 'CPM', yLabel: 'CPM ($)', format: (v: number) => `$${v.toFixed(2)}` },
    { value: 'cpa', label: 'CPA', yLabel: 'CPA ($)', format: (v: number) => `$${v.toFixed(2)}` },
  ];

  get currentMetricOption() {
    return this.correlationMetricOptions.find(o => o.value === this.correlationMetric)!;
  }

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private dialog: MatDialog,
    private route: ActivatedRoute,
    private router: Router,
    private snackBar: MatSnackBar,
    private jobMonitor: JobMonitorService,
  ) {}

  get orgCurrency(): string {
    return this.auth.currentUser?.organization_currency || 'USD';
  }

  ngOnInit(): void {
    // Debounced score filter
    this.scoreChange$.pipe(
      debounceTime(400),
      takeUntil(this.destroy$)
    ).subscribe(() => this.onFilterChange());

    // Load ad accounts for filter dropdown
    this.api.get<{ items: any[] }>('/platforms/connections').subscribe({
      next: (res) => {
        const conns = res.items || [];
        this.adAccounts = conns.map(c => ({
          ad_account_id: c.ad_account_id,
          ad_account_name: c.ad_account_name || c.ad_account_id,
          platform: c.platform,
        }));
        this._buildGroupedAccounts();
        this.loadMetadataFields();
      },
    });

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
      a => { const v = (a as any)[this.correlationMetric]; return v != null && (a.spend ?? 0) >= this.correlationMinSpend; }
    ).length;
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
    const metricOpt = this.currentMetricOption;
    const eligible = this.correlationAssets.filter(
      a => { const v = (a as any)[this.correlationMetric]; return v != null && (a.spend ?? 0) >= this.correlationMinSpend; }
    );

    if (eligible.length === 0) {
      this.scatterOptions = {};
      return;
    }

    const metricValues = eligible.map(a => (a as any)[this.correlationMetric] as number).sort((x, y) => x - y);
    const scoreValues = eligible.map(a => a.total_score).sort((x, y) => x - y);

    const cap = metricValues[Math.floor(metricValues.length * 0.99)] ?? metricValues[metricValues.length - 1] ?? 1;

    const median = (arr: number[]): number => {
      const mid = Math.floor(arr.length / 2);
      return arr.length % 2 !== 0 ? arr[mid] : (arr[mid - 1] + arr[mid]) / 2;
    };

    const medianScore = eligible.length === 1 ? eligible[0].total_score : median(scoreValues);
    const medianMetric = eligible.length === 1 ? metricValues[0] : median(metricValues);

    const scatterData = eligible.map(a => [
      a.total_score,
      Math.min((a as any)[this.correlationMetric] as number, cap),
      a,
    ]);

    const ratingColor = (rating: string | null): string => {
      switch (rating) {
        case 'positive': return '#2ECC71';
        case 'medium': return '#F39C12';
        case 'negative': return '#E74C3C';
        default: return '#707070';
      }
    };

    this.scatterOptions = {
      grid: { top: 40, right: 64, bottom: 50, left: 50 },
      xAxis: {
        name: 'ACE Score',
        min: 0,
        max: 100,
        nameLocation: 'center',
        nameGap: 30,
        nameTextStyle: { color: '#ccc', fontSize: 12 },
        axisLine: { lineStyle: { color: '#777' } },
        axisTick: { lineStyle: { color: '#777' } },
        axisLabel: { color: '#ccc', fontSize: 12 },
        splitLine: { lineStyle: { color: '#555', opacity: 0.5 } },
      },
      yAxis: {
        name: metricOpt.yLabel,
        min: 0,
        nameTextStyle: { color: '#ccc', fontSize: 12 },
        axisLine: { lineStyle: { color: '#777' } },
        axisTick: { lineStyle: { color: '#777' } },
        axisLabel: { color: '#ccc', fontSize: 12 },
        splitLine: { lineStyle: { color: '#555', opacity: 0.5 } },
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
          const yFormatted = metricOpt.format(params.data[1] as number);
          return `<div style="display:flex;gap:10px;align-items:flex-start;max-width:280px">
            <img src="${thumb}" style="width:48px;height:48px;object-fit:cover;border-radius:4px" />
            <div>
              <div style="font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px">${asset.ad_name || 'Untitled'}</div>
              <div style="font-size:14px;color:var(--text-secondary);margin-top:4px">
                Score: ${params.data[0]} &middot; ${metricOpt.label}: ${yFormatted} &middot; $${((asset.spend ?? 0) as number).toFixed(0)} &middot; ${asset.platform}
              </div>
            </div>
          </div>`;
        },
      },
      graphic: [
        { type: 'text', right: 30, top: 50, style: { text: 'Stars', fill: '#ffffff', fontSize: 12, fontWeight: '700' } },
        { type: 'text', left: 70, top: 50, style: { text: 'Workhorses', fill: '#ffffff', fontSize: 12, fontWeight: '700' } },
        { type: 'text', right: 30, bottom: 60, style: { text: 'Question Marks', fill: '#ffffff', fontSize: 12, fontWeight: '700' } },
        { type: 'text', left: 70, bottom: 60, style: { text: 'Laggards', fill: '#ffffff', fontSize: 12, fontWeight: '700' } },
      ],
      series: [{
        type: 'scatter',
        symbolSize: 12,
        data: scatterData,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#666', type: 'dashed', width: 1 },
          label: {
            color: '#fff',
            fontSize: 11,
            fontWeight: 'bold',
            backgroundColor: 'rgba(0,0,0,0.55)',
            padding: [2, 5],
            borderRadius: 3,
          },
          data: [
            { xAxis: medianScore },
            { yAxis: medianMetric },
            { yAxis: cap, lineStyle: { color: 'rgba(255,119,0,0.5)', type: 'dashed' }, label: { color: '#FF7700' } },
          ],
        },
        itemStyle: {
          color: (params: any) => ratingColor((params.data[2] as CorrelationAsset).total_rating),
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

  onCorrelationMetricChange(metric: string): void {
    this.correlationMetric = metric;
    this.buildScatterChart();
  }

  /** Format seconds as human-readable duration. Locked per Phase 23 CONTEXT.md §Specifics. */
  formatDuration(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
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
    if (this.selectedAdAccountIds.length > 0) params['ad_account_ids'] = this.selectedAdAccountIds.join(',');
    if (this.activeMetadataFilters.length > 0) params['metadata_filter'] = this.activeMetadataFilters.map(f => `${f.field}:${f.value}`);
    if (this.isDurationFilterActive) {
      params['duration_min'] = this.durationMin;
      params['duration_max'] = this.durationMax;
    }

    this.api.get<DashboardAssetsResponse>('/dashboard/assets', params).subscribe({
      next: (d) => {
        this.assets = d.items;
        this.total = d.total;
        this.totalPages = d.total_pages;
        this.loading = false;
        // Phase 23 (D-05, D-07): always call loadDurationBounds after data loads;
        // it is the authoritative source for hasVideoAssets (filter-aware, not page-scoped).
        this.nullDurationCount = d.null_duration_count ?? 0;
        this.loadDurationBounds();
        // Only enable slider once we've seen scored assets — don't disable when filtered results are empty
        if (this.assets.some((a: any) => a.scoring_status === 'COMPLETE')) {
          this.hasAnyScored = true;
        }
        this.sliderDisabled = !this.hasAnyScored;
        this.sliderOptions = { ...this.sliderOptions, disabled: !this.hasAnyScored };
        this.flippedTiles.clear();
        this.tileScoreError.clear();
        this.preloadAssetDetails();
        this.preloadScoreDetails();
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

  onScoreChange(): void {
    this.scoreChange$.next();
  }

  /** Load filter-aware duration bounds (D-01, D-02). Triggered from loadData response handler — NOT from slider events (avoid circular refresh, Pitfall 3). */
  loadDurationBounds(): void {
    this.loadingDurationBounds = true;
    const params: any = {
      date_from: this.dateFrom,
      date_to: this.dateTo,
    };
    if (this.selectedPlatforms?.size) {
      params.platforms = [...this.selectedPlatforms].join(',');
    }
    if (this.selectedFormat) params.formats = this.selectedFormat;
    if (this.selectedAdAccountIds.length > 0) params.ad_account_ids = this.selectedAdAccountIds.join(',');
    if (this.activeMetadataFilters.length > 0) {
      params.metadata_filter = this.activeMetadataFilters.map((f: any) => `${f.field}:${f.value}`);
    }
    // NOTE: do NOT pass duration_min / duration_max — that would be circular (D-02)

    this.api.get<{ min_duration: number | null; max_duration: number | null; has_video_assets: boolean }>('/dashboard/duration-bounds', params).subscribe({
      next: (res) => {
        // has_video_assets is authoritative — backend counts VIDEOs with current filters regardless of backfill state.
        this.hasVideoAssets = res.has_video_assets;
        const hasRealBounds = res.min_duration != null && res.max_duration != null && res.max_duration >= res.min_duration;
        this.hasDurationData = hasRealBounds;
        if (hasRealBounds) {
          const newFloor = res.min_duration!;
          const newCeil = res.max_duration!;
          const boundsChanged = newFloor !== this.durationSliderOptions.floor || newCeil !== this.durationSliderOptions.ceil;
          this.durationSliderOptions = { ...this.durationSliderOptions, floor: newFloor, ceil: newCeil };
          // Reset handles to full range whenever bounds change (other filters changed) or no filter is active.
          // Preserving a stale selection after bounds change silently applies an unintended filter.
          if (boundsChanged || !this.isDurationFilterActive) {
            this.durationMin = newFloor;
            this.durationMax = newCeil;
          }
          this.durationSliderRefresh.emit();
        }
        this.loadingDurationBounds = false;
      },
      error: () => {
        this.hasVideoAssets = false;
        this.hasDurationData = false;
        this.loadingDurationBounds = false;
      },
    });
  }

  /** Reset duration filter to full range; triggered by chip dismiss button. */
  clearDurationFilter(): void {
    this.durationMin = this.durationSliderOptions.floor ?? 0;
    this.durationMax = this.durationSliderOptions.ceil ?? 3600;
    this.onFilterChange();
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

  toggleAdAccount(id: string): void {
    const idx = this.selectedAdAccountIds.indexOf(id);
    if (idx >= 0) {
      this.selectedAdAccountIds.splice(idx, 1);
    } else {
      this.selectedAdAccountIds.push(id);
    }
    this.onFilterChange();
  }

  loadMetadataFields(): void {
    this.api.get<{fields: any[]}>('/dashboard/metadata-fields').subscribe({
      next: (res) => {
        this.metadataFields = res.fields ?? [];
      },
      error: () => { /* silent — empty list state is acceptable */ },
    });
  }

  selectMetadataField(field: {id: string; name: string; label: string; field_type: string}): void {
    this.selectedMetadataFieldId = field.id;
    this.selectedMetadataFieldName = field.name;
    this.selectedMetadataFieldLabel = field.label;
    this.metadataValueInput = '';
    this.metadataFieldValues = [];
    this.metadataValuesError = false;
    this.metadataValuesLoading = true;
    this.api.get<{values: string[]}>(`/dashboard/metadata-fields/${field.id}/values`).subscribe({
      next: (res) => {
        this.metadataFieldValues = res.values ?? [];
        this.metadataValuesLoading = false;
      },
      error: () => {
        this.metadataValuesError = true;
        this.metadataValuesLoading = false;
      },
    });
  }

  backToFieldList(): void {
    this.selectedMetadataFieldId = null;
    this.selectedMetadataFieldName = null;
    this.selectedMetadataFieldLabel = null;
    this.metadataValueInput = '';
    this.metadataFieldValues = [];
  }

  isMetadataValueSelected(value: string): boolean {
    return this.activeMetadataFilters.some(f => f.field === this.selectedMetadataFieldName && f.value === value);
  }

  selectMetadataValue(value: string): void {
    const existingIndex = this.activeMetadataFilters.findIndex(f => f.field === this.selectedMetadataFieldName && f.value === value);
    if (existingIndex >= 0) {
      this.activeMetadataFilters.splice(existingIndex, 1);
    } else {
      this.activeMetadataFilters.push({field: this.selectedMetadataFieldName!, fieldLabel: this.selectedMetadataFieldLabel!, value});
    }
    this.onFilterChange();
  }

  removeMetadataFilter(index: number): void {
    this.activeMetadataFilters.splice(index, 1);
    this.onFilterChange();
  }

  clearAllMetadataFilters(): void {
    this.activeMetadataFilters = [];
    this.onFilterChange();
  }

  retryLoadMetadataValues(): void {
    if (!this.selectedMetadataFieldId) return;
    const fieldId = this.selectedMetadataFieldId;
    this.metadataValuesError = false;
    this.metadataValuesLoading = true;
    this.api.get<{values: string[]}>(`/dashboard/metadata-fields/${fieldId}/values`).subscribe({
      next: (res) => {
        this.metadataFieldValues = res.values ?? [];
        this.metadataValuesLoading = false;
      },
      error: () => {
        this.metadataValuesError = true;
        this.metadataValuesLoading = false;
      },
    });
  }

  getPlatformDisplayName(platform: string): string {
    const names: Record<string, string> = {META: 'META', TIKTOK: 'TIKTOK', GOOGLE_ADS: 'GOOGLE ADS', DV360: 'DV360'};
    return names[platform] ?? platform;
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

  private preloadScoreDetails(): void {
    const toFetch = this.assets.filter(
      a => a.scoring_status === 'COMPLETE' && !this.tileScoreCache.has(a.id) && !this.tileScoreLoading.has(a.id)
    );
    for (const asset of toFetch) {
      this.tileScoreLoading.add(asset.id);
      this.api.getScoreDetail(asset.id).subscribe({
        next: (detail: any) => {
          const cats = detail?.score_dimensions?.legResults?.[0]?.executiveSummary?.categories ?? [];
          this.tileScoreCache.set(asset.id, cats);
          this.tileScoreLoading.delete(asset.id);
        },
        error: () => {
          this.tileScoreLoading.delete(asset.id);
        },
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
    const isSingle = assetIds.length === 1;
    const cached = isSingle ? (this.assetDetailCache.get(assetIds[0]) as any) : null;
    this.dialog.open(EditMetadataDialogComponent, {
      width: '480px',
      data: {
        assetIds,
        singleAssetName: isSingle ? (asset.ad_name || undefined) : undefined,
        existingValues: isSingle ? (cached?.metadata_values ?? undefined) : undefined,
      },
    }).afterClosed().subscribe(result => {
      if (result?.saved) {
        for (const id of assetIds) {
          this.assetDetailCache.delete(id);
        }
        this.loadData();
        this.snackBar.open('Metadata saved', 'OK', { duration: 3000 });
      }
    });
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

  onScoreCardClick(event: MouseEvent, asset: DashboardAsset): void {
    event.stopPropagation();
    if (this.flippedTiles.has(asset.id)) {
      this.flippedTiles.delete(asset.id);
      return;
    }
    this.flippedTiles.add(asset.id);
    if (!this.tileScoreCache.has(asset.id) && !this.tileScoreLoading.has(asset.id)) {
      this.tileScoreLoading.add(asset.id);
      this.tileScoreError.delete(asset.id);
      this.api.getScoreDetail(asset.id).subscribe({
        next: (detail: any) => {
          const cats = detail?.score_dimensions?.legResults?.[0]?.executiveSummary?.categories ?? [];
          this.tileScoreCache.set(asset.id, cats);
          this.tileScoreLoading.delete(asset.id);
        },
        error: () => {
          this.tileScoreLoading.delete(asset.id);
          this.tileScoreError.add(asset.id);
        },
      });
    }
  }

  onFlipBack(event: MouseEvent, asset: DashboardAsset): void {
    event.stopPropagation();
    this.flippedTiles.delete(asset.id);
  }

  getTileRatingLabel(rating: string | null): string {
    switch (rating) {
      case 'positive': return 'GREEN';
      case 'medium': return 'AMBER';
      case 'negative': return 'RED';
      default: return '';
    }
  }

  getPillarColor(rating: string | null): string {
    switch (rating) {
      case 'positive': return '#2ECC71';
      case 'medium': return '#F39C12';
      case 'negative': return '#E74C3C';
      default: return 'var(--text-muted)';
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

  needsRedownload(asset: DashboardAsset | null): boolean {
    if (!asset) return false;
    return asset.asset_format === 'VIDEO' && (!asset.asset_url || !asset.asset_url.endsWith('.mp4'));
  }

  redownloadAsset(asset: DashboardAsset | null): void {
    if (!asset) return;
    this.contextMenu.visible = false;
    this.snackBar.open('Download queued — video will be ready in ~1 minute', '', { duration: 5000 });
    this.api.redownloadAsset(asset.id).subscribe({
      next: (res) => {
        this.jobMonitor.jobs$.pipe(
          map(jobs => jobs.find(j => j.job_id === res.job_id)),
          filter((job): job is NonNullable<typeof job> => !!job && (job.status === 'COMPLETE' || job.status === 'FAILED')),
          take(1),
          takeUntil(this.destroy$),
        ).subscribe(job => {
          if (job.status === 'COMPLETE') {
            this.api.get<DashboardAsset>(`/dashboard/assets/${asset.id}`, {}).subscribe(updated => {
              asset.asset_url = updated.asset_url;
              if (updated.thumbnail_url) asset.thumbnail_url = updated.thumbnail_url;
              const cached = this.assetDetailCache.get(asset.id) as any;
              if (cached) {
                cached.asset_url = updated.asset_url;
                if (updated.thumbnail_url) cached.thumbnail_url = updated.thumbnail_url;
              }
              this.snackBar.open('Video downloaded — autofill and scoring queued', 'OK', { duration: 4000 });
            });
          } else {
            this.snackBar.open('Download failed — check yt-dlp cookies in Admin settings', 'OK', { duration: 5000 });
          }
        });
      },
      error: (err) => {
        const msg = err?.error?.detail || 'Download failed. Check yt-dlp cookies.';
        this.snackBar.open(msg, 'OK', { duration: 5000 });
      },
    });
  }

  triggerAutofill(asset: DashboardAsset | null): void {
    if (!asset) return;
    this.contextMenu.visible = false;
    this.api.triggerAutofillForAsset(asset.id).subscribe({
      next: () => {
        this.snackBar.open('Autofill started…', 'OK', { duration: 3000 });
        interval(3000).pipe(
          take(40),
          switchMap(() => this.api.get<any>(`/dashboard/assets/${asset.id}`)),
          takeWhile(d => !['COMPLETE', 'FAILED'].includes(d.ai_inference_status), true),
        ).subscribe(d => {
          const status = d.ai_inference_status;
          if (status === 'COMPLETE' || status === 'FAILED') {
            console.log('[Autofill result]', {
              asset_id: asset.id,
              ad_name: asset.ad_name,
              status,
              metadata_values: d.metadata_values,
            });
            this.snackBar.open(
              status === 'COMPLETE' ? 'Autofill complete' : 'Autofill failed',
              'OK',
              { duration: 5000 },
            );
            this.assetDetailCache.set(asset.id, d);
            this.loadData();
          }
        });
      },
      error: () => this.snackBar.open('Failed to trigger autofill', 'OK', { duration: 4000 }),
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
