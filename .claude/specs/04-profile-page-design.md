# Spec: Profile Page Design

## Overview
Redesign the profile page with a modern, polished layout that feels cohesive with the rest of Spendly's design language. The current page reuses `.auth-card` (built for login/register forms) and arranges two equal-width columns side by side — a layout that doesn't reflect the visual hierarchy of a settings page. This step replaces that with a full-width stacked layout featuring an avatar initials block, dedicated profile-card components, improved stats display, and a more restrained danger zone. No backend logic changes — all routes, form actions, and session handling remain identical.

## Depends on
Step 01 — Database Setup (users table must exist)  
Step 02 — Registration (user accounts must exist)  
Step 03 — Login and Logout (session auth required to reach `/profile`)

## Routes
No new routes. `/profile` (GET + POST) already exists and is unchanged.

## Database changes
No database changes.

## Templates

- **Modify:** `templates/profile.html`
  - Replace 2-column `.profile-grid` with a full-width stacked layout
  - Add an avatar block at the top: a circle showing the user's initials (first letter of name, uppercase), with `--accent` background and white text
  - Render `user.name` and `user.email` as read-only display fields below the avatar (distinct from the editable form fields inside the cards)
  - Replace `.auth-card` with a new `.profile-card` component for Account info and Change password sections — each card gets a thin left accent border (`--accent`) and a section icon or label
  - Remove the old `.profile-header` / `.profile-title` / `.profile-subtitle` block — the avatar block replaces it
  - Move member-since and expense-count into a `.profile-stats-row` of two `.profile-stat-chip` pills, shown directly below the avatar block
  - Danger zone: keep the red border card but wrap it in a collapsible `<details>` element so it's visually tucked away by default; the `<summary>` reads "Delete account"
  - Remove the "← Back to dashboard" text link from `.profile-meta`; the navbar already has a Dashboard link

- **Modify:** `templates/base.html`
  - No structural changes. Verify the navbar already links to `/profile` for the logged-in user name (it should from step 03).

## Files to change

- `templates/profile.html` — full template rewrite (structure only; form fields, names, actions, hidden inputs unchanged)
- `static/css/style.css` — replace the existing profile CSS block with new classes; add `.profile-avatar`, `.profile-avatar-initials`, `.profile-stats-row`, `.profile-stat-chip`, `.profile-card`, `.profile-card-label`, `.profile-card-icon`; keep `.danger-zone`, `.danger-zone-title`, `.danger-zone-card`, `.danger-zone-desc`; remove `.profile-grid`, `.profile-header`, `.profile-title`, `.profile-subtitle`, `.profile-meta`

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values (the one existing violation `border-color: #f5c6c2` on `.danger-zone-card` must be replaced with `var(--danger-light)`)
- All templates extend `base.html`
- Avatar initials: take `user.name | first | upper` in Jinja2 — no JS required
- The `<details>`/`<summary>` danger zone must still show `delete_error` when it exists; if an error is present, render the `<details>` with the `open` attribute so the user sees the error without having to re-expand
- Form field `name`, `id`, and `action` attributes must not change — backend handles them as-is
- `.profile-card` must not reuse `.auth-card`; write independent CSS so future changes to auth forms don't bleed into profile
- Keep all existing CSS classes that are referenced in the test suite (`.danger-zone`, `.danger-zone-card`, `.danger-zone-desc`, `.danger-zone-title`, `.btn-danger-submit`)
- Page max-width stays at `760px` (set on `.profile-inner`)
- Responsive: on `≤ 640 px`, `.profile-stats-row` stacks vertically

## Definition of done

- [ ] GET `/profile` renders an avatar circle with the user's initials (first letter, uppercase) on an accent-coloured background
- [ ] User name and email displayed as static read-only text directly below the avatar
- [ ] Two stat chips visible below the avatar: "Member since YYYY-MM-DD" and "N expenses tracked"
- [ ] Account info form (name, email, Save changes) is inside a `.profile-card` with a visible left accent border — not inside `.auth-card`
- [ ] Change password form (current, new, confirm, Update password) is inside a separate `.profile-card` with a visible left accent border
- [ ] Both forms still submit correctly and show errors / success toasts as before
- [ ] Danger zone is wrapped in a `<details>` element; by default it is collapsed (no `open` attribute)
- [ ] When `delete_error` is present the danger zone `<details>` renders with `open` attribute so the error is visible
- [ ] Delete account form still works: wrong password shows error, correct password deletes account and redirects to `/`
- [ ] `--danger-light` CSS variable used for the danger zone card border (no hardcoded hex)
- [ ] No `.auth-card` class appears in `profile.html`
- [ ] Page remains usable at mobile widths (≤ 640 px): stat chips stack, cards full-width
- [ ] "← Back to dashboard" text link is removed from the page footer area
