from cs50 import SQL

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

name_id = 6
cash = db.execute("SELECT cash FROM users WHERE id=:name_id", name_id = name_id)


print(cash)