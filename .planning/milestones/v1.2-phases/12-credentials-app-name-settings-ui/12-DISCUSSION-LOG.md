# Phase 12: Discussion Log

**Session:** 2026-04-16
**Mode:** Interactive discuss-phase

---

## Area 1 — Settings Page Placement

**Q: How should the BrainSuite configuration section live in the Settings page?**
Options: New nav tab / Section in existing Brainsuite Apps page
→ **Section in existing Brainsuite Apps page**

**Q: Should the credentials form be above or below the existing Apps list?**
Options: Above / Below
→ **Above, but auto-collapsed once filled and tested/verified**

**[Revised mid-session]**

**Q: Where does the app name value live in the data model?**
Options: Still on OrgBrainsuiteConfig (one per org) / Moves to each BrainsuiteApp row
→ **Moves to each BrainsuiteApp row** — column: `system_app_name`. Each org has at least 2 apps (video and image), more possible in future.

**Q: What does the expanded section look like on each app row?**
Options: Accordion (chevron expands inline) / Edit form replaces row
→ **Accordion — chevron expands inline**

**Q: What should the column be called on the brainsuite_apps table?**
Options: system_app_name / api_app_name
→ **system_app_name**

**Q: Should Phase 12 own the cleanup migration (drop OrgBrainsuiteConfig.video_app_name / static_app_name)?**
Options: Phase 12 owns the cleanup / Leave Phase 11 columns in place
→ **Phase 12 owns the cleanup**

---

## Area 2 — Client Secret UX

**Q: When a Client Secret is already saved, how should the field behave?**
Options: Placeholder + re-enter to change / Standard password input
→ **Placeholder + re-enter to change** (shows `●●●●●●●● (saved)`, "Change" button to enter edit mode)

**Q: When the user cancels out of edit mode, what happens?**
Options: Revert to placeholder state / Keep cleared until save
→ **Revert to placeholder state** (stored secret unchanged)

---

## Area 3 — Test Connection Feedback

**Q: How should Test Connection success/failure display inline?**
Options: Status block below button / Toast notification only
→ **Status block below button** — green/red, persists until next test, spinner during request

**Q: What does Test Connection actually do on the backend?**
Options: Auth token request / You decide
→ **Auth token request** (POST to BrainSuite auth endpoint using stored credentials)

**Q: Should the button be disabled until credentials are saved?**
Options: Disabled until saved / Tests live form values
→ **Disabled until saved**

---

## Area 4 — Re-score Prompt Design

**Q: When should the re-score prompt appear?**
Options: Only when credentials or app names actually changed / Always if scored assets exist
→ **Only when credentials or app names actually changed**

**Q: What format should the re-score prompt take?**
Options: MatDialog / Inline warning panel
→ **MatDialog** (two buttons: "Keep existing scores" / "Re-score all assets")

**Q: If user chooses re-score all, what happens?**
Options: Reset to UNSCORED + toast / Immediate background re-score
→ **Reset to UNSCORED + toast** ("Assets queued for re-scoring")

---

*Discussion log: 2026-04-16*
