import { createReducer, on } from '@ngrx/store';
import { loginSuccess, loginFailure, logout, loadUserSuccess, loadUserFailure, tokenRefreshed, UserProfile } from './auth.actions';

export interface AuthState {
  user: UserProfile | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
}

const initialState: AuthState = {
  user: null,
  accessToken: localStorage.getItem('bs_access'),
  refreshToken: localStorage.getItem('bs_refresh'),
  isAuthenticated: !!localStorage.getItem('bs_access'),
  loading: false,
  error: null,
};

export const authReducer = createReducer(
  initialState,

  on(loginSuccess, (state, { accessToken, refreshToken }) => ({
    ...state,
    accessToken,
    refreshToken,
    isAuthenticated: true,
    error: null,
  })),

  on(loginFailure, (state, { error }) => ({
    ...state,
    error,
    isAuthenticated: false,
    accessToken: null,
    refreshToken: null,
  })),

  on(logout, () => ({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    loading: false,
    error: null,
  })),

  on(loadUserSuccess, (state, { user }) => ({
    ...state,
    user,
    loading: false,
  })),

  on(loadUserFailure, (state, { error }) => ({
    ...state,
    error,
    loading: false,
  })),

  on(tokenRefreshed, (state, { accessToken, refreshToken }) => ({
    ...state,
    accessToken,
    refreshToken,
  })),
);
