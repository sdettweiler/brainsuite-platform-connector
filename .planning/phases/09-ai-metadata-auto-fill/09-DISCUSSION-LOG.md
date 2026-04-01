# Phase 9: AI Metadata Auto-Fill - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01

---

## Areas Discussed

User selected: Auto-fill button & dialog layout, Confidence indicators & field distinction, User confirmation flow, Whisper optionality & retry on FAILED

---

## Area 1: Auto-fill button & dialog layout

**Q: Where does the Auto-fill feature live in the asset detail dialog?**

Options presented: New 'Metadata' tab (Recommended), Inside CE tab, Dialog header area

**User:** "The autofill features are mostly related to the metadata fields which are used for scoring. Therefore, autofill configuration needs to live within the meta data field section. By default, I want to have asset language to be autofilled, as well as brand names, same for voice over language and voice over itself. For project name and asset name, I want us to directly use the campaign respectively ad name. And the asset stage will always be final."

**Clarification Q: Per-asset in dialog, bulk from config page, or both?**

**User:** "It's configured in the config page, but only runs upon scoring. If auto-fill for a metadata field is enabled, we'll try to auto-fill the field via AI, store the value on asset level and trigger the job. Also make sure that account level value/defaults get populated to the asset level. Auto-fill might overwrite those. Provided default values are serving as fallback if auto-fill fails."

**Decision captured:** Auto-fill is pipeline-integrated (not a dialog button). `auto_fill_enabled` toggle per `MetadataField`, configured in the metadata config page. Runs during scoring. Default values propagate and serve as fallback.

---

## Area 2: Confidence indicators & field distinction

**Q: Do we track/store confidence scores at all?**

Options presented: Skip confidence entirely, Store internally, Store and show in asset detail

**User selected:** Skip confidence entirely

**Q: Which fields run through Claude AI?**

Options presented: Language/Market, Brand Names, Voice Over (yes/no), Voice Over Language

**User selected all 4, with notes:** "only detect Language, no market. for voice over grab the entire transcript not just yes/no"

**Decision captured:** No confidence tracking. AI fields: Language (not market), Brand Names, VO transcript (full text), VO Language. All via OpenAI.

---

## Area 3: User confirmation flow

(Captured via the dialog layout discussion above)

**User:** "No — auto-apply immediately. But the user can overwrite afterwards, which would trigger a rescoring. But make sure you only reset to UNSCORED vs trigger the scoring immediately as the user might need to overwrite multiple values and we want to minimize the amount of rescores."

**Decision captured:** No review step — auto-apply directly. Post-edit resets to UNSCORED (not immediate rescore).

---

## Area 4: Whisper optionality & retry on FAILED

**Q: What happens if OPENAI_API_KEY is not configured?**

Options presented: Degrade gracefully — Claude-only (Recommended), Skip all AI inference, Block scoring if absent

**User:** "Like 1, but use openAI as the default model for all auto-detection"

**Q: Can auto-fill be retried on FAILED assets?**

Options presented: Yes — retry on next scoring run (Recommended), No — FAILED is terminal

**User selected:** Yes — retry on next scoring run

**Decision captured:** OpenAI for all AI inference (not Claude). Graceful degradation if `OPENAI_API_KEY` absent. FAILED status retried automatically on next scoring run.

---

## Alternatives Considered

| Area | Alternative | Why Not Chosen |
|------|-------------|----------------|
| Dialog layout | Auto-fill button in asset detail dialog (original AI-04) | Superseded by pipeline-integration design — auto-fill is a background process, not a user action |
| Confirmation | Review step with per-field accept/reject | User prefers direct auto-apply; manual overwrite is the correction mechanism |
| Confidence | Store internally for logging | User chose to skip entirely — simpler pipeline |
| AI provider | Claude API (original PROJECT.md constraint) | User explicitly switched to OpenAI for all inference |

