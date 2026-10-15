import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db, migrate, login_manager
from app import models
from app.models import Ticket

from sqlalchemy import func, select

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(models.User, int(user_id))
    except (TypeError, ValueError):
        return None

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialization
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to access POSCollective"
    login_manager.init_app(app)

    @app.route("/admin/users")
    @login_required
    def admin_users():
        if current_user.role != "Owner":
            flash("You are not authorized to access user approvals.", "error")
            return redirect(url_for("dashboard"))

        pending_users = models.User.query.filter_by(
            approval_status="Pending"
        ).order_by(models.User.id.asc()).all()

        return render_template(
            "admin_users.html",
            pending_users=pending_users,
        )

    @app.route("/admin/users/<int:user_id>/review", methods=["POST"])
    @login_required
    def review_user(user_id):
        if current_user.role != "Owner":
            flash("You are not authorized to manage user approvals.", "error")
            return redirect(url_for("dashboard"))

        user = db.session.get(models.User, user_id)

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("admin_users"))

        if user.approval_status != "Pending":
            flash("This account has already been reviewed.", "error")
            return redirect(url_for("admin_users"))

        decision = request.form.get("decision")

        if decision == "approve":
            user.approval_status = "Approved"
            db.session.commit()
            flash(f"Approved account: {user.email}", "success")

        elif decision == "reject":
            user.approval_status = "Rejected"
            db.session.commit()
            flash(f"Rejected account: {user.email}", "success")

        else:
            flash("Invalid review decision.", "error")

        return redirect(url_for("admin_users"))

    @app.route("/")
    def index():
        # if not login_required:
        #     return redirect(url_for("login"))
        return redirect(url_for("dashboard"))
        # return "POSCollective is running."

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")

            user = models.User.query.filter_by(username=username).first()

            if( 
                user
                and user.is_active
                and user.approval_status == "Approved"
                and user.check_password(password)
            ):
                login_user(user)
                return redirect(url_for("dashboard"))

            flash(
                "Login failed. Check your credentials or account approval status.",
                "error",
            )

        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            email = username
            full_name = request.form.get("full_name", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not username or not password:
                flash("Email address and password are required.", "error")
                return render_template("register.html")

            if "@" not in username or "." not in username.split("@")[-1]:
                flash("Enter a valid email address." , "error")
                return render_template("register.html")

            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return render_template("register.html")

            existing_user = models.User.query.filter(
                (models.User.username == username)
                | (models.User.email == email)
            ).first()

            if existing_user:
                flash("That username or email is already registered.", "error")
                return render_template("register.html")

            user = models.User(
                username=username,
                email=email,
                full_name=full_name or None,
                role="Member",
                approval_status="Pending",
                is_active=True,
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            flash(
                "Registration submitted. Your account is awaiting Owner approval.",
                "success",
            )
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        status = request.args.get("status", "Open")
        sort_by = request.args.get("sort", "updated_at")
        direction = request.args.get("direction", "desc")

        sortable_columns = {
            "ticket_key": models.Ticket.id,
            "created_by": func.coalesce(
                func.nullif(models.User.full_name, ""),
                models.User.username,
            ),
            "updated_at": models.Ticket.updated_at,
            "ncr_case_number": models.Ticket.ncr_case_number,
            "title": models.Ticket.title,
            "ticket_type": models.Ticket.ticket_type,
            "versions": (
                select(func.min(models.TicketVersion.version))
                .where(models.TicketVersion.ticket_id == models.Ticket.id)
                .scalar_subquery()
            ),
            "hardware_software": models.Ticket.hardware_software,
            "status": models.Ticket.status,
        }

        if sort_by not in sortable_columns:
            sort_by = "updated_at"

        if direction not in ("asc", "desc"):
            direction = "desc"

        query = models.Ticket.query

        if status in ("Open", "Closed"):
            query = query.filter_by(status=status)

        if sort_by == "created_by":
            query = query.join(
                models.User,
                models.Ticket.created_by_id == models.User.id,
            )

        sort_column = sortable_columns[sort_by]

        if direction == "desc":
            query = query.order_by(sort_column.desc(), models.Ticket.id.desc())
        else:
            query = query.order_by(sort_column.asc(), models.Ticket.id.asc())

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 25, type=int)

        if page < 1:
            page = 1

        if per_page not in (10, 25, 50, 100):
            per_page = 25

        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False,
        )

        tickets = pagination.items

        # tickets = query.all()

        return render_template(
            "dashboard.html",
            tickets=tickets,
            current_status=status,
            sort_by=sort_by,
            direction=direction,
            pagination=pagination,
            per_page=per_page,
        )
        # return "POSCollective dashboard - login successful."

    return app
