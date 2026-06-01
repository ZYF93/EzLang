"""EzLang LLVM IR 代码生成器"""

from typing import Optional
from pathlib import Path
import re
from llvmlite import ir
from parser.EzLangParser import EzLangParser
from parser.EzLangVisitor import EzLangVisitor


class LLVMCodeGenerator(EzLangVisitor):
    """LLVM IR 代码生成访问器"""

    def __init__(self, module_name: str = "ezlang", compile_target: Optional[str] = None):
        self.module = ir.Module(name=module_name)
        self.compile_target = compile_target
        self.builder: ir.IRBuilder = None
        self.current_function: ir.Function = None
        self._method_this: ir.Value = None
        self.locals: dict[str, ir.AllocaInstr] = {}
        self.globals: dict[str, ir.GlobalVariable] = {}
        self.loop_exit_blocks: list[ir.Block] = []
        self.loop_continue_blocks: list[ir.Block] = []
        self.catch_exit_blocks: list[ir.Block] = []
        self.catch_error_allocas: list[ir.AllocaInstr] = []
        self.structs: dict[str, ir.IdentifiedStructType] = {}
        self.struct_fields: dict[str, list[str]] = {}
        self.struct_defaults: dict[str, dict[str, any]] = {}  # struct_name → {field_name: expression_ctx}
        self.struct_methods: dict[str, dict[str, str]] = {}
        self.type_aliases: dict[str, ir.Type] = {}
        self.func_defaults: dict[str, dict[str, ir.Value]] = {}
        self.func_param_names: dict[str, list[str]] = {}
        self.generic_templates: dict[str, tuple] = {}
        self._monomorphized: set[str] = set()
        self.extern_libs: list[tuple[str, Optional[str]]] = []  # (lib_path, target)
        self.active_extern_libs: list[str] = []
        self._extern_diagnostics: list[str] = []
        self._declare_names: list[str] = []
        self._non_extern_decls_seen = 0
        self._compiler_builtin_declares = {'copy', 'set', 'allocRaw'}
        self._unimplemented_collection_declares = {
            'listPush', 'listPop', 'listShift', 'listUnshift', 'listSort',
            'listFilter', 'listMap', 'listFind', 'listLen', 'listSlice',
            'dictKeys', 'dictValues', 'dictHas', 'dictDelete', 'dictLen',
        }
        self._emcc_js_libs: list[str] = []
        self._emcc_binding_counter = 0
        self._supported_extern_exts = {".a", ".lib", ".so", ".dylib", ".dll", ".o", ".ll", ".bc", ".framework", ".js", ".c"}
        self._str_counter: int = 0  # 字符串全局变量唯一 ID
        self._type_width_cache: dict[str, int] = {}
        self._zero_constant_cache: dict[str, ir.Constant] = {}
        self._flow_depth = 0
        self._declare_builtins()

    def _declare_builtins(self):
        """声明 LLVM 内建函数和内置结构体类型"""
        i8_ptr = ir.PointerType(ir.IntType(8))
        void = ir.VoidType()
        i64 = ir.IntType(64)
        i1 = ir.IntType(1)
        i32 = ir.IntType(32)

        # llvm.memcpy
        func_type = ir.FunctionType(void, [i8_ptr, i8_ptr, i64, i1])
        ir.Function(self.module, func_type, 'llvm.memcpy.p0.p0.i64')

        # Arena 内存管理
        self._declare_arena()

        flow_hook_type = ir.FunctionType(void, [])
        self._flow_enter = ir.Function(self.module, flow_hook_type, '__ezrt_flow_enter')
        self._flow_exit = ir.Function(self.module, flow_hook_type, '__ezrt_flow_exit')
        self._flow_sleep = ir.Function(self.module, ir.FunctionType(void, [i64]), '__ezrt_sleep')
        self._flow_race = ir.Function(self.module, ir.FunctionType(i32, [i32, i32]), '__ezrt_race')

        # 内置结构体: Error = { i32 code, i8* message }
        err_type = ir.global_context.get_identified_type('Error')
        if err_type.is_opaque:
            err_type.set_body(i32, i8_ptr)
        self.structs['Error'] = err_type
        self.struct_fields['Error'] = ['code', 'message']

        # 内置结构体: Date = { i64 timestamp }
        date_type = ir.global_context.get_identified_type('Date')
        if date_type.is_opaque:
            date_type.set_body(i64)
        self.structs['Date'] = date_type
        self.struct_fields['Date'] = ['timestamp']

        # 内置结构体: Blob = { i8* data, i64 size }
        blob_type = ir.global_context.get_identified_type('Blob')
        if blob_type.is_opaque:
            blob_type.set_body(i8_ptr, i64)
        self.structs['Blob'] = blob_type
        self.struct_fields['Blob'] = ['data', 'size']

        # 内置结构体: Dict = { i8*** key_pages, i8*** value_pages, i32 count, i32 capacity, i32 page_count }
        dict_type = ir.global_context.get_identified_type('Dict')
        if dict_type.is_opaque:
            dict_page_table = ir.PointerType(ir.PointerType(i8_ptr))
            dict_type.set_body(
                dict_page_table,            # key_pages
                dict_page_table,            # value_pages
                i32,                        # count
                i32,                        # capacity
                i32                         # page_count
            )
        self.structs['Dict'] = dict_type
        self.struct_fields['Dict'] = ['key_pages', 'value_pages', 'count', 'capacity', 'page_count']

    def _declare_arena(self):
        """声明 Arena 内存管理基础设施：缓冲区 + 游标 + 分配函数"""
        i8 = ir.IntType(8)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)

        # Arena 缓冲区（1MB）
        arena_size = 1048576
        buf_type = ir.ArrayType(i8, arena_size)
        arena_buf = ir.GlobalVariable(self.module, buf_type, '__arena_buffer')
        arena_buf.initializer = ir.Constant(buf_type, ir.Undefined)
        arena_buf.linkage = 'internal'

        # Arena 游标（当前分配位置）
        arena_cursor = ir.GlobalVariable(self.module, i64, '__arena_cursor')
        arena_cursor.initializer = ir.Constant(i64, 0)
        arena_cursor.linkage = 'internal'

        # __arena_alloc(size: i64, align: i64) -> i8*
        func_type = ir.FunctionType(i8_ptr, [i64, i64])
        arena_alloc = ir.Function(self.module, func_type, '__arena_alloc')
        entry = arena_alloc.append_basic_block('entry')
        builder = ir.IRBuilder(entry)
        size = arena_alloc.args[0]
        align = arena_alloc.args[1]

        # 加载当前游标
        cursor = builder.load(arena_cursor, name='cursor')
        # 对齐: aligned = (cursor + align - 1) & ~(align - 1)
        align_minus_1 = builder.sub(align, ir.Constant(i64, 1))
        misaligned = builder.add(cursor, align_minus_1)
        mask = builder.xor(align_minus_1, ir.Constant(i64, -1))
        aligned = builder.and_(misaligned, mask)
        # 新游标位置
        next_pos = builder.add(aligned, size)
        builder.store(next_pos, arena_cursor)
        # 返回缓冲区中偏移后的指针
        buf_ptr = builder.bitcast(arena_buf, i8_ptr)
        result = builder.gep(buf_ptr, [aligned], name='arena_ptr')
        builder.ret(result)

        # 保存/恢复游标函数（作用域管理用）
        save_type = ir.FunctionType(i64, [])
        save_fn = ir.Function(self.module, save_type, '__arena_save')
        save_entry = save_fn.append_basic_block('entry')
        save_builder = ir.IRBuilder(save_entry)
        saved = save_builder.load(arena_cursor)
        save_builder.ret(saved)

        restore_type = ir.FunctionType(ir.VoidType(), [i64])
        restore_fn = ir.Function(self.module, restore_type, '__arena_restore')
        restore_entry = restore_fn.append_basic_block('entry')
        restore_builder = ir.IRBuilder(restore_entry)
        restore_builder.store(restore_fn.args[0], arena_cursor)
        restore_builder.ret_void()

        # 存储引用供其他方法使用
        self._arena_buffer = arena_buf
        self._arena_cursor = arena_cursor
        self._arena_alloc = arena_alloc
        self._arena_save = save_fn
        self._arena_restore = restore_fn

    @staticmethod
    def _is_aggregate_ptr(val: ir.Value) -> bool:
        """检查值是否为聚合类型（结构体/数组）的指针，需要 load 后才能 store"""
        if isinstance(val, ir.AllocaInstr):
            return isinstance(val.type.pointee, (ir.LiteralStructType, ir.IdentifiedStructType, ir.ArrayType))
        if isinstance(val.type, ir.PointerType):
            return isinstance(val.type.pointee, (ir.LiteralStructType, ir.IdentifiedStructType, ir.ArrayType))
        return False

    def _load_if_aggregate_ptr(self, val: ir.Value) -> ir.Value:
        """如果 val 是聚合类型的指针，load 它；否则原样返回"""
        if self._is_aggregate_ptr(val) and self.builder is not None:
            return self.builder.load(val)
        return val

    def _arena_allocate(self, llvm_type: ir.Type, name: str = "") -> ir.Value:
        """在 Arena 中分配内存，返回指向分配区域的指针"""
        if not hasattr(self, '_arena_alloc') or self.builder is None:
            return self.builder.alloca(llvm_type, name=name) if self.builder else None

        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(ir.IntType(8))

        # 计算类型大小和对齐
        size_val = ir.Constant(i64, max(self._type_width(llvm_type), 1))
        align_val = ir.Constant(i64, 8)

        # 调用 __arena_alloc(size, align)
        raw_ptr = self.builder.call(self._arena_alloc, [size_val, align_val])
        typed_ptr = self.builder.bitcast(raw_ptr, ir.PointerType(llvm_type), name=name)
        return typed_ptr

    # ==================== 类型映射 ====================

    def _map_type(self, ctx) -> ir.Type:
        """EzLang 类型 → LLVM 类型 (默认为 i32)"""
        if ctx is None:
            return ir.IntType(32)

        P = EzLangParser

        # 可选类型: T? → {i1, T}
        if isinstance(ctx, P.OptionalTypeContext):
            inner = self._map_type(ctx.type_())
            return ir.LiteralStructType([ir.IntType(1), inner])

        # 联合类型: T1 | T2 → {i32, [max_type]}
        if isinstance(ctx, P.UnionTypeContext):
            types = [self._map_type(t) for t in ctx.type_()]
            max_type = max(types, key=lambda t: self._type_width(t))
            return ir.LiteralStructType([ir.IntType(32), max_type])

        # 数组类型: T[] → { data, length, capacity }
        if isinstance(ctx, P.ArrayTypeContext):
            inner = self._map_type(ctx.type_())
            return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])

        # List 类型: List<T> → { data, length, capacity }
        if isinstance(ctx, P.ListTypeContext):
            inner = self._map_type(ctx.type_())
            return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])

        # 括号类型: (T)
        if isinstance(ctx, P.ParenTypeContext):
            return self._map_type(ctx.type_())

        # SIMD 向量类型: Vec<T>[N] → <N x T>
        if isinstance(ctx, P.VecTypeContext):
            inner = self._map_type(ctx.type_())
            count = int(ctx.INTEGER_LITERAL().getText())
            return ir.VectorType(inner, count)

        # 函数类型: (T1, T2) => Ret → 函数指针
        if isinstance(ctx, P.FunctionTypeRefContext):
            fn_ctx = ctx.functionType()
            ret_type = self._map_type(fn_ctx.type_())
            param_types = []
            ptl = fn_ctx.paramTypeList()
            if ptl is not None:
                for p in ptl.paramType():
                    param_types.append(self._map_type(p.type_()))
            func_type = ir.FunctionType(ret_type, param_types)
            return ir.PointerType(func_type)

        # 泛型函数类型: <T> => Ret（无参数）
        if isinstance(ctx, P.GenericFunctionTypeContext):
            ret_type = self._map_type(ctx.type_())
            func_type = ir.FunctionType(ret_type, [])
            return ir.PointerType(func_type)

        # 泛型参数函数类型: <T>(params) => Ret（带参数，用于 declare）
        if isinstance(ctx, P.GenericParamFunctionTypeContext):
            ret_type = self._map_type(ctx.type_())
            param_types = []
            ptl = ctx.paramTypeList()
            if ptl is not None:
                for p in ptl.paramType():
                    param_types.append(self._map_type(p.type_()))
            func_type = ir.FunctionType(ret_type, param_types)
            return ir.PointerType(func_type)

        # typeof 类型: typeof expr → 编译时类型查询（暂返回 i32）
        if isinstance(ctx, P.TypeofTypeContext):
            return ir.IntType(32)

        # 基础类型
        if hasattr(ctx, 'baseType'):
            bt = ctx.baseType()
            if bt is not None:
                return self._map_base_type(bt)

        return ir.IntType(32)

    def _map_base_type(self, bt) -> ir.Type:
        """基础类型映射"""
        if bt.I8() is not None: return ir.IntType(8)
        if bt.I32() is not None: return ir.IntType(32)
        if bt.I64() is not None: return ir.IntType(64)
        if bt.U8() is not None: return ir.IntType(8)
        if bt.U32() is not None: return ir.IntType(32)
        if bt.U64() is not None: return ir.IntType(64)
        if bt.F32() is not None: return ir.FloatType()
        if bt.F64() is not None: return ir.DoubleType()
        if bt.STR() is not None: return ir.PointerType(ir.IntType(8))
        if bt.BOOL() is not None: return ir.IntType(1)
        if bt.VOID() is not None: return ir.VoidType()
        if bt.TYPE_IDENTIFIER() is not None:
            name = bt.TYPE_IDENTIFIER().getText()
            if name == 'List' and bt.genericArgs() is not None:
                args = list(bt.genericArgs().type_())
                inner = self._map_type(args[0]) if args else ir.IntType(32)
                return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])
            if name == 'Meta' and bt.genericArgs() is not None:
                args = list(bt.genericArgs().type_())
                inner = self._map_type(args[0]) if args else ir.IntType(32)
                return self._get_meta_type(inner)
            if name == 'Dict':
                return self.structs['Dict']
            if name in self.type_aliases:
                return self.type_aliases[name]
            if name in self.structs:
                return self.structs[name]
            return ir.IntType(32)
        return ir.IntType(32)

    def _get_meta_type(self, value_type: ir.Type) -> ir.IdentifiedStructType:
        type_name = str(value_type).replace('%"', '').replace('"', '').replace('*', 'ptr').replace(' ', '_')
        meta_name = f"Meta_{type_name}"
        meta_type = ir.global_context.get_identified_type(meta_name)
        if meta_type.is_opaque:
            i8_ptr = ir.PointerType(ir.IntType(8))
            func_ptr = ir.PointerType(ir.FunctionType(value_type, [ir.PointerType(meta_type)]))
            setter_ptr = ir.PointerType(ir.FunctionType(ir.VoidType(), [ir.PointerType(meta_type), value_type]))
            meta_type.set_body(value_type, func_ptr, setter_ptr, i8_ptr, i8_ptr)
        self.structs[meta_name] = meta_type
        self.struct_fields[meta_name] = ['value', 'getter', 'setter', 'type', 'name']
        return meta_type

    def _emit_emcc_js_binding(self, symbol_name: str, lib_path: str):
        text = f"{lib_path}:{symbol_name}\0"
        data = bytearray(text, 'utf-8')
        arr_type = ir.ArrayType(ir.IntType(8), len(data))
        binding = ir.GlobalVariable(self.module, arr_type, f"__emcc_js_binding_{self._emcc_binding_counter}")
        self._emcc_binding_counter += 1
        binding.initializer = ir.Constant(arr_type, data)
        binding.global_constant = True
        binding.linkage = 'internal'
        return binding

    def _decorate_global(self, name: str, value: ir.Constant, decorator_name: str):
        meta_type = self._get_meta_type(value.type)
        gv = ir.GlobalVariable(self.module, meta_type, name)
        gv.initializer = ir.Constant(meta_type, [
            value,
            self._zero_constant(meta_type.elements[1]),
            self._zero_constant(meta_type.elements[2]),
            self._make_global_string(str(value.type), prefix="_meta_type"),
            self._make_global_string(name, prefix="_meta_name"),
        ])
        self.globals[name] = gv
        decorator = self.module.globals.get(decorator_name)
        if isinstance(decorator, ir.Function):
            init_name = f"__decorator_init_{name}"
            init_type = ir.FunctionType(ir.VoidType(), [])
            init_fn = ir.Function(self.module, init_type, init_name)
            block = init_fn.append_basic_block('entry')
            builder = ir.IRBuilder(block)
            meta_value = builder.load(gv)
            builder.call(decorator, [meta_value])
            builder.ret_void()
        return gv

    def _type_width(self, t: ir.Type) -> int:
        """获取 LLVM 类型的目标字节宽度（近似），并缓存递归结果。"""
        key = str(t)
        cached = self._type_width_cache.get(key)
        if cached is not None:
            return cached
        if isinstance(t, ir.IntType):
            width = max(t.width // 8, 1)
        elif isinstance(t, ir.FloatType):
            width = 4
        elif isinstance(t, ir.DoubleType):
            width = 8
        elif isinstance(t, ir.PointerType):
            width = 8
        elif isinstance(t, ir.ArrayType):
            width = t.count * self._type_width(t.element)
        elif isinstance(t, ir.VectorType):
            width = t.count * self._type_width(t.element)
        elif isinstance(t, (ir.LiteralStructType, ir.IdentifiedStructType)):
            width = max(sum(self._type_width(e) for e in t.elements), 1)
        else:
            width = 4
        self._type_width_cache[key] = width
        return width

    def _zero_constant(self, t: ir.Type) -> ir.Constant:
        """为任意 LLVM 类型生成零值常量，并缓存纯常量构造。"""
        key = str(t)
        cached = self._zero_constant_cache.get(key)
        if cached is not None:
            return cached
        if isinstance(t, ir.IntType):
            value = ir.Constant(t, 0)
        elif isinstance(t, ir.FloatType):
            value = ir.Constant(t, 0.0)
        elif isinstance(t, ir.DoubleType):
            value = ir.Constant(t, 0.0)
        elif isinstance(t, ir.PointerType):
            value = ir.Constant(t, None)
        elif isinstance(t, ir.ArrayType):
            elem = self._zero_constant(t.element)
            value = ir.Constant(t, [elem] * t.count)
        elif isinstance(t, ir.VectorType):
            elem = self._zero_constant(t.element)
            value = ir.Constant(t, [elem] * t.count)
        elif isinstance(t, (ir.LiteralStructType, ir.IdentifiedStructType)):
            fields = [self._zero_constant(e) for e in t.elements]
            value = ir.Constant(t, fields)
        elif isinstance(t, ir.VoidType):
            value = ir.Constant(t, None)
        else:
            value = ir.Constant(t, 0)
        self._zero_constant_cache[key] = value
        return value

    def _coerce_value(self, val: ir.Value, target_type: ir.Type) -> ir.Value:
        """值类型自动适配：可选类型/联合类型自动包装"""
        if val.type == target_type:
            return val
        if self._is_aggregate_ptr(val) and val.type.pointee == target_type:
            return self.builder.load(val)
        if isinstance(val.type, ir.IntType) and isinstance(target_type, ir.IntType):
            if val.type.width < target_type.width:
                return self.builder.zext(val, target_type)
            if val.type.width > target_type.width:
                return self.builder.trunc(val, target_type)
        if isinstance(val.type, ir.FloatType) and isinstance(target_type, ir.DoubleType):
            return self.builder.fpext(val, target_type)
        if isinstance(val.type, ir.DoubleType) and isinstance(target_type, ir.FloatType):
            return self.builder.fptrunc(val, target_type)
        if isinstance(target_type, ir.PointerType) and isinstance(target_type.pointee, (ir.LiteralStructType, ir.IdentifiedStructType)):
            coerced = self._coerce_value(val, target_type.pointee)
            if coerced.type == target_type.pointee:
                ptr = self.builder.alloca(target_type.pointee)
                self.builder.store(coerced, ptr)
                return ptr
        # 数组/List 分页结构: 空数组字面量可适配到声明的元素类型。
        if (
            isinstance(val.type, ir.LiteralStructType)
            and isinstance(target_type, ir.LiteralStructType)
            and len(val.type.elements) == 4
            and len(target_type.elements) == 4
        ):
            result = ir.Constant(target_type, ir.Undefined)
            for idx, target_elem in enumerate(target_type.elements):
                field = self.builder.extract_value(val, idx)
                if field.type != target_elem:
                    if isinstance(field.type, ir.PointerType) and isinstance(target_elem, ir.PointerType):
                        field = self.builder.bitcast(field, target_elem)
                    else:
                        field = self._coerce_value(field, target_elem)
                result = self.builder.insert_value(result, field, idx)
            return result
        # 可选类型包装: T → {i1, T}
        if isinstance(target_type, ir.LiteralStructType):
            if len(target_type.elements) == 2 and target_type.elements[0] == ir.IntType(1):
                inner_type = target_type.elements[1]
                if self._is_aggregate_ptr(val) and val.type.pointee == inner_type:
                    val = self.builder.load(val)
                if inner_type == val.type:
                    undef = ir.Constant(target_type, ir.Undefined)
                    v = self.builder.insert_value(undef, ir.Constant(ir.IntType(1), 1), 0)
                    return self.builder.insert_value(v, val, 1)
            # 联合类型包装: T → {i32, T_max}
            if len(target_type.elements) == 2 and isinstance(target_type.elements[0], ir.IntType) and target_type.elements[0].width == 32:
                undef = ir.Constant(target_type, ir.Undefined)
                v = self.builder.insert_value(undef, ir.Constant(ir.IntType(32), 0), 0)
                variant_type = target_type.elements[1]
                # 值类型与联合体槽位类型不一致时，尝试转换
                if val.type != variant_type:
                    if isinstance(val.type, ir.IntType) and isinstance(variant_type, ir.IntType):
                        val = self.builder.zext(val, variant_type)
                    elif isinstance(val.type, ir.IntType) and isinstance(variant_type, ir.PointerType):
                        val = self.builder.inttoptr(val, variant_type)
                    elif isinstance(val.type, ir.PointerType) and isinstance(variant_type, ir.IntType):
                        val = self.builder.ptrtoint(val, variant_type)
                    else:
                        return val  # 无法转换，保持原样，之后可能会报错
                return self.builder.insert_value(v, val, 1)
        return val

    # ==================== 辅助 ====================

    def visitChildren(self, ctx):
        """重写：根据 Context 类型自动分发到对应的 visit 方法"""
        ctx_name = type(ctx).__name__
        if ctx_name.endswith("Context"):
            rule_name = ctx_name[:-7]  # 去掉 "Context" 后缀
            method_name = "visit" + rule_name
            # 仅当子类重写了该方法时才分发（避免调用基类默认实现导致递归）
            if method_name in type(self).__dict__:
                method = getattr(self, method_name)
                return method(ctx)
        # 回退到默认行为：遍历子节点
        return self._visit_children(ctx)

    def _visit_children(self, ctx):
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if hasattr(child, 'accept'):
                child.accept(self)
        return None

    # ==================== 编译入口 ====================

    def visitCompilationUnit(self, ctx: EzLangParser.CompilationUnitContext):
        top_level_work = []
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if not hasattr(child, 'accept') or child.getChildCount() == 0:
                continue
            if self._is_top_level_runtime_statement(child):
                top_level_work.append(child)
            else:
                child_text = child.getText() if hasattr(child, 'getText') else ''
                child.accept(self)
                if 'std/mem.ez' in child_text:
                    for builtin_name in self._compiler_builtin_declares:
                        if builtin_name in self.module.globals:
                            del self.module.globals[builtin_name]
                var_decl = self._top_level_variable_decl(child)
                if (
                    var_decl is not None
                    and var_decl.expression() is not None
                    and not var_decl.decorator()
                ):
                    top_level_work.append(child)

        if top_level_work:
            self._gen_entrypoint(top_level_work)

        if not self.active_extern_libs and self._non_extern_decls_seen == 0:
            for name in self._declare_names:
                self._extern_diagnostics.append(f"declare 符号 '{name}' 没有关联 extern 库")
        return self.module

    def _is_top_level_runtime_statement(self, ctx) -> bool:
        """顶层非声明语句由内部宿主入口承载，声明仍保持模块全局符号。"""
        if isinstance(ctx, EzLangParser.StatementContext):
            return ctx.declaration() is None
        return False

    def _top_level_variable_decl(self, ctx):
        if isinstance(ctx, EzLangParser.StatementContext):
            decl = ctx.declaration()
            return decl.variableDecl() if decl is not None else None
        if isinstance(ctx, EzLangParser.DeclarationContext):
            return ctx.variableDecl()
        return None

    def _gen_entrypoint(self, statements):
        """生成宿主 main；EzLang 用户源码不需要显式入口函数。"""
        if 'main' in self.module.globals:
            return
        func_type = ir.FunctionType(ir.IntType(32), [])
        func = ir.Function(self.module, func_type, 'main')
        entry = func.append_basic_block('entry')

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}

        for stmt in statements:
            var_decl = self._top_level_variable_decl(stmt)
            if var_decl is not None:
                self._init_global_variable(var_decl)
            else:
                self._eval(stmt)
            if self.builder.block.is_terminated:
                break

        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(ir.IntType(32), 0))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        return func

    def _init_global_variable(self, ctx: EzLangParser.VariableDeclContext):
        name = ctx.VAR_IDENTIFIER().getText()
        initializer = ctx.expression()
        if initializer is None or name not in self.globals:
            return None
        gv = self.globals[name]
        val = self._eval_expr(initializer)
        if val is None:
            return None
        if self._is_aggregate_ptr(val):
            val = self.builder.load(val)
        val = self._coerce_value(val, gv.type.pointee)
        if val.type != gv.type.pointee:
            return None
        self.builder.store(val, gv)
        return None

    def _infer_global_initializer_type(self, initializer) -> ir.Type:
        text = initializer.getText()
        if text.startswith('"'):
            return ir.PointerType(ir.IntType(8))
        if text.startswith('{'):
            return self.structs['Dict']
        if text in {'true', 'false'}:
            return ir.IntType(1)
        if re.fullmatch(r'[-+]?\d+', text):
            return ir.IntType(32)
        if re.fullmatch(r'[-+]?\d+\.\d+(?:[eE][-+]?\d+)?', text):
            return ir.DoubleType()

        call_name = self._expr_call_name(initializer)
        generic_args = self._expr_call_generic_args(initializer)
        if call_name is not None and generic_args:
            call_name = self._monomorphize(call_name, generic_args)
        if call_name is not None and call_name in self.module.globals:
            callee = self.module.globals[call_name]
            func_type = callee.type.pointee if isinstance(callee.type, ir.PointerType) else None
            if isinstance(func_type, ir.FunctionType):
                return func_type.return_type

        struct_name = self._expr_struct_literal_name(initializer)
        if struct_name is not None and struct_name in self.structs:
            return self.structs[struct_name]

        return ir.IntType(32)

    def _expr_call_name(self, ctx) -> str | None:
        if isinstance(ctx, EzLangParser.CallContext):
            return self._leftmost_identifier_name(ctx.postfixExpression())
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._expr_call_name(ctx.getChild(i))
                if result is not None:
                    return result
        return None

    def _leftmost_identifier_name(self, ctx) -> str | None:
        if isinstance(ctx, EzLangParser.IdentifierExprContext):
            token = ctx.VAR_IDENTIFIER() or ctx.TYPE_IDENTIFIER()
            return token.getText() if token is not None else None
        if hasattr(ctx, 'postfixExpression') and ctx.postfixExpression() is not None:
            return self._leftmost_identifier_name(ctx.postfixExpression())
        if hasattr(ctx, 'primaryExpression') and ctx.primaryExpression() is not None:
            return self._leftmost_identifier_name(ctx.primaryExpression())
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._leftmost_identifier_name(ctx.getChild(i))
                if result is not None:
                    return result
        return None

    def _expr_call_generic_args(self, ctx) -> list[ir.Type]:
        if isinstance(ctx, EzLangParser.CallContext):
            ident = self._leftmost_identifier_ctx(ctx.postfixExpression())
            if ident is not None and ident.genericArgs() is not None:
                return [self._map_type(t) for t in ident.genericArgs().type_()]
            return []
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._expr_call_generic_args(ctx.getChild(i))
                if result:
                    return result
        return []

    def _leftmost_identifier_ctx(self, ctx):
        if isinstance(ctx, EzLangParser.IdentifierExprContext):
            return ctx
        if hasattr(ctx, 'postfixExpression') and ctx.postfixExpression() is not None:
            return self._leftmost_identifier_ctx(ctx.postfixExpression())
        if hasattr(ctx, 'primaryExpression') and ctx.primaryExpression() is not None:
            return self._leftmost_identifier_ctx(ctx.primaryExpression())
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._leftmost_identifier_ctx(ctx.getChild(i))
                if result is not None:
                    return result
        return None

    def _expr_struct_literal_name(self, ctx) -> str | None:
        if isinstance(ctx, EzLangParser.StructLiteralExprContext):
            return ctx.structLiteral().TYPE_IDENTIFIER().getText()
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._expr_struct_literal_name(ctx.getChild(i))
                if result is not None:
                    return result
        return None

    # ==================== 变量声明 ====================

    # ==================== declare / export / extern ====================

    def visitDeclareDecl(self, ctx: EzLangParser.DeclareDeclContext):
        """declare 外部函数/变量声明"""
        name = ctx.VAR_IDENTIFIER().getText()
        type_ctx = ctx.type_()

        if type_ctx is None:
            return None

        # 检查是否为泛型参数函数类型 <T>(params) => Ret
        if hasattr(type_ctx, 'typeList') and hasattr(type_ctx, 'paramTypeList') and hasattr(type_ctx, 'FAT_ARROW'):
            # type_ctx 本身就是 GenericParamFunctionTypeContext 实例
            # 从 typeList 中提取泛型参数名（通过 baseType → TYPE_IDENTIFIER）
            param_names = []
            for t in type_ctx.typeList().type_():
                bt = t.baseType() if hasattr(t, 'baseType') else None
                if bt is not None and bt.TYPE_IDENTIFIER() is not None:
                    param_names.append(bt.TYPE_IDENTIFIER().getText())
            if name in self._unimplemented_collection_declares:
                self.generic_templates[name] = (param_names, type_ctx, 'unimplemented')
            else:
                self.generic_templates[name] = (param_names, type_ctx)
            return None  # 泛型声明不生成 LLVM 函数，等到单态化时生成

        if name in self._compiler_builtin_declares:
            return None

        self._declare_names.append(name)
        if self.compile_target == 'emcc' and self._emcc_js_libs:
            self._emit_emcc_js_binding(name, self._emcc_js_libs[-1])

        # 检查是否为普通函数类型
        fn_type = type_ctx.functionType() if hasattr(type_ctx, 'functionType') else None
        if fn_type is not None:
            ret_type = self._map_type(fn_type.type_())
            param_types = []
            params = fn_type.paramTypeList()
            if params is not None:
                for p in params.paramType():
                    pt = self._map_type(p.type_())
                    if isinstance(pt, (ir.LiteralStructType, ir.IdentifiedStructType)):
                        pt = ir.PointerType(pt)
                    param_types.append(pt)
            func_type = ir.FunctionType(ret_type, param_types)
            func = ir.Function(self.module, func_type, name)
            # 记录参数名供 visitCall 使用
            param_names = []
            if params is not None:
                for p in params.paramType():
                    param_names.append(p.VAR_IDENTIFIER().getText())
            self.func_param_names[name] = param_names
            return func
        else:
            # 外部全局变量
            llvm_type = self._map_type(type_ctx)
            gv = ir.GlobalVariable(self.module, llvm_type, name)
            gv.initializer = self._zero_constant(llvm_type)
            return gv

    def visitExportDecl(self, ctx: EzLangParser.ExportDeclContext):
        """export 导出声明"""
        return self._visit_children(ctx)

    def _resolve_extern_path(self, lib_path: str) -> str:
        """解析内置标准库 extern 路径。"""
        if lib_path.startswith('@std/'):
            root = Path(__file__).resolve().parents[3]
            return str((root / 'packages' / 'std' / lib_path[len('@std/'):]).resolve())
        return lib_path

    def visitExternDecl(self, ctx: EzLangParser.ExternDeclContext):
        """extern 库引用：记录库路径和目标平台，供链接阶段使用"""
        raw_lib_path = ctx.STRING_LITERAL().getText()[1:-1]  # 去掉引号
        lib_path = self._resolve_extern_path(raw_lib_path)
        target = None
        tp_ctx = ctx.targetPlatform()
        if tp_ctx is not None:
            target = tp_ctx.getText()
        self.extern_libs.append((lib_path, target))
        suffix = Path(lib_path).suffix
        if suffix and suffix not in self._supported_extern_exts:
            self._extern_diagnostics.append(f"extern 路径格式不支持：'{raw_lib_path}'")
        if target is None or self.compile_target is None or target == self.compile_target:
            self.active_extern_libs.append(lib_path)
            if suffix == '.js' and (target == 'emcc' or self.compile_target == 'emcc'):
                self._emcc_js_libs.append(lib_path)
        return None

    def visitImportDecl(self, ctx: EzLangParser.ImportDeclContext):
        """import 模块导入：编译被导入文件，合并符号到当前模块"""
        import os as _os
        path = ctx.STRING_LITERAL().getText()[1:-1]

        # 解析路径（相对于当前源码目录 / examples/）
        base_dirs = [
            _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'examples'),
            _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'packages'),
        ]
        source = None
        for d in base_dirs:
            p = _os.path.join(d, path)
            if _os.path.exists(p):
                with open(p) as f:
                    source = f.read()
                break

        if source is None:
            return None

        # 编译导入文件到同一个模块（避免循环导入）
        if not hasattr(self, '_imported'):
            self._imported = set()
        if path in self._imported:
            return None
        self._imported.add(path)

        # 解析并访问
        from antlr4 import InputStream, CommonTokenStream
        from parser.EzLangLexer import EzLangLexer
        from parser.EzLangParser import EzLangParser as Parser

        lexer = EzLangLexer(InputStream(source))
        parser = Parser(CommonTokenStream(lexer))
        tree = parser.compilationUnit()

        # 处理导入符号重命名
        spec_list = ctx.importSpecList()
        renames = {}
        if spec_list is not None:
            for spec in spec_list.importSpec():
                def _get_import_name(name_ctx):
                    if name_ctx is None:
                        return ""
                    token = name_ctx.TYPE_IDENTIFIER() or name_ctx.VAR_IDENTIFIER()
                    return token.getText() if token else ""
                name = _get_import_name(spec.importName(0))
                alias = _get_import_name(spec.importName(1)) if spec.importName(1) else name
                renames[name] = alias

        # 访问被导入文件的 AST（符号会注册到当前模块）
        for i in range(tree.getChildCount()):
            child = tree.getChild(i)
            if hasattr(child, 'accept') and child.getChildCount() > 0:
                child.accept(self)

        # 处理重命名：为被导入符号创建别名
        for orig_name, alias in renames.items():
            if orig_name != alias and orig_name in self.module.globals:
                gv = self.module.globals[orig_name]
                if alias not in self.module.globals:
                    self.module.globals[alias] = gv

        return None

    # ==================== 变量声明 ====================

    def visitVariableDecl(self, ctx: EzLangParser.VariableDeclContext):
        self._non_extern_decls_seen += 1
        name = ctx.VAR_IDENTIFIER().getText()
        type_ctx = ctx.type_()
        initializer = ctx.expression()
        decorators = [d.VAR_IDENTIFIER().getText() for d in ctx.decorator()]

        if self.builder is None:
            # 全局变量
            if decorators and initializer is not None:
                val = self._const_from_expr(initializer)
                if val is not None:
                    self._decorate_global(name, val, decorators[-1])
                    return None
            llvm_type = self._map_type(type_ctx)
            if type_ctx is None and initializer is not None:
                llvm_type = self._infer_global_initializer_type(initializer)
            gv = ir.GlobalVariable(self.module, llvm_type, name)
            gv.initializer = self._zero_constant(llvm_type)
            self.globals[name] = gv
        else:
            # 局部变量
            if type_ctx is not None:
                llvm_type = self._map_type(type_ctx)
                alloca = self.builder.alloca(llvm_type, name=name)
                self.locals[name] = alloca
                if initializer is not None:
                    val = self._eval_expr(initializer)
                    if val is not None:
                        if self._is_aggregate_ptr(val):
                            val = self.builder.load(val)
                        val = self._coerce_value(val, llvm_type)
                        self.builder.store(val, alloca)
            elif initializer is not None:
                # 类型推断：先求值，根据结果确定类型
                val = self._eval_expr(initializer)
                if val is not None:
                    if isinstance(val, ir.AllocaInstr) or self._is_aggregate_ptr(val):
                        # 结构体字面量返回指针，直接复用
                        val.name = name
                        self.locals[name] = val
                    else:
                        alloca = self.builder.alloca(val.type, name=name)
                        self.builder.store(val, alloca)
                        self.locals[name] = alloca
            else:
                # 无类型无初值，默认 i32
                alloca = self.builder.alloca(ir.IntType(32), name=name)
                self.locals[name] = alloca

    # ==================== 类型别名 ====================

    def visitTypeAliasDecl(self, ctx: EzLangParser.TypeAliasDeclContext):
        name = ctx.TYPE_IDENTIFIER().getText()
        shape = ctx.typeShape()
        if shape is not None:
            members = list(shape.typeShapeMember())
            dynamic_members = [member for member in members if member.LBRACK() is not None]
            if dynamic_members and len(dynamic_members) == len(members):
                self.type_aliases[name] = self.structs['Dict']
                return None

            field_names = []
            alias_field_types = []
            for member in members:
                if member.VAR_IDENTIFIER() is None:
                    continue
                field_names.append(member.VAR_IDENTIFIER().getText())
                member_types = member.type_()
                member_types = member_types if isinstance(member_types, list) else [member_types]
                member_types = [t for t in member_types if t is not None]
                field_type = self._map_type(member_types[-1]) if member_types else ir.IntType(32)
                alias_field_types.append(field_type)
            alias_struct = ir.global_context.get_identified_type(name)
            if not alias_struct.elements:
                alias_struct.set_body(*alias_field_types)
            self.structs[name] = alias_struct
            self.struct_fields[name] = field_names
            self.type_aliases[name] = alias_struct
            return None

        if ctx.type_() is not None:
            self.type_aliases[name] = self._map_type(ctx.type_())
        return None

    # ==================== 结构体声明 ====================

    def visitStructDecl(self, ctx: EzLangParser.StructDeclContext):
        """注册结构体类型 → LLVM IdentifiedStructType"""
        self._non_extern_decls_seen += 1
        name = ctx.TYPE_IDENTIFIER().getText()
        struct_type = ir.global_context.get_identified_type(name)
        self.structs[name] = struct_type
        field_names = []
        field_types = []

        defaults = {}
        for member_ctx in ctx.structMember():
            # 字段
            field_ctx = member_ctx.structField()
            if field_ctx is not None:
                fname = field_ctx.VAR_IDENTIFIER().getText()
                ftype = self._map_type(field_ctx.type_())
                field_names.append(fname)
                field_types.append(ftype)
                # 收集默认值表达式（AST 上下文），实例化时求值
                if field_ctx.expression() is not None:
                    defaults[fname] = field_ctx.expression()
            # 结构体展开: ...Base → 继承 Base 的所有字段
            spread_ctx = member_ctx.structSpread()
            if spread_ctx is not None:
                base_type_ctx = spread_ctx.type_()
                if hasattr(base_type_ctx, 'baseType') and base_type_ctx.baseType() is not None:
                    base_name = base_type_ctx.baseType().TYPE_IDENTIFIER().getText()
                    if base_name in self.struct_fields:
                        for bf in self.struct_fields[base_name]:
                            if bf not in field_names:
                                field_names.append(bf)
                                base_struct = self.structs[base_name]
                                bf_idx = self.struct_fields[base_name].index(bf)
                                field_types.append(base_struct.elements[bf_idx])
            # 方法: methodName = (this: Type, ...) => body
            method_ctx = member_ctx.structMethod()
            if method_ctx is not None:
                mname = method_ctx.VAR_IDENTIFIER().getText()
                fn_lit = method_ctx.functionLiteral()
                if fn_lit is not None:
                    func_name = f"{name}_{mname}"
                    if name not in self.struct_methods:
                        self.struct_methods[name] = {}
                    self.struct_methods[name][mname] = func_name
                    self._gen_method_func(func_name, fn_lit, name)

        if not struct_type.elements:
            struct_type.set_body(*field_types)
        self.structs[name] = struct_type
        self.struct_fields[name] = field_names
        self.struct_defaults[name] = defaults
        return None

    def _gen_method_func(self, func_name: str, fn_lit_ctx, struct_name: str):
        """生成结构体方法对应的 LLVM 函数"""
        ret_type = self._map_type(fn_lit_ctx.type_())
        param_types = []
        param_names = []
        params = fn_lit_ctx.paramList()
        if params is not None:
            for p in params.param():
                param_types.append(self._map_type(p.type_()))
                param_names.append(p.VAR_IDENTIFIER().getText())

        func_type = ir.FunctionType(ret_type, param_types)
        func = ir.Function(self.module, func_type, func_name)
        for i, pn in enumerate(param_names):
            func.args[i].name = pn

        self.func_param_names[func_name] = param_names
        self.func_defaults[func_name] = {}

        # 生成函数体
        body = fn_lit_ctx.block() or fn_lit_ctx.expression()
        if body is not None:
            entry = func.append_basic_block('entry')
            prev_builder = self.builder
            prev_func = self.current_function
            prev_locals = self.locals

            self.builder = ir.IRBuilder(entry)
            self.current_function = func
            self.locals = {}

            for i, pn in enumerate(param_names):
                alloca = self.builder.alloca(param_types[i], name=pn)
                self.builder.store(func.args[i], alloca)
                self.locals[pn] = alloca

            self._eval(body)

            if not self.builder.block.is_terminated:
                if ret_type == ir.VoidType():
                    self.builder.ret_void()
                else:
                    self.builder.ret(self._zero_constant(ret_type))

            self.builder = prev_builder
            self.current_function = prev_func
            self.locals = prev_locals

    # ==================== 函数声明 ====================

    def visitFunctionDecl(self, ctx: EzLangParser.FunctionDeclContext):
        self._non_extern_decls_seen += 1
        name = ctx.VAR_IDENTIFIER().getText()
        fn_lit = ctx.functionLiteral()
        if fn_lit is None:
            return None

        # 泛型函数：存储模板，不立即生成
        # genericParams 可能被解析到 functionDecl 或 functionLiteral 上
        generic_params = ctx.genericParams()
        if generic_params is None:
            generic_params = fn_lit.genericParams()
        if generic_params is not None:
            param_names = [t.getText() for t in generic_params.TYPE_IDENTIFIER()]
            self.generic_templates[name] = (param_names, ctx)
            return None

        return self._gen_func(name, fn_lit)

    def _gen_func(self, name: str, fn_lit_ctx) -> ir.Function:
        """从函数字面量生成 LLVM 函数"""
        ret_type = self._map_type(fn_lit_ctx.type_())
        param_types = []
        params = fn_lit_ctx.paramList()
        param_names = []
        if params is not None:
            for p in params.param():
                param_types.append(self._map_type(p.type_()))
                param_names.append(p.VAR_IDENTIFIER().getText())

        func_type = ir.FunctionType(ret_type, param_types)
        func = ir.Function(self.module, func_type, name)

        for i, pn in enumerate(param_names):
            func.args[i].name = pn

        # 记录参数名和默认值（供调用时具名参数重排和默认参数注入）
        self.func_param_names[name] = param_names
        if params is not None:
            defaults = {}
            for p in params.param():
                if p.expression() is not None:
                    defaults[p.VAR_IDENTIFIER().getText()] = p.expression()
            if defaults:
                self.func_defaults[name] = defaults

        # 生成函数体
        block = func.append_basic_block(name="entry")
        old_builder = self.builder
        old_locals = self.locals
        self.builder = ir.IRBuilder(block)
        self.locals = {}

        # 参数 alloca
        for i, pn in enumerate(param_names):
            alloca = self.builder.alloca(param_types[i], name=pn)
            self.builder.store(func.args[i], alloca)
            self.locals[pn] = alloca

        # 函数体
        body = fn_lit_ctx.block() or fn_lit_ctx.expression()
        if body is not None:
            val = self._eval(body)

        if not block.is_terminated:
            if isinstance(ret_type, ir.VoidType):
                self.builder.ret_void()
            elif isinstance(val, ir.Value) and not isinstance(val.type, ir.VoidType):
                self.builder.ret(val)
            else:
                self.builder.ret_void()

        self.builder = old_builder
        self.locals = old_locals
        return func

    # ==================== 表达式求值 ====================

    def _eval(self, ctx):
        """通用求值入口"""
        if ctx is None:
            return None
        return ctx.accept(self)

    def _eval_expr(self, ctx):
        return self._eval(ctx)

    def _is_float(self, typ):
        return isinstance(typ, (ir.FloatType, ir.DoubleType))

    # ==================== 字符串插值 ====================

    @staticmethod
    def _parse_str_interp(text: str):
        """解析字符串插值: "Hello {{name}}!" → [("text", "Hello "), ("expr", "name"), ("text", "!")]"""
        import re
        parts = []
        last = 0
        for m in re.finditer(r'\{\{(.+?)\}\}', text):
            if m.start() > last:
                parts.append(("text", text[last:m.start()]))
            parts.append(("expr", m.group(1).strip()))
            last = m.end()
        if last < len(text):
            parts.append(("text", text[last:]))
        if not parts:
            parts.append(("text", text))
        return parts

    def _gen_str_interp(self, parts) -> ir.Value:
        """生成字符串插值的 LLVM IR：栈缓冲区 + memcpy 逐段拼接"""
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)

        # 分配 256 字节栈缓冲区
        buf_type = ir.ArrayType(i8, 256)
        buf = self.builder.alloca(buf_type, name="_interp_buf")
        buf_base = self.builder.gep(buf, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)

        # 获取 llvm.memcpy
        memcpy = self.module.get_global('llvm.memcpy.p0.p0.i64')

        seg_idx = 0
        pos = 0
        for seg_type, seg_content in parts:
            if seg_type == "text" and seg_content:
                # 创建临时全局字符串（唯一名称）
                data = bytearray(seg_content, 'utf-8')
                arr_type = ir.ArrayType(i8, len(data))
                gv_name = f"_interp_seg_{seg_idx}"
                gv = ir.GlobalVariable(self.module, arr_type, name=gv_name)
                gv.initializer = ir.Constant(arr_type, data)
                gv.global_constant = True
                gv.linkage = 'internal'
                src = self.builder.gep(gv, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
                seg_len = len(data)
                seg_idx += 1
            elif seg_type == "expr" and self.builder:
                # 查找变量
                var_name = seg_content.strip()
                if var_name in self.locals:
                    src_val = self.builder.load(self.locals[var_name])
                    # Str 类型为 i8*，直接使用
                    if isinstance(src_val.type, ir.PointerType) and src_val.type.pointee == i8:
                        src = src_val
                        seg_len = 64  # 简化：用固定上限
                    else:
                        continue
                else:
                    continue
            else:
                continue

            # memcpy(dst+pos, src, seg_len)
            dst_ptr = self.builder.gep(buf_base, [ir.Constant(i32, pos)], inbounds=True)
            self.builder.call(memcpy, [
                dst_ptr, src,
                ir.Constant(i64, seg_len),
                ir.Constant(ir.IntType(1), 0)
            ])
            pos += seg_len

        # 添加 null 终止符
        null_ptr = self.builder.gep(buf_base, [ir.Constant(i32, pos)], inbounds=True)
        self.builder.store(ir.Constant(i8, 0), null_ptr)

        return buf_base

    def _make_global_string(self, text: str, prefix: str = "_str") -> ir.Value:
        """创建全局字符串常量，返回 i8*"""
        data = bytearray(text + '\0', 'utf-8')
        arr_type = ir.ArrayType(ir.IntType(8), len(data))
        str_name = f"{prefix}_{self._str_counter}"
        self._str_counter += 1
        gv = ir.GlobalVariable(self.module, arr_type, name=str_name)
        gv.initializer = ir.Constant(arr_type, data)
        gv.global_constant = True
        gv.linkage = 'internal'
        if self.builder:
            return self.builder.gep(gv, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), 0)
            ], inbounds=True)
        return gv

    def _const_from_expr(self, ctx) -> Optional[ir.Constant]:
        if ctx is None:
            return None
        text = ctx.getText()
        if text == 'true' or text == 'false':
            return ir.Constant(ir.IntType(1), int(text == 'true'))
        if text.startswith('"') and text.endswith('"'):
            ptr = self._make_global_string(text[1:-1])
            if isinstance(ptr, ir.GlobalVariable):
                return ir.Constant(ir.PointerType(ir.IntType(8)), None)
            return ptr
        try:
            return ir.Constant(ir.IntType(32), int(text, 0))
        except ValueError:
            return None

    # 字面量
    def visitLiteralExpr(self, ctx: EzLangParser.LiteralExprContext):
        lit = ctx.literal()
        if lit is None:
            return ir.Constant(ir.IntType(32), 0)

        if lit.INTEGER_LITERAL() is not None:
            val_text = lit.INTEGER_LITERAL().getText()
            try:
                val = int(val_text)
            except ValueError:
                val = int(val_text, 0)
            return ir.Constant(ir.IntType(32), val)

        if lit.FLOAT_LITERAL() is not None:
            return ir.Constant(ir.DoubleType(), float(lit.FLOAT_LITERAL().getText()))

        if lit.BOOL_LITERAL() is not None:
            return ir.Constant(ir.IntType(1),
                              int(lit.BOOL_LITERAL().getText() == 'true'))

        if lit.STRING_LITERAL() is not None:
            text = lit.STRING_LITERAL().getText()[1:-1]
            # 检查字符串插值 {{expr}}
            parts = self._parse_str_interp(text)
            if len(parts) > 1 and self.builder is not None:
                # 有插值：生成运行时拼接
                return self._gen_str_interp(parts)
            # 无插值：创建全局常量字符串（唯一名称）
            return self._make_global_string(text)

        return ir.Constant(ir.IntType(32), 0)

    # 标识符引用
    def visitIdentifierExpr(self, ctx: EzLangParser.IdentifierExprContext):
        id_token = ctx.VAR_IDENTIFIER() or ctx.TYPE_IDENTIFIER()
        name = id_token.getText()

        # 泛型实例化: func<T1, T2>
        if ctx.genericArgs() is not None:
            type_args = [self._map_type(t) for t in ctx.genericArgs().type_()]
            name = self._monomorphize(name, type_args)

        if name in self.locals:
            alloca = self.locals[name]
            if isinstance(alloca.type.pointee, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
                return alloca
            return self.builder.load(alloca, name=name)
        if name in self.module.globals and isinstance(self.module.globals[name], ir.Function):
            return self.module.globals[name]
        if name in self.globals:
            gv = self.globals[name]
            if isinstance(gv.type.pointee, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
                return gv
            return self.builder.load(gv, name=name)
        return ir.Constant(ir.IntType(32), 0)

    def _monomorphize(self, base_name: str, type_args: list[ir.Type]) -> str:
        """为泛型函数生成特定类型的单态化版本"""
        suffix = '_'.join(self._type_name(t) for t in type_args)
        mono_name = f"{base_name}_{suffix}"
        if mono_name in self._monomorphized:
            return mono_name

        if base_name not in self.generic_templates:
            return base_name

        self._monomorphized.add(mono_name)
        template = self.generic_templates[base_name]
        param_names, template_ctx = template[0], template[1]
        if len(template) > 2 and template[2] == 'unimplemented':
            self._extern_diagnostics.append(
                f"标准库集合函数 '{base_name}' 尚未实现，不能生成外部符号 '{mono_name}'"
            )
            return mono_name

        # 创建类型替换映射
        type_map = dict(zip(param_names, type_args))

        # 判断是否为泛型 declare（GenericParamFunctionTypeContext）
        if hasattr(template_ctx, 'paramTypeList'):
            # 泛型 declare：只生成外部函数声明（无函数体）
            gen_ctx = template_ctx
            ret_type = self._map_type_with_map(gen_ctx.type_(), type_map)
            orig_param_names = []
            param_types = []
            ptl = gen_ctx.paramTypeList()
            if ptl is not None:
                for p in ptl.paramType():
                    pname = p.VAR_IDENTIFIER().getText()
                    ptype = self._map_type_with_map(p.type_(), type_map)
                    # 结构体参数使用指针传递（与 extern C ABI 兼容）
                    if isinstance(ptype, (ir.LiteralStructType, ir.IdentifiedStructType)):
                        ptype = ir.PointerType(ptype)
                    orig_param_names.append(pname)
                    param_types.append(ptype)

            func_type = ir.FunctionType(ret_type, param_types)
            func = ir.Function(self.module, func_type, mono_name)
            for i, pn in enumerate(orig_param_names):
                func.args[i].name = pn
            self.func_param_names[mono_name] = orig_param_names
            return mono_name

        # 普通泛型函数：生成完整的单态化函数体
        fn_lit = template_ctx.functionLiteral()

        ret_type = self._map_type_with_map(fn_lit.type_(), type_map)
        orig_param_names = []
        param_types = []
        params = fn_lit.paramList()
        if params is not None:
            for p in params.param():
                pname = p.VAR_IDENTIFIER().getText()
                ptype = self._map_type_with_map(p.type_(), type_map)
                orig_param_names.append(pname)
                param_types.append(ptype)

        func_type = ir.FunctionType(ret_type, param_types)
        func = ir.Function(self.module, func_type, mono_name)
        for i, pn in enumerate(orig_param_names):
            func.args[i].name = pn

        self.func_param_names[mono_name] = orig_param_names

        # 生成单态化函数体
        body = fn_lit.block() or fn_lit.expression()
        if body is not None:
            entry = func.append_basic_block(name='entry')
            prev_builder = self.builder
            prev_func = self.current_function
            prev_locals = self.locals

            self.builder = ir.IRBuilder(entry)
            self.current_function = func
            self.locals = {}

            for i, pn in enumerate(orig_param_names):
                alloca = self.builder.alloca(param_types[i], name=pn)
                self.builder.store(func.args[i], alloca)
                self.locals[pn] = alloca

            self._eval(body)

            if not self.builder.block.is_terminated:
                if isinstance(ret_type, ir.VoidType):
                    self.builder.ret_void()
                else:
                    self.builder.ret(self._zero_constant(ret_type))

            self.builder = prev_builder
            self.current_function = prev_func
            self.locals = prev_locals

        return mono_name

    def _map_type_with_map(self, ctx, type_map: dict[str, ir.Type]) -> ir.Type:
        """带泛型参数替换的类型映射 — 递归处理复合类型"""
        if ctx is None:
            return ir.IntType(32)

        P = EzLangParser

        # 泛型参数引用: 直接替换
        if isinstance(ctx, P.BaseTypeRefContext) and ctx.baseType() is not None:
            bt = ctx.baseType()
            if bt.TYPE_IDENTIFIER() is not None:
                name = bt.TYPE_IDENTIFIER().getText()
                if name in type_map:
                    return type_map[name]
            # 带泛型参数的内置复合类型引用，如 Dict<K, V> / List<T>
            if bt.genericArgs() is not None:
                args = list(bt.genericArgs().type_())
                if name == 'Dict':
                    return self.structs['Dict']
                if name == 'List':
                    inner = self._map_type_with_map(args[0], type_map) if args else ir.IntType(32)
                    return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])
            return self._map_type(ctx)

        # 可选类型: T? → {i1, T}
        if isinstance(ctx, P.OptionalTypeContext):
            inner = self._map_type_with_map(ctx.type_(), type_map)
            return ir.LiteralStructType([ir.IntType(1), inner])

        # List 类型: List<T> → { data, length, capacity }
        if isinstance(ctx, P.ListTypeContext):
            inner = self._map_type_with_map(ctx.type_(), type_map)
            return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])

        # 数组类型: T[] → { data, length, capacity }
        if isinstance(ctx, P.ArrayTypeContext):
            inner = self._map_type_with_map(ctx.type_(), type_map)
            return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])

        return self._map_type(ctx)

    @staticmethod
    def _type_name(t: ir.Type) -> str:
        """LLVM 类型简短名称"""
        if isinstance(t, ir.IntType):
            return f"I{t.width}"
        if isinstance(t, ir.FloatType):
            return "F32"
        if isinstance(t, ir.DoubleType):
            return "F64"
        if isinstance(t, ir.PointerType):
            if t.pointee == ir.IntType(8):
                return "Str"
            return "Ptr"
        if isinstance(t, ir.VectorType):
            return f"V{LLVMCodeGenerator._type_name(t.element)}{t.count}"
        if isinstance(t, (ir.LiteralStructType, ir.IdentifiedStructType)):
            return t.name if hasattr(t, 'name') and t.name else "Struct"
        if isinstance(t, ir.VoidType):
            return "Void"
        return "T"

    # 括号表达式
    def visitParenExpr(self, ctx: EzLangParser.ParenExprContext):
        return self._eval(ctx.expression())

    # Pipeline postfix 标签（链式管道）：left -> func<T>(args)
    def visitPipeline(self, ctx: EzLangParser.PipelineContext):
        left = self._eval(ctx.postfixExpression())
        if left is None:
            return None

        func_name = ctx.VAR_IDENTIFIER().getText()
        generic_args = ctx.genericArgs()
        if generic_args is not None:
            type_args = [self._map_type(t) for t in generic_args.type_()]
            func_name = self._monomorphize(func_name, type_args)
        func = self.module.get_global(func_name)
        if func is None or not isinstance(func, ir.Function):
            return left

        call_args = []
        has_percent = False
        arg_list = ctx.pipelineArgList()
        if arg_list is not None:
            for a in arg_list.pipelineArg():
                if a.PERCENT() is not None:
                    call_args.append(left)
                    has_percent = True
                elif a.expression() is not None:
                    val = self._eval(a.expression())
                    call_args.append(val if val is not None else ir.Constant(ir.IntType(32), 0))
        if not has_percent:
            call_args.insert(0, left)

        return self.builder.call(func, call_args)

    # PrimaryExpr（postfixExpression → primaryExpression 的入口）
    def visitPrimaryExpr(self, ctx: EzLangParser.PrimaryExprContext):
        return self._eval(ctx.primaryExpression())

    # Range 表达式
    def visitRangeExpression(self, ctx: EzLangParser.RangeExpressionContext):
        """范围表达式，直接返回第一个表达式，范围由 visitLoopExpr 专用处理"""
        return self._eval(ctx.orExpression(0))

    # ==================== 结构体字面量与成员访问 ====================

    def visitStructLiteral(self, ctx: EzLangParser.StructLiteralContext):
        """创建结构体实例: Point(x = 10, y = 20)"""
        name = ctx.TYPE_IDENTIFIER().getText()
        if name not in self.structs:
            return None
        struct_type = self.structs[name]
        field_names = self.struct_fields[name]

        # Arena 分配并零初始化
        alloca = self._arena_allocate(struct_type, name=f"_tmp_{name}")
        self.builder.store(self._zero_constant(struct_type), alloca)

        # 记录已显式提供的字段
        provided_fields: set[str] = set()
        def _set_field(fname: str, val: ir.Value):
            """向结构体写入字段值"""
            if fname in field_names and val is not None:
                idx = field_names.index(fname)
                field_type = struct_type.elements[idx]
                if self._is_aggregate_ptr(val) and val.type.pointee == field_type:
                    val = self.builder.load(val)
                if val.type != field_type:
                    val = self._coerce_value(val, field_type)
                ptr = self.builder.gep(alloca, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), idx)
                ], inbounds=True)
                self.builder.store(val, ptr)

        # 处理字段初始化
        init_list = ctx.structFieldInitList()
        if init_list is not None:
            for init_ctx in init_list.structFieldInit():
                # 实例展开: ...instance → 复制 instance 的所有字段
                if init_ctx.ELLIPSIS() is not None:
                    spread_val = self._eval(init_ctx.expression())
                    if spread_val is not None:
                        src_type = spread_val.type.pointee if hasattr(spread_val.type, 'pointee') else spread_val.type
                        src_name = src_type.name if isinstance(src_type, ir.IdentifiedStructType) else None
                        src_fields = self.struct_fields.get(src_name, []) if src_name else []
                        for fname in field_names:
                            if fname not in src_fields:
                                continue
                            dst_idx = field_names.index(fname)
                            src_idx = src_fields.index(fname)
                            ptr = self.builder.gep(alloca, [
                                ir.Constant(ir.IntType(32), 0),
                                ir.Constant(ir.IntType(32), dst_idx)
                            ], inbounds=True)
                            src_ptr = self.builder.gep(spread_val, [
                                ir.Constant(ir.IntType(32), 0),
                                ir.Constant(ir.IntType(32), src_idx)
                            ], inbounds=True)
                            val = self.builder.load(src_ptr)
                            if val.type == struct_type.elements[dst_idx]:
                                self.builder.store(val, ptr)
                                provided_fields.add(fname)
                    continue

                fname = init_ctx.VAR_IDENTIFIER().getText()
                if fname in field_names and init_ctx.expression() is not None:
                    val = self._eval(init_ctx.expression())
                    _set_field(fname, val)
                    provided_fields.add(fname)

        # 对未提供的字段应用默认值
        defaults = self.struct_defaults.get(name, {})
        for fname, default_expr in defaults.items():
            if fname not in provided_fields:
                val = self._eval(default_expr)
                _set_field(fname, val)

        return alloca

    def visitStructLiteralExpr(self, ctx: EzLangParser.StructLiteralExprContext):
        return self.visitStructLiteral(ctx.structLiteral())

    def _gen_struct_literal_from_call(self, struct_name: str, call_ctx):
        """从 CallContext 生成结构体实例（当语法解析为 # call 路径时）"""
        if struct_name not in self.structs:
            return None
        struct_type = self.structs[struct_name]
        field_names = self.struct_fields[struct_name]

        # Arena 分配并零初始化
        alloca = self._arena_allocate(struct_type, name=f"_tmp_{struct_name}")
        self.builder.store(self._zero_constant(struct_type), alloca)

        def _set_field(fname: str, val: ir.Value):
            if fname in field_names and val is not None:
                idx = field_names.index(fname)
                field_type = struct_type.elements[idx]
                if val.type != field_type:
                    if isinstance(val.type, ir.IntType) and isinstance(field_type, ir.IntType):
                        val = self.builder.zext(val, field_type) if val.type.width < field_type.width else self.builder.trunc(val, field_type)
                    elif isinstance(val.type, ir.IntType) and isinstance(field_type, ir.PointerType):
                        val = self.builder.inttoptr(val, field_type)
                    elif isinstance(val.type, ir.PointerType) and isinstance(field_type, ir.IntType):
                        val = self.builder.ptrtoint(val, field_type)
                ptr = self.builder.gep(alloca, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), idx)
                ], inbounds=True)
                self.builder.store(val, ptr)

        # 处理命名参数（等价于结构体字段初始化）
        provided = set()
        args = call_ctx.namedArgList()
        if args and args.namedArg():
            for a in args.namedArg():
                if a.VAR_IDENTIFIER() is None or a.expression() is None:
                    continue
                fname = a.VAR_IDENTIFIER().getText()
                val = self._eval(a.expression())
                _set_field(fname, val)
                provided.add(fname)

        # 对未提供的字段应用默认值
        defaults = self.struct_defaults.get(struct_name, {})
        for fname, default_expr in defaults.items():
            if fname not in provided:
                val = self._eval(default_expr)
                _set_field(fname, val)

        return alloca

    def visitMemberAccess(self, ctx: EzLangParser.MemberAccessContext):
        """对象字段访问: obj.field 或方法访问: obj.method"""
        obj_ptr = self._eval(ctx.postfixExpression())
        if obj_ptr is None:
            return None
        field_name = ctx.VAR_IDENTIFIER().getText()

        pointee = obj_ptr.type.pointee if hasattr(obj_ptr.type, 'pointee') else obj_ptr.type
        if not isinstance(pointee, (ir.IdentifiedStructType, ir.LiteralStructType)):
            return None

        struct_name = pointee.name if isinstance(pointee, ir.IdentifiedStructType) else None

        if struct_name and struct_name in self.struct_methods:
            methods = self.struct_methods[struct_name]
            if field_name in methods:
                func = self.module.get_global(methods[field_name])
                if func is not None:
                    self._method_this = obj_ptr
                    return func

        if struct_name and struct_name in self.struct_fields:
            field_names = self.struct_fields[struct_name]
            if field_name in field_names:
                idx = field_names.index(field_name)
                gep = self.builder.gep(obj_ptr, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), idx)
                ], inbounds=True)
                value = self.builder.load(gep, name=field_name)
                if isinstance(value.type, ir.PointerType) and isinstance(value.type.pointee, ir.FunctionType):
                    self._method_this = obj_ptr
                return value

        return None

    # ==================== 数组字面量与索引 ====================

    def visitArrayLiteral(self, ctx: EzLangParser.ArrayLiteralContext):
        """创建数组字面量 [e1, e2, ...]"""
        exprs = []
        expr_list = ctx.expressionList()
        if expr_list is not None:
            exprs = list(expr_list.expression())

        values = []
        for e in exprs:
            v = self._eval(e)
            if v is not None:
                if isinstance(v, ir.AllocaInstr):
                    v = self.builder.load(v)
                values.append(v)

        elem_type = values[0].type if values else ir.IntType(32)
        count = len(values)
        i64 = ir.IntType(64)
        page_size = 8
        page_count = max((count + page_size - 1) // page_size, 1)
        arr_type = ir.LiteralStructType([ir.PointerType(ir.PointerType(elem_type)), i64, i64, i64])
        alloca = self._arena_allocate(arr_type, name="_tmp_arr")
        page_table_type = ir.ArrayType(ir.PointerType(elem_type), page_count)
        page_table = self._arena_allocate(page_table_type, name="_tmp_arr_pages")
        current_pages: list[ir.Value] = []

        for page_idx in range(page_count):
            page_type = ir.ArrayType(elem_type, page_size)
            page_ptr = self._arena_allocate(page_type, name="_tmp_arr_page")
            page_base = self.builder.gep(page_ptr, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), 0)
            ], inbounds=True)
            page_slot = self.builder.gep(page_table, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), page_idx)
            ], inbounds=True)
            self.builder.store(page_base, page_slot)
            current_pages.append(page_ptr)

        for i, v in enumerate(values):
            if v.type != elem_type and isinstance(v.type, ir.IntType) and isinstance(elem_type, ir.IntType):
                v = self.builder.zext(v, elem_type) if v.type.width < elem_type.width else self.builder.trunc(v, elem_type)
            page_ptr = current_pages[i // page_size]
            ptr = self.builder.gep(page_ptr, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), i % page_size)
            ], inbounds=True)
            self.builder.store(v, ptr)

        pages_base = self.builder.gep(page_table, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), 0)
        ], inbounds=True)
        pages_field = self.builder.gep(alloca, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)], inbounds=True)
        len_field = self.builder.gep(alloca, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 1)], inbounds=True)
        cap_field = self.builder.gep(alloca, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 2)], inbounds=True)
        page_count_field = self.builder.gep(alloca, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 3)], inbounds=True)
        self.builder.store(pages_base, pages_field)
        self.builder.store(ir.Constant(i64, count), len_field)
        self.builder.store(ir.Constant(i64, page_count * page_size), cap_field)
        self.builder.store(ir.Constant(i64, page_count), page_count_field)
        return alloca

    def visitArrayLiteralExpr(self, ctx: EzLangParser.ArrayLiteralExprContext):
        return self.visitArrayLiteral(ctx.arrayLiteral())

    # ==================== 字典字面量 ====================

    def visitDictLiteral(self, ctx: EzLangParser.DictLiteralContext):
        """字典字面量 { key: Type = value } → Dict 分页结构"""
        fields = ctx.dictField() if ctx.dictField() else []
        dict_type = self.structs['Dict']
        alloca = self._arena_allocate(dict_type, name="_tmp_dict")
        self.builder.store(self._zero_constant(dict_type), alloca)
        for f in fields:
            key = self._make_global_string(f.VAR_IDENTIFIER().getText(), prefix="_dict_key")
            val = self._eval(f.expression())
            if isinstance(val, ir.AllocaInstr):
                val = self.builder.load(val)
            if val is not None and val.type != ir.PointerType(ir.IntType(8)):
                tmp = self.builder.alloca(val.type, name="_dict_val")
                self.builder.store(val, tmp)
                val = self.builder.bitcast(tmp, ir.PointerType(ir.IntType(8)))
            self._gen_dict_set(alloca, key, val)
        return alloca

    def visitDictExpr(self, ctx: EzLangParser.DictExprContext):
        return self.visitDictLiteral(ctx.dictLiteral())

    # ==================== 占位符 ====================

    def visitPlaceholderExpr(self, ctx: EzLangParser.PlaceholderExprContext):
        """? 占位符（柯里化占位，暂返回零值）"""
        return ir.Constant(ir.IntType(32), 0)

    # ==================== 标记字面量 ====================

    def visitMarkupExpr(self, ctx: EzLangParser.MarkupExprContext):
        return self.visitMarkupLiteral(ctx.markupLiteral())

    def visitMarkupLiteral(self, ctx: EzLangParser.MarkupLiteralContext):
        names = ctx.VAR_IDENTIFIER()
        tag_name = names[0].getText() if names else "tag"
        for attr in ctx.markupAttr():
            if attr.expression() is not None:
                self._eval(attr.expression())
        for child in ctx.markupChild():
            if child.markupLiteral() is not None:
                self.visitMarkupLiteral(child.markupLiteral())
            elif child.expression() is not None:
                self._eval(child.expression())
        return self._make_global_string(tag_name, prefix="_markup")

    # ==================== typeof 表达式 ====================

    def visitTypeofExpr(self, ctx: EzLangParser.TypeofExprContext):
        """typeof 表达式：编译时类型查询，运行时返回占位符"""
        return ir.Constant(ir.IntType(32), 0)

    def visitTypeofPrimaryExpr(self, ctx: EzLangParser.TypeofPrimaryExprContext):
        return self.visitTypeofExpr(ctx.typeofExpr())

    # ==================== flow 并发块 ====================

    def visitFlowBlock(self, ctx: EzLangParser.FlowBlockContext):
        """flow 块：插入运行时边界，当前仍保持同步块执行"""
        if self.builder is not None:
            self.builder.call(self._flow_enter, [])
        self._flow_depth += 1
        result = self._eval(ctx.block())
        self._flow_depth -= 1
        if self.builder is not None and not self.builder.block.is_terminated:
            self.builder.call(self._flow_exit, [])
        return result

    def visitFlowBlockExpr(self, ctx: EzLangParser.FlowBlockExprContext):
        return self.visitFlowBlock(ctx.flowBlock())

    # ==================== SIMD 向量 ====================

    def visitVecLiteral(self, ctx: EzLangParser.VecLiteralContext):
        """创建 SIMD 向量字面量: Vec[1, 2, 3, 4] → <4 x i32>"""
        exprs = []
        expr_list = ctx.expressionList()
        if expr_list is not None:
            exprs = list(expr_list.expression())
        if not exprs:
            return None

        values = []
        elem_type = None
        for e in exprs:
            v = self._eval(e)
            if v is not None:
                if isinstance(v, ir.AllocaInstr):
                    v = self.builder.load(v)
                values.append(v)
                if elem_type is None:
                    elem_type = v.type

        if not values or elem_type is None:
            return None

        vec_type = ir.VectorType(elem_type, len(values))
        # 逐个插入元素构建向量
        undef = ir.Constant(vec_type, ir.Undefined)
        for i, v in enumerate(values):
            undef = self.builder.insert_element(undef, v, ir.Constant(ir.IntType(32), i))
        return undef

    def visitVecLiteralExpr(self, ctx: EzLangParser.VecLiteralExprContext):
        return self.visitVecLiteral(ctx.vecLiteral())

    def visitIndex(self, ctx: EzLangParser.IndexContext):
        """数组索引: arr[index]"""
        obj_ptr = self._eval(ctx.postfixExpression())
        if obj_ptr is None:
            return None
        index_val = self._eval(ctx.expression())
        if index_val is None:
            return None

        pointee = obj_ptr.type.pointee if hasattr(obj_ptr.type, 'pointee') else None
        if isinstance(pointee, ir.LiteralStructType) and len(pointee.elements) == 4 and isinstance(pointee.elements[0], ir.PointerType):
            pages_field = self.builder.gep(obj_ptr, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), 0)
            ], inbounds=True)
            pages_ptr = self.builder.load(pages_field, name='_arr_pages')
            if isinstance(index_val.type, ir.IntType) and index_val.type.width < 64:
                index_val = self.builder.zext(index_val, ir.IntType(64))
            page_idx = self.builder.udiv(index_val, ir.Constant(ir.IntType(64), 8))
            slot_idx = self.builder.urem(index_val, ir.Constant(ir.IntType(64), 8))
            page_slot = self.builder.gep(pages_ptr, [page_idx], inbounds=True)
            page_ptr = self.builder.load(page_slot, name='_arr_page')
            elem_ptr = self.builder.gep(page_ptr, [slot_idx], inbounds=True)
            return self.builder.load(elem_ptr)

        # 兼容旧裸数组指针
        gep = self.builder.gep(obj_ptr, [
            ir.Constant(ir.IntType(32), 0),
            index_val
        ], inbounds=True)
        return self.builder.load(gep)

    # 函数调用
    def visitCall(self, ctx: EzLangParser.CallContext):
        target_expr = ctx.postfixExpression()

        # 方法调用：obj.method(...) → 先求值 postfixExpression
        # visitMemberAccess 返回 function 并设置 _method_this
        self._method_this = None
        func = self._eval(target_expr)

        # 如果 _eval 没返回可调用对象，尝试从标识符查找（通过 primaryExpression 间接访问）
        name = None
        if not self._is_callable_value(func):
            # target_expr 可能是 PrimaryExprContext（包装了 primaryExpression）
            inner = target_expr
            if hasattr(target_expr, 'primaryExpression') and target_expr.primaryExpression():
                inner = target_expr.primaryExpression()
            if hasattr(inner, 'identifierExpr') and inner.identifierExpr():
                id_ctx = inner.identifierExpr()
                id_token = id_ctx.VAR_IDENTIFIER() or id_ctx.TYPE_IDENTIFIER()
                name = id_token.getText()
                # 泛型函数调用：id<I32>(...) → 使用单态化后的名称 id_I32
                if id_ctx.genericArgs() is not None:
                    type_args = [self._map_type(t) for t in id_ctx.genericArgs().type_()]
                    name = self._monomorphize(name, type_args)
            elif hasattr(inner, 'VAR_IDENTIFIER') and inner.VAR_IDENTIFIER():
                name = inner.VAR_IDENTIFIER().getText()
                # 泛型函数调用（primaryExpression 直接返回 IdentifierExprContext 时不走上面分支）
                if hasattr(inner, 'genericArgs') and inner.genericArgs() is not None:
                    type_args = [self._map_type(t) for t in inner.genericArgs().type_()]
                    name = self._monomorphize(name, type_args)
            elif hasattr(inner, 'TYPE_IDENTIFIER') and inner.TYPE_IDENTIFIER():
                name = inner.TYPE_IDENTIFIER().getText()
            else:
                return None

            # 判断是结构体构造还是函数调用
            if name in self.structs:
                # 结构体构造：重定向到 structLiteral 逻辑
                sl_ctx = ctx
                return self._gen_struct_literal_from_call(name, sl_ctx)
            try:
                func = self.module.get_global(name)
            except KeyError:
                func = None

        is_unimplemented_collection = name and any(
            name == base or name.startswith(f'{base}_') for base in self._unimplemented_collection_declares
        )

        if func is None or not self._is_callable_value(func):
            # compiler builtin / 未实现集合函数不生成外部声明。
            if name in self._compiler_builtin_declares or (
                name and any(name == base or name.startswith(f'{base}_') for base in self._unimplemented_collection_declares)
            ):
                func = None
            elif name:
                args = ctx.namedArgList()
                nargs = len(args.namedArg()) if args and args.namedArg() else 1
                ftype = ir.FunctionType(ir.VoidType(), [ir.PointerType(ir.IntType(8))] * nargs)
                func = ir.Function(self.module, ftype, name)
            else:
                return None

        # 获取函数名，用于查参数元数据
        func_name = name if name else func.name if func is not None else ''

        # 获取函数期望的参数名列表和默认值
        expected_names = self.func_param_names.get(func_name, [])
        defaults = self.func_defaults.get(func_name, {})

        # 解析调用时提供的具名参数，检测 ? 占位符（柯里化）
        provided: dict[str, any] = {}
        placeholder_params: list[str] = []  # 柯里化：需要延迟绑定的参数名
        args = ctx.namedArgList()
        if args and args.namedArg():
            for a in args.namedArg():
                if a.VAR_IDENTIFIER() is not None and a.expression() is not None:
                    pname = a.VAR_IDENTIFIER().getText()
                    # 检查表达式是否为 ? 占位符
                    if a.expression().getText().strip() == '?':
                        placeholder_params.append(pname)
                    else:
                        val = self._eval(a.expression())
                        if val is not None:
                            provided[pname] = val

        # 如果存在 ? 占位符，生成柯里化闭包
        if placeholder_params:
            return self._gen_curried_call(func, func_name, expected_names, provided, placeholder_params)

        # 按函数参数顺序构建实参列表（具名重排 + 默认值注入）
        call_args = []
        if expected_names:
            # 方法调用：首个参数是 this
            if self._method_this is not None:
                call_args.append(self.builder.load(self._method_this) if isinstance(self._method_this, ir.AllocaInstr) else self._method_this)
            for pname in expected_names:
                if self._method_this is not None and pname == expected_names[0]:
                    continue  # this 已添加
                if pname in provided:
                    call_args.append(provided[pname])
                elif pname in defaults:
                    dv = self._eval(defaults[pname])
                    if dv is not None:
                        call_args.append(dv)
                    else:
                        call_args.append(ir.Constant(ir.IntType(32), 0))
                else:
                    call_args.append(ir.Constant(ir.IntType(32), 0))
        else:
            call_args = []
            func_type_for_args = func.type.pointee if func is not None and isinstance(func.type, ir.PointerType) else None
            if self._method_this is not None and isinstance(func_type_for_args, ir.FunctionType) and func_type_for_args.args:
                this_arg = self._method_this
                if self._is_aggregate_ptr(this_arg) and this_arg.type.pointee == func_type_for_args.args[0]:
                    this_arg = self.builder.load(this_arg)
                call_args.append(this_arg)
            call_args.extend(provided.values())

        # 检查是否为编译器内建函数
        intrinsic_result = self._try_gen_intrinsic_call(func_name, call_args)
        if intrinsic_result is not None:
            return intrinsic_result

        if func is None:
            return self._zero_constant(self._call_return_type(ctx))

        func_type = func.type.pointee if isinstance(func.type, ir.PointerType) else None
        if self._flow_depth > 0 and func_name == 'sleep' and call_args:
            sleep_arg = self._coerce_value(call_args[0], ir.IntType(64))
            return self.builder.call(self._flow_sleep, [sleep_arg])
        if self._flow_depth > 0 and func_name == 'race' and len(call_args) >= 2:
            task_arg = call_args[0]
            if task_arg.type != ir.IntType(32):
                task_arg = ir.Constant(ir.IntType(32), 0)
            timeout_arg = self._coerce_value(call_args[1], ir.IntType(32))
            return self.builder.call(self._flow_race, [task_arg, timeout_arg])

        if func_type is not None:
            call_args = [
                self._coerce_value(arg, func_type.args[i]) if i < len(func_type.args) else arg
                for i, arg in enumerate(call_args)
            ]

        return self.builder.call(func, call_args)

    def _call_return_type(self, ctx) -> ir.Type:
        """从调用表达式的类型上下文估算返回类型，用于错误恢复。"""
        target = ctx.postfixExpression()
        id_ctx = self._leftmost_identifier_ctx(target)
        if id_ctx is None or id_ctx.genericArgs() is None:
            return ir.IntType(32)
        id_token = id_ctx.VAR_IDENTIFIER() or id_ctx.TYPE_IDENTIFIER()
        base_name = id_token.getText()
        template = self.generic_templates.get(base_name)
        if template is None:
            return ir.IntType(32)
        type_args = [self._map_type(t) for t in id_ctx.genericArgs().type_()]
        type_map = dict(zip(template[0], type_args))
        template_ctx = template[1]
        if hasattr(template_ctx, 'type_'):
            return self._map_type_with_map(template_ctx.type_(), type_map)
        return ir.IntType(32)

    @staticmethod
    def _is_callable_value(value) -> bool:
        if isinstance(value, ir.Function):
            return True
        return isinstance(value, ir.Value) and isinstance(value.type, ir.PointerType) and isinstance(value.type.pointee, ir.FunctionType)

    def _try_gen_intrinsic_call(self, name: str, call_args: list) -> Optional[ir.Value]:
        """编译器内建函数：将标准库函数映射为 LLVM 内建操作"""
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)

        if name == 'copy' and len(call_args) >= 3:
            # copy(dst: Blob, src: Blob, count: I64) → llvm.memcpy
            memcpy = self.module.get_global('llvm.memcpy.p0.p0.i64')
            dst = self.builder.bitcast(call_args[0], i8_ptr) if call_args[0].type != i8_ptr else call_args[0]
            src = self.builder.bitcast(call_args[1], i8_ptr) if call_args[1].type != i8_ptr else call_args[1]
            count = call_args[2]
            is_volatile = ir.Constant(ir.IntType(1), 0)
            # 对 I32 count 做 zext 到 I64
            if isinstance(count.type, ir.IntType) and count.type.width < 64:
                count = self.builder.zext(count, i64)
            return self.builder.call(memcpy, [dst, src, count, is_volatile])

        if name == 'set' and len(call_args) >= 3:
            # set(dst: Blob, value: U8, count: I64) → llvm.memset
            void = ir.VoidType()
            memset_type = ir.FunctionType(void, [i8_ptr, i8, i64, ir.IntType(1)])
            memset_name = 'llvm.memset.p0.i64'
            try:
                memset = self.module.get_global(memset_name)
            except KeyError:
                memset = ir.Function(self.module, memset_type, memset_name)
            dst = self.builder.bitcast(call_args[0], i8_ptr) if call_args[0].type != i8_ptr else call_args[0]
            val = self.builder.trunc(call_args[1], i8) if isinstance(call_args[1].type, ir.IntType) and call_args[1].type.width > 8 else call_args[1]
            count = call_args[2]
            if isinstance(count.type, ir.IntType) and count.type.width < 64:
                count = self.builder.zext(count, i64)
            is_volatile = ir.Constant(ir.IntType(1), 0)
            return self.builder.call(memset, [dst, val, count, is_volatile])

        if name == 'allocRaw' and len(call_args) >= 1:
            size = call_args[0]
            if isinstance(size.type, ir.IntType) and size.type.width < 64:
                size = self.builder.zext(size, i64)
            raw = self.builder.call(self._arena_alloc, [size, ir.Constant(i64, 8)])
            blob_type = self.structs['Blob']
            blob = ir.Constant(blob_type, ir.Undefined)
            blob = self.builder.insert_value(blob, raw, 0)
            blob = self.builder.insert_value(blob, size, 1)
            return blob

        if name == 'dict_set' and len(call_args) >= 3:
            return self._gen_dict_set(call_args[0], call_args[1], call_args[2])
        if name == 'dict_get' and len(call_args) >= 2:
            return self._gen_dict_get(call_args[0], call_args[1])

        return None

    def _gen_dict_set(self, dict_ptr: ir.Value, key: ir.Value, value: ir.Value) -> ir.Value:
        """dict_set(dict, key, value): 向分页存储追加元素，容量不足时分配新页"""
        i32 = ir.IntType(32)
        i8 = ir.IntType(8)
        i8_ptr = ir.PointerType(i8)
        i8_ptr_ptr = ir.PointerType(i8_ptr)
        i8_ptr_ptr_ptr = ir.PointerType(i8_ptr_ptr)

        count_ptr = self.builder.gep(dict_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 2)], inbounds=True)
        capacity_ptr = self.builder.gep(dict_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 3)], inbounds=True)
        page_count_ptr = self.builder.gep(dict_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 4)], inbounds=True)
        count = self.builder.load(count_ptr, name='_count')
        capacity = self.builder.load(capacity_ptr, name='_capacity')
        page_count = self.builder.load(page_count_ptr, name='_page_count')

        has_capacity = self.builder.icmp_unsigned('<', count, capacity)
        current_block = self.builder.block
        grow_block = self.builder.append_basic_block('dict_grow')
        insert_block = self.builder.append_basic_block('dict_insert')
        self.builder.cbranch(has_capacity, insert_block, grow_block)

        self.builder.position_at_start(grow_block)
        new_page_count = self.builder.add(page_count, ir.Constant(i32, 1))
        page_table_slots = self.builder.mul(new_page_count, ir.Constant(i32, 8))
        page_table_bytes = self.builder.zext(page_table_slots, ir.IntType(64))
        page_table_raw = self.builder.call(self._arena_alloc, [page_table_bytes, ir.Constant(ir.IntType(64), 8)])
        new_key_pages = self.builder.bitcast(page_table_raw, i8_ptr_ptr_ptr)
        page_table_raw = self.builder.call(self._arena_alloc, [page_table_bytes, ir.Constant(ir.IntType(64), 8)])
        new_value_pages = self.builder.bitcast(page_table_raw, i8_ptr_ptr_ptr)
        key_pages_ptr = self.builder.gep(dict_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        value_pages_ptr = self.builder.gep(dict_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
        old_key_pages = self.builder.load(key_pages_ptr, name='_old_key_pages')
        old_value_pages = self.builder.load(value_pages_ptr, name='_old_value_pages')
        copy_idx = self.builder.alloca(i32, name='_dict_copy_i')
        self.builder.store(ir.Constant(i32, 0), copy_idx)
        copy_cond = self.builder.append_basic_block('dict_copy_cond')
        copy_body = self.builder.append_basic_block('dict_copy_body')
        copy_done = self.builder.append_basic_block('dict_copy_done')
        self.builder.branch(copy_cond)

        self.builder.position_at_start(copy_cond)
        i = self.builder.load(copy_idx, name='_dict_copy_i_val')
        copy_more = self.builder.icmp_unsigned('<', i, page_count)
        self.builder.cbranch(copy_more, copy_body, copy_done)

        self.builder.position_at_start(copy_body)
        old_k_slot = self.builder.gep(old_key_pages, [i], inbounds=True)
        old_v_slot = self.builder.gep(old_value_pages, [i], inbounds=True)
        new_k_slot = self.builder.gep(new_key_pages, [i], inbounds=True)
        new_v_slot = self.builder.gep(new_value_pages, [i], inbounds=True)
        self.builder.store(self.builder.load(old_k_slot), new_k_slot)
        self.builder.store(self.builder.load(old_v_slot), new_v_slot)
        self.builder.store(self.builder.add(i, ir.Constant(i32, 1)), copy_idx)
        self.builder.branch(copy_cond)

        self.builder.position_at_start(copy_done)
        page_bytes = ir.Constant(ir.IntType(64), 64)
        key_page_raw = self.builder.bitcast(
            self.builder.call(self._arena_alloc, [page_bytes, ir.Constant(ir.IntType(64), 8)]),
            i8_ptr_ptr
        )
        value_page_raw = self.builder.bitcast(
            self.builder.call(self._arena_alloc, [page_bytes, ir.Constant(ir.IntType(64), 8)]),
            i8_ptr_ptr
        )
        new_page_idx = page_count
        new_k_slot = self.builder.gep(new_key_pages, [new_page_idx], inbounds=True)
        new_v_slot = self.builder.gep(new_value_pages, [new_page_idx], inbounds=True)
        self.builder.store(key_page_raw, new_k_slot)
        self.builder.store(value_page_raw, new_v_slot)
        self.builder.store(new_key_pages, key_pages_ptr)
        self.builder.store(new_value_pages, value_pages_ptr)
        self.builder.store(new_page_count, page_count_ptr)
        self.builder.store(self.builder.mul(new_page_count, ir.Constant(i32, 8)), capacity_ptr)
        self.builder.branch(insert_block)

        self.builder.position_at_start(insert_block)
        pages_ptr = self.builder.gep(dict_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        values_ptr = self.builder.gep(dict_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
        key_pages = self.builder.load(pages_ptr, name='_key_pages')
        value_pages = self.builder.load(values_ptr, name='_value_pages')
        page_idx = self.builder.udiv(count, ir.Constant(i32, 8))
        slot_idx32 = self.builder.urem(count, ir.Constant(i32, 8))
        slot_idx = self.builder.zext(slot_idx32, ir.IntType(64))
        key_page_slot = self.builder.gep(key_pages, [page_idx], inbounds=True)
        value_page_slot = self.builder.gep(value_pages, [page_idx], inbounds=True)
        key_page = self.builder.load(key_page_slot, name='_key_page')
        value_page = self.builder.load(value_page_slot, name='_value_page')
        key_slot = self.builder.gep(key_page, [slot_idx], inbounds=True)
        value_slot = self.builder.gep(value_page, [slot_idx], inbounds=True)
        k = self.builder.bitcast(key, i8_ptr) if key.type != i8_ptr else key
        v = self.builder.bitcast(value, i8_ptr) if value.type != i8_ptr else value
        self.builder.store(k, key_slot)
        self.builder.store(v, value_slot)
        self.builder.store(self.builder.add(count, ir.Constant(i32, 1)), count_ptr)
        return None

    def _gen_dict_get(self, dict_ptr: ir.Value, key: ir.Value) -> ir.Value:
        """dict_get(dict, key): 从分页存储读取第一个值，空字典返回 null"""
        i32 = ir.IntType(32)
        i8_ptr = ir.PointerType(ir.IntType(8))

        count_ptr = self.builder.gep(dict_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 2)], inbounds=True)
        count = self.builder.load(count_ptr, name='_count')
        empty = self.builder.icmp_unsigned('==', count, ir.Constant(i32, 0))
        current_block = self.builder.block
        null_block = self.builder.append_basic_block('dict_get_null')
        value_block = self.builder.append_basic_block('dict_get_value')
        done_block = self.builder.append_basic_block('dict_get_done')
        self.builder.cbranch(empty, null_block, value_block)

        self.builder.position_at_start(null_block)
        self.builder.branch(done_block)

        self.builder.position_at_start(value_block)
        pages_ptr = self.builder.gep(dict_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
        value_pages = self.builder.load(pages_ptr, name='_value_pages')
        first_page_slot = self.builder.gep(value_pages, [ir.Constant(i32, 0)], inbounds=True)
        first_page = self.builder.load(first_page_slot, name='_first_value_page')
        value_slot = self.builder.gep(first_page, [ir.Constant(ir.IntType(64), 0)], inbounds=True)
        value = self.builder.load(value_slot)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        result = self.builder.phi(i8_ptr, name='_dict_value')
        result.add_incoming(ir.Constant(i8_ptr, None), null_block)
        result.add_incoming(value, value_block)
        return result

    def _gen_curried_call(self, func, func_name, expected_names, provided, placeholder_params):
        """为带 ? 占位符的调用生成柯里化闭包"""
        i32 = ir.IntType(32)
        i8_ptr = ir.PointerType(ir.IntType(8))

        # 获取被柯里化函数的类型信息
        if isinstance(func.type, ir.PointerType):
            func_type = func.type.pointee
        else:
            return ir.Constant(i32, 0)

        # 分类参数：捕获的参数 vs 占位符参数
        captured_types = []
        captured_values = []
        placeholder_types = []

        for pname in expected_names:
            if pname in placeholder_params:
                # 找到该参数在函数类型中的位置
                idx = expected_names.index(pname)
                if idx < len(func_type.args):
                    placeholder_types.append(func_type.args[idx])
            elif pname in provided:
                captured_types.append(provided[pname].type if hasattr(provided[pname], 'type') else i32)
                captured_values.append(pname)

        # 生成唯一的 trampoline 名称
        tramp_name = f"{func_name}_curried"
        counter = 0
        while tramp_name in self._monomorphized:
            tramp_name = f"{func_name}_curried_{counter}"
            counter += 1
        self._monomorphized.add(tramp_name)

        # 闭包结构体：{原函数指针, 捕获值...}
        closure_field_types = [func.type] + captured_types
        closure_type = ir.LiteralStructType(closure_field_types)
        closure_ptr_type = ir.PointerType(closure_type)

        # 分配闭包结构体
        closure = self.builder.alloca(closure_type, name="_closure")
        undef_closure = ir.Constant(closure_type, ir.Undefined)

        # 存入函数指针
        v = self.builder.insert_value(undef_closure, func, 0)

        # 存入捕获的值
        for i, pname in enumerate(captured_values):
            val = provided[pname]
            # 如果值与闭包字段类型不匹配，尝试转换
            if val.type != captured_types[i]:
                if isinstance(val.type, ir.IntType) and isinstance(captured_types[i], ir.IntType):
                    val = self.builder.zext(val, captured_types[i]) if val.type.width < captured_types[i].width else self.builder.trunc(val, captured_types[i])
            v = self.builder.insert_value(v, val, i + 1)

        self.builder.store(v, closure)

        # 创建跳板函数
        tramp_param_types = [closure_ptr_type] + placeholder_types
        ret_type = func_type.return_type
        tramp_func_type = ir.FunctionType(ret_type, tramp_param_types)
        tramp_func = ir.Function(self.module, tramp_func_type, name=tramp_name)

        # 保存当前 builder 状态，进入跳板函数体
        old_builder = self.builder
        old_locals = self.locals.copy()
        old_method_this = self._method_this

        entry_bb = tramp_func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(entry_bb)
        self.locals = {}

        # 从闭包加载捕获的值
        closure_arg = tramp_func.args[0]
        final_args = []
        cap_idx = 1
        placeholder_idx = 0

        for pname in expected_names:
            if pname in placeholder_params:
                # 使用传入的占位参数值
                placeholder_arg = tramp_func.args[1 + placeholder_idx]
                final_args.append(placeholder_arg)
                placeholder_idx += 1
            elif pname in provided:
                # 从闭包加载捕获的值
                cap_ptr = self.builder.gep(closure_arg, [
                    ir.Constant(i32, 0),
                    ir.Constant(i32, cap_idx)
                ], inbounds=True)
                final_args.append(self.builder.load(cap_ptr))
                cap_idx += 1

        # 加载函数指针并调用
        func_ptr = self.builder.gep(closure_arg, [
            ir.Constant(i32, 0),
            ir.Constant(i32, 0)
        ], inbounds=True)
        loaded_func = self.builder.load(func_ptr)

        if ret_type == ir.VoidType():
            self.builder.call(loaded_func, final_args)
            self.builder.ret_void()
        else:
            result = self.builder.call(loaded_func, final_args)
            self.builder.ret(result)

        # 恢复 builder 状态
        self.builder = old_builder
        self.locals = old_locals
        self._method_this = old_method_this

        # 返回闭包结构体指针（调用者可以将其作为函数指针使用）
        return closure

    # ==================== 二元运算 ====================

    def visitAdditiveExpression(self, ctx: EzLangParser.AdditiveExpressionContext):
        left = self._eval(ctx.multiplicativeExpression(0))
        for i in range(1, len(ctx.multiplicativeExpression())):
            right = self._eval(ctx.multiplicativeExpression(i))
            if left is None or right is None: continue
            # 通过遍历子节点找操作符
            is_sub = False
            for j in range(ctx.getChildCount()):
                if ctx.getChild(j).getText() == '-':
                    is_sub = True
                    break
            if self._is_float(left.type):
                left = self.builder.fsub(left, right) if is_sub else self.builder.fadd(left, right)
            else:
                left = self.builder.sub(left, right) if is_sub else self.builder.add(left, right)
        return left

    def visitMultiplicativeExpression(self, ctx: EzLangParser.MultiplicativeExpressionContext):
        left = self._eval(ctx.unaryExpression(0))
        for i in range(1, len(ctx.unaryExpression())):
            right = self._eval(ctx.unaryExpression(i))
            if left is None or right is None: continue
            op = '*'
            for j in range(ctx.getChildCount()):
                t = ctx.getChild(j).getText()
                if t in ('*', '/', '%'):
                    op = t
                    break
            if self._is_float(left.type):
                if op == '*': left = self.builder.fmul(left, right)
                elif op == '/': left = self.builder.fdiv(left, right)
            else:
                if op == '*': left = self.builder.mul(left, right)
                elif op == '/': left = self.builder.sdiv(left, right)
                elif op == '%': left = self.builder.srem(left, right)
        return left

    def visitEqualityExpression(self, ctx: EzLangParser.EqualityExpressionContext):
        left = self._eval(ctx.relationalExpression(0))
        for i in range(1, len(ctx.relationalExpression())):
            right = self._eval(ctx.relationalExpression(i))
            if left is None or right is None: continue
            op = '=='
            for j in range(ctx.getChildCount()):
                t = ctx.getChild(j).getText()
                if t in ('==', '!='):
                    op = t
                    break
            if self._is_float(left.type):
                left = self.builder.fcmp_ordered(op, left, right)
            else:
                left = self.builder.icmp_signed(op, left, right)
        return left

    def visitRelationalExpression(self, ctx: EzLangParser.RelationalExpressionContext):
        left = self._eval(ctx.shiftExpression(0))
        for i in range(1, len(ctx.shiftExpression())):
            right = self._eval(ctx.shiftExpression(i))
            if left is None or right is None: continue
            op = '<'
            for j in range(ctx.getChildCount()):
                t = ctx.getChild(j).getText()
                if t in ('<', '>', '<=', '>='):
                    op = t
                    break
            if self._is_float(left.type):
                left = self.builder.fcmp_ordered(op, left, right)
            else:
                left = self.builder.icmp_signed(op, left, right)
        return left

    # ==================== 位运算 ====================

    def visitShiftExpression(self, ctx: EzLangParser.ShiftExpressionContext):
        left = self._eval(ctx.additiveExpression(0))
        for i in range(1, len(ctx.additiveExpression())):
            right = self._eval(ctx.additiveExpression(i))
            if left is None or right is None: continue
            op = 'shl'
            for j in range(ctx.getChildCount()):
                t = ctx.getChild(j).getText()
                if t == '<<': op = 'shl'; break
                elif t == '>>': op = 'ashr'; break
            if op == 'shl':
                left = self.builder.shl(left, right)
            else:
                left = self.builder.ashr(left, right)
        return left

    def visitBitAndExpression(self, ctx: EzLangParser.BitAndExpressionContext):
        left = self._eval(ctx.equalityExpression(0))
        for i in range(1, len(ctx.equalityExpression())):
            right = self._eval(ctx.equalityExpression(i))
            if left is None or right is None: continue
            left = self.builder.and_(left, right)
        return left

    def visitBitXorExpression(self, ctx: EzLangParser.BitXorExpressionContext):
        left = self._eval(ctx.bitAndExpression(0))
        for i in range(1, len(ctx.bitAndExpression())):
            right = self._eval(ctx.bitAndExpression(i))
            if left is None or right is None: continue
            left = self.builder.xor(left, right)
        return left

    def visitBitOrExpression(self, ctx: EzLangParser.BitOrExpressionContext):
        left = self._eval(ctx.bitXorExpression(0))
        for i in range(1, len(ctx.bitXorExpression())):
            right = self._eval(ctx.bitXorExpression(i))
            if left is None or right is None: continue
            left = self.builder.or_(left, right)
        return left

    # ==================== 逻辑运算（短路求值）====================

    def _short_circuit(self, left, ctx_rhs_list, op: str):
        """短路求值辅助: op='and' | 'or'"""
        if self.builder is None:
            # 全局作用域不回退，直接返回 left
            return left
        if not ctx_rhs_list:
            return left

        b_false = ir.Constant(ir.IntType(1), 0)
        b_true = ir.Constant(ir.IntType(1), 1)

        for i, rhs_ctx in enumerate(ctx_rhs_list):
            rhs_bb = self.builder.append_basic_block(name=f"{op}_rhs")
            merge_bb = self.builder.append_basic_block(name=f"{op}_merge")

            if op == 'and':
                # left 为假 → 直接返回假，否则进入 rhs_bb
                skip_val = b_false
                self.builder.cbranch(left, rhs_bb, merge_bb)
            else:  # op == 'or'
                # left 为真 → 直接返回真，否则进入 rhs_bb
                skip_val = b_true
                self.builder.cbranch(left, merge_bb, rhs_bb)

            from_block = self.builder.block
            self.builder.position_at_start(rhs_bb)
            right = self._eval(rhs_ctx)
            rhs_block = self.builder.block
            self.builder.branch(merge_bb)

            self.builder.position_at_start(merge_bb)
            if right and left.type == right.type:
                phi = self.builder.phi(left.type)
                phi.add_incoming(skip_val, from_block)
                phi.add_incoming(right, rhs_block)
                left = phi
            else:
                left = right or skip_val

        return left

    def visitAndExpression(self, ctx: EzLangParser.AndExpressionContext):
        lhs_list = ctx.bitOrExpression()
        if len(lhs_list) == 0:
            return None
        left = self._eval(lhs_list[0])
        return self._short_circuit(left, lhs_list[1:], 'and')

    def visitOrExpression(self, ctx: EzLangParser.OrExpressionContext):
        lhs_list = ctx.andExpression()
        if len(lhs_list) == 0:
            return None
        left = self._eval(lhs_list[0])
        return self._short_circuit(left, lhs_list[1:], 'or')

    # ==================== 一元运算 ====================

    def visitUnaryExpression(self, ctx: EzLangParser.UnaryExpressionContext):
        # 后缀表达式（无一元运算符）
        if ctx.postfixExpression() is not None:
            return self._eval(ctx.postfixExpression())

        inner = self._eval(ctx.unaryExpression())
        if inner is None:
            return None

        if ctx.BANG() is not None:
            return self.builder.not_(inner)
        elif ctx.MINUS() is not None:
            if self._is_float(inner.type):
                return self.builder.fsub(ir.Constant(inner.type, 0.0), inner)
            return self.builder.sub(ir.Constant(inner.type, 0), inner)
        elif ctx.TILDE() is not None:
            return self.builder.not_(inner)
        elif ctx.PLUS() is not None:
            return inner
        return inner

    # 条件表达式（三元）
    # 管道表达式
    def visitPipelineExpression(self, ctx: EzLangParser.PipelineExpressionContext):
        """管道表达式: expr -> func(x = %) 或 expr -> func<T>(x = %) → func(x = expr)"""
        if ctx.THIN_ARROW() is None:
            return self._eval(ctx.conditionalExpression())

        # 求值管道左侧表达式
        pipe_val = self._eval(ctx.conditionalExpression())
        if pipe_val is None:
            return None

        # 获取函数名（考虑泛型参数：func<I32> → func_I32，触发单态化）
        func_name = ctx.VAR_IDENTIFIER().getText()
        generic_args = ctx.genericArgs()
        if generic_args is not None:
            type_args = [self._map_type(t) for t in generic_args.type_()]
            func_name = self._monomorphize(func_name, type_args)
        func = self.module.get_global(func_name)
        if func is None or not isinstance(func, ir.Function):
            return None

        # 构建参数：% 占位符替换为管道左侧的值
        call_args = []
        has_percent = False
        arg_list = ctx.pipelineArgList()
        if arg_list is not None:
            for a in arg_list.pipelineArg():
                if a.PERCENT() is not None:
                    call_args.append(pipe_val)
                    has_percent = True
                elif a.expression() is not None:
                    val = self._eval(a.expression())
                    call_args.append(val if val is not None else ir.Constant(ir.IntType(32), 0))
        # 如果没有显式的 % 占位符，管道值作为第一个参数
        if not has_percent:
            call_args.insert(0, pipe_val)

        return self.builder.call(func, call_args)

    # 条件表达式（三元）
    def visitConditionalExpression(self, ctx: EzLangParser.ConditionalExpressionContext):
        if ctx.QUESTION() is None:
            return self._eval(ctx.rangeExpression())

        cond = self._eval(ctx.rangeExpression())
        if cond is None:
            return None

        then_bb = self.builder.append_basic_block(name="then")
        else_bb = self.builder.append_basic_block(name="else")
        merge_bb = self.builder.append_basic_block(name="merge")

        self.builder.cbranch(cond, then_bb, else_bb)

        self.builder.position_at_start(then_bb)
        cond_exprs = ctx.conditionalExpression()
        if hasattr(cond_exprs, '__len__') and len(cond_exprs) > 0:
            then_val = self._eval(cond_exprs[0])
        else:
            then_val = self._eval(cond_exprs)
        then_block = self.builder.block
        if not then_block.is_terminated:
            self.builder.branch(merge_bb)

        self.builder.position_at_start(else_bb)
        if hasattr(cond_exprs, '__len__') and len(cond_exprs) > 1:
            else_val = self._eval(cond_exprs[1])
        else:
            else_val = ir.Constant(ir.IntType(32), 0)
        else_block = self.builder.block
        if not else_block.is_terminated:
            self.builder.branch(merge_bb)

        self.builder.position_at_start(merge_bb)
        if then_val and else_val and then_val.type == else_val.type:
            phi = self.builder.phi(then_val.type)
            phi.add_incoming(then_val, then_block)
            phi.add_incoming(else_val, else_block)
            return phi
        return then_val

    # 表达式入口
    def visitExpression(self, ctx: EzLangParser.ExpressionContext):
        return self._eval(ctx.assignmentExpression())

    # 赋值
    def visitAssignmentExpression(self, ctx: EzLangParser.AssignmentExpressionContext):
        if ctx.assignmentOperator() is None:
            return self._eval(ctx.pipelineExpression())

        left = ctx.pipelineExpression()
        name = None
        if hasattr(left, 'identifierExpr') and left.identifierExpr():
            id_token = left.identifierExpr().VAR_IDENTIFIER() or left.identifierExpr().TYPE_IDENTIFIER()
            name = id_token.getText()

        val = None
        if ctx.assignmentExpression():
            val = self._eval(ctx.assignmentExpression())

        if name and val:
            # 如果值是 alloca（结构体字面量），需要 load
            store_val = val
            if isinstance(val, ir.AllocaInstr):
                store_val = self.builder.load(val)
            if name in self.locals:
                self.builder.store(store_val, self.locals[name])
            elif name in self.globals:
                self.builder.store(store_val, self.globals[name])

        return val

    # ==================== 语句 ====================

    def visitExpressionStatement(self, ctx: EzLangParser.ExpressionStatementContext):
        if ctx.expression():
            return self._eval(ctx.expression())
        return None

    def visitReturnStatement(self, ctx: EzLangParser.ReturnStatementContext):
        if ctx.expression():
            val = self._eval(ctx.expression())
            if val is not None:
                # 聚合类型指针需要 load 后才能 ret（alloca 和 arena 都是指针）
                if self._is_aggregate_ptr(val):
                    val = self.builder.load(val)
                self.builder.ret(val)
            else:
                self.builder.ret_void()
        else:
            self.builder.ret_void()
        return None

    def visitBlock(self, ctx: EzLangParser.BlockContext):
        # Arena 作用域管理：进入时保存游标，退出时恢复
        saved_pos = None
        if self.builder and hasattr(self, '_arena_save'):
            saved_pos = self.builder.call(self._arena_save, [], name='_arena_saved')
        for stmt in ctx.statement():
            self._eval(stmt)
            if self.builder.block.is_terminated:
                return None
        if saved_pos is not None:
            self.builder.call(self._arena_restore, [saved_pos])
        return None

    # ==================== 循环与跳转 ====================

    def visitLoopExpr(self, ctx: EzLangParser.LoopExprContext):
        """loop { ... } 或 loop i in start...end { ... }"""
        if self.builder is None:
            return None

        body_ctx = ctx.block()
        if body_ctx is None:
            return None

        # 是否范围循环
        has_range = ctx.IN() is not None and ctx.VAR_IDENTIFIER() is not None

        # 基本块
        loop_header_bb = self.builder.append_basic_block(name="loop_header")
        loop_body_bb = self.builder.append_basic_block(name="loop_body")
        loop_exit_bb = self.builder.append_basic_block(name="loop_exit")

        if has_range:
            # 范围循环: loop i in start...end { ... }
            var_name = ctx.VAR_IDENTIFIER().getText()
            range_ctx = ctx.rangeExpression()
            range_exprs = range_ctx.orExpression()
            start_val = self._eval(range_exprs[0])
            end_val = self._eval(range_exprs[1]) if len(range_exprs) > 1 else ir.Constant(ir.IntType(32), 0)

            # 循环变量 alloca
            loop_var = self.builder.alloca(ir.IntType(32), name=var_name)
            self.builder.store(start_val, loop_var)
            self.locals[var_name] = loop_var

            loop_step_bb = self.builder.append_basic_block(name="loop_step")

            # 跳转到 header
            self.builder.branch(loop_header_bb)

            # header: 检查条件 i < end
            self.builder.position_at_start(loop_header_bb)
            i_val = self.builder.load(loop_var, name=var_name)
            cond = self.builder.icmp_signed('<', i_val, end_val)
            self.builder.cbranch(cond, loop_body_bb, loop_exit_bb)

            # body
            self.builder.position_at_start(loop_body_bb)
            self.loop_exit_blocks.append(loop_exit_bb)
            self.loop_continue_blocks.append(loop_step_bb)
            self._eval(body_ctx)
            self.loop_exit_blocks.pop()
            self.loop_continue_blocks.pop()
            if not self.builder.block.is_terminated:
                self.builder.branch(loop_step_bb)

            # step: i = i + 1
            self.builder.position_at_start(loop_step_bb)
            i_val = self.builder.load(loop_var, name=var_name)
            next_val = self.builder.add(i_val, ir.Constant(ir.IntType(32), 1))
            self.builder.store(next_val, loop_var)
            self.builder.branch(loop_header_bb)

            # 还原
            self.locals.pop(var_name, None)
        else:
            # 无限循环: loop { ... }
            self.builder.branch(loop_header_bb)

            self.builder.position_at_start(loop_header_bb)
            self.builder.branch(loop_body_bb)

            self.builder.position_at_start(loop_body_bb)
            self.loop_exit_blocks.append(loop_exit_bb)
            self.loop_continue_blocks.append(loop_header_bb)
            self._eval(body_ctx)
            self.loop_exit_blocks.pop()
            self.loop_continue_blocks.pop()
            if not self.builder.block.is_terminated:
                self.builder.branch(loop_header_bb)

        # 出口
        self.builder.position_at_start(loop_exit_bb)
        return None

    def visitLoopPrimaryExpr(self, ctx: EzLangParser.LoopPrimaryExprContext):
        return self.visitLoopExpr(ctx.loopExpr())

    def visitBreakStatement(self, ctx: EzLangParser.BreakStatementContext):
        if self.loop_exit_blocks:
            self.builder.branch(self.loop_exit_blocks[-1])
        return None

    def visitContinueStatement(self, ctx: EzLangParser.ContinueStatementContext):
        if self.loop_continue_blocks:
            self.builder.branch(self.loop_continue_blocks[-1])
        return None

    # ==================== match 模式匹配 ====================

    def visitMatchBlock(self, ctx: EzLangParser.MatchBlockContext):
        """match { (pat) ? body, (pat) ? body, ... } → if-else 链"""
        if self.builder is None:
            return None

        clauses = ctx.matchClause()
        if not clauses:
            return None

        merge_bb = self.builder.append_basic_block(name="match_merge")

        for i, clause in enumerate(ctx.matchClause()):
            is_last = (i == len(clauses) - 1)
            cond = self._eval(clause.expression())

            if is_last:
                # 最后一个子句：如果条件为真则进 body，否则到 merge
                body_bb = self.builder.append_basic_block(name="match_last")
                self.builder.cbranch(cond, body_bb, merge_bb)
                self.builder.position_at_start(body_bb)
            else:
                next_bb = self.builder.append_basic_block(name="match_next")
                body_bb = self.builder.append_basic_block(name="match_body")
                self.builder.cbranch(cond, body_bb, next_bb)
                self.builder.position_at_start(body_bb)

            # 执行子句体
            if clause.statement() is not None:
                self._eval(clause.statement())
            elif clause.block() is not None:
                self._eval(clause.block())

            if not self.builder.block.is_terminated:
                self.builder.branch(merge_bb)

            if not is_last:
                self.builder.position_at_start(next_bb)

        self.builder.position_at_start(merge_bb)
        return None

    def visitMatchBlockExpr(self, ctx: EzLangParser.MatchBlockExprContext):
        return self.visitMatchBlock(ctx.matchBlock())

    # ==================== throw / catch 异常处理 ====================

    def visitCatchBlock(self, ctx: EzLangParser.CatchBlockContext):
        """catch { ... } 异常捕获块"""
        if self.builder is None:
            return None

        # 创建错误状态 alloca（存储抛出的错误值）
        error_alloca = self.builder.alloca(ir.PointerType(ir.IntType(8)), name="_catch_err")
        null_ptr = ir.Constant(ir.PointerType(ir.IntType(8)), None)
        self.builder.store(null_ptr, error_alloca)

        catch_exit_bb = self.builder.append_basic_block(name="catch_exit")

        self.catch_exit_blocks.append(catch_exit_bb)
        self.catch_error_allocas.append(error_alloca)

        # 执行 catch 体内的代码
        if ctx.block() is not None:
            self._eval(ctx.block())

        self.catch_exit_blocks.pop()
        self.catch_error_allocas.pop()

        # 跳转到出口
        if not self.builder.block.is_terminated:
            self.builder.branch(catch_exit_bb)

        self.builder.position_at_start(catch_exit_bb)
        return None

    def visitCatchBlockExpr(self, ctx: EzLangParser.CatchBlockExprContext):
        return self.visitCatchBlock(ctx.catchBlock())

    def visitThrowStatement(self, ctx: EzLangParser.ThrowStatementContext):
        """throw expr → 存储错误标记并跳转到 catch_exit"""
        if self.catch_error_allocas:
            # 存储非空标记（i8 1 转为指针）表示发生了异常
            sentinel = ir.Constant(ir.IntType(64), 1).inttoptr(
                ir.PointerType(ir.IntType(8)))
            self.builder.store(sentinel, self.catch_error_allocas[-1])

        if self.catch_exit_blocks:
            self.builder.branch(self.catch_exit_blocks[-1])
        return None

    # ==================== 类 if 表达式 ====================

    def visitIfLikeExpr(self, ctx: EzLangParser.IfLikeExprContext):
        """(cond) ? expr : expr 或 (cond) ? { block } : { block }"""
        if self.builder is None:
            return None

        # 条件
        cond = self._eval(ctx.expression(0))
        if cond is None:
            return None

        then_bb = self.builder.append_basic_block(name="if_then")
        else_bb = self.builder.append_basic_block(name="if_else")
        merge_bb = self.builder.append_basic_block(name="if_merge")

        self.builder.cbranch(cond, then_bb, else_bb)

        # then 分支
        self.builder.position_at_start(then_bb)
        then_val = None
        if ctx.expression(1) is not None:
            then_val = self._eval(ctx.expression(1))
        elif ctx.block(0) is not None:
            self._eval(ctx.block(0))
        then_block = self.builder.block
        if not then_block.is_terminated:
            self.builder.branch(merge_bb)

        # else 分支
        self.builder.position_at_start(else_bb)
        else_val = None
        if ctx.expression(2) is not None:
            else_val = self._eval(ctx.expression(2))
        elif ctx.block(1) is not None:
            self._eval(ctx.block(1))
        else_block = self.builder.block
        if not else_block.is_terminated:
            self.builder.branch(merge_bb)

        # 合并
        self.builder.position_at_start(merge_bb)
        if then_val and else_val and then_val.type == else_val.type:
            phi = self.builder.phi(then_val.type)
            phi.add_incoming(then_val, then_block)
            phi.add_incoming(else_val, else_block)
            return phi
        return then_val or else_val

    def visitIfLikePrimaryExpr(self, ctx: EzLangParser.IfLikePrimaryExprContext):
        return self.visitIfLikeExpr(ctx.ifLikeExpr())

    # ==================== 默认 ====================

    def defaultResult(self):
        return None


def compile_source(source: str, module_name: str = "ezlang", compile_target: Optional[str] = None):
    """编译 EzLang 源码 → (LLVM Module, 解析错误, extern 库列表)"""
    from antlr4 import InputStream, CommonTokenStream
    from parser.EzLangLexer import EzLangLexer
    from parser.EzLangParser import EzLangParser as Parser

    _parse_errors.clear()
    lexer = EzLangLexer(InputStream(source))
    stream = CommonTokenStream(lexer)
    parser = Parser(stream)
    parser.addErrorListener(_ErrorCollector())
    tree = parser.compilationUnit()
    if _parse_errors:
        return ir.Module(name=module_name), list(_parse_errors), []

    codegen = LLVMCodeGenerator(module_name, compile_target=compile_target)
    codegen.visitCompilationUnit(tree)
    errors = list(_parse_errors) + codegen._extern_diagnostics
    libs = codegen.active_extern_libs if compile_target is not None else codegen.extern_libs
    return codegen.module, errors, libs


_parse_errors: list[str] = []


class _ErrorCollector:
    @staticmethod
    def syntaxError(recognizer, offendingSymbol, line, column, msg, e):
        token_text = getattr(offendingSymbol, 'text', '') or ''
        detail = f"语法错误 {line}:{column}: {msg}"
        if token_text:
            detail += f"，附近 token: '{token_text}'"
        detail += "。建议：检查分号、括号、逗号和语法结构是否完整"
        _parse_errors.append(detail)

    @staticmethod
    def reportAmbiguity(recognizer, dfa, startIndex, stopIndex, exact, ambigAlts, configs):
        pass

    @staticmethod
    def reportAttemptingFullContext(recognizer, dfa, startIndex, stopIndex, conflictingAlts, configs):
        pass

    @staticmethod
    def reportContextSensitivity(recognizer, dfa, startIndex, stopIndex, prediction, configs):
        pass
