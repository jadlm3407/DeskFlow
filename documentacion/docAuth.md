# `auth.py` — Authentication & Authorization

## Purpose
Centralizes all security logic: password hashing, JWT generation/validation, and FastAPI dependency injection for role-based access control.

---

## Constants

| Constant | Value | Description |
|---|---|---|
| `SECRET_KEY` | `"CAMBIA_ESTO..."` | HMAC signing key — **must be replaced in production** |
| `ALGORITHM` | `"HS256"` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Token TTL: 8 hours |

---

## Functions

### Password Utilities

```python
hash_password(plain: str) -> str
```
Hashes a plaintext password using **bcrypt** with auto-generated salt. Returns the hashed string stored in the DB.

```python
verify_password(plain: str, hashed: str) -> bool
```
Checks a plaintext password against a stored bcrypt hash. Used during login.

---

### JWT

```python
create_access_token(user_id: int, expires_delta: Optional[timedelta]) -> str
```
Encodes `{"sub": str(user_id), "exp": <UTC timestamp>}` into a signed JWT. Default expiry: 8 hours.

```python
decode_token(token: str) -> schemas.TokenData
```
Decodes and validates the JWT. Raises `HTTP 401` if the token is invalid or expired.

---

## FastAPI Dependencies

These are injected via `Depends()` in router endpoints.

```python
get_current_user(credentials, db) -> models.User
```
- Extracts the Bearer token from the `Authorization` header.
- Calls `decode_token()` to get `user_id`.
- Queries the DB for the user and verifies `is_active`.
- Raises `HTTP 401` if user is not found or inactive.

```python
require_admin(current) -> models.User
```
Wraps `get_current_user`. Raises `HTTP 403` if `role != admin`.

```python
require_profesor_or_admin(current) -> models.User
```
Wraps `get_current_user`. Raises `HTTP 403` if `role == estudiante`.

---

## Dependency Chain

```
bearer (HTTPBearer)
    └── get_current_user
            ├── require_admin
            └── require_profesor_or_admin
```

---

## Security Notes

- `SECRET_KEY` is hardcoded — replace with an environment variable (`os.environ["SECRET_KEY"]`) before any deployment.
- JWTs are stateless; logout is client-side only. For real revocation, implement a Redis token blacklist.
- bcrypt work factor is determined by `bcrypt.gensalt()` defaults (cost factor 12).
