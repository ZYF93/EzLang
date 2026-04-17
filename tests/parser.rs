use ezlang::parser;
use ezlang::ast::{Stmt, Expr, Literal, Type, BinOp, UnOp};

#[test]
fn parse_let_statement() {
    let input = "let x: I32 = 42;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Let(false, "x".to_string(), Some(Type::I32), Expr::Literal(Literal::Int(42))));
}

#[test]
fn parse_add_expression_statement() {
    let input = "x + 2;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Expr(Expr::BinaryOp(
        Box::new(Expr::Ident("x".to_string())),
        BinOp::Add,
        Box::new(Expr::Literal(Literal::Int(2)))
    )));
}

#[test]
fn parse_logical_and_or_expression() {
    let input = "true && false || true;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Expr(Expr::BinaryOp(
        Box::new(Expr::BinaryOp(
            Box::new(Expr::Literal(Literal::Bool(true))),
            BinOp::And,
            Box::new(Expr::Literal(Literal::Bool(false))),
        )),
        BinOp::Or,
        Box::new(Expr::Literal(Literal::Bool(true))),
    )));
}

#[test]
fn parse_mod_expression_statement() {
    let input = "x % 2;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Expr(Expr::BinaryOp(
        Box::new(Expr::Ident("x".to_string())),
        BinOp::Mod,
        Box::new(Expr::Literal(Literal::Int(2)))
    )));
}

#[test]
fn parse_static_statement() {
    let input = "static z: I32 = 5;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Static("z".to_string(), Type::I32, Expr::Literal(Literal::Int(5))));
}

#[test]
fn parse_string_literal() {
    let input = "\"hello\";";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Expr(Expr::Literal(Literal::Str("hello".to_string()))));
}

#[test]
fn parse_bool_literal() {
    let input = "true; false;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 2);
    assert_eq!(stmts[0], Stmt::Expr(Expr::Literal(Literal::Bool(true))));
    assert_eq!(stmts[1], Stmt::Expr(Expr::Literal(Literal::Bool(false))));
}

#[test]
fn parse_comments() {
    let input = "// line comment\nlet x = 1; /* block comment */ x + 2;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 2);
    assert_eq!(stmts[0], Stmt::Let(false, "x".to_string(), None, Expr::Literal(Literal::Int(1))));
    assert_eq!(stmts[1], Stmt::Expr(Expr::BinaryOp(
        Box::new(Expr::Ident("x".to_string())),
        BinOp::Add,
        Box::new(Expr::Literal(Literal::Int(2)))
    )));
}

#[test]
fn parse_const_statement() {
    let input = "const y: I32 = 10;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Let(true, "y".to_string(), Some(Type::I32), Expr::Literal(Literal::Int(10))));
}

#[test]
fn parse_unary_and_precedence() {
    let input = "-1; 1 + 2 * 3; (1 + 2) * 3;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 3);
    assert_eq!(stmts[0], Stmt::Expr(Expr::UnaryOp(UnOp::Neg, Box::new(Expr::Literal(Literal::Int(1))))));
    assert_eq!(stmts[1], Stmt::Expr(Expr::BinaryOp(
        Box::new(Expr::Literal(Literal::Int(1))),
        BinOp::Add,
        Box::new(Expr::BinaryOp(
            Box::new(Expr::Literal(Literal::Int(2))),
            BinOp::Mul,
            Box::new(Expr::Literal(Literal::Int(3))),
        )),
    )));
    assert_eq!(stmts[2], Stmt::Expr(Expr::BinaryOp(
        Box::new(Expr::BinaryOp(
            Box::new(Expr::Literal(Literal::Int(1))),
            BinOp::Add,
            Box::new(Expr::Literal(Literal::Int(2))),
        )),
        BinOp::Mul,
        Box::new(Expr::Literal(Literal::Int(3))),
    )));
}

#[test]
fn parse_ternary_expression() {
    let input = "true ? 1 : 0;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Expr(Expr::If(
        Box::new(Expr::Literal(Literal::Bool(true))),
        Box::new(Expr::Literal(Literal::Int(1))),
        Box::new(Expr::Literal(Literal::Int(0))),
    )));
}

#[test]
fn parse_block_expression() {
    let input = "{ let x = 1; x + 2; };";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Expr(Expr::Block(vec![
        Stmt::Let(false, "x".to_string(), None, Expr::Literal(Literal::Int(1))),
        Stmt::Expr(Expr::BinaryOp(
            Box::new(Expr::Ident("x".to_string())),
            BinOp::Add,
            Box::new(Expr::Literal(Literal::Int(2))),
        )),
    ])));
}

#[test]
fn parse_match_expression() {
    let input = "match { x == 1 ? 42, true ? 0, };";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Expr(Expr::Match(vec![
        (
            Expr::BinaryOp(
                Box::new(Expr::Ident("x".to_string())),
                BinOp::Eq,
                Box::new(Expr::Literal(Literal::Int(1))),
            ),
            Expr::Literal(Literal::Int(42)),
        ),
        (
            Expr::Literal(Literal::Bool(true)),
            Expr::Literal(Literal::Int(0)),
        ),
    ])));
}

#[test]
fn parse_float_literal() {
    let input = "3.14;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Expr(Expr::Literal(Literal::Float(3.14))));
}

#[test]
fn parse_infinite_loop_statement() {
    let input = "loop { let x = 1; break; continue; };";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(
        stmts[0],
        Stmt::Loop(
            ezlang::ast::LoopKind::Infinite,
            vec![
                Stmt::Let(false, "x".to_string(), None, Expr::Literal(Literal::Int(1))),
                Stmt::Break,
                Stmt::Continue,
            ],
        )
    );
}

#[test]
fn parse_range_loop_statement() {
    let input = "loop i in 0...10 { i; };";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(
        stmts[0],
        Stmt::Loop(
            ezlang::ast::LoopKind::Range(
                Expr::Literal(Literal::Int(0)),
                Expr::Literal(Literal::Int(10)),
            ),
            vec![Stmt::Expr(Expr::Ident("i".to_string()))],
        )
    );
}

#[test]
fn parse_iter_loop_statement() {
    let input = "loop item in list { item; };";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(
        stmts[0],
        Stmt::Loop(
            ezlang::ast::LoopKind::Iter(Expr::Ident("list".to_string())),
            vec![Stmt::Expr(Expr::Ident("item".to_string()))],
        )
    );
}

#[test]
fn parse_all_builtin_types_in_annotations() {
    let input = r#"
        let a: I8 = 1;
        let b: I64 = 2;
        let c: U8 = 3;
        let d: U32 = 4;
        let e: U64 = 5;
        let f: F32 = 6.5;
        let g: F64 = 7.25;
        let h: Bool = true;
        let i: Void = true;
        let j: Blob = 9;
    "#;
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 10);
    assert_eq!(stmts[0], Stmt::Let(false, "a".to_string(), Some(Type::I8), Expr::Literal(Literal::Int(1))));
    assert_eq!(stmts[1], Stmt::Let(false, "b".to_string(), Some(Type::I64), Expr::Literal(Literal::Int(2))));
    assert_eq!(stmts[2], Stmt::Let(false, "c".to_string(), Some(Type::U8), Expr::Literal(Literal::Int(3))));
    assert_eq!(stmts[3], Stmt::Let(false, "d".to_string(), Some(Type::U32), Expr::Literal(Literal::Int(4))));
    assert_eq!(stmts[4], Stmt::Let(false, "e".to_string(), Some(Type::U64), Expr::Literal(Literal::Int(5))));
    assert_eq!(stmts[5], Stmt::Let(false, "f".to_string(), Some(Type::F32), Expr::Literal(Literal::Float(6.5))));
    assert_eq!(stmts[6], Stmt::Let(false, "g".to_string(), Some(Type::F64), Expr::Literal(Literal::Float(7.25))));
    assert_eq!(stmts[7], Stmt::Let(false, "h".to_string(), Some(Type::Bool), Expr::Literal(Literal::Bool(true))));
    assert_eq!(stmts[8], Stmt::Let(false, "i".to_string(), Some(Type::Void), Expr::Literal(Literal::Bool(true))));
    assert_eq!(stmts[9], Stmt::Let(false, "j".to_string(), Some(Type::Blob), Expr::Literal(Literal::Int(9))));
}

#[test]
fn parse_accepts_trailing_whitespace() {
    let input = "let x: I32 = 1;\n   \n";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(stmts[0], Stmt::Let(false, "x".to_string(), Some(Type::I32), Expr::Literal(Literal::Int(1))));
}

#[test]
fn parse_array_types_in_annotations() {
    let input = r#"
        let dyn_arr: I32[] = [1];
        let fixed_arr: Str[10] = ["ok"];
    "#;
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 2);
    assert_eq!(
        stmts[0],
        Stmt::Let(
            false,
            "dyn_arr".to_string(),
            Some(Type::Array(Box::new(Type::I32), None)),
            Expr::Array(vec![Some(Expr::Literal(Literal::Int(1)))]),
        )
    );
    assert_eq!(
        stmts[1],
        Stmt::Let(
            false,
            "fixed_arr".to_string(),
            Some(Type::Array(Box::new(Type::Str), Some(10))),
            Expr::Array(vec![Some(Expr::Literal(Literal::Str("ok".to_string())))]),
        )
    );
}

#[test]
fn parse_array_literal_with_elisions() {
    let input = r#"let fixed_arr: Str[10] = ["ok",,,,,,,,,];"#;
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(
        stmts[0],
        Stmt::Let(
            false,
            "fixed_arr".to_string(),
            Some(Type::Array(Box::new(Type::Str), Some(10))),
            Expr::Array(vec![
                Some(Expr::Literal(Literal::Str("ok".to_string()))),
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ]),
        )
    );
}

#[test]
fn parse_optional_type_annotation() {
    let input = "let maybe_name: Str? = \"ok\";";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(
        stmts[0],
        Stmt::Let(
            false,
            "maybe_name".to_string(),
            Some(Type::Optional(Box::new(Type::Str))),
            Expr::Literal(Literal::Str("ok".to_string())),
        )
    );
}

#[test]
fn parse_union_type_annotation() {
    let input = "let value: I32 | Str = 1;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(
        stmts[0],
        Stmt::Let(
            false,
            "value".to_string(),
            Some(Type::Union(vec![Type::I32, Type::Str])),
            Expr::Literal(Literal::Int(1)),
        )
    );
}

#[test]
fn parse_union_with_optional_and_array_type_annotation() {
    let input = "let data: I32[]? | Str = [1];";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(
        stmts[0],
        Stmt::Let(
            false,
            "data".to_string(),
            Some(Type::Union(vec![
                Type::Optional(Box::new(Type::Array(Box::new(Type::I32), None))),
                Type::Str,
            ])),
            Expr::Array(vec![Some(Expr::Literal(Literal::Int(1)))]),
        )
    );
}

#[test]
fn parse_function_type_annotation() {
    let input = "let fn_ref: (a: I32, b: Str) => I32 = (a, b) => a;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(
        stmts[0],
        Stmt::Let(
            false,
            "fn_ref".to_string(),
            Some(Type::Fn(
                vec![
                    ezlang::ast::Param { name: "a".to_string(), ty: Type::I32 },
                    ezlang::ast::Param { name: "b".to_string(), ty: Type::Str },
                ],
                Box::new(Type::I32),
            )),
            Expr::FnDef(
                vec![
                    ezlang::ast::Param { name: "a".to_string(), ty: Type::Void },
                    ezlang::ast::Param { name: "b".to_string(), ty: Type::Void },
                ],
                Box::new(Expr::Ident("a".to_string())),
            ),
        )
    );
}

#[test]
fn parse_function_type_in_union_annotation() {
    let input = "let f: (x: I32) => I32 | Str = 1;";
    let (_, stmts) = parser::parse(input).expect("parse failed");
    assert_eq!(stmts.len(), 1);
    assert_eq!(
        stmts[0],
        Stmt::Let(
            false,
            "f".to_string(),
            Some(Type::Union(vec![
                Type::Fn(
                    vec![ezlang::ast::Param { name: "x".to_string(), ty: Type::I32 }],
                    Box::new(Type::I32),
                ),
                Type::Str,
            ])),
            Expr::Literal(Literal::Int(1)),
        )
    );
}
