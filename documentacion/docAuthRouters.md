# `authRouters.py` — Authentication Router

## Purpose
Exposes three HTTP endpoints under `/auth` for login, logout, and fetching the current user's profile.

---

## Endpoints

### `POST /auth/login`

**Request body:** `LoginRequest` (`dni`, `password`)

**Flow:**
1. Query DB for a `User` with matching `dni`.
2. `verify_password(body.password, user.hashed_pw)` — bcrypt check.
3. If the user is inactive (`is_active=False`) → `HTTP 403`.
4. `create_access_token(user.id)` → JWT valid for 8 hours.
5. Return `Token(access_token, token_type="bearer", user=UserOut)`.

**Errors:**

| Code | Condition |
|---|---|
| 401 | DNI not found or password mismatch |
| 403 | Account deactivated |

---

### `POST /auth/logout`

**Auth required:** Yes (Bearer token)

Stateless logout — does nothing server-side. The client is responsible for discarding the JWT.

Returns `{"detail": "Sesión cerrada correctamente"}`.

> To implement real token revocation, add a Redis blacklist and check it in `decode_token()`.

---

### `GET /auth/me`

**Auth required:** Yes (Bearer token)

Returns the `UserOut` schema for the authenticated user. Useful for the frontend to hydrate user state after a page refresh.

---

## Notes

- The router is registered in `main.py` as `app.include_router(auth.router)`.
- Login does not implement rate limiting or account lockout — add these before production deployment.
