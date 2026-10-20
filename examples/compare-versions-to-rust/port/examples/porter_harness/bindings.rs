// One entry per source call id in .porter/fixtures; nothing else.
// Bindings translate calling conventions only: never convert or patch a return value.

use crate::Binding;
use serde_json::Value;

pub fn bindings() -> Vec<(&'static str, Binding)> {
    vec![
        ("compare-versions:compareVersions", |input| {
            let ordering = compare_versions_port::compare_versions(input.str(0)?, input.str(1)?)?;
            Ok(Value::from(ordering as i32))
        }),
        ("compare-versions:compare", |input| {
            Ok(Value::Bool(compare_versions_port::compare(
                input.str(0)?,
                input.str(1)?,
                input.str(2)?,
            )?))
        }),
        ("compare-versions:satisfies", |input| {
            Ok(Value::Bool(compare_versions_port::satisfies(
                input.str(0)?,
                input.str(1)?,
            )?))
        }),
        ("compare-versions:validate", |input| {
            Ok(Value::Bool(compare_versions_port::validate(input.str(0)?)))
        }),
        ("compare-versions:validateStrict", |input| {
            Ok(Value::Bool(compare_versions_port::validate_strict(
                input.str(0)?,
            )))
        }),
    ]
}
