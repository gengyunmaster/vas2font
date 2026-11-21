import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("access_code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("font_family", sa.String(80), nullable=False),
        sa.Column("font_version", sa.String(20), nullable=False),
        sa.Column("pipeline_version", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id")),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("layout_version", sa.String(30), nullable=False),
        sa.Column("reference_font_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column(
            "template_id", sa.Uuid(), sa.ForeignKey("templates.id"), nullable=False
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("notebook", postgresql.JSONB(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("vas_version", sa.Integer(), nullable=False),
        sa.Column("glyph_count", sa.Integer(), nullable=False),
        sa.Column("stroke_count", sa.Integer(), nullable=False),
        sa.Column("validation_report", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_builtin_templates_name_version_active",
        "templates",
        ["name", "version"],
        unique=True,
        postgresql_where=sa.text("project_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_custom_templates_project_name_version_active",
        "templates",
        ["project_id", "name", "version"],
        unique=True,
        postgresql_where=sa.text("project_id IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_uploads_project_position_active",
        "uploads",
        ["project_id", "position"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_uploads_template_active",
        "uploads",
        ["template_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("uploads")
    op.drop_table("templates")
    op.drop_table("projects")
