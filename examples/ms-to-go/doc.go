// Package ms converts between human-readable durations and milliseconds.
//
// It is a Go port of the JavaScript package ms 2.1.3 (https://github.com/vercel/ms). Parse reads strings
// such as "2 days", "1.5h" or "-100" and returns milliseconds; Format and FormatLong turn milliseconds back
// into "2d" or "2 days". Durations are float64 milliseconds, the same IEEE-754 doubles the JavaScript
// package uses, so fractional and very large values behave as they do there.
//
// All functions are pure and safe for concurrent use.
package ms
