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
        <div class="auth-logo">
          <img src="/assets/images/logo-orange-white.png" alt="Brainsuite" class="logo-img" />
        </div>
        <p class="auth-subtitle">Create your account</p>

        <form [formGroup]="form" (ngSubmit)="submit()">
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

          <mat-form-field appearance="outline" class="w-full">
            <mat-label>Email</mat-label>
            <input matInput type="email" formControlName="email" />
          </mat-form-field>

          <mat-form-field appearance="outline" class="w-full">
            <mat-label>Password</mat-label>
            <input matInput type="password" formControlName="password" />
          </mat-form-field>

          <div class="error-msg" *ngIf="errorMsg">{{ errorMsg }}</div>

          <button mat-flat-button type="submit" class="submit-btn" [disabled]="form.invalid || loading">
            {{ loading ? 'Creating account...' : 'Create Account' }}
          </button>
        </form>

        <p class="auth-footer">
          Already have an account? <a routerLink="/auth/login">Sign in</a>
        </p>
      </div>
    </div>
  `,
  styles: [`
    .auth-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg-primary); padding: 24px; }
    .auth-card { width: 100%; max-width: 420px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--border-radius-lg); padding: 40px; }
    .auth-logo { margin-bottom: 8px; }
    .logo-img { height: 36px; width: auto; }
    .auth-subtitle { color: var(--text-secondary); font-size: 13px; margin-bottom: 28px; }
    form { display: flex; flex-direction: column; gap: 12px; }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .w-full { width: 100%; }
    .error-msg { background: rgba(231,76,60,0.1); color: var(--error); padding: 10px 14px; border-radius: 6px; font-size: 13px; }
    .submit-btn { width: 100%; height: 44px; background: var(--accent) !important; color: white !important; font-weight: 600; font-size: 15px; border-radius: var(--border-radius) !important; }
    .auth-footer { text-align: center; margin-top: 20px; font-size: 13px; color: var(--text-secondary); a { color: var(--accent); text-decoration: none; font-weight: 500; } a:hover { text-decoration: underline; } }
  `],
})
export class RegisterComponent {
  form: FormGroup;
  loading = false;
  errorMsg = '';

  constructor(private fb: FormBuilder, private auth: AuthService, private router: Router) {
    this.form = this.fb.group({
      first_name: [''],
      last_name: [''],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8)]],
    });
  }

  submit(): void {
    if (this.form.invalid) return;
    this.loading = true;
    this.auth.register(this.form.value).subscribe({
      next: () => this.router.navigate(['/auth/login']),
      error: (e) => {
        this.errorMsg = e.error?.detail || 'Registration failed';
        this.loading = false;
      },
    });
  }
}
