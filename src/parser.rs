use nom::{
    IResult,
    branch::alt,
    bytes::complete::{tag, take_until, take_while1, take_while},
    character::complete::{char, digit1, multispace1},
    combinator::{all_consuming, map, opt, recognize, value},
    multi::{many0, separated_list0},
    sequence::{delimited, preceded, tuple},
};
use crate::ast::*;

fn skip_ws(input: &str) -> IResult<&str, ()> {
    value(
        (),
        many0(alt((
            value((), multispace1),
            map(parse_comment, |_| ()),
        )))
    )(input)
}

fn ws<'a, F, O>(inner: F) -> impl FnMut(&'a str) -> IResult<&'a str, O>
where
    F: FnMut(&'a str) -> IResult<&'a str, O>,
{
    preceded(skip_ws, inner)
}

fn parse_comment(input: &str) -> IResult<&str, &str> {
    alt((parse_line_comment, parse_block_comment))(input)
}

fn parse_line_comment(input: &str) -> IResult<&str, &str> {
    preceded(tag("//"), take_while(|c| c != '\n'))(input)
}

fn parse_block_comment(input: &str) -> IResult<&str, &str> {
    delimited(tag("/*"), take_until("*/"), tag("*/"))(input)
}

pub fn parse(input: &str) -> IResult<&str, Vec<Stmt>> {
    all_consuming(many0(ws(parse_stmt)))(input)
}

fn parse_stmt(input: &str) -> IResult<&str, Stmt> {
    alt((
        parse_let_stmt,
        parse_const_stmt,
        parse_static_stmt,
        parse_expr_stmt,
        // add more
    ))(input)
}

fn parse_let_stmt(input: &str) -> IResult<&str, Stmt> {
    let (input, _) = ws(tag("let"))(input)?;
    let (input, name) = ws(parse_ident)(input)?;
    let (input, ty) = opt(preceded(ws(char(':')), ws(parse_type)))(input)?;
    let (input, _) = ws(char('='))(input)?;
    let (input, expr) = parse_expr(input)?;
    let (input, _) = ws(char(';'))(input)?;
    Ok((input, Stmt::Let(false, name, ty, expr)))
}

fn parse_const_stmt(input: &str) -> IResult<&str, Stmt> {
    let (input, _) = ws(tag("const"))(input)?;
    let (input, name) = ws(parse_ident)(input)?;
    let (input, ty) = opt(preceded(ws(char(':')), ws(parse_type)))(input)?;
    let (input, _) = ws(char('='))(input)?;
    let (input, expr) = parse_expr(input)?;
    let (input, _) = ws(char(';'))(input)?;
    Ok((input, Stmt::Let(true, name, ty, expr)))
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
    ws(parse_ternary)(input)
}

fn parse_ternary(input: &str) -> IResult<&str, Expr> {
    let (input, cond) = parse_binary_expr_prec(input, 1)?;
    let (input, opt_parts) = opt(tuple((
        ws(tag("?")),
        parse_expr,
        ws(tag(":")),
        parse_expr,
    )))(input)?;
    if let Some((_, then_expr, _, else_expr)) = opt_parts {
        Ok((input, Expr::If(Box::new(cond), Box::new(then_expr), Box::new(else_expr))))
    } else {
        Ok((input, cond))
    }
}

fn parse_binary_expr_prec(input: &str, min_prec: u8) -> IResult<&str, Expr> {
    let (mut input, mut lhs) = parse_unary(input)?;
    loop {
        let (next_input, op) = match ws(parse_binop)(input) {
            Ok(res) => res,
            Err(_) => break,
        };
        let prec = precedence(&op);
        if prec < min_prec {
            break;
        }
        let (after_rhs, rhs) = parse_binary_expr_prec(next_input, prec + 1)?;
        lhs = Expr::BinaryOp(Box::new(lhs), op, Box::new(rhs));
        input = after_rhs;
    }
    Ok((input, lhs))
}

fn parse_unary(input: &str) -> IResult<&str, Expr> {
    ws(alt((
        map(preceded(tag("-"), parse_unary), |expr| Expr::UnaryOp(UnOp::Neg, Box::new(expr))),
        map(preceded(tag("!"), parse_unary), |expr| Expr::UnaryOp(UnOp::Not, Box::new(expr))),
        parse_primary,
    )))(input)
}

fn precedence(op: &BinOp) -> u8 {
    match op {
        BinOp::Or => 1,
        BinOp::And => 2,
        BinOp::Eq | BinOp::Ne => 3,
        BinOp::Lt | BinOp::Le | BinOp::Gt | BinOp::Ge => 4,
        BinOp::Add | BinOp::Sub => 5,
        BinOp::Mul | BinOp::Div | BinOp::Mod => 6,
    }
}

fn parse_primary(input: &str) -> IResult<&str, Expr> {
    alt((
        parse_literal,
        parse_match,
        parse_ident_expr,
        parse_block,
        delimited(ws(char('(')), parse_expr, ws(char(')'))),
    ))(input)
}

fn parse_match(input: &str) -> IResult<&str, Expr> {
    let (input, _) = ws(tag("match"))(input)?;
    let (input, arms) = delimited(
        ws(char('{')),
        separated_list0(ws(char(',')), parse_match_arm),
        opt(ws(char(','))),
    )(input)?;
    let (input, _) = ws(char('}'))(input)?;
    Ok((input, Expr::Match(arms)))
}

fn parse_match_arm(input: &str) -> IResult<&str, (Expr, Expr)> {
    let (input, cond) = parse_binary_expr_prec(input, 1)?;
    let (input, _) = ws(tag("?"))(input)?;
    let (input, result) = parse_expr(input)?;
    Ok((input, (cond, result)))
}

fn parse_block(input: &str) -> IResult<&str, Expr> {
    map(
        delimited(
            ws(char('{')),
            many0(ws(parse_stmt)),
            ws(char('}')),
        ),
        Expr::Block,
    )(input)
}

fn parse_binop(input: &str) -> IResult<&str, BinOp> {
    alt((
        map(tag("||"), |_| BinOp::Or),
        map(tag("&&"), |_| BinOp::And),
        map(tag("=="), |_| BinOp::Eq),
        map(tag("!="), |_| BinOp::Ne),
        map(tag("<="), |_| BinOp::Le),
        map(tag(">="), |_| BinOp::Ge),
        map(tag("<"), |_| BinOp::Lt),
        map(tag(">"), |_| BinOp::Gt),
        map(tag("+"), |_| BinOp::Add),
        map(tag("-"), |_| BinOp::Sub),
        map(tag("*"), |_| BinOp::Mul),
        map(tag("/"), |_| BinOp::Div),
        map(tag("%"), |_| BinOp::Mod),
    ))(input)
}

fn parse_string_literal(input: &str) -> IResult<&str, String> {
    delimited(char('"'), map(take_while(|c| c != '"'), |s: &str| s.to_string()), char('"'))(input)
}

fn parse_bool_literal(input: &str) -> IResult<&str, Expr> {
    alt((
        map(tag("true"), |_| Expr::Literal(Literal::Bool(true))),
        map(tag("false"), |_| Expr::Literal(Literal::Bool(false))),
    ))(input)
}

fn parse_float_literal(input: &str) -> IResult<&str, Expr> {
    map(
        recognize(tuple((digit1, char('.'), digit1))),
        |s: &str| Expr::Literal(Literal::Float(s.parse().unwrap())),
    )(input)
}

fn parse_literal(input: &str) -> IResult<&str, Expr> {
    alt((
        parse_float_literal,
        parse_bool_literal,
        map(parse_string_literal, |s: String| Expr::Literal(Literal::Str(s))),
        map(digit1, |s: &str| Expr::Literal(Literal::Int(s.parse().unwrap()))),
    ))(input)
}

fn parse_ident_expr(input: &str) -> IResult<&str, Expr> {
    map(parse_ident, Expr::Ident)(input)
}

fn parse_expr_stmt(input: &str) -> IResult<&str, Stmt> {
    let (input, expr) = parse_expr(input)?;
    let (input, _) = ws(char(';'))(input)?;
    Ok((input, Stmt::Expr(expr)))
}

fn parse_static_stmt(input: &str) -> IResult<&str, Stmt> {
    let (input, _) = ws(tag("static"))(input)?;
    let (input, name) = ws(parse_ident)(input)?;
    let (input, _) = ws(char(':'))(input)?;
    let (input, ty) = ws(parse_type)(input)?;
    let (input, _) = ws(char('='))(input)?;
    let (input, expr) = parse_expr(input)?;
    let (input, _) = ws(char(';'))(input)?;
    Ok((input, Stmt::Static(name, ty, expr)))
}