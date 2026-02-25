# Communication Full View — V2 Implementation Corrections

**Purpose:** This document identifies gaps between the current V2 implementation (screenshot) and the approved PRD specifications. Each issue references the specific PRD section Claude Code should re-read before implementing the fix.

**Source PRD:** `PRDs/communication-view-prd.md`

---

## Issue 1: Sender Is Missing From the Content Card Header

**Status:** NOT IMPLEMENTED

**What V2 shows:** The Content Card header starts with "To: doug@dougbower.com" — there is no sender name or sender email visible in the header area.

**What the PRD requires (Section 7.1 — "Header section — Sender"):**

The sender is the **first and most prominent element** in the header:

- **Sender display name** on the first line — large, bold, high contrast. This is the most prominent element in the header after the subject line. If the sender is unresolved (no CRM contact), the email address renders in the name position instead.
- **Sender email address** on the second line — smaller, lighter weight.
- Sender name is a clickable link to the Contact record if resolved.

**Expected rendering:**

```
Matt Brennan                                    Dec 9, 2015
mbrennan@lovelandexcavating.com                    4:05 PM

To: **Doug Bower**
...
```

The sender is the answer to "who sent this?" and must be the user's first anchor point.

---

## Issue 2: Recipient Line Does Not Follow Spec Rules

**Status:** PARTIALLY IMPLEMENTED (wrong format)

**What V2 shows:** "To: doug@dougbower.com" — just a raw email address with no name resolution, no bolding, no user-first ordering.

**What the PRD requires (Section 7.1 — "Header section — Recipients"):**

1. If the current user is a To recipient, their name appears **first and bold**.
2. After the current user (if present), remaining To recipients are listed alphabetically by last name.
3. Show a maximum of **three names** per line (including the current user).
4. If more recipients exist beyond three, show **"+X Others"** as a clickable link to the Participants Card.
5. CC line follows the same rules. Omitted if no CC recipients.
6. Resolved contacts render as clickable links. Unresolved show email address with a subtle indicator.

**Expected rendering for this email:**

```
To: **Doug Bower**
```

(Single recipient, so just one bold name. No "+X Others" needed here.)

---

## Issue 3: Subject Line Not Prominent Enough

**Status:** PARTIALLY IMPLEMENTED (present but undersized)

**What V2 shows:** "RE: 235" renders at approximately the same size as body text.

**What the PRD requires (Section 7.1 — "Subject line"):**

- Rendered as the **largest, boldest text on the entire Content Card** — a clear heading below the recipient lines, above the content divider.
- Prominent enough that the user's eye goes to it naturally as the answer to "what is this about?"

The subject line should visually dominate the card. "RE: 235" should be unmissable.

---

## Issue 4: Quoted Reply Chain Has No Visual Treatment

**Status:** NOT IMPLEMENTED — this is the highest-impact visual issue

**What V2 shows:** The "Original Message" block — including the forwarded email headers (From, Sent, To, Subject), the message body, the signature block (Matthew J. Brennan, Chief Executive Officer, address, phone number, quote) — all renders at identical visual weight to the actual new message. The user cannot instantly distinguish what was written in *this* email vs. what was forwarded.

**What the PRD requires (Section 7.1 — "Body — Two-Zone Rendering"):**

The body renders in two visual zones:

**Primary zone (new message content):**
- Full contrast, full text weight.
- This is the content the sender actually wrote in this email.

**Quoted zone (reply chain):**
- **Vertical bar** — A subtle left-border line running the full height of the quoted block.
- **Reduced opacity** — Text renders at reduced contrast (lighter color or lower opacity).
- **Indent** — The quoted block is indented from the left edge.
- Nested quotes get additional vertical bars and indentation per nesting level.
- "On [date], [person] wrote:" attribution lines are part of the quoted zone.

**Pipeline implication:**
- cleaned_html should wrap quoted portions in a semantic element (e.g., `<blockquote class="quoted-reply">`) so the UI can apply the two-zone visual treatment.
- Signatures, boilerplate, and promotional footers should still be **stripped entirely** — only the meaningful quoted reply chain is preserved with markup.

**In the V2 screenshot specifically:**
- "The site requires a username / password." is the PRIMARY ZONE (full contrast).
- Everything from "----- Original Message -----" downward is the QUOTED ZONE (vertical bar, reduced opacity, indent).
- The signature block (Matthew J. Brennan, CEO, address, phone, motto) should be **stripped entirely** by the pipeline — it is boilerplate, not meaningful quoted content.

---

## Issue 5: Participants Card — Missing Required Information

**Status:** PARTIALLY IMPLEMENTED (minimal)

**What V2 shows:** A single row showing "doug@dougbower.com" with a "To" badge. No sender listed, no display names, no company info, no receiving account.

**What the PRD requires (Section 8.2 — Participants Card Rendering):**

Each participant needs:

| Element | What to show |
|---|---|
| Name | Contact display name (clickable link if resolved). If unresolved, show the email address with an unresolved indicator. |
| Role | "Sender", "To", "CC", "BCC" — right-aligned on the name line |
| Email/phone | The specific address used in this communication, below the name |
| Receiving account | For account owner only: "via [account address]" — which of the user's accounts received this |
| Title + Company | From the contact's employment record. Below the address. Omitted if no employment record. |
| (You) badge | If this participant is the account owner |

**Expected rendering for this email:**

```
┌──────────────────────────────────────────────────┐
│  Participants                                     │
│──────────────────────────────────────────────────│
│  Matt Brennan                 Sender              │
│  mbrennan@lovelandexcavating.com                  │
│  CEO · Loveland Excavating                        │
│                                                   │
│  Doug Bower                   To       (You)      │
│  via doug@dougbower.com                           │
│  Owner · CRMExtender                              │
└──────────────────────────────────────────────────┘
```

The **sender is missing entirely** from the current implementation. Both parties should be listed.

---

## Issue 6: Identity Card — Correct But Verify

**Status:** IMPLEMENTED CORRECTLY

**What V2 shows:** "Email Communication" with date/time on the right. This matches the PRD spec (Section 6.1). No direction, source, or provider account shown — correct per spec.

**No changes needed.** Just confirming this is right.

---

## Issue 7: Two-Column Layout — Rendering But Verify Logic

**Status:** APPEARS IMPLEMENTED

**What V2 shows:** Content on the left, CRM cards on the right. This is correct.

**Verify the decision logic (Section 5.1):**

Two-column requires BOTH conditions:
1. Container width ≥ 900px
2. Two or more visible, non-collapsed CRM cards

In the screenshot, Participants + Conversation + Metadata (collapsed) = 2 visible non-collapsed cards (Participants and Conversation). Metadata is collapsed so it does not count. The condition is met. This appears correct.

---

## Priority Order for Fixes

1. **Issue 4 (Quoted reply visual treatment)** — Highest visual impact. The body is the largest area on screen and currently unreadable.
2. **Issue 1 (Missing sender)** — The user cannot tell who sent the email.
3. **Issue 2 (Recipient formatting)** — User's name should be bold and first.
4. **Issue 3 (Subject prominence)** — Needs to be the dominant text element.
5. **Issue 5 (Participants Card)** — Missing sender, missing names, missing detail.
6. **Issues 6-7** — Already correct, just verify.

---

## Reference

All specifications are in `PRDs/communication-view-prd.md`:

| Issue | PRD Section |
|---|---|
| Sender display | 7.1 — "Header section — Sender (left side)" |
| Recipient rules | 7.1 — "Header section — Recipients" |
| Subject prominence | 7.1 — "Subject line" |
| Two-zone body | 7.1 — "Body — Two-Zone Rendering" |
| Participants Card | 8.2 — "Rendering" |
| Identity Card | 6.1 — "Communication Identity Card Rendering" |
| Layout logic | 5.1 — "Layout Logic" |
