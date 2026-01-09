# Design System – Light & Dark Modes

## Overview / Überblick
- **EN:** The Cognitive Staffing UI uses a shared set of design tokens for typography, spacing, and color across the dark and light Streamlit themes. The variables live in `styles/cognitive_needs.css` and `styles/cognitive_needs_light.css` so every page inherits consistent values.
- **DE:** Die Cognitive-Staffing-Oberfläche nutzt gemeinsame Design-Tokens für Typografie, Abstände und Farben in den dunklen und hellen Streamlit-Themes. Die Variablen befinden sich in `styles/cognitive_needs.css` und `styles/cognitive_needs_light.css`, damit jede Seite einheitliche Werte erhält.

## Typography Tokens / Typografie-Tokens
| Token | Purpose (EN) | Zweck (DE) | Value |
| --- | --- | --- | --- |
| `--font-family-base` | Body copy font | Fließtext-Schrift | `Inter, system-ui, ...` |
| `--font-family-heading` | Headings font | Überschrift-Schrift | `Space Grotesk, Inter, ...` |
| `--font-size-body` | Default body size | Standard-Fließtextgröße | `1rem` |
| `--font-size-h1` | Primary heading size | Größe für Hauptüberschriften | `clamp(1.6rem, 1.2rem + 1.4vw, 2.1rem)` |
| `--font-size-h2` | Section heading size | Größe für Abschnittsüberschriften | `clamp(1.35rem, 1.05rem + 1vw, 1.75rem)` |
| `--font-size-h3` | Subheading size | Größe für Unterüberschriften | `clamp(1.15rem, 1rem + 0.6vw, 1.4rem)` |
| `--font-size-small` | Secondary text | Sekundärtext | `0.94rem` |
| `--font-size-caption` | Captions & helper text | Bildunterschriften & Hilfetext | `0.85rem` |
| `--line-height-body` | Body line height | Zeilenhöhe Fließtext | `1.6` |
| `--line-height-heading` | Heading line height | Zeilenhöhe Überschriften | `1.25` |

## Spacing Scale / Abstands-Skala
| Token | Description (EN) | Beschreibung (DE) | Value |
| --- | --- | --- | --- |
| `--space-2xs` | Micro gaps (chips, badges) | Minimale Abstände (Chips, Badges) | `0.25rem` |
| `--space-xs` | Tight component spacing | Enger Komponentenabstand | `0.35rem` |
| `--space-sm` | Small gaps & column gutters | Kleine Abstände & Spalten-Gutters | `0.5rem` |
| `--space-md` | Default block spacing | Standard-Blockabstand | `0.75rem` |
| `--space-lg` | Section margin/padding | Abschnitts-Abstand/Innenabstand | `1rem` |
| `--space-xl` | Hero/Panel padding | Innenabstand für Panels/Hero | `1.5rem` |
| `--space-2xl` | Large layout breaks | Große Layout-Abstände | `2.25rem` |

## Hero & Banner Tokens / Hero- & Banner-Tokens
Shared hero/banner tokens drive the onboarding hero (`wizard/layout.py`) and the global banner (`.app-banner`) so both themes render consistent panel spacing and typography.

| Token | Purpose (EN) | Zweck (DE) | Value |
| --- | --- | --- | --- |
| `--hero-panel-bg` | Onboarding hero background gradient | Hintergrundverlauf für Onboarding-Hero | Theme-specific gradient |
| `--hero-overlay` | Onboarding hero overlay | Overlay für Onboarding-Hero | Theme-specific gradient |
| `--hero-panel-border` | Onboarding hero border color | Rahmenfarbe für Onboarding-Hero | Theme-specific RGBA |
| `--hero-panel-gap` | Onboarding hero layout gap | Layout-Abstand im Onboarding-Hero | `clamp(1rem, 3vw, 2.75rem)` |
| `--hero-panel-padding` | Onboarding hero padding | Innenabstand im Onboarding-Hero | `clamp(1.4rem, 1rem + 2vw, 2.4rem)` |
| `--hero-panel-padding-compact` | Onboarding hero padding (mobile) | Innenabstand im Onboarding-Hero (mobil) | `clamp(1.1rem, 0.9rem + 1.2vw, 1.6rem)` |
| `--hero-panel-margin` | Onboarding hero block margin | Außenabstand des Onboarding-Hero | `1.2rem 0 1.4rem` |
| `--hero-panel-radius` | Onboarding hero corner radius | Eckenradius des Onboarding-Hero | `clamp(1.2rem, 0.8rem + 1vw, 1.75rem)` |
| `--hero-panel-eyebrow-size` | Onboarding hero eyebrow size | Schriftgröße für Eyebrow | `0.8rem` |
| `--hero-panel-eyebrow-letter-spacing` | Eyebrow letter spacing | Zeichenabstand Eyebrow | `0.22em` |
| `--hero-panel-eyebrow-margin` | Eyebrow bottom margin | Unterer Abstand Eyebrow | `0.5rem` |
| `--hero-panel-headline-size` | Hero headline size | Größe der Hero-Überschrift | `clamp(1.9rem, 1.2rem + 2vw, 2.6rem)` |
| `--hero-panel-headline-weight` | Hero headline weight | Gewicht der Hero-Überschrift | `700` |
| `--hero-panel-headline-line-height` | Hero headline line height | Zeilenhöhe der Hero-Überschrift | `1.2` |
| `--hero-panel-subheadline-size` | Hero subheadline size | Größe der Subheadline | `clamp(1.05rem, 0.95rem + 0.45vw, 1.25rem)` |
| `--hero-panel-subheadline-line-height` | Hero subheadline line height | Zeilenhöhe der Subheadline | `1.6` |
| `--hero-panel-subheadline-margin` | Subheadline top margin | Oberer Abstand der Subheadline | `0.85rem` |
| `--hero-image-filter` | Hero illustration filter | Filter für Hero-Grafik | Theme-specific |
| `--hero-copy-max-width` | Max width for hero copy | Maximale Breite für Hero-Text | `640px` |
| `--hero-banner-bg` | Global banner background | Hintergrund des globalen Banners | Theme-specific gradient |
| `--hero-banner-overlay` | Global banner overlay | Overlay des globalen Banners | Theme-specific gradient |
| `--hero-banner-border` | Global banner border | Rahmenfarbe des Banners | Theme-specific RGBA |
| `--hero-banner-logo-bg` | Banner logo tile background | Hintergrund der Logo-Kachel | Theme-specific RGBA |
| `--hero-banner-logo-border` | Banner logo tile border | Rahmen der Logo-Kachel | Theme-specific RGBA |
| `--hero-banner-logo-shadow` | Banner logo tile shadow | Schatten der Logo-Kachel | Theme-specific |
| `--hero-banner-meta-bg` | Banner meta badge background | Hintergrund für Meta-Badges | Theme-specific RGBA |
| `--hero-banner-meta-border` | Banner meta badge border | Rahmen für Meta-Badges | Theme-specific RGBA |
| `--hero-banner-gap` | Banner layout gap | Layout-Abstand im Banner | `clamp(1rem, 3vw, 2rem)` |
| `--hero-banner-padding` | Banner padding | Innenabstand im Banner | `clamp(1.2rem, 1rem + 1.8vw, 2rem) clamp(1.4rem, 1rem + 2vw, 2.4rem)` |
| `--hero-banner-radius` | Banner corner radius | Eckenradius des Banners | `var(--radius)` |
| `--hero-banner-eyebrow-size` | Banner eyebrow size | Schriftgröße für Eyebrow im Banner | `0.8rem` |
| `--hero-banner-eyebrow-letter-spacing` | Banner eyebrow letter spacing | Zeichenabstand Eyebrow im Banner | `0.22em` |
| `--hero-banner-eyebrow-margin` | Banner eyebrow margin | Abstand unter Eyebrow | `0.35rem` |
| `--hero-banner-headline-size` | Banner headline size | Größe der Banner-Überschrift | `clamp(1.6rem, 1.2rem + 1.6vw, 2.3rem)` |
| `--hero-banner-subtitle-size` | Banner subtitle size | Größe der Banner-Subline | `clamp(1rem, 0.95rem + 0.4vw, 1.2rem)` |
| `--hero-banner-subtitle-line-height` | Banner subtitle line height | Zeilenhöhe der Banner-Subline | `1.6` |
| `--hero-banner-subtitle-margin` | Banner subtitle margin | Abstand oberhalb der Banner-Subline | `0.6rem` |
| `--hero-banner-meta-size` | Banner meta text size | Schriftgröße für Meta-Text | `0.9rem` |
| `--hero-banner-meta-line-height` | Banner meta line height | Zeilenhöhe für Meta-Text | `1.6` |
| `--hero-banner-meta-margin` | Banner meta top margin | Abstand oberhalb der Meta-Zeile | `0.9rem` |

## Brand & Interaction Tokens / Marken- & Interaktions-Tokens
| Token | Purpose (EN) | Zweck (DE) | Value |
| --- | --- | --- | --- |
| `--brand` | Default brand tint | Primärer Markenfarbton | `#0C1F3D` (dark) / `#2A4A85` (light) |
| `--brand-strong` | Strong brand contrast | Kontrastreiche Markenfarbe | `#08142B` (dark) / `#1F3561` (light) |
| `--brand-soft` | Soft brand backdrop | Sanfter Markenhintergrund | `#16335C` (dark) / `#D8E1F5` (light) |
| `--accent` | Primary accent | Primärer Akzent | `#1FB5C5` (dark & light) |
| `--accent-strong` | Active accent state | Aktiver Akzentzustand | `#18C9D4` (dark) / `#18C9D4` (light) |
| `--accent-2` | Secondary accent | Zweiter Akzent | `#FFC368` (dark) / `#FFB65C` (light) |
| `--focus-ring` | Focus halo colour | Fokus-Markierung | `rgba(56, 192, 255, 0.5)` (dark) / `rgba(31, 181, 197, 0.32)` (light) |
| `--focus-ring-contrast` | Focus outline base | Fokus-Kontur | `rgba(2, 9, 20, 0.96)` (dark) / `rgba(236, 245, 255, 0.95)` (light) |
| `--focus-border` | Focus border for panels | Fokus-Rahmen für Panels | `rgba(56, 192, 255, 0.8)` (dark) / `rgba(24, 201, 212, 0.7)` (light) |
| `--ring-accent` | Focus ring accent glow | Akzent-Glow für Fokus | `rgba(56, 192, 255, 0.35)` (dark) / `rgba(24, 201, 212, 0.22)` (light) |

### Palette & Accessibility / Farbpalette & Barrierefreiheit
- **EN:** The navy (`#0C1F3D` dark / `#2A4A85` light) anchors both themes, while teal (`#1FB5C5`) and amber (`#FFC368`/`#FFB65C`) accents provide hierarchy and state feedback. Each pairing below exceeds WCAG AA (≥ 4.5:1) for body text so headings and controls stay legible on bright monitors.
- **DE:** Das Navy (`#0C1F3D` im Dark-Mode / `#2A4A85` im Light-Mode) bildet das Fundament beider Themes. Teal (`#1FB5C5`) und Bernstein (`#FFC368`/`#FFB65C`) setzen Hierarchien und Zustände. Alle Kombinationen unten übertreffen WCAG AA (≥ 4,5:1), damit Überschriften und Controls auf hellen Displays klar bleiben.

| Pair / Kombination | Use Case (EN) | Anwendungsfall (DE) | Contrast Ratio |
| --- | --- | --- | --- |
| `#0C1F3D` background + `#F4F9FF` text | Dark hero & sidebar panels | Dunkle Hero-/Sidebar-Panels | 15.5 : 1 |
| `#2A4A85` background + `#F8FBFF` text | Light brand strips, callouts | Helle Markenbänder & Callouts | 8.4 : 1 |
| `#1FB5C5` accent + `#041120` text | Accent chips & sliders | Akzent-Chips und Regler | 7.7 : 1 |
| `#FFC368` accent + `#041120` text | Warning/positive pills | Hinweis-/Positive-Pills | 12.0 : 1 |

### Typography Guidance / Typografie-Hinweise
- **EN:** `Inter` (body) and `Space Grotesk` (headings) remain the canonical stacks. Keep headings at `600` weight for readability, use `400` for paragraph copy, and leave captions at `--font-size-caption` with `--line-height-body` to avoid cramped bilingual helper text.
- **DE:** `Inter` (Fließtext) und `Space Grotesk` (Überschriften) sind weiterhin die verbindlichen Stacks. Überschriften bitte mit Gewicht `600`, Fließtext mit `400` und Bildunterschriften mit `--font-size-caption` plus `--line-height-body`, damit zweisprachige Hilfetexte nicht gedrängt wirken.
| `--transition-base` | Default animation timing | Standard-Transition | `0.18s ease-out` |

## Color Tokens / Farb-Tokens
The palette keeps token names aligned between both modes; only the values differ.

### Dark Theme / Dunkles Theme (`styles/cognitive_needs.css`)
| Token | Description (EN) | Beschreibung (DE) | Value |
| --- | --- | --- | --- |
| `--color-primary` | Accent blue | Primärakzent (Blau) | `var(--accent)` |
| `--color-secondary` | Secondary accent | Zweitakzent | `var(--accent-2)` |
| `--color-surface` | Base background | Basis-Hintergrund | `var(--surface-0)` |
| `--color-surface-elevated` | Raised panels | Erhöhte Flächen | `var(--surface-1)` |
| `--color-text-strong` | Primary text | Primärtext | `var(--text-strong)` |
| `--color-text-muted` | Secondary text | Sekundärtext | `var(--text-muted)` |
| `--color-border-subtle` | Subtle border | Zurückhaltende Rahmenfarbe | `var(--border-subtle)` |
| `--surface-hover` | Hover state background | Hintergrund Hover-Zustand | `var(--surface-hover)` |
| `--surface-press` | Pressed background | Hintergrund gedrückter Zustand | `var(--surface-press)` |

### Light Theme / Helles Theme (`styles/cognitive_needs_light.css`)
| Token | Description (EN) | Beschreibung (DE) | Value |
| --- | --- | --- | --- |
| `--color-primary` | Accent blue | Primärakzent (Blau) | `var(--accent)` |
| `--color-secondary` | Accent amber | Akzentfarbe (Bernstein) | `var(--accent-2)` |
| `--color-surface` | Base background | Basis-Hintergrund | `var(--surface-0)` |
| `--color-surface-elevated` | Raised panels | Erhöhte Flächen | `var(--surface-1)` |
| `--color-text-strong` | Primary text | Primärtext | `var(--text-strong)` |
| `--color-text-muted` | Secondary text | Sekundärtext | `var(--text-muted)` |
| `--color-border-subtle` | Subtle border | Zurückhaltende Rahmenfarbe | `var(--border-subtle)` |
| `--surface-hover` | Hover state background | Hintergrund Hover-Zustand | `var(--surface-hover)` |
| `--surface-press` | Pressed background | Hintergrund gedrückter Zustand | `var(--surface-press)` |

## Usage Notes / Nutzungshinweise
- **EN:** Reference the tokens via `var(--token-name)` in Streamlit CSS snippets (see `COMPACT_STEP_STYLE` in `wizard/layout.py`). Fallback values are provided for compatibility when the CSS runs outside the themed context.
- **DE:** Die Tokens werden per `var(--token-name)` in Streamlit-CSS-Snippets genutzt (siehe `COMPACT_STEP_STYLE` in `wizard/layout.py`). Für die Kompatibilität außerhalb des Themes sind Fallback-Werte hinterlegt.
- **EN:** Brand colours are only applied to sidebar hero panels when the contrast ratio between background and text reaches WCAG AA (≥ 4.5:1); otherwise the UI falls back to the neutral accent tokens. Mobile adjustments target ≤ 768 px to keep forms usable on tablets.
- **DE:** Markenfarben werden nur dann im Sidebar-Hero genutzt, wenn der Kontrast zwischen Hintergrund und Text die WCAG-AA-Schwelle (≥ 4,5:1) erfüllt; andernfalls greift der neutrale Akzentton. Mobile Anpassungen zielen auf ≤ 768 px ab, damit Formulare auch auf Tablets nutzbar bleiben.
- **EN:** The onboarding hero includes a primary CTA and a compact timeline; keep these elements within the hero container and style them using existing accent/surface tokens to preserve visual hierarchy.
- **DE:** Der Onboarding-Hero enthält eine primäre CTA und eine kompakte Timeline; diese Elemente bleiben innerhalb des Hero-Containers und werden mit bestehenden Akzent-/Surface-Tokens gestylt, damit die visuelle Hierarchie erhalten bleibt.
- **EN:** Any hover or motion effects in the onboarding hero must be disabled under `prefers-reduced-motion: reduce` to respect accessibility preferences.
- **DE:** Hover- oder Motion-Effekte im Onboarding-Hero müssen unter `prefers-reduced-motion: reduce` deaktiviert werden, um Barrierefreiheit zu respektieren.

## Components / Komponenten

### Onboarding hero / Onboarding-Hero
- **Structure (EN):** The hero lives in the onboarding step container and uses `.onboarding-hero` with a headline, supporting copy, and a `.onboarding-hero__cta` primary button. The compact timeline is rendered as `.onboarding-hero__timeline` with individual steps inside `.onboarding-hero__timeline-item` rows for consistent spacing.
- **Struktur (DE):** Der Hero befindet sich im Onboarding-Container und nutzt `.onboarding-hero` mit Headline, Begleittext und einer primären `.onboarding-hero__cta`-Schaltfläche. Die kompakte Timeline wird als `.onboarding-hero__timeline` mit einzelnen `.onboarding-hero__timeline-item`-Zeilen gerendert.
- **CTA (EN):** Keep the CTA within the hero panel; use accent tokens (`--accent`, `--accent-strong`) and focus ring tokens for keyboard focus.
- **CTA (DE):** Die CTA bleibt im Hero-Panel; nutze Akzent-Tokens (`--accent`, `--accent-strong`) sowie Fokus-Tokens für Tastaturfokus.

### Source input panels / Quell-Input-Panels
- **Structure (EN):** The URL vs. upload choices are grouped in `.onboarding-source-inputs`, with each panel styled via `.onboarding-source__panel`. The OR divider uses `.onboarding-source__or` and its `::before` line for the visual separator.
- **Struktur (DE):** Die URL- und Upload-Auswahl liegt in `.onboarding-source-inputs`, jede Fläche nutzt `.onboarding-source__panel`. Der OR-Trenner verwendet `.onboarding-source__or` und die `::before`-Linie als Separator.
- **Responsive rules (EN):** For ≤ 768 px, panels stack vertically and the OR divider becomes a horizontal rule via `.onboarding-source__or::before`, while columns collapse to a single column.
- **Responsive rules (DE):** Für ≤ 768 px stapeln sich die Panels vertikal und der OR-Trenner wird über `.onboarding-source__or::before` als horizontale Linie dargestellt; die Spalten reduzieren sich auf eine.

## Motion rules / Bewegungsregeln
- **Hover (EN):** CTA and panels may use subtle hover transitions via `--transition-base` and accent tokens; avoid additional motion that competes with the primary flow.
- **Hover (DE):** CTA und Panels dürfen dezente Hover-Transitions über `--transition-base` und Akzent-Tokens nutzen; vermeide zusätzliche Motion, die vom Hauptflow ablenkt.
- **Load animation (EN):** Follow-up highlight flashes (`.fu-highlight`, `.fu-highlight-soft`) are allowed to draw attention to missing fields.
- **Load animation (DE):** Follow-up-Highlights (`.fu-highlight`, `.fu-highlight-soft`) dürfen fehlende Felder kurz hervorheben.
- **Reduced motion (EN):** Disable highlight animations and other non-essential motion under `prefers-reduced-motion: reduce`.
- **Reduced motion (DE):** Deaktiviere Highlight-Animationen und nicht notwendige Motion unter `prefers-reduced-motion: reduce`.
