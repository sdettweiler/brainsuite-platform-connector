import { Component, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule } from '@angular/material/menu';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { Subject, debounceTime, takeUntil } from 'rxjs';
import { ApiService } from '../../core/services/api.service';
import { format, subDays } from 'date-fns';

@Component({
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule, FormsModule, MatButtonModule, MatIconModule,
    MatSelectModule, MatFormFieldModule, MatInputModule, MatMenuModule,
    MatDialogModule, MatTooltipModule, MatCheckboxModule,
  ],
  template: `
    <div class="page-enter dashboard-page">
      <!-- Toolbar -->
      <div class="toolbar card card-sm">
        <!-- Date range -->
        <div class="toolbar-group">
          <mat-form-field appearance="outline" class="date-field">
            <mat-label>From</mat-label>
            <input matInput type="date" [(ngModel)]="dateFrom" (change)="onFilterChange()" />
          </mat-form-field>
          <mat-form-field appearance="outline" class="date-field">
            <mat-label>To</mat-label>
            <input matInput type="date" [(ngModel)]="dateTo" (change)="onFilterChange()" />
          </mat-form-field>
        </div>

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
        <mat-form-field appearance="outline" class="filter-field">
          <mat-label>Format</mat-label>
          <mat-select [(ngModel)]="selectedFormat" (selectionChange)="onFilterChange()">
            <mat-option value="">All</mat-option>
            <mat-option value="IMAGE">Image</mat-option>
            <mat-option value="VIDEO">Video</mat-option>
            <mat-option value="CAROUSEL">Carousel</mat-option>
          </mat-select>
        </mat-form-field>

        <!-- Sort -->
        <mat-form-field appearance="outline" class="filter-field">
          <mat-label>Sort by</mat-label>
          <mat-select [(ngModel)]="sortBy" (selectionChange)="onFilterChange()">
            <mat-option value="spend">Spend</mat-option>
            <mat-option value="ctr">CTR</mat-option>
            <mat-option value="roas">ROAS</mat-option>
            <mat-option value="cpm">CPM</mat-option>
            <mat-option value="vtr">VTR</mat-option>
            <mat-option value="ace_score">ACE Score</mat-option>
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
          <mat-icon>{{ sortOrder === 'desc' ? 'arrow_downward' : 'arrow_upward' }}</mat-icon>
        </button>

        <div class="toolbar-spacer"></div>

        <!-- Export button -->
        <button mat-stroked-button (click)="openExport()">
          <mat-icon>download</mat-icon>
          Export
        </button>
      </div>

      <!-- Aggregate Stats -->
      <div class="agg-stats" *ngIf="stats">
        <div class="agg-stat" *ngFor="let s of aggStats">
          <div class="agg-value">{{ s.value }}</div>
          <div class="agg-label">{{ s.label }}</div>
          <div class="agg-change" [class]="s.changeClass" *ngIf="s.change !== null">
            <mat-icon>{{ s.changeDir }}</mat-icon>
            {{ s.change }}
          </div>
        </div>
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
            <div class="tile-thumb">
              <img
                [src]="asset.thumbnail_url || '/assets/images/placeholder.svg'"
                [alt]="asset.ad_name"
                (error)="onImgError($event)"
              />
              <!-- Overlays -->
              <span class="overlay-format">{{ asset.asset_format }}</span>
              <span class="overlay-platform">
                <mat-icon [class]="'platform-' + asset.platform.toLowerCase()">
                  {{ getPlatformIcon(asset.platform) }}
                </mat-icon>
              </span>
              <div class="overlay-ace" [class]="getAceClass(asset.ace_score)">
                {{ asset.ace_score | number:'1.0-0' }}
              </div>
            </div>

            <!-- Tile body -->
            <div class="tile-body">
              <div class="tile-objective">{{ asset.campaign_objective || 'No objective' }}</div>
              <div class="tile-name">{{ asset.ad_name || 'Unnamed Ad' }}</div>
              <div class="tile-metrics">
                <span>
                  <span class="metric-label">Spend</span>
                  <span class="metric-value">{{ asset.performance?.spend | currency:'USD':'symbol':'1.0-0' }}</span>
                </span>
                <span>
                  <span class="metric-label">CTR</span>
                  <span class="metric-value">{{ ((asset.performance?.ctr || 0) | number:'1.1-1') }}%</span>
                </span>
              </div>
              <div class="tile-roas" *ngIf="asset.performance?.roas">
                ROAS: <strong>{{ asset.performance.roas | number:'1.1-2' }}x</strong>
              </div>
              <div class="tile-tag" [class]="getTagClass(asset.performer_tag)">
                {{ asset.performer_tag }}
              </div>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div class="pagination" *ngIf="!loading && totalPages > 1">
          <button mat-icon-button [disabled]="page === 1" (click)="changePage(page - 1)">
            <mat-icon>chevron_left</mat-icon>
          </button>
          <span class="page-info">Page {{ page }} of {{ totalPages }} · {{ total | number }} assets</span>
          <button mat-icon-button [disabled]="page === totalPages" (click)="changePage(page + 1)">
            <mat-icon>chevron_right</mat-icon>
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
        <button (click)="openAssetDetail(contextMenu.asset)">
          <mat-icon>open_in_new</mat-icon> Open Report
        </button>
        <button (click)="openAssignProject(contextMenu.asset)">
          <mat-icon>folder</mat-icon> Assign to Project
        </button>
        <button [disabled]="selectedAssets.length < 2 || selectedAssets.length > 4" (click)="compareSelected()">
          <mat-icon>compare</mat-icon> Compare ({{ selectedAssets.length }})
        </button>
        <button (click)="openEditMetadata(contextMenu.asset)">
          <mat-icon>label</mat-icon> Edit Metadata
        </button>
      </div>

      <!-- Backdrop to close context menu -->
      <div class="context-backdrop" *ngIf="contextMenu.visible" (click)="contextMenu.visible = false"></div>
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

    .date-field { width: 140px; }
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
      mat-icon { font-size: 12px; width: 12px; height: 12px; }
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
      width: 24px; height: 24px;
      display: flex; align-items: center; justify-content: center;
      mat-icon { font-size: 14px; width: 14px; height: 14px; }
    }

    .overlay-ace {
      position: absolute; bottom: 6px; right: 6px;
      width: 32px; height: 32px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 10px; font-weight: 700;

      &.ace-high   { background: rgba(46,204,113,0.85);  color: white; }
      &.ace-medium { background: rgba(243,156,18,0.85);  color: white; }
      &.ace-low    { background: rgba(231,76,60,0.85);   color: white; }
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
      display: inline-block;
      font-size: 10px; font-weight: 600;
      padding: 2px 8px;
      border-radius: 12px;
      text-transform: uppercase;
      &.tag-top    { background: rgba(46,204,113,0.15); color: var(--success); }
      &.tag-avg    { background: var(--accent-light); color: var(--accent); }
      &.tag-below  { background: rgba(231,76,60,0.15);  color: var(--error); }
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
        mat-icon { font-size: 16px; width: 16px; height: 16px; color: var(--text-secondary); }
        &:hover { background: var(--bg-hover); }
        &:disabled { opacity: 0.4; cursor: not-allowed; }
      }
    }

    .context-backdrop {
      position: fixed; inset: 0; z-index: 999;
    }

    .skeleton-tile { pointer-events: none; }
  `],
})
export class DashboardComponent implements OnInit, OnDestroy {
  assets: any[] = [];
  stats: any = null;
  loading = true;

  dateFrom = format(subDays(new Date(), 30), 'yyyy-MM-dd');
  dateTo = format(subDays(new Date(), 1), 'yyyy-MM-dd');

  selectedPlatforms = new Set(['META', 'TIKTOK', 'YOUTUBE']);
  selectedFormat = '';
  sortBy = 'spend';
  sortOrder = 'desc';
  page = 1;
  pageSize = 50;
  total = 0;
  totalPages = 1;

  selectedAssets: string[] = [];
  lastSelectedId: string | null = null;

  contextMenu = { visible: false, x: 0, y: 0, asset: null as any };

  platforms = [
    { key: 'META', label: 'Meta', icon: 'facebook', color: '#1877F2', iconUrl: '/assets/images/icon-meta.png' },
    { key: 'TIKTOK', label: 'TikTok', icon: 'music_video', color: '#FF0050', iconUrl: '/assets/images/icon-tiktok.png' },
    { key: 'YOUTUBE', label: 'YouTube', icon: 'smart_display', color: '#FF0000', iconUrl: '/assets/images/icon-youtube.png' },
  ];

  private destroy$ = new Subject<void>();

  constructor(
    private api: ApiService,
    private dialog: MatDialog,
    private route: ActivatedRoute,
    private router: Router,
  ) {}

  ngOnInit(): void {
    // Handle query params (from homepage navigation or direct link)
    this.route.queryParams.pipe(takeUntil(this.destroy$)).subscribe(params => {
      if (params['platforms']) {
        this.selectedPlatforms = new Set([params['platforms'].toUpperCase()]);
      }
      this.loadData();
      if (params['assetId']) {
        this.openAssetById(params['assetId']);
      }
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  get aggStats(): any[] {
    if (!this.stats) return [];
    const s = this.stats;
    return [
      {
        label: 'Total Spend',
        value: new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(s.total_spend || 0),
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

  private pctChange(curr: number, prev: number): string | null {
    if (!prev) return null;
    const pct = ((curr - prev) / prev * 100).toFixed(1);
    return `${pct}%`;
  }

  private changeClass(curr: number, prev: number): string {
    if (!prev) return 'change-neutral';
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

    this.api.get<any>('/dashboard/assets', params).subscribe({
      next: (d) => {
        this.assets = d.items;
        this.total = d.total;
        this.totalPages = d.total_pages;
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });

    this.api.get<any>('/dashboard/stats', params).subscribe({
      next: (s) => this.stats = s,
    });
  }

  onFilterChange(): void {
    this.page = 1;
    this.loadData();
  }

  togglePlatform(key: string): void {
    if (this.selectedPlatforms.has(key)) {
      if (this.selectedPlatforms.size > 1) this.selectedPlatforms.delete(key);
    } else {
      this.selectedPlatforms.add(key);
    }
    this.onFilterChange();
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
  selectAsset(event: MouseEvent, asset: any): void {
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

  onRightClick(event: MouseEvent, asset: any): void {
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

  async openAssetDetail(asset: any): Promise<void> {
    this.contextMenu.visible = false;
    const { AssetDetailDialogComponent } = await import('../dashboard/dialogs/asset-detail-dialog.component');
    this.dialog.open(AssetDetailDialogComponent, {
      width: '90vw',
      maxWidth: '1100px',
      height: '85vh',
      data: { assetId: asset.id, dateFrom: this.dateFrom, dateTo: this.dateTo },
      panelClass: 'asset-detail-dialog',
    });
  }

  async openAssetById(assetId: string): Promise<void> {
    const { AssetDetailDialogComponent } = await import('../dashboard/dialogs/asset-detail-dialog.component');
    this.dialog.open(AssetDetailDialogComponent, {
      width: '90vw',
      maxWidth: '1100px',
      height: '85vh',
      data: { assetId, dateFrom: this.dateFrom, dateTo: this.dateTo },
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

  async openAssignProject(asset: any): Promise<void> {
    this.contextMenu.visible = false;
    const { AssignProjectDialogComponent } = await import('../dashboard/dialogs/assign-project-dialog.component');
    const assetIds = this.selectedAssets.length > 0 ? this.selectedAssets : [asset.id];
    this.dialog.open(AssignProjectDialogComponent, {
      width: '420px',
      data: { assetIds },
    });
  }

  async openEditMetadata(asset: any): Promise<void> {
    this.contextMenu.visible = false;
    const { EditMetadataDialogComponent } = await import('../dashboard/dialogs/edit-metadata-dialog.component');
    const assetIds = this.selectedAssets.length > 0 ? this.selectedAssets : [asset.id];
    this.dialog.open(EditMetadataDialogComponent, {
      width: '480px',
      data: { assetIds },
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
      YOUTUBE: 'smart_display',
    };
    return icons[platform] || 'ads_click';
  }

  getAceClass(score: number | null): string {
    if (!score) return 'ace-low';
    if (score >= 70) return 'ace-high';
    if (score >= 45) return 'ace-medium';
    return 'ace-low';
  }

  getTagClass(tag: string): string {
    if (tag === 'Top Performer') return 'tag-top';
    if (tag === 'Below Average') return 'tag-below';
    return 'tag-avg';
  }

  onImgError(event: Event): void {
    (event.target as HTMLImageElement).src = '/assets/images/placeholder.svg';
  }
}
