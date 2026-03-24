import { Component, Input, Output, EventEmitter, OnInit, OnDestroy } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subscription } from 'rxjs';
import { ThemeService } from '../../services/theme.service';

interface NavItem {
  label: string;
  icon: string;
  route: string;
  exact?: boolean;
  separator?: boolean;
}

@Component({
  selector: 'bs-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, MatTooltipModule],
  template: `
    <aside class="sidebar" [class.collapsed]="collapsed">
      <div class="sidebar-logo">
        <img
          *ngIf="!collapsed"
          [src]="isDark ? '/assets/images/logo-orange-white.png' : '/assets/images/logo-orange.png'"
          alt="Brainsuite"
          class="logo-full"
        />
        <img
          *ngIf="collapsed"
          src="/assets/images/signet-orange.png"
          alt="Brainsuite"
          class="logo-signet"
        />
      </div>

      <button class="collapse-btn" (click)="toggleCollapse.emit()" [matTooltip]="collapsed ? 'Expand' : 'Collapse'" matTooltipPosition="right">
        <i class="bi" [ngClass]="collapsed ? 'bi-chevron-right' : 'bi-chevron-left'"></i>
      </button>

      <nav class="sidebar-nav">
        <ng-container *ngFor="let item of navItems">
          <div class="nav-separator" *ngIf="item.separator"></div>
          <a
            class="nav-item"
            [routerLink]="item.route"
            routerLinkActive="active"
            [routerLinkActiveOptions]="{ exact: !!item.exact }"
            [matTooltip]="collapsed ? item.label : ''"
            matTooltipPosition="right"
          >
            <i class="bi nav-icon" [ngClass]="'bi-' + item.icon"></i>
            <span class="nav-label" *ngIf="!collapsed">{{ item.label }}</span>
          </a>
        </ng-container>
      </nav>
    </aside>
  `,
  styles: [`
    .sidebar {
      position: fixed;
      top: 0;
      left: 0;
      height: 100vh;
      width: var(--sidebar-width);
      background: var(--bg-secondary);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      transition: width var(--transition);
      z-index: 100;
      overflow: visible;
    }

    .sidebar.collapsed {
      width: var(--sidebar-collapsed-width);
    }

    .sidebar-logo {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 18px 16px;
      border-bottom: 1px solid var(--border);
      min-height: var(--header-height);
      overflow: hidden;
    }

    .logo-full {
      height: 28px;
      width: auto;
      object-fit: contain;
    }

    .logo-signet {
      width: 32px;
      height: 32px;
      object-fit: contain;
      border-radius: 8px;
    }

    .collapse-btn {
      position: absolute;
      top: 70px;
      right: -12px;
      width: 24px;
      height: 24px;
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      z-index: 101;
      color: var(--text-secondary);
      padding: 0;
      transition: all var(--transition);

      i {
        font-size: 14px;
        line-height: 1;
      }

      &:hover { background: var(--accent); border-color: var(--accent); color: white; }
    }

    .sidebar-nav {
      flex: 1;
      padding: 12px 8px;
      display: flex;
      flex-direction: column;
      gap: 2px;
      overflow-y: auto;
      overflow-x: hidden;
    }

    .nav-separator {
      height: 1px;
      background: var(--border);
      margin: 12px 8px;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: var(--border-radius);
      color: var(--text-secondary);
      text-decoration: none;
      font-weight: 500;
      transition: all var(--transition);
      white-space: nowrap;
      overflow: hidden;

      &:hover {
        background: var(--bg-hover);
        color: var(--text-primary);
      }

      &.active {
        background: var(--accent-light);
        color: var(--accent);
      }
    }

    .nav-icon { font-size: 20px; width: 20px; height: 20px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
    .nav-label { font-size: 14px; }

    .sidebar.collapsed .nav-label { display: none; }
  `],
})
export class SidebarComponent implements OnInit, OnDestroy {
  @Input() collapsed = false;
  @Output() toggleCollapse = new EventEmitter<void>();

  isDark = true;
  private themeSub!: Subscription;

  constructor(private themeService: ThemeService) {}

  ngOnInit(): void {
    this.themeSub = this.themeService.currentTheme$.subscribe(
      t => this.isDark = t === 'dark-theme'
    );
  }

  ngOnDestroy(): void { this.themeSub?.unsubscribe(); }

  navItems: NavItem[] = [
    { label: 'Home',        icon: 'house',              route: '/home' },
    { label: 'Dashboard',   icon: 'bar-chart',          route: '/dashboard' },
    { label: 'Comparison',  icon: 'arrow-left-right',   route: '/comparison' },
    { label: 'Configuration', icon: 'gear',             route: '/configuration', separator: true },
  ];
}
