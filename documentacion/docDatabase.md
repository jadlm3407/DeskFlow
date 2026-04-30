# `database.py` — Database Configuration

## Purpose
Bootstraps the SQLAlchemy engine, session factory, and declarative base. Exposes `get_db()` as a FastAPI dependency that yields a DB session per request.

---

## Configuration

| Variable | Value |
|---|---|
| `DATABASE_URL` | `sqlite:///./espacios.db` |
| `check_same_thread` | `False` — required for SQLite with FastAPI's async request handling |

---

## Objects

```python
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
```
The SQLAlchemy engine. SQLite stores the DB file as `espacios.db` in the working directory.

```python
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```
Session factory. `autocommit=False` means changes require an explicit `db.commit()`.

```python
Base = declarative_base()
```
Base class for all ORM models (`models.py` imports this to define tables).

---

## Dependency

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
Generator used with `Depends(get_db)` in every router endpoint. Guarantees the session is closed after each request regardless of success or exception.

---

## Production Notes

- SQLite is suitable for development/single-instance deployments only.
- For production, replace `DATABASE_URL` with PostgreSQL/MySQL: `postgresql://user:pass@host/dbname`.
- With PostgreSQL, remove `connect_args={"check_same_thread": False}` (SQLite-specific).
- Use `alembic` for schema migrations instead of `Base.metadata.create_all()`.
