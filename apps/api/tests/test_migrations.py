from alembic import command
from sqlalchemy import inspect, text

from app.core.db import get_engine
from tests.conftest import alembic_config


def _tables() -> set[str]:
    return set(inspect(get_engine()).get_table_names()) - {"alembic_version"}


def test_migrations_down_and_up() -> None:
    cfg = alembic_config()

    command.downgrade(cfg, "base")
    assert _tables() == set()

    command.upgrade(cfg, "head")
    assert {"users", "candidate_profiles", "settings"} <= _tables()
    with get_engine().connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")) == 1


def test_models_match_migrations() -> None:
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.models import Base

    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
