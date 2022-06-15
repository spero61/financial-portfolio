import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute("SELECT * FROM stocks WHERE user_id = ?", session["user_id"])
    total = 0
    for stock in stocks:
        result = lookup(stock["symbol"])
        current_price = result["price"]
        stock["price"] = current_price
        total += (current_price * stock["shares"])

    users = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    balance = users[0]["cash"]
    total += balance
    return render_template("index.html", stocks=stocks, balance=balance, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        id = session["user_id"]
        # Ensure the number of shares was submitted
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Invalid Shares", 400)

        if shares < 1:
            return apology("Shares cannot be less than 1", 400)

        # check if the symbol submitted is valid
        result = lookup(request.form.get("symbol"))
        if result:
            # Query database for user id to check his / her balance
            rows = db.execute("SELECT cash FROM users WHERE id = ?", id)
            if len(rows) != 1:
                return apology("cannot find your balance", 403)

            # current stock price that a user want to buy
            price = result["price"]
            # balance of the current user
            balance = float(rows[0]["cash"])

            # check if the user can afford
            if (price * shares) <= balance:
                balance -= (price * shares)

                # proceed the "buy" transaction
                db.execute("UPDATE users SET cash = ? WHERE id = ?", balance, id)

                # https://www.programiz.com/python-programming/datetime/current-datetime
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.execute("INSERT INTO transactions (user_id, symbol, name, price, shares, transaction_time) VALUES (?, ?, ?, ?, ?, ?)",
                           id, result["symbol"], result["name"], result["price"], shares, current_time)
                rows = db.execute("SELECT symbol, shares FROM stocks WHERE user_id = ? AND symbol = ?", id, result["symbol"])

                # if this user already has had this stock
                if len(rows) != 0:
                    previous_shares = rows[0]["shares"]
                    updated_shares = previous_shares + shares
                    db.execute("UPDATE stocks SET shares = ? WHERE user_id = ? AND symbol = ?",
                               updated_shares, id, result["symbol"])
                else:
                    db.execute("INSERT INTO stocks (user_id, symbol, name, shares) VALUES (?, ?, ?, ?)",
                               id, result["symbol"], result["name"], shares)

            else:
                return apology("You have not enough money", 403)
            return redirect("/")

        else:
            return apology("Invalid Symbol", 400)

    # User reached route via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)
        username = username.lower()

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

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


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        result = lookup(request.form.get("symbol"))
        if result:
            return render_template("quote-result.html", result=result)
        else:
            return apology("Invalid Symbol", 400)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        # Validation check
        # check if username field is left blank
        if not request.form.get("username"):
            return apology("must provide username", 400)
        username = request.form.get("username").lower()
        # check if password field is left blank
        if not request.form.get("password"):
            return apology("must provide password", 400)
        # check if password and confirmation do not match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password confirmation failed", 400)

        # check if the username is already taken
        rows = db.execute("SELECT username FROM users")
        for row in rows:
            if row["username"] == username:
                return apology("username is already taken", 400)

        # generate hashed password
        # https://werkzeug.palletsprojects.com/en/2.0.x/utils/#module-werkzeug.security

        hash = generate_password_hash(request.form.get("password"))
        id = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)

        # log in
        session.clear()
        session["user_id"] = id
        return redirect("/")

    # When requested via GET, display registration form
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # sanity check
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("must provide symbol", 403)

        try:
            shares_to_sell = int(request.form.get("shares"))
        except ValueError:
            return apology("Invalid Shares", 400)

        if not shares_to_sell:
            return apology("must provide shares", 403)
        elif shares_to_sell < 1:
            return apology("the number of shares cannot be less than 1", 400)

        id = session["user_id"]

        rows = db.execute("SELECT shares FROM stocks WHERE user_id = ? AND symbol = ?", id, symbol)
        if len(rows) != 1:
            return apology("You don't have that stock!", 403)

        shares_have = rows[0]["shares"]
        if shares_have - shares_to_sell < 0:
            return apology("You don't have enough stocks to sell that much", 400)

        # proceed the "sell" transaction
        result = lookup(symbol)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("INSERT INTO transactions (user_id, symbol, name, price, shares, transaction_time) VALUES (?, ?, ?, ?, ?, ?)",
                   id, result["symbol"], result["name"], result["price"], -shares_to_sell, current_time)
        db.execute("UPDATE stocks SET shares = ? WHERE user_id = ? AND symbol = ?",
                   shares_have - shares_to_sell, id, result["symbol"])

        users = db.execute("SELECT cash FROM users WHERE id = ?", id)
        previous_balance = users[0]["cash"]
        print(previous_balance)
        updated_balance = previous_balance + (result["price"] * shares_to_sell)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_balance, id)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        stocks = db.execute("SELECT * FROM stocks WHERE user_id = ?", session["user_id"])
        return render_template("sell.html", stocks=stocks)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """View Profile, a user can change password"""
    if request.method == "POST":
        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database from users
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid password", 403)

        if not request.form.get("new-password") or not request.form.get("new-password-confirmation"):
            return apology("must provide new password", 403)

        if request.form.get("new-password") != request.form.get("new-password-confirmation"):
            return apology("new password confirmation failed", 403)

        hash = generate_password_hash(request.form.get("new-password"))
        db.execute("UPDATE users SET hash = ? WHERE id = ?", hash, session["user_id"])

        return redirect("/")

    else:
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        username = rows[0]["username"]
        return render_template("profile.html", username=username)
