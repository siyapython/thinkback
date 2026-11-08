"""Migration 0002 renames the real account "Demo Learner" to "You"; the seed uses the new name."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select

from app import seed
from app.models import User

MIGRATION = Path(__file__).parents[1] / "alembic/versions/0002_rename_demo_user_to_you.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_0002", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _name(session, user_id):
    session.expire_all()
    return session.scalar(select(User.display_name).where(User.id == user_id))


def test_upgrade_renames_only_the_exact_old_name_and_downgrade_reverses_it(session):
    real = User(display_name="Demo Learner")
    synthetic = User(display_name="Demo Learner (synthetic)")
    other = User(display_name="Somebody else")
    session.add_all([real, synthetic, other])
    session.flush()

    migration = _load_migration()
    with Operations.context(MigrationContext.configure(session.connection())):
        migration.upgrade()
        assert _name(session, real.id) == "You"
        assert _name(session, synthetic.id) == "Demo Learner (synthetic)"
        assert _name(session, other.id) == "Somebody else"

        migration.downgrade()
        assert _name(session, real.id) == "Demo Learner"
        assert _name(session, synthetic.id) == "Demo Learner (synthetic)"


def test_seed_uses_the_new_name():
    assert seed.DEMO_NAME == "You"
