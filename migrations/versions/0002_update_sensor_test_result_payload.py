"""update_sensor_test_result_payload

Revision ID: 0002_update_sensor_test_result
Revises: 0001_initial
Create Date: 2026-06-29 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_update_sensor_test_result"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename columns to preserve data
    op.alter_column('sensor_test_results', 'quality_score_afiq', new_column_name='image_quality')
    op.alter_column('sensor_test_results', 'nfiq_score', new_column_name='nfiq2_score')

    # Drop removed columns
    op.drop_column('sensor_test_results', 'minutiae_count')

def downgrade() -> None:
    # Re-add removed columns
    op.add_column('sensor_test_results', sa.Column('minutiae_count', sa.Integer(), nullable=True, comment='Number of minutiae detected in the captured fingerprint'))
    
    # In a real environment, we would attempt to fill minutiae_count if possible before making it non-nullable,
    # but for downgrade simplicity we just leave it nullable or fill with 0.
    op.execute('UPDATE sensor_test_results SET minutiae_count = 0 WHERE minutiae_count IS NULL')
    op.alter_column('sensor_test_results', 'minutiae_count', nullable=False)

    # Rename columns back
    op.alter_column('sensor_test_results', 'image_quality', new_column_name='quality_score_afiq')
    op.alter_column('sensor_test_results', 'nfiq2_score', new_column_name='nfiq_score')
