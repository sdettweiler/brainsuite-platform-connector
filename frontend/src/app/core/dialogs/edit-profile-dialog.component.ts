import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { AuthService, CurrentUser } from '../services/auth.service';
import { ApiService } from '../services/api.service';

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'de', label: 'Deutsch' },
  { code: 'fr', label: 'Français' },
  { code: 'es', label: 'Español' },
];

@Component({
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule,
    MatDialogModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule,
  ],
  template: `
    <div class="dialog-container">
      <h2 mat-dialog-title>Edit Profile</h2>

      <mat-dialog-content>
        <form [formGroup]="form" class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>First Name</mat-label>
            <input matInput formControlName="first_name" />
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Last Name</mat-label>
            <input matInput formControlName="last_name" />
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Email</mat-label>
            <input matInput formControlName="email" type="email" />
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Business Unit</mat-label>
            <input matInput formControlName="business_unit" />
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Language</mat-label>
            <mat-select formControlName="language">
              <mat-option *ngFor="let l of languages" [value]="l.code">{{ l.label }}</mat-option>
            </mat-select>
          </mat-form-field>
        </form>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button (click)="dialogRef.close()">Cancel</button>
        <button mat-flat-button color="primary" (click)="save()" [disabled]="form.invalid || saving">
          {{ saving ? 'Saving...' : 'Save Changes' }}
        </button>
      </mat-dialog-actions>
    </div>
  `,
  styles: [`
    .dialog-container { padding: 8px; }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      padding-top: 8px;
    }
    .full-width { grid-column: 1 / -1; }
  `],
})
export class EditProfileDialogComponent implements OnInit {
  form!: FormGroup;
  languages = LANGUAGES;
  saving = false;

  constructor(
    private fb: FormBuilder,
    private api: ApiService,
    private auth: AuthService,
    public dialogRef: MatDialogRef<EditProfileDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: CurrentUser,
  ) {}

  ngOnInit(): void {
    this.form = this.fb.group({
      first_name: [this.data?.first_name || ''],
      last_name: [this.data?.last_name || ''],
      email: [this.data?.email || '', [Validators.required, Validators.email]],
      business_unit: [this.data?.business_unit || ''],
      language: [this.data?.language || 'en'],
    });
  }

  save(): void {
    if (this.form.invalid) return;
    this.saving = true;
    this.api.patch('/users/me', this.form.value).subscribe({
      next: () => {
        this.auth.loadCurrentUser().subscribe();
        this.dialogRef.close(true);
      },
      error: () => { this.saving = false; },
    });
  }
}
