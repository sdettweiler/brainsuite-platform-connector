import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatRadioModule } from '@angular/material/radio';

export interface DisconnectDialogData {
  accountName: string;
  count?: number;
}

export interface DisconnectDialogResult {
  mode: 'retain' | 'purge';
}

@Component({
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatDialogModule, MatButtonModule, MatRadioModule,
  ],
  template: `
    <div class="disconnect-dialog">
      <h2 mat-dialog-title>
        <i class="bi bi-plug" style="margin-right: 8px; color: var(--accent);"></i>
        Disconnect {{ data.count ? data.count + ' connection(s)' : '"' + data.accountName + '"' }}
      </h2>

      <mat-dialog-content>
        <div class="option-group">
          <mat-radio-group [(ngModel)]="selectedMode">
            <div class="option" [class.selected]="selectedMode === 'retain'" (click)="selectedMode = 'retain'">
              <mat-radio-button value="retain">
                <span class="option-title">Disconnect — keep existing data</span>
              </mat-radio-button>
              <p class="option-desc">The account will be deactivated. All synced performance data and creative assets will be preserved and remain accessible.</p>
            </div>

            <div class="option danger" [class.selected]="selectedMode === 'purge'" (click)="selectedMode = 'purge'">
              <mat-radio-button value="purge">
                <span class="option-title">Disconnect and delete all data</span>
              </mat-radio-button>
              <p class="option-desc">The account and all associated data will be permanently deleted, including performance metrics, creative assets, and stored files. This action cannot be undone.</p>
            </div>
          </mat-radio-group>
        </div>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button (click)="onCancel()">Cancel</button>
        <button mat-flat-button
                [color]="selectedMode === 'purge' ? 'warn' : 'primary'"
                (click)="onConfirm()">
          {{ selectedMode === 'purge' ? 'Delete permanently' : 'Disconnect' }}
        </button>
      </mat-dialog-actions>
    </div>
  `,
  styles: [`
    .disconnect-dialog {
      min-width: 420px;
    }
    h2 {
      font-family: 'Nunito Sans', sans-serif;
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 8px;
    }
    .option-group {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .option {
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 8px;
      padding: 14px 16px;
      cursor: pointer;
      transition: border-color 0.2s;
    }
    .option:hover {
      border-color: rgba(255,255,255,0.25);
    }
    .option.selected {
      border-color: var(--accent, #FF7700);
      background: rgba(255, 119, 0, 0.05);
    }
    .option.danger.selected {
      border-color: #f44336;
      background: rgba(244, 67, 54, 0.06);
    }
    .option-title {
      font-weight: 600;
      font-size: 14px;
    }
    .option-desc {
      margin: 6px 0 0 28px;
      font-size: 12.5px;
      color: rgba(255,255,255,0.55);
      line-height: 1.5;
    }
    .option.danger .option-desc {
      color: rgba(244, 67, 54, 0.7);
    }
    mat-dialog-actions {
      padding-top: 16px;
    }
    mat-dialog-actions button {
      font-family: 'Nunito Sans', sans-serif;
    }
  `],
})
export class DisconnectDialogComponent {
  selectedMode: 'retain' | 'purge' = 'retain';

  constructor(
    public dialogRef: MatDialogRef<DisconnectDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: DisconnectDialogData,
  ) {}

  onCancel(): void {
    this.dialogRef.close(null);
  }

  onConfirm(): void {
    this.dialogRef.close({ mode: this.selectedMode } as DisconnectDialogResult);
  }
}
