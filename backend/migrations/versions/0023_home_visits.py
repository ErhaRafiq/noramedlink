"""on-demand home visits: doctor base location and radius, requests and offers

Additive and guarded: four columns on doctor_profiles (home visits off, no location until the doctor sets
one) and two new tables. emergency_bookings is not touched and nothing is copied from it.

Revision ID: 0023
Revises: 0022
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROFILE_COLUMNS = ("home_visits_enabled", "service_radius_km", "base_latitude", "base_longitude")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("doctor_profiles")}
    if "home_visits_enabled" not in existing:
        op.add_column(
            "doctor_profiles",
            sa.Column("home_visits_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
    for name in ("service_radius_km", "base_latitude", "base_longitude"):
        if name not in existing:
            op.add_column("doctor_profiles", sa.Column(name, sa.Float(), nullable=True))

    if not inspector.has_table("home_visit_requests"):
        op.create_table(
            "home_visit_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(20), server_default="offered", nullable=False),
            sa.Column("match_mode", sa.String(10), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("specialty", sa.String(80), nullable=False),
            sa.Column("contact_phone", sa.String(40), nullable=False),
            sa.Column("address_text", sa.Text(), nullable=False),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("accuracy_m", sa.Float(), nullable=True),
            sa.Column("location_source", sa.String(10), nullable=False),
            sa.Column("eta_minutes", sa.Integer(), nullable=True),
            sa.Column("visit_findings", sa.Text(), nullable=True),
            sa.Column("visit_advice", sa.Text(), nullable=True),
            sa.Column("visit_follow_up", sa.Text(), nullable=True),
            sa.Column("ended_reason", sa.String(300), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("en_route_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="home_visit_latitude_range"),
            sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="home_visit_longitude_range"),
            sa.CheckConstraint("match_mode IN ('auto', 'choose')", name="home_visit_match_mode"),
        )
        op.create_index("home_visit_requests_patient_idx", "home_visit_requests", ["patient_id", "created_at"])
        op.create_index("home_visit_requests_doctor_idx", "home_visit_requests", ["doctor_id", "status"])
        op.create_index(
            "home_visit_one_active_per_doctor_uq",
            "home_visit_requests",
            ["doctor_id"],
            unique=True,
            postgresql_where=sa.text("status IN ('accepted', 'en_route', 'arrived')"),
        )

    if not inspector.has_table("home_visit_offers"):
        op.create_table(
            "home_visit_offers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "request_id", sa.Integer(), sa.ForeignKey("home_visit_requests.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("distance_km", sa.Float(), nullable=False),
            sa.Column("outcome", sa.String(10), server_default="pending", nullable=False),
            sa.Column("offered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("request_id", "doctor_id", name="home_visit_offer_once_per_doctor"),
            sa.CheckConstraint(
                "outcome IN ('pending', 'accepted', 'declined', 'expired', 'withdrawn')",
                name="home_visit_offer_outcome",
            ),
        )
        op.create_index("home_visit_offers_doctor_idx", "home_visit_offers", ["doctor_id", "outcome"])
        op.create_index(
            "home_visit_one_pending_offer_uq",
            "home_visit_offers",
            ["request_id"],
            unique=True,
            postgresql_where=sa.text("outcome = 'pending'"),
        )


def downgrade() -> None:
    # The tables hold patients' requests and visit summaries: refuse while any exist.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("home_visit_requests") and bind.execute(
        sa.text("SELECT COUNT(*) FROM home_visit_requests")
    ).scalar():
        raise RuntimeError("0023 cannot be downgraded: home-visit requests are recorded.")
    if inspector.has_table("home_visit_offers"):
        op.drop_table("home_visit_offers")
    if inspector.has_table("home_visit_requests"):
        op.drop_table("home_visit_requests")
    existing = {c["name"] for c in inspector.get_columns("doctor_profiles")}
    for column in reversed(PROFILE_COLUMNS):
        if column in existing:
            op.drop_column("doctor_profiles", column)
