use ezlang::{parser, types::TypeChecker};

#[test]
fn fixed_array_length_matches_slots() {
    let input = r#"let fixed_arr: Str[10] = ["ok",,,,,,,,,];"#;
    let (_, stmts) = parser::parse(input).expect("parse failed");
    let mut checker = TypeChecker::new();
    checker.check_stmts(&stmts).expect("type check failed");
}

#[test]
fn fixed_array_length_mismatch_is_rejected() {
    let input = r#"let fixed_arr: Str[10] = ["ok"];"#;
    let (_, stmts) = parser::parse(input).expect("parse failed");
    let mut checker = TypeChecker::new();
    let err = checker.check_stmts(&stmts).expect_err("expected length mismatch");
    assert!(err.contains("Array length mismatch"));
}

#[test]
fn fn_literal_matches_annotated_fn_type() {
    let input = r#"let fn_ref: (a: I32, b: Str) => I32 = (a, b) => a;"#;
    let (_, stmts) = parser::parse(input).expect("parse failed");
    let mut checker = TypeChecker::new();
    checker.check_stmts(&stmts).expect("type check failed");
}

#[test]
fn fn_literal_param_count_mismatch_is_rejected() {
    let input = r#"let fn_ref: (a: I32, b: Str) => I32 = (a) => a;"#;
    let (_, stmts) = parser::parse(input).expect("parse failed");
    let mut checker = TypeChecker::new();
    let err = checker.check_stmts(&stmts).expect_err("expected param count mismatch");
    assert!(err.contains("Function parameter count mismatch"));
}
