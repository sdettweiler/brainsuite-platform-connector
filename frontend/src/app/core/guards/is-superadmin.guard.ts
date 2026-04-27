import { Injectable } from '@angular/core';
import { CanActivate, Router } from '@angular/router';
import { Observable, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { AuthService } from '../services/auth.service';

@Injectable({ providedIn: 'root' })
export class IsSuperAdminGuard implements CanActivate {
  constructor(
    private authService: AuthService,
    private router: Router,
  ) {}

  canActivate(): Observable<boolean> | boolean {
    if (this.authService.currentUser?.is_superuser) {
      return true;
    }
    // Attempt a fresh load before denying — handles stale session after promotion
    return this.authService.loadCurrentUser().pipe(
      map(user => {
        if (user.is_superuser) return true;
        this.router.navigate(['/']);
        return false;
      }),
      catchError(() => {
        this.router.navigate(['/']);
        return of(false);
      }),
    );
  }
}
