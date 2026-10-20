//! The pyhumps 3.8.0 test suite: one test per pytest function, iterating its parametrize table.
//! `tests/test_separate_words.py` tests a private helper and lives in `src/lib.rs`.

use serde_json::{json, Value};

/// [ref: tests/test_camelize.py::test_camelize]
#[test]
fn camelize_test_camelize() {
    let rows = [
        ("fallback_url", "fallbackUrl"),
        ("scrubber_media_url", "scrubberMediaUrl"),
        ("dash_url", "dashUrl"),
        ("_fallback_url", "_fallbackUrl"),
        ("__scrubber_media___url_", "__scrubberMediaUrl_"),
        ("_url__", "_url__"),
        ("API", "API"),
        ("_API_", "_API_"),
        ("__API__", "__API__"),
        ("APIResponse", "APIResponse"),
        ("_APIResponse_", "_APIResponse_"),
        ("__APIResponse__", "__APIResponse__"),
        ("whatever_10", "whatever10"),
        ("test-1-2-3-4-5-6", "test123456"),
        ("test_n_test", "testNTest"),
        ("field_value_2_type", "fieldValue2Type"),
        ("", ""),
    ];
    for (input, expected) in rows {
        assert_eq!(humps::camelize(input), expected, "camelize({input:?})");
    }
    assert_eq!(humps::camelize_value(&Value::Null), json!(""));
}

/// [ref: tests/test_camelize.py::test_camelize_dict_list]
#[test]
fn camelize_test_camelize_dict_list() {
    let actual = humps::camelize_value(&json!({
        "videos": [{
            "fallback_url": "https://media.io/video",
            "scrubber_media_url": "https://media.io/video",
            "dash_url": "https://media.io/video",
        }],
        "images": [{
            "fallback_url": "https://media.io/image",
            "scrubber_media_url": "https://media.io/image",
            "url": "https://media.io/image",
        }],
        "other": [
            {
                "_fallback_url": "https://media.io/image",
                "__scrubber_media___url_": "https://media.io/image",
                "_url__": "https://media.io/image",
            },
            {
                "API": "test_upper",
                "_API_": "test_upper",
                "__API__": "test_upper",
                "APIResponse": "test_acronym",
                "_APIResponse_": "test_acronym",
                "__APIResponse__": "test_acronym",
            },
        ],
    }));
    let expected = json!({
        "videos": [{
            "fallbackUrl": "https://media.io/video",
            "scrubberMediaUrl": "https://media.io/video",
            "dashUrl": "https://media.io/video",
        }],
        "images": [{
            "fallbackUrl": "https://media.io/image",
            "scrubberMediaUrl": "https://media.io/image",
            "url": "https://media.io/image",
        }],
        "other": [
            {
                "_fallbackUrl": "https://media.io/image",
                "__scrubberMediaUrl_": "https://media.io/image",
                "_url__": "https://media.io/image",
            },
            {
                "API": "test_upper",
                "_API_": "test_upper",
                "__API__": "test_upper",
                "APIResponse": "test_acronym",
                "_APIResponse_": "test_acronym",
                "__APIResponse__": "test_acronym",
            },
        ],
    });
    assert_eq!(actual, expected);
}

/// [ref: tests/test_decamelize.py::test_decamelize]
#[test]
fn decamelize_test_decamelize() {
    let rows = [
        ("symbol", "symbol"),
        ("lastPrice", "last_price"),
        ("changePct", "change_pct"),
        ("impliedVolatility", "implied_volatility"),
        ("_symbol", "_symbol"),
        ("changePct_", "change_pct_"),
        ("_lastPrice__", "_last_price__"),
        ("__impliedVolatility_", "__implied_volatility_"),
        ("API", "API"),
        ("_API_", "_API_"),
        ("__API__", "__API__"),
        ("APIResponse", "api_response"),
        ("_APIResponse_", "_api_response_"),
        ("__APIResponse__", "__api_response__"),
        ("_itemID", "_item_id"),
        ("memMB", "mem_mb"),
        ("sizeX", "size_x"),
        ("aB", "a_b"),
        ("testNTest", "test_n_test"),
    ];
    for (input, expected) in rows {
        assert_eq!(humps::decamelize(input), expected, "decamelize({input:?})");
    }
}

/// [ref: tests/test_decamelize.py::test_decamelize_dict_list]
#[test]
fn decamelize_test_decamelize_dict_list() {
    let actual = humps::decamelize_value(&json!([
        {"symbol": "AAL", "lastPrice": 31.78, "changePct": 2.8146, "impliedVolatility": 0.482},
        {"symbol": "LBTYA", "lastPrice": 25.95, "changePct": 2.6503, "impliedVolatility": 0.7287},
        {"_symbol": "LBTYK", "changePct_": 2.5827, "_lastPrice__": 25.42, "__impliedVolatility_": 0.4454},
        {
            "API": "test_upper",
            "_API_": "test_upper",
            "__API__": "test_upper",
            "APIResponse": "test_acronym",
            "_APIResponse_": "test_acronym",
            "__APIResponse__": "test_acronym",
            "ruby_tuesdays": "ruby_tuesdays",
            "_itemID": "_item_id",
        },
    ]));
    let expected = json!([
        {"symbol": "AAL", "last_price": 31.78, "change_pct": 2.8146, "implied_volatility": 0.482},
        {"symbol": "LBTYA", "last_price": 25.95, "change_pct": 2.6503, "implied_volatility": 0.7287},
        {"_symbol": "LBTYK", "change_pct_": 2.5827, "_last_price__": 25.42, "__implied_volatility_": 0.4454},
        {
            "API": "test_upper",
            "_API_": "test_upper",
            "__API__": "test_upper",
            "api_response": "test_acronym",
            "_api_response_": "test_acronym",
            "__api_response__": "test_acronym",
            "ruby_tuesdays": "ruby_tuesdays",
            "_item_id": "_item_id",
        },
    ]);
    assert_eq!(actual, expected);
}

/// [ref: tests/test_dekebabize.py::test_dekebabize]
#[test]
fn dekebabize_test_dekebabize() {
    let rows = [
        ("symbol", "symbol"),
        ("last-price", "last_price"),
        ("Change-Pct", "Change_Pct"),
        ("implied-Volatility", "implied_Volatility"),
        ("_symbol", "_symbol"),
        ("change-pct_", "change_pct_"),
        ("_last-price__", "_last_price__"),
        ("__implied-volatility_", "__implied_volatility_"),
        ("API", "API"),
        ("_API_", "_API_"),
        ("__API__", "__API__"),
        ("API-Response", "API_Response"),
        ("_API-Response_", "_API_Response_"),
        ("__API-Response__", "__API_Response__"),
        ("12345", "12345"),
    ];
    for (input, expected) in rows {
        assert_eq!(humps::dekebabize(input), expected, "dekebabize({input:?})");
    }
}

/// [ref: tests/test_dekebabize.py::test_dekebabize_dict_list]
#[test]
fn dekebabize_test_dekebabize_dict_list() {
    let actual = humps::dekebabize_value(&json!([
        {"symbol": "AAL", "last-price": 31.78, "Change-Pct": 2.8146, "implied-Volatility": 0.482},
        {"symbol": "LBTYA", "last-price": 25.95, "Change-Pct": 2.6503, "implied-Volatility": 0.7287},
        {"_symbol": "LBTYK", "Change-Pct_": 2.5827, "_last-price__": 25.42, "__implied-Volatility_": 0.4454},
        {
            "API": "test_upper",
            "_API_": "test_upper",
            "__API__": "test_upper",
            "API-Response": "test_acronym",
            "_API-Response_": "test_acronym",
            "__API-Response__": "test_acronym",
            "ruby_tuesdays": "ruby_tuesdays",
            "_item-ID": "_item_id",
        },
    ]));
    let expected = json!([
        {"symbol": "AAL", "last_price": 31.78, "Change_Pct": 2.8146, "implied_Volatility": 0.482},
        {"symbol": "LBTYA", "last_price": 25.95, "Change_Pct": 2.6503, "implied_Volatility": 0.7287},
        {"_symbol": "LBTYK", "Change_Pct_": 2.5827, "_last_price__": 25.42, "__implied_Volatility_": 0.4454},
        {
            "API": "test_upper",
            "_API_": "test_upper",
            "__API__": "test_upper",
            "API_Response": "test_acronym",
            "_API_Response_": "test_acronym",
            "__API_Response__": "test_acronym",
            "ruby_tuesdays": "ruby_tuesdays",
            "_item_ID": "_item_id",
        },
    ]);
    assert_eq!(actual, expected);
}

/// [ref: tests/test_humps.py::test_converting_strings]
#[test]
fn humps_test_converting_strings() {
    assert_eq!(humps::camelize("jack_in_the_box"), "jackInTheBox");
    assert_eq!(humps::decamelize("rubyTuesdays"), "ruby_tuesdays");
    assert_eq!(humps::depascalize("UnosPizza"), "unos_pizza");
    assert_eq!(humps::pascalize("red_robin"), "RedRobin");
    assert_eq!(humps::kebabize("white_castle"), "white-castle");
    assert_eq!(humps::dekebabize("taco-bell"), "taco_bell");
}

/// [ref: tests/test_humps.py::test_camelized_acronyms]
#[test]
fn humps_test_camelized_acronyms() {
    let rows = [
        ("PERatio", "pe_ratio"),
        ("HTTPResponse", "http_response"),
        ("_HTTPResponse", "_http_response"),
        ("_HTTPResponse__", "_http_response__"),
        ("BIP73", "BIP73"),
        ("BIP72b", "bip72b"),
        ("memMB", "mem_mb"),
        ("B52Thing", "b52_thing"),
    ];
    for (input, expected) in rows {
        assert_eq!(humps::decamelize(input), expected, "decamelize({input:?})");
    }
}

/// [ref: tests/test_humps.py::test_conditionals]
#[test]
fn humps_test_conditionals() {
    // (input, is_camelcase, is_pascalcase, is_snakecase, is_kebabcase)
    let rows = [
        ("RedRobin", false, true, false, false),
        ("ruby_tuesdays", false, false, true, false),
        ("jackInTheBox", true, false, false, false),
        ("white-castle", false, false, false, true),
        ("API", true, true, true, true),
        ("whatever_10", false, false, true, false),
    ];
    for (input, camel, pascal, snake, kebab) in rows {
        assert_eq!(humps::is_camelcase(input), camel, "is_camelcase({input:?})");
        assert_eq!(
            humps::is_pascalcase(input),
            pascal,
            "is_pascalcase({input:?})"
        );
        assert_eq!(humps::is_snakecase(input), snake, "is_snakecase({input:?})");
        assert_eq!(humps::is_kebabcase(input), kebab, "is_kebabcase({input:?})");
    }
}

/// [ref: tests/test_humps.py::test_numeric]
#[test]
fn humps_test_numeric() {
    assert_eq!(humps::camelize_value(&json!(1234)), json!(1234));
    assert_eq!(humps::decamelize_value(&json!(123)), json!(123));
    assert_eq!(humps::pascalize_value(&json!(123)), json!(123));
    assert_eq!(humps::kebabize_value(&json!(123)), json!(123));
}

/// [ref: tests/test_humps.py::test_upper]
#[test]
fn humps_test_upper() {
    assert_eq!(humps::camelize("API"), "API");
    assert_eq!(humps::decamelize("API"), "API");
    assert_eq!(humps::pascalize("API"), "API");
    assert_eq!(humps::depascalize("API"), "API");
    assert_eq!(humps::kebabize("API"), "API");
    assert_eq!(humps::dekebabize("API"), "API");
}

fn pascalize_input() -> Value {
    json!({
        "videos": [{
            "fallback_url": "https://media.io/video",
            "scrubber_media_url": "https://media.io/video",
            "dash_url": "https://media.io/video",
        }],
        "images": [{
            "fallback_url": "https://media.io/image",
            "scrubber_media_url": "https://media.io/image",
            "url": "https://media.io/image",
        }],
        "other": [
            {
                "_fallback_url": "https://media.io/image",
                "__scrubber_media___url_": "https://media.io/image",
                "_url__": "https://media.io/image",
            },
            {
                "API": "test_upper",
                "_API_": "test_upper",
                "__API__": "test_upper",
                "APIResponse": "test_acronym",
                "_APIResponse_": "test_acronym",
                "__APIResponse__": "test_acronym",
            },
        ],
    })
}

fn pascalize_expected() -> Value {
    json!({
        "Videos": [{
            "FallbackUrl": "https://media.io/video",
            "ScrubberMediaUrl": "https://media.io/video",
            "DashUrl": "https://media.io/video",
        }],
        "Images": [{
            "FallbackUrl": "https://media.io/image",
            "ScrubberMediaUrl": "https://media.io/image",
            "Url": "https://media.io/image",
        }],
        "Other": [
            {
                "_FallbackUrl": "https://media.io/image",
                "__ScrubberMediaUrl_": "https://media.io/image",
                "_Url__": "https://media.io/image",
            },
            {
                "API": "test_upper",
                "_API_": "test_upper",
                "__API__": "test_upper",
                "APIResponse": "test_acronym",
                "_APIResponse_": "test_acronym",
                "__APIResponse__": "test_acronym",
            },
        ],
    })
}

/// [ref: tests/test_humps.py::test_pascalize]
#[test]
fn humps_test_pascalize() {
    assert_eq!(
        humps::pascalize_value(&pascalize_input()),
        pascalize_expected()
    );
}

/// [ref: tests/test_humps.py::test_depascalize]
#[test]
fn humps_test_depascalize() {
    let actual = humps::depascalize_value(&json!([
        {"Symbol": "AAL", "LastPrice": 31.78, "ChangePct": 2.8146, "ImpliedVolatality": 0.482},
        {"Symbol": "LBTYA", "LastPrice": 25.95, "ChangePct": 2.6503, "ImpliedVolatality": 0.7287},
        {"_Symbol": "LBTYK", "ChangePct_": 2.5827, "_LastPrice__": 25.42, "__ImpliedVolatality_": 0.4454},
        {
            "API": "test_upper",
            "_API_": "test_upper",
            "__API__": "test_upper",
            "APIResponse": "test_acronym",
            "_APIResponse_": "test_acronym",
            "__APIResponse__": "test_acronym",
            "ruby_tuesdays": "ruby_tuesdays",
        },
    ]));
    let expected = json!([
        {"symbol": "AAL", "last_price": 31.78, "change_pct": 2.8146, "implied_volatality": 0.482},
        {"symbol": "LBTYA", "last_price": 25.95, "change_pct": 2.6503, "implied_volatality": 0.7287},
        {"_symbol": "LBTYK", "change_pct_": 2.5827, "_last_price__": 25.42, "__implied_volatality_": 0.4454},
        {
            "API": "test_upper",
            "_API_": "test_upper",
            "__API__": "test_upper",
            "api_response": "test_acronym",
            "_api_response_": "test_acronym",
            "__api_response__": "test_acronym",
            "ruby_tuesdays": "ruby_tuesdays",
        },
    ]);
    assert_eq!(actual, expected);
}

/// [ref: tests/test_kebabize.py::test_kebabize]
#[test]
fn kebabize_test_kebabize() {
    let rows = [
        ("fallback_url", "fallback-url"),
        ("scrubber_media_url", "scrubber-media-url"),
        ("dash_url", "dash-url"),
        ("_fallback_url", "_fallback-url"),
        ("__scrubber_media___url_", "__scrubber-media-url_"),
        ("_url__", "_url__"),
        ("API", "API"),
        ("_API_", "_API_"),
        ("__API__", "__API__"),
        ("API_Response", "API-Response"),
        ("_API_Response_", "_API-Response_"),
        ("__API_Response__", "__API-Response__"),
    ];
    for (input, expected) in rows {
        assert_eq!(humps::kebabize(input), expected, "kebabize({input:?})");
    }
}

/// [ref: tests/test_kebabize.py::test_kebabize_dict_list]
#[test]
fn kebabize_test_kebabize_dict_list() {
    let actual = humps::kebabize_value(&json!({
        "videos": [{
            "fallback_url": "https://media.io/video",
            "scrubber_Media_Url": "https://media.io/video",
            "dash_Url": "https://media.io/video",
        }],
        "images": [{
            "fallback_url": "https://media.io/image",
            "scrubber_Media_Url": "https://media.io/image",
            "url": "https://media.io/image",
        }],
        "other": [
            {
                "_fallback_url": "https://media.io/image",
                "__scrubber_Media___Url_": "https://media.io/image",
                "_url__": "https://media.io/image",
            },
            {
                "API": "test_upper",
                "_API_": "test_upper",
                "__API__": "test_upper",
                "APIResponse": "test_acronym",
                "_APIResponse_": "test_acronym",
                "__APIResponse__": "test_acronym",
            },
        ],
    }));
    let expected = json!({
        "videos": [{
            "fallback-url": "https://media.io/video",
            "scrubber-Media-Url": "https://media.io/video",
            "dash-Url": "https://media.io/video",
        }],
        "images": [{
            "fallback-url": "https://media.io/image",
            "scrubber-Media-Url": "https://media.io/image",
            "url": "https://media.io/image",
        }],
        "other": [
            {
                "_fallback-url": "https://media.io/image",
                "__scrubber-Media-Url_": "https://media.io/image",
                "_url__": "https://media.io/image",
            },
            {
                "API": "test_upper",
                "_API_": "test_upper",
                "__API__": "test_upper",
                "api-response": "test_acronym",
                "_api-response_": "test_acronym",
                "__api-response__": "test_acronym",
            },
        ],
    });
    assert_eq!(actual, expected);
}

/// [ref: tests/test_pascalize.py::test_pascalize]
#[test]
fn pascalize_test_pascalize() {
    let rows = [
        ("fallback_url", "FallbackUrl"),
        ("scrubber_media_url", "ScrubberMediaUrl"),
        ("dash_url", "DashUrl"),
        ("_fallback_url", "_FallbackUrl"),
        ("__scrubber_media___url_", "__ScrubberMediaUrl_"),
        ("_url__", "_Url__"),
        ("API", "API"),
        ("_API_", "_API_"),
        ("__API__", "__API__"),
        ("APIResponse", "APIResponse"),
        ("_APIResponse_", "_APIResponse_"),
        ("__APIResponse__", "__APIResponse__"),
        ("", ""),
    ];
    for (input, expected) in rows {
        assert_eq!(humps::pascalize(input), expected, "pascalize({input:?})");
    }
    assert_eq!(humps::pascalize_value(&Value::Null), json!(""));
}

/// [ref: tests/test_pascalize.py::test_pascalize_dict_list]
#[test]
fn pascalize_test_pascalize_dict_list() {
    assert_eq!(
        humps::pascalize_value(&pascalize_input()),
        pascalize_expected()
    );
}
