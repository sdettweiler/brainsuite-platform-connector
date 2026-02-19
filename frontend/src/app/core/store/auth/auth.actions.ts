import { createAction, props } from '@ngrx/store';

export interface UserProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  organization_id: string;
  organization_name: string;
  organization_currency: string;
}

export const loginSuccess = createAction(
  '[Auth] Login Success',
  props<{ accessToken: string; refreshToken: string }>(),
);

export const loginFailure = createAction(
  '[Auth] Login Failure',
  props<{ error: string }>(),
);

export const logout = createAction('[Auth] Logout');

export const loadUserSuccess = createAction(
  '[Auth] Load User Success',
  props<{ user: UserProfile }>(),
);

export const loadUserFailure = createAction(
  '[Auth] Load User Failure',
  props<{ error: string }>(),
);

export const tokenRefreshed = createAction(
  '[Auth] Token Refreshed',
  props<{ accessToken: string; refreshToken: string }>(),
);
