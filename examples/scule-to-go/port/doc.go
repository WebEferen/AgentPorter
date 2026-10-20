// Package scule splits strings by case and converts them between naming
// conventions (PascalCase, camelCase, kebab-case, snake_case, flatcase,
// Train-Case, Title Case).
//
// It is a Go port of the JavaScript package scule 1.3.0 and returns the same
// results, with the differences listed below. Text is measured and cased the way JavaScript does it: splitting
// walks code points but measures and cuts in UTF-16 code units, and case
// mapping is the full, locale-independent Unicode mapping of
// String.prototype.toUpperCase and toLowerCase (so "ß" uppercases to "SS"
// and a final Greek sigma lowercases to "ς").
//
// Known differences: where JavaScript would return a string holding a
// lone UTF-16 surrogate (for example SplitByCase("\U00010400a"), which cuts
// the surrogate pair of U+10400), the Go result holds U+FFFD in its place,
// because a Go string is UTF-8. Single code point case mappings and the
// Final_Sigma context come from Go's unicode package (unicode.Version), which
// may be older than the Unicode version of the JavaScript engine: characters
// added or re-cased in later versions (for example "ƛ" and "ɤ") can case
// differently. Invalid UTF-8 in the input is read as U+FFFD.
package scule
