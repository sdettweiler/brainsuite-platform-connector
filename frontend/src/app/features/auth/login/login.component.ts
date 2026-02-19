import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule, RouterLink,
    MatFormFieldModule, MatInputModule, MatButtonModule, MatIconModule,
  ],
  template: `
    <div class="auth-page">
      <div class="auth-card">
        <!-- Logo -->
        <div class="auth-logo">
          <div class="logo-mark"><span>B</span></div>
          <h1>Brainsuite</h1>
        </div>

        <p class="auth-subtitle">Platform Connector</p>

        <form [formGroup]="form" (ngSubmit)="submit()">
          <mat-form-field appearance="outline" class="w-full">
            <mat-label>Email</mat-label>
            <input matInput type="email" formControlName="email" autocomplete="email" />
            <mat-icon matPrefix>mail_outline</mat-icon>
          </mat-form-field>

          <mat-form-field appearance="outline" class="w-full">
            <mat-label>Password</mat-label>
            <input matInput [type]="showPassword ? 'text' : 'password'" formControlName="password" autocomplete="current-password" />
            <mat-icon matPrefix>lock_outline</mat-icon>
            <button type="button" mat-icon-button matSuffix (click)="showPassword = !showPassword">
              <mat-icon>{{ showPassword ? 'visibility_off' : 'visibility' }}</mat-icon>
            </button>
          </mat-form-field>

          <div class="error-msg" *ngIf="errorMsg">{{ errorMsg }}</div>

          <button
            mat-flat-button
            type="submit"
            class="submit-btn"
            [disabled]="form.invalid || loading"
          >
            {{ loading ? 'Signing in...' : 'Sign In' }}
          </button>
        </form>

        <p class="auth-footer">
          Don't have an account? <a routerLink="/auth/register">Create one</a>
        </p>
      </div>
    </div>
  `,
  styles: [`
    .auth-page {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-primary);
      padding: 24px;
    }

    .auth-card {
      width: 100%;
      max-width: 400px;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--border-radius-lg);
      padding: 40px;
    }

    .auth-logo {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
      h1 { font-size: 22px; font-weight: 700; }
    }

    .logo-mark {
      width: 40px;
      height: 40px;
      background: var(--accent);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      span { color: white; font-weight: 800; font-size: 20px; }
    }

    .auth-subtitle {
      color: var(--text-secondary);
      font-size: 13px;
      margin-bottom: 28px;
    }

    form { display: flex; flex-direction: column; gap: 16px; }

    .w-full { width: 100%; }

    .error-msg {
      background: rgba(231,76,60,0.1);
      color: var(--error);
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 13px;
    }

    .submit-btn {
      width: 100%;
      height: 44px;
      background: var(--accent) !important;
      color: white !important;
      font-weight: 600;
    }

    .auth-footer {
      text-align: center;
      margin-top: 20px;
      font-size: 13px;
      color: var(--text-secondary);
      a { color: var(--accent); text-decoration: none; font-weight: 500; }
    }
  `],
})
export class LoginComponent {
  form: FormGroup;
  loading = false;
  showPassword = false;
  errorMsg = '';

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
  ) {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required],
    });
  }

  submit(): void {
    if (this.form.invalid) return;
    this.loading = true;
    this.errorMsg = '';
    const { email, password } = this.form.value;
    this.auth.login(email, password).subscribe({
      next: () => {
        this.auth.loadCurrentUser().subscribe(() => {
          this.router.navigate(['/home']);
        });
      },
      error: () => {
        this.errorMsg = 'Invalid email or password';
        this.loading = false;
      },
    });
  }
}
