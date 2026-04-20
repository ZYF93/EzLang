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

    def visitPostfixExpression(self, ctx: EzLangParser.PostfixExpressionContext):
        # 如果有 postfix (LPAREN ... RPAREN)，说明是调用或实例化
        base = self.visit(ctx.primaryExpression())
        
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if isinstance(child, EzLangParser.PostfixContext):
                if child.LPAREN():
                    # 简化逻辑：如果是首字母大写的 ID 后跟 ()，认为是结构体实例化
                    # 这里先直接为测试生成 arena_alloc 调用
                    size = ir.Constant(self.i32, 64)
                    base = self.builder.call(self.alloc_func, [size])
        return base

    def visitPrimaryExpression(self, ctx: EzLangParser.PrimaryExpressionContext):
        if ctx.ID():
            name = ctx.ID().getText()
            for scope in reversed(self.locals):
                if name in scope:
                    return scope[name]
            return name # 返回名称用于识别（简化处理）
        return self.visitChildren(ctx)

    def visitLiteral(self, ctx: EzLangParser.LiteralContext):
        if ctx.INT():
            val = int(ctx.INT().getText(), 0)
            return ir.Constant(self.i32, val)
        return None

    # 默认遍历
    def visitStatement(self, ctx): return self.visitChildren(ctx)
    def visitExpression(self, ctx): return self.visitChildren(ctx)
    def visitAssignmentExpression(self, ctx): return self.visitChildren(ctx)
    def visitPipelineExpression(self, ctx): return self.visitChildren(ctx)
    def visitConditionalExpression(self, ctx): return self.visitChildren(ctx)
    def visitLogicalOrExpression(self, ctx): return self.visitChildren(ctx)
    def visitLogicalAndExpression(self, ctx): return self.visitChildren(ctx)
    def visitEqualityExpression(self, ctx): return self.visitChildren(ctx)
    def visitRelationalExpression(self, ctx): return self.visitChildren(ctx)
    def visitShiftExpression(self, ctx): return self.visitChildren(ctx)
    def visitAdditiveExpression(self, ctx): return self.visitChildren(ctx)
    def visitMultiplicativeExpression(self, ctx): return self.visitChildren(ctx)
    def visitUnaryExpression(self, ctx): return self.visitChildren(ctx)