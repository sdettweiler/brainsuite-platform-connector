import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { ApiService } from '../../../core/services/api.service';

@Component({
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="auth-page">
      <div class="auth-card">
        <div class="auth-logo">
          <img src="/assets/images/logo-orange-white.png" alt="Brainsuite" class="logo-img" />
        </div>
        <p class="auth-subtitle">Create your account</p>

        <div class="steps-indicator">
          <div class="step" [class.active]="step === 1" [class.done]="step > 1">
            <div class="step-dot">{{ step > 1 ? '&#10003;' : '1' }}</div>
            <span>Your Details</span>
          </div>
          <div class="step-line" [class.active]="step > 1"></div>
          <div class="step" [class.active]="step === 2">
            <div class="step-dot">2</div>
            <span>Organization</span>
          </div>
        </div>

        <!-- Step 1: Personal Info -->
        <form *ngIf="step === 1" [formGroup]="personalForm" (ngSubmit)="nextStep()">
          <div class="form-row">
            <div class="input-group">
              <span class="input-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                </svg>
              </span>
              <input type="text" formControlName="first_name" placeholder="First Name" autocomplete="off" />
            </div>
            <div class="input-group">
              <span class="input-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                </svg>
              </span>
              <input type="text" formControlName="last_name" placeholder="Last Name" autocomplete="off" />
            </div>
          </div>

          <div class="input-group">
            <span class="input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
              </svg>
            </span>
            <input type="email" formControlName="email" placeholder="Email" autocomplete="off" spellcheck="false" />
          </div>

          <div class="input-group">
            <span class="input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </span>
            <input type="password" formControlName="password" placeholder="Password (min. 8 characters)" autocomplete="off" />
          </div>

          <div class="error-msg" *ngIf="errorMsg">{{ errorMsg }}</div>

          <button type="submit" class="submit-btn" [disabled]="personalForm.invalid">
            Continue
          </button>
        </form>

        <!-- Step 2: Organization -->
        <form *ngIf="step === 2" [formGroup]="orgForm" (ngSubmit)="submit()">
          <div class="org-choice">
            <label class="choice-card" [class.selected]="orgAction === 'create'" (click)="setOrgAction('create')">
              <div class="choice-radio">
                <div class="radio-dot" *ngIf="orgAction === 'create'"></div>
              </div>
              <div class="choice-content">
                <strong>Create New Organization</strong>
                <span>Set up a new workspace for your team</span>
              </div>
            </label>
            <label class="choice-card" [class.selected]="orgAction === 'join'" (click)="setOrgAction('join')">
              <div class="choice-radio">
                <div class="radio-dot" *ngIf="orgAction === 'join'"></div>
              </div>
              <div class="choice-content">
                <strong>Join Existing Organization</strong>
                <span>Request access to your team's workspace</span>
              </div>
            </label>
          </div>

          <!-- Create Org Fields -->
          <div *ngIf="orgAction === 'create'" class="org-fields">
            <div class="input-group">
              <span class="input-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
                </svg>
              </span>
              <input type="text" formControlName="org_name" placeholder="Organization Name" autocomplete="off" />
            </div>
            <div class="input-group select-group">
              <span class="input-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                </svg>
              </span>
              <select formControlName="org_currency">
                <option *ngFor="let c of currencies" [value]="c">{{ c }}</option>
              </select>
            </div>
          </div>

          <!-- Join Org Fields -->
          <div *ngIf="orgAction === 'join'" class="org-fields">
            <div class="input-group" [class.error]="slugError">
              <span class="input-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
              </span>
              <input type="text" formControlName="org_slug" placeholder="Organization Slug (e.g. my-company)" autocomplete="off" />
            </div>
            <div class="slug-hint" *ngIf="!slugError && !slugValid">
              Enter the slug provided by your organization admin
            </div>
            <div class="slug-found" *ngIf="slugValid">
              Organization found — your request will be sent to the admin for approval
            </div>
            <div class="slug-error" *ngIf="slugError">
              {{ slugError }}
            </div>
          </div>

          <div class="error-msg" *ngIf="errorMsg">{{ errorMsg }}</div>

          <div class="form-buttons">
            <button type="button" class="back-btn" (click)="step = 1">Back</button>
            <button type="submit" class="submit-btn" [disabled]="!isStep2Valid() || loading">
              {{ loading ? 'Creating...' : (orgAction === 'join' ? 'Request to Join' : 'Create Account') }}
            </button>
          </div>
        </form>

        <!-- Success message for join requests -->
        <div *ngIf="step === 3" class="success-state">
          <div class="success-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>
            </svg>
          </div>
          <h3>Request Sent</h3>
          <p>Your request to join the organization has been sent. You'll be able to log in once an admin approves your request.</p>
          <a routerLink="/auth/login" class="submit-btn" style="display:block;text-align:center;text-decoration:none;line-height:44px;">Go to Login</a>
        </div>

        <p class="auth-footer" *ngIf="step !== 3">
          Already have an account? <a routerLink="/auth/login">Sign in</a>
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
      max-width: 460px;
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
      margin-bottom: 20px;
    }

    .steps-indicator {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0;
      margin-bottom: 28px;
    }

    .step {
      display: flex;
      align-items: center;
      gap: 6px;
      opacity: 0.4;
      transition: opacity 0.2s;
    }

    .step.active, .step.done { opacity: 1; }

    .step-dot {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: var(--bg-secondary);
      border: 2px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 600;
      color: var(--text-secondary);
      flex-shrink: 0;
    }

    .step.active .step-dot {
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }

    .step.done .step-dot {
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }

    .step span {
      font-size: 12px;
      font-weight: 500;
      color: var(--text-secondary);
    }

    .step.active span { color: var(--text-primary); }

    .step-line {
      width: 40px;
      height: 2px;
      background: var(--border);
      margin: 0 8px;
      transition: background 0.2s;
    }

    .step-line.active { background: var(--accent); }

    form { display: flex; flex-direction: column; gap: 12px; }
    .form-row { display: flex; gap: 12px; }
    .form-row .input-group { flex: 1; min-width: 0; }

    .input-group {
      display: flex;
      align-items: center;
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: var(--border-radius);
      padding: 0 14px;
      height: 48px;
      transition: border-color 0.2s;
      box-sizing: border-box;
      overflow: hidden;
    }

    .input-group:focus-within { border-color: var(--accent); }
    .input-group.error { border-color: var(--error); }

    .input-icon {
      display: flex;
      align-items: center;
      color: var(--text-muted);
      margin-right: 10px;
      flex-shrink: 0;
    }

    .input-group input, .input-group select {
      flex: 1;
      border: none;
      outline: none;
      background: transparent;
      color: var(--text-primary);
      font-family: inherit;
      font-size: 14px;
      height: 100%;
      padding: 0;
      min-width: 0;
    }

    .input-group select {
      cursor: pointer;
      -webkit-appearance: none;
      -moz-appearance: none;
      appearance: none;
    }

    .input-group select option {
      background: var(--bg-card);
      color: var(--text-primary);
    }

    .input-group input::placeholder { color: var(--text-muted); }

    .input-group input:-webkit-autofill,
    .input-group input:-webkit-autofill:hover,
    .input-group input:-webkit-autofill:focus {
      -webkit-box-shadow: 0 0 0 30px var(--input-bg) inset !important;
      -webkit-text-fill-color: var(--text-primary) !important;
      font-family: inherit;
      font-size: 14px;
    }

    .org-choice {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-bottom: 4px;
    }

    .choice-card {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 14px 16px;
      border: 1px solid var(--border);
      border-radius: var(--border-radius);
      cursor: pointer;
      transition: all 0.2s;
      background: var(--input-bg);
    }

    .choice-card:hover { border-color: var(--accent); }

    .choice-card.selected {
      border-color: var(--accent);
      background: rgba(255, 119, 0, 0.05);
    }

    .choice-radio {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      border: 2px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .choice-card.selected .choice-radio { border-color: var(--accent); }

    .radio-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--accent);
    }

    .choice-content {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .choice-content strong {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .choice-content span {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .org-fields { margin-top: 4px; display: flex; flex-direction: column; gap: 12px; }

    .slug-hint, .slug-found, .slug-error {
      font-size: 12px;
      padding: 0 4px;
    }

    .slug-hint { color: var(--text-muted); }
    .slug-found { color: #34A853; }
    .slug-error { color: var(--error); }

    .error-msg {
      background: rgba(231,76,60,0.1);
      color: var(--error);
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 13px;
    }

    .form-buttons {
      display: flex;
      gap: 12px;
    }

    .back-btn {
      flex: 0 0 auto;
      height: 44px;
      padding: 0 20px;
      background: var(--bg-secondary);
      color: var(--text-primary);
      font-weight: 500;
      font-size: 14px;
      font-family: inherit;
      border: 1px solid var(--border);
      border-radius: var(--border-radius);
      cursor: pointer;
      transition: all 0.2s;
    }

    .back-btn:hover { background: var(--bg-primary); }

    .submit-btn {
      flex: 1;
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

    .success-state {
      text-align: center;
      padding: 20px 0;
    }

    .success-icon { margin-bottom: 16px; }

    .success-state h3 {
      font-size: 18px;
      font-weight: 600;
      margin: 0 0 8px;
      color: var(--text-primary);
    }

    .success-state p {
      font-size: 14px;
      color: var(--text-secondary);
      margin: 0 0 24px;
      line-height: 1.5;
    }

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
export class RegisterComponent {
  personalForm: FormGroup;
  orgForm: FormGroup;
  step = 1;
  orgAction: 'create' | 'join' = 'create';
  loading = false;
  errorMsg = '';
  slugError = '';
  slugValid = false;
  currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'CHF', 'JPY', 'SEK', 'NOK', 'DKK'];

  private slugCheckTimeout: any;

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private api: ApiService,
    private router: Router,
  ) {
    this.personalForm = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8)]],
    });

    this.orgForm = this.fb.group({
      org_name: [''],
      org_currency: ['USD'],
      org_slug: [''],
    });

    this.orgForm.get('org_slug')?.valueChanges.subscribe(val => {
      this.slugError = '';
      this.slugValid = false;
      clearTimeout(this.slugCheckTimeout);
      if (val && val.length >= 2) {
        this.slugCheckTimeout = setTimeout(() => this.checkSlug(val), 500);
      }
    });
  }

  setOrgAction(action: 'create' | 'join'): void {
    this.orgAction = action;
    this.errorMsg = '';
    this.slugError = '';
    this.slugValid = false;
  }

  nextStep(): void {
    if (this.personalForm.invalid) return;
    this.errorMsg = '';
    this.step = 2;
  }

  checkSlug(slug: string): void {
    this.api.get<{available: boolean, slug: string}>(`/auth/check-slug/${slug}`).subscribe({
      next: (res) => {
        if (res.available) {
          this.slugError = 'No organization found with this slug';
          this.slugValid = false;
        } else {
          this.slugValid = true;
          this.slugError = '';
        }
      },
      error: () => {
        this.slugError = 'Could not verify slug';
      },
    });
  }

  isStep2Valid(): boolean {
    if (this.orgAction === 'create') {
      return !!this.orgForm.get('org_name')?.value?.trim();
    }
    return this.slugValid;
  }

  submit(): void {
    if (!this.isStep2Valid()) return;
    this.loading = true;
    this.errorMsg = '';

    const payload: any = {
      ...this.personalForm.value,
      org_action: this.orgAction,
    };

    if (this.orgAction === 'create') {
      payload.org_name = this.orgForm.get('org_name')?.value;
      payload.org_currency = this.orgForm.get('org_currency')?.value;
    } else {
      payload.org_slug = this.orgForm.get('org_slug')?.value;
    }

    this.auth.register(payload).subscribe({
      next: () => {
        if (this.orgAction === 'join') {
          this.step = 3;
          this.loading = false;
        } else {
          this.router.navigate(['/auth/login']);
        }
      },
      error: (e) => {
        this.errorMsg = e.error?.detail || 'Registration failed';
        this.loading = false;
      },
    });
  }
}
