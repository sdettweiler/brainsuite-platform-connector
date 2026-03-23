import { createReducer, on } from '@ngrx/store';
import { loginSuccess, loginFailure, logout, loadUserSuccess, loadUserFailure, tokenRefreshed, UserProfile } from './auth.actions';

export interface AuthState {
  user: UserProfile | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
}

const initialState: AuthState = {
  user: null,
  accessToken: null,
  isAuthenticated: false,
  loading: false,
  error: null,
};

export const authReducer = createReducer(
  initialState,

  on(loginSuccess, (state, { accessToken }) => ({
    ...state,
    accessToken,
    isAuthenticated: !!accessToken,
    error: null,
  })),

  on(loginFailure, (state, { error }) => ({
    ...state,
    error,
    isAuthenticated: false,
    accessToken: null,
  })),

  on(logout, () => ({
    user: null,
    accessToken: null,
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

  on(tokenRefreshed, (state, { accessToken }) => ({
    ...state,
    accessToken,
    isAuthenticated: !!accessToken,
  })),
);
