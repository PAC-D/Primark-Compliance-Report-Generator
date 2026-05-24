# Info Cards Redesign — TPS Compliance Report

## Date: 2026-05-20

## Status
Approved — Implementation pending

---

## Overview

Redesign the supplier info cards (Origin Country, Factories, Global Ranking, Local Ranking) in the TPS PDF report from their current stacked/block style to a clean minimal horizontal bar layout that feels more professional and modern.

---

## Design Decisions

### Style: Clean Minimal
- Subtle borders, near-flat design, understated palette
- No gradients, no heavy shadows, no decorative elements
- White backgrounds with 1px `#e5e7eb` borders
- Everything aligned on a single visual baseline

### Value Color: Deep Navy
- Value text: `#00205b` (Primark navy), bold weight
- Contrasts with muted labels, uses brand authority

### Layout: Horizontal Bar
- Supplier name occupies left portion of the header bar
- Info cards sit inline to the right, sharing the same baseline
- No vertical stacking — everything on one row
- Multi-country layout: two horizontal rows, separated by small gap

---

## Layout Specification

### Single-Country Row
```
┌──────────────────┬────────────────────────────────────────────────┐
│  SUPPLIER NAME   │  [Origin Country] [Factories] [Global#] [Local#]│
│  (18px, navy,    │  (info cards, inline, same baseline, navy values)│
│   bold, ~40%)     │  (~60%)                                        │
└──────────────────┴────────────────────────────────────────────────┘
```

### Multi-Country Rows
Row 1: Origin Country + Factories (left label, cards to right)
Row 2: Global Ranking + Local Rankings (left label, cards to right)
8px vertical gap between rows, faint `#f3f4f6` divider line

---

## CSS Specification

### Supplier Header Bar
```css
.supplier-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 10px;
}
.supplier-name-large {
  flex: 0 0 auto;
  width: 38%;
  font-size: 15px;
  font-weight: 800;
  color: #00205b;
  line-height: 1.2;
  word-break: break-word;
}
.info-cards {
  flex: 1;
  display: flex;
  justify-content: flex-start;
  gap: 10px;
  flex-wrap: wrap;
  align-items: flex-start;
}
```

### Info Card
```css
.info-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 7px 12px;
  min-width: 100px;
  text-align: center;
}
.info-card-label {
  font-size: 8px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}
.info-card-value {
  font-size: 15px;
  font-weight: 800;
  color: #00205b;
  line-height: 1.1;
}
```

### Row 2 Cards (multi-country)
Row 2 uses same `.info-card` styles as row 1, separated by 8px top margin and a faint top border on the `.info-cards-row2` container.

---

## Implementation Notes

- Remove stacked supplier-name-large above cards — merge into single flex row
- Remove `.info-cards-row2` separate flex container — replace with `.info-cards` continuation
- Multi-country uses `flex-wrap: wrap` to handle variable card counts per country
- Long supplier names (>30 chars) still trigger `long_supplier_name` class for chart height adjustment
- No JavaScript changes required — pure CSS layout
- Keep all existing functionality (shared indicator, ranking format, etc.)

---

## Files to Modify

- `tps-pipeline/templates/report.html.j2` — CSS classes and HTML structure
- No changes to `renderer.py` or `metrics.py`