import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatMenuModule } from '@angular/material/menu';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';

interface OrgUser {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  is_active: boolean;
  last_login?: string;
}

interface OrgSettings {
  name: string;
  slug: string;
  currency: string;
}

const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'CHF', 'JPY', 'SEK', 'NOK', 'DKK'];
const ROLES = ['ADMIN', 'STANDARD', 'READ_ONLY'];

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule, ReactiveFormsModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule, MatMenuModule,
    MatDialogModule, MatProgressSpinnerModule, MatSnackBarModule,
  ],
  template: `
    <div class="page-container">
      <!-- Organization Settings -->
      <section class="config-section">
        <div class="section-header">
          <div>
            <h2>Organization Settings</h2>
            <p>Manage your organization name and default currency</p>
          </div>
        </div>
        <div class="section-body" *ngIf="orgForm">
          <form [formGroup]="orgForm" (ngSubmit)="saveOrg()">
            <div class="form-row">
              <mat-form-field appearance="outline">
                <mat-label>Organization Name</mat-label>
                <input matInput formControlName="name" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Default Currency</mat-label>
                <mat-select formControlName="currency">
                  <mat-option *ngFor="let c of currencies" [value]="c">{{ c }}</mat-option>
                </mat-select>
              </mat-form-field>
            </div>
            <div class="form-actions">
              <button mat-flat-button type="submit" class="save-btn" [disabled]="orgForm.invalid || savingOrg">
                <mat-spinner *ngIf="savingOrg" diameter="16"></mat-spinner>
                {{ savingOrg ? 'Saving...' : 'Save Changes' }}
              </button>
            </div>
          </form>
        </div>
      </section>

      <!-- Users -->
      <section class="config-section">
        <div class="section-header">
          <div>
            <h2>Users</h2>
            <p>{{ users.length }} member{{ users.length !== 1 ? 's' : '' }}</p>
          </div>
          <button mat-flat-button class="invite-btn" (click)="openInvite()">
            <mat-icon>person_add</mat-icon>
            Invite User
          </button>
        </div>

        <div class="users-table" *ngIf="!loadingUsers; else loadingTpl">
          <div class="table-header">
            <div class="col-user">User</div>
            <div class="col-role">Role</div>
            <div class="col-status">Status</div>
            <div class="col-last">Last Login</div>
            <div class="col-actions"></div>
          </div>

          <div *ngFor="let user of users" class="user-row">
            <div class="col-user">
              <div class="user-avatar">{{ getUserInitials(user) }}</div>
              <div class="user-info">
                <span class="user-name">{{ user.first_name }} {{ user.last_name }}</span>
                <span class="user-email">{{ user.email }}</span>
              </div>
            </div>
            <div class="col-role">
              <span class="role-badge" [class]="'role-' + user.role.toLowerCase()">{{ user.role }}</span>
            </div>
            <div class="col-status">
              <span class="status-dot" [class.active]="user.is_active"></span>
              {{ user.is_active ? 'Active' : 'Inactive' }}
            </div>
            <div class="col-last">
              {{ user.last_login ? (user.last_login | date:'mediumDate') : 'Never' }}
            </div>
            <div class="col-actions">
              <button mat-icon-button [matMenuTriggerFor]="userMenu" [matMenuTriggerData]="{user: user}">
                <mat-icon>more_vert</mat-icon>
              </button>
            </div>
          </div>

          <div *ngIf="users.length === 0" class="empty-table">
            <mat-icon>people_outline</mat-icon>
            <span>No users found</span>
          </div>
        </div>

        <ng-template #loadingTpl>
          <div class="loading-row"><mat-spinner diameter="24"></mat-spinner></div>
        </ng-template>
      </section>

      <!-- User context menu -->
      <mat-menu #userMenu="matMenu">
        <ng-template matMenuContent let-user="user">
          <button mat-menu-item (click)="changeRole(user)">
            <mat-icon>manage_accounts</mat-icon> Change Role
          </button>
          <button mat-menu-item (click)="toggleActive(user)">
            <mat-icon>{{ user.is_active ? 'block' : 'check_circle' }}</mat-icon>
            {{ user.is_active ? 'Deactivate' : 'Activate' }}
          </button>
        </ng-template>
      </mat-menu>

      <!-- Invite panel (inline) -->
      <section class="config-section" *ngIf="showInvite">
        <div class="section-header">
          <div>
            <h2>Invite New User</h2>
          </div>
          <button mat-icon-button (click)="showInvite = false"><mat-icon>close</mat-icon></button>
        </div>
        <div class="section-body">
          <form [formGroup]="inviteForm" (ngSubmit)="sendInvite()">
            <div class="form-row">
              <mat-form-field appearance="outline">
                <mat-label>First Name</mat-label>
                <input matInput formControlName="first_name" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Last Name</mat-label>
                <input matInput formControlName="last_name" />
              </mat-form-field>
            </div>
            <div class="form-row">
              <mat-form-field appearance="outline">
                <mat-label>Email</mat-label>
                <input matInput type="email" formControlName="email" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Role</mat-label>
                <mat-select formControlName="role">
                  <mat-option *ngFor="let r of roles" [value]="r">{{ r }}</mat-option>
                </mat-select>
              </mat-form-field>
            </div>
            <div class="invite-note">
              <mat-icon>info_outline</mat-icon>
              <span>User will receive an email with a temporary password to set up their account.</span>
            </div>
            <div class="form-actions">
              <button mat-stroked-button type="button" (click)="showInvite = false">Cancel</button>
              <button mat-flat-button type="submit" class="save-btn" [disabled]="inviteForm.invalid || inviting">
                <mat-spinner *ngIf="inviting" diameter="16"></mat-spinner>
                {{ inviting ? 'Sending...' : 'Send Invite' }}
              </button>
            </div>
          </form>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .page-container { padding: 28px; display: flex; flex-direction: column; gap: 24px; max-width: 900px; }

    .config-section {
      background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
    }

    .section-header {
      display: flex; align-items: flex-start; justify-content: space-between;
      padding: 20px 24px; border-bottom: 1px solid var(--border);
      h2 { font-size: 16px; font-weight: 600; margin: 0 0 4px; }
      p { font-size: 13px; color: var(--text-secondary); margin: 0; }
    }

    .section-body { padding: 24px; }

    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }

    .form-actions { display: flex; justify-content: flex-end; gap: 12px; }

    .save-btn { background: var(--accent) !important; color: white !important; display: flex; align-items: center; gap: 8px; }
    .invite-btn { background: var(--accent) !important; color: white !important; gap: 6px; }

    .users-table { overflow-x: auto; }

    .table-header, .user-row {
      display: grid; grid-template-columns: 1fr 120px 100px 140px 48px; align-items: center;
    }

    .table-header {
      padding: 10px 24px; background: var(--bg-secondary); border-bottom: 1px solid var(--border);
      font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; color: var(--text-secondary);
    }

    .user-row {
      padding: 12px 24px; border-bottom: 1px solid var(--border);
      &:last-child { border-bottom: none; }
      &:hover { background: var(--bg-secondary); }
    }

    .col-user { display: flex; align-items: center; gap: 12px; }

    .user-avatar {
      width: 36px; height: 36px; border-radius: 50%;
      background: var(--accent); color: white;
      display: flex; align-items: center; justify-content: center;
      font-size: 13px; font-weight: 700; flex-shrink: 0;
    }

    .user-name { font-size: 14px; font-weight: 500; display: block; }
    .user-email { font-size: 12px; color: var(--text-secondary); }

    .role-badge {
      padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;
      &.role-admin { background: var(--accent-light); color: var(--accent); }
      &.role-standard { background: rgba(52,168,83,0.15); color: #34A853; }
      &.role-read_only { background: var(--bg-secondary); color: var(--text-secondary); }
    }

    .status-dot {
      display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--text-muted); margin-right: 6px;
      &.active { background: #34A853; }
    }

    .col-last { font-size: 13px; color: var(--text-secondary); }

    .empty-table {
      display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 40px;
      color: var(--text-muted);
      mat-icon { font-size: 28px; opacity: 0.4; }
      span { font-size: 13px; }
    }

    .loading-row { display: flex; justify-content: center; padding: 32px; }

    .invite-note {
      display: flex; align-items: flex-start; gap: 8px; padding: 12px;
      background: var(--accent-light); border-radius: 6px; margin-bottom: 16px;
      mat-icon { font-size: 16px; color: var(--accent); margin-top: 1px; }
      span { font-size: 13px; color: var(--text-secondary); }
    }
  `],
})
export class OrganizationComponent implements OnInit {
  users: OrgUser[] = [];
  loadingUsers = true;
  savingOrg = false;
  inviting = false;
  showInvite = false;

  currencies = CURRENCIES;
  roles = ROLES;

  orgForm!: FormGroup;
  inviteForm!: FormGroup;

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private fb: FormBuilder,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.orgForm = this.fb.group({
      name: ['', Validators.required],
      currency: ['USD', Validators.required],
    });

    this.inviteForm = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      role: ['STANDARD', Validators.required],
    });

    this.loadData();
  }

  loadData(): void {
    // Load org settings
    this.api.get<OrgSettings>('/users/organization').subscribe({
      next: (org) => {
        this.orgForm.patchValue({ name: org.name, currency: org.currency });
      },
    });

    // Load users
    this.api.get<OrgUser[]>('/users').subscribe({
      next: (users) => { this.users = users; this.loadingUsers = false; },
      error: () => { this.loadingUsers = false; },
    });
  }

  saveOrg(): void {
    if (this.orgForm.invalid) return;
    this.savingOrg = true;
    this.api.patch('/users/organization', this.orgForm.value).subscribe({
      next: () => {
        this.savingOrg = false;
        this.snackBar.open('Organization settings saved', '', { duration: 3000 });
      },
      error: () => { this.savingOrg = false; },
    });
  }

  openInvite(): void {
    this.showInvite = true;
    this.inviteForm.reset({ role: 'STANDARD' });
  }

  sendInvite(): void {
    if (this.inviteForm.invalid) return;
    this.inviting = true;
    this.api.post('/users/invite', this.inviteForm.value).subscribe({
      next: () => {
        this.inviting = false;
        this.showInvite = false;
        this.snackBar.open('Invitation sent', '', { duration: 3000 });
        this.loadData();
      },
      error: () => { this.inviting = false; },
    });
  }

  changeRole(user: OrgUser): void {
    const roles = ROLES.filter(r => r !== user.role);
    // Simple prompt-based role change for MVP
    const newRole = window.prompt(`Change role for ${user.email}.\nCurrent: ${user.role}\nOptions: ${roles.join(', ')}`, roles[0]);
    if (newRole && ROLES.includes(newRole.toUpperCase())) {
      this.api.patch(`/users/${user.id}/role`, { role: newRole.toUpperCase() }).subscribe({
        next: () => {
          user.role = newRole.toUpperCase();
          this.snackBar.open('Role updated', '', { duration: 2000 });
        },
      });
    }
  }

  toggleActive(user: OrgUser): void {
    this.api.patch(`/users/${user.id}`, { is_active: !user.is_active }).subscribe({
      next: () => {
        user.is_active = !user.is_active;
        this.snackBar.open(`User ${user.is_active ? 'activated' : 'deactivated'}`, '', { duration: 2000 });
      },
    });
  }

  getUserInitials(user: OrgUser): string {
    return `${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase();
  }
}
