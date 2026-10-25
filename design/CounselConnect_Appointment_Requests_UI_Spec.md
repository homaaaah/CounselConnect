# CounselConnect — Appointment Requests UI Specification

## 1. Purpose and instructions for the implementing LLM

Create the counselor-facing **Appointment Requests** page for CounselConnect using this document as the visual reference. Match the supplied screenshot's composition, spacing, card hierarchy, typography, colors, and expanded/collapsed states. The deliverable described here is a frontend page, not an entire counseling system.

The reference image is `image(5).png`, approximately **805 × 605 pixels**. Coordinates and sizes below are approximate measurements in that image, not original design-file values. Treat them as proportions when adapting to a larger viewport. Font family, exact color values, interactions, and mobile layouts cannot be conclusively determined from a static screenshot.

**Evidence labels:**

- **Observed:** visible in the screenshot.
- **Estimated:** a visual approximation intended to reproduce it.
- **Recommended:** proposed implementation behavior where the screenshot provides no evidence.

Do not treat recommended interactions as confirmed project business requirements. Do not add unrelated dashboard widgets, facial expression analysis, chat, or session features to this page.

## 2. Page identity and visual direction

| Property | Specification |
| --- | --- |
| Application | CounselConnect |
| User context | Counselor/staff reviewing incoming student appointment requests |
| Active navigation item | Appointments |
| Main heading | Appointment Requests |
| Supporting text | Review and manage incoming booking requests from your students. |
| Overall composition | Full-width top navigation above a single-column request list |
| Visual tone | Calm, clean, professional academic counseling interface |
| Primary accent | Medium/dark green |
| Main surface | Very pale cool gray background with white cards |
| Shape language | Rounded cards, rounded inputs, compact pills, soft icon containers |
| Density | Compact desktop layout, generous horizontal breathing room |
| Key emphasis | First request expanded and outlined in green |

## 3. Overall layout and approximate geometry

The page has no visible sidebar. A white top header spans the viewport. Below it, a pale gray content area contains the title/toolbar, four stacked request cards, and centered pagination.

| Region | Approximate screenshot bounds | Notes |
| --- | --- | --- |
| Header | x: 0–805, y: 1–45 | About 44 px high |
| Main content | x: 25–782, y: 66 onward | About 24–28 px outer horizontal padding |
| Title | x: 28, y: 70 | Green, bold, left aligned |
| Subtitle | x: 28, y: 95 | Smaller dark gray text |
| Search/control group | x: 570–779, y: 80–105 | Right side of the title area |
| Expanded request | x: 25–782, y: 124–300 | About 757 px wide and 176 px high |
| Collapsed request 2 | x: 28–779, y: 305–378 | About 73 px high |
| Collapsed request 3 | x: 28–779, y: 385–458 | About 73 px high |
| Collapsed request 4 | x: 28–779, y: 466–539 | About 73 px high |
| Pagination | x: 296–511, y: 568–587 | Compact horizontal control |

**Estimated layout rules:**

- Use a full-width main wrapper with approximately 24–28 px padding at the reference size.
- Keep cards aligned to the same left and right edges, allowing the selected card's outline to extend slightly beyond the other cards.
- Place the list roughly 18–22 px below the subtitle.
- Use approximately 6–8 px between cards.
- Leave approximately 28–30 px between the last card and pagination.
- Use normal document flow; do not position the entire page with absolute coordinates.
- Let long content increase card height naturally.

## 4. Shared navbar dependency

Use the reusable navbar defined in [CounselConnect_Navbar_UI_Spec.md](CounselConnect_Navbar_UI_Spec.md). Set its active item to **Appointments**. The account area is text-only: counselor name and role, with no profile image, avatar fallback, or placeholder. The brand logo is retained. Navbar layout, styling, navigation, account content, and responsive rules are owned by that separate specification.

## 5. Page heading and toolbar

### 5.1 Heading block

- Main title: **Appointment Requests**.
- Estimated size: 18 px at reference scale, weight 700.
- Color: deep green.
- Subtitle: **Review and manage incoming booking requests from your students.**
- Estimated subtitle size: 9–10 px, regular weight, dark neutral gray.
- Keep about 5–7 px between the title and subtitle.

### 5.2 Toolbar controls

Position on the right side of the heading area, around the subtitle's vertical level.

| Control | Appearance | Estimated reference size |
| --- | --- | --- |
| Search | White rounded input, faint gray border, magnifying glass on the left, placeholder `Search` | 146 × 25 px |
| Filter | White rounded square with dark funnel icon | 26 × 25 px |
| Sort | White rounded square with small vertical ordering icon | 24 × 25 px |

Use roughly 7 px gaps. The search placeholder is light gray. The filter and sort icons have no visible text labels. Their menus and available options are not shown.

**Recommended:** give icon-only controls accessible names such as `Filter appointment requests` and `Sort appointment requests`.

## 6. Request card structure

Each request is a rounded white card with these shared regions:

1. Student identity at the upper left.
2. Status pill at the upper right.
3. A horizontal metadata strip below the identity.
4. A caret aligned at the metadata strip's far right.
5. Expanded details and action buttons when open.

### 6.1 Common card styling

- Estimated radius: 16–18 px.
- White surface and very subtle gray border.
- Minimal shadow, if any; separation is mostly achieved through the background, border, and spacing.
- Inner horizontal padding around 13–16 px.
- First card uses a thin green outline, roughly 1–1.5 px.
- Other cards have soft neutral outlines.
- Collapsed card text/icons appear more muted than the expanded card. This is visual hierarchy; do not infer that the cards are disabled.

### 6.2 Student identity

- Photo: rounded square, approximately 35–36 px; use `object-fit: cover`.
- Name: bold, dark slate, approximately 12 px.
- Program/year: approximately 8–9 px, muted gray, directly beneath the name.
- Expanded Alex Rivera card includes a small bright green dot overlapping the photo's lower-right corner with a light border. The dot's meaning is not specified by the screenshot.
- Do not label the dot as verified availability, wellbeing, or an online status unless that meaning is confirmed separately.

### 6.3 Pending status pill

All four visible cards show **PENDING REVIEW**.

- Pale cream/amber background.
- Orange text, uppercase, small and semibold/bold.
- Rounded capsule shape.
- Estimated dimensions: 79–89 px wide and 16–18 px high.
- Align near each card's upper-right corner.
- On the expanded card, a small muted timestamp appears underneath: **Received 12 minutes ago**.
- Timestamps are not visible on the three collapsed cards.

## 7. Expanded request: Alex Rivera

### 7.1 Header content

| Field | Visible content |
| --- | --- |
| Student | Alex Rivera |
| Program/year | B.Sc. Computer Science • 3rd Year |
| Status | PENDING REVIEW |
| Relative timestamp | Received 12 minutes ago |

### 7.2 Metadata strip

Below the identity, place a very pale gray horizontal band with rounded corners. At the reference size it spans approximately x: 42–766 and y: 173–202.

Use three broad columns separated by faint vertical lines, followed by a small caret area:

| Column | Icon | Small uppercase label | Value |
| --- | --- | --- | --- |
| Date | Calendar | DATE | Sept 14, 2026 |
| Time | Clock | TIME | 1:00 PM (45m) |
| Mode | Location pin | MODE | Face-to-face |

- Icons are green and sit in small white rounded containers.
- Labels use muted gray, tiny uppercase text with slight letter spacing.
- Values use dark slate, small bold text.
- Icon and text stack align horizontally within each column.
- Separators are inset vertically and do not touch the strip's outer edges.
- Far-right caret points upward and is green, indicating expanded content.

### 7.3 Primary concern block

Below the metadata strip, render a pale neutral rounded panel, approximately x: 42–766, y: 207–258.

- Thin light green vertical accent at the left edge.
- Internal padding approximately 10 px.
- Label: **PRIMARY CONCERN**, small uppercase muted text with letter spacing.
- Body: smaller italic gray text, wrapping across two lines in the screenshot.

Visible concern copy, transcribed as closely as the image allows:

> "I've been feeling quite overwhelmed lately with upcoming midterms and finding it difficult to manage my time effectively. I'd like to discuss some strategies for stress management..."

The trailing ellipsis is visible. It is unclear whether it is stored text or UI truncation. Keep it in the reference fixture; do not assume the actual concern should always be truncated.

### 7.4 Action row

Place the actions below the concern panel, approximately y: 267–292.

| Action | Placement | Styling |
| --- | --- | --- |
| Accept Appointment | Left | Solid green, white bold text, leading checkmark |
| Reschedule | Immediately beside Accept | White surface, subtle gray border, dark text |
| Reject | Far right | White surface, faint red border, dark red text |

Estimated reference sizes:

- Accept: 125 × 25 px.
- Reschedule: 72 × 25 px.
- Reject: 52 × 25 px.
- Radius: 7–8 px.
- Gap between left buttons: 5–6 px.

Use a flexible spacer to push Reject to the right. The action row spans the card's inner width.

## 8. Collapsed requests

Three collapsed cards follow the expanded card. Each retains its student identity, pending pill, metadata strip, and downward caret. Concern details and action buttons are hidden.

| Order | Student | Program/year | Date | Time | Mode |
| --- | --- | --- | --- | --- | --- |
| 2 | Jamie Chen | B.A. Psychology • 1st Year | Sept 15, 2026 | 10:00 AM | Online Call |
| 3 | Chelly Chen | B.A. Psychology • 1st Year | Sept 16, 2026 | 10:00 AM | Online Call |
| 4 | Joanna Chen | B.A. Psychology • 1st Year | Sept 21, 2026 | 10:00 AM | Online Call |

**Observed details:**

- Calendar, clock, and video-camera icons appear in muted gray.
- The metadata strip presents values without the tiny DATE/TIME/MODE labels visible on the expanded card.
- Vertical dividers remain between metadata groups.
- The far-right caret points downward and is light gray.
- Student names remain stronger than their secondary text.
- Different portrait images are used for each student; one appears grayscale. Do not apply a grayscale filter to all collapsed cards.
- No durations are shown for these three requests.

## 9. Pagination

**Observed:** a small centered rounded gray pagination bar below the list.

- Left chevron, numbered pages appearing to run **1–6**, and right chevron.
- Subtle inset/drop shadow and muted neutral styling.
- Numbers and arrows are very small in the source image.
- A clearly selected page style cannot be confidently determined at this resolution.

**Recommended:** use a distinguishable active page, keyboard focus states, and disabled previous/next states at boundaries. Preserve the compact centered composition, but increase target sizes for a production interface.

## 10. Estimated design tokens

These are visual approximations, not sampled authoritative brand values.

| Token | Suggested value | Usage |
| --- | --- | --- |
| `color-page` | `#F7F9FB` | Main background |
| `color-surface` | `#FFFFFF` | Header, cards, inputs, buttons |
| `color-surface-subtle` | `#F8FAFB` | Metadata strip and concern panel |
| `color-primary` | `#207524` | Heading, selected nav, primary action |
| `color-primary-border` | `#21812B` | Expanded card outline |
| `color-primary-soft` | `#D8EAD8` | Concern accent |
| `color-text` | `#374151` | Primary text |
| `color-text-muted` | `#7B8493` | Program/year and secondary details |
| `color-icon-muted` | `#B1B8C2` | Collapsed icons and caret |
| `color-border` | `#E9EDF1` | Dividers, neutral borders |
| `color-pending-bg` | `#FFFAEB` | Pending pill |
| `color-pending-text` | `#D97724` | Pending pill text |
| `color-danger` | `#8F2525` | Reject text |
| `color-danger-border` | `#EAD6D6` | Reject outline |
| `color-presence-dot` | `#22C55E` | Visible photo indicator |
| `radius-card` | `18px` | Request cards |
| `radius-control` | `8px` | Inputs and buttons |
| `radius-pill` | `999px` | Status capsule |
| `font-family` | `Arial, Helvetica, sans-serif` | Close neutral sans-serif starting point |

Suggested screenshot-scale typography: 18 px title; 12 px student names; 9–10 px subtitle/navigation; 8–9 px metadata/body/buttons; 6–7 px micro-labels and status. These tiny sizes reflect the supplied image and may be downscaled from an original design. For a usable full-size application, use a consistent larger scale, such as 24–28 px title, 16 px names, 13–14 px body/controls, and 11–12 px labels. Keep the visual hierarchy and proportions.

## 11. Recommended component hierarchy

```text
AppointmentRequestsPage
  AppHeader
    (see CounselConnect_Navbar_UI_Spec.md; text-only account identity)
  MainContent
    PageHeadingAndToolbar
      HeadingBlock
      SearchField
      FilterButton
      SortButton
    RequestList
      AppointmentRequestCard (repeated)
        StudentIdentity
        RequestStatus
        AppointmentMetadata
        ExpandCollapseButton
        PrimaryConcernPanel (when expanded)
        RequestActions (when expanded)
    Pagination
```

Use reusable components for expanded and collapsed requests rather than separate duplicated card implementations. This hierarchy is a suggested organization, not a framework requirement.

## 12. Recommended interaction contract

The screenshot confirms visual states, not behavior after an action. The following are frontend recommendations to connect to confirmed business rules later:

| Interaction | Suggested behavior |
| --- | --- |
| Initial state | Display Alex Rivera expanded and the other three collapsed to reproduce the screenshot |
| Expand/collapse | Caret button toggles details; optionally use a single-open accordion to retain the reference's composition |
| Search | Filter by student name; add other searchable fields only when supported by requirements |
| Filter | Open an anchored panel; populate only with supported filter fields |
| Sort | Open a sort menu; actual fields and default ordering require product decisions |
| Accept Appointment | Invoke the supplied accept handler and display loading/success/error feedback |
| Reschedule | Invoke the scheduling flow; available slots and approval logic must come from the system's rules |
| Reject | Open the configured rejection flow; whether a reason is required remains a business decision |
| Pagination | Update visible requests and active page, preserving the chosen filter/search state |

Prevent duplicate submissions while an action is pending. Do not mark an appointment accepted/rejected in persistent state until the operation succeeds. Exact statuses after review, notifications, conflict handling, and appointment policies are outside what the screenshot establishes.

## 13. Recommended responsive adaptation

Only the desktop/reference layout is observed. Use these as proposed responsive rules:

### Wide desktop

- Keep the horizontal header and single-column card list.
- Retain a left heading and right toolbar.
- Keep metadata in three columns and Reject aligned to the far right.
- At much wider widths, consider a centered content container around 1200–1440 px instead of letting lines become excessively long.

### Tablet

- Use the navbar responsive rules in the separate navbar specification.
- Allow the toolbar to wrap below the heading.
- Keep metadata in columns while values remain readable.

### Mobile

- Use the compact navbar defined in the separate navbar specification; no profile image is required.
- Stack heading and toolbar, with search taking the available width.
- Keep student identity and status on one row when possible; allow wrapping without overlap.
- Stack metadata fields vertically or use a two-column arrangement with the final field wrapping.
- Wrap action buttons; use sufficient touch targets.
- Let cards grow vertically and keep concern text readable.
- Avoid horizontal page scrolling.

## 14. Accessibility and additional UI states

These are implementation recommendations, not additional elements visible in the screenshot:

- Use a semantic header/nav/main and a single main page heading.
- Represent cards as list items or articles with names as headings.
- Use real buttons for actions and accordion toggles.
- Give the toggle `aria-expanded` and `aria-controls` tied to the detail panel.
- Avoid nesting action buttons inside another clickable button/card container.
- Support keyboard navigation with clearly visible focus outlines.
- Provide accessible labels for search and all icon-only buttons.
- Use meaningful alternative text for the brand; use empty portrait alt text when the adjacent name already identifies the student.
- Do not communicate pending status or expansion solely through color.
- Increase small text contrast and pointer targets for production use, even if the source uses faint grays and tiny controls.
- Define loading, empty list, no search results, action-in-progress, and request-failed states.
- Handle missing avatars using initials and long names without breaking alignment.
- Treat student concerns as sensitive content; avoid putting full concern text into incidental logs or unrelated tooltips.

## 15. Visual acceptance checklist

- [ ] Reuse the separately specified navbar with Appointments active and a text-only account area; no profile image.
- [ ] Pale gray page background with a green Appointment Requests heading.
- [ ] Exact subtitle and compact right-side search/filter/sort controls.
- [ ] Four request cards in the correct order.
- [ ] Alex Rivera expanded with green outline; the other three collapsed.
- [ ] Every request has a pale amber PENDING REVIEW pill.
- [ ] Expanded metadata has labels, green icons, and the upward caret.
- [ ] Collapsed metadata has muted icons, values, and downward carets.
- [ ] Primary concern is italic inside a pale inset panel with a green left accent.
- [ ] Accept and Reschedule are grouped left; Reject is aligned right.
- [ ] Compact pagination is centered below the list.
- [ ] Cards align consistently and preserve the screenshot's relative spacing.
- [ ] Responsive and loading/error states are implemented without inventing business logic.

## 16. Copy-ready implementation prompt

> Build the CounselConnect counselor-facing Appointment Requests page using this specification and the attached screenshot. Reproduce its visual hierarchy: the reusable navbar from CounselConnect_Navbar_UI_Spec.md with Appointments active and no account profile image, pale gray background, green page title, compact search/filter/sort toolbar, and four rounded request cards. Show Alex Rivera expanded with a green border, three labeled metadata columns, a primary concern panel, and Accept Appointment / Reschedule / Reject actions. Show Jamie Chen, Chelly Chen, and Joanna Chen collapsed with muted metadata and downward carets. Use the exact visible fixture content documented above. Match relative spacing and proportions before adding decorative details. Use reusable components, semantic markup, accessible accordion controls, and responsive behavior. Keep unspecified business rules behind configurable handlers. Treat measurements, fonts, and colors as estimates, and distinguish screenshot fidelity from proposed usability improvements. Do not add unrelated pages or counseling features.
