package main

// Dispatch for github.com/kballard/go-shellquote at 95032a82bc518f77982ea72343cc1ade730072f0.

import (
	shellquote "github.com/kballard/go-shellquote"
)

func init() {
	Sentinels[shellquote.UnterminatedSingleQuoteError] = "UnterminatedSingleQuoteError"
	Sentinels[shellquote.UnterminatedDoubleQuoteError] = "UnterminatedDoubleQuoteError"
	Sentinels[shellquote.UnterminatedEscapeError] = "UnterminatedEscapeError"
}

var dispatch = map[string]Call{
	// Join is variadic: input.args are the arguments, one string each.
	"github.com/kballard/go-shellquote:Join": func(in Input) (any, error) {
		args := make([]string, in.Len())
		for i := range args {
			args[i] = in.Str(i)
		}
		return shellquote.Join(args...), nil
	},
	// Split returns (words, err). On error the words parsed so far come back too; main.go keeps them
	// as expect.value on the error outcome.
	"github.com/kballard/go-shellquote:Split": func(in Input) (any, error) {
		if in.Len() != 1 {
			argFail("Split takes exactly one string argument, got %d", in.Len())
		}
		return shellquote.Split(in.Str(0))
	},
}
