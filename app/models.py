from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)



class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    company = db.Column(db.String(150), nullable=True)

    role = db.Column(db.String(20), nullable=False, default="Member")
    approval_status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending",
        server_default="Pending",
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(50))

    create_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    # Display as T-0001, T-0002, etc.
    @property
    def ticket_key(self):
        return f"T-{self.id:04d}"

    ncr_case_number = db.Column(db.String(50))
    encor_jira_number = db.Column(db.String(100))
    encor_jira_na = db.Column(db.Boolean, nullable=False, default=False)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    ticket_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Open")
    priority = db.Column(db.String(20), default="Medium")

    # NCR's status is independent of our internal ticket status.
    ncr_state = db.Column(db.String(50))

    # site = db.Column(db.String(255))
    hardware_software = db.Column(db.String(20))

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )
    closed_at = db.Column(db.DateTime(timezone=True))

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    versions = db.relationship(
        "TicketVersion",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )
    ncr_threads = db.relationship(
        "NCRThread",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )
    internal_comments = db.relationship(
        "InternalComment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="InternalComment.created_at",
    )


class TicketVersion(db.Model):
    __tablename__ = "ticket_versions"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("tickets.id"),
        nullable=False,
    )

    version = db.Column(db.String(30), nullable=False)
    service_pack = db.Column(db.String(10))

    adk_version = db.Column(db.String(50))
    tb_version = db.Column(db.String(50))
    unit_model = db.Column(db.String(100))

    ticket = db.relationship("Ticket", back_populates="versions")


class NCRThread(db.Model):
    __tablename__ = "ncr_threads"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("tickets.id"),
        nullable=False
    )

    case_number = db.Column(db.String(50))
    subject = db.Column(db.String(255))
    ncr_state = db.Column(db.String(50))

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    ticket = db.relationship("Ticket", back_populates="ncr_threads")
    comments = db.relationship(
        "NCRComment",
        back_populates="thread",
       cascade="all, delete-orphan",
        order_by="NCRComment.comment_date",
    )

class NCRComment(db.Model):
    __tablename__ = "ncr_comments"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(
        db.Integer,
        db.ForeignKey("ncr_threads.id"),
        nullable=False,
    )

    author_name = db.Column(db.String(255))
    author_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    body = db.Column(db.Text, nullable=False)
    comment_date = db.Column(db.DateTime(timezone=True))
    imported_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    thread = db.relationship("NCRThread", back_populates="comments")
    author_user = db.relationship("User", foreign_keys=[author_user_id])


class InternalComment(db.Model):
    __tablename__ = "internal_comments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("tickets.id"),
        nullable=False,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    ticket = db.relationship("Ticket", back_populates="internal_comments")
    user = db.relationship("User", foreign_keys=[user_id])
