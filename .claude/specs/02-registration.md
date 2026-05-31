# Spec: Registration

## Overview
Add user account creation to Spendly. A visitor fills in their name, email, and password on a dedicated registration page. On success the same page renders a confirmation state (no redirect) so the user knows the account was created and can navigate to sign in. This is the entry point for all authenticated features — without it no one can own expenses, profiles, or recurring schedules.

## Depends on
Step 01 — Database Setup (users table and `get_db()` must exist)

## Routes

- `GET /register` — Render the empty registration form — public
- `POST /register` — Validate input and insert the new user — public

## Database changes
No new tables or columns. Uses the `users` table created in step 01:
```
users (id, name, email, password_hash, created_at)
```

## Templates

- **Create:** `templates/register.html`
  - Extends `base.html`
  - Form fields: Name, Email, Password
  - Inline error message area (shown when `error` is passed from the route)
  - Success state (shown when `success=True` is passed) — replaces the form with a confirmation message and a link to `/login`
  - Reuses auth layout classes: `.auth-section`, `.auth-card`, `.form-group`, `.form-input`, `.btn-submit`

## Files to change

- `app.py` — add the `/register` route (GET + POST)

## Files to create

- `templates/register.html`

## New dependencies
No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never string-format values into SQL
- Hash passwords with `werkzeug.security.generate_password_hash` — never store plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Strip and lowercase the email before storing (`email.strip().lower()`)
- Validate server-side: name, email, and password are all required; password must be ≥ 8 characters
- Catch the `UNIQUE` constraint violation on email and return a friendly error ("An account with that email already exists.")
- On success, render the same `register.html` template with `success=True` — do **not** redirect to `/dashboard` or auto-login the user
- Close the DB connection in a `finally` block so it is released even when an exception is raised

## Definition of done

- [ ] `GET /register` renders the form with Name, Email, and Password fields
- [ ] Submitting an empty form shows "All fields are required."
- [ ] Submitting a password shorter than 8 characters shows the length error
- [ ] Submitting a duplicate email shows "An account with that email already exists."
- [ ] Valid submission inserts a row in `users` with a hashed password (not plaintext)
- [ ] After valid submission the page shows the success state with a link to `/login`
- [ ] The new user can log in at `/login` using the email and password they registered with
- [ ] Refreshing the success page does not create a duplicate user
