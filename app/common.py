"""Small helpers that several pages use.

    Time         now_utc(), now_for_database(), today()
    Money        to_cents(), percent(), money(), shares(), change() and percent_change() for showing numbers
    Encryption   encrypt(), decrypt()
    Portfolios   list_portfolios(), get_portfolio()
"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from flask import current_app
from markupsafe import Markup

from app.models import Portfolio

#Market Runs off of EST
EASTERN = ZoneInfo("America/New_York")

ONE_CENT = Decimal("0.01")


class UserError(Exception):
    #A problem with what the user typed, to show them on the page

    def __init__(self, message, field="form"):
        super().__init__(message)
        self.message = message
        self.field = field


# --- Time --------------------------------------------------------------------------------------------

def now_utc():
    #The current date and time in UTC
    return datetime.now(timezone.utc)


def now_for_database():
    #The current time as we store it in the database: UTC, without the time zone attached
    return now_utc().replace(tzinfo=None)


def today():
    #Today's date in Eastern time.
    return now_utc().astimezone(EASTERN).date()


# --- Money -------------------------------------------------------------------------------------------

def to_cents(amount):
    #Round to the nearest cent
    return amount.quantize(ONE_CENT, rounding=ROUND_HALF_UP)


def percent(part, whole):
    #Rounds to 0.00%
    if whole <= 0:
        return Decimal("0.00")
    result = part / whole * 100
    return result.quantize(ONE_CENT, rounding=ROUND_HALF_UP)


def money(amount):
    #Set to money formate $0.00 with commas
    if amount is None:
        return "—"
    cents = to_cents(Decimal(amount))
    if cents < 0:
        return f"-${abs(cents):,.2f}"
    return f"${cents:,.2f}"


def shares(quantity):
    #Show a number of shares without extra zeros
    if quantity is None:
        return "—"
    text = f"{Decimal(quantity):,.6f}"
    text = text.rstrip("0").rstrip(".")
    if text == "" or text == "-0":
        return "0"
    return text


def colour_for(number):
    #Bootstrap's text colour for a change: green when up, red when down
    if number > 0:
        return "text-success"
    if number < 0:
        return "text-danger"
    return ""


def change(amount, percent=None):
    #Show a change like "+$12.50 (+1.25%)" in green, or "-$3.00 (-0.50%)" in red

    sign = "+" if amount > 0 else ""
    text = sign + money(amount)
    if percent is not None:
        text += f" ({sign}{percent}%)"
    return Markup(f'<span class="{colour_for(amount)}">{text}</span>')


def percent_change(percent):
    #Show a percentage on its own, like "+1.25%" in green. Used in templates as {{ percent_change(p) }}
    sign = "+" if percent > 0 else ""
    return Markup(f'<span class="{colour_for(percent)}">{sign}{percent}%</span>')


#Encryption: SSNs and bank account numbers

def encrypt(plain_text):
    key = current_app.config["FIELD_ENCRYPTION_KEY"]
    return Fernet(key).encrypt(plain_text.encode()).decode()


def decrypt(encrypted_text):
    key = current_app.config["FIELD_ENCRYPTION_KEY"]
    return Fernet(key).decrypt(encrypted_text.encode()).decode()


#Portfolios
def list_portfolios(user_id):
    #All of a customer's portfolios, oldest first
    query = Portfolio.query.filter_by(user_id=user_id)
    return query.order_by(Portfolio.created_at, Portfolio.portfolio_id).all()


def get_portfolio(user_id, portfolio_id):
    #One of the customer's portfolios. Shows the 404 page if it isn't theirs
    query = Portfolio.query.filter_by(portfolio_id=portfolio_id, user_id=user_id)
    return query.first_or_404()


