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

## Brand & Interaction Tokens / Marken- & Interaktions-Tokens
| Token | Purpose (EN) | Zweck (DE) | Value |
| --- | --- | --- | --- |
| `--brand` | Default brand tint | Primärer Markenfarbton | `#0C1F3D` (dark) / `#2A4A85` (light) |
| `--brand-strong` | Strong brand contrast | Kontrastreiche Markenfarbe | `#071327` (dark) / `#1E335B` (light) |
| `--brand-soft` | Soft brand backdrop | Sanfter Markenhintergrund | `#173760` (dark) / `#3C5A96` (light) |
| `--accent` | Primary accent | Primärer Akzent | `#33B6FF` (dark) / `#1E88F7` (light) |
| `--accent-strong` | Active accent state | Aktiver Akzentzustand | `#33B6FF` (dark) / `#0F6ED6` (light) |
| `--accent-2` | Secondary accent | Zweiter Akzent | `#F7B955` (dark) / `#FFCE73` (light) |
| `--focus-ring` | Focus halo colour | Fokus-Markierung | `rgba(94, 207, 254, 0.55)` (dark) / `rgba(30, 136, 247, 0.35)` (light) |
| `--focus-ring-contrast` | Focus outline base | Fokus-Kontur | `rgba(3, 9, 19, 0.92)` (dark) / `rgba(227, 239, 255, 0.95)` (light) |
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
