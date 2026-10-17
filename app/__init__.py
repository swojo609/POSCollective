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

    @app.route("/tickets/new", methods=["GET","POST"])
    @login_required
    def create_ticket():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            ticket_type = request.form.get("ticket_type", "").strip()

            if not title or not ticket_type:
                flash("Title and incident type are required.", "error")
                return render_template("ticket_form.html")

            ticket = models.Ticket(
                title=title,
                description=request.form.get("description", "").strip(),
                ncr_case_number=request.form.get("ncr_case_number", "").strip() or None,
                encor_jira_number=request.form.get("encor_jira_number", "").strip() or None,
                encor_jira_na=request.form.get("encor_jira_na") == "yes",
                ticket_type=ticket_type,
                priority=request.form.get("priority", "Medium"),
                # site=request.form.get("site", "").strip() or None,
                hardware_software=request.form.get("hardware_software") or None,
                created_by_id=current_user.id,
            )

            db.session.add(ticket)
            db.session.flush()

            if ticket_type == "ENCOR":
                version = request.form.get("version", "").strip()
                service_pack = request.form.get("service_pack", "-").strip()

                if version:
                    ticket_version = models.TicketVersion(
                        ticket_id=ticket.id,
                        version=version,
                        service_pack=None if service_pack == "-" else service_pack,
                    )
                    db.session.add(ticket_version)

            elif ticket_type == "SCO":
                adk_version = request.form.get("adk_version", "").strip()
                tb_version = request.form.get("tb_version", "").strip()

                if adk_version or tb_version:
                    ticket_version = models.TicketVersion(
                        ticket_id=ticket.id,
                        version=f"ADK{adk_version} TB{tb_version}",
                    )
                    db.session.add(ticket_version)

            elif ticket_type == "ISS45":
                iss45_version = request.form.get("iss45_version", "").strip()

                if iss45_version:
                    ticket_version = models.TicketVersion(
                        ticket_id=ticket.id,
                        version=iss45_version,
                    )
                    db.session.add(ticket_version)

            elif ticket_type == "Connected Payments":
                pos_dll = request.form.get("pos_dll", "").strip()
                eps_dll = request.form.get("eps_dll", "").strip()

                if pos_dll or eps_dll:
                    ticket_version = models.TicketVersion(
                        ticket_id=ticket.id,
                        version=f"POS{pos_dll} EPS{eps_dll}",
                    )
                    db.session.add(ticket_version)

            db.session.commit()

            flash(f"Incident {ticket.ticket_key} created successfully.", "success")
            return redirect(url_for("dashboard"))

        return render_template("ticket_form.html")

    @app.route("/tickets/<int:ticket_id>")
    @login_required
    def ticket_detail(ticket_id):
        ticket = models.Ticket.query.get_or_404(ticket_id)
    
        return render_template("ticket_detail.html", ticket=ticket)

    @app.route("/tickets/<int:ticket_id>/edit", methods=(["GET", "POST"]))
    @login_required
    def edit_ticket(ticket_id):
        ticket = models.Ticket.query.get_or_404(ticket_id)

        if request.method == "POST":
            title = request.form.get("title", "").strip()

            if not title:
                flash("Title is required.", "error")
                return render_template("edit_ticket.html", ticket=ticket)

            ticket.title = title
            ticket.description = request.form.get("description", "").strip()
            ticket.priority = request.form.get("priority", "").strip()

            db.session.commit()

            flash("Ticket updated successfully.", "success")
            return redirect(url_for("ticket_detail", ticket_id=ticket.id))

        return render_template("edit_ticket.html", ticket=ticket)
    
    @app.route("/tickets/<int:ticket_id>/versions/add", methods=["POST"])
    @login_required
    def add_ticket_version(ticket_id):
        ticket = models.Ticket.query.get_or_404(ticket_id)

        if ticket.ticket_type == "ENCOR":
            version = request.form.get("version", "").strip()
            service_pack = request.form.get("service_pack", "").strip()

            if not version:
                flash("Please select a version.", "error")
                return redirect(url_for("ticket_detail", ticket_id=ticket.id))

            ticket_version = models.TicketVersion(
                ticket_id=ticket.id,
                version=version,
                service_pack=None if service_pack in ("", "-") else service_pack,
            )

        elif ticket.ticket_type =="SCO":
            adk_version = request.form.get("adk_version", "").strip()
            tb_version = request.form.get("tb_version", "").strip()

            if not adk_version and not tb_version:
                flash("Enter an ADK or TB version.", "error"),
                return redirect(url_for("ticket_detail", ticket_id=ticket.id))

            ticket_version = models.Ticketversion(
                ticket_id=ticket.id,
                version=f"ADK{adk_version} TB{tb_version}",
            )

        elif ticket.ticket_type == "ISS45":
            version = request.form.get("version", "").strip()

            if version not in ("V7", "V8"):
                flash("Please select V7 or V8.", "error")
                return redirect(url_for("ticket_detail", ticket_id=ticket.id))

            ticket_version = models.TicketVersion(
                ticket_id=ticket.id,
                version=version,
            )

        elif ticket.ticket_type == "Connected Payments":
            pos_dll = request.form.get("pos_dll", "").strip()
            eps_dll = request.form.get("eps_dll", "").strip()

            if not pos_dll and not eps_dll:
                flash("Enter a POS DLL or EPS DLL.", "error")
                return redirect(url_for("ticket_detail", ticket_id=ticket.id))

            ticket_version = models.TicketVersion(
                ticket_id=ticket.id,
                version=f"POS{pos_dll} EPS{eps_dll}",
            )

        else:
            flash("Unsupported incident type.", "error")
            return redirect(url_for("ticket_detail", ticket_id=ticket.id))

        db.session.add(ticket_version)
        db.session.commit()

        flash("Software version added successfully.", "success")
        return redirect(url_for("ticket_detail", ticket_id=ticket.id))
# Tech discussion
    @app.route("/tickets/<int:ticket_id>/comments", methods=["POST"])
    @login_required
    def add_internal_comment(ticket_id):
        ticket=models.Ticket.query.get_or_404(ticket_id)

        comment_text = request.form.get("comment", "").strip()

        if not comment_text:
            flash("Comment cannot be empty.", "error")
            return redirect(url_for("ticket_detail", ticket_id=ticket.id))

        comment = models.InternalComment(
            ticket_id=ticket.id,
            user_id=current_user.id,
            body=comment_text,
        )

        db.session.add(comment)
        db.session.commit()

        flash("Internal comment added.", "success")
        return redirect(url_for("ticket_detail", ticket_id=ticket.id))
# NCR Discussion




    @app.route("/tickets/<int:ticket_id>/versions/<int:version_id>/remove", methods=["POST"])
    @login_required
    def remove_ticket_version(ticket_id, version_id):
        ticket = models.Ticket.query.get_or_404(ticket_id)

        version = models.TicketVersion.query.filter_by(
            id=version_id,
            ticket_id=ticket.id,
        ).first_or_404()

        db.session.delete(version)
        db.session.commit()

        flash("Software version remove.", "success")
        return redirect(url_for("ticket_detail", ticket_id=ticket.id))



    return app