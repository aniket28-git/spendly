# Spec: Date Filter for Profile Page

## Overview
Extend the profile page with a date-range spending summary section. Currently the profile hero shows only a static expense count. This step adds a filter form (start date / end date) that scopes a set of stat chips — total spent, expense count, and top category — to the selected period. When no filter is active, the stats default to all-time totals. This gives users a lightweight way to review their spending for any custom period without navigating to the full dashboard.

## Depends on
Step 01 — Database Setup (`expenses` table and `get_db()` must exist)  
Step 02 — Registration (user accounts must exist)  
Step 03 — Login and Logout (`session["user_id"]` required to reach `/profile`)  
Step 04 — Profile Page Design (template structure already in place)  
Step 05 — Backend Routes for Profile Page (`GET /profile` route exists and renders `profile.html`)

## Routes
- `GET /profile` — Extended to accept optional `start_date` and `end_date` query params (YYYY-MM-DD); computes scoped stats and passes them to the template — logged-in only

No new routes needed; the existing `GET /profile` route is extended.

## Database changes
No database changes. Reads from the existing `expenses` table.

## Templates
- **Modify:** `templates/profile.html`
  - Add a spending summary card below the profile hero and above the "Account info" card
  - Card contains a filter form (`GET /profile`) with two date inputs and a filter/clear button row
  - Below the form, render three stat chips: total spent in period, expense count in period, and top category in period (or "—" when no expenses match)
  - When a filter is active, show a "Filtered: start → end" badge next to the card heading
  - If `filter_error` is set, show an inline error message inside the card and skip the stat chips
  - Pre-populate date inputs with the active `start_date` / `end_date` values so the form is sticky after submission

## Files to change
- `app.py` — extend the `GET /profile` handler to read `start_date` / `end_date` query params, validate them, run aggregate queries, and pass stats to the template
- `templates/profile.html` — add the spending summary card
- `static/css/style.css` — add styles for `.profile-summary-card`, `.profile-summary-filter`, `.profile-stat-chips`, `.profile-stat-chip-value` (if not already covered by existing chip styles)

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (not relevant here, but keep existing password handling untouched)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Redirect to `/login` if `session["user_id"]` is not set
- Validate both dates with `date.fromisoformat()`; if only one date is provided, set `filter_error = "Please provide both a start and end date."`; if start > end, set `filter_error = "Start date must be on or before the end date."`; invalid ISO format sets `filter_error = "Invalid date format."`
- When `filter_error` is set, pass `start_date` and `end_date` back to the template so inputs stay populated, but skip the stat chips
- Stats to compute (all via SQL aggregates, scoped to `user_id` + optional date range):
  - `period_total` — `COALESCE(SUM(amount), 0)` rounded to 2 decimal places
  - `period_count` — `COUNT(*)`
  - `top_category` — category with the highest `SUM(amount)`; `None` when count is 0
- When no filter is active (both params absent), compute the same stats over all expenses (all-time)
- The existing `expense_count` passed to the template (total all-time count shown in the hero chips) must not be changed — it always reflects the all-time count
- The POST actions (`update_info`, `change_password`, `delete_account`) must not be touched
- `start_date` and `end_date` must not be forwarded to POST forms — they are GET-only query params

## Definition of done
- [ ] Profile page renders the spending summary card for a logged-in user
- [ ] No filter active — stat chips show all-time total spent, all-time expense count, and all-time top category
- [ ] Valid date range — stat chips update to show totals for that period only
- [ ] "Filtered: start → end" badge visible when a date range is active
- [ ] Date inputs pre-populated with the active filter values after submission
- [ ] Only start date provided — `filter_error` shown, stat chips hidden
- [ ] Only end date provided — `filter_error` shown, stat chips hidden
- [ ] Start date after end date — `filter_error` shown, stat chips hidden
- [ ] Date range with no matching expenses — chips show ₹0.00, 0 expenses, "—" top category
- [ ] Clear filter link (or empty form submit) returns to all-time stats
- [ ] Existing profile cards (account info, change password, danger zone) are unaffected
- [ ] Unauthenticated request with date params still redirects to `/login`
