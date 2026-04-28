"""
EzLang LLVM IR 生成器 (Codegen)。
将 AST 转换为 LLVM IR 指令。
"""

from __future__ import annotations

import llvmlite.ir as ir
from typing import Optional, Union

from compiler.ast_nodes import (
    Program, StmtNode, ExprNode,
    LetDecl, ConstDecl, StaticDecl, DeclareStmt,
    IntLiteral, FloatLiteral, StringLiteral, BoolLiteral,
    Identifier, BinaryExpr, UnaryExpr, AssignExpr, ConditionalExpr,
    BlockStmt, ReturnStmt, ExprStmt, LoopExpr, BreakStmt, ContinueStmt,
    MatchExpr, MatchArm, LambdaExpr, CallExpr,
    StructDef, MemberAccess, DictLiteral,
    NamedType, VecType, TypeNode, VecLiteral, FunctionType,
)
from compiler.context import CompileContext
from compiler.errors import ErrorCollector


class CodeGenerator:
    """
    AST 到 LLVM IR 的转换器。
    """

    def __init__(self, context: CompileContext, collector: ErrorCollector):
        self.ctx = context
        self.collector = collector
        self.builder: Optional[ir.IRBuilder] = None
        
        # 存储当前函数的返回值 alloca (用于 return 语句)
        self._current_return_alloca = None
        self._current_return_block = None
        
        # 循环控制栈 (break_block, continue_block)
        self._loop_stack: list[tuple[ir.Block, ir.Block]] = []

    def generate(self, program: Program) -> str:
        """
        生成整个程序的 LLVM IR。
        """
        # 我们先扫描一遍所有的全局定义 (如 LambdaExpr 赋值给 const/let)
        # 阶段二简化：只处理顶层 ConstDecl/LetDecl 指向 LambdaExpr 的情况作为函数定义。
        
        # 为了让其他顶层语句能运行，我们依然创建一个 main 函数
        main_func = self.ctx.create_function(
            name="main",
            ret_type=self.ctx.types.i32,
            param_types=[]
        )
        main_builder = self.ctx.create_entry_block(main_func)
        self.builder = main_builder
        
        for stmt in program.statements:
            self.visit_stmt(stmt)
            
        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(self.ctx.types.i32, 0))
        
        return self.ctx.dump_ir()

    # ======================== 语句访问 ========================

    def visit_stmt(self, node: StmtNode):
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit_stmt)
        return visitor(node)

    def generic_visit_stmt(self, node: StmtNode):
        self.collector.error(
            f"Codegen: 尚未实现语句类型 {type(node).__name__}",
            line=node.span.start_line,
            column=node.span.start_col
        )

    def visit_LetDecl(self, node: LetDecl):
        # 检查是否是函数定义 (顶层)
        if isinstance(node.value, LambdaExpr) and self.builder.function.name == "main":
            # 这是一个顶层函数定义 (已经在 visit_LambdaExpr 中定义了)
            self.visit_LambdaExpr(node.value, name=node.name)
            return

        # 1. 确定类型
        llvm_type = self._resolve_type(node.type) if node.type else None
        
        # 2. 计算初始值
        val = self.visit_expr(node.value, expected_type=llvm_type)
        if val is None:
            return
            
        if llvm_type is None:
            llvm_type = val.type
        elif val.type != llvm_type:
            # 简单的位宽转换
            if isinstance(llvm_type, ir.IntType) and isinstance(val.type, ir.IntType):
                if llvm_type.width > val.type.width:
                    val = self.builder.sext(val, llvm_type)
                elif llvm_type.width < val.type.width:
                    val = self.builder.trunc(val, llvm_type)
            elif isinstance(llvm_type, ir.FloatType) and isinstance(val.type, ir.FloatType):
                # float extension/truncation
                pass # TODO
            
        # 3. 分配内存 (alloca)
        ptr = self.builder.alloca(llvm_type, name=node.name)
        
        # 4. 存储初始值
        self.builder.store(val, ptr)
        
        # 5. 注册到符号表
        self.ctx.define(node.name, ptr)

    def visit_ConstDecl(self, node: ConstDecl):
        # 检查是否是函数定义 (顶层)
        if isinstance(node.value, LambdaExpr) and self.builder.function.name == "main":
            self.visit_LambdaExpr(node.value, name=node.name)
            return

        self.visit_LetDecl(LetDecl(
            name=node.name, type=node.type, value=node.value, span=node.span
        ))

    def visit_StaticDecl(self, node: StaticDecl):
        llvm_type = self._resolve_type(node.type) if node.type else None
        val = self.visit_expr(node.value, expected_type=llvm_type)
        
        if not isinstance(val, ir.Constant):
            self.collector.error("Static 变量初始值必须是常量表达式", 
                                 line=node.span.start_line, column=node.span.start_col)
            return

        if llvm_type is None:
            llvm_type = val.type

        global_var = ir.GlobalVariable(self.ctx.module, llvm_type, name=node.name)
        global_var.initializer = val
        global_var.linkage = 'internal'
        self.ctx.define(node.name, global_var)

    def visit_DeclareStmt(self, node: DeclareStmt):
        # 外部声明: declare const name: Type
        llvm_type = self._resolve_type(node.type)
        if llvm_type is None:
            return

        if isinstance(llvm_type, ir.FunctionType):
            # 声明外部函数
            func = ir.Function(self.ctx.module, llvm_type, name=node.name)
            # 设置参数名以支持命名参数调用
            if isinstance(node.type, FunctionType):
                for i, p in enumerate(node.type.params):
                    func.args[i].name = p.name
            self.ctx.define(node.name, func)
        else:
            # 声明外部变量
            ext_var = ir.GlobalVariable(self.ctx.module, llvm_type, name=node.name)
            ext_var.linkage = 'external'
            self.ctx.define(node.name, ext_var)

    def visit_ExprStmt(self, node: ExprStmt) -> Optional[ir.Value]:
        return self.visit_expr(node.expr)

    def visit_BlockStmt(self, node: BlockStmt) -> Optional[ir.Value]:
        self.ctx.push_scope()
        last_val = None
        for stmt in node.statements:
            last_val = self.visit_stmt(stmt)
        self.ctx.pop_scope()
        return last_val

    def visit_ReturnStmt(self, node: ReturnStmt):
        if node.value:
            val = self.visit_expr(node.value)
            self.builder.ret(val)
        else:
            self.builder.ret_void()

    def visit_LambdaExpr(self, node: LambdaExpr, name: Optional[str] = None) -> ir.Function:
        param_types = [self._resolve_type(p.type) for p in node.params]
        ret_type = self._resolve_type(node.return_type) if node.return_type else self.ctx.types.i32
        
        func_name = name or "lambda"
        func = self.ctx.create_function(func_name, ret_type, param_types)
        
        if name:
            self.ctx.define(name, func)
            
        old_builder = self.builder
        self.builder = self.ctx.create_entry_block(func)
        self.ctx.push_scope()
        
        for i, p in enumerate(node.params):
            arg = func.args[i]
            arg.name = p.name
            ptr = self.builder.alloca(arg.type, name=p.name)
            self.builder.store(arg, ptr)
            self.ctx.define(p.name, ptr)
            
        if isinstance(node.body, BlockStmt):
            self.visit_BlockStmt(node.body)
        else:
            val = self.visit_expr(node.body)
            if val and not self.builder.block.is_terminated:
                self.builder.ret(val)
        
        if not self.builder.block.is_terminated:
            if ret_type == self.ctx.types.void:
                self.builder.ret_void()
            else:
                self.builder.ret(ir.Constant(ret_type, 0))
                
        self.ctx.pop_scope()
        self.builder = old_builder
        return func

    def visit_StructDef(self, node: StructDef):
        # 1. 创建命名的结构体类型
        struct_type = self.ctx.module.context.get_identified_type(node.name)
        
        # 2. 注册到类型系统
        self.ctx.types.define_type(node.name, struct_type)
        
        # 3. 确定字段类型与默认值
        field_types = []
        field_names = []
        default_values = {}
        
        for f in node.fields:
            if f.is_spread:
                # 字段展开 ...Point
                # 阶段二简化：只支持展开已定义的结构体
                base_name = f.type.name if hasattr(f.type, "name") else ""
                base_info = getattr(self.ctx, "struct_fields", {}).get(base_name)
                if base_info:
                    base_type = base_info["type"]
                    # 将 base 的字段加入当前结构体
                    for bname, bidx in base_info["fields"].items():
                        field_names.append(bname)
                        field_types.append(base_type.elements[bidx])
                        if bname in base_info["defaults"]:
                             default_values[bname] = base_info["defaults"][bname]
                continue
                
            ftype = self._resolve_type(f.type)
            field_types.append(ftype if ftype else self.ctx.types.i32)
            field_names.append(f.name)
            if f.default:
                default_values[f.name] = f.default
            
        struct_type.set_body(*field_types)
        
        # 记录字段索引与默认值
        if not hasattr(self.ctx, "struct_fields"):
            self.ctx.struct_fields = {}
        self.ctx.struct_fields[node.name] = {
            "type": struct_type,
            "fields": {name: i for i, name in enumerate(field_names)},
            "defaults": default_values
        }

    def visit_CallExpr(self, node: CallExpr) -> Optional[ir.Value]:
        if not isinstance(node.callee, Identifier):
            self.collector.error("目前仅支持直接函数调用", 
                                 line=node.span.start_line, column=node.span.start_col)
            return None
            
        # 检查是否是结构体构造函数
        struct_info = getattr(self.ctx, "struct_fields", {}).get(node.callee.name)
        if struct_info:
            struct_type = struct_info["type"]
            fields_map = struct_info["fields"]
            defaults_map = struct_info["defaults"]
            
            ptr = self.builder.alloca(struct_type, name=f"tmp_{node.callee.name}")
            
            # 1. 填充默认值
            for fname, fidx in fields_map.items():
                field_ptr = self.builder.gep(ptr, [
                    ir.Constant(self.ctx.types.i32, 0), 
                    ir.Constant(self.ctx.types.i32, fidx)
                ])
                if fname in defaults_map:
                    val = self.visit_expr(defaults_map[fname])
                    self.builder.store(val, field_ptr)
                else:
                    self.builder.store(ir.Constant(struct_type.elements[fidx], ir.Undefined), field_ptr)
            
            # 2. 覆盖传入参数
            for arg_node in node.args:
                if arg_node.name in fields_map:
                    idx = fields_map[arg_node.name]
                    field_ptr = self.builder.gep(ptr, [
                        ir.Constant(self.ctx.types.i32, 0), 
                        ir.Constant(self.ctx.types.i32, idx)
                    ])
                    val = self.visit_expr(arg_node.value)
                    self.builder.store(val, field_ptr)
                    
            return self.builder.load(ptr)

        func = self.ctx.lookup(node.callee.name)
        if not isinstance(func, ir.Function):
            self.collector.error(f"{node.callee.name} 不是可调用的函数", 
                                 line=node.span.start_line, column=node.span.start_col)
            return None
            
        # 匹配参数
        param_names = [arg.name for arg in func.args]
        final_args = [None] * len(param_names)
        
        for i, arg_node in enumerate(node.args):
            if arg_node.name:
                if arg_node.name in param_names:
                    idx = param_names.index(arg_node.name)
                    final_args[idx] = self.visit_expr(arg_node.value)
                else:
                    self.collector.error(f"函数 {node.callee.name} 没有名为 {arg_node.name} 的参数",
                                         line=arg_node.span.start_line)
            else:
                if i < len(final_args):
                    final_args[i] = self.visit_expr(arg_node.value)
        
        # 填充缺失参数
        for i in range(len(final_args)):
            if final_args[i] is None:
                final_args[i] = ir.Constant(func.args[i].type, ir.Undefined)
            
        return self.builder.call(func, final_args)

    def visit_MemberAccess(self, node: MemberAccess) -> Optional[ir.Value]:
        obj = self.visit_expr(node.object)
        if obj is None: return None
        
        # 阶段二简化：假定 obj 是一个 IdentifiedStructType 的 load 结果
        # 获取结构体名字，LLVM 的 name 可能带有前缀 %"..."
        struct_type = obj.type
        if not isinstance(struct_type, ir.IdentifiedStructType):
             self.collector.error(f"类型 {struct_type} 不支持成员访问", line=node.span.start_line)
             return None
             
        struct_name = struct_type.name.strip('"')
        struct_info = getattr(self.ctx, "struct_fields", {}).get(struct_name)
        
        if struct_info and node.member in struct_info["fields"]:
            idx = struct_info["fields"][node.member]
            # LLVM 不能直接 GEP 值，需要一个地址
            temp_ptr = self.builder.alloca(obj.type)
            self.builder.store(obj, temp_ptr)
            field_ptr = self.builder.gep(temp_ptr, [
                ir.Constant(self.ctx.types.i32, 0),
                ir.Constant(self.ctx.types.i32, idx)
            ])
            return self.builder.load(field_ptr)
            
        self.collector.error(f"无法访问成员 {node.member}", line=node.span.start_line)
        return None

    def visit_DictLiteral(self, node: DictLiteral) -> ir.Value:
        field_values = []
        for entry in node.entries:
            val = self.visit_expr(entry.value)
            field_values.append(val)
            
        field_types = [v.type for v in field_values]
        struct_type = ir.LiteralStructType(field_types)
        
        ptr = self.builder.alloca(struct_type)
        for i, val in enumerate(field_values):
            field_ptr = self.builder.gep(ptr, [
                ir.Constant(self.ctx.types.i32, 0),
                ir.Constant(self.ctx.types.i32, i)
            ])
            self.builder.store(val, field_ptr)
            
        return self.builder.load(ptr)

    # ======================== 表达式访问 ========================

    def visit_expr(self, node: ExprNode, expected_type: Optional[ir.Type] = None) -> Optional[ir.Value]:
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit_expr)
        if method_name in ["visit_IntLiteral", "visit_FloatLiteral", "visit_VecLiteral"]:
            return visitor(node, expected_type)
        return visitor(node)

    def generic_visit_expr(self, node: ExprNode):
        self.collector.error(
            f"Codegen: 尚未实现表达式类型 {type(node).__name__}",
            line=node.span.start_line,
            column=node.span.start_col
        )
        return None

    def visit_IntLiteral(self, node: IntLiteral, expected_type: Optional[ir.Type] = None) -> ir.Value:
        target_type = expected_type if isinstance(expected_type, ir.IntType) else self.ctx.types.i32
        return ir.Constant(target_type, node.value)

    def visit_FloatLiteral(self, node: FloatLiteral, expected_type: Optional[ir.Type] = None) -> ir.Value:
        target_type = expected_type if isinstance(expected_type, (ir.FloatType, ir.DoubleType)) else self.ctx.types.f64
        return ir.Constant(target_type, node.value)

    def visit_BoolLiteral(self, node: BoolLiteral) -> ir.Value:
        return ir.Constant(self.ctx.types.bool, 1 if node.value else 0)

    def visit_StringLiteral(self, node: StringLiteral) -> ir.Value:
        const_str = ir.Constant(ir.ArrayType(self.ctx.types.i8, len(node.value) + 1),
                                bytearray(node.value.encode("utf-8") + b'\0'))
        global_str = ir.GlobalVariable(self.ctx.module, const_str.type, name=".str")
        global_str.initializer = const_str
        global_str.linkage = 'internal'
        global_str.global_constant = True
        
        ptr = self.builder.bitcast(global_str, self.ctx.types.ptr_i8)
        
        struct_val = self.builder.alloca(self.ctx.types.str_type)
        len_ptr = self.builder.gep(struct_val, [ir.Constant(self.ctx.types.i32, 0), ir.Constant(self.ctx.types.i32, 0)])
        data_ptr = self.builder.gep(struct_val, [ir.Constant(self.ctx.types.i32, 0), ir.Constant(self.ctx.types.i32, 1)])
        
        self.builder.store(ir.Constant(self.ctx.types.i64, len(node.value)), len_ptr)
        self.builder.store(ptr, data_ptr)
        
        return self.builder.load(struct_val)

    def visit_Identifier(self, node: Identifier) -> Optional[ir.Value]:
        ptr = self.ctx.lookup(node.name)
        if ptr is None:
            self.collector.error(f"未定义的变量: {node.name}", 
                                 line=node.span.start_line, column=node.span.start_col)
            return None
        
        return self.builder.load(ptr, name=node.name)

    def visit_ConditionalExpr(self, node: ConditionalExpr) -> Optional[ir.Value]:
        condition = self.visit_expr(node.condition)
        if condition is None:
            return None
            
        # 确保 condition 是 i1
        if condition.type != self.ctx.types.bool:
            condition = self.builder.icmp_signed('!=', condition, ir.Constant(condition.type, 0))
            
        func = self.builder.function
        then_block = func.append_basic_block(name="then")
        else_block = func.append_basic_block(name="else")
        merge_block = func.append_basic_block(name="merge")
        
        self.builder.cbranch(condition, then_block, else_block)
        
        # Then 分支
        self.builder.position_at_end(then_block)
        then_val = None
        if isinstance(node.then_expr, BlockStmt):
            self.visit_BlockStmt(node.then_expr)
        else:
            then_val = self.visit_expr(node.then_expr)
            
        if not self.builder.block.is_terminated:
            self.builder.branch(merge_block)
        then_block = self.builder.block # 记录实际结束的块
        
        # Else 分支
        self.builder.position_at_end(else_block)
        else_val = None
        if node.else_expr:
            if isinstance(node.else_expr, BlockStmt):
                self.visit_BlockStmt(node.else_expr)
            elif isinstance(node.else_expr, (ExprNode, ConditionalExpr)):
                else_val = self.visit_expr(node.else_expr)
        
        if not self.builder.block.is_terminated:
            self.builder.branch(merge_block)
        else_block = self.builder.block
        
        # Merge 分支
        self.builder.position_at_end(merge_block)
        
        # 如果都有值且类型一致，构造 phi
        if then_val is not None and else_val is not None and then_val.type == else_val.type:
            phi = self.builder.phi(then_val.type, name="phi")
            phi.add_incoming(then_val, then_block)
            phi.add_incoming(else_val, else_block)
            return phi
            
        return None

    def visit_AssignExpr(self, node: AssignExpr) -> Optional[ir.Value]:
        if not isinstance(node.target, Identifier):
            self.collector.error("赋值目标必须是标识符 (当前简化版)", 
                                 line=node.span.start_line, column=node.span.start_col)
            return None
            
        ptr = self.ctx.lookup(node.target.name)
        if ptr is None:
            self.collector.error(f"未定义的变量: {node.target.name}", 
                                 line=node.span.start_line, column=node.target.name)
            return None
            
        new_val = self.visit_expr(node.value)
        if new_val is None:
            return None
            
        if node.op == '=':
            self.builder.store(new_val, ptr)
            return new_val
        else:
            # 复合赋值: +=, -=, *= 等
            current_val = self.builder.load(ptr)
            # 提取操作符 (+ from +=)
            base_op = node.op[:-1]
            
            # 使用 BinaryExpr 的逻辑 (通过创建一个临时的 BinaryExpr 节点来重用逻辑，
            # 或者直接在这里写。为了简单，我们直接在这里根据 base_op 调用方法。)
            
            # 这里我们重用 BinaryExpr 的逻辑部分
            is_int = isinstance(current_val.type, ir.IntType)
            is_float = isinstance(current_val.type, (ir.FloatType, ir.DoubleType))
            
            res = None
            if is_int:
                if base_op == '+': res = self.builder.add(current_val, new_val)
                if base_op == '-': res = self.builder.sub(current_val, new_val)
                if base_op == '*': res = self.builder.mul(current_val, new_val)
                if base_op == '/': res = self.builder.sdiv(current_val, new_val)
                if base_op == '%': res = self.builder.srem(current_val, new_val)
                if base_op == '<<': res = self.builder.shl(current_val, new_val)
                if base_op == '>>': res = self.builder.ashr(current_val, new_val)
                if base_op == '&': res = self.builder.and_(current_val, new_val)
                if base_op == '|': res = self.builder.or_(current_val, new_val)
                if base_op == '^': res = self.builder.xor(current_val, new_val)
            elif is_float:
                if base_op == '+': res = self.builder.fadd(current_val, new_val)
                if base_op == '-': res = self.builder.fsub(current_val, new_val)
                if base_op == '*': res = self.builder.fmul(current_val, new_val)
                if base_op == '/': res = self.builder.fdiv(current_val, new_val)
                if base_op == '%': res = self.builder.frem(current_val, new_val)
                
            if res:
                self.builder.store(res, ptr)
                return res
            else:
                self.collector.error(f"不支持的复合运算符 {node.op}", 
                                     line=node.span.start_line, column=node.span.start_col)
                return None

    def visit_BinaryExpr(self, node: BinaryExpr) -> Optional[ir.Value]:
        lhs = self.visit_expr(node.left)
        rhs = self.visit_expr(node.right)
        
        if lhs is None or rhs is None:
            return None
            
        # 简单的类型提升与广播
        if lhs.type != rhs.type:
            if isinstance(lhs.type, ir.VectorType) and not isinstance(rhs.type, ir.VectorType):
                rhs = self._broadcast(rhs, lhs.type)
            elif not isinstance(lhs.type, ir.VectorType) and isinstance(rhs.type, ir.VectorType):
                lhs = self._broadcast(lhs, rhs.type)
            else:
                # TODO: 实现更复杂的类型提升
                pass

        op = node.op
        is_float = isinstance(lhs.type, (ir.FloatType, ir.DoubleType))
        is_int = isinstance(lhs.type, ir.IntType)
        is_vec = isinstance(lhs.type, ir.VectorType)
        
        if is_int:
            if op == '+': return self.builder.add(lhs, rhs)
            if op == '-': return self.builder.sub(lhs, rhs)
            if op == '*': return self.builder.mul(lhs, rhs)
            if op == '/': return self.builder.sdiv(lhs, rhs)
            if op == '%': return self.builder.srem(lhs, rhs)
            if op == '<<': return self.builder.shl(lhs, rhs)
            if op == '>>': return self.builder.ashr(lhs, rhs)
            if op == '&': return self.builder.and_(lhs, rhs)
            if op == '|': return self.builder.or_(lhs, rhs)
            if op == '^': return self.builder.xor(lhs, rhs)
            if op == '==': return self.builder.icmp_signed('==', lhs, rhs)
            if op == '!=': return self.builder.icmp_signed('!=', lhs, rhs)
            if op == '<':  return self.builder.icmp_signed('<', lhs, rhs)
            if op == '<=': return self.builder.icmp_signed('<=', lhs, rhs)
            if op == '>':  return self.builder.icmp_signed('>', lhs, rhs)
            if op == '>=': return self.builder.icmp_signed('>=', lhs, rhs)
            if op == '&&': return self.builder.and_(lhs, rhs)
            if op == '||': return self.builder.or_(lhs, rhs)
        elif is_float:
            if op == '+': return self.builder.fadd(lhs, rhs)
            if op == '-': return self.builder.fsub(lhs, rhs)
            if op == '*': return self.builder.fmul(lhs, rhs)
            if op == '/': return self.builder.fdiv(lhs, rhs)
            if op == '%': return self.builder.frem(lhs, rhs)
            if op == '==': return self.builder.fcmp_ordered('==', lhs, rhs)
            if op == '!=': return self.builder.fcmp_ordered('!=', lhs, rhs)
            if op == '<':  return self.builder.fcmp_ordered('<', lhs, rhs)
            if op == '<=': return self.builder.fcmp_ordered('<=', lhs, rhs)
            if op == '>':  return self.builder.fcmp_ordered('>', lhs, rhs)
            if op == '>=': return self.builder.fcmp_ordered('>=', lhs, rhs)
        elif is_vec:
            # 向量运算
            if op == '+': return self.builder.add(lhs, rhs)
            if op == '-': return self.builder.sub(lhs, rhs)
            if op == '*': return self.builder.mul(lhs, rhs)
            if op == '/':
                if isinstance(lhs.type.element, ir.IntType):
                    return self.builder.sdiv(lhs, rhs)
                return self.builder.fdiv(lhs, rhs)
            
        self.collector.error(f"不支持的运算符 {op} 用于类型 {lhs.type}", 
                             line=node.span.start_line, column=node.span.start_col)
        return None

    def _broadcast(self, scalar: ir.Value, vector_type: ir.VectorType) -> ir.Value:
        """将标量广播为向量。"""
        # 简单的类型转换 (TODO: 增强类型转换逻辑)
        if scalar.type != vector_type.element:
            if isinstance(vector_type.element, ir.IntType) and isinstance(scalar.type, ir.IntType):
                if vector_type.element.width > scalar.type.width:
                    scalar = self.builder.sext(scalar, vector_type.element)
                else:
                    scalar = self.builder.trunc(scalar, vector_type.element)
            elif isinstance(vector_type.element, (ir.FloatType, ir.DoubleType)) and isinstance(scalar.type, (ir.FloatType, ir.DoubleType)):
                # TODO: float extension/truncation
                pass

        res = ir.Constant(vector_type, ir.Undefined)
        for i in range(vector_type.count):
            res = self.builder.insert_element(res, scalar, ir.Constant(self.ctx.types.i32, i))
        return res

    def visit_UnaryExpr(self, node: UnaryExpr) -> Optional[ir.Value]:
        val = self.visit_expr(node.operand)
        if val is None:
            return None
            
        op = node.op
        if op == '-':
            if isinstance(val.type, ir.IntType):
                return self.builder.neg(val)
            if isinstance(val.type, (ir.FloatType, ir.DoubleType)):
                return self.builder.fneg(val)
        if op == '!':
            if isinstance(val.type, ir.IntType) and val.type.width == 1:
                return self.builder.not_(val)
                
        self.collector.error(f"不支持的一元运算符 {op} 用于类型 {val.type}", 
                             line=node.span.start_line, column=node.span.start_col)
        return None

    def visit_VecLiteral(self, node: VecLiteral, expected_type: Optional[ir.Type] = None) -> Optional[ir.Value]:
        # Vec[1, 2, 3, 4]
        if not node.elements:
            return None
            
        elements = [self.visit_expr(e) for e in node.elements]
        if any(e is None for e in elements):
            return None
            
        # 构造 LLVM 向量
        vec_type = ir.VectorType(elements[0].type, len(elements))
        
        # 使用 insert_element 构造
        res = ir.Constant(vec_type, ir.Undefined)
        for i, val in enumerate(elements):
            res = self.builder.insert_element(res, val, ir.Constant(self.ctx.types.i32, i))
            
        return res

    def visit_LoopExpr(self, node: LoopExpr) -> Optional[ir.Value]:
        func = self.builder.function
        
        if node.var:
            # Range loop: loop i in start...end { ... }
            start_val = self.visit_expr(node.start)
            end_val = self.visit_expr(node.end)
            
            # 1. 初始化循环变量
            ptr = self.builder.alloca(start_val.type, name=node.var)
            self.builder.store(start_val, ptr)
            
            cond_block = func.append_basic_block(name="loop_cond")
            body_block = func.append_basic_block(name="loop_body")
            inc_block = func.append_basic_block(name="loop_inc")
            exit_block = func.append_basic_block(name="loop_exit")
            
            self.builder.branch(cond_block)
            
            # 2. 条件检查
            self.builder.position_at_end(cond_block)
            curr_i = self.builder.load(ptr)
            cond = self.builder.icmp_signed('<', curr_i, end_val)
            self.builder.cbranch(cond, body_block, exit_block)
            
            # 3. 循环体
            self.builder.position_at_end(body_block)
            self._loop_stack.append((exit_block, inc_block))
            self.ctx.push_scope()
            self.ctx.define(node.var, ptr)
            self.visit_BlockStmt(node.body)
            self.ctx.pop_scope()
            self._loop_stack.pop()
            self.builder.branch(inc_block)
            
            # 4. 增量
            self.builder.position_at_end(inc_block)
            next_i = self.builder.add(curr_i, ir.Constant(curr_i.type, 1))
            self.builder.store(next_i, ptr)
            self.builder.branch(cond_block)
            
            self.builder.position_at_end(exit_block)
        else:
            # Infinite loop: loop { ... }
            loop_block = func.append_basic_block(name="loop")
            exit_block = func.append_basic_block(name="loop_exit")
            
            self.builder.branch(loop_block)
            self.builder.position_at_end(loop_block)
            
            self._loop_stack.append((exit_block, loop_block))
            self.visit_BlockStmt(node.body)
            self._loop_stack.pop()
            
            # 只有当块内没有终结符时才跳转
            if not self.builder.block.is_terminated:
                self.builder.branch(loop_block)
                
            self.builder.position_at_end(exit_block)
            
        return None

    def visit_BreakStmt(self, node: BreakStmt):
        if not self._loop_stack:
            self.collector.error("break 只能在循环或 match 中使用", 
                                 line=node.span.start_line, column=node.span.start_col)
            return
        break_block, _ = self._loop_stack[-1]
        self.builder.branch(break_block)

    def visit_ContinueStmt(self, node: ContinueStmt):
        if not self._loop_stack:
            self.collector.error("continue 只能在循环或 match 中使用", 
                                 line=node.span.start_line, column=node.span.start_col)
            return
        _, continue_block = self._loop_stack[-1]
        self.builder.branch(continue_block)

    def visit_MatchExpr(self, node: MatchExpr) -> Optional[ir.Value]:
        func = self.builder.function
        exit_block = func.append_basic_block(name="match_exit")
        
        for i, arm in enumerate(node.arms):
            next_arm_entry = func.append_basic_block(name=f"arm_{i+1}_cond") if i < len(node.arms) - 1 else exit_block
            
            cond = self.visit_expr(arm.condition)
            if cond.type != self.ctx.types.bool:
                 cond = self.builder.icmp_signed('!=', cond, ir.Constant(cond.type, 0))
            
            this_arm_body = func.append_basic_block(name=f"arm_{i}_body")
            self.builder.cbranch(cond, this_arm_body, next_arm_entry)
            
            self.builder.position_at_end(this_arm_body)
            
            # 支持 break/continue (针对 match 语义)
            self._loop_stack.append((exit_block, next_arm_entry))
            
            if isinstance(arm.body, BlockStmt):
                self.visit_BlockStmt(arm.body)
            else:
                self.visit_expr(arm.body)
                
            self._loop_stack.pop()
            
            if not self.builder.block.is_terminated:
                self.builder.branch(exit_block)
                
            self.builder.position_at_end(next_arm_entry)
            
        return None

    # ======================== 类型解析 ========================

    def _resolve_type(self, node: TypeNode) -> Optional[ir.Type]:
        if isinstance(node, NamedType):
            return self.ctx.types.resolve(node.name)
        if isinstance(node, VecType):
            elem = self._resolve_type(node.element)
            if elem:
                return ir.VectorType(elem, node.count)
        if isinstance(node, FunctionType):
            params = [self._resolve_type(p.type) for p in node.params]
            ret = self._resolve_type(node.return_type)
            return ir.FunctionType(ret, params)
        # TODO: 其他类型
        return None
