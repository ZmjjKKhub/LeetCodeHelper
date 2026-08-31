"""数据库连接。DB 路径可用 LCH_DB_PATH 覆盖，测试用内存库。"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, create_engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_db_path(project_root: Path | None = None) -> Path:
    override = os.environ.get("LCH_DB_PATH")
    if override:
        return Path(override)
    root = project_root if project_root is not None else PROJECT_ROOT
    return root / "data" / "app.db"


def make_engine(db_path: Path | None = None) -> Engine:
    path = db_path if db_path is not None else resolve_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
