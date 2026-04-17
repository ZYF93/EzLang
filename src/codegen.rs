use inkwell::builder::Builder;
use inkwell::context::Context;
use inkwell::module::Module;
use inkwell::types::{BasicTypeEnum, StructType};
use inkwell::values::{BasicValueEnum, FunctionValue, PointerValue};
use std::collections::HashMap;
use crate::ast::*;

pub struct CodeGen<'ctx> {
    context: &'ctx Context,
    module: Module<'ctx>,
    builder: Builder<'ctx>,
    variables: HashMap<String, PointerValue<'ctx>>,
}

impl<'ctx> CodeGen<'ctx> {
    pub fn new(context: &'ctx Context) -> Self {
        let module = context.create_module("ezlang");
        let builder = context.create_builder();
        Self {
            context,
            module,
            builder,
            variables: HashMap::new(),
        }
    }

    pub fn compile_stmts(&mut self, stmts: &[Stmt]) -> Result<(), String> {
        for stmt in stmts {
            self.compile_stmt(stmt)?;
        }
        Ok(())
    }

    fn compile_stmt(&mut self, stmt: &Stmt) -> Result<(), String> {
        match stmt {
            Stmt::Let(_, name, _, expr) => {
                let val = self.compile_expr(expr)?;
                let ptr = self.builder.build_alloca(val.get_type(), name)?;
                self.builder.build_store(ptr, val)?;
                self.variables.insert(name.clone(), ptr);
            }
            Stmt::Static(name, ty, expr) => {
                let val = self.compile_expr(expr)?;
                let global = self.module.add_global(val.get_type(), None, name);
                global.set_initializer(&val);
                // Note: statics are global, not in variables map
            }
            Stmt::Expr(expr) => {
                self.compile_expr(expr)?;
            }
            _ => {} // TODO
        }
        Ok(())
    }

    fn compile_expr(&mut self, expr: &Expr) -> Result<BasicValueEnum<'ctx>, String> {
        match expr {
            Expr::Literal(lit) => match lit {
                Literal::Int(i) => Ok(self.context.i32_type().const_int(*i as u64, false).into()),
                Literal::Str(s) => {
                    let str_val = self.builder.build_global_string_ptr(s, "str")?;
                    Ok(str_val.as_pointer_value().into())
                }
                Literal::Bool(b) => Ok(self.context.bool_type().const_int(*b as u64, false).into()),
                _ => Err("Unsupported literal".to_string()),
            },
            Expr::Ident(name) => {
                let ptr = self.variables.get(name).ok_or("Undefined variable")?;
                Ok(self.builder.build_load(*ptr, name)?)
            }
            Expr::BinaryOp(left, op, right) => {
                let left_val = self.compile_expr(left)?;
                let right_val = self.compile_expr(right)?;
                match op {
                    BinOp::Add => Ok(self.builder.build_int_add(left_val.into_int_value(), right_val.into_int_value(), "add")?.into()),
                    BinOp::Sub => Ok(self.builder.build_int_sub(left_val.into_int_value(), right_val.into_int_value(), "sub")?.into()),
                    BinOp::Eq => Ok(self.builder.build_int_compare(inkwell::IntPredicate::EQ, left_val.into_int_value(), right_val.into_int_value(), "eq")?.into()),
                    _ => Err("Unsupported op".to_string()),
                }
            }
            _ => Err("Unsupported expr".to_string()),
        }
    }

    pub fn get_module(&self) -> &Module<'ctx> {
        &self.module
    }
}