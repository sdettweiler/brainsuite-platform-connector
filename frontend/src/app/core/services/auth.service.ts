import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  business_unit: string | null;
  language: string;
  organization_id: string;
  role?: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly ACCESS_KEY = 'bs_access';
  private readonly REFRESH_KEY = 'bs_refresh';

  private user$ = new BehaviorSubject<CurrentUser | null>(null);
  currentUser$ = this.user$.asObservable();

  constructor(private http: HttpClient, private router: Router) {}

  get isAuthenticated(): boolean {
    return !!this.getAccessToken();
  }

  get currentUser(): CurrentUser | null {
    return this.user$.value;
  }

  getAccessToken(): string | null {
    return localStorage.getItem(this.ACCESS_KEY);
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(this.REFRESH_KEY);
  }

  login(email: string, password: string): Observable<AuthTokens> {
    return this.http.post<AuthTokens>(`${environment.apiUrl}/auth/login`, { email, password }).pipe(
      tap(tokens => this.storeTokens(tokens))
    );
  }

  register(payload: any): Observable<any> {
    return this.http.post(`${environment.apiUrl}/auth/register`, payload);
  }

  logout(): void {
    const refresh = this.getRefreshToken();
    if (refresh) {
      this.http.post(`${environment.apiUrl}/auth/logout`, { refresh_token: refresh }).subscribe();
    }
    this.clearTokens();
    this.user$.next(null);
    this.router.navigate(['/auth/login']);
  }

  refreshTokens(): Observable<AuthTokens> {
    return this.http.post<AuthTokens>(`${environment.apiUrl}/auth/refresh`, {
      refresh_token: this.getRefreshToken(),
    }).pipe(
      tap(tokens => this.storeTokens(tokens))
    );
  }

  loadCurrentUser(): Observable<CurrentUser> {
    return this.http.get<CurrentUser>(`${environment.apiUrl}/auth/me`).pipe(
      tap(user => this.user$.next(user))
    );
  }

  private storeTokens(tokens: AuthTokens): void {
    localStorage.setItem(this.ACCESS_KEY, tokens.access_token);
    localStorage.setItem(this.REFRESH_KEY, tokens.refresh_token);
  }

  private clearTokens(): void {
    localStorage.removeItem(this.ACCESS_KEY);
    localStorage.removeItem(this.REFRESH_KEY);
  }
}
