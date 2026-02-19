import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatMenuModule } from '@angular/material/menu';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { MatBadgeModule } from '@angular/material/badge';
import { AuthService, CurrentUser } from '../../services/auth.service';
import { ThemeService } from '../../services/theme.service';
import { ApiService } from '../../services/api.service';

interface NotificationItem {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

@Component({
  selector: 'bs-header',
  standalone: true,
  imports: [
    CommonModule, RouterLink, MatMenuModule, MatIconModule,
    MatButtonModule, MatDialogModule, MatTooltipModule, MatDividerModule,
    MatBadgeModule,
  ],
  template: `
    <header class="header">
      <div class="header-left"></div>

      <div class="header-right">
        <button
          mat-icon-button
          [matMenuTriggerFor]="notifMenu"
          class="icon-btn notif-btn"
          [matBadge]="unreadCount > 0 ? unreadCount : null"
          matBadgeColor="warn"
          matBadgeSize="small"
          [matBadgeHidden]="unreadCount === 0"
        >
          <mat-icon>{{ unreadCount > 0 ? 'notifications' : 'notifications_none' }}</mat-icon>
        </button>

        <mat-menu #notifMenu="matMenu" xPosition="before" class="notif-menu">
          <div class="notif-header" (click)="$event.stopPropagation()">
            <span>Notifications</span>
            <button *ngIf="unreadCount > 0" mat-button class="mark-all-btn" (click)="markAllRead()">Mark all read</button>
          </div>
          <mat-divider />
          <div *ngIf="notifications.length === 0" class="notif-empty" (click)="$event.stopPropagation()">
            <mat-icon>notifications_none</mat-icon>
            <span>No notifications</span>
          </div>
          <button
            *ngFor="let n of notifications"
            mat-menu-item
            class="notif-item"
            [class.unread]="!n.is_read"
            (click)="markRead(n)"
          >
            <div class="notif-icon-wrap">
              <mat-icon [class]="getNotifIconClass(n)">{{ getNotifIcon(n) }}</mat-icon>
            </div>
            <div class="notif-content">
              <span class="notif-title">{{ n.title }}</span>
              <span class="notif-msg">{{ n.message }}</span>
              <span class="notif-time">{{ n.created_at | date:'short' }}</span>
            </div>
            <div class="notif-unread-dot" *ngIf="!n.is_read"></div>
          </button>
        </mat-menu>

        <button
          mat-button
          [matMenuTriggerFor]="userMenu"
          class="avatar-btn"
        >
          <div class="avatar">{{ initials }}</div>
          <span class="avatar-name">{{ user?.full_name || user?.email }}</span>
          <mat-icon class="chevron">expand_more</mat-icon>
        </button>

        <mat-menu #userMenu="matMenu" xPosition="before">
          <div class="menu-header" (click)="$event.stopPropagation()">
            <div class="avatar avatar-lg">{{ initials }}</div>
            <div>
              <div class="menu-name">{{ user?.full_name }}</div>
              <div class="menu-email">{{ user?.email }}</div>
            </div>
          </div>

          <mat-divider />

          <button mat-menu-item (click)="toggleTheme()">
            <mat-icon>{{ isDark ? 'light_mode' : 'dark_mode' }}</mat-icon>
            {{ isDark ? 'Light Mode' : 'Dark Mode' }}
          </button>

          <button mat-menu-item (click)="openEditProfile()">
            <mat-icon>person</mat-icon>
            Edit Profile
          </button>

          <mat-divider />

          <button mat-menu-item (click)="logout()" class="logout-item">
            <mat-icon>logout</mat-icon>
            Sign Out
          </button>
        </mat-menu>
      </div>
    </header>
  `,
  styles: [`
    .header {
      height: var(--header-height);
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      flex-shrink: 0;
      z-index: 50;
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .icon-btn {
      color: var(--text-secondary) !important;
      &:hover { color: var(--text-primary) !important; }
    }

    .notif-btn {
      position: relative;
    }

    :host ::ng-deep .notif-btn .mat-badge-content {
      background: var(--accent) !important;
      color: white !important;
      font-size: 10px;
      font-weight: 600;
      right: 4px !important;
      top: 4px !important;
    }

    .org-name {
      font-size: 13px;
      color: var(--text-secondary);
      font-weight: 500;
    }

    .avatar-btn {
      display: inline-flex !important;
      align-items: center !important;
      flex-direction: row !important;
      flex-wrap: nowrap !important;
      gap: 8px;
      padding: 4px 8px !important;
      border-radius: var(--border-radius) !important;
      white-space: nowrap !important;
      max-width: none !important;
      min-width: auto !important;
      width: auto !important;
    }

    :host ::ng-deep .avatar-btn .mdc-button__label {
      display: inline-flex !important;
      align-items: center !important;
      gap: 8px;
      white-space: nowrap !important;
      overflow: visible !important;
    }

    .avatar {
      width: 32px;
      height: 32px;
      min-width: 32px;
      border-radius: 50%;
      background: var(--accent);
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 12px;
      line-height: 1;
      letter-spacing: 0.5px;
      flex-shrink: 0;

      &.avatar-lg {
        width: 40px;
        height: 40px;
        min-width: 40px;
        font-size: 15px;
      }
    }

    .avatar-name {
      font-size: 13px;
      font-weight: 500;
      color: var(--text-primary);
      white-space: nowrap;
      flex-shrink: 0;
    }

    .chevron { font-size: 18px !important; color: var(--text-muted); }

    .menu-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
    }

    .menu-name {
      font-weight: 600;
      font-size: 14px;
      color: var(--text-primary);
    }

    .menu-email {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .logout-item { color: var(--error) !important; }

    .notif-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px 8px;
      span { font-weight: 600; font-size: 14px; }
    }

    .mark-all-btn {
      font-size: 12px !important;
      color: var(--accent) !important;
      min-width: auto !important;
      padding: 0 8px !important;
      height: 28px !important;
      line-height: 28px !important;
    }

    .notif-empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 24px 16px;
      color: var(--text-muted);
      mat-icon { font-size: 24px; opacity: 0.4; }
      span { font-size: 13px; }
    }

    :host ::ng-deep .notif-item {
      display: flex !important;
      align-items: flex-start !important;
      gap: 10px;
      padding: 10px 16px !important;
      height: auto !important;
      min-height: 56px;
      white-space: normal !important;
    }

    :host ::ng-deep .notif-item.unread {
      background: rgba(255, 119, 0, 0.04);
    }

    .notif-icon-wrap {
      flex-shrink: 0;
      margin-top: 2px;
    }

    .notif-icon-wrap mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .notif-icon-wrap .icon-join { color: var(--accent); }
    .notif-icon-wrap .icon-approved { color: #34A853; }
    .notif-icon-wrap .icon-rejected { color: var(--error); }

    .notif-content {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
      flex: 1;
    }

    .notif-title { font-size: 13px; font-weight: 600; }
    .notif-msg { font-size: 12px; color: var(--text-secondary); line-height: 1.4; }
    .notif-time { font-size: 11px; color: var(--text-muted); }

    .notif-unread-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
      flex-shrink: 0;
      margin-top: 6px;
    }
  `],
})
export class HeaderComponent implements OnInit, OnDestroy {
  user: CurrentUser | null = null;
  isDark = true;
  notifications: NotificationItem[] = [];
  unreadCount = 0;
  private pollInterval: any;

  constructor(
    private auth: AuthService,
    private theme: ThemeService,
    private dialog: MatDialog,
    private api: ApiService,
  ) {}

  ngOnInit(): void {
    this.auth.currentUser$.subscribe(u => {
      this.user = u;
      if (u) {
        this.loadNotifications();
        this.pollInterval = setInterval(() => this.loadUnreadCount(), 30000);
      }
    });
    this.theme.currentTheme$.subscribe(t => this.isDark = t === 'dark-theme');
  }

  ngOnDestroy(): void {
    if (this.pollInterval) clearInterval(this.pollInterval);
  }

  loadNotifications(): void {
    this.api.get<NotificationItem[]>('/users/notifications').subscribe({
      next: (notifs) => {
        this.notifications = notifs;
        this.unreadCount = notifs.filter(n => !n.is_read).length;
      },
    });
  }

  loadUnreadCount(): void {
    this.api.get<{count: number}>('/users/notifications/unread-count').subscribe({
      next: (res) => { this.unreadCount = res.count; },
    });
  }

  markRead(n: NotificationItem): void {
    if (!n.is_read) {
      this.api.post(`/users/notifications/${n.id}/read`, {}).subscribe({
        next: () => {
          n.is_read = true;
          this.unreadCount = Math.max(0, this.unreadCount - 1);
        },
      });
    }
  }

  markAllRead(): void {
    this.api.post('/users/notifications/read-all', {}).subscribe({
      next: () => {
        this.notifications.forEach(n => n.is_read = true);
        this.unreadCount = 0;
      },
    });
  }

  getNotifIcon(n: NotificationItem): string {
    switch (n.type) {
      case 'JOIN_REQUEST': return 'person_add';
      case 'JOIN_APPROVED': return 'check_circle';
      case 'JOIN_REJECTED': return 'cancel';
      default: return 'notifications';
    }
  }

  getNotifIconClass(n: NotificationItem): string {
    switch (n.type) {
      case 'JOIN_REQUEST': return 'icon-join';
      case 'JOIN_APPROVED': return 'icon-approved';
      case 'JOIN_REJECTED': return 'icon-rejected';
      default: return '';
    }
  }

  get initials(): string {
    if (!this.user) return '?';
    const fn = this.user.first_name?.[0] || '';
    const ln = this.user.last_name?.[0] || '';
    return (fn + ln).toUpperCase() || this.user.email[0].toUpperCase();
  }

  get orgName(): string {
    return 'Brainsuite Platform';
  }

  toggleTheme(): void {
    this.theme.toggle();
  }

  async openEditProfile(): Promise<void> {
    const { EditProfileDialogComponent } = await import('../../dialogs/edit-profile-dialog.component');
    this.dialog.open(EditProfileDialogComponent, {
      width: '480px',
      data: this.user,
    });
  }

  logout(): void {
    this.auth.logout();
  }
}
