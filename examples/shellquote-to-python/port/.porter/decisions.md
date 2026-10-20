# Decisions

Append-only log of human decisions for this port: gates, scope changes, authorizations and overrides.
`porter.py` appends an entry for every gate. Add an entry by hand for anything else a future reader
needs to know, newest last. One heading per decision, then a few lines: what was decided, by whom, why.

## 2026-10-20 strategy gate: approved

approve the proposed units, order and budgets as written.

## 2026-10-20 strategy scope: partial words on split errors

unattended: the user's answers say "exceptions for errors" but not what happens to the words Go returns
alongside an error. Conservative option taken: every split exception carries them as `exc.words`, and a
target test checks them against the recorded `expect.value`. Decided by the agent in an unattended run.

## 2026-10-20 strategy scope: invalid UTF-8 out of scope

unattended: a Python `str` API cannot receive invalid UTF-8 bytes, which Go copies through unchanged
(contract leak `invalid-utf8`). Conservative option taken: `str`-only API, no promise for invalid UTF-8,
no fixtures for it; a `bytes` overload is a seam for later. Decided by the agent in an unattended run.
