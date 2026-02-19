import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="auth-page">
      <div class="auth-card">
        <div class="auth-logo">
          <img src="/assets/images/logo-orange-white.png" alt="Brainsuite" class="logo-img" />
        </div>

        <p class="auth-subtitle">Platform Connector</p>

        <form [formGroup]="form" (ngSubmit)="submit()">
          <div class="input-group">
            <span class="input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
              </svg>
            </span>
            <input
              type="email"
              formControlName="email"
              placeholder="Email"
              autocomplete="off"
              spellcheck="false"
            />
          </div>

          <div class="input-group">
            <span class="input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </span>
            <input
              [type]="showPassword ? 'text' : 'password'"
              formControlName="password"
              placeholder="Password"
              autocomplete="off"
            />
            <button type="button" class="toggle-pw" (click)="showPassword = !showPassword">
              <svg *ngIf="!showPassword" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
              <svg *ngIf="showPassword" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>
              </svg>
            </button>
          </div>

          <div class="pending-msg" *ngIf="pendingMsg">{{ pendingMsg }}</div>
          <div class="error-msg" *ngIf="errorMsg">{{ errorMsg }}</div>

          <button
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
      max-width: 420px;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--border-radius-lg);
      padding: 40px;
    }

    .auth-logo { margin-bottom: 8px; }

    .logo-img { height: 36px; width: auto; }

    .auth-subtitle {
      color: var(--text-secondary);
      font-size: 13px;
      margin-bottom: 28px;
    }

    form { display: flex; flex-direction: column; gap: 16px; }

    .input-group {
      display: flex;
      align-items: center;
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: var(--border-radius);
      padding: 0 14px;
      height: 48px;
      transition: border-color 0.2s;
    }

    .input-group:focus-within {
      border-color: var(--accent);
    }

    .input-icon {
      display: flex;
      align-items: center;
      color: var(--text-muted);
      margin-right: 10px;
      flex-shrink: 0;
    }

    .input-group input {
      flex: 1;
      border: none;
      outline: none;
      background: transparent;
      color: var(--text-primary);
      font-family: inherit;
      font-size: 14px;
      height: 100%;
      padding: 0;
    }

    .input-group input::placeholder {
      color: var(--text-muted);
    }

    .input-group input:-webkit-autofill,
    .input-group input:-webkit-autofill:hover,
    .input-group input:-webkit-autofill:focus {
      -webkit-box-shadow: 0 0 0 30px var(--input-bg) inset !important;
      -webkit-text-fill-color: var(--text-primary) !important;
      font-family: inherit;
      font-size: 14px;
    }

    .toggle-pw {
      display: flex;
      align-items: center;
      justify-content: center;
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      padding: 4px;
      margin-left: 8px;
      flex-shrink: 0;
      transition: color 0.2s;
    }

    .toggle-pw:hover { color: var(--text-secondary); }

    .pending-msg {
      background: rgba(255, 170, 0, 0.1);
      color: #FFAA00;
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 13px;
      border: 1px solid rgba(255, 170, 0, 0.25);
    }

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
      background: var(--accent);
      color: white;
      font-weight: 600;
      font-size: 15px;
      font-family: inherit;
      border: none;
      border-radius: var(--border-radius);
      cursor: pointer;
      transition: background 0.2s;
    }

    .submit-btn:hover:not(:disabled) { background: var(--accent-hover); }
    .submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }

    .auth-footer {
      text-align: center;
      margin-top: 20px;
      font-size: 13px;
      color: var(--text-secondary);
    }

    .auth-footer a {
      color: var(--accent);
      text-decoration: none;
      font-weight: 500;
    }

    .auth-footer a:hover { text-decoration: underline; }
  `],
})
export class LoginComponent {
  form: FormGroup;
  loading = false;
  showPassword = false;
  errorMsg = '';
  pendingMsg = '';

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
    this.pendingMsg = '';
    const { email, password } = this.form.value;
    this.auth.login(email, password).subscribe({
      next: () => {
        this.auth.loadCurrentUser().subscribe(() => {
          this.router.navigate(['/home']);
        });
      },
      error: (e) => {
        if (e.status === 403 && e.error?.detail?.toLowerCase().includes('pending')) {
          this.pendingMsg = e.error.detail;
        } else {
          this.errorMsg = 'Invalid email or password';
        }
        this.loading = false;
      },
    });
  }
}
