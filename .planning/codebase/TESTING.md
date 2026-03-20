# Testing Patterns

**Analysis Date:** 2026-03-20

## Current Test Status

**No test files detected** in the codebase. Testing infrastructure is configured but no tests have been written.

## Test Framework Configuration

**Frontend (Angular 17):**
- Test runner: Karma (default Angular setup)
- Run command: `npm run test` (mapped to `ng test`)
- Config: No explicit `karma.conf.js` or `test.ts` files found
- TypeScript test support enabled via `tsconfig.json`
- Likely testing framework: Jasmine (Angular default)

**Backend (FastAPI):**
- No test dependencies in `pyproject.toml`
- No pytest configuration found
- Test infrastructure not set up

## Frontend Test Patterns

**When tests are added, follow these patterns based on Angular CLI defaults:**

**Component Tests - Basic Structure:**
```typescript
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HomeComponent } from './home.component';

describe('HomeComponent', () => {
  let component: HomeComponent;
  let fixture: ComponentFixture<HomeComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomeComponent]
    }).compileComponents();

    fixture = TestBed.createComponent(HomeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
```

**Service Tests - Dependency Injection:**
```typescript
import { TestBed } from '@angular/core/testing';
import { AuthService } from './auth.service';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [AuthService]
    });
    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
```

**Test File Location:**
- Co-located with source files (not in separate `tests/` directory)
- Naming: `name.spec.ts` (e.g., `auth.service.spec.ts`, `home.component.spec.ts`)

**Testing Services:**
- Use `HttpClientTestingModule` from `@angular/common/http/testing`
- Inject `HttpTestingController` to verify HTTP calls
- Mock dependencies via `TestBed.configureTestingModule()`
- Call `httpMock.verify()` after each test to ensure no outstanding HTTP requests

**Testing Components:**
- Create fixture via `TestBed.createComponent(ComponentClass)`
- Call `fixture.detectChanges()` to trigger initial `ngOnInit()`
- Access component via `fixture.componentInstance`
- Query DOM via `fixture.debugElement.query()` or `fixture.nativeElement`
- Standalone components passed to `imports: []` in TestBed

**Testing Observable Patterns:**
```typescript
// Example: testing BehaviorSubject from service
it('should emit current user', (done) => {
  service.currentUser$.subscribe(user => {
    expect(user).toBeDefined();
    done();
  });
});

// Example: testing service with HttpClient
it('should call login endpoint', () => {
  service.login('user@example.com', 'password').subscribe();
  const req = httpMock.expectOne(`${environment.apiUrl}/auth/login`);
  expect(req.request.method).toBe('POST');
  req.flush({ access_token: 'token', refresh_token: 'refresh' });
});
```

**Testing NgRx Store:**
- Mock store via `provideMockStore()` in TestBed
- Test actions with `store.dispatch()`
- Verify selectors return expected state slices

**Testing Interceptors:**
```typescript
// Interceptors tested via HttpClientTestingModule
// Mock the service dependencies and verify HTTP request modification
it('should add authorization header', () => {
  service.login('test', 'test').subscribe();
  const req = httpMock.expectOne(url);
  expect(req.request.headers.has('Authorization')).toBe(true);
});
```

## Backend Test Patterns

**When tests are added to FastAPI, follow these patterns:**

**Setup - Dependencies:**
```python
# Install test dependencies (add to project)
# pip install pytest pytest-asyncio httpx

# Create conftest.py for shared fixtures
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from fastapi.testclient import TestClient

@pytest.fixture
async def db_session():
    """Database session for tests"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest.fixture
def client():
    """Test client for API"""
    return TestClient(app)
```

**Endpoint Tests - Basic Structure:**
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_success():
    """Test successful login"""
    response = client.post("/api/v1/auth/login", json={
        "email": "user@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()

def test_login_invalid_credentials():
    """Test login with wrong password"""
    response = client.post("/api/v1/auth/login", json={
        "email": "user@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"

def test_register_email_already_exists():
    """Test registration with duplicate email"""
    # First registration
    client.post("/api/v1/auth/register", json={...})
    # Duplicate
    response = client.post("/api/v1/auth/register", json={...})
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]
```

**Async Test Patterns:**
```python
import pytest

@pytest.mark.asyncio
async def test_token_refresh(db_session):
    """Test token refresh endpoint with async database"""
    # Create test user
    user = User(email="test@example.com", password_hash=hash_password("pass"))
    db_session.add(user)
    await db_session.commit()

    # Test refresh token logic
    assert user.id is not None
```

**Database Test Fixtures:**
```python
@pytest.fixture
async def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("password123"),
        first_name="Test",
        last_name="User"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
async def test_organization(db_session):
    """Create a test organization"""
    org = Organization(name="Test Org", slug="test-org", currency="USD")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org
```

**Authentication Testing:**
```python
def test_protected_endpoint_without_token():
    """Test that protected endpoints reject missing auth"""
    response = client.get("/api/v1/users/me")
    assert response.status_code == 403

def test_protected_endpoint_with_token(test_user):
    """Test protected endpoint with valid token"""
    token = create_access_token({"sub": str(test_user.id)})
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email
```

**Testing Database Constraints:**
```python
def test_unique_email_constraint(db_session, test_user):
    """Test database enforces email uniqueness"""
    duplicate = User(email=test_user.email, password_hash="hash")
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
```

**Test File Location:**
- Either co-located with source: `auth.test.py` next to `auth.py`
- Or in `tests/` directory with matching structure: `tests/api/v1/endpoints/test_auth.py`
- Naming: `test_*.py` or `*_test.py` (pytest discovers both)

## Coverage Requirements

**Current:** No coverage targets enforced

**Recommended approach when tests are added:**
- Aim for 70%+ coverage for critical paths (auth, user management)
- Lower coverage acceptable for UI components and generated code
- View coverage with: `npm run test -- --code-coverage` (frontend) or `pytest --cov=app` (backend)

## What to Test

**Frontend - High Priority:**
1. **Auth Service:**
   - Login success/failure
   - Token storage/retrieval
   - Logout clears tokens
   - Token refresh flow

2. **Auth Interceptor:**
   - Adds auth header to requests
   - Handles 401 responses with token refresh
   - Prevents infinite refresh loops

3. **Auth Guard:**
   - Blocks navigation to protected routes when not authenticated
   - Allows navigation when authenticated

4. **Core Components:**
   - Home component renders data when loaded
   - Shows loading state during fetch
   - Handles empty states correctly

**Backend - High Priority:**
1. **Authentication Endpoints:**
   - Register (success, duplicate email, validation)
   - Login (success, invalid credentials, 2FA)
   - Logout (revokes refresh token)
   - Token refresh (creates new tokens, revokes old)

2. **User Endpoints:**
   - Get current user profile
   - Update user profile
   - Get organization details

3. **Platform Connections:**
   - Create connection (validates platform, ad account)
   - List connections for organization
   - Delete/deactivate connection

4. **Authorization:**
   - Admin-only endpoints reject non-admins
   - Users can only access their own organization data

## What NOT to Test

- Third-party library functionality (Angular Material, RxJS operators)
- Obvious getters/setters with no logic
- HTML formatting and styling (use visual regression testing instead)
- Database migrations (test via integration tests only)

## Test Data & Factories

**Frontend:**
- Use literal test data objects
- No factory pattern needed (small test sets)

**Backend:**
- Use pytest fixtures for test data
- Create reusable fixtures: `test_user`, `test_organization`, `test_auth_token`
- Fixtures should be in `conftest.py` for sharing across test files

## Mocking Strategy

**Frontend:**
- HttpClientTestingModule for HTTP mocks
- TestBed for service dependency mocking
- No external API calls in tests
- localStorage mocked via spyOn/jasmine

**Backend:**
- Database tests use in-memory SQLite (`:memory:`)
- External API calls: mock requests/responses
- JWT token generation: use real functions (no mocks)
- Password hashing: use real bcrypt (no mocks - security critical)

## Running Tests

**Frontend:**
```bash
npm run test                    # Run tests in watch mode
npm run test -- --code-coverage # Run with coverage report
ng test --watch=false --browsers=ChromeHeadless  # Single run
```

**Backend:**
```bash
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest --cov=app               # With coverage
pytest -k test_auth            # Run specific tests
pytest -x                       # Stop on first failure
pytest --asyncio-mode=auto     # For async tests
```

## Best Practices

1. **Test Names:**
   - Descriptive: `test_login_with_valid_credentials_returns_tokens` not `test_login`
   - Follows pattern: `test_[unit]_[scenario]_[expected_outcome]`

2. **Isolation:**
   - Each test is independent
   - No shared state between tests
   - Clean up after each test (cleanup fixtures)

3. **Assertions:**
   - One logical assertion per test (multiple related assertions OK)
   - Use specific matchers: `expect(status).toBe(401)` not `expect(status).toBeTruthy()`

4. **Error Testing:**
   - Test both success AND failure paths
   - Verify error messages are helpful
   - Test edge cases (empty inputs, missing fields, expired tokens)

5. **Async Handling:**
   - Frontend: use `done()` callback or return Promise from test
   - Backend: use `@pytest.mark.asyncio` for async test functions

6. **Mocking:**
   - Mock external dependencies (HTTP, database)
   - Don't mock code under test
   - Keep mocks simple and readable

## Environment & Configuration

**Frontend Test Environment:**
- Uses default browser from karma.conf.js (Chrome/ChromeHeadless)
- TypeScript compiled on-the-fly during test runs
- Module resolution uses same path aliases as production (`@core/*`, etc.)

**Backend Test Environment:**
- Uses in-memory database by default (SQLite)
- Async SQLAlchemy requires pytest-asyncio plugin
- Environment variables loaded from `.env.test` if exists

## Known Limitations

1. **No E2E Tests:** Cypress/Playwright not set up - integration tests would be valuable
2. **No Visual Regression:** Component styling not tested - manual or visual regression testing needed
3. **No API Contract Tests:** No tools like Pact or Prism for API contract validation
4. **No Performance Tests:** Load testing not configured

---

*Testing analysis: 2026-03-20*
