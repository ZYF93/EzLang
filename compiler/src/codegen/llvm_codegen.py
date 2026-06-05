"""EzLang LLVM IR 代码生成器"""

from typing import Optional
from pathlib import Path
import re
from llvmlite import ir
from parser.EzLangParser import EzLangParser
from parser.EzLangVisitor import EzLangVisitor


class LLVMCodeGenerator(EzLangVisitor):
    """LLVM IR 代码生成访问器"""

    def __init__(self, module_name: str = "ezlang", compile_target: Optional[str] = None,
                 target_arch: Optional[str] = None, log_compile_min_level: Optional[int] = None):
        self.module = ir.Module(name=module_name)
        self.compile_target = compile_target
        self.target_arch = target_arch
        self.log_compile_min_level = log_compile_min_level
        self.builder: ir.IRBuilder = None
        self.current_function: ir.Function = None
        self._method_this: ir.Value = None
        self.locals: dict[str, ir.AllocaInstr] = {}
        self.globals: dict[str, ir.GlobalVariable] = {}
        self._ptr_unsigned: dict[int, bool] = {}
        self._value_unsigned: dict[int, bool] = {}
        self._struct_field_unsigned: dict[str, list[bool]] = {}
        self._list_elem_unsigned: dict[int, bool] = {}
        self.loop_exit_blocks: list[ir.Block] = []
        self.loop_continue_blocks: list[ir.Block] = []
        self.catch_exit_blocks: list[ir.Block] = []
        self.catch_error_allocas: list[ir.AllocaInstr] = []
        self.catch_result_allocas: list[ir.AllocaInstr] = []
        self._function_throw_exit_stack: list[ir.Block] = []
        self._function_return_type_ctx_stack: list[object] = []
        self.structs: dict[str, ir.IdentifiedStructType] = {}
        self.struct_fields: dict[str, list[str]] = {}
        self.struct_defaults: dict[str, dict[str, any]] = {}  # struct_name → {field_name: expression_ctx}
        self.struct_methods: dict[str, dict[str, str]] = {}
        self.struct_generic_params: dict[str, list[str]] = {}
        self.struct_generic_templates: dict[str, object] = {}
        self._struct_monomorphized: set[str] = set()
        self.type_aliases: dict[str, ir.Type] = {}
        self.func_defaults: dict[str, dict[str, ir.Value]] = {}
        self.func_param_names: dict[str, list[str]] = {}
        self.func_return_unsigned: dict[str, bool] = {}
        self.func_return_dict_types: dict[str, tuple[ir.Type, ir.Type]] = {}
        self.generic_templates: dict[str, tuple] = {}
        self._monomorphized: set[str] = set()
        self._generic_type_map_stack: list[dict[str, ir.Type]] = []
        self._mapping_with_map = False
        self.extern_libs: list[tuple[str, Optional[str]]] = []  # (lib_path, target)
        self.active_extern_libs: list[str] = []
        self._extern_diagnostics: list[str] = []
        self._declare_names: list[str] = []
        self._sret_functions: dict[str, ir.Type] = {}
        self._c_abi_return_bridges: dict[str, tuple[ir.Type, ir.Type]] = {}
        self._non_extern_decls_seen = 0
        self._list_collection_builtins = {
            'listPush', 'listPop', 'listShift', 'listUnshift', 'listSort',
            'listFilter', 'listMap', 'listFind', 'listLen', 'listSlice',
        }
        self._dict_collection_builtins = {
            'dictKeys', 'dictValues', 'dictHas', 'dictDelete', 'dictLen',
        }
        self._collection_builtin_declares = self._list_collection_builtins | self._dict_collection_builtins
        self._compiler_builtin_declares = {'copy', 'set', 'allocRaw'} | self._collection_builtin_declares
        self._unimplemented_collection_declares = set()
        self._collection_mono_types: dict[str, tuple[str, list[ir.Type]]] = {}
        self._emcc_js_libs: list[str] = []
        self._emcc_binding_counter = 0
        self._supported_extern_exts = {".a", ".lib", ".so", ".dylib", ".dll", ".o", ".ll", ".bc", ".framework", ".js", ".c"}
        self._void_intrinsic_result = object()
        self._str_counter: int = 0  # 字符串全局变量唯一 ID
        self._type_width_cache: dict[str, int] = {}
        self._type_align_cache: dict[str, int] = {}
        self._zero_constant_cache: dict[str, ir.Constant] = {}
        self._type_ids: dict[str, int] = {}
        self._runtime_required = False
        self._race_branch_counter = 0
        self._flow_future_stack: list[dict[str, dict[str, ir.Value]]] = []
        self._flow_depth = 0
        self._parallel_result_stack: list[ir.AllocaInstr] = []
        self._parallel_exit_stack: list[ir.Block] = []
        self._parallel_arena_depth_stack: list[int] = []
        self._arena_scope_stack: list[ir.Value] = []
        self._lock_policies: dict[str, int] = {}
        self._uncaught_throw: ir.Function | None = None
        self._throw_active: ir.GlobalVariable | None = None
        self._throw_value: ir.GlobalVariable | None = None
        self._curried_closures: dict[str, tuple[ir.Function, list[str]]] = {}
        self._locals_type_names: dict[str, str] = {}
        self._globals_type_names: dict[str, str] = {}
        self._dict_item_types: dict[int, tuple[ir.Type, ir.Type]] = {}
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
        self._flow_enter = self._define_runtime_void_hook('__ezrt_flow_enter', flow_hook_type)
        self._flow_exit = self._define_runtime_void_hook('__ezrt_flow_exit', flow_hook_type)
        self._flow_sleep = self._define_sleep_hook('__ezrt_sleep', ir.FunctionType(void, [i64]))
        self._flow_race = self._define_runtime_race_hook('__ezrt_race', ir.FunctionType(i32, [i32, i32]))
        self._parallel_enter = self._define_runtime_void_hook('__ezrt_parallel_enter', flow_hook_type)
        self._parallel_exit = self._define_runtime_void_hook('__ezrt_parallel_exit', flow_hook_type)
        self._lock_register = self._define_runtime_void_hook('__ezrt_lock_register', ir.FunctionType(void, [i8_ptr, i32]))
        self._lock_read_acquire = self._define_runtime_void_hook('__ezrt_lock_read_acquire', ir.FunctionType(void, [i8_ptr]))
        self._lock_read_release = self._define_runtime_void_hook('__ezrt_lock_read_release', ir.FunctionType(void, [i8_ptr]))
        self._lock_write_acquire = self._define_runtime_void_hook('__ezrt_lock_write_acquire', ir.FunctionType(void, [i8_ptr]))
        self._lock_write_release = self._define_runtime_void_hook('__ezrt_lock_write_release', ir.FunctionType(void, [i8_ptr]))

        # 内置结构体: Error = { i32 code, i8* message }
        err_type = ir.global_context.get_identified_type('Error')
        if err_type.is_opaque:
            err_type.set_body(i32, i8_ptr)
        self.structs['Error'] = err_type
        self.struct_fields['Error'] = ['code', 'message']
        self._declare_throw_state(err_type)

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

    def _define_runtime_void_hook(self, name: str, func_type: ir.FunctionType) -> ir.Function:
        """定义最小运行时 hook，避免本机链接时遗留未定义符号。"""
        func = ir.Function(self.module, func_type, name)
        entry = func.append_basic_block('entry')
        builder = ir.IRBuilder(entry)
        builder.ret_void()
        return func

    def _define_runtime_race_hook(self, name: str, func_type: ir.FunctionType) -> ir.Function:
        """当前同步 lowering 下的 race hook：返回任务参数作为占位结果。"""
        func = ir.Function(self.module, func_type, name)
        entry = func.append_basic_block('entry')
        builder = ir.IRBuilder(entry)
        builder.ret(func.args[0])
        return func

    def _define_sleep_hook(self, name: str, func_type: ir.FunctionType) -> ir.Function:
        """flow 内 sleep suspend point；本机目标映射到 usleep 保留可验证挂起。"""
        func = ir.Function(self.module, func_type, name)
        entry = func.append_basic_block('entry')
        builder = ir.IRBuilder(entry)
        usleep_fn = self._get_or_declare_function('usleep', ir.FunctionType(ir.IntType(32), [ir.IntType(32)]))
        ms = func.args[0]
        ms32 = builder.trunc(ms, ir.IntType(32)) if isinstance(ms.type, ir.IntType) and ms.type.width > 32 else ms
        micros = builder.mul(ms32, ir.Constant(ir.IntType(32), 1000), name='_sleep_us')
        builder.call(usleep_fn, [micros])
        builder.ret_void()
        return func

    def _runtime_lib_path(self) -> str:
        root = Path(__file__).resolve().parents[3]
        return str((root / 'packages' / 'std' / 'native' / 'runtime.c').resolve())

    def _require_runtime(self) -> None:
        """标记需要链接语言运行时 C helper。"""
        self._runtime_required = True
        path = self._runtime_lib_path()
        if path not in self.active_extern_libs:
            self.active_extern_libs.append(path)
        if self.compile_target != 'windows' and 'pthread' not in self.active_extern_libs:
            self.active_extern_libs.append('pthread')
        if (path, None) not in self.extern_libs:
            self.extern_libs.append((path, None))
        if ('pthread', None) not in self.extern_libs and self.compile_target != 'windows':
            self.extern_libs.append(('pthread', None))

    def _get_or_declare_function(self, name: str, func_type: ir.FunctionType) -> ir.Function:
        existing = self.module.globals.get(name)
        if isinstance(existing, ir.Function):
            return existing
        return ir.Function(self.module, func_type, name)

    def _define_uncaught_throw_hook(self) -> ir.Function:
        """未捕获 throw 的最小终止路径。"""
        if self._uncaught_throw is not None:
            return self._uncaught_throw
        void = ir.VoidType()
        i8_ptr = ir.PointerType(ir.IntType(8))
        i32 = ir.IntType(32)
        func = ir.Function(self.module, ir.FunctionType(void, []), '__ezrt_uncaught_throw')
        entry = func.append_basic_block('entry')
        builder = ir.IRBuilder(entry)

        puts_fn = self._get_or_declare_function('puts', ir.FunctionType(i32, [i8_ptr]))
        exit_fn = self._get_or_declare_function('exit', ir.FunctionType(void, [i32]))
        data = bytearray('uncaught EzLang throw\0', 'utf-8')
        arr_type = ir.ArrayType(ir.IntType(8), len(data))
        msg = ir.GlobalVariable(self.module, arr_type, '_ez_uncaught_throw_msg')
        msg.initializer = ir.Constant(arr_type, data)
        msg.global_constant = True
        msg.linkage = 'internal'
        msg_ptr = builder.gep(msg, [
            ir.Constant(i32, 0),
            ir.Constant(i32, 0),
        ], inbounds=True)
        builder.call(puts_fn, [msg_ptr])
        builder.call(exit_fn, [ir.Constant(i32, 1)])
        builder.unreachable()
        self._uncaught_throw = func
        return func

    def _declare_throw_state(self, err_type: ir.IdentifiedStructType):
        """声明模块内异常槽，供同步函数调用边界传播 Error。"""
        active = ir.GlobalVariable(self.module, ir.IntType(1), '__ezrt_throw_active')
        active.linkage = 'internal'
        active.initializer = ir.Constant(ir.IntType(1), 0)
        value = ir.GlobalVariable(self.module, err_type, '__ezrt_throw_value')
        value.linkage = 'internal'
        value.initializer = self._zero_constant(err_type)
        self._throw_active = active
        self._throw_value = value

    def _throw_is_active(self) -> ir.Value:
        return self.builder.load(self._throw_active, name='_throw_active')

    def _clear_throw_state(self):
        self.builder.store(ir.Constant(ir.IntType(1), 0), self._throw_active)

    def _store_throw_value(self, value: ir.Value | None):
        if value is None:
            value = self._zero_constant(self.structs['Error'])
        if self._is_aggregate_ptr(value):
            value = self.builder.load(value)
        value = self._coerce_value(value, self.structs['Error'])
        self.builder.store(value, self._throw_value)
        self.builder.store(ir.Constant(ir.IntType(1), 1), self._throw_active)

    def _branch_to_throw_exit_or_abort(self):
        if self.catch_exit_blocks:
            self.builder.branch(self.catch_exit_blocks[-1])
            return
        if self._function_throw_exit_stack:
            self.builder.branch(self._function_throw_exit_stack[-1])
            return
        self.builder.call(self._define_uncaught_throw_hook(), [])
        self.builder.unreachable()

    def _emit_throw_check_after_call(self):
        if self.builder is None or self.builder.block.is_terminated:
            return
        active = self._throw_is_active()
        throw_bb = self.builder.append_basic_block('call_throw')
        cont_bb = self.builder.append_basic_block('call_continue')
        self.builder.cbranch(active, throw_bb, cont_bb)
        self.builder.position_at_start(throw_bb)
        self._branch_to_throw_exit_or_abort()
        self.builder.position_at_start(cont_bb)

    def _finish_function_with_throw_exit(self, ret_type: ir.Type, result: ir.Value | None = None):
        """补全普通出口和异常出口；异常出口返回零值，由调用边界继续传播。"""
        normal_block = self.builder.block if self.builder is not None else None
        throw_exit = self._function_throw_exit_stack.pop()

        if normal_block is not None and not normal_block.is_terminated:
            if isinstance(ret_type, ir.VoidType):
                self.builder.ret_void()
            elif isinstance(result, ir.Value) and not isinstance(result.type, ir.VoidType):
                if self._is_aggregate_ptr(result):
                    result = self.builder.load(result)
                if result.type != ret_type:
                    result = self._coerce_return_value(result, ret_type)
                self._restore_active_arena_scopes_for_return(result, ret_type)
                self.builder.ret(result)
            else:
                self._restore_active_arena_scopes_for_return(ret_type=ret_type)
                self.builder.ret(self._zero_constant(ret_type))

        if not throw_exit.is_terminated:
            self.builder.position_at_start(throw_exit)
            if self.current_function is not None and self.current_function.name == 'main':
                self.builder.call(self._define_uncaught_throw_hook(), [])
                self.builder.unreachable()
                return
            if isinstance(ret_type, ir.VoidType):
                self.builder.ret_void()
            else:
                self.builder.ret(self._zero_constant(ret_type))

    def _declare_arena(self):
        """声明 Arena 内存管理基础设施：线程本地缓冲区 + 游标 + 可扩容分配函数"""
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        void = ir.VoidType()

        # Arena 缓冲区指针与容量。每个线程持有独立游标，满足 flow/parallel 的基础隔离语义。
        arena_buf = ir.GlobalVariable(self.module, i8_ptr, '__arena_buffer')
        arena_buf.initializer = ir.Constant(i8_ptr, None)
        arena_buf.linkage = 'internal'
        arena_buf.storage_class = 'thread_local'

        arena_capacity = ir.GlobalVariable(self.module, i64, '__arena_capacity')
        arena_capacity.initializer = ir.Constant(i64, 0)
        arena_capacity.linkage = 'internal'
        arena_capacity.storage_class = 'thread_local'

        # Arena 游标（当前分配位置）
        arena_cursor = ir.GlobalVariable(self.module, i64, '__arena_cursor')
        arena_cursor.initializer = ir.Constant(i64, 0)
        arena_cursor.linkage = 'internal'
        arena_cursor.storage_class = 'thread_local'

        realloc_type = ir.FunctionType(i8_ptr, [i8_ptr, i64])
        realloc_fn = ir.Function(self.module, realloc_type, 'realloc')
        trap_fn = ir.Function(self.module, ir.FunctionType(void, []), 'llvm.trap')

        # __arena_alloc(size: i64, align: i64) -> i8*
        func_type = ir.FunctionType(i8_ptr, [i64, i64])
        arena_alloc = ir.Function(self.module, func_type, '__arena_alloc')
        entry = arena_alloc.append_basic_block('entry')
        grow_check = arena_alloc.append_basic_block('grow_check')
        grow_loop = arena_alloc.append_basic_block('grow_loop')
        grow_done = arena_alloc.append_basic_block('grow_done')
        oom = arena_alloc.append_basic_block('oom')
        ok = arena_alloc.append_basic_block('ok')
        builder = ir.IRBuilder(entry)
        size = arena_alloc.args[0]
        align = arena_alloc.args[1]

        # 加载当前游标并对齐: aligned = (cursor + align - 1) & ~(align - 1)
        cursor = builder.load(arena_cursor, name='cursor')
        align_minus_1 = builder.sub(align, ir.Constant(i64, 1))
        misaligned = builder.add(cursor, align_minus_1)
        mask = builder.xor(align_minus_1, ir.Constant(i64, -1))
        aligned = builder.and_(misaligned, mask)
        # 新游标位置
        next_pos = builder.add(aligned, size)
        capacity = builder.load(arena_capacity, name='arena_capacity')
        existing_buf = builder.load(arena_buf, name='arena_buffer_existing')
        fits = builder.icmp_unsigned('<=', next_pos, capacity, name='arena_fits')
        builder.cbranch(fits, ok, grow_check)

        # 容量不足时按 2 倍增长，至少扩到当前需求；realloc 失败时 trap。
        builder.position_at_start(grow_check)
        old_capacity = builder.load(arena_capacity, name='old_arena_capacity')
        has_capacity = builder.icmp_unsigned('>', old_capacity, ir.Constant(i64, 0), name='arena_has_capacity')
        initial_capacity = builder.select(has_capacity, old_capacity, ir.Constant(i64, 1048576), name='arena_initial_capacity')
        enough_initial = builder.icmp_unsigned('>=', initial_capacity, next_pos, name='arena_initial_enough')
        builder.cbranch(enough_initial, grow_done, grow_loop)

        builder.position_at_start(grow_loop)
        current_capacity = builder.phi(i64, name='arena_grow_capacity')
        current_capacity.add_incoming(initial_capacity, grow_check)
        doubled_capacity = builder.shl(current_capacity, ir.Constant(i64, 1), name='arena_doubled_capacity')
        overflowed = builder.icmp_unsigned('<', doubled_capacity, current_capacity, name='arena_capacity_overflow')
        next_capacity = builder.select(overflowed, next_pos, doubled_capacity, name='arena_next_capacity')
        enough_next = builder.icmp_unsigned('>=', next_capacity, next_pos, name='arena_next_enough')
        current_capacity.add_incoming(next_capacity, grow_loop)
        builder.cbranch(enough_next, grow_done, grow_loop)

        builder.position_at_start(grow_done)
        target_capacity = builder.phi(i64, name='arena_target_capacity')
        target_capacity.add_incoming(initial_capacity, grow_check)
        target_capacity.add_incoming(next_capacity, grow_loop)
        old_buf = builder.load(arena_buf, name='old_arena_buffer')
        new_buf = builder.call(realloc_fn, [old_buf, target_capacity], name='new_arena_buffer')
        realloc_ok = builder.icmp_unsigned('!=', new_buf, ir.Constant(i8_ptr, None), name='arena_realloc_ok')
        builder.cbranch(realloc_ok, ok, oom)

        builder.position_at_start(oom)
        builder.call(trap_fn, [])
        builder.unreachable()

        builder.position_at_start(ok)
        active_buf = builder.phi(i8_ptr, name='arena_active_buffer')
        active_buf.add_incoming(existing_buf, entry)
        active_buf.add_incoming(new_buf, grow_done)
        active_capacity = builder.phi(i64, name='arena_active_capacity')
        active_capacity.add_incoming(capacity, entry)
        active_capacity.add_incoming(target_capacity, grow_done)
        builder.store(active_buf, arena_buf)
        builder.store(active_capacity, arena_capacity)
        builder.store(next_pos, arena_cursor)
        # 返回缓冲区中偏移后的指针。
        result = builder.gep(active_buf, [aligned], name='arena_ptr')
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
        self._arena_capacity = arena_capacity
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

    @staticmethod
    def _is_optional_type(t: ir.Type) -> bool:
        return isinstance(t, ir.LiteralStructType) and len(t.elements) == 2 and t.elements[0] == ir.IntType(1)

    @staticmethod
    def _is_union_type(t: ir.Type) -> bool:
        return isinstance(t, ir.LiteralStructType) and len(t.elements) == 2 and isinstance(t.elements[0], ir.IntType) and t.elements[0].width == 32

    def _load_if_aggregate_ptr(self, val: ir.Value) -> ir.Value:
        """如果 val 是聚合类型的指针，load 它；否则原样返回"""
        if self._is_aggregate_ptr(val) and self.builder is not None:
            return self.builder.load(val)
        return val

    def _copy_aggregate_value(self, val: ir.Value, name: str = "") -> ir.Value:
        """复制聚合值，避免普通变量共享同一块结构体/数组存储。"""
        if not self._is_aggregate_ptr(val) or self.builder is None:
            return val
        pointee = val.type.pointee
        if self._is_list_type(pointee):
            return self._copy_list_value(val, name=name)
        if pointee == self.structs.get('Dict'):
            return self._copy_dict_value(val, name=name)
        value = self.builder.load(val)
        ptr = self._arena_allocate(value.type, name=name)
        self.builder.store(value, ptr)
        return ptr

    def _copy_list_value(self, src_ptr: ir.Value, name: str = "") -> ir.Value:
        """复制 List/数组分页存储，避免两个变量共享元素页。"""
        i64 = ir.IntType(64)
        elem_type = self._list_elem_type(src_ptr)
        length = self._list_length(src_ptr)
        dst_ptr = self._list_new(elem_type, length)
        if name:
            dst_ptr.name = name

        index_ptr = self.builder.alloca(i64, name='_list_value_copy_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        cond_block = self.builder.append_basic_block('list_value_copy_cond')
        body_block = self.builder.append_basic_block('list_value_copy_body')
        done_block = self.builder.append_basic_block('list_value_copy_done')
        self.builder.branch(cond_block)

        self.builder.position_at_start(cond_block)
        index = self.builder.load(index_ptr, name='_list_value_copy_i_val')
        more = self.builder.icmp_unsigned('<', index, length, name='_list_value_copy_more')
        self.builder.cbranch(more, body_block, done_block)

        self.builder.position_at_start(body_block)
        item = self.builder.load(self._list_element_ptr(src_ptr, index), name='_list_value_copy_item')
        self.builder.store(item, self._list_element_ptr(dst_ptr, index))
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(cond_block)

        self.builder.position_at_start(done_block)
        self._mark_list_elem_unsigned(dst_ptr, self._list_type_is_unsigned(src_ptr.type))
        return dst_ptr

    def _copy_dict_value(self, src_ptr: ir.Value, name: str = "") -> ir.Value:
        """复制 Dict 分页存储，避免两个变量共享 key/value 页。"""
        i32 = ir.IntType(32)
        dict_type = self.structs['Dict']
        dst_ptr = self._arena_allocate(dict_type, name=name or '_tmp_dict_copy')
        self.builder.store(self._zero_constant(dict_type), dst_ptr)

        key_type, value_type = self._dict_item_types_for_value(src_ptr)
        count = self._dict_count(src_ptr)
        index_ptr = self.builder.alloca(i32, name='_dict_value_copy_i')
        self.builder.store(ir.Constant(i32, 0), index_ptr)
        cond_block = self.builder.append_basic_block('dict_value_copy_cond')
        body_block = self.builder.append_basic_block('dict_value_copy_body')
        done_block = self.builder.append_basic_block('dict_value_copy_done')
        self.builder.branch(cond_block)

        self.builder.position_at_start(cond_block)
        index = self.builder.load(index_ptr, name='_dict_value_copy_i_val')
        more = self.builder.icmp_unsigned('<', index, count, name='_dict_value_copy_more')
        self.builder.cbranch(more, body_block, done_block)

        self.builder.position_at_start(body_block)
        raw_key = self.builder.load(self._dict_key_slot_ptr(src_ptr, index), name='_dict_value_copy_key_raw')
        raw_value = self.builder.load(self._dict_value_slot_ptr(src_ptr, index), name='_dict_value_copy_value_raw')
        key = self._dict_from_i8_ptr(raw_key, key_type)
        value = self._dict_from_i8_ptr(raw_value, value_type)
        self._gen_dict_set(dst_ptr, key, value)
        self.builder.store(self.builder.add(index, ir.Constant(i32, 1)), index_ptr)
        self.builder.branch(cond_block)

        self.builder.position_at_start(done_block)
        self._mark_dict_item_types(dst_ptr, key_type, value_type)
        return dst_ptr

    def _bind_function_param(self, name: str, param_type: ir.Type, arg: ir.Value, *, this_ref: bool = False):
        """把函数参数绑定到局部符号；this 聚合参数保留引用语义。"""
        if this_ref and isinstance(param_type, ir.PointerType) and isinstance(param_type.pointee, (ir.LiteralStructType, ir.IdentifiedStructType)):
            self.locals[name] = arg
            return arg
        alloca = self.builder.alloca(param_type, name=name)
        self.builder.store(arg, alloca)
        if isinstance(param_type, (ir.LiteralStructType, ir.IdentifiedStructType)):
            copied = self._copy_aggregate_value(alloca, name=name)
            self.locals[name] = copied
            return copied
        self.locals[name] = alloca
        return alloca

    def _restore_active_arena_scopes(self, target_depth: int = 0) -> None:
        """提前退出当前控制流前恢复所有活动块作用域 Arena 游标。"""
        if self.builder is None or not hasattr(self, '_arena_restore'):
            return
        while len(self._arena_scope_stack) > target_depth:
            saved_pos = self._arena_scope_stack.pop()
            self.builder.call(self._arena_restore, [saved_pos])

    @staticmethod
    def _type_may_reference_arena(t: ir.Type) -> bool:
        """判断值类型内部是否可能保存 Arena 指针，返回时需要提升到外层生命周期。"""
        if isinstance(t, ir.PointerType):
            return True
        if isinstance(t, ir.LiteralStructType):
            return any(LLVMCodeGenerator._type_may_reference_arena(e) for e in t.elements)
        if isinstance(t, ir.IdentifiedStructType) and not t.is_opaque:
            return any(LLVMCodeGenerator._type_may_reference_arena(e) for e in t.elements)
        if isinstance(t, ir.ArrayType):
            return LLVMCodeGenerator._type_may_reference_arena(t.element)
        return False

    def _restore_active_arena_scopes_for_return(self, ret_value: ir.Value | None = None,
                                                ret_type: ir.Type | None = None,
                                                target_depth: int = 0) -> None:
        """return 前恢复作用域；若返回值含 Arena 指针，则保留当前块分配避免悬垂引用。"""
        value_type = ret_type
        if value_type is None and isinstance(ret_value, ir.Value):
            value_type = ret_value.type.pointee if self._is_aggregate_ptr(ret_value) else ret_value.type
        if value_type is not None and self._type_may_reference_arena(value_type):
            if target_depth > 0:
                del self._arena_scope_stack[target_depth:]
            else:
                self._arena_scope_stack.clear()
            return
        self._restore_active_arena_scopes(target_depth)

    def _type_ctx_is_unsigned(self, ctx) -> bool:
        """判断语法类型是否为无符号整数类型。"""
        if ctx is None:
            return False
        if isinstance(ctx, EzLangParser.ArrayTypeContext) or isinstance(ctx, EzLangParser.ListTypeContext):
            return self._type_ctx_is_unsigned(ctx.type_())
        if hasattr(ctx, 'baseType') and ctx.baseType() is not None:
            bt = ctx.baseType()
            return bt.U8() is not None or bt.U32() is not None or bt.U64() is not None
        if hasattr(ctx, 'type_'):
            inner = ctx.type_()
            if inner is not None and not isinstance(inner, list):
                return self._type_ctx_is_unsigned(inner)
        return False

    def _type_ctx_name(self, ctx) -> str:
        """把类型语法规范化为 TypeID 使用的 EzLang 类型名。"""
        if ctx is None:
            return "unknown"
        if isinstance(ctx, EzLangParser.OptionalTypeContext):
            return f"{self._type_ctx_name(ctx.type_())}?"
        if isinstance(ctx, EzLangParser.ArrayTypeContext):
            return f"{self._type_ctx_name(ctx.type_())}[]"
        if isinstance(ctx, EzLangParser.ListTypeContext):
            return f"List<{self._type_ctx_name(ctx.type_())}>"
        if isinstance(ctx, EzLangParser.VecTypeContext):
            return f"Vec<{self._type_ctx_name(ctx.type_())}>[{ctx.INTEGER_LITERAL().getText()}]"
        if isinstance(ctx, EzLangParser.PointerTypeContext):
            return f"*{self._type_ctx_name(ctx.type_())}"
        if isinstance(ctx, EzLangParser.ParenTypeContext):
            return self._type_ctx_name(ctx.type_())
        if isinstance(ctx, EzLangParser.UnionTypeContext):
            return " | ".join(self._type_ctx_name(t) for t in ctx.type_())
        if isinstance(ctx, EzLangParser.TypeShapeTypeContext):
            return "Dict" if self._type_shape_is_dynamic(ctx.typeShape()) else "shape"
        if isinstance(ctx, EzLangParser.TypeofTypeContext):
            return "I32"
        if hasattr(ctx, 'baseType') and ctx.baseType() is not None:
            return self._base_type_name(ctx.baseType())
        text = ctx.getText() if hasattr(ctx, 'getText') else ""
        return text or "unknown"

    def _base_type_name(self, bt) -> str:
        if bt.I8() is not None: return "I8"
        if bt.I32() is not None: return "I32"
        if bt.I64() is not None: return "I64"
        if bt.U8() is not None: return "U8"
        if bt.U32() is not None: return "U32"
        if bt.U64() is not None: return "U64"
        if bt.F32() is not None: return "F32"
        if bt.F64() is not None: return "F64"
        if bt.STR() is not None: return "Str"
        if bt.BOOL() is not None: return "Bool"
        if bt.VOID() is not None: return "Void"
        if bt.TYPE_IDENTIFIER() is not None:
            name = bt.TYPE_IDENTIFIER().getText()
            if bt.genericArgs() is not None:
                args = ", ".join(self._type_ctx_name(t) for t in bt.genericArgs().type_())
                return f"{name}<{args}>"
            return name
        return "unknown"

    def _type_shape_is_dynamic(self, shape_ctx) -> bool:
        if shape_ctx is None:
            return False
        members = list(shape_ctx.typeShapeMember())
        return bool(members) and all(member.LBRACK() is not None for member in members)

    def _remember_type_name(self, name: str, llvm_type: ir.Type, type_ctx=None, value: ir.Value | None = None,
                            *, global_scope: bool = False) -> None:
        type_name = self._type_ctx_name(type_ctx) if type_ctx is not None else None
        if (type_name is None or type_name == "unknown") and value is not None:
            type_name = self._type_name_from_value(value)
        if type_name is None or type_name == "unknown":
            type_name = self._type_name_from_ir_type(llvm_type)
        if global_scope:
            self._globals_type_names[name] = type_name
        else:
            self._locals_type_names[name] = type_name

    def _mark_unsigned(self, value: ir.Value | None, unsigned: bool) -> None:
        if value is None:
            return
        if isinstance(value.type, ir.PointerType):
            self._ptr_unsigned[id(value)] = unsigned
        else:
            self._value_unsigned[id(value)] = unsigned

    def _is_unsigned_value(self, value: ir.Value | None) -> bool:
        if value is None:
            return False
        if isinstance(value.type, ir.PointerType):
            return self._ptr_unsigned.get(id(value), False)
        return self._value_unsigned.get(id(value), False)

    def _load_with_unsigned(self, ptr: ir.Value, name: str = "") -> ir.Value:
        value = self.builder.load(ptr, name=name)
        self._mark_unsigned(value, self._ptr_unsigned.get(id(ptr), False))
        return value

    def _coerce_preserve_unsigned(self, value: ir.Value, target_type: ir.Type) -> ir.Value:
        unsigned = self._is_unsigned_value(value)
        coerced = self._coerce_value(value, target_type) if value.type != target_type else value
        self._mark_unsigned(coerced, unsigned)
        return coerced

    def _coerce_integer_value(self, value: ir.Value, target_type: ir.IntType) -> ir.Value:
        if not isinstance(value.type, ir.IntType):
            return value
        if value.type == target_type:
            return value
        if value.type.width < target_type.width:
            return self.builder.zext(value, target_type) if self._is_unsigned_value(value) else self.builder.sext(value, target_type)
        if value.type.width > target_type.width:
            return self.builder.trunc(value, target_type)
        return value

    def _binary_result_unsigned(self, left: ir.Value, right: ir.Value) -> bool:
        return self._is_unsigned_value(left) or self._is_unsigned_value(right)

    @staticmethod
    def _is_vector_value(value: ir.Value | None) -> bool:
        return value is not None and isinstance(value.type, ir.VectorType)

    def _broadcast_scalar_to_vector(self, scalar: ir.Value, vector_type: ir.VectorType) -> ir.Value:
        """把标量广播为与目标向量同宽的 LLVM 向量。"""
        elem_type = vector_type.element
        if scalar.type != elem_type:
            scalar = self._coerce_preserve_unsigned(scalar, elem_type)
        value = ir.Constant(vector_type, ir.Undefined)
        for index in range(vector_type.count):
            value = self.builder.insert_element(value, scalar, ir.Constant(ir.IntType(32), index))
        self._mark_unsigned(value, self._is_unsigned_value(scalar))
        return value

    def _prepare_vector_binary_operands(self, left: ir.Value, right: ir.Value) -> tuple[ir.Value, ir.Value]:
        """向量/标量混合运算时，将标量广播成向量。"""
        if self._is_vector_value(left) and not self._is_vector_value(right):
            return left, self._broadcast_scalar_to_vector(right, left.type)
        if self._is_vector_value(right) and not self._is_vector_value(left):
            return self._broadcast_scalar_to_vector(left, right.type), right
        return left, right

    def _list_type_is_unsigned(self, list_type: ir.Type) -> bool:
        elem_type = None
        if isinstance(list_type, ir.PointerType):
            list_type = list_type.pointee
        if self._is_list_type(list_type):
            elem_type = list_type.elements[0].pointee.pointee
        return isinstance(elem_type, ir.IntType) and self._list_elem_unsigned.get(id(list_type), False)

    def _mark_list_elem_unsigned(self, list_value: ir.Value | ir.Type | None, unsigned: bool) -> None:
        if list_value is None:
            return
        list_type = list_value
        if isinstance(list_value, ir.Value):
            list_type = list_value.type.pointee if isinstance(list_value.type, ir.PointerType) else list_value.type
        if self._is_list_type(list_type):
            self._list_elem_unsigned[id(list_type)] = unsigned

    def _mark_dict_item_types(self, dict_value: ir.Value | ir.Type | None, key_type: ir.Type, value_type: ir.Type) -> None:
        if dict_value is None:
            return
        if isinstance(dict_value, ir.Value):
            self._dict_item_types[id(dict_value)] = (key_type, value_type)
            return
        self._dict_item_types[id(dict_value)] = (key_type, value_type)

    def _dict_item_types_for_value(self, dict_value: ir.Value | None) -> tuple[ir.Type, ir.Type]:
        i8_ptr = ir.PointerType(ir.IntType(8))
        if dict_value is None:
            return i8_ptr, i8_ptr
        found = self._dict_item_types.get(id(dict_value))
        if found is not None:
            return found
        dict_type = dict_value.type.pointee if isinstance(dict_value.type, ir.PointerType) else dict_value.type
        return self._dict_item_types.get(id(dict_type), (i8_ptr, i8_ptr))

    def _dict_types_from_type_ctx(self, ctx) -> tuple[ir.Type, ir.Type] | None:
        if ctx is None:
            return None
        if isinstance(ctx, EzLangParser.TypeShapeTypeContext):
            members = list(ctx.typeShape().typeShapeMember()) if ctx.typeShape() is not None else []
            dynamic_members = [member for member in members if member.LBRACK() is not None]
            if dynamic_members and len(dynamic_members) == len(members):
                member = dynamic_members[0]
                member_types = member.type_()
                member_types = member_types if isinstance(member_types, list) else [member_types]
                member_types = [t for t in member_types if t is not None]
                key_type = self._map_type(member_types[0]) if member_types else ir.PointerType(ir.IntType(8))
                value_type = self._map_type(member_types[-1]) if len(member_types) > 1 else ir.PointerType(ir.IntType(8))
                return key_type, value_type
        if hasattr(ctx, 'baseType') and ctx.baseType() is not None:
            bt = ctx.baseType()
            if bt.TYPE_IDENTIFIER() is not None and bt.TYPE_IDENTIFIER().getText() == 'Dict' and bt.genericArgs() is not None:
                args = list(bt.genericArgs().type_())
                key_type = self._map_type(args[0]) if args else ir.PointerType(ir.IntType(8))
                value_type = self._map_type(args[1]) if len(args) > 1 else ir.PointerType(ir.IntType(8))
                return key_type, value_type
        if hasattr(ctx, 'type_'):
            inner = ctx.type_()
            if inner is not None and not isinstance(inner, list):
                return self._dict_types_from_type_ctx(inner)
        return None

    def _dict_types_from_type_ctx_with_map(self, ctx, type_map: dict[str, ir.Type]) -> tuple[ir.Type, ir.Type] | None:
        if ctx is None:
            return None
        if isinstance(ctx, EzLangParser.TypeShapeTypeContext):
            members = list(ctx.typeShape().typeShapeMember()) if ctx.typeShape() is not None else []
            dynamic_members = [member for member in members if member.LBRACK() is not None]
            if dynamic_members and len(dynamic_members) == len(members):
                member = dynamic_members[0]
                member_types = member.type_()
                member_types = member_types if isinstance(member_types, list) else [member_types]
                member_types = [t for t in member_types if t is not None]
                key_type = self._map_type_with_map(member_types[0], type_map) if member_types else ir.PointerType(ir.IntType(8))
                value_type = self._map_type_with_map(member_types[-1], type_map) if len(member_types) > 1 else ir.PointerType(ir.IntType(8))
                return key_type, value_type
        if hasattr(ctx, 'baseType') and ctx.baseType() is not None:
            bt = ctx.baseType()
            if bt.TYPE_IDENTIFIER() is not None and bt.TYPE_IDENTIFIER().getText() == 'Dict' and bt.genericArgs() is not None:
                args = list(bt.genericArgs().type_())
                key_type = self._map_type_with_map(args[0], type_map) if args else ir.PointerType(ir.IntType(8))
                value_type = self._map_type_with_map(args[1], type_map) if len(args) > 1 else ir.PointerType(ir.IntType(8))
                return key_type, value_type
        if hasattr(ctx, 'type_'):
            inner = ctx.type_()
            if inner is not None and not isinstance(inner, list):
                return self._dict_types_from_type_ctx_with_map(inner, type_map)
        return None

    def _struct_mono_name(self, base_name: str, type_args: list[ir.Type]) -> str:
        suffix = '_'.join(self._type_name(t) for t in type_args)
        return f"{base_name}_{suffix}" if suffix else base_name

    def _struct_name_from_generic_args(self, base_name: str, generic_args_ctx) -> str:
        if generic_args_ctx is None or base_name not in self.struct_generic_templates:
            return base_name
        type_arg_ctxs = list(generic_args_ctx.type_())
        type_args = [self._map_type(t) for t in type_arg_ctxs]
        type_arg_unsigned = [self._type_ctx_is_unsigned(t) for t in type_arg_ctxs]
        return self._monomorphize_struct(base_name, type_args, type_arg_unsigned)

    def _struct_name_from_literal(self, ctx) -> str:
        base_name = ctx.TYPE_IDENTIFIER().getText()
        return self._struct_name_from_generic_args(base_name, ctx.genericArgs())

    def _infer_struct_type_args_from_values(self, base_name: str,
                                           provided: dict[str, ir.Value]) -> tuple[list[ir.Type], list[bool]] | None:
        """根据构造字段实参值推导泛型结构体类型实参。"""
        generic_names = self.struct_generic_params.get(base_name, [])
        template_ctx = self.struct_generic_templates.get(base_name)
        if not generic_names or template_ctx is None or not provided:
            return None
        type_map: dict[str, ir.Type] = {}
        unsigned_map: dict[str, bool] = {}
        generic_set = set(generic_names)
        for member_ctx in template_ctx.structMember():
            field_ctx = member_ctx.structField()
            if field_ctx is None:
                continue
            fname = field_ctx.VAR_IDENTIFIER().getText()
            actual = provided.get(fname)
            if actual is None:
                continue
            actual_type = self._value_type_for_generic_inference(actual)
            before = dict(type_map)
            self._infer_generic_type_from_ctx(field_ctx.type_(), actual_type, type_map, generic_set)
            for name, typ in type_map.items():
                if name not in before and typ == actual_type:
                    unsigned_map[name] = self._is_unsigned_value(actual)
        if any(name not in type_map for name in generic_names):
            return None
        return [type_map[name] for name in generic_names], [unsigned_map.get(name, False) for name in generic_names]

    def _monomorphize_struct(self, base_name: str, type_args: list[ir.Type],
                             type_arg_unsigned: list[bool] | None = None) -> str:
        """为显式泛型结构体实参生成独立 LLVM 布局。"""
        generic_names = self.struct_generic_params.get(base_name, [])
        if not generic_names or len(generic_names) != len(type_args):
            return base_name

        mono_name = self._struct_mono_name(base_name, type_args)
        if mono_name in self._struct_monomorphized:
            return mono_name
        template_ctx = self.struct_generic_templates.get(base_name)
        if template_ctx is None:
            return base_name

        self._struct_monomorphized.add(mono_name)
        type_map = dict(zip(generic_names, type_args))
        unsigned_map = dict(zip(generic_names, type_arg_unsigned or [False] * len(generic_names)))

        struct_type = ir.global_context.get_identified_type(mono_name)
        self.structs[mono_name] = struct_type
        field_names: list[str] = []
        field_types: list[ir.Type] = []
        field_unsigned: list[bool] = []
        defaults: dict[str, object] = {}
        methods: list[tuple[str, object, object]] = []

        for member_ctx in template_ctx.structMember():
            field_ctx = member_ctx.structField()
            if field_ctx is not None:
                fname = field_ctx.VAR_IDENTIFIER().getText()
                ftype = self._map_type_with_map(field_ctx.type_(), type_map)
                field_names.append(fname)
                field_types.append(ftype)
                if self._type_ctx_is_generic_name(field_ctx.type_(), unsigned_map):
                    field_unsigned.append(unsigned_map.get(field_ctx.type_().baseType().TYPE_IDENTIFIER().getText(), False))
                else:
                    field_unsigned.append(self._type_ctx_is_unsigned(field_ctx.type_()))
                if field_ctx.expression() is not None:
                    defaults[fname] = field_ctx.expression()

            spread_ctx = member_ctx.structSpread()
            if spread_ctx is not None:
                base_type = self._map_type_with_map(spread_ctx.type_(), type_map)
                spread_name = base_type.name if isinstance(base_type, ir.IdentifiedStructType) else None
                if spread_name in self.struct_fields:
                    for bf in self.struct_fields[spread_name]:
                        if bf in field_names:
                            continue
                        bf_idx = self.struct_fields[spread_name].index(bf)
                        field_names.append(bf)
                        field_types.append(base_type.elements[bf_idx])
                        base_unsigned = self._struct_field_unsigned.get(spread_name, [])
                        field_unsigned.append(base_unsigned[bf_idx] if bf_idx < len(base_unsigned) else False)

            method_ctx = member_ctx.structMethod()
            if method_ctx is not None:
                methods.append((method_ctx.VAR_IDENTIFIER().getText(), method_ctx.functionLiteral(), method_ctx.functionSignature()))

        if struct_type.is_opaque:
            struct_type.set_body(*field_types)
        self.struct_fields[mono_name] = field_names
        self._struct_field_unsigned[mono_name] = field_unsigned
        self.struct_defaults[mono_name] = defaults
        if methods:
            self.struct_methods[mono_name] = {}
            self._generic_type_map_stack.append(type_map)
            try:
                for mname, fn_lit, sig in methods:
                    func_name = f"{mono_name}_{mname}"
                    self.struct_methods[mono_name][mname] = func_name
                    if fn_lit is not None:
                        self._gen_method_func(func_name, fn_lit, mono_name)
                    elif sig is not None:
                        self._declare_method_signature(func_name, sig)
            finally:
                self._generic_type_map_stack.pop()
        return mono_name

    def _type_ctx_is_generic_name(self, ctx, unsigned_map: dict[str, bool]) -> bool:
        return isinstance(ctx, EzLangParser.BaseTypeRefContext) \
            and ctx.baseType() is not None \
            and ctx.baseType().TYPE_IDENTIFIER() is not None \
            and ctx.baseType().TYPE_IDENTIFIER().getText() in unsigned_map \
            and ctx.baseType().genericArgs() is None

    def _save_unsigned_state(self):
        return dict(self._ptr_unsigned), dict(self._value_unsigned)

    def _restore_unsigned_state(self, state) -> None:
        self._ptr_unsigned, self._value_unsigned = state

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
        if self._generic_type_map_stack and not self._mapping_with_map:
            return self._map_type_with_map(ctx, self._generic_type_map_stack[-1])

        P = EzLangParser

        # 指针类型 *T 当前 lowering 为裸指针。
        if isinstance(ctx, P.PointerTypeContext):
            return ir.PointerType(self._map_type(ctx.type_()))

        # 匿名类型结构：动态键结构按 Dict ABI，普通结构使用字面结构。
        if isinstance(ctx, P.TypeShapeTypeContext):
            return self._map_type_shape(ctx.typeShape())

        # 可选类型: T? → {i1, T}
        if isinstance(ctx, P.OptionalTypeContext):
            inner = self._map_type(ctx.type_())
            return ir.LiteralStructType([ir.IntType(1), inner])

        # 联合类型: T1 | T2 → {i32, [max_type]}
        if isinstance(ctx, P.UnionTypeContext):
            types = [self._map_type(t) for t in ctx.type_()]
            max_type = max(types, key=lambda t: self._type_width(t))
            return ir.LiteralStructType([ir.IntType(32), max_type])

        # 数组类型: T[] → { pages, length, capacity, page_count }
        if isinstance(ctx, P.ArrayTypeContext):
            inner = self._map_type(ctx.type_())
            return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])

        # List 类型: List<T> → { pages, length, capacity, page_count }
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

    def _union_variant_tag(self, union_ctx, value_type: ir.Type) -> int:
        """按联合类型声明顺序计算变体 tag。"""
        if not isinstance(union_ctx, EzLangParser.UnionTypeContext):
            return 0
        for index, type_ctx in enumerate(union_ctx.type_()):
            variant_type = self._map_type(type_ctx)
            if variant_type == value_type:
                return index
            if isinstance(value_type, ir.IntType) and isinstance(variant_type, ir.IntType):
                return index
            if isinstance(value_type, ir.PointerType) and isinstance(variant_type, ir.PointerType):
                return index
        return 0

    def _union_variant_tag_for_type(self, target_type: ir.LiteralStructType, value_type: ir.Type) -> int:
        """缺少语法上下文时，根据联合载荷类型推断最可能的 tag。"""
        if value_type == target_type:
            return 0
        variant_type = target_type.elements[1]
        if value_type == variant_type:
            return 0
        type_name = self._type_name(value_type)
        payload_name = self._type_name(variant_type)
        if payload_name == 'Str' and type_name != 'Str':
            return 0
        if payload_name != 'Str' and type_name == 'Str':
            return 1
        return 0

    def _map_type_shape(self, shape_ctx) -> ir.Type:
        if shape_ctx is None:
            return ir.IntType(32)
        members = list(shape_ctx.typeShapeMember())
        dynamic_members = [member for member in members if member.LBRACK() is not None]
        if dynamic_members and len(dynamic_members) == len(members):
            return self.structs['Dict']
        fields = []
        for member in members:
            if member.VAR_IDENTIFIER() is None:
                continue
            member_types = member.type_()
            member_types = member_types if isinstance(member_types, list) else [member_types]
            member_types = [t for t in member_types if t is not None]
            fields.append(self._map_type(member_types[-1]) if member_types else ir.IntType(32))
        return ir.LiteralStructType(fields) if fields else ir.IntType(32)

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
            if name in self.struct_generic_templates and bt.genericArgs() is not None:
                type_arg_ctxs = list(bt.genericArgs().type_())
                type_args = [self._map_type(t) for t in type_arg_ctxs]
                type_arg_unsigned = [self._type_ctx_is_unsigned(t) for t in type_arg_ctxs]
                mono_name = self._monomorphize_struct(name, type_args, type_arg_unsigned)
                return self.structs.get(mono_name, self.structs.get(name, ir.IntType(32)))
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
        """获取 LLVM 类型的目标字节宽度（近似 C ABI 对齐），并缓存递归结果。"""
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
            offset = 0
            max_align = 1
            for elem in t.elements:
                align = self._type_align(elem)
                max_align = max(max_align, align)
                offset = self._align_to(offset, align)
                offset += self._type_width(elem)
            width = max(self._align_to(offset, max_align), 1)
        else:
            width = 4
        self._type_width_cache[key] = width
        return width

    def _type_align(self, t: ir.Type) -> int:
        """获取 LLVM 类型的近似 C ABI 对齐，当前按 64 位平台保守估算。"""
        key = str(t)
        cached = self._type_align_cache.get(key)
        if cached is not None:
            return cached
        if isinstance(t, ir.IntType):
            align = min(max(t.width // 8, 1), 8)
        elif isinstance(t, ir.FloatType):
            align = 4
        elif isinstance(t, ir.DoubleType):
            align = 8
        elif isinstance(t, ir.PointerType):
            align = 8
        elif isinstance(t, ir.ArrayType):
            align = self._type_align(t.element)
        elif isinstance(t, ir.VectorType):
            align = min(max(self._type_width(t), self._type_align(t.element)), 16)
        elif isinstance(t, (ir.LiteralStructType, ir.IdentifiedStructType)):
            align = max((self._type_align(e) for e in t.elements), default=1)
        else:
            align = 4
        self._type_align_cache[key] = align
        return align

    @staticmethod
    def _align_to(value: int, align: int) -> int:
        if align <= 1:
            return value
        return (value + align - 1) // align * align

    def _uses_c_sret(self, ret_type: ir.Type) -> bool:
        """外部 C ABI: 大聚合返回值使用隐藏 sret 指针。"""
        if not isinstance(ret_type, (ir.LiteralStructType, ir.IdentifiedStructType)):
            return False
        if self.compile_target == 'emcc':
            return True
        return self._type_width(ret_type) > 16

    def _c_abi_return_type(self, ret_type: ir.Type) -> ir.Type:
        """native C ABI 中的小可选聚合会按目标 ABI 重新分类返回值。"""
        if self.compile_target not in {'linux', 'macos', 'windows', 'android', 'ios'}:
            return ret_type
        if not (
            isinstance(ret_type, ir.LiteralStructType)
            and len(ret_type.elements) == 2
            and ret_type.elements[0] == ir.IntType(1)
        ):
            return ret_type

        value_type = ret_type.elements[1]
        if value_type == ir.IntType(32) or isinstance(value_type, ir.FloatType):
            return ir.IntType(64)
        if (
            value_type == ir.IntType(64)
            or isinstance(value_type, ir.DoubleType)
            or isinstance(value_type, ir.PointerType)
        ):
            if self.target_arch in {'aarch64', 'arm64'}:
                return ir.ArrayType(ir.IntType(64), 2)
            if self.target_arch in {'x86_64', 'amd64'}:
                ok_type = ir.IntType(8)
                return ir.LiteralStructType([ok_type, value_type])
        return ret_type

    def _restore_c_abi_return(self, func_name: str, value: ir.Value) -> ir.Value:
        bridge = self._c_abi_return_bridges.get(func_name)
        if bridge is None:
            return value
        ret_type, abi_ret_type = bridge
        slot = self.builder.alloca(ret_type, name=f"_{func_name}_abi_ret")
        raw_slot = self.builder.bitcast(slot, ir.PointerType(abi_ret_type))
        self.builder.store(value, raw_slot)
        return self.builder.load(slot, name=f"_{func_name}_ret")

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
        duck = self._coerce_struct_duck_value(val, target_type)
        if duck is not None:
            return duck
        if isinstance(val.type, ir.IntType) and isinstance(target_type, ir.IntType):
            return self._coerce_integer_value(val, target_type)
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
            if self._is_union_type(target_type):
                return self._coerce_union_value(val, target_type, self._union_variant_tag_for_type(target_type, val.type))
        return val

    def _coerce_struct_duck_value(self, val: ir.Value, target_type: ir.Type) -> ir.Value | None:
        """按字段名把兼容结构体值重组为目标结构体布局。"""
        if not isinstance(target_type, ir.IdentifiedStructType):
            return None
        target_name = target_type.name
        target_fields = self.struct_fields.get(target_name, []) if target_name else []
        if not target_fields:
            return None

        src_ptr = val if self._is_aggregate_ptr(val) else None
        src_type = val.type.pointee if src_ptr is not None else val.type
        if not isinstance(src_type, (ir.IdentifiedStructType, ir.LiteralStructType)) or src_type == target_type:
            return None
        src_name = src_type.name if isinstance(src_type, ir.IdentifiedStructType) else None
        src_fields = self.struct_fields.get(src_name, []) if src_name else []
        if not src_fields:
            return None

        result = ir.Constant(target_type, ir.Undefined)
        for target_idx, field_name in enumerate(target_fields):
            if field_name not in src_fields:
                return None
            src_idx = src_fields.index(field_name)
            if src_idx >= len(src_type.elements) or target_idx >= len(target_type.elements):
                return None
            if src_ptr is not None:
                src_field_ptr = self.builder.gep(src_ptr, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), src_idx),
                ], inbounds=True)
                field_val = self.builder.load(src_field_ptr)
            else:
                field_val = self.builder.extract_value(val, src_idx)
            target_field_type = target_type.elements[target_idx]
            if field_val.type != target_field_type:
                field_val = self._coerce_value(field_val, target_field_type)
            if field_val.type != target_field_type:
                return None
            result = self.builder.insert_value(result, field_val, target_idx)
        return result

    def _coerce_union_value(self, val: ir.Value, target_type: ir.LiteralStructType, tag: int) -> ir.Value:
        """把具体值包装成联合值，tag 由联合声明顺序决定。"""
        if val.type == target_type:
            return val
        undef = ir.Constant(target_type, ir.Undefined)
        result = self.builder.insert_value(undef, ir.Constant(ir.IntType(32), tag), 0)
        variant_type = target_type.elements[1]
        if self._is_aggregate_ptr(val) and val.type.pointee == variant_type:
            val = self.builder.load(val)
        if val.type != variant_type:
            if isinstance(val.type, ir.IntType) and isinstance(variant_type, ir.IntType):
                val = self._coerce_integer_value(val, variant_type)
            elif isinstance(val.type, ir.IntType) and isinstance(variant_type, ir.PointerType):
                val = self.builder.inttoptr(val, variant_type)
            elif isinstance(val.type, ir.PointerType) and isinstance(variant_type, ir.IntType):
                val = self.builder.ptrtoint(val, variant_type)
            else:
                return val
        return self.builder.insert_value(result, val, 1)

    def _optional_method_call(self, call_ctx, unwrap_ctx, method_name: str, args_ctx) -> ir.Value | None:
        """生成 opt?.method(...)：空值返回空可选，非空时调用方法并包装返回值。"""
        opt_val = self._eval(unwrap_ctx.postfixExpression())
        if opt_val is None or not hasattr(opt_val, 'type'):
            return None
        opt_type = opt_val.type.pointee if isinstance(opt_val.type, ir.PointerType) else opt_val.type
        if not self._is_optional_type(opt_type):
            return None
        value_type = opt_type.elements[1]
        if not isinstance(value_type, ir.IdentifiedStructType):
            return None
        struct_name = value_type.name
        method_table = self.struct_methods.get(struct_name, {})
        func_name = method_table.get(method_name)
        if func_name is None:
            return None
        try:
            func = self.module.get_global(func_name)
        except KeyError:
            return None
        if func is None or not isinstance(func, ir.Function):
            return None

        func_type = func.type.pointee if isinstance(func.type, ir.PointerType) else None
        if func_type is None:
            return None
        ret_type = func_type.return_type
        if isinstance(ret_type, ir.VoidType):
            return None
        result_type = ir.LiteralStructType([ir.IntType(1), ret_type])
        result_ptr = self.builder.alloca(result_type, name='_optional_method_result')
        self.builder.store(self._optional_value(ret_type, False), result_ptr)
        if not isinstance(opt_val.type, ir.PointerType):
            tmp = self.builder.alloca(opt_type, name='_optional_method_tmp')
            self.builder.store(opt_val, tmp)
            opt_val = tmp

        ok_ptr = self.builder.gep(opt_val, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), 0),
        ], inbounds=True)
        ok = self.builder.load(ok_ptr, name='_optional_method_ok')
        call_block = self.builder.append_basic_block('optional_method_call')
        done_block = self.builder.append_basic_block('optional_method_done')
        self.builder.cbranch(ok, call_block, done_block)

        self.builder.position_at_start(call_block)
        this_ptr = self.builder.gep(opt_val, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), 1),
        ], inbounds=True)
        provided: dict[str, ir.Value] = {}
        if args_ctx is not None:
            for a in args_ctx.namedArg():
                if a.VAR_IDENTIFIER() is None or a.expression() is None:
                    continue
                val = self._eval(a.expression())
                if val is not None:
                    provided[a.VAR_IDENTIFIER().getText()] = val
        expected_names = self.func_param_names.get(func_name, [])
        call_args = []
        abi_arg_types = list(func_type.args)
        if expected_names:
            call_args.append(this_ptr)
            for pname in expected_names[1:]:
                if pname in provided:
                    call_args.append(provided[pname])
                elif pname in self.func_defaults.get(func_name, {}):
                    default_val = self._eval(self.func_defaults[func_name][pname])
                    call_args.append(default_val if default_val is not None else ir.Constant(ir.IntType(32), 0))
                else:
                    call_args.append(ir.Constant(ir.IntType(32), 0))
        else:
            call_args.append(this_ptr)
            call_args.extend(provided.values())
        call_args = [
            self._coerce_value(arg, abi_arg_types[i]) if i < len(abi_arg_types) and arg.type != abi_arg_types[i] else arg
            for i, arg in enumerate(call_args)
        ]
        ret_val = self.builder.call(func, call_args)
        self._emit_throw_check_after_call()
        if self.builder is not None and not self.builder.block.is_terminated:
            self.builder.store(self._optional_value(ret_type, True, ret_val), result_ptr)
            self.builder.branch(done_block)
        self.builder.position_at_start(done_block)
        return self.builder.load(result_ptr, name='_optional_method_value')

    def _coerce_return_value(self, val: ir.Value, ret_type: ir.Type) -> ir.Value:
        """按当前函数返回类型转换返回值，联合类型需要保留声明顺序 tag。"""
        if val.type == ret_type:
            return val
        ret_ctx = self._function_return_type_ctx_stack[-1] if self._function_return_type_ctx_stack else None
        if isinstance(ret_ctx, EzLangParser.UnionTypeContext) and self._is_union_type(ret_type):
            return self._coerce_union_value(val, ret_type, self._union_variant_tag(ret_ctx, val.type))
        return self._coerce_value(val, ret_type)

    # ==================== 辅助 ====================

    def _qualified_name(self, ctx) -> str:
        """读取支持点号命名空间的声明名。"""
        qname = ctx.qualifiedVarName() if hasattr(ctx, 'qualifiedVarName') else None
        if qname is None:
            token = ctx.VAR_IDENTIFIER() if hasattr(ctx, 'VAR_IDENTIFIER') else None
            return token.getText() if token is not None else ""
        return qname.getText()

    def _lock_policy_code(self, ctx) -> int:
        prefix = ctx.lockPrefix() if hasattr(ctx, 'lockPrefix') else None
        if prefix is None:
            return 0
        if prefix.RP() is not None:
            return 1
        if prefix.WP() is not None:
            return 2
        return 0

    def _dict_key_text(self, field_ctx) -> str | None:
        key_ctx = field_ctx.dictKey() if hasattr(field_ctx, 'dictKey') else None
        if key_ctx is None:
            token = field_ctx.VAR_IDENTIFIER() if hasattr(field_ctx, 'VAR_IDENTIFIER') else None
            return token.getText() if token is not None else None
        if key_ctx.VAR_IDENTIFIER() is not None:
            return key_ctx.VAR_IDENTIFIER().getText()
        if key_ctx.STRING_LITERAL() is not None:
            return key_ctx.STRING_LITERAL().getText()[1:-1]
        return None

    def _dict_key_value(self, field_ctx) -> ir.Value:
        key_ctx = field_ctx.dictKey() if hasattr(field_ctx, 'dictKey') else None
        if key_ctx is not None and key_ctx.expression() is not None:
            val = self._eval(key_ctx.expression())
            if val is not None:
                if isinstance(val, ir.AllocaInstr):
                    val = self.builder.load(val)
                return val
        text = self._dict_key_text(field_ctx) or ""
        return self._make_global_string(text, prefix="_dict_key")

    def _emit_lock_metadata(self, name: str, policy_code: int):
        if policy_code == 0:
            return None
        self._lock_policies[name] = policy_code
        meta_name = "__ez_lock_" + re.sub(r"\W+", "_", name)
        if meta_name in self.module.globals:
            return self.module.globals[meta_name]
        meta = ir.GlobalVariable(self.module, ir.IntType(32), meta_name)
        meta.initializer = ir.Constant(ir.IntType(32), policy_code)
        meta.linkage = 'internal'
        return meta

    def _lock_name_ptr(self, name: str) -> ir.Value | None:
        if self.builder is None or name not in self._lock_policies:
            return None
        return self._make_global_string(name, prefix="_lock_name")

    def _emit_lock_access(self, name: str, mode: str, thunk):
        name_ptr = self._lock_name_ptr(name)
        if name_ptr is None:
            return thunk()
        if mode == "read":
            acquire = self._lock_read_acquire
            release = self._lock_read_release
        else:
            acquire = self._lock_write_acquire
            release = self._lock_write_release
        self.builder.call(acquire, [name_ptr])
        value = thunk()
        self.builder.call(release, [name_ptr])
        return value

    def _simple_lvalue_name(self, ctx) -> str | None:
        """仅识别裸标识符左值；成员和索引左值由后续语义完善。"""
        if ctx is None:
            return None
        text = ctx.getText() if hasattr(ctx, 'getText') else ''
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', text):
            return text
        return None

    def _outer_postfix_ctx(self, ctx):
        """返回表达式最外层的后缀表达式，用于判断真实左值形态。"""
        if ctx is None:
            return None
        if isinstance(ctx, EzLangParser.PostfixExpressionContext):
            return ctx
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._outer_postfix_ctx(ctx.getChild(i))
                if result is not None:
                    return result
        return None

    def _member_lvalue_ptr(self, ctx) -> ir.Value | None:
        """识别结构体字段左值，返回字段地址。"""
        member_ctx = self._find_member_access_ctx(ctx)
        if member_ctx is None:
            return None
        obj_ptr = self._eval(member_ctx.postfixExpression())
        if obj_ptr is None or not hasattr(obj_ptr, 'type'):
            return None
        pointee = obj_ptr.type.pointee if hasattr(obj_ptr.type, 'pointee') else obj_ptr.type
        if not isinstance(pointee, (ir.IdentifiedStructType, ir.LiteralStructType)):
            return None

        field_name = member_ctx.VAR_IDENTIFIER().getText()
        field_index = None
        if isinstance(pointee, ir.LiteralStructType) and len(pointee.elements) == 2 and pointee.elements[0] == ir.IntType(1):
            optional_fields = {'ok': 0, 'value': 1}
            field_index = optional_fields.get(field_name)
        else:
            struct_name = pointee.name if isinstance(pointee, ir.IdentifiedStructType) else None
            field_names = self.struct_fields.get(struct_name, []) if struct_name else []
            if field_name in field_names:
                field_index = field_names.index(field_name)

        if field_index is None:
            return None
        field_ptr = self.builder.gep(obj_ptr, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), field_index),
        ], inbounds=True)
        struct_name = pointee.name if isinstance(pointee, ir.IdentifiedStructType) else None
        if struct_name is not None:
            field_unsigned = self._struct_field_unsigned.get(struct_name, [])
            self._mark_unsigned(field_ptr, field_unsigned[field_index] if field_index < len(field_unsigned) else False)
        return field_ptr

    def _index_lvalue_ptr(self, ctx) -> ir.Value | None:
        """识别数组/List 索引左值，返回元素地址。"""
        index_ctx = ctx if isinstance(ctx, EzLangParser.IndexContext) else self._outer_postfix_ctx(ctx)
        if not isinstance(index_ctx, EzLangParser.IndexContext):
            return None

        obj_ptr = self._eval(index_ctx.postfixExpression())
        if obj_ptr is None or not hasattr(obj_ptr, 'type'):
            return None
        index_val = self._eval(index_ctx.expression())
        if index_val is None:
            return None

        if isinstance(obj_ptr.type, ir.PointerType) and self._is_list_type(obj_ptr.type.pointee):
            elem_ptr = self._list_element_ptr(obj_ptr, index_val)
            self._mark_unsigned(elem_ptr, self._list_type_is_unsigned(obj_ptr.type))
            return elem_ptr

        if isinstance(obj_ptr.type, ir.PointerType):
            return self.builder.gep(obj_ptr, [
                ir.Constant(ir.IntType(32), 0),
                index_val,
            ], inbounds=True)
        return None

    def _dict_index_target(self, ctx) -> tuple[ir.Value, ir.Value, ir.Type, ir.Type] | None:
        """识别简单 Dict 索引左值，并求出对象、key 与键值类型。"""
        index_ctx = ctx if isinstance(ctx, EzLangParser.IndexContext) else self._outer_postfix_ctx(ctx)
        if not isinstance(index_ctx, EzLangParser.IndexContext):
            return None

        target_name = self._simple_lvalue_name(index_ctx.postfixExpression())
        storage = self.locals.get(target_name) if target_name else None
        if storage is None and target_name:
            storage = self.globals.get(target_name)
        if storage is None or not isinstance(getattr(storage, 'type', None), ir.PointerType):
            return None
        storage_pointee = storage.type.pointee
        if not isinstance(storage_pointee, ir.IdentifiedStructType) or storage_pointee.name != 'Dict':
            return None

        obj_ptr = self._eval(index_ctx.postfixExpression())
        if obj_ptr is None or not isinstance(getattr(obj_ptr, 'type', None), ir.PointerType):
            return None
        pointee = obj_ptr.type.pointee
        if not isinstance(pointee, ir.IdentifiedStructType) or pointee.name != 'Dict':
            return None
        key = self._eval(index_ctx.expression())
        if key is None:
            return None
        key_type, value_type = self._dict_item_types_for_value(obj_ptr)
        return obj_ptr, key, key_type, value_type

    def _dict_index_assignment(self, target: tuple[ir.Value, ir.Value, ir.Type, ir.Type] | None,
                               val: ir.Value | None, op_ctx) -> ir.Value | None:
        """处理 Dict 索引赋值，按 key 更新已存在元素或插入新元素。"""
        if target is None or val is None:
            return None
        obj_ptr, key, key_type, value_type = target
        store_val = val
        if isinstance(store_val, ir.AllocaInstr):
            store_val = self.builder.load(store_val)
        if op_ctx is not None and op_ctx.ASSIGN() is None:
            current = self._gen_dict_lookup_value(obj_ptr, key, key_type, value_type)
            store_val = self._apply_assignment_operator(current, store_val, op_ctx)
        if store_val.type != value_type:
            store_val = self._coerce_preserve_unsigned(store_val, value_type)
        self._gen_dict_upsert_value(obj_ptr, key, store_val, key_type, value_type)
        return store_val

    def _find_member_access_ctx(self, ctx):
        if ctx is None:
            return None
        if isinstance(ctx, EzLangParser.MemberAccessContext):
            return ctx
        if hasattr(ctx, 'getChildCount'):
            found = None
            for i in range(ctx.getChildCount()):
                child_found = self._find_member_access_ctx(ctx.getChild(i))
                if child_found is not None:
                    found = child_found
            return found
        return None

    def _apply_assignment_operator(self, current: ir.Value, rhs: ir.Value, op_ctx) -> ir.Value:
        if op_ctx is None or op_ctx.ASSIGN() is not None:
            return rhs
        rhs = self._coerce_preserve_unsigned(rhs, current.type) if rhs.type != current.type else rhs
        unsigned = self._binary_result_unsigned(current, rhs)
        if op_ctx.PLUS_ASSIGN() is not None:
            result = self.builder.fadd(current, rhs, name="_assign_value") if self._is_float(current.type) else self.builder.add(current, rhs, name="_assign_value")
            self._mark_unsigned(result, unsigned)
            return result
        if op_ctx.MINUS_ASSIGN() is not None:
            result = self.builder.fsub(current, rhs, name="_assign_value") if self._is_float(current.type) else self.builder.sub(current, rhs, name="_assign_value")
            self._mark_unsigned(result, unsigned)
            return result
        if op_ctx.STAR_ASSIGN() is not None:
            result = self.builder.fmul(current, rhs, name="_assign_value") if self._is_float(current.type) else self.builder.mul(current, rhs, name="_assign_value")
            self._mark_unsigned(result, unsigned)
            return result
        if op_ctx.SLASH_ASSIGN() is not None:
            if self._is_float(current.type):
                result = self.builder.fdiv(current, rhs, name="_assign_value")
            else:
                result = self.builder.udiv(current, rhs, name="_assign_value") if unsigned else self.builder.sdiv(current, rhs, name="_assign_value")
            self._mark_unsigned(result, unsigned)
            return result
        if op_ctx.PERCENT_ASSIGN() is not None:
            result = self.builder.urem(current, rhs, name="_assign_value") if unsigned else self.builder.srem(current, rhs, name="_assign_value")
            self._mark_unsigned(result, unsigned)
            return result
        if op_ctx.AMPERSAND_ASSIGN() is not None:
            result = self.builder.and_(current, rhs, name="_assign_value")
            self._mark_unsigned(result, unsigned)
            return result
        if op_ctx.PIPE_ASSIGN() is not None:
            result = self.builder.or_(current, rhs, name="_assign_value")
            self._mark_unsigned(result, unsigned)
            return result
        if op_ctx.CARET_ASSIGN() is not None:
            result = self.builder.xor(current, rhs, name="_assign_value")
            self._mark_unsigned(result, unsigned)
            return result
        if op_ctx.SHL_ASSIGN() is not None:
            result = self.builder.shl(current, rhs, name="_assign_value")
            self._mark_unsigned(result, unsigned)
            return result
        if op_ctx.SHR_ASSIGN() is not None:
            result = self.builder.lshr(current, rhs, name="_assign_value") if unsigned else self.builder.ashr(current, rhs, name="_assign_value")
            self._mark_unsigned(result, unsigned)
            return result
        return rhs

    def _type_id(self, type_name: str) -> int:
        """为类型名分配稳定的 31-bit 正整数 ID。"""
        if type_name in self._type_ids:
            return self._type_ids[type_name]
        value = 2166136261
        for byte in type_name.encode("utf-8"):
            value ^= byte
            value = (value * 16777619) & 0xFFFFFFFF
        value &= 0x7FFFFFFF
        if value == 0:
            value = 1
        self._type_ids[type_name] = value
        return value

    def _typeof_name(self, ctx) -> str:
        text = ctx.getText() if ctx is not None else "unknown"
        if text in {"true", "false"}:
            return "Bool"
        if re.fullmatch(r'[-+]?\d+', text):
            return "I32"
        if re.fullmatch(r'[-+]?\d+\.\d+(?:[eE][-+]?\d+)?', text):
            return "F64"
        if text.startswith('"') and text.endswith('"'):
            return "Str"
        return text or "unknown"

    def _type_name_from_value(self, value: ir.Value | None) -> str:
        if value is None:
            return "unknown"
        return self._type_name_from_ir_type(value.type)

    def _type_name_from_ir_type(self, typ: ir.Type | None) -> str:
        if typ is None:
            return "unknown"
        if isinstance(typ, ir.PointerType):
            if typ.pointee == ir.IntType(8):
                return "Str"
            return self._type_name_from_ir_type(typ.pointee)
        if isinstance(typ, ir.IntType):
            if typ.width == 1:
                return "Bool"
            return f"I{typ.width}"
        if isinstance(typ, ir.FloatType):
            return "F32"
        if isinstance(typ, ir.DoubleType):
            return "F64"
        if isinstance(typ, ir.VectorType):
            return f"Vec<{self._type_name_from_ir_type(typ.element)}>[{typ.count}]"
        if self._is_list_type(typ):
            elem_type = typ.elements[0].pointee.pointee
            return f"{self._type_name_from_ir_type(elem_type)}[]"
        if isinstance(typ, ir.IdentifiedStructType):
            return typ.name or "Struct"
        if isinstance(typ, ir.LiteralStructType):
            return "Struct"
        if isinstance(typ, ir.ArrayType):
            return f"[{self._type_name_from_ir_type(typ.element)};{typ.count}]"
        if isinstance(typ, ir.VoidType):
            return "Void"
        return "unknown"

    def _typeof_name_from_expr(self, expr_ctx) -> str:
        ident = self._leftmost_identifier_ctx(expr_ctx)
        if ident is not None and ident.getText() == expr_ctx.getText():
            token = ident.VAR_IDENTIFIER() or ident.TYPE_IDENTIFIER()
            name = token.getText() if token is not None else ""
            if name in self._locals_type_names:
                return self._locals_type_names[name]
            if name in self._globals_type_names:
                return self._globals_type_names[name]
            if name in self.locals:
                return self._type_name_from_ir_type(self.locals[name].type.pointee)
            if name in self.globals:
                return self._type_name_from_ir_type(self.globals[name].type.pointee)
            if name in self.structs or name in self.type_aliases:
                return name

        struct_name = self._expr_struct_literal_name(expr_ctx)
        if struct_name is not None:
            return struct_name

        text_name = self._typeof_name(expr_ctx)
        if text_name != (expr_ctx.getText() if expr_ctx is not None else "unknown"):
            return text_name

        return self._type_name_from_ir_type(self._infer_global_initializer_type(expr_ctx))

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
        old_type_names = self._locals_type_names
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        throw_exit = func.append_basic_block('throw_exit')
        self._function_throw_exit_stack.append(throw_exit)

        for stmt in statements:
            var_decl = self._top_level_variable_decl(stmt)
            if var_decl is not None:
                self._init_global_variable(var_decl)
            else:
                self._eval(stmt)
            if self.builder.block.is_terminated:
                break

        self._finish_function_with_throw_exit(ir.IntType(32), ir.Constant(ir.IntType(32), 0))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        return func

    def _init_global_variable(self, ctx: EzLangParser.VariableDeclContext):
        name = self._qualified_name(ctx)
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
        self._emit_lock_access(name, "write", lambda: self.builder.store(val, gv))
        return None

    def _infer_global_initializer_type(self, initializer) -> ir.Type:
        text = initializer.getText()
        if text.startswith('typeof'):
            return ir.IntType(32)
        if text.startswith('parallel'):
            return self._infer_parallel_result_type(initializer)
        if text.startswith('race('):
            return ir.IntType(32)
        if text.startswith('"'):
            return ir.PointerType(ir.IntType(8))
        if text.startswith('{'):
            return self.structs['Dict']
        if text in {'true', 'false'}:
            return ir.IntType(1)
        if re.fullmatch(r'[-+]?\d+', text):
            return self._integer_literal_type(int(text, 0))
        if re.fullmatch(r'[-+]?\d+\.\d+(?:[eE][-+]?\d+)?', text):
            return ir.DoubleType()

        call_name = self._expr_call_name(initializer)
        generic_args = self._expr_call_generic_args(initializer)
        if call_name is not None and generic_args:
            call_name = self._monomorphize(call_name, generic_args)
        if call_name is not None:
            list_builtin = self._list_builtin_base(call_name)
            elem_type = generic_args[0] if generic_args else ir.IntType(32)
            if list_builtin == 'listLen':
                return ir.IntType(64)
            if list_builtin in {'listPush', 'listUnshift', 'listSort'}:
                return ir.VoidType()
            if list_builtin in {'listPop', 'listShift'}:
                return ir.LiteralStructType([ir.IntType(1), elem_type])
            if list_builtin == 'listFind':
                return ir.LiteralStructType([ir.IntType(1), elem_type])
            if list_builtin in {'listSlice', 'listFilter'}:
                return ir.LiteralStructType([
                    ir.PointerType(ir.PointerType(elem_type)),
                    ir.IntType(64),
                    ir.IntType(64),
                    ir.IntType(64),
                ])
            if list_builtin == 'listMap':
                result_elem = generic_args[1] if len(generic_args) > 1 else ir.IntType(32)
                return ir.LiteralStructType([
                    ir.PointerType(ir.PointerType(result_elem)),
                    ir.IntType(64),
                    ir.IntType(64),
                    ir.IntType(64),
                ])
            dict_builtin = self._dict_builtin_base(call_name)
            key_type = generic_args[0] if generic_args else ir.PointerType(ir.IntType(8))
            value_type = generic_args[1] if len(generic_args) > 1 else ir.PointerType(ir.IntType(8))
            if dict_builtin == 'dictLen':
                return ir.IntType(64)
            if dict_builtin in {'dictHas', 'dictDelete'}:
                return ir.IntType(1)
            if dict_builtin == 'dictKeys':
                return ir.LiteralStructType([
                    ir.PointerType(ir.PointerType(key_type)),
                    ir.IntType(64),
                    ir.IntType(64),
                    ir.IntType(64),
                ])
            if dict_builtin == 'dictValues':
                return ir.LiteralStructType([
                    ir.PointerType(ir.PointerType(value_type)),
                    ir.IntType(64),
                    ir.IntType(64),
                    ir.IntType(64),
                ])
        if call_name is not None and call_name in self.module.globals:
            if call_name in self._sret_functions:
                return self._sret_functions[call_name]
            if call_name in self._c_abi_return_bridges:
                return self._c_abi_return_bridges[call_name][0]
            callee = self.module.globals[call_name]
            func_type = callee.type.pointee if isinstance(callee.type, ir.PointerType) else None
            if isinstance(func_type, ir.FunctionType):
                return func_type.return_type

        struct_name = self._expr_struct_literal_name(initializer)
        if struct_name is not None and struct_name in self.structs:
            return self.structs[struct_name]

        return ir.IntType(32)

    def _infer_parallel_result_type(self, ctx) -> ir.Type:
        """从 parallel 块中的首个 return 粗略推断结果类型。"""
        if isinstance(ctx, EzLangParser.ParallelBlockExprContext):
            return self._infer_block_return_type(ctx.parallelBlock().block())
        if hasattr(ctx, 'parallelBlock') and ctx.parallelBlock() is not None:
            return self._infer_block_return_type(ctx.parallelBlock().block())
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._infer_parallel_result_type(ctx.getChild(i))
                if not isinstance(result, ir.IntType) or result.width != 32:
                    return result
        return ir.IntType(32)

    def _infer_block_return_type(self, block_ctx) -> ir.Type:
        if block_ctx is None:
            return ir.VoidType()
        for stmt in block_ctx.statement():
            ret = stmt.returnStatement()
            if ret is not None and ret.expression() is not None:
                return self._infer_global_initializer_type(ret.expression())
        return ir.VoidType()

    def _infer_function_literal_return_type(self, fn_lit) -> ir.Type:
        if fn_lit is None:
            return ir.VoidType()
        if fn_lit.type_() is not None:
            return self._map_type(fn_lit.type_())
        if fn_lit.block() is not None:
            return self._infer_block_return_type(fn_lit.block())
        if fn_lit.expression() is not None:
            expr_block = self._find_block_expr_ctx(fn_lit.expression())
            if expr_block is not None:
                return self._infer_block_return_type(expr_block)
            return self._infer_global_initializer_type(fn_lit.expression())
        return ir.VoidType()

    def _find_block_expr_ctx(self, ctx):
        if ctx is None:
            return None
        if isinstance(ctx, EzLangParser.BlockExprContext):
            return ctx.block()
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._find_block_expr_ctx(ctx.getChild(i))
                if result is not None:
                    return result
        return None

    def _infer_catch_result_type(self, block_ctx) -> ir.Type:
        """从 catch 块中的首个 throw 表达式粗略推断捕获值类型。"""
        if block_ctx is None:
            return self.structs['Error']
        for stmt in block_ctx.statement():
            thrown = self._infer_throw_expression_type(stmt)
            if thrown is not None:
                return thrown
        return self.structs['Error']

    def _infer_throw_expression_type(self, ctx) -> ir.Type | None:
        if ctx is None:
            return None
        throw_stmt = ctx.throwStatement() if hasattr(ctx, 'throwStatement') else None
        if throw_stmt is not None and throw_stmt.expression() is not None:
            return self._infer_global_initializer_type(throw_stmt.expression())
        if isinstance(ctx, EzLangParser.ThrowStatementContext) and ctx.expression() is not None:
            return self._infer_global_initializer_type(ctx.expression())
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._infer_throw_expression_type(ctx.getChild(i))
                if result is not None:
                    return result
        return None

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
        name = self._qualified_name(ctx)
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
            self.func_return_unsigned[name] = self._type_ctx_is_unsigned(fn_type.type_())
            param_types = []
            params = fn_type.paramTypeList()
            if params is not None:
                for p in params.paramType():
                    pt = self._map_type(p.type_())
                    if isinstance(pt, (ir.LiteralStructType, ir.IdentifiedStructType)):
                        pt = ir.PointerType(pt)
                    param_types.append(pt)
            uses_sret = self._uses_c_sret(ret_type)
            bridged_ret_type = self._c_abi_return_type(ret_type)
            abi_ret_type = ir.VoidType() if uses_sret else bridged_ret_type
            abi_param_types = ([ir.PointerType(ret_type)] if uses_sret else []) + param_types
            func_type = ir.FunctionType(abi_ret_type, abi_param_types)
            func = ir.Function(self.module, func_type, name)
            if uses_sret:
                func.args[0].add_attribute('sret')
                self._sret_functions[name] = ret_type
            elif bridged_ret_type != ret_type:
                self._c_abi_return_bridges[name] = (ret_type, bridged_ret_type)
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
        if lib_path.startswith('@pkg/'):
            root = Path(__file__).resolve().parents[3]
            return str((root / 'packages' / lib_path[len('@pkg/'):]).resolve())
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
            raw = _os.path.join(d, path)
            candidates = [raw]
            if not raw.endswith('.ez'):
                candidates.extend([raw + '.ez', _os.path.join(raw, 'index.ez')])
            p = next((candidate for candidate in candidates if _os.path.isfile(candidate)), None)
            if p is not None:
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
        name = self._qualified_name(ctx)
        type_ctx = ctx.type_()
        initializer = ctx.expression()
        decorators = [d.VAR_IDENTIFIER().getText() for d in ctx.decorator()]
        lock_policy_code = self._lock_policy_code(ctx)
        self._emit_lock_metadata(name, lock_policy_code)

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
            const_initializer = self._global_const_initializer(initializer, llvm_type)
            gv.initializer = const_initializer if const_initializer is not None else self._zero_constant(llvm_type)
            self.globals[name] = gv
            self._remember_type_name(name, llvm_type, type_ctx, global_scope=True)
            self._mark_unsigned(gv, self._type_ctx_is_unsigned(type_ctx))
            if type_ctx is not None:
                self._mark_list_elem_unsigned(gv, self._type_ctx_is_unsigned(type_ctx))
        else:
            # 局部变量
            if type_ctx is not None:
                llvm_type = self._map_type(type_ctx)
                alloca = self.builder.alloca(llvm_type, name=name)
                self.locals[name] = alloca
                self._remember_type_name(name, llvm_type, type_ctx)
                dict_item_types = self._dict_types_from_type_ctx(type_ctx)
                if dict_item_types is not None:
                    self._mark_dict_item_types(alloca, dict_item_types[0], dict_item_types[1])
                self._mark_unsigned(alloca, self._type_ctx_is_unsigned(type_ctx))
                self._mark_list_elem_unsigned(alloca, self._type_ctx_is_unsigned(type_ctx))
                if initializer is not None:
                    val = self._eval_expr(initializer)
                    if val is not None:
                        if self._is_aggregate_ptr(val):
                            val = self._copy_aggregate_value(val, name=f"_{name}_copy")
                            val = self.builder.load(val)
                        if isinstance(type_ctx, EzLangParser.UnionTypeContext) and self._is_union_type(llvm_type):
                            val = self._coerce_union_value(val, llvm_type, self._union_variant_tag(type_ctx, val.type))
                        else:
                            val = self._coerce_value(val, llvm_type)
                        self._emit_lock_access(name, "write", lambda: self.builder.store(val, alloca))
                else:
                    self._emit_lock_access(name, "write", lambda: self.builder.store(self._zero_constant(llvm_type), alloca))
            elif initializer is not None:
                # 类型推断：先求值，根据结果确定类型
                parallel_block = self._parallel_block_from_initializer(initializer)
                if parallel_block is not None and self._flow_depth > 0:
                    future_handle = self._start_flow_parallel_i32_future(name, parallel_block)
                    if future_handle is not None:
                        alloca = self.builder.alloca(ir.IntType(32), name=name)
                        self.builder.store(ir.Constant(ir.IntType(32), 0), alloca)
                        self.locals[name] = alloca
                        self._remember_type_name(name, ir.IntType(32))
                        self._mark_unsigned(alloca, False)
                        return None
                val = self._eval_expr(initializer)
                if val is not None:
                    if isinstance(val, ir.AllocaInstr) or self._is_aggregate_ptr(val):
                        source_dict_types = None
                        if isinstance(val.type, ir.PointerType) and val.type.pointee == self.structs.get('Dict'):
                            source_dict_types = self._dict_item_types_for_value(val)
                        copied = self._copy_aggregate_value(val, name=name)
                        self.locals[name] = copied
                        self._remember_type_name(name, copied.type.pointee, value=copied)
                        if copied.type.pointee == self.structs['Dict']:
                            key_type, value_type = source_dict_types or self._dict_item_types_for_value(val)
                            self._mark_dict_item_types(copied, key_type, value_type)
                        self._mark_list_elem_unsigned(copied, self._list_type_is_unsigned(copied.type))
                    else:
                        alloca = self.builder.alloca(val.type, name=name)
                        self._emit_lock_access(name, "write", lambda: self.builder.store(val, alloca))
                        self.locals[name] = alloca
                        self._remember_type_name(name, val.type, value=val)
                        if val.type == self.structs.get('Dict'):
                            key_type, value_type = self._dict_item_types_for_value(val)
                            self._mark_dict_item_types(alloca, key_type, value_type)
                        self._mark_unsigned(alloca, self._is_unsigned_value(val))
            else:
                # 无类型无初值，默认 i32
                alloca = self.builder.alloca(ir.IntType(32), name=name)
                self._emit_lock_access(name, "write", lambda: self.builder.store(ir.Constant(ir.IntType(32), 0), alloca))
                self.locals[name] = alloca
                self._remember_type_name(name, ir.IntType(32))
                self._mark_unsigned(alloca, False)

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
            alias_field_unsigned = []
            for member in members:
                if member.VAR_IDENTIFIER() is None:
                    continue
                field_names.append(member.VAR_IDENTIFIER().getText())
                member_types = member.type_()
                member_types = member_types if isinstance(member_types, list) else [member_types]
                member_types = [t for t in member_types if t is not None]
                field_type = self._map_type(member_types[-1]) if member_types else ir.IntType(32)
                alias_field_types.append(field_type)
                alias_field_unsigned.append(self._type_ctx_is_unsigned(member_types[-1]) if member_types else False)
            alias_struct = ir.global_context.get_identified_type(name)
            if not alias_struct.elements:
                alias_struct.set_body(*alias_field_types)
            self.structs[name] = alias_struct
            self.struct_fields[name] = field_names
            self._struct_field_unsigned[name] = alias_field_unsigned
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
        if ctx.genericParams() is not None:
            self.struct_generic_params[name] = [t.getText() for t in ctx.genericParams().TYPE_IDENTIFIER()]
            self.struct_generic_templates[name] = ctx
            return None

        struct_type = ir.global_context.get_identified_type(name)
        self.structs[name] = struct_type
        field_names = []
        field_types = []
        field_unsigned = []

        defaults = {}
        methods = []
        for member_ctx in ctx.structMember():
            # 字段
            field_ctx = member_ctx.structField()
            if field_ctx is not None:
                fname = field_ctx.VAR_IDENTIFIER().getText()
                ftype = self._map_type(field_ctx.type_())
                field_names.append(fname)
                field_types.append(ftype)
                field_unsigned.append(self._type_ctx_is_unsigned(field_ctx.type_()))
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
                                base_unsigned = self._struct_field_unsigned.get(base_name, [])
                                field_unsigned.append(base_unsigned[bf_idx] if bf_idx < len(base_unsigned) else False)
            # 方法: methodName = (this: Type, ...) => body
            method_ctx = member_ctx.structMethod()
            if method_ctx is not None:
                mname = method_ctx.VAR_IDENTIFIER().getText()
                if name not in self.struct_methods:
                    self.struct_methods[name] = {}
                self.struct_methods[name][mname] = f"{name}_{mname}"
                methods.append((mname, method_ctx.functionLiteral(), method_ctx.functionSignature()))

        if not struct_type.elements:
            struct_type.set_body(*field_types)
        self.structs[name] = struct_type
        self.struct_fields[name] = field_names
        self._struct_field_unsigned[name] = field_unsigned
        self.struct_defaults[name] = defaults
        for mname, fn_lit, sig in methods:
            func_name = f"{name}_{mname}"
            if fn_lit is not None:
                self._gen_method_func(func_name, fn_lit, name)
            elif sig is not None:
                self._declare_method_signature(func_name, sig)
        return None

    def _declare_method_signature(self, func_name: str, sig_ctx):
        """结构体方法签名声明：只生成外部函数原型。"""
        ret_type = self._map_type(sig_ctx.type_())
        self.func_return_unsigned[func_name] = self._type_ctx_is_unsigned(sig_ctx.type_())
        ret_dict_types = self._dict_types_from_type_ctx(sig_ctx.type_())
        if ret_dict_types is not None:
            self.func_return_dict_types[func_name] = ret_dict_types
        param_types = []
        param_names = []
        params = sig_ctx.paramList()
        if params is not None:
            for index, p in enumerate(params.param()):
                pname = p.VAR_IDENTIFIER().getText()
                ptype = self._map_type(p.type_())
                if index == 0 and pname == 'this' and isinstance(ptype, (ir.LiteralStructType, ir.IdentifiedStructType)):
                    ptype = ir.PointerType(ptype)
                param_types.append(ptype)
                param_names.append(pname)
        if func_name in self.module.globals:
            return self.module.globals[func_name]
        func = ir.Function(self.module, ir.FunctionType(ret_type, param_types), func_name)
        for i, pn in enumerate(param_names):
            func.args[i].name = pn
        self.func_param_names[func_name] = param_names
        return func

    def _gen_method_func(self, func_name: str, fn_lit_ctx, struct_name: str):
        """生成结构体方法对应的 LLVM 函数"""
        ret_type = self._map_type(fn_lit_ctx.type_())
        self.func_return_unsigned[func_name] = self._type_ctx_is_unsigned(fn_lit_ctx.type_())
        ret_dict_types = self._dict_types_from_type_ctx(fn_lit_ctx.type_())
        if ret_dict_types is not None:
            self.func_return_dict_types[func_name] = ret_dict_types
        param_types = []
        param_names = []
        params = fn_lit_ctx.paramList()
        if params is not None:
            for index, p in enumerate(params.param()):
                pname = p.VAR_IDENTIFIER().getText()
                ptype = self._map_type(p.type_())
                if index == 0 and pname == 'this' and isinstance(ptype, (ir.LiteralStructType, ir.IdentifiedStructType)):
                    ptype = ir.PointerType(ptype)
                param_types.append(ptype)
                param_names.append(pname)

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
            prev_unsigned = self._save_unsigned_state()
            prev_type_names = self._locals_type_names

            self.builder = ir.IRBuilder(entry)
            self.current_function = func
            self.locals = {}
            throw_exit = func.append_basic_block('throw_exit')
            self._function_throw_exit_stack.append(throw_exit)
            self._function_return_type_ctx_stack.append(fn_lit_ctx.type_())
            self._locals_type_names = {}

            for i, pn in enumerate(param_names):
                alloca = self._bind_function_param(pn, param_types[i], func.args[i], this_ref=(i == 0 and pn == 'this'))
                param_ctx = params.param()[i] if params is not None else None
                self._remember_type_name(pn, param_types[i], param_ctx.type_() if param_ctx is not None else None)
                if param_ctx is not None:
                    self._mark_unsigned(alloca, self._type_ctx_is_unsigned(param_ctx.type_()))
                    self._mark_list_elem_unsigned(alloca, self._type_ctx_is_unsigned(param_ctx.type_()))

            val = self._eval(body)
            self._finish_function_with_throw_exit(ret_type, val)
            self._function_return_type_ctx_stack.pop()

            self.builder = prev_builder
            self.current_function = prev_func
            self.locals = prev_locals
            self._locals_type_names = prev_type_names
            self._restore_unsigned_state(prev_unsigned)

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
        self.func_return_unsigned[name] = self._type_ctx_is_unsigned(fn_lit_ctx.type_())
        ret_dict_types = self._dict_types_from_type_ctx(fn_lit_ctx.type_())
        if ret_dict_types is not None:
            self.func_return_dict_types[name] = ret_dict_types
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
        old_func = self.current_function
        old_locals = self.locals
        old_unsigned = self._save_unsigned_state()
        old_type_names = self._locals_type_names
        self.builder = ir.IRBuilder(block)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        throw_exit = func.append_basic_block('throw_exit')
        self._function_throw_exit_stack.append(throw_exit)
        self._function_return_type_ctx_stack.append(fn_lit_ctx.type_())

        # 参数 alloca
        for i, pn in enumerate(param_names):
            alloca = self.builder.alloca(param_types[i], name=pn)
            self.builder.store(func.args[i], alloca)
            self.locals[pn] = alloca
            param_ctx = params.param()[i] if params is not None else None
            self._remember_type_name(pn, param_types[i], param_ctx.type_() if param_ctx is not None else None)
            if param_ctx is not None:
                self._mark_unsigned(alloca, self._type_ctx_is_unsigned(param_ctx.type_()))
                self._mark_list_elem_unsigned(alloca, self._type_ctx_is_unsigned(param_ctx.type_()))

        # 函数体
        body = fn_lit_ctx.block() or fn_lit_ctx.expression()
        val = None
        if body is not None:
            val = self._eval(body)

        self._finish_function_with_throw_exit(ret_type, val)
        self._function_return_type_ctx_stack.pop()

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
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

    def _is_float_or_float_vector(self, typ):
        if self._is_float(typ):
            return True
        return isinstance(typ, ir.VectorType) and self._is_float(typ.element)

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
            value = int(text, 0)
            return ir.Constant(self._integer_literal_type(value), value)
        except ValueError:
            return None

    def _integer_literal_type(self, value: int) -> ir.IntType:
        """未标注类型的整数字面量默认使用能容纳其值的最小内置整型。"""
        return ir.IntType(32) if -(2 ** 31) <= value <= (2 ** 31 - 1) else ir.IntType(64)

    def _global_const_initializer(self, ctx, target_type: ir.Type) -> Optional[ir.Constant]:
        """将可编译期求值的字面量写入全局 initializer。"""
        if ctx is None:
            return None
        text = ctx.getText()
        if isinstance(target_type, ir.IntType):
            if text == 'true' or text == 'false':
                return ir.Constant(target_type, int(text == 'true'))
            try:
                return ir.Constant(target_type, int(text, 0))
            except ValueError:
                return None
        if isinstance(target_type, (ir.FloatType, ir.DoubleType)):
            try:
                return ir.Constant(target_type, float(text))
            except ValueError:
                return None
        return None

    # 字面量
    def visitLiteralExpr(self, ctx: EzLangParser.LiteralExprContext):
        lit = ctx.literal()
        if lit is None:
            return ir.Constant(ir.IntType(32), 0)

        if lit.INTEGER_LITERAL() is not None:
            val_text = lit.INTEGER_LITERAL().getText()
            try:
                val = int(val_text, 0)
            except ValueError:
                val = 0
            return ir.Constant(self._integer_literal_type(val), val)

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
            self._join_flow_future(name)
            alloca = self.locals[name]
            if isinstance(alloca.type.pointee, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
                return alloca
            return self._emit_lock_access(name, "read", lambda: self._load_with_unsigned(alloca, name=name))
        if name in self.module.globals and isinstance(self.module.globals[name], ir.Function):
            return self.module.globals[name]
        if name in self.globals:
            gv = self.globals[name]
            if isinstance(gv.type.pointee, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
                return gv
            return self._emit_lock_access(name, "read", lambda: self._load_with_unsigned(gv, name=name))
        if name in self.structs or name in self.type_aliases or name in {"I8", "I32", "I64", "U8", "U32", "U64", "F32", "F64", "Str", "Bool", "Void", "List", "Dict", "Vec"}:
            return ir.Constant(ir.IntType(32), self._type_id(name))
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
        if base_name in self._collection_builtin_declares:
            self._collection_mono_types[mono_name] = (base_name, list(type_args))
            self.func_param_names[mono_name] = [
                p.VAR_IDENTIFIER().getText()
                for p in (template_ctx.paramTypeList().paramType() if template_ctx.paramTypeList() is not None else [])
            ]
            return mono_name
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
            ret_dict_types = self._dict_types_from_type_ctx_with_map(gen_ctx.type_(), type_map)
            if ret_dict_types is not None:
                self.func_return_dict_types[mono_name] = ret_dict_types
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

            uses_sret = self._uses_c_sret(ret_type)
            bridged_ret_type = self._c_abi_return_type(ret_type)
            abi_ret_type = ir.VoidType() if uses_sret else bridged_ret_type
            abi_param_types = ([ir.PointerType(ret_type)] if uses_sret else []) + param_types
            func_type = ir.FunctionType(abi_ret_type, abi_param_types)
            func = ir.Function(self.module, func_type, mono_name)
            if uses_sret:
                func.args[0].add_attribute('sret')
                self._sret_functions[mono_name] = ret_type
            elif bridged_ret_type != ret_type:
                self._c_abi_return_bridges[mono_name] = (ret_type, bridged_ret_type)
            offset = 1 if uses_sret else 0
            for i, pn in enumerate(orig_param_names):
                func.args[i + offset].name = pn
            self.func_param_names[mono_name] = orig_param_names
            return mono_name

        # 普通泛型函数：生成完整的单态化函数体
        fn_lit = template_ctx.functionLiteral()

        ret_type = self._map_type_with_map(fn_lit.type_(), type_map)
        ret_dict_types = self._dict_types_from_type_ctx_with_map(fn_lit.type_(), type_map)
        if ret_dict_types is not None:
            self.func_return_dict_types[mono_name] = ret_dict_types
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
            prev_unsigned = self._save_unsigned_state()
            prev_type_names = self._locals_type_names

            self.builder = ir.IRBuilder(entry)
            self.current_function = func
            self.locals = {}
            self._locals_type_names = {}
            self._generic_type_map_stack.append(type_map)
            throw_exit = func.append_basic_block('throw_exit')
            self._function_throw_exit_stack.append(throw_exit)
            self._function_return_type_ctx_stack.append(fn_lit.type_())

            for i, pn in enumerate(orig_param_names):
                alloca = self._bind_function_param(pn, param_types[i], func.args[i])
                self._remember_type_name(pn, param_types[i])

            val = self._eval(body)
            self._finish_function_with_throw_exit(ret_type, val)
            self._function_return_type_ctx_stack.pop()
            self._generic_type_map_stack.pop()

            self.builder = prev_builder
            self.current_function = prev_func
            self.locals = prev_locals
            self._locals_type_names = prev_type_names
            self._restore_unsigned_state(prev_unsigned)

        return mono_name

    def _map_type_with_map(self, ctx, type_map: dict[str, ir.Type]) -> ir.Type:
        prev_mapping = self._mapping_with_map
        self._mapping_with_map = True
        try:
            return self._map_type_with_map_impl(ctx, type_map)
        finally:
            self._mapping_with_map = prev_mapping

    def _map_type_with_map_impl(self, ctx, type_map: dict[str, ir.Type]) -> ir.Type:
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
                if name in self.struct_generic_templates:
                    type_args = [self._map_type_with_map(t, type_map) for t in args]
                    type_arg_unsigned = [self._type_ctx_is_unsigned(t) for t in args]
                    mono_name = self._monomorphize_struct(name, type_args, type_arg_unsigned)
                    return self.structs.get(mono_name, self.structs.get(name, ir.IntType(32)))
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

        # List 类型: List<T> → { pages, length, capacity, page_count }
        if isinstance(ctx, P.ListTypeContext):
            inner = self._map_type_with_map(ctx.type_(), type_map)
            return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])

        # 数组类型: T[] → { pages, length, capacity, page_count }
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
        base_name = ctx.TYPE_IDENTIFIER().getText()
        name = self._struct_name_from_literal(ctx)
        init_list = ctx.structFieldInitList()
        precomputed_values: dict[int, ir.Value] = {}

        if ctx.genericArgs() is None and base_name in self.struct_generic_templates and init_list is not None:
            provided_for_inference: dict[str, ir.Value] = {}
            for init_ctx in init_list.structFieldInit():
                if init_ctx.ELLIPSIS() is not None or init_ctx.expression() is None:
                    continue
                fname = init_ctx.VAR_IDENTIFIER().getText()
                val = self._eval(init_ctx.expression())
                if val is not None:
                    precomputed_values[id(init_ctx)] = val
                    provided_for_inference[fname] = val
            inferred = self._infer_struct_type_args_from_values(base_name, provided_for_inference)
            if inferred is not None:
                type_args, type_arg_unsigned = inferred
                name = self._monomorphize_struct(base_name, type_args, type_arg_unsigned)
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
                    val = precomputed_values.get(id(init_ctx))
                    if val is None:
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

    def _optional_safe_member_access(self, optional_ctx, field_name: str) -> ir.Value | None:
        """生成 opt?.field：空值返回空可选，非空时读取字段并包装。"""
        opt_val = self._eval(optional_ctx.postfixExpression())
        if opt_val is None or not hasattr(opt_val, 'type'):
            return None
        opt_type = opt_val.type.pointee if isinstance(opt_val.type, ir.PointerType) else opt_val.type
        if not self._is_optional_type(opt_type):
            return None
        value_type = opt_type.elements[1]
        if not isinstance(value_type, (ir.IdentifiedStructType, ir.LiteralStructType)):
            return None
        if not isinstance(opt_val.type, ir.PointerType):
            tmp = self.builder.alloca(opt_type, name='_optional_chain_tmp')
            self.builder.store(opt_val, tmp)
            opt_val = tmp

        field_names = None
        if isinstance(value_type, ir.IdentifiedStructType):
            field_names = self.struct_fields.get(value_type.name, [])
        if field_names is None and self._is_optional_type(value_type):
            field_names = ['ok', 'value']
        if not field_names or field_name not in field_names:
            return None
        field_index = field_names.index(field_name)
        field_type = value_type.elements[field_index]
        result_type = ir.LiteralStructType([ir.IntType(1), field_type])
        result_ptr = self.builder.alloca(result_type, name='_optional_chain_result')
        self.builder.store(self._optional_value(field_type, False), result_ptr)

        ok_ptr = self.builder.gep(opt_val, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), 0),
        ], inbounds=True)
        ok = self.builder.load(ok_ptr, name='_optional_chain_ok')
        value_block = self.builder.append_basic_block('optional_chain_value')
        done_block = self.builder.append_basic_block('optional_chain_done')
        self.builder.cbranch(ok, value_block, done_block)

        self.builder.position_at_start(value_block)
        value_ptr = self.builder.gep(opt_val, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), 1),
        ], inbounds=True)
        field_ptr = self.builder.gep(value_ptr, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), field_index),
        ], inbounds=True)
        field_value = field_ptr if isinstance(field_type, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)) else self._load_with_unsigned(field_ptr, name=field_name)
        self.builder.store(self._optional_value(field_type, True, field_value), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        return self.builder.load(result_ptr, name='_optional_chain_value')

    def _gen_struct_literal_from_call(self, struct_name: str, call_ctx):
        """从 CallContext 生成结构体实例（当语法解析为 # call 路径时）"""
        base_name = struct_name
        if struct_name not in self.structs and struct_name in self.struct_generic_templates:
            target = call_ctx.postfixExpression() if hasattr(call_ctx, 'postfixExpression') else None
            ident = self._leftmost_identifier_ctx(target)
            if ident is not None:
                struct_name = self._struct_name_from_generic_args(struct_name, ident.genericArgs())
        precomputed_values: dict[str, ir.Value] = {}
        args = call_ctx.namedArgList()
        if struct_name == base_name and struct_name not in self.structs and base_name in self.struct_generic_templates and args is not None:
            provided_for_inference: dict[str, ir.Value] = {}
            for a in args.namedArg():
                if a.VAR_IDENTIFIER() is None or a.expression() is None:
                    continue
                fname = a.VAR_IDENTIFIER().getText()
                val = self._eval(a.expression())
                if val is not None:
                    precomputed_values[fname] = val
                    provided_for_inference[fname] = val
            inferred = self._infer_struct_type_args_from_values(base_name, provided_for_inference)
            if inferred is not None:
                type_args, type_arg_unsigned = inferred
                struct_name = self._monomorphize_struct(base_name, type_args, type_arg_unsigned)
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
                        val = self._coerce_integer_value(val, field_type)
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
        if args and args.namedArg():
            for a in args.namedArg():
                if a.VAR_IDENTIFIER() is None or a.expression() is None:
                    continue
                fname = a.VAR_IDENTIFIER().getText()
                val = precomputed_values.get(fname)
                if val is None:
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
        if isinstance(ctx.postfixExpression(), EzLangParser.OptionalUnwrapContext):
            safe_value = self._optional_safe_member_access(ctx.postfixExpression(), ctx.VAR_IDENTIFIER().getText())
            if safe_value is not None:
                return safe_value

        obj_ptr = self._eval(ctx.postfixExpression())
        if obj_ptr is None:
            return None
        field_name = ctx.VAR_IDENTIFIER().getText()

        pointee = obj_ptr.type.pointee if hasattr(obj_ptr.type, 'pointee') else obj_ptr.type
        if not isinstance(pointee, (ir.IdentifiedStructType, ir.LiteralStructType)):
            return None

        struct_name = pointee.name if isinstance(pointee, ir.IdentifiedStructType) else None

        if self._is_list_type(pointee):
            list_fields = {'pages': 0, 'length': 1, 'capacity': 2, 'page_count': 3}
            if field_name in list_fields:
                idx = list_fields[field_name]
                gep = self.builder.gep(obj_ptr, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), idx)
                ], inbounds=True)
                if idx == 0:
                    return self.builder.load(gep, name=field_name)
                return self._load_with_unsigned(gep, name=field_name)

        if self._is_optional_type(pointee):
            optional_fields = {'ok': 0, 'value': 1}
            if field_name in optional_fields:
                idx = optional_fields[field_name]
                gep = self.builder.gep(obj_ptr, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), idx)
                ], inbounds=True)
                field_type = pointee.elements[idx]
                if isinstance(field_type, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
                    return gep
                return self._load_with_unsigned(gep, name=field_name)

        if self._is_union_type(pointee):
            union_fields = {'tag': 0, 'value': 1}
            if field_name in union_fields:
                idx = union_fields[field_name]
                gep = self.builder.gep(obj_ptr, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), idx)
                ], inbounds=True)
                field_type = pointee.elements[idx]
                if isinstance(field_type, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
                    return gep
                return self._load_with_unsigned(gep, name=field_name)

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
                field_unsigned = self._struct_field_unsigned.get(struct_name, [])
                self._mark_unsigned(gep, field_unsigned[idx] if idx < len(field_unsigned) else False)
                field_type = pointee.elements[idx]
                if isinstance(field_type, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
                    return gep
                value = self._load_with_unsigned(gep, name=field_name)
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
        elem_unsigned = False
        for e in exprs:
            v = self._eval(e)
            if v is not None:
                if isinstance(v, ir.AllocaInstr):
                    v = self.builder.load(v)
                values.append(v)
                elem_unsigned = elem_unsigned or self._is_unsigned_value(v)

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
                v = self._coerce_integer_value(v, elem_type)
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
        self._mark_list_elem_unsigned(alloca, elem_unsigned)
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
        key_type = ir.PointerType(ir.IntType(8))
        value_type = ir.PointerType(ir.IntType(8))
        saw_value_type = False
        for f in fields:
            key = self._dict_key_value(f)
            if key.type != ir.PointerType(ir.IntType(8)):
                key_type = key.type
            val = self._eval(f.expression())
            if isinstance(val, ir.AllocaInstr):
                val = self.builder.load(val)
            if val is not None and not saw_value_type:
                value_type = val.type
                saw_value_type = True
            self._gen_dict_set(alloca, key, val)
        self._mark_dict_item_types(alloca, key_type, value_type)
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

    def _markup_attr_value(self, attr) -> ir.Value | None:
        if attr.expression() is not None:
            return self._eval(attr.expression())
        if attr.STRING_LITERAL() is not None:
            text = attr.STRING_LITERAL().getText()[1:-1]
            return self._make_global_string(text, prefix="_markup_attr")
        if attr.INTEGER_LITERAL() is not None:
            return ir.Constant(ir.IntType(32), int(attr.INTEGER_LITERAL().getText(), 0))
        if attr.BOOL_LITERAL() is not None:
            return ir.Constant(ir.IntType(1), int(attr.BOOL_LITERAL().getText() == 'true'))
        return None

    def _markup_child_value(self, child) -> ir.Value | None:
        if child.markupLiteral() is not None:
            return self.visitMarkupLiteral(child.markupLiteral())
        if child.expression() is not None:
            return self._eval(child.expression())
        if child.STRING_LITERAL() is not None:
            return self._make_global_string(child.STRING_LITERAL().getText()[1:-1], prefix="_markup_child")
        return None

    def _markup_children_array(self, children) -> ir.Value:
        values = []
        for child in children:
            value = self._markup_child_value(child)
            if value is None:
                continue
            if isinstance(value, ir.AllocaInstr):
                value = self.builder.load(value)
            values.append((child, value))

        elem_type = values[0][1].type if values else ir.PointerType(ir.IntType(8))
        i64 = ir.IntType(64)
        page_size = 8
        page_count = max((len(values) + page_size - 1) // page_size, 1)
        arr_type = ir.LiteralStructType([ir.PointerType(ir.PointerType(elem_type)), i64, i64, i64])
        alloca = self._arena_allocate(arr_type, name="_markup_children")
        page_table_type = ir.ArrayType(ir.PointerType(elem_type), page_count)
        page_table = self._arena_allocate(page_table_type, name="_markup_children_pages")
        page_ptrs = []
        for page_idx in range(page_count):
            page_type = ir.ArrayType(elem_type, page_size)
            page_ptr = self._arena_allocate(page_type, name="_markup_children_page")
            page_base = self.builder.gep(page_ptr, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), 0)
            ], inbounds=True)
            page_slot = self.builder.gep(page_table, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), page_idx)
            ], inbounds=True)
            self.builder.store(page_base, page_slot)
            page_ptrs.append(page_ptr)

        for index, (child, value) in enumerate(values):
            if value.type != elem_type:
                coerced = self._coerce_value(value, elem_type)
                if coerced.type != elem_type:
                    self._extern_diagnostics.append(
                        f"行 {child.start.line}: 标记子节点类型不一致"
                    )
                    value = self._zero_constant(elem_type)
                else:
                    value = coerced
            page_ptr = page_ptrs[index // page_size]
            slot = self.builder.gep(page_ptr, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), index % page_size)
            ], inbounds=True)
            self.builder.store(value, slot)

        pages_base = self.builder.gep(page_table, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), 0)
        ], inbounds=True)
        self.builder.store(pages_base, self._list_field_ptr(alloca, 0))
        self.builder.store(ir.Constant(i64, len(values)), self._list_field_ptr(alloca, 1))
        self.builder.store(ir.Constant(i64, page_count * page_size), self._list_field_ptr(alloca, 2))
        self.builder.store(ir.Constant(i64, page_count), self._list_field_ptr(alloca, 3))
        return alloca

    def _markup_list_type_mismatch(self, actual: ir.Type, expected: ir.Type) -> bool:
        if isinstance(actual, ir.PointerType):
            actual = actual.pointee
        if isinstance(expected, ir.PointerType):
            expected = expected.pointee
        if not (self._is_list_type(actual) and self._is_list_type(expected)):
            return False
        actual_elem = actual.elements[0].pointee.pointee
        expected_elem = expected.elements[0].pointee.pointee
        return not self._markup_ir_types_compatible(actual_elem, expected_elem)

    def _markup_ir_types_compatible(self, actual: ir.Type, expected: ir.Type) -> bool:
        if actual == expected:
            return True
        if isinstance(actual, ir.IntType) and isinstance(expected, ir.IntType):
            return True
        if isinstance(actual, (ir.FloatType, ir.DoubleType)) and isinstance(expected, (ir.FloatType, ir.DoubleType)):
            return True
        if isinstance(expected, ir.LiteralStructType) and len(expected.elements) == 2 and expected.elements[0] == ir.IntType(1):
            return self._markup_ir_types_compatible(actual, expected.elements[1])
        return False

    def _markup_prepare_arg(self, tag_name: str, param_name: str, value: ir.Value,
                            expected_type: ir.Type, line: int) -> ir.Value:
        if self._markup_list_type_mismatch(value.type, expected_type):
            self._extern_diagnostics.append(
                f"行 {line}: 参数 '{param_name}' 类型不匹配"
            )
            return self._zero_constant(expected_type)
        coerced = self._coerce_value(value, expected_type)
        if coerced.type != expected_type and self._is_aggregate_ptr(coerced):
            coerced = self._load_if_aggregate_ptr(coerced)
        if coerced.type != expected_type:
            self._extern_diagnostics.append(
                f"行 {line}: 标记 '<{tag_name}>' 参数 '{param_name}' 类型不匹配"
            )
            return self._zero_constant(expected_type)
        return coerced

    def _markup_factory_call(self, tag_name: str, ctx: EzLangParser.MarkupLiteralContext) -> ir.Value | None:
        func = self.module.globals.get(tag_name)
        if not isinstance(func, ir.Function):
            return None

        expected_names = self.func_param_names.get(tag_name, [])
        expected_name_set = set(expected_names)
        provided = {}
        for attr in ctx.markupAttr():
            attr_name = attr.VAR_IDENTIFIER().getText()
            value = self._markup_attr_value(attr)
            if value is not None:
                provided[attr_name] = value
        if ctx.markupChild():
            provided['children'] = self._markup_children_array(ctx.markupChild())

        for pname in provided:
            if pname not in expected_name_set:
                self._extern_diagnostics.append(f"行 {ctx.start.line}: 未知参数 '{pname}'")

        call_args = []
        defaults = self.func_defaults.get(tag_name, {})
        abi_arg_types = list(func.function_type.args)
        if expected_names:
            for index, pname in enumerate(expected_names):
                param_type = abi_arg_types[index] if index < len(abi_arg_types) else ir.IntType(32)
                if pname in provided:
                    call_args.append(self._markup_prepare_arg(tag_name, pname, provided[pname], param_type, ctx.start.line))
                elif pname in defaults:
                    default_value = self._eval(defaults[pname])
                    if default_value is None:
                        call_args.append(self._zero_constant(param_type))
                    else:
                        call_args.append(self._markup_prepare_arg(tag_name, pname, default_value, param_type, ctx.start.line))
                else:
                    self._extern_diagnostics.append(f"行 {ctx.start.line}: 缺少必填参数 '{pname}'")
                    call_args.append(self._zero_constant(param_type))
        while len(call_args) < len(abi_arg_types):
            call_args.append(self._zero_constant(abi_arg_types[len(call_args)]))
        if len(call_args) > len(abi_arg_types):
            call_args = call_args[:len(abi_arg_types)]
        return self.builder.call(func, call_args)

    def visitMarkupLiteral(self, ctx: EzLangParser.MarkupLiteralContext):
        names = ctx.VAR_IDENTIFIER()
        tag_name = names[0].getText() if names else "tag"
        factory_value = self._markup_factory_call(tag_name, ctx)
        if factory_value is not None:
            return factory_value
        for attr in ctx.markupAttr():
            self._markup_attr_value(attr)
        for child in ctx.markupChild():
            self._markup_child_value(child)
        self._extern_diagnostics.append(
            f"行 {ctx.start.line}: 标记 '<{tag_name}>' 需要作用域内存在同名工厂函数 '{tag_name}'"
        )
        return ir.Constant(ir.IntType(32), 0)

    # ==================== typeof 表达式 ====================

    def visitTypeofExpr(self, ctx: EzLangParser.TypeofExprContext):
        """typeof 表达式：返回稳定类型 ID。"""
        if ctx.type_() is not None:
            type_name = self._type_ctx_name(ctx.type_())
        else:
            type_name = self._typeof_name_from_expr(ctx.unaryExpression())
        return ir.Constant(ir.IntType(32), self._type_id(type_name))

    def visitTypeofPrimaryExpr(self, ctx: EzLangParser.TypeofPrimaryExprContext):
        return self.visitTypeofExpr(ctx.typeofExpr())

    # ==================== flow 并发块 ====================

    def visitFlowBlock(self, ctx: EzLangParser.FlowBlockContext):
        """flow 块：保留运行时边界，并把块内 return 捕获为表达式结果。"""
        if self.builder is not None:
            self.builder.call(self._flow_enter, [])
        result_type = self._infer_block_return_type(ctx.block())
        result_alloca = None
        exit_block = None
        if self.builder is not None and not isinstance(result_type, ir.VoidType):
            result_alloca = self.builder.alloca(result_type, name="_flow_result")
            self.builder.store(self._zero_constant(result_type), result_alloca)
            exit_block = self.builder.append_basic_block(name="flow_exit")
            self._parallel_result_stack.append(result_alloca)
            self._parallel_exit_stack.append(exit_block)
            self._parallel_arena_depth_stack.append(len(self._arena_scope_stack))
        self._flow_future_stack.append({})
        self._flow_depth += 1
        self._eval(ctx.block())
        self._flow_depth -= 1
        if result_alloca is not None:
            if self._parallel_result_stack and self._parallel_result_stack[-1] is result_alloca:
                self._parallel_result_stack.pop()
            if self._parallel_exit_stack and self._parallel_exit_stack[-1] is exit_block:
                self._parallel_exit_stack.pop()
            if self._parallel_arena_depth_stack:
                self._parallel_arena_depth_stack.pop()
            if self.builder is not None and not self.builder.block.is_terminated:
                self.builder.branch(exit_block)
            self.builder.position_at_start(exit_block)
        if self.builder is not None and not self.builder.block.is_terminated:
            self._join_pending_flow_futures()
        if self._flow_future_stack:
            self._flow_future_stack.pop()
        if self.builder is not None and not self.builder.block.is_terminated:
            self.builder.call(self._flow_exit, [])
        if result_alloca is not None:
            return self.builder.load(result_alloca, name="flow_value")
        return None

    def visitFlowBlockExpr(self, ctx: EzLangParser.FlowBlockExprContext):
        return self.visitFlowBlock(ctx.flowBlock())

    # ==================== parallel 并发块 ====================

    def visitParallelBlock(self, ctx: EzLangParser.ParallelBlockContext):
        """parallel 块：先保留运行时 ABI 边界，当前按同步块 lowering。"""
        if self.builder is not None:
            self.builder.call(self._parallel_enter, [])
        result_type = self._infer_block_return_type(ctx.block())
        result_alloca = None
        exit_block = None
        if self.builder is not None and not isinstance(result_type, ir.VoidType):
            result_alloca = self.builder.alloca(result_type, name="_parallel_result")
            self.builder.store(self._zero_constant(result_type), result_alloca)
            exit_block = self.builder.append_basic_block(name="parallel_exit")
            self._parallel_result_stack.append(result_alloca)
            self._parallel_exit_stack.append(exit_block)
            self._parallel_arena_depth_stack.append(len(self._arena_scope_stack))
        self._eval(ctx.block())
        if result_alloca is not None:
            if self._parallel_result_stack and self._parallel_result_stack[-1] is result_alloca:
                self._parallel_result_stack.pop()
            if self._parallel_exit_stack and self._parallel_exit_stack[-1] is exit_block:
                self._parallel_exit_stack.pop()
            if self._parallel_arena_depth_stack:
                self._parallel_arena_depth_stack.pop()
            if self.builder is not None and not self.builder.block.is_terminated:
                self.builder.branch(exit_block)
            self.builder.position_at_start(exit_block)
        if self.builder is not None and not self.builder.block.is_terminated:
            self.builder.call(self._parallel_exit, [])
        if result_alloca is not None:
            return self.builder.load(result_alloca, name="parallel_value")
        return None

    def visitParallelBlockExpr(self, ctx: EzLangParser.ParallelBlockExprContext):
        return self.visitParallelBlock(ctx.parallelBlock())

    def _gen_race_call(self, args_ctx, provided: dict[str, ir.Value]):
        """race hook：支持旧的 task 参数，也支持文档中的 pl 分支数组。"""
        i32 = ir.IntType(32)
        task_arg = provided.get('task')
        timeout_arg = provided.get('timeout', ir.Constant(i32, 0))
        pl_array = None

        if task_arg is None:
            branch_count = 0
            if args_ctx is not None:
                for named in args_ctx.namedArg():
                    if named.VAR_IDENTIFIER() is None or named.expression() is None:
                        continue
                    if named.VAR_IDENTIFIER().getText() != 'pl':
                        continue
                    array_expr = named.expression().getText().strip()
                    array_ctx = named.expression()
                    if array_ctx is not None:
                        array_literal = self._find_array_literal_ctx(array_ctx)
                        if array_literal is not None and array_literal.expressionList() is not None:
                            pl_array = array_literal
                            branch_count = len(array_literal.expressionList().expression())
                    if branch_count == 0 and array_expr.startswith('[') and array_expr.endswith(']'):
                        branch_count = 1
                    break
            task_arg = ir.Constant(i32, branch_count)
        elif task_arg.type != i32:
            task_arg = self._coerce_value(task_arg, i32) if isinstance(task_arg.type, ir.IntType) else ir.Constant(i32, 0)

        timeout_arg = self._coerce_value(timeout_arg, i32) if timeout_arg.type != i32 else timeout_arg
        race_hook = self.builder.call(self._flow_race, [task_arg, timeout_arg])
        if pl_array is None:
            return race_hook

        async_result = self._gen_race_i32_runtime_call(pl_array, timeout_arg)
        if async_result is not None:
            return async_result

        first_branch = self._first_function_literal_in_array(pl_array)
        if first_branch is None:
            return race_hook
        params = first_branch.paramList()
        if params is not None and params.param():
            return race_hook

        branch_type = self._infer_function_literal_return_type(first_branch)
        result_type = i32 if isinstance(branch_type, ir.VoidType) else branch_type
        result_alloca = self.builder.alloca(result_type, name="_race_result")
        self.builder.store(self._zero_constant(result_type), result_alloca)
        exit_block = self.builder.append_basic_block(name="race_exit")
        self._parallel_result_stack.append(result_alloca)
        self._parallel_exit_stack.append(exit_block)
        self._parallel_arena_depth_stack.append(len(self._arena_scope_stack))
        expr_block = self._find_block_expr_ctx(first_branch.expression()) if first_branch.expression() is not None else None
        if first_branch.block() is not None:
            self._eval(first_branch.block())
        elif expr_block is not None:
            self._eval(expr_block)
        elif first_branch.expression() is not None:
            branch_value = self._eval(first_branch.expression())
            if branch_value is not None and not isinstance(branch_type, ir.VoidType):
                if self._is_aggregate_ptr(branch_value):
                    branch_value = self.builder.load(branch_value)
                branch_value = self._coerce_value(branch_value, branch_type)
                self.builder.store(branch_value, result_alloca)
        if self._parallel_result_stack and self._parallel_result_stack[-1] is result_alloca:
            self._parallel_result_stack.pop()
        if self._parallel_exit_stack and self._parallel_exit_stack[-1] is exit_block:
            self._parallel_exit_stack.pop()
        if self._parallel_arena_depth_stack:
            self._parallel_arena_depth_stack.pop()
        if self.builder is not None and not self.builder.block.is_terminated:
            self.builder.branch(exit_block)
        self.builder.position_at_start(exit_block)
        if isinstance(branch_type, ir.VoidType):
            return race_hook
        return self.builder.load(result_alloca, name="race_value")

    def _function_literals_in_array(self, array_ctx) -> list:
        expr_list = array_ctx.expressionList() if array_ctx is not None else None
        if expr_list is None or not expr_list.expression():
            return []
        result = []
        for expr in expr_list.expression():
            fn = self._find_function_literal_ctx(expr)
            if fn is None:
                return []
            result.append(fn)
        return result

    def _gen_race_i32_runtime_call(self, array_ctx, timeout_arg: ir.Value) -> ir.Value | None:
        """把 race(pl=[() => I32, ...]) lower 为真实并发调度。"""
        branches = self._function_literals_in_array(array_ctx)
        if not branches:
            return None
        i32 = ir.IntType(32)
        branch_funcs = []
        for fn_lit in branches:
            params = fn_lit.paramList()
            if params is not None and params.param():
                return None
            if self._ctx_references_local_capture(fn_lit):
                return None
            ret_type = self._infer_function_literal_return_type(fn_lit)
            if ret_type != i32:
                return None
            branch_funcs.append(self._gen_race_i32_branch_function(fn_lit))
        self._require_runtime()
        fn_ptr_type = ir.PointerType(ir.FunctionType(i32, []))
        array_type = ir.ArrayType(fn_ptr_type, len(branch_funcs))
        array_ptr = self.builder.alloca(array_type, name='_race_branches')
        for index, func in enumerate(branch_funcs):
            slot = self.builder.gep(array_ptr, [ir.Constant(i32, 0), ir.Constant(i32, index)], inbounds=True)
            self.builder.store(func, slot)
        first_slot = self.builder.gep(array_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        timed_out = self.builder.alloca(i32, name='_race_timed_out')
        self.builder.store(ir.Constant(i32, 0), timed_out)
        runtime_type = ir.FunctionType(i32, [ir.PointerType(fn_ptr_type), i32, i32, ir.PointerType(i32)])
        runtime = self._get_or_declare_function('__ezrt_race_i32', runtime_type)
        result = self.builder.call(runtime, [first_slot, ir.Constant(i32, len(branch_funcs)), timeout_arg, timed_out], name='_race_i32')
        self._emit_throw_check_after_call()
        return result

    def _gen_race_i32_branch_function(self, fn_lit) -> ir.Function:
        """生成零捕获 race I32 分支函数。"""
        i32 = ir.IntType(32)
        name = f"__ez_race_branch_{self._race_branch_counter}"
        self._race_branch_counter += 1
        func = ir.Function(self.module, ir.FunctionType(i32, []), name)
        entry = func.append_basic_block('entry')
        prev_builder = self.builder
        prev_func = self.current_function
        prev_locals = self.locals
        prev_unsigned = self._save_unsigned_state()
        prev_type_names = self._locals_type_names
        prev_flow_depth = self._flow_depth
        prev_arena_stack = self._arena_scope_stack
        prev_catch_exit_blocks = self.catch_exit_blocks
        prev_catch_error_allocas = self.catch_error_allocas
        prev_catch_result_allocas = self.catch_result_allocas
        prev_parallel_result_stack = self._parallel_result_stack
        prev_parallel_exit_stack = self._parallel_exit_stack
        prev_parallel_arena_depth_stack = self._parallel_arena_depth_stack
        prev_loop_exit_blocks = self.loop_exit_blocks
        prev_loop_continue_blocks = self.loop_continue_blocks

        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._flow_depth = max(prev_flow_depth, 1)
        self._arena_scope_stack = []
        self.catch_exit_blocks = []
        self.catch_error_allocas = []
        self.catch_result_allocas = []
        self._parallel_result_stack = []
        self._parallel_exit_stack = []
        self._parallel_arena_depth_stack = []
        self.loop_exit_blocks = []
        self.loop_continue_blocks = []
        throw_exit = func.append_basic_block('throw_exit')
        self._function_throw_exit_stack.append(throw_exit)
        self._function_return_type_ctx_stack.append(fn_lit.type_())

        body = fn_lit.block() or fn_lit.expression()
        val = self._eval(body) if body is not None else ir.Constant(i32, 0)
        self._finish_function_with_throw_exit(i32, val)
        self._function_return_type_ctx_stack.pop()

        self.builder = prev_builder
        self.current_function = prev_func
        self.locals = prev_locals
        self._locals_type_names = prev_type_names
        self._flow_depth = prev_flow_depth
        self._arena_scope_stack = prev_arena_stack
        self.catch_exit_blocks = prev_catch_exit_blocks
        self.catch_error_allocas = prev_catch_error_allocas
        self.catch_result_allocas = prev_catch_result_allocas
        self._parallel_result_stack = prev_parallel_result_stack
        self._parallel_exit_stack = prev_parallel_exit_stack
        self._parallel_arena_depth_stack = prev_parallel_arena_depth_stack
        self.loop_exit_blocks = prev_loop_exit_blocks
        self.loop_continue_blocks = prev_loop_continue_blocks
        self._restore_unsigned_state(prev_unsigned)
        return func

    def _parallel_block_from_initializer(self, initializer):
        """识别 flow 内 const x = parallel { ... } 初始化。"""
        if initializer is None:
            return None
        if isinstance(initializer, EzLangParser.ParallelBlockExprContext):
            return initializer.parallelBlock()
        if hasattr(initializer, 'parallelBlock') and initializer.parallelBlock() is not None:
            return initializer.parallelBlock()
        if hasattr(initializer, 'getChildCount'):
            for i in range(initializer.getChildCount()):
                result = self._parallel_block_from_initializer(initializer.getChild(i))
                if result is not None:
                    return result
        return None

    def _ctx_references_local_capture(self, ctx) -> bool:
        """保守检测零捕获任务是否读取了外层局部变量。"""
        local_names = set(self.locals.keys())
        if not local_names:
            return False

        def walk(node) -> bool:
            if node is None:
                return False
            if isinstance(node, EzLangParser.IdentifierExprContext):
                token = node.VAR_IDENTIFIER() or node.TYPE_IDENTIFIER()
                return token is not None and token.getText() in local_names
            if hasattr(node, 'getChildCount'):
                for i in range(node.getChildCount()):
                    if walk(node.getChild(i)):
                        return True
            return False

        return walk(ctx)

    def _start_flow_parallel_i32_future(self, name: str, parallel_block) -> ir.Value | None:
        """flow 内 parallel I32 块启动为后台任务，读取变量时 join。"""
        if self._flow_depth <= 0 or not self._flow_future_stack or parallel_block is None:
            return None
        if self._ctx_references_local_capture(parallel_block):
            return None
        result_type = self._infer_block_return_type(parallel_block.block())
        if result_type != ir.IntType(32):
            return None
        fake_fn = type('ParallelFutureLiteral', (), {})()
        fake_fn.block = lambda: parallel_block.block()
        fake_fn.expression = lambda: None
        fake_fn.type_ = lambda: None
        branch = self._gen_race_i32_branch_function(fake_fn)
        self._require_runtime()
        i8_ptr = ir.PointerType(ir.IntType(8))
        start_type = ir.FunctionType(i8_ptr, [ir.PointerType(ir.FunctionType(ir.IntType(32), []))])
        start = self._get_or_declare_function('__ezrt_task_start_i32', start_type)
        handle = self.builder.call(start, [branch], name=f'_{name}_future')
        self._flow_future_stack[-1][name] = {'handle': handle, 'joined': False}
        return handle

    def _join_flow_future(self, name: str) -> None:
        if not self._flow_future_stack or name not in self._flow_future_stack[-1]:
            return
        meta = self._flow_future_stack[-1][name]
        if meta.get('joined'):
            return
        alloca = self.locals.get(name)
        if alloca is None:
            return
        join_type = ir.FunctionType(ir.IntType(32), [ir.PointerType(ir.IntType(8))])
        join = self._get_or_declare_function('__ezrt_task_join_i32', join_type)
        value = self.builder.call(join, [meta['handle']], name=f'_{name}_joined')
        self._emit_throw_check_after_call()
        if self.builder is not None and not self.builder.block.is_terminated:
            self.builder.store(value, alloca)
            meta['joined'] = True

    def _join_pending_flow_futures(self) -> None:
        if not self._flow_future_stack:
            return
        for name in list(self._flow_future_stack[-1].keys()):
            if self.builder is None or self.builder.block.is_terminated:
                return
            self._join_flow_future(name)

    def _find_array_literal_ctx(self, ctx):
        if ctx is None:
            return None
        if hasattr(ctx, 'arrayLiteral') and ctx.arrayLiteral() is not None:
            return ctx.arrayLiteral()
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                child = ctx.getChild(i)
                result = self._find_array_literal_ctx(child)
                if result is not None:
                    return result
        return None

    def _first_function_literal_in_array(self, array_ctx):
        expr_list = array_ctx.expressionList() if array_ctx is not None else None
        if expr_list is None or not expr_list.expression():
            return None
        return self._find_function_literal_ctx(expr_list.expression()[0])

    def _find_function_literal_ctx(self, ctx):
        if ctx is None:
            return None
        if hasattr(ctx, 'functionLiteral') and ctx.functionLiteral() is not None:
            return ctx.functionLiteral()
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._find_function_literal_ctx(ctx.getChild(i))
                if result is not None:
                    return result
        return None

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
        """数组/List/Dict 索引。"""
        obj_ptr = self._eval(ctx.postfixExpression())
        if obj_ptr is None:
            return None
        index_val = self._eval(ctx.expression())
        if index_val is None:
            return None

        pointee = obj_ptr.type.pointee if hasattr(obj_ptr.type, 'pointee') else None
        if isinstance(pointee, ir.IdentifiedStructType) and pointee.name == 'Dict':
            key_type, value_type = self._dict_item_types_for_value(obj_ptr)
            return self._gen_dict_lookup_value(obj_ptr, index_val, key_type, value_type)

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
            self._mark_unsigned(elem_ptr, self._list_type_is_unsigned(obj_ptr.type))
            return self._load_with_unsigned(elem_ptr)

        # 兼容旧裸数组指针
        gep = self.builder.gep(obj_ptr, [
            ir.Constant(ir.IntType(32), 0),
            index_val
        ], inbounds=True)
        return self._load_with_unsigned(gep)

    def _optional_unwrapped_value(self, ctx) -> ir.Value | None:
        opt_ptr = self._eval(ctx)
        if opt_ptr is None or not hasattr(opt_ptr, 'type'):
            return None
        opt_type = opt_ptr.type.pointee if isinstance(opt_ptr.type, ir.PointerType) else opt_ptr.type
        if not self._is_optional_type(opt_type):
            return opt_ptr
        if not isinstance(opt_ptr.type, ir.PointerType):
            tmp = self.builder.alloca(opt_type, name='_optional_tmp')
            self.builder.store(opt_ptr, tmp)
            opt_ptr = tmp
        value_ptr = self.builder.gep(opt_ptr, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), 1),
        ], inbounds=True)
        value_type = opt_type.elements[1]
        if isinstance(value_type, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
            return value_ptr
        return self._load_with_unsigned(value_ptr, name='_optional_value')

    def visitTypeAssertion(self, ctx: EzLangParser.TypeAssertionContext):
        return self._optional_unwrapped_value(ctx.postfixExpression())

    def visitOptionalUnwrap(self, ctx: EzLangParser.OptionalUnwrapContext):
        return self._optional_unwrapped_value(ctx.postfixExpression())

    # 函数调用
    def visitCall(self, ctx: EzLangParser.CallContext):
        target_expr = ctx.postfixExpression()

        if isinstance(target_expr, EzLangParser.MemberAccessContext) and isinstance(target_expr.postfixExpression(), EzLangParser.OptionalUnwrapContext):
            safe_call = self._optional_method_call(
                ctx,
                target_expr.postfixExpression(),
                target_expr.VAR_IDENTIFIER().getText(),
                ctx.namedArgList(),
            )
            if safe_call is not None:
                return safe_call

        # 方法调用：obj.method(...) → 先求值 postfixExpression
        # visitMemberAccess 返回 function 并设置 _method_this
        self._method_this = None
        func = self._eval(target_expr)
        method_this = self._method_this
        # _method_this 只属于当前调用目标。求实参时可能发生嵌套方法调用，不能让内层 this 泄漏到外层调用。
        self._method_this = None
        curried_target = None
        curried_closure_value = None
        if func is not None and isinstance(func, ir.Value) and hasattr(func, 'type'):
            closure_type = func.type.pointee if isinstance(func.type, ir.PointerType) else None
            curried_target = self._curried_closures.get(str(closure_type)) if closure_type is not None else None
            if curried_target is not None:
                curried_closure_value = func

        # 如果 _eval 没返回可调用对象，尝试从标识符查找（通过 primaryExpression 间接访问）
        name = None
        if curried_target is None and not self._is_callable_value(func):
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
                    if name in self.struct_generic_templates:
                        name = self._struct_name_from_generic_args(name, id_ctx.genericArgs())
                    else:
                        type_args = [self._map_type(t) for t in id_ctx.genericArgs().type_()]
                        name = self._monomorphize(name, type_args)
            elif hasattr(inner, 'VAR_IDENTIFIER') and inner.VAR_IDENTIFIER():
                name = inner.VAR_IDENTIFIER().getText()
                # 泛型函数调用（primaryExpression 直接返回 IdentifierExprContext 时不走上面分支）
                if hasattr(inner, 'genericArgs') and inner.genericArgs() is not None:
                    if name in self.struct_generic_templates:
                        name = self._struct_name_from_generic_args(name, inner.genericArgs())
                    else:
                        type_args = [self._map_type(t) for t in inner.genericArgs().type_()]
                        name = self._monomorphize(name, type_args)
            elif hasattr(inner, 'TYPE_IDENTIFIER') and inner.TYPE_IDENTIFIER():
                name = inner.TYPE_IDENTIFIER().getText()
            else:
                return None

            if self._should_drop_log_call(name, ctx.namedArgList()):
                return None

            # 判断是结构体构造还是函数调用
            if name in self.structs or name in self.struct_generic_templates:
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
        is_compiler_builtin = name and any(
            name == base or name.startswith(f'{base}_') for base in self._compiler_builtin_declares
        )

        if curried_target is None and (func is None or not self._is_callable_value(func)):
            # compiler builtin / 未实现集合函数不生成外部声明。
            if is_compiler_builtin or is_unimplemented_collection:
                func = None
            elif name in self.generic_templates:
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

        if curried_target is not None:
            tramp_func, placeholder_names = curried_target
            func = tramp_func
            func_name = tramp_func.name
            expected_names = list(placeholder_names)
        else:
            expected_names = self.func_param_names.get(func_name, [])

        if self._should_drop_log_call(func_name, ctx.namedArgList()):
            return None

        # 获取函数期望的参数名列表和默认值
        defaults = self.func_defaults.get(func_name, {})

        # 解析调用时提供的具名参数，检测 ? 占位符（柯里化）
        provided: dict[str, any] = {}
        placeholder_params: list[str] = []  # 柯里化：需要延迟绑定的参数名
        args = ctx.namedArgList()
        if args and args.namedArg():
            for a in args.namedArg():
                if a.VAR_IDENTIFIER() is not None and a.expression() is not None:
                    pname = a.VAR_IDENTIFIER().getText()
                    if self._flow_depth > 0 and func_name == 'race' and pname == 'pl':
                        continue
                    # 检查表达式是否为 ? 占位符
                    if a.expression().getText().strip() == '?':
                        placeholder_params.append(pname)
                    else:
                        val = self._eval(a.expression())
                        if val is not None:
                            provided[pname] = val

        if curried_target is None and name in self.generic_templates and func_name == name:
            inferred_args = self._infer_generic_call_type_args(name, provided)
            if inferred_args is not None:
                func_name = self._monomorphize(name, inferred_args)
                name = func_name
                try:
                    func = self.module.get_global(func_name)
                except KeyError:
                    func = None
                expected_names = self.func_param_names.get(func_name, [])
                defaults = self.func_defaults.get(func_name, {})

        if self._flow_depth > 0 and func_name == 'race':
            return self._gen_race_call(args, provided)

        # 如果存在 ? 占位符，生成柯里化闭包
        if placeholder_params:
            return self._gen_curried_call(func, func_name, expected_names, provided, placeholder_params)

        # 按函数参数顺序构建实参列表（具名重排 + 默认值注入）
        call_args = []
        if expected_names:
            if curried_target is not None and curried_closure_value is not None:
                call_args.append(curried_closure_value)
            # 方法调用：首个参数是 this
            if method_this is not None:
                call_args.append(method_this)
            for pname in expected_names:
                if method_this is not None and pname == expected_names[0]:
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
            if method_this is not None and isinstance(func_type_for_args, ir.FunctionType) and func_type_for_args.args:
                call_args.append(method_this)
            call_args.extend(provided.values())

        # 检查是否为编译器内建函数
        intrinsic_result = self._try_gen_intrinsic_call(func_name, call_args)
        if intrinsic_result is not None:
            if intrinsic_result is self._void_intrinsic_result:
                return None
            return intrinsic_result

        if func is None:
            return self._zero_constant(self._call_return_type(ctx))

        func_type = func.type.pointee if isinstance(func.type, ir.PointerType) else None
        if self._flow_depth > 0 and func_name == 'sleep' and call_args:
            sleep_arg = self._coerce_value(call_args[0], ir.IntType(64))
            return self.builder.call(self._flow_sleep, [sleep_arg])
        sret_type = self._sret_functions.get(func_name)
        abi_arg_types = list(func_type.args) if func_type is not None else []
        if sret_type is not None:
            ret_slot = self._arena_allocate(sret_type, name=f"_{func_name}_ret")
            call_args = [ret_slot] + call_args

        if func_type is not None:
            call_args = [
                self._coerce_value(arg, abi_arg_types[i]) if i < len(abi_arg_types) else arg
                for i, arg in enumerate(call_args)
            ]
            call_args = [
                self._load_if_aggregate_ptr(arg)
                if i < len(abi_arg_types) and arg.type != abi_arg_types[i] and self._is_aggregate_ptr(arg)
                else arg
                for i, arg in enumerate(call_args)
            ]

        call = self.builder.call(func, call_args)
        if sret_type is not None:
            self._emit_throw_check_after_call()
            ret_dict_types = self.func_return_dict_types.get(func_name)
            if ret_dict_types is not None:
                self._mark_dict_item_types(ret_slot, ret_dict_types[0], ret_dict_types[1])
            return ret_slot
        call = self._restore_c_abi_return(func_name, call)
        self._mark_unsigned(call, self.func_return_unsigned.get(func_name, False))
        ret_dict_types = self.func_return_dict_types.get(func_name)
        if ret_dict_types is not None:
            self._mark_dict_item_types(call, ret_dict_types[0], ret_dict_types[1])
        self._emit_throw_check_after_call()
        return call

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

    def _value_type_for_generic_inference(self, value: ir.Value) -> ir.Type:
        """泛型推导使用值语义类型，聚合指针按其指向类型推导。"""
        if self._is_aggregate_ptr(value):
            return value.type.pointee
        return value.type

    def _infer_generic_type_from_ctx(self, type_ctx, actual_type: ir.Type, type_map: dict[str, ir.Type], generic_names: set[str]) -> None:
        """根据形参类型语法和实参 LLVM 类型推导泛型参数。"""
        if type_ctx is None or actual_type is None:
            return
        P = EzLangParser
        if isinstance(type_ctx, P.OptionalTypeContext):
            if self._is_optional_type(actual_type):
                self._infer_generic_type_from_ctx(type_ctx.type_(), actual_type.elements[1], type_map, generic_names)
            return
        if isinstance(type_ctx, (P.ArrayTypeContext, P.ListTypeContext)):
            list_type = actual_type.pointee if isinstance(actual_type, ir.PointerType) else actual_type
            if self._is_list_type(list_type):
                self._infer_generic_type_from_ctx(type_ctx.type_(), list_type.elements[0].pointee.pointee, type_map, generic_names)
            return
        if isinstance(type_ctx, P.PointerTypeContext):
            if isinstance(actual_type, ir.PointerType):
                self._infer_generic_type_from_ctx(type_ctx.type_(), actual_type.pointee, type_map, generic_names)
            return
        if isinstance(type_ctx, P.ParenTypeContext):
            self._infer_generic_type_from_ctx(type_ctx.type_(), actual_type, type_map, generic_names)
            return
        if hasattr(type_ctx, 'baseType') and type_ctx.baseType() is not None:
            bt = type_ctx.baseType()
            if bt.TYPE_IDENTIFIER() is None:
                return
            name = bt.TYPE_IDENTIFIER().getText()
            if name in generic_names and bt.genericArgs() is None:
                type_map.setdefault(name, actual_type)
                return
            if name == 'List' and bt.genericArgs() is not None:
                list_type = actual_type.pointee if isinstance(actual_type, ir.PointerType) else actual_type
                if self._is_list_type(list_type):
                    args = list(bt.genericArgs().type_())
                    if args:
                        self._infer_generic_type_from_ctx(args[0], list_type.elements[0].pointee.pointee, type_map, generic_names)

    def _infer_generic_call_type_args(self, base_name: str, provided: dict[str, ir.Value]) -> list[ir.Type] | None:
        """从命名实参推导泛型函数类型参数。"""
        template = self.generic_templates.get(base_name)
        if template is None or len(template) < 2:
            return None
        generic_names, template_ctx = template[0], template[1]
        if not generic_names or not hasattr(template_ctx, 'functionLiteral'):
            return None
        fn_lit = template_ctx.functionLiteral()
        if fn_lit is None or fn_lit.paramList() is None:
            return None
        type_map: dict[str, ir.Type] = {}
        generic_set = set(generic_names)
        for param in fn_lit.paramList().param():
            pname = param.VAR_IDENTIFIER().getText()
            if pname not in provided:
                continue
            actual_type = self._value_type_for_generic_inference(provided[pname])
            self._infer_generic_type_from_ctx(param.type_(), actual_type, type_map, generic_set)
        if any(name not in type_map for name in generic_names):
            return None
        return [type_map[name] for name in generic_names]

    @staticmethod
    def _is_callable_value(value) -> bool:
        if isinstance(value, ir.Function):
            return True
        return isinstance(value, ir.Value) and isinstance(value.type, ir.PointerType) and isinstance(value.type.pointee, ir.FunctionType)

    def _blob_data_ptr(self, value: ir.Value) -> ir.Value:
        """提取 Blob.data 指针，供 std/mem 内建函数操作底层字节。"""
        i8_ptr = ir.PointerType(ir.IntType(8))
        blob_type = self.structs.get('Blob')
        if value.type == i8_ptr:
            return value
        if blob_type is not None and isinstance(value.type, ir.PointerType) and value.type.pointee == blob_type:
            data_ptr = self.builder.gep(value, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), 0),
            ], inbounds=True)
            return self.builder.load(data_ptr)
        if blob_type is not None and value.type == blob_type:
            return self.builder.extract_value(value, 0)
        return self.builder.bitcast(value, i8_ptr) if value.type != i8_ptr else value

    def _try_gen_intrinsic_call(self, name: str, call_args: list) -> Optional[ir.Value]:
        """编译器内建函数：将标准库函数映射为 LLVM 内建操作"""
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)

        if name == 'copy' and len(call_args) >= 3:
            # copy(dst: Blob, src: Blob, count: I64) → llvm.memcpy
            memcpy = self.module.get_global('llvm.memcpy.p0.p0.i64')
            dst = self._blob_data_ptr(call_args[0])
            src = self._blob_data_ptr(call_args[1])
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
            dst = self._blob_data_ptr(call_args[0])
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

        list_builtin = self._list_builtin_base(name)
        if list_builtin == 'listLen' and len(call_args) >= 1:
            return self._gen_list_len(call_args[0])
        if list_builtin == 'listPush' and len(call_args) >= 2:
            self._gen_list_push(call_args[0], call_args[1])
            return self._void_intrinsic_result
        if list_builtin == 'listPop' and len(call_args) >= 1:
            return self._gen_list_pop(call_args[0])
        if list_builtin == 'listShift' and len(call_args) >= 1:
            return self._gen_list_shift(call_args[0])
        if list_builtin == 'listUnshift' and len(call_args) >= 2:
            self._gen_list_unshift(call_args[0], call_args[1])
            return self._void_intrinsic_result
        if list_builtin == 'listSlice' and len(call_args) >= 3:
            return self._gen_list_slice(call_args[0], call_args[1], call_args[2])
        if list_builtin == 'listFind' and len(call_args) >= 2:
            return self._gen_list_find(call_args[0], call_args[1])
        if list_builtin == 'listFilter' and len(call_args) >= 2:
            return self._gen_list_filter(call_args[0], call_args[1])
        if list_builtin == 'listMap' and len(call_args) >= 2:
            return self._gen_list_map(name, call_args[0], call_args[1])
        if list_builtin == 'listSort' and len(call_args) >= 2:
            self._gen_list_sort(call_args[0], call_args[1])
            return self._void_intrinsic_result

        dict_builtin = self._dict_builtin_base(name)
        if dict_builtin == 'dictLen' and len(call_args) >= 1:
            return self._gen_dict_len(call_args[0])
        if dict_builtin == 'dictHas' and len(call_args) >= 2:
            return self._gen_dict_has(name, call_args[0], call_args[1])
        if dict_builtin == 'dictDelete' and len(call_args) >= 2:
            return self._gen_dict_delete(name, call_args[0], call_args[1])
        if dict_builtin == 'dictKeys' and len(call_args) >= 1:
            return self._gen_dict_keys(name, call_args[0])
        if dict_builtin == 'dictValues' and len(call_args) >= 1:
            return self._gen_dict_values(name, call_args[0])

        return None

    def _list_builtin_base(self, name: str) -> str | None:
        for base in self._list_collection_builtins:
            if name == base or name.startswith(f'{base}_'):
                return base
        return None

    def _dict_builtin_base(self, name: str) -> str | None:
        for base in self._dict_collection_builtins:
            if name == base or name.startswith(f'{base}_'):
                return base
        return None

    def _log_level_constant_from_call(self, func_name: str, args_ctx) -> int | None:
        levels = {
            'logTraceMsg': 0,
            'logDebugMsg': 1,
            'logInfoMsg': 2,
            'logWarnMsg': 3,
            'logErrorMsg': 4,
            'logTrace': 0,
            'logDebug': 1,
            'logInfo': 2,
            'logWarn': 3,
            'logError': 4,
        }
        if func_name in levels:
            return levels[func_name]
        if func_name not in {'logWrite', 'logWriteFields', 'logWriteAt'} or args_ctx is None:
            return None
        for named in args_ctx.namedArg():
            if named.VAR_IDENTIFIER() is None or named.expression() is None:
                continue
            if named.VAR_IDENTIFIER().getText() != 'level':
                continue
            text = named.expression().getText().strip()
            if text in levels:
                return levels[text]
            if re.fullmatch(r'\d+', text):
                return int(text)
            return None
        return None

    def _should_drop_log_call(self, func_name: str, args_ctx) -> bool:
        if self.log_compile_min_level is None:
            return False
        level = self._log_level_constant_from_call(func_name, args_ctx)
        return level is not None and level < self.log_compile_min_level

    def _collection_type_args(self, name: str) -> list[ir.Type]:
        meta = self._collection_mono_types.get(name)
        return list(meta[1]) if meta is not None else []

    @staticmethod
    def _is_list_type(t: ir.Type) -> bool:
        return (
            isinstance(t, ir.LiteralStructType)
            and len(t.elements) == 4
            and isinstance(t.elements[0], ir.PointerType)
            and isinstance(t.elements[0].pointee, ir.PointerType)
            and t.elements[1] == ir.IntType(64)
            and t.elements[2] == ir.IntType(64)
            and t.elements[3] == ir.IntType(64)
        )

    def _as_list_ptr(self, value: ir.Value) -> ir.Value | None:
        if isinstance(value.type, ir.PointerType) and self._is_list_type(value.type.pointee):
            return value
        if self._is_list_type(value.type):
            tmp = self.builder.alloca(value.type, name='_list_tmp')
            self.builder.store(value, tmp)
            return tmp
        return None

    def _list_elem_type(self, list_ptr: ir.Value) -> ir.Type:
        pages_type = list_ptr.type.pointee.elements[0]
        return pages_type.pointee.pointee

    def _as_i64(self, value: ir.Value) -> ir.Value:
        i64 = ir.IntType(64)
        if value.type == i64:
            return value
        if isinstance(value.type, ir.IntType):
            return self.builder.sext(value, i64) if value.type.width < 64 else self.builder.trunc(value, i64)
        return ir.Constant(i64, 0)

    def _list_field_ptr(self, list_ptr: ir.Value, index: int) -> ir.Value:
        return self.builder.gep(list_ptr, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), index),
        ], inbounds=True)

    def _list_length(self, list_ptr: ir.Value) -> ir.Value:
        return self.builder.load(self._list_field_ptr(list_ptr, 1), name='_list_len')

    def _list_element_ptr(self, list_ptr: ir.Value, index: ir.Value) -> ir.Value:
        i64 = ir.IntType(64)
        index = self._as_i64(index)
        pages = self.builder.load(self._list_field_ptr(list_ptr, 0), name='_list_pages')
        page_idx = self.builder.udiv(index, ir.Constant(i64, 8), name='_list_page_idx')
        slot_idx = self.builder.urem(index, ir.Constant(i64, 8), name='_list_slot_idx')
        page_slot = self.builder.gep(pages, [page_idx], inbounds=True)
        page = self.builder.load(page_slot, name='_list_page')
        return self.builder.gep(page, [slot_idx], inbounds=True)

    def _coerce_list_item(self, value: ir.Value, elem_type: ir.Type) -> ir.Value:
        if self._is_aggregate_ptr(value) and value.type.pointee == elem_type:
            value = self.builder.load(value)
        if value.type != elem_type:
            value = self._coerce_value(value, elem_type)
        return value

    def _optional_value(self, elem_type: ir.Type, ok: bool, value: ir.Value | None = None) -> ir.Value:
        opt_type = ir.LiteralStructType([ir.IntType(1), elem_type])
        if value is None:
            value = self._zero_constant(elem_type)
        else:
            value = self._coerce_list_item(value, elem_type)
        result = ir.Constant(opt_type, ir.Undefined)
        result = self.builder.insert_value(result, ir.Constant(ir.IntType(1), int(ok)), 0)
        return self.builder.insert_value(result, value, 1)

    def _gen_list_len(self, list_value: ir.Value) -> ir.Value:
        list_ptr = self._as_list_ptr(list_value)
        if list_ptr is None:
            return ir.Constant(ir.IntType(64), 0)
        return self._list_length(list_ptr)

    def _gen_list_push(self, list_value: ir.Value, item: ir.Value) -> None:
        list_ptr = self._as_list_ptr(list_value)
        if list_ptr is None:
            return None
        i64 = ir.IntType(64)
        old_len = self._list_length(list_ptr)
        new_len = self.builder.add(old_len, ir.Constant(i64, 1), name='_list_new_len')
        self._list_ensure_capacity(list_ptr, new_len)
        elem_type = self._list_elem_type(list_ptr)
        elem_ptr = self._list_element_ptr(list_ptr, old_len)
        self.builder.store(self._coerce_list_item(item, elem_type), elem_ptr)
        self.builder.store(new_len, self._list_field_ptr(list_ptr, 1))
        return None

    def _gen_list_pop(self, list_value: ir.Value) -> ir.Value:
        list_ptr = self._as_list_ptr(list_value)
        if list_ptr is None:
            return self._optional_value(ir.IntType(32), False)
        i64 = ir.IntType(64)
        elem_type = self._list_elem_type(list_ptr)
        opt_type = ir.LiteralStructType([ir.IntType(1), elem_type])
        result_ptr = self.builder.alloca(opt_type, name='_list_pop_result')
        length = self._list_length(list_ptr)
        is_empty = self.builder.icmp_unsigned('==', length, ir.Constant(i64, 0), name='_list_empty')
        empty_block = self.builder.append_basic_block('list_pop_empty')
        value_block = self.builder.append_basic_block('list_pop_value')
        done_block = self.builder.append_basic_block('list_pop_done')
        self.builder.cbranch(is_empty, empty_block, value_block)

        self.builder.position_at_start(empty_block)
        self.builder.store(self._optional_value(elem_type, False), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(value_block)
        new_len = self.builder.sub(length, ir.Constant(i64, 1), name='_list_new_len')
        value = self.builder.load(self._list_element_ptr(list_ptr, new_len), name='_list_pop_value')
        self.builder.store(new_len, self._list_field_ptr(list_ptr, 1))
        self.builder.store(self._optional_value(elem_type, True, value), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        return self.builder.load(result_ptr, name='_list_pop_result_val')

    def _gen_list_shift(self, list_value: ir.Value) -> ir.Value:
        list_ptr = self._as_list_ptr(list_value)
        if list_ptr is None:
            return self._optional_value(ir.IntType(32), False)
        i64 = ir.IntType(64)
        elem_type = self._list_elem_type(list_ptr)
        opt_type = ir.LiteralStructType([ir.IntType(1), elem_type])
        result_ptr = self.builder.alloca(opt_type, name='_list_shift_result')
        length = self._list_length(list_ptr)
        is_empty = self.builder.icmp_unsigned('==', length, ir.Constant(i64, 0), name='_list_empty')
        empty_block = self.builder.append_basic_block('list_shift_empty')
        value_block = self.builder.append_basic_block('list_shift_value')
        done_block = self.builder.append_basic_block('list_shift_done')
        self.builder.cbranch(is_empty, empty_block, value_block)

        self.builder.position_at_start(empty_block)
        self.builder.store(self._optional_value(elem_type, False), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(value_block)
        first = self.builder.load(self._list_element_ptr(list_ptr, ir.Constant(i64, 0)), name='_list_shift_value')
        index_ptr = self.builder.alloca(i64, name='_list_shift_i')
        self.builder.store(ir.Constant(i64, 1), index_ptr)
        loop_cond = self.builder.append_basic_block('list_shift_cond')
        loop_body = self.builder.append_basic_block('list_shift_body')
        loop_done = self.builder.append_basic_block('list_shift_loop_done')
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_list_shift_i_val')
        keep_moving = self.builder.icmp_unsigned('<', index, length, name='_list_shift_more')
        self.builder.cbranch(keep_moving, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        prev_index = self.builder.sub(index, ir.Constant(i64, 1))
        moved = self.builder.load(self._list_element_ptr(list_ptr, index), name='_list_shift_item')
        self.builder.store(moved, self._list_element_ptr(list_ptr, prev_index))
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        new_len = self.builder.sub(length, ir.Constant(i64, 1), name='_list_new_len')
        self.builder.store(new_len, self._list_field_ptr(list_ptr, 1))
        self.builder.store(self._optional_value(elem_type, True, first), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        return self.builder.load(result_ptr, name='_list_shift_result_val')

    def _gen_list_unshift(self, list_value: ir.Value, item: ir.Value) -> None:
        list_ptr = self._as_list_ptr(list_value)
        if list_ptr is None:
            return None
        i64 = ir.IntType(64)
        elem_type = self._list_elem_type(list_ptr)
        old_len = self._list_length(list_ptr)
        new_len = self.builder.add(old_len, ir.Constant(i64, 1), name='_list_new_len')
        self._list_ensure_capacity(list_ptr, new_len)
        index_ptr = self.builder.alloca(i64, name='_list_unshift_i')
        self.builder.store(old_len, index_ptr)
        loop_cond = self.builder.append_basic_block('list_unshift_cond')
        loop_body = self.builder.append_basic_block('list_unshift_body')
        loop_done = self.builder.append_basic_block('list_unshift_done')
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_list_unshift_i_val')
        keep_moving = self.builder.icmp_unsigned('>', index, ir.Constant(i64, 0), name='_list_unshift_more')
        self.builder.cbranch(keep_moving, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        prev_index = self.builder.sub(index, ir.Constant(i64, 1))
        moved = self.builder.load(self._list_element_ptr(list_ptr, prev_index), name='_list_unshift_item')
        self.builder.store(moved, self._list_element_ptr(list_ptr, index))
        self.builder.store(prev_index, index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        self.builder.store(self._coerce_list_item(item, elem_type), self._list_element_ptr(list_ptr, ir.Constant(i64, 0)))
        self.builder.store(new_len, self._list_field_ptr(list_ptr, 1))
        return None

    def _gen_list_slice(self, list_value: ir.Value, start_value: ir.Value, end_value: ir.Value) -> ir.Value:
        list_ptr = self._as_list_ptr(list_value)
        if list_ptr is None:
            return self._list_new(ir.IntType(32), ir.Constant(ir.IntType(64), 0))
        i64 = ir.IntType(64)
        zero = ir.Constant(i64, 0)
        elem_type = self._list_elem_type(list_ptr)
        length = self._list_length(list_ptr)
        start = self._clamp_list_index(self._as_i64(start_value), length)
        end = self._clamp_list_index(self._as_i64(end_value), length)
        end_before_start = self.builder.icmp_unsigned('<', end, start, name='_list_slice_empty')
        raw_len = self.builder.sub(end, start, name='_list_slice_raw_len')
        slice_len = self.builder.select(end_before_start, zero, raw_len, name='_list_slice_len')
        result = self._list_new(elem_type, slice_len)

        index_ptr = self.builder.alloca(i64, name='_list_slice_i')
        self.builder.store(zero, index_ptr)
        loop_cond = self.builder.append_basic_block('list_slice_cond')
        loop_body = self.builder.append_basic_block('list_slice_body')
        loop_done = self.builder.append_basic_block('list_slice_done')
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_list_slice_i_val')
        keep_copying = self.builder.icmp_unsigned('<', index, slice_len, name='_list_slice_more')
        self.builder.cbranch(keep_copying, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        src_index = self.builder.add(start, index, name='_list_slice_src_i')
        item = self.builder.load(self._list_element_ptr(list_ptr, src_index), name='_list_slice_item')
        self.builder.store(item, self._list_element_ptr(result, index))
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        return result

    def _call_list_function(self, func: ir.Value, args: list[ir.Value]) -> ir.Value | None:
        if isinstance(func, ir.Function):
            func_type = func.function_type
            coerced = [self._coerce_value(arg, func_type.args[i]) if i < len(func_type.args) else arg for i, arg in enumerate(args)]
            return self.builder.call(func, coerced)
        if isinstance(func, ir.Value) and isinstance(func.type, ir.PointerType) and isinstance(func.type.pointee, ir.FunctionType):
            func_type = func.type.pointee
            coerced = [self._coerce_value(arg, func_type.args[i]) if i < len(func_type.args) else arg for i, arg in enumerate(args)]
            return self.builder.call(func, coerced)
        return None

    def _gen_list_find(self, list_value: ir.Value, pred: ir.Value) -> ir.Value:
        list_ptr = self._as_list_ptr(list_value)
        if list_ptr is None:
            return self._optional_value(ir.IntType(32), False)
        i64 = ir.IntType(64)
        elem_type = self._list_elem_type(list_ptr)
        opt_type = ir.LiteralStructType([ir.IntType(1), elem_type])
        result_ptr = self.builder.alloca(opt_type, name='_list_find_result')
        self.builder.store(self._optional_value(elem_type, False), result_ptr)
        length = self._list_length(list_ptr)
        index_ptr = self.builder.alloca(i64, name='_list_find_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        loop_cond = self.builder.append_basic_block('list_find_cond')
        loop_body = self.builder.append_basic_block('list_find_body')
        found_block = self.builder.append_basic_block('list_find_found')
        step_block = self.builder.append_basic_block('list_find_step')
        done_block = self.builder.append_basic_block('list_find_done')
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_list_find_i_val')
        more = self.builder.icmp_unsigned('<', index, length, name='_list_find_more')
        self.builder.cbranch(more, loop_body, done_block)

        self.builder.position_at_start(loop_body)
        item = self.builder.load(self._list_element_ptr(list_ptr, index), name='_list_find_item')
        keep = self._call_list_function(pred, [item])
        if keep is None or keep.type != ir.IntType(1):
            keep = ir.Constant(ir.IntType(1), 0)
        self.builder.cbranch(keep, found_block, step_block)

        self.builder.position_at_start(found_block)
        self.builder.store(self._optional_value(elem_type, True, item), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(step_block)
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(done_block)
        return self.builder.load(result_ptr, name='_list_find_result_val')

    def _gen_list_filter(self, list_value: ir.Value, pred: ir.Value) -> ir.Value:
        list_ptr = self._as_list_ptr(list_value)
        if list_ptr is None:
            return self._list_new(ir.IntType(32), ir.Constant(ir.IntType(64), 0))
        i64 = ir.IntType(64)
        elem_type = self._list_elem_type(list_ptr)
        length = self._list_length(list_ptr)
        result = self._list_new(elem_type, ir.Constant(i64, 0))
        index_ptr = self.builder.alloca(i64, name='_list_filter_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        loop_cond = self.builder.append_basic_block('list_filter_cond')
        loop_body = self.builder.append_basic_block('list_filter_body')
        keep_block = self.builder.append_basic_block('list_filter_keep')
        step_block = self.builder.append_basic_block('list_filter_step')
        done_block = self.builder.append_basic_block('list_filter_done')
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_list_filter_i_val')
        more = self.builder.icmp_unsigned('<', index, length, name='_list_filter_more')
        self.builder.cbranch(more, loop_body, done_block)

        self.builder.position_at_start(loop_body)
        item = self.builder.load(self._list_element_ptr(list_ptr, index), name='_list_filter_item')
        keep = self._call_list_function(pred, [item])
        if keep is None or keep.type != ir.IntType(1):
            keep = ir.Constant(ir.IntType(1), 0)
        self.builder.cbranch(keep, keep_block, step_block)

        self.builder.position_at_start(keep_block)
        self._gen_list_push(result, item)
        self.builder.branch(step_block)

        self.builder.position_at_start(step_block)
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(done_block)
        return result

    def _gen_list_map(self, name: str, list_value: ir.Value, func: ir.Value) -> ir.Value:
        list_ptr = self._as_list_ptr(list_value)
        type_args = self._collection_type_args(name)
        result_elem_type = type_args[1] if len(type_args) > 1 else ir.IntType(32)
        if list_ptr is None:
            return self._list_new(result_elem_type, ir.Constant(ir.IntType(64), 0))
        i64 = ir.IntType(64)
        length = self._list_length(list_ptr)
        result = self._list_new(result_elem_type, length)
        index_ptr = self.builder.alloca(i64, name='_list_map_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        loop_cond = self.builder.append_basic_block('list_map_cond')
        loop_body = self.builder.append_basic_block('list_map_body')
        done_block = self.builder.append_basic_block('list_map_done')
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_list_map_i_val')
        more = self.builder.icmp_unsigned('<', index, length, name='_list_map_more')
        self.builder.cbranch(more, loop_body, done_block)

        self.builder.position_at_start(loop_body)
        item = self.builder.load(self._list_element_ptr(list_ptr, index), name='_list_map_item')
        mapped = self._call_list_function(func, [item])
        if mapped is None:
            mapped = self._zero_constant(result_elem_type)
        mapped = self._coerce_list_item(mapped, result_elem_type)
        self.builder.store(mapped, self._list_element_ptr(result, index))
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(done_block)
        return result

    def _gen_list_sort(self, list_value: ir.Value, cmp_func: ir.Value) -> None:
        list_ptr = self._as_list_ptr(list_value)
        if list_ptr is None:
            return None
        i64 = ir.IntType(64)
        length = self._list_length(list_ptr)
        outer_ptr = self.builder.alloca(i64, name='_list_sort_i')
        self.builder.store(ir.Constant(i64, 1), outer_ptr)
        outer_cond = self.builder.append_basic_block('list_sort_outer_cond')
        outer_body = self.builder.append_basic_block('list_sort_outer_body')
        inner_cond = self.builder.append_basic_block('list_sort_inner_cond')
        compare_block = self.builder.append_basic_block('list_sort_compare')
        inner_body = self.builder.append_basic_block('list_sort_inner_body')
        outer_step = self.builder.append_basic_block('list_sort_outer_step')
        done_block = self.builder.append_basic_block('list_sort_done')
        self.builder.branch(outer_cond)

        self.builder.position_at_start(outer_cond)
        outer = self.builder.load(outer_ptr, name='_list_sort_i_val')
        more_outer = self.builder.icmp_unsigned('<', outer, length, name='_list_sort_more_outer')
        self.builder.cbranch(more_outer, outer_body, done_block)

        self.builder.position_at_start(outer_body)
        inner_ptr = self.builder.alloca(i64, name='_list_sort_j')
        self.builder.store(outer, inner_ptr)
        self.builder.branch(inner_cond)

        self.builder.position_at_start(inner_cond)
        inner = self.builder.load(inner_ptr, name='_list_sort_j_val')
        has_prev = self.builder.icmp_unsigned('>', inner, ir.Constant(i64, 0), name='_list_sort_has_prev')
        self.builder.cbranch(has_prev, compare_block, outer_step)

        self.builder.position_at_start(compare_block)
        prev_index = self.builder.sub(inner, ir.Constant(i64, 1), name='_list_sort_prev_i')
        cur_val = self.builder.load(self._list_element_ptr(list_ptr, inner), name='_list_sort_cur')
        prev_val = self.builder.load(self._list_element_ptr(list_ptr, prev_index), name='_list_sort_prev')
        cmp_result = self._call_list_function(cmp_func, [prev_val, cur_val])
        if cmp_result is None:
            cmp_result = ir.Constant(ir.IntType(32), 0)
        if cmp_result.type != ir.IntType(32):
            cmp_result = self._coerce_value(cmp_result, ir.IntType(32))
        should_swap_cmp = self.builder.icmp_signed('>', cmp_result, ir.Constant(ir.IntType(32), 0), name='_list_sort_should_swap_cmp')
        self.builder.cbranch(should_swap_cmp, inner_body, outer_step)

        self.builder.position_at_start(inner_body)
        cur_ptr = self._list_element_ptr(list_ptr, inner)
        prev_ptr = self._list_element_ptr(list_ptr, prev_index)
        tmp = self.builder.load(cur_ptr, name='_list_sort_tmp')
        self.builder.store(self.builder.load(prev_ptr), cur_ptr)
        self.builder.store(tmp, prev_ptr)
        self.builder.store(prev_index, inner_ptr)
        self.builder.branch(inner_cond)

        self.builder.position_at_start(outer_step)
        self.builder.store(self.builder.add(outer, ir.Constant(i64, 1)), outer_ptr)
        self.builder.branch(outer_cond)

        self.builder.position_at_start(done_block)
        return None

    def _clamp_list_index(self, value: ir.Value, length: ir.Value) -> ir.Value:
        i64 = ir.IntType(64)
        zero = ir.Constant(i64, 0)
        is_negative = self.builder.icmp_signed('<', value, zero)
        non_negative = self.builder.select(is_negative, zero, value)
        too_large = self.builder.icmp_unsigned('>', non_negative, length)
        return self.builder.select(too_large, length, non_negative)

    def _list_new(self, elem_type: ir.Type, length: ir.Value) -> ir.Value:
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        page_ptr_type = ir.PointerType(elem_type)
        pages_type = ir.PointerType(page_ptr_type)
        list_type = ir.LiteralStructType([pages_type, i64, i64, i64])
        list_ptr = self._arena_allocate(list_type, name='_tmp_list')
        self.builder.store(self._zero_constant(list_type), list_ptr)

        page_count = self.builder.udiv(self.builder.add(length, ir.Constant(i64, 7)), ir.Constant(i64, 8), name='_list_page_count_raw')
        no_pages = self.builder.icmp_unsigned('==', page_count, ir.Constant(i64, 0))
        page_count = self.builder.select(no_pages, ir.Constant(i64, 1), page_count, name='_list_page_count')
        page_table_bytes = self.builder.mul(page_count, ir.Constant(i64, 8), name='_list_page_table_bytes')
        page_table_raw = self.builder.call(self._arena_alloc, [page_table_bytes, ir.Constant(i64, 8)])
        pages = self.builder.bitcast(page_table_raw, pages_type, name='_list_new_pages')

        index_ptr = self.builder.alloca(i64, name='_list_new_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        loop_cond = self.builder.append_basic_block('list_new_cond')
        loop_body = self.builder.append_basic_block('list_new_body')
        loop_done = self.builder.append_basic_block('list_new_done')
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_list_new_i_val')
        more = self.builder.icmp_unsigned('<', index, page_count, name='_list_new_more')
        self.builder.cbranch(more, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        page_bytes = ir.Constant(i64, max(self._type_width(elem_type), 1) * 8)
        page_raw = self.builder.call(self._arena_alloc, [page_bytes, ir.Constant(i64, 8)])
        page = self.builder.bitcast(page_raw, page_ptr_type, name='_list_new_page')
        page_slot = self.builder.gep(pages, [index], inbounds=True)
        self.builder.store(page, page_slot)
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        self.builder.store(pages, self._list_field_ptr(list_ptr, 0))
        self.builder.store(length, self._list_field_ptr(list_ptr, 1))
        self.builder.store(self.builder.mul(page_count, ir.Constant(i64, 8)), self._list_field_ptr(list_ptr, 2))
        self.builder.store(page_count, self._list_field_ptr(list_ptr, 3))
        return list_ptr

    def _list_ensure_capacity(self, list_ptr: ir.Value, required_len: ir.Value) -> None:
        i64 = ir.IntType(64)
        elem_type = self._list_elem_type(list_ptr)
        page_ptr_type = ir.PointerType(elem_type)
        pages_type = ir.PointerType(page_ptr_type)
        capacity = self.builder.load(self._list_field_ptr(list_ptr, 2), name='_list_capacity')
        page_count = self.builder.load(self._list_field_ptr(list_ptr, 3), name='_list_page_count')
        has_capacity = self.builder.icmp_unsigned('>=', capacity, required_len, name='_list_has_capacity')
        grow_block = self.builder.append_basic_block('list_grow')
        done_block = self.builder.append_basic_block('list_grow_done')
        self.builder.cbranch(has_capacity, done_block, grow_block)

        self.builder.position_at_start(grow_block)
        new_page_count = self.builder.add(page_count, ir.Constant(i64, 1), name='_list_new_page_count')
        page_table_bytes = self.builder.mul(new_page_count, ir.Constant(i64, 8), name='_list_page_table_bytes')
        page_table_raw = self.builder.call(self._arena_alloc, [page_table_bytes, ir.Constant(i64, 8)])
        new_pages = self.builder.bitcast(page_table_raw, pages_type, name='_list_grown_pages')
        old_pages = self.builder.load(self._list_field_ptr(list_ptr, 0), name='_list_old_pages')
        index_ptr = self.builder.alloca(i64, name='_list_copy_page_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        copy_cond = self.builder.append_basic_block('list_page_copy_cond')
        copy_body = self.builder.append_basic_block('list_page_copy_body')
        copy_done = self.builder.append_basic_block('list_page_copy_done')
        self.builder.branch(copy_cond)

        self.builder.position_at_start(copy_cond)
        index = self.builder.load(index_ptr, name='_list_copy_page_i_val')
        more = self.builder.icmp_unsigned('<', index, page_count, name='_list_copy_more')
        self.builder.cbranch(more, copy_body, copy_done)

        self.builder.position_at_start(copy_body)
        old_slot = self.builder.gep(old_pages, [index], inbounds=True)
        new_slot = self.builder.gep(new_pages, [index], inbounds=True)
        self.builder.store(self.builder.load(old_slot), new_slot)
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(copy_cond)

        self.builder.position_at_start(copy_done)
        page_bytes = ir.Constant(i64, max(self._type_width(elem_type), 1) * 8)
        page_raw = self.builder.call(self._arena_alloc, [page_bytes, ir.Constant(i64, 8)])
        new_page = self.builder.bitcast(page_raw, page_ptr_type, name='_list_new_page')
        new_page_slot = self.builder.gep(new_pages, [page_count], inbounds=True)
        self.builder.store(new_page, new_page_slot)
        self.builder.store(new_pages, self._list_field_ptr(list_ptr, 0))
        self.builder.store(new_page_count, self._list_field_ptr(list_ptr, 3))
        self.builder.store(self.builder.mul(new_page_count, ir.Constant(i64, 8)), self._list_field_ptr(list_ptr, 2))
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        return None

    def _as_dict_ptr(self, value: ir.Value) -> ir.Value | None:
        dict_type = self.structs['Dict']
        if isinstance(value.type, ir.PointerType) and value.type.pointee == dict_type:
            return value
        if value.type == dict_type:
            tmp = self.builder.alloca(dict_type, name='_dict_tmp')
            self.builder.store(value, tmp)
            return tmp
        return None

    def _dict_count_ptr(self, dict_ptr: ir.Value) -> ir.Value:
        return self.builder.gep(dict_ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 2)], inbounds=True)

    def _dict_count(self, dict_ptr: ir.Value) -> ir.Value:
        return self.builder.load(self._dict_count_ptr(dict_ptr), name='_dict_count')

    def _dict_slot_ptr(self, dict_ptr: ir.Value, page_field: int, index: ir.Value) -> ir.Value:
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        if index.type != i32:
            index32 = self.builder.trunc(index, i32) if isinstance(index.type, ir.IntType) and index.type.width > 32 else self.builder.zext(index, i32)
        else:
            index32 = index
        pages_ptr = self.builder.gep(dict_ptr, [ir.Constant(i32, 0), ir.Constant(i32, page_field)], inbounds=True)
        pages = self.builder.load(pages_ptr, name='_dict_pages')
        page_idx = self.builder.udiv(index32, ir.Constant(i32, 8), name='_dict_page_idx')
        slot_idx32 = self.builder.urem(index32, ir.Constant(i32, 8), name='_dict_slot_idx32')
        slot_idx = self.builder.zext(slot_idx32, i64)
        page_slot = self.builder.gep(pages, [page_idx], inbounds=True)
        page = self.builder.load(page_slot, name='_dict_page')
        return self.builder.gep(page, [slot_idx], inbounds=True)

    def _dict_key_slot_ptr(self, dict_ptr: ir.Value, index: ir.Value) -> ir.Value:
        return self._dict_slot_ptr(dict_ptr, 0, index)

    def _dict_value_slot_ptr(self, dict_ptr: ir.Value, index: ir.Value) -> ir.Value:
        return self._dict_slot_ptr(dict_ptr, 1, index)

    def _dict_to_i8_ptr(self, value: ir.Value) -> ir.Value:
        i8_ptr = ir.PointerType(ir.IntType(8))
        if value.type == i8_ptr:
            return value
        if self._is_aggregate_ptr(value):
            return self.builder.bitcast(value, i8_ptr)
        tmp = self._arena_allocate(value.type, name='_dict_item_ptr')
        self.builder.store(value, tmp)
        return self.builder.bitcast(tmp, i8_ptr)

    def _dict_from_i8_ptr(self, raw: ir.Value, value_type: ir.Type) -> ir.Value:
        i8_ptr = ir.PointerType(ir.IntType(8))
        if value_type == i8_ptr:
            return raw
        ptr = self.builder.bitcast(raw, ir.PointerType(value_type), name='_dict_typed_ptr')
        return self.builder.load(ptr, name='_dict_typed_value')

    def _gen_c_string_equal(self, left: ir.Value, right: ir.Value) -> ir.Value:
        i1 = ir.IntType(1)
        i8 = ir.IntType(8)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        left = left if left.type == i8_ptr else self._dict_to_i8_ptr(left)
        right = right if right.type == i8_ptr else self._dict_to_i8_ptr(right)
        same_ptr = self.builder.icmp_unsigned('==', left, right, name='_dict_key_same_ptr')
        result_ptr = self.builder.alloca(i1, name='_dict_key_eq_result')
        self.builder.store(ir.Constant(i1, 1), result_ptr)
        index_ptr = self.builder.alloca(i64, name='_dict_key_eq_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        scan_cond = self.builder.append_basic_block('dict_key_eq_cond')
        scan_body = self.builder.append_basic_block('dict_key_eq_body')
        mismatch_block = self.builder.append_basic_block('dict_key_eq_mismatch')
        step_block = self.builder.append_basic_block('dict_key_eq_step')
        done_block = self.builder.append_basic_block('dict_key_eq_done')
        self.builder.cbranch(same_ptr, done_block, scan_cond)

        self.builder.position_at_start(scan_cond)
        index = self.builder.load(index_ptr, name='_dict_key_eq_i_val')
        left_ch = self.builder.load(self.builder.gep(left, [index], inbounds=True), name='_dict_key_left_ch')
        right_ch = self.builder.load(self.builder.gep(right, [index], inbounds=True), name='_dict_key_right_ch')
        chars_equal = self.builder.icmp_unsigned('==', left_ch, right_ch, name='_dict_key_chars_equal')
        self.builder.cbranch(chars_equal, scan_body, mismatch_block)

        self.builder.position_at_start(scan_body)
        at_end = self.builder.icmp_unsigned('==', left_ch, ir.Constant(i8, 0), name='_dict_key_at_end')
        self.builder.cbranch(at_end, done_block, step_block)

        self.builder.position_at_start(step_block)
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(scan_cond)

        self.builder.position_at_start(mismatch_block)
        self.builder.store(ir.Constant(i1, 0), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        return self.builder.load(result_ptr, name='_dict_key_eq')

    def _gen_dict_find_index(self, dict_ptr: ir.Value, key: ir.Value, key_type: ir.Type) -> tuple[ir.Value, ir.Value]:
        i1 = ir.IntType(1)
        i32 = ir.IntType(32)
        found_ptr = self.builder.alloca(i1, name='_dict_found')
        index_result_ptr = self.builder.alloca(i32, name='_dict_found_index')
        scan_ptr = self.builder.alloca(i32, name='_dict_find_i')
        self.builder.store(ir.Constant(i1, 0), found_ptr)
        self.builder.store(ir.Constant(i32, 0), index_result_ptr)
        self.builder.store(ir.Constant(i32, 0), scan_ptr)
        count = self._dict_count(dict_ptr)
        cond_block = self.builder.append_basic_block('dict_find_cond')
        body_block = self.builder.append_basic_block('dict_find_body')
        found_block = self.builder.append_basic_block('dict_find_found')
        step_block = self.builder.append_basic_block('dict_find_step')
        done_block = self.builder.append_basic_block('dict_find_done')
        self.builder.branch(cond_block)

        self.builder.position_at_start(cond_block)
        index = self.builder.load(scan_ptr, name='_dict_find_i_val')
        more = self.builder.icmp_unsigned('<', index, count, name='_dict_find_more')
        self.builder.cbranch(more, body_block, done_block)

        self.builder.position_at_start(body_block)
        stored_raw = self.builder.load(self._dict_key_slot_ptr(dict_ptr, index), name='_dict_find_key')
        if key_type == ir.PointerType(ir.IntType(8)):
            matches = self._gen_c_string_equal(stored_raw, key)
        else:
            stored = self._dict_from_i8_ptr(stored_raw, key_type)
            wanted = self._coerce_list_item(key, key_type)
            if isinstance(key_type, ir.IntType):
                matches = self.builder.icmp_signed('==', stored, wanted, name='_dict_key_match')
            elif key_type == ir.FloatType() or key_type == ir.DoubleType():
                matches = self.builder.fcmp_ordered('==', stored, wanted, name='_dict_key_match')
            else:
                stored_ptr = self.builder.bitcast(stored_raw, ir.PointerType(ir.IntType(8)))
                wanted_ptr = self._dict_to_i8_ptr(wanted)
                matches = self.builder.icmp_unsigned('==', stored_ptr, wanted_ptr, name='_dict_key_match')
        self.builder.cbranch(matches, found_block, step_block)

        self.builder.position_at_start(found_block)
        self.builder.store(ir.Constant(i1, 1), found_ptr)
        self.builder.store(index, index_result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(step_block)
        self.builder.store(self.builder.add(index, ir.Constant(i32, 1)), scan_ptr)
        self.builder.branch(cond_block)

        self.builder.position_at_start(done_block)
        return self.builder.load(found_ptr, name='_dict_found_val'), self.builder.load(index_result_ptr, name='_dict_found_index_val')

    def _gen_dict_len(self, dict_value: ir.Value) -> ir.Value:
        dict_ptr = self._as_dict_ptr(dict_value)
        if dict_ptr is None:
            return ir.Constant(ir.IntType(64), 0)
        return self.builder.zext(self._dict_count(dict_ptr), ir.IntType(64))

    def _gen_dict_has(self, name: str, dict_value: ir.Value, key: ir.Value) -> ir.Value:
        dict_ptr = self._as_dict_ptr(dict_value)
        if dict_ptr is None:
            return ir.Constant(ir.IntType(1), 0)
        type_args = self._collection_type_args(name)
        key_type = type_args[0] if type_args else ir.PointerType(ir.IntType(8))
        found, _ = self._gen_dict_find_index(dict_ptr, key, key_type)
        return found

    def _gen_dict_delete(self, name: str, dict_value: ir.Value, key: ir.Value) -> ir.Value:
        dict_ptr = self._as_dict_ptr(dict_value)
        if dict_ptr is None:
            return ir.Constant(ir.IntType(1), 0)
        i32 = ir.IntType(32)
        type_args = self._collection_type_args(name)
        key_type = type_args[0] if type_args else ir.PointerType(ir.IntType(8))
        found, found_index = self._gen_dict_find_index(dict_ptr, key, key_type)
        count = self._dict_count(dict_ptr)
        shift_start = self.builder.append_basic_block('dict_delete_shift_start')
        shift_cond = self.builder.append_basic_block('dict_delete_shift_cond')
        shift_body = self.builder.append_basic_block('dict_delete_shift_body')
        done_block = self.builder.append_basic_block('dict_delete_done')
        self.builder.cbranch(found, shift_start, done_block)

        self.builder.position_at_start(shift_start)
        index_ptr = self.builder.alloca(i32, name='_dict_delete_i')
        self.builder.store(found_index, index_ptr)
        self.builder.branch(shift_cond)

        self.builder.position_at_start(shift_cond)
        index = self.builder.load(index_ptr, name='_dict_delete_i_val')
        next_index = self.builder.add(index, ir.Constant(i32, 1), name='_dict_delete_next_i')
        more = self.builder.icmp_unsigned('<', next_index, count, name='_dict_delete_more')
        self.builder.cbranch(more, shift_body, done_block)

        self.builder.position_at_start(shift_body)
        self.builder.store(self.builder.load(self._dict_key_slot_ptr(dict_ptr, next_index)), self._dict_key_slot_ptr(dict_ptr, index))
        self.builder.store(self.builder.load(self._dict_value_slot_ptr(dict_ptr, next_index)), self._dict_value_slot_ptr(dict_ptr, index))
        self.builder.store(next_index, index_ptr)
        self.builder.branch(shift_cond)

        self.builder.position_at_start(done_block)
        new_count = self.builder.sub(count, ir.Constant(i32, 1), name='_dict_delete_new_count')
        count_to_store = self.builder.select(found, new_count, count, name='_dict_delete_count')
        self.builder.store(count_to_store, self._dict_count_ptr(dict_ptr))
        return found

    def _gen_dict_keys(self, name: str, dict_value: ir.Value) -> ir.Value:
        type_args = self._collection_type_args(name)
        key_type = type_args[0] if type_args else ir.PointerType(ir.IntType(8))
        return self._gen_dict_list_from_slots(dict_value, 0, key_type)

    def _gen_dict_values(self, name: str, dict_value: ir.Value) -> ir.Value:
        type_args = self._collection_type_args(name)
        value_type = type_args[1] if len(type_args) > 1 else ir.PointerType(ir.IntType(8))
        return self._gen_dict_list_from_slots(dict_value, 1, value_type)

    def _gen_dict_list_from_slots(self, dict_value: ir.Value, field_index: int, elem_type: ir.Type) -> ir.Value:
        dict_ptr = self._as_dict_ptr(dict_value)
        if dict_ptr is None:
            return self._list_new(elem_type, ir.Constant(ir.IntType(64), 0))
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        count32 = self._dict_count(dict_ptr)
        count = self.builder.zext(count32, i64)
        result = self._list_new(elem_type, count)
        index_ptr = self.builder.alloca(i32, name='_dict_list_i')
        self.builder.store(ir.Constant(i32, 0), index_ptr)
        loop_cond = self.builder.append_basic_block('dict_list_cond')
        loop_body = self.builder.append_basic_block('dict_list_body')
        loop_done = self.builder.append_basic_block('dict_list_done')
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_dict_list_i_val')
        more = self.builder.icmp_unsigned('<', index, count32, name='_dict_list_more')
        self.builder.cbranch(more, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        slot_ptr = self._dict_key_slot_ptr(dict_ptr, index) if field_index == 0 else self._dict_value_slot_ptr(dict_ptr, index)
        raw = self.builder.load(slot_ptr, name='_dict_list_raw')
        value = self._dict_from_i8_ptr(raw, elem_type)
        self.builder.store(value, self._list_element_ptr(result, self.builder.zext(index, i64)))
        self.builder.store(self.builder.add(index, ir.Constant(i32, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        return result

    def _gen_dict_lookup_raw(self, dict_ptr: ir.Value, key: ir.Value, key_type: ir.Type) -> tuple[ir.Value, ir.Value]:
        i1 = ir.IntType(1)
        i8_ptr = ir.PointerType(ir.IntType(8))
        result_ptr = self.builder.alloca(i8_ptr, name='_dict_lookup_raw')
        self.builder.store(ir.Constant(i8_ptr, None), result_ptr)
        found, found_index = self._gen_dict_find_index(dict_ptr, key, key_type)
        found_block = self.builder.append_basic_block('dict_lookup_found')
        done_block = self.builder.append_basic_block('dict_lookup_done')
        self.builder.cbranch(found, found_block, done_block)

        self.builder.position_at_start(found_block)
        raw = self.builder.load(self._dict_value_slot_ptr(dict_ptr, found_index), name='_dict_lookup_value_raw')
        self.builder.store(raw, result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        return found, self.builder.load(result_ptr, name='_dict_lookup_raw_val')

    def _gen_dict_lookup_value(self, dict_ptr: ir.Value, key: ir.Value, key_type: ir.Type, value_type: ir.Type) -> ir.Value:
        found, raw = self._gen_dict_lookup_raw(dict_ptr, key, key_type)
        value_ptr = self.builder.alloca(value_type, name='_dict_lookup_value')
        self.builder.store(self._zero_constant(value_type), value_ptr)
        found_block = self.builder.append_basic_block('dict_lookup_typed_found')
        done_block = self.builder.append_basic_block('dict_lookup_typed_done')
        self.builder.cbranch(found, found_block, done_block)

        self.builder.position_at_start(found_block)
        self.builder.store(self._dict_from_i8_ptr(raw, value_type), value_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        return self.builder.load(value_ptr, name='_dict_lookup_value_val')

    def _gen_dict_upsert_value(self, dict_ptr: ir.Value, key: ir.Value, value: ir.Value,
                               key_type: ir.Type, value_type: ir.Type) -> ir.Value:
        """按 key 更新 Dict；不存在时追加一项。"""
        found, found_index = self._gen_dict_find_index(dict_ptr, key, key_type)
        update_block = self.builder.append_basic_block('dict_upsert_update')
        insert_block = self.builder.append_basic_block('dict_upsert_insert')
        done_block = self.builder.append_basic_block('dict_upsert_done')
        self.builder.cbranch(found, update_block, insert_block)

        self.builder.position_at_start(update_block)
        update_value = value
        if update_value.type != value_type:
            update_value = self._coerce_preserve_unsigned(update_value, value_type)
        self.builder.store(self._dict_to_i8_ptr(update_value), self._dict_value_slot_ptr(dict_ptr, found_index))
        self.builder.branch(done_block)

        self.builder.position_at_start(insert_block)
        insert_value = value
        if insert_value.type != value_type:
            insert_value = self._coerce_preserve_unsigned(insert_value, value_type)
        self._gen_dict_set(dict_ptr, key, insert_value)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        self._mark_dict_item_types(dict_ptr, key_type, value_type)
        return value

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
        k = self._dict_to_i8_ptr(key)
        v = self._dict_to_i8_ptr(value)
        self.builder.store(k, key_slot)
        self.builder.store(v, value_slot)
        self.builder.store(self.builder.add(count, ir.Constant(i32, 1)), count_ptr)
        return None

    def _gen_dict_get(self, dict_ptr: ir.Value, key: ir.Value) -> ir.Value:
        """dict_get(dict, key): 按 key 从分页存储读取原始值指针，缺失返回 null。"""
        key_type = key.type if key.type != ir.PointerType(ir.IntType(8)) else ir.PointerType(ir.IntType(8))
        _, raw = self._gen_dict_lookup_raw(dict_ptr, key, key_type)
        return raw

    def _gen_curried_call(self, func, func_name, expected_names, provided, placeholder_params):
        """为带 ? 占位符的调用生成柯里化闭包"""
        i32 = ir.IntType(32)
        i8_ptr = ir.PointerType(ir.IntType(8))

        # 获取被柯里化函数的类型信息
        if isinstance(func.type, ir.PointerType):
            func_type = func.type.pointee
        else:
            return ir.Constant(i32, 0)

        # 分类参数：捕获的参数 vs 占位符参数。占位符必须按原函数参数顺序保存，
        # 否则 add(c = ?, a = ?) 这类调用会把实参错位传给跳板函数。
        ordered_placeholders = [pname for pname in expected_names if pname in placeholder_params]
        captured_types = []
        captured_values = []
        placeholder_types = []

        for pname in expected_names:
            if pname in ordered_placeholders:
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
                    val = self._coerce_integer_value(val, captured_types[i])
            v = self.builder.insert_value(v, val, i + 1)

        self.builder.store(v, closure)

        # 创建跳板函数
        tramp_param_types = [closure_ptr_type] + placeholder_types
        ret_type = func_type.return_type
        tramp_func_type = ir.FunctionType(ret_type, tramp_param_types)
        tramp_func = ir.Function(self.module, tramp_func_type, name=tramp_name)
        self.func_param_names[tramp_name] = ['__closure'] + ordered_placeholders
        self._curried_closures[str(closure_type)] = (tramp_func, ordered_placeholders)

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
            if pname in ordered_placeholders:
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
            op = ctx.getChild((i * 2) - 1).getText()
            left, right = self._prepare_vector_binary_operands(left, right)
            unsigned = self._binary_result_unsigned(left, right)
            if self._is_float_or_float_vector(left.type):
                left = self.builder.fsub(left, right) if op == '-' else self.builder.fadd(left, right)
            else:
                left = self.builder.sub(left, right) if op == '-' else self.builder.add(left, right)
            self._mark_unsigned(left, unsigned)
        return left

    def visitMultiplicativeExpression(self, ctx: EzLangParser.MultiplicativeExpressionContext):
        left = self._eval(ctx.unaryExpression(0))
        for i in range(1, len(ctx.unaryExpression())):
            right = self._eval(ctx.unaryExpression(i))
            if left is None or right is None: continue
            op = ctx.getChild((i * 2) - 1).getText()
            left, right = self._prepare_vector_binary_operands(left, right)
            unsigned = self._binary_result_unsigned(left, right)
            if self._is_float_or_float_vector(left.type):
                if op == '*': left = self.builder.fmul(left, right)
                elif op == '/': left = self.builder.fdiv(left, right)
            else:
                if op == '*': left = self.builder.mul(left, right)
                elif op == '/': left = self.builder.udiv(left, right) if unsigned else self.builder.sdiv(left, right)
                elif op == '%': left = self.builder.urem(left, right) if unsigned else self.builder.srem(left, right)
            self._mark_unsigned(left, unsigned)
        return left

    def visitEqualityExpression(self, ctx: EzLangParser.EqualityExpressionContext):
        left = self._eval(ctx.relationalExpression(0))
        for i in range(1, len(ctx.relationalExpression())):
            right = self._eval(ctx.relationalExpression(i))
            if left is None or right is None: continue
            op = ctx.getChild((i * 2) - 1).getText()
            left, right = self._prepare_vector_binary_operands(left, right)
            if self._is_float_or_float_vector(left.type):
                left = self.builder.fcmp_ordered(op, left, right)
            else:
                left = self.builder.icmp_signed(op, left, right)
        return left

    def visitRelationalExpression(self, ctx: EzLangParser.RelationalExpressionContext):
        left = self._eval(ctx.bitOrExpression(0))
        for i in range(1, len(ctx.bitOrExpression())):
            right = self._eval(ctx.bitOrExpression(i))
            if left is None or right is None: continue
            op = ctx.getChild((i * 2) - 1).getText()
            left, right = self._prepare_vector_binary_operands(left, right)
            if self._is_float_or_float_vector(left.type):
                left = self.builder.fcmp_ordered(op, left, right)
            elif self._binary_result_unsigned(left, right):
                left = self.builder.icmp_unsigned(op, left, right)
            else:
                left = self.builder.icmp_signed(op, left, right)
        return left

    # ==================== 位运算 ====================

    def visitShiftExpression(self, ctx: EzLangParser.ShiftExpressionContext):
        left = self._eval(ctx.additiveExpression(0))
        for i in range(1, len(ctx.additiveExpression())):
            right = self._eval(ctx.additiveExpression(i))
            if left is None or right is None: continue
            op = ctx.getChild((i * 2) - 1).getText()
            left, right = self._prepare_vector_binary_operands(left, right)
            unsigned = self._is_unsigned_value(left)
            if op == '<<':
                left = self.builder.shl(left, right)
            else:
                left = self.builder.lshr(left, right) if unsigned else self.builder.ashr(left, right)
            self._mark_unsigned(left, unsigned)
        return left

    def visitBitAndExpression(self, ctx: EzLangParser.BitAndExpressionContext):
        left = self._eval(ctx.shiftExpression(0))
        for i in range(1, len(ctx.shiftExpression())):
            right = self._eval(ctx.shiftExpression(i))
            if left is None or right is None: continue
            left, right = self._prepare_vector_binary_operands(left, right)
            unsigned = self._binary_result_unsigned(left, right)
            left = self.builder.and_(left, right)
            self._mark_unsigned(left, unsigned)
        return left

    def visitBitXorExpression(self, ctx: EzLangParser.BitXorExpressionContext):
        left = self._eval(ctx.bitAndExpression(0))
        for i in range(1, len(ctx.bitAndExpression())):
            right = self._eval(ctx.bitAndExpression(i))
            if left is None or right is None: continue
            left, right = self._prepare_vector_binary_operands(left, right)
            unsigned = self._binary_result_unsigned(left, right)
            left = self.builder.xor(left, right)
            self._mark_unsigned(left, unsigned)
        return left

    def visitBitOrExpression(self, ctx: EzLangParser.BitOrExpressionContext):
        left = self._eval(ctx.bitXorExpression(0))
        for i in range(1, len(ctx.bitXorExpression())):
            right = self._eval(ctx.bitXorExpression(i))
            if left is None or right is None: continue
            left, right = self._prepare_vector_binary_operands(left, right)
            unsigned = self._binary_result_unsigned(left, right)
            left = self.builder.or_(left, right)
            self._mark_unsigned(left, unsigned)
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
        lhs_list = ctx.equalityExpression()
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
                result = self.builder.fsub(ir.Constant(inner.type, 0.0), inner)
            else:
                result = self.builder.sub(ir.Constant(inner.type, 0), inner)
            self._mark_unsigned(result, self._is_unsigned_value(inner))
            return result
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
        op_ctx = ctx.assignmentOperator()
        name = self._simple_lvalue_name(left)

        lvalue_ptr = None
        outer = self._outer_postfix_ctx(left)
        dict_target = self._dict_index_target(outer) if isinstance(outer, EzLangParser.IndexContext) else None

        val = None
        if ctx.assignmentExpression():
            val = self._eval(ctx.assignmentExpression())

        if dict_target is not None:
            dict_store = self._dict_index_assignment(dict_target, val, op_ctx)
            if dict_store is not None:
                return dict_store

        if isinstance(outer, EzLangParser.IndexContext):
            lvalue_ptr = self._index_lvalue_ptr(outer)
        elif isinstance(outer, EzLangParser.MemberAccessContext):
            lvalue_ptr = self._member_lvalue_ptr(outer)

        if lvalue_ptr is not None and val is not None:
            store_val = val
            if self._is_aggregate_ptr(store_val):
                store_val = self._copy_aggregate_value(store_val, name="_assign_copy")
                store_val = self.builder.load(store_val)
            current = self._load_with_unsigned(lvalue_ptr, name="_assign_current")
            store_val = self._apply_assignment_operator(current, store_val, op_ctx)
            if store_val.type != lvalue_ptr.type.pointee:
                store_val = self._coerce_preserve_unsigned(store_val, lvalue_ptr.type.pointee)
            self.builder.store(store_val, lvalue_ptr)
            return store_val

        if name and val is not None:
            # 如果值是 alloca（结构体字面量），需要 load
            store_val = val
            if self._is_aggregate_ptr(val):
                store_val = self._copy_aggregate_value(val, name="_assign_copy")
                store_val = self.builder.load(store_val)
            if name in self.locals:
                target = self.locals[name]
                current = self._load_with_unsigned(target, name="_assign_current")
                store_val = self._apply_assignment_operator(current, store_val, op_ctx)
                self._emit_lock_access(name, "write", lambda: self.builder.store(store_val, target))
            elif name in self.globals:
                target = self.globals[name]
                current = self._load_with_unsigned(target, name="_assign_current")
                store_val = self._apply_assignment_operator(current, store_val, op_ctx)
                self._emit_lock_access(name, "write", lambda: self.builder.store(store_val, target))

        return val

    # ==================== 语句 ====================

    def visitStatement(self, ctx: EzLangParser.StatementContext):
        if ctx.declaration() is not None:
            return self._eval(ctx.declaration())
        if ctx.expressionStatement() is not None:
            return self._eval(ctx.expressionStatement())
        if ctx.returnStatement() is not None:
            return self._eval(ctx.returnStatement())
        if ctx.breakStatement() is not None:
            return self._eval(ctx.breakStatement())
        if ctx.continueStatement() is not None:
            return self._eval(ctx.continueStatement())
        if ctx.throwStatement() is not None:
            return self._eval(ctx.throwStatement())
        return None

    def visitExpressionStatement(self, ctx: EzLangParser.ExpressionStatementContext):
        if ctx.expression():
            return self._eval(ctx.expression())
        return None

    def visitReturnStatement(self, ctx: EzLangParser.ReturnStatementContext):
        if self._parallel_result_stack:
            if ctx.expression():
                val = self._eval(ctx.expression())
                result_alloca = self._parallel_result_stack[-1]
                if val is not None:
                    if self._is_aggregate_ptr(val):
                        val = self.builder.load(val)
                    val = self._coerce_value(val, result_alloca.type.pointee)
                    self.builder.store(val, result_alloca)
            result_type = self._parallel_result_stack[-1].type.pointee if self._parallel_result_stack else None
            target_depth = self._parallel_arena_depth_stack[-1] if self._parallel_arena_depth_stack else 0
            self._restore_active_arena_scopes_for_return(ret_type=result_type, target_depth=target_depth)
            self.builder.branch(self._parallel_exit_stack[-1])
            return None
        if ctx.expression():
            val = self._eval(ctx.expression())
            if val is not None:
                # 聚合类型指针需要 load 后才能 ret（alloca 和 arena 都是指针）
                if self._is_aggregate_ptr(val):
                    val = self.builder.load(val)
                if self.current_function is not None:
                    expected = self.current_function.function_type.return_type
                    if not isinstance(expected, ir.VoidType) and val.type != expected:
                        val = self._coerce_return_value(val, expected)
                self._restore_active_arena_scopes_for_return(val, val.type)
                self.builder.ret(val)
            else:
                self._restore_active_arena_scopes()
                self.builder.ret_void()
        else:
            self._restore_active_arena_scopes()
            self.builder.ret_void()
        return None

    def visitBlock(self, ctx: EzLangParser.BlockContext):
        # Arena 作用域管理：进入时保存游标，退出时恢复
        saved_pos = None
        if self.builder and hasattr(self, '_arena_save'):
            saved_pos = self.builder.call(self._arena_save, [], name='_arena_saved')
            self._arena_scope_stack.append(saved_pos)
        for stmt in ctx.statement():
            self._eval(stmt)
            if self.builder.block.is_terminated:
                if saved_pos is not None and self._arena_scope_stack and self._arena_scope_stack[-1] is saved_pos:
                    self._arena_scope_stack.pop()
                return None
        if saved_pos is not None:
            self.builder.call(self._arena_restore, [saved_pos])
            if self._arena_scope_stack and self._arena_scope_stack[-1] is saved_pos:
                self._arena_scope_stack.pop()
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

        result_type = self._infer_catch_result_type(ctx.block())
        result_alloca = None
        if not isinstance(result_type, ir.VoidType):
            result_alloca = self.builder.alloca(result_type, name="_catch_result")
            self.builder.store(self._zero_constant(result_type), result_alloca)

        catch_exit_bb = self.builder.append_basic_block(name="catch_exit")

        self.catch_exit_blocks.append(catch_exit_bb)
        if result_alloca is not None:
            self.catch_result_allocas.append(result_alloca)

        # 执行 catch 体内的代码
        if ctx.block() is not None:
            self._eval(ctx.block())

        self.catch_exit_blocks.pop()
        if result_alloca is not None:
            self.catch_result_allocas.pop()

        # 跳转到出口
        if not self.builder.block.is_terminated:
            self.builder.branch(catch_exit_bb)

        self.builder.position_at_start(catch_exit_bb)
        if result_alloca is not None:
            caught = self._throw_is_active()
            caught_bb = self.builder.append_basic_block('catch_caught')
            done_bb = self.builder.append_basic_block('catch_done')
            self.builder.cbranch(caught, caught_bb, done_bb)

            self.builder.position_at_start(caught_bb)
            if result_type == self.structs['Error']:
                self.builder.store(self.builder.load(self._throw_value, name='catch_error'), result_alloca)
            self._clear_throw_state()
            self.builder.branch(done_bb)

            self.builder.position_at_start(done_bb)
            return self.builder.load(result_alloca, name="catch_value")
        return None

    def visitCatchBlockExpr(self, ctx: EzLangParser.CatchBlockExprContext):
        return self.visitCatchBlock(ctx.catchBlock())

    def visitThrowStatement(self, ctx: EzLangParser.ThrowStatementContext):
        """throw expr → 存储错误标记并跳转到 catch_exit"""
        thrown_value = self._eval(ctx.expression()) if ctx.expression() is not None else None
        self._store_throw_value(thrown_value)
        if self.catch_result_allocas and thrown_value is not None:
            result_alloca = self.catch_result_allocas[-1]
            if self._is_aggregate_ptr(thrown_value):
                thrown_value = self.builder.load(thrown_value)
            thrown_value = self._coerce_value(thrown_value, result_alloca.type.pointee)
            self.builder.store(thrown_value, result_alloca)
        self._branch_to_throw_exit_or_abort()
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
        if ctx.block(0) is not None:
            self._eval(ctx.block(0))
        then_block = self.builder.block
        if not then_block.is_terminated:
            self.builder.branch(merge_bb)

        # else 分支
        self.builder.position_at_start(else_bb)
        else_val = None
        if len(ctx.expression()) > 1 and ctx.expression(1) is not None:
            else_val = self._eval(ctx.expression(1))
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


def compile_source(source: str, module_name: str = "ezlang", compile_target: Optional[str] = None,
                   target_arch: Optional[str] = None, log_compile_min_level: Optional[int] = None):
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

    codegen = LLVMCodeGenerator(
        module_name,
        compile_target=compile_target,
        target_arch=target_arch,
        log_compile_min_level=log_compile_min_level,
    )
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
