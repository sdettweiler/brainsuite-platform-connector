import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

interface ConfigNav {
  path: string;
  label: string;
  icon: string;
}

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, RouterOutlet, MatIconModule],
  template: `
    <div class="config-layout">
      <!-- Config sidebar nav -->
      <aside class="config-nav">
        <div class="config-nav-title">Configuration</div>
        <nav>
          <a
            *ngFor="let item of navItems"
            [routerLink]="item.path"
            routerLinkActive="active"
            class="config-nav-item"
          >
            <mat-icon>{{ item.icon }}</mat-icon>
            <span>{{ item.label }}</span>
          </a>
        </nav>
      </aside>

      <!-- Config content -->
      <main class="config-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: [`
    .config-layout { display: flex; height: 100%; overflow: hidden; }

    .config-nav {
      width: 220px; flex-shrink: 0; border-right: 1px solid var(--border);
      padding: 24px 0; background: var(--bg-card);
    }

    .config-nav-title {
      padding: 0 16px 16px; font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 1px; color: var(--text-muted);
    }

    .config-nav-item {
      display: flex; align-items: center; gap: 10px; padding: 10px 16px;
      text-decoration: none; color: var(--text-secondary); font-size: 14px; transition: all 0.15s;
      mat-icon { font-size: 18px; }
      &:hover { background: var(--bg-secondary); color: var(--text-primary); }
      &.active { background: rgba(66,133,244,0.1); color: var(--accent); font-weight: 500; }
    }

    .config-content { flex: 1; overflow-y: auto; }
  `],
})
export class ConfigurationShellComponent {
  navItems: ConfigNav[] = [
    { path: 'organization', label: 'Organization & Users', icon: 'business' },
    { path: 'metadata', label: 'Metadata Fields', icon: 'tune' },
    { path: 'platforms', label: 'Platform Connections', icon: 'link' },
    { path: 'brainsuite-apps', label: 'Brainsuite Apps', icon: 'psychology' },
  ];
}
