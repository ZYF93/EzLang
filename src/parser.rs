use nom::{
    IResult,
    branch::alt,
    bytes::complete::{tag, take_until, take_while1, take_while},
    character::complete::{char, digit1, multispace1},
    combinator::{all_consuming, map, opt, recognize, value},
    multi::{many0, separated_list0},
    sequence::{delimited, preceded, terminated, tuple},
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
    all_consuming(terminated(many0(ws(parse_stmt)), skip_ws))(input)
}

fn parse_stmt(input: &str) -> IResult<&str, Stmt> {
    alt((
        parse_let_stmt,
        parse_const_stmt,
        parse_static_stmt,
        parse_loop_stmt,
        parse_break_stmt,
        parse_continue_stmt,
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
    let (mut input, first) = parse_single_type(input)?;
    let mut members = vec![first];

    loop {
        let parsed_union = preceded(ws(char('|')), parse_single_type)(input);
        match parsed_union {
            Ok((next_input, ty)) => {
                members.push(ty);
                input = next_input;
            }
            Err(_) => break,
        }
    }

    if members.len() == 1 {
        Ok((input, members.remove(0)))
    } else {
        Ok((input, Type::Union(members)))
    }
}

fn parse_single_type(input: &str) -> IResult<&str, Type> {
    let (mut input, mut ty) = ws(parse_base_type)(input)?;
    loop {
        let parsed = alt((
            value(None, ws(tag("[]"))),
            map(delimited(ws(char('[')), ws(digit1), ws(char(']'))), |s: &str| {
                Some(s.parse::<usize>().unwrap())
            }),
        ))(input);

        match parsed {
            Ok((next_input, len)) => {
                ty = Type::Array(Box::new(ty), len);
                input = next_input;
            }
            Err(_) => break,
        }
    }

    loop {
        match ws(char('?'))(input) {
            Ok((next_input, _)) => {
                ty = Type::Optional(Box::new(ty));
                input = next_input;
            }
            Err(_) => break,
        }
    }

    Ok((input, ty))
}

fn parse_base_type(input: &str) -> IResult<&str, Type> {
    alt((
        parse_fn_type,
        map(tag("I64"), |_| Type::I64),
        map(tag("I32"), |_| Type::I32),
        map(tag("I8"), |_| Type::I8),
        map(tag("U64"), |_| Type::U64),
        map(tag("U32"), |_| Type::U32),
        map(tag("U8"), |_| Type::U8),
        map(tag("F32"), |_| Type::F32),
        map(tag("F64"), |_| Type::F64),
        map(tag("Str"), |_| Type::Str),
        map(tag("Bool"), |_| Type::Bool),
        map(tag("Void"), |_| Type::Void),
        map(tag("Blob"), |_| Type::Blob),
    ))(input)
}

fn parse_fn_type(input: &str) -> IResult<&str, Type> {
    let (input, params) = delimited(
        ws(char('(')),
        separated_list0(ws(char(',')), parse_type_param),
        ws(char(')')),
    )(input)?;
    let (input, _) = ws(tag("=>"))(input)?;
    let (input, ret_ty) = parse_single_type(input)?;
    Ok((input, Type::Fn(params, Box::new(ret_ty))))
}

fn parse_type_param(input: &str) -> IResult<&str, Param> {
    let (input, name) = ws(parse_ident)(input)?;
    let (input, _) = ws(char(':'))(input)?;
    let (input, ty) = parse_type(input)?;
    Ok((input, Param { name, ty }))
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
        parse_fn_literal,
        parse_literal,
        parse_array_literal,
        parse_match,
        parse_ident_expr,
        parse_block,
        delimited(ws(char('(')), parse_expr, ws(char(')'))),
    ))(input)
}

fn parse_fn_literal(input: &str) -> IResult<&str, Expr> {
    let (input, params) = delimited(
        ws(char('(')),
        separated_list0(ws(char(',')), parse_fn_literal_param),
        ws(char(')')),
    )(input)?;
    let (input, _) = ws(tag("=>"))(input)?;
    let (input, body) = parse_expr(input)?;
    Ok((input, Expr::FnDef(params, Box::new(body))))
}

fn parse_fn_literal_param(input: &str) -> IResult<&str, Param> {
    let (input, name) = ws(parse_ident)(input)?;
    let (input, ty) = opt(preceded(ws(char(':')), parse_type))(input)?;
    Ok((input, Param {
        name,
        ty: ty.unwrap_or(Type::Void),
    }))
}

fn parse_array_literal(input: &str) -> IResult<&str, Expr> {
    let (mut input, _) = ws(char('['))(input)?;
    let mut items: Vec<Option<Expr>> = Vec::new();
    let mut last_was_comma = false;

    loop {
        let (next, _) = skip_ws(input)?;
        input = next;

        if let Ok((next, _)) = char::<&str, nom::error::Error<&str>>(']')(input) {
            if last_was_comma {
                items.push(None);
            }
            input = next;
            break;
        }

        if let Ok((next, expr)) = parse_expr(input) {
            items.push(Some(expr));
            input = next;
        } else if let Ok((next, _)) = char::<&str, nom::error::Error<&str>>(',')(input) {
            items.push(None);
            input = next;
            last_was_comma = true;
            continue;
        } else {
            return Err(nom::Err::Error(nom::error::Error::new(input, nom::error::ErrorKind::Char)));
        }

        let (next, _) = skip_ws(input)?;
        input = next;
        if let Ok((next, _)) = char::<&str, nom::error::Error<&str>>(',')(input) {
            input = next;
            last_was_comma = true;
        } else {
            last_was_comma = false;
        }
    }

    Ok((input, Expr::Array(items)))
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

fn parse_break_stmt(input: &str) -> IResult<&str, Stmt> {
    let (input, _) = ws(tag("break"))(input)?;
    let (input, _) = ws(char(';'))(input)?;
    Ok((input, Stmt::Break))
}

fn parse_continue_stmt(input: &str) -> IResult<&str, Stmt> {
    let (input, _) = ws(tag("continue"))(input)?;
    let (input, _) = ws(char(';'))(input)?;
    Ok((input, Stmt::Continue))
}

fn parse_loop_stmt(input: &str) -> IResult<&str, Stmt> {
    let (input, _) = ws(tag("loop"))(input)?;
    let (input, kind) = parse_loop_kind(input)?;
    let (input, body) = delimited(ws(char('{')), many0(ws(parse_stmt)), ws(char('}')))(input)?;
    let (input, _) = ws(char(';'))(input)?;
    Ok((input, Stmt::Loop(kind, body)))
}

fn parse_loop_kind(input: &str) -> IResult<&str, LoopKind> {
    if let Ok((_, _)) = ws(char('{'))(input) {
        return Ok((input, LoopKind::Infinite));
    }

    let (input, _) = ws(parse_ident)(input)?;
    let (input, _) = ws(tag("in"))(input)?;
    let (input, start_or_iter) = parse_binary_expr_prec(input, 1)?;
    let (input, range_end) = opt(preceded(ws(tag("...")), |i| parse_binary_expr_prec(i, 1)))(input)?;

    if let Some(end) = range_end {
        Ok((input, LoopKind::Range(start_or_iter, end)))
    } else {
        Ok((input, LoopKind::Iter(start_or_iter)))
    }
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