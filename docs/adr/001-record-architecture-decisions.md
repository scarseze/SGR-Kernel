# 1. Record Architecture Decisions

Date: 2026-03-06

## Status

Accepted

## Context

We need to record the architectural decisions made on this project. Formalizing decisions ensures that standard practices (e.g., TLA+ invariants, exactly-once processing guarantees, and distributed systems semantics) are documented and justified for future developers and stakeholders.

## Decision

We will use Architecture Decision Records (ADRs). ADRs will be stored in the `docs/adr/` directory. Each record describes a single decision along with its context and consequences.

## Consequences

- We have a clear historical record of "why" a decision was made.
- New team members can quickly understand the system's underlying design principles.
- Decisions are treated as code artifacts, subject to pull requests and version control.
