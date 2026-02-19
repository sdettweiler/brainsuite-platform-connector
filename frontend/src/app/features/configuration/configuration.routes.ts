import { Routes } from '@angular/router';

export const CONFIGURATION_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () => import('./configuration-shell.component').then(m => m.ConfigurationShellComponent),
    children: [
      { path: '', redirectTo: 'organization', pathMatch: 'full' },
      {
        path: 'organization',
        loadComponent: () => import('./pages/organization.component').then(m => m.OrganizationComponent),
      },
      {
        path: 'metadata',
        loadComponent: () => import('./pages/metadata.component').then(m => m.MetadataComponent),
      },
      {
        path: 'platforms',
        loadComponent: () => import('./pages/platforms.component').then(m => m.PlatformsComponent),
      },
      {
        path: 'brainsuite-apps',
        loadComponent: () => import('./pages/brainsuite-apps.component').then(m => m.BrainsuiteAppsComponent),
      },
    ],
  },
];
