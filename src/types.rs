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
            Stmt::Let(_, _name, ty, expr) => {
                let expr_ty = self.check_expr(expr)?;
                if let Some(expected_ty) = ty {
                    self.ensure_assignment_compatible(expected_ty, expr, &expr_ty)?;
                }
            }
            Stmt::Static(_name, ty, expr) => {
                let expr_ty = self.check_expr(expr)?;
                self.ensure_assignment_compatible(ty, expr, &expr_ty)?;
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
            Expr::Ident(_name) => Err("Undefined variable".to_string()), // TODO: self.symbols.get(name).cloned().ok_or(format!("Undefined variable {}", name)),
            Expr::Array(items) => self.check_array_expr(items),
            Expr::BinaryOp(left, op, right) => {
                let left_ty = self.check_expr(left)?;
                let _right_ty = self.check_expr(right)?;
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
            Expr::FnDef(params, body) => {
                let ret_ty = match &**body {
                    Expr::Ident(name) => params
                        .iter()
                        .find(|p| p.name == *name)
                        .map(|p| p.ty.clone())
                        .unwrap_or(Type::Void),
                    _ => self.check_expr(body)?,
                };
                Ok(Type::Fn(params.clone(), Box::new(ret_ty)))
            }
            _ => Err("Unsupported expr".to_string()),
        }
    }

    fn check_array_expr(&mut self, items: &[Option<Expr>]) -> Result<Type, String> {
        let mut elem_type: Option<Type> = None;
        for expr in items.iter().flatten() {
            let current = self.check_expr(expr)?;
            if let Some(existing) = &elem_type {
                if *existing != current {
                    return Err("Array element type mismatch".to_string());
                }
            } else {
                elem_type = Some(current);
            }
        }
        Ok(Type::Array(
            Box::new(elem_type.unwrap_or(Type::Void)),
            Some(items.len()),
        ))
    }

    fn ensure_assignment_compatible(
        &mut self,
        expected: &Type,
        expr: &Expr,
        actual: &Type,
    ) -> Result<(), String> {
        match (expected, expr, actual) {
            (Type::Fn(expected_params, expected_ret), Expr::FnDef(actual_params, body), Type::Fn(_, _)) => {
                if expected_params.len() != actual_params.len() {
                    return Err(format!(
                        "Function parameter count mismatch: expected {}, got {}",
                        expected_params.len(),
                        actual_params.len()
                    ));
                }

                let mut resolved_params = Vec::with_capacity(expected_params.len());
                for (actual_p, expected_p) in actual_params.iter().zip(expected_params.iter()) {
                    if actual_p.ty != Type::Void && actual_p.ty != expected_p.ty {
                        return Err(format!(
                            "Function parameter type mismatch: expected {:?}, got {:?}",
                            expected_p.ty, actual_p.ty
                        ));
                    }
                    resolved_params.push(Param {
                        name: actual_p.name.clone(),
                        ty: expected_p.ty.clone(),
                    });
                }

                let inferred_ret = match &**body {
                    Expr::Ident(name) => resolved_params
                        .iter()
                        .find(|p| p.name == *name)
                        .map(|p| p.ty.clone())
                        .unwrap_or(Type::Void),
                    _ => self.check_expr(body)?,
                };

                if inferred_ret != **expected_ret {
                    return Err(format!(
                        "Function return type mismatch: expected {:?}, got {:?}",
                        expected_ret, inferred_ret
                    ));
                }
                Ok(())
            }
            (Type::Array(expected_elem, expected_len), Expr::Array(items), Type::Array(actual_elem, actual_len)) => {
                if let Some(n) = expected_len {
                    if items.len() != *n {
                        return Err(format!("Array length mismatch: expected {}, got {}", n, items.len()));
                    }
                }
                if let Some(actual_n) = actual_len {
                    if let Some(expected_n) = expected_len {
                        if actual_n != expected_n {
                            return Err(format!("Array length mismatch: expected {}, got {}", expected_n, actual_n));
                        }
                    }
                }
                if **expected_elem != **actual_elem && **actual_elem != Type::Void {
                    return Err(format!(
                        "Type mismatch: expected {:?}, got {:?}",
                        expected, actual
                    ));
                }
                for item in items.iter().flatten() {
                    let item_ty = self.check_expr(item)?;
                    if item_ty != **expected_elem {
                        return Err(format!(
                            "Array element type mismatch: expected {:?}, got {:?}",
                            expected_elem, item_ty
                        ));
                    }
                }
                Ok(())
            }
            _ => {
                if expected != actual {
                    return Err(format!("Type mismatch: expected {:?}, got {:?}", expected, actual));
                }
                Ok(())
            }
        }
    }
}