"""enable pgvector

Revision ID: dbf193372fb1
Revises: 729ec658106b
Create Date: 2026-09-14 10:33:33.040141

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dbf193372fb1'
down_revision: Union[str, Sequence[str], None] = '729ec658106b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
