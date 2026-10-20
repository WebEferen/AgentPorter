module porteroracle

go 1.21

require github.com/kballard/go-shellquote v0.0.0

// upstream/ is `git archive 95032a82bc518f77982ea72343cc1ade730072f0` of the source checkout plus a
// one-line go.mod (the repo predates Go modules, and replace needs a go.mod in the target directory).
replace github.com/kballard/go-shellquote => ./upstream
