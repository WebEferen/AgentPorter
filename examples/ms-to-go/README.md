# ms

Convert durations to milliseconds and back. A Go port of the JavaScript package
[ms](https://github.com/vercel/ms) 2.1.3.

```sh
go get github.com/agentporter-examples/ms
```

```go
import "github.com/agentporter-examples/ms"

ms.Parse("2 days")  // 172800000, true
ms.Parse("1d")      // 86400000, true
ms.Parse("2.5 hrs") // 9000000, true
ms.Parse("1y")      // 31557600000, true
ms.Parse("-3 days") // -259200000, true
ms.Parse("100")     // 100, true
ms.Parse("nope")    // 0, false

ms.Format(60000)      // "1m", nil
ms.Format(-3 * 60000) // "-3m", nil

ms.FormatLong(60000)     // "1 minute", nil
ms.FormatLong(2 * 60000) // "2 minutes", nil
```

`Format` and `FormatLong` return an `*InvalidValueError` for NaN and the infinities.

## Differences from the JavaScript package

- `ms(val, options)` is split into `Parse` (strings), `Format` and `FormatLong` (numbers, with
  `FormatLong` in place of `{ long: true }`). Values the JavaScript function rejects at run time
  (`null`, booleans, arrays, objects) cannot be passed at all.
- `Parse("")` returns `0, false` like any other string that is not a duration. The JavaScript
  package throws for the empty string.

Parity with the original is tracked in [`.porter/`](.porter).

## License

MIT, see [LICENSE](LICENSE).
