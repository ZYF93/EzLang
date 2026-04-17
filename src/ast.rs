use std::collections::HashMap;

#[derive(Debug, Clone)]
pub enum Type {
    I8, I32, I64, U8, U32, U64, F32, F64,
    Str, Bool, Void, Blob,
    Array(Box<Type>, Option<usize>), // Type[] or Type[n]
    Fn(Vec<Param>, Box<Type>), // (args) => Return
    Optional(Box<Type>),
    Union(Vec<Type>),
    Struct(String, Vec<Field>, Option<Box<Type>>), // name, fields, base
    Generic(String), // T
    Alias(String, Box<Type>), // type Alias = Shape
}

#[derive(Debug, Clone)]
pub struct Field {
    pub name: String,
    pub ty: Type,
    pub default: Option<Box<Expr>>,
}

#[derive(Debug, Clone)]
pub struct Param {
    pub name: String,
    pub ty: Type,
}

#[derive(Debug, Clone)]
pub enum Expr {
    Literal(Literal),
    Ident(String),
    BinaryOp(Box<Expr>, BinOp, Box<Expr>),
    UnaryOp(UnOp, Box<Expr>),
    Call(Box<Expr>, Vec<Arg>),
    StructInit(String, Vec<(String, Expr)>), // Name(field=val)
    Array(Vec<Expr>),
    If(Box<Expr>, Box<Expr>, Box<Expr>), // cond ? then : else
    Match(Vec<(Expr, Expr)>), // match { cond ? expr, ... }
    Block(Vec<Stmt>),
    FnDef(Vec<Param>, Box<Expr>), // (args) => expr
    Async(Box<Expr>), // async expr
    Await(Box<Expr>),
    Cast(Type, Box<Expr>), // Type! expr
    Typeof(Box<Expr>),
    Pipe(Box<Expr>, Box<Expr>), // value -> fn
    Curry(Box<Expr>, Vec<Arg>), // fn(a=?, b=2)
    Tag(String, HashMap<String, Expr>, Vec<Expr>), // <tag attrs> children </tag>
}

#[derive(Debug, Clone)]
pub enum Literal {
    Int(i64),
    Uint(u64),
    Float(f64),
    Str(String),
    Bool(bool),
}

#[derive(Debug, Clone)]
pub enum BinOp {
    Add, Sub, Mul, Div, Mod,
    Eq, Ne, Lt, Le, Gt, Ge,
    And, Or,
}

#[derive(Debug, Clone)]
pub enum UnOp {
    Neg, Not,
}

#[derive(Debug, Clone)]
pub struct Arg {
    pub name: Option<String>,
    pub expr: Expr,
}

#[derive(Debug, Clone)]
pub enum Stmt {
    Let(bool, String, Option<Type>, Expr), // let/const name: Type = expr
    Static(String, Type, Expr),
    Expr(Expr),
    Loop(LoopKind, Vec<Stmt>),
    Break,
    Continue,
    Return(Option<Expr>),
    Import(String, Vec<String>), // from "path" import {items}
    Export(Box<Stmt>),
    Declare(String, Type), // declare const name: Type
    StructDef(String, Vec<String>, Vec<Field>, Vec<Method>), // struct Name<T> { ...Base; fields; methods }
    TypeAlias(String, Type),
}

#[derive(Debug, Clone)]
pub enum LoopKind {
    Infinite,
    Range(Expr, Expr), // 0...10
    Iter(Expr), // item in list
}

#[derive(Debug, Clone)]
pub struct Method {
    pub name: String,
    pub params: Vec<Param>,
    pub body: Expr,
}

#[derive(Debug, Clone)]
pub struct Decorator {
    pub name: String,
    pub args: Vec<Expr>,
}