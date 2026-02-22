# Product Requirements Document: Communication & Conversation Intelligence

## CRMExtender — Multi-Channel Conversation Management Subsystem

**Version:** 2.0
**Date:** 2026-02-07
**Status:** Draft
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Organizational Hierarchy](#5-organizational-hierarchy)
6. [Communications](#6-communications)
7. [Conversations](#7-conversations)
8. [Topics & Projects](#8-topics--projects)
9. [Multi-Channel Communication Types](#9-multi-channel-communication-types)
10. [Communication Segmentation & Cross-Conversation References](#10-communication-segmentation--cross-conversation-references)
11. [AI Intelligence Layer](#11-ai-intelligence-layer)
12. [Contact Association & Identity Resolution](#12-contact-association--identity-resolution)
13. [Email Provider Integration](#13-email-provider-integration)
14. [Email Sync Pipeline](#14-email-sync-pipeline)
15. [Email Parsing & Content Extraction](#15-email-parsing--content-extraction)
16. [Triage & Intelligent Filtering](#16-triage--intelligent-filtering)
17. [Views & Dashboards](#17-views--dashboards)
18. [User-Defined Alerts](#18-user-defined-alerts)
19. [Conversation Lifecycle & Status Management](#19-conversation-lifecycle--status-management)
20. [Multi-Account Management](#20-multi-account-management)
21. [Search & Discovery](#21-search--discovery)
22. [Storage & Data Retention](#22-storage--data-retention)
23. [Privacy, Security & Compliance](#23-privacy-security--compliance)
24. [Phasing & Roadmap](#24-phasing--roadmap)
25. [Related PRDs](#25-related-prds)
26. [Dependencies & Risks](#26-dependencies--risks)
27. [Open Questions](#27-open-questions)
28. [Glossary](#28-glossary)

---

## 1. Executive Summary

The Communication & Conversation Intelligence subsystem is the primary relationship signal layer of CRMExtender. It captures communications across multiple channels — email, SMS, phone calls, video meetings, in-person meetings, and manual notes — and organizes them into a structured hierarchy of **Projects**, **Topics**, **Conversations**, and **Communications** that reflects how professionals actually think about their work.

Unlike traditional CRM email integrations that log individual messages as flat artifacts, this system understands that a business relationship plays out across channels, over time, and across multiple parallel workstreams. A lease negotiation might involve email threads with a lawyer, SMS exchanges with a broker, and in-person meetings with a landlord — all part of the same topic, under the same project, sequenced by timestamp into a coherent narrative.

**Core principles:**

- **Multi-channel, unified timeline** — Communications from any channel (email, SMS, phone, video, in-person) are sequenced by timestamp into conversations. An email exchange can seamlessly continue via SMS and back to email, and the system maintains continuity.
- **Hierarchical organization** — Projects contain Topics, Topics contain Conversations, Conversations contain Communications. This hierarchy is optional and flexible — communications can exist unassigned, and conversations don't need to belong to a project.
- **AI-powered auto-organization with human oversight** — The system automatically classifies, routes, and groups communications into conversations and topics. Users review auto-assignments and correct mistakes. The system learns from corrections to improve over time.
- **Intelligence-first** — Every conversation receives AI-generated summaries, status classifications, action items, and topic tags. Content is cleaned of noise (quoted replies, signatures, boilerplate) before any human or AI sees it.
- **Contact-centric** — Every communication participant is resolved to a CRM contact via the Contact Intelligence system. Unknown identifiers trigger identity resolution workflows. Conversations are always associated with identified contacts.

**Current state:** A functional Gmail-only proof of concept exists with 95+ tests covering the email parsing pipeline, multi-account sync, SQLite persistence, triage filtering, and Claude-powered summarization. This PRD defines the requirements for the full multi-channel conversation management system.

---

## 2. Problem Statement

### The Communication Intelligence Gap

Professional relationships play out across multiple channels — email, text messages, phone calls, video meetings, and in-person conversations. Yet existing CRM tools treat each channel as an isolated silo, and even within email, they log individual messages rather than understanding conversations.

**The consequences for CRM users:**

| Pain Point                      | Impact                                                                                                                                                                                              |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Channel silos**               | An email thread about a deal, a follow-up SMS, and a phone call with the same contact appear as three unrelated entries. The full picture requires manual assembly.                                 |
| **Manual conversation logging** | Sales reps spend 20-30 minutes daily copying email content into CRM records. Phone calls and meetings require manual note entry with no structure. Most users give up, leaving CRM data incomplete. |
| **No thread context**           | Individual emails are logged without conversation context. A 15-message negotiation thread appears as 15 disconnected entries.                                                                      |
| **No organizational structure** | CRM tools provide no way to group conversations by project or topic. A complex deal with legal, financial, and technical workstreams appears as a flat list.                                        |
| **Noise overwhelms signal**     | Forwarded chains, legal disclaimers, and signature blocks bloat logged content. Finding the actual message requires manual editing.                                                                 |
| **Blind spots on engagement**   | Without systematic cross-channel analysis, managers cannot see which relationships are active, stale, or at risk.                                                                                   |
| **Scattered across accounts**   | Professionals with multiple email accounts and phone numbers have no unified view of their communication landscape.                                                                                 |
| **No proactive intelligence**   | Communication content is rich with signals — pending action items, open questions, sentiment shifts — but extracting them requires reading every thread and listening to every call.                |

### Why Existing Solutions Fall Short

- **Native CRM email integrations** (Salesforce, HubSpot) — Log individual emails, not conversations. No multi-channel unification. No AI analysis. No content cleaning. Require manual association with contacts/deals.
- **Email aggregation services** (Nylas, Mailgun) — Provide email API abstraction but no intelligence layer. Email only — no SMS, calls, or meetings. Per-mailbox pricing at scale.
- **Communication platforms** (Slack, Teams) — Excellent for real-time collaboration but siloed from CRM data. No cross-channel conversation model.
- **Email clients** (Gmail, Outlook) — Excellent for reading/sending but offer no CRM-level relationship intelligence, no cross-channel view, no project organization.

CRMExtender closes this gap by treating all communications — regardless of channel — as **signals to mine and organize**, not artifacts to log.

---

## 3. Goals & Success Metrics

### Primary Goals

1. **Unified multi-channel capture** — Communications from email, SMS, phone, video, and in-person interactions flow into a single system and are organized into coherent conversations.
2. **Intelligent auto-organization** — The system automatically groups communications into conversations, associates conversations with topics, and suggests project assignments — with user review and correction.
3. **Actionable conversation intelligence** — Every conversation of sufficient substance has an AI-generated summary, status classification, action items, and topic tags.
4. **Zero-noise content** — Email content displayed to users and fed to AI has quotes, signatures, disclaimers, and boilerplate removed with >95% accuracy.
5. **Cross-channel continuity** — A conversation that starts via email, continues via SMS, and resumes via email is presented as a single coherent timeline.
6. **Contact resolution for all channels** — Every communication participant is resolved to a CRM contact, regardless of whether they were identified by email address, phone number, or other identifier.
7. **User-empowered visibility** — Users define their own views and alerts to see exactly the information they need, rather than relying on a prescriptive dashboard.

### Success Metrics

| Metric                                     | Target                                                                    | Measurement                                                  |
| ------------------------------------------ | ------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Email sync coverage                        | 100% of inbox emails captured                                             | Audit: compare message counts between provider and DB        |
| Conversation auto-assignment accuracy      | >85% of communications assigned to the correct conversation               | User correction rate as inverse proxy                        |
| Topic auto-assignment accuracy             | >75% of conversations assigned to the correct topic                       | User correction rate as inverse proxy                        |
| Content cleaning accuracy                  | >95% of email quotes/signatures/boilerplate removed                       | Human evaluation of 200 sampled cleaned emails               |
| False-positive cleaning rate               | <1% of original authored content incorrectly removed                      | Human evaluation of same 200 samples                         |
| AI summarization coverage                  | 100% of non-triaged, substantive conversations summarized                 | DB query: eligible conversations with ai_summary IS NOT NULL |
| Action item extraction recall              | >80% of genuine action items captured                                     | Human evaluation of 100 conversation summaries               |
| Contact resolution rate                    | >95% of communication participants identified                             | DB query: communications with unresolved contacts            |
| Cross-channel conversation stitching       | >90% of related cross-channel communications in the same conversation     | Human evaluation of 100 multi-channel conversations          |
| Triage precision                           | >95% of filtered communications are genuinely automated/marketing         | Human review of 200 triaged items                            |
| User correction rate (declining over time) | <10% of auto-assignments corrected after 90 days of use                   | Analytics: correction actions / total assignments            |
| Sync latency (email — Gmail/Outlook)       | <60 seconds from delivery to CRM availability                             | Instrumented end-to-end measurement                          |
| User adoption                              | >70% of users connect at least one communication source within first week | Analytics: account connection rate                           |
| Time savings                               | >20 minutes/day reduction in manual CRM logging                           | User survey at 30 and 90 days                                |

---

## 4. User Personas & Stories

### Personas

| Persona                | Communication Context                                                                                                                          | Key Needs                                                                                                                                                          |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Alex — Sales Rep**   | 2 email accounts (work Gmail, personal Outlook). Texts clients from mobile. 80+ emails/day, 20+ SMS/day. Manages 30 active deal conversations. | See which deals have unanswered communications across all channels. Get summaries of long threads before calls. Link conversations to deals.                       |
| **Maria — Consultant** | 1 Gmail account. Frequent phone calls with clients. 40+ emails/day. Manages relationships across 50+ clients and referral partners.            | Track which relationships are going stale across all channels. Surface action items from emails AND call notes. Prep for meetings with full conversation history.  |
| **Jordan — Team Lead** | 1 work Outlook + shared team inbox (IMAP). Team uses SMS for quick coordination. 100+ emails/day.                                              | Unified view of team's client conversations across channels. Identify conversations requiring escalation. Weekly summary of open action items across all projects. |

### User Stories

#### Hierarchy & Organization

- **US-1:** As a user, I want to create projects to organize my work so that all related topics, conversations, and communications are grouped together.
- **US-2:** As a user, I want to create sub-projects within a project so that I can organize complex initiatives with multiple workstreams.
- **US-3:** As a user, I want to create topics within a project so that conversations about distinct aspects of the project are separated (e.g., "Legal Review" vs. "Financial Analysis" under an acquisition project).
- **US-4:** As a user, I want the system to automatically create new conversations when it detects communications that don't fit any existing conversation.
- **US-5:** As a user, I want the system to automatically suggest topic assignments for new conversations based on their content.
- **US-6:** As a user, I want to move conversations between topics and projects when the system's auto-assignment is wrong.
- **US-7:** As a user, I want conversations and communications to be allowed to exist unassigned — not everything belongs to a project.

#### Multi-Channel Communications

- **US-8:** As a user, I want my email conversations to automatically sync into the system so I don't have to manually log them.
- **US-9:** As a user, I want my SMS messages to appear in the system so that text-based follow-ups are captured alongside emails.
- **US-10:** As a user, I want to log a phone call by entering the date, duration, participants, and my notes so that the call is part of the conversation record.
- **US-11:** As a user, I want recorded phone calls to be transcribed and stored as communications so that the content is searchable and summarizable.
- **US-12:** As a user, I want to log an in-person meeting with participants, date, and notes so that face-to-face interactions are part of the conversation history.
- **US-13:** As a user, I want to see a unified timeline for a conversation that interleaves emails, SMS messages, call notes, and meeting notes in chronological order.
- **US-14:** As a user, I want to attach files (recordings, documents, photos) to any communication so that supporting materials are linked to the conversation.

#### Communication Segmentation

- **US-15:** As a user, I want to select a portion of a communication and assign it to a different conversation when a single email covers multiple topics.
- **US-16:** As a user, I want a communication that spans two conversations to appear in both, with the full original preserved and the relevant segment highlighted in each.

#### Intelligence & AI

- **US-17:** As a user, I want AI-generated summaries for conversations that have substantive content so that I can quickly understand the state of every active thread.
- **US-18:** As a user, I want the system to extract action items from conversations across all communication types.
- **US-19:** As a user, I want conversations classified by status (Open, Closed, Uncertain) so I can visually scan for threads needing attention.
- **US-20:** As a user, I want the system to learn from my corrections when I reassign communications to different conversations, so that auto-assignment improves over time.

#### Views & Alerts

- **US-21:** As a user, I want to create custom views (saved queries) that show me exactly the data I care about, filtered and sorted my way.
- **US-22:** As a user, I want to share views with my team so that everyone can benefit from useful queries.
- **US-23:** As a user, I want to turn any view into an alert that notifies me when new results appear, with configurable frequency (immediate, hourly, daily, weekly).
- **US-24:** As a user, I want no default alerts — I define only the notifications I actually want.

#### Contact Association

- **US-25:** As a user, I want every communication participant automatically resolved to a CRM contact, whether identified by email address, phone number, or other identifier.
- **US-26:** As a user, I want to be notified when the system encounters an unknown sender so I can identify them or create a new contact.
- **US-27:** As a user, I want communications from unidentified contacts to still be documented and assigned to conversations — identification should not block the workflow.

---

## 5. Organizational Hierarchy

### 5.1 The Hierarchy Model

Communications are organized into an optional, flexible hierarchy:

```
Project
  └── Sub-project (optional, recursive)
        └── Topic
              └── Conversation
                    └── Communication
                          └── Segment (when split across conversations)
```

**Every level is optional.** Communications can exist unassigned. Conversations don't need to belong to a topic or project. The hierarchy exists to help users organize their work — it is never forced.

### 5.2 Hierarchy Entities

#### Project

The highest-level organizational container. Represents a business initiative, engagement, deal, or any user-defined grouping of related work.

| Attribute       | Description                                             |
| --------------- | ------------------------------------------------------- |
| Name            | User-defined project name                               |
| Description     | Optional description of the project's purpose and scope |
| Status          | Active, On Hold, Completed, Archived                    |
| Owner           | The user who created/manages the project                |
| Sub-projects    | Zero or more child projects (recursive nesting)         |
| Topics          | Zero or more topics within the project                  |
| Created/Updated | Timestamps                                              |

**Creation model:**

- **Proactive** — User creates a project before any communications occur, in anticipation of future work. May pre-define topics that will have future conversations. Example: "Office Relocation" project created with topics "Lease Negotiation", "Moving Logistics", "IT Setup" before any emails are exchanged.
- **Reactive** — User creates a project in response to an incoming communication that introduces a new initiative. Example: An email arrives about a new opportunity, and the user creates a project to organize the ensuing conversations.

#### Sub-project

A child project nested within a parent project. Shares the same structure as a project. Enables organizing complex initiatives with multiple workstreams.

Example:

```
Project: Office Relocation
  ├── Sub-project: NYC Office
  │     ├── Topic: Lease Negotiation
  │     └── Topic: IT Setup
  └── Sub-project: Chicago Office
        ├── Topic: Lease Negotiation
        └── Topic: Build-Out
```

#### Topic

An organizational grouping within a project that represents a distinct subject area or workstream. A topic contains one or more conversations, each with different participants, all about the same subject.

| Attribute       | Description                                               |
| --------------- | --------------------------------------------------------- |
| Name            | User-defined or AI-suggested topic name                   |
| Description     | Optional description                                      |
| Project         | The parent project (or sub-project) this topic belongs to |
| Conversations   | Zero or more conversations about this topic               |
| Created/Updated | Timestamps                                                |

**Key distinction — Topic vs. Conversation:** A topic groups conversations that are about the same subject but with different people. Under a "Lease Negotiation" topic, there might be:

- A conversation with the lawyer (emails + phone calls about contract terms)
- A conversation with the accountant (emails about financial analysis)
- A conversation with the lessor (emails + in-person meetings about the deal itself)

Three separate conversations, each with different participants, all about the same topic.

**Creation model:**

- **User-created** — User explicitly creates a topic within a project.
- **AI-suggested** — When a new conversation doesn't fit existing topics, the system suggests creating a new topic. User confirms or adjusts.

#### Conversation

A logical grouping of related communications between a specific set of participants about a specific subject. A conversation can span multiple channels (email, SMS, phone) and is sequenced by timestamp.

| Attribute       | Description                                                             |
| --------------- | ----------------------------------------------------------------------- |
| Subject/Title   | Derived from email subject, or user-defined for non-email conversations |
| Participants    | The set of contacts involved                                            |
| Communications  | One or more communications, ordered by timestamp                        |
| Topic           | The parent topic (optional — conversations can be unassigned)           |
| AI Summary      | AI-generated summary (when warranted)                                   |
| AI Status       | Open, Closed, Uncertain                                                 |
| AI Action Items | Extracted action items                                                  |
| AI Key Topics   | Extracted topic tags                                                    |
| System Status   | Active, Stale, Closed                                                   |
| Created/Updated | Timestamps                                                              |

**Creation model:**

- **Automatic from email threading** — Email thread IDs (Gmail `threadId`, Outlook `conversationId`) automatically create and populate conversations.
- **Automatic from participant grouping** — SMS messages between the same set of contacts form a default participant-based conversation.
- **AI-suggested splitting** — When the AI detects a communication doesn't fit the current conversation, it may suggest creating a new one.
- **User-created** — User explicitly creates a conversation and assigns communications to it.

**Contact requirement:** Under no circumstance should a conversation be left with unidentified contacts. The system actively works to identify all participants. While identification is pending, the communication is still documented and the conversation proceeds — but the system flags unresolved contacts for user review.

#### Communication

An individual interaction — a single email, SMS message, phone call, video meeting, in-person meeting, or user-entered note. The atomic unit of the system.

| Attribute       | Description                                                                   |
| --------------- | ----------------------------------------------------------------------------- |
| Timestamp       | When the communication occurred                                               |
| Channel         | Email, SMS, Phone, Video, In-Person, Note                                     |
| Participants    | Sender/recipients (resolved to CRM contacts)                                  |
| Content         | Email body, SMS text, call transcript, meeting notes, user-written notes      |
| Direction       | Inbound, Outbound, or Mutual (for meetings/calls)                             |
| Source          | Auto-synced (email, SMS) or Manually entered (notes, unrecorded calls)        |
| Conversation    | The conversation this communication belongs to (optional — can be unassigned) |
| Attachments     | Zero or more attached files (recordings, documents, images)                   |
| AI Summary      | AI-generated summary (for long communications only)                           |
| Created/Updated | Timestamps                                                                    |

**Unassigned communications:** Communications from marketing organizations, unknown senders awaiting identification, or one-off exchanges that don't relate to any conversation simply exist in a list of unassigned communications. They can be assigned later by the user or by AI as more context becomes available.

#### Segment

A portion of a communication that has been assigned to a different conversation than the communication's primary conversation. Used when a single email or message covers multiple topics.

| Attribute            | Description                                                |
| -------------------- | ---------------------------------------------------------- |
| Source Communication | The original communication this segment was extracted from |
| Content              | The selected text from the original communication          |
| Target Conversation  | The conversation this segment is assigned to               |
| Created by           | User who created the segment                               |
| Created/Updated      | Timestamps                                                 |

**The split/reference model:**

- The original communication lives in its primary conversation (full content preserved).
- A segment (selected text) is created and assigned to a second conversation.
- The original communication now has references in both conversations.
- Both conversations show the relevant content: the primary shows the full communication, the secondary shows the segment with a link back to the original.

---

## 6. Communications

### 6.1 Unified Communication Record

All communication types share a common record structure, regardless of channel:

| Field          | Description           | Email                | SMS               | Recorded Call               | Unrecorded Call    | Video                       | In-Person          | Note               |
| -------------- | --------------------- | -------------------- | ----------------- | --------------------------- | ------------------ | --------------------------- | ------------------ | ------------------ |
| Timestamp      | When it happened      | Email date header    | Message timestamp | Call start time             | User-entered       | Meeting start               | User-entered       | User-entered       |
| Participants   | Who was involved      | From/To/CC           | Phone numbers     | Call participants           | User-entered       | Attendees                   | User-entered       | User-entered       |
| Channel        | Communication type    | `email`              | `sms`             | `phone`                     | `phone`            | `video`                     | `in_person`        | `note`             |
| Content        | The substance         | Email body (cleaned) | Message text      | Transcript                  | User-written notes | Transcript                  | User-written notes | User-written notes |
| Direction      | Relative to user      | Inbound/Outbound     | Inbound/Outbound  | Mutual                      | Mutual             | Mutual                      | Mutual             | N/A                |
| Source         | How it entered        | Auto-synced          | Auto-synced       | Auto-synced + transcription | Manual entry       | Auto-synced + transcription | Manual entry       | Manual entry       |
| Attachments    | Linked files          | Email attachments    | Media             | Audio recording             | None               | Video recording             | Photos, documents  | Any files          |
| Auto-captured? | Requires user action? | Yes                  | Yes               | Yes (metadata + transcript) | No                 | Yes (metadata + transcript) | No                 | No                 |

### 6.2 Content Characteristics by Channel

Different channels have fundamentally different content characteristics that affect how the system processes them:

| Channel          | Content Length              | Threading Available?      | Content Quality                   | Parsing Needed?                               |
| ---------------- | --------------------------- | ------------------------- | --------------------------------- | --------------------------------------------- |
| Email            | Medium-long (50-5000 words) | Yes (provider thread IDs) | High (structured, detailed)       | Yes (heavy — quotes, signatures, boilerplate) |
| SMS              | Very short (1-50 words)     | No (flat stream)          | Low (terse, context-dependent)    | Minimal                                       |
| Phone transcript | Long (500-10,000 words)     | No                        | Medium (conversational, rambling) | Some (filler words, speaker labels)           |
| Video transcript | Long                        | No                        | Medium (same as phone)            | Some                                          |
| In-person notes  | Variable (user-written)     | No                        | High (user curates)               | None                                          |
| Manual notes     | Variable (user-written)     | No                        | High (user curates)               | None                                          |

### 6.3 Communication Entry Points

| Channel               | How It Enters the System                                                                                                   |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Email                 | Auto-synced from Gmail API, Microsoft Graph API, or IMAP                                                                   |
| SMS                   | Auto-synced from phone integration or SMS provider API                                                                     |
| Recorded phone call   | Metadata + recording from VoIP integration (Twilio, RingCentral, etc.); transcript generated via speech-to-text            |
| Unrecorded phone call | User manually creates a communication record (Note) with date, participants, and key points                                |
| Recorded video call   | Metadata + recording from meeting platform (Zoom, Teams); transcript generated via speech-to-text                          |
| Unrecorded video call | User manually creates a Note                                                                                               |
| In-person meeting     | User manually creates a Note with date, attendees, and key points                                                          |
| Calendar-triggered    | Scheduled meetings from calendar integration can auto-create placeholder communications; user adds notes after the meeting |

### 6.4 Timestamp as the Universal Sequencing Key

All communications across all channels are sequenced by timestamp. This is what enables a unified conversation timeline:

```
Conversation: Lease Negotiation with Bob
  10:15 AM  [EMAIL]     Bob → Me: Contract draft attached
  10:32 AM  [EMAIL]     Me → Bob: Questions about clause 5
  12:45 PM  [SMS]       Me → Bob: "Hey, did you see my questions?"
   1:02 PM  [SMS]       Bob → Me: "Yes, checking with legal, will reply tonight"
   3:00 PM  [PHONE]     Call with Bob (12 min) — "Discussed clause 5, agreed to revise"
   6:30 PM  [EMAIL]     Bob → Me: Revised clause 5 language
```

A single conversation, three channels, one coherent timeline.

### 6.5 Attachments

Any communication can have zero or more attached files:

| Attribute         | Description                                                             |
| ----------------- | ----------------------------------------------------------------------- |
| Filename          | Original filename                                                       |
| File type         | MIME type / extension (audio, video, document, image, etc.)             |
| Size              | File size in bytes                                                      |
| Storage reference | Location in object storage (S3/MinIO)                                   |
| Source            | Synced from email, uploaded by user, pulled from meeting platform, etc. |

For recorded calls and video meetings, the **transcript becomes the content** of the communication (for AI processing and search), while the **original recording is an attachment** (for playback and verification).

---

## 7. Conversations

### 7.1 Conversation Formation

Conversations are formed through different mechanisms depending on the communication channel:

#### Email-Based Conversations (Automatic)

Email providers supply native thread identifiers that automatically group related messages:

| Provider | Threading Mechanism                                                                                                     |
| -------- | ----------------------------------------------------------------------------------------------------------------------- |
| Gmail    | `threadId` — Gmail groups messages by subject and participants                                                          |
| Outlook  | `conversationId` — Outlook groups messages by conversation                                                              |
| IMAP     | Reconstructed from RFC 5322 headers (`Message-ID`, `References`, `In-Reply-To`), with subject-line matching as fallback |

An email thread automatically creates a conversation. Additional email threads may be merged into the same conversation by the AI or user if they are determined to be part of the same exchange.

#### Participant-Based Conversations (SMS, Calls)

For channels without native threading (SMS, phone calls), the system creates **default participant-based conversations**:

- All SMS messages between the same set of participants form a single default conversation: "SMS with Bob" or "Group SMS with Bob, Alice, and Carol."
- This is a catch-all stream — it contains all SMS exchanges with that participant set, regardless of topic.
- Users can select specific messages from this default conversation and assign them to topic-specific conversations (e.g., move a lease-related SMS into the "Lease Negotiation" conversation).

#### Manually Created Conversations

Users can create conversations explicitly and assign communications to them. This is the primary model for:

- Organizing phone call and meeting notes into topic-specific conversations.
- Pulling SMS messages out of the default participant-based conversation.
- Creating a conversation around communications from multiple channels.

### 7.2 Multi-Channel Conversations

A conversation can contain communications from multiple channels. The system maintains continuity through timestamp sequencing:

- An email thread forms the backbone of a conversation.
- An SMS sent 30 minutes after the last email, between the same participants, is likely part of the same conversation.
- A phone call note logged by the user and assigned to the conversation appears in the timeline at the correct chronological position.

**Automatic cross-channel stitching for email:** Email thread IDs provide reliable automatic conversation assignment for email communications.

**Manual cross-channel stitching for other channels:** SMS, calls, and meetings must be assigned to conversations by the user (or by AI with user review) because there is no reliable automatic mechanism to determine which conversation they belong to.

### 7.3 Conversation Properties

| Property            | Source                                  | Description                                             |
| ------------------- | --------------------------------------- | ------------------------------------------------------- |
| Participant list    | Union of all communication participants | All contacts involved across all channels               |
| Communication count | Computed                                | Total number of communications across all channels      |
| Channel breakdown   | Computed                                | Count of communications by channel type                 |
| First/last activity | Computed from timestamps                | Earliest and most recent communication                  |
| Active channels     | Computed                                | Which channels have been used (email, SMS, phone, etc.) |

---

## 8. Topics & Projects

### 8.1 Topics

Topics group related conversations within a project. They are an organizational device for user understanding — they help users find and manage conversations about the same subject area.

**Example:**

```
Topic: Lease Negotiation
  ├── Conversation with lawyer (3 emails, 1 phone call)
  ├── Conversation with accountant (2 emails)
  └── Conversation with lessor (5 emails, 1 in-person meeting)
```

Three different conversations, three different sets of people, all about lease negotiation.

**Topic creation:**

- **User-created:** User explicitly creates a topic within a project, possibly before any conversations exist.
- **AI-suggested:** When the system detects a conversation about a subject that doesn't fit any existing topic, it suggests creating a new topic. The user confirms, adjusts the name, or assigns to an existing topic.

### 8.2 Projects

Projects are the top-level organizational container. They represent a business initiative, engagement, deal, or any user-defined grouping.

**Project creation:**

- **Almost always user-created.** Projects are intentional — they represent a decision to organize work around a specific initiative.
- **Proactive:** Created before any communications, in anticipation of future work. Topics may be pre-defined. Example: Creating "Acme Corp Acquisition" with topics "Due Diligence", "Legal Review", "Integration Planning" before the first email.
- **Reactive:** Created in response to communications that introduce a new initiative. Example: An email arrives about an unexpected opportunity, and the user creates a project to organize the ensuing work.

### 8.3 Sub-Projects

Projects can contain sub-projects for additional organizational depth. Sub-projects share the same structure as projects (name, description, status, topics) and can be nested recursively.

**Use case:** A large initiative with distinct sub-initiatives:

```
Project: 2026 Expansion
  ├── Sub-project: NYC Office
  │     ├── Topic: Real Estate
  │     ├── Topic: Hiring
  │     └── Topic: Regulatory
  ├── Sub-project: London Office
  │     ├── Topic: Real Estate
  │     └── Topic: Visa Sponsorship
  └── Sub-project: Infrastructure
        ├── Topic: Cloud Migration
        └── Topic: Security Audit
```

### 8.4 The Optional Nature of the Hierarchy

The hierarchy is a tool, not a requirement:

| Entity        | Must belong to a parent?             | Can exist independently?                                                  |
| ------------- | ------------------------------------ | ------------------------------------------------------------------------- |
| Communication | No — can be unassigned               | Yes — marketing emails, unknown senders, one-offs                         |
| Conversation  | No — doesn't need a topic or project | Yes — an ongoing exchange with a colleague that isn't part of any project |
| Topic         | Yes — must belong to a project       | No — topics exist within projects                                         |
| Project       | No — top-level entity                | Yes — always independent                                                  |

---

## 9. Multi-Channel Communication Types

### 9.1 Email

The most structured and automatically captured communication type.

**Characteristics:**

- Rich content (text + HTML)
- Native threading from providers (Gmail, Outlook, IMAP headers)
- Heavy parsing needed (quotes, signatures, boilerplate)
- Automatic sync via provider APIs
- Multiple accounts supported per user

**Processing pipeline:** See Sections 13-15 for detailed email provider integration, sync pipeline, and parsing requirements.

### 9.2 SMS

Short text messages between phone numbers.

**Characteristics:**

- Very short content (typically 1-50 words)
- No native threading — flat stream between participants
- Minimal parsing needed
- Contact resolution via phone number (requires Contact Intelligence system)
- Automatic sync via phone integration or SMS provider API

**Conversation model:**

- Default: All SMS between the same participant set forms one participant-based conversation.
- User-driven: Specific messages can be assigned to topic-specific conversations.
- The system cannot automatically determine which conversation an SMS belongs to beyond the participant match — it relies on user assignment for topic-level organization.

### 9.3 Phone Calls (Recorded)

Phone calls with audio recordings captured via VoIP integration.

**Characteristics:**

- Recording stored as attachment
- Transcript generated via speech-to-text becomes the communication content
- A single transcribed call is processed like a long text communication — the transcript can be summarized by AI
- Metadata auto-captured: participants, timestamp, duration
- Contact resolution via phone number

### 9.4 Phone Calls (Unrecorded)

Phone calls without recordings — the user logs the interaction manually.

**Characteristics:**

- User enters: date, time, duration, participants, and notes
- This is functionally a **Note** communication type — the user is the content source
- The note captures key points, decisions, and action items from the call
- Entered via the CRM UI (or potentially via voice-to-text dictation)

### 9.5 Video Meetings (Recorded)

Video meetings with recordings captured via meeting platform integration (Zoom, Teams, etc.).

**Characteristics:**

- Recording stored as attachment
- Transcript generated via speech-to-text becomes the communication content
- Metadata auto-captured: participants, timestamp, duration
- Calendar event may provide additional context (meeting title, agenda)

### 9.6 Video Meetings (Unrecorded)

Same as unrecorded phone calls — user logs manually as a Note.

### 9.7 In-Person Meetings

Face-to-face meetings logged manually by the user.

**Characteristics:**

- User enters: date, time, attendees, location (optional), and notes
- Functionally a Note — user is the content source
- May be triggered by a calendar event (calendar integration creates placeholder, user adds notes after)
- Attachments: photos of whiteboards, signed documents, etc.

### 9.8 Notes (General)

A catch-all for any user-entered communication that doesn't fit another category. Also serves as the entry point for unrecorded calls and in-person meetings.

**A Note is not a separate concept — it is a Communication where the user is the content source.** It has the same fields as any other communication: timestamp, participants, content, channel, and optional attachments.

---

## 10. Communication Segmentation & Cross-Conversation References

### 10.1 The Problem

A single communication may address multiple topics. An email might say: "Attached is the contract you asked about. Also, are we still on for the team offsite planning?" — that's two topics, potentially two conversations.

### 10.2 The Solution: Split/Reference Model

The system uses a combined split and reference model:

**Primary assignment (automatic):**

- Each communication is automatically assigned to its primary conversation (via email thread ID, participant matching, or AI classification).
- The full communication lives in the primary conversation.

**Segment creation (user-driven):**

- When a user identifies that a communication spans two conversations, they select a portion of the text.
- They invoke an "Assign selected to different conversation" action.
- This creates a **segment** — the selected text assigned to the target conversation.
- The original communication now has references in both conversations.

**What the user sees:**

- In the primary conversation: the full communication, with the segmented portion highlighted or annotated.
- In the secondary conversation: the segment (selected text), with a link back to the full original communication.

**What is preserved:**

- The original communication is never modified or moved — it stays in its primary conversation in full.
- The segment is an additional reference, not a copy.
- Both conversations show contextually relevant content.

### 10.3 Future: AI-Assisted Segmentation

In a future iteration, the AI could analyze communications at the paragraph level and suggest segments when it detects that a communication addresses multiple conversations or topics. This would be presented as a suggestion for user confirmation, not an automatic action.

This capability is deferred to a separate discussion and will be documented in the **AI Learning & Classification PRD**.

---

## 11. AI Intelligence Layer

### 11.1 AI Roles

The AI serves three distinct functions in the conversation system:

#### Role 1: Classify & Route

For every incoming communication, the AI attempts to determine:

- **Which conversation does this belong to?** (existing conversation, or create a new one?)
- **Which topic does this conversation belong to?** (existing topic, or suggest a new one?)
- **Confidence score** for each assignment

High-confidence assignments happen silently. Low-confidence assignments are flagged for user review.

#### Role 2: Summarize

For communications and conversations with substantive content:

- **Communication-level summary** — For long communications only (lengthy emails, call transcripts, extended SMS exchanges). Short communications (a 4-word SMS, a brief note) are not summarized — the content IS the summary.
- **Conversation-level summary** — Synthesizes across all communications in the conversation, regardless of channel. Updated when new communications arrive. Produces a 2-4 sentence narrative of the conversation's current state.

#### Role 3: Extract Intelligence

At the conversation level:

- **Status classification** — OPEN (unresolved items), CLOSED (resolved), UNCERTAIN (insufficient context). Biased toward OPEN for multi-message exchanges between known contacts.
- **Action items** — Specific tasks mentioned in the conversation, with identification of who is responsible and any deadlines.
- **Key topics** — 2-5 short topic phrases, normalized for cross-conversation aggregation.
- **Sentiment score** (future) — Emotional tone tracking with per-communication trends.

### 11.2 The Review Workflow

Auto-organization is only useful if users can efficiently review and correct it. The system presents:

> "14 new communications since yesterday. 11 auto-assigned (review). 3 unassigned (needs your input)."

The review workflow allows users to:

- See all auto-assignments with confidence indicators
- Accept or correct conversation assignment with minimal clicks
- Accept or correct topic/project assignment
- Identify unknown contacts
- Create new conversations, topics, or projects as needed

The UI must be **extremely efficient** for this workflow — it is a daily activity that must take seconds, not minutes.

### 11.3 Learning from User Corrections

**The system learns from every user correction to improve future auto-assignment.**

When a user corrects an assignment (moves a communication to a different conversation, reassigns a topic, etc.), that correction becomes a training signal. Over time, the system should:

- Recognize patterns specific to each user's organizational preferences
- Learn contact-specific routing (e.g., "emails from Bob about invoices go to Accounting")
- Improve confidence thresholds based on correction rates
- Apply organizational learning across team members where appropriate

**The details of how learning is implemented — prompt-based context, embedding similarity, fine-tuning, or hybrid approaches — are defined in the AI Learning & Classification PRD (see Section 25: Related PRDs).** This PRD establishes the product requirement: the system learns from corrections and improves over time.

### 11.4 Summarization Thresholds

Not all communications warrant AI summarization:

| Content Length                                 | Summarize? | Rationale                                           |
| ---------------------------------------------- | ---------- | --------------------------------------------------- |
| <50 words (e.g., short SMS, brief note)        | No         | The content itself is already concise enough        |
| 50-200 words (e.g., typical email)             | Optional   | May benefit from summary in conversation context    |
| >200 words (e.g., long email, call transcript) | Yes        | Substantial content that benefits from distillation |

Conversation-level summaries are always generated when the conversation has sufficient total content, regardless of individual communication lengths.

### 11.5 Multi-Channel Formatting for AI

When the AI processes a conversation for summarization, the prompt includes channel markers so the AI understands the communication type:

```
Subject: Lease Negotiation — Clause 5

[EMAIL] From: Bob Smith
Date: 2026-02-07 10:15

Contract draft attached. Please review clause 5 regarding liability caps.

---

[EMAIL] From: Me
Date: 2026-02-07 10:32

Two questions about clause 5: [...]

---

[SMS] From: Me → Bob Smith
Date: 2026-02-07 12:45

Hey, did you see my questions?

---

[SMS] From: Bob Smith
Date: 2026-02-07 13:02

Yes, checking with legal, will reply tonight

---

[PHONE] Participants: Me, Bob Smith
Date: 2026-02-07 15:00 (12 min)

[Transcript / Notes]: Discussed clause 5 revisions. Bob agreed to cap liability
at $500K. Will send revised language by EOD.

---

[EMAIL] From: Bob Smith
Date: 2026-02-07 18:30

Here's the revised clause 5 with the $500K liability cap we discussed.
```

### 11.6 Re-Summarization Triggers

Conversation summaries are automatically refreshed when:

- A new communication is added to the conversation (any channel).
- A user explicitly requests a refresh.
- A communication is reassigned to or from the conversation.

### 11.7 Error Handling

| Failure                    | Recovery                                                                              |
| -------------------------- | ------------------------------------------------------------------------------------- |
| AI API timeout             | Retry with exponential backoff (3 attempts); mark as pending                          |
| AI API rate limit          | Queue and retry after cooldown                                                        |
| Malformed AI response      | Return with error flag; log raw response                                              |
| AI API unavailable         | Conversations remain visible without summaries; queue for processing when API returns |
| Empty conversation content | Skip summarization; display "(no content to analyze)"                                 |

---

## 12. Contact Association & Identity Resolution

### 12.1 Design Principle

**Every communication participant must be resolved to a CRM contact.** The system actively works to identify all senders and recipients across all channels. Under no circumstance should a conversation be left with permanently unidentified contacts.

### 12.2 Integration with Contact Intelligence System

The Contact Intelligence system (defined in a separate PRD) is the **single source of truth** for identity resolution. The Conversations subsystem:

**Consumes from Contact Intelligence:**

- "This phone number belongs to Bob" → SMS messages route to Bob's conversations
- "This email address belongs to Bob" → Emails associate with the same contact as Bob's phone
- A unified contact record means communications across all channels are correctly attributed

**Contributes to Contact Intelligence:**

- A new email arrives from an unknown address → trigger identity resolution workflow
- An SMS comes from an unknown number → trigger identity resolution workflow
- A user creates a note about a meeting with "Sarah from Acme" → potential new contact signal
- Every communication with an unrecognized identifier is a **signal** fed back to the Contact Intelligence system

### 12.3 Identifier Types by Channel

| Channel             | Primary Identifier            | Resolution Method                       |
| ------------------- | ----------------------------- | --------------------------------------- |
| Email               | Email address                 | Direct lookup in contact database       |
| SMS                 | Phone number                  | Phone number lookup in contact database |
| Phone call (VoIP)   | Phone number                  | Phone number lookup                     |
| Phone call (manual) | User-specified                | User selects contact during entry       |
| Video meeting       | Platform display name + email | Email lookup; name matching as fallback |
| In-person meeting   | User-specified                | User selects contacts during entry      |

### 12.4 Pending Identification State

When a communication arrives with an unrecognized identifier:

1. Communication enters the system normally — it is **not blocked**.
2. The contact identifier enters **Pending Identification** state.
3. The Contact Intelligence system runs resolution:
   - Check existing contacts for alternate identifiers
   - Check user's contact book (Google Contacts, Outlook, phone)
   - OSINT lookup if enabled (third-party enrichment)
   - Pattern matching (same name, same company domain)
4. **If resolved automatically** → Contact linked; communication fully attributed.
5. **If not resolved** → User prompted to identify the contact:
   - Suggestions provided if partial matches exist
   - User can match to existing contact, create new contact, or mark as irrelevant

**Critical principle:** Pending identification does **not** block conversation assignment or documentation. The communication flows through the pipeline — it can be assigned to a conversation, summarized by AI, and displayed to users — while contact resolution proceeds in parallel. Eventually, the contact information is updated to provide the complete picture.

### 12.5 Cross-Channel Contact Unification

The Contact Intelligence system maintains a unified contact record that links all known identifiers:

```
Contact: Bob Smith (Acme Corp)
  ├── Email: bob.smith@acmecorp.com
  ├── Email: bob@gmail.com (personal)
  ├── Phone: +1-555-0100 (work)
  ├── Phone: +1-555-0199 (mobile)
  ├── Slack: @bsmith
  └── Zoom: "Bob S"
```

This means an email from `bob.smith@acmecorp.com` and an SMS from `+1-555-0199` are both recognized as Bob Smith — enabling the system to maintain cross-channel conversation continuity.

---

## 13. Email Provider Integration

### 13.1 Design Philosophy

CRMExtender uses **direct provider API integration** — no third-party email aggregation services (Nylas, Mailgun, etc.). This eliminates per-mailbox fees, reduces latency, and provides access to provider-native features (threading, push notifications).

Each provider is implemented as an **adapter** that normalizes email data to the common Communication schema. The rest of the pipeline is provider-agnostic.

### 13.2 Gmail (Tier 1 — Primary)

| Aspect                | Detail                                                                                               |
| --------------------- | ---------------------------------------------------------------------------------------------------- |
| **API**               | Gmail API v1 (RESTful) via `google-api-python-client`                                                |
| **Authentication**    | OAuth 2.0 (desktop flow for PoC, web flow for production)                                            |
| **Scopes**            | `gmail.readonly` (email access), `gmail.send` (future: outbound), `contacts.readonly` (contact sync) |
| **Threading**         | Native `threadId` — Gmail groups messages by subject and participants automatically                  |
| **Initial sync**      | `threads.list` with configurable query (default: `newer_than:90d`), paginated                        |
| **Incremental sync**  | `history.list` with `startHistoryId` — returns only changes since last sync                          |
| **Real-time updates** | Google Pub/Sub push notifications (production); polling via history API (PoC fallback)               |
| **Rate limits**       | 250 quota units/second per user; `threads.get` costs 10 units                                        |
| **Data available**    | Full MIME structure, headers, body (text + HTML), labels, attachments metadata                       |

**Gmail-specific considerations:**

- Gmail's `threadId` is highly reliable but occasionally groups unrelated messages with the same subject.
- Gmail wraps some email bodies inside `gmail_signature` divs, requiring a resilience check in the parser.
- Gmail's History API may return `historyId` gaps; the system must handle "404 historyId not found" by falling back to a date-based re-sync.

### 13.3 Microsoft Outlook / Exchange (Tier 2)

| Aspect                | Detail                                                         |
| --------------------- | -------------------------------------------------------------- |
| **API**               | Microsoft Graph API v1.0                                       |
| **Authentication**    | OAuth 2.0 via Microsoft Identity Platform (MSAL)               |
| **Scopes**            | `Mail.Read`, `Mail.Send` (future), `Contacts.Read`             |
| **Threading**         | Native `conversationId`                                        |
| **Initial sync**      | `/me/messages` with `$filter` on `receivedDateTime`, paginated |
| **Incremental sync**  | Delta queries (`/me/messages/delta`) returning a `deltaLink`   |
| **Real-time updates** | Webhook subscriptions (`/subscriptions`)                       |
| **Rate limits**       | 10,000 requests per 10 minutes per app per mailbox             |

**Outlook-specific considerations:**

- `div#appendonsend` separates composed content from quoted reply — content after it (siblings) must be removed.
- `div#divRplyFwdMsg` serves a similar separator function.
- Border-based separators (`border-top: solid #E1E1E1`) must be detected as cutoff points.
- Outlook's `conversationId` may group differently than Gmail's `threadId` for the same exchange.

### 13.4 IMAP (Tier 3 — Fallback)

| Aspect                | Detail                                                                         |
| --------------------- | ------------------------------------------------------------------------------ |
| **Protocol**          | IMAP4rev1 (RFC 3501) over TLS                                                  |
| **Authentication**    | Username/password or OAuth 2.0 (where supported)                               |
| **Threading**         | Reconstructed from RFC 5322 headers: `Message-ID`, `References`, `In-Reply-To` |
| **Initial sync**      | `FETCH` with UID range, scanning configured folders                            |
| **Incremental sync**  | `UIDVALIDITY` + last-synced UID                                                |
| **Real-time updates** | IMAP IDLE (RFC 2177) or polling (default: 5 min)                               |

**IMAP-specific considerations:**

- Thread reconstruction uses the JWZ threading algorithm from `Message-ID`, `References`, and `In-Reply-To` chains, with subject-line matching as fallback.
- `UIDVALIDITY` changes require a full re-sync of the folder.
- Sent mail must be explicitly synced from the Sent folder and merged with inbox threads.
- Connection pooling is essential for servers with strict connection limits.

### 13.5 Provider Adapter Architecture

All email providers normalize to the common Communication schema via an adapter layer responsible for:

1. **Authentication** — Provider-specific OAuth or credential flows
2. **Fetching** — Translating sync requests into provider API calls
3. **Normalization** — Converting provider responses to the common Communication schema
4. **Cursor management** — Tracking sync position in provider-specific format
5. **Error handling** — Translating provider errors into common error types

---

## 14. Email Sync Pipeline

### 14.1 Sync Modes

#### Initial Sync (First Connection)

- **Scope:** All emails matching the backfill query (configurable, default: 90 days)
- **Method:** Batch fetch, paginated
- **Performance target:** <5 minutes for a typical mailbox (5,000 messages)
- **Idempotency:** Safe to restart; deduplication by provider message ID

#### Incremental Sync (Ongoing)

- **Scope:** Changes since last sync cursor
- **Method:** Provider-specific change detection (Gmail History API, Outlook Delta, IMAP UID comparison)
- **Performance target:** <5 seconds for typical changes (0-20 new messages)
- **Frequency:** Webhook/push (Gmail, Outlook) or polling (IMAP, default: 5 min)

#### Manual Sync (User-Triggered)

- Forces an immediate incremental sync regardless of schedule.

### 14.2 Sync Cursor Mechanics

| Provider | Cursor Type           | Format                                       |
| -------- | --------------------- | -------------------------------------------- |
| Gmail    | `historyId`           | Numeric string — monotonically increasing    |
| Outlook  | `deltaLink`           | URL string — opaque token from delta queries |
| IMAP     | `UIDVALIDITY:lastUID` | Compound string — detects mailbox rebuilds   |

**Cursor lifecycle:** NULL → set on initial sync completion → advanced on each incremental sync → recorded in audit log.

**Failure handling:** Invalid cursor (expired historyId, UIDVALIDITY change) → date-based re-sync from last known timestamp.

### 14.3 Sync Reliability

| Failure Scenario               | Recovery                                                    |
| ------------------------------ | ----------------------------------------------------------- |
| Provider API timeout           | Exponential backoff retry (3 attempts)                      |
| Provider rate limit (HTTP 429) | Respect `Retry-After` header                                |
| Invalid sync cursor            | Date-based re-sync                                          |
| Partial batch failure          | Skip failed messages, log for retry                         |
| Network interruption           | Retry with backoff; queue for next sync                     |
| Token expiration (HTTP 401)    | Auto-refresh; re-authenticate if refresh fails              |
| Duplicate messages             | INSERT OR IGNORE (UNIQUE constraint on provider message ID) |
| Message deletion at provider   | Delete DB row; recompute conversation metadata              |

### 14.4 Sync Audit Trail

Every sync operation is logged: type, start/end timestamps, message counts (fetched, stored, skipped), conversations created/updated, cursor before/after, status, and error details.

---

## 15. Email Parsing & Content Extraction

### 15.1 The Problem

Raw email bodies contain noise that obscures the author's original message: quoted replies, forwarded blocks, signatures, disclaimers, mobile footers, marketing remnants, and boilerplate. This noise must be removed before content is displayed to users or processed by AI.

### 15.2 Architecture: Dual-Track Pipeline

```
Input: body_html + body_plain
          │
          ├── body_html available?
          │        │
          │      YES → HTML Track ──→ result empty? ──→ YES ──┐
          │        │                                           │
          │        │                  result non-empty → DONE  │
          │        │                                           │
          │      NO ──────────────────────────────────────────┤
          │                                                    │
          └────────────────── Plain-Text Track ◄──────────────┘
                                     │
                                   DONE
```

### 15.3 HTML Track (Preferred)

**Phase 1 — Structural HTML removal** using quotequail + BeautifulSoup:

| Selector                                             | Client                  | Content Type            |
| ---------------------------------------------------- | ----------------------- | ----------------------- |
| `div.gmail_quote`                                    | Gmail                   | Quoted reply            |
| `div.gmail_attr`                                     | Gmail                   | Attribution line        |
| `[data-smartmail=gmail_signature]`                   | Gmail                   | Signature               |
| `div.gmail_signature`                                | Gmail                   | Signature               |
| `div.yahoo_quoted`                                   | Yahoo                   | Quoted reply            |
| `blockquote[type=cite]`                              | Apple Mail, Thunderbird | Quoted reply            |
| `div#appendonsend` + siblings                        | Outlook                 | Reply separator         |
| `div#divRplyFwdMsg` + siblings                       | Outlook                 | Reply/forward separator |
| `div#Signature`                                      | Outlook                 | Signature               |
| Elements with `border-top: solid #E1E1E1` + siblings | Outlook                 | Visual separator        |
| `div#ms-outlook-mobile-signature`                    | Outlook Mobile          | Mobile signature        |

**Signature resilience check:** If signature removal empties the result (Gmail sometimes wraps bodies in `gmail_signature` divs), re-parse without signature removal.

**Unsubscribe footer removal:** Elements with IDs matching `footerUnsubscribe*` and elements containing "unsubscribe" text plus following siblings.

**Phase 2 — Text-level cleanup** (shared with plain-text track, see below).

### 15.4 Plain-Text Track (Fallback)

1. **Library-based quote detection** — `mail-parser-reply` detects `>` prefixed blocks. Falls back to regex on failure.
2. **Pattern-based removal:**
   - `-- Forwarded message --` → truncate
   - 10+ underscores/dashes (Outlook separator) → truncate
   - `From:/Sent:/To:` block → truncate
   - `On <date> <person> wrote:` → truncate

### 15.5 Shared Text-Level Cleanup (Both Tracks)

Applied in order after track-specific processing:

1. **Mobile & notification signatures** — "Sent from my iPhone", "Get Outlook for iOS", notification-only address disclaimers. Remove line and everything after.

2. **Confidentiality notices** — "This message contains confidential information" and variations. Truncate from first match.

3. **Environmental messages** — "Please consider the environment before printing." Truncate.

4. **Separator-based signature stripping** (three-pass chain):
   
   - **Pass 1 — Dash-dash (`--`):** Truncate if content after is <500 chars, ≤10 lines, and contains signature markers.
   - **Pass 2 — Underscore (`__`):** Truncate if content after is <1,500 chars, ≤25 lines, and contains signature markers.
   - **Pass 3 — Dash-dash cleanup:** Re-run Pass 1 to catch separators exposed by Pass 2.

5. **Valediction-based signature detection** — "Best regards", "Thanks", "Sincerely", etc. followed by name/contact lines. Validated to ensure remaining content is signature-like, not prose. Truncate.

6. **Standalone signature detection** — All-caps name followed within 5 lines by title/phone/email/URL. Only on short trailing blocks. Truncate.

7. **Promotional content** — Social media links, vCards, award citations, marketing taglines. Remove.

8. **Unsubscribe footers** — Lines containing "unsubscribe." Truncate.

9. **Line unwrapping** — Rejoin hard-wrapped lines (70-76 char) while preserving intentional breaks.

10. **Whitespace normalization** — Collapse 3+ newlines to 2. Trim.

### 15.6 Parsing Quality Targets

| Metric                         | Target          | Current (PoC)                      |
| ------------------------------ | --------------- | ---------------------------------- |
| Emails improved after cleaning | >90%            | 91.2% (3,752 production emails)    |
| Average character reduction    | >50%            | 58%                                |
| False-positive empty results   | 0%              | 0%                                 |
| Test coverage                  | >100 test cases | 95 tests (60 plain-text + 35 HTML) |
| Processing speed               | <2ms per email  | ~1.3ms per email                   |

### 15.7 Provider-Specific Parsing Challenges

| Provider       | Challenge                                      | Mitigation                                    |
| -------------- | ---------------------------------------------- | --------------------------------------------- |
| Gmail          | Body wrapped in `gmail_signature` div          | Resilience check: re-parse without signatures |
| Outlook        | `#appendonsend` content in siblings            | Remove element AND all following siblings     |
| Outlook        | Border separator (`border-top: solid #E1E1E1`) | Regex on inline style                         |
| Apple Mail     | Deep `blockquote` nesting                      | quotequail + CSS selector                     |
| IMAP (generic) | No structural cues; plain-text only            | Full plain-text pipeline                      |
| All            | Signatures without separators or valedictions  | Standalone detection heuristics               |

---

## 16. Triage & Intelligent Filtering

### 16.1 Purpose

Not every communication warrants AI analysis. Automated notifications, marketing emails, and messages from unknown sources consume AI resources without providing relationship intelligence.

### 16.2 Filter Layers

#### Layer 1: Heuristic Junk Detection

| Filter                | What It Detects          | Examples                                                           |
| --------------------- | ------------------------ | ------------------------------------------------------------------ |
| **Automated sender**  | Known automated patterns | `noreply@`, `notification@`, `billing@`, `alerts@` (16 patterns)   |
| **Automated subject** | Known automated patterns | "out of office", "automatic reply", "password reset" (12 patterns) |
| **Marketing content** | Marketing language       | Body contains "unsubscribe"                                        |

#### Layer 2: Known-Contact Gate

At least one participant (excluding the account owner) must be a known CRM contact. Communications where all participants are unknown are filtered as `no_known_contacts`.

### 16.3 Triage Transparency

Filtered communications are **not deleted** — they remain with their filter reason visible. Users can override filter decisions and adjust sensitivity.

### 16.4 Future Enhancements

- ML-based classification learning from user overrides
- User-configurable allowlists/blocklists
- Category-based rules using provider labels (Gmail categories, Outlook Focused/Other)
- Volume-based detection for high-frequency automated senders

---

## 17. Views & Dashboards

### 17.1 Design Philosophy

Rather than a prescriptive dashboard, the system provides **powerful, user-defined views** — saved queries against the data model that show users exactly the information they need.

### 17.2 Views as Saved Queries

A view is essentially any query the user might want to execute against the system. The UI provides a visual query builder (not raw SQL) that maps to the underlying data model, with support for:

- **Filters** — By project, topic, conversation, contact, company, channel, status, date range, triage result, AI status, etc.
- **Sorting** — By timestamp, activity, participant, status, etc.
- **Grouping** — By project, topic, contact, channel, status, etc.
- **Columns** — User chooses which fields to display

**Example views a user might create:**

| View Name                    | Query                                                                            |
| ---------------------------- | -------------------------------------------------------------------------------- |
| "My Open Action Items"       | All action items across all conversations where AI status = Open, sorted by date |
| "Stale Client Conversations" | Conversations with no activity in 14+ days, grouped by contact                   |
| "Project X Status"           | All conversations under Project X, grouped by topic, sorted by last activity     |
| "Unassigned This Week"       | Communications from the last 7 days with no conversation assignment              |
| "All Comms with Bob"         | Communications where Bob is a participant, across all channels, chronological    |
| "Pending Reviews"            | Auto-assigned communications with low confidence scores                          |

### 17.3 Shareable Views

Views can be shared with team members. A manager creates a "Team Open Action Items" view, and everyone on the team can use it. Shared views use the viewer's data permissions — sharing the view definition doesn't grant access to data the viewer wouldn't otherwise see.

### 17.4 Views as the Foundation for Alerts

Views and alerts share the same underlying architecture. An alert is a view with a trigger attached (see Section 18).

---

## 18. User-Defined Alerts

### 18.1 Design Philosophy

**No default alerts.** The system sends zero notifications unless the user explicitly creates them. Users define exactly the alerts they want — no more, no less.

### 18.2 Alert Architecture

An alert is a **saved query** (view) with a **trigger**, **frequency**, and **delivery method**:

```
Saved Query (filter criteria against the data model)
  ├── Rendered as a View (pull — user opens it on demand)
  └── Attached as an Alert (push — system notifies when results change)
        ├── Frequency: Immediate, Hourly, Daily, Weekly
        ├── Aggregation: Individual (one alert per result) or Batched (digest)
        └── Delivery: In-app notification, Push notification, Email, SMS
```

### 18.3 Alert Examples

| Alert                                    | Query                                                                       | Frequency | Delivery          |
| ---------------------------------------- | --------------------------------------------------------------------------- | --------- | ----------------- |
| "New communication from VIP contacts"    | Communications from contacts tagged "VIP"                                   | Immediate | Push notification |
| "Conversations going stale on Project X" | Conversations under Project X with no activity in 7+ days                   | Daily     | Email digest      |
| "Unassigned items to review"             | Communications with no conversation assignment or low-confidence assignment | Daily     | In-app            |
| "Any change to the Acme Deal"            | Any new communication in any conversation under the Acme Deal project       | Immediate | Push notification |
| "Weekly action item summary"             | All open action items across all conversations                              | Weekly    | Email digest      |

### 18.4 Alert Frequency & Aggregation

When a user sets an alert on a broad query (e.g., "any change to Project X") that triggers frequently, the **frequency and aggregation settings** prevent alert fatigue:

- **Immediate + Individual:** Every matching event triggers a notification. For high-priority, low-frequency alerts.
- **Hourly/Daily + Batched:** Matching events are collected and delivered as a digest. For high-frequency monitoring where real-time isn't needed.
- **Weekly + Batched:** Summary report. For oversight and review patterns.

---

## 19. Conversation Lifecycle & Status Management

### 19.1 Three Status Dimensions

#### System Status (`status`)

Time-based, managed automatically:

| Value    | Trigger                                                    |
| -------- | ---------------------------------------------------------- |
| `active` | New communication within the activity window               |
| `stale`  | No activity for N days (configurable, default: 14)         |
| `closed` | No activity for M days (default: 30), or user manual close |

**Transitions:** `active` ↔ `stale` ↔ `closed` — any state reopens to `active` when a new communication arrives.

#### AI Status (`ai_status`)

Semantic, from AI analysis:

| Value       | Meaning                                             |
| ----------- | --------------------------------------------------- |
| `open`      | Unresolved items, pending tasks, ongoing discussion |
| `closed`    | Definitively resolved or finished                   |
| `uncertain` | Insufficient context                                |

**Bias:** Toward OPEN for multi-message exchanges. Casual sign-offs don't close a conversation.

#### Triage Status (`triage_result`)

Whether the communication was filtered: NULL = passed, non-NULL = filtered with reason.

### 19.2 Status Independence

The three dimensions are independent and complementary:

- **System: active** + **AI: closed** → Recent messages, but the topic was resolved
- **System: stale** + **AI: open** → No recent activity, but the last message asked an unanswered question
- **Triage** is orthogonal — determines whether AI analysis happens at all

---

## 20. Multi-Account Management

### 20.1 Account Operations

| Operation                    | Behavior                                                             |
| ---------------------------- | -------------------------------------------------------------------- |
| **Connect**                  | OAuth or credential entry → account registered → initial sync begins |
| **Disconnect (retain data)** | Stop syncing, revoke access, keep existing data                      |
| **Disconnect (delete data)** | Stop syncing, revoke access, cascade-delete all associated data      |
| **Re-authenticate**          | Refresh credentials without affecting data                           |
| **Pause/Resume sync**        | Temporarily stop/resume without affecting credentials or data        |

### 20.2 Unified Feed

Multiple accounts produce a single, chronologically sorted communication/conversation feed. Each item is tagged with its source account.

### 20.3 Cross-Account Considerations

- Same real-world thread via two accounts currently creates separate conversation records.
- Future: cross-account merge detection via subject + participants + dates.
- Contact resolution is unified across accounts via the Contact Intelligence system.

---

## 21. Search & Discovery

### 21.1 Search Capabilities

| Search Type                    | Scope                                               |
| ------------------------------ | --------------------------------------------------- |
| Full-text communication search | Body text, subjects across all channels             |
| Conversation search            | AI summaries, topics, action items                  |
| Contact-scoped                 | "All communications with Alice" across all channels |
| Project/topic browsing         | Navigate the hierarchy                              |
| Channel filtering              | "Only emails" or "Only SMS"                         |
| Status filtering               | Open, Closed, Uncertain, Stale                      |
| Date-range filtering           | Any time period                                     |
| Account filtering              | Specific source accounts                            |

### 21.2 Search Indexing

Communications and conversations are indexed asynchronously when created, updated, or summarized. Search results may lag by a few seconds.

---

## 22. Storage & Data Retention

### 22.1 What Gets Stored

| Data                                 | Format                   | Retention                          |
| ------------------------------------ | ------------------------ | ---------------------------------- |
| Communication content (cleaned text) | Plain text               | Configurable (default: indefinite) |
| Email raw HTML                       | Original HTML            | Same as content                    |
| Call/video transcripts               | Plain text               | Same as content                    |
| Attachments (files)                  | Binary in object storage | Configurable (default: on demand)  |
| Attachment metadata                  | Structured data          | Same as content                    |
| AI summaries/intelligence            | Text fields              | Regenerated on demand              |
| Sync cursors                         | Per-account              | Overwritten each sync              |
| Sync audit log                       | Structured data          | Configurable (default: 90 days)    |

### 22.2 Storage Estimates

| Data Type                    | Per Communication        | 10,000 Communications  |
| ---------------------------- | ------------------------ | ---------------------- |
| Cleaned text content         | ~2 KB avg                | ~20 MB                 |
| Raw HTML (email only)        | ~8 KB avg                | ~80 MB                 |
| Metadata + indexes           | ~1 KB avg                | ~10 MB                 |
| AI intelligence              | ~0.5 KB per conversation | ~2.5 MB (5,000 convos) |
| Audio recordings (if stored) | ~1 MB/min                | Highly variable        |

---

## 23. Privacy, Security & Compliance

### 23.1 Data Protection

- **Minimum necessary access** — Read-only scopes for all providers until send capability is needed.
- **Encrypted at rest and in transit** — TLS 1.2+ for all API calls; database encryption in production.
- **Credential isolation** — OAuth tokens and IMAP passwords stored separately, never in logs.
- **Tenant isolation** — Schema-per-tenant in PostgreSQL.

### 23.2 Compliance

| Requirement                            | How Addressed                                                   |
| -------------------------------------- | --------------------------------------------------------------- |
| **GDPR — Access/Deletion/Portability** | Full export via API; cascade deletion; standard export formats  |
| **GDPR — Consent**                     | Account connection is explicit consent; AI processing disclosed |
| **SOC 2 — Audit trails**               | Sync logs, event sourcing, modification tracking                |
| **CCPA**                               | Same as GDPR; no sale of communication data                     |

### 23.3 AI Data Handling

- Only cleaned, truncated content sent to AI — not raw HTML, attachments, or full threads.
- AI responses stored in CRM, not retained by AI provider.
- Users informed that content is processed by an external AI service during account connection.

---

## 24. Phasing & Roadmap

### Phase 1: Email Foundation (Current PoC → Production)

**Goal:** Graduate Gmail PoC to production; establish the hierarchy data model.

- Gmail provider adapter (production-hardened)
- Communication & Conversation data model (replacing current flat model)
- Project / Sub-project / Topic hierarchy (CRUD operations)
- Email parsing pipeline (unchanged — already production-tested)
- Triage filtering
- AI summarization adapted for new conversation model
- Manual communication entry (Notes for calls and meetings)
- Basic views and filtering
- Conversation API endpoints

### Phase 2: Outlook + Multi-Channel Foundation

**Goal:** Second email provider; SMS integration; cross-channel conversations.

- Outlook provider adapter (Microsoft Graph API)
- SMS integration (provider TBD)
- Cross-channel conversation timeline (email + SMS sequenced by timestamp)
- AI classification and routing for conversation assignment
- User review workflow for auto-assignments
- Outlook-specific parsing patterns
- Expanded test suite (target: 120+ tests)

### Phase 3: IMAP + Intelligence + Recorded Communications

**Goal:** Universal email support; recorded call/video integration; learning system.

- IMAP provider adapter with JWZ thread reconstruction
- VoIP integration for recorded phone calls (transcription pipeline)
- Video meeting integration (Zoom/Teams transcript capture)
- Communication segmentation (split/reference model)
- AI learning from user corrections (initial implementation)
- Sentiment analysis
- Automated lifecycle state transitions (stale/closed)

### Phase 4: Advanced Features

**Goal:** Full platform-level conversation intelligence.

- Cross-account conversation deduplication
- Calendar ↔ conversation linking
- Advanced views and shareable views
- User-defined alerts
- Conversation analytics dashboard
- Email sending from CRM (elevated OAuth scopes)
- Communication templates
- AI-assisted paragraph-level segmentation

---

## 25. Related PRDs

This PRD defines the conversation management system. Several aspects are covered by separate, dedicated PRDs:

| PRD                              | Scope                                                                                                                                       | Relationship                                                                    |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **AI Learning & Classification** | How the system learns from user corrections; classification algorithms; embedding/similarity approaches; model training; confidence scoring | This PRD establishes that the system learns; the AI PRD defines how             |
| **Contact Intelligence**         | Identity resolution across channels; contact enrichment; OSINT; cross-channel contact unification                                           | This PRD consumes contact resolution and contributes unknown-identifier signals |
| **Permissions & Sharing**        | Team access controls; who can see which conversations; role-based permissions; shared vs. private data                                      | This PRD defers all permission concerns to the Permissions PRD                  |
| **CRMExtender PRD v1.1**         | Full platform architecture; event sourcing; Neo4j relationships; pipeline/deals; offline sync                                               | This PRD is a subsystem of the broader platform                                 |

---

## 26. Dependencies & Risks

### Technical Dependencies

| Dependency                     | Risk Level | Mitigation                                               |
| ------------------------------ | ---------- | -------------------------------------------------------- |
| Gmail API                      | Low        | Stable, well-documented; quota management                |
| Microsoft Graph API            | Low        | Stable; MSAL handles auth                                |
| Anthropic Claude API           | Medium     | Abstract model selection; pricing changes possible       |
| quotequail / mail-parser-reply | Medium     | Niche libraries; could fork or internalize               |
| SMS provider integration       | Medium     | Provider TBD; adapter pattern isolates changes           |
| Speech-to-text service         | Medium     | Multiple options (Whisper, Google, AWS); adapter pattern |

### Product Risks

| Risk                                    | Probability | Impact                                             | Mitigation                                                                   |
| --------------------------------------- | ----------- | -------------------------------------------------- | ---------------------------------------------------------------------------- |
| AI auto-assignment accuracy too low     | Medium      | Users lose trust, stop using hierarchy             | Conservative confidence thresholds; excellent review UX; rapid learning loop |
| AI costs at scale                       | Medium      | Expensive for high-volume tenants                  | Model tiering; summarization thresholds; configurable processing             |
| Cross-channel stitching is unreliable   | Medium      | Conversations fragmented across channels           | Participant-based defaults; easy manual assignment; AI improvement over time |
| Email parsing accuracy for new patterns | Medium      | Unrecognized quote/signature patterns leak through | Continuous monitoring; user feedback; expandable pattern library             |
| SMS integration complexity              | Medium      | Fragmented provider landscape                      | Start with one integration; adapter pattern for flexibility                  |
| IMAP threading accuracy                 | High        | Inherently less reliable than provider-native      | JWZ algorithm + subject fallback; manual correction; confidence indicators   |
| Privacy concerns about AI processing    | Medium      | User resistance                                    | Clear disclosure; data minimization; opt-out capability                      |

---

## 27. Open Questions

1. **SMS provider selection** — Which SMS integration to pursue first? Twilio, native phone sync, or platform-specific (iMessage, Google Messages)?

2. **Speech-to-text service** — Which transcription service for recorded calls and video? Self-hosted (Whisper) vs. cloud (Google, AWS)? Cost and accuracy tradeoffs.

3. **Slack/Teams integration model** — These tools have their own hierarchy (workspaces/teams → channels → threads). How should their structure map to our Projects → Topics → Conversations model? Deferred to separate discussion.

4. **Calendar-conversation linking** — Should calendar events auto-create placeholder communications? What's the heuristic for matching meetings to conversations?

5. **Cross-account conversation merging** — When two accounts participate in the same real-world conversation, auto-merge or keep separate? Confidence threshold?

6. **Sub-project depth limit** — Should recursive sub-project nesting have a maximum depth? Unlimited nesting could create organizational complexity.

7. **Attachment storage model** — Store all attachments (high storage cost) vs. on-demand download from provider (requires continued provider access)?

8. **Real-time sync infrastructure** — Gmail Pub/Sub and Outlook webhooks need publicly accessible callbacks. Cloud function, dedicated endpoint, or message queue?

9. **Email sending from CRM** — Should the system support sending (requires elevated OAuth scopes)? Adds value but significant complexity and security surface.

10. **Conversation merge/split operations** — When a user merges two conversations or splits one, what happens to AI summaries, action items, and topic assignments? Re-process entirely or patch incrementally?

11. **Shared mailbox support** — How should team/shared mailboxes be handled? Each user connects independently (duplicating data), or shared connection model?

12. **Opt-out granularity** — Can users exclude specific conversations, contacts, or entire channels from AI processing? What does "exclude" mean operationally?

---

## 28. Glossary

| Term                       | Definition                                                                                                                                                                  |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Communication**          | An individual interaction — a single email, SMS, phone call, video meeting, in-person meeting, or user-entered note. The atomic unit of the system.                         |
| **Conversation**           | A logical grouping of related communications between specific participants about a specific subject. Can span multiple channels.                                            |
| **Topic**                  | An organizational grouping within a project that represents a distinct subject area. Contains one or more conversations with different participants about the same subject. |
| **Project**                | The highest-level organizational container representing a business initiative, engagement, or deal. Contains topics and sub-projects.                                       |
| **Sub-project**            | A child project nested within a parent project. Same structure as a project.                                                                                                |
| **Segment**                | A portion of a communication assigned to a different conversation than the primary. Created by user selection.                                                              |
| **Channel**                | The medium of a communication: email, SMS, phone, video, in-person, or note.                                                                                                |
| **Provider adapter**       | A module normalizing a specific source's API to the common Communication schema.                                                                                            |
| **Sync cursor**            | An opaque marker tracking the system's sync position in a provider's data stream.                                                                                           |
| **Triage**                 | Classifying communications as real human interaction vs. automated/marketing noise.                                                                                         |
| **Content extraction**     | Removing quoted replies, signatures, and boilerplate from email bodies.                                                                                                     |
| **Dual-track pipeline**    | Email parsing architecture: HTML-based structural removal with plain-text regex fallback.                                                                                   |
| **Resilience check**       | Re-parsing without signature removal if the HTML track produces an empty result.                                                                                            |
| **Valediction**            | A closing phrase (e.g., "Best regards") used as a signature detection anchor.                                                                                               |
| **JWZ threading**          | Algorithm reconstructing conversation threads from RFC 5322 message headers.                                                                                                |
| **Known-contact gate**     | Triage filter requiring at least one recognized CRM contact among participants.                                                                                             |
| **Pending Identification** | State of an unrecognized contact identifier that is undergoing resolution. Does not block communication processing.                                                         |
| **View**                   | A saved query against the data model, defining a user-customized lens into their data. Can be shared with team members.                                                     |
| **Alert**                  | A view with an attached trigger, frequency, and delivery method — pushes notifications when results change.                                                                 |
| **Split/Reference model**  | The approach for handling communications that span multiple conversations: primary assignment + segments with cross-references.                                             |
| **Auto-organization**      | AI-driven classification and routing of communications into conversations, topics, and projects, with user review and correction.                                           |

---

*This document is a living specification. As implementation progresses and as related PRDs (AI Learning & Classification, Contact Intelligence, Permissions & Sharing) are developed, sections will be updated to reflect design decisions, scope adjustments, and lessons learned.*
