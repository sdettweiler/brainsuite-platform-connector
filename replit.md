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

## Recent Changes
- 2026-02-19: Imported project to Replit, fixed Angular build errors, configured for port 5000, fixed database connectivity

## User Preferences
- None recorded yet
