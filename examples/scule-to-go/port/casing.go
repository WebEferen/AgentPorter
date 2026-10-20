package scule

import (
	"unicode"
	"unicode/utf16"
)

//go:generate go run ./internal/gencasing/main.go

// Case mapping follows JavaScript's toUpperCase and toLowerCase: the full,
// locale-independent Unicode mapping. That is unicode.ToUpper and
// unicode.ToLower, except for the code points in specialUpper and specialLower
// (casing_table.go), which map to several code points ("ß" to "SS"), plus the
// Final_Sigma rule in lowerUnits. A surrogate code unit maps to itself.

const (
	capitalSigma    = 0x03A3 // Σ
	smallFinalSigma = 0x03C2 // ς
)

// appendUpper appends the full uppercase mapping of r to dst.
// DIVERGENCE(d2): single code point mappings use Go's unicode tables.
func appendUpper(dst []uint16, r rune) []uint16 {
	if utf16.IsSurrogate(r) {
		return append(dst, uint16(r))
	}
	if s, ok := specialUpper[r]; ok {
		return appendString(dst, s)
	}
	return utf16.AppendRune(dst, unicode.ToUpper(r))
}

// appendLower appends the full lowercase mapping of r, without context, to
// dst. Σ becomes σ here; lowerUnits applies Final_Sigma.
// DIVERGENCE(d2): single code point mappings use Go's unicode tables.
func appendLower(dst []uint16, r rune) []uint16 {
	if utf16.IsSurrogate(r) {
		return append(dst, uint16(r))
	}
	if s, ok := specialLower[r]; ok {
		return appendString(dst, s)
	}
	return utf16.AppendRune(dst, unicode.ToLower(r))
}

func appendString(dst []uint16, s string) []uint16 {
	for _, r := range s {
		dst = utf16.AppendRune(dst, r)
	}
	return dst
}

// lowerChanges reports whether lowercasing r changes it, which is
// JavaScript's c !== c.toLowerCase() for a one-code-point string c.
func lowerChanges(r rune) bool {
	if utf16.IsSurrogate(r) {
		return false
	}
	_, special := specialLower[r]
	return special || unicode.ToLower(r) != r
}

// upperFirstUnits returns a new slice holding u with its first code unit
// uppercased: JavaScript's str[0].toUpperCase() + str.slice(1). The mapping
// may be longer than one unit ("ß" gives "SS"). A leading surrogate is left as
// it is, so a character above U+FFFF is never re-cased.
func upperFirstUnits(u []uint16) []uint16 {
	if len(u) == 0 {
		return nil
	}
	return append(appendUpper(make([]uint16, 0, len(u)+2), rune(u[0])), u[1:]...)
}

// lowerFirstUnits is upperFirstUnits with the lowercase mapping: JavaScript's
// str[0].toLowerCase() + str.slice(1). A lone first unit has no context, so Σ
// gives σ.
func lowerFirstUnits(u []uint16) []uint16 {
	if len(u) == 0 {
		return nil
	}
	return append(appendLower(make([]uint16, 0, len(u)+1), rune(u[0])), u[1:]...)
}

// lowerUnits returns the full lowercase mapping of u as a new slice:
// JavaScript's toLowerCase on the whole of u, including Final_Sigma with u as
// the context.
func lowerUnits(u []uint16) []uint16 {
	out := make([]uint16, 0, len(u))
	for i := 0; i < len(u); {
		r, n := codePointAt(u, i)
		if r == capitalSigma && isFinalSigma(u, i, i+n) {
			out = append(out, smallFinalSigma)
		} else {
			out = appendLower(out, r)
		}
		i += n
	}
	return out
}

// isFinalSigma reports whether the Σ at u[start:end] is final: a cased
// letter comes before it and none comes after it, skipping case-ignorable
// characters on both sides. As in ICU (which V8 uses), a character that is
// both cased and case-ignorable is skipped.
func isFinalSigma(u []uint16, start, end int) bool {
	before := false
	for i := start; i > 0; {
		r, n := codePointBefore(u, i)
		if !isCaseIgnorable(r) {
			before = isCased(r)
			break
		}
		i -= n
	}
	if !before {
		return false
	}
	for i := end; i < len(u); {
		r, n := codePointAt(u, i)
		if !isCaseIgnorable(r) {
			return !isCased(r)
		}
		i += n
	}
	return true
}

// isCased reports the Unicode Cased property: Lowercase, Uppercase or
// Titlecase_Letter.
func isCased(r rune) bool {
	return unicode.In(r, unicode.Lu, unicode.Ll, unicode.Lt, unicode.Other_Lowercase, unicode.Other_Uppercase)
}

// isCaseIgnorable reports the Unicode Case_Ignorable property: Mn, Me, Cf, Lm,
// Sk, and Word_Break MidLetter, MidNumLet or Single_Quote.
func isCaseIgnorable(r rune) bool {
	switch r {
	case '\'', '.', ':', 0x00B7, 0x0387, 0x055F, 0x05F4, 0x2018, 0x2019, 0x2024, 0x2027,
		0xFE13, 0xFE52, 0xFE55, 0xFF07, 0xFF0E, 0xFF1A:
		return true
	}
	return unicode.In(r, unicode.Mn, unicode.Me, unicode.Cf, unicode.Lm, unicode.Sk)
}
