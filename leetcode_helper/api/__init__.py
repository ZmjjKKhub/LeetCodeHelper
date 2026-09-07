"""JSON API layer for the React frontend.

Every route here returns JSON only and goes through repositories/ -- no
select() in this package. Mounted under /api by
web/app_factory.py::create_app.
"""

from __future__ import annotations

from fastapi import APIRouter

from .routes import history as history_routes
from .routes import meta as meta_routes
from .routes import progress as progress_routes
from .routes import today as today_routes

router = APIRouter()
router.include_router(today_routes.router)
router.include_router(history_routes.router)
router.include_router(meta_routes.router)
router.include_router(progress_routes.router)

__all__ = ["router"]
