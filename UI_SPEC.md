# UI Specification

All pages share a common shell. Page content swaps via tab navigation without full reload (SPA-style with separate HTML partials or JS-rendered sections).

---

## Global layout

```
┌─────────────────────────────────────────────────────────────┐
│  LOGO BAR (centered partner logos, green gradient bg)        │
├─────────────────────────────────────────────────────────────┤
│  NAVBAR: [Summary][Time Series][Distributions][Cohorts]     │
│          [Data Mgmt][Customise][Reports]     [Logout]      │
├──────────────┬──────────────────────────────────────────────┤
│   SIDEBAR    │              MAIN CONTENT                     │
│   350px      │                                               │
│   Filters    │   (active page)                               │
│              │                                               │
│   Saved      │                                               │
│   Views      │                                               │
└──────────────┴──────────────────────────────────────────────┘
```

### Mobile (`<768px`)
- Sidebar becomes off-canvas drawer (hamburger toggle)
- Logo bar stacks logos with smaller height (40px)
- Nav tabs scroll horizontally

---

## Login page (`login.html`)

### Layout
- Left 50%: full-bleed background image (`login_background.png` — pastoral/cattle photo)
- Right 50%: green (`#1B4332`) panel with login form
- Form card: white gradient, rounded 1.5rem, shadow

### Form fields
- Username (text)
- Password (password, Enter key submits)
- Submit button: full width, primary green

### Copy
- Title: **Welcome to Livestock Dashboard**
- Subtitle: *Advanced Analytics for Livestock Management*

### Behavior
- On success → store JWT → redirect to `/dashboard.html?farm=KF` (or first accessible farm)
- On failure → inline error below form
- If already logged in → redirect to dashboard

---

## Sidebar — Data Filters

### Section title
`DATA FILTERS` (uppercase, small, semibold)

### Controls (top to bottom)

1. **Year / Month / Day** — 3-column row
   - Year: required select
   - Month: select, default "All"
   - Day: select, default "All"

2. **Sex / Treatment** — 2-column row
   - Multi-select with search
   - Links: Select All · Invert
   - Empty → reset to "Overall"

3. **Breed / Mob** — 2-column row (same pattern)

4. **EID** — full width (admin only; hidden for user role)

5. **Measure** — single select with search
   - Default: Final processed weight

6. **Record count** — muted small text  
   `Showing 450 of 12,118 records`

7. **Clear all filters** — full width primary button

### Saved Views panel
- Border card below filters
- Text input: "Enter view name..."
- Save button (green)
- List of saved views: name + Load (play icon) + Delete (trash icon)
- Empty state: "No saved views yet"

---

## Empty state (all data pages)

Shown when `record_count === 0`:

```
        📊
   No Data Found

No livestock records match your current filter criteria.
Try adjusting your filters to see more data.

Current filters:
  Year: 2024
  Month: October
  ...

[Reset All Filters]
```

---

## Page 1: Summary Stats

### Info alert (blue)
> The summary statistics below show separate statistics for each animal group based on your current filter selections.

### Per-group section
- Group header (full_group label, green, h5)
- 4 KPI cards in a row:

| Card | Content |
|------|---------|
| Last Day (DD/MM/YYYY) | Mean (large), "Mean", hr, Min, Max, Median, Count |
| Last 15 Days | same |
| Last Month | same |
| Overall | same |

Currency: `$1,234.56` prefix  
Other units: `620.50 kg` suffix

---

## Page 2: Time Series

### Info alert
> Tip: Click on legend items to toggle their visibility on the time series plot below.

### Common filters note (gray alert, conditional)
> Comparing groups by Sex only

### Controls bar (gray bg)
- Point Size slider: 1–5, default 3
- Show Trend Line checkbox

### Chart card
- Header: "Time Series Plot"
- Plotly line chart, 500px height
- X: date, Y: measure with unit
- Legend: "Animal Group"
- Hover: group, date, average, record count

---

## Page 3: Distributions

### Info alert
> Tip: Click on legend items to toggle their visibility on the graphs below.

### Controls
- Histogram Bins slider: 10–50, step 5, default 20

### Two-column layout
| Histogram Comparison | Box Plot |
|---------------------|----------|
| Overlaid histograms per group | Box plot per group |
| Dashed line: mean (accent) | |
| Dotted line: median (danger) | |

---

## Page 4: Cohorts

### Top control
- Top/Bottom percentile select: 10%, 15%, 20% (page-local, not sidebar)

### Mixed selection warning (conditional, yellow card)
> You have selected both 'Overall' and specific items in your filters...

### Explanation card (scrollable, ~300px min)
Full educational copy from original app:
- How Individual Animal Ranking Works
- How It Works (6 bullet points)
- Real-World Example (Animal A vs B)
- Benefits for Your Farm (4 bullets)
- Tip alert about cards vs timeline

### Two cohort cards side by side

**Top Cohort — Individual Averages** (trophy icon)
- Subtitle: Based on each animal's overall average...
- Stats row: Average | Min | Max | N animals
- Buttons: View Animals | Export

**Bottom Cohort** (warning icon) — same layout

### Modals
- View Animals → table of EIDs + avg measure (anonymized EIDs for user role)

### Timeline chart
- Lines for top vs bottom cohort daily performance

---

## Page 5: Data Management

### Card: Data Table
- DataTables-style: pagination, column sort, top filters
- All filtered columns visible, horizontal scroll
- EID column shows `*****` for user role

### Card: Download
- "Download CSV" button → triggers export with current filters

---

## Page 6: Customise

### Card: Chart Configuration
- Chart Type toggle buttons: Line | Bar | Scatter | Area | Histogram | Box
- Chart Title text input (default "Custom Chart")
- X-Axis select
- Y-Axis select (hidden for histogram)
- Group By select (hidden for some types)
- Trend line checkbox (line/scatter only)
- Aggregation select: mean, sum, count, min, max (bar/line)
- Bar Position: stack, dodge, fill (bar only)

### Card: Preview
- Dynamic title
- Plotly chart 520px
- Footer meta: row count, chart type

---

## Page 7: Reports

### Section 1: Export (two columns)

**Export Chart**
- Chart Type: Time Series | Distribution | Summary
- Format: PNG
- Download Chart button

**Export Report**
- Report Filename text input
- Format: PDF | HTML (PRINT_HTML)
- Include Charts checkboxes: Time Series, Distribution, Cohorts, Summary Statistics
- Download Report button

### Section 2: Schedule Automated Reports

**Email Mode** radio: Send Now | Schedule

When Schedule:
- Frequency: Daily | Weekly | Monthly
- Send Time: 15-min increments 00:00–23:45
- Day of week (weekly) / Day of month (monthly)

Always:
- Recipient Email
- Subject (optional)
- Body message (optional)
- Schedule / Send button

### Section 3: Scheduled Email Data
- Table: ID, recipient, frequency, time, active, last sent, actions
- Activate/Deactivate toggle per row
- Delete button
- "Test Send Emails" button (admin)

### Export status
Text line below buttons showing last export result.

---

## Component library (CSS classes)

Implement as reusable classes in `components.css`:

| Class | Use |
|-------|-----|
| `.card` | White card, rounded 1rem, shadow |
| `.card-header` | Green gradient header |
| `.card-body` | Padded content |
| `.btn-primary` | Green gradient button |
| `.btn-success` | Green solid |
| `.btn-danger` | Red gradient |
| `.alert-info` | Blue info banner |
| `.alert-warning` | Yellow warning |
| `.alert-secondary` | Gray filter note |
| `.form-label` | Uppercase small labels |
| `.form-control` | Rounded inputs |
| `.empty-state-*` | Empty state components |
| `.toast` | Notification popup |

---

## JavaScript module responsibilities

| File | Responsibility |
|------|----------------|
| `api.js` | `api.get/post`, attach JWT, handle 401 → login |
| `auth.js` | Token storage (sessionStorage), logout |
| `filters.js` | Filter state object, debounce, sync UI ↔ state |
| `saved-views.js` | localStorage CRUD |
| `router.js` | Tab switching, update URL hash `#summary` |
| `pages/*.js` | Fetch data, render charts/tables per page |

### Filter state object (global)
```javascript
const filterState = {
  farm_id: 'KF',
  year: 2024,
  month: 'All',
  day: 'All',
  sex: ['Overall'],
  treatment: ['Overall'],
  breed: ['Overall'],
  mob: ['Overall'],
  eid: ['Overall'],
  measure: 'finalpweight'
};
```

On any filter change → debounce 300ms → `POST /api/data/query` → dispatch `filters:changed` event → active page re-renders.

---

## Accessibility requirements

- All inputs have `<label>` or `aria-label`
- Focus visible outline on interactive elements
- Color contrast ≥ 4.5:1 for body text
- Chart images have `aria-label` describing chart type
- Keyboard navigable nav tabs (arrow keys)

---

## Assets to include

| Asset | Source |
|-------|--------|
| `login_background.png` | Copy from original `src/` or use similar stock image |
| Farm logos | Upload via admin; dev placeholders OK |
| Favicon | Cattle/farm icon |
