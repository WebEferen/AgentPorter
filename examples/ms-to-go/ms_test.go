package ms_test

import (
	"errors"
	"fmt"
	"math"
	"strings"
	"testing"

	"github.com/agentporter-examples/ms"
)

// ref tags a subtest with its source test in tests.js. go test rewrites the spaces in subtest names to
// underscores, so imported refs need the spaces restored to match the tests.js ids.
func ref(id string) string { return "[ref:tests.js::" + id + "]" }

type parseCase struct {
	in   string
	want float64
}

type formatCase struct {
	in   float64
	want string
}

func checkParse(t *testing.T, cases ...parseCase) {
	t.Helper()
	for _, c := range cases {
		got, ok := ms.Parse(c.in)
		if !ok || got != c.want {
			t.Errorf("Parse(%q) = %v, %v; want %v, true", c.in, got, ok, c.want)
		}
	}
}

func checkNoValue(t *testing.T, inputs ...string) {
	t.Helper()
	for _, in := range inputs {
		if got, ok := ms.Parse(in); ok {
			t.Errorf("Parse(%q) = %v, true; want no value", in, got)
		}
	}
}

func checkFormat(t *testing.T, name string, f func(float64) (string, error), cases ...formatCase) {
	t.Helper()
	for _, c := range cases {
		got, err := f(c.in)
		if err != nil || got != c.want {
			t.Errorf("%s(%v) = %q, %v; want %q, nil", name, c.in, got, err, c.want)
		}
	}
}

func checkInvalid(t *testing.T, name string, f func(float64) (string, error), in float64) {
	t.Helper()
	got, err := f(in)
	var invalid *ms.InvalidValueError
	if !errors.As(err, &invalid) {
		t.Fatalf("%s(%v) = %q, %v; want *InvalidValueError", name, in, got, err)
	}
	const want = "val is not a non-empty string or a valid number. val=null"
	if err.Error() != want {
		t.Errorf("%s(%v) error = %q; want %q", name, in, err.Error(), want)
	}
}

func TestParseString(t *testing.T) {
	tests := []struct {
		it    string
		check func(t *testing.T)
	}{
		{"should not throw an error", func(t *testing.T) { checkParse(t, parseCase{"1m", 60000}) }},
		{"should preserve ms", func(t *testing.T) { checkParse(t, parseCase{"100", 100}) }},
		{"should convert from m to ms", func(t *testing.T) { checkParse(t, parseCase{"1m", 60000}) }},
		{"should convert from h to ms", func(t *testing.T) { checkParse(t, parseCase{"1h", 3600000}) }},
		{"should convert d to ms", func(t *testing.T) { checkParse(t, parseCase{"2d", 172800000}) }},
		{"should convert w to ms", func(t *testing.T) { checkParse(t, parseCase{"3w", 1814400000}) }},
		{"should convert s to ms", func(t *testing.T) { checkParse(t, parseCase{"1s", 1000}) }},
		{"should convert ms to ms", func(t *testing.T) { checkParse(t, parseCase{"100ms", 100}) }},
		{"should work with decimals", func(t *testing.T) { checkParse(t, parseCase{"1.5h", 5400000}) }},
		{"should work with multiple spaces", func(t *testing.T) { checkParse(t, parseCase{"1   s", 1000}) }},
		// The source returns undefined here (isNaN(undefined) is true); the port reports no value.
		{"should return NaN if invalid", func(t *testing.T) { checkNoValue(t, "☃", "10-.5") }},
		{"should be case-insensitive", func(t *testing.T) { checkParse(t, parseCase{"1.5H", 5400000}) }},
		{"should work with numbers starting with .", func(t *testing.T) { checkParse(t, parseCase{".5ms", 0.5}) }},
		{"should work with negative integers", func(t *testing.T) { checkParse(t, parseCase{"-100ms", -100}) }},
		{"should work with negative decimals", func(t *testing.T) {
			checkParse(t, parseCase{"-1.5h", -5400000}, parseCase{"-10.5h", -37800000})
		}},
		{`should work with negative decimals starting with "."`, func(t *testing.T) {
			checkParse(t, parseCase{"-.5h", -1800000})
		}},
	}
	for _, tt := range tests {
		t.Run(ref("ms(string)::"+tt.it), tt.check)
	}
}

func TestParseLongString(t *testing.T) {
	tests := []struct {
		it    string
		cases []parseCase
	}{
		{"should not throw an error", []parseCase{{"53 milliseconds", 53}}},
		{"should convert milliseconds to ms", []parseCase{{"53 milliseconds", 53}}},
		{"should convert msecs to ms", []parseCase{{"17 msecs", 17}}},
		{"should convert sec to ms", []parseCase{{"1 sec", 1000}}},
		{"should convert from min to ms", []parseCase{{"1 min", 60000}}},
		{"should convert from hr to ms", []parseCase{{"1 hr", 3600000}}},
		{"should convert days to ms", []parseCase{{"2 days", 172800000}}},
		{"should work with decimals", []parseCase{{"1.5 hours", 5400000}}},
		{"should work with negative integers", []parseCase{{"-100 milliseconds", -100}}},
		{"should work with negative decimals", []parseCase{{"-1.5 hours", -5400000}}},
		{`should work with negative decimals starting with "."`, []parseCase{{"-.5 hr", -1800000}}},
	}
	for _, tt := range tests {
		t.Run(ref("ms(long string)::"+tt.it), func(t *testing.T) { checkParse(t, tt.cases...) })
	}
}

func TestFormatLong(t *testing.T) {
	tests := []struct {
		it    string
		cases []formatCase
	}{
		{"should not throw an error", []formatCase{{500, "500 ms"}}},
		{"should support milliseconds", []formatCase{{500, "500 ms"}, {-500, "-500 ms"}}},
		{"should support seconds", []formatCase{
			{1000, "1 second"}, {1200, "1 second"}, {10000, "10 seconds"},
			{-1000, "-1 second"}, {-1200, "-1 second"}, {-10000, "-10 seconds"},
		}},
		{"should support minutes", []formatCase{
			{60 * 1000, "1 minute"}, {60 * 1200, "1 minute"}, {60 * 10000, "10 minutes"},
			{-1 * 60 * 1000, "-1 minute"}, {-1 * 60 * 1200, "-1 minute"}, {-1 * 60 * 10000, "-10 minutes"},
		}},
		{"should support hours", []formatCase{
			{60 * 60 * 1000, "1 hour"}, {60 * 60 * 1200, "1 hour"}, {60 * 60 * 10000, "10 hours"},
			{-1 * 60 * 60 * 1000, "-1 hour"}, {-1 * 60 * 60 * 1200, "-1 hour"}, {-1 * 60 * 60 * 10000, "-10 hours"},
		}},
		{"should support days", []formatCase{
			{24 * 60 * 60 * 1000, "1 day"}, {24 * 60 * 60 * 1200, "1 day"}, {24 * 60 * 60 * 10000, "10 days"},
			{-1 * 24 * 60 * 60 * 1000, "-1 day"}, {-1 * 24 * 60 * 60 * 1200, "-1 day"},
			{-1 * 24 * 60 * 60 * 10000, "-10 days"},
		}},
		{"should round", []formatCase{{234234234, "3 days"}, {-234234234, "-3 days"}}},
	}
	for _, tt := range tests {
		t.Run(ref("ms(number, { long: true })::"+tt.it), func(t *testing.T) {
			checkFormat(t, "FormatLong", ms.FormatLong, tt.cases...)
		})
	}
}

func TestFormat(t *testing.T) {
	tests := []struct {
		it    string
		cases []formatCase
	}{
		{"should not throw an error", []formatCase{{500, "500ms"}}},
		{"should support milliseconds", []formatCase{{500, "500ms"}, {-500, "-500ms"}}},
		{"should support seconds", []formatCase{{1000, "1s"}, {10000, "10s"}, {-1000, "-1s"}, {-10000, "-10s"}}},
		{"should support minutes", []formatCase{
			{60 * 1000, "1m"}, {60 * 10000, "10m"}, {-1 * 60 * 1000, "-1m"}, {-1 * 60 * 10000, "-10m"},
		}},
		{"should support hours", []formatCase{
			{60 * 60 * 1000, "1h"}, {60 * 60 * 10000, "10h"}, {-1 * 60 * 60 * 1000, "-1h"}, {-1 * 60 * 60 * 10000, "-10h"},
		}},
		{"should support days", []formatCase{
			{24 * 60 * 60 * 1000, "1d"}, {24 * 60 * 60 * 10000, "10d"},
			{-1 * 24 * 60 * 60 * 1000, "-1d"}, {-1 * 24 * 60 * 60 * 10000, "-10d"},
		}},
		{"should round", []formatCase{{234234234, "3d"}, {-234234234, "-3d"}}},
	}
	for _, tt := range tests {
		t.Run(ref("ms(number)::"+tt.it), func(t *testing.T) {
			checkFormat(t, "Format", ms.Format, tt.cases...)
		})
	}
}

// ms(""), ms(undefined), ms(null), ms([]) and ms({}) have no Go counterpart: see the empty-string and
// typed-input divergences and .porter/reftests.json.
func TestInvalidInputs(t *testing.T) {
	tests := []struct {
		it string
		in float64
	}{
		{"should throw an error, when ms(NaN)", math.NaN()},
		{"should throw an error, when ms(Infinity)", math.Inf(1)},
		{"should throw an error, when ms(-Infinity)", math.Inf(-1)},
	}
	for _, tt := range tests {
		t.Run(ref("ms(invalid inputs)::"+tt.it), func(t *testing.T) {
			checkInvalid(t, "Format", ms.Format, tt.in)
			checkInvalid(t, "FormatLong", ms.FormatLong, tt.in)
		})
	}
}

func TestParseEmptyStringIsNotADuration(t *testing.T) {
	checkNoValue(t, "")
}

func TestInvalidValueErrorThroughWrapping(t *testing.T) {
	_, err := ms.Format(math.NaN())
	wrapped := fmt.Errorf("config timeout: %w", err)
	var invalid *ms.InvalidValueError
	if !errors.As(wrapped, &invalid) {
		t.Fatalf("errors.As(%v) = false; want *InvalidValueError", wrapped)
	}
	if !math.IsNaN(invalid.Value) {
		t.Errorf("Value = %v; want NaN", invalid.Value)
	}
}

func TestParseGrammar(t *testing.T) {
	checkParse(t,
		parseCase{"1 ", 1},
		parseCase{"01", 1},
		parseCase{"1y", 31557600000},
		parseCase{"1 YRS", 31557600000},
		parseCase{"1 MilliSeconds", 1},
		parseCase{"1.15h", 4139999.9999999995},
		parseCase{"1.1d", 95040000.00000001},
		parseCase{strings.Repeat("9", 100), 1e100},
		parseCase{"1" + strings.Repeat(" ", 99), 1},
	)
	checkNoValue(t,
		"1.", ".", "-", "-.", "1e3", "+1", "1,5s", "1 s ", "1\ts", "1 2", "s", "1.5.5", "1 secss",
		strings.Repeat("9", 101), "1"+strings.Repeat(" ", 100),
	)
}

func TestParseNegativeZero(t *testing.T) {
	got, ok := ms.Parse("-0")
	if !ok || got != 0 || !math.Signbit(got) {
		t.Errorf("Parse(%q) = %v, %v; want -0, true", "-0", got, ok)
	}
}

// Go's Unicode-aware case folding would accept these; the JavaScript grammar folds ASCII only.
func TestParseUnicodeIsNotFolded(t *testing.T) {
	checkNoValue(t,
		"1ſ", "1 ſecs", "1 weeK", "1 mİn", "1 mın", "1µs", "1ś",
		"１", "٣", "¹s", "1☃", "\U0001f600",
	)
}

func TestFormatRounding(t *testing.T) {
	checkFormat(t, "Format", ms.Format,
		formatCase{1500, "2s"},
		formatCase{-1500, "-1s"},
		formatCase{-2500, "-2s"},
		formatCase{1499, "1s"},
		formatCase{59999, "60s"},
		formatCase{3599999, "60m"},
		formatCase{86399999, "24h"},
		formatCase{31557600000, "365d"},
		formatCase{3.891110078048109e+23, "4503599627370497d"},
	)
}

func TestFormatLongPlural(t *testing.T) {
	checkFormat(t, "FormatLong", ms.FormatLong,
		formatCase{1499, "1 second"},
		formatCase{1500, "2 seconds"},
		formatCase{-1500, "-1 seconds"},
		formatCase{-90000, "-1 minutes"},
		formatCase{0.5, "0.5 ms"},
	)
}

func TestFormatNumberText(t *testing.T) {
	checkFormat(t, "Format", ms.Format,
		formatCase{0, "0ms"},
		formatCase{math.Copysign(0, -1), "0ms"},
		formatCase{0.30000000000000004, "0.30000000000000004ms"},
		formatCase{1e-6, "0.000001ms"},
		formatCase{9.99e-7, "9.99e-7ms"},
		formatCase{-1e-7, "-1e-7ms"},
		formatCase{5e-324, "5e-324ms"},
		formatCase{8.64e+28, "999999999999999900000d"},
		formatCase{8.640000000000001e+28, "1.0000000000000001e+21d"},
		formatCase{8.64e+29, "1e+22d"},
		formatCase{1e+300, "1.1574074074074075e+292d"},
		formatCase{-1e+300, "-1.1574074074074075e+292d"},
	)
}
