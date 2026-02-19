import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';

@Component({
  standalone: true,
  imports: [CommonModule, MatIconModule, MatButtonModule, MatTooltipModule],
  template: `
    <div class="page-enter">
      <!-- Welcome header -->
      <div class="welcome-header">
        <div>
          <h1>Welcome back, {{ firstName }}! 👋</h1>
          <p class="text-muted">Here's what's happening with your creative performance.</p>
        </div>
        <div class="date-badge">{{ today }}</div>
      </div>

      <!-- Overall Stats -->
      <div class="stats-grid" *ngIf="!loading">
        <div class="stat-card">
          <div class="stat-icon" style="background: rgba(52,152,219,0.15);">
            <mat-icon style="color: var(--accent)">image</mat-icon>
          </div>
          <div>
            <div class="stat-value">{{ data?.overall_stats?.total_assets | number }}</div>
            <div class="stat-label">Total Assets</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: rgba(46,204,113,0.15);">
            <mat-icon style="color: var(--success)">account_balance_wallet</mat-icon>
          </div>
          <div>
            <div class="stat-value">{{ data?.overall_stats?.total_accounts | number }}</div>
            <div class="stat-label">Ad Accounts</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: rgba(243,156,18,0.15);">
            <mat-icon style="color: var(--warning)">payments</mat-icon>
          </div>
          <div>
            <div class="stat-value">{{ data?.overall_stats?.total_spend | currency:'USD':'symbol':'1.0-0' }}</div>
            <div class="stat-label">Total Lifetime Spend</div>
          </div>
        </div>
      </div>

      <!-- Platform widgets -->
      <div class="widgets-section">
        <h2>Top Performing Ads — Last 7 Days</h2>

        <div class="widgets-grid">
          <ng-container *ngFor="let platform of platforms">
            <div class="platform-widget card" *ngIf="getWidget(platform).length > 0 || !loading">
              <!-- Widget header -->
              <div class="widget-header">
                <div class="platform-label">
                  <span class="platform-dot" [class]="'platform-' + platform.toLowerCase()"></span>
                  {{ platform }}
                </div>
                <a class="see-all-link" (click)="navigateToDashboard(platform)">
                  See all {{ platform }} ads →
                </a>
              </div>

              <!-- Skeleton loading -->
              <div *ngIf="loading" class="ads-list">
                <div class="ad-row skeleton-row" *ngFor="let s of [1,2,3]">
                  <div class="skeleton" style="width:56px;height:56px;border-radius:8px;flex-shrink:0;"></div>
                  <div style="flex:1;display:flex;flex-direction:column;gap:6px;">
                    <div class="skeleton" style="height:12px;width:80%;"></div>
                    <div class="skeleton" style="height:10px;width:50%;"></div>
                  </div>
                </div>
              </div>

              <!-- Actual ads -->
              <div class="ads-list" *ngIf="!loading">
                <div
                  class="ad-row"
                  *ngFor="let ad of getWidget(platform)"
                  (click)="openAdDetail(ad)"
                  matTooltip="View details"
                >
                  <div class="ad-thumb-container">
                    <img
                      class="ad-thumb"
                      [src]="ad.thumbnail_url || '/assets/images/placeholder.svg'"
                      [alt]="ad.ad_name"
                      (error)="onImgError($event)"
                    />
                    <span class="format-badge">{{ ad.asset_format || 'AD' }}</span>
                  </div>
                  <div class="ad-info">
                    <div class="ad-name">{{ ad.ad_name || 'Unnamed Ad' }}</div>
                    <div class="ad-metrics">
                      <span class="metric">
                        <mat-icon>payments</mat-icon>
                        {{ ad.spend_l7d | currency:'USD':'symbol':'1.0-0' }}
                      </span>
                      <span class="metric">
                        <mat-icon>touch_app</mat-icon>
                        {{ (ad.ctr * 100 | number:'1.1-1') }}% CTR
                      </span>
                    </div>
                  </div>
                  <div class="ace-score" [class]="getAceClass(ad.ace_score)">
                    {{ ad.ace_score | number:'1.0-0' }}
                  </div>
                </div>

                <div class="empty-state" *ngIf="getWidget(platform).length === 0">
                  <mat-icon>campaign</mat-icon>
                  <p>No data for the last 7 days</p>
                  <small>Connect a {{ platform }} account to start tracking</small>
                </div>
              </div>
            </div>
          </ng-container>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .welcome-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      margin-bottom: 28px;
      h1 { margin-bottom: 6px; }
    }

    .date-badge {
      font-size: 12px;
      color: var(--text-muted);
      background: var(--bg-card);
      border: 1px solid var(--border);
      padding: 6px 12px;
      border-radius: 20px;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }

    .stat-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--border-radius-lg);
      padding: 20px;
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      mat-icon { font-size: 24px; }
    }

    .stat-value { font-size: 22px; font-weight: 700; }
    .stat-label { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

    .widgets-section h2 { margin-bottom: 20px; }

    .widgets-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 20px;
    }

    .platform-widget { padding: 0; overflow: hidden; }

    .widget-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
    }

    .platform-label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 600;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .platform-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      &.platform-meta    { background: #1877F2; }
      &.platform-tiktok  { background: #FF0050; }
      &.platform-youtube { background: #FF0000; }
    }

    .see-all-link {
      font-size: 12px;
      color: var(--accent);
      cursor: pointer;
      text-decoration: none;
      &:hover { text-decoration: underline; }
    }

    .ads-list { padding: 8px 0; }

    .ad-row {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 20px;
      cursor: pointer;
      transition: background var(--transition);
      &:hover { background: var(--bg-hover); }
    }

    .skeleton-row { pointer-events: none; }

    .ad-thumb-container {
      position: relative;
      flex-shrink: 0;
    }

    .ad-thumb {
      width: 56px;
      height: 56px;
      object-fit: cover;
      border-radius: 8px;
      background: var(--bg-hover);
    }

    .format-badge {
      position: absolute;
      top: 2px;
      left: 2px;
      background: rgba(0,0,0,0.6);
      color: white;
      font-size: 9px;
      font-weight: 600;
      padding: 1px 5px;
      border-radius: 4px;
      text-transform: uppercase;
    }

    .ad-info {
      flex: 1;
      min-width: 0;
    }

    .ad-name {
      font-size: 13px;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-bottom: 4px;
    }

    .ad-metrics {
      display: flex;
      gap: 12px;
    }

    .metric {
      display: flex;
      align-items: center;
      gap: 3px;
      font-size: 11px;
      color: var(--text-secondary);
      mat-icon { font-size: 12px; width: 12px; height: 12px; }
    }

    .ace-score {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 700;
      flex-shrink: 0;

      &.ace-high   { background: rgba(46,204,113,0.2);  color: var(--success); border: 2px solid var(--success); }
      &.ace-medium { background: rgba(243,156,18,0.2);  color: var(--warning); border: 2px solid var(--warning); }
      &.ace-low    { background: rgba(231,76,60,0.2);   color: var(--error);   border: 2px solid var(--error);   }
    }

    .empty-state {
      text-align: center;
      padding: 32px 20px;
      color: var(--text-muted);
      mat-icon { font-size: 32px; opacity: 0.4; }
      p { font-size: 13px; margin: 8px 0 4px; }
      small { font-size: 11px; }
    }
  `],
})
export class HomeComponent implements OnInit {
  data: any = null;
  loading = true;
  platforms = ['META', 'TIKTOK', 'YOUTUBE'];
  today = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.api.get('/dashboard/homepage-widgets').subscribe({
      next: (d: any) => { this.data = d; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  get firstName(): string {
    return this.auth.currentUser?.first_name || 'there';
  }

  getWidget(platform: string): any[] {
    return this.data?.widgets?.[platform.toLowerCase()] || [];
  }

  getAceClass(score: number | null): string {
    if (!score) return 'ace-low';
    if (score >= 70) return 'ace-high';
    if (score >= 45) return 'ace-medium';
    return 'ace-low';
  }

  navigateToDashboard(platform: string): void {
    this.router.navigate(['/dashboard'], { queryParams: { platforms: platform } });
  }

  openAdDetail(ad: any): void {
    this.router.navigate(['/dashboard'], { queryParams: { assetId: ad.id } });
  }

  onImgError(event: Event): void {
    (event.target as HTMLImageElement).src = '/assets/images/placeholder.svg';
  }
}
