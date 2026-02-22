# Product Requirements Document: Outbound Email

## CRMExtender — Email Composition, Templates, Signatures, Automation Rules & Click Tracking

**Version:** 1.0
**Date:** 2026-02-20
**Status:** Draft — Fully reconciled with Communications PRD, Documents PRD, Custom Objects PRD
**Parent Document:** [Communications PRD](communications-prd_V2.md)

> **V1.0 (2026-02-20):**
> This document defines the outbound email subsystem for CRMExtender — the user-facing experience for composing, sending, and managing outgoing email through connected provider accounts. While the Communications PRD defines the channel-agnostic Communication entity and the provider adapter framework for syncing inbound communications, and the planned Email Provider Sync PRD covers the mechanics of Gmail/Outlook/IMAP adapters, this PRD governs the user-initiated sending experience: compose/reply/forward, email templates, signature management, merge field substitution, date-triggered automation rules, scheduled sends, click tracking, and delivery status management.
>
> **Architectural positioning:**
> - Outbound emails are **Communication records** in the unified object model. Sending an email creates a Communication (`direction = outbound`, `source = composed`) immediately, before the provider sync cycle catches up.
> - Email templates are a **new system object type** (`is_system = true`, prefix `etl_`) in the Custom Objects framework with their own field registry, event sourcing, and relation model.
> - Automation rules are a **new system object type** (`is_system = true`, prefix `arl_`) governing date-triggered template sends with View-scoped recipients and mandatory user approval.
> - Attachments always create **Document entities** per the Documents PRD, providing full version traceability ("which version of the brochure was sent to which contact in which email").
> - Click tracking uses a **redirect service** for body and template links only (not signature links), with passive surfacing on Communication records and Contact timelines.
> - The compose experience uses the **same rich text editor** as Notes and Communication Published Summaries, with email-safe HTML transformation at send time.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Email Template as System Object Type](#5-email-template-as-system-object-type)
6. [Automation Rule as System Object Type](#6-automation-rule-as-system-object-type)
7. [Data Model](#7-data-model)
8. [Compose Experience](#8-compose-experience)
9. [Sending Identity Model](#9-sending-identity-model)
10. [Rich Text Editor & Email-Safe HTML](#10-rich-text-editor--email-safe-html)
11. [Reply, Reply All & Forward](#11-reply-reply-all--forward)
12. [Recipients & Contact Resolution](#12-recipients--contact-resolution)
13. [Attachments & Document Integration](#13-attachments--document-integration)
14. [Email Templates](#14-email-templates)
15. [Merge Fields & Variable Substitution](#15-merge-fields--variable-substitution)
16. [Signature Management](#16-signature-management)
17. [Drafts & Auto-Save](#17-drafts--auto-save)
18. [Scheduled Sends](#18-scheduled-sends)
19. [Date-Triggered Automation](#19-date-triggered-automation)
20. [Approval Workflow](#20-approval-workflow)
21. [Click Tracking](#21-click-tracking)
22. [Outbound Email Lifecycle & Communication Record Creation](#22-outbound-email-lifecycle--communication-record-creation)
23. [Conversation Assignment](#23-conversation-assignment)
24. [Bounce & Delivery Failure Handling](#24-bounce--delivery-failure-handling)
25. [Unsubscribe & Opt-Out](#25-unsubscribe--opt-out)
26. [Event Sourcing](#26-event-sourcing)
27. [Virtual Schema & Data Sources](#27-virtual-schema--data-sources)
28. [API Design](#28-api-design)
29. [Design Decisions](#29-design-decisions)
30. [Phasing & Roadmap](#30-phasing--roadmap)
31. [Dependencies & Related PRDs](#31-dependencies--related-prds)
32. [Open Questions](#32-open-questions)
33. [Future Work](#33-future-work)
34. [Glossary](#34-glossary)

---

## 1. Executive Summary

The Outbound Email subsystem transforms CRMExtender from a communication observation platform into an active communication tool. Users can compose, reply, forward, and schedule emails directly from within the CRM — eliminating the context switch between viewing relationship intelligence and acting on it. Every outbound email becomes a first-class Communication record with full participant tracking, conversation assignment, document traceability, and click analytics.

Beyond individual email composition, the system supports **email templates** with merge field substitution (personal and shared), **signature management** per provider account, and **date-triggered automation rules** that generate emails based on Contact date fields (birthdays, anniversaries, renewal dates) scoped to saved Views. All automation-generated emails require explicit user approval before sending — the system does the work of generating and scheduling, but the user has final say.

**Core principles:**

- **Communication first** — Every outbound email creates a Communication record immediately on send, with `direction = outbound` and `source = composed`. The record appears instantly in Contact timelines, Conversation timelines, and activity feeds. Provider sync later deduplicates by `provider_message_id`.
- **Document traceability** — All attachments are stored as Document entities per the Documents PRD. When a user attaches a file (whether uploaded or selected from existing Documents), the system creates a Communication↔Document relation. This enables queries like "which version of the pricing sheet did I send to Bob?"
- **Smart identity** — The system intelligently defaults the sending account based on reply context, historical communication patterns, and user preference — always visible and overridable.
- **Templates as entities** — Email templates are a system object type with ownership (personal vs. shared), merge field support, default attachments, and usage tracking. The same template framework powers both manual sends and automation rules.
- **Automation with oversight** — Date-triggered automation generates emails and surfaces them for approval. Nothing sends without explicit user action. The approval workflow uses a dedicated View on the home page, making pending emails impossible to miss.
- **Click intelligence** — All links in email body and template content are tracked through a redirect service. Click data surfaces passively on Communication records and Contact timelines, providing sales signals without invasive open/read tracking.

**Relationship to other PRDs:**

- **[Communications PRD](communications-prd_V2.md)** — Outbound emails are Communication records (`com_` prefix) in the unified schema. The Communications PRD defines the entity structure, field registry, provider account framework, participant model, and event sourcing that outbound emails inherit. This PRD adds the compose experience, send pipeline, and outbound-specific behaviors (templates, automation, click tracking) as extensions.
- **[Email Provider Sync PRD](email-provider-sync-prd_V1.md)** (planned) — The sync PRD covers the mechanics of provider API interaction: OAuth flows, message fetching, incremental sync cursors. This PRD uses the provider adapter's send capability but defines the user-facing compose experience and business logic independently.
- **[Documents PRD](documents-prd_V1.md)** — Every outbound email attachment creates a Document entity. Templates can have default Document attachments. The Documents PRD's Universal Attachment Relation and version control provide full traceability.
- **[Conversations PRD](conversations-prd_V3.md)** — Replies inherit conversation assignment from the parent Communication. New compositions use the standard conversation formation logic after provider sync, keeping compose-time assignment simple.
- **[Contact Management PRD](contact-management-prd_V4.md)** — Recipient resolution uses Contact identifiers. CC/BCC recipients who are not existing Contacts are auto-created. Merge fields pull from Contact field values. Bounce handling updates Contact email validity.
- **[Views & Grid PRD](views-grid-prd_V3.md)** — Automation rules scope recipients to saved Views. The "Awaiting Approval" list is a system View. Template usage and click tracking data are filterable through standard View mechanisms.
- **[Notes PRD](notes-prd_V2.md)** — Outbound email composition uses the same rich text editor and content architecture (JSON source of truth, HTML rendering) as Notes and Communication Published Summaries.
- **[Permissions & Sharing PRD](permissions-sharing-prd_V1.md)** — Template visibility (personal vs. shared), automation rule management, and BCC participant visibility follow role-based access controls.
- **[GUI Functional Requirements PRD](gui-functional-requirements-prd_V1.md)** — The compose experience uses a panel-based composer within the existing layout system, with undockable window support for multi-monitor workflows.

---

## 2. Problem Statement

CRMExtender captures and organizes inbound communications, giving users deep visibility into their relationship landscape. But acting on that intelligence — actually sending an email — still requires switching to a separate email client, losing the context of the CRM view, and hoping the sent email eventually syncs back into the system.

**The consequences for CRM users:**

| Pain Point | Impact |
|---|---|
| **Context switching** | User sees a Contact needs a follow-up, switches to Gmail, composes the email, switches back to CRM. The CRM view with all the relevant intelligence is no longer visible during composition. |
| **Broken traceability** | When sending from an external client, the user cannot attach a specific Document version from the CRM. There's no record of which brochure version was sent until the email syncs back and someone manually associates the attachment. |
| **No template consistency** | Each team member writes their own version of common emails (introductions, follow-ups, pricing responses). No shared library, no merge fields, no version control. |
| **Manual repetitive sends** | Birthday emails, anniversary greetings, renewal reminders, and seasonal follow-ups are either manually composed each time or forgotten entirely. |
| **Delayed visibility** | An email sent from Gmail doesn't appear in CRMExtender until the next sync cycle. During that gap, other team members don't know the email was sent, potentially duplicating outreach. |
| **No engagement signals** | After sending, the user has no visibility into whether the recipient clicked the links in the email. Did they look at the proposal? Did they visit the pricing page? |

### Why Existing Solutions Fall Short

- **CRM email integrations** (Salesforce, HubSpot) — Provide basic compose but with limited template engines, no date-triggered automation within the CRM itself, and poor attachment traceability. Templates are disconnected from the CRM's document management.
- **Email marketing tools** (Mailchimp, SendGrid) — Built for mass outreach, not relationship-focused 1:1 communication. Open tracking is standard but increasingly unreliable. Sequence automation is powerful but designed for cold outreach, not warm relationship maintenance.
- **Email clients** (Gmail, Outlook) — Excellent for composition but completely disconnected from CRM intelligence. Templates (canned responses) are per-user with no sharing, no merge fields against CRM data, and no usage tracking.

CRMExtender closes this gap by making email composition a native CRM action — compose with full relationship context visible, use shared templates with CRM merge fields, attach tracked Document versions, and automate routine relationship maintenance emails with human oversight.

---

## 3. Goals & Success Metrics

### Goals

1. **Native compose experience** — Users can compose, reply, forward, and schedule emails directly from CRMExtender without switching to an external email client. The compose panel is integrated into the existing GUI layout with undockable window support.
2. **Immediate visibility** — Outbound emails create Communication records instantly on send. No sync delay. Team members see outbound activity immediately.
3. **Template-driven consistency** — Personal and shared email templates with merge field substitution ensure consistent messaging. Templates track usage and support default attachments.
4. **Automated relationship maintenance** — Date-triggered automation rules generate emails for birthdays, anniversaries, renewals, and custom date fields — scoped to saved Views, requiring user approval before sending.
5. **Document traceability** — Every attachment is a Document entity. Users can answer "which version of what file did I send to whom and when?" through standard queries.
6. **Click intelligence** — Link click tracking provides passive engagement signals on Communication records and Contact timelines without invasive open/read tracking.
7. **Smart identity management** — The system intelligently defaults the sending account and signature based on context, reducing friction while keeping the user in control.

### Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Compose-to-send time | <60 seconds for template-based sends | Instrumented from compose open to send action |
| Template adoption rate | >50% of outbound emails use a template within 30 days | DB query: outbound Communications with `template_id` set |
| Automation approval rate | >90% of generated emails approved without edit | DB query: approved vs. edited vs. rejected automation emails |
| Click tracking coverage | 100% of body/template links tracked | Audit: compare links in sent HTML vs. tracked link records |
| Immediate record creation | 100% of sent emails have Communication record within 1 second | Instrumented send pipeline timing |
| Bounce detection rate | >95% of bounces detected and flagged | Audit: compare provider bounce notifications vs. flagged records |
| Document attachment traceability | 100% of outbound attachments linked to Document entities | DB query: outbound Communications with attachments vs. Document relations |

---

## 4. User Personas & Stories

### 4.1 Personas

| Persona | Description | Primary Use |
|---|---|---|
| **Solo entrepreneur** | Runs a service business (e.g., gutter cleaning across multiple cities). Manages hundreds of customer relationships with multiple email accounts. | Birthday/anniversary automation, seasonal service reminders, template-based follow-ups. |
| **Sales professional** | Manages a pipeline of prospects and customers. Needs consistent messaging and engagement visibility. | Templates for follow-ups and proposals, click tracking on pricing links, reply from CRM with full context. |
| **Team manager** | Oversees a team's outbound communication. Needs shared templates and visibility into team activity. | Shared template library, team-wide automation rules, approval oversight. |

### 4.2 User Stories

| ID | Story | Priority |
|---|---|---|
| OE-001 | As a user, I want to compose and send an email to a Contact from within CRMExtender so I don't lose context switching to Gmail. | P0 |
| OE-002 | As a user, I want to reply to an inbound email directly from the Conversation timeline so I can respond in context. | P0 |
| OE-003 | As a user, I want the system to automatically select the correct sending account when I reply, using the account that received the original email. | P0 |
| OE-004 | As a user, I want to forward an email to a new recipient with all original attachments preserved. | P0 |
| OE-005 | As a user, I want to save email templates with merge fields so I can send consistent messages quickly. | P0 |
| OE-006 | As a user, I want to share templates with my team so everyone uses consistent messaging. | P1 |
| OE-007 | As a user, I want to attach Documents from CRMExtender to my outbound email so the system tracks which version was sent. | P0 |
| OE-008 | As a user, I want to schedule an email to send at a future date/time so I can time my outreach appropriately. | P1 |
| OE-009 | As a user, I want to set up an automation rule that generates birthday emails for all contacts in a saved View. | P1 |
| OE-010 | As a user, I want to review and approve automation-generated emails before they send so I maintain personal control. | P0 |
| OE-011 | As a user, I want to batch-approve multiple automation emails at once when I trust the template. | P1 |
| OE-012 | As a user, I want to see when a recipient clicks a link in my email so I know they're engaged. | P1 |
| OE-013 | As a user, I want my outbound email to appear immediately in the Contact timeline so my team sees it right away. | P0 |
| OE-014 | As a user, I want to manage multiple email signatures and have the correct one applied based on which account I'm sending from. | P1 |
| OE-015 | As a user, I want to be notified when an email bounces so I can update the contact's information. | P1 |
| OE-016 | As a user, I want to undock the compose window so I can write an email on one screen while viewing CRM data on another. | P2 |
| OE-017 | As a user, I want automation rules to skip Contacts who have opted out of automated emails. | P0 |
| OE-018 | As a user, I want CC/BCC recipients who aren't in my CRM to be automatically created as Contacts. | P1 |

---

## 5. Email Template as System Object Type

### 5.1 Object Type Registration

Email Template is registered as a system object type in the Custom Objects framework:

| Attribute | Value |
|---|---|
| `name` | Email Template |
| `slug` | `email_templates` |
| `type_prefix` | `etl_` |
| `is_system` | `true` |
| `display_name_field_id` | → `name` field |
| `description` | A reusable email composition template with merge field support, default attachments, and signature association. Used for manual sends and automation rules. |

### 5.2 Registered Behaviors

| Behavior | Trigger | Description |
|---|---|---|
| Merge field validation | On save | Validates that all `{{...}}` merge field references in the template body resolve to known field paths. Warns on unrecognized fields but does not block save. |
| Usage tracking | On send | Increments usage counters and records the most recent use timestamp when an email is sent using this template. |
| Default attachment sync | On Document update | When a Document entity linked as a default attachment receives a new version, the template's attachment reference automatically points to the latest version. |

### 5.3 Protected Core Fields

The following fields are `is_system = true` and cannot be archived, deleted, or have their type converted.

---

## 6. Automation Rule as System Object Type

### 6.1 Object Type Registration

Automation Rule is registered as a system object type in the Custom Objects framework:

| Attribute | Value |
|---|---|
| `name` | Automation Rule |
| `slug` | `automation_rules` |
| `type_prefix` | `arl_` |
| `is_system` | `true` |
| `display_name_field_id` | → `name` field |
| `description` | A date-triggered email automation that generates outbound emails from a template, scoped to a saved View, on a schedule relative to a Contact date field. Generated emails require user approval before sending. |

### 6.2 Registered Behaviors

| Behavior | Trigger | Description |
|---|---|---|
| Email generation | On schedule (daily evaluation) | Evaluates the trigger date field for all Contacts in the scoped View, generates outbound email records for qualifying Contacts within the configured timing offset, and places them in `awaiting_approval` status. |
| Overlap detection | On generation | Checks whether a Contact already has a pending or scheduled outbound email from another automation rule for the same date. Flags overlaps on the generated email record for user awareness during approval. |
| Opt-out enforcement | On generation | Skips Contacts whose `automated_email_opt_out` flag is `true`. Skips Contacts whose target email address has `delivery_status = bounced`. |
| Notification | On generation | Sends the rule owner a notification summarizing the generated batch: count of emails, date range, any flagged overlaps or skipped contacts. |

### 6.3 Protected Core Fields

The following fields are `is_system = true` and cannot be archived, deleted, or have their type converted.

---

## 7. Data Model

### 7.1 Email Template Field Registry

**Universal fields** (present on all object types per Custom Objects PRD Section 7):

| Field | Column | Type | Description |
|---|---|---|---|
| ID | `id` | TEXT, PK | Prefixed ULID: `etl_01HX8A...` |
| Tenant | `tenant_id` | TEXT, NOT NULL | Tenant isolation |
| Created At | `created_at` | TIMESTAMPTZ, NOT NULL | Record creation timestamp |
| Updated At | `updated_at` | TIMESTAMPTZ, NOT NULL | Last modification timestamp |
| Created By | `created_by` | TEXT, FK → users | User who created the template |
| Updated By | `updated_by` | TEXT, FK → users | User who last modified the template |
| Archived At | `archived_at` | TIMESTAMPTZ, NULL | Soft-delete timestamp |

**Core system fields** (`is_system = true`, protected):

| Field | Column | Type | Required | Description |
|---|---|---|---|---|
| Name | `name` | Text (single-line) | YES | Template display name. E.g., "Birthday Greeting", "Proposal Follow-Up". |
| Subject | `subject` | Text (single-line) | YES | Email subject line template. Supports merge field substitution: `Happy Birthday, {{contact.first_name}}!` |
| Visibility | `visibility` | Select | YES | `personal` (visible only to creator) or `shared` (visible to all tenant users). |
| Category | `category` | Select | NO | User-defined template category. E.g., "Follow-Up", "Holiday", "Sales", "Service Reminder". |
| Description | `description` | Text (multi-line) | NO | Internal description of the template's purpose and usage context. Not included in the email. |
| Use Count | `use_count` | Number (integer) | NO | Total number of times this template has been used to send an email. Auto-incremented. |
| Last Used At | `last_used_at` | TIMESTAMPTZ | NO | Timestamp of most recent use. Auto-updated on send. |

**Behavior-managed content fields** (not in field registry, stored as columns):

| Field | Column | Type | Description |
|---|---|---|---|
| Body JSON | `body_json` | JSONB | Rich text source of truth (same contract as Notes `content_json`). |
| Body HTML | `body_html` | TEXT | Rendered HTML for preview. Contains merge field placeholders in display form. |
| Body Text | `body_text` | TEXT | Plain text fallback. Used for email `text/plain` multipart and search indexing. |

### 7.2 Email Template Read Model Table

```sql
-- Within tenant schema: tenant_abc.email_templates
CREATE TABLE email_templates (
    -- Universal fields
    id              TEXT PRIMARY KEY,        -- etl_01HX8A...
    tenant_id       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT REFERENCES platform.users(id),
    updated_by      TEXT REFERENCES platform.users(id),
    archived_at     TIMESTAMPTZ,

    -- Core system fields
    name            TEXT NOT NULL,
    subject         TEXT NOT NULL,
    visibility      TEXT NOT NULL DEFAULT 'personal',  -- 'personal', 'shared'
    category        TEXT,
    description     TEXT,
    use_count       INTEGER NOT NULL DEFAULT 0,
    last_used_at    TIMESTAMPTZ,

    -- Behavior-managed content
    body_json       JSONB,
    body_html       TEXT,
    body_text       TEXT,

    -- Constraints
    CONSTRAINT valid_visibility CHECK (visibility IN ('personal', 'shared'))
);

-- Indexes
CREATE INDEX idx_email_templates_tenant ON email_templates(tenant_id);
CREATE INDEX idx_email_templates_visibility ON email_templates(tenant_id, visibility);
CREATE INDEX idx_email_templates_creator ON email_templates(created_by);
CREATE INDEX idx_email_templates_category ON email_templates(tenant_id, category);
```

### 7.3 Email Template Default Attachments

Templates can have default Document attachments that are automatically included when the template is used:

```sql
-- Within tenant schema: tenant_abc.email_template_attachments
CREATE TABLE email_template_attachments (
    id              TEXT PRIMARY KEY,        -- Prefixed ULID
    template_id     TEXT NOT NULL REFERENCES email_templates(id),
    document_id     TEXT NOT NULL REFERENCES documents(id),
    display_order   INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT REFERENCES platform.users(id),

    UNIQUE(template_id, document_id)
);
```

When a Document entity linked as a default attachment receives a new version, the template attachment reference automatically resolves to the latest version at send time (Documents use content-addressable storage — the Document entity ID is stable, the version is a separate concept).

### 7.4 Automation Rule Field Registry

**Universal fields** (same as above — id, tenant_id, timestamps, created/updated by, archived_at).

**Core system fields** (`is_system = true`, protected):

| Field | Column | Type | Required | Description |
|---|---|---|---|---|
| Name | `name` | Text (single-line) | YES | Rule display name. E.g., "Birthday Greetings", "Annual Service Reminder". |
| Template ID | `template_id` | Relation (→ email_templates) | YES | The email template this rule uses to generate emails. |
| View ID | `view_id` | Relation (→ views) | YES | The saved View that defines the recipient scope. Evaluated dynamically at generation time. |
| Trigger Field | `trigger_field` | Text (single-line) | YES | The date field path on the Contact entity to trigger against. E.g., `birthday`, `anniversary`, or a custom date field slug. |
| Timing Offset Days | `timing_offset_days` | Number (integer) | YES | Number of days relative to the trigger date. Negative = before (e.g., `-3` means 3 days before birthday). Positive = after. `0` = on the day. |
| Sending Account ID | `sending_account_id` | Relation (→ provider_accounts) | YES | The provider account to send from. |
| Status | `status` | Select | YES | `active`, `paused`, `archived`. Only `active` rules generate emails. |
| Last Run At | `last_run_at` | TIMESTAMPTZ | NO | When the rule last evaluated and generated emails. |
| Last Run Count | `last_run_count` | Number (integer) | NO | Number of emails generated in the most recent run. |

### 7.5 Automation Rule Read Model Table

```sql
-- Within tenant schema: tenant_abc.automation_rules
CREATE TABLE automation_rules (
    -- Universal fields
    id                  TEXT PRIMARY KEY,        -- arl_01HX8A...
    tenant_id           TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          TEXT REFERENCES platform.users(id),
    updated_by          TEXT REFERENCES platform.users(id),
    archived_at         TIMESTAMPTZ,

    -- Core system fields
    name                TEXT NOT NULL,
    template_id         TEXT NOT NULL REFERENCES email_templates(id),
    view_id             TEXT NOT NULL REFERENCES views(id),
    trigger_field       TEXT NOT NULL,
    timing_offset_days  INTEGER NOT NULL DEFAULT 0,
    sending_account_id  TEXT NOT NULL REFERENCES provider_accounts(id),
    status              TEXT NOT NULL DEFAULT 'active',
    last_run_at         TIMESTAMPTZ,
    last_run_count      INTEGER,

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('active', 'paused', 'archived'))
);

CREATE INDEX idx_automation_rules_tenant ON automation_rules(tenant_id);
CREATE INDEX idx_automation_rules_status ON automation_rules(tenant_id, status);
CREATE INDEX idx_automation_rules_template ON automation_rules(template_id);
```

### 7.6 Outbound Email Queue

Outbound emails (both manual and automation-generated) pass through a queue before sending:

```sql
-- Within tenant schema: tenant_abc.outbound_email_queue
CREATE TABLE outbound_email_queue (
    id                      TEXT PRIMARY KEY,        -- Prefixed ULID
    tenant_id               TEXT NOT NULL,
    communication_id        TEXT REFERENCES communications(id),  -- NULL until Communication record created
    
    -- Composition data
    from_account_id         TEXT NOT NULL REFERENCES provider_accounts(id),
    to_addresses            JSONB NOT NULL,          -- [{email, contact_id?}]
    cc_addresses            JSONB,                   -- [{email, contact_id?}]
    bcc_addresses           JSONB,                   -- [{email, contact_id?}]
    subject                 TEXT NOT NULL,
    body_json               JSONB NOT NULL,          -- Rich text source of truth
    body_html               TEXT NOT NULL,            -- Email-safe HTML (post-transformation)
    body_text               TEXT NOT NULL,            -- Plain text fallback
    signature_id            TEXT,                     -- Signature applied
    
    -- Source context
    source_type             TEXT NOT NULL,            -- 'manual', 'automation', 'reply', 'forward'
    template_id             TEXT,                     -- Template used, if any
    automation_rule_id      TEXT,                     -- Automation rule, if generated by automation
    reply_to_communication_id TEXT,                   -- Parent Communication for replies
    forward_of_communication_id TEXT,                 -- Source Communication for forwards
    
    -- Scheduling & lifecycle
    status                  TEXT NOT NULL DEFAULT 'draft',
    -- Status values: 'draft', 'awaiting_approval', 'approved', 'scheduled', 'queued',
    --               'sending', 'sent', 'failed', 'rejected', 'cancelled'
    scheduled_send_at       TIMESTAMPTZ,             -- NULL = send immediately on approval/queue
    approved_at             TIMESTAMPTZ,
    approved_by             TEXT,
    sent_at                 TIMESTAMPTZ,
    
    -- Automation context
    overlap_flag            BOOLEAN DEFAULT FALSE,    -- Another rule targets same contact on same date
    overlap_details         TEXT,                      -- Human-readable overlap description
    
    -- Failure tracking
    failure_reason          TEXT,
    retry_count             INTEGER DEFAULT 0,
    
    -- Undo-send support
    undo_window_expires_at  TIMESTAMPTZ,             -- Typically send_time + 10 seconds
    
    -- Audit
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by              TEXT REFERENCES platform.users(id),

    CONSTRAINT valid_source_type CHECK (source_type IN ('manual', 'automation', 'reply', 'forward')),
    CONSTRAINT valid_status CHECK (status IN (
        'draft', 'awaiting_approval', 'approved', 'scheduled', 'queued',
        'sending', 'sent', 'failed', 'rejected', 'cancelled'
    ))
);

CREATE INDEX idx_outbound_queue_tenant_status ON outbound_email_queue(tenant_id, status);
CREATE INDEX idx_outbound_queue_scheduled ON outbound_email_queue(scheduled_send_at) WHERE status = 'scheduled';
CREATE INDEX idx_outbound_queue_awaiting ON outbound_email_queue(tenant_id) WHERE status = 'awaiting_approval';
CREATE INDEX idx_outbound_queue_automation ON outbound_email_queue(automation_rule_id);
```

### 7.7 Outbound Email Attachments

```sql
-- Within tenant schema: tenant_abc.outbound_email_attachments
CREATE TABLE outbound_email_attachments (
    id                  TEXT PRIMARY KEY,
    outbound_email_id   TEXT NOT NULL REFERENCES outbound_email_queue(id),
    document_id         TEXT NOT NULL REFERENCES documents(id),
    document_version_id TEXT,                        -- Specific version at time of send. NULL = latest.
    display_order       INTEGER NOT NULL DEFAULT 0,
    source              TEXT NOT NULL,               -- 'template_default', 'user_attached', 'forwarded'
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(outbound_email_id, document_id)
);
```

### 7.8 Click Tracking Tables

```sql
-- Within tenant schema: tenant_abc.tracked_links
CREATE TABLE tracked_links (
    id                  TEXT PRIMARY KEY,             -- Prefixed ULID
    communication_id    TEXT NOT NULL REFERENCES communications(id),
    original_url        TEXT NOT NULL,
    tracking_token      TEXT NOT NULL UNIQUE,         -- Unique token for redirect URL
    position_index      INTEGER,                      -- Ordinal position in email body
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tracked_links_communication ON tracked_links(communication_id);
CREATE INDEX idx_tracked_links_token ON tracked_links(tracking_token);

-- Within tenant schema: tenant_abc.link_clicks
CREATE TABLE link_clicks (
    id                  TEXT PRIMARY KEY,
    tracked_link_id     TEXT NOT NULL REFERENCES tracked_links(id),
    contact_id          TEXT REFERENCES contacts(id), -- Resolved from tracking context
    clicked_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_agent          TEXT,
    ip_address          INET
);

CREATE INDEX idx_link_clicks_tracked_link ON link_clicks(tracked_link_id);
CREATE INDEX idx_link_clicks_contact ON link_clicks(contact_id);
CREATE INDEX idx_link_clicks_time ON link_clicks(clicked_at);
```

### 7.9 Email Signatures Table

```sql
-- Within tenant schema: tenant_abc.email_signatures
CREATE TABLE email_signatures (
    id                  TEXT PRIMARY KEY,             -- Prefixed ULID
    tenant_id           TEXT NOT NULL,
    user_id             TEXT NOT NULL REFERENCES platform.users(id),
    name                TEXT NOT NULL,                -- Display name: "Work Signature", "Personal"
    body_json           JSONB NOT NULL,               -- Rich text source of truth
    body_html           TEXT NOT NULL,                -- Rendered HTML
    provider_account_id TEXT REFERENCES provider_accounts(id),  -- Default for this account (NULL = no default)
    is_default          BOOLEAN NOT NULL DEFAULT FALSE,  -- User's overall default if no account match
    reply_behavior      TEXT NOT NULL DEFAULT 'full', -- 'full', 'abbreviated', 'none'
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_signatures_user ON email_signatures(user_id);
CREATE INDEX idx_signatures_account ON email_signatures(provider_account_id);
```

### 7.10 Contact Opt-Out and Delivery Status

These fields are added to the Contact entity's field registry (extending the Contact Management PRD):

| Field | Column | Type | Description |
|---|---|---|---|
| Automated Email Opt-Out | `automated_email_opt_out` | Checkbox | `true` = Contact has opted out of automated emails. Automation rules skip this contact. Manual compose is unaffected. |

The following is tracked on contact identifiers (email addresses) in the `contact_identifiers` table:

| Field | Column | Type | Description |
|---|---|---|---|
| Delivery Status | `delivery_status` | Select | `valid`, `bounced`, `unknown`. Set by bounce handling. `bounced` addresses are skipped by automation and flagged in compose. |
| Delivery Status Updated At | `delivery_status_updated_at` | TIMESTAMPTZ | When the delivery status was last updated. |

---

## 8. Compose Experience

### 8.1 Compose Entry Points

Users can initiate email composition from multiple locations in the CRM:

| Entry Point | Context Provided | Sending Account Default |
|---|---|---|
| **Contact detail panel** → "New Email" action | To: Contact's primary email. | Historical pattern: most-used account for this Contact. If no history, prompt user. |
| **Conversation timeline** → "Reply" on a Communication | To: original sender. In-reply-to headers set. Quoted content included. | Account that received the original email. |
| **Conversation timeline** → "Reply All" on a Communication | To/CC: all original participants (excluding self). In-reply-to headers set. | Account that received the original email. |
| **Conversation timeline** → "Forward" on a Communication | To: empty (user fills in). Original content and attachments included. | Account that received the original email. |
| **Conversation detail** → "New Email" | To: primary participant(s) of the Conversation. | Historical pattern for the Conversation's contacts. |
| **Global compose action** (e.g., keyboard shortcut or nav bar button) | Empty compose. No pre-filled context. | User's default sending account. If no default, prompt user. |
| **Automation approval queue** → "Edit & Approve" | Fully pre-filled from template + merge fields. | As configured on the automation rule. |

### 8.2 Panel-Based Composer

The compose experience opens in the **contextual action panel** within the existing GUI layout system (GUI Functional Requirements PRD Section 11). The panel includes:

- **Header bar:** Sending account selector (always visible), minimize/close buttons, undock button.
- **Recipient fields:** To, CC (collapsed by default, expandable), BCC (collapsed by default, expandable). Each field supports type-ahead Contact search and freeform email entry.
- **Subject line:** Single-line text input. Pre-filled from template (with merge fields resolved) or from reply context.
- **Body editor:** Rich text editor (same as Notes). Full formatting toolbar. Template insertion button. Merge field insertion button.
- **Attachments bar:** Shows attached files with Document entity references. "Attach from Documents" and "Upload" buttons.
- **Signature preview:** Rendered below the body editor, separated by a divider. Editable per-send if needed.
- **Footer bar:** Send button (with dropdown for scheduled send), Save Draft button, template selector, undo-send timer (visible after send action).

### 8.3 Undockable Window

The compose panel can be undocked into a separate OS-level window (Flutter multi-window support). The undocked composer:

- Contains the identical compose UI as the panel version.
- Operates independently of the main CRM window — the user can navigate, search, and view records in the main window while composing.
- Supports multiple simultaneous undocked composers (one per draft).
- When the undocked window is closed, any unsaved content is auto-saved as a draft.
- The undocked state is per-compose-session, not a global preference. Each new compose starts in the panel; the user undocks if desired.

---

## 9. Sending Identity Model

### 9.1 Smart Default Priority Chain

When a compose session is initiated, the system selects the default sending account using the following priority chain (first match wins):

| Priority | Condition | Default Account |
|---|---|---|
| 1 | **Reply/Reply All/Forward** — composing in response to an existing Communication | The provider account that received/synced the original Communication (`provider_account_id` on the parent Communication record). |
| 2 | **Historical pattern** — the To recipient is a Contact with prior outbound email from the user | The provider account most recently used by this user to send email to this Contact. Determined by querying outbound Communications to this Contact's email addresses, ordered by timestamp desc. |
| 3 | **User default** — user has set a default sending account in their settings | The user's configured default provider account. |
| 4 | **Only one account** — user has exactly one connected email account | That account. |
| 5 | **Ambiguous** — none of the above resolve | Prompt the user to select an account. The compose panel opens with the From field highlighted and a dropdown of available accounts. |

### 9.2 Visibility and Override

- The **From field** is always visible at the top of the compose panel, showing the selected provider account's email address and a display label.
- Clicking the From field opens a dropdown listing all of the user's connected email accounts (active provider accounts with `provider = gmail` or `provider = outlook`).
- Changing the sending account also updates the default signature to match the new account's assigned signature (Section 16).
- The selected sending account is stored on the outbound email queue record. If the user overrides the smart default, the override is used but does not change the default logic for future sends.

---

## 10. Rich Text Editor & Email-Safe HTML

### 10.1 Editor

The outbound email composer uses the same rich text editor as Notes (Notes PRD Section 9) and Communication Published Summaries (Communications PRD Section 7). This provides a consistent editing experience across all text composition in CRMExtender.

Supported formatting:

- Headings (H1, H2, H3)
- Bold, italic, underline, strikethrough
- Ordered and unordered lists
- Links (with URL editing)
- Images (inline, from upload or Document reference)
- Tables (basic)
- Block quotes
- Horizontal rules
- Code blocks (monospace)

### 10.2 Email-Safe HTML Transformation

At send time, the rich text content (`body_json`) is transformed into email-safe HTML that renders consistently across email clients. This transformation is a backend process invisible to the user.

**Transformation rules:**

| Rich Text Feature | Email-Safe Output |
|---|---|
| CSS classes / external stylesheets | Inline styles on each element |
| Modern CSS (flexbox, grid) | Table-based layout where needed |
| Custom fonts | System font stack fallback (`Arial, Helvetica, sans-serif`) |
| Responsive width | Fixed-width container (600px) with percentage-based inner elements |
| Images | `<img>` with explicit `width` and `height` attributes; hosted on CRMExtender CDN |
| Links | Standard `<a>` tags with link tracking rewrite (Section 21) |
| Background colors | Inline `background-color` style |
| Margin/padding | Inline styles or table cell padding |

**Multipart message format:** Every outbound email is sent as `multipart/alternative` with both `text/html` (email-safe HTML) and `text/plain` (generated from `body_text`) parts. This ensures readability for recipients whose email clients prefer or require plain text.

The user sees a WYSIWYG editor during composition. The email-safe transformation is tested against a reference matrix of email clients (Gmail web, Gmail mobile, Outlook desktop, Outlook web, Apple Mail, Yahoo Mail) during development. The user never needs to think about email client compatibility.

---

## 11. Reply, Reply All & Forward

### 11.1 Reply

When the user clicks "Reply" on a Communication in the Conversation timeline:

- **To:** Pre-filled with the sender of the original Communication (resolved from the Communication Participants relation, role = `sender`).
- **Subject:** Pre-filled with `Re: {original_subject}`.
- **Quoted content:** The `content_clean` of the original Communication is included below the compose area, separated by a standard reply separator line (`On {date}, {sender} wrote:`). Quoted content uses `content_clean` (noise already removed) rather than raw content, producing cleaner quoted replies than composing from a standard email client.
- **From:** Defaults to the provider account that received the original email (Priority 1 in the sending identity model).
- **In-Reply-To / References headers:** Set from the original Communication's `provider_message_id` to maintain email threading at the provider level.

### 11.2 Reply All

Same as Reply, with additional recipient population:

- **To:** Original sender.
- **CC:** All other participants from the original Communication (roles `to`, `cc`) except the current user's email addresses. The user can modify To and CC before sending.
- **BCC:** Not pre-populated (BCC from the original is invisible by design).

### 11.3 Forward

When the user clicks "Forward" on a Communication:

- **To:** Empty (user fills in the recipient).
- **Subject:** Pre-filled with `Fwd: {original_subject}`.
- **Body:** The original Communication's `content_clean` is included below a forward separator (`---------- Forwarded message ----------`), with original sender, date, subject, and recipients displayed.
- **Attachments:** All attachments from the original Communication are included. Each is a Document entity reference — the forward does not duplicate file storage.
- **From:** Defaults to the provider account that received the original email.
- **Communication record:** The forwarded email creates a new Communication record with a `forwarded_from_communication_id` reference back to the original. It does not join the original email's conversation thread — it starts a new provider thread.

---

## 12. Recipients & Contact Resolution

### 12.1 Recipient Input

The To, CC, and BCC fields support two input modes:

- **Contact search:** As the user types, a dropdown shows matching Contacts (searched by name and email addresses from `contact_identifiers`). Selecting a Contact populates the field with the Contact's primary email address and creates a link to the Contact record.
- **Freeform email:** The user can type or paste a raw email address that doesn't match any Contact. The address is validated for format before send.

### 12.2 Auto-Create Contacts

When an outbound email is sent with a freeform email address (not linked to an existing Contact) in the To, CC, or BCC fields:

- The system creates a new Contact record with the email address as the sole identifier in `contact_identifiers`.
- The Contact's `source` is set to `outbound_email`.
- The new Contact is linked as a Communication Participant on the outbound Communication record.
- Standard enrichment pipelines (Contact Management PRD Section 8) are triggered for the new Contact.
- The user is not interrupted during the send flow — auto-creation happens asynchronously after send.

### 12.3 BCC Visibility

BCC participants are recorded on the Communication record's Communication Participants relation with `role = bcc`. Visibility rules:

| Viewer | Can see BCC participants? |
|---|---|
| The sender (created_by on the Communication) | Yes |
| Tenant Admins / Sys Admins | Yes |
| Other tenant users | No — BCC participants are excluded from participant lists for non-sender, non-admin viewers |

---

## 13. Attachments & Document Integration

### 13.1 Attachment Sources

| Source | Flow |
|---|---|
| **Upload from device** | File picker → file uploaded to object storage → Document entity created (Documents PRD Section 17) → linked to outbound email via `outbound_email_attachments`. |
| **Attach from Documents** | User browses/searches CRMExtender Documents → selects one or more → linked to outbound email. The Document's current version is referenced. |
| **Template default attachments** | When a template is applied, its default attachments (Section 7.3) are automatically included. The user can remove or add to these. |
| **Forward attachments** | When forwarding, original Communication's Document attachments are included automatically. |

### 13.2 Version Tracking

When an outbound email is sent, the `outbound_email_attachments` record captures the `document_version_id` that was current at send time. Even if the Document is later updated to a new version, the historical record shows exactly which version was sent to which recipient. This is the core of CRMExtender's attachment traceability.

### 13.3 Size Limits

Email providers impose attachment size limits (Gmail: 25MB, Outlook: 20MB). The compose UI displays cumulative attachment size and warns the user if the total exceeds the sending provider's limit. The system does not block the send — the provider will reject it, and the failure is handled by the bounce/failure pipeline (Section 24).

---

## 14. Email Templates

### 14.1 Template Creation

Templates are created from the Template management area (accessible from the main navigation) or by saving the current compose content as a new template ("Save as Template" action in the compose panel).

The template editor is the same rich text editor as the compose panel, with the addition of a **merge field inserter** — a button/dropdown that lists available merge fields by category and inserts the selected field's placeholder syntax (`{{contact.first_name}}`) at the cursor position.

### 14.2 Ownership and Visibility

| Visibility | Who can create | Who can view/use | Who can edit | Who can delete |
|---|---|---|---|---|
| `personal` | Any user | Creator only | Creator only | Creator only |
| `shared` | Any user | All tenant users | Creator only | Creator + Admins |

A template's visibility can be changed from `personal` to `shared` (and vice versa) by the creator. Changing from `shared` to `personal` does not affect automation rules that reference the template — those rules continue to function but will fail if the template is archived.

### 14.3 Template Application

When the user selects a template in the compose panel:

1. The subject line is populated from the template's `subject`, with merge fields resolved against the current recipient Contact (if one is already in the To field).
2. The body is populated from the template's `body_json`, with merge fields resolved.
3. Default attachments are added to the attachment bar.
4. If merge fields cannot be resolved (no To recipient yet, or the Contact is missing a required field), the placeholder is shown in a visually distinct style (e.g., highlighted yellow) so the user can fill it in manually.
5. The user can edit any part of the populated content before sending. The template is a starting point, not a constraint.

### 14.4 Template Usage Tracking

Each time an email is sent using a template:

- The template's `use_count` is incremented.
- The template's `last_used_at` is updated.
- The outbound email queue record's `template_id` is set, enabling queries like "show all emails sent from this template" or "which contacts have received the Birthday Greeting template."

---

## 15. Merge Fields & Variable Substitution

### 15.1 Merge Field Syntax

Merge fields use double-brace syntax: `{{entity.field}}`. This syntax is used in both the template subject and body.

### 15.2 Available Merge Fields

| Category | Field Path | Resolves To |
|---|---|---|
| **Contact** | `{{contact.first_name}}` | Contact's first name |
| | `{{contact.last_name}}` | Contact's last name |
| | `{{contact.full_name}}` | Contact's display name (first + last) |
| | `{{contact.email}}` | Contact's primary email address |
| | `{{contact.phone}}` | Contact's primary phone number |
| | `{{contact.title}}` | Contact's job title |
| | `{{contact.company_name}}` | Display name of the Contact's primary company |
| **Company** | `{{company.name}}` | Company display name (via Contact's primary company) |
| | `{{company.domain}}` | Company primary domain |
| | `{{company.industry}}` | Company industry field |
| **Sender** | `{{user.first_name}}` | Current user's first name |
| | `{{user.last_name}}` | Current user's last name |
| | `{{user.full_name}}` | Current user's display name |
| | `{{user.email}}` | Sending account email address |
| | `{{user.phone}}` | Current user's phone number |
| | `{{user.title}}` | Current user's job title |
| **Date** | `{{today}}` | Current date (formatted per tenant locale) |
| | `{{current_year}}` | Current year (4-digit) |

Custom fields on Contact and Company entities are also accessible via their field slugs: `{{contact.custom_field_slug}}`, `{{company.custom_field_slug}}`.

### 15.3 Resolution Behavior

- Merge fields are resolved at **compose time** (when a template is applied) for manual sends, allowing the user to preview and edit.
- Merge fields are resolved at **generation time** for automation-generated emails, producing fully-resolved content that the user reviews during approval.
- If a merge field references a field that has no value on the target Contact/Company, the field resolves to an empty string. The resolved content is displayed so the user can spot and fix gaps (e.g., "Dear ," with a missing first name is visible during preview or approval).

---

## 16. Signature Management

### 16.1 Signature Model

Users manage signatures in their account settings. Each signature consists of:

- **Name:** Display label for identification (e.g., "Work - Full", "Personal", "Brief").
- **Body:** Rich text content (same editor), supporting formatted text, images (logos, headshots), and links.
- **Provider account default:** Optionally assigned as the default signature for a specific provider account. When composing from that account, this signature is automatically applied.
- **Reply behavior:** Controls signature inclusion on replies — `full` (include complete signature), `abbreviated` (include a shortened version — future enhancement, initially same as full), or `none` (no signature on replies).

### 16.2 Signature Selection Logic

| Compose Action | Signature Applied |
|---|---|
| New compose from a specific provider account | That account's default signature. Falls back to user's overall default signature. Falls back to no signature. |
| Reply / Reply All | Follows the matched signature's `reply_behavior` setting. |
| Forward | Full signature (same as new compose). |
| Change sending account during compose | Signature swaps to the new account's default. |
| User manually changes | Selected signature persists for this compose session regardless of account changes. |

### 16.3 Signature in Email

The signature is appended below the user's composed content, separated by the standard email signature delimiter (`-- \n`). In HTML emails, the signature is rendered in a visually distinct block (lighter text, smaller font) per email conventions.

Signature links are **not** subject to click tracking (Section 21). The click tracking rewrite applies only to links in the email body and template content.

---

## 17. Drafts & Auto-Save

### 17.1 Auto-Save

Compose sessions are automatically saved to the `outbound_email_queue` with `status = 'draft'` at regular intervals (every 30 seconds while the user is composing, and immediately on compose panel close or window focus loss).

Auto-saved drafts capture the complete compose state: recipients, subject, body, attachments, sending account, signature selection, and source context (reply-to reference, template ID, etc.).

### 17.2 Draft Storage

Drafts are stored in CRMExtender only — they are not synced to the provider's Drafts folder. This keeps draft management simple and avoids sync complexity.

### 17.3 Draft Management

- Users access their drafts from a "Drafts" section in the navigation or from a filtered View on the outbound email queue (`status = 'draft'`).
- Opening a draft restores the full compose session — all fields, attachments, and context.
- Drafts older than 30 days with no modifications are flagged for cleanup. The user is notified before deletion.
- Drafts are per-user and follow standard visibility rules (a user's drafts are not visible to other users).

### 17.4 Undo-Send

When the user clicks Send:

1. The outbound email transitions from `draft`/`queued` to `sending` status.
2. An **undo-send timer** appears in the compose panel footer (10-second countdown).
3. During the undo window, the email is held in the queue — not yet submitted to the provider API.
4. If the user clicks "Undo" within the window, the email returns to `draft` status and the compose panel reopens with full content.
5. If the timer expires without undo, the email is submitted to the provider API for delivery.
6. The `undo_window_expires_at` timestamp on the queue record governs the window duration.

---

## 18. Scheduled Sends

### 18.1 Manual Scheduling

The Send button includes a dropdown option: **"Schedule Send."** Selecting this opens a date/time picker where the user chooses when the email should be sent.

- Minimum schedule time: 1 minute from now.
- Time zone: The picker displays and stores times in the user's configured time zone.
- The outbound email queue record is created with `status = 'scheduled'` and `scheduled_send_at` set to the chosen time.

### 18.2 Scheduled Email Management

Scheduled emails appear in a "Scheduled" section alongside Drafts. The user can:

- **View** the scheduled email's content and send time.
- **Edit** the content or recipients (transitions back to draft, requires re-scheduling or immediate send).
- **Reschedule** to a different time.
- **Cancel** the scheduled send (transitions to `cancelled` status; can be reopened as a draft).

### 18.3 Send Worker

A background worker process evaluates the `outbound_email_queue` on a regular interval (every 30 seconds):

- Selects records where `status = 'scheduled'` AND `scheduled_send_at <= NOW()`.
- Transitions each to `queued` → `sending` → `sent` (or `failed`).
- Applies the undo-send window only to manual immediate sends, not to scheduled sends (the scheduling itself is the deliberate action).

---

## 19. Date-Triggered Automation

### 19.1 Overview

Date-triggered automation allows users to configure rules that automatically generate outbound emails based on date fields on Contact records. The classic use cases are birthday greetings, anniversary emails, annual service reminders, and contract renewal notices.

**Architecture:** An automation rule combines a **trigger** (which date field, with what timing offset), a **scope** (which Contacts, defined by a saved View), and an **action** (which template to send, from which account). A daily evaluation job generates emails for qualifying Contacts and places them in the approval queue.

### 19.2 Rule Configuration

When creating an automation rule, the user configures:

| Setting | Description | Example |
|---|---|---|
| **Name** | Display name for the rule. | "Birthday Greetings" |
| **Trigger field** | A date field on the Contact entity. Can be a system field (e.g., `birthday`) or a custom date field. | `birthday` |
| **Timing offset** | Days relative to the trigger date. Negative = before, 0 = on the day, positive = after. | `-3` (three days before birthday) |
| **Recipient View** | A saved View that defines the scope of Contacts this rule applies to. The View is evaluated dynamically at generation time — if a Contact is added to or removed from the View's filter criteria, the rule automatically adjusts. | "Active Customers" View |
| **Template** | The email template to use. | "Birthday Greeting" template |
| **Sending account** | Which provider account to send from. | `doug@example.com` |

### 19.3 Daily Evaluation Job

A scheduled job runs daily (configurable time, default: 2:00 AM in the tenant's time zone):

1. **Iterate active rules.** For each rule with `status = 'active'`:
2. **Evaluate the View.** Execute the saved View's query to get the current list of qualifying Contacts.
3. **Filter by trigger date.** For each Contact, check whether `trigger_field + timing_offset_days` falls within the generation window (today through the next evaluation cycle — typically today).
4. **Enforce opt-out.** Skip Contacts where `automated_email_opt_out = true`.
5. **Enforce delivery status.** Skip Contacts whose target email address has `delivery_status = bounced`.
6. **Check for duplicates.** Skip Contacts who already have a pending (any non-terminal status) outbound email from this same rule for this same trigger date occurrence.
7. **Detect overlaps.** Check whether the Contact has a pending outbound email from a *different* automation rule for the same date. If so, set `overlap_flag = true` and populate `overlap_details`.
8. **Generate email.** Create an `outbound_email_queue` record:
   - Resolve all merge fields in the template against the Contact's data.
   - Set `status = 'awaiting_approval'`.
   - Set `source_type = 'automation'`.
   - Set `automation_rule_id`.
   - Attach the template's default attachments.
9. **Update rule metadata.** Set `last_run_at` and `last_run_count` on the automation rule.
10. **Notify the user.** Send a notification to the rule creator: "Birthday Greetings generated 12 emails for approval."

### 19.4 Rule Lifecycle

| Status | Behavior |
|---|---|
| `active` | Rule is evaluated on each daily run. New emails are generated for qualifying Contacts. |
| `paused` | Rule is skipped during daily evaluation. Existing pending emails in the approval queue are not affected — they remain awaiting approval. |
| `archived` | Rule is soft-deleted. Not evaluated. Existing pending emails in the approval queue are cancelled. |

Pausing a rule is useful for temporary suspension (e.g., holiday period) without losing the configuration. Reactivating a paused rule causes the next daily evaluation to pick up any Contacts whose trigger dates were missed during the pause.

---

## 20. Approval Workflow

### 20.1 Awaiting Approval View

Automation-generated emails enter the system with `status = 'awaiting_approval'`. These are surfaced to the user in two places:

- **Home page widget:** A card on the user's home page showing the count of emails awaiting approval, with a link to the full approval view. If the count is zero, the widget is hidden.
- **Outbound Email Awaiting Approval View:** A dedicated system View (filterable by automation rule, date range, recipient) showing all pending emails. This is a standard View on the `outbound_email_queue` with `status = 'awaiting_approval'` as the base filter.

### 20.2 Individual Review

Each email in the approval queue displays:

- Recipient name and email address.
- Subject line (merge fields resolved).
- Body preview (merge fields resolved).
- Sending account.
- Automation rule name.
- Trigger date and timing offset context (e.g., "Birthday: March 15 — sending 3 days before").
- Overlap flag (if another rule targets the same Contact on the same date).
- Attachments.

The user can:

| Action | Result |
|---|---|
| **Approve** | Email transitions to `scheduled` (if `scheduled_send_at` is set) or `queued` (for immediate send). |
| **Edit & Approve** | Opens the email in the compose panel for editing. After edits, the user approves and the email transitions to `scheduled` or `queued`. |
| **Reject** | Email transitions to `rejected`. Not sent. The rejection is logged for rule performance tracking. |

### 20.3 Batch Approval

The approval view supports multi-select with batch actions:

- **Select multiple** (checkboxes) or **Select All** on the current filtered list.
- **Batch Approve:** All selected emails transition to `scheduled`/`queued`.
- **Batch Reject:** All selected emails transition to `rejected`.

Before batch approval executes, a confirmation summary is shown: "Approve 12 emails? 2 have overlap flags." The user confirms or cancels.

---

## 21. Click Tracking

### 21.1 Link Rewriting

When an outbound email is submitted for sending (after undo-send window expires), the email-safe HTML body is processed by the click tracking rewriter:

1. **Parse all `<a href>` links** in the email body HTML.
2. **Exclude signature links.** Links within the signature block (identified by position after the `-- ` delimiter) are not rewritten.
3. **For each body link:**
   a. Generate a unique `tracking_token`.
   b. Create a `tracked_links` record mapping the token to the original URL and the Communication record.
   c. Rewrite the `href` to the redirect URL: `https://{tracking_domain}/c/{tracking_token}`.
4. **Update the email HTML** with rewritten links before submitting to the provider API.

### 21.2 Redirect Service

When a recipient clicks a tracked link:

1. The redirect service receives the request at `https://{tracking_domain}/c/{tracking_token}`.
2. Looks up the `tracked_links` record by token.
3. Creates a `link_clicks` record capturing the click time, user agent, and IP address.
4. Resolves the `contact_id` from the Communication's participants (the tracked link is associated with a Communication, which has recipient Contact participants).
5. Issues an HTTP 302 redirect to the original URL.
6. The entire redirect completes in <100ms to avoid perceptible delay for the recipient.

### 21.3 Click Data Surfacing

Click data is displayed passively in existing views:

| Location | Display |
|---|---|
| **Communication record detail** | A "Link Clicks" section showing each tracked link's original URL, total click count, and most recent click time. |
| **Contact timeline** | Click events appear as activity items: "{Contact} clicked {link description} in your email '{subject}'" with timestamp. |
| **Template usage stats** | Aggregate click-through rates per template (total links clicked / total links sent across all emails using that template). |

No real-time notifications or alerts are generated for clicks in V1. Click data is available for passive review and for building Views/filters (e.g., "show me Contacts who clicked a link in the last 7 days").

---

## 22. Outbound Email Lifecycle & Communication Record Creation

### 22.1 Lifecycle States

```
                                    ┌──────────────────┐
                                    │   awaiting_       │
                              ┌────▶│   approval        │────┐
                              │     └──────────────────┘    │
                              │          │        │         │
                   [automation │    [approve] [edit+approve] │ [reject]
                    generates] │          │        │         │
                              │          ▼        ▼         ▼
┌─────────┐   [save]    ┌────┴────┐  ┌──────────┐   ┌──────────┐
│  (new)   │────────────▶│  draft   │  │ scheduled │   │ rejected  │
└─────────┘              └────┬────┘  └─────┬────┘   └──────────┘
                              │             │
                        [send] │    [time     │
                              │    arrives]  │
                              ▼             ▼
                         ┌──────────┐
                         │  queued   │
                         └────┬────┘
                              │
                     [undo window│expires]
                              │
                              ▼
                         ┌──────────┐
                         │  sending  │
                         └────┬────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
              ┌──────────┐       ┌──────────┐
              │   sent    │       │  failed   │
              └──────────┘       └──────────┘
```

Additional terminal state: `cancelled` (user cancels a scheduled or draft email).

### 22.2 Communication Record Creation

When an outbound email transitions to `sending`:

1. **Create Communication record.** A new Communication (`com_` prefix) is created in the `communications` table with:
   - `direction = 'outbound'`
   - `source = 'composed'` (new source value for CRM-originated sends)
   - `channel = 'email'`
   - `subject`, `content_raw` (email-safe HTML), `content_clean` (user's composed text), `content_html` (email-safe HTML)
   - `body_preview` (first 200 chars of content_clean)
   - `timestamp = NOW()`
   - `provider_account_id` = sending account
   - `has_attachments`, `attachment_count` from attachments

2. **Create Communication Participants.** Participant records for all To, CC, and BCC recipients with appropriate roles.

3. **Create Document relations.** Communication↔Document relations for each attachment, with `document_version_id` capturing the version at send time.

4. **Set `communication_id` on the queue record.** Links the outbound email queue entry to the Communication.

5. **Submit to provider API.** The email is sent via the provider adapter's send method (Gmail API `messages.send`, Outlook `sendMail`, etc.).

6. **Capture `provider_message_id`.** On successful send, the provider returns a message ID. This is stored on the Communication record for deduplication when the provider sync later encounters the same message in the Sent folder.

7. **Transition to `sent`.** The queue record transitions to `sent` and `sent_at` is recorded.

### 22.3 Provider Sync Deduplication

When the incremental sync adapter encounters a sent email in the provider's Sent folder:

- The sync process checks `provider_message_id` against existing Communication records.
- If a match is found (the CRM-composed email), the sync skips creating a duplicate. It may update metadata (provider-assigned thread ID, etc.) on the existing record.
- The `UNIQUE` constraint on `(provider_account_id, provider_message_id)` prevents accidental duplicates at the database level.

---

## 23. Conversation Assignment

### 23.1 Reply Context

When the user replies to an existing Communication, the outbound email inherits the parent Communication's `conversation_id`. This is set at compose time and stored on the outbound email queue record. The resulting Communication record joins the same Conversation.

### 23.2 Conversation Context Compose

When the user initiates a new compose from within a Conversation view (e.g., "New Email" button on a Conversation detail page), the outbound email's `conversation_id` is pre-set to that Conversation. Even though it's not a reply to any specific message, the user's intent is clear from the compose context.

### 23.3 New Compose

When the user composes a fresh email outside of any Conversation context (from a Contact record, from the global compose action, or from automation):

- The outbound email is created with `conversation_id = NULL`.
- After the provider syncs the sent message, the standard conversation formation logic (Conversations PRD) evaluates whether to assign it to an existing Conversation or create a new one, based on `provider_thread_id` and other signals.
- This avoids duplicating conversation formation logic in the compose path.

---

## 24. Bounce & Delivery Failure Handling

### 24.1 Failure Detection

When the provider API returns an error during send:

| Error Type | Detection | System Response |
|---|---|---|
| **Hard bounce** (address doesn't exist, domain invalid) | Provider API error response or post-send bounce notification (DSN) | Queue record → `failed`. Communication record `delivery_status` field set to `bounced`. |
| **Soft bounce** (mailbox full, temporary issue) | Provider API error or DSN | Queue record → `failed` with retry eligibility. Up to 3 retries with exponential backoff over 24 hours. |
| **Provider rejection** (rate limited, flagged as spam) | Provider API HTTP error (429, 550, etc.) | Queue record → `failed`. Logged for troubleshooting. No automatic retry for spam flags. Rate-limit retries follow provider `Retry-After` header. |
| **Authentication failure** (token expired) | Provider API HTTP 401 | Attempt token refresh. If refresh fails, queue record → `failed`, provider account status → `error`. User notified to re-authenticate. |

### 24.2 Contact Email Flagging

When a hard bounce is confirmed for a recipient email address:

- The `delivery_status` on the corresponding `contact_identifiers` record is set to `bounced`.
- The `delivery_status_updated_at` timestamp is recorded.
- The user is notified: "Email to {contact} at {email} bounced — address may be invalid."
- Future automation rules skip Contacts whose target email has `delivery_status = bounced`.
- The compose UI shows a warning if the user manually addresses an email to a bounced address: "This address has previously bounced. Send anyway?"

### 24.3 Communication Record for Failed Sends

If the email fails to send:

- The Communication record is still created (it was created at the `sending` transition) but is marked with a `delivery_status = 'failed'` field.
- The Communication appears in timelines with a visual indicator (e.g., red warning icon) so the user knows it wasn't delivered.
- The user can retry the send from the failed Communication's detail view.

---

## 25. Unsubscribe & Opt-Out

### 25.1 Contact-Level Opt-Out

The `automated_email_opt_out` field on the Contact entity (Section 7.10) controls whether automation rules generate emails for that Contact:

- `false` (default): Contact receives automation-generated emails.
- `true`: Automation rules skip this Contact during generation. Manual compose is unaffected.

### 25.2 Unsubscribe Link

All automation-generated outbound emails include a small unsubscribe link in the footer (below the signature). The link text is configurable at the tenant level (default: "Unsubscribe from automated emails").

When clicked:

1. The recipient is directed to a CRMExtender-hosted page.
2. The page confirms: "You have been unsubscribed from automated emails from {tenant name}."
3. The Contact's `automated_email_opt_out` flag is set to `true`.
4. The rule owner is notified: "{Contact} unsubscribed from automated emails."

### 25.3 Manual Opt-Out

Users can manually set the `automated_email_opt_out` flag on any Contact record through the standard field editing interface. This is useful when a Contact verbally requests to stop receiving automated emails.

### 25.4 Scope of Opt-Out

Opt-out applies **only** to automation-generated emails. It does not restrict:

- Manual compose and send to the opted-out Contact.
- Replies to emails initiated by the opted-out Contact.
- The Contact's appearance in Views or other CRM functions.

---

## 26. Event Sourcing

### 26.1 Email Template Events

Per Custom Objects PRD Section 19, email templates use a per-entity-type event table:

```sql
CREATE TABLE email_templates_events (
    event_id        TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL,       -- etl_01HX8A...
    tenant_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    event_data      JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT
);
```

**Event types:** `template_created`, `template_updated`, `template_archived`, `template_unarchived`, `visibility_changed`, `template_used`.

### 26.2 Automation Rule Events

```sql
CREATE TABLE automation_rules_events (
    event_id        TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL,       -- arl_01HX8A...
    tenant_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    event_data      JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT
);
```

**Event types:** `rule_created`, `rule_updated`, `rule_paused`, `rule_activated`, `rule_archived`, `rule_evaluated` (daily run), `emails_generated` (batch generation record).

### 26.3 Outbound Email Events

Outbound email queue state transitions are captured as events on the parent Communication record (in `communications_events`) rather than a separate event table, since the outbound email is ultimately a Communication. Additional event types for Communications:

- `email_composed` — User initiated composition.
- `email_draft_saved` — Auto-save or manual save.
- `email_scheduled` — Scheduled for future send.
- `email_approved` — Automation email approved.
- `email_rejected` — Automation email rejected.
- `email_sent` — Successfully sent via provider.
- `email_send_failed` — Provider returned error.
- `email_bounced` — Bounce detected post-send.
- `link_clicked` — Recipient clicked a tracked link (also stored in `link_clicks` table).

---

## 27. Virtual Schema & Data Sources

### 27.1 Email Template Virtual Schema

The email template object type's field registry generates a virtual schema table for use in Data Source queries:

| Virtual Column | Source | Type |
|---|---|---|
| `id` | `id` | TEXT |
| `name` | `name` | TEXT |
| `subject` | `subject` | TEXT |
| `visibility` | `visibility` | TEXT |
| `category` | `category` | TEXT |
| `use_count` | `use_count` | INTEGER |
| `last_used_at` | `last_used_at` | TIMESTAMPTZ |
| `created_at` | `created_at` | TIMESTAMPTZ |
| `created_by` | `created_by` | TEXT |

### 27.2 Automation Rule Virtual Schema

| Virtual Column | Source | Type |
|---|---|---|
| `id` | `id` | TEXT |
| `name` | `name` | TEXT |
| `template_id` | `template_id` | TEXT |
| `view_id` | `view_id` | TEXT |
| `trigger_field` | `trigger_field` | TEXT |
| `timing_offset_days` | `timing_offset_days` | INTEGER |
| `status` | `status` | TEXT |
| `last_run_at` | `last_run_at` | TIMESTAMPTZ |
| `last_run_count` | `last_run_count` | INTEGER |

### 27.3 Click Tracking Virtual Schema

Click tracking data is queryable through the Communication virtual schema with additional join capabilities:

- Communications gain a computed `click_count` field (count of `link_clicks` for tracked links on this Communication).
- Contacts gain a computed `email_clicks_30d` field (count of link clicks attributed to this Contact in the last 30 days).

These computed fields are available as filter and sort criteria in Views.

---

## 28. API Design

### 28.1 Compose & Send API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/outbound-emails` | POST | Create a new outbound email (draft or immediate send). Body includes recipients, subject, body, attachments, sending account, template_id, reply context. |
| `/api/v1/outbound-emails/{id}` | GET | Get outbound email detail (draft, scheduled, or sent). |
| `/api/v1/outbound-emails/{id}` | PATCH | Update a draft or scheduled email (recipients, subject, body, schedule time). |
| `/api/v1/outbound-emails/{id}/send` | POST | Send a draft immediately (enters undo-send window). |
| `/api/v1/outbound-emails/{id}/schedule` | POST | Schedule a draft for future send. Body: `{scheduled_send_at}`. |
| `/api/v1/outbound-emails/{id}/cancel` | POST | Cancel a scheduled or draft email. |
| `/api/v1/outbound-emails/{id}/undo` | POST | Undo a send during the undo window. |
| `/api/v1/outbound-emails/drafts` | GET | List current user's drafts. |
| `/api/v1/outbound-emails/scheduled` | GET | List current user's scheduled emails. |

### 28.2 Approval API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/outbound-emails/awaiting-approval` | GET | List emails awaiting approval (filterable by rule, date, recipient). |
| `/api/v1/outbound-emails/{id}/approve` | POST | Approve a single email for sending. |
| `/api/v1/outbound-emails/{id}/reject` | POST | Reject a single email. Optional body: `{reason}`. |
| `/api/v1/outbound-emails/batch-approve` | POST | Approve multiple emails. Body: `{ids: [...]}`. |
| `/api/v1/outbound-emails/batch-reject` | POST | Reject multiple emails. Body: `{ids: [...], reason?}`. |

### 28.3 Template CRUD API

Per Custom Objects PRD Section 23.4:

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/email-templates` | GET | List templates (filterable by visibility, category, creator). |
| `/api/v1/email-templates` | POST | Create a template. |
| `/api/v1/email-templates/{id}` | GET | Get template detail with body, merge fields, and default attachments. |
| `/api/v1/email-templates/{id}` | PATCH | Update template fields or body. |
| `/api/v1/email-templates/{id}/archive` | POST | Archive a template. |
| `/api/v1/email-templates/{id}/unarchive` | POST | Restore a template. |
| `/api/v1/email-templates/{id}/attachments` | GET | List default attachments. |
| `/api/v1/email-templates/{id}/attachments` | POST | Add a default attachment (body: `{document_id}`). |
| `/api/v1/email-templates/{id}/attachments/{attachment_id}` | DELETE | Remove a default attachment. |
| `/api/v1/email-templates/{id}/preview` | POST | Preview template with merge fields resolved against a specific Contact. Body: `{contact_id}`. |

### 28.4 Automation Rule API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/automation-rules` | GET | List automation rules (filterable by status). |
| `/api/v1/automation-rules` | POST | Create an automation rule. |
| `/api/v1/automation-rules/{id}` | GET | Get rule detail with last run info. |
| `/api/v1/automation-rules/{id}` | PATCH | Update rule configuration. |
| `/api/v1/automation-rules/{id}/pause` | POST | Pause the rule. |
| `/api/v1/automation-rules/{id}/activate` | POST | Activate (or reactivate) the rule. |
| `/api/v1/automation-rules/{id}/archive` | POST | Archive the rule (cancels pending emails). |
| `/api/v1/automation-rules/{id}/preview` | POST | Dry-run: show which Contacts would qualify and what emails would be generated, without actually generating them. |

### 28.5 Signature API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/signatures` | GET | List current user's signatures. |
| `/api/v1/signatures` | POST | Create a signature. |
| `/api/v1/signatures/{id}` | GET | Get signature detail. |
| `/api/v1/signatures/{id}` | PATCH | Update signature content or settings. |
| `/api/v1/signatures/{id}` | DELETE | Delete a signature. |

### 28.6 Click Tracking API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/communications/{id}/click-tracking` | GET | List tracked links and click events for a Communication. |
| `/api/v1/contacts/{id}/click-activity` | GET | List all click events attributed to a Contact (paginated, sorted by time). |
| `/c/{tracking_token}` | GET | Public redirect endpoint. Records click and redirects to original URL. (No authentication required.) |

### 28.7 Unsubscribe API

| Endpoint | Method | Description |
|---|---|---|
| `/unsubscribe/{token}` | GET | Public unsubscribe page. Displays confirmation and sets opt-out flag. (No authentication required.) |

---

## 29. Design Decisions

### 29.1 Why a Separate PRD from Email Provider Sync?

The Email Provider Sync PRD covers the plumbing — how emails are fetched from and sent to provider APIs, OAuth flows, sync cursors, and parsing pipelines. This PRD covers the user-facing experience — compose UI, templates, automation, click tracking. The audiences are different (infrastructure vs. product), the change cadences are different (adapter updates vs. feature additions), and the concerns are orthogonal.

### 29.2 Why Panel-Based Composer with Undock, Not Modal Overlay?

A modal overlay (Gmail-style floating compose) was considered. The panel-based approach was chosen because it integrates with the established GUI layout system (contextual action panel) rather than introducing a new UI paradigm. The undockable window option provides the multi-monitor benefit that a modal would offer, with the additional advantage of being a true OS window that persists independently of the main application state.

### 29.3 Why Click Tracking but Not Open Tracking?

Open tracking (invisible pixel) has degraded significantly due to Apple Mail Privacy Protection and Gmail image proxying. False positive rates are high enough to make open data unreliable for decision-making. Click tracking, by contrast, requires actual user action and provides a much stronger signal of engagement. Omitting open tracking also avoids the privacy perception issues that are increasingly relevant in relationship-focused communication.

### 29.4 Why Mandatory Approval for Automation?

Automation-generated emails are relationship-critical — they're sent to people the user actually knows. An incorrectly merged template or a poorly-timed birthday email to someone who recently experienced a loss could damage a real relationship. Mandatory approval ensures human oversight while still automating the 90% of the work (generating, populating, scheduling). The batch approve option provides the escape hatch for trusted, high-volume rules.

### 29.5 Why Auto-Create Contacts for CC/BCC?

Every person who appears in a user's email communication is a potential relationship worth tracking. Auto-creating Contacts for unknown CC/BCC addresses ensures the CRM captures the full communication landscape. The alternative — silently dropping unknown addresses from the CRM's participant model — creates gaps in the relationship graph.

### 29.6 Why All Attachments Must Be Document Entities?

This was a deliberate choice to maintain complete traceability. A "lightweight" attachment model (storing raw files without Document entity creation) would be simpler but would lose the version tracking, entity relation, and queryability that are core to CRMExtender's value proposition. The overhead of Document entity creation is minimal — it's an INSERT with metadata extraction — and the long-term benefit of answering "which version of what file was sent to whom" is substantial.

### 29.7 Why CRMExtender-Only Drafts?

Syncing drafts to the provider (Gmail Drafts, Outlook Drafts) adds bidirectional sync complexity: the user might edit the draft in Gmail, the CRM needs to detect the change, merge conflicts could arise. For V1, the simplicity of CRMExtender-only drafts outweighs the cross-client convenience. Users who want to finish a draft in Gmail can copy-paste. Provider draft sync is a candidate for future work.

### 29.8 Why `composed` as a New Source Value?

The Communications PRD defines `source` values: `synced`, `manual`, `imported`. CRM-composed outbound emails need a distinct source to differentiate them from emails that were composed externally and later synced back. The `composed` value enables queries like "how many emails were sent from within CRMExtender vs. from external clients?" which is valuable for measuring CRM adoption.

### 29.9 Why Provider-Enforced Rate Limits?

CRMExtender's target users are relationship-focused professionals, not high-volume senders. Gmail's 500/day (personal) or 2,000/day (Workspace) limits are well above typical relationship communication volume. Adding internal rate-limiting logic introduces complexity without serving a real user need. If the user hits provider limits, the error surfaces through the standard failure pipeline.

---

## 30. Phasing & Roadmap

### Phase 1: Core Compose & Send

**Goal:** Enable users to compose, reply, forward, and send emails directly from CRMExtender.

- Panel-based composer UI with recipient, subject, body, signature
- Rich text editor (shared with Notes)
- Email-safe HTML transformation pipeline
- Sending identity model (smart default priority chain)
- Reply, Reply All, Forward with proper header threading
- Recipient resolution (Contact search + freeform)
- Auto-create Contacts for unknown recipients
- BCC visibility rules
- Attachment upload and Document entity creation
- Attach from existing Documents
- Immediate Communication record creation on send
- Provider sync deduplication
- Undo-send window (10 seconds)
- Draft auto-save and management
- Outbound email queue with lifecycle management
- Conversation assignment (reply context and new compose)
- Bounce and delivery failure handling
- Contact email delivery status flagging
- `source = 'composed'` on Communications
- Event sourcing for outbound email state transitions

### Phase 2: Templates, Signatures & Scheduling

**Goal:** Template-driven composition, signature management, and scheduled sends.

- Email Template system object type with field registry and event sourcing
- Template creation, editing, and visibility management (personal/shared)
- Template application in compose (merge field resolution, default attachments)
- Merge field system (basic Contact/Company/Sender/Date fields + custom fields)
- Template usage tracking (use count, last used)
- Signature management (multiple per user, per-account defaults, reply behavior)
- Scheduled sends (manual date/time picker)
- Send worker for scheduled email dispatch
- Scheduled email management (view, edit, reschedule, cancel)
- Template default attachments
- "Save as Template" from compose

### Phase 3: Automation & Click Tracking

**Goal:** Date-triggered automation with approval workflow and link click tracking.

- Automation Rule system object type with field registry and event sourcing
- Automation rule configuration UI (trigger field, timing offset, View scope, template, sending account)
- Daily evaluation job (generate emails for qualifying Contacts)
- Opt-out enforcement (Contact flag + bounced addresses)
- Overlap detection across rules
- Approval workflow (individual review, edit & approve, reject)
- Batch approval with confirmation
- Home page widget (awaiting approval count + link)
- Awaiting Approval system View
- Automation rule lifecycle (active/paused/archived)
- Notification on generation (count, overlaps, skips)
- Click tracking: link rewriting in email body
- Click tracking: redirect service
- Click tracking: click data recording
- Click tracking: surfacing on Communication records and Contact timelines
- Unsubscribe link in automation emails
- Unsubscribe endpoint and opt-out flag management
- Template click-through rate aggregation
- Undockable compose window (Flutter multi-window)

---

## 31. Dependencies & Related PRDs

| PRD | Relationship | Dependency Direction |
|---|---|---|
| **Communications PRD** | Outbound emails are Communication records. This PRD extends the Communication entity with outbound-specific behaviors and adds the `composed` source value. | **Bidirectional.** Communications PRD defines the entity; this PRD adds compose/send behavior. Communications PRD needs update to add `source = 'composed'` option and reference this PRD. |
| **Email Provider Sync PRD** (planned) | This PRD uses the provider adapter's send method. The sync PRD handles deduplication when synced sent-folder messages match CRM-composed sends. | **Bidirectional.** Sync PRD provides send API; this PRD defines when/how send is called. |
| **Documents PRD** | All attachments create Document entities. Template default attachments reference Documents. | **This PRD depends on Documents** for attachment storage and version tracking. |
| **Conversations PRD** | Reply conversation assignment uses Conversations. New compose delegates to conversation formation logic. | **This PRD depends on Conversations** for thread assignment. |
| **Contact Management PRD** | Merge fields resolve against Contact fields. Auto-create Contacts for unknown recipients. Bounce handling updates Contact identifiers. Opt-out field added to Contact entity. | **Bidirectional.** Contact PRD needs update to add `automated_email_opt_out` field and `delivery_status` on identifiers. |
| **Custom Objects PRD** | Email Template and Automation Rule are system object types. Standard framework for field registry, event sourcing, and virtual schema. | **This PRD depends on Custom Objects** for the entity framework. |
| **Views & Grid PRD** | Automation rules scope recipients to saved Views. Awaiting Approval is a system View. Click tracking data is filterable in Views. | **This PRD depends on Views** for automation scoping and approval UI. |
| **Notes PRD** | Shared rich text editor and content architecture. | **Shared dependency** on the same editor component. |
| **Permissions & Sharing PRD** | Template visibility, BCC visibility, and automation rule access follow RBAC. | **This PRD depends on Permissions** for access control. |
| **GUI Functional Requirements PRD** | Compose panel uses the contextual action panel layout. Undockable window uses Flutter multi-window. | **This PRD depends on GUI PRD** for layout integration. |

---

## 32. Open Questions

1. **Click tracking domain** — Should click tracking use a subdomain of the tenant's domain (e.g., `track.customerdomain.com`) for better deliverability, or a shared CRMExtender tracking domain? Custom domains require DNS configuration per tenant. Shared domains risk domain reputation issues if any tenant sends poorly.

2. **Template versioning** — Should templates have full version history (like Documents), or is the current model (single current version with event sourcing for audit) sufficient? Full versioning would let automation rules pin to a specific template version rather than always using the latest.

3. **Bounce detection completeness** — Hard bounces from Gmail API are returned synchronously. But some bounces arrive asynchronously as DSN (Delivery Status Notification) emails. Should the system parse inbound DSN messages to detect bounces that weren't caught at send time?

4. **Rich text merge fields** — Can merge fields appear in rich text formatting contexts (e.g., a merge field inside a bold span, a merge field as link text)? The current model resolves merge fields as plain text. Supporting rich-text-aware merge fields adds complexity to the template engine.

5. **Automation rule calendar awareness** — Should automation rules have awareness of holidays or blackout dates? For example, a birthday email scheduled on Christmas Day might be better deferred. This adds a calendar/holiday data dependency.

6. **Multi-recipient automation** — The current model generates one email per Contact. Should automation rules support sending a single email to multiple Contacts (e.g., a "Season Opener" email to all contacts in a View, sent as one BCC batch)? This is a different paradigm from personalized 1:1 sends.

7. **Compose session recovery** — If the user's browser/app crashes during composition, the auto-save draft should recover the session. What is the maximum acceptable data loss window? Current spec says 30-second auto-save intervals.

---

## 33. Future Work

- **Email sequences** — Multi-step automated email sequences triggered by events or time delays. E.g., "Day 1: Introduction → Day 3: Follow-up → Day 7: Check-in." Requires a sequence builder UI, step conditions, and exit criteria.
- **Conditional merge fields** — Template logic like "if Contact has a company, include this paragraph." Requires a template expression language.
- **Computed merge fields** — Derived values like "days since last communication" or "number of open tasks." Requires the template engine to execute queries.
- **Provider draft sync** — Bidirectional draft sync with Gmail/Outlook Drafts folder, enabling cross-client composition.
- **A/B testing for templates** — Send variant A to half of an automation's recipients and variant B to the other half. Track click-through rates per variant.
- **Send-time optimization** — AI-suggested optimal send times based on recipient engagement history (when do they typically open/click?).
- **Real-time click notifications** — Push notification or in-app alert when a recipient clicks a tracked link. Useful for time-sensitive sales scenarios.
- **Thread summary in compose** — When replying, show an AI-generated summary of the conversation thread in the compose panel so the user can reference key points without scrolling through the full history.
- **Abbreviated signatures** — A shortened signature variant for replies (currently `reply_behavior` supports full or none; abbreviated is a future enhancement).
- **Template categories as entity** — Promote template categories from a simple Select field to a managed entity with descriptions, ownership, and ordering.
- **Internal rate limiting** — If CRMExtender expands to support high-volume senders, internal rate limiting per provider account to prevent provider-level blocks.

---

## 34. Glossary

| Term | Definition |
|---|---|
| **Outbound email** | An email composed and sent from within CRMExtender, as opposed to one composed in an external email client and later synced. |
| **Email template** | A reusable email composition blueprint with merge field placeholders, stored as a system object type (`etl_` prefix). |
| **Merge field** | A placeholder in a template that is resolved to actual data at compose or generation time. Syntax: `{{entity.field}}`. |
| **Automation rule** | A configuration that generates outbound emails based on Contact date fields, scoped to a saved View, with mandatory approval before sending. Stored as a system object type (`arl_` prefix). |
| **Approval queue** | The list of automation-generated emails awaiting user review and approval before sending. |
| **Click tracking** | The system of rewriting links in outbound email body content to pass through a redirect service, recording recipient clicks. |
| **Tracked link** | A link in an outbound email whose URL has been rewritten to include a tracking token for click detection. |
| **Undo-send window** | A 10-second delay after the user clicks Send during which the email can be recalled. |
| **Email-safe HTML** | HTML that uses inline styles, table-based layout, and limited CSS to render consistently across email clients (Gmail, Outlook, Apple Mail, etc.). |
| **Sending identity** | The provider account (email address) from which an outbound email is sent. Selected by the smart default priority chain or manually by the user. |
| **Provider adapter** | A module implementing the provider interface for a specific email service (Gmail, Outlook, IMAP). Used for both fetching inbound and sending outbound email. |
| **Bounce** | A delivery failure where the recipient's mail server rejects the email. Hard bounces indicate permanent failure (invalid address); soft bounces indicate temporary issues. |
| **Opt-out** | A Contact-level flag (`automated_email_opt_out`) that prevents automation rules from generating emails for that Contact. Does not affect manual sends. |
| **DSN** | Delivery Status Notification — a standardized email message sent by a mail server to report delivery success or failure. |

---

*This document is a living specification. As the Email Provider Sync PRD is developed and as implementation reveals design decisions, sections will be updated to reflect scope adjustments and lessons learned.*
