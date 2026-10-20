<?php
// AgentPorter oracle driver for PHP sources, see knowledge/oracles/CONTRACT.md.
// PHP 8.1+, no dependencies beyond the source package's own autoloader:
//   php oracle.php --workspace .porter --unit <unit> [--bootstrap vendor/autoload.php]
declare(strict_types=1);

const DRIVER = 'agentporter/knowledge/oracles/php/oracle.php';
const SAFE_INT = 9007199254740992;
const MAX_DEPTH = 64;
const MAX_ITEMS = 10000;
const JSON_FLAGS = JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION
    | JSON_INVALID_UTF8_SUBSTITUTE | JSON_THROW_ON_ERROR;

final class OracleError extends Exception {}

// Extends Error so `catch (Exception $e)` in the code under test does not swallow it.
final class CaseTimeout extends Error {}

function short_name(object|string $v): string
{
    $name = is_object($v) ? get_class($v) : $v;
    $pos = strrpos($name, '\\');
    return $pos === false ? $name : substr($name, $pos + 1);
}

function tag(string $k, mixed $v): array
{
    return [$k => $v];
}

function canonical(mixed $v): string
{
    if (is_array($v) && !array_is_list($v)) {
        ksort($v, SORT_STRING);
        $parts = [];
        foreach ($v as $k => $x) {
            $parts[] = json_encode((string)$k, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . ':' . canonical($x);
        }
        return '{' . implode(',', $parts) . '}';
    }
    if (is_array($v)) {
        return '[' . implode(',', array_map('canonical', $v)) . ']';
    }
    return json_encode($v, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION | JSON_INVALID_UTF8_SUBSTITUTE);
}

function serialize_value(mixed $v, int $depth = 0): mixed
{
    if ($depth > MAX_DEPTH) {
        return ['$type' => get_debug_type($v), 'truncated' => true];
    }
    $d = $depth + 1;
    if ($v === null || is_bool($v)) {
        return $v;
    }
    if (is_int($v)) {
        return ($v > SAFE_INT || $v < -SAFE_INT) ? tag('$int', (string)$v) : $v;
    }
    if (is_float($v)) {
        if (is_nan($v)) return tag('$float', 'nan');
        if (is_infinite($v)) return tag('$float', $v > 0 ? 'inf' : '-inf');
        if ($v == 0.0 && fdiv(1.0, $v) < 0) return tag('$float', '-0');
        return $v;
    }
    if (is_string($v)) {
        return preg_match('//u', $v) === 1 ? $v : tag('$bytes', base64_encode($v));
    }
    if (is_array($v)) {
        if (array_is_list($v)) {
            return array_map(fn($x) => serialize_value($x, $d), $v);
        }
        $stringKeys = true;
        foreach ($v as $k => $_) {
            if (!is_string($k)) { $stringKeys = false; break; }
        }
        if ($stringKeys) {
            $out = [];
            foreach ($v as $k => $x) $out[$k] = serialize_value($x, $d);
            return $out;
        }
        $entries = [];
        foreach ($v as $k => $x) $entries[] = [serialize_value($k, $d), serialize_value($x, $d)];
        return tag('$map', $entries);
    }
    if ($v instanceof UnitEnum) {
        return tag('$enum', short_name($v) . '.' . $v->name);
    }
    if ($v instanceof DateTimeInterface) {
        return tag('$datetime', $v->format('u') === '000000' ? $v->format('Y-m-d\TH:i:sP') : $v->format('Y-m-d\TH:i:s.uP'));
    }
    if ($v instanceof Closure) {
        return ['$type' => 'function'];
    }
    if ($v instanceof Throwable) {
        return ['$type' => short_name($v), 'message' => $v->getMessage()];
    }
    if ($v instanceof Traversable) {
        $out = [];
        foreach ($v as $x) {
            if (count($out) >= MAX_ITEMS) { $out[] = tag('$truncated', MAX_ITEMS); break; }
            $out[] = serialize_value($x, $d);
        }
        return $out;
    }
    if (is_object($v)) {
        $fields = get_object_vars($v);
        ksort($fields, SORT_STRING);
        $out = ['$type' => short_name($v)];
        foreach ($fields as $k => $x) $out[$k] = serialize_value($x, $d);
        return $out;
    }
    return ['$type' => get_debug_type($v)];
}

function decode(mixed $v): mixed
{
    if (is_array($v)) {
        return array_map('decode', $v);
    }
    if (!$v instanceof stdClass) {
        return $v;
    }
    $a = (array)$v;
    if (count($a) === 1) {
        $tagName = array_key_first($a);
        $raw = $a[$tagName];
        switch ($tagName) {
            case '$float':
                return ['nan' => NAN, 'inf' => INF, '-inf' => -INF, '-0' => -0.0][$raw];
            case '$int':
                $n = filter_var($raw, FILTER_VALIDATE_INT);
                return $n === false ? $raw : $n;
            case '$bytes':
                return base64_decode($raw, true);
            case '$decimal':
                return $raw;
            case '$datetime':
                return new DateTimeImmutable($raw);
            case '$set':
                return array_map('decode', $raw);
            case '$map':
                $out = [];
                foreach ($raw as [$k, $x]) {
                    $key = decode($k);
                    if (!is_int($key) && !is_string($key)) {
                        throw new OracleError('$map key ' . json_encode($k) . ' cannot be a PHP array key');
                    }
                    $out[$key] = decode($x);
                }
                return $out;
            case '$undefined':
                return null;
        }
    }
    return array_map('decode', $a);
}

function type_exists(string $name): bool
{
    return class_exists($name) || interface_exists($name) || enum_exists($name);
}

function invoke(string $call, array $input): mixed
{
    $sep = strrpos($call, ':');
    if ($sep === false) {
        throw new OracleError("call '$call' is not <module>:<qualified name>");
    }
    $module = ltrim(substr($call, 0, $sep), '\\');
    $parts = explode('.', substr($call, $sep + 1));
    $args = decode($input['args'] ?? []);
    $kwargs = decode($input['kwargs'] ?? []);
    $hasCall = array_key_exists('args', $input) || array_key_exists('kwargs', $input) || array_key_exists('init', $input);

    if ($module !== '' && type_exists($module)) {
        $class = $module;
        $rest = $parts;
    } else {
        $first = ($module === '' ? '' : $module . '\\') . $parts[0];
        if (count($parts) === 1 && function_exists($first)) {
            return $first(...$args, ...$kwargs);
        }
        if (count($parts) === 1 && class_exists($first)) {
            return new $first(...$args, ...$kwargs);
        }
        if (count($parts) === 1 && defined($first)) {
            return constant($first);
        }
        if (!type_exists($first)) {
            throw new OracleError("cannot resolve $call: no function, class or constant $first");
        }
        $class = $first;
        $rest = array_slice($parts, 1);
    }
    if (count($rest) !== 1) {
        throw new OracleError("cannot resolve $call: expected <Class>.<member>");
    }
    $member = $rest[0];
    if (!$hasCall) {
        if (defined("$class::$member")) {
            return constant("$class::$member");
        }
        if (property_exists($class, $member) && (new ReflectionProperty($class, $member))->isStatic()) {
            return $class::$$member;
        }
        throw new OracleError("cannot resolve $call: no constant or static property $member");
    }
    if (!method_exists($class, $member)) {
        throw new OracleError("cannot resolve $call: no method $member");
    }
    $method = new ReflectionMethod($class, $member);
    if (!$method->isPublic()) {
        throw new OracleError("cannot resolve $call: $member is not public");
    }
    if (array_key_exists('init', $input)) {
        $init = $input['init'];
        $object = new $class(...decode($init['args'] ?? []), ...decode($init['kwargs'] ?? []));
        return $object->$member(...$args, ...$kwargs);
    }
    if (!$method->isStatic()) {
        throw new OracleError("$call is an instance method: give input.init");
    }
    return $class::$member(...$args, ...$kwargs);
}

function to_array(mixed $v): mixed
{
    if ($v instanceof stdClass) {
        $out = [];
        foreach ((array)$v as $k => $x) $out[$k] = $x;
        return $out;
    }
    return $v;
}

function record_case(stdClass $case, float $timeout, bool $alarm): array
{
    $input = to_array($case->input ?? new stdClass());
    if (isset($input['init'])) {
        $input['init'] = to_array($input['init']);
    }
    $started = hrtime(true);
    try {
        if ($alarm) pcntl_alarm(max(1, (int)ceil($timeout)));
        try {
            $value = invoke($case->call, $input);
        } finally {
            if ($alarm) pcntl_alarm(0);
        }
        $ms = (hrtime(true) - $started) / 1e6;
        return [['kind' => 'value', 'value' => serialize_value($value)], $ms];
    } catch (CaseTimeout) {
        return [['kind' => 'error', 'category' => 'timeout', 'message' => "timed out after {$timeout}s"], $timeout * 1000];
    } catch (OracleError $e) {
        throw new OracleError("case {$case->case}: " . $e->getMessage());
    } catch (Throwable $e) {
        $ms = (hrtime(true) - $started) / 1e6;
        // PHP appends the caller location to TypeError messages; the caller is this driver, not the source.
        $message = preg_replace('/, called in ' . preg_quote(__FILE__, '/') . ' on line \\d+/', '', $e->getMessage());
        $out = ['kind' => 'error', 'category' => short_name($e), 'message' => $message];
        if (isset($case->messagePattern)) {
            $out['messagePattern'] = $case->messagePattern;
        }
        return [$out, $ms];
    }
}

function write_json(string $path, mixed $data): void
{
    if (!is_dir(dirname($path))) {
        mkdir(dirname($path), 0777, true);
    }
    file_put_contents("$path.tmp", json_encode($data, JSON_FLAGS) . "\n");
    rename("$path.tmp", $path);
}

function read_json(string $path): mixed
{
    $text = @file_get_contents($path);
    if ($text === false) {
        throw new OracleError("cannot read $path");
    }
    return json_decode($text, false, 512, JSON_THROW_ON_ERROR);
}

function package_version(?string $name): ?string
{
    if (!class_exists(\Composer\InstalledVersions::class)) {
        return null;
    }
    try {
        $root = \Composer\InstalledVersions::getRootPackage();
        if ($name === null || $root['name'] === $name) {
            return $root['pretty_version'] ?? null;
        }
        return \Composer\InstalledVersions::getPrettyVersion($name);
    } catch (Throwable) {
        return null;
    }
}

function main(array $argv): int
{
    $opts = ['workspace' => '.porter', 'unit' => [], 'package-version' => null, 'commit' => null, 'timeout' => 10.0, 'bootstrap' => null];
    for ($i = 1; $i < count($argv); $i++) {
        $flag = ltrim($argv[$i], '-');
        if (!array_key_exists($flag, $opts) || !isset($argv[$i + 1])) {
            fwrite(STDERR, "oracle: unknown or incomplete argument {$argv[$i]}\n");
            return 2;
        }
        $value = $argv[++$i];
        if ($flag === 'unit') $opts['unit'][] = $value;
        elseif ($flag === 'timeout') $opts['timeout'] = (float)$value;
        else $opts[$flag] = $value;
    }
    ini_set('display_errors', 'stderr');
    try {
        $ws = rtrim($opts['workspace'], '/');
        $config = read_json("$ws/config.json");
        $src = $config->source ?? new stdClass();
        $base = $src->path ?? null;
        if ($base !== null && !empty($src->subpath)) {
            $base .= '/' . $src->subpath;
        }
        $bootstrap = $opts['bootstrap'] ?? ($base !== null ? "$base/vendor/autoload.php" : null);
        if ($bootstrap === null || !is_file($bootstrap)) {
            throw new OracleError('no autoloader at ' . ($bootstrap ?? '<unset>') . '; run composer install in the source or pass --bootstrap');
        }
        require_once $bootstrap;

        $alarm = function_exists('pcntl_async_signals');
        if ($alarm) {
            pcntl_async_signals(true);
            pcntl_signal(SIGALRM, function () { throw new CaseTimeout(); });
        } else {
            fwrite(STDERR, "oracle: pcntl is not loaded, per-case timeouts are disabled\n");
        }

        $expandedDir = "$ws/oracle/expanded";
        $units = $opts['unit'];
        if (!$units) {
            foreach (glob("$expandedDir/*.json") ?: [] as $f) $units[] = basename($f, '.json');
            sort($units);
        }
        if (!$units) {
            throw new OracleError("no expanded cases in $expandedDir; run porter.py fixtures expand");
        }
        $composer = $base !== null && is_file("$base/composer.json") ? read_json("$base/composer.json") : new stdClass();
        $name = $src->package->name ?? $composer->name ?? null;
        $version = $opts['package-version'] ?? ($src->package->version ?? null) ?? package_version($name) ?? $composer->version ?? 'unknown';
        foreach ($units as $unit) {
            $spec = read_json("$expandedDir/$unit.json");
            if (($spec->kind ?? null) === 'cli') {
                throw new OracleError("unit $unit is a CLI unit; record it with porter.py cli record");
            }
            $cases = [];
            $timings = new stdClass();
            $errors = 0;
            foreach ($spec->cases as $case) {
                [$expect, $ms] = record_case($case, $opts['timeout'], $alarm);
                $out = clone $case;
                unset($out->messagePattern);
                $out->expect = $expect;
                $cases[] = $out;
                $timings->{$case->case} = round($ms, 4);
                if ($expect['kind'] === 'error') $errors++;
            }
            write_json("$ws/fixtures/$unit/oracle.json", [
                'schema' => 1,
                'unit' => $unit,
                'oracle' => [
                    'language' => 'php',
                    'package' => $name ?? $unit,
                    'version' => $version,
                    'commit' => $opts['commit'] ?? ($src->commit ?? null),
                    'runtime' => 'php ' . PHP_VERSION,
                    'driver' => DRIVER,
                    'recordedAt' => gmdate('Y-m-d\TH:i:s\Z'),
                ],
                'cases' => $cases,
            ]);
            write_json("$ws/oracle/timings/$unit.json", ['unit' => $unit, 'cases' => $timings]);
            echo "$unit: recorded " . count($cases) . " cases ($errors errors) -> fixtures/$unit/oracle.json\n";
        }
    } catch (OracleError | JsonException $e) {
        fwrite(STDERR, 'oracle: ' . $e->getMessage() . "\n");
        return 2;
    }
    return 0;
}

exit(main($argv));
