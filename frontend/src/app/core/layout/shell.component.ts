import { Component, OnInit, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { CommonModule } from '@angular/common';
import { SidebarComponent } from './sidebar/sidebar.component';
import { HeaderComponent } from './header/header.component';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'bs-shell',
  standalone: true,
  imports: [CommonModule, RouterOutlet, SidebarComponent, HeaderComponent],
  template: `
    <div class="shell" [class.sidebar-collapsed]="sidebarCollapsed()">
      <bs-sidebar
        [collapsed]="sidebarCollapsed()"
        (toggleCollapse)="sidebarCollapsed.set(!sidebarCollapsed())"
      />
      <div class="shell-main">
        <bs-header />
        <main class="shell-content">
          <router-outlet />
        </main>
        <footer class="shell-footer">
          <a href="https://app.brainsuite.ai/privacy" target="_blank" rel="noopener">Privacy Policy</a>
          <span class="footer-sep">·</span>
          <a href="https://app.brainsuite.ai/imprint" target="_blank" rel="noopener">Imprint</a>
        </footer>
      </div>
    </div>
  `,
  styles: [`
    .shell {
      display: flex;
      height: 100vh;
      overflow: hidden;
    }

    .shell-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      margin-left: var(--sidebar-width);
      transition: margin-left var(--transition);
    }

    .shell.sidebar-collapsed .shell-main {
      margin-left: var(--sidebar-collapsed-width);
    }

    .shell-content {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      background: var(--bg-primary);
    }

    .shell-footer {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 10px 24px;
      font-size: 12px;
      color: var(--text-muted);
      background: var(--bg-card);
      border-top: 1px solid var(--border);
      flex-shrink: 0;
    }

    .shell-footer a {
      color: var(--text-muted);
      text-decoration: none;
      transition: color 0.2s;
    }

    .shell-footer a:hover {
      color: var(--text-secondary);
      text-decoration: underline;
    }

    .footer-sep {
      margin: 0 6px;
    }
  `],
})
export class ShellComponent implements OnInit {
  sidebarCollapsed = signal(false);

  constructor(private auth: AuthService) {}

  ngOnInit(): void {
    // Load current user if not already loaded
    if (!this.auth.currentUser) {
      this.auth.loadCurrentUser().subscribe();
    }
  }
}
