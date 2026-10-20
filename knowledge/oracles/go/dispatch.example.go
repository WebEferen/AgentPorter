package main

// Copy to dispatch.go and list every call id used by .porter/oracle/cases/*.json.
// Each entry converts the case input to the Go signature and returns what the source returns.
// Return the source's error unchanged: the driver records its type name (or a Sentinels name) as the category.

import (
	upstream "example.com/upstream"
)

func init() {
	// Sentinels[upstream.ErrInvalid] = "ErrInvalid"
}

var dispatch = map[string]Call{
	"example.com/upstream:Parse": func(in Input) (any, error) {
		return upstream.Parse(in.Str(0))
	},
	"example.com/upstream:Format": func(in Input) (any, error) {
		return upstream.Format(in.Float(0), in.Has("long") && in.Kw("long") == true), nil
	},
	"example.com/upstream:Split": func(in Input) (any, error) {
		head, tail := upstream.Split(in.Str(0))
		return []any{head, tail}, nil
	},
}
