# ms: JavaScript to Go

[ms](https://github.com/vercel/ms) converts durations such as `"2 days"` to milliseconds and back. This
is version 2.1.3 ported to Go.

- [original/](original/): `index.js`, `tests.js`, readme and license of ms 2.1.3 (commit `1c6264b`).
- [port/](port/): the module `github.com/agentporter-examples/ms`, its tests, the parity harness in
  `cmd/porter-harness` and the `.porter/` workspace.

## Original and port

```js
const ms = require("ms");

ms("2 days");              // 172800000
ms("nope");                // undefined
ms(60000);                 // "1m"
ms(60000, { long: true }); // "1 minute"
```

```go
import "github.com/agentporter-examples/ms"

ms.Parse("2 days")   // 172800000, true
ms.Parse("nope")     // 0, false
ms.Format(60000)     // "1m", nil
ms.FormatLong(60000) // "1 minute", nil
```

The one overloaded `ms(value, options)` became three typed functions.

## Result

DIVERGENT. Of 1490 recorded cases, 1458 match exactly, 8 match through the error map (JavaScript `Error`
to Go `*InvalidValueError`, same message) and 24 differ on purpose. None fail. 44 of the 49 upstream tests
are ported and pass; the other 5 test the inputs below. Full report: [port/PARITY.md](port/PARITY.md).

- `typed-input` (22 cases): `undefined`, `null`, booleans, arrays and objects can't be passed to the typed
  Go functions, so the JavaScript errors for them have no Go counterpart.
- `empty-string` (2 cases): `Parse("")` returns `0, false` like any other string that isn't a duration.
  JavaScript throws.

## How it was made

One unattended session (see [how the examples were made](../README.md#how-they-were-made)): $18.48,
98 turns, 65 minutes. Pre-approved answers:

```text
- deps gate: approve the proposed decisions when every MAP and SHIM candidate is registry-verified. Prefer the Go
  standard library.
- strategy gate: approve the proposed units, order and budgets as written.
- Anything about the package: the Go module path is github.com/agentporter-examples/ms, Go 1.22 or newer, a
  library with an idiomatic Go API. The fixtures keep the JavaScript call ids; the bindings translate.
```

Both divergences were planned in the strategy and accepted with the strategy answer.

## Check it

```sh
cd port
go test ./...
go run ./cmd/porter-harness --workspace .porter --run local
python3 ../../../scripts/porter.py parity collect --run local --dry-run
```

## License

MIT, from ms (Vercel). `original/` and `port/` both keep the notice.
