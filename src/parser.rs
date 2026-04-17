use nom::{
    IResult,
    branch::alt,
    bytes::complete::{tag, take_while1, take_while},
    character::complete::{char, digit1, space0, multispace0},
    combinator::{map, opt, recognize},
    multi::many0,
    sequence::{delimited, preceded, tuple},
};
use crate::ast::*;

pub fn parse(input: &str) -> IResult<&str, Vec<Stmt>> {
    many0(preceded(multispace0, parse_stmt))(input)
}

fn parse_stmt(input: &str) -> IResult<&str, Stmt> {
    alt((
        parse_let_stmt,
        parse_static_stmt,
        parse_expr_stmt,
        // add more
    ))(input)
}

fn parse_let_stmt(input: &str) -> IResult<&str, Stmt> {
    let (input, _) = tag("let")(input)?;
    let (input, _) = space0(input)?;
    let (input, name) = parse_ident(input)?;
    let (input, _) = space0(input)?;
    let (input, ty) = opt(preceded(char(':'), preceded(space0, parse_type)))(input)?;
    let (input, _) = space0(input)?;
    let (input, _) = char('=')(input)?;
    let (input, _) = space0(input)?;
    let (input, expr) = parse_expr(input)?;
    let (input, _) = char(';')(input)?;
    Ok((input, Stmt::Let(false, name, ty, expr)))
}

fn parse_ident(input: &str) -> IResult<&str, String> {
    map(
        recognize(tuple((
            take_while1(|c: char| c.is_alphabetic() || c == '_'),
            take_while(|c: char| c.is_alphanumeric() || c == '_'),
        ))),
        |s: &str| s.to_string(),
    )(input)
}

fn parse_type(input: &str) -> IResult<&str, Type> {
    alt((
        map(tag("I32"), |_| Type::I32),
        map(tag("Str"), |_| Type::Str),
        // add more
    ))(input)
}

fn parse_expr(input: &str) -> IResult<&str, Expr> {
    parse_binary_op(input)
}

fn parse_binary_op(input: &str) -> IResult<&str, Expr> {
    let (input, left) = parse_primary(input)?;
    let (input, ops) = many0(tuple((parse_binop, parse_primary)))(input)?;
    if ops.is_empty() {
        Ok((input, left))
    } else {
        // Simple left-assoc, no precedence
        let mut expr = left;
        for (op, right) in ops {
            expr = Expr::BinaryOp(Box::new(expr), op, Box::new(right));
        }
        Ok((input, expr))
    }
}

fn parse_primary(input: &str) -> IResult<&str, Expr> {
    alt((
        parse_literal,
        parse_ident_expr,
        delimited(char('('), parse_expr, char(')')),
    ))(input)
}

fn parse_binop(input: &str) -> IResult<&str, BinOp> {
    alt((
        map(tag("+"), |_| BinOp::Add),
        map(tag("-"), |_| BinOp::Sub),
        map(tag("*"), |_| BinOp::Mul),
        map(tag("/"), |_| BinOp::Div),
        map(tag("=="), |_| BinOp::Eq),
    ))(input)
}

fn parse_literal(input: &str) -> IResult<&str, Expr> {
    alt((
        map(digit1, |s: &str| Expr::Literal(Literal::Int(s.parse().unwrap()))),
        // add more
    ))(input)
}

fn parse_ident_expr(input: &str) -> IResult<&str, Expr> {
    map(parse_ident, Expr::Ident)(input)
}

fn parse_expr_stmt(input: &str) -> IResult<&str, Stmt> {
    let (input, expr) = parse_expr(input)?;
    let (input, _) = char(';')(input)?;
    Ok((input, Stmt::Expr(expr)))
}

fn parse_static_stmt(input: &str) -> IResult<&str, Stmt> {
    let (input, _) = tag("static")(input)?;
    let (input, _) = space0(input)?;
    let (input, name) = parse_ident(input)?;
    let (input, _) = space0(input)?;
    let (input, _) = char(':')(input)?;
    let (input, _) = space0(input)?;
    let (input, ty) = parse_type(input)?;
    let (input, _) = space0(input)?;
    let (input, _) = char('=')(input)?;
    let (input, _) = space0(input)?;
    let (input, expr) = parse_expr(input)?;
    let (input, _) = char(';')(input)?;
    Ok((input, Stmt::Static(name, ty, expr)))
}