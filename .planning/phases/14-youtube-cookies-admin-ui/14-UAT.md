---
status: complete
phase: 14-youtube-cookies-admin-ui
source: [14-01-SUMMARY.md, 14-02-SUMMARY.md, 14-03-SUMMARY.md]
started: 2026-04-27T00:00:00Z
updated: 2026-04-27T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Clear ephemeral state (temp DBs, caches, lock files). Start the application from scratch. Server boots without errors, the Phase 14 Alembic migration (x6y7z8a9b0c — creates system_config table, inserts singleton row) completes without error, and the frontend loads and reaches the login screen.
result: skipped
reason: Cold start would destroy existing data — skipped per user instruction; always flag before including

### 2. Admin Nav Visible for SuperAdmin
expected: Log in as a SuperAdmin user. Navigate to the Configuration section. The left sidebar shows an "Admin" nav item (with a shield-lock icon) below the existing nav items (Organization, Metadata, Platforms, BrainSuite Apps).
result: pass

### 3. Admin Nav Hidden for Regular User
expected: Log in as a regular (non-SuperAdmin) user. Navigate to the Configuration section. The left sidebar does NOT contain an "Admin" nav item — only the standard four items appear.
result: skipped
reason: no other user accounts available to test with

### 4. Route Guard Redirect
expected: While logged in as a non-SuperAdmin, navigate directly to /configuration/admin in the browser URL bar. You are immediately redirected away (to / or the dashboard) and never see the Admin page content.
result: skipped
reason: no other user accounts available to test with

### 5. YouTube Cookie Health Display
expected: As SuperAdmin, navigate to Configuration > Admin. The "YouTube Cookies" section loads and shows two slots (Primary and Backup). Each slot shows either a masked display (••••) with a "Replace" button if a cookie is stored, or an "Add Cookie" button if no cookie is set. A loading skeleton is visible briefly before data loads.
result: pass

### 6. Cookie Replace / Save Flow
expected: Click "Replace" (or "Add Cookie") on one slot. A textarea appears. Paste a cookie string and click Save. The spinner appears briefly. On success the textarea closes and the health display updates to show the new status (valid/expired). The cookie content is NOT visible anywhere in the UI after saving.
result: pass

### 7. SuperAdmin Users List
expected: The "SuperAdmin Management" section on the Admin page shows a table listing all current SuperAdmin users (email, name, joined date). Your own account appears in the list.
result: pass

### 8. Promote User to SuperAdmin
expected: In the "Promote" input field, type the email of a non-SuperAdmin user and click "Promote to SuperAdmin". On success the user appears in the SuperAdmin table. If the email doesn't exist, you see "No user found with that email address." If already a SuperAdmin, you see "This user is already a SuperAdmin."
result: pass

### 9. Organizations List
expected: The "Organizations" section on the Admin page shows a read-only table with org name, slug (monospace), active user count, and created date. The list reflects the actual orgs in the system.
result: pass

### 10. COOKIE_FAILED Notification Routing
expected: When a video download fails due to cookie exhaustion, a bell notification of type COOKIE_FAILED appears in the notification bell. Clicking the toast action ("Fix Now") or clicking the notification item in the bell popover navigates you to /configuration/admin. The notification icon is a key icon with the "rejected" color class.
result: skipped
reason: requires triggering a failed cookie download to test

## Summary

total: 10
passed: 6
issues: 0
pending: 0
skipped: 4
blocked: 0

## Gaps

[none yet]
