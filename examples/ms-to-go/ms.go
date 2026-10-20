package ms

import (
	"math"
	"strconv"
	"strings"
)

const (
	second = 1000
	minute = second * 60
	hour   = minute * 60
	day    = hour * 24
	week   = day * 7
	year   = day * 365.25
)

// maxParseLen is the longest input Parse reads. Only ASCII can match the grammar, so counting bytes gives
// the same answers as the JavaScript package counting UTF-16 code units.
const maxParseLen = 100

var unitMillis = map[string]float64{
	"years": year, "year": year, "yrs": year, "yr": year, "y": year,
	"weeks": week, "week": week, "w": week,
	"days": day, "day": day, "d": day,
	"hours": hour, "hour": hour, "hrs": hour, "hr": hour, "h": hour,
	"minutes": minute, "minute": minute, "mins": minute, "min": minute, "m": minute,
	"seconds": second, "second": second, "secs": second, "sec": second, "s": second,
	"milliseconds": 1, "millisecond": 1, "msecs": 1, "msec": 1, "ms": 1,
}

var formatUnits = []struct {
	millis float64
	short  string
	long   string
}{
	{day, "d", "day"},
	{hour, "h", "hour"},
	{minute, "m", "minute"},
	{second, "s", "second"},
}

// Parse converts a duration such as "2 days", "1.5h", ".5ms" or "-100" to milliseconds.
//
// The input is a number (ASCII digits, an optional leading '-', an optional decimal point, no exponent),
// any number of spaces, and an optional unit: ms, msec(s), millisecond(s), s, sec(s), second(s), m,
// min(s), minute(s), h, hr(s), hour(s), d, day(s), w, week(s), y, yr(s) or year(s), in any ASCII case.
// Without a unit the number is milliseconds. A year is 365.25 days. ok is false when s does not have this
// form or is longer than 100 bytes.
func Parse(s string) (millis float64, ok bool) {
	// DIVERGENCE(empty-string): the JavaScript ms("") throws; here "" is just a string that is not a
	// duration and falls through to ok == false.
	if len(s) > maxParseLen {
		return 0, false
	}
	num, rest, ok := cutNumber(s)
	if !ok {
		return 0, false
	}
	unit := 1.0
	if rest = strings.TrimLeft(rest, " "); rest != "" {
		if unit, ok = unitMillis[lowerASCII(rest)]; !ok {
			return 0, false
		}
	}
	n, err := strconv.ParseFloat(num, 64)
	if err != nil {
		return 0, false
	}
	return n * unit, true
}

// cutNumber splits s into a leading -?(\d+|\d*\.\d+) with ASCII digits and the rest.
func cutNumber(s string) (num, rest string, ok bool) {
	i := 0
	if i < len(s) && s[i] == '-' {
		i++
	}
	start := i
	i = skipDigits(s, i)
	if i < len(s) && s[i] == '.' {
		end := skipDigits(s, i+1)
		if end == i+1 {
			return "", "", false
		}
		i = end
	} else if i == start {
		return "", "", false
	}
	return s[:i], s[i:], true
}

func skipDigits(s string, i int) int {
	for i < len(s) && '0' <= s[i] && s[i] <= '9' {
		i++
	}
	return i
}

// lowerASCII lower-cases A-Z only. strings.ToLower and strings.EqualFold would also fold 'ſ' (U+017F) and
// the Kelvin sign (U+212A) to ASCII letters, which the JavaScript grammar rejects.
func lowerASCII(s string) string {
	b := []byte(s)
	for i, c := range b {
		if 'A' <= c && c <= 'Z' {
			b[i] = c + ('a' - 'A')
		}
	}
	return string(b)
}

// Format writes milliseconds in the largest unit the magnitude reaches, rounded to a whole count:
// "1d", "-3h", "10m", "1s". Below one second the value is written as is, fractions included: "500ms",
// "0.5ms". Days are the largest unit. Halves round toward +Inf, so -1500 is "-1s".
//
// Format returns an *InvalidValueError for NaN and the infinities.
func Format(ms float64) (string, error) {
	return format(ms, false)
}

// FormatLong is Format with unit names: "1 day", "-3 hours", "10 minutes", "500 ms". The unit is plural
// when the magnitude is at least 1.5 units, judged before rounding, so 1499 is "1 second", 1500 is
// "2 seconds" and -1500 is "-1 seconds".
//
// FormatLong returns an *InvalidValueError for NaN and the infinities.
func FormatLong(ms float64) (string, error) {
	return format(ms, true)
}

func format(ms float64, long bool) (string, error) {
	// DIVERGENCE(typed-input): only a float64 reaches here, and FormatLong replaces a truthy
	// options.long. The JavaScript errors for null, booleans, arrays and objects, and its truthiness
	// rules for non-boolean options, have no Go counterpart.
	if math.IsNaN(ms) || math.IsInf(ms, 0) {
		return "", &InvalidValueError{Value: ms}
	}
	abs := math.Abs(ms)
	for _, u := range formatUnits {
		if abs < u.millis {
			continue
		}
		count := formatNumber(jsRound(ms / u.millis))
		switch {
		case !long:
			return count + u.short, nil
		case abs >= 1.5*u.millis:
			return count + " " + u.long + "s", nil
		default:
			return count + " " + u.long, nil
		}
	}
	if long {
		return formatNumber(ms) + " ms", nil
	}
	return formatNumber(ms) + "ms", nil
}

// InvalidValueError is returned by Format and FormatLong for a value they cannot format: NaN, +Inf or
// -Inf. Test for it with errors.As.
type InvalidValueError struct {
	Value float64
}

// Error returns the message the JavaScript package throws, with the value written as JSON.stringify
// writes it (null for NaN and the infinities).
func (e *InvalidValueError) Error() string {
	val := "null"
	if !math.IsNaN(e.Value) && !math.IsInf(e.Value, 0) {
		val = formatNumber(e.Value)
	}
	return "val is not a non-empty string or a valid number. val=" + val
}
