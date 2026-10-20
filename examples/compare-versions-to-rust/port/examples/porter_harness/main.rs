//! AgentPorter parity harness for Rust ports, see knowledge/oracles/CONTRACT.md.
//! Copy to examples/porter_harness/main.rs next to bindings.rs, add serde_json as a dev-dependency, then:
//!   cargo run --example porter_harness -- --workspace .porter --run <run> [--unit <unit>]

mod bindings;

use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::panic::{self, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const DRIVER: &str = "agentporter/knowledge/harnesses/rust";
const SAFE_INT: i128 = 1 << 53;

/// One binding: unpack the case input, call the port, serialize its result with `to_contract()`.
pub type Binding = fn(&Input) -> Result<Value, Failure>;

/// A thrown error. `?` on any `std::error::Error` fills the category with the error's type name.
#[derive(Debug, Clone)]
pub struct Failure {
    pub category: String,
    pub message: String,
}

impl Failure {
    pub fn new(category: impl Into<String>, message: impl Into<String>) -> Self {
        Failure {
            category: category.into(),
            message: message.into(),
        }
    }

    fn binding(message: String) -> Self {
        Failure::new("BindingError", message)
    }
}

impl<E: std::error::Error> From<E> for Failure {
    fn from(e: E) -> Self {
        Failure::new(short_type_name(std::any::type_name::<E>()), e.to_string())
    }
}

fn short_type_name(full: &str) -> String {
    let base = full.split('<').next().unwrap_or(full);
    base.rsplit("::").next().unwrap_or(base).to_string()
}

/// Case input: `{"args": [...], "kwargs": {...}, "init": {...}}`. Accessors decode tagged values.
#[derive(Debug, Clone, Default)]
pub struct Input {
    pub args: Vec<Value>,
    pub kwargs: Map<String, Value>,
    pub init: Option<Box<Input>>,
}

impl Input {
    fn from_json(v: &Value) -> Input {
        Input {
            args: v
                .get("args")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default(),
            kwargs: v
                .get("kwargs")
                .and_then(Value::as_object)
                .cloned()
                .unwrap_or_default(),
            init: v.get("init").map(|i| Box::new(Input::from_json(i))),
        }
    }

    #[allow(clippy::len_without_is_empty)]
    pub fn len(&self) -> usize {
        self.args.len()
    }

    pub fn arg(&self, i: usize) -> Result<&Value, Failure> {
        self.args.get(i).ok_or_else(|| {
            Failure::binding(format!("argument {i} missing (have {})", self.args.len()))
        })
    }

    pub fn kw(&self, name: &str) -> Option<&Value> {
        self.kwargs.get(name)
    }

    pub fn str(&self, i: usize) -> Result<&str, Failure> {
        self.arg(i)?
            .as_str()
            .ok_or_else(|| Failure::binding(format!("argument {i}: want string")))
    }

    pub fn bool(&self, i: usize) -> Result<bool, Failure> {
        self.arg(i)?
            .as_bool()
            .ok_or_else(|| Failure::binding(format!("argument {i}: want bool")))
    }

    pub fn i64(&self, i: usize) -> Result<i64, Failure> {
        let v = self.arg(i)?;
        if let Some(n) = v.as_i64() {
            return Ok(n);
        }
        tag(v, "$int")
            .and_then(|s| s.parse().ok())
            .ok_or_else(|| Failure::binding(format!("argument {i}: want integer")))
    }

    pub fn f64(&self, i: usize) -> Result<f64, Failure> {
        let v = self.arg(i)?;
        if let Some(n) = v.as_f64() {
            return Ok(n);
        }
        match tag(v, "$float") {
            Some("nan") => Ok(f64::NAN),
            Some("inf") => Ok(f64::INFINITY),
            Some("-inf") => Ok(f64::NEG_INFINITY),
            Some("-0") => Ok(-0.0),
            _ => Err(Failure::binding(format!("argument {i}: want number"))),
        }
    }

    pub fn bytes(&self, i: usize) -> Result<Vec<u8>, Failure> {
        let v = self.arg(i)?;
        if let Some(s) = tag(v, "$bytes") {
            return base64_decode(s)
                .ok_or_else(|| Failure::binding(format!("argument {i}: bad base64")));
        }
        v.as_str()
            .map(|s| s.as_bytes().to_vec())
            .ok_or_else(|| Failure::binding(format!("argument {i}: want $bytes")))
    }

    pub fn strs(&self, i: usize) -> Result<Vec<String>, Failure> {
        let items = self
            .arg(i)?
            .as_array()
            .ok_or_else(|| Failure::binding(format!("argument {i}: want array")))?;
        items
            .iter()
            .map(|x| {
                x.as_str()
                    .map(str::to_string)
                    .ok_or_else(|| Failure::binding(format!("argument {i}: want strings")))
            })
            .collect()
    }
}

fn tag<'a>(v: &'a Value, name: &str) -> Option<&'a str> {
    let o = v.as_object()?;
    if o.len() != 1 {
        return None;
    }
    o.get(name)?.as_str()
}

/// Contract serialization (tagged values for what JSON cannot carry).
pub trait ToContract {
    fn to_contract(&self) -> Value;
}

/// `{"$undefined": true}`, for a source that returned JavaScript undefined.
pub fn undefined() -> Value {
    json!({"$undefined": true})
}

/// `{"$bytes": "<base64>"}`. `Vec<u8>` serializes as an array of numbers, so call this for byte strings.
pub fn bytes(b: &[u8]) -> Value {
    json!({"$bytes": base64_encode(b)})
}

/// `{"$type": name, field: value, ...}` for a struct with public fields.
pub fn object<const N: usize>(name: &str, fields: [(&str, Value); N]) -> Value {
    let mut m = Map::new();
    m.insert("$type".into(), Value::String(name.into()));
    for (k, v) in fields {
        m.insert(k.into(), v);
    }
    Value::Object(m)
}

/// `{"$enum": "Type.MEMBER"}`.
pub fn enum_member(type_name: &str, member: &str) -> Value {
    json!({"$enum": format!("{type_name}.{member}")})
}

/// `{"$datetime": "<ISO 8601>"}`.
pub fn datetime(iso: &str) -> Value {
    json!({"$datetime": iso})
}

fn canonical(v: &Value) -> String {
    serde_json::to_string(v).unwrap_or_default()
}

fn float(f: f64) -> Value {
    if f.is_nan() {
        json!({"$float": "nan"})
    } else if f.is_infinite() {
        json!({"$float": if f > 0.0 { "inf" } else { "-inf" }})
    } else if f == 0.0 && f.is_sign_negative() {
        json!({"$float": "-0"})
    } else {
        serde_json::Number::from_f64(f)
            .map(Value::Number)
            .unwrap_or(Value::Null)
    }
}

fn int(n: i128) -> Value {
    if (-SAFE_INT..=SAFE_INT).contains(&n) {
        Value::from(n as i64)
    } else {
        json!({"$int": n.to_string()})
    }
}

macro_rules! int_contract {
    ($($t:ty),*) => {$(
        impl ToContract for $t {
            fn to_contract(&self) -> Value { int(*self as i128) }
        }
    )*};
}
int_contract!(i8, i16, i32, i64, i128, isize, u8, u16, u32, u64, usize);

impl ToContract for u128 {
    fn to_contract(&self) -> Value {
        if *self <= SAFE_INT as u128 {
            Value::from(*self as u64)
        } else {
            json!({"$int": self.to_string()})
        }
    }
}

impl ToContract for f64 {
    fn to_contract(&self) -> Value {
        float(*self)
    }
}

impl ToContract for f32 {
    fn to_contract(&self) -> Value {
        // Shortest f32 text, so 0.1f32 becomes 0.1 rather than 0.10000000149011612.
        float(self.to_string().parse().unwrap_or(f64::NAN))
    }
}

impl ToContract for bool {
    fn to_contract(&self) -> Value {
        Value::Bool(*self)
    }
}

impl ToContract for char {
    fn to_contract(&self) -> Value {
        Value::String(self.to_string())
    }
}

impl ToContract for str {
    fn to_contract(&self) -> Value {
        Value::String(self.to_string())
    }
}

impl ToContract for String {
    fn to_contract(&self) -> Value {
        Value::String(self.clone())
    }
}

impl ToContract for () {
    fn to_contract(&self) -> Value {
        Value::Null
    }
}

impl ToContract for Value {
    fn to_contract(&self) -> Value {
        self.clone()
    }
}

impl<T: ToContract + ?Sized> ToContract for &T {
    fn to_contract(&self) -> Value {
        (**self).to_contract()
    }
}

impl<T: ToContract + ?Sized> ToContract for Box<T> {
    fn to_contract(&self) -> Value {
        (**self).to_contract()
    }
}

impl<T: ToContract> ToContract for Option<T> {
    fn to_contract(&self) -> Value {
        self.as_ref().map_or(Value::Null, ToContract::to_contract)
    }
}

impl<T: ToContract> ToContract for [T] {
    fn to_contract(&self) -> Value {
        Value::Array(self.iter().map(ToContract::to_contract).collect())
    }
}

impl<T: ToContract, const N: usize> ToContract for [T; N] {
    fn to_contract(&self) -> Value {
        self.as_slice().to_contract()
    }
}

impl<T: ToContract> ToContract for Vec<T> {
    fn to_contract(&self) -> Value {
        self.as_slice().to_contract()
    }
}

fn set<'a, T: ToContract + 'a>(items: impl Iterator<Item = &'a T>) -> Value {
    let mut out: Vec<Value> = items.map(ToContract::to_contract).collect();
    out.sort_by_key(canonical);
    json!({"$set": out})
}

impl<T: ToContract, S> ToContract for HashSet<T, S> {
    fn to_contract(&self) -> Value {
        set(self.iter())
    }
}

impl<T: ToContract> ToContract for BTreeSet<T> {
    fn to_contract(&self) -> Value {
        set(self.iter())
    }
}

fn map<'a, K: ToContract + 'a, V: ToContract + 'a>(
    entries: impl Iterator<Item = (&'a K, &'a V)>,
) -> Value {
    let pairs: Vec<(Value, Value)> = entries
        .map(|(k, v)| (k.to_contract(), v.to_contract()))
        .collect();
    if pairs.iter().all(|(k, _)| k.is_string()) {
        let mut m = Map::new();
        for (k, v) in pairs {
            if let Value::String(k) = k {
                m.insert(k, v);
            }
        }
        return Value::Object(m);
    }
    let mut entries: Vec<Value> = pairs.into_iter().map(|(k, v)| json!([k, v])).collect();
    entries.sort_by_key(|e| canonical(&e[0]));
    json!({"$map": entries})
}

impl<K: ToContract, V: ToContract, S> ToContract for HashMap<K, V, S> {
    fn to_contract(&self) -> Value {
        map(self.iter())
    }
}

impl<K: ToContract, V: ToContract> ToContract for BTreeMap<K, V> {
    fn to_contract(&self) -> Value {
        map(self.iter())
    }
}

macro_rules! tuple_contract {
    ($($name:ident),+) => {
        impl<$($name: ToContract),+> ToContract for ($($name,)+) {
            #[allow(non_snake_case)]
            fn to_contract(&self) -> Value {
                let ($($name,)+) = self;
                Value::Array(vec![$($name.to_contract()),+])
            }
        }
    };
}
tuple_contract!(A);
tuple_contract!(A, B);
tuple_contract!(A, B, C);
tuple_contract!(A, B, C, D);

const B64: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

fn base64_encode(data: &[u8]) -> String {
    let mut out = String::with_capacity(data.len().div_ceil(3) * 4);
    for chunk in data.chunks(3) {
        let n = (chunk[0] as u32) << 16
            | (*chunk.get(1).unwrap_or(&0) as u32) << 8
            | *chunk.get(2).unwrap_or(&0) as u32;
        for k in 0..4 {
            if k <= chunk.len() {
                out.push(B64[(n >> (18 - 6 * k) & 63) as usize] as char);
            } else {
                out.push('=');
            }
        }
    }
    out
}

fn base64_decode(s: &str) -> Option<Vec<u8>> {
    let mut out = Vec::new();
    let (mut buf, mut bits) = (0u32, 0);
    for c in s.bytes().filter(|&c| c != b'=') {
        buf = buf << 6 | B64.iter().position(|&b| b == c)? as u32;
        bits += 6;
        if bits >= 8 {
            bits -= 8;
            out.push((buf >> bits) as u8);
        }
    }
    Some(out)
}

fn outcome(binding: Binding, input: Input, timeout: Duration) -> Value {
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        let result = panic::catch_unwind(AssertUnwindSafe(|| binding(&input)));
        let _ = tx.send(result);
    });
    match rx.recv_timeout(timeout) {
        Ok(Ok(Ok(value))) => json!({"kind": "value", "value": value}),
        Ok(Ok(Err(f))) => json!({"kind": "error", "category": f.category, "message": f.message}),
        Ok(Err(payload)) => {
            let message = payload
                .downcast_ref::<&str>()
                .map(|s| s.to_string())
                .or_else(|| payload.downcast_ref::<String>().cloned())
                .unwrap_or_else(|| "panic".into());
            json!({"kind": "error", "category": "panic", "message": message})
        }
        Err(_) => {
            json!({"kind": "error", "category": "timeout", "message": format!("timed out after {}s", timeout.as_secs_f64())})
        }
    }
}

fn utc_now(compact: bool) -> String {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let (days, rem) = (secs.div_euclid(86400), secs.rem_euclid(86400));
    let z = days + 719468;
    let era = z.div_euclid(146097);
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + if month <= 2 { 1 } else { 0 };
    let (h, m, s) = (rem / 3600, rem % 3600 / 60, rem % 60);
    if compact {
        format!("{year:04}{month:02}{day:02}T{h:02}{m:02}{s:02}Z")
    } else {
        format!("{year:04}-{month:02}-{day:02}T{h:02}:{m:02}:{s:02}Z")
    }
}

fn fail(msg: String) -> ! {
    eprintln!("harness: {msg}");
    std::process::exit(2);
}

fn read_json(path: &Path) -> Value {
    let text =
        std::fs::read_to_string(path).unwrap_or_else(|e| fail(format!("{}: {e}", path.display())));
    serde_json::from_str(&text).unwrap_or_else(|e| fail(format!("{}: {e}", path.display())))
}

fn write_json(path: &Path, v: &Value) {
    let dir = path.parent().unwrap_or(Path::new("."));
    std::fs::create_dir_all(dir).unwrap_or_else(|e| fail(format!("{}: {e}", dir.display())));
    let tmp = path.with_extension("json.tmp");
    let text = serde_json::to_string_pretty(v).unwrap_or_else(|e| fail(e.to_string())) + "\n";
    std::fs::write(&tmp, text).unwrap_or_else(|e| fail(format!("{}: {e}", tmp.display())));
    std::fs::rename(&tmp, path).unwrap_or_else(|e| fail(format!("{}: {e}", path.display())));
}

fn main() {
    let mut workspace = PathBuf::from(".porter");
    let mut run = utc_now(true);
    let mut units: Vec<String> = Vec::new();
    let mut timeout = 10.0f64;
    let mut argv = std::env::args().skip(1);
    while let Some(a) = argv.next() {
        let mut value = || {
            argv.next()
                .unwrap_or_else(|| fail(format!("{a} needs a value")))
        };
        match a.as_str() {
            "--workspace" => workspace = PathBuf::from(value()),
            "--run" => run = value(),
            "--unit" => units.push(value()),
            "--timeout" => {
                timeout = value()
                    .parse()
                    .unwrap_or_else(|_| fail("--timeout needs seconds".into()))
            }
            _ => fail(format!("unknown argument {a}")),
        }
    }
    // Panics in bindings become outcomes; the default hook would only add noise on stderr.
    panic::set_hook(Box::new(|_| {}));
    let table: HashMap<&str, Binding> = bindings::bindings().into_iter().collect();
    let fixtures = workspace.join("fixtures");
    if units.is_empty() {
        let entries = std::fs::read_dir(&fixtures)
            .unwrap_or_else(|e| fail(format!("no fixtures under {}: {e}", fixtures.display())));
        units = entries
            .flatten()
            .filter(|e| e.path().is_dir())
            .map(|e| e.file_name().to_string_lossy().into_owned())
            .collect();
        units.sort();
    }
    if units.is_empty() {
        fail(format!("no fixtures under {}", fixtures.display()));
    }
    let mut missing = 0;
    for unit in &units {
        let dir = fixtures.join(unit);
        let mut files: Vec<PathBuf> = std::fs::read_dir(&dir)
            .unwrap_or_else(|_| fail(format!("no fixtures for unit {unit}")))
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.extension().is_some_and(|x| x == "json"))
            .collect();
        files.sort();
        let started_at = utc_now(false);
        let mut results = Vec::new();
        let mut errors = 0;
        for f in &files {
            let fixture = read_json(f);
            for c in fixture["cases"].as_array().cloned().unwrap_or_default() {
                if c["expect"]["kind"] == "cli" {
                    continue;
                }
                let call = c["call"].as_str().unwrap_or_default();
                let started = Instant::now();
                let actual = match table.get(call) {
                    Some(binding) => outcome(
                        *binding,
                        Input::from_json(&c["input"]),
                        Duration::from_secs_f64(timeout),
                    ),
                    None => {
                        missing += 1;
                        json!({"kind": "error", "category": "MissingBinding", "message": format!("no binding for {call}")})
                    }
                };
                if actual["kind"] == "error" {
                    errors += 1;
                }
                let ms = started.elapsed().as_secs_f64() * 1000.0;
                results.push(json!({"case": c["case"], "actual": actual, "durationMs": (ms * 10000.0).round() / 10000.0}));
            }
        }
        let count = results.len();
        let out = json!({
            "schema": 1,
            "unit": unit,
            "runner": {"language": "rust", "driver": DRIVER},
            "startedAt": started_at,
            "results": results,
        });
        write_json(
            &workspace
                .join("runs")
                .join(&run)
                .join(format!("{unit}.json")),
            &out,
        );
        println!("{unit}: ran {count} cases ({errors} errors) -> runs/{run}/{unit}.json");
    }
    if missing > 0 {
        eprintln!("harness: {missing} case(s) have no binding (recorded as MissingBinding)");
    }
}
