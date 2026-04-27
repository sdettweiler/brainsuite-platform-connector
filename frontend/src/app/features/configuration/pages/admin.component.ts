import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../../core/services/api.service';

interface CookieSlotHealth {
  status: 'valid' | 'expired' | 'missing';
}

interface CookieHealthResponse {
  primary: CookieSlotHealth;
  backup: CookieSlotHealth;
}

interface SuperAdminUser {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

interface OrgItem {
  id: string;
  name: string;
  slug: string;
  user_count: number;
  created_at: string;
}

@Component({
  standalone: true,
  selector: 'app-admin',
  imports: [CommonModule, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatProgressSpinnerModule, MatSnackBarModule],
  template: `
<div class="page-container">

  <!-- Section 1: YouTube Cookies -->
  <section class="config-section">
    <div class="section-header">
      <div>
        <h2>YouTube Cookies</h2>
        <p class="section-desc">Manage system-wide DV360 cookie credentials used for video asset downloads.</p>
      </div>
    </div>
    <div class="section-body">
      <div *ngIf="loadingCookies" class="skeleton-block"></div>
      <div *ngIf="cookieError && !loadingCookies" class="error-text">Could not load cookie status. Refresh to retry.</div>

      <ng-container *ngIf="cookieHealth && !loadingCookies">
        <!-- Primary Cookie Card -->
        <div class="cookie-card">
          <div class="slot-header">
            <span>Primary Cookie</span>
            <span class="badge" [ngClass]="'badge-' + cookieHealth.primary.status">{{ cookieHealth.primary.status | uppercase }}</span>
          </div>

          <!-- State D: MISSING -->
          <div *ngIf="cookieHealth.primary.status === 'missing' && !editingPrimary" class="cookie-missing">
            <span class="text-muted">No cookie saved.</span>
            <button mat-stroked-button (click)="editingPrimary = true">Add Cookie</button>
          </div>

          <!-- State A: Masked (not missing, not editing) -->
          <div *ngIf="cookieHealth.primary.status !== 'missing' && !editingPrimary" class="cookie-display">
            <span class="masked">&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;</span>
            <button mat-stroked-button (click)="editingPrimary = true">Replace</button>
          </div>

          <!-- State C: Replace mode -->
          <div *ngIf="editingPrimary" class="cookie-edit">
            <textarea [(ngModel)]="newPrimaryCookie" placeholder="Paste Netscape cookie text here" rows="6" aria-label="Primary cookie content"></textarea>
            <div class="cookie-edit-actions">
              <button mat-stroked-button (click)="discardEdit('primary')">Discard</button>
              <button mat-flat-button class="save-btn" (click)="saveCookie('primary')" [disabled]="savingPrimary">
                <mat-spinner *ngIf="savingPrimary" diameter="16"></mat-spinner>
                {{ savingPrimary ? 'Saving...' : 'Save Cookie' }}
              </button>
            </div>
          </div>
        </div>

        <!-- Backup Cookie Card -->
        <div class="cookie-card">
          <div class="slot-header">
            <span>Backup Cookie</span>
            <span class="badge" [ngClass]="'badge-' + cookieHealth.backup.status">{{ cookieHealth.backup.status | uppercase }}</span>
          </div>

          <div *ngIf="cookieHealth.backup.status === 'missing' && !editingBackup" class="cookie-missing">
            <span class="text-muted">No cookie saved.</span>
            <button mat-stroked-button (click)="editingBackup = true">Add Cookie</button>
          </div>

          <div *ngIf="cookieHealth.backup.status !== 'missing' && !editingBackup" class="cookie-display">
            <span class="masked">&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;</span>
            <button mat-stroked-button (click)="editingBackup = true">Replace</button>
          </div>

          <div *ngIf="editingBackup" class="cookie-edit">
            <textarea [(ngModel)]="newBackupCookie" placeholder="Paste Netscape cookie text here" rows="6" aria-label="Backup cookie content"></textarea>
            <div class="cookie-edit-actions">
              <button mat-stroked-button (click)="discardEdit('backup')">Discard</button>
              <button mat-flat-button class="save-btn" (click)="saveCookie('backup')" [disabled]="savingBackup">
                <mat-spinner *ngIf="savingBackup" diameter="16"></mat-spinner>
                {{ savingBackup ? 'Saving...' : 'Save Cookie' }}
              </button>
            </div>
          </div>
        </div>
      </ng-container>
    </div>
  </section>

  <!-- Section 2: SuperAdmin Management -->
  <section class="config-section">
    <div class="section-header">
      <div>
        <h2>SuperAdmin Management</h2>
        <p class="section-desc">Manage platform administrators. SuperAdmins have access to system configuration.</p>
      </div>
    </div>
    <div class="section-body">
      <div *ngIf="superAdmins.length === 0 && !loadingAdmins" class="empty-state">
        <p>No SuperAdmins found. Use the form below to promote a user.</p>
      </div>
      <table *ngIf="superAdmins.length > 0" class="admin-table">
        <thead>
          <tr><th>Email</th><th style="width: 160px">Name</th><th style="width: 120px">Joined</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let admin of superAdmins">
            <td>{{ admin.email }}</td>
            <td>{{ admin.full_name }}</td>
            <td class="text-secondary">{{ admin.created_at | date:'mediumDate' }}</td>
          </tr>
        </tbody>
      </table>

      <div class="promote-row">
        <mat-form-field appearance="outline" class="promote-input">
          <mat-label>Email address to promote</mat-label>
          <input matInput type="email" [(ngModel)]="promoteEmail" (keyup.enter)="promoteUser()">
        </mat-form-field>
        <button mat-flat-button class="save-btn" (click)="promoteUser()" [disabled]="promotingUser || !promoteEmail.trim()">
          <mat-spinner *ngIf="promotingUser" diameter="16"></mat-spinner>
          {{ promotingUser ? 'Promoting...' : 'Promote to SuperAdmin' }}
        </button>
      </div>
    </div>
  </section>

  <!-- Section 3: Organizations (read-only) -->
  <section class="config-section">
    <div class="section-header">
      <div>
        <h2>Organizations</h2>
        <p class="section-desc">Read-only list of all organizations on the platform.</p>
      </div>
    </div>
    <div class="section-body">
      <div *ngIf="organizations.length === 0 && !loadingOrgs" class="empty-state">
        <p>No organizations found.</p>
      </div>
      <table *ngIf="organizations.length > 0" class="admin-table">
        <thead>
          <tr><th>Name</th><th style="width: 160px">Slug</th><th style="width: 80px; text-align: right">Users</th><th style="width: 120px">Created</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let org of organizations">
            <td>{{ org.name }}</td>
            <td><code class="slug-code">{{ org.slug }}</code></td>
            <td style="text-align: right">{{ org.user_count }}</td>
            <td class="text-secondary">{{ org.created_at | date:'mediumDate' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

</div>
  `,
  styles: [`
    .page-container {
      padding: 28px;
      max-width: 900px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .config-section {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }

    .section-header {
      padding: 24px;
      border-bottom: 1px solid var(--border);
      h2 { margin: 0 0 4px; font-size: 16px; font-weight: 600; }
      .section-desc { margin: 0; font-size: 13px; color: var(--text-secondary); }
    }

    .section-body { padding: 24px; }

    .cookie-card {
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
      margin-bottom: 12px;
    }

    .slot-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 600;
      margin-bottom: 8px;
    }

    .badge {
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 2px 8px;
      border-radius: 3px;
    }

    .badge-valid { background: rgba(46, 204, 113, 0.15); color: #2ECC71; }
    .badge-expired { background: rgba(243, 156, 18, 0.15); color: #F39C12; }
    .badge-missing { background: var(--border); color: var(--text-secondary); }

    .cookie-display {
      display: flex;
      gap: 8px;
      align-items: center;
    }

    .cookie-missing {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .masked {
      font-family: monospace;
      color: var(--text-muted);
      letter-spacing: 1px;
    }

    .cookie-edit {
      textarea {
        width: 100%;
        padding: 8px;
        border: 1px solid var(--border);
        border-radius: 8px;
        background: var(--bg-primary);
        color: var(--text-primary);
        font-family: monospace;
        font-size: 13px;
        resize: vertical;
      }
    }

    .cookie-edit-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 8px;
    }

    .save-btn {
      background: var(--accent) !important;
      color: white !important;
      display: inline-flex !important;
      align-items: center;
      gap: 8px;
    }

    .admin-table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 16px;
      thead { background: var(--bg-hover); }
      th, td { padding: 8px; text-align: left; border-bottom: 1px solid var(--border); font-size: 14px; }
      th { font-size: 13px; font-weight: 400; color: var(--text-secondary); }
    }

    .slug-code {
      font-family: monospace;
      color: var(--text-muted);
      font-size: 13px;
    }

    .text-secondary { color: var(--text-secondary); }
    .text-muted { color: var(--text-muted); }

    .promote-row {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      .promote-input { flex: 1; }
    }

    .empty-state {
      padding: 48px 0;
      text-align: center;
      color: var(--text-muted);
      font-size: 14px;
    }

    .skeleton-block {
      height: 120px;
      background: var(--bg-secondary);
      border-radius: 6px;
      animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }

    .error-text { color: var(--error); font-size: 14px; }
  `],
})
export class AdminComponent implements OnInit {
  cookieHealth: CookieHealthResponse | null = null;
  loadingCookies = true;
  cookieError = false;
  superAdmins: SuperAdminUser[] = [];
  loadingAdmins = true;
  organizations: OrgItem[] = [];
  loadingOrgs = true;

  editingPrimary = false;
  editingBackup = false;
  newPrimaryCookie = '';
  newBackupCookie = '';
  savingPrimary = false;
  savingBackup = false;

  promoteEmail = '';
  promotingUser = false;

  constructor(
    private api: ApiService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.loadCookieHealth();
    this.loadSuperAdmins();
    this.loadOrganizations();
  }

  loadCookieHealth(): void {
    this.loadingCookies = true;
    this.cookieError = false;
    this.api.get<CookieHealthResponse>('/super-admin/youtube-cookies').subscribe({
      next: (data) => { this.cookieHealth = data; this.loadingCookies = false; },
      error: () => { this.cookieError = true; this.loadingCookies = false; },
    });
  }

  loadSuperAdmins(): void {
    this.loadingAdmins = true;
    this.api.get<SuperAdminUser[]>('/super-admin/users').subscribe({
      next: (data) => { this.superAdmins = data; this.loadingAdmins = false; },
      error: () => { this.loadingAdmins = false; },
    });
  }

  loadOrganizations(): void {
    this.loadingOrgs = true;
    this.api.get<OrgItem[]>('/super-admin/organizations').subscribe({
      next: (data) => { this.organizations = data; this.loadingOrgs = false; },
      error: () => { this.loadingOrgs = false; },
    });
  }

  saveCookie(slot: 'primary' | 'backup'): void {
    const content = slot === 'primary' ? this.newPrimaryCookie : this.newBackupCookie;
    if (!content.trim()) return;

    const payload = slot === 'primary' ? { primary: content } : { backup: content };

    if (slot === 'primary') this.savingPrimary = true;
    else this.savingBackup = true;

    this.api.put<CookieHealthResponse>('/super-admin/youtube-cookies', payload).subscribe({
      next: (updated) => {
        this.cookieHealth = updated;
        if (slot === 'primary') { this.savingPrimary = false; this.editingPrimary = false; this.newPrimaryCookie = ''; }
        else { this.savingBackup = false; this.editingBackup = false; this.newBackupCookie = ''; }
        this.snackBar.open('Cookie updated successfully.', 'Close', { duration: 3000 });
      },
      error: () => {
        if (slot === 'primary') this.savingPrimary = false;
        else this.savingBackup = false;
        this.snackBar.open('Failed to save cookie. Check your connection and try again.', 'Close');
      },
    });
  }

  discardEdit(slot: 'primary' | 'backup'): void {
    if (slot === 'primary') { this.editingPrimary = false; this.newPrimaryCookie = ''; }
    else { this.editingBackup = false; this.newBackupCookie = ''; }
  }

  promoteUser(): void {
    if (!this.promoteEmail.trim()) return;
    this.promotingUser = true;

    this.api.post<SuperAdminUser>('/super-admin/users/promote', { email: this.promoteEmail }).subscribe({
      next: () => {
        this.snackBar.open('User promoted to SuperAdmin.', 'Close', { duration: 3000 });
        this.loadSuperAdmins();
        this.promoteEmail = '';
        this.promotingUser = false;
      },
      error: (err) => {
        this.promotingUser = false;
        const detail = err?.error?.detail;
        if (detail === 'User not found') {
          this.snackBar.open('No user found with that email address.', 'Close');
        } else if (detail === 'User is already a SuperAdmin') {
          this.snackBar.open('This user is already a SuperAdmin.', 'Close');
        } else {
          this.snackBar.open('Failed to promote user. Check your connection and try again.', 'Close');
        }
      },
    });
  }
}
