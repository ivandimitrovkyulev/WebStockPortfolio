import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    name_id = session["user_id"]
    transactions = db.execute("SELECT symbol, SUM(shares) AS shares FROM transactions WHERE id=:name_id GROUP BY symbol", name_id = name_id)
    portfolio = []
    shares_value = 0

    for transaction in transactions:
        if transaction['shares'] == 0:
            continue
        company_info = lookup(transaction['symbol'])
        transaction['name'] = company_info['name']
        transaction['price'] = usd(company_info['price'])
        total = float(company_info['price']) * float(transaction['shares'])
        transaction['total'] = usd(total)
        portfolio.append(transaction)
        shares_value += total

    buffer = db.execute("SELECT cash FROM users WHERE id=:name_id", name_id = name_id)
    balance = buffer[0]['cash']
    total_balance = shares_value + balance

    return render_template("index.html", portfolio = portfolio, balance = usd(balance), total = usd(total_balance))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        name_id = session["user_id"]
        company_info = lookup(symbol)

        if symbol == "":
            return apology("Must provide a symbol", 400)

        elif not company_info:
            return apology("no such symbol", 400)

        elif shares == "":
            return apology("must provide shares", 400)

        elif int(shares) <= 0:
            return apology("shares must be > 0", 400)

        else:
            price = company_info["price"]
            customer_info = db.execute("SELECT cash FROM users WHERE id=:name_id", name_id = name_id)
            available_cash = customer_info[0]["cash"]

            if available_cash >= float(shares) * float(price):
                db.execute("INSERT INTO transactions (id, symbol, shares, price) VALUES (:id, :symbol, :shares, :price)",
                            id = name_id, symbol = symbol.upper(), shares = shares, price = price)
                available_cash -= float(price) * float(shares)
                db.execute("UPDATE users SET cash=:cash WHERE id=:name_id", cash = available_cash, name_id = name_id)

            else:
                return apology("not enough funds", 403)


        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    name_id = session["user_id"]
    transactions = db.execute("SELECT symbol, shares, price, date FROM transactions WHERE id=:name_id", name_id = name_id)

    return render_template("history.html", transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        user_name = request.form.get("username")
        password = request.form.get("password")
        password_confirmation = request.form.get("confirmation")

        names = db.execute("SELECT username FROM users WHERE username = :value", value = user_name)

        if user_name == "":
            return apology("must provide a username", 400)

        elif len(names) != 0:
            return apology("username already exists", 400)

        if password == "" or password_confirmation == "":
            return apology("must provide a password", 400)

        elif password == password_confirmation:
            password_hash = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES (:val_1, :val_2)",
                        val_1 = user_name, val_2 = password_hash)

            return redirect("/")

        else:
            return apology("password does not match", 400)

    else:
        return render_template("register.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/top-up", methods=["GET", "POST"])
@login_required
def top_up():
    """Allows user to add money to account"""

    if request.method == "POST":
        name_id = session["user_id"]
        amount = request.form.get("top-up")

        balance = db.execute("SELECT cash FROM users WHERE id=:name_id", name_id = name_id)
        new_balance = float(balance[0]["cash"]) + float(amount)

        db.execute("UPDATE users SET cash=:cash WHERE id=:name_id", cash = new_balance, name_id = name_id)

        return redirect("/")

    return render_template("top-up.html")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        share = request.form.get("symbol")
        company_info = lookup(share)

        if share == "":
            return apology("Must provide a symbol", 400)
        elif not company_info:
            return apology("No such symbol", 400)
        else:
            return render_template("quoted.html", company_info=company_info)

        return render_template("quote.html")

    else:
        return render_template("quote.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    name_id = session["user_id"]
    symbols = db.execute("SELECT DISTINCT symbol FROM transactions WHERE id=:name_id ORDER BY symbol", name_id = name_id)

    if request.method == "POST":
        shares = request.form.get("shares")
        symbol = request.form.get("symbol")
        total_shares = db.execute("SELECT shares FROM (SELECT symbol, SUM(shares) AS shares FROM transactions WHERE id=:name_id GROUP BY symbol) WHERE symbol=:symbol", name_id=name_id, symbol=symbol)

        if symbol == "":
            return apology("must provide a symbol", 400)

        elif not shares:
            return apology("must provide shares", 400)
        elif int(shares) <= 0:
            return apology("shares must be > 0", 400)
        elif int(shares) > total_shares[0]['shares']:
            return apology(f"you only have {total_shares[0]['shares']} shares", 403)

        company_info = lookup(symbol)
        balance = db.execute("SELECT cash FROM users WHERE id=:name_id", name_id = name_id)
        profit = float(company_info["price"]) * int(shares)
        price = company_info['price']
        new_balance = balance[0]['cash'] + profit

        db.execute("UPDATE users SET cash=:cash WHERE id=:name_id", cash = new_balance, name_id = name_id)

        db.execute("INSERT INTO transactions (id, symbol, shares, price) VALUES (:id, :symbol, :shares, :price)",
                            id = name_id, symbol = symbol.upper(), shares = -int(shares), price = price)

        return redirect("/")

    else:
        return render_template("sell.html", symbols = symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
