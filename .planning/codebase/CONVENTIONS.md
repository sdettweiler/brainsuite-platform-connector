# Coding Conventions

**Analysis Date:** 2026-03-20

## Languages & Type Systems

**TypeScript (Frontend):**
- Target: ES2022
- Strict mode: Enabled (`strict: true`)
- Implicit override checks enabled
- Property access from index signature disabled
- Return type inference enforced
- Case sensitivity enforced

**Python (Backend):**
- Async/await patterns used throughout (FastAPI + SQLAlchemy async)
- Type hints required (Pydantic models for validation)
- Docstrings for module-level classes (e.g., `"""Brainsuite scoring apps..."""`)

## Naming Patterns

**Files:**
- Components: `name.component.ts` (e.g., `sidebar.component.ts`)
- Services: `name.service.ts` (e.g., `auth.service.ts`)
- Guards: `name.guard.ts` (e.g., `auth.guard.ts`)
- Interceptors: `name.interceptor.ts` (e.g., `auth.interceptor.ts`)
- Actions: `name.actions.ts`
- Reducers: `name.reducer.ts`
- Selectors: `name.selectors.ts`
- Python models: `snake_case.py` (e.g., `user.py`, `platform.py`)
- Python schemas: `snake_case.py` in `schemas/` directory

**Functions:**
- camelCase for all functions across both frontends and backends
- Private functions prefixed with underscore: `_functionName()` (Python) or private methods in classes
- Async functions explicitly marked with `async` keyword (Python/TypeScript)

**Variables:**
- camelCase for local variables and properties
- UPPERCASE_SNAKE_CASE for constants (e.g., `ACCESS_KEY`, `REFRESH_KEY` in `auth.service.ts`)
- Private fields use underscore prefix: `private fieldName` or `_fieldName`

**Types & Interfaces:**
- PascalCase for all type/interface names
- Prefix with "I" NOT used (e.g., `AuthState` not `IAuthState`)
- Interface examples: `CurrentUser`, `AuthTokens`, `UserProfile`, `NavItem`

**Classes & Models:**
- PascalCase for all class names
- SQLAlchemy models use descriptive names: `User`, `Organization`, `PlatformConnection`, `BrainsuiteApp`
- Pydantic schema classes use suffixes: `UserCreate`, `UserResponse`, `UserUpdate`, `TokenResponse`

**Database/API:**
- Table names: snake_case (e.g., `refresh_tokens`, `organization_roles`)
- Column names: snake_case (e.g., `access_token_encrypted`, `last_synced_at`)
- Enum values: UPPERCASE_SNAKE_CASE (e.g., `ADMIN`, `STANDARD`, `READ_ONLY`, `PENDING`)

## Code Organization

**Frontend - Directory Structure:**
- `src/app/core/` - Core services, guards, interceptors, layout, store
- `src/app/features/` - Feature modules (home, configuration, dashboard, etc.)
- `src/app/shared/` - Shared components and utilities
- `src/environments/` - Environment configuration
- Path aliases configured in `tsconfig.json`:
  - `@core/*` → `src/app/core/*`
  - `@features/*` → `src/app/features/*`
  - `@shared/*` → `src/app/shared/*`
  - `@env/*` → `src/environments/*`

**Frontend - Component Structure:**
- Standalone components (no module declarations)
- Single-file components with inline template and styles using backtick strings
- Imports organized: Angular → Third-party → Local services/features
- Components declare dependencies inline in `imports: []`
- Change detection strategy `OnPush` is default in schematics configuration

**Backend - Directory Structure:**
- `app/core/` - Config, security, constants
- `app/models/` - SQLAlchemy ORM models
- `app/schemas/` - Pydantic request/response models
- `app/api/v1/endpoints/` - Route handlers grouped by resource
- `app/api/v1/deps.py` - Dependency injection functions
- `app/db/` - Database configuration and base classes

**Backend - API Patterns:**
- APIRouter per resource (e.g., `/auth`, `/users`, `/platforms`)
- Route functions are `async def`
- Dependencies injected via `Depends()` from FastAPI
- Request/response models validated with Pydantic
- Status codes returned explicitly (e.g., `status_code=201`)

## Import Organization

**Frontend:**
1. Angular core imports
2. RxJS imports
3. Third-party library imports (Material, ngx-echarts, etc.)
4. Local service imports (using path aliases)
5. Model/type imports

**Example from `auth.service.ts`:**
```typescript
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';

export interface AuthTokens { ... }
```

**Backend:**
1. Standard library imports
2. Third-party library imports (FastAPI, SQLAlchemy, Pydantic, etc.)
3. Local app imports

**Example from `auth.py` endpoint:**
```python
from datetime import datetime, timedelta
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.base import get_db
from app.core.security import verify_password, get_password_hash
from app.models.user import User, Organization
```

## Angular-Specific Patterns

**Dependency Injection:**
- Services marked with `@Injectable({ providedIn: 'root' })`
- Constructor injection used for all dependencies
- Typed parameters enforced (no `any` types)

**Observables & RxJS:**
- Services expose Observables: `currentUser$: Observable<CurrentUser>`
- BehaviorSubject for state: `private user$ = new BehaviorSubject<CurrentUser | null>(null)`
- `.pipe()` operators: `tap()` for side effects, `switchMap()` for async operations, `catchError()` for error handling
- Subscribe patterns: Component subscriptions stored in `Subscription` and cleaned up in `ngOnDestroy()`

**NgRx Store:**
- Actions defined in separate files with event naming convention: `[Source] Event Name`
- Examples: `[Auth] Login Success`, `[Auth] Logout`
- Reducers use spread operator for immutability: `{ ...state, field: value }`
- Strict typing for state interfaces and action payloads

**Components:**
- Inline template and styles (no external files)
- Use `CommonModule` for `*ngIf`, `*ngFor`
- Event handlers prefixed with `on` or `handle`: `onImgError()`, `navigateToDashboard()`
- Getter methods for computed values: `get firstName(): string { ... }`
- Lifecycle hooks implemented when needed: `OnInit`, `OnDestroy`

## Python/FastAPI Patterns

**Models (SQLAlchemy 2.0 with Mapped types):**
- Use type annotations: `Mapped[str]`, `Mapped[uuid.UUID]`, `Mapped[dict]`
- Column definitions with `mapped_column()`: `mapped_column(String(255), nullable=False, index=True)`
- Relationships defined with `relationship()` on both sides
- Timestamps included: `created_at`, `updated_at` with timezone
- Default values for status fields: `default="ACTIVE"` or similar
- Comments on complex classes (see `BrainsuiteApp` docstring)

**Schemas (Pydantic):**
- Separate Create/Update/Response schemas (e.g., `UserCreate`, `UserResponse`, `UserUpdate`)
- Validation using `@validator` decorators
- `from_attributes = True` in Config for ORM conversion
- EmailStr for email validation (from Pydantic)
- Optional fields for nullable columns: `Optional[str] = None`

**Endpoint Functions:**
- All functions are `async def`
- Status codes returned explicitly: `status_code=201` for create, default 200 for get/list
- HTTPException for errors: `HTTPException(status_code=400, detail="message")`
- Response models defined: `response_model=UserResponse`
- Dependencies injected: `db: AsyncSession = Depends(get_db)`, `current_user: User = Depends(get_current_user)`

**Error Handling:**
- FastAPI `HTTPException` with specific status codes (401, 403, 404, 400)
- Detail messages included: `detail="Email already registered"`
- Token validation returns `None` on error, checked with `if not payload`
- Database queries use `scalar_one_or_none()` to safely handle missing records

## Async Patterns

**Frontend (RxJS):**
- Observable-based (no promises)
- Operators like `switchMap()` for chaining async operations
- Error handling with `catchError()` returning Observable
- Subscription cleanup in component `ngOnDestroy()`

**Backend (SQLAlchemy Async):**
- `async with` for database sessions
- `await` on all database operations
- Background tasks via `BackgroundTasks` dependency for non-blocking work
- Token refresh logic shows retry pattern with `switchMap()` equivalent using `db.flush()` before `db.commit()`

## State Management

**Frontend:**
- BehaviorSubject for local state in services
- NgRx for global app state (auth state)
- Observables exposed for component consumption: `currentUser$ = this.user$.asObservable()`

**Backend:**
- SQLAlchemy models as source of truth
- No separate state management (stateless REST API)
- Session-based state with async transaction handling

## Comments & Documentation

**When to Comment:**
- Classes with non-obvious purpose (e.g., `BrainsuiteApp`: "Brainsuite scoring apps that ad accounts are mapped to.")
- Complex business logic in endpoints (e.g., organization join request flow)
- Constants with unclear meaning
- NOT used for obvious code (no comments for getters, simple assignments)

**JSDoc/TSDoc:**
- Minimal usage observed
- Type annotations used instead of JSDoc type comments
- Properties documented via TypeScript interface definitions

**Docstrings (Python):**
- Triple-quoted strings at class level (not extensively used)
- Endpoint docstrings minimal - logic is in the code

## Error Handling

**Frontend:**
- HTTP errors caught in interceptors
- 401 errors trigger token refresh retry logic with `switchMap()`
- Failed refresh logs user out
- Component-level error handling in subscribe `error` callback
- Loading states managed with boolean flags: `loading = true/false`

**Backend:**
- HTTPException for all API errors
- Status codes match HTTP standards (400, 401, 403, 404)
- Validation happens in Pydantic schemas before endpoint logic
- Database constraints enforced at schema and column level (unique, nullable, index)
- Optional token decoding returns `None` instead of throwing

## Formatting

**No linting config found** - Projects use default Angular/TypeScript formatting. Follow these patterns:
- 2-space indentation (observed in SCSS and TypeScript)
- Semicolons required (TypeScript)
- Single quotes for strings in template literals, double quotes in most code
- SCSS nesting permitted in component styles
- No Prettier config - format for readability

## Logging

**Framework:** Python uses standard `logging` module, frontend uses `console`

**Backend Patterns:**
- Logger instantiated per module: `logger = logging.getLogger(__name__)`
- Info level for migrations/startup: `logger.info("Database migrations complete")`
- Warning level for non-fatal errors: `logger.warning(f"Migration failed...")`
- Used in startup procedures and exception handling

**Frontend Patterns:**
- Direct `console.log()` not observed in samples
- Component logic keeps state via properties instead of logging

## Testing

**No test files detected** in codebase. See TESTING.md for framework setup.

## Convention Violations & Inconsistencies

**Observed inconsistencies:**
- Some endpoint functions use `payload` parameter name, others use typed parameters directly
- Error handling mixes implicit returns with explicit `return` statements
- NgRx action naming uses brackets `[Source]` - not universally enforced (optional pattern)

## Database Conventions

**Timestamps:**
- All major tables include `created_at` and `updated_at`
- Type: `DateTime(timezone=True)`
- Default: `datetime.utcnow`
- Auto-update on write: `onupdate=datetime.utcnow`

**IDs:**
- All primary keys are UUIDs: `UUID(as_uuid=True)`
- Generated server-side: `default=uuid.uuid4`
- Foreign keys reference UUIDs consistently

**Enums/Status Fields:**
- String columns with uppercase values (e.g., `ADMIN`, `PENDING`, `ACTIVE`)
- No enum types used (plain string columns with validation in code)

**Soft Deletes:**
- Not used - deletion is hard delete with constraints
- `is_active` flag used for logical disable instead

---

*Convention analysis: 2026-03-20*
