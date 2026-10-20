package scule

import (
	"fmt"
	"slices"
	"testing"
)

func TestIsUppercase(t *testing.T) {
	tests := []struct {
		in        string
		upper, ok bool
	}{
		{"", false, true},
		{"a", false, true},
		{"A", true, true},
		{"aB", true, true},
		{"a1", false, false},
		{"Ⅻ", true, true},
		{"ǅ", true, true},
		{"ǈ", true, true},
		{"Ⓐ", true, true},
		{"\U0001D400", false, true},
		{"١", false, true},
		{"ß", false, true},
		{"İ", true, true},
		{"ʰ", false, true},
		{"Σ", true, true},
		{"ᾈ", true, true},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%q", tt.in), func(t *testing.T) {
			upper, ok := IsUppercase(tt.in)
			if upper != tt.upper || ok != tt.ok {
				t.Errorf("got (%v, %v), want (%v, %v)", upper, ok, tt.upper, tt.ok)
			}
		})
	}
}

func TestUpperFirstFullMapping(t *testing.T) {
	tests := []struct{ in, want string }{
		{"ßa", "SSa"},
		{"ŉx", "ʼNx"},
		{"ﬀ", "FF"},
		{"ǰ", "J\u030C"},
		{"ΐ", "Ι\u0308\u0301"},
		{"ǆa", "Ǆa"},
		{"ᾳ", "ΑΙ"},
		{"\U00010428abc", "\U00010428abc"},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%q", tt.in), func(t *testing.T) {
			if got := UpperFirst(tt.in); got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestLowerFirstFullMapping(t *testing.T) {
	tests := []struct{ in, want string }{
		{"İa", "i\u0307a"},
		{"Σ", "σ"},
		{"ΣΑ", "σΑ"},
		{"ǅa", "ǆa"},
		{"\U00010400abc", "\U00010400abc"},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%q", tt.in), func(t *testing.T) {
			if got := LowerFirst(tt.in); got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestFirstUnitsLeaveLoneSurrogate(t *testing.T) {
	in := []uint16{0xDC00, 'a'}
	if got := upperFirstUnits(in); !slices.Equal(got, in) {
		t.Errorf("upperFirstUnits: got %x, want %x", got, in)
	}
	if got := lowerFirstUnits(in); !slices.Equal(got, in) {
		t.Errorf("lowerFirstUnits: got %x, want %x", got, in)
	}
}

func TestLowerUnitsFinalSigma(t *testing.T) {
	tests := []struct{ in, want string }{
		{"Σ", "σ"},
		{"AΣ", "aς"},
		{"AΣB", "aσb"},
		{"AΣΣ", "aσς"},
		{"A Σ", "a σ"},
		{"1Σ", "1σ"},
		{"AΣ.", "aς."},
		{"A.Σ", "a.ς"},
		{"A\u0301Σ", "a\u0301ς"},
		{"AΣ\u0301", "aς\u0301"},
		{"AΣ\u0301b", "aσ\u0301b"},
		{"AΣ\U00010428", "aσ\U00010428"},
		{"\U00010400Σ", "\U00010428ς"},
		// Cased and case-ignorable at once: skipped, as ICU does.
		{"ʰΣ", "ʰσ"},
		{"AʰΣ", "aʰς"},
		{"\u0345Σ", "\u0345σ"},
		{"AΣʰ", "aςʰ"},
		{"AΣʰa", "aσʰa"},
		{"ΟΔΟΣ-ΚΑΛΟΣ", "οδος-καλος"},
		{"İ", "i\u0307"},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%q", tt.in), func(t *testing.T) {
			if got := decodeUnits(lowerUnits(encodeUnits(tt.in))); got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestLowerUnitsLoneSurrogateContext(t *testing.T) {
	// A lone surrogate is neither cased nor case-ignorable, and maps to itself.
	in := []uint16{'A', capitalSigma, 0xD801}
	want := []uint16{'a', smallFinalSigma, 0xD801}
	if got := lowerUnits(in); !slices.Equal(got, want) {
		t.Errorf("got %x, want %x", got, want)
	}
}
