"""
EzLang IR Generator Module
"""

import llvmlite.ir as ir
from .antlr_generated.EzLangVisitor import EzLangVisitor
from .antlr_generated.EzLangParser import EzLangParser

class IRGenerator(EzLangVisitor):
    def __init__(self, tree):
        self.tree = tree
        self.module = ir.Module(name="ezlang_module")
        self.builder = None
        self.scopes = []
        self.locals = [{}]
        
        # 定义内置类型
        self.i32 = ir.IntType(32)
        self.i64 = ir.IntType(64)
        self.i1 = ir.IntType(1)
        self.i8 = ir.IntType(8)
        self.void = ir.VoidType()
        
        # 全局 Arena 指针
        self.arena_ptr = ir.GlobalVariable(self.module, self.i32, name="arena_top")
        self.arena_ptr.initializer = ir.Constant(self.i32, 0)
        self.arena_ptr.linkage = 'internal'

    def generate_ir(self):
        self._setup_builtins()
        self.visit(self.tree)
        return str(self.module)

    def _setup_builtins(self):
        func_type = ir.FunctionType(self.i32, [self.i32])
        self.alloc_func = ir.Function(self.module, func_type, name="arena_alloc")
        block = self.alloc_func.append_basic_block(name="entry")
        builder = ir.IRBuilder(block)
        size = self.alloc_func.args[0]
        old_ptr = builder.load(self.arena_ptr)
        aligned_ptr = builder.add(old_ptr, ir.Constant(self.i32, 7))
        aligned_ptr = builder.and_(aligned_ptr, ir.Constant(self.i32, -8))
        new_ptr = builder.add(aligned_ptr, size)
        builder.store(new_ptr, self.arena_ptr)
        builder.ret(aligned_ptr)

    def visitProgram(self, ctx: EzLangParser.ProgramContext):
        func_type = ir.FunctionType(self.void, [])
        func = ir.Function(self.module, func_type, name="main")
        block = func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)
        self.visitChildren(ctx)
        self.builder.ret_void()
        return None

    def visitBlock(self, ctx: EzLangParser.BlockContext):
        saved_ptr = self.builder.load(self.arena_ptr)
        self.scopes.append(saved_ptr)
        self.locals.append({})
        self.visitChildren(ctx)
        self.locals.pop()
        current_saved_ptr = self.scopes.pop()
        self.builder.store(current_saved_ptr, self.arena_ptr)
        return None

    def visitVariableDeclaration(self, ctx: EzLangParser.VariableDeclarationContext):
        if ctx.expression():
            val = self.visit(ctx.expression())
            if ctx.ID():
                var_name = ctx.ID().getText()
                self.locals[-1][var_name] = val
        return None

    def visitAdditiveExpression(self, ctx: EzLangParser.AdditiveExpressionContext):
        results = [self.visit(m) for m in ctx.multiplicativeExpression()]
        res = results[0]
        for i in range(1, len(results)):
            op = ctx.getChild(i*2-1).getText()
            if op == '+': res = self.builder.add(res, results[i])
            else: res = self.builder.sub(res, results[i])
        return res

    def visitMultiplicativeExpression(self, ctx: EzLangParser.MultiplicativeExpressionContext):
        results = [self.visit(u) for u in ctx.unaryExpression()]
        res = results[0]
        for i in range(1, len(results)):
            op = ctx.getChild(i*2-1).getText()
            if op == '*': res = self.builder.mul(res, results[i])
            elif op == '/': res = self.builder.sdiv(res, results[i])
            else: res = self.builder.srem(res, results[i])
        return res

    def visitRelationalExpression(self, ctx: EzLangParser.RelationalExpressionContext):
        results = [self.visit(s) for s in ctx.shiftExpression()]
        if len(results) == 1: return results[0]
        res = results[0]
        for i in range(1, len(results)):
            op = ctx.getChild(i*2-1).getText()
            pred = {'>': '>', '<': '<', '>=': '>=', '<=': '<='}[op]
            res = self.builder.icmp_signed(pred, res, results[i])
        return res

    def visitLogicalAndExpression(self, ctx: EzLangParser.LogicalAndExpressionContext):
        # 短路与：if left is false, result is false; else evaluate right.
        sub_exprs = ctx.equalityExpression()
        if len(sub_exprs) == 1: return self.visit(sub_exprs[0])
        
        left_val = self.visit(sub_exprs[0])
        
        for i in range(1, len(sub_exprs)):
            current_block = self.builder.block
            right_block = self.builder.function.append_basic_block(name="and.rhs")
            exit_block = self.builder.function.append_basic_block(name="and.exit")
            
            self.builder.cbranch(left_val, right_block, exit_block)
            
            # Right side
            self.builder.position_at_end(right_block)
            right_val = self.visit(sub_exprs[i])
            self.builder.branch(exit_block)
            last_right_block = self.builder.block
            
            # Exit
            self.builder.position_at_end(exit_block)
            phi = self.builder.phi(self.i1, name="and.phi")
            phi.add_incoming(ir.Constant(self.i1, 0), current_block)
            phi.add_incoming(right_val, last_right_block)
            left_val = phi
            
        return left_val

    def visitLogicalOrExpression(self, ctx: EzLangParser.LogicalOrExpressionContext):
        # 短路或：if left is true, result is true; else evaluate right.
        sub_exprs = ctx.logicalAndExpression()
        if len(sub_exprs) == 1: return self.visit(sub_exprs[0])
        
        left_val = self.visit(sub_exprs[0])
        for i in range(1, len(sub_exprs)):
            current_block = self.builder.block
            right_block = self.builder.function.append_basic_block(name="or.rhs")
            exit_block = self.builder.function.append_basic_block(name="or.exit")
            
            self.builder.cbranch(left_val, exit_block, right_block)
            
            # Right side
            self.builder.position_at_end(right_block)
            right_val = self.visit(sub_exprs[i])
            self.builder.branch(exit_block)
            last_right_block = self.builder.block
            
            # Exit
            self.builder.position_at_end(exit_block)
            phi = self.builder.phi(self.i1, name="or.phi")
            phi.add_incoming(ir.Constant(self.i1, 1), current_block)
            phi.add_incoming(right_val, last_right_block)
            left_val = phi
            
        return left_val

    def visitEqualityExpression(self, ctx: EzLangParser.EqualityExpressionContext):
        results = [self.visit(r) for r in ctx.relationalExpression()]
        if len(results) == 1: return results[0]
        res = results[0]
        for i in range(1, len(results)):
            op = ctx.getChild(i*2-1).getText()
            pred = '==' if op == '==' else '!='
            res = self.builder.icmp_signed(pred, res, results[i])
        return res

    def visitPostfixExpression(self, ctx: EzLangParser.PostfixExpressionContext):
        base = self.visit(ctx.primaryExpression())
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if isinstance(child, EzLangParser.PostfixContext):
                if child.LPAREN():
                    size = ir.Constant(self.i32, 64)
                    base = self.builder.call(self.alloc_func, [size])
        return base

    def visitPrimaryExpression(self, ctx: EzLangParser.PrimaryExpressionContext):
        if ctx.ID():
            name = ctx.ID().getText()
            for scope in reversed(self.locals):
                if name in scope: return scope[name]
            return name
        return self.visitChildren(ctx)

    def visitLiteral(self, ctx: EzLangParser.LiteralContext):
        if ctx.INT():
            val = int(ctx.INT().getText(), 0)
            return ir.Constant(self.i32, val)
        if ctx.TRUE(): return ir.Constant(self.i1, 1)
        if ctx.FALSE(): return ir.Constant(self.i1, 0)
        return None

    def visitStatement(self, ctx): return self.visitChildren(ctx)
    def visitExpression(self, ctx): return self.visitChildren(ctx)
    def visitAssignmentExpression(self, ctx): return self.visitChildren(ctx)
    def visitPipelineExpression(self, ctx): return self.visitChildren(ctx)
    def visitConditionalExpression(self, ctx): return self.visitChildren(ctx)
    def visitShiftExpression(self, ctx): return self.visit(ctx.additiveExpression(0))
    def visitUnaryExpression(self, ctx): return self.visitChildren(ctx)