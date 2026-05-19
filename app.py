import calendar
import csv
import hashlib
import io
import os
import secrets
from datetime import date, datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, Response, flash
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db

app = Flask(__name__)
app.secret_key = "dev-secret-change-in-production"

app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAIL_SERVER=os.environ.get("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.environ.get("MAIL_PORT", 587)),
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.environ.get("MAIL_DEFAULT_SENDER") or os.environ.get("MAIL_USERNAME"),
)
mail = Mail(app)

with app.app_context():
    init_db()


# ------------------------------------------------------------------ #
# Recurring expense helpers                                           #
# ------------------------------------------------------------------ #

FREQUENCIES = ("weekly", "monthly", "yearly")


def _advance_date(d, frequency):
    if frequency == "weekly":
        return d + timedelta(weeks=1)
    if frequency == "monthly":
        month = d.month + 1
        year  = d.year
        if month > 12:
            month, year = 1, year + 1
        return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))
    # yearly
    year = d.year + 1
    return date(year, d.month, min(d.day, calendar.monthrange(year, d.month)[1]))


def generate_due_recurring(db, user_id):
    today = date.today()
    due = db.execute(
        "SELECT * FROM recurring_expenses WHERE user_id = ? AND next_due <= ?",
        (user_id, today.isoformat())
    ).fetchall()
    for r in due:
        next_due = date.fromisoformat(r["next_due"])
        while next_due <= today:
            db.execute(
                "INSERT INTO expenses (user_id, title, amount, category, date) VALUES (?, ?, ?, ?, ?)",
                (user_id, r["title"], r["amount"], r["category"], next_due.isoformat())
            )
            next_due = _advance_date(next_due, r["frequency"])
        db.execute(
            "UPDATE recurring_expenses SET next_due = ? WHERE id = ?",
            (next_due.isoformat(), r["id"])
        )
    if due:
        db.commit()


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

        session.permanent = bool(request.form.get("remember"))
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        db = get_db()
        user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()

        if user:
            db.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user["id"],))
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expires_at = datetime.utcnow() + timedelta(hours=1)
            db.execute(
                "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
                (user["id"], token_hash, expires_at.isoformat())
            )
            db.commit()
            reset_url = url_for("reset_password", token=token, _external=True)
            _send_reset_email(email, reset_url)

        db.close()
        return render_template("forgot_password.html", sent=True)

    return render_template("forgot_password.html")


def _send_reset_email(to_email, reset_url):
    if not app.config.get("MAIL_USERNAME"):
        print(f"\n[DEV] Password reset link for {to_email}:\n{reset_url}\n")
        return
    try:
        msg = Message(
            subject="Reset your Spendly password",
            recipients=[to_email],
            html=(
                "<p>Hi,</p>"
                "<p>Click the link below to reset your Spendly password. "
                "This link expires in 1 hour.</p>"
                f'<p><a href="{reset_url}">{reset_url}</a></p>'
                "<p>If you didn't request this, you can safely ignore this email.</p>"
                "<p>— Spendly</p>"
            )
        )
        mail.send(msg)
    except Exception as e:
        print(f"[MAIL ERROR] {e}")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db = get_db()
    row = db.execute(
        "SELECT * FROM password_reset_tokens WHERE token_hash = ? AND expires_at > datetime('now')",
        (token_hash,)
    ).fetchone()

    if row is None:
        db.close()
        return render_template("reset_password.html", invalid=True)

    if request.method == "POST":
        new_pw  = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(new_pw) < 8:
            db.close()
            return render_template("reset_password.html", token=token,
                                   error="Password must be at least 8 characters.")
        if new_pw != confirm:
            db.close()
            return render_template("reset_password.html", token=token,
                                   error="Passwords don't match.")

        db.execute("UPDATE users SET password_hash=? WHERE id=?",
                   (generate_password_hash(new_pw), row["user_id"]))
        db.execute("DELETE FROM password_reset_tokens WHERE token_hash=?", (token_hash,))
        db.commit()
        db.close()
        return render_template("reset_password.html", success=True)

    db.close()
    return render_template("reset_password.html", token=token)


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

PER_PAGE = 10


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    generate_due_recurring(db, session["user_id"])
    db.close()

    start_date = request.args.get("start_date", "").strip()
    end_date   = request.args.get("end_date", "").strip()
    category   = request.args.get("category", "").strip()

    VALID_SORT = {"date", "title", "category", "amount"}
    sort  = request.args.get("sort", "date").strip()
    order = request.args.get("order", "desc").strip()
    if sort not in VALID_SORT:
        sort = "date"
    if order not in ("asc", "desc"):
        order = "desc"

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    date_filtered = False
    filter_error  = None

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
                date_filtered = True
        except ValueError:
            filter_error = "Invalid date format."

    cat_filtered = bool(category)
    filtered     = date_filtered or cat_filtered

    db = get_db()

    conditions = ["user_id = ?"]
    params     = [session["user_id"]]
    if date_filtered:
        conditions.append("date BETWEEN ? AND ?")
        params.extend([start_date, end_date])
    if cat_filtered:
        conditions.append("category = ?")
        params.append(category)

    where = " AND ".join(conditions)

    # Aggregate totals for stat cards (all matching rows, not just current page)
    agg = db.execute(
        f"SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM expenses WHERE {where}",
        params
    ).fetchone()
    total_count = agg[0]
    total_sum   = round(float(agg[1]), 2)

    total_pages = max(1, (total_count + PER_PAGE - 1) // PER_PAGE)
    page        = max(1, min(page, total_pages))

    if filtered:
        range_total    = total_sum
        monthly_total  = None
        all_time_total = None
    else:
        this_month   = date.today().strftime("%Y-%m")
        monthly_total = round(float(db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ? AND date LIKE ?",
            (session["user_id"], f"{this_month}%")
        ).fetchone()[0]), 2)
        all_time_total = total_sum
        range_total    = None

    # Paginated expense rows for the table
    offset   = (page - 1) * PER_PAGE
    expenses = db.execute(
        f"SELECT * FROM expenses WHERE {where}"
        f" ORDER BY {sort} {order.upper()}, id DESC"
        f" LIMIT ? OFFSET ?",
        params + [PER_PAGE, offset]
    ).fetchall()

    # Page range list: integers for page buttons, None for ellipsis
    if total_pages <= 7:
        page_range = list(range(1, total_pages + 1))
    else:
        pages = sorted({1, 2, max(1, page - 1), page,
                        min(total_pages, page + 1), total_pages - 1, total_pages})
        page_range, prev = [], None
        for p in pages:
            if prev is not None and p - prev > 1:
                page_range.append(None)
            page_range.append(p)
            prev = p

    # Chart data: last 6 months, always unfiltered
    chart_expenses = db.execute(
        "SELECT date, amount, category FROM expenses WHERE user_id = ?",
        (session["user_id"],)
    ).fetchall()

    today = date.today()
    chart_labels, chart_values = [], []
    for i in range(5, -1, -1):
        m, y = today.month - i, today.year
        while m <= 0:
            m += 12
            y -= 1
        label = date(y, m, 1).strftime("%b %Y")
        month_prefix = f"{y}-{m:02d}"
        total = sum(e["amount"] for e in chart_expenses if e["date"].startswith(month_prefix))
        chart_labels.append(label)
        chart_values.append(round(total, 2))

    # Category doughnut: all-time, unfiltered
    cat_order = ["Food & Dining", "Transport", "Shopping", "Entertainment", "Health", "Bills & Utilities", "Other"]
    cat_totals = {cat: 0.0 for cat in cat_order}
    for e in chart_expenses:
        cat = e["category"] if e["category"] in cat_totals else "Other"
        cat_totals[cat] += e["amount"]
    donut_labels = [c for c in cat_order if cat_totals[c] > 0]
    donut_values = [round(cat_totals[c], 2) for c in donut_labels]

    db.close()

    return render_template(
        "dashboard.html",
        expenses=expenses,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        per_page=PER_PAGE,
        page_range=page_range,
        monthly_total=monthly_total,
        all_time_total=all_time_total,
        range_total=range_total,
        filtered=filtered,
        date_filtered=date_filtered,
        cat_filtered=cat_filtered,
        start_date=start_date,
        end_date=end_date,
        category=category,
        filter_error=filter_error,
        sort=sort,
        order=order,
        chart_labels=chart_labels,
        chart_values=chart_values,
        donut_labels=donut_labels,
        donut_values=donut_values,
    )


@app.route("/expenses/export")
def export_expenses():
    if "user_id" not in session:
        return redirect(url_for("login"))

    start_date = request.args.get("start_date", "").strip()
    end_date   = request.args.get("end_date", "").strip()
    category   = request.args.get("category", "").strip()

    conditions = ["user_id = ?"]
    params     = [session["user_id"]]

    try:
        if start_date and end_date:
            date.fromisoformat(start_date)
            date.fromisoformat(end_date)
            if start_date <= end_date:
                conditions.append("date BETWEEN ? AND ?")
                params.extend([start_date, end_date])
    except ValueError:
        pass

    if category:
        conditions.append("category = ?")
        params.append(category)

    db = get_db()
    expenses = db.execute(
        f"SELECT date, title, category, amount FROM expenses"
        f" WHERE {' AND '.join(conditions)} ORDER BY date DESC, id DESC",
        params
    ).fetchall()
    db.close()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Title", "Category", "Amount"])
    for e in expenses:
        writer.writerow([e["date"], e["title"], e["category"], f"{e['amount']:.2f}"])

    filename = f"spendly-{date.today().isoformat()}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
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

            db.close()
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))

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
            flash("Password changed.", "success")
            return redirect(url_for("profile"))

        elif action == "delete_account":
            password = request.form.get("confirm_delete_password", "")

            if not check_password_hash(user["password_hash"], password):
                db.close()
                return render_template("profile.html", user=user, expense_count=expense_count,
                                       delete_error="Incorrect password.")

            user_id = session["user_id"]
            db.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
            db.execute("DELETE FROM recurring_expenses WHERE user_id = ?", (user_id,))
            db.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
            db.execute("DELETE FROM users WHERE id = ?", (user_id,))
            db.commit()
            db.close()
            session.clear()
            return redirect(url_for("landing"))

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
        flash("Expense added.", "success")
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
        flash("Expense updated.", "success")
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
        flash("Expense deleted.", "success")
        return redirect(url_for("dashboard"))

    db.close()
    return render_template("delete_expense.html", expense=expense)


@app.route("/recurring", methods=["GET", "POST"])
def recurring():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()

    if request.method == "POST":
        title     = request.form.get("title", "").strip()
        amount    = request.form.get("amount", "").strip()
        category  = request.form.get("category", "Other")
        frequency = request.form.get("frequency", "monthly")
        start     = request.form.get("start_date", "").strip()

        error = None
        if not title or not amount or not start:
            error = "All fields are required."
        elif frequency not in FREQUENCIES:
            error = "Invalid frequency."
        else:
            try:
                amount_f = float(amount)
                if amount_f <= 0:
                    raise ValueError
            except ValueError:
                error = "Enter a valid positive amount."

        if error:
            rows = db.execute(
                "SELECT * FROM recurring_expenses WHERE user_id = ? ORDER BY next_due",
                (session["user_id"],)
            ).fetchall()
            db.close()
            return render_template("recurring.html", recurring=rows, error=error,
                                   today=date.today().isoformat())

        db.execute(
            "INSERT INTO recurring_expenses (user_id, title, amount, category, frequency, next_due)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (session["user_id"], title, amount_f, category, frequency, start)
        )
        db.commit()
        db.close()
        flash(f"Recurring \"{title}\" added.", "success")
        return redirect(url_for("recurring"))

    rows = db.execute(
        "SELECT * FROM recurring_expenses WHERE user_id = ? ORDER BY next_due",
        (session["user_id"],)
    ).fetchall()
    db.close()
    return render_template("recurring.html", recurring=rows, today=date.today().isoformat())


@app.route("/recurring/<int:id>/delete", methods=["POST"])
def delete_recurring(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    db.execute(
        "DELETE FROM recurring_expenses WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    )
    db.commit()
    db.close()
    flash("Recurring expense stopped.", "success")
    return redirect(url_for("recurring"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
