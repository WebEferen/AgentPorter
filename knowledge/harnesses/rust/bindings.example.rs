// Copy to examples/porter_harness/bindings.rs. One entry per source call id in .porter/fixtures; nothing else.
// Bindings translate calling conventions only: never convert or patch a return value.

use crate::{undefined, Binding, Failure, Input, ToContract};
use serde_json::Value;

pub fn bindings() -> Vec<(&'static str, Binding)> {
    vec![
        ("ms:default", ms_default as Binding),
        ("slugify.slugify:slugify", slugify as Binding),
        ("pkg.mod:Counter.inc", counter_inc as Binding),
        ("slugify.slugify:DEFAULT_SEPARATOR", default_separator as Binding),
    ]
}

// `?` turns the port's error into a Failure whose category is the error type's name.
fn ms_default(input: &Input) -> Result<Value, Failure> {
    Ok(match mylib::parse(input.str(0)?)? {
        Some(n) => n.to_contract(),
        None => undefined(), // the JavaScript source returned undefined
    })
}

// Keyword arguments become an options struct.
fn slugify(input: &Input) -> Result<Value, Failure> {
    let mut opts = mylib::Options::default();
    if let Some(sep) = input.kw("separator").and_then(Value::as_str) {
        opts.separator = sep.to_string();
    }
    Ok(mylib::slugify(input.str(0)?, &opts).to_contract())
}

// <Class>.<method>: build the receiver from input.init, then call the method.
fn counter_inc(input: &Input) -> Result<Value, Failure> {
    let init = input.init.as_deref().cloned().unwrap_or_default();
    let mut c = mylib::Counter::new(init.i64(0)?);
    Ok(c.inc(input.i64(0)?).to_contract())
}

// Constant reads (input is {}).
fn default_separator(_: &Input) -> Result<Value, Failure> {
    Ok(mylib::DEFAULT_SEPARATOR.to_contract())
}
