# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (always use the venv python)
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# Run dev server (http://localhost:5001)
.\venv\Scripts\python.exe app.py

# Run tests
.\venv\Scripts\python.exe -m pytest
```

> The system Python does not have Flask installed. Always run via `.\venv\Scripts\python.exe` or activate the venv first with `.\venv\Scripts\Activate.ps1`.

## Email Configuration (forgot-password flow)

Flask-Mail is used for password reset emails. Set these environment variables before starting the server:

```bash
$env:MAIL_USERNAME = "you@gmail.com"
$env:MAIL_PASSWORD = "your-app-password"   # Gmail: generate an App Password in Google Account settings
# Optional overrides (defaults shown):
# $env:MAIL_SERVER = "smtp.gmail.com"
# $env:MAIL_PORT   = "587"
# $env:MAIL_DEFAULT_SENDER = "you@gmail.com"
```

**Dev mode:** if `MAIL_USERNAME` is not set, the reset link is printed to the server console instead of emailed — no SMTP setup needed for local development.

## Architecture

**Spendly** is a server-side rendered Flask application with SQLite. There is no frontend build step — no Node, no bundler, no TypeScript.

- **`app.py`** — All Flask routes. Calls `init_db()` at startup inside `with app.app_context()`. Uses `session` for auth (`user_id`, `user_name`).
- **`database/db.py`** — SQLite module. `get_db()` returns a connection with `row_factory = sqlite3.Row` and foreign keys enabled. `init_db()` creates all tables with `CREATE TABLE IF NOT EXISTS`. `get_spending_summary(db, user_id, start_date, end_date)` returns `period_total`, `period_count`, and `top_category` for a given user and optional date range.
- **`templates/`** — Jinja2 templates. `base.html` defines the shared navbar/footer; all others extend it. The navbar conditionally shows Dashboard · Recurring · user name (→ `/profile`) · Sign out (when `session.user_id` is set) or Sign in / Get started.
- **`static/css/style.css`** — Global styles: design tokens, navbar, footer, auth forms, dashboard, expense pages.
- **`static/css/landing.css`** — Landing-page-only styles (hero dark section, floating cards, video modal).
- **`static/js/main.js`** — Vanilla JS. Handles toast auto-dismiss (4 s) and close-button logic.
- **Chart.js 4.4** — loaded from CDN on the dashboard only (`{% block head %}`). Used for the monthly spending bar chart and the category doughnut chart; no local install required.

## Database Schema

```sql
users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,       -- werkzeug generate_password_hash
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

expenses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    title      TEXT NOT NULL,
    amount     REAL NOT NULL,
    category   TEXT NOT NULL DEFAULT 'Other',
    date       DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

password_reset_tokens (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    token_hash TEXT NOT NULL UNIQUE,   -- SHA-256 of the raw URL token
    expires_at TIMESTAMP NOT NULL,     -- 1 hour from creation (UTC)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

recurring_expenses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    title      TEXT NOT NULL,
    amount     REAL NOT NULL,
    category   TEXT NOT NULL DEFAULT 'Other',
    frequency  TEXT NOT NULL,          -- 'weekly' | 'monthly' | 'yearly'
    next_due   DATE NOT NULL,          -- advanced after each generation run
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## Implemented Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Landing page |
| GET/POST | `/register` | Create account; on success renders success state (no redirect) |
| GET/POST | `/login` | Sign in; redirects to `/dashboard` on success. "Remember me for 30 days" checkbox sets `session.permanent = True`, attaching a 30-day `Max-Age` cookie; unchecked gives a session cookie that expires on browser close |
| GET | `/logout` | Clears session, redirects to `/` |
| GET | `/dashboard` | Shows stat cards, two charts (bar + doughnut), filter bar, and expense table; login-gated. Calls `generate_due_recurring()` on every load to auto-create any overdue recurring entries. Accepts optional `start_date`, `end_date` (YYYY-MM-DD), and `category` query params to filter expenses; filters can be combined. Accepts `sort` (`date`, `title`, `category`, `amount`) and `order` (`asc`, `desc`) for column sorting. Accepts `page` for pagination (10 rows per page, `PER_PAGE = 10`). Stat card totals are computed via SQL aggregates over all matching rows regardless of page. Charts are always unfiltered. Expense table has a client-side search bar and an Export CSV button (both in the card header); the export link forwards active filter params to `/expenses/export` |
| GET | `/expenses/export` | Download all expenses as a CSV file (`spendly-YYYY-MM-DD.csv`). Accepts the same `start_date`, `end_date`, and `category` query params as the dashboard — export matches the active filter. Invalid dates are silently ignored. Login-gated |
| GET/POST | `/expenses/add` | Add new expense form |
| GET/POST | `/expenses/<id>/edit` | Edit existing expense (owner-checked) |
| GET/POST | `/expenses/<id>/delete` | Confirmation page + delete (owner-checked) |
| GET/POST | `/profile` | Edit name/email, change password, and delete account; login-gated. Delete action (`action=delete_account`) requires password confirmation, wipes tokens → recurring → expenses → user row, clears session, and redirects to `/`. GET accepts optional `start_date` and `end_date` (YYYY-MM-DD) query params to filter the spending summary card — shows `period_total`, `period_count`, and `top_category` for the selected range, or all-time totals when no filter is active. Invalid/partial dates set `filter_error`; stats are computed via `get_spending_summary()` in `database/db.py` |
| GET/POST | `/recurring` | List and add recurring expense schedules; login-gated. POST creates a new schedule (title, amount, category, frequency, start date). Redirects with toast on success |
| POST | `/recurring/<id>/delete` | Stop (delete) a recurring schedule (owner-checked). Redirects with toast |
| GET/POST | `/forgot-password` | Request a password reset; shows same "check your email" message regardless of whether address exists |
| GET/POST | `/reset-password/<token>` | Consume a reset token; sets new password and deletes the token. Shows expired/invalid state if token not found or past 1-hour TTL |
| GET | `/terms` | Terms and Conditions |
| GET | `/privacy` | Privacy Policy |

All expense routes check `session["user_id"]` and redirect to `/login` if not set. Edit and delete also verify the expense belongs to the logged-in user.

## Design System

CSS custom properties in `style.css`:
- `--ink`, `--ink-soft`, `--ink-muted`, `--ink-faint` — text shades
- `--paper`, `--paper-warm`, `--paper-card` — background shades
- `--accent` (dark green), `--accent-light`, `--accent-2` (gold), `--accent-2-light`
- `--danger`, `--danger-light`
- `--border`, `--border-soft`
- `--radius-sm: 6px`, `--radius-md: 12px`, `--radius-lg: 20px`
- `--max-width: 1200px`, `--auth-width: 440px`
- Fonts: `--font-display` (DM Serif Display), `--font-body` (DM Sans)

Auth/form pages reuse `.auth-section`, `.auth-card`, `.form-group`, `.form-input`, `.btn-submit`, `.form-check` (checkbox + label row). Profile danger zone uses `.danger-zone`, `.danger-zone-title`, `.danger-zone-card`, `.danger-zone-desc`. The profile spending summary card uses `.profile-summary-card` (gold left-border variant of `.profile-card`), `.profile-summary-header` (flex row for heading + badge), `.filter-badge` (pill showing active date range), `.profile-summary-filter` (flex filter form row), `.btn-clear` (outlined clear link), `.profile-stat-chips` (flex row of stat tiles), `.profile-stat-chip-item` (individual tile), `.profile-stat-chip-value` (display-font metric), `.profile-stat-chip-label` (uppercase label). The dashboard uses `.dashboard-section`, `.stat-card`, `.expenses-card`, `.expenses-table`; charts sit in a `.charts-row` grid (`.chart-wrap` for the bar chart, `.donut-wrap` for the doughnut); the expenses card header uses `.search-wrap`, `.search-icon`, `.search-input` for the search bar; pagination uses `.pagination-bar`, `.pagination`, `.page-btn`, `.page-btn-active`, `.page-btn-disabled`, `.page-ellipsis`. Toast notifications use `.toast-container`, `.toast`, `.toast-success`, `.toast-error`, `.toast-msg`, `.toast-close`. The recurring page uses `.recurring-section`, `.recurring-inner`, `.recurring-header`, `.recurring-title`, `.recurring-subtitle`, `.recur-freq` (frequency badge), `.btn-unstyled` (unstyled form button). Category badges use `.cat-food-dining`, `.cat-grocery`, `.cat-transport`, `.cat-shopping`, `.cat-entertainment`, `.cat-self-learning`, `.cat-health`, `.cat-bills-utilities`, `.cat-other` — the class is derived from the category name via `lower | replace(' ', '-') | replace('&', '') | replace('--', '-')`. Landing page has its own button variants (`.btn-coral`, `.btn-white-ghost`, `.btn-watch`) in `landing.css`.

## Expense Categories

Fixed list used in add/edit forms and styled as coloured badges on the dashboard:
`Food & Dining`, `Grocery`, `Transport`, `Shopping`, `Entertainment`, `Self Learning`, `Health`, `Bills & Utilities`, `Other`

## Manual Test Coverage

### `/dashboard` date range filter (tested 2026-05-19)
| Scenario | Result |
|---|---|
| No filter — all expenses shown, This month / All time stat cards | PASS |
| Valid range — correct subset of expenses, Range total + Period cards, Filtered badge | PASS |
| Valid range with no matching expenses — "No expenses in this range" empty state | PASS |
| Start date after end date — error message | PASS |
| Only one date provided — error message | PASS |

### `/dashboard` spending chart (tested 2026-05-20)
| Scenario | Result |
|---|---|
| Chart.js CDN script tag present in page | PASS |
| Canvas element rendered | PASS |
| Last 6 month labels present in page data | PASS |
| Correct monthly totals passed to chart | PASS |
| Chart data unaffected by active category/date filter | PASS |
| Chart card title and subtitle rendered | PASS |

### `/dashboard` category doughnut chart (tested 2026-05-20)
| Scenario | Result |
|---|---|
| Doughnut canvas rendered alongside bar chart in 2-column grid | PASS |
| Only categories with spending > 0 included in chart data | PASS |
| Category colours match badge colours | PASS |
| Tooltip shows ₹ amount on hover | PASS |
| Legend rendered at bottom with category names | PASS |
| Chart data always unfiltered (all-time totals) | PASS |
| Empty state shown when user has no expenses | PASS |
| Grid collapses to single column on mobile (≤900 px) | PASS |

### `/dashboard` sort feature (tested 2026-05-20)
| Scenario | Result |
|---|---|
| Sort by amount asc — correct ascending order | PASS |
| Sort by title asc — correct alphabetical order | PASS |
| Sort by date desc (default) — correct descending order | PASS |
| Column headers rendered as sort links | PASS |
| Active column has `col-sorted` class (accent highlight) | PASS |
| ↑/↓ arrow shown on active sort column | PASS |
| Sort preserved when combined with category filter | PASS |
| Invalid `sort` param safely falls back to `date` | PASS |

### `/dashboard` category filter (tested 2026-05-19)
| Scenario | Result |
|---|---|
| Category only — correct subset shown, Category stat card | PASS |
| Date + category combined — correct subset, Period & category stat card | PASS |
| Category with no matching expenses — "No expenses in this range" empty state | PASS |
| No filter — all expenses, default stat cards unchanged | PASS |
| Category select pre-populated with active filter value | PASS |

### `/profile` (tested 2026-05-19)
| Scenario | Result |
|---|---|
| GET — page renders with title, both cards, member since, expense count | PASS |
| GET — name and email pre-filled from DB | PASS |
| GET — Dashboard link present in navbar | PASS |
| POST `update_info` — valid name/email update shows "Profile updated." toast | PASS |
| POST `update_info` — updated name reflected in pre-filled form after redirect | PASS |
| POST `change_password` — wrong current password shows error | PASS |
| POST `change_password` — mismatched confirm password shows error | PASS |
| POST `change_password` — password under 8 chars shows error | PASS |
| POST `change_password` — valid change shows "Password changed." toast | PASS |

### `/forgot-password` + `/reset-password/<token>` (tested 2026-05-20)
| Scenario | Result |
|---|---|
| GET `/forgot-password` — form renders | PASS |
| POST with registered email — "check your email" state shown | PASS |
| POST with unregistered email — same "check your email" state (no enumeration) | PASS |
| Dev mode (no MAIL_USERNAME) — reset link printed to console | PASS |
| GET `/reset-password/<valid-token>` — new password form renders | PASS |
| POST — password under 8 chars shows error | PASS |
| POST — mismatched passwords shows error | PASS |
| POST — valid reset updates password, token deleted, success shown | PASS |
| GET `/reset-password/<expired-or-bad-token>` — invalid state + re-request link | PASS |
| Token cannot be reused after successful reset | PASS |

### `/profile` account deletion (tested 2026-05-20)
| Scenario | Result |
|---|---|
| Danger zone card visible on profile page | PASS |
| Wrong password — error shown, account not deleted | PASS |
| Correct password — account, expenses, and reset tokens all deleted | PASS |
| Session cleared after deletion — redirected to landing page | PASS |
| Deleted user cannot log in again | PASS |

### `/login` remember me (tested 2026-05-20)
| Scenario | Result |
|---|---|
| Checkbox unchecked — session cookie with no Max-Age (expires on browser close) | PASS |
| Checkbox checked — cookie has 30-day Max-Age, persists across browser restart | PASS |
| "Remember me for 30 days" checkbox rendered on login page | PASS |

### `/dashboard` pagination (tested 2026-05-20)
| Scenario | Result |
|---|---|
| 10 rows shown per page | PASS |
| Pagination bar hidden when total rows ≤ 10 | PASS |
| "X–Y of Z" info label correct on each page | PASS |
| Prev disabled on page 1, Next disabled on last page | PASS |
| Page numbers with ellipsis rendered for large sets | PASS |
| Clicking page number navigates to correct page | PASS |
| Filter/sort params preserved in all pagination links | PASS |
| Sorting resets to page 1 | PASS |
| Stat card totals reflect all matching rows, not just current page | PASS |
| Out-of-range `page` param clamped to valid range | PASS |

### `/expenses/export` CSV export (tested 2026-05-20)
| Scenario | Result |
|---|---|
| No filter — all expenses downloaded as CSV | PASS |
| Active date range — only matching rows in CSV | PASS |
| Active category filter — only matching rows in CSV | PASS |
| CSV columns: Date, Title, Category, Amount | PASS |
| Filename includes today's date (`spendly-YYYY-MM-DD.csv`) | PASS |
| Invalid date params silently ignored, full export returned | PASS |
| Unauthenticated request redirects to `/login` | PASS |

### Toast notifications (tested 2026-05-20)
| Scenario | Result |
|---|---|
| "Expense added." toast appears on dashboard after add | PASS |
| "Expense updated." toast appears on dashboard after edit | PASS |
| "Expense deleted." toast appears on dashboard after delete | PASS |
| "Profile updated." toast appears on profile page after saving account info | PASS |
| "Password changed." toast appears on profile page after password update | PASS |
| Toast auto-dismisses after 4 s | PASS |
| Close button (×) dismisses toast immediately | PASS |
| Toast slides in from the right on appear, slides out on dismiss | PASS |

### `/recurring` recurring expenses (tested 2026-05-20)
| Scenario | Result |
|---|---|
| Recurring nav link present for logged-in users | PASS |
| GET — empty state shown when no schedules exist | PASS |
| POST — valid schedule added, "Recurring X added." toast shown | PASS |
| POST — missing fields show inline error | PASS |
| Active schedules table shows title, category, frequency badge, amount, next due | PASS |
| On dashboard load — overdue entries auto-generated, next_due advanced | PASS |
| Multi-period backfill — months of missed entries all created in one load | PASS |
| Stop button removes schedule, "Recurring expense stopped." toast shown | PASS |
| Month-end clamping — e.g. Jan 31 monthly → Feb 28, not Feb 31 | PASS |
| Account deletion wipes recurring schedules along with expenses | PASS |

### `/profile` date filter — spending summary (tested 2026-06-04)
| Scenario | Result |
|---|---|
| GET — spending summary card renders with heading and filter form | PASS |
| No filter active — all-time total, count, and top category shown | PASS |
| Valid date range — stat chips update to filtered period totals | PASS |
| "Filtered: start → end" badge visible when date range is active | PASS |
| Date inputs pre-populated with submitted values after filter | PASS |
| Only start date provided — `filter_error` shown, chips hidden | PASS |
| Only end date provided — `filter_error` shown, chips hidden | PASS |
| Start date after end date — `filter_error` shown, chips hidden | PASS |
| Date range with no matching expenses — ₹0.00, 0, "—" top category | PASS |
| Clear link returns to all-time stats | PASS |
| Existing profile cards (account info, change password, danger zone) unaffected | PASS |
| Unauthenticated GET with date params redirects to `/login` | PASS |

### `/dashboard` search bar (tested 2026-05-20)
| Scenario | Result |
|---|---|
| Search input and icon rendered in expenses card header | PASS |
| Empty query — all rows visible | PASS |
| Query matching title — correct rows shown | PASS |
| Query matching category — correct rows shown | PASS |
| Query matching date prefix — correct rows shown | PASS |
| Case-insensitive match | PASS |
| Query with no matches — "No expenses match your search." row shown | PASS |
| Search composes with active server-side date/category filters | PASS |
