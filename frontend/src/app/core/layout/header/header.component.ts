import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatMenuModule } from '@angular/material/menu';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { AuthService, CurrentUser } from '../../services/auth.service';
import { ThemeService } from '../../services/theme.service';

@Component({
  selector: 'bs-header',
  standalone: true,
  imports: [
    CommonModule, RouterLink, MatMenuModule, MatIconModule,
    MatButtonModule, MatDialogModule, MatTooltipModule, MatDividerModule,
  ],
  template: `
    <header class="header">
      <!-- Left: breadcrumb / page title placeholder -->
      <div class="header-left">
        <span class="org-name">{{ orgName }}</span>
      </div>

      <!-- Right: actions -->
      <div class="header-right">
        <!-- Notifications (placeholder) -->
        <button mat-icon-button matTooltip="Notifications" class="icon-btn">
          <mat-icon>notifications_none</mat-icon>
        </button>

        <!-- User avatar -->
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

    .org-name {
      font-size: 13px;
      color: var(--text-secondary);
      font-weight: 500;
    }

    .avatar-btn {
      display: flex !important;
      align-items: center;
      gap: 8px;
      padding: 4px 8px !important;
      border-radius: var(--border-radius) !important;
    }

    .avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: var(--accent);
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 13px;

      &.avatar-lg {
        width: 40px;
        height: 40px;
        font-size: 16px;
      }
    }

    .avatar-name {
      font-size: 13px;
      font-weight: 500;
      color: var(--text-primary);
      max-width: 140px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
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
  `],
})
export class HeaderComponent implements OnInit {
  user: CurrentUser | null = null;
  isDark = true;

  constructor(
    private auth: AuthService,
    private theme: ThemeService,
    private dialog: MatDialog,
  ) {}

  ngOnInit(): void {
    this.auth.currentUser$.subscribe(u => this.user = u);
    this.theme.currentTheme$.subscribe(t => this.isDark = t === 'dark-theme');
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
