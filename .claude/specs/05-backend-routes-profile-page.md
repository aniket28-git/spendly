# Spec: Backend Routes for Profile Page

## Overview
Add the server-side logic that powers the profile page. A logged-in user can view their account details, update their name and email, change their password, and permanently delete their account. All three mutations go through a single `POST /profile` route distinguished by a hidden `action` field. This step transforms the static profile design from step 04 into a fully functional settings page — it is the backend complement to the frontend-only work done in that step.

## Depends on
Step 01 — Database Setup (`users` table and `get_db()` must exist)  
Step 02 — Registration (user accounts must exist)  
Step 03 — Login and Logout (`session["user_id"]` must be set to reach `/profile`)  
Step 04 — Profile Page Design (template structure and form field names are already in place)

## Routes

- `GET /profile` — Render the profile page with user info and expense count — logged-in only
- `POST /profile` (action=`update_info`) — Update name and email — logged-in only
- `POST /profile` (action=`change_password`) — Change password after verifying the current one — logged-in only
- `POST /profile` (action=`delete_account`) — Delete the account after password confirmation — logged-in only

## Database changes
No new tables or columns. Reads and writes to the existing `users`, `expenses`, `password_reset_tokens`, and `recurring_expenses` tables.

## Templates

- **Modify:** `templates/profile.html`
  - No structural changes required — form field `name`, `id`, and `action` attributes must match exactly what the route expects
  - `info_error` context variable: displayed inside the account info card when name/email update fails
  - `pw_error` context variable: displayed inside the change password card on failure
  - `delete_error` context variable: displayed inside the danger zone on failure; when present the `<details>` renders with the `open` attribute
  - Flash messages (`"Profile updated."`, `"Password changed."`) are already handled by the toast system in `base.html`

## Files to change

- `app.py` — add the `/profile` route (GET + POST with three action branches)

## Files to create
No new files.

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` and `generate_password_hash` are already installed.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`; verified with `check_password_hash` — never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Redirect to `/login` if `session["user_id"]` is not set
- Strip and lowercase email before storing (`email.strip().lower()`)
- `update_info`: name and email are both required; catch the `UNIQUE` constraint violation and return `info_error="That email is already in use."`; on success update `session["user_name"]`, flash `"Profile updated."` and redirect to `url_for("profile")`
- `change_password`: verify current password first; new password must be ≥ 8 characters; new password and confirm must match; on success flash `"Password changed."` and redirect to `url_for("profile")`
- `delete_account`: verify password before deleting anything; deletion order must respect foreign keys — delete `password_reset_tokens`, then `recurring_expenses`, then `expenses`, then `users`; call `session.clear()` after deletion and redirect to `url_for("landing")`
- Always close the DB connection before redirecting or re-rendering — use `db.close()` in each branch
- The expense count shown on the page is a `COUNT(*)` query scoped to `session["user_id"]`

## Definition of done

- [ ] `GET /profile` renders the page with the logged-in user's name and email pre-filled
- [ ] `GET /profile` shows the correct expense count for the user
- [ ] `GET /profile` shows the correct `created_at` date for the user (member since)
- [ ] Unauthenticated `GET /profile` redirects to `/login`
- [ ] `POST update_info` with empty name or email shows `info_error` without redirecting
- [ ] `POST update_info` with a duplicate email shows `info_error="That email is already in use."`
- [ ] `POST update_info` with valid data updates the DB, refreshes `session["user_name"]`, and shows a "Profile updated." toast
- [ ] `POST change_password` with wrong current password shows `pw_error="Current password is incorrect."`
- [ ] `POST change_password` with new password under 8 characters shows the length error
- [ ] `POST change_password` with mismatched confirm shows `pw_error="Passwords don't match."`
- [ ] `POST change_password` with valid data updates the password hash and shows a "Password changed." toast
- [ ] `POST delete_account` with wrong password shows `delete_error="Incorrect password."` with the danger zone expanded
- [ ] `POST delete_account` with correct password deletes all user data (tokens → recurring → expenses → user row), clears the session, and redirects to `/`
- [ ] Deleted user cannot log in again
