import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required

from app.extensions import db, migrate, login_manager
from app import models
from app.models import Ticket

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

    @app.route("/")
    def index():
        # if not login_required:
        #     return redirect(url_for("login"))
        return redirect(url_for("dashboard"))
        # return "POSCollective is running."

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            user = models.User.query.filter_by(username=username).first()

            if user and user.is_active and user.check_password(password):
                login_user(user)
                return redirect(url_for("dashboard"))

        return render_template("login.html")

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

        query = models.Ticket.query

        if status in ("Open", "Closed"):
            query = query.filter_by(status=status)

        tickets = query.all()

        return render_template(
            "dashboard.html",
            tickets=tickets,
            current_status=status,
        )
        # return "POSCollective dashboard - login successful."

    return app
