# Brainsuite Platform Connector

## Overview
A platform connector tool that integrates with Meta, TikTok, and YouTube/Google advertising platforms. Built with a FastAPI backend and Angular 16 frontend, using PostgreSQL for data storage.

## Architecture
- **Backend**: Python 3.12 + FastAPI (served via uvicorn on port 5000)
- **Frontend**: Angular 16 (production build served as static files by FastAPI)
- **Database**: PostgreSQL (Replit-managed)
- **ORM**: SQLAlchemy 2.0 (async with asyncpg)
- **Migrations**: Alembic

## Project Structure
```
backend/
  app/
    api/v1/          # REST API endpoints
    core/            # Config, security
    db/              # Database session/base
    models/          # SQLAlchemy models
    schemas/         # Pydantic schemas
    services/        # Business logic, sync scheduler
  alembic/           # Database migrations
  requirements.txt   # Python dependencies
frontend/
  src/               # Angular source
  angular.json       # Angular CLI config
  package.json       # Node dependencies
replit_start.sh      # Startup script (installs deps, runs migrations, starts server)
```

## Key Configuration
- The startup script (`replit_start.sh`) handles dependency installation, database migrations, and launching the server
- FastAPI serves both the API (`/api/v1/`) and the Angular SPA (static files)
- Database URL is auto-configured from Replit's `DATABASE_URL` environment variable
- CORS is auto-configured for the Replit domain

## Design System
- **Typography**: Nunito Sans (web fallback for Avenir Next) — Headlines: Demi Bold, Sub Headlines: Medium, Body: Regular
- **Primary Colors**: True White (#FFFFFF), Asphalt Black (#1B1B1B), Dusky Blue (#04093A)
- **Secondary Colors**: Deep Blue (#0009BC), Juicy Orange (#FF7700)
- **Brand Gradient**: 45deg from #DF4742 → #EC7235 → #F38A2E
- **CSS Variables**: All colors use CSS custom properties defined in `styles.scss` (--accent, --bg-primary, etc.)
- **Logo Assets**: Located in `frontend/src/assets/images/` (orange, white, black, orange-white, signet variants)

## Recent Changes
- 2026-02-19: Complete UI rework — brand colors (Juicy Orange + Dusky Blue), Nunito Sans typography, actual brand logos, comprehensive Material Design overrides for inputs/dropdowns/dialogs
- 2026-02-19: Imported project to Replit, fixed Angular build errors, configured for port 5000, fixed database connectivity

## User Preferences
- Brand-first design: All UI elements must use the Brainsuite design system colors and typography
- bcrypt must stay pinned to version 4.0.1 due to passlib compatibility
