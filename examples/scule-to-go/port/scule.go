package scule

import (
	"reflect"
	"slices"
	"strings"
)

// CaseOptions configures PascalCase, CamelCase, TrainCase and TitleCase.
type CaseOptions struct {
	// Normalize lowercases each word before its first letter is uppercased.
	Normalize bool
}

// Words is a string to split by case, or words that are used as they are.
type Words interface{ ~string | ~[]string }

// IsUppercase reports whether lowercasing s changes it. When s contains an
// ASCII digit 0-9, ok and upper are false (the JavaScript original returns
// undefined).
//
// The whole of s is compared with its full lowercase mapping, so "aB" is
// uppercase and so are "Ⅻ" and "ǅ".
func IsUppercase(s string) (upper, ok bool) {
	if strings.ContainsAny(s, "0123456789") {
		return false, false
	}
	u := encodeUnits(s)
	return !slices.Equal(lowerUnits(u), u), true
}

// SplitByCase splits s into words at the separators "-", "_", "/" and "." and
// at case changes: "fooBar" gives ["foo" "Bar"] and "FOOBar" gives
// ["FOO" "Bar"]. A case change right after an ASCII digit does not split:
// "a1B" stays one word. Parts keep their
// case, empty parts between separators are kept, and "" gives an empty slice.
func SplitByCase(s string) []string {
	return decodeParts(splitUnits(s, defaultSeparators))
}

// SplitByCaseWith is SplitByCase with its own separators in place of the
// default ones. Each separator must be exactly one character to match; an
// empty or nil list splits at case changes only.
func SplitByCaseWith(s string, separators []string) []string {
	return decodeParts(splitUnits(s, separatorRunes(separators)))
}

// UpperFirst uppercases the first character of s with the full Unicode
// mapping ("ßa" gives "SSa"). A first character above U+FFFF is left as it is,
// as in JavaScript, where it is two UTF-16 code units.
func UpperFirst(s string) string {
	return decodeUnits(upperFirstUnits(encodeUnits(s)))
}

// LowerFirst lowercases the first character of s with the full Unicode
// mapping ("İa" gives "i̇a"). A first character above U+FFFF is left as it is,
// as in JavaScript, where it is two UTF-16 code units.
func LowerFirst(s string) string {
	return decodeUnits(lowerFirstUnits(encodeUnits(s)))
}

// PascalCase joins the words with no separator, each with its first letter
// uppercased: "foo-bar_baz" gives "FooBarBaz".
func PascalCase[W Words](w W, opts ...CaseOptions) string {
	return decodeCase(pascalUnits(wordParts(w), normalize(opts)))
}

// CamelCase is PascalCase with the first letter lowercased: "foo-bar" gives
// "fooBar".
func CamelCase[W Words](w W, opts ...CaseOptions) string {
	return decodeCase(lowerFirstUnits(pascalUnits(wordParts(w), normalize(opts))))
}

// KebabCase lowercases the words and joins them with joiner, "-" when none is
// given: "fooBar" gives "foo-bar". An empty joiner is used as is. Empty words
// are kept.
func KebabCase[W Words](w W, joiner ...string) string {
	j := "-"
	if len(joiner) > 0 {
		j = joiner[0]
	}
	return kebabCase(wordParts(w), j)
}

// SnakeCase is KebabCase with "_": "fooBar" gives "foo_bar".
func SnakeCase[W Words](w W) string { return kebabCase(wordParts(w), "_") }

// FlatCase is KebabCase with no joiner: "foo-bar" gives "foobar".
func FlatCase[W Words](w W) string { return kebabCase(wordParts(w), "") }

// TrainCase drops empty words, uppercases the first letter of each word and
// joins them with "-": "fooBar" gives "Foo-Bar".
func TrainCase[W Words](w W, opts ...CaseOptions) string {
	norm := normalize(opts)
	var out [][]uint16
	for _, p := range wordParts(w) {
		if len(p) > 0 {
			out = append(out, upperFirstUnits(maybeLower(p, norm)))
		}
	}
	return decodeCase(joinUnits(out, "-"))
}

// TitleCase is TrainCase joined with spaces, except that minor words ("a",
// "and", "the", "of" and others, matched ASCII case-insensitively) are
// lowercased: "this-IS-aTitle" gives "This is a Title".
func TitleCase[W Words](w W, opts ...CaseOptions) string {
	norm := normalize(opts)
	var out [][]uint16
	for _, p := range wordParts(w) {
		switch {
		case len(p) == 0:
		case isMinorWord(p):
			out = append(out, lowerUnits(p))
		default:
			out = append(out, upperFirstUnits(maybeLower(p, norm)))
		}
	}
	return decodeCase(joinUnits(out, " "))
}

// wordParts returns w split by case when it is a string, or its words as they
// are when it is a slice.
func wordParts[W Words](w W) [][]uint16 {
	switch v := any(w).(type) {
	case string:
		return splitUnits(v, defaultSeparators)
	case []string:
		return encodeAll(v)
	}
	rv := reflect.ValueOf(w)
	if rv.Kind() == reflect.String {
		return splitUnits(rv.String(), defaultSeparators)
	}
	words := make([]string, rv.Len())
	for i := range words {
		words[i] = rv.Index(i).String()
	}
	return encodeAll(words)
}

func encodeAll(words []string) [][]uint16 {
	parts := make([][]uint16, len(words))
	for i, s := range words {
		parts[i] = encodeUnits(s)
	}
	return parts
}

func normalize(opts []CaseOptions) bool { return len(opts) > 0 && opts[0].Normalize }

func maybeLower(p []uint16, lower bool) []uint16 {
	if lower {
		return lowerUnits(p)
	}
	return p
}

func pascalUnits(parts [][]uint16, norm bool) []uint16 {
	for i, p := range parts {
		parts[i] = upperFirstUnits(maybeLower(p, norm))
	}
	return joinUnits(parts, "")
}

func kebabCase(parts [][]uint16, joiner string) string {
	for i, p := range parts {
		parts[i] = lowerUnits(p)
	}
	return decodeCase(joinUnits(parts, joiner))
}

// joinUnits joins parts with sep in code units, so the halves of a surrogate
// pair that splitUnits put in adjacent parts join back up when sep is "".
func joinUnits(parts [][]uint16, sep string) []uint16 {
	s := encodeUnits(sep)
	var out []uint16
	for i, p := range parts {
		if i > 0 {
			out = append(out, s...)
		}
		out = append(out, p...)
	}
	return out
}

// decodeCase decodes a converter's joined result.
func decodeCase(u []uint16) string {
	// DIVERGENCE(d1-cases): a lone surrogate left next to a joiner becomes U+FFFD; JavaScript keeps it.
	return decodeUnits(u)
}

// minorWords are the words TitleCase keeps lowercase.
var minorWords = []string{"a", "an", "and", "as", "at", "but", "by", "for", "if", "in", "is", "nor", "of", "on", "or", "the", "to", "with"}

// isMinorWord matches p against minorWords ignoring ASCII case only, as the
// JavaScript /^(...)$/i regex without the u flag does: "ſ" and the Kelvin sign
// never match.
func isMinorWord(p []uint16) bool {
	if len(p) > 4 {
		return false
	}
	var b [4]byte
	for i, c := range p {
		switch {
		case 'a' <= c && c <= 'z':
			b[i] = byte(c)
		case 'A' <= c && c <= 'Z':
			b[i] = byte(c) + 'a' - 'A'
		default:
			return false
		}
	}
	return slices.Contains(minorWords, string(b[:len(p)]))
}
