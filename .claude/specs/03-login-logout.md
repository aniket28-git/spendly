# Spec: Login and Logout

## Overview
Add sign-in and sign-out to Spendly. A registered user submits their email and password on the login page; on success the server writes `user_id` and `user_name` into the Flask session and redirects to `/dashboard`. An optional "Remember me" checkbox makes the session cookie persist for 30 days instead of expiring on browser close. Logging out clears the session and returns the user to the landing page. This step gates all authenticated features — the dashboard, profile, and expense routes all depend on `session["user_id"]` being set.

## Depends on
Step 01 — Database Setup (`users` table and `get_db()` must exist)
Step 02 — Registration (a user account must exist to sign in with)

## Routes

- `GET /login` — Render the sign-in form — public
- `POST /login` — Validate credentials, write session, redirect to `/dashboard` — public
- `GET /logout` — Clear session, redirect to `/` — public (no login check needed)

## Database changes
No database changes. Reads from the `users` table created in step 01.

## Templates

- **Create:** `templates/login.html`
  - Extends `base.html`
  - Form fields: Email, Password
  - "Remember me for 30 days" checkbox (`name="remember"`, `value="1"`)
  - Inline error area shown when `error` context variable is set
  - Link to `forgot_password` below the form
  - Link to `/register` ("Don't have an account?") below the card
  - Reuses `.auth-section`, `.auth-card`, `.form-group`, `.form-input`, `.btn-submit`, `.form-check`

- **Modify:** `templates/base.html`
  - Navbar should show **Dashboard · Recurring · `session.user_name` (→ `/profile`) · Sign out** when `session.user_id` is set
  - Navbar should show **Sign in · Get started** when `session.user_id` is not set

## Files to change

- `app.py` — add `/login` (GET + POST) and `/logout` routes
- `templates/base.html` — conditional navbar links based on `session.user_id`

## Files to create

- `templates/login.html`

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is already installed.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never string-format values into SQL
- Use `check_password_hash` from `werkzeug.security` to verify the password — never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Strip and lowercase the submitted email before querying (`email.strip().lower()`)
- On invalid credentials show a single generic error: `"Invalid email or password."` — do **not** reveal whether the email exists
- Set `session.permanent = True` only when the "remember" checkbox is submitted; leave it `False` otherwise
- Store both `session["user_id"]` (integer) and `session["user_name"]` (string) on successful login
- `PERMANENT_SESSION_LIFETIME` must be set to `timedelta(days=30)` in `app.config` so the persistent cookie gets the correct `Max-Age`
- `/logout` calls `session.clear()` and redirects to `url_for("landing")`
- Close the DB connection after querying in `/login`

## Definition of done

- [ ] `GET /login` renders the form with Email, Password fields and a "Remember me for 30 days" checkbox
- [ ] A "Forgot your password?" link is present below the form
- [ ] Submitting wrong email or wrong password shows "Invalid email or password." and does not redirect
- [ ] Valid credentials redirect the user to `/dashboard`
- [ ] After login, navbar shows Dashboard · Recurring · user's name · Sign out
- [ ] "Remember me" unchecked — session cookie has no `Max-Age` (expires on browser close)
- [ ] "Remember me" checked — session cookie has a 30-day `Max-Age`
- [ ] Clicking "Sign out" clears the session and returns to the landing page
- [ ] After logout, navbar shows Sign in · Get started links
- [ ] A logged-out user visiting `/dashboard` is redirected to `/login`
- [ ] The registration success page has a working link to `/login`
