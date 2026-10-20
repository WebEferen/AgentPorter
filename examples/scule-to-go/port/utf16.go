package scule

import "unicode/utf16"

// Internally a string is a []uint16 of UTF-16 code units, the unit JavaScript
// strings are made of. Parts cut between the two halves of a surrogate pair
// keep the lone surrogate, so joining parts restores the pair exactly as in
// JavaScript; only decodeUnits loses it.

// encodeUnits returns the UTF-16 code units of s.
func encodeUnits(s string) []uint16 {
	u := make([]uint16, 0, len(s))
	for _, r := range s {
		u = utf16.AppendRune(u, r)
	}
	return u
}

// decodeUnits returns u as a Go string.
func decodeUnits(u []uint16) string {
	// DIVERGENCE(d1): a lone surrogate has no UTF-8 encoding, so it becomes U+FFFD; JavaScript keeps it.
	return string(utf16.Decode(u))
}

// decodeParts decodes every part. The result is never nil.
func decodeParts(parts [][]uint16) []string {
	out := make([]string, len(parts))
	for i, p := range parts {
		out[i] = decodeUnits(p)
	}
	return out
}

func isHighSurrogate(c uint16) bool { return 0xD800 <= c && c < 0xDC00 }

func isLowSurrogate(c uint16) bool { return 0xDC00 <= c && c < 0xE000 }

// codePointAt returns the code point starting at u[i] and its length in code
// units. A surrogate that is not part of a pair is returned as itself.
func codePointAt(u []uint16, i int) (rune, int) {
	if isHighSurrogate(u[i]) && i+1 < len(u) && isLowSurrogate(u[i+1]) {
		return utf16.DecodeRune(rune(u[i]), rune(u[i+1])), 2
	}
	return rune(u[i]), 1
}

// codePointBefore returns the code point that ends just before u[i] and its
// length in code units. A surrogate that is not part of a pair is returned
// as itself.
func codePointBefore(u []uint16, i int) (rune, int) {
	if isLowSurrogate(u[i-1]) && i >= 2 && isHighSurrogate(u[i-2]) {
		return utf16.DecodeRune(rune(u[i-2]), rune(u[i-1])), 2
	}
	return rune(u[i-1]), 1
}
