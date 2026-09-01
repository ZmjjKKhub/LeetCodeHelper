"""Guard against models.py and the Alembic migration drifting apart.

Every other test builds its schema with SQLModel.metadata.create_all --
none of them ever run `alembic upgrade head`, which is the only path a real
user's data/app.db is created through (app.py refuses to start until it has
run). If models.py changes without a matching migration, every one of those
155 create_all-based tests keeps passing while a real install breaks on its
first query.
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlmodel import SQLModel

REPO_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def test_alembic_upgrade_head_matches_models(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_check.db"
    # migrations/env.py resolves its DB path through resolve_db_path(),
    # which honours LCH_DB_PATH -- point it at a throwaway file so this
    # test never touches the real data/app.db.
    monkeypatch.setenv("LCH_DB_PATH", str(db_path))

    cfg = Config(str(ALEMBIC_INI))
    from alembic import command

    command.upgrade(cfg, "head")

    assert db_path.exists()

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            diff = compare_metadata(context, SQLModel.metadata)
    finally:
        engine.dispose()

    assert diff == [], f"migration drifted from models.py: {diff!r}"
