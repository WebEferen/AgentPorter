package main

// Copy to bindings.go. One entry per source call id in .porter/fixtures; nothing else.
// Bindings translate calling conventions only: never convert or patch a return value.

import (
	"io"

	ms "example.com/goms"
)

var bindings = map[string]Call{
	// Positional arguments: Input accessors decode tagged values ($float, $int, $bytes, $datetime).
	"ms:default": func(in Input) (any, error) {
		n, ok := ms.Parse(in.Str(0))
		if !ok {
			return Undefined, nil // the JavaScript source returned undefined
		}
		return n, nil
	},

	// Keyword arguments become an options struct.
	"slugify.slugify:slugify": func(in Input) (any, error) {
		opts := ms.Options{Separator: "-"}
		if in.Has("separator") {
			opts.Separator = in.Kw("separator").(string)
		}
		return ms.Slugify(in.Str(0), opts), nil
	},

	// Several return values become an array, the way the source returned a tuple.
	"pkg.mod:split_pair": func(in Input) (any, error) {
		a, b := ms.SplitPair(in.Str(0))
		return []any{a, b}, nil
	},

	// <Class>.<method>: build the receiver from in.Init, then call the method.
	"pkg.mod:Counter.inc": func(in Input) (any, error) {
		c := ms.NewCounter(in.Init.Int(0))
		return c.Inc(in.Int(0)), nil
	},

	// Constant reads (input is {}).
	"slugify.slugify:DEFAULT_SEPARATOR": func(in Input) (any, error) { return ms.DefaultSeparator, nil },
}

func init() {
	// Name sentinel errors so their category is stable: the default is the error's type name.
	Sentinels[io.ErrUnexpectedEOF] = "ErrUnexpectedEOF"
}
