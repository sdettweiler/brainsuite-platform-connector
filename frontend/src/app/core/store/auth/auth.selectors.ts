import { createFeatureSelector, createSelector } from '@ngrx/store';
import { AuthState } from './auth.reducer';

export const selectAuthState = createFeatureSelector<AuthState>('auth');

export const selectCurrentUser = createSelector(selectAuthState, s => s.user);
export const selectIsAuthenticated = createSelector(selectAuthState, s => s.isAuthenticated);
export const selectAccessToken = createSelector(selectAuthState, s => s.accessToken);
export const selectAuthError = createSelector(selectAuthState, s => s.error);
