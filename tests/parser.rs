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
