#The Stocks pages: a list of every stock (with a search box), and one stock's own page.

from flask import Blueprint, render_template, request
from sqlalchemy import or_

from app.common import today
from app.models import Issuer, StockPrice

bp = Blueprint("stocks", __name__)

SEARCH_MAX_LENGTH = 100


def listed_stocks():
    #A query for every listed stock, in symbol order
    return Issuer.query.filter_by(is_listed=True).order_by(Issuer.symbol)


def show_stock_list(search, error=None, status_code=200):
    #The Stocks page: every listed stock, or only the ones matching `search`
    query = listed_stocks()
    if search and error is None:
        #In LIKE, % and _ mean "anything". We put | in front of them so they only match themselves
        escaped = search.replace("|", "||").replace("%", "|%").replace("_", "|_")
        #Contains the search text anywhere
        pattern = "%" + escaped + "%"
        query = query.filter(or_(Issuer.symbol.like(pattern, escape="|"),
                                 Issuer.company_name.like(pattern, escape="|")))
    stocks = query.all()

    html = render_template("stocks/search.html", query=search, stocks=stocks, error=error)
    return html, status_code


@bp.get("/stocks")
def search_page():
    search = request.args.get("q", "").strip()
    if len(search) > SEARCH_MAX_LENGTH:
        return show_stock_list(search, f"Search for {SEARCH_MAX_LENGTH} characters or fewer.")
    return show_stock_list(search)


@bp.get("/stocks/<symbol>")
def detail_page(symbol):
    stock = listed_stocks().filter_by(symbol=symbol.strip().upper()).first()
    if stock is None:
        return show_stock_list("", "Symbol not found", 404)

    #Today's opening price, if prices have moved today.
    todays_prices = StockPrice.query.filter_by(issuer_id=stock.issuer_id, price_date=today()).first()
    open_price = None
    if todays_prices is not None:
        open_price = todays_prices.open_price

    return render_template("stocks/detail.html", stock=stock, open_price=open_price)
