# HospitalSuite v2 — Master Rebuild Specification & Prompt Set

**Purpose:** This is a phased build prompt for rebuilding HospitalSuite from the ground up, engineered specifically so the 87 findings (F-001–F-087) from the full architecture, security, workflow, AI, accessibility, and visual-design audit of the current codebase cannot recur — not patched after the fact, but structurally prevented by how each phase is built.

**How to use this document:** Each phase below is written as a self-contained prompt. Feed one phase at a time to an AI coding agent (or hand to a developer as a sprint brief), in order — later phases assume earlier ones are done. Every phase ends with **Acceptance Criteria** (testable, not aspirational) and **Findings Addressed** (the specific audit findings this phase exists to prevent, by ID). Section 11 is a full traceability table proving all 87 findings are accounted for somewhere in this spec — if a future reviewer can't find a finding ID anywhere in this document, that is a real gap, not an oversight to wave away.

**What "premium+++++" means here, concretely, not as marketing language:** every patient sees an honest, accurate wait time; every staff action is auditable and cannot exceed the actor's own privilege; every message is sent exactly once; the product looks and is branded the same everywhere a person encounters it; and every claim this document or the resulting product makes about itself (test coverage, security posture, department coverage) is independently verifiable, not self-reported.

---

## Phase 0 — Constitution: Non-Negotiable Principles

Before any code is written, these rules are fixed. Every later phase is graded against them. An AI agent or developer picking up any future phase must re-read this section first.

1. **No feature ships without its failure mode being named.** For every write path, state on paper: what happens if this runs twice concurrently? What happens if the actor has less privilege than the action implies? What happens if the network call it depends on times out? (Directly answers the root cause of F-064, F-046/F-068, and the various silent-`except`-pass patterns found throughout the original codebase.)
2. **Privilege can only ever move downward through delegation.** A user or role may never be able to grant, to anyone including themselves, a permission they do not already hold. This is enforced at the function that mutates permissions, not just at the route decorator layer, and is covered by a test that specifically tries to break it. (Prevents F-046/F-068 by construction, not by review.)
3. **Every shared identifier that survives a redeploy is either a random capability token or has an explicit authorization check — never both trusted implicitly.** A "reference number," "code," or "ID" in a URL is not a secret. If a lookup by that identifier returns personal data, the lookup also verifies a second factor the requester should independently know (phone number, session ownership, or a random unguessable token). (Prevents F-028, F-049, F-066.)
5. **Rate limiting is keyed to the actual distinguishable actor, never blindly to source IP.** Before writing a `@rate_limit` decorator, ask "could many legitimate, unrelated users share this IP?" (mobile carriers, USSD gateways, corporate NAT, proxies). If yes, key on a real per-user identifier from the payload instead or in addition. (Prevents F-077.)
6. **One knowledge base, one design system, one product identity.** Content and visual design each live in exactly one place with one owner. A second file, a second `<style>` block, or a second product name is not a "quick addition" — it is technical debt from the moment it's created, and it requires an explicit decision to accept, not a silent merge. (Prevents F-059/071 and F-086.)
7. **Every versioned or evolving business rule (scoring criteria, permission schemas, message templates) is versioned at the row level from day one, not inferred later from a timestamp.** If a rule can change, every record scored under it stores which version it used. (Prevents F-065/069.)
8. **Nothing is "self-audited" without also being continuously verified.** A pentest checklist, a test suite, a coverage number — if it isn't wired into CI and blocking merges, it is documentation, not a control. State clearly, in every phase, which claims are enforced by CI and which are merely aspirational. (Prevents F-001, F-053.)
9. **Silence is only acceptable for genuinely non-critical failures, and even then it is logged.** A `try/except: pass` is permitted only for cosmetic/best-effort UX paths (an ETA estimate, a push notification retry) and never for anything safety-critical (an emergency alert, a payment confirmation, an audit write) — and even the permitted cases log at warning level so an operator can see the failure rate. (Generalizes the lesson from F-006 and the wider except-pass sweep.)
10. **Every public-facing claim the product makes about itself must be checkable by someone outside the team.** Test counts, department coverage, uptime, response times — if it's stated in a report or in-app copy, there is a script or test that verifies it against reality. (Prevents the stale-README pattern found in F-017 and the false F-042/F-043 claims that had to be retracted.)

---

## Phase 1 — Data Model & Multi-Tenancy Foundation

**Goal:** A schema and tenant-isolation strategy that makes the specific data-leak and versioning bugs found in the audit structurally impossible, not just unlikely.

**Build:**
- PostgreSQL with **Row-Level Security enabled and forced (`FORCE ROW LEVEL SECURITY`) from the very first migration**, not added later. Every tenant-scoped table gets a policy that defaults to zero rows when no tenant context is set — never "all rows." Provide one explicit, audited, greppable escape hatch function (e.g. `all_orgs()`) for the handful of legitimate cross-tenant jobs (backups, platform-wide reports), and nothing else may bypass RLS.
- A single `Branch`/`Department` hierarchy where **branch scoping is enforced at the query layer for every clinically-relevant table** (queue tickets, triage records, consultations) — not assumed to follow indirectly from department assignment. Write an integration test that creates two branches sharing a naively-named department and asserts their queues do not mix.
- Every table whose meaning can change over time under a versioned business rule (inspection criteria, permission schemas, pricing/fee schedules) gets a `rule_version` or `criteria_version` column **at creation**, populated from a single source-of-truth version constant at write time. Trend/aggregate queries over such tables must filter or group by this column — write this as a lint rule or a required code-review checklist item, not just a convention.
- `username` and any other "should be unique within a hospital" field is a **composite unique constraint on `(org_id, field)`**, never a bare global unique constraint, from the first migration.
- A migration system with a **Postgres advisory lock around schema changes** from day one (this fixed a real production incident in the prior system — keep the fix, don't reintroduce the race).
- Seed/demo data generation **never** falls back to a hardcoded password for a privileged role under any code path, including local dev and demos. If no strong password/env override is supplied, generation must fail loudly rather than default to a known string.

**Findings addressed:** F-021, F-056, F-065, F-069, F-074, plus the RLS/migration strengths from the original audit (F-008 gap addressed by explicit escape-hatch design) that should be *carried forward*, not just avoided as regressions.

**Acceptance criteria:**
- [ ] A test exists that attempts to read another tenant's data with RLS enabled and asserts zero rows returned, for every tenant-scoped table.
- [ ] A test exists that creates a shared-name department across two branches and asserts queue/queue-adjacent data does not cross branches.
- [ ] Every versioned table has a non-nullable version column with a default drawn from a single named constant, never a magic number repeated in multiple files.
- [ ] `seed_data()`-equivalent function has a test asserting it refuses to create a privileged account without an explicit strong-password argument or a cryptographically random one.

---

## Phase 2 — Identity, Permission Engine & Audit

**Goal:** A permission system where the F-046/F-068 escalation class of bug is impossible by construction, and an audit trail that is actually tamper-evident across every deployment topology the app will run under.

**Build:**
- Passwords hashed with a memory-hard algorithm (scrypt or Argon2). Login comparison is **constant-time regardless of whether the account exists** — always perform the hash comparison (against a dummy hash if the account is missing) so there is no timing signal distinguishing "no such user" from "wrong password".
- A capability-based permission system (not just role strings) where **the function that grants or edits a permission set enforces, as a database-level check, that the grantor's own effective permission set is a superset of what is being granted.** This is not a route-decorator check alone — it is a check inside the mutation function itself, covered by a test that logs in as a deliberately under-privileged account and attempts to grant itself the top permission, asserting rejection.
- No "master key" shortcut where holding one permission silently implies all others, unless that specific permission is explicitly and separately reviewed as equivalent to full admin — and if it is, it must not be assignable through the same unrestricted self-service UI as ordinary permissions.
- TOTP-based MFA (RFC 6238) with hashed backup codes, enforced for all elevated roles, with disable requiring re-authentication (password + current code) — this worked well in the prior system; keep it.
- A tamper-evident, hash-chained audit log, but built from day one to be correct under multiple concurrent application processes: the chain-continuation lock is a **database-level advisory lock or a serializable transaction**, never an in-process `threading.Lock()`, so horizontal scaling can never silently fork the chain.
- Rate limiting on authentication and any PII-returning endpoint, keyed per Phase 0 Rule 5 — never blindly by IP for anything that might sit behind a shared gateway (USSD, corporate networks).
- Session cookies: `HttpOnly`, `SameSite=Lax`, `Secure` by default, bounded lifetime. Patients, who never authenticate, must never share this session mechanism — their identity is always a capability token (see Phase 3), never a cookie-based session, so there is no code path where "patient identity" and "staff identity" could ever be confused.

**Findings addressed:** F-046, F-062, F-063, F-068, F-010 (CSRF timing), F-002 (audit chain lock), F-037/F-038 (interface isolation — carry the strength forward by design, don't just avoid regressing it).

**Acceptance criteria:**
- [ ] Automated test: an account holding only the role-editing capability cannot create or self-assign a role containing a permission it doesn't already hold.
- [ ] Automated test: response time for a login attempt against a nonexistent username is statistically indistinguishable from a login attempt with a wrong password for a real username, across 100+ samples.
- [ ] Load test: audit log integrity holds under at least 4 concurrent application workers writing simultaneously.
- [ ] Static check (lint or code-review checklist): no `threading.Lock()` guards anything that must be correct across multiple OS processes.

---

## Phase 3 — Core Clinical & Operational Domain

**Goal:** Patient records, queueing, rostering, and branch-aware workflows that are mathematically correct and personally accurate, not just "usually close enough."

**Build:**
- **Queue wait-time estimation implemented as a correct application of Little's Law from day one**: expected wait for a given patient is a function of *that patient's actual position* in the relevant stage, divided by the actual number of parallel servers (staff) working that stage — not a bolted-on multiplicative correction factor applied to a position-blind base estimate. Every personalized "your estimated wait" view must use the patient's real, current position, not a hardcoded assumption of first-in-line. Write a unit test with a synthetic queue of 10 patients and 3 staff and assert the 1st, 5th, and 10th patients get meaningfully different, individually-accurate estimates.
- Roster and leave management enforce **both directions of the duty/leave conflict**: approving leave must check for and resolve any existing duty assignment on the same dates, and creating a duty assignment must check for existing approved leave — symmetric validation, tested in both directions, not just one.
- Any "autofill next period from last period" feature reads its source data from **the same table(s) its own write path uses for that same scope** — a single source-of-truth query builder shared between read and write, so a scope-specific table split (e.g., organization-wide vs. department-scoped duty) cannot silently diverge into "writes go to table A, reads assume table B."
- Department, clinic, and consulting-room management has **exactly one implementation**, discoverable from the main navigation for whichever role manages it. Before building a second "quick add" or "bulk import" surface for the same entity, check whether one already exists; if a second is genuinely needed, it must call into the same underlying service functions as the first, never duplicate the business logic.
- Referential-integrity checks before any destructive delete (a department, clinic, or room referenced by active records) — block deletion, suggest "suspend" instead, and enumerate exactly what's blocking it. (This worked well in the prior system; keep it, and apply the same pattern to every entity type that can be referenced elsewhere, not just the ones that happened to get it.)
- Complaint, booking, and feedback status-lookup pages that accept a reference number from an unauthenticated visitor **always** pair it with a second verifying fact (phone number match) before returning any personal detail — apply this uniformly across every such "thanks" or "status" page in the product, including confirmation pages shown immediately after submission, not just the pages built later with more attention to the risk.

**Findings addressed:** F-013, F-014, F-047, F-048, F-070, F-028 (the underlying access-control principle), F-049, F-066, F-067 (generalize the pattern that worked).

**Findings addressed (Phase 3 actually reads):** F-013, F-014, F-047, F-048, F-070, F-028, F-049, F-066, F-067. *(F-070's second reference: Phase 3 lists F-070 among workflow findings — cross-checked with Phase 6 where the orphaned-route control lives.)*

**Acceptance criteria:**
- [ ] Unit tests proving queue ETA scales correctly with both position and staff count (Little's Law), not just "some number changes when inputs change."
- [ ] Integration test: approving leave for a person with an existing duty shift on the same date either blocks the approval or reassigns/flags the duty shift — verified both directions.
- [ ] A single, documented service layer for department/clinic/room CRUD; a repo-wide search confirms no second implementation exists.
- [ ] Every public status/confirmation lookup route has a test asserting it returns no personal data without a correct second-factor match.

---

## Phase 4 — Communications: SMS, WhatsApp, Push, Voice, USSD, TV

**Goal:** Every message sent exactly once, every public data feed exposes only what its own stated privacy rule allows, and every telecom-gateway integration accounts for shared-IP traffic instead of assuming one caller per IP.

**Build:**
- All outbound message dispatch (SMS, WhatsApp) is processed by **exactly one consumer per queue**, claiming rows atomically (`UPDATE ... SET status='SENDING' WHERE status='QUEUED' RETURNING id`, or an equivalent `SKIP LOCKED` pattern) before sending — never a plain `SELECT` followed by a send, and never triggered by spawning a fresh, uncoordinated worker thread per event. If background dispatch needs to be fast, use a proper task queue (or a single long-running consumer loop) rather than one thread per HTTP request.
- Every provider-facing webhook (WhatsApp, payment, any inbound telecom callback) **verifies a cryptographic signature and fails closed** if the verification secret is not configured — never fail open and accept unverified traffic just because a secret happens to be unset in a given environment.
- USSD (or any protocol relayed through a shared telecom gateway) has its rate limiting keyed by the caller's phone number or session ID from the payload, **never** by source IP, since the gateway's IP is shared across every simultaneous user.
- TV/queue-display data feeds are designed **privacy-first at the API boundary, not just at the template layer**: the JSON or data payload returned by any public, unauthenticated feed contains only what the rendered display is allowed to show (first name, ticket code — never full name, never a hospital/record number) as a matter of what fields exist in the response at all, not a rendering choice made downstream. If a voice-announcement feature needs the full name, it is delivered through a server-side-only channel, never shipped to the browser.
- Voice/TTS features prefer a real, warm pre-recorded phrase bank with placeholder substitution over generic synthetic TTS where budget allows, matching what worked well in the prior system, with multi-language support designed in from the start rather than retrofitted.
- Voice-to-text (dictation) input on patient-facing forms handles the known browser quirk where recognition sessions periodically restart and reset internal indexing — freeze each session's committed transcript rather than trusting a resettable running index.

**Findings addressed:** F-064, F-005, F-077, F-028, F-018 (backup/egress-adjacent design lesson), F-029/F-030/F-031/F-032 (carry forward the things that worked).

**Acceptance criteria:**
- [ ] Load test: firing 20 simultaneous triggering events for message dispatch results in exactly 20 messages sent, never more, never fewer.
- [ ] Test: an inbound webhook with no configured verification secret is rejected, not accepted.
- [ ] Load test simulating 50 simultaneous USSD sessions from one shared IP: none are rejected by rate limiting due to sharing that IP.
- [ ] A schema/contract test asserts the public TV feed JSON response contains no field beyond an explicit allow-list (first name, code, department, room) — adding a new field to the underlying model must not silently expose it.

---

## Phase 5 — AI Chatbot & Knowledge Base

**Goal:** One knowledge base, safety guardrails that work in every supported language from day one, and a human-in-the-loop correction mechanism at least as careful as the best version found in the prior system.

**Build:**
- **One knowledge base, one file (or one clearly-owned data store), searchable and auditable as a single collection from the start.** If content naturally organizes into categories (departments, general FAQs, admin topics), use a structured schema (a category field) within the single store — never separate files that must be manually remembered and merged at boot. Before merging any future content addition, run an automated keyword-collision check as part of CI; a collision is a build warning, not a silent runtime ambiguity.
- Knowledge base content is tagged by **intended audience** (patient-facing vs. staff-facing) at the schema level, so staff-flavored content (permission management, audit log questions) cannot end up sharing a match pool with patient questions by accident.
- The AI-fallback layer (used when the knowledge base has no direct answer) is knowledge-base-first with a real LLM as fallback only, using: (a) a pre-model guardrail that blocks diagnosis-seeking questions, (b) a post-model guardrail that scans the model's own reply for leaked clinical claims or invented facts, and (c) provider failover so a single vendor outage never surfaces a raw error to a patient. **Both guardrails must work in every language the product supports from day one** — build them as structured intent/pattern matching per supported language, or as a lightweight classifier call, not an English-only keyword list with an implicit assumption that non-English conversations are rare enough to ignore.
- A second, independent "honesty" filter runs on **every** answer — knowledge-base and AI-generated alike — stripping any capability promise the system cannot actually fulfill (booking something it doesn't book, texting a map it can't send). This should not be bolted onto only the newer content; it applies uniformly.
- Any mechanism allowing a privileged user to correct or edit live content through the same chat interface patients use is gated by **two independent checks** (server-side role re-verification, plus a separate secret verified with a timing-safe comparison), and returns an identical, uninformative response on any failed attempt — never a response that reveals which of the two checks failed, or that content editing was attempted at all.
- Departments/topics covered in the knowledge base are tracked against the canonical list of standard departments/services as a **CI-checked completeness test**, not a manual audit — if a new standard department is added to the org-structure seed data without matching KB content, the build should flag it, not wait for someone to notice a patient got an unhelpful answer.
- Sensitive topics (mental health, sexual health, substance use) are held to a distinctly gentler tone standard than general operational content, reviewed by clinical or a designated sensitive-content reviewer before publishing, and are not treated as "just another department" for content-generation purposes.

**Findings addressed:** F-059, F-071, F-033, F-034 (carry forward), F-035 (carry forward), F-060/F-072/F-073 (carry forward the honesty/quickedit/links patterns as the standard, not the exception), F-036, F-041, F-042/F-043 (the corrected finding — build the completeness check that would have prevented the false claim in the first place).

**Acceptance criteria:**
- [ ] CI step: zero exact-keyword collisions across the entire knowledge base at merge time (or an explicit, reviewed override list for accepted near-duplicates).
- [ ] CI step: every standard department/service in the org-structure seed data has at least one matching KB entry; new departments added without matching content fail the build.
- [ ] Test: a clinical-diagnosis-seeking question submitted in each supported language is blocked by the pre-model guardrail; a synthetic "leaked diagnosis" reply in each supported language is caught by the post-model filter.
- [ ] Test: the privileged content-correction path returns byte-identical responses for "wrong secret" and "unrelated ordinary question," so no information is leaked by response shape.

---

## Phase 6 — Admin, Reports & Analytics

**Goal:** Every admin capability has exactly one discoverable home, every report is bounded and accurate, and every claim in a generated report is traceable to a real query, not an assumption.

**Build:**
- Before building any admin CRUD screen, search the codebase for an existing implementation of the same entity's management. If building a new one is genuinely justified (a full rewrite, a deliberate replacement), the old one is deleted in the same change, not left running in parallel.
- **Every admin route that exists is linked from somewhere reachable in normal navigation** for the roles authorized to use it — an automated check (crawl the route table, crawl the templates, flag any authorized-but-unlinked route) runs in CI, not as a one-off manual audit.
- All list/report queries are explicitly bounded (a `LIMIT`, with pagination for anything that can exceed it) — no report endpoint may run an unbounded `.all()` against a table that grows with patient volume, even if it "seems fine" at current scale.
- Trend/aggregate analytics that depend on a versioned business rule (see Phase 1) explicitly filter or segment by version — a "recurring problem" or similar cross-time comparison feature must be built and tested against a synthetic dataset that spans a version change, from day one, not discovered as a bug after the fact.
- Self-audit/diagnostic tooling (a security checklist, a data-quality checklist) that exists in the app is **wired into CI as a build gate**, not only a manually-visited dashboard page — if it's worth writing the check, it's worth failing the build on it.

**Findings addressed:** F-070, F-052, F-011/F-020 (rate-limit and audit PII-returning admin endpoints as a standard, not an exception), F-053, F-065/069 (analytics-specific application of the Phase 1 principle).

**Acceptance criteria:**
- [ ] CI check: every route requiring authorization is reachable via at least one link from a template accessible to an authorized role.
- [ ] Code review checklist item, enforced at PR time: "does this duplicate an existing CRUD surface for the same entity? If yes, why does the old one still exist?"
- [ ] Every report/list endpoint has an explicit page size or hard cap, verified by a test that seeds more rows than the cap and asserts the response size.
- [ ] `pentest.py`-equivalent self-audit script runs in CI and fails the build on any "fail"-level result.

---

## Phase 7 — Frontend Design System & Accessibility

**Goal:** One visual identity everywhere a person encounters the product, and accessibility that is verified by computation, not assumed from good intentions.

**Build:**
- **One design-token system** (CSS custom properties or equivalent) for color, spacing, radius, shadow, and type scale, used by every page in the product without exception — including marketing/sales pages. Before writing a new page's styles, the design-token file is the only source of colors, spacing, and radii; a new color value requires adding it to the shared tokens, never typing a one-off hex value inline.
- **Every color pair used for actual text (not purely decorative elements) is checked against WCAG AA contrast ratios (4.5:1 normal text, 3:1 for 18px+/14px-bold+ text) as an automated build step**, computed from the actual rendered font-size each color is used at — not eyeballed. A palette change that fails this check fails the build.
- **Every interactive element meets a 44px minimum touch target**, verified by a linting rule or visual-regression check, applied uniformly to primary buttons, navigation links, and any custom interactive component — not just the component that happened to get attention first.
- A skip-link to bypass navigation and reach main content is present on every page, and every icon-only interactive element carries a real `aria-label` (not solely a `title` attribute, which is not reliably read by assistive technology and is invisible on touch devices).
- `<html lang>` (and any other locale-dependent attribute) reflects the actual active session language, computed from the single source of truth for locale already used elsewhere in the request lifecycle — never hardcoded.
- A single, well-documented back-navigation pattern (with sensible fallback behavior when there's no real browser history) is implemented once, styled with real touch-target-sized, visible CSS, and used everywhere — not left as unstyled logic that happens to work but is hard to see or tap.
- Any marketing, sales, or landing page uses the **same product name and the same design tokens** as the actual product. If a genuinely different visual treatment is wanted for a marketing context, it is a deliberate, reviewed brand decision applied consistently — not an independently-styled one-off page that drifts from the product it's supposed to represent.
- `prefers-reduced-motion` is respected; visible focus indicators (`:focus-visible`) are implemented and never removed for aesthetic reasons.

**Findings addressed:** F-022, F-024, F-025, F-026, F-039, F-040, F-080, F-081, F-082, F-083, F-084, F-085, F-086, F-087 (carry forward the strong token-system foundation as the standard for the whole product, not an unevenly-applied one).

**Acceptance criteria:**
- [ ] Automated contrast-ratio check runs in CI over every token color pair at its actual usage font-size; the build fails on any AA violation.
- [ ] Automated check (or documented manual review checklist) confirms every interactive element's computed height/width meets 44px.
- [ ] A crawl of all templates confirms zero raw hex color values outside the token definition file (or an explicit, reviewed exception list).
- [ ] Manual test with a screen reader and keyboard-only navigation on the core patient and staff flows before every major release.
- [ ] Visual diff/screenshot comparison between the marketing site and the core product confirms shared color palette, typography, and product naming.

---

## Phase 8 — Reliability, Scaling & Operations

**Goal:** The gap between "what the tests say" and "what actually runs in production" is zero, and the system's behavior under real concurrency is understood and tested before launch, not discovered afterward.

**Build:**
- **CI is wired and required from the very first commit** — no test suite is ever written without also being connected to a branch-protection rule that blocks merging on failure. This is not deferred to "once we have enough tests"; a small, real, enforced suite from day one beats a large, unenforced one added later.
- Dependency vulnerability scanning (e.g., `pip-audit` or equivalent) runs in CI on every dependency change.
- Any in-process concurrency primitive (a `threading.Lock`, an in-memory counter, an in-process scheduler singleton guard) is explicitly documented as **only correct under a single worker process**, and the deployment configuration is either pinned to a single process with that constraint written down, or the primitive is replaced with a database-level equivalent before scaling past one process. This decision is made consciously in this phase, not discovered as a production incident later.
- Background scheduled jobs (reminders, backups, cleanup) are idempotent at the database level (a marker row, a claimed-status column) so they are safe to run from multiple processes even if the "only one scheduler" assumption is ever violated.
- Backup generation streams data rather than materializing an entire dataset in memory where practical, and — critically — **a backup is not considered validated until a restore has actually been performed and verified**, on a real or realistic dataset, on a recurring schedule, not just "we take backups."
- A load test simulating realistic worst-case simultaneous usage (queue joins during a morning rush, USSD sessions from a shared gateway, message dispatch bursts) is run before launch and after any change to the areas covered by Phases 3 and 4.

**Findings addressed:** F-001, F-002, F-003, F-009, F-016, F-018, plus generalizing the lesson of F-064/F-077 into an explicit operational practice rather than a one-off fix.

**Acceptance criteria:**
- [ ] CI runs on every pull request and merging is blocked on failure, from the first week of the project.
- [ ] A written, dated document exists stating exactly which subsystems are single-process-only and why, reviewed before any change to worker count.
- [ ] At least one full backup-restore drill has been performed and documented before go-live, and is scheduled to recur.
- [ ] A load test report exists covering the scenarios above, run before launch.

---

## Phase 9 — QA, Launch Readiness & Definition of Done

**Goal:** A single, honest checklist that must be fully green before this product can call itself ready — no self-reported claim stands without independent verification.

**Definition of Done (all must be true, verified, not asserted):**
- [ ] Every acceptance criterion in Phases 1–8 is checked and passing in CI or documented via a dated manual test.
- [ ] Test coverage is measured (not just counted) and published; the number is generated by tooling, never typed by hand into a README.
- [ ] A security review has specifically attempted the F-046/F-068-style escalation pattern against the new permission system and failed to reproduce it.
- [ ] A load test has specifically attempted the F-064-style concurrent-dispatch race and failed to reproduce a duplicate send.
- [ ] An accessibility pass (automated contrast/touch-target checks plus one manual screen-reader run-through of the core patient and staff flows) is complete and documented.
- [ ] The knowledge base passes its completeness check (Phase 5) against the current standard department list, with zero unresolved keyword collisions.
- [ ] Every admin surface is confirmed reachable from navigation for its intended role; zero orphaned routes.
- [ ] The marketing/sales presence (if any) uses the same product name and design tokens as the core product, confirmed by direct comparison.
- [ ] A backup has been restored and verified within the last release cycle.
- [ ] This document itself is updated to reflect what was actually built, and any deviation from a stated rule is written down with the reason — silently drifting from this specification is exactly the failure mode this whole rebuild exists to prevent.

---

## 11. Full Traceability — Every Finding, Accounted For

This table exists so no finding from the original audit can be silently dropped between "we found it" and "we built around it." Every one of the 87 findings (F-001 through F-087) is listed with the phase(s) responsible for preventing its recurrence.

| Finding | Phase(s) | Finding | Phase(s) | Finding | Phase(s) |
|---|---|---|---|---|---|
| F-001 | 8 | F-030 | 4 | F-059 | 5 |
| F-002 | 2, 8 | F-031 | 4 | F-060 | 5 |
| F-003 | 8 | F-032 | 4 | F-061 | 2 |
| F-004 | 2 (constitution) | F-033 | 5 | F-062 | 2 |
| F-005 | 4 | F-034 | 5 | F-063 | 2 |
| F-006 | 0, 4 | F-035 | 5 | F-064 | 4 |
| F-007 | 3, 6 | F-036 | 5 | F-065 | 1, 6 |
| F-008 | 1 | F-037 | 2 | F-066 | 3 |
| F-009 | 8 | F-038 | 2 | F-067 | 3 |
| F-010 | 2 | F-039 | 7 | F-068 | 2 |
| F-011 | 6 | F-040 | 7 | F-069 | 1, 6 |
| F-012 | 3 (workflow rule) | F-041 | 5 | F-070 | 6 |
| F-013 | 3 | F-042 | 5 (retracted; completeness check built anyway) | F-071 | 5 |
| F-014 | 3 | F-043 | 5 (retracted; sensitive-content review built anyway) | F-072 | 5 |
| F-015 | 1 (data protection, noted for future encryption-at-rest pass) | F-044 | 5 (copyedit discipline) | F-073 | 3, 4 |
| F-016 | 8 | F-045 | 5 (copyedit discipline) | F-074 | 1 |
| F-017 | 0, 6 (verifiable claims rule) | F-046 | 2 | F-075 | 3 (accepted tradeoff, documented) |
| F-018 | 4, 8 | F-047 | 3 | F-076 | 3, 4 |
| F-019 | 4 (future multi-tenant WhatsApp routing) | F-048 | 3 | F-077 | 2, 4 |
| F-020 | 6 | F-049 | 3 | F-078 | 3 |
| F-021 | 1 | F-050 | 4 | F-079 | 5 |
| F-022 | 7 | F-051 | 3 (escalation-ladder design, carried forward) | F-080 | 7 |
| F-023 | 7 | F-052 | 6 | F-081 | 7 |
| F-024 | 7 | F-053 | 6, 8 | F-082 | 7 |
| F-025 | 7 | F-054 | 3 (scope clarification, no change needed) | F-083 | 7 |
| F-026 | 7 | F-055 | 2 (confirmed-safe pattern, carried forward) | F-084 | 7 |
| F-027 | — (corrected during original audit; no rebuild action needed) | F-056 | 1, 3 | F-085 | 7 |
| F-028 | 4 | F-057 | 4 (storage architecture, carried forward) | F-086 | 0, 7 |
| F-029 | 4 | F-058 | 4 (design pattern, carried forward) | F-087 | 7 (foundation to build on, not a gap) |

**Reading this table honestly:** a handful of rows point to "carried forward" or "no change needed" — those are the parts of the original system that were already done well and should not be lost in a rebuild out of an assumption that everything needs redoing. The majority point to a specific phase with a specific structural change, not a promise to "be more careful this time." If a future reviewer opens this document looking for any of F-001 through F-087 and cannot find it in this table, that is itself a finding to raise immediately — this document is only as honest as its willingness to be checked.

---

## How to actually use this with an AI coding agent

Feed Phase 0 first, in full, as system-level context that persists across the whole project. Then feed each subsequent phase as its own task, in order, explicitly telling the agent: "Before writing any code for this phase, restate which Phase 0 rules and which listed findings apply, and how the design you're about to propose addresses each one." Do not let a phase be marked complete until its Acceptance Criteria are demonstrated, not just claimed — this mirrors the exact failure mode (self-reported test counts, unenforced self-audit tooling) that this whole specification exists to prevent.
