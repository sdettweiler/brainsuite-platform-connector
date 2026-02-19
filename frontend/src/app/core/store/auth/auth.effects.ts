import { Injectable } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';
import { loginSuccess, logout, tokenRefreshed } from './auth.actions';

@Injectable()
export class AuthEffects {
  // Persist tokens to localStorage on login
  persistLogin$ = createEffect(
    () =>
      this.actions$.pipe(
        ofType(loginSuccess),
        tap(({ accessToken, refreshToken }) => {
          localStorage.setItem('bs_access', accessToken);
          localStorage.setItem('bs_refresh', refreshToken);
        }),
      ),
    { dispatch: false },
  );

  // Persist refreshed tokens
  persistRefresh$ = createEffect(
    () =>
      this.actions$.pipe(
        ofType(tokenRefreshed),
        tap(({ accessToken, refreshToken }) => {
          localStorage.setItem('bs_access', accessToken);
          localStorage.setItem('bs_refresh', refreshToken);
        }),
      ),
    { dispatch: false },
  );

  // Clear storage and redirect on logout
  logout$ = createEffect(
    () =>
      this.actions$.pipe(
        ofType(logout),
        tap(() => {
          localStorage.removeItem('bs_access');
          localStorage.removeItem('bs_refresh');
          this.router.navigate(['/auth/login']);
        }),
      ),
    { dispatch: false },
  );

  constructor(
    private actions$: Actions,
    private router: Router,
  ) {}
}
