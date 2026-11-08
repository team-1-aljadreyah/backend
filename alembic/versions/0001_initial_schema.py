"""initial schema baseline

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline schema migration - tables are initialized via database/schema.sql and SQLAlchemy Base metadata
    pass


def downgrade() -> None:
    pass
