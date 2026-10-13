from getpass import getpass

from app import create_app
from app.extensions import db
from app.models import User


def main():
    app = create_app()

    with app.app_context():
        existing_owner = User.query.filter_by(role="Owner").first()

        if existing_owner:
            print(f"An owner account already exists: {existing_owner.username}")
            print("No account was created.")
            return

        print("Create the intial POSCollective Owner account.")
        print("Your password will not be displayed as you type.")

        username = input("Email address (used to log in): ").strip()
        email = username
        company=input("Company: ").strip()
        full_name = input("Full name: ").strip()

        if not username or not email or not company or not full_name:
            print("Email, company, and full name are required.")
            return

        if User.query.filter_by(username=username).first():
            print("That username is already in use.")
            return

        if User.query.filter_by(email=email).first():
            print("That email address is already in use.")
            return

        password = getpass("Password (minimum 12 characters): ")
        confirmation = getpass("Confirm password: ")

        if len(password) < 12:
            print("Password must be at least 12 characters long.")
            return

        if not any(c.islower() for c in password):
            print("Password must include at least one lowercase letter.")
            return

        if not any(c.isupper() for c in password):
            print("Password must include at least one upppercase letter.")
            return

        if not any(c.isdigit() for c in password):
            print("Password must include at least one number.")
            return
        
        if not any(not c.isalnum() for c in password):
            print("Password must include at least one special character.")

        if password != confirmation:
            print("Passwords do not match.")
            return

        owner = User(
            username=username,
            email=email,
            company=company,
            full_name=full_name,
            role="Owner",
            is_active=True,
        )
        owner.set_password(password)

        db.session.add(owner)
        db.session.commit()

        print(f"Owner account '{username}' created successfully.")


if __name__ == "__main__":
    main()