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

## Architecture

**Spendly** is a server-side rendered Flask application with SQLite. There is no frontend build step — no Node, no bundler, no TypeScript.

- **`app.py`** — All Flask routes. Calls `init_db()` at startup inside `with app.app_context()`. Uses `session` for auth (`user_id`, `user_name`).
- **`database/db.py`** — SQLite module. `get_db()` returns a connection with `row_factory = sqlite3.Row` and foreign keys enabled. `init_db()` creates the `users` and `expenses` tables with `CREATE TABLE IF NOT EXISTS`.
- **`templates/`** — Jinja2 templates. `base.html` defines the shared navbar/footer; all others extend it. The navbar conditionally shows Dashboard (links to `/dashboard`) + the user's name (links to `/profile`) + Sign out (when `session.user_id` is set) or Sign in / Get started.
- **`static/css/style.css`** — Global styles: design tokens, navbar, footer, auth forms, dashboard, expense pages.
- **`static/css/landing.css`** — Landing-page-only styles (hero dark section, floating cards, video modal).
- **`static/js/main.js`** — Vanilla JS entry point (stub).

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
```

## Implemented Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Landing page |
| GET/POST | `/register` | Create account; on success renders success state (no redirect) |
| GET/POST | `/login` | Sign in; redirects to `/dashboard` on success |
| GET | `/logout` | Clears session, redirects to `/` |
| GET | `/dashboard` | Shows stat cards + expense table; login-gated. Accepts optional `start_date`, `end_date` (YYYY-MM-DD), and `category` query params to filter expenses; filters can be combined. Accepts `sort` (`date`, `title`, `category`, `amount`) and `order` (`asc`, `desc`) for column sorting. Stat cards adapt to show Filtered total / Period / Category context when any filter is active |
| GET/POST | `/expenses/add` | Add new expense form |
| GET/POST | `/expenses/<id>/edit` | Edit existing expense (owner-checked) |
| GET/POST | `/expenses/<id>/delete` | Confirmation page + delete (owner-checked) |
| GET/POST | `/profile` | Edit name/email and change password; login-gated |
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

Auth/form pages reuse `.auth-section`, `.auth-card`, `.form-group`, `.form-input`, `.btn-submit`. The dashboard uses `.dashboard-section`, `.stat-card`, `.expenses-card`, `.expenses-table`. Landing page has its own button variants (`.btn-coral`, `.btn-white-ghost`, `.btn-watch`) in `landing.css`.

## Expense Categories

Fixed list used in add/edit forms and styled as coloured badges on the dashboard:
`Food & Dining`, `Transport`, `Shopping`, `Entertainment`, `Health`, `Bills & Utilities`, `Other`

## Manual Test Coverage

### `/dashboard` date range filter (tested 2026-05-19)
| Scenario | Result |
|---|---|
| No filter — all expenses shown, This month / All time stat cards | PASS |
| Valid range — correct subset of expenses, Range total + Period cards, Filtered badge | PASS |
| Valid range with no matching expenses — "No expenses in this range" empty state | PASS |
| Start date after end date — error message | PASS |
| Only one date provided — error message | PASS |

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
| POST `update_info` — valid name/email update shows success message | PASS |
| POST `update_info` — updated name reflected in pre-filled form | PASS |
| POST `change_password` — wrong current password shows error | PASS |
| POST `change_password` — mismatched confirm password shows error | PASS |
| POST `change_password` — password under 8 chars shows error | PASS |
| POST `change_password` — valid change shows success message | PASS |
