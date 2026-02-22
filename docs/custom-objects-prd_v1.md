# Product Requirements Document: Custom Objects

## CRMExtender â€” Object Type Framework, Field Registry & Relation Model

**Version:** 1.0
**Date:** 2026-02-17
**Status:** Draft
**Parent Document:** [CRMExtender PRD v1.1](PRD.md)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Personas & Stories](#4-user-personas--stories)
5. [Core Concepts & Terminology](#5-core-concepts--terminology)
6. [Object Type Definition Model](#6-object-type-definition-model)
7. [Universal Fields](#7-universal-fields)
8. [Field Registry](#8-field-registry)
9. [Field Type System](#9-field-type-system)
10. [Field Type Conversion Matrix](#10-field-type-conversion-matrix)
11. [Field Groups](#11-field-groups)
12. [Field Validation](#12-field-validation)
13. [Select & Multi-Select Options](#13-select--multi-select-options)
14. [Relation Types](#14-relation-types)
15. [Relation Metadata](#15-relation-metadata)
16. [Neo4j Graph Sync](#16-neo4j-graph-sync)
17. [Physical Storage Architecture](#17-physical-storage-architecture)
18. [DDL Management System](#18-ddl-management-system)
19. [Event Sourcing](#19-event-sourcing)
20. [Object Type Lifecycle](#20-object-type-lifecycle)
21. [Field Lifecycle](#21-field-lifecycle)
22. [System Entity Specialization](#22-system-entity-specialization)
23. [API Design](#23-api-design)
24. [Schema-Per-Tenant Architecture](#24-schema-per-tenant-architecture)
25. [Phasing & Roadmap](#25-phasing--roadmap)
26. [Cross-PRD Reconciliation](#26-cross-prd-reconciliation)
27. [Dependencies & Related PRDs](#27-dependencies--related-prds)
28. [Open Questions](#28-open-questions)
29. [Glossary](#29-glossary)

---

## 1. Executive Summary

The Custom Objects framework is the entity model foundation of CRMExtender. It defines what things exist in the system â€” Contacts, Conversations, Companies, and any user-created entity type â€” and what attributes they have. Every other subsystem depends on this: the Views system renders entity fields, the Data Sources query engine joins across entity types, the Communication subsystem resolves participants to entity records, and the relationship intelligence layer models graph connections between entities.

This PRD establishes a **Unified Object Model** where system entities and user-created entities are instances of the same framework. A Contact is not a special snowflake with hand-crafted storage â€” it is an object type that happens to be pre-installed, with core fields that are protected from deletion, and specialized behaviors (identity resolution, enrichment) that custom entities don't have. A user-created "Jobs" entity type works identically to Contacts at the storage, query, field, and relation layers. This architectural unification eliminates dual code paths and ensures that every platform capability â€” views, data sources, filters, sorting, inline editing, event sourcing, audit trails â€” works uniformly across all entity types.

**Core design principles:**

- **Unified Object Model** â€” System entities (Contact, Conversation, Company, Project, Topic, Communication) and user-created entities are instances of the same `ObjectType` framework. No first-class vs. second-class distinction at the storage, query, or rendering layers.
- **Dedicated typed tables** â€” Every entity type gets its own PostgreSQL table with native typed columns. Fields map directly to database columns. This provides maximum query performance, full PostgreSQL type safety, native indexing, and the simplest possible virtual-to-physical schema translation for the Data Sources query engine.
- **Full event sourcing** â€” Every entity type (system and custom) has a companion event table recording all field-level mutations as immutable events. This enables audit trails, point-in-time reconstruction, undo/revert, and temporal analytics â€” uniformly, for every entity type.
- **First-class Relation Types** â€” Relationships between entity types are explicitly defined as Relation Type objects with cardinality, directionality (bidirectional or unidirectional), cascade behavior, optional metadata attributes, and optional Neo4j graph sync. Relations work between any combination of entity types, including self-referential.
- **Schema-per-tenant isolation** â€” Each tenant gets its own PostgreSQL schema, containing its entity type tables and event tables. Custom fields added by one tenant do not affect another tenant's schema. This aligns with the multi-tenant isolation model referenced in the Communication PRD.
- **DDL-as-a-service** â€” Adding fields, creating entity types, and defining relations trigger database schema changes (ALTER TABLE, CREATE TABLE). The platform manages these DDL operations through a safe, queued execution system with locking, validation, and rollback.

**Relationship to other PRDs:**

- **[Views & Grid PRD](views-grid-prd_V3.md)** â€” Consumes the field registry and field type system. The Views PRD's field type rendering, filter operators, sort behavior, and column system are defined against field types that this PRD specifies. The Views PRD is entity-agnostic because this PRD provides a uniform entity model.
- **[Data Sources PRD](data-sources-prd.md)** â€” Consumes the entity type definitions and relation model. The virtual schema that SQL data sources query against is derived from the object types and their field registries defined here. The prefixed entity ID convention (established in the Data Sources PRD) is adopted as the platform-wide standard and detailed in this PRD.
- **[Contact Management PRD](contact-management-prd.md)** â€” The Contact entity type and Company entity type defined in that PRD become pre-installed object types in the unified framework. Custom fields on Contacts are managed through this PRD's field registry, replacing the previous `custom_fields` JSONB column. See Section 26 for reconciliation details.
- **[Communication & Conversation Intelligence PRD](email-conversations-prd.md)** â€” Conversation, Communication, Project, and Topic entity types become pre-installed object types. Their specialized AI behaviors (status detection, summarization) are registered as system behaviors per Section 22.

---

## 2. Problem Statement

### The Rigid Entity Problem

Traditional CRMs ship with a fixed set of entity types â€” Contacts, Companies, Deals, Activities â€” and expect every business to fit their workflow into these predetermined categories. But real businesses have domain-specific entities that don't map to generic CRM objects.

**The consequences for CRM users:**

| Pain Point | Impact |
|---|---|
| **No domain modeling** | A gutter cleaning business needs to track Properties, Jobs, and Service Areas. A consulting firm needs Engagements and Deliverables. A VC fund needs Portfolio Companies and Rounds. None of these exist in a standard CRM. Users resort to abusing generic entities (Deals become Jobs, Companies become Properties) or maintaining separate spreadsheets. |
| **Custom fields aren't enough** | Adding custom fields to Contacts or Deals doesn't solve the problem â€” a Job is not a Contact with extra fields. It's a fundamentally different entity with its own lifecycle, relationships, and views. |
| **No cross-entity relationships** | Even when users create custom entities through third-party add-ons, those entities can't participate in the same relationship graph, view system, or query engine as native entities. They're second-class citizens. |
| **Schema rigidity** | As the business evolves, the data model needs to evolve too. Adding a field to track a new dimension of a Job shouldn't require a developer, a deployment, or a database migration. |
| **Lost intelligence** | Custom entities created outside the CRM don't get the platform's intelligence capabilities â€” no event history, no audit trails, no AI analysis, no relationship tracking. The data exists but the platform ignores it. |

### Why Existing Solutions Fall Short

- **Salesforce Custom Objects** â€” Powerful but complex. Requires developer skills for anything beyond basic fields. Governor limits (500 custom objects, 800 fields per object) create artificial constraints. No event sourcing. Custom objects feel bolted-on rather than native.
- **HubSpot Custom Objects** â€” Limited to Operations Hub Professional+. No raw SQL querying. Relations are simple and don't support metadata. No graph modeling.
- **Attio Objects** â€” Closest to the target. Everything is an "object" with a flexible data model. But treats data as flat records without event sourcing, no point-in-time reconstruction, no graph database integration, and no relation metadata.
- **Airtable/Notion databases** â€” Excellent flexibility but no CRM intelligence layer. No identity resolution, no enrichment, no AI conversation analysis. Pure data modeling without business context.
- **ClickUp Custom Fields** â€” Rich field types but limited to pre-defined entity types (Tasks, Docs, etc.). Can't create entirely new entity types with their own views and relationships.

CRMExtender closes this gap by making custom entities **equal citizens** in a platform that provides event sourcing, relationship intelligence, AI analysis, and polymorphic views to every entity type â€” not just the ones that shipped with the product.

---

## 3. Goals & Success Metrics

### Primary Goals

1. **Entity-agnostic platform** â€” Any capability that works for system entities (views, data sources, filters, inline editing, event history, audit trails) works identically for custom entities with zero additional implementation.
2. **Self-service data modeling** â€” Users with the appropriate permission can create entity types, define fields, and establish relationships without developer assistance, database expertise, or deployment cycles.
3. **Full lifecycle tracking** â€” Every custom entity record has the same event-sourced history, point-in-time reconstruction, and audit trail capabilities as Contacts and Conversations.
4. **Rich relationship modeling** â€” Relationships between entity types are first-class objects with cardinality, directionality, metadata, and optional graph database sync â€” enabling the same relationship intelligence for custom entities as for system entities.
5. **Domain fidelity** â€” Users can model their specific business domain (gutter cleaning, consulting, venture capital, real estate) with entity types, fields, and relationships that faithfully represent their real-world operations.

### Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Custom entity type adoption | >60% of tenants create at least 1 custom entity type within 30 days | Analytics: entity type creation events where `is_system = false` |
| Fields per custom entity | Average 8-15 fields per custom entity type | Analytics: field count per entity type |
| Relation adoption | >70% of custom entity types have at least 1 relation to another entity type | Analytics: relation type count per entity type |
| Cross-entity data source usage | >40% of data sources reference at least 1 custom entity type | Analytics: entity type references in data source definitions |
| Custom entity view creation | >80% of custom entity types have at least 2 views within 14 days of creation | Analytics: view-to-entity-type ratio |
| Field addition time | <2 seconds from field definition submission to table column creation | Instrumented DDL execution timing |
| Entity type creation time | <5 seconds from entity type definition submission to table creation | Instrumented DDL execution timing |
| Event sourcing coverage | 100% of field mutations on custom entities produce events | Audit: event count vs. mutation count |
| Entity type limit utilization | <20% of tenants exceed 25 custom entity types (50 is the cap) | Analytics: entity type count distribution |

---

## 4. User Personas & Stories

### Personas

| Persona | Custom Object Needs | Key Scenarios |
|---|---|---|
| **Sam â€” Gutter Cleaning Business Owner** | Domain-specific entities for service operations: Jobs, Properties, Service Areas, Estimates. Needs relations to Contacts and Companies. Wants views of Jobs by status, Properties by service frequency, and Estimates by expiration date. | "I need a Jobs entity with address, service type, price, and status. Each Job links to a Contact (the customer) and a Property. I want a Board view of Jobs by status and a Calendar view by scheduled date." |
| **Alex â€” Sales Rep** | Deals entity with pipeline stages, linked to Contacts and Companies. Products/Services catalog linked to Deals. Custom fields on Contacts for industry-specific attributes. | "I want to add a 'Budget Range' field to Contacts and create a Deals entity with amount, stage, and close date. Each Deal links to multiple Contacts (stakeholders) with roles like 'Decision Maker' and 'Influencer'." |
| **Maria â€” Consultant** | Engagements with clients, Deliverables linked to Engagements, custom fields on Companies for engagement history. | "I need an Engagements entity that tracks scope, budget, and status. Each Engagement links to a Company and multiple Contacts. Deliverables are a separate entity linked to Engagements with due dates." |
| **Jordan â€” Team Lead** | Team-wide custom entities shared across the workspace. Needs entity type management and field configuration for the team. | "I want to create a 'Client Projects' entity type for the team with standardized fields and status values. Everyone should be able to create records, but only I should be able to modify the entity type's fields and options." |

### User Stories

#### Entity Type Creation

| ID | Story | Acceptance Criteria |
|---|---|---|
| CO-01 | As a user with the Object Creator permission, I want to create a custom entity type with a name and description, so I can model domain-specific data. | Entity type created with auto-generated type prefix and database table. Appears in entity type list. Available in Data Source entity picker and View creation. |
| CO-02 | As a user, I want to add fields to an entity type with specific data types, so I can define what data each record captures. | Field added as typed column on entity type's table. Field appears in Views field picker, Data Source column registry, and record creation forms. |
| CO-03 | As a user, I want to create a relation between two entity types, so records can be linked and traversed. | Relation type created. Relation fields appear on both entity types (if bidirectional). Views can traverse the relation for lookup columns. Data Sources can JOIN across the relation. |

#### Record Management

| ID | Story | Acceptance Criteria |
|---|---|---|
| CO-04 | As a user, I want to create, view, edit, and archive records of any entity type through a consistent interface. | CRUD operations work identically for system and custom entities. All mutations are event-sourced. Archived records are hidden from default views but recoverable. |
| CO-05 | As a user, I want to see the complete change history of any record, so I can audit who changed what and when. | Event history available on record detail view. Shows field-level changes with old/new values, timestamps, and user attribution. |
| CO-06 | As a user, I want to add custom fields to system entities like Contacts, so I can track industry-specific attributes without creating a separate entity type. | Custom field added to Contact entity type's table through the same field registry. Field appears in Contact views, data sources, and detail pages. |

#### Domain Modeling (Gutter Business Test Case)

| ID | Story | Acceptance Criteria |
|---|---|---|
| CO-07 | As Sam, I want to create a "Properties" entity type with address, property type, gutter footage, and service frequency fields, linked to Contacts (owners). | Entity type created with typed fields. Bidirectional relation to Contacts established. Property records show owner; Contact records show linked Properties. |
| CO-08 | As Sam, I want to create a "Jobs" entity type with service type, price, status, and date fields, linked to a Property and a Contact (customer), with crew assignment as a many-to-many relation with a "role" attribute. | Entity type created. Relations established: Jobâ†’Property (many:1), Jobâ†’Contact customer (many:1), Jobâ†”Contact crew (many:many with role metadata). |
| CO-09 | As Sam, I want to create an "Estimates" entity type linked to a Contact and Property, where accepting an Estimate can generate a Job. | Entity type created with status workflow. Relation to Contact, Property, and optionally to a generated Job. Status transition from "accepted" triggers Job creation (Phase 2 â€” automation). |
| CO-10 | As Sam, I want to create a "Service Areas" entity type to define geographic zones with active status, linked to Properties. | Entity type created. Relation to Properties established. Views can filter Properties by Service Area. |

---

## 5. Core Concepts & Terminology

### 5.1 Conceptual Model

```
Object Type Framework
  â”œâ”€â”€ Object Type Definition
  â”‚     â”œâ”€â”€ Identity: name, slug, type prefix, description
  â”‚     â”œâ”€â”€ Field Registry: ordered list of field definitions
  â”‚     â”œâ”€â”€ Field Groups: logical sections for detail view rendering
  â”‚     â”œâ”€â”€ Relation Types: connections to other entity types
  â”‚     â”œâ”€â”€ Display Name Field: which field serves as the record title
  â”‚     â””â”€â”€ Behaviors: registered specialized logic (system entities only)
  â”‚
  â”œâ”€â”€ System Object Types (pre-installed, is_system=true)
  â”‚     â”œâ”€â”€ Contact (con_)    â€” Behaviors: identity resolution, enrichment
  â”‚     â”œâ”€â”€ Company (cmp_)    â€” Behaviors: firmographic enrichment
  â”‚     â”œâ”€â”€ Conversation (cvr_) â€” Behaviors: AI status detection, summarization
  â”‚     â”œâ”€â”€ Communication (com_) â€” Behaviors: parsing, segmentation
  â”‚     â”œâ”€â”€ Project (prj_)    â€” Behaviors: topic aggregation
  â”‚     â”œâ”€â”€ Topic (top_)      â€” Behaviors: conversation aggregation
  â”‚     â”œâ”€â”€ Event (evt_)            â€” Behaviors: attendee resolution, birthday auto-gen, recurrence
  â”‚     â”œâ”€â”€ Note (not_)             â€” Behaviors: revision mgmt, FTS sync, mentions
  â”‚     â””â”€â”€ Task (tsk_)             â€” Behaviors: status enforcement, recurrence, AI extraction, overdue
  â”‚
  â””â”€â”€ Custom Object Types (user-created, is_system=false)
        â”œâ”€â”€ Jobs (job_)       â€” Fields: address, service_type, price, status, ...
        â”œâ”€â”€ Properties (prop_) â€” Fields: address, property_type, footage, ...
        â”œâ”€â”€ Service Areas (svca_) â€” Fields: name, state, active, ...
        â””â”€â”€ Estimates (est_)  â€” Fields: description, total_price, status, ...
```

### 5.2 Key Terminology

| Term | Definition |
|---|---|
| **Object Type** | A named definition of an entity class â€” its identity, fields, relations, and behaviors. Analogous to a database table definition or a class in object-oriented programming. Both system entities and custom entities are object types. |
| **System Object Type** | A pre-installed object type that ships with the platform (`is_system = true`). Cannot be deleted or archived. Core fields are protected from removal. May have registered behaviors (specialized logic). |
| **Custom Object Type** | A user-created object type (`is_system = false`). Has the same capabilities as system object types except behaviors. Can be archived (soft deleted). Subject to the per-tenant limit. |
| **Field** | A named, typed attribute on an object type. Maps to a physical column on the object type's database table. Has a data type, validation rules, display configuration, and lifecycle state. |
| **Field Registry** | The complete ordered set of fields defined on an object type, including universal fields and user-defined fields. The authoritative source for what data an entity type captures. |
| **Field Group** | A named grouping of fields for organizing the detail view layout. Purely presentational â€” does not affect storage or queries. |
| **Relation Type** | A first-class definition of a relationship between two object types (or an object type and itself). Specifies cardinality, directionality, cascade behavior, and optional metadata attributes. |
| **Relation Metadata** | Additional attributes stored on the relationship instance itself (not on either entity record). Examples: role, strength score, start date, notes. |
| **Display Name Field** | The field designated as the record's human-readable title. Used in views, previews, relation pickers, search results, and card headers. Every object type must designate exactly one field. |
| **Type Prefix** | A 3â€“4 character immutable identifier for an object type, used in the prefixed entity ID convention. System prefixes are reserved (`con_`, `cvr_`, `com_`, etc.); custom prefixes are auto-generated. |
| **Behavior** | A registered piece of specialized logic that applies to a system object type. Examples: identity resolution (Contact), AI status detection (Conversation), firmographic enrichment (Company). Custom object types do not have behaviors. |
| **DDL Operation** | A database schema change (CREATE TABLE, ALTER TABLE ADD COLUMN, etc.) triggered by user actions in the object type framework. Managed through the DDL Management System. |
| **Schema Version** | A counter on the object type's field registry that increments when fields are added, removed, renamed, or have their type converted. Used by the Data Sources PRD to detect breaking changes for dependent data sources and views. |

### 5.3 Architecture Overview

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    OBJECT TYPE FRAMEWORK (this PRD)                      â”‚
â”‚                                                                          â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                      â”‚
â”‚  â”‚  Object Type        â”‚  â”‚   Relation Type       â”‚                      â”‚
â”‚  â”‚  Registry           â”‚  â”‚   Registry            â”‚                      â”‚
â”‚  â”‚  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€  â”‚  â”‚  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ â”‚                      â”‚
â”‚  â”‚  System types       â”‚  â”‚  Cardinality          â”‚                      â”‚
â”‚  â”‚  Custom types       â”‚  â”‚  Directionality       â”‚                      â”‚
â”‚  â”‚  Field registries   â”‚  â”‚  Cascade behavior     â”‚                      â”‚
â”‚  â”‚  Field groups       â”‚  â”‚  Metadata attributes  â”‚                      â”‚
â”‚  â”‚  Behaviors          â”‚  â”‚  Neo4j sync flag      â”‚                      â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                      â”‚
â”‚           â”‚                          â”‚                                   â”‚
â”‚           â–¼                          â–¼                                   â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                       â”‚
â”‚  â”‚           DDL Management System               â”‚                       â”‚
â”‚  â”‚  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€        â”‚                       â”‚
â”‚  â”‚  CREATE TABLE, ALTER TABLE ADD COLUMN,         â”‚                       â”‚
â”‚  â”‚  CREATE junction tables, manage indexes         â”‚                       â”‚
â”‚  â”‚  Queued execution, locking, validation          â”‚                       â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                       â”‚
â”‚                       â”‚                                                  â”‚
â”‚                       â–¼                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                       â”‚
â”‚  â”‚        Physical Storage (per tenant schema)   â”‚                       â”‚
â”‚  â”‚  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€        â”‚                       â”‚
â”‚  â”‚  tenant_abc.contacts       (read model)       â”‚                       â”‚
â”‚  â”‚  tenant_abc.contacts_events (event store)     â”‚                       â”‚
â”‚  â”‚  tenant_abc.jobs           (read model)       â”‚                       â”‚
â”‚  â”‚  tenant_abc.jobs_events    (event store)      â”‚                       â”‚
â”‚  â”‚  tenant_abc.jobs__contacts (junction table)   â”‚                       â”‚
â”‚  â”‚  ...                                          â”‚                       â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                       â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚                          â”‚                        â”‚
         â–¼                          â–¼                        â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Data Sources   â”‚  â”‚    Views & Grid      â”‚  â”‚  Communication &     â”‚
â”‚  PRD            â”‚  â”‚    PRD               â”‚  â”‚  Conversation PRD    â”‚
â”‚  â”€â”€â”€â”€â”€â”€â”€â”€â”€      â”‚  â”‚  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€          â”‚  â”‚  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€      â”‚
â”‚  Virtual schema â”‚  â”‚  Field type          â”‚  â”‚  Participant         â”‚
â”‚  from object    â”‚  â”‚  rendering from      â”‚  â”‚  resolution to       â”‚
â”‚  type field     â”‚  â”‚  field registry      â”‚  â”‚  entity records      â”‚
â”‚  registries     â”‚  â”‚                      â”‚  â”‚                      â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## 6. Object Type Definition Model

An Object Type is a first-class entity in the system (meta-entity: it describes other entities). It is stored in a platform-level registry table that exists outside tenant schemas.

### 6.1 Object Type Attributes

| Attribute | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | Prefixed ULID: `oty_` prefix (e.g., `oty_01HX7VFBK3...`). Immutable. |
| `tenant_id` | TEXT | NOT NULL, FK | Owning tenant. System object types have a special platform tenant ID. |
| `name` | TEXT | NOT NULL | Display name, user-facing. Renamable. (e.g., "Jobs", "Properties") |
| `slug` | TEXT | NOT NULL, UNIQUE per tenant | Machine name, immutable after creation. Used in API paths and virtual schema. (e.g., `jobs`, `properties`) |
| `type_prefix` | TEXT | NOT NULL, UNIQUE globally | 3â€“4 character prefix for entity IDs. Immutable. (e.g., `job_`, `prop_`) |
| `description` | TEXT | | Optional description of the entity type's purpose |
| `icon` | TEXT | | Optional icon identifier for UI display |
| `display_name_field_id` | TEXT | FK â†’ fields | Which field serves as the record title. Required. |
| `is_system` | BOOLEAN | NOT NULL, DEFAULT false | Whether this is a pre-installed system entity type |
| `is_archived` | BOOLEAN | NOT NULL, DEFAULT false | Soft-delete flag. System types cannot be archived. |
| `schema_version` | INTEGER | NOT NULL, DEFAULT 1 | Incremented on field registry changes that affect the column set |
| `field_limit` | INTEGER | DEFAULT 200 | Maximum number of user-defined fields on this entity type |
| `created_by` | TEXT | FK â†’ users | User who created the entity type |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

### 6.2 Type Prefix Generation

When a user creates a custom object type, the system generates a type prefix:

1. Take the first 3â€“4 characters of the slug (e.g., `jobs` â†’ `job`, `properties` â†’ `prop`, `service_areas` â†’ `svca`)
2. Check for collisions against all existing prefixes (system and custom, across all tenants)
3. If collision detected, append or modify characters until unique (e.g., if `job_` exists, try `jobs_`, `jbs_`, `jb_`)
4. The prefix is immutable once assigned â€” renaming the object type does not change the prefix

### 6.3 System Object Type Prefix Registry

| Object Type | Prefix | Slug | Pre-installed Fields |
|---|---|---|---|
| Contact | `con_` | `contacts` | first_name, last_name, display_name, email_primary, phone_primary, job_title, avatar_url, lead_source, lead_status, engagement_score, intelligence_score, status |
| Company | `cmp_` | `companies` | name, domain, industry, size, location, revenue, logo_url, status |
| Conversation | `cvr_` | `conversations` | subject, channel, ai_status, human_status, resolution_status, communication_count, first_activity_at, last_activity_at |
| Communication | `com_` | `communications` | channel, direction, timestamp, from_address, to_addresses, subject, body_preview, content_clean |
| Project | `prj_` | `projects` | name, description, status, owner_id, topic_count, last_activity_at |
| Topic | `top_` | `topics` | name, description, project_id, conversation_count, last_activity_at |
| Event | `evt_` | `events` | title, event_type, start_datetime, end_datetime, location, status, source (managed by Event Management PRD) |
| Note | `not_` | `notes` | title, visibility, current_revision_id, revision_count (managed by Notes PRD) |
| Task | `tsk_` | `tasks` | title, status, priority, start_date, due_date, completed_at, estimated_duration, actual_duration, source (managed by Tasks PRD) |
| Data Source | `dts_` | `data_sources` | (managed by Data Sources PRD) |
| View | `viw_` | `views` | (managed by Views PRD) |
| User | `usr_` | `users` | (managed by Permissions PRD) |
| Segment | `seg_` | `segments` | (managed by Contact Management PRD) |

### 6.4 Object Type Creation Permission

Creating custom object types requires the **Object Creator** permission. This is a discrete permission that can be granted to any role â€” it is not restricted to workspace administrators, though administrators have it by default.

Rationale: Creating an object type triggers DDL operations (table creation) and allocates schema resources. It should be intentional, not casual. But restricting to admins only is too rigid for teams where multiple people need to model domain data.

### 6.5 Object Type Limit

Each tenant may have a maximum of **50 custom object types** (excluding system object types, which do not count against the limit). This limit balances flexibility against schema complexity and is adjustable per tenant for enterprise plans.

At 50 object types Ã— 200 fields each Ã— dedicated tables with indexes, the per-tenant schema contains up to ~100 tables (50 read models + 50 event tables) plus junction tables for many-to-many relations. PostgreSQL handles this scale comfortably.

---

## 7. Universal Fields

Every object type â€” system and custom â€” has a set of universal fields that the framework manages automatically. These fields exist on every entity table and are not user-configurable (they cannot be removed, renamed, or have their types changed).

### 7.1 Universal Field Set

| Field | Column Name | Type | Description |
|---|---|---|---|
| **ID** | `id` | TEXT, PK | Prefixed ULID (e.g., `job_01HX7VFBK3...`). Generated by the system on record creation. Immutable. |
| **Tenant** | `tenant_id` | TEXT, NOT NULL | Tenant isolation. Set on creation, immutable. |
| **Created At** | `created_at` | TIMESTAMPTZ, NOT NULL | Record creation timestamp. Set by the system, immutable. |
| **Updated At** | `updated_at` | TIMESTAMPTZ, NOT NULL | Last modification timestamp. Updated automatically on every mutation. |
| **Created By** | `created_by` | TEXT, FK â†’ users | User who created the record. NULL for system-generated records. |
| **Updated By** | `updated_by` | TEXT, FK â†’ users | User who last modified the record. |
| **Archived At** | `archived_at` | TIMESTAMPTZ, NULL | Soft-delete timestamp. NULL means active. Non-NULL means archived. Default views filter to `archived_at IS NULL`. |

### 7.2 Display Name Field

In addition to universal fields, every object type must designate exactly one user-defined field as the **display name field**. This field is used as the record's human-readable title throughout the platform:

- View row identifiers (first column in List/Grid views)
- Relation picker search and display
- Preview panel header
- Board view card titles
- Calendar view event labels
- Search result labels
- Activity timeline references

When a user creates a custom object type, the system creates a default `name` field (type: Text, single-line, required) and designates it as the display name field. The user can change which field serves as the display name, but the designation cannot be empty.

---

## 8. Field Registry

The field registry is the ordered set of field definitions on an object type. It is the authoritative source for what data an entity type captures and how each field behaves across the platform.

### 8.1 Field Definition Model

| Attribute | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PK | Prefixed ULID: `fld_` prefix. Immutable. |
| `object_type_id` | TEXT | FK â†’ object_types | The entity type this field belongs to |
| `slug` | TEXT | NOT NULL, UNIQUE per object type | Machine name, immutable after creation. Maps to the physical column name. (e.g., `service_type`, `price`) |
| `display_name` | TEXT | NOT NULL | User-facing label, renamable. (e.g., "Service Type", "Price") |
| `description` | TEXT | | Optional help text shown in forms and tooltips |
| `field_type` | TEXT | NOT NULL | One of the registered field types (see Section 9). Immutable after creation except for safe conversions (see Section 10). |
| `field_type_config` | JSONB | | Type-specific configuration (e.g., decimal places for Number, option list for Select, target entity type for Relation). See Section 9. |
| `is_required` | BOOLEAN | DEFAULT false | Whether a value must be provided on record creation/update |
| `default_value` | TEXT | | Default value for new records (stored as string, parsed according to field type) |
| `validation_rules` | JSONB | | Type-specific validation constraints. See Section 12. |
| `display_order` | INTEGER | NOT NULL | Position in the field registry ordering. Used for default detail view layout. |
| `field_group_id` | TEXT | FK â†’ field_groups | Optional grouping for detail view layout. See Section 11. |
| `is_system` | BOOLEAN | DEFAULT false | Whether this field is a core field of a system entity type (protected from deletion) |
| `is_archived` | BOOLEAN | DEFAULT false | Soft-delete for fields. Archived fields are hidden from UI but the column and data are preserved. |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

### 8.2 Field Slug to Column Name Mapping

The field's `slug` is used directly as the PostgreSQL column name on the entity type's table. This means slugs must be valid PostgreSQL identifiers:

- Lowercase alphanumeric characters and underscores only
- Must start with a letter
- Maximum 63 characters (PostgreSQL identifier limit)
- Cannot collide with universal field column names (`id`, `tenant_id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `archived_at`)
- Cannot collide with PostgreSQL reserved words

The system validates these constraints at field creation time and rejects invalid slugs with a clear error message.

### 8.3 Field Ordering

Fields have a `display_order` integer that determines their default position in:

- Record detail views (the form layout)
- Record creation forms
- The "Add Column" picker in views (within the "Direct Fields" section)
- Export column ordering

Users can reorder fields within the entity type settings. Reordering does not affect the physical column order in the database table (PostgreSQL doesn't have meaningful column ordering for queries).

### 8.4 Field Limits

Each object type can have a maximum of **200 user-defined fields** (universal fields don't count). This limit is per-entity-type, not per-tenant. At 200 columns per table, PostgreSQL performs well for the target record volumes (low thousands per entity type).

---

## 9. Field Type System

Each field type defines the physical PostgreSQL column type, the validation behavior, the serialization format for events, and the configuration options. The **rendering behavior** (display renderer, inline editor, filter operators, sort behavior, group-by support) is defined in the [Views & Grid PRD, Section 9](views-grid-prd_V3.md#9-field-type-registry) â€” this PRD defines the data layer.

### 9.1 Phase 1 Field Types

| Field Type | PostgreSQL Column Type | Config Options | Notes |
|---|---|---|---|
| **Text (single-line)** | `TEXT` | `max_length` | General-purpose short text |
| **Text (multi-line)** | `TEXT` | `max_length` | Long-form text, rendered with line breaks |
| **Number** | `NUMERIC` | `decimal_places`, `min_value`, `max_value` | Arbitrary precision. `decimal_places` controls display formatting. |
| **Currency** | `NUMERIC` | `decimal_places` (default 2), `currency_code` (e.g., "USD"), `min_value`, `max_value` | Stored as numeric value; currency code in config determines display symbol. |
| **Date** | `DATE` | `min_date`, `max_date` | Date without time |
| **Datetime** | `TIMESTAMPTZ` | `min_date`, `max_date` | Date with time, timezone-aware |
| **Select (single)** | `TEXT` | `options` (ordered list of option definitions, see Section 13) | Value is the option's slug. FK-like integrity enforced at application level. |
| **Select (multi)** | `TEXT[]` | `options` (ordered list of option definitions) | PostgreSQL array of option slugs |
| **Checkbox** | `BOOLEAN` | | True/false |
| **Relation (single)** | `TEXT` | `target_object_type_id`, `relation_type_id` | Foreign key to target entity's `id`. See Section 14 for full relation model. |
| **Relation (multi)** | â€” | `target_object_type_id`, `relation_type_id` | Implemented via junction table, not a column on the entity table. See Section 14. |
| **Email** | `TEXT` | | Validated as email format |
| **Phone** | `TEXT` | | Stored in E.164 format; displayed with locale-aware formatting |
| **URL** | `TEXT` | | Validated as URL format |
| **Rating** | `INTEGER` | `min_value` (default 1), `max_value` (default 5) | Integer within range |
| **Duration** | `INTEGER` | `display_format` (`hours_minutes`, `minutes_seconds`, `hours_minutes_seconds`) | Stored as seconds. Displayed in configured format. |
| **User** | `TEXT` | | Foreign key to users table. Validated against active users in the tenant. |

### 9.2 Phase 2 Field Types

| Field Type | PostgreSQL Column Type | Notes |
|---|---|---|
| **Formula** | `NUMERIC` or `TEXT` (based on output type) | Computed from other fields. Read-only. Expression defined in config. Column value recomputed on dependency change. |
| **Rollup** | `NUMERIC` | Aggregated from related records (e.g., COUNT of Jobs on a Property, SUM of Job prices on a Contact). Read-only. Defined by: relation, target field, aggregation function. |

### 9.3 Field Type Configuration Examples

**Number field with constraints:**
```json
{
  "field_type": "number",
  "field_type_config": {
    "decimal_places": 2,
    "min_value": 0,
    "max_value": 999999.99
  }
}
```

**Single-select field with options:**
```json
{
  "field_type": "select_single",
  "field_type_config": {
    "options": [
      { "slug": "full_clean", "label": "Full Clean", "color": "#4CAF50", "order": 1 },
      { "slug": "downspout_flush", "label": "Downspout Flush", "color": "#2196F3", "order": 2 },
      { "slug": "repair", "label": "Repair", "color": "#FF9800", "order": 3 },
      { "slug": "guard_install", "label": "Guard Install", "color": "#9C27B0", "order": 4 }
    ]
  }
}
```

**Currency field:**
```json
{
  "field_type": "currency",
  "field_type_config": {
    "decimal_places": 2,
    "currency_code": "USD",
    "min_value": 0
  }
}
```

**Relation field (single):**
```json
{
  "field_type": "relation_single",
  "field_type_config": {
    "target_object_type_id": "oty_01HX7V...",
    "relation_type_id": "rel_01HX8A..."
  }
}
```

---

## 10. Field Type Conversion Matrix

Users can convert a field's type through limited safe conversions. Safe conversions preserve data without loss (or with clearly communicated, minor formatting changes). Unsafe conversions that would cause data loss or ambiguity are blocked.

### 10.1 Conversion Rules

| From â†’ To | Allowed? | Conversion Behavior |
|---|---|---|
| Text â†’ Text (multi-line) | **Yes** | No data change. Column type unchanged (both TEXT). |
| Text (multi-line) â†’ Text | **Yes, with warning** | Truncation risk if values contain newlines. Warning shown. |
| Text â†’ Select (single) | **Yes, with wizard** | System scans existing values, proposes option list. Values not matching an option become NULL (with preview). |
| Text â†’ Email | **Yes, with validation** | Values that fail email validation become NULL (with preview). |
| Text â†’ Phone | **Yes, with validation** | Values that fail phone format validation become NULL (with preview). |
| Text â†’ URL | **Yes, with validation** | Values that fail URL validation become NULL (with preview). |
| Number â†’ Currency | **Yes** | `ALTER TABLE ALTER COLUMN TYPE` (NUMERIC â†’ NUMERIC, no change). Currency config added. |
| Currency â†’ Number | **Yes** | Currency config removed. Column type unchanged. |
| Number â†’ Rating | **Yes, with clamping** | Values outside rating range are clamped (with preview). |
| Rating â†’ Number | **Yes** | No data change. Rating config removed. |
| Date â†’ Datetime | **Yes** | Date values gain midnight time component. `ALTER TABLE ALTER COLUMN TYPE TIMESTAMPTZ`. |
| Datetime â†’ Date | **Yes, with warning** | Time component is dropped. Warning shown. |
| Select (single) â†’ Text | **Yes** | Option slugs become plain text values. |
| Select (single) â†’ Select (multi) | **Yes** | Single values become single-element arrays. `ALTER TABLE ALTER COLUMN TYPE TEXT[]`. |
| Select (multi) â†’ Select (single) | **Yes, with warning** | Multi-value fields keep only the first value. Warning shown. |
| Checkbox â†’ Select (single) | **Yes** | `true` â†’ option "Yes", `false` â†’ option "No". Options auto-created. |
| All other conversions | **Blocked** | User must create a new field and manually migrate data. |

### 10.2 Conversion Workflow

1. User selects "Change field type" from field settings
2. System shows the target type options (only safe conversions listed)
3. System scans existing data and shows a preview: how many records will be affected, what data will change, what will become NULL
4. User confirms or cancels
5. On confirmation: DDL operation queued, executed, field type config updated, schema version incremented
6. Dependent data sources and views are notified of the schema change

---

## 11. Field Groups

Field groups organize fields into logical sections on the record detail view. They are purely presentational â€” they do not affect physical storage, query behavior, or field ordering in views.

### 11.1 Field Group Definition

| Attribute | Type | Description |
|---|---|---|
| `id` | TEXT, PK | `fgr_` prefixed ULID |
| `object_type_id` | TEXT, FK | The entity type this group belongs to |
| `name` | TEXT, NOT NULL | Display name (e.g., "Basic Info", "Pricing", "Scheduling") |
| `description` | TEXT | Optional description |
| `display_order` | INTEGER | Position among groups in the detail view |
| `is_collapsed_default` | BOOLEAN | Whether the group starts collapsed on the detail view |

### 11.2 Behavior

- Fields not assigned to any group appear in a default "General" group at the top
- Groups are rendered as collapsible sections on the record detail view
- Each group displays its member fields in their `display_order` sequence
- Groups can be reordered via drag-and-drop in entity type settings
- Empty groups (no fields assigned) are hidden from the detail view
- Universal fields (id, created_at, etc.) appear in a system-rendered "Record Info" section, not in user-defined groups

### 11.3 Example: Jobs Entity Type

```
â”€â”€ Basic Info â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  Name            | Address         | Service Type

â”€â”€ Pricing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  Price           | Discount        | Final Amount

â”€â”€ Scheduling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  Scheduled Date  | Completed Date  | Duration

â”€â”€ Assignment â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  Customer (â†’Contact) | Property (â†’Property) | Crew (â†’Contact[])

â”€â”€ Record Info (system) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  Created: Feb 17, 2026 by Sam  |  Updated: Feb 17, 2026
```

---

## 12. Field Validation

Each field type supports type-specific validation constraints beyond the inherent type validation. Validation rules are stored in the field definition's `validation_rules` JSONB column and enforced at the application level on record creation and update.

### 12.1 Validation Rules by Field Type

| Field Type | Available Validation Rules |
|---|---|
| **Text (single-line)** | `max_length` (integer), `min_length` (integer), `regex_pattern` (string), `is_unique` (boolean â€” unique within tenant for this field) |
| **Text (multi-line)** | `max_length` (integer), `min_length` (integer) |
| **Number** | `min_value` (numeric), `max_value` (numeric), `decimal_places` (integer, for display) |
| **Currency** | `min_value` (numeric), `max_value` (numeric) |
| **Date** | `min_date` (ISO date or relative: `"today"`, `"+7d"`), `max_date` (same) |
| **Datetime** | `min_date`, `max_date` (same as Date) |
| **Select** | Implicit: value must match a defined option slug |
| **Checkbox** | None beyond type (boolean) |
| **Relation** | Implicit: referenced record must exist and be of the correct entity type |
| **Email** | `is_unique` (boolean). Format validation is inherent to the type. |
| **Phone** | `is_unique` (boolean). E.164 format validation is inherent. |
| **URL** | None beyond format validation |
| **Rating** | `min_value`, `max_value` (integer range) |
| **Duration** | `min_value`, `max_value` (in seconds) |
| **User** | Implicit: must be an active user in the tenant |

### 12.2 Unique Constraints

When `is_unique` is enabled on a text, email, or phone field, the system creates a unique index on that column within the tenant schema. This prevents duplicate values at the database level, providing the strongest possible enforcement.

Unique constraints interact with archived records: the constraint applies across both active and archived records by default. An option to scope uniqueness to active records only (`is_unique_active_only`) is available if the business case requires reusing values from archived records.

### 12.3 Required Field Behavior

When `is_required` is true on a field:

- **Record creation:** API and UI reject creation if the field is not provided (unless a `default_value` is set, in which case the default is applied)
- **Record update:** API and UI reject updates that set the field to NULL
- **Bulk import (CSV):** Rows missing the required field are rejected with error details (not silently skipped)
- **Existing records:** Adding `is_required` to a field with existing NULL values is allowed â€” the constraint applies going forward only. A warning shows the count of records with NULL values.

---

## 13. Select & Multi-Select Options

Select fields have an ordered list of options, each of which is a first-class definition. Options are managed at the field level and shared across all records of that entity type.

### 13.1 Option Definition

| Attribute | Type | Description |
|---|---|---|
| `slug` | TEXT | Machine name, immutable. The value stored in the database column. |
| `label` | TEXT | Display name, renamable. User-facing text. |
| `color` | TEXT | Hex color code for badge/tag rendering in views. |
| `order` | INTEGER | Position in the option list. Determines Board view column order. |
| `is_archived` | BOOLEAN | Soft-delete. Archived options are hidden from the picker but remain valid values on existing records. |

### 13.2 Option Lifecycle

- **Adding an option:** Immediate. No data migration needed.
- **Renaming an option (label change):** Immediate. The stored `slug` does not change; only the display label changes.
- **Reordering options:** Immediate. Affects Board view column order and dropdown display order.
- **Archiving an option:** The option is removed from the picker UI. Records with this value retain it and display it with an "archived" indicator. New records cannot select this option.
- **Deleting an option:** Blocked if any records have this value. User must first reassign those records to a different option or clear the field, then delete.

---

## 14. Relation Types

Relation Types are first-class definitions that describe connections between object types. They are the foundation for cross-entity navigation, relation traversal columns in views, JOIN operations in data sources, and relationship intelligence in the graph database.

### 14.1 Relation Type Definition Model

| Attribute | Type | Description |
|---|---|---|
| `id` | TEXT, PK | `rel_` prefixed ULID |
| `tenant_id` | TEXT | Owning tenant |
| `name` | TEXT | Human-readable name of the relationship (e.g., "Employment", "Ownership", "Assignment") |
| `description` | TEXT | Optional description of the relationship's meaning |
| `source_object_type_id` | TEXT, FK | The "from" entity type |
| `target_object_type_id` | TEXT, FK | The "to" entity type (can be the same as source for self-referential) |
| `cardinality` | TEXT | `one_to_one`, `one_to_many`, `many_to_many` |
| `directionality` | TEXT | `bidirectional` or `unidirectional` |
| `source_field_label` | TEXT | Display name of the relation field on the source entity (e.g., "Customer") |
| `target_field_label` | TEXT | Display name of the inverse relation field on the target entity. Required if bidirectional; NULL if unidirectional. (e.g., "Jobs") |
| `cascade_behavior` | TEXT | `nullify` (default), `restrict`, `cascade_archive` |
| `has_metadata` | BOOLEAN | Whether this relation supports additional attributes on the relationship instance |
| `metadata_fields` | JSONB | If `has_metadata`, the field definitions for relation metadata (see Section 15) |
| `neo4j_sync` | BOOLEAN, DEFAULT false | Whether relation instances are synced to Neo4j as graph edges (see Section 16) |
| `neo4j_edge_type` | TEXT | If `neo4j_sync`, the Neo4j edge type label (e.g., "WORKS_AT", "OWNS", "ASSIGNED_TO") |
| `is_system` | BOOLEAN | Whether this relation is part of the platform's core model |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### 14.2 Cardinality and Physical Implementation

| Cardinality | Source Side | Target Side | Physical Storage |
|---|---|---|---|
| **One-to-one** | Relation (single) field | Relation (single) inverse field (if bidirectional) | FK column on source table, unique constraint |
| **One-to-many** | Relation (single) field on the "many" side | Relation (multi) inverse field on the "one" side (if bidirectional) | FK column on the "many" side table |
| **Many-to-many** | Relation (multi) field | Relation (multi) inverse field (if bidirectional) | Junction table: `{source_slug}__{target_slug}` |

**Junction table structure (many-to-many):**

```sql
CREATE TABLE tenant_abc.jobs__contacts_crew (
    id TEXT PRIMARY KEY,               -- rel instance ID for metadata
    source_id TEXT NOT NULL,           -- FK â†’ jobs(id)
    target_id TEXT NOT NULL,           -- FK â†’ contacts(id)
    -- Metadata columns (if has_metadata = true):
    role TEXT,                          -- e.g., "lead", "helper"
    assigned_date DATE,
    notes TEXT,
    -- Universal:
    created_at TIMESTAMPTZ NOT NULL,
    created_by TEXT,
    UNIQUE (source_id, target_id)      -- prevent duplicate links
);
```

### 14.3 Directionality Behavior

**Bidirectional relations:**

- A relation field is created on both the source and target entity types
- The source field shows the target record(s); the target field shows the source record(s)
- Both fields are navigable in views (relation traversal columns work from either direction)
- Data Sources can JOIN from either side
- Deleting the relation type removes both fields

**Unidirectional relations:**

- A relation field is created only on the source entity type
- The target entity type has no auto-created inverse field
- Views can only traverse the relation from source to target
- Data Sources can only JOIN from source to target
- Use case: a Communication references a Conversation (the Conversation doesn't need a "Communications" field â€” its activity timeline handles that differently)

### 14.4 Self-Referential Relations

When `source_object_type_id` equals `target_object_type_id`, the relation is self-referential. Both labels must be provided and must be distinct (to differentiate the two sides of the relationship on the same entity type's detail view).

**Example: Contact Reporting Structure**

```
Relation Type: "Reporting Structure"
  Source: Contact          Target: Contact
  Cardinality: many_to_one
  Directionality: bidirectional
  Source Label: "Reports To"      (shows the manager)
  Target Label: "Direct Reports"  (shows subordinates)
  Neo4j Sync: true
  Neo4j Edge Type: "REPORTS_TO"
```

On a Contact's detail view:
- "Reports To" shows a single Contact (the manager) â€” Relation (single) field
- "Direct Reports" shows multiple Contacts (subordinates) â€” Relation (multi) inverse field

### 14.5 Cascade Behavior

| Behavior | When target record is archived... | Use case |
|---|---|---|
| **Nullify** (default) | The relation field on the source record is set to NULL. Junction table rows referencing the archived record are soft-deleted. | Contact is archived â†’ Jobs' "Customer" field becomes empty |
| **Restrict** | The archive operation is blocked with an error listing the referencing records. User must unlink or archive source records first. | Cannot archive a Property if it has active Jobs |
| **Cascade archive** | All source records referencing the archived target are also archived. | Archiving a Company archives all its subsidiary Companies (self-referential cascade) |

---

## 15. Relation Metadata

When a Relation Type has `has_metadata = true`, each relationship instance can carry additional attributes beyond the simple link between two records. Metadata is stored on the junction table (for many-to-many) or on a companion relation instance table (for one-to-one and one-to-many).

### 15.1 Metadata Field Definition

Relation metadata fields use the same field type system as entity fields (Section 9), but with a reduced set of supported types:

| Supported Metadata Field Types | Rationale |
|---|---|
| Text (single-line) | Labels, notes |
| Text (multi-line) | Longer descriptions |
| Number | Scores, ratings |
| Currency | Financial attributes |
| Date | Start/end dates |
| Datetime | Precise timestamps |
| Select (single) | Roles, categories |
| Checkbox | Flags |
| Rating | Strength scores |
| Duration | Time measurements |

Relation, Formula, Rollup, and User fields are not supported as metadata fields (to avoid recursive complexity).

### 15.2 Metadata Storage

**Many-to-many relations:** Metadata fields are columns on the junction table (as shown in Section 14.2). Adding a metadata field triggers `ALTER TABLE ADD COLUMN` on the junction table.

**One-to-one and one-to-many relations with metadata:** When metadata is enabled, the system creates a companion `relation_instances` table rather than relying solely on the FK column:

```sql
CREATE TABLE tenant_abc.rel_job_customer_instances (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,       -- FK â†’ jobs(id)
    target_id TEXT NOT NULL,       -- FK â†’ contacts(id)
    -- Metadata columns:
    referral_source TEXT,
    satisfaction_rating INTEGER,
    -- Universal:
    created_at TIMESTAMPTZ NOT NULL,
    created_by TEXT,
    UNIQUE (source_id)             -- enforces one-to-many: each job has one customer
);
```

The FK column on the source table is retained for query performance (JOINs don't need to go through the instance table for basic traversal). The instance table provides metadata when needed.

### 15.3 Metadata in Views

Relation metadata fields are accessible in views as a special category of lookup column. When a view displays a relation traversal column, metadata fields appear as additional traversal options:

```
Add Column
â”œâ”€â”€ Direct Fields
â”‚     â”œâ”€â”€ Name
â”‚     â”œâ”€â”€ Price
â”‚     â””â”€â”€ ...
â””â”€â”€ Related Entity Fields
      â””â”€â”€ Customer (â†’Contact)
            â”œâ”€â”€ Contact Name
            â”œâ”€â”€ Contact Email
            â”œâ”€â”€ ...
            â””â”€â”€ [Relationship] Referral Source    â† metadata field
            â””â”€â”€ [Relationship] Satisfaction Rating â† metadata field
```

### 15.4 Event Sourcing for Relation Metadata

Changes to relation metadata are event-sourced in the entity's event table (the source entity's event table, with a special event type `relation_metadata_updated` that captures the relation type ID, target record ID, field name, old value, and new value).

---

## 16. Neo4j Graph Sync

Relation Types with `neo4j_sync = true` have their instances automatically synchronized to Neo4j as graph edges, enabling graph-based queries, traversal, and relationship intelligence.

### 16.1 Sync Model

```
PostgreSQL (source of truth)          Neo4j (graph projection)
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”          â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ contacts table           â”‚          â”‚ (:Contact {id, name})   â”‚
â”‚ jobs table              â”‚   sync   â”‚ (:Job {id, name})       â”‚
â”‚ junction/instance tables â”‚  â”€â”€â”€â”€â”€â–º â”‚ -[:ASSIGNED_TO {role}]â†’ â”‚
â”‚ event tables            â”‚          â”‚ -[:OWNS]â†’               â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜          â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

- **PostgreSQL is always the source of truth.** Neo4j is a read-optimized projection for graph queries.
- Sync is asynchronous (event-driven). When a relation is created, updated, or deleted in PostgreSQL, a sync event is published.
- Entity records are synced as nodes with their `id` and `display_name` field (plus any additional fields designated for graph sync â€” configurable per object type).
- Relation instances are synced as edges with the `neo4j_edge_type` label and any metadata fields.

### 16.2 Graph-Enabled Queries

When a relation type is graph-synced, the platform can answer graph-native questions:

- **Path finding:** "What's the shortest connection path between me and Contact X?" (warm intro paths)
- **Neighborhood queries:** "Show me all entities within 2 hops of this Contact"
- **Influence analysis:** "Who are the most connected people in my network?" (centrality metrics)
- **Pattern matching:** "Find all Contacts who work at Companies in the same industry as Company X"

These queries are powered by Neo4j's Cypher query language and surfaced through the API and (in future phases) through the Data Sources layer.

### 16.3 Phasing

- **Phase 1:** Neo4j sync infrastructure built. System relation types (Contactâ†’Company employment, Contactâ†’Contact reporting structure) synced.
- **Phase 2:** Custom relation types can opt into Neo4j sync. Basic graph queries available via API.
- **Phase 3:** Graph queries available in Data Sources (Cypher as an alternative query mode). Graph visualization in Views.

---

## 17. Physical Storage Architecture

### 17.1 Dedicated Tables Per Entity Type

Every object type gets its own PostgreSQL table within the tenant's schema. The table name is the object type's `slug`. Columns correspond directly to the object type's field definitions, with column names matching field slugs.

**Example: Jobs entity type for tenant `tenant_abc`**

```sql
CREATE TABLE tenant_abc.jobs (
    -- Universal fields
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT,
    updated_by TEXT,
    archived_at TIMESTAMPTZ,

    -- User-defined fields (from field registry)
    name TEXT NOT NULL,                         -- Display name field
    address TEXT,
    service_type TEXT,                          -- Select: full_clean, downspout_flush, ...
    price NUMERIC,
    status TEXT,                                -- Select: estimated, scheduled, ...
    scheduled_date DATE,
    completed_date DATE,
    duration_minutes INTEGER,
    crew_notes TEXT,

    -- Relation fields (FK columns for single relations)
    customer_contact_id TEXT,                   -- FK â†’ tenant_abc.contacts(id)
    property_id TEXT                            -- FK â†’ tenant_abc.properties(id)
);

-- Indexes
CREATE INDEX idx_jobs_tenant ON tenant_abc.jobs(tenant_id);
CREATE INDEX idx_jobs_status ON tenant_abc.jobs(status);
CREATE INDEX idx_jobs_scheduled ON tenant_abc.jobs(scheduled_date);
CREATE INDEX idx_jobs_customer ON tenant_abc.jobs(customer_contact_id);
CREATE INDEX idx_jobs_property ON tenant_abc.jobs(property_id);
CREATE INDEX idx_jobs_archived ON tenant_abc.jobs(archived_at) WHERE archived_at IS NULL;
```

### 17.2 Index Strategy

The system automatically creates indexes for:

- **Primary key** â€” On `id` (inherent from PK constraint)
- **Tenant isolation** â€” On `tenant_id`
- **Active record filter** â€” Partial index on `archived_at IS NULL`
- **Relation FK columns** â€” On every relation (single) field
- **Select fields** â€” On every select (single) and select (multi) field (for Board view and filter performance)
- **Date/Datetime fields** â€” On every date and datetime field (for Calendar/Timeline view and date range filters)

Additional indexes can be created by the system based on query patterns observed in Data Source execution (Phase 3 â€” automatic index recommendation).

### 17.3 Virtual Schema Mapping

The Data Sources PRD defines a virtual schema that users write SQL against. With dedicated tables and field slug = column name, the virtual-to-physical mapping is nearly 1:1:

| Virtual Schema | Physical Schema |
|---|---|
| `SELECT name, price, status FROM Jobs` | `SELECT name, price, status FROM tenant_abc.jobs WHERE archived_at IS NULL` |
| `Jobs.customer â†’ Contacts.display_name` | `JOIN tenant_abc.contacts ON jobs.customer_contact_id = contacts.id` |

The query engine adds tenant isolation (`WHERE tenant_id = ?`), archived record filtering (`WHERE archived_at IS NULL`), and permission injection. But the core translation is trivial â€” field slugs ARE column names, and object type slugs ARE table names.

---

## 18. DDL Management System

Creating entity types, adding fields, and defining relations trigger database schema operations (DDL). These operations are managed through a controlled, safe execution system.

### 18.1 DDL Operations Catalog

| User Action | DDL Operation(s) |
|---|---|
| Create entity type | `CREATE TABLE` (read model) + `CREATE TABLE` (event table) + system indexes |
| Add field | `ALTER TABLE ADD COLUMN` + optional index creation |
| Archive field | `ALTER TABLE` (rename column to `_archived_{slug}`, or logical archive with metadata update) |
| Convert field type | `ALTER TABLE ALTER COLUMN TYPE` |
| Create relation (1:1, 1:many) | `ALTER TABLE ADD COLUMN` (FK column) + index + optional relation instance table |
| Create relation (many:many) | `CREATE TABLE` (junction table) + indexes |
| Add relation metadata field | `ALTER TABLE ADD COLUMN` on junction/instance table |

### 18.2 Execution Model

DDL operations are:

1. **Validated** â€” The system checks that the operation is structurally valid (valid column types, no name collisions, within field limits, etc.)
2. **Queued** â€” Operations are placed in a per-tenant DDL queue to serialize schema changes and prevent concurrent DDL conflicts
3. **Executed** â€” The DDL statement runs within a transaction. If it fails, the transaction is rolled back and the user is notified with an error.
4. **Recorded** â€” Successful DDL operations are logged in a `ddl_audit_log` table (who, what, when, tenant, object type)
5. **Propagated** â€” The object type's `schema_version` is incremented, and dependent data sources and views are notified of the schema change

### 18.3 Locking Strategy

PostgreSQL DDL statements acquire locks. For `ALTER TABLE ADD COLUMN` with a NULL default and no NOT NULL constraint, PostgreSQL (11+) performs this as a metadata-only operation that does not rewrite the table and acquires only a brief `ACCESS EXCLUSIVE` lock. This is fast and safe for concurrent reads.

For type conversions (`ALTER TABLE ALTER COLUMN TYPE`), PostgreSQL must rewrite the column, which acquires a longer lock. The DDL management system:

- Warns the user that a type conversion on a table with >10,000 records may cause brief read delays
- Executes type conversions during low-traffic periods if the table is large (configurable threshold)
- Uses `LOCK_TIMEOUT` to fail fast if the lock cannot be acquired within a reasonable window (5 seconds), retrying with backoff

### 18.4 Rollback

If a DDL operation fails mid-execution (e.g., disk full, lock timeout), the transaction ensures the schema is unchanged. The operation status is updated to `failed` with the error message, and the user is notified.

The DDL audit log records both successful and failed operations, providing a complete history of schema changes per tenant.

---

## 19. Event Sourcing

Every entity type (system and custom) has a companion event table that records all field-level mutations as immutable events.

### 19.1 Event Table Structure

For each entity type with slug `{slug}`, the event table is `{slug}_events`:

```sql
CREATE TABLE tenant_abc.jobs_events (
    event_id TEXT PRIMARY KEY,         -- evt_ prefixed ULID
    record_id TEXT NOT NULL,           -- FK â†’ jobs(id)
    event_type TEXT NOT NULL,          -- See event types below
    field_slug TEXT,                   -- Which field changed (NULL for record-level events)
    old_value TEXT,                    -- Previous value (serialized as text)
    new_value TEXT,                    -- New value (serialized as text)
    metadata JSONB,                   -- Additional context (e.g., source, relation details)
    user_id TEXT,                      -- Who triggered the change
    source TEXT,                       -- How the change occurred: 'api', 'ui', 'import', 'automation', 'enrichment'
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_jobs_events_record ON tenant_abc.jobs_events(record_id, created_at);
CREATE INDEX idx_jobs_events_type ON tenant_abc.jobs_events(event_type);
```

### 19.2 Event Types

| Event Type | Field Slug | Description |
|---|---|---|
| `record_created` | NULL | Record was created. `new_value` contains the initial field values as JSON. |
| `field_updated` | The changed field | A single field was updated. `old_value` and `new_value` contain the field's previous and new values. |
| `record_archived` | NULL | Record was soft-deleted. `archived_at` set. |
| `record_unarchived` | NULL | Record was restored from archive. `archived_at` cleared. |
| `relation_linked` | Relation field slug | A relation was established. `new_value` contains the target record ID. `metadata` contains relation type ID. |
| `relation_unlinked` | Relation field slug | A relation was removed. `old_value` contains the former target record ID. |
| `relation_metadata_updated` | NULL | Metadata on a relation instance changed. `metadata` contains relation_type_id, target_id, field_slug, old_value, new_value. |
| `bulk_update` | NULL | Multiple fields updated in a single operation. `metadata` contains the field-level changes as JSON. |

### 19.3 Write Path

On every record mutation:

1. The event is appended to the event table (insert)
2. The read model table is synchronously updated (update)
3. Both operations occur within a single database transaction
4. If either fails, the transaction rolls back â€” no partial writes

This ensures the read model always reflects the complete event history. The read model is a performance optimization, not the source of truth â€” the event table is the source of truth.

### 19.4 Point-in-Time Reconstruction

To reconstruct a record's state at any historical timestamp:

1. Query the event table for all events on that record with `created_at <= target_timestamp`
2. Order by `created_at ASC`
3. Replay events from `record_created` forward, applying each `field_updated` event
4. The resulting state is the record as it appeared at that point in time

For performance, the system maintains **snapshots** at configurable intervals (e.g., every 100 events per record, or weekly). Reconstruction replays from the nearest prior snapshot rather than from the initial creation event.

### 19.5 Audit Trail UI

Every record's detail view includes an "History" tab that renders the event stream as a human-readable timeline:

```
Feb 17, 2026 2:30 PM â€” Sam updated Status
  scheduled â†’ in_progress

Feb 17, 2026 9:00 AM â€” Sam updated Scheduled Date
  (empty) â†’ Feb 20, 2026

Feb 16, 2026 4:15 PM â€” Sam updated Price
  $200.00 â†’ $250.00

Feb 16, 2026 3:00 PM â€” Sam created this Job
  Name: "Smith Residence Gutter Clean"
  Service Type: Full Clean
  Price: $200.00
  Status: Estimated
```

---

## 20. Object Type Lifecycle

### 20.1 Creation

1. User with Object Creator permission defines: name, description, icon
2. System generates slug (from name, lowercased, underscored) and type prefix
3. System validates: slug uniqueness within tenant, prefix uniqueness globally, field limit not exceeded
4. DDL Management System creates: read model table, event table, system indexes
5. System creates default `name` field (Text, required) and designates it as display name field
6. System creates system-generated Data Source for the new entity type (per Data Sources PRD Section 21)
7. Object type appears in entity type pickers throughout the platform

### 20.2 Modification

- **Rename (display name):** Immediate metadata update. No DDL.
- **Change description/icon:** Immediate metadata update. No DDL.
- **Add field:** DDL operation (ALTER TABLE ADD COLUMN). Schema version incremented.
- **Archive field:** Field hidden from UI. Column data preserved. Schema version incremented.
- **Add/modify/remove field group:** Metadata update only. No DDL.
- **Change display name field:** Metadata update. No DDL.

### 20.3 Archiving

Custom entity types can be archived (soft-deleted). System entity types cannot.

**Archive behavior:**

1. Object type's `is_archived` flag is set to true
2. The entity type is hidden from: entity type pickers, Data Source entity selectors, View creation, record creation forms
3. Existing views and data sources that reference this entity type continue to work but display a warning badge: "This entity type is archived"
4. The database tables and data are preserved intact
5. New records cannot be created for an archived entity type
6. Existing records can still be viewed and searched
7. The object type counts against the per-tenant limit (to prevent archive/create cycling)

### 20.4 Unarchiving

Archived custom entity types can be restored to active status:

1. Object type's `is_archived` flag is set to false
2. The entity type reappears in all pickers and selectors
3. Warning badges on dependent views and data sources are removed
4. Record creation is re-enabled

---

## 21. Field Lifecycle

### 21.1 Creation

1. User defines: display name, field type, type config, required flag, default value, validation rules, field group
2. System generates slug from display name (lowercased, underscored, validated)
3. System validates: slug uniqueness within object type, field limit not exceeded, valid type config
4. DDL Management System executes: `ALTER TABLE ADD COLUMN {slug} {pg_type}`
5. If `is_required` and no `default_value`: only applies to future records (existing records have NULL)
6. Schema version on the object type is incremented
7. Field appears in Views field picker, Data Source column registry, and record forms

### 21.2 Modification

- **Rename (display name):** Immediate. No DDL.
- **Change description:** Immediate. No DDL.
- **Change required flag:** Immediate. If enabling required: warning about existing NULL values.
- **Change default value:** Immediate. Applies to future records only.
- **Change validation rules:** Immediate. Applies to future writes only. Existing values are not retroactively validated.
- **Change field group:** Immediate. No DDL.
- **Change display order:** Immediate. No DDL.
- **Convert field type:** DDL operation with data conversion (see Section 10).

### 21.3 Archiving

Fields can be archived (soft-deleted):

1. Field's `is_archived` flag is set to true
2. Field is hidden from: Views field picker, Data Source visual builder column selector, record forms
3. **The physical column and data are preserved.** No DDL operation.
4. Existing views that display this field show a warning: "This field is archived"
5. Data sources using raw SQL can still query the column
6. The field can be unarchived at any time, restoring full visibility

System fields on system entity types (`is_system = true`) cannot be archived.

### 21.4 Deletion

Field deletion is not supported. Fields can only be archived. This aligns with the event sourcing philosophy: data is never destroyed, and the historical event stream remains valid (events reference field slugs that must remain meaningful).

If a tenant needs to reclaim the field slot (approaching the 200-field limit), archived fields do not count toward the limit â€” they are excluded from the active field count.

---

## 22. System Entity Specialization

System object types are instances of the unified framework with two additional capabilities that custom object types do not have:

### 22.1 Behaviors

A behavior is a registered piece of specialized logic that the platform executes in response to events on a specific system entity type. Behaviors are defined in their respective PRDs and registered with the object type framework.

| System Entity | Behavior | Source PRD | Trigger |
|---|---|---|---|
| Contact | Identity resolution | Contact Management PRD | On creation, on identifier change |
| Contact | Auto-enrichment | Contact Management PRD | On creation, on schedule |
| Contact | Engagement score computation | Contact Management PRD | On communication event |
| Contact | Intelligence score computation | Contact Management PRD | On enrichment, on field update |
| Company | Firmographic enrichment | Contact Management PRD | On creation, on schedule |
| Conversation | AI status detection | Communication PRD | On new communication |
| Conversation | Summarization | Communication PRD | On new communication, on demand |
| Conversation | Action item extraction | Communication PRD | On new communication |
| Communication | Email parsing & content extraction | Communication PRD | On sync |
| Communication | Segmentation | Communication PRD | On creation |
| Project | Topic aggregation | Communication PRD | On topic change |
| Topic | Conversation aggregation | Communication PRD | On conversation change |
| Event | Attendee resolution | Event Management PRD | On sync, on manual participant add |
| Event | Birthday auto-generation | Event Management PRD | On contact birthday field update |
| Event | Recurrence defaulting | Event Management PRD | On creation with type birthday or anniversary |
| Note | Revision management | Notes PRD | On content save |
| Note | FTS sync | Notes PRD | On content save, on delete |
| Note | Mention extraction | Notes PRD | On content save |
| Note | Orphan attachment cleanup | Notes PRD | On schedule (background job) |
| Note | Visibility enforcement | Notes PRD | On query |
| Task | Status category enforcement | Tasks PRD | On status change |
| Task | Subtask cascade (warn) | Tasks PRD | On parent status → done category |
| Task | Subtask count sync | Tasks PRD | On child task create, archive, status change |
| Task | Recurrence generation | Tasks PRD | On task completion (status → done) |
| Task | AI action-item extraction | Tasks PRD | On Conversation intelligence event |
| Task | Due date reminder scheduling | Tasks PRD | On task create, on due_date change |
| Task | Overdue detection | Tasks PRD | Periodic (background job) |

### 22.2 Protected Core Fields

System entity types have core fields marked `is_system = true`. These fields cannot be:

- Archived or deleted
- Have their type converted
- Have their slug changed

They can have their display name changed and their validation rules adjusted (for example, a tenant could make `phone_primary` required on Contacts even though it's optional by default).

### 22.3 Extensibility

Users can add custom fields to system entity types through the same field registry mechanism used for custom entity types. These user-added fields are stored as additional columns on the system entity's table and participate fully in views, data sources, filters, and event sourcing.

---

## 23. API Design

### 23.1 Object Type Management API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/object-types` | GET | List all object types (system + custom, active only by default) |
| `/api/v1/object-types` | POST | Create a custom object type |
| `/api/v1/object-types/{slug}` | GET | Get object type definition with full field registry |
| `/api/v1/object-types/{slug}` | PATCH | Update object type metadata (name, description, icon, display_name_field) |
| `/api/v1/object-types/{slug}/archive` | POST | Archive a custom object type |
| `/api/v1/object-types/{slug}/unarchive` | POST | Unarchive a custom object type |

### 23.2 Field Management API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/object-types/{slug}/fields` | GET | List all fields on an object type |
| `/api/v1/object-types/{slug}/fields` | POST | Add a field to an object type |
| `/api/v1/object-types/{slug}/fields/{field_slug}` | GET | Get field definition |
| `/api/v1/object-types/{slug}/fields/{field_slug}` | PATCH | Update field metadata (name, description, required, default, validation, group, order) |
| `/api/v1/object-types/{slug}/fields/{field_slug}/convert` | POST | Convert field type (with preview) |
| `/api/v1/object-types/{slug}/fields/{field_slug}/archive` | POST | Archive a field |
| `/api/v1/object-types/{slug}/fields/{field_slug}/unarchive` | POST | Unarchive a field |

### 23.3 Relation Type Management API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/relation-types` | GET | List all relation types |
| `/api/v1/relation-types` | POST | Create a relation type |
| `/api/v1/relation-types/{id}` | GET | Get relation type definition |
| `/api/v1/relation-types/{id}` | PATCH | Update relation type metadata |
| `/api/v1/relation-types/{id}` | DELETE | Delete a relation type (removes fields from both sides) |

### 23.4 Record CRUD API

Record operations use a uniform pattern for all entity types:

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/{object_type_slug}` | GET | List records (paginated, filterable, sortable) |
| `/api/v1/{object_type_slug}` | POST | Create a record |
| `/api/v1/{object_type_slug}/{id}` | GET | Get a single record |
| `/api/v1/{object_type_slug}/{id}` | PATCH | Update record fields |
| `/api/v1/{object_type_slug}/{id}/archive` | POST | Archive a record |
| `/api/v1/{object_type_slug}/{id}/unarchive` | POST | Unarchive a record |
| `/api/v1/{object_type_slug}/{id}/history` | GET | Get event history for a record |
| `/api/v1/{object_type_slug}/{id}/history?at={timestamp}` | GET | Get record state at a point in time |

### 23.5 Relation Instance API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/{object_type_slug}/{id}/relations/{relation_type_id}` | GET | List related records for a relation type |
| `/api/v1/{object_type_slug}/{id}/relations/{relation_type_id}` | POST | Link a record (create relation instance) |
| `/api/v1/{object_type_slug}/{id}/relations/{relation_type_id}/{target_id}` | DELETE | Unlink a record |
| `/api/v1/{object_type_slug}/{id}/relations/{relation_type_id}/{target_id}` | PATCH | Update relation metadata |

---

## 24. Schema-Per-Tenant Architecture

### 24.1 Tenant Isolation Model

Each tenant gets its own PostgreSQL schema, containing all entity type tables, event tables, and junction tables for that tenant:

```
PostgreSQL Database: crmextender
  â”œâ”€â”€ Schema: platform                  (shared, cross-tenant)
  â”‚     â”œâ”€â”€ object_types                (object type registry)
  â”‚     â”œâ”€â”€ field_definitions           (field registry)
  â”‚     â”œâ”€â”€ field_groups                (field grouping)
  â”‚     â”œâ”€â”€ relation_types              (relation registry)
  â”‚     â”œâ”€â”€ tenants                     (tenant registry)
  â”‚     â””â”€â”€ users                       (user registry)
  â”‚
  â”œâ”€â”€ Schema: tenant_abc                (tenant-specific)
  â”‚     â”œâ”€â”€ contacts                    (Contact read model)
  â”‚     â”œâ”€â”€ contacts_events             (Contact event store)
  â”‚     â”œâ”€â”€ companies                   (Company read model)
  â”‚     â”œâ”€â”€ companies_events            (Company event store)
  â”‚     â”œâ”€â”€ conversations               (Conversation read model)
  â”‚     â”œâ”€â”€ conversations_events        (Conversation event store)
  â”‚     â”œâ”€â”€ jobs                        (custom: Jobs read model)
  â”‚     â”œâ”€â”€ jobs_events                 (custom: Jobs event store)
  â”‚     â”œâ”€â”€ properties                  (custom: Properties read model)
  â”‚     â”œâ”€â”€ properties_events           (custom: Properties event store)
  â”‚     â”œâ”€â”€ jobs__contacts_crew         (junction: Jobs â†” Contacts crew)
  â”‚     â””â”€â”€ ...
  â”‚
  â”œâ”€â”€ Schema: tenant_def                (another tenant)
  â”‚     â”œâ”€â”€ contacts
  â”‚     â”œâ”€â”€ contacts_events
  â”‚     â”œâ”€â”€ deals                       (custom: Deals â€” this tenant, not tenant_abc)
  â”‚     â”œâ”€â”€ deals_events
  â”‚     â””â”€â”€ ...
  â”‚
  â””â”€â”€ Schema: tenant_ghi                ...
```

### 24.2 Tenant Schema Provisioning

When a new tenant is created:

1. A new PostgreSQL schema is created: `tenant_{tenant_id}`
2. System entity tables are created within the schema (contacts, companies, conversations, etc.) with their pre-installed core fields
3. System entity event tables are created
4. System relation types are instantiated (Contactâ†’Company employment, etc.) with their FK columns and junction tables
5. System-generated Data Sources are created for each system entity type

### 24.3 Search Path

The API server sets `search_path` to the tenant's schema on each request, ensuring all queries are automatically scoped to the correct tenant without requiring `tenant_id` in every WHERE clause:

```sql
SET search_path = tenant_abc, platform;
SELECT * FROM jobs WHERE status = 'scheduled';
-- Resolves to tenant_abc.jobs
```

---

## 25. Phasing & Roadmap

### Phase 1 â€” Core Object Framework (MVP)

**Goal:** Users can create custom entity types, define fields, establish relations, and manage records through the same framework as system entities.

**Scope:**

- Object type CRUD (create, rename, archive, unarchive)
- Field registry with all Phase 1 field types (Text, Number, Currency, Date, Datetime, Select, Multi-select, Checkbox, Relation, Email, Phone, URL, Rating, Duration, User)
- Universal fields on all entity types
- Display name field designation
- Field groups for detail view organization
- Field validation (type-specific constraints, required, default values)
- Select option management (add, rename, reorder, archive)
- Relation Types with all three cardinalities (1:1, 1:many, many:many)
- Bidirectional and unidirectional relations
- Self-referential relations
- Cascade behavior (nullify, restrict, cascade archive)
- Dedicated tables per entity type (DDL Management System)
- Full event sourcing (per-entity-type event tables)
- Schema-per-tenant architecture
- Record CRUD API (uniform for all entity types)
- System entity types pre-installed with core fields and protected status
- User-added custom fields on system entities
- Object Creator permission gate
- 50 custom entity type limit per tenant

**Not in Phase 1:** Relation metadata, Neo4j sync, field type conversions, Formula/Rollup fields, automatic index recommendations.

### Phase 2 â€” Relations & Intelligence

**Goal:** Enrich the relation model with metadata and graph intelligence. Add computed field types.

**Scope:**

- Relation metadata (additional attributes on relationship instances)
- Relation metadata in views (traversal columns for metadata fields)
- Neo4j graph sync for system relation types
- Field type conversions (safe conversion matrix with preview wizard)
- Formula fields (computed from other fields on the same record)
- Rollup fields (aggregated from related records)
- Event sourcing snapshots (for point-in-time reconstruction performance)
- Audit trail UI on record detail views

### Phase 3 â€” Graph & Advanced

**Goal:** Full graph intelligence and advanced schema management.

**Scope:**

- Neo4j graph sync for custom relation types
- Graph queries via API (path finding, neighborhood, centrality)
- Automatic index recommendations based on Data Source query patterns
- Object type templates (pre-built entity type definitions for common domains: real estate, consulting, sales)
- Object type duplication (clone an entity type's definition)
- Bulk field operations (add multiple fields at once)

### Phase 4 â€” Platform Maturity

**Goal:** Advanced features for scale and enterprise use cases.

**Scope:**

- Graph queries in Data Sources (Cypher as alternative query mode)
- Graph visualization in Views
- Object type versioning and change history
- Cross-tenant object type sharing (enterprise: shared templates across workspaces)
- Field-level permissions (restrict who can view/edit specific fields)
- Dynamic field limit increases per tenant

---

## 26. Cross-PRD Reconciliation

This PRD establishes the entity model foundation that several existing PRDs reference. The following reconciliation items must be addressed:

### 26.1 Contact Management PRD Updates

| Item | Current State | Required Change |
|---|---|---|
| **`custom_fields` JSONB column** | `contacts_current` has a `custom_fields` TEXT (JSONB) column for tenant-defined custom fields | **Remove.** Custom fields on Contacts are now managed through the unified field registry (Section 8). Each custom field becomes a typed column on the contacts table via ALTER TABLE. |
| **Entity ID format** | Contact IDs use UUID v4 without prefixes | **Migrate to prefixed ULID.** Contact IDs become `con_` prefixed ULIDs per the Data Sources PRD convention (Section 6.3). Migration path: add `con_` prefix to existing UUIDs or re-generate IDs. |
| **`contacts_current` materialized view** | Described as a hand-crafted table with specific typed columns | **Reframe as the Contact object type's dedicated table**, managed through the object type framework. Core columns become system fields (`is_system = true`). The table is created by tenant schema provisioning, not hand-crafted SQL. |
| **Employment history tables** | Separate `employment_history` table | **Reframe as a system relation type** (Contactâ†’Company) with temporal metadata (start_date, end_date, title, department). The relation type has `has_metadata = true`. |
| **Intelligence items** | Separate `contact_intelligence_items` table | Remains as-is â€” intelligence items are a specialized subsystem, not a generic field type. The Contact object type's enrichment behavior (Section 22) manages these. |

### 26.2 Data Sources PRD Alignment

| Item | Current State | Required Change |
|---|---|---|
| **Virtual schema composition** | Defers to Custom Objects PRD for entity type definitions | **Resolved.** Virtual schema tables = object type slugs. Virtual schema columns = field slugs. The mapping is 1:1 (Section 17.3). |
| **Custom entity storage** | Blocked on Custom Objects PRD | **Resolved.** Dedicated tables per entity type. No JSONB, no EAV. Direct column access. |
| **Type prefix registry** | Lists system prefixes, notes custom prefixes are auto-generated | **Confirmed and detailed.** Section 6.2 specifies the generation algorithm, collision handling, and immutability. |

### 26.3 Views & Grid PRD Alignment

| Item | Current State | Required Change |
|---|---|---|
| **Field type registry** | Section 9 defines rendering/filter behavior per field type, notes "field types are defined by the Custom Objects PRD" | **Confirmed.** This PRD (Section 9) defines the data layer; Views PRD Section 9 defines the presentation layer. Both reference the same field type names. |
| **Entity type references** | References "Custom Objects PRD" for entity type definitions | **Resolved.** Entity types, field registries, and relation traversal are fully defined here. |
| **Relation traversal** | Section 10 defines traversal behavior, depends on relation model | **Resolved.** Relation Types (Section 14) provide the model. Bidirectional relations enable traversal from either side. Unidirectional relations enable traversal only from source to target. |

### 26.4 Communication PRD Alignment

| Item | Current State | Required Change |
|---|---|---|
| **Conversation, Communication, Project, Topic entities** | Defined with dedicated schemas | **Reframe as system object types** in the unified framework. Their tables are created by tenant schema provisioning. Specialized behaviors (AI classification, parsing) are registered per Section 22. |

---

## 27. Dependencies & Related PRDs

| PRD | Relationship | Dependency Direction |
|---|---|---|
| **Views & Grid PRD** | Views consume the field registry for column rendering, filter operators, sort behavior, and inline editing. The view system is entity-agnostic because this PRD provides a uniform entity model. | **Views depend on Custom Objects** for entity type definitions, field types, and relation model. |
| **Data Sources PRD** | Data sources query the virtual schema derived from object type field registries. The prefixed entity ID convention enables automatic entity detection. Cross-entity JOINs traverse relation types defined here. | **Data Sources depend on Custom Objects** for entity type definitions, field registries, virtual schema, and relation metadata. |
| **Contact Management PRD** | The Contact and Company entity types are pre-installed system object types. Custom fields on Contacts, identity resolution, enrichment, and relationship intelligence are built on the object type framework. | **Bidirectional.** Contact Management defines the Contact entity's specialized behaviors; Custom Objects provides the entity framework those behaviors operate within. |
| **Communication PRD** | Conversation, Communication, Project, and Topic entity types are pre-installed system object types. Specialized AI behaviors are registered with the object type framework. | **Bidirectional.** Communication PRD defines entity behaviors; Custom Objects provides the framework. |
| **Event Management PRD** | The Event entity type is a pre-installed system object type. Calendar sync, attendee resolution, birthday auto-generation, and recurrence are built on the object type framework. | **Bidirectional.** Event Management PRD defines Event-specific behaviors; Custom Objects provides the framework. |
| **Notes PRD** | The Note entity type is a pre-installed system object type. Introduces the Universal Attachment Relation pattern (target = *) extending the relation type model with polymorphic targets. | **Bidirectional.** Notes PRD defines Note-specific behaviors and Universal Attachment pattern; Custom Objects provides the framework. |
| **Tasks PRD** | The Task entity type is a pre-installed system object type. Reuses the Universal Attachment pattern from Notes. Defines status category model, subtask hierarchy, dependencies, recurrence, and AI action-item extraction behaviors. | **Bidirectional.** Tasks PRD defines Task-specific behaviors; Custom Objects provides the framework. |
| **Permissions & Sharing PRD** | The Object Creator permission, field-level permissions (Phase 4), and row-level security on entity records depend on the permissions model. | **Custom Objects depend on Permissions** for access control on entity types, fields, and records. |
| **AI Learning & Classification PRD** | AI classification operates on entity records. Custom entity types with select fields could benefit from auto-classification (Phase 3+). | **AI depends on Custom Objects** for entity type awareness. |

---

## 28. Open Questions

1. **DDL execution during high-traffic periods** â€” Should the system automatically defer non-urgent DDL operations (field additions on large tables) to off-peak hours? Or is the brief `ACCESS EXCLUSIVE` lock on metadata-only operations acceptable at any time? PostgreSQL 11+'s instant ADD COLUMN mitigates this, but type conversions are more impactful.

2. **Field slug reserved words** â€” The current approach validates slugs against PostgreSQL reserved words. Should the system also reserve application-level keywords (e.g., `type`, `class`, `status` â€” words that might conflict with framework internals)?

3. **Custom entity record limit per tenant** â€” Should there be a per-entity-type or per-tenant record count limit? At the target scale (low thousands per entity type), this is unlikely to be an issue, but enterprise tenants might push boundaries.

4. **Cross-entity-type field templates** â€” If multiple entity types need the same field (e.g., `address` with identical validation), should there be a field template system to define once and apply to many entity types? Or is copy-paste sufficient?

5. **Entity type import/export** â€” Should entity type definitions (fields, relations, groups) be exportable as JSON and importable into another tenant? This would enable template sharing and environment replication (dev â†’ staging â†’ production).

6. **Relation type limits** â€” Should there be a limit on the number of relation types per entity type or per tenant? With dedicated tables for junction tables, many-to-many relations create additional schema objects.

7. **Event store retention policy** â€” For high-volume custom entities (thousands of records Ã— frequent updates), the event table can grow large. Should there be a configurable retention policy (e.g., keep events for 2 years, then compact to snapshots)? Or is unbounded retention acceptable at the target scale?

8. **Multi-line text storage** â€” Should multi-line text fields have a separate storage strategy (e.g., TOAST-optimized) for very long values, or is standard TEXT column storage sufficient?

9. **Offline SQLite sync for custom entities** â€” The Contact Management PRD mentions SQLite for offline read access. Should custom entity types also sync to SQLite on mobile/desktop clients? If so, the DDL system needs to generate SQLite-compatible schemas.

10. **Computed default values** â€” Should default values support expressions (e.g., `TODAY()`, `CURRENT_USER()`) in addition to static values? This adds complexity but enables useful patterns like auto-setting a date field to today on record creation.

11. **Relation Type modification** â€” Can a relation type's cardinality or directionality be changed after creation? Changing cardinality (e.g., 1:many â†’ many:many) has significant DDL implications (adding a junction table, migrating FK data). Recommendation: block cardinality changes; require creating a new relation type and migrating data.

12. **Neo4j sync selective fields** â€” When syncing entity records to Neo4j as nodes, which fields are included as node properties? All fields? Only the display name? A user-configurable subset? Including all fields increases sync overhead but enables richer graph queries.

---

## 29. Glossary

| Term | Definition |
|---|---|
| **Object Type** | A named definition of an entity class â€” its identity, fields, relations, and behaviors. Both system entities (Contact, Conversation) and user-created entities (Jobs, Properties) are object types. |
| **System Object Type** | A pre-installed object type that ships with the platform. Cannot be deleted. Core fields are protected. May have registered behaviors. |
| **Custom Object Type** | A user-created object type. Same capabilities as system object types except behaviors. Can be archived. Subject to per-tenant limit. |
| **Field** | A named, typed attribute on an object type. Maps to a physical column on the entity type's database table. |
| **Field Registry** | The ordered set of field definitions on an object type. The authoritative source for what data an entity type captures. |
| **Field Group** | A named grouping of fields for organizing the record detail view layout. Purely presentational. |
| **Field Type** | The data type of a field (text, number, date, select, relation, etc.). Determines storage type, validation, rendering, and filter behavior. |
| **Field Slug** | The immutable machine name of a field, used as the physical column name and virtual schema identifier. |
| **Display Name Field** | The field designated as the record's human-readable title throughout the platform (views, previews, pickers, cards). |
| **Type Prefix** | A 3â€“4 character immutable identifier for an object type, prepended to entity IDs (e.g., `con_`, `job_`). Enables automatic entity type detection from any ID value. |
| **Relation Type** | A first-class definition of a relationship between two object types. Specifies cardinality, directionality, cascade behavior, metadata fields, and Neo4j sync configuration. |
| **Relation Metadata** | Additional attributes stored on a relationship instance (e.g., role, strength, start date). |
| **Cardinality** | The multiplicity of a relation: one-to-one, one-to-many, or many-to-many. |
| **Directionality** | Whether a relation creates navigable fields on one side (unidirectional) or both sides (bidirectional). |
| **Cascade Behavior** | What happens to referencing records when a referenced record is archived: nullify (clear the link), restrict (block the archive), or cascade archive (archive referencing records too). |
| **Junction Table** | A database table that implements a many-to-many relation by storing pairs of entity IDs (and optional metadata columns). |
| **Behavior** | A registered piece of specialized logic on a system object type (e.g., identity resolution on Contact, AI status detection on Conversation). Custom object types do not have behaviors. |
| **DDL Operation** | A database schema change (CREATE TABLE, ALTER TABLE, etc.) triggered by user actions in the object type framework. |
| **DDL Management System** | The platform component that validates, queues, executes, and audits DDL operations triggered by entity type and field changes. |
| **Schema Version** | A counter on the object type that increments when the field registry changes in ways that affect the column set. Used by Data Sources to detect breaking changes. |
| **Schema-Per-Tenant** | The multi-tenant isolation model where each tenant gets its own PostgreSQL schema containing entity tables, event tables, and junction tables. |
| **Event Sourcing** | The data architecture where all field-level mutations are stored as immutable events. The entity table is a read-optimized materialized view derived from the event stream. |
| **Read Model** | The entity type's dedicated table, containing current-state data for fast reads. Updated synchronously on every event. |
| **Event Table** | The companion table storing immutable events for an entity type. The source of truth for the entity's complete history. |
| **Snapshot** | A periodically stored copy of a record's full state at a point in time, used to accelerate point-in-time reconstruction by avoiding full event replay. |
| **Object Creator** | A permission that allows a user to create custom object types. Not restricted to administrators. |
| **Universal Fields** | The set of fields present on every entity type (id, tenant_id, created_at, updated_at, created_by, updated_by, archived_at). Managed by the framework, not user-configurable. |
| **Safe Conversion** | A field type change that preserves data without loss (e.g., Number â†’ Currency). Only safe conversions are allowed. |
| **Relation Instance** | A single link between two records via a relation type. For many-to-many relations, stored as a row in the junction table. For 1:1/1:many with metadata, stored in a companion instance table. |

---

## Related PRDs

| Document | Relationship |
|---|---|
| [CRMExtender PRD v1.1](PRD.md) | Parent document defining system architecture, phasing, and all feature areas |
| [Views & Grid PRD](views-grid-prd_V3.md) | Consumes entity type definitions and field registry for view rendering |
| [Data Sources PRD](data-sources-prd.md) | Consumes entity type definitions for virtual schema and query engine |
| [Contact Management PRD](contact-management-prd.md) | Contact and Company are system object types managed by this framework |
| [Communication & Conversation Intelligence PRD](email-conversations-prd.md) | Conversation, Communication, Project, Topic are system object types |
| [Email Parsing & Content Extraction](email_stripping.md) | Technical spec for Communication entity's parsing behavior |

---

*This document is a living specification. As implementation progresses and as the Permissions & Sharing PRD and AI Learning & Classification PRD are developed, sections will be updated to reflect design decisions, scope adjustments, and lessons learned. Implementation-level decisions (DDL execution infrastructure, Neo4j sync mechanics, snapshot intervals) are documented separately in architecture decision records and the codebase.*
