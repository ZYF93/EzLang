use crate::ast::*;
use std::collections::HashMap;

pub struct TypeChecker {
    symbols: HashMap<String, Type>,
}

impl TypeChecker {
    pub fn new() -> Self {
        Self {
            symbols: HashMap::new(),
        }
    }

    pub fn check_stmts(&mut self, stmts: &[Stmt]) -> Result<(), String> {
        for stmt in stmts {
            self.check_stmt(stmt)?;
        }
        Ok(())
    }

    fn check_stmt(&mut self, stmt: &Stmt) -> Result<(), String> {
        match stmt {
            Stmt::Let(_, name, ty, expr) => {
                let expr_ty = self.check_expr(expr)?;
                if let Some(expected_ty) = ty {
                    // TODO: implement type equality
                    // if expr_ty != *expected_ty {
                    //     return Err(format!("Type mismatch: expected {:?}, got {:?}", expected_ty, expr_ty));
                    // }
                }
                // self.symbols.insert(name.clone(), expr_ty);
            }
            Stmt::Static(name, ty, expr) => {
                let expr_ty = self.check_expr(expr)?;
                // TODO: check ty
                // if expr_ty != *ty {
                //     return Err(format!("Type mismatch for static {}", name));
                // }
                // self.symbols.insert(name.clone(), ty.clone());
            }
            Stmt::Expr(expr) => {
                self.check_expr(expr)?;
            }
            _ => {} // TODO: add more
        }
        Ok(())
    }

    fn check_expr(&mut self, expr: &Expr) -> Result<Type, String> {
        match expr {
            Expr::Literal(lit) => match lit {
                Literal::Int(_) => Ok(Type::I32), // assume I32 for now
                Literal::Str(_) => Ok(Type::Str),
                Literal::Bool(_) => Ok(Type::Bool),
                _ => Err("Unsupported literal".to_string()),
            },
            Expr::Ident(name) => Err("Undefined variable".to_string()), // TODO: self.symbols.get(name).cloned().ok_or(format!("Undefined variable {}", name)),
            Expr::BinaryOp(left, op, right) => {
                let left_ty = self.check_expr(left)?;
                let right_ty = self.check_expr(right)?;
                // TODO: check types equal
                // if left_ty != right_ty {
                //     return Err("Type mismatch in binary op".to_string());
                // }
                match op {
                    BinOp::Add | BinOp::Sub | BinOp::Mul | BinOp::Div => Ok(left_ty),
                    BinOp::Eq | BinOp::Ne | BinOp::Lt | BinOp::Le | BinOp::Gt | BinOp::Ge => Ok(Type::Bool),
                    _ => Err("Unsupported op".to_string()),
                }
            }
            _ => Err("Unsupported expr".to_string()),
        }
    }
}