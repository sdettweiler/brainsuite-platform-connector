import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

export type Theme = 'dark-theme' | 'light-theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly STORAGE_KEY = 'bs-theme';
  private theme$ = new BehaviorSubject<Theme>('dark-theme');

  get currentTheme$() { return this.theme$.asObservable(); }
  get isDark() { return this.theme$.value === 'dark-theme'; }

  init(): void {
    const saved = localStorage.getItem(this.STORAGE_KEY) as Theme | null;
    const theme = saved || 'dark-theme';
    this.apply(theme);
  }

  toggle(): void {
    const next: Theme = this.theme$.value === 'dark-theme' ? 'light-theme' : 'dark-theme';
    this.apply(next);
  }

  private apply(theme: Theme): void {
    document.body.classList.remove('dark-theme', 'light-theme');
    document.body.classList.add(theme);
    this.theme$.next(theme);
    localStorage.setItem(this.STORAGE_KEY, theme);
  }
}
