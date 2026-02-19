import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'auth',
    loadChildren: () => import('./features/auth/auth.routes').then(m => m.authRoutes),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./core/layout/shell.component').then(m => m.ShellComponent),
    children: [
      {
        path: '',
        redirectTo: 'home',
        pathMatch: 'full',
      },
      {
        path: 'home',
        loadComponent: () => import('./features/home/home.component').then(m => m.HomeComponent),
        title: 'Home — Brainsuite',
      },
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
        title: 'Dashboard — Brainsuite',
      },
      {
        path: 'comparison',
        loadComponent: () => import('./features/comparison/comparison.component').then(m => m.ComparisonComponent),
        title: 'Comparison — Brainsuite',
      },
      {
        path: 'configuration',
        loadChildren: () => import('./features/configuration/configuration.routes').then(m => m.CONFIGURATION_ROUTES),
        title: 'Configuration — Brainsuite',
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
