#The History page
    #Customers see the transactions in all of their own portfolios.
    #Administrators see every customer's transactions.

from datetime import timezone

from flask import Blueprint, render_template
from flask_login import current_user

from app.common import EASTERN, decrypt, money, shares
from app.models import History, Portfolio, mask

bp = Blueprint("history", __name__)

def to_eastern_time(stored_time):
    #Turn a time read from the database (UTC) into Eastern time, for showing on a page
    utc_time = stored_time.replace(tzinfo=timezone.utc)
    return utc_time.astimezone(EASTERN)


def describe(history_row):
    #One line of the History table, as a dictionary.

    portfolio = history_row.portfolio
    line = {
        "at": to_eastern_time(history_row.timestamp),
        "type": history_row.action,
        "symbol": None,
        "quantity": None,
        "price": None,
        "customer": portfolio.owner.name,
        "account": portfolio.account_name + " " + portfolio.masked_account_number,
    }

    trade = history_row.trade
    if trade is not None:
        symbol = trade.issuer.symbol
        how_many = shares(trade.quantity)
        price = money(trade.price_per_share)
        line["symbol"] = symbol
        line["quantity"] = trade.quantity
        line["price"] = trade.price_per_share
        line["status"] = trade.status
        if trade.type == "Buy":
            line["description"] = f"Bought {how_many} {symbol} @ {price}"
            line["amount"] = -trade.total_amount
        else:
            line["description"] = f"Sold {how_many} {symbol} @ {price}"
            line["amount"] = trade.total_amount
        return line

    transfer = history_row.transfer
    line["status"] = transfer.status
    action = history_row.action
    if action == "Deposit" or action == "Withdrawal":
        #Still shown even if it was removed later
        bank = transfer.bank_account
        bank_name = bank.nickname + " " + mask(decrypt(bank.account_number))
        if action == "Deposit":
            line["description"] = "Deposit from " + bank_name
            line["amount"] = transfer.amount
        else:
            line["description"] = "Withdrawal to " + bank_name
            line["amount"] = -transfer.amount
    elif action == "Transfer out":
        other = transfer.to_portfolio
        line["description"] = "Transfer to " + other.account_name + " " + other.masked_account_number
        line["amount"] = -transfer.amount
    else:  
        #"Transfer in"
        other = transfer.from_portfolio
        line["description"] = "Transfer from " + other.account_name + " " + other.masked_account_number
        line["amount"] = transfer.amount
    return line


@bp.get("/history")
def history_page():
    query = History.query
    if not current_user.is_admin:
        #Only the rows for this customer's own portfolios
        query = query.join(Portfolio, Portfolio.portfolio_id == History.portfolio_id)
        query = query.filter(Portfolio.user_id == current_user.user_id)
    #newest first    
    query = query.order_by(History.timestamp.desc(), History.history_id.desc())

    lines = []
    for history_row in query.all():
        lines.append(describe(history_row))
    return render_template("history/history.html", lines=lines, is_admin=current_user.is_admin)
