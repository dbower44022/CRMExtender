The Conversation View PRD defines two viewing modes for conversation records:                                                                                                                                        

1. Preview Card (quick scan in detail panel) — timeline-first, most-recent-first, with participant color coding

2. Full View (deep reading) — responsive 1-or-2-column layout with timeline + CRM intelligence sidebar
   
   It covers 10 major areas with a total of ~60 tasks and ~100 tests:
   
   ┌─────────┬───────────────────────────────────────────────────────┬───────┬───────┐
   │ Section │                         Area                          │ Tasks │ Tests │
   ├─────────┼───────────────────────────────────────────────────────┼───────┼───────┤
   │ 4       │ Preview Card (standard + aggregate + color coding)    │ 7     │ 13    │
   ├─────────┼───────────────────────────────────────────────────────┼───────┼───────┤
   │ 5       │ Responsive Layout (1/2-col, dynamic sizing, splitter) │ 9     │ 16    │
   ├─────────┼───────────────────────────────────────────────────────┼───────┼───────┤
   │ 6       │ Identity Card                                         │ 4     │ 6     │
   ├─────────┼───────────────────────────────────────────────────────┼───────┼───────┤
   │ 7       │ Timeline Card (entries, order, navigation, color)     │ 14    │ 20    │
   ├─────────┼───────────────────────────────────────────────────────┼───────┼───────┤
   │ 8       │ Participants Card                                     │ 6     │ 10    │
   ├─────────┼───────────────────────────────────────────────────────┼───────┼───────┤
   │ 9       │ AI Intelligence Card                                  │ 7     │ 7     │
   ├─────────┼───────────────────────────────────────────────────────┼───────┼───────┤
   │ 10      │ Entity Associations Card                              │ 4     │ 7     │
   ├─────────┼───────────────────────────────────────────────────────┼───────┼───────┤
   │ 11      │ Children Card (aggregates)                            │ 5     │ 8     │
   ├─────────┼───────────────────────────────────────────────────────┼───────┼───────┤
   │ 12      │ Notes Card                                            │ 3     │ 5     │
   ├─────────┼───────────────────────────────────────────────────────┼───────┼───────┤
   │ 13      │ Metadata Card                                         │ 4     │ 5     │
   └─────────┴───────────────────────────────────────────────────────┴───────┴───────┘
   
   ---
   
   Proposed Implementation Phases
   
   Here's how I'd organize this into logical implementation phases, ordered by dependencies:
   
   Phase 1: API Foundation + Participant Color System
- Build the backend API endpoints needed to serve preview/full view data (conversation detail, communications with cleaned_html, participants with counts, associations)

- Implement the participant color coding system (deterministic palette from contact ID, fixed owner tint) — it's shared by Preview Card and Timeline Card

- Tasks: New API endpoints, color utility module

- Tests: API response shape, color determinism, owner fixed tint
  
  Phase 2: Preview Card — Standard Conversations

- CNVP-01, CNVP-04, CNVP-05, CNVP-06, CNVP-07

- Header (subject, statuses, count, channel breakdown)

- Timeline entries with cleaned_html, participant colors, most-recent-first

- Tests: CNVP-T01 through T06, T11–T13
  
  Phase 3: Preview Card — Aggregate Conversations

- CNVP-02, CNVP-03

- Child conversation entries sorted by last activity

- Direct Communications group at bottom

- Tests: CNVP-T07 through T10
  
  Phase 4: Full View Layout + Identity Card

- CNVL-01 through CNVL-09 (responsive layout, dynamic sizing, splitter, persist)

- CNVI-01 through CNVI-04 (Identity Card)

- Two-column at ≥700px, independent scrolling, CRM sidebar styling

- Tests: CNVL-T01 through T16, CNVI-T01 through T06
  
  Phase 5: Timeline Card

- CNVT-01 through CNVT-14

- Chronological entries with cleaned_html, order preference + toggle

- Attachment/segment indicators

- Double-click → Communication in Undocked Window, keyboard nav

- Tests: CNVT-T01 through T20
  
  Phase 6: CRM Intelligence Cards

- Participants Card (CNVP-01 through 06) — roster, counts, ordering, overflow, color swatches

- AI Intelligence Card (CNVA-01 through 07) — summary, action items, topics, edit/regenerate

- Tests: CNVP-T01 through T10, CNVA-T01 through T07
  
  Phase 7: Remaining Cards + Settings

- Entity Associations Card (CNVE-01 through 04) — grouped associations, + Link picker

- Children Card (CNVC-01 through 05) — aggregate children, + Add

- Notes Card (CNVN-01 through 03)

- Metadata Card (CNVM-01 through 04) — collapsed default, event history

- Timeline order user setting (Section 15)

- Tests: remaining ~25 tests
  
  ---
  
  Key Dependencies

- Phase 1 (API + colors) underpins everything

- Phase 2-3 (Preview Card) can proceed in parallel with Phase 4 (Layout)

- Phase 5 (Timeline) depends on Phase 4 (Layout) and Phase 1 (colors)

- Phase 6-7 (CRM cards) depend on Phase 4 (Layout)
  
  How does this phasing look to you? Want to adjust the grouping, reorder priorities, or break any phase down further?
