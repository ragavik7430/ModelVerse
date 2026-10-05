"""Add Phase 5 experiment and trained model records.

Revision ID: 202610050001
Revises: 202610030001
Create Date: 2026-10-05 00:01:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "202610050001"
down_revision = "202610030001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=True),
        sa.Column("problem_type", sa.String(length=32), nullable=False),
        sa.Column("target_column", sa.String(length=255), nullable=True),
        sa.Column("experiment_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("random_state", sa.Integer(), nullable=False),
        sa.Column("test_size", sa.Float(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("best_model_id", sa.Integer(), nullable=True),
        sa.Column("comparison_policy", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_experiments_id"), "experiments", ["id"], unique=False)
    op.create_index(op.f("ix_experiments_project_id"), "experiments", ["project_id"], unique=False)
    op.create_index(op.f("ix_experiments_dataset_id"), "experiments", ["dataset_id"], unique=False)

    op.create_table(
        "experiment_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("algorithm", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("preprocessing", sa.JSON(), nullable=False),
        sa.Column("artifact_key", sa.String(length=500), nullable=True),
        sa.Column("mlflow_run_id", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_experiment_models_id"), "experiment_models", ["id"], unique=False)
    op.create_index(op.f("ix_experiment_models_experiment_id"), "experiment_models", ["experiment_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_experiment_models_experiment_id"), table_name="experiment_models")
    op.drop_index(op.f("ix_experiment_models_id"), table_name="experiment_models")
    op.drop_table("experiment_models")
    op.drop_index(op.f("ix_experiments_dataset_id"), table_name="experiments")
    op.drop_index(op.f("ix_experiments_project_id"), table_name="experiments")
    op.drop_index(op.f("ix_experiments_id"), table_name="experiments")
    op.drop_table("experiments")
