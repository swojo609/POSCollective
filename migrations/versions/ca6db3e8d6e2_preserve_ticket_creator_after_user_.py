"""Preserve ticket creator after user deletion

Revision ID: ca6db3e8d6e2
Revises: e59c1c5804c7
Create Date: 2026-10-20 16:48:58.237305

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ca6db3e8d6e2'
down_revision = 'e59c1c5804c7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tickets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("created_by_name", sa.String(length=255), nullable=True)
        )
        batch_op.alter_column(
            "created_by_id",
            existing_type=sa.INTEGER(),
            nullable=True,
        )
        batch_op.drop_constraint(
            "tickets_created_by_id_fkey",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_tickets_created_by_id_users",
            "users",
            ["created_by_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table("tickets", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_tickets_created_by_id_users",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "tickets_created_by_id_fkey",
            "users",
            ["created_by_id"],
            ["id"],
        )
        batch_op.alter_column(
            "created_by_id",
            existing_type=sa.INTEGER(),
            nullable=False,
        )
        batch_op.drop_column("created_by_name")

    # ### end Alembic commands ###
