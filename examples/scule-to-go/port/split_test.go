package scule

import (
	"fmt"
	"slices"
	"testing"
)

func TestSplitByCaseEdges(t *testing.T) {
	tests := []struct {
		in   string
		want []string
	}{
		{"a\U00010400", []string{"a", "\U00010400"}},
		{"CAFE\u0301", []string{"CAF", "E\u0301"}},
		{"a1B", []string{"a1B"}},
		{"A1b", []string{"A1b"}},
		{"ABCdef", []string{"AB", "Cdef"}},
		{"ǅa", []string{"ǅa"}},
		{"aǅ", []string{"a", "ǅ"}},
		{"ΣΑ-ΟΔΟΣ", []string{"ΣΑ", "ΟΔΟΣ"}},
		{"-", []string{"", ""}},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%q", tt.in), func(t *testing.T) {
			if got := SplitByCase(tt.in); !slices.Equal(got, tt.want) {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestSplitByCaseWithSeparators(t *testing.T) {
	tests := []struct {
		in         string
		separators []string
		want       []string
	}{
		{"a😀b", []string{"😀"}, []string{"a", "b"}},
		{"a--b", []string{"--"}, []string{"a--b"}},
		{"a-b", []string{""}, []string{"a-b"}},
		{"foo-bar_Baz", []string{}, []string{"foo-bar_", "Baz"}},
		{"foo-bar_Baz", nil, []string{"foo-bar_", "Baz"}},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%q/%q", tt.in, tt.separators), func(t *testing.T) {
			if got := SplitByCaseWith(tt.in, tt.separators); !slices.Equal(got, tt.want) {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestSplitByCaseEmptyIsNotNil(t *testing.T) {
	if got := SplitByCase(""); got == nil || len(got) != 0 {
		t.Errorf("got %#v, want an empty non-nil slice", got)
	}
}

// The falling edge cuts in UTF-16 code units: after a capital above U+FFFF
// only its low surrogate moves to the next part.
func TestSplitUnitsCutsSurrogatePair(t *testing.T) {
	tests := []struct {
		in   string
		want [][]uint16
	}{
		{"\U00010400a", [][]uint16{{0xD801}, {0xDC00, 'a'}}},
		{"A\U00010400a", [][]uint16{{'A', 0xD801}, {0xDC00, 'a'}}},
		{"\U00010400\U00010400a", [][]uint16{{0xD801, 0xDC00, 0xD801}, {0xDC00, 'a'}}},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%q", tt.in), func(t *testing.T) {
			got := splitUnits(tt.in, defaultSeparators)
			if !slices.EqualFunc(got, tt.want, slices.Equal[[]uint16]) {
				t.Fatalf("got %x, want %x", got, tt.want)
			}
			if joined := decodeUnits(slices.Concat(got...)); joined != tt.in {
				t.Errorf("joined parts %q, want %q", joined, tt.in)
			}
		})
	}
}

func TestSplitByCaseLoneSurrogate(t *testing.T) {
	// Divergence d1 (see decodeUnits): JavaScript returns ["\ud801", "\udc00a"].
	want := []string{"\uFFFD", "\uFFFDa"}
	if got := SplitByCase("\U00010400a"); !slices.Equal(got, want) {
		t.Errorf("got %q, want %q", got, want)
	}
}
