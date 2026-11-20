# Builds the Flask app

# The settings (passwords and keys) come from a .env file
# Copy .env.example to .env and fill it in.

import os

from dotenv import load_dotenv
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import URL

# The settings that must be in .env.
REQUIRED_SETTINGS = [
    "SECRET_KEY",
    "DB_HOST",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "FIELD_ENCRYPTION_KEY",
]

def database_address():
    #The address SQLAlchemy uses to reach MySQL: mysql+pymysql://user:password@host:port/database.

    return URL.create(
        "mysql+pymysql",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        database=os.environ["DB_NAME"],
        query={"charset": "utf8mb4"},
    )


def create_app():
    # read .env into the environment
    load_dotenv()
    missing = []
    for setting in REQUIRED_SETTINGS:
        if not os.environ.get(setting):
            missing.append(setting)
    if missing:
        raise RuntimeError("Set these in .env (copy .env.example to start): " + ", ".join(missing))

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.config["FIELD_ENCRYPTION_KEY"] = os.environ["FIELD_ENCRYPTION_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"] = database_address()
    # Store every time in UTC.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"init_command": "SET time_zone = '+00:00'"}}
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"

    # Every form that uses POST must include {{ csrf_token() }}
    # This stops other websites from submitting forms to our site on a logged-in user's behalf
    CSRFProtect(app)

    # app imports
    from app import account, admin, auth, common, history, stocks, trade, transfer
    from app.models import db

    db.init_app(app)
    auth.login_manager.init_app(app)
    auth.bcrypt.init_app(app)

    with app.app_context():
        # create any tables that don't exist yet
        db.create_all()
        # The first administrator, from .env
        admin.create_first_admin(os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD"))

    # Register Blueprints
    app.register_blueprint(auth.bp)
    app.register_blueprint(account.bp)
    app.register_blueprint(stocks.bp)
    app.register_blueprint(trade.bp)
    app.register_blueprint(transfer.bp)
    app.register_blueprint(history.bp)
    app.register_blueprint(admin.bp)

    # Lets templates write
    app.add_template_filter(common.money, "money")
    app.add_template_filter(common.shares, "shares")
    # Lets templates write
    app.add_template_global(common.change, "change")
    app.add_template_global(common.percent_change, "percent_change")

    return app
