package ms

import (
	"math"
	"strconv"
	"strings"
)

// jsRound rounds like JavaScript's Math.round: ties go toward +Inf, so -2.5 rounds to -2.
// math.Round sends ties away from zero, and math.Floor(x+0.5) is off by one for odd integers in
// [2^52, 2^53) because the addition itself rounds. x-math.Floor(x) is exact for every double.
func jsRound(x float64) float64 {
	r := math.Floor(x)
	if x-r >= 0.5 {
		r++
	}
	return r
}

// formatNumber prints a finite x the way JavaScript's Number.prototype.toString does (ECMAScript
// Number::toString): the shortest round-trip digits, plain decimal while the decimal exponent n satisfies
// -6 < n <= 21, otherwise exponent form with an explicit sign and no zero padding ("1e-7", "1.5e+21").
// -0 prints as "0".
func formatNumber(x float64) string {
	if x == 0 {
		return "0"
	}
	if x < 0 {
		return "-" + formatNumber(-x)
	}
	mantissa, exp, _ := strings.Cut(strconv.FormatFloat(x, 'e', -1, 64), "e")
	digits := strings.Replace(mantissa, ".", "", 1)
	e, _ := strconv.Atoi(exp)
	k, n := len(digits), e+1
	switch {
	case k <= n && n <= 21:
		return digits + strings.Repeat("0", n-k)
	case 0 < n && n <= 21:
		return digits[:n] + "." + digits[n:]
	case -6 < n && n <= 0:
		return "0." + strings.Repeat("0", -n) + digits
	}
	suffix := "e" + strconv.Itoa(e)
	if e >= 0 {
		suffix = "e+" + strconv.Itoa(e)
	}
	if k == 1 {
		return digits + suffix
	}
	return digits[:1] + "." + digits[1:] + suffix
}
