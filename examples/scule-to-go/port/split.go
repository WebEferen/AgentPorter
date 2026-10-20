package scule

import (
	"slices"
	"unicode/utf16"
	"unicode/utf8"
)

// defaultSeparators are the code points splitByCase splits on when no
// separators are given.
var defaultSeparators = []rune{'-', '_', '/', '.'}

// separatorRunes turns separator strings into the code points splitUnits
// compares with. JavaScript compares each separator with one whole code point
// of the input, so a separator that is empty, longer than one code point or
// not valid UTF-8 never matches and is dropped.
func separatorRunes(separators []string) []rune {
	runes := make([]rune, 0, len(separators))
	for _, sep := range separators {
		if utf8.RuneCountInString(sep) == 1 && utf8.ValidString(sep) {
			r, _ := utf8.DecodeRuneInString(sep)
			runes = append(runes, r)
		}
	}
	return runes
}

// letterCase is JavaScript's isUppercase(char) for one code point:
// caseNone stands for undefined (an ASCII digit), and is also the state at the
// start and after a separator.
type letterCase int8

const (
	caseNone letterCase = iota
	caseLower
	caseUpper
)

func caseOf(r rune) letterCase {
	switch {
	case '0' <= r && r <= '9':
		return caseNone
	case lowerChanges(r):
		return caseUpper
	default:
		return caseLower
	}
}

// splitUnits is splitByCase: it splits s at separators and case changes and
// returns the parts as UTF-16 code units. It walks s by code point but
// measures and cuts the current part in code units, so on an upper-to-lower
// change after a character above U+FFFF only the low surrogate moves to the
// next part. s == "" gives no parts; empty parts between separators are kept.
func splitUnits(s string, separators []rune) [][]uint16 {
	var parts [][]uint16
	if s == "" {
		return parts
	}
	var buff []uint16
	previous := caseNone
	for _, r := range s {
		if slices.Contains(separators, r) {
			parts = append(parts, buff)
			buff = nil
			previous = caseNone
			continue
		}
		current := caseOf(r)
		// Rising edge: lower to upper starts a new part with r.
		if previous == caseLower && current == caseUpper {
			parts = append(parts, buff)
			buff = utf16.AppendRune(nil, r)
			previous = current
			continue
		}
		// Falling edge: upper to lower after two or more code units moves the
		// last code unit into the new part.
		if previous == caseUpper && current == caseLower && len(buff) > 1 {
			last := len(buff) - 1
			parts = append(parts, buff[:last:last])
			buff = utf16.AppendRune([]uint16{buff[last]}, r)
			previous = current
			continue
		}
		buff = utf16.AppendRune(buff, r)
		previous = current
	}
	return append(parts, buff)
}
