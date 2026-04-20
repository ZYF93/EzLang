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
        self.current_func = None
        self.scopes = []
        self.locals = [{}]
        self.struct_types = {}
        
        # 定义内置类型
        self.i32 = ir.IntType(32)
        self.i64 = ir.IntType(64)
        self.i1 = ir.IntType(1)
        self.i8 = ir.IntType(8)
        self.void = ir.VoidType()
        
        self.type_map = {
            "I32": self.i32,
            "I64": self.i64,
            "Bool": self.i1,
            "Void": self.void
        }
        
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
        self.current_func = ir.Function(self.module, func_type, name="main")
        block = self.current_func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)
        self.visitChildren(ctx)
        if not self.builder.block.is_terminated:
            self.builder.ret_void()
        return None

    # --- Types ---

    def visitType(self, ctx: EzLangParser.TypeContext):
        st = ctx.getChild(0)
        if isinstance(st, EzLangParser.SimpleTypeContext):
            type_name = st.getText()
            return self.type_map.get(type_name, self.i32)
        return self.i32

    def visitStructDeclaration(self, ctx: EzLangParser.StructDeclarationContext):
        name = ctx.ID().getText()
        fields = {}
        field_types = []
        body = ctx.structBody()
        idx = 0
        for i in range(body.getChildCount()):
            child = body.getChild(i)
            if isinstance(child, EzLangParser.FieldContext):
                field_name = child.ID().getText()
                field_type = self.visitType(child.type_())
                fields[field_name] = idx
                field_types.append(field_type)
                idx += 1
        struct_type = ir.LiteralStructType(field_types)
        self.struct_types[name] = {"fields": fields, "ir_type": struct_type}
        return None

    # --- Expressions ---

    def visitVariableDeclaration(self, ctx: EzLangParser.VariableDeclarationContext):
        var_name = ctx.ID().getText()
        
        if ctx.expression():
            # 为 visitLiteral 提示目标类型 (如果有显式类型)
            if ctx.type_():
                target_type = self.visitType(ctx.type_())
                self._target_type_hint = target_type
            else:
                target_type = None # 待推断
            
            val = self.visit(ctx.expression())
            if hasattr(self, '_target_type_hint'): del self._target_type_hint
            
            # 类型推断
            if target_type is None:
                target_type = val.type
                
            ptr = self.builder.alloca(target_type, name=var_name)
            self.builder.store(val, ptr)
            self.locals[-1][var_name] = self.builder.load(ptr)
        return None

    def visitLiteral(self, ctx: EzLangParser.LiteralContext):
        target_type = getattr(self, '_target_type_hint', self.i32)
        if ctx.INT():
            val = int(ctx.INT().getText(), 0)
            return ir.Constant(target_type, val)
        if ctx.TRUE(): return ir.Constant(self.i1, 1)
        if ctx.FALSE(): return ir.Constant(self.i1, 0)
        return None

    def visitPostfixExpression(self, ctx: EzLangParser.PostfixExpressionContext):
        base = self.visit(ctx.primaryExpression())
        current_struct_name = None
        if isinstance(base, str) and base in self.struct_types:
            current_struct_name = base
            
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if isinstance(child, EzLangParser.PostfixContext):
                if child.LPAREN():
                    args = []
                    if child.argumentList():
                        for na in child.argumentList().namedArgument():
                            args.append(self.visit(na.expression()))
                    
                    if isinstance(base, ir.Function):
                        base = self.builder.call(base, args)
                    elif current_struct_name:
                        st_info = self.struct_types[current_struct_name]
                        size = ir.Constant(self.i32, 64) # 简化：固定大小或手动计算
                        addr_int = self.builder.call(self.alloc_func, [size])
                        ptr_type = ir.PointerType(st_info["ir_type"])
                        base = self.builder.inttoptr(addr_int, ptr_type)
                    else:
                        size = ir.Constant(self.i32, 64)
                        base = self.builder.call(self.alloc_func, [size])
                
                elif child.DOT():
                    field_name = child.ID().getText()
                    if hasattr(base, 'type') and isinstance(base.type, ir.PointerType) and isinstance(base.type.pointee, ir.LiteralStructType):
                        found_st = None
                        for name, info in self.struct_types.items():
                            if info["ir_type"] == base.type.pointee:
                                found_st = info
                                break
                        if found_st and field_name in found_st["fields"]:
                            idx = found_st["fields"][field_name]
                            ptr = self.builder.gep(base, [ir.Constant(self.i32, 0), ir.Constant(self.i32, idx)])
                            # 保存最后一个访问的地址用于赋值
                            self._last_ptr = ptr
                            base = self.builder.load(ptr)
        return base

    def visitAssignmentExpression(self, ctx: EzLangParser.AssignmentExpressionContext):
        if ctx.assignmentOp():
            self._last_ptr = None
            # 先访问 LHS 触发 postfix 的 gep
            self.visit(ctx.pipelineExpression())
            target_ptr = getattr(self, '_last_ptr', None)
            
            val = self.visit(ctx.assignmentExpression())
            if target_ptr:
                self.builder.store(val, target_ptr)
            else:
                target_name = ctx.pipelineExpression().getText()
                # 简化处理：更新本地绑定
                self.locals[-1][target_name] = val
            return val
        return self.visit(ctx.pipelineExpression())

    # --- Blocks ---

    def visitBlock(self, ctx: EzLangParser.BlockContext):
        saved_ptr = self.builder.load(self.arena_ptr)
        self.scopes.append(saved_ptr)
        self.locals.append({})
        last_val = None
        if ctx.statement():
            for stmt in ctx.statement():
                last_val = self.visit(stmt)
        self.locals.pop()
        current_saved_ptr = self.scopes.pop()
        self.builder.store(current_saved_ptr, self.arena_ptr)
        return last_val

    # --- Builtins / Helpers ---

    def _ensure_value(self, val):
        if isinstance(val, str): return ir.Constant(self.i32, 0)
        return val

    def visitAdditiveExpression(self, ctx: EzLangParser.AdditiveExpressionContext):
        results = [self._ensure_value(self.visit(m)) for m in ctx.multiplicativeExpression()]
        res = results[0]
        for i in range(1, len(results)):
            op = ctx.getChild(i*2-1).getText()
            if op == '+': res = self.builder.add(res, results[i])
            else: res = self.builder.sub(res, results[i])
        return res

    def visitMultiplicativeExpression(self, ctx: EzLangParser.MultiplicativeExpressionContext):
        results = [self._ensure_value(self.visit(u)) for u in ctx.unaryExpression()]
        res = results[0]
        for i in range(1, len(results)):
            op = ctx.getChild(i*2-1).getText()
            if op == '*': res = self.builder.mul(res, results[i])
            elif op == '/': res = self.builder.sdiv(res, results[i])
            else: res = self.builder.srem(res, results[i])
        return res

    def visitRelationalExpression(self, ctx: EzLangParser.RelationalExpressionContext):
        results = [self._ensure_value(self.visit(s)) for s in ctx.shiftExpression()]
        if len(results) == 1: return results[0]
        res = results[0]
        for i in range(1, len(results)):
            op = ctx.getChild(i*2-1).getText()
            pred = {'>': '>', '<': '<', '>=': '>=', '<=': '<='}[op]
            res = self.builder.icmp_signed(pred, res, results[i])
        return res

    def visitLogicalAndExpression(self, ctx: EzLangParser.LogicalAndExpressionContext):
        sub_exprs = ctx.equalityExpression()
        if len(sub_exprs) == 1: return self.visit(sub_exprs[0])
        left_val = self._ensure_value(self.visit(sub_exprs[0]))
        for i in range(1, len(sub_exprs)):
            current_block = self.builder.block
            right_block = self.builder.function.append_basic_block(name="and.rhs")
            exit_block = self.builder.function.append_basic_block(name="and.exit")
            self.builder.cbranch(left_val, right_block, exit_block)
            self.builder.position_at_end(right_block)
            right_val = self._ensure_value(self.visit(sub_exprs[i]))
            self.builder.branch(exit_block)
            last_right_block = self.builder.block
            self.builder.position_at_end(exit_block)
            phi = self.builder.phi(self.i1, name="and.phi")
            phi.add_incoming(ir.Constant(self.i1, 0), current_block)
            phi.add_incoming(right_val, last_right_block)
            left_val = phi
        return left_val

    def visitPrimaryExpression(self, ctx: EzLangParser.PrimaryExpressionContext):
        if ctx.ID():
            name = ctx.ID().getText()
            for scope in reversed(self.locals):
                if name in scope: return scope[name]
            return name
        if ctx.LPAREN(): return self.visit(ctx.expression())
        if ctx.structLiteral(): return self.visit(ctx.structLiteral())
        return self.visitChildren(ctx)

    def visitStructLiteral(self, ctx: EzLangParser.StructLiteralContext):
        name = ctx.ID().getText()
        if name in self.struct_types:
            st_info = self.struct_types[name]
            size = ir.Constant(self.i32, 64)
            addr_int = self.builder.call(self.alloc_func, [size])
            return self.builder.inttoptr(addr_int, ir.PointerType(st_info["ir_type"]))
        return self.builder.call(self.alloc_func, [ir.Constant(self.i32, 64)])

    def visitExpressionStatement(self, ctx: EzLangParser.ExpressionStatementContext):
        if ctx.expression(): return self.visit(ctx.expression())
        return self.visitChildren(ctx)

    def visitConditionalStatement(self, ctx: EzLangParser.ConditionalStatementContext):
        cond = self.visit(ctx.expression(0))
        then_block = self.builder.function.append_basic_block(name="if.then")
        exit_block = self.builder.function.append_basic_block(name="if.exit")
        if ctx.COLON():
            else_block = self.builder.function.append_basic_block(name="if.else")
            self.builder.cbranch(cond, then_block, else_block)
            self.builder.position_at_end(then_block)
            self._visit_branch_body(ctx, 1)
            if not self.builder.block.is_terminated: self.builder.branch(exit_block)
            self.builder.position_at_end(else_block)
            self._visit_branch_body(ctx, 2)
            if not self.builder.block.is_terminated: self.builder.branch(exit_block)
        else:
            self.builder.cbranch(cond, then_block, exit_block)
            self.builder.position_at_end(then_block)
            self._visit_branch_body(ctx, 1)
            if not self.builder.block.is_terminated: self.builder.branch(exit_block)
        self.builder.position_at_end(exit_block)
        return None

    def _visit_branch_body(self, ctx, branch_idx):
        found = 0
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if i < 2: continue
            if child.getText() in ['?', ':']: continue
            found += 1
            if found == branch_idx: return self.visit(child)
        return None

    def visitStatement(self, ctx): return self.visitChildren(ctx)
    def visitPipelineExpression(self, ctx): return self.visitChildren(ctx)
    def visitShiftExpression(self, ctx): return self.visit(ctx.additiveExpression(0))
    def visitUnaryExpression(self, ctx): return self.visitChildren(ctx)
    def visitFunctionExpression(self, ctx): return None # 简化