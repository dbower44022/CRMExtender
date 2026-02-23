# [Product Name] — Product TDD

**Version:** [X.X]
**Last Updated:** [YYYY-MM-DD]
**Status:** [Draft | Review | Approved]

---

## 1. Overview

[Brief description of this document's scope. The Product TDD captures global technology and architecture decisions that apply across the entire system. Entity or action-specific decisions belong in their own TDDs. When an entity TDD is silent on a topic, the decisions in this document apply as defaults.]

This is a living document. Decisions are recorded here as they are made — both by the product/architecture owner and by Claude Code during implementation. Each decision includes rationale so that future sessions can understand why a choice was made without re-deriving it.

**Current state:** [Brief description of where the product is in development — e.g., "active development with a working system (vN schema, N tables, N tests)" or "greenfield, no code yet." This helps Claude Code calibrate its decisions.]

---

## 2. Language & Framework

### 2.1 [Backend Decision]

**Decision:** [Language, framework, server.]

**Rationale:** [Why this stack.]

**Alternatives Rejected:**
- [Alternative] — [Why rejected.]

**Constraints/Tradeoffs:** [What limitations were accepted.]

### 2.2 [Frontend Decision]

**Decision:** [Framework, language, styling, build tool.]

**Rationale:** [Why this stack.]

**Key libraries:**

| Library | Purpose |
| --- | --- |
| [Library] | [Purpose] |

---

## 3. Data Storage

### 3.1 [Primary Database]

**Decision:** [Database engine(s) and rationale.]

**Rationale:** [Why this choice.]

**Alternatives Rejected:**
- [Alternative] — [Why rejected.]

**Constraints/Tradeoffs:** [What limitations were accepted.]

### 3.2 [Compatibility / Migration Strategy]

[If multiple database engines are involved, document the compatibility approach.]

### 3.3 [Supplementary Storage]

[Graph databases, search engines, caching layers, offline storage — each as a separate decision entry.]

---

## 4. API Design

### 4.1 [API Pattern]

**Decision:** [REST, GraphQL, RPC — the primary API pattern and conventions.]

**Rationale:** [Why this approach.]

[Document URL structure, naming conventions, pagination, error format, and similar cross-cutting API decisions.]

---

## 5. Authentication & Security

### 5.1 [Auth Strategy]

**Decision:** [Session-based, JWT, OAuth — the authentication approach.]

**Rationale:** [Why this approach.]

[Document session management, CSRF protection, password handling, and similar security decisions.]

---

## 6. AI Integration

### 6.1 [AI Provider & Usage]

**Decision:** [Which AI provider(s), which models, how they're used.]

**Rationale:** [Why this approach.]

[Document prompt patterns, token management, fallback strategies, and cost considerations.]

---

## 7. External Integrations

### 7.1 [Integration Pattern]

**Decision:** [How external services (email providers, calendar APIs, enrichment services) are integrated.]

[Document the adapter pattern, credential management, rate limiting, error handling.]

---

## 8. Frontend Architecture Patterns

### 8.1 [State Management]

**Decision:** [State management approach and store architecture.]

### 8.2 [Component Architecture]

**Decision:** [Component organization, layout patterns, data fetching approach.]

[Document routing, code splitting, and other frontend architectural decisions.]

---

## 9. Testing

### 9.1 [Testing Strategy]

**Decision:** [Testing framework, coverage expectations, test organization.]

[Document unit test patterns, integration test approach, fixture management.]

---

## 10. Configuration

### 10.1 [Configuration Approach]

**Decision:** [How configuration is managed — environment variables, config files, cascade.]

[Document the settings hierarchy, secrets management, environment-specific overrides.]

---

## 11. Design Principles

These principles apply globally across all entity TDDs and implementation work. They are not suggestions — they are constraints that Claude Code must follow.

### 11.1 [Principle Name]

[Concise statement of the principle and its practical implications for implementation.]

### 11.2 [Principle Name]

[Add principles as needed. Common examples: display speed priorities, idempotent writes, schema compatibility, editability rules, sort performance awareness, correction capture.]

---

## 12. Project Structure

```
[Directory tree showing the major directories and key files. This helps Claude Code navigate the codebase and place new files correctly.]
```

---

## 13. Production Data Profile

[Current production metrics for performance benchmarking and capacity planning. Update periodically.]

| Metric | Value |
| --- | --- |
| [Metric] | [Value] |

---

## [N]. [Additional Categories]

[Add categories as needed. Common additions: background processing, deployment infrastructure, monitoring/observability, CI/CD, caching strategy. Each follows the same decision format.]
