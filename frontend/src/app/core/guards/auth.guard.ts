import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { map, catchError, of } from 'rxjs';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  // If already authenticated in memory, allow immediately
  if (auth.isAuthenticated) {
    return true;
  }

  // Attempt silent refresh (browser sends httpOnly cookie automatically)
  return auth.refreshTokens().pipe(
    map(() => true),
    catchError(() => of(router.createUrlTree(['/auth/login']))),
  );
};
