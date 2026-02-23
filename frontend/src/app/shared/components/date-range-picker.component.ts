import {
  Component, EventEmitter, Input, Output, ElementRef,
  ViewChild, HostListener, OnInit, OnChanges, SimpleChanges
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';

export interface DateRangeChange {
  dateFrom: string;
  dateTo: string;
  preset: string;
}

interface CalendarDay {
  date: Date;
  day: number;
  inMonth: boolean;
  isToday: boolean;
  isSelected: boolean;
  isInRange: boolean;
  isRangeStart: boolean;
  isRangeEnd: boolean;
  isPast: boolean;
}

@Component({
  selector: 'app-date-range-picker',
  standalone: true,
  imports: [CommonModule, MatButtonModule],
  template: `
    <div class="drp-wrapper" #drpRef>
      <button class="drp-trigger" (click)="toggle()">
        <i class="bi bi-calendar3 cal-icon"></i>
        <span class="drp-label">{{ displayLabel }}</span>
        <i class="bi bi-chevron-down drp-chevron"></i>
      </button>

      <div class="drp-dropdown" *ngIf="open" [class.drop-up]="dropUp">
        <div class="drp-body">
          <div class="drp-sidebar">
            <div class="sidebar-title">Quick select</div>
            <button
              *ngFor="let p of presets"
              class="sidebar-btn"
              [class.active]="pendingPreset === p.key"
              (click)="onPresetClick(p.key)"
            >{{ p.label }}</button>
          </div>

          <div class="drp-calendars">
            <div class="cal-header">
              <button class="nav-btn" (click)="prevMonth()">
                <i class="bi bi-chevron-left"></i>
              </button>
              <span class="cal-month-label">{{ monthLabel(leftMonth) }}</span>
              <span class="cal-month-label">{{ monthLabel(rightMonth) }}</span>
              <button class="nav-btn" (click)="nextMonth()">
                <i class="bi bi-chevron-right"></i>
              </button>
            </div>

            <div class="cal-grids">
              <div class="cal-grid">
                <div class="cal-weekdays">
                  <span *ngFor="let d of weekdays">{{ d }}</span>
                </div>
                <div class="cal-days">
                  <button
                    *ngFor="let day of leftDays"
                    class="day-btn"
                    [class.other-month]="!day.inMonth"
                    [class.today]="day.isToday"
                    [class.selected]="day.isSelected"
                    [class.in-range]="day.isInRange"
                    [class.range-start]="day.isRangeStart"
                    [class.range-end]="day.isRangeEnd"
                    [disabled]="!day.inMonth"
                    (click)="onDayClick(day)"
                    (mouseenter)="onDayHover(day)"
                  >{{ day.day }}</button>
                </div>
              </div>

              <div class="cal-grid">
                <div class="cal-weekdays">
                  <span *ngFor="let d of weekdays">{{ d }}</span>
                </div>
                <div class="cal-days">
                  <button
                    *ngFor="let day of rightDays"
                    class="day-btn"
                    [class.other-month]="!day.inMonth"
                    [class.today]="day.isToday"
                    [class.selected]="day.isSelected"
                    [class.in-range]="day.isInRange"
                    [class.range-start]="day.isRangeStart"
                    [class.range-end]="day.isRangeEnd"
                    [disabled]="!day.inMonth"
                    (click)="onDayClick(day)"
                    (mouseenter)="onDayHover(day)"
                  >{{ day.day }}</button>
                </div>
              </div>
            </div>

            <div class="cal-footer">
              <button class="today-link" (click)="goToToday()">Today</button>
              <div class="footer-actions">
                <button class="cancel-btn" (click)="onCancel()">Cancel</button>
                <button class="apply-btn" (click)="onApply()">Apply</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .drp-wrapper { position: relative; }

    .drp-trigger {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--bg-card);
      color: var(--text-primary);
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      height: 36px;
      transition: all 0.15s;
      white-space: nowrap;
      font-family: inherit;
    }
    .drp-trigger:hover { border-color: var(--accent); background: var(--bg-hover); }
    .cal-icon { font-size: 15px; color: var(--accent); }
    .drp-chevron { font-size: 12px; color: var(--text-secondary); }

    .drp-dropdown {
      position: absolute;
      top: calc(100% + 4px);
      left: 0;
      z-index: 1000;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.25);
      animation: drpIn 0.15s ease-out;
    }
    .drp-dropdown.drop-up {
      top: auto;
      bottom: calc(100% + 4px);
    }

    @keyframes drpIn {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .drp-body {
      display: flex;
    }

    .drp-sidebar {
      width: 160px;
      border-right: 1px solid var(--border);
      padding: 16px 12px;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .sidebar-title {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      padding: 0 8px 8px;
    }

    .sidebar-btn {
      padding: 8px 12px;
      border: none;
      background: transparent;
      color: var(--text-primary);
      font-size: 13px;
      text-align: left;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.1s;
      font-family: inherit;
    }
    .sidebar-btn:hover { background: var(--bg-hover); }
    .sidebar-btn.active { color: var(--accent); font-weight: 600; }

    .drp-calendars {
      padding: 16px 20px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .cal-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 4px 8px;
    }

    .cal-month-label {
      font-size: 14px;
      font-weight: 600;
      flex: 1;
      text-align: center;
    }

    .nav-btn {
      width: 28px;
      height: 28px;
      border: none;
      background: transparent;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--text-secondary);
      transition: all 0.1s;
    }
    .nav-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
    .nav-btn i.bi { font-size: 16px; }

    .cal-grids {
      display: flex;
      gap: 24px;
    }

    .cal-grid {
      width: 252px;
    }

    .cal-weekdays {
      display: grid;
      grid-template-columns: repeat(7, 36px);
      text-align: center;
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 4px;
    }
    .cal-weekdays span {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 28px;
    }

    .cal-days {
      display: grid;
      grid-template-columns: repeat(7, 36px);
    }

    .day-btn {
      width: 36px;
      height: 34px;
      border: none;
      background: transparent;
      font-size: 13px;
      cursor: pointer;
      border-radius: 0;
      color: var(--text-primary);
      transition: background 0.08s;
      font-family: inherit;
      position: relative;
    }
    .day-btn:hover:not(:disabled):not(.selected) { background: var(--bg-hover); }
    .day-btn:disabled, .day-btn.other-month {
      color: transparent;
      pointer-events: none;
    }

    .day-btn.today {
      font-weight: 700;
      color: var(--accent);
    }
    .day-btn.today::after {
      content: '';
      position: absolute;
      bottom: 3px;
      left: 50%;
      transform: translateX(-50%);
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: var(--accent);
    }

    .day-btn.in-range {
      background: rgba(255, 119, 0, 0.12);
    }
    .day-btn.selected {
      background: var(--accent);
      color: white;
      font-weight: 600;
    }
    .day-btn.range-start {
      border-radius: 50% 0 0 50%;
      background: var(--accent);
      color: white;
      font-weight: 600;
    }
    .day-btn.range-end {
      border-radius: 0 50% 50% 0;
      background: var(--accent);
      color: white;
      font-weight: 600;
    }
    .day-btn.range-start.range-end {
      border-radius: 50%;
    }

    .cal-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 0 0;
      border-top: 1px solid var(--border);
      margin-top: 4px;
    }

    .today-link {
      border: none;
      background: none;
      color: var(--text-secondary);
      font-size: 13px;
      cursor: pointer;
      padding: 4px 8px;
      font-family: inherit;
    }
    .today-link:hover { color: var(--accent); }

    .footer-actions {
      display: flex;
      gap: 8px;
    }

    .cancel-btn {
      padding: 6px 16px;
      border: none;
      background: transparent;
      color: var(--text-secondary);
      font-size: 13px;
      cursor: pointer;
      border-radius: 6px;
      font-family: inherit;
    }
    .cancel-btn:hover { background: var(--bg-hover); }

    .apply-btn {
      padding: 6px 20px;
      border: none;
      background: var(--accent);
      color: white;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      border-radius: 6px;
      font-family: inherit;
      transition: opacity 0.1s;
    }
    .apply-btn:hover { opacity: 0.9; }
  `]
})
export class DateRangePickerComponent implements OnInit, OnChanges {
  @Input() dateFrom = '';
  @Input() dateTo = '';
  @Input() selectedPreset = 'last30';
  @Input() dropUp = false;
  @Output() dateChange = new EventEmitter<DateRangeChange>();

  @ViewChild('drpRef') drpRef!: ElementRef;

  open = false;
  weekdays = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

  leftMonth!: Date;
  rightMonth!: Date;
  leftDays: CalendarDay[] = [];
  rightDays: CalendarDay[] = [];

  pendingFrom: Date | null = null;
  pendingTo: Date | null = null;
  hoverDate: Date | null = null;
  pendingPreset = '';
  selectingEnd = false;

  presets = [
    { key: 'last7', label: 'Last 7 days' },
    { key: 'last30', label: 'Last 30 days' },
    { key: 'last90', label: 'Last 90 days' },
    { key: 'last6months', label: 'Last 6 months' },
    { key: 'lastYear', label: 'Last year' },
    { key: 'lifetime', label: 'Lifetime' },
    { key: 'custom', label: 'Custom range' },
  ];

  get displayLabel(): string {
    if (!this.dateFrom || !this.dateTo) return 'Select dates';
    const from = new Date(this.dateFrom + 'T00:00:00');
    const to = new Date(this.dateTo + 'T00:00:00');
    const fmtOpts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' };
    return `${from.toLocaleDateString('en-GB', fmtOpts)} — ${to.toLocaleDateString('en-GB', fmtOpts)}`;
  }

  ngOnInit(): void {
    this.initMonths();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['dateFrom'] || changes['dateTo'] || changes['selectedPreset']) {
      this.initMonths();
    }
  }

  private initMonths(): void {
    const ref = this.dateTo ? new Date(this.dateTo + 'T00:00:00') : new Date();
    this.leftMonth = new Date(ref.getFullYear(), ref.getMonth(), 1);
    this.rightMonth = new Date(ref.getFullYear(), ref.getMonth() + 1, 1);
    this.pendingFrom = this.dateFrom ? new Date(this.dateFrom + 'T00:00:00') : null;
    this.pendingTo = this.dateTo ? new Date(this.dateTo + 'T00:00:00') : null;
    this.pendingPreset = this.selectedPreset;
    this.selectingEnd = false;
    this.buildDays();
  }

  @HostListener('document:click', ['$event'])
  onDocClick(event: MouseEvent): void {
    if (this.open && this.drpRef && !this.drpRef.nativeElement.contains(event.target)) {
      this.open = false;
    }
  }

  toggle(): void {
    this.open = !this.open;
    if (this.open) {
      this.initMonths();
    }
  }

  prevMonth(): void {
    this.leftMonth = new Date(this.leftMonth.getFullYear(), this.leftMonth.getMonth() - 1, 1);
    this.rightMonth = new Date(this.leftMonth.getFullYear(), this.leftMonth.getMonth() + 1, 1);
    this.buildDays();
  }

  nextMonth(): void {
    this.leftMonth = new Date(this.leftMonth.getFullYear(), this.leftMonth.getMonth() + 1, 1);
    this.rightMonth = new Date(this.leftMonth.getFullYear(), this.leftMonth.getMonth() + 1, 1);
    this.buildDays();
  }

  monthLabel(d: Date): string {
    return d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  }

  onPresetClick(key: string): void {
    this.pendingPreset = key;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    switch (key) {
      case 'last7': {
        const from = new Date(today);
        from.setDate(from.getDate() - 7);
        this.pendingFrom = from;
        this.pendingTo = yesterday;
        break;
      }
      case 'last30': {
        const from = new Date(today);
        from.setDate(from.getDate() - 30);
        this.pendingFrom = from;
        this.pendingTo = yesterday;
        break;
      }
      case 'last90': {
        const from = new Date(today);
        from.setDate(from.getDate() - 90);
        this.pendingFrom = from;
        this.pendingTo = yesterday;
        break;
      }
      case 'last6months': {
        const from = new Date(today);
        from.setMonth(from.getMonth() - 6);
        this.pendingFrom = from;
        this.pendingTo = yesterday;
        break;
      }
      case 'lastYear': {
        const from = new Date(today.getFullYear() - 1, 0, 1);
        const to = new Date(today.getFullYear() - 1, 11, 31);
        this.pendingFrom = from;
        this.pendingTo = to;
        break;
      }
      case 'lifetime': {
        this.pendingFrom = new Date(2020, 0, 1);
        this.pendingTo = yesterday;
        break;
      }
      case 'custom': {
        this.selectingEnd = false;
        break;
      }
    }

    if (key !== 'custom' && this.pendingFrom) {
      this.leftMonth = new Date(this.pendingFrom.getFullYear(), this.pendingFrom.getMonth(), 1);
      this.rightMonth = new Date(this.leftMonth.getFullYear(), this.leftMonth.getMonth() + 1, 1);
    }
    this.selectingEnd = false;
    this.buildDays();
  }

  onDayClick(day: CalendarDay): void {
    if (!day.inMonth) return;
    this.pendingPreset = 'custom';

    if (!this.selectingEnd || !this.pendingFrom) {
      this.pendingFrom = new Date(day.date);
      this.pendingTo = null;
      this.selectingEnd = true;
    } else {
      if (day.date < this.pendingFrom) {
        this.pendingTo = new Date(this.pendingFrom);
        this.pendingFrom = new Date(day.date);
      } else {
        this.pendingTo = new Date(day.date);
      }
      this.selectingEnd = false;
    }
    this.buildDays();
  }

  onDayHover(day: CalendarDay): void {
    if (this.selectingEnd && day.inMonth) {
      this.hoverDate = day.date;
      this.buildDays();
    }
  }

  goToToday(): void {
    const today = new Date();
    this.leftMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    this.rightMonth = new Date(today.getFullYear(), today.getMonth() + 1, 1);
    this.buildDays();
  }

  onCancel(): void {
    this.open = false;
  }

  onApply(): void {
    if (this.pendingFrom && this.pendingTo) {
      this.dateFrom = this.fmt(this.pendingFrom);
      this.dateTo = this.fmt(this.pendingTo);
      this.selectedPreset = this.pendingPreset;
      this.open = false;
      this.dateChange.emit({
        dateFrom: this.dateFrom,
        dateTo: this.dateTo,
        preset: this.pendingPreset,
      });
    }
  }

  private fmt(d: Date): string {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  private sameDay(a: Date | null, b: Date): boolean {
    if (!a) return false;
    return a.getFullYear() === b.getFullYear()
      && a.getMonth() === b.getMonth()
      && a.getDate() === b.getDate();
  }

  private buildDays(): void {
    this.leftDays = this.buildMonth(this.leftMonth);
    this.rightDays = this.buildMonth(this.rightMonth);
  }

  private buildMonth(monthDate: Date): CalendarDay[] {
    const year = monthDate.getFullYear();
    const month = monthDate.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const rangeStart = this.pendingFrom;
    const rangeEnd = this.selectingEnd && this.hoverDate ? this.hoverDate : this.pendingTo;

    const days: CalendarDay[] = [];

    for (let i = 0; i < firstDay; i++) {
      const prevDate = new Date(year, month, -(firstDay - 1 - i));
      days.push({
        date: prevDate,
        day: prevDate.getDate(),
        inMonth: false,
        isToday: false,
        isSelected: false,
        isInRange: false,
        isRangeStart: false,
        isRangeEnd: false,
        isPast: prevDate < today,
      });
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const date = new Date(year, month, d);
      const isStart = this.sameDay(rangeStart, date);
      const isEnd = this.sameDay(rangeEnd, date);
      let inRange = false;

      if (rangeStart && rangeEnd) {
        const effectiveStart = rangeStart <= rangeEnd ? rangeStart : rangeEnd;
        const effectiveEnd = rangeStart <= rangeEnd ? rangeEnd : rangeStart;
        inRange = date > effectiveStart && date < effectiveEnd;
      }

      days.push({
        date,
        day: d,
        inMonth: true,
        isToday: this.sameDay(today, date),
        isSelected: isStart || isEnd,
        isInRange: inRange,
        isRangeStart: isStart && (!isEnd || this.sameDay(rangeStart, rangeEnd!)),
        isRangeEnd: isEnd && !isStart,
        isPast: date < today,
      });
    }

    const remaining = 42 - days.length;
    for (let i = 1; i <= remaining; i++) {
      const nextDate = new Date(year, month + 1, i);
      days.push({
        date: nextDate,
        day: nextDate.getDate(),
        inMonth: false,
        isToday: false,
        isSelected: false,
        isInRange: false,
        isRangeStart: false,
        isRangeEnd: false,
        isPast: false,
      });
    }

    return days;
  }
}
