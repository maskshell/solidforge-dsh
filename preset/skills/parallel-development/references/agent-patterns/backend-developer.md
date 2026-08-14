# Backend Code Patterns

Comprehensive code patterns for backend development across languages and frameworks.

## REST API Handlers

### Python/FastAPI

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str


class UserService:
    async def create_user(self, data: UserCreate) -> UserResponse:
        existing = await self.db.users.find_one({"username": data.username})
        if existing:
            raise HTTPException(status_code=400, detail="Username exists")
        user = await self.db.users.insert_one(data.dict())
        return UserResponse(id=user.inserted_id, **data.dict())


@router.post("/", response_model=UserResponse)
async def create_user(data: UserCreate, service: UserService = Depends(get_service)):
    return await service.create_user(data)
```

### Node.js/Express

```typescript
import { Router } from 'express';
const router = Router();

router.post('/', async (req, res) => {
  try {
    const user = await userService.createUser(req.body);
    res.status(201).json(user);
  } catch (error) {
    if (error.code === 'DUPLICATE_KEY') {
      return res.status(409).json({ error: 'Username exists' });
    }
    res.status(500).json({ error: 'Internal server error' });
  }
});
```

### Rust/Axum

```rust
use axum::{extract::State, http::StatusCode, response::IntoResponse, Json, Router};
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
pub struct CreateUser {
    pub username: String,
    pub email: String,
    pub password: String,
}

#[derive(Serialize)]
pub struct User {
    pub id: i32,
    pub username: String,
    pub email: String,
}

pub fn router() -> Router<PgPool> {
    Router::new()
        .route("/users", axum::routing::post(create_user))
        .route("/users/:id", axum::routing::get(get_user))
}

pub async fn create_user(
    State(pool): State<PgPool>,
    Json(payload): Json<CreateUser>,
) -> Result<impl IntoResponse, StatusCode> {
    // Check and create user logic
    let user = sqlx::query_as::<_, User>(
        "INSERT INTO users (username, email) VALUES ($1, $2) RETURNING *"
    )
    .bind(&payload.username)
    .bind(&payload.email)
    .fetch_one(&pool)
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(user))
}
```

## Database Models

### Python/SQLAlchemy

```python
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Rust/SQLx

```rust
use serde::{Deserialize, Serialize};
use sqlx::FromRow;

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct User {
    pub id: i32,
    pub username: String,
    pub email: String,
    pub created_at: chrono::DateTime<chrono::Utc>,
}
```

## Authentication Services

### TypeScript/JWT

```typescript
export class AuthService {
  async generateToken(user: User): Promise<string> {
    return jwt.sign({ userId: user.id }, config.SECRET, { expiresIn: '24h' });
  }

  async verifyToken(token: string): Promise<TokenPayload | null> {
    try {
      return jwt.verify(token, config.SECRET) as TokenPayload;
    } catch {
      return null;
    }
  }
}
```

### Rust/JWT

```rust
pub struct AuthService { pub secret: String }

impl AuthService {
  pub fn generate_token(&self, user_id: &str) -> Result<String, jsonwebtoken::Error> {
    let claims = Claims { sub: user_id.to_string(), exp: expiration() };
    encode(&Header::default(), &claims, &EncodingKey::from_secret(self.secret.as_ref()))
  }
}
```

## Middleware Patterns

### Python/FastAPI

```python
async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    token = creds.credentials
    payload = await AuthService.verifyToken(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return await UserService.get_user_by_id(payload.userId)
```

### Rust/Axum

```rust
pub async fn auth_middleware(
    req: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let token = req.headers().get("Authorization")
        .and_then(|h| h.to_str().ok())
        .and_then(|h| h.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;

    let claims = crate::services::auth::verify_token(token)
        .map_err(|_| StatusCode::UNAUTHORIZED)?;

    req.extensions_mut().insert(AuthenticatedUser { id: claims.sub });
    Ok(next.run(req).await)
}
```

## Error Handling

```typescript
interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

function errorResponse(code: string, message: string): ApiError {
  return { code, message };
}
```

## Testing Patterns

### Python/Pytest

```python
@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.mark.asyncio
async def test_create_user(mock_db):
    mock_db.users.find_one.return_value = None
    service = UserService(mock_db)
    result = await service.create_user({"username": "test"})
    assert result.username == "test"
```

### Rust

```rust
#[tokio::test]
async fn test_create_user() {
    let user = create_user("testuser").await;
    assert_eq!(user.username, "testuser");
}
```

## Cargo Commands

```bash
cargo test              # Run all tests
cargo check             # Quick compile check
cargo clippy -- -D warnings  # Lint
cargo fmt               # Format code
```

## Common Crates

```toml
[dependencies]
axum = "0.7"
tokio = { version = "1", features = ["full"] }
sqlx = { version = "0.7", features = ["runtime-tokio-rustls", "postgres"] }
serde = { version = "1", features = ["derive"] }
anyhow = "1"
thiserror = "1"
```

## See Also

- [memory-protocol.md](../skills/parallel-dev/references/memory-protocol.md)
- [ast-grep-patterns.md](../skills/parallel-dev/references/ast-grep-patterns.md)
