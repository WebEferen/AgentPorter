package main

// One entry per source call id in .porter/fixtures; nothing else.
// Bindings translate calling conventions only: never convert or patch a return value.

import (
	ms "github.com/agentporter-examples/ms"
)

var bindings = map[string]Call{
	// ms(val, options): a string goes to Parse (options ignored, as in the source), a number to Format, or to
	// FormatLong when options.long is true.
	"ms:default": func(in Input) (any, error) {
		if s, ok := in.Arg(0).(string); ok {
			n, ok := ms.Parse(s)
			if !ok {
				return Undefined, nil // the JavaScript source returned undefined
			}
			return n, nil
		}
		v := in.Float(0)
		if longOption(in) {
			return ms.FormatLong(v)
		}
		return ms.Format(v)
	},
}

// longOption reads the options argument as a Go caller would express it: absent, null (or undefined) or an
// object whose "long" is true, false, null or absent.
func longOption(in Input) bool {
	if in.Len() < 2 || absent(in.Arg(1)) {
		return false
	}
	opts, ok := in.Arg(1).(map[string]any)
	if !ok {
		// DIVERGENCE(typed-input): non-object options only exist through JavaScript truthiness.
		argFail("argument 1: want an options object or null, got %T", in.Arg(1))
	}
	if absent(opts["long"]) {
		return false
	}
	if long, ok := opts["long"].(bool); ok {
		return long
	}
	// DIVERGENCE(typed-input): a non-boolean options.long only exists through JavaScript truthiness.
	argFail("argument 1: want options.long to be a boolean or null, got %T", opts["long"])
	return false
}

// absent reports JSON null or the fixture marker for JavaScript undefined.
func absent(v any) bool {
	if v == nil {
		return true
	}
	m, ok := v.(map[string]any)
	return ok && len(m) == 1 && m["$undefined"] == true
}
