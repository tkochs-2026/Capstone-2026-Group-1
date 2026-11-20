#The Transfer Funds page. 
    #Customers only
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth import customer_required
from app.common import (UserError, decrypt, encrypt, get_portfolio, list_portfolios, money,
                        now_for_database, today)
from app.models import BankAccount, History, Transfer, db, mask

bp = Blueprint("transfer", __name__)

SUPPORT_EMAIL = "support@example.com"
SUPPORT_HOURS = "Monday–Friday, 9:00 AM–5:00 PM Eastern time"


# --- Looking things up -------------------------------------------------------------------------------

def list_bank_accounts(user_id):
    #The customer's bank accounts
    accounts = (
        BankAccount.query
        .filter_by(user_id=user_id, is_active=True)
        .order_by(BankAccount.created_at, BankAccount.bank_account_id)
        .all()
    )
    result = []
    for account in accounts:
        result.append({
            "bank_account_id": account.bank_account_id,
            "bank_name": account.bank_name,
            "nickname": account.nickname,
            "masked_account_number": mask(decrypt(account.account_number)),
        })
    return result


def menu_labels(names_and_ids, masked_numbers):
    #The names to show in the From and To menus, by id
    name_count = {}
    for name, _ in names_and_ids:
        name_count[name] = name_count.get(name, 0) + 1

    labels = {}
    for name, account_id in names_and_ids:
        if name_count[name] == 1:
            labels[account_id] = name
        else:
            labels[account_id] = name + " " + masked_numbers[account_id]
    return labels


def show_transfer_page():
    banks = list_bank_accounts(current_user.user_id)
    portfolios = list_portfolios(current_user.user_id)

    bank_names = []
    bank_numbers = {}
    for bank in banks:
        bank_names.append((bank["nickname"], bank["bank_account_id"]))
        bank_numbers[bank["bank_account_id"]] = bank["masked_account_number"]

    portfolio_names = []
    portfolio_numbers = {}
    for portfolio in portfolios:
        portfolio_names.append((portfolio.account_name, portfolio.portfolio_id))
        portfolio_numbers[portfolio.portfolio_id] = portfolio.masked_account_number

    return render_template(
        "transfer/transfer.html",
        banks=banks,
        portfolios=portfolios,
        bank_labels=menu_labels(bank_names, bank_numbers),
        portfolio_labels=menu_labels(portfolio_names, portfolio_numbers),
        today=today(),
        support_email=SUPPORT_EMAIL,
        support_hours=SUPPORT_HOURS,
    )


def check_bank_account(bank_account_id):
    #404 unless this is one of the customer's bank accounts and it hasn't been removed
    query = BankAccount.query.filter_by(bank_account_id=bank_account_id,
                                        user_id=current_user.user_id, is_active=True)
    query.first_or_404()


def record_transfer(kind, amount, from_portfolio_id, to_portfolio_id, bank_account_id):
    #Add the Transfer row, and a History row for each portfolio it touched
    now = now_for_database()
    transfer = Transfer(transfer_type=kind, amount=amount, from_portfolio_id=from_portfolio_id,
                        to_portfolio_id=to_portfolio_id, bank_account_id=bank_account_id,
                        transfer_date=today(), created_at=now)
    db.session.add(transfer)

    if kind == "Deposit":
        db.session.add(History(portfolio_id=to_portfolio_id, transfer=transfer,
                               action="Deposit", timestamp=now))
    elif kind == "Withdrawal":
        db.session.add(History(portfolio_id=from_portfolio_id, transfer=transfer,
                               action="Withdrawal", timestamp=now))
    else:
        db.session.add(History(portfolio_id=from_portfolio_id, transfer=transfer,
                               action="Transfer out", timestamp=now))
        db.session.add(History(portfolio_id=to_portfolio_id, transfer=transfer,
                               action="Transfer in", timestamp=now))


#Three kinds of transfer. Each returns the message to show, or raises UserError

def deposit(bank_account_id, portfolio_id, amount):
    check_bank_account(bank_account_id)
    portfolio = get_portfolio(current_user.user_id, portfolio_id)
    portfolio.cash_balance = portfolio.cash_balance + amount
    record_transfer("Deposit", amount, None, portfolio_id, bank_account_id)
    db.session.commit()
    return (f"Deposited {money(amount)} into {portfolio.account_name}. "
            f"New cash balance: {money(portfolio.cash_balance)}.")


def withdraw(portfolio_id, bank_account_id, amount):
    check_bank_account(bank_account_id)
    portfolio = get_portfolio(current_user.user_id, portfolio_id)
    if amount > portfolio.cash_balance:
        raise UserError("Insufficient funds")

    portfolio.cash_balance = portfolio.cash_balance - amount
    record_transfer("Withdrawal", amount, portfolio_id, None, bank_account_id)
    db.session.commit()
    return (f"Withdrew {money(amount)} from {portfolio.account_name}. "
            f"New cash balance: {money(portfolio.cash_balance)}.")


def move_between_portfolios(from_id, to_id, amount):
    if from_id == to_id:
        raise UserError("Choose a different account to move the money to.", "to_account")

    source = get_portfolio(current_user.user_id, from_id)
    target = get_portfolio(current_user.user_id, to_id)

    if amount > source.cash_balance:
        raise UserError("Insufficient funds")

    source.cash_balance = source.cash_balance - amount
    target.cash_balance = target.cash_balance + amount
    record_transfer("Internal", amount, from_id, to_id, None)
    db.session.commit()
    return (f"Moved {money(amount)} from {source.account_name} "
            f"(new cash balance {money(source.cash_balance)}) to {target.account_name} "
            f"(new cash balance {money(target.cash_balance)}).")


#Pages

def read_menu_choice(value):
    #The From and To menus send text like "bank:12" or "portfolio:3".
        #Returns the kind ("bank" or "portfolio") and the id (12), or (None, None) if nothing valid
        #was chosen.
    
    kind, _, id_text = (value or "").partition(":")
    if kind not in ["bank", "portfolio"] or not id_text.isdigit():
        return None, None
    return kind, int(id_text)


@bp.get("/transfer")
@customer_required
def transfer_page():
    return show_transfer_page()


@bp.post("/transfer")
@customer_required
def submit_transfer():
    from_kind, from_id = read_menu_choice(request.form.get("from_account"))
    to_kind, to_id = read_menu_choice(request.form.get("to_account"))
    amount = Decimal(request.form.get("amount", ""))
    try:
        if amount <= 0:
            raise UserError("Enter an amount greater than 0.")
        if from_kind == "bank" and to_kind == "bank":
            raise UserError("Money can't move from one bank account to another. "
                            "Choose a portfolio for From or To.")

        if from_kind == "bank":
            message = deposit(from_id, to_id, amount)
        elif to_kind == "bank":
            message = withdraw(from_id, to_id, amount)
        else:
            message = move_between_portfolios(from_id, to_id, amount)
    except UserError as error:
        #undo any change
        db.session.rollback()
        flash(error.message, "error")
        return redirect(url_for("transfer.transfer_page"))

    flash(message, "success")
    return redirect(url_for("transfer.transfer_page"))


@bp.post("/transfer/bank-accounts")
@customer_required
def add_bank_account():
    form = request.form
    bank_name = form.get("bank_name", "").strip()
    account_number = form.get("account_number", "").strip()
    routing_number = form.get("routing_number", "").strip()
    nickname = form.get("nickname", "").strip()

    account = BankAccount(user_id=current_user.user_id, bank_name=bank_name, nickname=nickname,
                          account_number=encrypt(account_number), routing_number=routing_number)
    db.session.add(account)
    db.session.commit()
    flash(f'Bank account "{nickname}" ({mask(account_number)}) linked.', "success")
    return redirect(url_for("transfer.transfer_page"))


@bp.post("/transfer/bank-accounts/<int:bank_account_id>/remove")
@customer_required
def remove_bank_account(bank_account_id):
    #Hide a bank account. It isn't deleted, so old transfers can still show it
    query = BankAccount.query.filter_by(bank_account_id=bank_account_id,
                                        user_id=current_user.user_id, is_active=True)
    account = query.first_or_404()
    account.is_active = False
    db.session.commit()
    flash("Bank account removed. Past transfers still show it.", "success")
    return redirect(url_for("transfer.transfer_page"))
