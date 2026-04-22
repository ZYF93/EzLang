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
        self.loop_stack = []
        
        # 定义内置类型
        self.i32 = ir.IntType(32)
        self.i64 = ir.IntType(64)
        self.i1 = ir.IntType(1)
        self.i8 = ir.IntType(8)
        self.void = ir.VoidType()
        
        self.type_map = {
            "I8": self.i8,
            "I32": self.i32,
            "I64": self.i64,
            "U8": self.i8,
            "U32": self.i32,
            "U64": self.i64,
            "F32": ir.FloatType(),
            "F64": ir.DoubleType(),
            "Str": ir.PointerType(self.i8),
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
        # 创建一个全局初始化函数作为顶层代码的容器
        func_type = ir.FunctionType(self.void, [])
        self.current_func = ir.Function(self.module, func_type, name="__ezlang_init")
        block = self.current_func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)
        
        self.visitChildren(ctx)
        
        if not self.builder.block.is_terminated:
            self.builder.ret_void()
        return None

    # --- Memory Management (Promotion Logic) ---

    def _should_promote(self, val):
        """检测一个值是否应该被提升（即是否是一个指向 Arena 的指针）"""
        if val is None: return False
        if not hasattr(val, 'type'): return False
        # 如果是结构体指针，通常是分配在 Arena 上的
        if isinstance(val.type, ir.PointerType) and isinstance(val.type.pointee, ir.LiteralStructType):
            return True
        # 未来的通用指针类型也应该包含在这里
        return False

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
        
        # --- Promotion Logic ---
        if not self._should_promote(last_val):
            # 只有当不返回指针时，才安全地重置 Arena 指针
            self.builder.store(current_saved_ptr, self.arena_ptr)
        
        return last_val

    # --- Functions ---

    def visitFunctionExpression(self, ctx: EzLangParser.FunctionExpressionContext):
        param_names = []
        param_types = []
        if ctx.parameters():
            for p in ctx.parameters().parameter():
                if p.THIS():
                    param_names.append("this")
                else:
                    param_names.append(p.ID().getText())
                param_types.append(self.visitType(p.type_()))
        
        return_type = self.i32
        if ctx.type_(): return_type = self.visitType(ctx.type_())
        
        func_type = ir.FunctionType(return_type, param_types)
        func_name = "anonymous"
        if isinstance(ctx.parentCtx, EzLangParser.FunctionDeclarationContext):
            func_name = ctx.parentCtx.ID().getText()
            
        func = ir.Function(self.module, func_type, name=func_name)
        old_builder = self.builder
        old_func = self.current_func
        block = func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)
        self.current_func = func
        
        # 函数入口保存 arena 状态
        entry_arena = self.builder.load(self.arena_ptr)
        
        self.locals.append({})
        for i, name in enumerate(param_names):
            arg = func.args[i]
            arg.name = name
            self.locals[-1][name] = arg
            
        body = ctx.getChild(ctx.getChildCount()-1)
        ret_val = self.visit(body)
        
        # 退出前提升
        if not self._should_promote(ret_val):
            self.builder.store(entry_arena, self.arena_ptr)
            
        if not self.builder.block.is_terminated:
            if ret_val and hasattr(ret_val, 'type') and not isinstance(ret_val.type, ir.VoidType):
                self.builder.ret(ret_val)
            else:
                self.builder.ret(ir.Constant(return_type, 0))
        self.locals.pop()
        self.builder = old_builder
        self.current_func = old_func
        return func

    # --- Variables & Values ---

    def visitVariableDeclaration(self, ctx: EzLangParser.VariableDeclarationContext):
        var_name = ctx.ID().getText()
        if ctx.expression():
            if ctx.type_():
                target_type = self.visitType(ctx.type_())
                self._target_type_hint = target_type
            else: target_type = None
            
            val = self.visit(ctx.expression())
            if hasattr(self, '_target_type_hint'): del self._target_type_hint
            
            if target_type is None:
                # 增强型类型推断：如果 val 是 None，默认 i32
                target_type = getattr(val, 'type', self.i32)
                
            is_static = ctx.STATIC() is not None
            if is_static:
                # Global Variable
                global_var = ir.GlobalVariable(self.module, target_type, name=var_name)
                global_var.linkage = 'internal'
                global_var.initializer = val if isinstance(val, ir.Constant) else ir.Constant(target_type, 0)
                # Store the pointer in locals
                self.locals[-1][var_name] = {"ptr": global_var, "type": target_type}
            else:
                ptr = self.builder.alloca(target_type, name=var_name)
                self.builder.store(val, ptr)
                self.locals[-1][var_name] = {"ptr": ptr, "type": target_type}
        return None

    def visitPrimaryExpression(self, ctx: EzLangParser.PrimaryExpressionContext):
        if ctx.ID():
            name = ctx.ID().getText()
            for scope in reversed(self.locals):
                if name in scope:
                    var_info = scope[name]
                    # Check if var_info is a dict with ptr (our new format)
                    if isinstance(var_info, dict) and "ptr" in var_info:
                        ptr = var_info["ptr"]
                        self._last_ptr = ptr
                        return self.builder.load(ptr)
                    # For function args which might just be values
                    self._last_ptr = None
                    return var_info
            # Not found in locals, might be global or unresolved
            self._last_ptr = None
            return name
        if ctx.literal(): return self.visit(ctx.literal())
        if ctx.LPAREN(): return self.visit(ctx.expression())
        if ctx.structLiteral(): return self.visit(ctx.structLiteral())
        if ctx.block(): return self.visit(ctx.block()) # 显式支持 block 表达式返回值
        return self.visitChildren(ctx)

    # --- The rest remain unchanged (operators, control flow, etc.) ---

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
        if body:
            for i in range(body.getChildCount()):
                child = body.getChild(i)
                if isinstance(child, EzLangParser.BaseStructContext):
                    base_name = child.ID().getText()
                    if base_name in self.struct_types:
                        base_st = self.struct_types[base_name]
                        # Assume literal struct type has elements we can extract
                        base_elements = base_st["ir_type"].elements
                        # To preserve order we sort the fields by index
                        sorted_fields = sorted(base_st["fields"].items(), key=lambda x: x[1])
                        for f_name, f_idx in sorted_fields:
                            fields[f_name] = idx
                            field_types.append(base_elements[f_idx])
                            idx += 1
                elif isinstance(child, EzLangParser.FieldContext):
                    field_name = child.ID().getText()
                    field_type = self.visitType(child.type_())
                    fields[field_name] = idx
                    field_types.append(field_type)
                    idx += 1
        struct_type = ir.LiteralStructType(field_types)
        self.struct_types[name] = {"fields": fields, "ir_type": struct_type}
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
                    if isinstance(base, ir.Function): base = self.builder.call(base, args)
                    elif current_struct_name:
                        st_info = self.struct_types[current_struct_name]
                        size = ir.Constant(self.i32, 64)
                        addr_int = self.builder.call(self.alloc_func, [size])
                        base = self.builder.inttoptr(addr_int, ir.PointerType(st_info["ir_type"]))
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
                            self._last_ptr = ptr
                            base = self.builder.load(ptr)
        return base

    def visitAssignmentExpression(self, ctx: EzLangParser.AssignmentExpressionContext):
        if ctx.assignmentOp():
            self._last_ptr = None
            self.visit(ctx.pipelineExpression())
            target_ptr = getattr(self, '_last_ptr', None)
            val = self.visit(ctx.assignmentExpression())
            if target_ptr: self.builder.store(val, target_ptr)
            else:
                target_name = ctx.pipelineExpression().getText()
                self.locals[-1][target_name] = val
            return val
        return self.visit(ctx.pipelineExpression())

    def visitLiteral(self, ctx: EzLangParser.LiteralContext):
        has_hint = hasattr(self, '_target_type_hint')
        target_type = getattr(self, '_target_type_hint', self.i32)
        if ctx.INT():
            val = int(ctx.INT().getText(), 0)
            return ir.Constant(target_type, val)
        if ctx.FLOAT():
            val = float(ctx.FLOAT().getText())
            if not has_hint:
                target_type = ir.DoubleType()
            return ir.Constant(target_type, val)
        if ctx.STRING():
            # For strings we just create a global constant for now
            string_val = ctx.STRING().getText().strip('"')
            str_const = ir.Constant(ir.ArrayType(self.i8, len(string_val) + 1), bytearray(string_val + '\0', 'utf8'))
            global_str = ir.GlobalVariable(self.module, str_const.type, name=f"str_{id(ctx)}")
            global_str.linkage = 'internal'
            global_str.initializer = str_const
            return self.builder.bitcast(global_str, ir.PointerType(self.i8))
        if ctx.TRUE(): return ir.Constant(self.i1, 1)
        if ctx.FALSE(): return ir.Constant(self.i1, 0)
        return ir.Constant(target_type, 0)

    def visitExpressionStatement(self, ctx: EzLangParser.ExpressionStatementContext):
        if ctx.expression(): return self.visit(ctx.expression())
        return self.visitChildren(ctx)

    def visitConditionalStatement(self, ctx: EzLangParser.ConditionalStatementContext):
        return self._handle_conditional(ctx)
        
    def visitConditionalExpression(self, ctx: EzLangParser.ConditionalExpressionContext):
        return self._handle_conditional(ctx)
        
    def _handle_conditional(self, ctx):
        cond_ctx = ctx.logicalOrExpression() if hasattr(ctx, 'logicalOrExpression') else ctx.expression(0)
        cond = self.visit(cond_ctx)
        
        if not hasattr(ctx, 'QMARK') or ctx.QMARK() is None:
            return cond
            
        then_block = self.builder.function.append_basic_block(name="if.then")
        exit_block = self.builder.function.append_basic_block(name="if.exit")
        
        has_colon = False
        if hasattr(ctx, 'COLON') and ctx.COLON(): has_colon = True
        
        if has_colon:
            else_block = self.builder.function.append_basic_block(name="if.else")
            self.builder.cbranch(cond, then_block, else_block)
            
            self.builder.position_at_end(then_block)
            then_val = self._visit_branch_body(ctx, 1)
            if not self.builder.block.is_terminated: self.builder.branch(exit_block)
            last_then_block = self.builder.block
            
            self.builder.position_at_end(else_block)
            else_val = self._visit_branch_body(ctx, 2)
            if not self.builder.block.is_terminated: self.builder.branch(exit_block)
            last_else_block = self.builder.block
            
            self.builder.position_at_end(exit_block)
            
            # If both branches return a value of the same type, we can build a phi node
            if then_val is not None and else_val is not None and hasattr(then_val, 'type') and hasattr(else_val, 'type') and then_val.type == else_val.type:
                phi = self.builder.phi(then_val.type)
                phi.add_incoming(then_val, last_then_block)
                phi.add_incoming(else_val, last_else_block)
                return phi
        else:
            self.builder.cbranch(cond, then_block, exit_block)
            self.builder.position_at_end(then_block)
            self._visit_branch_body(ctx, 1)
            if not self.builder.block.is_terminated: self.builder.branch(exit_block)
            self.builder.position_at_end(exit_block)
            
        return None

    def visitFunctionDeclaration(self, ctx: EzLangParser.FunctionDeclarationContext):
        return self.visit(ctx.functionExpression())

    def _ensure_value(self, val):
        if val is None or isinstance(val, str): return ir.Constant(self.i32, 0)
        return val

    def visitLoopStatement(self, ctx: EzLangParser.LoopStatementContext):
        loop_cond = self.builder.function.append_basic_block(name="loop.cond")
        loop_body = self.builder.function.append_basic_block(name="loop.body")
        loop_exit = self.builder.function.append_basic_block(name="loop.exit")
        
        self.loop_stack.append((loop_cond, loop_exit))
        
        if ctx.infiniteLoop():
            self.builder.branch(loop_body)
            self.builder.position_at_end(loop_body)
            self.visit(ctx.infiniteLoop().block())
            if not self.builder.block.is_terminated:
                self.builder.branch(loop_cond)
            self.builder.position_at_end(loop_cond)
            self.builder.branch(loop_body)
        elif ctx.rangeLoop():
            rl = ctx.rangeLoop()
            var_name = rl.ID().getText()
            start_val = self._ensure_value(self.visit(rl.expression(0)))
            end_val = self._ensure_value(self.visit(rl.expression(1)))
            
            ptr = self.builder.alloca(self.i32, name=var_name)
            self.builder.store(start_val, ptr)
            
            self.locals.append({})
            self.locals[-1][var_name] = {"ptr": ptr, "type": self.i32}
            
            self.builder.branch(loop_cond)
            self.builder.position_at_end(loop_cond)
            current_val = self.builder.load(ptr)
            cond = self.builder.icmp_signed('<', current_val, end_val)
            self.builder.cbranch(cond, loop_body, loop_exit)
            
            self.builder.position_at_end(loop_body)
            self.visit(rl.block())
            
            if not self.builder.block.is_terminated:
                next_val = self.builder.add(self.builder.load(ptr), ir.Constant(self.i32, 1))
                self.builder.store(next_val, ptr)
                self.builder.branch(loop_cond)
                
            self.locals.pop()
            
        self.loop_stack.pop()
        self.builder.position_at_end(loop_exit)
        return None

    def visitBreakStatement(self, ctx: EzLangParser.BreakStatementContext):
        if self.loop_stack:
            _, loop_exit = self.loop_stack[-1]
            self.builder.branch(loop_exit)
        return None

    def visitContinueStatement(self, ctx: EzLangParser.ContinueStatementContext):
        if self.loop_stack:
            loop_cond, _ = self.loop_stack[-1]
            self.builder.branch(loop_cond)
        return None

    def visitControlFlowOnly(self, ctx: EzLangParser.ControlFlowOnlyContext):
        if ctx.BREAK():
            if self.loop_stack:
                _, loop_exit = self.loop_stack[-1]
                self.builder.branch(loop_exit)
        elif ctx.CONTINUE():
            if self.loop_stack:
                loop_cond, _ = self.loop_stack[-1]
                self.builder.branch(loop_cond)
        elif ctx.throwExpression():
            self.visit(ctx.throwExpression())
        return None

    def visitMatchStatement(self, ctx: EzLangParser.MatchStatementContext):
        exit_block = self.builder.function.append_basic_block(name="match.exit")
        
        for i, case_ctx in enumerate(ctx.matchCase()):
            cond_val = self._ensure_value(self.visit(case_ctx.expression(0)))
            case_block = self.builder.function.append_basic_block(name=f"match.case{i}")
            next_block = self.builder.function.append_basic_block(name=f"match.next{i}")
            
            self.builder.cbranch(cond_val, case_block, next_block)
            
            self.builder.position_at_end(case_block)
            body = case_ctx.getChild(4)
            self.visit(body)
            if not self.builder.block.is_terminated:
                self.builder.branch(exit_block)
                
            self.builder.position_at_end(next_block)
            
        self.builder.branch(exit_block)
        self.builder.position_at_end(exit_block)
        return None

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

    def visitEqualityExpression(self, ctx: EzLangParser.EqualityExpressionContext):
        results = [self._ensure_value(self.visit(r)) for r in ctx.relationalExpression()]
        if len(results) == 1: return results[0]
        res = results[0]
        for i in range(1, len(results)):
            op = ctx.getChild(i*2-1).getText()
            pred = '==' if op == '==' else '!='
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
            phi = self.builder.phi(self.i1, name="and.phi")
            phi.add_incoming(ir.Constant(self.i1, 0), current_block)
            phi.add_incoming(right_val, last_right_block)
            left_val = phi
        return left_val

    def visitStatement(self, ctx): return self.visitChildren(ctx)
    def visitPipelineExpression(self, ctx): return self.visitChildren(ctx)
    def visitShiftExpression(self, ctx): return self.visit(ctx.additiveExpression(0))
    def visitUnaryExpression(self, ctx): return self.visitChildren(ctx)
    def _visit_branch_body(self, ctx, branch_idx):
        found = 0
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if i < 2: continue
            if child.getText() in ['?', ':']: continue
            found += 1
            if found == branch_idx: return self.visit(child)
        return None