"""
tests/test_06-date-filter-profile-page.py

Tests for Spec 06 — Date Filter for Profile Page.

The /profile route accepts optional start_date / end_date query params (YYYY-MM-DD)
and renders a "Spending summary" card with three stat chips:
  - period_total   (COALESCE(SUM(amount), 0), 2 dp)
  - period_count   (COUNT(*))
  - top_category   (highest SUM(amount) category, or None / "—" when 0 rows)

When no filter is active, the same stats are computed over all expenses (all-time).
Validation errors (one date missing, start > end, bad format) set filter_error and
hide the stat chips.

Fixture strategy:
  - The DATABASE path in database.db is monkey-patched to a temporary file so every
    call to get_db() inside the request shares the same persistent SQLite file.
  - Expenses seeded:
      Jan 2026 — "Lunch" Food & Dining  500.00  (2026-01-10)
      Jan 2026 — "Bus"   Transport      200.00  (2026-01-20)
      May 2026 — "Shoes" Shopping      1000.00  (2026-05-05)
    All-time total = 1700.00, count = 3, top_category = Shopping (1000 > 500 > 200)
    Jan 2026 range total = 700.00, count = 2, top_category = Food & Dining
    May 2026 range total = 1000.00, count = 1, top_category = Shopping
"""

import os
import tempfile
import pytest

import database.db as db_module
from app import app as flask_app
from database.db import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(tmp_path):
    """
    Configure the Flask app for testing with an isolated SQLite file.

    We use a real file (not :memory:) because get_db() opens a new connection
    on every call, and :memory: would give a fresh empty DB each time.
    tmp_path is a pytest-provided temporary directory that is unique per test.
    """
    db_file = str(tmp_path / "test_spendly.db")

    # Patch the DATABASE global so all get_db() calls inside this test use our file.
    original_database = db_module.DATABASE
    db_module.DATABASE = db_file

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "WTF_CSRF_ENABLED": False,
    })

    with flask_app.app_context():
        init_db()

    yield flask_app

    # Restore the original DATABASE path after the test.
    db_module.DATABASE = original_database


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    """
    A test client that is already logged in as 'testuser'.

    Expenses seeded (designed for predictable filter assertions):
      - 2026-01-10  "Lunch"  Food & Dining  500.00   (Jan 2026)
      - 2026-01-20  "Bus"    Transport      200.00   (Jan 2026)
      - 2026-05-05  "Shoes"  Shopping      1000.00  (May 2026)

    All-time: total=1700.00, count=3, top_category="Shopping"
    Jan 2026:  total= 700.00, count=2, top_category="Food & Dining"
    May 2026:  total=1000.00, count=1, top_category="Shopping"
    """
    # Register and log in.
    client.post("/register", data={
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "testpass1",
    })
    client.post("/login", data={
        "email": "testuser@example.com",
        "password": "testpass1",
    })

    # Seed expenses directly via get_db so there is no dependency on add_expense.
    db = db_module.get_db()
    user_id = db.execute(
        "SELECT id FROM users WHERE email = ?", ("testuser@example.com",)
    ).fetchone()["id"]

    db.executemany(
        "INSERT INTO expenses (user_id, title, amount, category, date) VALUES (?, ?, ?, ?, ?)",
        [
            (user_id, "Lunch",  500.00, "Food & Dining", "2026-01-10"),
            (user_id, "Bus",    200.00, "Transport",     "2026-01-20"),
            (user_id, "Shoes", 1000.00, "Shopping",      "2026-05-05"),
        ],
    )
    db.commit()
    db.close()

    return client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get(client, path, **query):
    """Build a query string from keyword arguments and issue a GET."""
    if query:
        qs = "&".join(f"{k}={v}" for k, v in query.items())
        path = f"{path}?{qs}"
    return client.get(path, follow_redirects=False)


# ---------------------------------------------------------------------------
# 1. Profile page renders the spending summary card for a logged-in user
# ---------------------------------------------------------------------------

class TestSpendingSummaryCardRendered:
    def test_spending_summary_card_heading_present(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        assert b"Spending summary" in response.data, (
            "Expected 'Spending summary' card heading on the profile page"
        )

    def test_filter_form_inputs_present(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        # The filter form must have start_date and end_date inputs.
        assert b'name="start_date"' in response.data, (
            "Expected start_date input in the spending summary filter form"
        )
        assert b'name="end_date"' in response.data, (
            "Expected end_date input in the spending summary filter form"
        )


# ---------------------------------------------------------------------------
# 2. No filter active — all-time stats shown in chips
# ---------------------------------------------------------------------------

class TestNoFilterAllTimeStats:
    def test_all_time_total_shown(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        # All-time total is 500 + 200 + 1000 = 1700.00.
        assert b"1700.00" in response.data, (
            "Expected all-time total of 1700.00 in stat chips when no filter is active"
        )

    def test_all_time_count_shown(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        # All-time count is 3.
        assert b"3" in response.data, (
            "Expected all-time expense count of 3 when no filter is active"
        )

    def test_all_time_top_category_shown(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        # Shopping has the highest all-time sum (1000 > 500 > 200).
        assert b"Shopping" in response.data, (
            "Expected top category 'Shopping' when no filter is active"
        )

    def test_no_filtered_badge_without_filter(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        # "Filtered:" badge must NOT appear when no date range is active.
        assert b"Filtered:" not in response.data, (
            "Filtered badge must not appear when no date filter is active"
        )

    def test_no_filter_error_shown_without_filter(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        assert b"auth-error" not in response.data, (
            "No error message should be shown when no filter params are provided"
        )


# ---------------------------------------------------------------------------
# 3. Valid date range — chips update to show filtered period totals
# ---------------------------------------------------------------------------

class TestValidDateRangeStats:
    def test_filtered_total_for_jan_2026(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        # Jan 2026: 500.00 + 200.00 = 700.00
        assert b"700.00" in response.data, (
            "Expected filtered total of 700.00 for January 2026"
        )

    def test_filtered_count_for_jan_2026(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        # Jan 2026 has 2 expenses.
        assert b"2" in response.data, (
            "Expected filtered expense count of 2 for January 2026"
        )

    def test_filtered_top_category_for_jan_2026(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        # Jan 2026 top category is Food & Dining (500 > 200 for Transport).
        assert b"Food" in response.data, (
            "Expected top category 'Food & Dining' for January 2026 filter"
        )

    def test_filtered_total_for_may_2026(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-05-01", end_date="2026-05-31")
        assert response.status_code == 200
        # May 2026: 1000.00
        assert b"1000.00" in response.data, (
            "Expected filtered total of 1000.00 for May 2026"
        )

    def test_alltime_total_not_shown_when_filtered(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        # The all-time total of 1700.00 must not appear in the stat chips when filtered.
        assert b"1700.00" not in response.data, (
            "All-time total 1700.00 must not appear in chips when a date filter is active"
        )

    def test_no_filter_error_on_valid_range(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"auth-error" not in response.data, (
            "No error should be shown for a valid date range"
        )


# ---------------------------------------------------------------------------
# 4. "Filtered: start → end" badge visible when date range is active
# ---------------------------------------------------------------------------

class TestFilteredBadge:
    def test_filtered_badge_shown_when_range_active(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"Filtered:" in response.data, (
            "Expected 'Filtered:' badge to appear when a valid date range is active"
        )

    def test_filtered_badge_contains_start_date(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"2026-01-01" in response.data, (
            "Filtered badge must include the start date"
        )

    def test_filtered_badge_contains_end_date(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"2026-01-31" in response.data, (
            "Filtered badge must include the end date"
        )

    def test_filtered_badge_absent_without_filter(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        assert b"Filtered:" not in response.data, (
            "Filtered badge must not appear when no date filter is set"
        )


# ---------------------------------------------------------------------------
# 5. Date inputs pre-populated with submitted filter values
# ---------------------------------------------------------------------------

class TestDateInputsPrePopulated:
    def test_start_date_prepopulated(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"2026-01-01" in response.data, (
            "start_date input must be pre-populated with the submitted value"
        )

    def test_end_date_prepopulated(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"2026-01-31" in response.data, (
            "end_date input must be pre-populated with the submitted value"
        )

    def test_dates_prepopulated_even_on_filter_error(self, auth_client):
        # When only start_date is provided (error state), the value must still be
        # echoed back into the input so the user does not lose their entry.
        response = _get(auth_client, "/profile", start_date="2026-01-01")
        assert response.status_code == 200
        assert b"2026-01-01" in response.data, (
            "start_date must be echoed back into the form even when filter_error is set"
        )


# ---------------------------------------------------------------------------
# 6. Only start date provided — filter_error shown, chips hidden
# ---------------------------------------------------------------------------

class TestOnlyStartDateProvided:
    def test_filter_error_shown(self, auth_client):
        response = _get(auth_client, "/profile", start_date="2026-01-01")
        assert response.status_code == 200
        assert b"auth-error" in response.data, (
            "Expected error element when only start_date is provided"
        )

    def test_error_message_text(self, auth_client):
        response = _get(auth_client, "/profile", start_date="2026-01-01")
        assert response.status_code == 200
        assert b"both" in response.data.lower() or b"start and end" in response.data.lower(), (
            "Error message must mention that both dates are required"
        )

    def test_stat_chips_hidden_on_error(self, auth_client):
        response = _get(auth_client, "/profile", start_date="2026-01-01")
        assert response.status_code == 200
        # When filter_error is set, the all-time total (1700.00) must NOT appear
        # in the stat chips section — chips are hidden.
        assert b"1700.00" not in response.data, (
            "Stat chips must be hidden when filter_error is set (only start_date provided)"
        )

    def test_filtered_badge_absent_on_error(self, auth_client):
        response = _get(auth_client, "/profile", start_date="2026-01-01")
        assert response.status_code == 200
        assert b"Filtered:" not in response.data, (
            "Filtered badge must not appear when filter_error is set"
        )


# ---------------------------------------------------------------------------
# 7. Only end date provided — filter_error shown, chips hidden
# ---------------------------------------------------------------------------

class TestOnlyEndDateProvided:
    def test_filter_error_shown(self, auth_client):
        response = _get(auth_client, "/profile", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"auth-error" in response.data, (
            "Expected error element when only end_date is provided"
        )

    def test_error_message_text(self, auth_client):
        response = _get(auth_client, "/profile", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"both" in response.data.lower() or b"start and end" in response.data.lower(), (
            "Error message must mention that both dates are required"
        )

    def test_stat_chips_hidden_on_error(self, auth_client):
        response = _get(auth_client, "/profile", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"1700.00" not in response.data, (
            "Stat chips must be hidden when filter_error is set (only end_date provided)"
        )

    def test_end_date_value_echoed_back(self, auth_client):
        response = _get(auth_client, "/profile", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"2026-01-31" in response.data, (
            "end_date value must be echoed back into the form even on error"
        )


# ---------------------------------------------------------------------------
# 8. Start date after end date — filter_error shown, chips hidden
# ---------------------------------------------------------------------------

class TestStartDateAfterEndDate:
    def test_filter_error_shown(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-31", end_date="2026-01-01")
        assert response.status_code == 200
        assert b"auth-error" in response.data, (
            "Expected error element when start_date is after end_date"
        )

    def test_error_message_text(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-31", end_date="2026-01-01")
        assert response.status_code == 200
        assert b"on or before" in response.data.lower() or b"start date" in response.data.lower(), (
            "Error message must indicate that start date must be on or before end date"
        )

    def test_stat_chips_hidden_on_error(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-31", end_date="2026-01-01")
        assert response.status_code == 200
        assert b"1700.00" not in response.data, (
            "Stat chips must be hidden when start_date is after end_date"
        )

    def test_filtered_badge_absent_on_error(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-31", end_date="2026-01-01")
        assert response.status_code == 200
        assert b"Filtered:" not in response.data, (
            "Filtered badge must not appear when start_date > end_date"
        )

    def test_dates_echoed_back_on_error(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-31", end_date="2026-01-01")
        assert response.status_code == 200
        assert b"2026-01-31" in response.data and b"2026-01-01" in response.data, (
            "Both date values must be echoed into form inputs even when start > end"
        )


# ---------------------------------------------------------------------------
# 9. Date range with no matching expenses — ₹0.00, 0 expenses, "—" top category
# ---------------------------------------------------------------------------

class TestEmptyDateRange:
    def test_zero_total_for_empty_range(self, auth_client):
        # March 2026 has no seeded expenses.
        response = _get(auth_client, "/profile",
                        start_date="2026-03-01", end_date="2026-03-31")
        assert response.status_code == 200
        assert b"0.00" in response.data, (
            "Expected ₹0.00 total when no expenses exist in the filtered range"
        )

    def test_zero_count_for_empty_range(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-03-01", end_date="2026-03-31")
        assert response.status_code == 200
        # The count chip must show 0.
        assert b"0" in response.data, (
            "Expected expense count of 0 when no expenses match the date range"
        )

    def test_dash_top_category_for_empty_range(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-03-01", end_date="2026-03-31")
        assert response.status_code == 200
        # Top category must render as "—" when there are no matching expenses.
        assert "—".encode() in response.data or b"&mdash;" in response.data, (
            "Expected '—' for top category when no expenses match the date range"
        )

    def test_no_filter_error_for_valid_empty_range(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-03-01", end_date="2026-03-31")
        assert response.status_code == 200
        assert b"auth-error" not in response.data, (
            "A valid date range with no matching rows must not trigger a filter error"
        )

    def test_filtered_badge_shown_for_valid_empty_range(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-03-01", end_date="2026-03-31")
        assert response.status_code == 200
        assert b"Filtered:" in response.data, (
            "Filtered badge must appear even when the matching range is empty"
        )


# ---------------------------------------------------------------------------
# 10. Clear filter (both params absent) returns to all-time stats
# ---------------------------------------------------------------------------

class TestClearFilter:
    def test_all_time_total_after_clear(self, auth_client):
        # First, apply a filter.
        _get(auth_client, "/profile", start_date="2026-01-01", end_date="2026-01-31")
        # Then request the page with no filter params.
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        assert b"1700.00" in response.data, (
            "All-time total must be shown when no filter params are present"
        )

    def test_no_filtered_badge_after_clear(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        assert b"Filtered:" not in response.data, (
            "Filtered badge must not appear when no filter params are present"
        )

    def test_all_time_count_after_clear(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        assert b"3" in response.data, (
            "All-time expense count of 3 must appear when no filter is active"
        )


# ---------------------------------------------------------------------------
# 11. Existing profile cards are unaffected
# ---------------------------------------------------------------------------

class TestExistingProfileCardsUnaffected:
    def test_account_info_card_present_no_filter(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        # The account info card must still render.
        assert b"Account info" in response.data or b"account" in response.data.lower(), (
            "Account info card must still appear on the profile page"
        )

    def test_change_password_card_present_no_filter(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        assert b"password" in response.data.lower(), (
            "Change password card must still appear on the profile page"
        )

    def test_danger_zone_card_present_no_filter(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        assert b"danger" in response.data.lower() or b"delete" in response.data.lower(), (
            "Danger zone / delete account section must still appear on the profile page"
        )

    def test_account_info_card_present_with_filter(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"Account info" in response.data or b"account" in response.data.lower(), (
            "Account info card must still appear when a date filter is active"
        )

    def test_change_password_card_present_with_filter(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"password" in response.data.lower(), (
            "Change password card must still appear when a date filter is active"
        )

    def test_danger_zone_present_with_filter(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"danger" in response.data.lower() or b"delete" in response.data.lower(), (
            "Danger zone must still appear when a date filter is active"
        )

    def test_user_name_pre_filled_in_account_info(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        assert b"Test User" in response.data, (
            "User name must be pre-filled in the account info form"
        )

    def test_user_email_pre_filled_in_account_info(self, auth_client):
        response = _get(auth_client, "/profile")
        assert response.status_code == 200
        assert b"testuser@example.com" in response.data, (
            "User email must be pre-filled in the account info form"
        )


# ---------------------------------------------------------------------------
# 12. Unauthenticated request with date params still redirects to /login
# ---------------------------------------------------------------------------

class TestUnauthenticatedAccess:
    def test_redirect_to_login_without_params(self, client):
        response = _get(client, "/profile")
        assert response.status_code == 302, (
            "Unauthenticated GET /profile must redirect (302)"
        )
        assert "/login" in response.headers.get("Location", ""), (
            "Unauthenticated GET /profile must redirect to /login"
        )

    def test_redirect_to_login_with_date_params(self, client):
        response = _get(client, "/profile",
                        start_date="2026-01-01", end_date="2026-01-31")
        assert response.status_code == 302, (
            "Unauthenticated GET /profile?start_date=...&end_date=... must redirect (302)"
        )
        assert "/login" in response.headers.get("Location", ""), (
            "Redirect target must be /login even when date params are present"
        )

    def test_redirect_to_login_with_only_start_date(self, client):
        response = _get(client, "/profile", start_date="2026-01-01")
        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", ""), (
            "Unauthenticated request with only start_date must redirect to /login"
        )


# ---------------------------------------------------------------------------
# Additional edge-case tests for invalid date formats
# ---------------------------------------------------------------------------

class TestInvalidDateFormat:
    def test_invalid_start_date_format_shows_error(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="not-a-date", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"auth-error" in response.data, (
            "Expected filter_error for an invalid start_date format"
        )

    def test_invalid_end_date_format_shows_error(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="2026-01-01", end_date="31/01/2026")
        assert response.status_code == 200
        assert b"auth-error" in response.data, (
            "Expected filter_error for an end_date in a non-ISO format"
        )

    def test_invalid_format_error_message_text(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="not-a-date", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"Invalid date format" in response.data or b"date" in response.data.lower(), (
            "Error message must reference invalid date format"
        )

    def test_stat_chips_hidden_on_format_error(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="not-a-date", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"1700.00" not in response.data, (
            "Stat chips must be hidden when the date format is invalid"
        )

    def test_no_filtered_badge_on_format_error(self, auth_client):
        response = _get(auth_client, "/profile",
                        start_date="not-a-date", end_date="2026-01-31")
        assert response.status_code == 200
        assert b"Filtered:" not in response.data, (
            "Filtered badge must not appear when the date format is invalid"
        )


# ---------------------------------------------------------------------------
# Parametrized: all single-date-only combinations trigger the same error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("params,description", [
    ({"start_date": "2026-01-01"}, "only start_date"),
    ({"end_date": "2026-01-31"},   "only end_date"),
])
def test_single_date_always_errors(auth_client, params, description):
    path = "/profile?" + "&".join(f"{k}={v}" for k, v in params.items())
    response = auth_client.get(path, follow_redirects=False)
    assert response.status_code == 200, f"Expected 200 for {description}"
    assert b"auth-error" in response.data, (
        f"Expected filter_error element for {description}"
    )


# ---------------------------------------------------------------------------
# Parametrize: start_date > end_date — various reversed pairs all error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("start,end", [
    ("2026-06-01", "2026-01-01"),
    ("2026-12-31", "2026-01-01"),
    ("2026-01-02", "2026-01-01"),
])
def test_start_after_end_always_errors(auth_client, start, end):
    path = f"/profile?start_date={start}&end_date={end}"
    response = auth_client.get(path, follow_redirects=False)
    assert response.status_code == 200
    assert b"auth-error" in response.data, (
        f"Expected filter_error when start={start} is after end={end}"
    )


# ---------------------------------------------------------------------------
# Boundary: same start and end date (single-day range)
# ---------------------------------------------------------------------------

class TestSingleDayRange:
    def test_single_day_range_valid_with_matching_expense(self, auth_client):
        # 2026-01-10 has "Lunch" 500.00.
        response = _get(auth_client, "/profile",
                        start_date="2026-01-10", end_date="2026-01-10")
        assert response.status_code == 200
        assert b"auth-error" not in response.data, (
            "Single-day range (start == end) is valid and must not error"
        )
        assert b"500.00" in response.data, (
            "Expected 500.00 for the single-day range 2026-01-10"
        )

    def test_single_day_range_with_no_matching_expense(self, auth_client):
        # 2026-02-15 has no seeded expenses.
        response = _get(auth_client, "/profile",
                        start_date="2026-02-15", end_date="2026-02-15")
        assert response.status_code == 200
        assert b"auth-error" not in response.data, (
            "Single-day range with no expenses must not produce a filter error"
        )
        assert b"0.00" in response.data, (
            "Expected ₹0.00 for a single-day range with no matching expenses"
        )
