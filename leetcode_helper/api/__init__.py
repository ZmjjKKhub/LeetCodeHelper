"""JSON API layer for the React frontend migration.

Every route here returns JSON only, mirrors an existing Jinja page's data
(see web/routes/), and goes through repositories/ exactly as the HTML routes
do -- no select() in this package. Mounted under /api by
web/app_factory.py::create_app.
"""

from __future__ import annotations

from fastapi import APIRouter

from .routes import history as history_routes
from .routes import meta as meta_routes
from .routes import today as today_routes

router = APIRouter()
router.include_router(today_routes.router)
router.include_router(history_routes.router)
router.include_router(meta_routes.router)

__all__ = ["router"]
