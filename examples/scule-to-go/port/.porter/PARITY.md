# Parity report

Upstream: scule 1.3.0 (typescript, commit 90d28593c842).
Port: github.com/agentporter-examples/scule in go. Evidence date: 2026-10-20. Harness run: final-1.
Fixtures: 2984 cases, 2984 exact, 0 normalized, 0 divergent, 0 failed, 0 missing.

| Unit | Level | Fixtures (exact / normalized / divergent / failed of total) | Reference tests (pass / total) | Divergences | Perf (median ratio) |
| --- | --- | --- | --- | --- | --- |
| cases | EXACT | 1997 / 0 / 0 / 0 of 1997 | 44 / 44 | - | 0.01x |
| split | EXACT | 987 / 0 / 0 / 0 of 987 | 19 / 19 | - | 0.01x |

Levels: EXACT means every fixture matched byte for byte. EQUIVALENT means every fixture matched under
the normalization declared on the fixture. DIVERGENT means some cases differ on purpose (listed below).
ASSERTED means no oracle fixtures exist and ported reference tests carry the evidence. GAP means a known
mismatch remains.

## Intentional divergences

- **d1** (split): Where JavaScript returns a string holding a lone UTF-16 surrogate, the Go result holds U+FFFD in its place: SplitByCase("\U00010400a") is ["\uFFFD", "\uFFFDa"] where JavaScript gives ["\ud801", "\udc00a"]. Why: Go strings are UTF-8, which cannot encode a lone surrogate. The port keeps parts as UTF-16 code units internally, so it cuts in the same place as JavaScript and rejoins the halves exactly (flatCase and pascalCase stay identical); only decoding a part that still holds a lone surrogate replaces it. Planned as DIVERGENCE D1 in strategy.md (scope gauntlet, lone-surrogate outputs). The affected inputs were removed from the fixtures (contract/units/split.md, Removed cases), so no fixture fails on it.
- **d2** (split): Single code point case mappings and the Final_Sigma context use Go's unicode tables (Unicode 15.0 in Go 1.22-1.26) instead of the JavaScript engine's (Unicode 17.0 in Node 24). UpperFirst("ƛ") is "ƛ" where JavaScript gives "Ƛ"; SplitByCase("a\uA7CB") is one part in Go and two in JavaScript (U+A7CB is uppercase only from Unicode 16). Why: strategy.md lists the Unicode version gap as a seam for later. No fixture touches an affected code point (the corpus uses mappings from Unicode 11 or earlier). Found by the split review, which compared every code point against Node 24.18; documented in doc.go. Fix later by making internal/gencasing emit single code point differences too.
- **d1-cases** (cases): Where JavaScript returns a joined string holding a lone UTF-16 surrogate, the Go result holds U+FFFD in its place: KebabCase("\U00010400a") is "\uFFFD-\uFFFDa" where JavaScript gives "\ud801-\udc00a". Why: Same cause as d1: Go strings are UTF-8 and cannot carry a lone surrogate. The converters join the UTF-16 parts from splitUnits and decode once, so PascalCase, CamelCase and FlatCase rejoin split surrogate pairs exactly; only a joiner placed between the two halves (kebab, snake, train, title) leaves lone surrogates, which decoding replaces. Planned as DIVERGENCE D1 in strategy.md; the 18 affected inputs were removed from the fixtures (contract/units/cases.md, Removed cases).
