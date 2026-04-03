import secrets
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlite3 import IntegrityError

load_dotenv()

from auth import (  # noqa: E402
    auth_user_dependency,
    create_access_token,
    find_user_by_username_timing_safe,
    get_token_user,
    hash_password,
    require_permission,
    verify_password,
)
from config import get_settings  # noqa: E402
from database import get_db_connection, init_db  # noqa: E402
from models import (  # noqa: E402
    LoginJSON,
    TodoCreate,
    TodoOut,
    TodoUpdate,
    UserRegister,
)

limiter = Limiter(key_func=get_remote_address)


def _safe_digest(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="KR3 API",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    docs_basic = HTTPBasic()

    def verify_docs_credentials(credentials: HTTPBasicCredentials = Depends(docs_basic)) -> None:
        if settings.mode != "DEV":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if not (
            _safe_digest(credentials.username, settings.docs_user)
            and _safe_digest(credentials.password, settings.docs_password)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Basic"},
            )

    if settings.mode == "DEV":

        @app.get("/docs", include_in_schema=False)
        async def custom_docs(_: None = Depends(verify_docs_credentials)):
            return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} docs")

        @app.get("/openapi.json", include_in_schema=False)
        async def openapi_json(_: None = Depends(verify_docs_credentials)):
            return JSONResponse(app.openapi())

    else:

        @app.get("/docs", include_in_schema=False)
        async def docs_disabled():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        @app.get("/openapi.json", include_in_schema=False)
        async def openapi_disabled():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    @app.get("/redoc", include_in_schema=False)
    async def redoc_disabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    @app.get("/login", tags=["auth-basic"])
    async def login_basic(username: str = Depends(auth_user_dependency)):
        return {"message": f"Welcome, {username}!"}

    @app.post("/register", status_code=status.HTTP_201_CREATED, tags=["auth-jwt"])
    @limiter.limit("1/minute")
    async def register_jwt(request: Request, body: UserRegister):
        conn = get_db_connection()
        try:
            hashed = hash_password(body.password)
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (body.username, hashed, body.role),
            )
            conn.commit()
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists",
            )
        finally:
            conn.close()
        return {"message": "New user created"}

    @app.post("/login", tags=["auth-jwt"])
    @limiter.limit("5/minute")
    async def login_jwt(request: Request, body: LoginJSON):
        conn = get_db_connection()
        try:
            user = find_user_by_username_timing_safe(conn, body.username)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            if not verify_password(body.password, user["password"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authorization failed",
                )
            token = create_access_token(username=user["username"], role=user["role"])
            return {"access_token": token, "token_type": "bearer"}
        finally:
            conn.close()

    @app.get("/protected_resource", tags=["auth-jwt"])
    async def protected_resource(user: dict = Depends(get_token_user)):
        if user["role"] not in ("admin", "user"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return {"message": "Access granted"}

    @app.get("/rbac/admin/ping", tags=["rbac"])
    async def rbac_admin(_: dict = Depends(require_permission("rbac:admin"))):
        return {"message": "admin area"}

    @app.get("/rbac/user/readwrite", tags=["rbac"])
    async def rbac_user(_: dict = Depends(require_permission("rbac:user_rw"))):
        return {"message": "user read/write area"}

    @app.get("/rbac/guest/read", tags=["rbac"])
    async def rbac_guest(_: dict = Depends(require_permission("rbac:guest_read"))):
        return {"message": "guest read area"}

    @app.post(
        "/todos",
        response_model=TodoOut,
        status_code=status.HTTP_201_CREATED,
        tags=["todos"],
    )
    async def create_todo(
        body: TodoCreate,
        _: dict = Depends(require_permission("todo:create")),
    ):
        conn = get_db_connection()
        try:
            cur = conn.execute(
                "INSERT INTO todos (title, description, completed) VALUES (?, ?, 0)",
                (body.title, body.description),
            )
            conn.commit()
            tid = cur.lastrowid
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (tid,)).fetchone()
        finally:
            conn.close()
        return TodoOut(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            completed=bool(row["completed"]),
        )

    @app.get("/todos/{todo_id}", response_model=TodoOut, tags=["todos"])
    async def read_todo(
        todo_id: int,
        _: dict = Depends(require_permission("todo:read")),
    ):
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
        return TodoOut(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            completed=bool(row["completed"]),
        )

    @app.put("/todos/{todo_id}", response_model=TodoOut, tags=["todos"])
    async def update_todo(
        todo_id: int,
        body: TodoUpdate,
        _: dict = Depends(require_permission("todo:update")),
    ):
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
            conn.execute(
                "UPDATE todos SET title = ?, description = ?, completed = ? WHERE id = ?",
                (body.title, body.description, 1 if body.completed else 0, todo_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        finally:
            conn.close()
        return TodoOut(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            completed=bool(row["completed"]),
        )

    @app.delete("/todos/{todo_id}", tags=["todos"])
    async def delete_todo(
        todo_id: int,
        _: dict = Depends(require_permission("todo:delete")),
    ):
        conn = get_db_connection()
        try:
            cur = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
        finally:
            conn.close()
        return {"message": "Todo deleted successfully"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
