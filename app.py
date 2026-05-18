from datetime import date
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db

app = Flask(__name__)
app.secret_key = "dev-secret-change-in-production"

with app.app_context():
    init_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")
        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters.")

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password))
            )
            db.commit()
        except Exception:
            return render_template("register.html", error="An account with that email already exists.")
        finally:
            db.close()

        return render_template("register.html", success=True)

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid email or password.")

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("dashboard"))

    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    start_date  = request.args.get("start_date", "").strip()
    end_date    = request.args.get("end_date", "").strip()
    filtered    = False
    filter_error = None

    if start_date or end_date:
        try:
            if start_date:
                date.fromisoformat(start_date)
            if end_date:
                date.fromisoformat(end_date)
            if not start_date or not end_date:
                filter_error = "Please provide both a start and end date."
            elif start_date > end_date:
                filter_error = "Start date must be on or before the end date."
            else:
                filtered = True
        except ValueError:
            filter_error = "Invalid date format."

    db = get_db()

    if filtered:
        expenses = db.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ?"
            " ORDER BY date DESC, id DESC",
            (session["user_id"], start_date, end_date)
        ).fetchall()
        range_total   = sum(e["amount"] for e in expenses)
        monthly_total = None
        all_time_total = None
    else:
        expenses = db.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC, id DESC",
            (session["user_id"],)
        ).fetchall()
        this_month    = date.today().strftime("%Y-%m")
        monthly_total = sum(e["amount"] for e in expenses if e["date"].startswith(this_month))
        all_time_total = sum(e["amount"] for e in expenses)
        range_total   = None

    db.close()

    return render_template(
        "dashboard.html",
        expenses=expenses,
        monthly_total=monthly_total,
        all_time_total=all_time_total,
        range_total=range_total,
        filtered=filtered,
        start_date=start_date,
        end_date=end_date,
        filter_error=filter_error,
    )


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    expense_count = db.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (session["user_id"],)
    ).fetchone()[0]

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_info":
            name  = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()

            if not name or not email:
                db.close()
                return render_template("profile.html", user=user, expense_count=expense_count,
                                       info_error="Name and email are required.")

            try:
                db.execute("UPDATE users SET name=?, email=? WHERE id=?",
                           (name, email, session["user_id"]))
                db.commit()
                session["user_name"] = name
            except Exception:
                db.close()
                return render_template("profile.html", user=user, expense_count=expense_count,
                                       info_error="That email is already in use.")

            user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
            db.close()
            return render_template("profile.html", user=user, expense_count=expense_count,
                                   info_success=True)

        elif action == "change_password":
            current = request.form.get("current_password", "")
            new_pw  = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")

            if not check_password_hash(user["password_hash"], current):
                db.close()
                return render_template("profile.html", user=user, expense_count=expense_count,
                                       pw_error="Current password is incorrect.")

            if len(new_pw) < 8:
                db.close()
                return render_template("profile.html", user=user, expense_count=expense_count,
                                       pw_error="New password must be at least 8 characters.")

            if new_pw != confirm:
                db.close()
                return render_template("profile.html", user=user, expense_count=expense_count,
                                       pw_error="Passwords don't match.")

            db.execute("UPDATE users SET password_hash=? WHERE id=?",
                       (generate_password_hash(new_pw), session["user_id"]))
            db.commit()
            db.close()
            return render_template("profile.html", user=user, expense_count=expense_count,
                                   pw_success=True)

    db.close()
    return render_template("profile.html", user=user, expense_count=expense_count)


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title    = request.form.get("title", "").strip()
        amount   = request.form.get("amount", "").strip()
        category = request.form.get("category", "Other")
        exp_date = request.form.get("date", "").strip()

        if not title or not amount or not exp_date:
            return render_template("add_expense.html", error="All fields are required.")

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return render_template("add_expense.html", error="Enter a valid positive amount.")

        db = get_db()
        db.execute(
            "INSERT INTO expenses (user_id, title, amount, category, date) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], title, amount, category, exp_date)
        )
        db.commit()
        db.close()
        return redirect(url_for("dashboard"))

    return render_template("add_expense.html", today=date.today().isoformat())


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    expense = db.execute(
        "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    ).fetchone()

    if expense is None:
        db.close()
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        title    = request.form.get("title", "").strip()
        amount   = request.form.get("amount", "").strip()
        category = request.form.get("category", "Other")
        exp_date = request.form.get("date", "").strip()

        if not title or not amount or not exp_date:
            db.close()
            return render_template("edit_expense.html", expense=expense, error="All fields are required.")

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            db.close()
            return render_template("edit_expense.html", expense=expense, error="Enter a valid positive amount.")

        db.execute(
            "UPDATE expenses SET title=?, amount=?, category=?, date=? WHERE id=? AND user_id=?",
            (title, amount, category, exp_date, id, session["user_id"])
        )
        db.commit()
        db.close()
        return redirect(url_for("dashboard"))

    db.close()
    return render_template("edit_expense.html", expense=expense)


@app.route("/expenses/<int:id>/delete", methods=["GET", "POST"])
def delete_expense(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    expense = db.execute(
        "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    ).fetchone()

    if expense is None:
        db.close()
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        db.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (id, session["user_id"]))
        db.commit()
        db.close()
        return redirect(url_for("dashboard"))

    db.close()
    return render_template("delete_expense.html", expense=expense)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
