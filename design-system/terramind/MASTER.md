# TerraMind — Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/terramind/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file. If not, follow the rules below.

**Project:** TerraMind — AI Agriculture Intelligence Platform
**Category:** Agriculture / Farm Tech (advisory tool + conversational AI)
**Design Dials:** Variance 6/10 (Balanced/Modern) · Motion 6/10 (Standard) · Density 4/10 (Standard)
**Audience:** Farmers and agronomists. Largely non-technical, frequently on mid-range Android phones, often outdoors in bright daylight.

> **Note on generation.** `--design-system` initially resolved this project to *AI-Native UI* (purple `#7C3AED` + pink `#EC4899`, Fira Code) because the query contained "AI/intelligence". That is wrong for an agriculture product and wrong for a non-technical audience. This file is the corrected system, sourced from direct domain queries: `--domain color "agriculture organic natural..."` → **Agriculture/Farm Tech**, `--domain style` → **Organic Biophilic**, `--domain typography` → **Friendly SaaS**. Do not regenerate with `--persist --force` without re-applying these corrections.

---

## 1. Color Tokens

All colors are HSL triplets in CSS variables so Tailwind can apply opacity modifiers (`bg-primary/10`).
Every pair below was validated with a WCAG contrast script; ratios are recorded in §1.3.

### 1.1 Light (default)

| Role | Hex | Notes |
|------|-----|-------|
| `--background` | `#FCF8F3` | Warm ivory — app canvas |
| `--foreground` | `#3B2517` | Dark umber — body text |
| `--card` | `#FFFFFF` | Clean white surfaces |
| `--card-foreground` | `#3B2517` |  |
| `--primary` | `#8E4D10` | Field ochre (hue 29 = measured footage) — primary actions |
| `--primary-foreground` | `#FFFFFF` |  |
| `--secondary` | `#196B3B` | Crop green — **health signal only** (success, high confidence) |
| `--secondary-foreground` | `#FFFFFF` |  |
| `--accent` | `#8F6D04` | Deep gold — caution/monitor |
| `--accent-foreground` | `#FFFFFF` |  |
| `--muted` | `#F1ECE4` | Chips, inactive surfaces |
| `--muted-foreground` | `#6E5F53` | Warmed; still darkened to clear 4.5:1 on `--muted` |
| `--border` | `#EDDCC4` | Decorative dividers only |
| `--border-input` | `#8C715A` | Controls where the border is the only affordance |
| `--destructive` | `#C51B2C` | Hue 354, not 0 — keeps error clear of an orange primary |
| `--destructive-foreground` | `#FFFFFF` |  |
| `--ring` | `#8E4D10` | Focus rings |

### 1.2 Dark

Derived from the light palette, then validated. Deep tilled earth rather than pure black — pure black on OLED causes smear during scroll and reads as harsh.

| Role | Hex | Notes |
|------|-----|-------|
| `--background` | `#140F0B` | Tilled earth, not pure black |
| `--foreground` | `#F1ECE4` | Dark umber — body text |
| `--card` | `#201913` | Clean white surfaces |
| `--card-foreground` | `#F1ECE4` |  |
| `--primary` | `#F5A242` | Lightened — dark surfaces need lighter accents |
| `--primary-foreground` | `#271607` |  |
| `--secondary` | `#39D070` | **Health signal only.** Kept green so confidence bands stay distinct |
| `--secondary-foreground` | `#082112` |  |
| `--accent` | `#F9D02F` | Deep gold — caution/monitor |
| `--accent-foreground` | `#221B02` |  |
| `--muted` | `#2B231D` | Chips, inactive surfaces |
| `--muted-foreground` | `#BAAFA0` | Warmed; still darkened to clear 4.5:1 on `--muted` |
| `--border` | `#3E3228` | Decorative dividers only |
| `--border-input` | `#8D7053` | Controls where the border is the only affordance |
| `--destructive` | `#F26977` | Hue 354, not 0 — keeps error clear of an orange primary |
| `--destructive-foreground` | `#1D0707` |  |
| `--ring` | `#F5A242` | Focus rings |

### 1.3 Verified contrast ratios

Regenerate with `python frontend/scripts/check-contrast.py`; it reads `index.css` directly, so these cannot drift from the shipped tokens without the check failing.

| Pair | Light | Dark | Requirement |
|------|-------|------|-------------|
| body on background | 13.57:1 | 16.18:1 | 4.5 |
| body on card | 14.34:1 | 14.74:1 | 4.5 |
| muted-fg on background | 5.79:1 | 8.85:1 | 4.5 |
| muted-fg on card | 6.11:1 | 8.06:1 | 4.5 |
| muted-fg on muted | 5.20:1 | 7.16:1 | 4.5 |
| primary-fg on primary | 6.52:1 | 8.39:1 | 4.5 |
| secondary-fg on secondary | 6.51:1 | 8.50:1 | 4.5 |
| accent-fg on accent | 4.82:1 | 11.47:1 | 4.5 |
| destructive-fg on destructive | 5.87:1 | 6.50:1 | 4.5 |
| primary text on card | 6.52:1 | 8.35:1 | 4.5 |
| accent text on card | 4.82:1 | 11.66:1 | 4.5 |
| destructive text on card | 5.87:1 | 5.83:1 | 4.5 |
| secondary text on card | 6.51:1 | 8.66:1 | 4.5 |
| border-input on card | 4.54:1 | 3.79:1 | 3.0 |
| border-input on background | 4.30:1 | 4.17:1 | 3.0 |

**Status separation** (CIE76 dE between the three confidence swatches; min 25):

| Pair | Light | Dark |
|------|-------|------|
| high / success vs moderate / caution | dE 53.8 | dE 73.0 |
| high / success vs low / risk | dE 100.8 | dE 115.8 |
| moderate / caution vs low / risk | dE 60.7 | dE 83.0 |

**Rule:** `--border` is decorative and intentionally below 3:1. Never use it as the sole boundary of an interactive control — use `--border-input`.

### 1.4 Semantic status colors

Never encode meaning in hue alone (colorblind users, and the sun-washed-screen case). Always pair with an icon and a text label.

| Status | Token | Light | Dark | Icon |
|--------|-------|-------|------|------|
| Healthy / optimal | `--secondary` | `#196B3B` | `#39D070` | `CheckCircle2` |
| Caution / monitor | `--accent` | `#8F6D04` | `#F9D02F` | `AlertTriangle` |
| Risk / disease | `--destructive` | `#C51B2C` | `#F26977` | `AlertOctagon` |
| Neutral / info | `--muted-foreground` | `#6E5F53` | `#BAAFA0` | `Info` |

**Healthy reads `--secondary`, not `--primary`, and this is not interchangeable.** Primary is the brand's field
ochre and accent is a gold; once both went warm they sat 16 degrees of hue apart and measured dE 21.9, under the
25 this system treats as clearly distinct. A success chip and a caution chip stopped being tellable apart. On a
tool that reports how much to trust a yield forecast before a smallholder spends on seed, that is a correctness
bug rather than a style one — so `--secondary` stays green and carries the health signal alone. `Badge` and
`ConfidenceMeter` both point at it, and `check-contrast.py` fails the build path if the separation regresses.

---

## 2. Typography

**Family:** Plus Jakarta Sans (single family, weights 400/500/600/700/800).
Chosen over the two-font default: one family = one webfont payload, which protects the 95+ Lighthouse target. Self-hosted via `@fontsource` rather than the Google CDN to avoid a render-blocking third-party connection.

| Token | Size / Line-height | Use |
|-------|-------------------|-----|
| `text-display` | 3.5rem / 1.05, weight 800, tracking -0.03em | Landing hero |
| `text-h1` | 2.25rem / 1.15, weight 700 | Page titles |
| `text-h2` | 1.5rem / 1.25, weight 700 | Section headers |
| `text-h3` | 1.125rem / 1.4, weight 600 | Card titles |
| `text-body` | 1rem / 1.6, weight 400 | Body copy and form inputs |
| `text-sm` | 0.875rem / 1.5 | Secondary text, dense data readouts |
| `text-label` | 0.8125rem / 1.4, weight 600 | Form labels |
| `text-xs` | 0.75rem / 1.5 | Metadata, units, hints, disclaimers |

**Size rule, stated precisely.** *Prose the user is expected to read* — page descriptions, empty/error state copy, model explanations, module descriptions — is **16px minimum**. Supporting text that is scanned rather than read (units, field hints, timestamps, badge text, stat-tile captions) may be 12–14px. Form **inputs** are always 16px, without exception: anything smaller triggers an involuntary zoom on iOS Safari when the field receives focus.

Numeric readouts (yield, confidence, NPK) use `font-variant-numeric: tabular-nums` so digits don't jitter when values animate.

---

## 3. Spacing, Radius, Shadow

**Spacing** (density 4/10 — standard): `--space-xs 4px` · `sm 8px` · `md 16px` · `lg 24px` · `xl 32px` · `2xl 48px` · `3xl 64px`

**Radius** — Organic Biophilic calls for generous, *varied* curvature:

| Token | Value | Use |
|-------|-------|-----|
| `--radius-sm` | 8px | Badges, chips |
| `--radius-md` | 12px | Inputs, buttons |
| `--radius-lg` | 16px | Cards |
| `--radius-xl` | 24px | Feature panels, modals |
| `--radius-organic` | `28px 24px 26px 22px` | Hero blobs, illustration frames only |

**Shadow** — soft and natural, never hard-edged:

| Token | Value |
|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(8,19,13,0.04)` |
| `--shadow-md` | `0 4px 16px rgba(8,19,13,0.06)` |
| `--shadow-lg` | `0 12px 32px rgba(8,19,13,0.08)` |
| `--shadow-xl` | `0 24px 56px rgba(8,19,13,0.10)` |

In dark mode shadows are near-invisible; use `--border` elevation instead of shadow to signal depth.

---

## 4. Motion

Framer Motion (not GSAP — the DB preset assumed GSAP; the equivalent stagger is expressed with `staggerChildren`).

| Interaction | Duration | Easing |
|-------------|----------|--------|
| Micro (hover, press) | 150ms | `ease-out` |
| Standard (card reveal, accordion) | 250ms | `[0.22, 1, 0.36, 1]` |
| Page transition | 300ms in / 200ms out | exit faster than enter |
| Stagger children | 60ms each | cap total at ~400ms |

**Rules**
- Animate only `transform` and `opacity`. Never `width`/`height`/`top`/`left` — they trigger layout.
- Every entrance animation must have its final state as the default so no-JS/reduced-motion users see finished content.
- `prefers-reduced-motion: reduce` collapses all durations to ~0.01ms globally. Non-negotiable.
- No overshoot easing (`back.out`) on data readouts — it reads as sloppy on informational UI.

---

## 5. Product-Specific Rules

TerraMind is an **advisory tool**, not a consumer app. Its output influences real planting and spending decisions.

1. **Always show confidence.** Every model output carries a confidence indicator. Never present a prediction as certainty.
2. **Never fabricate agronomic data.** Empty state ≠ zero. If the backend returns nothing, say so — do not render a plausible-looking placeholder number.
3. **Cite sources in AugNosis.** GraphRAG answers must surface their source citations; that is the feature's entire trust proposition.
4. **Results are the hero, forms are the means.** On desktop, form left / results right. On mobile, form first, then auto-scroll to results on completion.
5. **Touch targets ≥ 44×44px with ≥8px spacing.** Assume gloved hands and a phone in direct sun.
6. **Long-running inference needs staged feedback.** Ensemble inference is slow; show what stage it is in, not an indefinite spinner.
7. **Degrade honestly.** Backend down is a first-class state with a retry, not a silent failure.

---

## 6. Anti-Patterns

- ❌ **Dynamic Tailwind class construction** — `` `bg-${color}-500` `` produces *no styles*; Tailwind scans statically. (This bug is live in `Advisor.jsx:122`.) Use a static variant map.
- ❌ Emoji as icons — use Lucide SVG.
- ❌ Placeholder-as-label — every input needs a real `<label>`.
- ❌ Errors collected at form top — put each error under its field, with `role="alert"`.
- ❌ Color as the only carrier of meaning.
- ❌ Removing focus rings.
- ❌ Body prose below 16px, or any form input below 16px (see §2).
- ❌ Raw hex in components — semantic tokens only.
- ❌ Layout-shifting hover (animating size/margin).
- ❌ Indefinite spinners with no stage information.

---

## 7. Pre-Delivery Checklist

- [ ] No emoji icons; Lucide throughout
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover transitions 150–300ms
- [ ] Light and dark both ≥4.5:1 body text
- [ ] Focus visible on every interactive element
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive at 375 / 768 / 1024 / 1440px
- [ ] No horizontal scroll at 375px
- [ ] Nothing hidden behind the fixed navbar
- [ ] Every input has a `<label>`; every error has `role="alert"`
- [ ] Touch targets ≥44px
- [ ] Loading states reserve space (CLS < 0.1)
