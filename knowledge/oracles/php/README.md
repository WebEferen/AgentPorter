# PHP oracle driver

`oracle.php` records what the pinned PHP source does. It reads `.porter/oracle/expanded/<unit>.json`, loads
the source through its Composer autoloader, calls each case, and writes `.porter/fixtures/<unit>/oracle.json`
plus `.porter/oracle/timings/<unit>.json` as [CONTRACT.md](../CONTRACT.md) describes. PHP 8.1 or newer, no
dependencies.

`porter` below is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py`.

## Run it

Run `composer install` in the source checkout first. Then:

```sh
porter fixtures expand
php ${CLAUDE_PLUGIN_ROOT}/knowledge/oracles/php/oracle.php --workspace .porter \
    [--unit <unit>]... [--bootstrap <autoload.php>] [--package-version <v>] [--commit <sha>] [--timeout <seconds>]
porter fixtures validate
```

The default bootstrap is `vendor/autoload.php` under `config.source.path` (joined with
`config.source.subpath`). Use `--bootstrap` for anything else. Package name and version come from
`config.source.package`, then Composer's installed metadata, then the source's `composer.json`.

Exit codes: 0 when fixtures were written (thrown exceptions are outcomes), 2 when the driver cannot run: no
autoloader, a call that does not resolve, a CLI unit.

## How calls resolve

Call ids use the namespaced name. In JSON the backslash is escaped: `"App\\Text:slugify"`.

| Call | Input | What runs |
| --- | --- | --- |
| `App\Text:slugify` | `args`, `kwargs` | static method |
| `App\Text:SEP`, `App\Text:calls` | `{}` | class constant, public static property |
| `App\Color:Green` | `{}` | enum case |
| `App:slugify` | `args`, `kwargs` | namespaced function |
| `App:VERSION` | `{}` | namespaced constant |
| `App:Counter` | `args`, `kwargs` | `new App\Counter(...)` |
| `App:Counter.inc`, `App\Counter:inc` | `init`, `args`, `kwargs` | `(new App\Counter(...init))->inc(...)` |
| `:strlen` | `args` | global function (empty module means the global namespace) |

`kwargs` become PHP 8 named arguments after the positional ones.

Tagged inputs are decoded before the call: `$float`, `$int` (an `int`, or a numeric string beyond
`PHP_INT_MAX`), `$bytes` (a binary string), `$decimal` (a string), `$datetime` (`DateTimeImmutable`), `$set` (a
list), `$map` (an array; keys must be ints or strings) and `$undefined` (`null`). JSON objects become
associative arrays.

## Serialization

| PHP | JSON |
| --- | --- |
| list array | array |
| array with only string keys | object |
| any other array | `{"$map": [[k, v], ...]}` in insertion order |
| empty array | `[]` |
| string that is not valid UTF-8 | `{"$bytes": "<base64>"}` |
| `int` beyond 2^53 | `{"$int": "..."}` |
| `float` | keeps its fraction (`1.0` stays `1.0`) |
| `NAN`, `INF`, `-INF`, `-0.0` | `{"$float": ...}` |
| enum case (pure or backed) | `{"$enum": "Type.Case"}` |
| `DateTimeInterface` | `{"$datetime": "Y-m-d\TH:i:sP"}`, with microseconds when they are not zero |
| `Closure` | `{"$type": "function"}` |
| `Traversable`, generator | array of values (keys dropped), capped at 10000 |
| `Throwable` value | `{"$type": "Name", "message"}` |
| other objects | `{"$type": "Name", ...}` with public properties, sorted |

## Errors and timeouts

The category is the short class name (`InvalidArgumentException`, `TypeError`, `ValueError`,
`DivisionByZeroError`, `ArgumentCountError`). PHP appends ", called in <file> on line N" to argument
`TypeError` messages; the driver strips that suffix when the file is the driver itself, so messages do not
depend on where the plugin is installed.

Timeouts need the `pcntl` extension (`php -m | grep pcntl`). The official Docker images leave it out; add it
with `docker-php-ext-install pcntl`. With `pcntl` each case gets `--timeout` seconds (default 10, rounded up
to whole seconds) and an overrun becomes category `timeout`. Without it the driver warns once on stderr and a
case that never returns blocks the run.

Warnings and notices go to stderr. They are not outcomes.

## Limitations

- PHP turns numeric string keys into integers, so `["10" => x]` serializes as `$map`, and an empty array
  cannot be told apart from an empty object.
- By-reference parameters and resources are not supported.
- A `catch (\Throwable)` in the source also catches the driver's timeout.
