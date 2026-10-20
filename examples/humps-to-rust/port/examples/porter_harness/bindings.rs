// One entry per source call id in .porter/fixtures. Bindings translate calling conventions only:
// a string argument goes to the `&str` function, anything else to the `*_value` function.

use crate::{Binding, Failure, Input, ToContract};
use serde_json::Value;

pub fn bindings() -> Vec<(&'static str, Binding)> {
    vec![
        ("humps.main:camelize", |i: &Input| {
            convert(i, humps::camelize, humps::camelize_value)
        }),
        ("humps.main:pascalize", |i: &Input| {
            convert(i, humps::pascalize, humps::pascalize_value)
        }),
        ("humps.main:kebabize", |i: &Input| {
            convert(i, humps::kebabize, humps::kebabize_value)
        }),
        ("humps.main:decamelize", |i: &Input| {
            convert(i, humps::decamelize, humps::decamelize_value)
        }),
        ("humps.main:depascalize", |i: &Input| {
            convert(i, humps::depascalize, humps::depascalize_value)
        }),
        ("humps.main:dekebabize", |i: &Input| {
            convert(i, humps::dekebabize, humps::dekebabize_value)
        }),
        ("humps.main:is_camelcase", |i: &Input| {
            check(i, humps::is_camelcase, humps::is_camelcase_value)
        }),
        ("humps.main:is_pascalcase", |i: &Input| {
            check(i, humps::is_pascalcase, humps::is_pascalcase_value)
        }),
        ("humps.main:is_kebabcase", |i: &Input| {
            check(i, humps::is_kebabcase, humps::is_kebabcase_value)
        }),
        ("humps.main:is_snakecase", |i: &Input| {
            check(i, humps::is_snakecase, humps::is_snakecase_value)
        }),
    ]
}

fn convert(
    input: &Input,
    on_str: fn(&str) -> String,
    on_value: fn(&Value) -> Value,
) -> Result<Value, Failure> {
    let arg = input.arg(0)?;
    Ok(match arg.as_str() {
        Some(s) => on_str(s).to_contract(),
        None => encode(on_value(&decode(arg))),
    })
}

fn check(
    input: &Input,
    on_str: fn(&str) -> bool,
    on_value: fn(&Value) -> bool,
) -> Result<Value, Failure> {
    let arg = input.arg(0)?;
    Ok(match arg.as_str() {
        Some(s) => on_str(s).to_contract(),
        None => on_value(&decode(arg)).to_contract(),
    })
}

/// A top-level `$int` or `-0` `$float` tag is a JSON number the oracle could not write plainly.
fn decode(arg: &Value) -> Value {
    if let Some(s) = crate::tag(arg, "$int") {
        if let Ok(n) = s.parse::<i64>() {
            return n.into();
        }
        if let Ok(n) = s.parse::<u64>() {
            return n.into();
        }
    }
    if crate::tag(arg, "$float") == Some("-0") {
        return (-0.0f64).into();
    }
    arg.clone()
}

/// Integers go through the harness's integer serializer, which tags values beyond 2^53.
fn encode(v: Value) -> Value {
    match &v {
        Value::Number(n) if n.is_i64() => n.as_i64().to_contract(),
        Value::Number(n) if n.is_u64() => n.as_u64().to_contract(),
        _ => v,
    }
}
