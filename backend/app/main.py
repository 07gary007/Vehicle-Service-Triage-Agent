from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import get_settings
from .db import Base, engine
from .observability import RequestIdMiddleware

settings = get_settings()
app = FastAPI(title="Vehicle Service Triage Agent", version=settings.app_version)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    # Local development remains zero-setup. Production should run Alembic before
    # starting the API and set AUTO_CREATE_SCHEMA=false.
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)


app.include_router(router)
