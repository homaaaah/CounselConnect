# CounselConnect — Counseling Session History UI Specification

## 1. Purpose and implementation scope

Build the counselor-facing **History** page using the attached `image(6).png` as the visual reference. This document describes the page body: heading, search/filter/sort toolbar, session history table, report actions, and pagination.

Reuse the navbar defined in [CounselConnect_Navbar_UI_Spec.md](CounselConnect_Navbar_UI_Spec.md) and set **History** as the active navigation item. Preserve the previously requested text-only counselor account area: show the counselor’s name and role without a profile image, avatar fallback, or placeholder. The student portraits in history rows are separate from the account profile and remain part of this page’s reference design.

The screenshot is approximately **1052 × 747 px**. All coordinates, dimensions, colors, and font sizes below are visual estimates, not original design-file values. Use them to match proportions rather than fixing every element to an absolute position.

### Evidence labels

- **Observed:** directly visible in the screenshot.
- **Estimated:** a suggested approximation of a visible design detail.
- **Recommended:** proposed frontend behavior or adaptation not established by the static image.

Do not infer report contents, access policies, session completion rules, or backend behavior from this page. Keep those connected to the actual system requirements.

## 2. Page identity and overall visual style

| Property | Specification |
| --- | --- |
| Application | CounselConnect |
| Page title | History |
| Active navbar item | History |
| Subtitle | Review and manage previous counseling of your students. |
| Main content | Table-like list of previous counseling sessions |
| Primary action per record | View Reports |
| Layout | Single main content column; no sidebar |
| Background | White or nearly white with a subtle cool tint near the header |
| Primary accent | Deep green for the title and active navigation state |
| Main text | Dark navy/slate |
| Secondary text | Muted blue-gray |
| Row treatment | Thin neutral separators, student identity left, pale inset surface across remaining columns |
| Action treatment | Rounded pale pink-gray button with dark slate text |
| Visible records | Eight repeated sample rows |

The composition is restrained and spacious. Compared with the appointment requests page, this page uses a table/list presentation rather than expanded request cards. Avoid applying the green selected-card outline, pending pills, concern panels, accordion controls, or appointment approval buttons to history rows.

## 3. Page geometry and spacing

| Region | Approximate screenshot bounds | Notes |
| --- | --- | --- |
| Shared navbar | x: 0–1052, y: 0–57 | Reuse the separate navbar specification |
| Main content width | x: 37–1019 | Approximately 982 px |
| Heading | x: 37, y: 90 | Left aligned |
| Subtitle | x: 37, y: 123 | Directly beneath heading |
| Toolbar | x: 741–1019, y: 104–137 | Right aligned in the title area |
| Table column labels | y: 170–179 | Unfilled header area |
| Table body | x: 37–1019, y: 194–675 | Eight rows, approximately 60 px each |
| Pagination | x: 385–671, y: 709–734 | Centered beneath the table |

**Estimated layout rules:**

- Use approximately 36–38 px horizontal page padding at the reference width.
- Leave approximately 30–34 px between the navbar’s bottom edge and the heading’s top.
- Keep approximately 7–9 px between the title and subtitle.
- Align the toolbar toward the right of the title/subtitle region rather than inside the navbar.
- Leave roughly 30–35 px between the subtitle and the table labels.
- Leave around 14–16 px between the column-label baseline and the first body row.
- Keep about 34 px between the last row and pagination.
- Use normal layout flow and let the list grow with content.
- Do not fix pagination to the viewport bottom; the image only establishes its position below the list.

## 4. Heading and toolbar

### 4.1 Heading block

- Title: **History**.
- Estimated typography: 23–24 px, bold, green around `#207524`.
- Subtitle: **Review and manage previous counseling of your students.**
- Estimated typography: 12 px, regular weight, dark gray.
- Keep the title and subtitle left aligned to the table’s outer left edge.

### 4.2 Search

**Observed:**

- A wide white rounded rectangle with a faint gray border.
- Small magnifying-glass icon on the left.
- Light gray placeholder text: **Search**.
- Approximate size: 194 × 33 px.
- Approximate corner radius: 10–11 px.
- No visible search submit button.

**Recommended:** use a labeled search input. Search can filter by student name when supported; additional searchable fields and server/client behavior require actual product decisions. Do not assume full report text is searchable.

### 4.3 Filter and sort

| Control | Observed visual | Estimated size |
| --- | --- | --- |
| Filter | Funnel icon in a white rounded square with subtle border | 35 × 33 px |
| Sort | Small vertically stacked up/down ordering icon in the same control style | 31 × 33 px |

Use approximately 9 px gaps between controls. Icons are muted dark slate. Available filter fields, sort options, open menus, and active-filter states are not visible in the screenshot.

**Recommended:** accessible names `Filter session history` and `Sort session history`. If date or mode filtering is implemented, populate it only with supported fields and actual values.

## 5. Session history table structure

### 5.1 Columns

Render the following four headers exactly:

| Column | Approximate horizontal center | Content and alignment |
| --- | --- | --- |
| Student | x: 159 | Header centered above identity group; row identity is left aligned |
| Date & Time | x: 404 | Centered header and values |
| Mode | x: 650 | Centered header and values |
| Action | x: 896 | Centered header and buttons |

Column headers use muted blue-gray text, approximately 11–12 px and regular weight. They sit above the body without a colored header background. There are no visible sort arrows in individual column headers.

Use four approximately equal-width columns as the starting point. At the reference width, each is roughly 245 px. Ensure the student identity has enough space for the program/year line. Row geometry suggests the left student section ends around x: 267, where the rounded inset surface begins; treat this as an approximate visual inset rather than an exact column boundary.

### 5.2 Table outer frame

- Very thin light border around the body.
- Horizontal dividers between records.
- No prominent vertical grid lines.
- White student cells.
- No zebra striping or selected row is apparent.
- Rounded surfaces are inside rows rather than a large rounded card enclosing the entire table.

### 5.3 Repeated row layout

Each of the eight rows is approximately 60 px high and contains:

1. A rounded-square student portrait on the far left.
2. A two-line student identity block to the portrait’s right.
3. A centered date value.
4. A centered session mode value.
5. A centered **View Reports** button.

The date, mode, and action areas share one extremely pale rounded horizontal inset surface, beginning after the student identity area and extending near the table’s right edge. It is approximately 48 px high, inset about 6 px vertically, with a radius around 12–15 px. The color is close to `#FAFBFC`, only slightly darker than white.

Do not style each field as an independently outlined box. Keep this surface continuous across the last three columns, with the button providing a stronger fill inside it. A row-level background layer or wrapper can reproduce it without compromising semantic table markup.

## 6. Student identity cell

### 6.1 Portrait

- Approximately 47 × 47 px at screenshot scale.
- Rounded square, approximately 12 px corner radius.
- Positioned at x: 38, with about 6–7 px vertical row inset.
- `object-fit: cover` to preserve the portrait’s aspect ratio.
- No green presence dot, badge, or status indicator is visible.
- The same Alex Rivera portrait is repeated in all eight sample rows.

The account navbar remains image-free; this does not remove student portraits from the session list. **Recommended:** if a student photo is unavailable, support an unobtrusive fallback so row layout does not break.

### 6.2 Name and academic details

| Element | Visible content | Estimated styling |
| --- | --- | --- |
| Student name | Alex Rivera | 15–16 px, bold, dark navy/slate |
| Program/year | B.Sc. Computer Science • 3rd Year | 10–11 px, regular, muted blue-gray |

- Text begins around x: 96, about 11–12 px after the portrait.
- Vertically center the combined two-line block within the row.
- Keep approximately 3–5 px between name and secondary text.
- Preserve the bullet separator between program and year.
- Allow long names or programs to wrap or truncate deliberately without overlapping the next column. Provide access to full text when truncation is used.

## 7. Date and session mode cells

### 7.1 Date & Time

Every visible row displays **Sept 14, 2026**.

- Small semibold/bold dark text, approximately 11 px.
- Horizontally and vertically centered in the date column.
- The header reads **Date & Time**, but no time value appears in the screenshot.

For visual reproduction, show the date alone. Do not invent a session time or duration. If the actual system requires both date and time, obtain the stored time and display it consistently; whether this is one line or two is a product decision outside the visible reference.

### 7.2 Mode

Every visible row displays **Face-to-Face**, with this capitalization and hyphenation.

- Small semibold/bold dark text, approximately 11 px.
- Centered in the mode column.
- Plain text without a colored badge or icon.

Do not add Online Call fixtures unless needed for additional test data. Other supported modes must come from the real system.

## 8. View Reports action

**Observed:**

- Label: **View Reports**.
- Approximate dimensions: 105 × 34 px.
- Rounded rectangle with radius around 10–11 px.
- Pale pink-gray fill, approximately `#F1E9ED`.
- Very subtle matching border or no visually distinct border.
- Dark slate semibold/bold label, approximately 11 px.
- No icon, arrow, or dropdown indicator.
- Centered in the action column with consistent width across rows.

The muted styling does not establish that the button is disabled. Implement it as an available action when a report can be viewed.

**Recommended interaction:** invoke a callback with the selected session’s unique identifier. The destination may be a report page, drawer, or modal according to the application’s existing requirements. The screenshot does not establish which one, what the report contains, or whether downloading, printing, editing, or expression analysis is included. Do not invent a report screen from this reference.

## 9. Reference fixture data

The screenshot contains eight visually identical records. Use this repetition when matching the image, but preserve separate record identity in code.

| Visible row | Student | Program/year | Displayed date | Mode | Action |
| --- | --- | --- | --- | --- | --- |
| 1 | Alex Rivera | B.Sc. Computer Science • 3rd Year | Sept 14, 2026 | Face-to-Face | View Reports |
| 2 | Alex Rivera | B.Sc. Computer Science • 3rd Year | Sept 14, 2026 | Face-to-Face | View Reports |
| 3 | Alex Rivera | B.Sc. Computer Science • 3rd Year | Sept 14, 2026 | Face-to-Face | View Reports |
| 4 | Alex Rivera | B.Sc. Computer Science • 3rd Year | Sept 14, 2026 | Face-to-Face | View Reports |
| 5 | Alex Rivera | B.Sc. Computer Science • 3rd Year | Sept 14, 2026 | Face-to-Face | View Reports |
| 6 | Alex Rivera | B.Sc. Computer Science • 3rd Year | Sept 14, 2026 | Face-to-Face | View Reports |
| 7 | Alex Rivera | B.Sc. Computer Science • 3rd Year | Sept 14, 2026 | Face-to-Face | View Reports |
| 8 | Alex Rivera | B.Sc. Computer Science • 3rd Year | Sept 14, 2026 | Face-to-Face | View Reports |

These are reference fixtures, not evidence that eight actual sessions occurred for the same student on that date. Do not group or deduplicate real sessions merely because their displayed values match.

## 10. Pagination

- Center a compact horizontal pagination control beneath the table.
- Estimated bounds: 286 × 25 px.
- Light gray pill-shaped surface, roughly `#E6E9ED`.
- Soft lower shadow.
- Left chevron, page numbers appearing to run **1–6**, then right chevron.
- Small muted numbers and darker muted arrows.
- Evenly spaced page controls.
- The active page treatment is not clearly identifiable at this resolution.

**Recommended:** clearly distinguish the current page, label previous/next controls, disable them at boundaries, and preserve search/filter/sort selections when changing pages. Eight visible rows are a reference fixture count; they do not establish a mandatory page size.

## 11. Estimated design tokens

| Token | Suggested value | Usage |
| --- | --- | --- |
| `history-page-bg` | `#FFFFFF` | Main page surface |
| `history-primary` | `#207524` | History title |
| `history-text` | `#172033` | Names and primary values |
| `history-secondary` | `#66728A` | Program/year |
| `history-header-text` | `#939DB0` | Column labels |
| `history-border` | `#EEF0F4` | Frame and row separators |
| `history-row-inset` | `#FAFBFC` | Pale surface across date/mode/action |
| `history-report-bg` | `#F1E9ED` | View Reports button |
| `history-report-text` | `#4B5568` | Action label |
| `history-control-border` | `#E7EAF0` | Search/filter/sort outline |
| `history-pagination-bg` | `#E6E9ED` | Pagination bar |
| `history-font` | `Arial, Helvetica, sans-serif` | Neutral sans-serif approximation |
| `history-row-height` | `60px` | Reference row height |
| `history-portrait-size` | `47px` | Student photo |
| `history-control-radius` | `10px` | Toolbar and report button |
| `history-row-inset-radius` | `14px` | Pale continuous inset |

For production, keep body/control text readable, for example 13–14 px, and allow rows to grow if larger typography requires it. Do not scale up only one element and lose alignment. Navbar tokens belong to the separate navbar specification.

## 12. Recommended component and data structure

Suggested reusable components:

- `SessionHistoryPage`: composes the shared navbar and main content.
- `HistoryHeading`: title and subtitle.
- `HistoryToolbar`: search, filter, sort.
- `SessionHistoryTable`: column headers and repeated records.
- `SessionHistoryRow`: student identity, date, mode, action.
- `StudentIdentity`: portrait and academic text.
- `ViewReportsButton`: selected-session action.
- `Pagination`: current page and page navigation.

Suggested data fields, with names adapted to the actual application model:

| Field | Purpose |
| --- | --- |
| `sessionId` | Stable unique session identifier and report action target |
| `studentId` | Student reference, separate from session identity |
| `studentName` | Display name |
| `studentPhotoUrl` | Optional portrait source |
| `programName` | Academic program |
| `yearLevel` | Academic year level |
| `sessionDate` | Stored session date formatted for display |
| `sessionTime` | Optional real time if available and required; not visible in the reference |
| `sessionMode` | Displayed counseling mode |
| `reportReference` | Optional existing report identifier or route data as supported |

This table describes a frontend view model, not a proposed database schema. Do not require navbar profile-image data. Use a session ID rather than student name or array index as the record key and action identifier.

## 13. Recommended states and behavior

| State/interaction | Proposed implementation |
| --- | --- |
| Initial reference | Eight fixture rows with History active |
| Search input | Filter using supported fields; reset to a valid page when result count changes |
| Filter/sort | Open accessible anchored controls; use only supported options |
| Report action | Pass selected session identity into the configured report flow |
| Loading | Keep table geometry stable with placeholders or a clear loading state |
| Empty history | Show a short empty-state message in the table body area |
| No matching results | Show a search/filter-specific message and a way to clear criteria |
| Fetch failure | Show an inline error and retry control |
| Report unavailable | Provide an explicit unavailable state when the backend indicates it; do not infer availability from button color |
| Long content | Wrap or truncate intentionally while retaining full information access |

Whether history includes only completed sessions, cancelled sessions, or other statuses is not visible. Use the system’s confirmed history inclusion rules rather than inventing status filters.

## 14. Recommended responsive adaptation

Only desktop is observed. Suggested adaptations:

### Wide screens

- Preserve the four-column alignment and generous whitespace.
- Use a centered content container if the viewport becomes much wider than the reference.
- Keep toolbar aligned right and pagination centered.

### Tablet

- Reduce outer padding and let the toolbar wrap below the title/subtitle when needed.
- Preserve readable columns while space allows.
- Avoid shrinking portraits, text, and report buttons to unusable sizes.

### Mobile

- Use the shared navbar’s mobile behavior with no account profile image.
- Stack heading and toolbar; let search occupy the available width.
- Adapt each session into a compact record card with explicit Student, Date & Time, Mode, and Action labels, or use a deliberately scrollable accessible table if preserving table structure is required.
- Keep View Reports easy to locate and activate.
- Preserve date-only display when no real time is available.
- Ensure long program names and pagination fit without causing unintended page-level horizontal scrolling.

## 15. Accessibility

- Use semantic `main`, a single `h1`, and an appropriately labeled table.
- Use `th` with `scope="col"` for column headers.
- Give icon-only toolbar and pagination controls accessible labels.
- Give the search input a proper label rather than relying solely on its placeholder.
- Use buttons or links according to whether View Reports opens UI or navigates.
- Make repeated report actions distinguishable to assistive technology using the student and actual session context; do not invent times to distinguish fixtures.
- Use empty portrait alt text when adjacent text already identifies the student.
- Support keyboard operation and visible focus indicators.
- Use sufficient text contrast and practical pointer/touch targets even if larger than the screenshot’s tiny pagination controls.
- Announce relevant loading/error changes without exposing sensitive session details unnecessarily.

## 16. Visual acceptance checklist

- [ ] Reuse the separate navbar, with History active and a text-only counselor identity.
- [ ] Green History heading and exact screenshot subtitle.
- [ ] Search, filter, and sort at the right of the heading region.
- [ ] Student / Date & Time / Mode / Action headers in the correct order.
- [ ] Eight reference rows, approximately 60 px high at screenshot scale.
- [ ] Rounded student portraits and two-line identity blocks.
- [ ] Date-only Sept 14, 2026 values, with no invented time.
- [ ] Plain centered Face-to-Face labels.
- [ ] Continuous pale inset surface across the final three columns.
- [ ] Pale pink-gray View Reports buttons, aligned consistently.
- [ ] Thin horizontal separators and subtle body frame.
- [ ] Compact centered pagination below the table.
- [ ] No appointment request status pills, accordion sections, or acceptance actions.
- [ ] Responsive and accessible states do not introduce unsupported business logic.

## 17. Copy-ready implementation prompt

> Build the CounselConnect counseling session History page using this document and image(6).png. Reuse CounselConnect_Navbar_UI_Spec.md with History active and no counselor profile image. Match the white page, green History title, exact subtitle, and right-aligned search/filter/sort controls. Render four columns labeled Student, Date & Time, Mode, and Action. Show eight repeated Alex Rivera fixture rows with rounded student portraits, B.Sc. Computer Science • 3rd Year secondary text, Sept 14, 2026, Face-to-Face, and View Reports buttons. Keep the student area white and place a continuous very pale rounded inset across each row’s date, mode, and action areas. Use subtle row dividers and pale pink-gray report buttons. Center compact pagination below. Do not invent session times, report contents, routes, or business rules. Use stable session identities, reusable components, semantic accessible markup, and responsive layout. Treat measurements and colors as approximations and distinguish screenshot details from recommended behavior.
