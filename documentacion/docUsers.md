# `users.py` — Users Router

## Purpose
CRUD endpoints for managing user accounts. Access is gated by role: admins can manage all users; non-admins can only read/update their own profile with restrictions.

---

## Endpoints

### `GET /users/` — List users
**Auth:** Admin only

Query params:
- `skip: int = 0` — pagination offset
- `limit: int = 50` — max 200
- `role: RoleEnum?` — filter by role

Returns `List[UserOut]`.

---

### `POST /users/` — Create user
**Auth:** Admin only

**Request body:** `UserCreate`

Validates:
- `dni` is unique → `HTTP 400` if duplicate.
- `email` is unique → `HTTP 400` if duplicate.

Hashes `password` with bcrypt before storing. Returns the created `UserOut`.

---

### `GET /users/{user_id}` — Get user
**Auth:** Any authenticated user

- Admin → can fetch any user.
- Non-admin → can only fetch own profile (`current.id == user_id`), else `HTTP 403`.

Returns `UserOut` or `HTTP 404`.

---

### `PATCH /users/{user_id}` — Update user
**Auth:** Any authenticated user

- Admin → can update any user, including `role` and `is_active`.
- Non-admin → can only update own profile; attempts to change `role` or `is_active` raise `HTTP 403`.

**Request body:** `UserUpdate` (all fields optional).

Returns updated `UserOut`.

---

### `DELETE /users/{user_id}` — Delete user
**Auth:** Admin only

Hard delete. Returns `{"detail": "Usuario <dni> eliminado"}`.

> No soft-delete: prefer setting `is_active=False` via PATCH to preserve audit history in `occupancies`.

---

## Permission Matrix

| Action | Estudiante | Profesor | Admin |
|---|---|---|---|
| List all users | ✗ | ✗ | ✓ |
| Create user | ✗ | ✗ | ✓ |
| View own profile | ✓ | ✓ | ✓ |
| View other profile | ✗ | ✗ | ✓ |
| Edit own profile | ✓ (no role/active) | ✓ (no role/active) | ✓ |
| Edit other profile | ✗ | ✗ | ✓ |
| Delete user | ✗ | ✗ | ✓ |
