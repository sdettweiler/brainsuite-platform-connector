import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterResponse {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  is_active: boolean;
  organization_id: string | null;
  last_login: string | null;
  created_at: string;
  business_unit: string | null;
  language: string;
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
  organization_currency: string;
  role?: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private accessToken$ = new BehaviorSubject<string | null>(null);

  private user$ = new BehaviorSubject<CurrentUser | null>(null);
  currentUser$ = this.user$.asObservable();

  constructor(private http: HttpClient, private router: Router) {}

  get isAuthenticated(): boolean {
    return this.accessToken$.value !== null;
  }

  get currentUser(): CurrentUser | null {
    return this.user$.value;
  }

  getAccessToken(): string | null {
    return this.accessToken$.value;
  }

  login(email: string, password: string): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(
      `${environment.apiUrl}/auth/login`,
      { email, password },
      { withCredentials: true },
    ).pipe(
      tap(res => this.accessToken$.next(res.access_token)),
    );
  }

  register(payload: any): Observable<RegisterResponse> {
    return this.http.post<RegisterResponse>(`${environment.apiUrl}/auth/register`, payload);
  }

  logout(): void {
    this.http.post(
      `${environment.apiUrl}/auth/logout`,
      {},
      { withCredentials: true },
    ).subscribe();
    this.accessToken$.next(null);
    this.user$.next(null);
    this.router.navigate(['/auth/login']);
  }

  refreshTokens(): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(
      `${environment.apiUrl}/auth/refresh`,
      {},
      { withCredentials: true },
    ).pipe(
      tap(res => this.accessToken$.next(res.access_token)),
    );
  }

  loadCurrentUser(): Observable<CurrentUser> {
    return this.http.get<CurrentUser>(`${environment.apiUrl}/auth/me`).pipe(
      tap(user => this.user$.next(user)),
    );
  }
}
