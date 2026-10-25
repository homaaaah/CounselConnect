# CounselConnect — Navbar UI Specification

## 1. Scope and reference

Build a reusable top navigation bar for CounselConnect. This specification is separate from `CounselConnect_Appointment_Requests_UI_Spec.md`, which covers the page body.

Reference: `image(5).png`, approximately 805 × 605 px. The navbar occupies the full width, approximately y: 1–45. Measurements, colors, and font sizes are visual estimates rather than original design values. The screenshot shows desktop only; responsive rules below are recommendations.

**Requested change from the screenshot:** omit the counselor profile image entirely. Show only the counselor’s name and role beside the notification bell. Do not require an image URL, initials avatar, or image placeholder. The brand logo remains a separate branding element.

## 2. Navbar layout and content

### 2.1 Left brand

**Observed:**

- Small circular emblem at the far left, around 22–24 px in diameter.
- Emblem contains green and muted gold shapes on a light background with a green outer ring. Its internal artwork is too small to reproduce accurately from this screenshot.
- Bold dark wordmark: **CounselConnect**.
- The logo begins around x: 33, and the wordmark around x: 67.

Use the application's actual logo if available. Otherwise use a clearly identified placeholder with the same size and circular silhouette; do not invent official logo artwork.

### 2.2 Primary navigation

Render these links in this order:

1. Dashboard
2. Appointments
3. Sessions
4. Schedule
5. History

**Observed styling:**

- Links run horizontally beside the brand.
- Dark neutral text for inactive items.
- **Appointments** uses green text and a thin green underline.
- Small, moderately bold typography with consistent horizontal gaps.
- No enclosing tab backgrounds or large navigation buttons.

**Estimated:** 8–10 px text at screenshot scale, approximately 18–22 px between items. Use proportionally larger text if the application is rendered at a larger design size.

### 2.3 Right account area

From left to right:

- Dark green/gray notification bell.
- Tiny red notification badge near the bell's upper-right edge; appears to show **1**.
- Two-line identity block:
  - **Dr. Sarah Jenkins** in bold dark text.
  - **Academic Specialist** in smaller muted text.
- No profile photo, avatar, initials badge, or image placeholder. The account area ends with the counselor’s text identity.

The account block sits near the header's right edge, vertically centered. Align the name and role to the right and retain comfortable right padding after removing the screenshot’s avatar. Use a subtle bottom divider/shadow under the header. A sticky header is optional behavior, not established by the image.

## 3. Estimated layout and styling

| Element | Specification |
| --- | --- |
| Header surface | White `#FFFFFF`, full viewport width |
| Height | Approximately 44 px at screenshot scale; use 60–72 px if scaling for readable production sizing |
| Horizontal inset | Approximately 28–33 px at reference scale |
| Alignment | Brand, navigation, and account controls vertically centered |
| Layout | Brand left; links beside it; flexible space; notification and text-only account summary right |
| Logo | Circular, approximately 22–24 px at reference scale |
| Brand text | Dark slate `#374151`, bold |
| Active link | Green `#207524`, thin underline, no filled pill |
| Inactive links | Dark neutral text, moderately bold |
| Secondary identity text | Muted gray `#7B8493` |
| Notification badge | Small red circle `#E44D53` near bell’s upper-right corner |
| Bottom edge | Subtle divider `#E9EDF1` or soft shadow |
| Font | Neutral sans-serif such as Arial/Helvetica; exact font unknown |

Reference text sizes are roughly 8–10 px for navigation and brand, with a smaller role line. They may reflect a downscaled design. Prefer 13–14 px links, 15–16 px brand text, 13–14 px account name, and 11–12 px role for a readable production implementation. Preserve the hierarchy and compact appearance.

Use flex layout and natural document flow. Keep brand and account text from shrinking into illegibility. The right account group contains only the bell and the two-line identity block; do not reserve empty space for an avatar.

## 4. Reusable component and data contract

Suggested components: `AppNavbar`, `Brand`, `PrimaryNavigation`, `NotificationButton`, and `AccountSummary`.

| Input | Purpose |
| --- | --- |
| `brandName` | Defaults to CounselConnect |
| `brandLogo` | Optional actual brand logo; if unavailable, use a clearly identified brand placeholder |
| `navigationItems` | Ordered labels and actual configured destinations |
| `activeItem` | Current navigation item; Appointments for the reference page |
| `notificationCount` | Reference fixture appears to show 1; actual value comes from the application |
| `displayName` | Reference fixture: Dr. Sarah Jenkins |
| `roleLabel` | Reference fixture: Academic Specialist |
| `onNotificationsOpen` | Optional notification handler when supported |

There is no profile-image input. Use real configured routes; do not invent paths or notification contents. The visible counselor identity is a reference fixture, not a hardcoded identity for every user.

## 5. Recommended responsive and interaction behavior

- Keep the observed horizontal layout while all regions fit comfortably.
- On narrow screens, place navigation in an accessible collapsible menu; this is a proposed adaptation, not visible in the screenshot.
- Preserve the brand and notification access; allow the text identity block to wrap or move into the menu if necessary.
- Do not introduce a profile image at any breakpoint.
- Use a visible hover/focus state on navigation links and the bell.
- Set `aria-current="page"` on the active navigation link.
- Use a real button with an accessible notification label; announce the unread count when provided.
- Give the brand logo suitable alternative text without redundantly repeating adjacent brand text.
- If account actions exist, use a text-based menu trigger with clear keyboard interaction. A menu and its contents are not established by the screenshot.
- A sticky header is optional and requires a product decision; normal document flow is sufficient for matching the screenshot.

## 6. Acceptance checklist

- [ ] Full-width white navbar with a subtle lower edge.
- [ ] Circular brand logo and bold CounselConnect wordmark on the left.
- [ ] Dashboard, Appointments, Sessions, Schedule, History in that order.
- [ ] Appointments green and underlined in the reference state.
- [ ] Notification bell with small red badge on the right.
- [ ] Dr. Sarah Jenkins above Academic Specialist in a text-only identity block.
- [ ] No profile image, avatar fallback, image placeholder, or reserved avatar gap.
- [ ] Readable layout and accessible controls on narrow screens.

## 7. Copy-ready implementation prompt

> Create the reusable CounselConnect navbar from this specification. Use a white full-width horizontal header, circular brand logo and bold wordmark on the left, the five navigation links in their documented order, and green text with a thin underline for the active item. On the right, place the notification bell and a two-line text-only counselor identity. Do not include or require a profile image, initials avatar, or avatar placeholder. Match the supplied screenshot’s proportions while keeping production text readable. Make the active item and identity configurable, use actual configured routes, and support accessible responsive navigation. Keep the appointment request cards and page toolbar outside the navbar.
