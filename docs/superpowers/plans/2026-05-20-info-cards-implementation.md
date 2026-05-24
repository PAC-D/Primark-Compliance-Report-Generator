# Info Cards Redesign — Implementation Plan

> **For agentic workers:** Use subagent-driven-development or execute tasks inline.

**Goal:** Restyle supplier header to use a horizontal bar layout with supplier name inline-left and info cards inline-right. Clean minimal style, navy values, flat cards.

**Architecture:** Pure CSS/HTML changes to `report.html.j2`. No Python changes. Uses flexbox for horizontal alignment. Two-row layout for multi-country (row 1 = name+origin/factories, row 2 = global/local rankings).

**Tech Stack:** Jinja2 template, CSS flexbox, Inter font.

---

## File: `tps-pipeline/templates/report.html.j2`

### 1. Update `.supplier-header` CSS

**Location:** Line ~558

- [ ] **Step 1: Update `.supplier-header`**

```css
.supplier-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 8px;
  flex-shrink: 0;
}
```

- [ ] **Step 2: Update `.supplier-name-large`** (change from block to inline in flex context, reduce font size, use navy color)

```css
.supplier-name-large {
  flex: 0 0 38%;
  font-size: 15px;
  font-weight: 800;
  color: #00205b;
  line-height: 1.2;
  word-break: break-word;
  padding-top: 4px;
}
```

- [ ] **Step 3: Update `.info-cards`**

```css
.info-cards {
  flex: 1;
  display: flex;
  justify-content: flex-start;
  gap: 10px;
  flex-wrap: wrap;
  align-items: flex-start;
}
```

- [ ] **Step 4: Update `.info-card`**

```css
.info-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 7px 12px;
  min-width: 100px;
  text-align: center;
}
```

- [ ] **Step 5: Update `.info-card-label`**

```css
.info-card-label {
  font-size: 8px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}
```

- [ ] **Step 6: Update `.info-card-value`**

```css
.info-card-value {
  font-size: 15px;
  font-weight: 800;
  color: #00205b;
  line-height: 1.1;
}
```

- [ ] **Step 7: Update `.info-cards-row2`**

```css
.info-cards-row2 {
  display: flex;
  justify-content: flex-start;
  gap: 10px;
  flex-wrap: wrap;
  align-items: flex-start;
  padding-top: 8px;
  border-top: 1px solid #f3f4f6;
  margin-top: 2px;
}
```

---

### 2. Restructure Single-Country HTML

**Location:** Lines ~696–735

**Current structure:**
```html
<div class="supplier-header">
  <div class="supplier-name-large">{{ supplier_name }}</div>  <!-- block, above cards -->
  <div class="info-cards">
    <!-- Origin, Factory, Global, Local cards -->
  </div>
  {% if multi_country %}
  <div class="info-cards-row2">
    <!-- Global, Local cards -->
  </div>
  {% endif %}
</div>
```

**New single-country structure:**
```html
<div class="supplier-header">
  <div class="supplier-name-large">{{ supplier_name }}</div>
  <div class="info-cards">
    <div class="info-card">
      <div class="info-card-label">Origin Country</div>
      <div class="info-card-value">{{ kpis.origin_country }}</div>
    </div>
    <div class="info-card">
      <div class="info-card-label">No of Factories</div>
      <div class="info-card-value">{{ kpis.factory_count }}</div>
    </div>
    <div class="info-card">
      <div class="info-card-label">Global Ranking</div>
      <div class="info-card-value">#{{ ranking }} of {{ total_suppliers }}{% if shared %} <span>(shared)</span>{% endif %}</div>
    </div>
    {% for lr in local_rankings %}
    <div class="info-card">
      <div class="info-card-label">Local Ranking ({{ lr.country }})</div>
      <div class="info-card-value">#{{ lr.rank }} of {{ lr.total }}{% if lr.shared %} <span>(shared)</span>{% endif %}</div>
    </div>
    {% endfor %}
  </div>
</div>
```

---

### 3. Restructure Multi-Country HTML

**New multi-country structure (both rows inside supplier-header flex):**
```html
<div class="supplier-header">
  <div class="supplier-name-large">{{ supplier_name }}</div>
  <div>
    <div class="info-cards">
      <div class="info-card">
        <div class="info-card-label">Origin Country</div>
        <div class="info-card-value">{{ kpis.origin_country }}</div>
      </div>
      <div class="info-card">
        <div class="info-card-label">No of Factories</div>
        <div class="info-card-value">{{ kpis.factory_count }}</div>
      </div>
    </div>
    <div class="info-cards info-cards-row2">
      <div class="info-card">
        <div class="info-card-label">Global Ranking</div>
        <div class="info-card-value">#{{ ranking }} of {{ total_suppliers }}{% if shared %} <span>(shared)</span>{% endif %}</div>
      </div>
      {% for lr in local_rankings %}
      <div class="info-card">
        <div class="info-card-label">Local Ranking ({{ lr.country }})</div>
        <div class="info-card-value">#{{ lr.rank }} of {{ lr.total }}{% if lr.shared %} <span>(shared)</span>{% endif %}</div>
      </div>
      {% endfor %}
    </div>
  </div>
</div>
```

Note: `.info-cards-row2` inherits `.info-cards` display properties but adds top border and margin.

---

### 4. Remove Old `.supplier-name-large` Block Styling

The old CSS had `margin-bottom: 8px; text-align: center;`. Remove `text-align: center` from `.supplier-header` (set in step 1). The supplier name is no longer a block above — it's inline-left in a flex row.

---

### 5. Verify Tests

Run: `cd "/home/shoaib/projects/Primark Report Generator" && python3 -m pytest tps-pipeline/tests/ -q`

Expected: 34 passed. No visual/structure tests exist for info card layout — this is a template-only change.

---

## Verification Checklist

After all changes:
- [ ] Single-country: supplier name and all cards in one horizontal flex row
- [ ] Multi-country: supplier name on left, two card rows stacked to the right (origin/factories row 1, rankings row 2)
- [ ] All card values use `#00205b` navy, bold 15px
- [ ] All card labels use `#9ca3af` gray, 8px uppercase
- [ ] Cards have 1px `#e5e7eb` border, 6px radius, no heavy shadow
- [ ] `.info-cards-row2` has faint top border separating it from row 1
- [ ] `long_supplier_name` and `multi_country` classes still affect chart height correctly
- [ ] All 34 tests pass