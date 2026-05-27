from contextlib import asynccontextmanager
import hashlib
import re
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from starlette.types import Scope
import os

from app.database import init_db
from app.api.sessions_routes import router as sessions_router
from app.api.messages_routes import router as messages_router
from app.api.meta_routes import router as meta_router
from app.api.memory_routes import router as memory_router
from app.api.document_routes import router as document_router
from app.api.settings_routes import router as settings_router
from app.api.metrics_routes import router as metrics_router
from app.api.upload_routes import router as upload_router
from app.auth import router as auth_router, SessionAuthMiddleware
from app.config import settings
from app.runtime_settings import load_settings_from_db


def _parse_cors_origins(raw: str, auth_enabled: bool) -> list[str]:
    """Parse CORS_ORIGINS env var into a list FastAPI can use.

    - Explicit list (comma-separated): used as-is regardless of auth state.
    - Wildcard "*" with auth disabled: allow all origins (dev default).
    - Wildcard "*" with auth enabled: collapse to same-origin only ([])
      because browsers reject wildcard origins with credentials anyway.
    """
    stripped = raw.strip()
    if stripped and stripped != "*":
        return [o.strip() for o in stripped.split(",") if o.strip()]
    return ["*"] if not auth_enabled else []


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await load_settings_from_db()
    # # DEBUG: Uncomment to dump the LangGraph node diagram on startup.
    # # Saves langgraph_nodes.png next to wherever the server is launched from.
    # from app.agents.graph import RESUME_GRAPH
    # with open("langgraph_nodes.png", "wb") as _f:
    #     _f.write(RESUME_GRAPH.get_graph().draw_mermaid_png())
    yield


app = FastAPI(
    title="StackResume",
    version="4.1.0",
    lifespan=lifespan,
)

# CORS — driven by CORS_ORIGINS env var; safe same-origin default when auth is on.
_origins = _parse_cors_origins(settings.cors_origins, settings.auth_enabled)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=settings.auth_enabled,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional session auth — no-op when AUTH_ENABLED=false.
app.add_middleware(SessionAuthMiddleware)

app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(messages_router)
app.include_router(meta_router)
app.include_router(memory_router)
app.include_router(document_router)
app.include_router(settings_router)
app.include_router(metrics_router)
app.include_router(upload_router)

# Serve frontend
frontend_dir = "/frontend"

# Cache-busting: every /assets URL in index.html gets `?v=<build_id>` appended,
# where build_id is a hash of frontend file mtimes+sizes. A new build → new id →
# browsers refetch. Paired with no-cache on the HTML itself (so the new id is
# always discovered) and immutable long-max-age on /assets (so unchanged files
# stay cached forever between deploys).
_INDEX_CACHE: tuple[str, str] | None = None
_ASSET_URL_RE = re.compile(r'((?:href|src)="/assets/[^"?#]+)(["#])')


def _compute_build_id(root: str) -> str:
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            st = p.stat()
            h.update(str(p.relative_to(root)).encode())
            h.update(f"{st.st_mtime_ns}:{st.st_size}".encode())
    return h.hexdigest()[:12]


def _load_index(root: str) -> tuple[str, str]:
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        build_id = _compute_build_id(root)
        html = Path(root, "index.html").read_text()
        rewritten = _ASSET_URL_RE.sub(rf'\1?v={build_id}\2', html)
        _INDEX_CACHE = (build_id, rewritten)
    return _INDEX_CACHE


class _ImmutableStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        resp = await super().get_response(path, scope)
        if resp.status_code == 200:
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp


def _index_response(request: Request) -> Response:
    build_id, html = _load_index(frontend_dir)
    etag = f'"{build_id}"'
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=html, media_type="text/html", headers=headers)


if os.path.exists(frontend_dir):
    app.mount("/assets", _ImmutableStaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index(request: Request):
        return _index_response(request)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def catch_all(full_path: str, request: Request):
        return _index_response(request)
