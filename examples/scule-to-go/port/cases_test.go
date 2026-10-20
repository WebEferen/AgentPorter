package scule

import (
	"fmt"
	"testing"
)

type caseRow struct {
	line     int
	in, want string
}

func runRows(t *testing.T, rows []caseRow, fn func(string) string) {
	t.Helper()
	for _, tt := range rows {
		t.Run(fmt.Sprintf("%q", tt.in), func(t *testing.T) {
			t.Logf("[ref: test/scule.test.ts:%d]", tt.line)
			if got := fn(tt.in); got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

var normalized = CaseOptions{Normalize: true}

// Ported from test/scule.test.ts. Each row logs its source test id.

func TestPascalCase(t *testing.T) {
	runRows(t, []caseRow{
		{46, "", ""},
		{47, "foo", "Foo"},
		{48, "foo-bAr", "FooBAr"},
		{49, "FooBARb", "FooBaRb"},
		{50, "foo_bar-baz/qux", "FooBarBazQux"},
		{51, "FOO_BAR", "FooBar"},
		{52, "foo--bar-Baz", "FooBarBaz"},
	}, func(s string) string { return PascalCase(s, normalized) })
}

func TestCamelCase(t *testing.T) {
	runRows(t, []caseRow{
		{60, "FooBarBaz", "fooBarBaz"},
		{61, "FOO_BAR", "fooBar"},
	}, func(s string) string { return CamelCase(s, normalized) })
}

func TestKebabCase(t *testing.T) {
	runRows(t, []caseRow{
		{69, "", ""},
		{70, "foo", "foo"},
		{71, "foo/Bar", "foo-bar"},
		{72, "foo-bAr", "foo-b-ar"},
		{73, "foo--bar", "foo--bar"},
		{74, "FooBAR", "foo-bar"},
		{75, "ALink", "a-link"},
		{76, "FOO_BAR", "foo-bar"},
	}, func(s string) string { return KebabCase(s) })
}

func TestSnakeCase(t *testing.T) {
	runRows(t, []caseRow{
		{84, "FooBarBaz", "foo_bar_baz"},
		{85, "FOO_BAR", "foo_bar"},
	}, SnakeCase[string])
}

func TestTrainCase(t *testing.T) {
	runRows(t, []caseRow{
		{113, "", ""},
		{114, "f", "F"},
		{115, "foo", "Foo"},
		{116, "foo-bAr", "Foo-B-Ar"},
		{117, "AcceptCH", "Accept-CH"},
		{118, "foo_bar-baz/qux", "Foo-Bar-Baz-Qux"},
		{119, "FOO_BAR", "FOO-BAR"},
		{120, "foo--bar-Baz", "Foo-Bar-Baz"},
		{121, "WWW-authenticate", "WWW-Authenticate"},
		{122, "WWWAuthenticate", "WWW-Authenticate"},
	}, func(s string) string { return TrainCase(s) })
}

func TestTrainCaseNormalize(t *testing.T) {
	runRows(t, []caseRow{
		{128, "AcceptCH", "Accept-Ch"},
		{129, "FOO_BAR", "Foo-Bar"},
		{130, "WWW-authenticate", "Www-Authenticate"},
	}, func(s string) string { return TrainCase(s, normalized) })
}

func TestTitleCase(t *testing.T) {
	runRows(t, []caseRow{
		{138, "", ""},
		{139, "f", "F"},
		{140, "foo", "Foo"},
		{141, "foo-bar", "Foo Bar"},
		{142, "this-IS-aTitle", "This is a Title"},
	}, func(s string) string { return TitleCase(s) })
}

func TestFlatCase(t *testing.T) {
	runRows(t, []caseRow{
		{150, "", ""},
		{151, "foo", "foo"},
		{152, "foo-bAr", "foobar"},
		{153, "FooBARb", "foobarb"},
		{154, "foo_bar-baz/qux", "foobarbazqux"},
		{155, "FOO_BAR", "foobar"},
		{156, "foo--bar-Baz", "foobarbaz"},
	}, FlatCase[string])
}

type label string

type labels []string

func TestConverterEdges(t *testing.T) {
	tests := []struct {
		name, got, want string
	}{
		{"words are not re-split", KebabCase([]string{"FooBar", "Baz"}), "foobar-baz"},
		{"named string type", PascalCase(label("foo-bar")), "FooBar"},
		{"named slice type", TrainCase(labels{"", "a", "b"}), "A-B"},
		{"empty joiner", KebabCase("fooBar", ""), "foobar"},
		{"final sigma per part", KebabCase("ΟΔΟΣ-ΚΑΛΟΣ"), "οδος-καλος"},
		{"full mapping", CamelCase("ßfoo"), "sSfoo"},
		{"surrogate halves rejoin", FlatCase("\U00010400a"), "\U00010400a"},
		{"surrogate halves rejoin in pascal", PascalCase("\U00010400a"), "\U00010400a"},
		{"minor word ASCII only", TitleCase([]string{"a\u017F", "AS"}), "A\u017F as"},
		// Divergence d1-cases (see decodeCase): JavaScript returns "\ud801-\udc00a".
		{"lone surrogate next to joiner", KebabCase("\U00010400a"), "\uFFFD-\uFFFDa"},
	}
	for _, tt := range tests {
		if tt.got != tt.want {
			t.Errorf("%s: got %q, want %q", tt.name, tt.got, tt.want)
		}
	}
}
