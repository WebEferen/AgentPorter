package scule

import (
	"fmt"
	"slices"
	"testing"
)

// Ported from test/scule.test.ts. Each row logs its source test id as
// [ref: test/scule.test.ts:<line>].

func TestSplitByCase(t *testing.T) {
	tests := []struct {
		line       int
		in         string
		want       []string
		separators []string
	}{
		{17, "", []string{}, nil},
		{18, "foo", []string{"foo"}, nil},
		{19, "fooBar", []string{"foo", "Bar"}, nil},
		{20, "FooBarBaz", []string{"Foo", "Bar", "Baz"}, nil},
		{21, "FooBARb", []string{"Foo", "BA", "Rb"}, nil},
		{22, "foo_bar-baz/qux", []string{"foo", "bar", "baz", "qux"}, nil},
		{23, "foo--bar-Baz", []string{"foo", "", "bar", "Baz"}, nil},
		{24, "FOO_BAR", []string{"FOO", "BAR"}, nil},
		{25, "foo123-bar", []string{"foo123", "bar"}, nil},
		{26, "FOOBar", []string{"FOO", "Bar"}, nil},
		{27, "ALink", []string{"A", "Link"}, nil},
		{29, "foo\\Bar.fuzz-FIZz", []string{"foo", "Bar", "fuzz", "FI", "Zz"}, []string{"\\", ".", "-"}},
		{34, "new-name-value", []string{"new-name-value"}, []string{"_"}},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%q", tt.in), func(t *testing.T) {
			t.Logf("[ref: test/scule.test.ts:%d]", tt.line)
			var got []string
			if tt.separators != nil {
				got = SplitByCaseWith(tt.in, tt.separators)
			} else {
				got = SplitByCase(tt.in)
			}
			if !slices.Equal(got, tt.want) {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestUpperFirst(t *testing.T) {
	tests := []struct {
		line     int
		in, want string
	}{
		{93, "", ""},
		{94, "foo", "Foo"},
		{95, "Foo", "Foo"},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%q", tt.in), func(t *testing.T) {
			t.Logf("[ref: test/scule.test.ts:%d]", tt.line)
			if got := UpperFirst(tt.in); got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestLowerFirst(t *testing.T) {
	tests := []struct {
		line     int
		in, want string
	}{
		{103, "", ""},
		{104, "foo", "foo"},
		{105, "Foo", "foo"},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%q", tt.in), func(t *testing.T) {
			t.Logf("[ref: test/scule.test.ts:%d]", tt.line)
			if got := LowerFirst(tt.in); got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}
