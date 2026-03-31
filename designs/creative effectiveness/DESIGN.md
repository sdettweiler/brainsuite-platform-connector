# Design System Strategy: The Cinematic Analyst

## 1. Overview & Creative North Star
The "Cinematic Analyst" is our creative north star. For a state-of-the-art video analytics platform, the UI must not merely display data; it must curate it with the precision of a film editor and the authority of a high-end editorial journal. 

We break the "SaaS Template" look by rejecting the rigid, boxy grids of the past decade. Instead, we utilize **Intentional Asymmetry** and **Tonal Depth**. By overlapping video preview elements with floating data glassmorphism and using high-contrast typography scales (Manrope for cinematic impact, Inter for analytical precision), we create a workspace that feels like a premium production suite. The interface breathes through expansive white space, allowing complex heatmaps and donut charts to stand out as the heroes of the experience.

---

## 2. Colors & Surface Philosophy
The palette is rooted in a "Deep Charcoal" ecosystem, designed to make video content and vibrant KPIs pop with "OLED-grade" contrast.

*   **Primary Identity:** We use `primary` (#a3a6ff) and its variants (`primary_dim` #6063ee) to signify intelligence and action. Use these for high-intent CTAs and active analytical states.
*   **Semantic Intelligence:** Success (`secondary` #6bff8f), Warning (`tertiary` #ffb148), and Critical (`error` #ff6e84) are reserved strictly for data storytelling.
*   **The "No-Line" Rule:** We do not use 1px solid borders to section content. Boundaries are defined exclusively by shifts in background tokens. For example, a `surface_container_low` sidebar sits against a `surface` background. The eye perceives the edge through the shift in value, not a stroke.
*   **Surface Hierarchy & Nesting:** Treat the UI as layers of physical material. 
    *   **Level 0 (Base):** `surface` (#0e0e0e)
    *   **Level 1 (Sections):** `surface_container_low` (#131313)
    *   **Level 2 (Cards/Modules):** `surface_container` (#1a1a1a)
    *   **Level 3 (Interactive/Pop-overs):** `surface_container_high` (#20201f)
*   **The "Glass & Gradient" Rule:** For overlays (video taggers, lightbox insights), use `surface_variant` (#262626) with a 60% opacity and a `20px` backdrop-blur. Apply a subtle linear gradient from `primary` to `primary_container` on primary actions to give them a "lit-from-within" soul.

---

## 3. Typography: Editorial Precision
We utilize a dual-typeface system to balance brand character with high-density data readability.

*   **Display & Headlines (Manrope):** Use `display-lg` through `headline-sm` for high-level insights and page titles. Manrope’s geometric nature feels "engineered" yet premium. Use wide tracking (-0.02em) for a more cinematic, professional feel.
*   **Functional & Data (Inter):** Use `title-md` through `label-sm` for all numerical data, labels, and UI controls. Inter is chosen for its exceptional legibility in small-scale analytics and multi-digit values.
*   **Hierarchy Note:** Always pair a large `display-md` metric with a `label-md` uppercase tag. The contrast in scale communicates immediate importance.

---

## 4. Elevation & Depth: Tonal Layering
Traditional shadows are a fallback, not a foundation. We achieve depth through the **Layering Principle**.

*   **Tonal Stacking:** A `surface_container_highest` card placed on a `surface_dim` background creates a natural lift.
*   **Ambient Shadows:** For floating elements (Modals/Dropdowns), use an ultra-diffused shadow: `0px 24px 48px rgba(0, 0, 0, 0.5)`. The shadow must feel like ambient light occlusion, not a dark glow.
*   **The "Ghost Border" Fallback:** If accessibility requires a container edge, use the `outline_variant` token at 15% opacity. This creates a "whisper" of a line that defines space without cluttering the visual field.
*   **Glassmorphism:** Use semi-transparent surfaces for "Floating Insights" that hover over video playback. This ensures the user never loses context of the creative content being analyzed.

---

## 5. Component Logic

### Buttons & Controls
*   **Primary:** A vibrant gradient of `primary` to `primary_dim`. Roundedness: `md` (0.75rem). No border.
*   **Secondary:** Ghost style. No background, `outline` token at 20% opacity. On hover, transition to `surface_container_highest`.
*   **Chips:** Use `surface_container_high` for inactive filters. Active filters should use `secondary_container` with `on_secondary_container` text for a "vibrant success" feel.

### Data Visualization
*   **Charts:** Forbid solid lines. Use `secondary` (#6bff8f) for growth metrics with a `2px` stroke and a soft glow effect (drop-shadow with the same color at 20% opacity).
*   **Heatmaps:** Use semi-transparent overlays on video frames using the `error`, `tertiary`, and `secondary` tokens with 40% opacity.
*   **Donuts:** Use a "Thick-to-Thin" stroke ratio to emphasize the primary data point.

### Content Containers (Cards)
*   **The "Anti-Divider" Rule:** Never use a horizontal line to separate content within a card. Use the Spacing Scale (e.g., `8` (2rem) or `10` (2.5rem)) or a subtle shift to `surface_container_low` for the card footer.

### Video Analytics Specifics
*   **Timeline Scrubber:** A sleek `primary_fixed` track with a `secondary` playhead to indicate "Success/Effective" zones of the video.
*   **AI Insight Tags:** High-quality icons (Brain, Eye) should be paired with `label-md` text, nested in a `surface_variant` glass capsule.

---

## 6. Do’s and Don’ts

### Do:
*   **Do** use intentional asymmetry. Align a large KPI to the left and a detailed line graph to the right with generous `spacing-12` between them.
*   **Do** use `surface_bright` sparingly to highlight "Active" or "Live" analytical streams.
*   **Do** ensure all numerical data uses tabular-nums (monospaced numbers) for alignment in tables.

### Don't:
*   **Don't** use 100% black (#000000) for backgrounds; it kills the premium "charcoal" depth. Use `surface` (#0e0e0e).
*   **Don't** use high-contrast borders. If a boundary isn't clear through color shifts, your layout needs more white space, not more lines.
*   **Don't** use standard "drop shadows" on cards sitting on the base surface. Only "floating" objects (modals/tooltips) get shadows.