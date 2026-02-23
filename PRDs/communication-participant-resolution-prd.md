# Communication — Participant Resolution Sub-PRD

**Version:** 1.0
**Last Updated:** 2026-02-23
**Status:** Draft
**Entity Base PRD:** [communication-entity-base-prd.md]
**Referenced Entity PRDs:** [contact-entity-base-prd.md] (identity resolution), [contact-identity-resolution-prd.md] (resolution pipeline)

---

## 1. Overview

### 1.1 Purpose

Every communication has participants — senders, recipients, attendees. The participant resolution system links each participant to a CRM contact record, enabling cross-channel relationship intelligence. Unknown identifiers trigger the Contact Intelligence system for resolution. Pending identification never blocks communication processing — the communication flows through the entire pipeline while contact resolution proceeds in parallel.

### 1.2 Preconditions

- Communication record exists with raw participant data from the provider (email addresses, phone numbers, display names).
- Contact Intelligence system is operational for identity resolution.
- The `communication_participants` system Relation Type is registered.

---

## 2. Context

### 2.1 Relevant Fields

| Field | Role in This Action |
|---|---|
| Provider Account ID | Identifies the account owner for the is_account_owner flag. |
| Channel | Determines which identifier type to use for resolution (email for email channel, phone number for SMS, etc.). |

### 2.2 Relevant Relationships

- **Communication Participants** — System Relation Type linking Communication→Contact with role, address, display name, and account-owner metadata.
- **Contact Identifiers** — Contacts own multiple identifiers (email addresses, phone numbers, platform handles). Resolution looks up participant addresses against these identifiers.

### 2.3 Cross-Entity Context

- **Contact Identity Resolution Sub-PRD:** The Contact Intelligence system is the single source of truth for identity resolution. This sub-PRD consumes that capability — submitting unknown identifiers for resolution and receiving contact matches.
- **Contact Entity Base PRD:** Contact records are the resolution targets. Employment relationships link contacts to companies.
- **Company Domain Resolution Sub-PRD:** Email domain extraction from participant addresses triggers company auto-creation during sync.

---

## 3. Key Processes

### KP-1: Resolving Participants on a Synced Communication

**Trigger:** New communication arrives via provider sync with participant data in the raw payload.

**Step 1 — Extract identifiers:** Extract participant identifiers from the raw communication. For email: From, To, CC, BCC headers. For SMS: sender and recipient phone numbers. For calls: caller and callee numbers.

**Step 2 — Identify account owner:** Match the provider account's account_identifier against participants. Flag the matching participant as is_account_owner = true.

**Step 3 — Resolve known identifiers:** For each non-owner participant, look up the address in contact_identifiers. If found, create a participant relation instance linked to the identified contact.

**Step 4 — Handle unknown identifiers:** For unrecognized addresses, create a participant relation instance with the address but a placeholder contact reference. Submit the identifier to the Contact Intelligence system for resolution.

**Step 5 — Resolution completes (async):** When Contact Intelligence resolves the identifier (automatically or via user action), the participant relation instance is updated to point to the identified contact. `participant_resolved` event emitted.

### KP-2: Adding Participants to a Manual Communication

**Trigger:** User creates a manual communication and specifies participants.

**Step 1 — Contact selection:** User selects existing contacts from the CRM or creates new contacts inline.

**Step 2 — Role assignment:** User assigns roles (participant for calls/meetings; for manual entries, all non-owner contacts are `participant` by default).

**Step 3 — Relation creation:** Participant relation instances created with the selected contacts. No resolution needed — user explicitly identified participants.

### KP-3: Resolving a Previously Unknown Participant

**Trigger:** User identifies an unknown participant from the pending identification queue.

**Step 1 — Suggestions:** System presents suggestions: partial matches from existing contacts (same name, same company domain), or option to create a new contact.

**Step 2 — User decision:** User matches to existing contact, creates a new contact, or marks as irrelevant.

**Step 3 — Update:** Participant relation instance updated to point to the identified contact (or marked as irrelevant). `participant_resolved` event emitted. If the contact is new, employment linking and company resolution may trigger.

---

## 4. Participant Relation Type

**Supports processes:** KP-1 (step 3), KP-2 (step 3), KP-3 (step 3)

### 4.1 Requirements

Communication participants are modeled as a system Relation Type in the Custom Objects framework:

| Attribute | Value |
|---|---|
| Relation Type Name | Communication Participants |
| Relation Type Slug | `communication_participants` |
| Source Object Type | Communication (`com_`) |
| Target Object Type | Contact (`con_`) |
| Cardinality | Many-to-many |
| Directionality | Bidirectional |
| `is_system` | `true` |
| Cascade (source archived) | Cascade archive participant links |
| Cascade (target archived) | Nullify (preserve communication, mark participant as archived contact) |

### 4.2 Metadata Fields

| Field | Type | Description |
|---|---|---|
| `role` | Select | `sender`, `to`, `cc`, `bcc`, `participant` (calls/meetings) |
| `address` | Text | The identifier used in this communication (email, phone number, etc.) |
| `display_name` | Text | Display name from the communication header |
| `is_account_owner` | Checkbox | Whether this participant is the CRM user |

**Tasks:**

- [ ] CPAR-01: Register communication_participants system Relation Type
- [ ] CPAR-02: Create junction table with metadata columns
- [ ] CPAR-03: Implement participant extraction from raw communication data
- [ ] CPAR-04: Implement account owner identification from provider account

**Tests:**

- [ ] CPAR-T01: Test Relation Type registration with correct metadata fields
- [ ] CPAR-T02: Test participant extraction from email headers (From, To, CC, BCC)
- [ ] CPAR-T03: Test account owner correctly identified from provider account
- [ ] CPAR-T04: Test cascade archive on communication archival

---

## 5. Contact Resolution Integration

**Supports processes:** KP-1 (steps 3–5)

### 5.1 Design Principle

Every communication participant must be resolved to a CRM contact. The system actively works to identify all senders and recipients across all channels. Under no circumstance should a conversation be left with permanently unidentified contacts.

### 5.2 Resolution Flow

**Communications consumes from Contact Intelligence:**

- "This email address belongs to Bob" → emails associate with Bob's contact record
- "This phone number belongs to Bob" → SMS and calls associate with the same contact
- Unified contact records mean communications across all channels are correctly attributed

**Communications contributes to Contact Intelligence:**

- New email from unknown address → trigger identity resolution workflow
- SMS from unknown number → trigger identity resolution
- Manual communication "meeting with Sarah from Acme" → potential new contact signal
- Every unrecognized identifier is a signal fed back to Contact Intelligence

### 5.3 Pending Identification State

When a communication arrives with an unrecognized identifier:

1. Communication enters the system normally — it is **not blocked**.
2. Participant relation instance created with address and placeholder contact reference.
3. Contact Intelligence runs resolution: check existing contacts for alternate identifiers, check user's contact book, OSINT lookup if enabled, pattern matching.
4. **If resolved automatically** → participant relation updated to identified contact.
5. **If not resolved** → user prompted with suggestions; user matches, creates, or marks irrelevant.

**Critical principle:** Pending identification does **not** block conversation assignment, AI processing, or user display.

**Tasks:**

- [ ] CPAR-05: Implement known-identifier lookup against contact_identifiers
- [ ] CPAR-06: Implement placeholder participant creation for unknown identifiers
- [ ] CPAR-07: Implement async resolution callback (update participant when contact identified)
- [ ] CPAR-08: Implement identity resolution signal submission to Contact Intelligence
- [ ] CPAR-09: Implement pending identification UI (suggestion list, match/create/ignore)

**Tests:**

- [ ] CPAR-T05: Test known email address resolves to correct contact
- [ ] CPAR-T06: Test unknown address creates placeholder participant
- [ ] CPAR-T07: Test async resolution updates participant to identified contact
- [ ] CPAR-T08: Test communication processing proceeds while resolution is pending
- [ ] CPAR-T09: Test participant_resolved event emitted on resolution

---

## 6. Identifier Types by Channel

**Supports processes:** KP-1 (step 1)

### 6.1 Requirements

| Channel | Primary Identifier | Resolution Method |
|---|---|---|
| `email` | Email address | Direct lookup in contact_identifiers |
| `sms` / `mms` | Phone number | Phone number lookup in contact_identifiers |
| `phone_recorded` | Phone number | Phone number lookup |
| `phone_manual` | User-specified | User selects contact during entry |
| `video_recorded` | Platform display name + email | Email lookup; name matching as fallback |
| `video_manual` | User-specified | User selects contacts during entry |
| `in_person` | User-specified | User selects contacts during entry |

**Tasks:**

- [ ] CPAR-10: Implement channel-specific identifier extraction
- [ ] CPAR-11: Implement phone number normalization for SMS/phone resolution
- [ ] CPAR-12: Implement video platform display name matching as fallback

**Tests:**

- [ ] CPAR-T10: Test email identifier extraction from email headers
- [ ] CPAR-T11: Test phone number identifier extraction from SMS metadata
- [ ] CPAR-T12: Test phone number normalization handles international formats

---

## 7. Cross-Channel Contact Unification

**Supports processes:** KP-1 (step 3), all KPs

### 7.1 Requirements

The Contact Intelligence system maintains unified contact records linking all known identifiers:

```
Contact: Bob Smith (Acme Corp)
  ├── Email: bob.smith@acmecorp.com
  ├── Email: bob@gmail.com (personal)
  ├── Phone: +1-555-0100 (work)
  ├── Phone: +1-555-0199 (mobile)
  ├── Slack: @bsmith
  └── Zoom: "Bob S"
```

This means an email from `bob.smith@acmecorp.com` and an SMS from `+1-555-0199` are both recognized as Bob Smith — enabling the Conversations PRD to maintain cross-channel conversation continuity.

**Tasks:**

- [ ] CPAR-13: Implement cross-channel participant matching via unified contact identifiers

**Tests:**

- [ ] CPAR-T13: Test same contact recognized across email and phone channels
- [ ] CPAR-T14: Test cross-channel participant links enable unified conversation view

---

## 8. Participant API

**Supports processes:** KP-2 (step 3), KP-3 (step 3)

### 8.1 Requirements

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/communications/{id}/participants` | GET | List participants with roles and contact references |
| `/api/v1/communications/{id}/participants` | POST | Add a participant (manual communications) |
| `/api/v1/communications/{id}/participants/{contact_id}` | PATCH | Update participant metadata (role, etc.) |

**Tasks:**

- [ ] CPAR-14: Implement participant API endpoints

**Tests:**

- [ ] CPAR-T15: Test participant API list returns roles, addresses, and contact links
- [ ] CPAR-T16: Test participant API add works for manual communications
