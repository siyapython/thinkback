"""rename the real demo account's display name from "Demo Learner" to "You"

The synthetic learner is called "Demo Learner (synthetic)"; having the real account called
"Demo Learner" too made the dashboard's user list confusing. Only the exact old name is
touched, so the synthetic user (a different name) is never renamed.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET display_name = 'You' WHERE display_name = 'Demo Learner'")


def downgrade() -> None:
    op.execute("UPDATE users SET display_name = 'Demo Learner' WHERE display_name = 'You'")
