# Decomposition

Proposed by `porter.py decompose` on 2026-10-20.
Budgets: at most 400 LOC and 8 public symbols per unit, merge below 30 LOC.

## Layer map

- core: index

## Units in order

| # | Unit | Layer | Wave | LOC | Public symbols | Depends on | Risk | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | index (tracer) | core | 0 | 111 | default | - | error-model, float-format, nullability, numeric, reflection, regex |  |

## Why the cuts are where they are

- tracer bullet: index (closure index), the lowest-risk vertical slice

## Adjustments

The agent records every change it makes to the proposal here, one line each: what changed and why.

- (none yet)
