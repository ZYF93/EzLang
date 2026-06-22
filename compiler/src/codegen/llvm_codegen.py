"""EzLang LLVM IR 代码生成器"""

from typing import Optional
from pathlib import Path
import re
from antlr4 import CommonTokenStream, InputStream, Token
from llvmlite import ir
from parser.EzLangLexer import EzLangLexer
from parser.EzLangParser import EzLangParser
from parser.EzLangVisitor import EzLangVisitor
from parser.string_literals import decode_string_literal_token


_EZ_VAR_IDENTIFIER_RE = re.compile(r'(?:[A-Za-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+)')


class LLVMCodeGenerator(EzLangVisitor):
    """LLVM IR 代码生成访问器"""

    def __init__(self, module_name: str = "ezlang", compile_target: Optional[str] = None,
                 target_arch: Optional[str] = None, log_compile_min_level: Optional[int] = None,
                 ensure_entrypoint: bool = False, base_dir: Optional[Path | str] = None,
                 source_name: Optional[Path | str] = None):
        self.context = ir.Context()
        self.module = ir.Module(name=module_name, context=self.context)
        self.compile_target = compile_target
        self.target_arch = target_arch
        self.log_compile_min_level = log_compile_min_level
        self.ensure_entrypoint = ensure_entrypoint
        self.base_dir = Path(base_dir).resolve() if base_dir is not None else Path.cwd()
        self.source_name = str(source_name) if source_name is not None else "<memory>"
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
        self._struct_field_type_names: dict[str, list[str]] = {}
        self.struct_defaults: dict[str, dict[str, any]] = {}  # struct_name → {field_name: expression_ctx}
        self.struct_methods: dict[str, dict[str, str]] = {}
        self.struct_generic_params: dict[str, list[str]] = {}
        self.struct_generic_templates: dict[str, object] = {}
        self._struct_monomorphized: set[str] = set()
        self.type_aliases: dict[str, ir.Type] = {}
        self.func_defaults: dict[str, dict[str, ir.Value]] = {}
        self.func_param_names: dict[str, list[str]] = {}
        self.func_param_type_ctxs: dict[str, list[object]] = {}
        self.func_return_unsigned: dict[str, bool] = {}
        self.func_return_dict_types: dict[str, tuple[ir.Type, ir.Type]] = {}
        self.generic_templates: dict[str, tuple] = {}
        self._monomorphized: set[str] = set()
        self._generic_type_map_stack: list[tuple[dict[str, ir.Type], dict[str, bool], dict[str, str]]] = []
        self._mapping_with_map = False
        self.extern_libs: list[tuple[str, Optional[str]]] = []  # (lib_path, target)
        self.active_extern_libs: list[str] = []
        self._extern_diagnostics: list[str] = []
        self._declare_names: list[str] = []
        self._sret_functions: dict[str, ir.Type] = {}
        self._c_abi_return_bridges: dict[str, tuple[ir.Type, ir.Type]] = {}
        self._c_abi_callback_trampolines: dict[tuple[str, str], ir.Function] = {}
        self._fmt_generation_stack: set[str] = set()
        self._non_extern_decls_seen = 0
        self._list_collection_builtins = {
            'listPush', 'listPop', 'listShift', 'listUnshift', 'listSort',
            'listFilter', 'listMap', 'listFind', 'listLen', 'listSlice',
            'randomShuffle',
        }
        self._dict_collection_builtins = {
            'dictKeys', 'dictValues', 'dictHas', 'dictDelete', 'dictLen',
        }
        self._collection_builtin_declares = self._list_collection_builtins | self._dict_collection_builtins
        self._compiler_builtin_declares = {'copy', 'set', 'allocRaw'} | self._collection_builtin_declares
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
        self._parallel_branch_counter = 0
        self._flow_future_stack: list[dict[str, dict[str, ir.Value]]] = []
        self._flow_depth = 0
        self._import_depth = 0
        self._source_dir_stack: list[Path] = [self.base_dir]
        self._shared_capture_locals: set[str] = set()
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
        self._type_alias_dict_item_types: dict[str, tuple[ir.Type, ir.Type]] = {}
        self._expected_expr_type_stack: list[ir.Type] = []
        self._expected_dict_item_types_stack: list[tuple[ir.Type, ir.Type] | None] = []
        self._struct_type_build_stack: list[str] = []
        self._decorated_globals: set[str] = set()
        self._decorator_init_functions: list[ir.Function] = []
        self._closure_types: dict[str, ir.LiteralStructType] = {}
        self._closure_invokers: dict[str, ir.Function] = {}
        self._function_literal_counter = 0
        self._declare_builtins()

    def _closure_key(self, ret_type: ir.Type, param_types: list[ir.Type]) -> str:
        return str(ir.FunctionType(ret_type, [ir.PointerType(ir.IntType(8))] + param_types))

    def _closure_type(self, ret_type: ir.Type, param_types: list[ir.Type]) -> ir.LiteralStructType:
        key = self._closure_key(ret_type, param_types)
        existing = self._closure_types.get(key)
        if existing is not None:
            return existing
        i8_ptr = ir.PointerType(ir.IntType(8))
        invoke_type = ir.PointerType(ir.FunctionType(ret_type, [i8_ptr] + param_types))
        closure_type = ir.LiteralStructType([invoke_type, i8_ptr])
        self._closure_types[key] = closure_type
        return closure_type

    def _is_closure_type(self, typ: ir.Type) -> bool:
        if not isinstance(typ, ir.LiteralStructType) or len(typ.elements) != 2:
            return False
        invoke_ptr, env_ptr = typ.elements
        return (
            isinstance(invoke_ptr, ir.PointerType)
            and isinstance(invoke_ptr.pointee, ir.FunctionType)
            and len(invoke_ptr.pointee.args) >= 1
            and invoke_ptr.pointee.args[0] == ir.PointerType(ir.IntType(8))
            and env_ptr == ir.PointerType(ir.IntType(8))
        )

    def _closure_signature(self, closure_type: ir.Type) -> tuple[ir.Type, list[ir.Type]] | None:
        if not self._is_closure_type(closure_type):
            return None
        invoke_type = closure_type.elements[0].pointee
        return invoke_type.return_type, list(invoke_type.args[1:])

    def _callable_return_type(self, value: ir.Value | None) -> ir.Type | None:
        """从函数值或闭包值推断返回类型。"""
        if value is None or not hasattr(value, 'type'):
            return None
        typ = value.type
        if isinstance(typ, ir.PointerType) and isinstance(typ.pointee, ir.FunctionType):
            return typ.pointee.return_type
        closure_type = typ.pointee if isinstance(typ, ir.PointerType) else typ
        signature = self._closure_signature(closure_type)
        return signature[0] if signature is not None else None

    def _closure_from_function(self, func: ir.Function, target_type: ir.Type | None = None) -> ir.Value:
        func_type = func.function_type
        if target_type is not None and self._is_closure_type(target_type):
            signature = self._closure_signature(target_type)
            ret_type, param_types = signature if signature is not None else (func_type.return_type, list(func_type.args))
        else:
            ret_type, param_types = func_type.return_type, list(func_type.args)
            target_type = self._closure_type(ret_type, param_types)
        invoke_type = target_type.elements[0].pointee
        if func.type == target_type.elements[0]:
            invoke = func
        else:
            invoke = self._get_plain_function_closure_invoker(func, invoke_type)
        i8_ptr = ir.PointerType(ir.IntType(8))
        value = ir.Constant(target_type, ir.Undefined)
        value = self.builder.insert_value(value, invoke, 0)
        value = self.builder.insert_value(value, ir.Constant(i8_ptr, None), 1)
        return value

    def _get_plain_function_closure_invoker(self, func: ir.Function, invoke_type: ir.FunctionType) -> ir.Function:
        key = f"{func.name}:{invoke_type}"
        cached = self._closure_invokers.get(key)
        if cached is not None:
            return cached
        base_name = re.sub(r'[^0-9A-Za-z_]', '_', func.name)
        name = f"{base_name}_closure_invoke"
        counter = 0
        while name in self.module.globals:
            counter += 1
            name = f"{base_name}_closure_invoke_{counter}"
        invoker = ir.Function(self.module, invoke_type, name)
        self._closure_invokers[key] = invoker
        old_builder = self.builder
        old_func = self.current_function
        block = invoker.append_basic_block('entry')
        self.builder = ir.IRBuilder(block)
        self.current_function = invoker
        args = [arg for arg in invoker.args[1:]]
        if isinstance(func.function_type.return_type, ir.VoidType):
            self.builder.call(func, args)
            self.builder.ret_void()
        else:
            self.builder.ret(self.builder.call(func, args))
        self.builder = old_builder
        self.current_function = old_func
        return invoker

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
        self._flow_sleep = None
        self._flow_race = self._define_runtime_race_hook('__ezrt_race', ir.FunctionType(i32, [i32, i32]))
        self._parallel_enter = self._define_runtime_void_hook('__ezrt_parallel_enter', flow_hook_type)
        self._parallel_exit = self._define_runtime_void_hook('__ezrt_parallel_exit', flow_hook_type)
        self._flow_suspend_names = {
            'fetch', 'fetchEx', 'readFile', 'writeFile', 'appendFile', 'removeFile', 'mkdir', 'removeDir',
            'listDir', 'exists', 'isDir', 'stat', 'readLine', 'processExec', 'processSpawn', 'processWait',
            'streamOpenFileRead', 'streamOpenFileWrite', 'streamRead', 'streamWrite', 'streamCopy',
            'streamFlush', 'streamClose', 'start', 'tcpConnect', 'tcpListen', 'udpBind',
            'udpRecvFrom', 'udpRecv', 'tcpRead', 'wsConnect', 'wsRecv', 'accept', 'read', 'write',
            'recv', 'send',
        }
        self._lock_register = self._get_or_declare_function('__ezrt_lock_register', ir.FunctionType(void, [i8_ptr, i32]))
        self._lock_read_acquire = self._get_or_declare_function('__ezrt_lock_read_acquire', ir.FunctionType(void, [i8_ptr]))
        self._lock_read_release = self._get_or_declare_function('__ezrt_lock_read_release', ir.FunctionType(void, [i8_ptr]))
        self._lock_write_acquire = self._get_or_declare_function('__ezrt_lock_write_acquire', ir.FunctionType(void, [i8_ptr]))
        self._lock_write_release = self._get_or_declare_function('__ezrt_lock_write_release', ir.FunctionType(void, [i8_ptr]))

        # 内置结构体: Error = { i32 code, i8* message, i8* file, i32 line, i32 column, i8* trace }
        err_type = self.context.get_identified_type('Error')
        if err_type.is_opaque:
            err_type.set_body(i32, i8_ptr, i8_ptr, i32, i32, i8_ptr)
        self.structs['Error'] = err_type
        self.struct_fields['Error'] = ['code', 'message', 'file', 'line', 'column', 'trace']
        self._struct_field_type_names['Error'] = ['I32', 'Str', 'Str', 'I32', 'I32', 'Str']
        self.struct_methods['Error'] = {'toString': 'Error_toString'}
        self.func_param_names['Error_toString'] = ['this']
        self._declare_throw_state(err_type)

        # 内置结构体: Date = { i64 timestamp }
        date_type = self.context.get_identified_type('Date')
        if date_type.is_opaque:
            date_type.set_body(i64)
        self.structs['Date'] = date_type
        self.struct_fields['Date'] = ['timestamp']
        self._struct_field_type_names['Date'] = ['I64']
        date_methods = ['getYear', 'getMonth', 'getDay', 'getHour', 'getMinute', 'getSecond', 'add', 'sub', 'format']
        date_method_symbols = {
            'getYear': 'dateGetYear',
            'getMonth': 'dateGetMonth',
            'getDay': 'dateGetDay',
            'getHour': 'dateGetHour',
            'getMinute': 'dateGetMinute',
            'getSecond': 'dateGetSecond',
            'add': 'dateAdd',
            'sub': 'dateSub',
            'format': 'dateFormat',
        }
        self.struct_methods['Date'] = date_method_symbols
        for name in date_methods[:6]:
            self.func_param_names[date_method_symbols[name]] = ['this']
        for name in ['add', 'sub']:
            self.func_param_names[date_method_symbols[name]] = ['this', 'year', 'month', 'day', 'hour', 'minute', 'second']
        self.func_param_names[date_method_symbols['format']] = ['this', 'fmt']

        # 内置结构体: Blob = { i8* data, i64 size }
        blob_type = self.context.get_identified_type('Blob')
        if blob_type.is_opaque:
            blob_type.set_body(i8_ptr, i64)
        self.structs['Blob'] = blob_type
        self.struct_fields['Blob'] = ['data', 'size']
        self._struct_field_type_names['Blob'] = ['*U8', 'I64']
        self.struct_methods['Blob'] = {'get': 'Blob_get', 'slice': 'Blob_slice'}
        self.func_param_names['Blob_get'] = ['this', 'index']
        self.func_param_names['Blob_slice'] = ['this', 'start', 'len']

        # 内置结构体: Dict = { i8*** key_pages, i8*** value_pages, i32 count, i32 capacity, i32 page_count }
        dict_type = self.context.get_identified_type('Dict')
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
        self._struct_field_type_names['Dict'] = ['Ptr', 'Ptr', 'I32', 'I32', 'I32']
        self._define_error_to_string()
        self._define_blob_methods()

    def _define_error_to_string(self) -> ir.Function:
        """内置 Error.toString(): Str。"""
        existing = self.module.globals.get('Error_toString')
        if isinstance(existing, ir.Function):
            return existing

        i8 = ir.IntType(8)
        i8_ptr = ir.PointerType(i8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        error_ptr = ir.PointerType(self.structs['Error'])
        func = ir.Function(self.module, ir.FunctionType(i8_ptr, [error_ptr]), 'Error_toString')
        func.args[0].name = 'this'

        entry = func.append_basic_block('entry')
        builder = ir.IRBuilder(entry)
        old_builder = self.builder
        self.builder = builder
        try:
            fmt = self._make_global_string('Error(code=%d, message=%s, file=%s, line=%d, column=%d, trace=%s)\0', prefix='_err_to_string_fmt')
            empty = self._make_global_string('', prefix='_err_to_string_empty')
        finally:
            self.builder = old_builder

        this = func.args[0]

        def _field(index: int, name: str) -> ir.Value:
            ptr = builder.gep(this, [ir.Constant(i32, 0), ir.Constant(i32, index)], inbounds=True)
            return builder.load(ptr, name=name)

        code = _field(0, '_err_code')
        message = _field(1, '_err_message')
        file = _field(2, '_err_file')
        line = _field(3, '_err_line')
        column = _field(4, '_err_column')
        trace = _field(5, '_err_trace')

        def _safe_str(value: ir.Value, name: str) -> ir.Value:
            has_value = builder.icmp_unsigned('!=', value, ir.Constant(i8_ptr, None), name=f'{name}_has_value')
            return builder.select(has_value, value, empty, name=name)

        message = _safe_str(message, '_err_safe_message')
        file = _safe_str(file, '_err_safe_file')
        trace = _safe_str(trace, '_err_safe_trace')

        snprintf = self._get_or_declare_function('snprintf', ir.FunctionType(i32, [i8_ptr, i64, i8_ptr], var_arg=True))
        needed_i32 = builder.call(snprintf, [
            ir.Constant(i8_ptr, None),
            ir.Constant(i64, 0),
            fmt,
            code,
            message,
            file,
            line,
            column,
            trace,
        ], name='_err_to_string_needed_i32')
        needed_i64 = builder.sext(needed_i32, i64, name='_err_to_string_needed_i64')
        alloc_len = builder.add(needed_i64, ir.Constant(i64, 1), name='_err_to_string_alloc_len')
        buf = builder.call(self._arena_alloc, [alloc_len, ir.Constant(i64, 1)], name='_err_to_string_buf')
        builder.call(snprintf, [buf, alloc_len, fmt, code, message, file, line, column, trace])
        builder.ret(buf)
        return func

    def _define_blob_methods(self) -> None:
        """内置 Blob.get / Blob.slice。"""
        self._define_blob_get()
        self._define_blob_slice()

    def _define_blob_get(self) -> ir.Function:
        existing = self.module.globals.get('Blob_get')
        if isinstance(existing, ir.Function):
            return existing

        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        blob_ptr = ir.PointerType(self.structs['Blob'])
        func = ir.Function(self.module, ir.FunctionType(i8, [blob_ptr, i64]), 'Blob_get')
        func.args[0].name = 'this'
        func.args[1].name = 'index'

        entry = func.append_basic_block('entry')
        ok_bb = func.append_basic_block('blob_get_ok')
        done_bb = func.append_basic_block('blob_get_done')
        builder = ir.IRBuilder(entry)
        data_ptr = builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        size_ptr = builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
        data = builder.load(data_ptr, name='_blob_get_data')
        size = builder.load(size_ptr, name='_blob_get_size')
        non_null = builder.icmp_unsigned('!=', data, ir.Constant(i8_ptr, None), name='_blob_get_non_null')
        non_negative = builder.icmp_signed('>=', func.args[1], ir.Constant(i64, 0), name='_blob_get_non_negative')
        in_range = builder.icmp_signed('<', func.args[1], size, name='_blob_get_in_range')
        valid = builder.and_(builder.and_(non_null, non_negative), in_range, name='_blob_get_valid')
        builder.cbranch(valid, ok_bb, done_bb)

        builder.position_at_start(ok_bb)
        item_ptr = builder.gep(data, [func.args[1]], inbounds=True)
        item = builder.load(item_ptr, name='_blob_get_item')
        builder.branch(done_bb)

        builder.position_at_start(done_bb)
        result = builder.phi(i8, name='_blob_get_result')
        result.add_incoming(ir.Constant(i8, 0), entry)
        result.add_incoming(item, ok_bb)
        builder.ret(result)
        return func

    def _define_blob_slice(self) -> ir.Function:
        existing = self.module.globals.get('Blob_slice')
        if isinstance(existing, ir.Function):
            return existing

        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        blob_type = self.structs['Blob']
        blob_ptr = ir.PointerType(blob_type)
        func = ir.Function(self.module, ir.FunctionType(blob_type, [blob_ptr, i64, i64]), 'Blob_slice')
        func.args[0].name = 'this'
        func.args[1].name = 'start'
        func.args[2].name = 'len'

        entry = func.append_basic_block('entry')
        clamp_len_bb = func.append_basic_block('blob_slice_clamp_len')
        full_len_bb = func.append_basic_block('blob_slice_full_len')
        build_bb = func.append_basic_block('blob_slice_build')
        empty_bb = func.append_basic_block('blob_slice_empty')
        done_bb = func.append_basic_block('blob_slice_done')
        builder = ir.IRBuilder(entry)

        data_ptr = builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        size_ptr = builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
        data = builder.load(data_ptr, name='_blob_slice_data')
        size = builder.load(size_ptr, name='_blob_slice_size')
        non_null = builder.icmp_unsigned('!=', data, ir.Constant(i8_ptr, None), name='_blob_slice_non_null')
        start_non_negative = builder.icmp_signed('>=', func.args[1], ir.Constant(i64, 0), name='_blob_slice_start_non_negative')
        len_positive = builder.icmp_signed('>', func.args[2], ir.Constant(i64, 0), name='_blob_slice_len_positive')
        start_before_end = builder.icmp_signed('<', func.args[1], size, name='_blob_slice_start_before_end')
        valid = builder.and_(builder.and_(non_null, start_non_negative), builder.and_(len_positive, start_before_end), name='_blob_slice_valid')
        builder.cbranch(valid, clamp_len_bb, empty_bb)

        builder.position_at_start(clamp_len_bb)
        remaining = builder.sub(size, func.args[1], name='_blob_slice_remaining')
        use_requested = builder.icmp_signed('<=', func.args[2], remaining, name='_blob_slice_use_requested')
        builder.cbranch(use_requested, full_len_bb, build_bb)

        builder.position_at_start(full_len_bb)
        builder.branch(build_bb)

        builder.position_at_start(build_bb)
        slice_len = builder.phi(i64, name='_blob_slice_len')
        slice_len.add_incoming(remaining, clamp_len_bb)
        slice_len.add_incoming(func.args[2], full_len_bb)
        slice_data = builder.gep(data, [func.args[1]], inbounds=True, name='_blob_slice_ptr')
        slice_value = ir.Constant(blob_type, ir.Undefined)
        slice_value = builder.insert_value(slice_value, slice_data, 0)
        slice_value = builder.insert_value(slice_value, slice_len, 1)
        builder.branch(done_bb)

        builder.position_at_start(empty_bb)
        empty_value = self._zero_constant(blob_type)
        builder.branch(done_bb)

        builder.position_at_start(done_bb)
        result = builder.phi(blob_type, name='_blob_slice_result')
        result.add_incoming(slice_value, build_bb)
        result.add_incoming(empty_value, empty_bb)
        builder.ret(result)
        return func

    def _define_runtime_void_hook(self, name: str, func_type: ir.FunctionType) -> ir.Function:
        """定义最小运行时 hook，避免本机链接时遗留未定义符号。"""
        func = ir.Function(self.module, func_type, name)
        entry = func.append_basic_block('entry')
        builder = ir.IRBuilder(entry)
        builder.ret_void()
        return func

    def _define_runtime_race_hook(self, name: str, func_type: ir.FunctionType) -> ir.Function:
        """旧 task 形态的 race hook：保留 ABI，返回任务参数作为兼容占位结果。"""
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
        if self.compile_target == 'emcc':
            sleep_fn = self._get_or_declare_function('__ezrt_emcc_sleep', ir.FunctionType(ir.VoidType(), [ir.IntType(64)]))
            builder.call(sleep_fn, [func.args[0]])
            builder.ret_void()
            return func
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

    def _emcc_runtime_lib_path(self) -> str:
        root = Path(__file__).resolve().parents[3]
        return str((root / 'packages' / 'std' / 'emcc' / 'runtime.js').resolve())

    def _add_active_extern_lib(self, lib_path: str) -> None:
        """按声明顺序收集当前目标需要链接的库，并避免重复传参。"""
        if lib_path not in self.active_extern_libs:
            self.active_extern_libs.append(lib_path)

    def _require_runtime(self) -> None:
        """标记需要链接当前目标的语言运行时 helper。"""
        if self.compile_target == 'emcc':
            path = self._emcc_runtime_lib_path()
            self._add_active_extern_lib(path)
            if (path, 'emcc') not in self.extern_libs:
                self.extern_libs.append((path, 'emcc'))
            return
        self._runtime_required = True
        path = self._runtime_lib_path()
        self._add_active_extern_lib(path)
        if self.compile_target != 'windows':
            self._add_active_extern_lib('pthread')
        if (path, None) not in self.extern_libs:
            self.extern_libs.append((path, None))
        if ('pthread', None) not in self.extern_libs and self.compile_target != 'windows':
            self.extern_libs.append(('pthread', None))

    def _require_flow_sleep(self) -> ir.Function:
        """按需生成 flow sleep hook；emcc 由 time.js 提供 Asyncify 兼容 helper。"""
        if self._flow_sleep is None:
            self._flow_sleep = self._define_sleep_hook('__ezrt_sleep', ir.FunctionType(ir.VoidType(), [ir.IntType(64)]))
        if self.compile_target == 'emcc':
            root = Path(__file__).resolve().parents[3]
            self._add_active_extern_lib(str((root / 'packages' / 'std' / 'emcc' / 'time.js').resolve()))
        return self._flow_sleep

    def _require_flow_suspend_source(self, func_name: str) -> None:
        """flow 内阻塞标准库调用在 emcc 下必须触发 Asyncify 链接准备。"""
        if self.compile_target != 'emcc' or func_name not in self._flow_suspend_names:
            return
        self._require_runtime()

    def _require_std_time(self) -> None:
        """内置 Date 方法需要链接 std/time 的目标平台封装。"""
        root = Path(__file__).resolve().parents[3]
        if self.compile_target == 'emcc':
            path = str((root / 'packages' / 'std' / 'emcc' / 'time.js').resolve())
            self._add_active_extern_lib(path)
            if (path, 'emcc') not in self.extern_libs:
                self.extern_libs.append((path, 'emcc'))
            return
        path = str((root / 'packages' / 'std' / 'native' / 'time.c').resolve())
        self._add_active_extern_lib(path)
        if (path, None) not in self.extern_libs:
            self.extern_libs.append((path, None))

    def _date_method_abi_type(self, func_name: str) -> ir.FunctionType | None:
        """返回内置 Date 方法对应的外部 ABI 签名。"""
        date_ptr = ir.PointerType(self.structs['Date'])
        i32 = ir.IntType(32)
        i8_ptr = ir.PointerType(ir.IntType(8))
        opt_i32 = ir.LiteralStructType([ir.IntType(1), i32])
        opt_i32_ptr = ir.PointerType(opt_i32)
        if func_name in {'dateGetYear', 'dateGetMonth', 'dateGetDay', 'dateGetHour', 'dateGetMinute', 'dateGetSecond'}:
            return ir.FunctionType(i32, [date_ptr])
        if func_name in {'dateAdd', 'dateSub'}:
            return ir.FunctionType(ir.VoidType(), [date_ptr, opt_i32_ptr, opt_i32_ptr, opt_i32_ptr, opt_i32_ptr, opt_i32_ptr, opt_i32_ptr])
        if func_name == 'dateFormat':
            return ir.FunctionType(i8_ptr, [date_ptr, i8_ptr])
        return None

    def _get_or_declare_date_method(self, func_name: str) -> ir.Function | None:
        """按需声明 Date 方法 ABI，并触发 std/time 链接。"""
        func_type = self._date_method_abi_type(func_name)
        if func_type is None:
            return None
        self._require_std_time()
        return self._get_or_declare_function(func_name, func_type)

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

        printf_fn = self._get_or_declare_function('printf', ir.FunctionType(i32, [i8_ptr], var_arg=True))
        exit_fn = self._get_or_declare_function('exit', ir.FunctionType(void, [i32]))
        data = bytearray('uncaught EzLang throw code=%d message=%s trace=%s\n\0', 'utf-8')
        arr_type = ir.ArrayType(ir.IntType(8), len(data))
        msg = ir.GlobalVariable(self.module, arr_type, '_ez_uncaught_throw_msg')
        msg.initializer = ir.Constant(arr_type, data)
        msg.global_constant = True
        msg.linkage = 'internal'
        msg_ptr = builder.gep(msg, [
            ir.Constant(i32, 0),
            ir.Constant(i32, 0),
        ], inbounds=True)
        code_ptr = builder.gep(self._throw_value, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        message_ptr = builder.gep(self._throw_value, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
        trace_ptr = builder.gep(self._throw_value, [ir.Constant(i32, 0), ir.Constant(i32, 5)], inbounds=True)
        code = builder.load(code_ptr, name='_uncaught_code')
        message = builder.load(message_ptr, name='_uncaught_message')
        trace = builder.load(trace_ptr, name='_uncaught_trace')
        empty_data = bytearray('\0', 'utf-8')
        empty_arr_type = ir.ArrayType(ir.IntType(8), len(empty_data))
        empty_msg = ir.GlobalVariable(self.module, empty_arr_type, '_ez_uncaught_empty_msg')
        empty_msg.initializer = ir.Constant(empty_arr_type, empty_data)
        empty_msg.global_constant = True
        empty_msg.linkage = 'internal'
        fallback = builder.gep(empty_msg, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        has_message = builder.icmp_unsigned('!=', message, ir.Constant(i8_ptr, None), name='_uncaught_has_message')
        safe_message = builder.select(has_message, message, fallback, name='_uncaught_safe_message')
        has_trace = builder.icmp_unsigned('!=', trace, ir.Constant(i8_ptr, None), name='_uncaught_has_trace')
        safe_trace = builder.select(has_trace, trace, fallback, name='_uncaught_safe_trace')
        builder.call(printf_fn, [msg_ptr, code, safe_message, safe_trace])
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

    def _current_error_file(self) -> str:
        """返回 Error.file 使用的源码文件名。"""
        try:
            return Path(self.source_name).name or str(self.source_name) or "<memory>"
        except Exception:
            return str(self.source_name) or "<memory>"

    def _current_error_trace(self, line: int, column: int) -> str:
        """生成轻量调用栈片段，格式保持可读且稳定。"""
        func_name = self.current_function.name if self.current_function is not None else "<top>"
        return f"{func_name}@{line}:{column}"

    def _error_location_values(self, ctx=None) -> tuple[ir.Value, ir.Value, ir.Value, ir.Value]:
        """生成 Error 的 file/line/column/trace 默认值。"""
        token = getattr(ctx, 'start', None)
        line = int(getattr(token, 'line', 1) or 1)
        column = int(getattr(token, 'column', 0) or 0) + 1
        return (
            self._make_global_string(self._current_error_file(), prefix="_err_file"),
            ir.Constant(ir.IntType(32), line),
            ir.Constant(ir.IntType(32), column),
            self._make_global_string(self._current_error_trace(line, column), prefix="_err_trace"),
        )

    def _error_value_with_location(self, code: ir.Value, message: ir.Value, ctx=None) -> ir.Value:
        """按内置 Error ABI 构造带位置元数据的值。"""
        file_value, line_value, column_value, trace_value = self._error_location_values(ctx)
        error = ir.Constant(self.structs['Error'], ir.Undefined)
        error = self.builder.insert_value(error, code, 0)
        error = self.builder.insert_value(error, message, 1)
        error = self.builder.insert_value(error, file_value, 2)
        error = self.builder.insert_value(error, line_value, 3)
        error = self.builder.insert_value(error, column_value, 4)
        return self.builder.insert_value(error, trace_value, 5)

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

    def _raise_error(self, code: int, message: str):
        """写入 Error 异常槽并跳转到当前异常出口。"""
        msg = self._make_global_string(message, prefix="_err_msg")
        error = self._error_value_with_location(ir.Constant(ir.IntType(32), code), msg)
        self._store_throw_value(error)
        self._branch_to_throw_exit_or_abort()

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
    def _is_weak_ref_type(t: ir.Type) -> bool:
        return (
            isinstance(t, ir.LiteralStructType)
            and len(t.elements) == 2
            and t.elements[0] == ir.IntType(1)
            and isinstance(t.elements[1], ir.PointerType)
        )

    @staticmethod
    def _is_union_type(t: ir.Type) -> bool:
        return isinstance(t, ir.LiteralStructType) and len(t.elements) == 2 and isinstance(t.elements[0], ir.IntType) and t.elements[0].width == 32

    def _union_type_ctxs(self, union_ctx) -> list:
        """把左递归解析得到的联合类型上下文展平为源码顺序。"""
        if not isinstance(union_ctx, EzLangParser.UnionTypeContext):
            return [union_ctx]
        result = []
        for child_ctx in union_ctx.type_():
            result.extend(self._union_type_ctxs(child_ctx))
        return result

    @staticmethod
    def _is_str_type(t: ir.Type) -> bool:
        """Str 在当前 ABI 中是 i8*。"""
        return isinstance(t, ir.PointerType) and t.pointee == ir.IntType(8)

    def _load_if_aggregate_ptr(self, val: ir.Value) -> ir.Value:
        """如果 val 是聚合类型的指针，load 它；否则原样返回"""
        if self._is_aggregate_ptr(val) and self.builder is not None:
            return self.builder.load(val)
        return val

    def _concat_str_values(self, left: ir.Value, right: ir.Value, name_prefix: str = '_str_concat') -> ir.Value:
        """生成 Str + Str 的最小拼接实现，返回 Arena 中的新 C 字符串。"""
        strlen = self._get_or_define_strlen()
        return self._join_c_string_segments([
            (left, self.builder.call(strlen, [left], name=f'{name_prefix}_left_len')),
            (right, self.builder.call(strlen, [right], name=f'{name_prefix}_right_len')),
        ], name_prefix=name_prefix)

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
        if isinstance(ctx, EzLangParser.WeakTypeContext):
            return f"#{self._type_ctx_name(ctx.type_())}"
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

    def _type_ctx_name_with_map(self, ctx, type_map: dict[str, ir.Type], unsigned_map: dict[str, bool],
                                type_name_map: dict[str, str] | None = None) -> str:
        """把泛型结构体字段类型名替换成实例化后的源类型名。"""
        if ctx is None:
            return "unknown"
        if isinstance(ctx, EzLangParser.OptionalTypeContext):
            return f"{self._type_ctx_name_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)}?"
        if isinstance(ctx, EzLangParser.ArrayTypeContext):
            return f"{self._type_ctx_name_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)}[]"
        if isinstance(ctx, EzLangParser.ListTypeContext):
            return f"List<{self._type_ctx_name_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)}>"
        if isinstance(ctx, EzLangParser.VecTypeContext):
            return f"Vec<{self._type_ctx_name_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)}>[{ctx.INTEGER_LITERAL().getText()}]"
        if isinstance(ctx, EzLangParser.PointerTypeContext):
            return f"*{self._type_ctx_name_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)}"
        if isinstance(ctx, EzLangParser.WeakTypeContext):
            return f"#{self._type_ctx_name_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)}"
        if isinstance(ctx, EzLangParser.ParenTypeContext):
            return self._type_ctx_name_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)
        if isinstance(ctx, EzLangParser.UnionTypeContext):
            return " | ".join(self._type_ctx_name_with_map(t, type_map, unsigned_map, type_name_map) for t in ctx.type_())
        if isinstance(ctx, EzLangParser.TypeShapeTypeContext):
            return "Dict" if self._type_shape_is_dynamic(ctx.typeShape()) else "shape"
        if isinstance(ctx, EzLangParser.TypeofTypeContext):
            return "I32"
        if hasattr(ctx, 'baseType') and ctx.baseType() is not None:
            bt = ctx.baseType()
            if bt.TYPE_IDENTIFIER() is not None:
                name = bt.TYPE_IDENTIFIER().getText()
                if name in type_map and bt.genericArgs() is None:
                    if type_name_map is not None and name in type_name_map:
                        return type_name_map[name]
                    return self._type_name_from_ir_type_with_unsigned(type_map[name], unsigned_map.get(name, False))
                if bt.genericArgs() is not None:
                    args = ", ".join(self._type_ctx_name_with_map(t, type_map, unsigned_map, type_name_map) for t in bt.genericArgs().type_())
                    return f"{name}<{args}>"
            return self._base_type_name(bt)
        text = ctx.getText() if hasattr(ctx, 'getText') else ""
        return text or "unknown"

    def _type_ctx_suffix(self, ctx) -> str:
        """把显式泛型参数转换为单态化后缀，保留 U32/U64 这类无符号名称。"""
        name = self._type_ctx_name(ctx)
        if name and name != "unknown":
            return self._type_suffix_from_name(name)
        return self._type_name(self._map_type(ctx))

    @staticmethod
    def _type_suffix_from_name(name: str) -> str:
        if name == "Bool":
            return "I1"
        name = name.replace("[]", "Array").replace("?", "Opt").replace("*", "Ptr")
        return re.sub(r'[^A-Za-z0-9_]+', '_', name).strip('_') or "T"

    def _type_ctx_is_unsigned_with_map(self, ctx, unsigned_map: dict[str, bool]) -> bool:
        """判断可能引用泛型参数的类型上下文是否为无符号整数。"""
        if self._type_ctx_is_generic_name(ctx, unsigned_map):
            return unsigned_map.get(ctx.baseType().TYPE_IDENTIFIER().getText(), False)
        return self._type_ctx_is_unsigned(ctx)

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
        return any(member.LBRACK() is not None for member in members)

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

    def _dict_literal_item_types(self, ctx) -> tuple[ir.Type, ir.Type] | None:
        """从字典字面量语法推导键和值类型，供全局声明阶段使用。"""
        literal = ctx.dictLiteral() if isinstance(ctx, EzLangParser.DictExprContext) else ctx
        if not isinstance(literal, EzLangParser.DictLiteralContext) and hasattr(ctx, 'getChildCount') and ctx.getChildCount() == 1:
            return self._dict_literal_item_types(ctx.getChild(0))
        if not isinstance(literal, EzLangParser.DictLiteralContext):
            return None
        i8_ptr = ir.PointerType(ir.IntType(8))
        key_type = i8_ptr
        value_type = i8_ptr
        saw_value_type = False
        for field in literal.dictField() if literal.dictField() else []:
            key_ctx = field.dictKey()
            if key_ctx is not None and key_ctx.expression() is not None:
                inferred_key_type = self._infer_global_initializer_type(key_ctx.expression())
                if inferred_key_type != i8_ptr:
                    key_type = inferred_key_type
            type_ctx = field.type_()
            if type_ctx is not None:
                value_type = self._map_type(type_ctx)
                saw_value_type = True
                continue
            inferred_value_type = self._infer_global_initializer_type(field.expression())
            if not saw_value_type and inferred_value_type is not None:
                value_type = inferred_value_type
                saw_value_type = True
        return key_type, value_type

    def _dict_item_types_for_name(self, name: str | None) -> tuple[ir.Type, ir.Type] | None:
        if not name:
            return None
        storage = self.locals.get(name) or self.globals.get(name)
        if storage is None:
            return None
        storage_type = storage.type.pointee if isinstance(storage.type, ir.PointerType) else storage.type
        if storage_type != self.structs.get('Dict'):
            return None
        return self._dict_item_types_for_value(storage)

    def _dict_item_types_from_decl(self, type_ctx, initializer) -> tuple[ir.Type, ir.Type] | None:
        item_types = self._dict_types_from_type_ctx(type_ctx)
        if item_types is not None:
            return item_types
        return self._dict_literal_item_types(initializer)

    def _infer_dict_index_value_type(self, ctx) -> ir.Type | None:
        """在全局变量声明期推断 headers[key] 这类 Dict 索引的值类型。"""
        if isinstance(ctx, EzLangParser.IndexContext):
            name = self._leftmost_identifier_name(ctx.postfixExpression())
            item_types = self._dict_item_types_for_name(name)
            if item_types is not None:
                return item_types[1]
        if hasattr(ctx, 'getChildCount') and ctx.getChildCount() == 1:
            for i in range(ctx.getChildCount()):
                result = self._infer_dict_index_value_type(ctx.getChild(i))
                if result is not None:
                    return result
        return None

    def _dict_types_from_type_ctx(self, ctx) -> tuple[ir.Type, ir.Type] | None:
        if ctx is None:
            return None
        if isinstance(ctx, EzLangParser.TypeShapeTypeContext):
            members = list(ctx.typeShape().typeShapeMember()) if ctx.typeShape() is not None else []
            dynamic_members = [member for member in members if member.LBRACK() is not None]
            if dynamic_members:
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
            if bt.TYPE_IDENTIFIER() is not None:
                name = bt.TYPE_IDENTIFIER().getText()
                if name in self._type_alias_dict_item_types:
                    return self._type_alias_dict_item_types[name]
        if hasattr(ctx, 'type_'):
            inner = ctx.type_()
            if inner is not None and not isinstance(inner, list):
                return self._dict_types_from_type_ctx(inner)
        return None

    def _expected_expr_type(self) -> ir.Type | None:
        return self._expected_expr_type_stack[-1] if self._expected_expr_type_stack else None

    def _expected_dict_item_types(self) -> tuple[ir.Type, ir.Type] | None:
        return self._expected_dict_item_types_stack[-1] if self._expected_dict_item_types_stack else None

    def _eval_expr_with_expected(
        self,
        ctx,
        expected_type: ir.Type | None,
        dict_item_types: tuple[ir.Type, ir.Type] | None = None,
    ):
        if ctx is None:
            return None
        if expected_type is None and dict_item_types is None:
            return self._eval_expr(ctx)
        self._expected_expr_type_stack.append(expected_type)
        self._expected_dict_item_types_stack.append(dict_item_types)
        try:
            return self._eval_expr(ctx)
        finally:
            self._expected_dict_item_types_stack.pop()
            self._expected_expr_type_stack.pop()

    def _dict_types_from_type_ctx_with_map(self, ctx, type_map: dict[str, ir.Type]) -> tuple[ir.Type, ir.Type] | None:
        if ctx is None:
            return None
        if isinstance(ctx, EzLangParser.TypeShapeTypeContext):
            members = list(ctx.typeShape().typeShapeMember()) if ctx.typeShape() is not None else []
            dynamic_members = [member for member in members if member.LBRACK() is not None]
            if dynamic_members:
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

    def _struct_mono_name(self, base_name: str, type_args: list[ir.Type],
                          type_arg_unsigned: list[bool] | None = None,
                          type_arg_names: list[str] | None = None) -> str:
        if type_arg_names is not None and len(type_arg_names) == len(type_args):
            suffix = '_'.join(self._type_suffix_from_name(name) for name in type_arg_names)
        else:
            unsigned = type_arg_unsigned or [False] * len(type_args)
            suffix = '_'.join(
                self._type_suffix_from_name(self._type_name_from_ir_type_with_unsigned(t, unsigned[i] if i < len(unsigned) else False))
                for i, t in enumerate(type_args)
            )
        return f"{base_name}_{suffix}" if suffix else base_name

    def _struct_name_from_generic_args(self, base_name: str, generic_args_ctx) -> str:
        if generic_args_ctx is None or base_name not in self.struct_generic_templates:
            return base_name
        type_arg_ctxs = list(generic_args_ctx.type_())
        if self._generic_type_map_stack:
            type_map, unsigned_map, type_name_map = self._generic_type_map_stack[-1]
            type_args = [self._map_type_with_map(t, type_map, unsigned_map, type_name_map) for t in type_arg_ctxs]
            type_arg_unsigned = [self._type_ctx_is_unsigned_with_map(t, unsigned_map) for t in type_arg_ctxs]
            type_arg_names = [self._type_ctx_name_with_map(t, type_map, unsigned_map, type_name_map) for t in type_arg_ctxs]
        else:
            type_args = [self._map_type(t) for t in type_arg_ctxs]
            type_arg_unsigned = [self._type_ctx_is_unsigned(t) for t in type_arg_ctxs]
            type_arg_names = [self._type_ctx_name(t) for t in type_arg_ctxs]
        return self._monomorphize_struct(base_name, type_args, type_arg_unsigned, type_arg_names)

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
            fname = self._field_name_text(field_ctx)
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
                             type_arg_unsigned: list[bool] | None = None,
                             type_arg_names: list[str] | None = None) -> str:
        """为显式泛型结构体实参生成独立 LLVM 布局。"""
        generic_names = self.struct_generic_params.get(base_name, [])
        if not generic_names or len(generic_names) != len(type_args):
            return base_name

        mono_name = self._struct_mono_name(base_name, type_args, type_arg_unsigned, type_arg_names)
        if mono_name in self._struct_monomorphized:
            return mono_name
        template_ctx = self.struct_generic_templates.get(base_name)
        if template_ctx is None:
            return base_name

        self._struct_monomorphized.add(mono_name)
        type_map = dict(zip(generic_names, type_args))
        unsigned_map = dict(zip(generic_names, type_arg_unsigned or [False] * len(generic_names)))
        type_name_map = dict(zip(generic_names, type_arg_names or []))

        struct_type = self.context.get_identified_type(mono_name)
        self.structs[mono_name] = struct_type
        field_names: list[str] = []
        field_types: list[ir.Type] = []
        field_unsigned: list[bool] = []
        field_type_names: list[str] = []
        defaults: dict[str, object] = {}
        methods: list[tuple[str, object, object]] = []

        self._struct_type_build_stack.append(mono_name)
        try:
            for member_ctx in template_ctx.structMember():
                field_ctx = member_ctx.structField()
                if field_ctx is not None:
                    fname = self._field_name_text(field_ctx)
                    ftype = self._map_type_with_map(field_ctx.type_(), type_map, unsigned_map, type_name_map)
                    field_names.append(fname)
                    field_types.append(ftype)
                    field_type_names.append(self._type_ctx_name_with_map(field_ctx.type_(), type_map, unsigned_map, type_name_map))
                    if self._type_ctx_is_generic_name(field_ctx.type_(), unsigned_map):
                        field_unsigned.append(unsigned_map.get(field_ctx.type_().baseType().TYPE_IDENTIFIER().getText(), False))
                    else:
                        field_unsigned.append(self._type_ctx_is_unsigned(field_ctx.type_()))
                    if field_ctx.expression() is not None:
                        defaults[fname] = field_ctx.expression()

                spread_ctx = member_ctx.structSpread()
                if spread_ctx is not None:
                    base_type = self._map_type_with_map(spread_ctx.type_(), type_map, unsigned_map, type_name_map)
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
                            base_type_names = self._struct_field_type_names.get(spread_name, [])
                            field_type_names.append(base_type_names[bf_idx] if bf_idx < len(base_type_names) else self._type_name_from_ir_type(base_type.elements[bf_idx]))

                method_ctx = member_ctx.structMethod()
                if method_ctx is not None:
                    methods.append((self._field_name_text(method_ctx), method_ctx.functionLiteral(), method_ctx.functionSignature()))
        finally:
            self._struct_type_build_stack.pop()

        if struct_type.is_opaque:
            struct_type.set_body(*field_types)
        self.struct_fields[mono_name] = field_names
        self._struct_field_unsigned[mono_name] = field_unsigned
        self._struct_field_type_names[mono_name] = field_type_names
        self.struct_defaults[mono_name] = defaults
        if methods:
            self.struct_methods[mono_name] = {}
            method_context = (type_map, unsigned_map, type_name_map)
            for mname, fn_lit, sig in methods:
                func_name = f"{mono_name}_{mname}"
                self.struct_methods[mono_name][mname] = func_name
                if fn_lit is not None:
                    self._gen_method_func(func_name, fn_lit, mono_name, generic_context=method_context)
                elif sig is not None:
                    self._generic_type_map_stack.append(method_context)
                    try:
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

    def _enter_function_codegen_state(self, builder: ir.IRBuilder, func: ir.Function) -> dict:
        """进入独立函数体生成上下文，避免继承外层 flow/loop/catch 状态。"""
        state = {
            'builder': self.builder,
            'current_function': self.current_function,
            'method_this': self._method_this,
            'locals': self.locals,
            'locals_type_names': self._locals_type_names,
            'shared_capture_locals': self._shared_capture_locals,
            'loop_exit_blocks': self.loop_exit_blocks,
            'loop_continue_blocks': self.loop_continue_blocks,
            'catch_exit_blocks': self.catch_exit_blocks,
            'catch_error_allocas': self.catch_error_allocas,
            'catch_result_allocas': self.catch_result_allocas,
            'function_throw_exit_stack': self._function_throw_exit_stack,
            'function_return_type_ctx_stack': self._function_return_type_ctx_stack,
            'flow_future_stack': self._flow_future_stack,
            'flow_depth': self._flow_depth,
            'parallel_result_stack': self._parallel_result_stack,
            'parallel_exit_stack': self._parallel_exit_stack,
            'parallel_arena_depth_stack': self._parallel_arena_depth_stack,
            'arena_scope_stack': self._arena_scope_stack,
        }
        self.builder = builder
        self.current_function = func
        self._method_this = None
        self.locals = {}
        self._locals_type_names = {}
        self._shared_capture_locals = set()
        self.loop_exit_blocks = []
        self.loop_continue_blocks = []
        self.catch_exit_blocks = []
        self.catch_error_allocas = []
        self.catch_result_allocas = []
        self._function_throw_exit_stack = []
        self._function_return_type_ctx_stack = []
        self._flow_future_stack = []
        self._flow_depth = 0
        self._parallel_result_stack = []
        self._parallel_exit_stack = []
        self._parallel_arena_depth_stack = []
        self._arena_scope_stack = []
        return state

    def _restore_function_codegen_state(self, state: dict) -> None:
        self.builder = state['builder']
        self.current_function = state['current_function']
        self._method_this = state['method_this']
        self.locals = state['locals']
        self._locals_type_names = state['locals_type_names']
        self._shared_capture_locals = state['shared_capture_locals']
        self.loop_exit_blocks = state['loop_exit_blocks']
        self.loop_continue_blocks = state['loop_continue_blocks']
        self.catch_exit_blocks = state['catch_exit_blocks']
        self.catch_error_allocas = state['catch_error_allocas']
        self.catch_result_allocas = state['catch_result_allocas']
        self._function_throw_exit_stack = state['function_throw_exit_stack']
        self._function_return_type_ctx_stack = state['function_return_type_ctx_stack']
        self._flow_future_stack = state['flow_future_stack']
        self._flow_depth = state['flow_depth']
        self._parallel_result_stack = state['parallel_result_stack']
        self._parallel_exit_stack = state['parallel_exit_stack']
        self._parallel_arena_depth_stack = state['parallel_arena_depth_stack']
        self._arena_scope_stack = state['arena_scope_stack']

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

    def _heap_allocate(self, llvm_type: ir.Type, name: str = "") -> ir.Value:
        """在进程堆上分配内存，用于可能跨线程访问的捕获环境。"""
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(ir.IntType(8))
        malloc = self._get_or_declare_function('malloc', ir.FunctionType(i8_ptr, [i64]))
        size_val = ir.Constant(i64, max(self._type_width(llvm_type), 1))
        raw_ptr = self.builder.call(malloc, [size_val], name=f'{name}_raw' if name else '')
        return self.builder.bitcast(raw_ptr, ir.PointerType(llvm_type), name=name)

    def _capture_shared_storage(self, name: str) -> ir.Value | None:
        """把捕获局部提升为共享存储槽，闭包/parallel 与外层共同读写。"""
        storage = self.locals.get(name)
        if storage is None or not isinstance(storage.type, ir.PointerType):
            return storage
        if name in self._shared_capture_locals:
            return storage
        pointee = storage.type.pointee
        shared = self._heap_allocate(pointee, name=f'_{name}_shared')
        current = self.builder.load(storage, name=f'_{name}_shared_init')
        self.builder.store(current, shared)
        self.locals[name] = shared
        self._shared_capture_locals.add(name)
        self._mark_unsigned(shared, self._ptr_unsigned.get(id(storage), False))
        if self._is_list_type(pointee):
            self._mark_list_elem_unsigned(shared, self._list_type_is_unsigned(storage.type))
        if pointee == self.structs.get('Dict'):
            key_type, value_type = self._dict_item_types_for_value(storage)
            self._mark_dict_item_types(shared, key_type, value_type)
        return shared

    # ==================== 类型映射 ====================

    def _map_type(self, ctx) -> ir.Type:
        """EzLang 类型 → LLVM 类型 (默认为 i32)"""
        if ctx is None:
            return ir.IntType(32)
        if self._generic_type_map_stack and not self._mapping_with_map:
            type_map, unsigned_map, type_name_map = self._generic_type_map_stack[-1]
            return self._map_type_with_map(ctx, type_map, unsigned_map, type_name_map)

        P = EzLangParser

        # 指针类型 *T 当前 lowering 为裸指针。
        if isinstance(ctx, P.PointerTypeContext):
            return ir.PointerType(self._map_type(ctx.type_()))

        # 弱引用类型 #T：运行时表示为 { ok, T* }。
        if isinstance(ctx, P.WeakTypeContext):
            return ir.LiteralStructType([ir.IntType(1), ir.PointerType(self._map_type(ctx.type_()))])

        # 匿名类型结构：动态键结构按 Dict ABI，普通结构使用字面结构。
        if isinstance(ctx, P.TypeShapeTypeContext):
            return self._map_type_shape(ctx.typeShape())

        # 可选类型: T? → {i1, T}
        if isinstance(ctx, P.OptionalTypeContext):
            inner = self._map_type(ctx.type_())
            if self._struct_type_build_stack and inner == self.structs.get(self._struct_type_build_stack[-1]):
                inner = ir.PointerType(inner)
            return ir.LiteralStructType([ir.IntType(1), inner])

        # 联合类型: T1 | T2 → {i32, [max_type]}
        if isinstance(ctx, P.UnionTypeContext):
            types = [self._map_type(t) for t in self._union_type_ctxs(ctx)]
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
            return self._closure_type(ret_type, param_types)

        # 泛型函数类型: <T> => Ret（无参数）
        if isinstance(ctx, P.GenericFunctionTypeContext):
            ret_type = self._map_type(ctx.type_())
            return self._closure_type(ret_type, [])

        # 泛型参数函数类型: <T>(params) => Ret（带参数，用于 declare）
        if isinstance(ctx, P.GenericParamFunctionTypeContext):
            ret_type = self._map_type(ctx.type_())
            param_types = []
            ptl = ctx.paramTypeList()
            if ptl is not None:
                for p in ptl.paramType():
                    param_types.append(self._map_type(p.type_()))
            return self._closure_type(ret_type, param_types)

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
        type_ctxs = self._union_type_ctxs(union_ctx)
        for index, type_ctx in enumerate(type_ctxs):
            variant_type = self._map_type(type_ctx)
            if variant_type == value_type:
                return index
        for index, type_ctx in enumerate(type_ctxs):
            variant_type = self._map_type(type_ctx)
            if isinstance(value_type, ir.PointerType) and isinstance(variant_type, ir.PointerType):
                return index
        for index, type_ctx in enumerate(type_ctxs):
            variant_type = self._map_type(type_ctx)
            if isinstance(value_type, ir.IntType) and isinstance(variant_type, ir.IntType):
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
        if dynamic_members:
            return self.structs['Dict']
        fields = []
        for _name, field_type, _unsigned, _type_name in self._shape_fixed_field_layout(shape_ctx):
            fields.append(field_type)
        return ir.LiteralStructType(fields) if fields else ir.IntType(32)

    def _shape_fixed_field_layout(self, shape_ctx) -> list[tuple[str, ir.Type, bool, str]]:
        layout: list[tuple[str, ir.Type, bool, str]] = []
        seen: set[str] = set()
        if shape_ctx is None:
            return layout
        for spread in shape_ctx.typeShapeSpread():
            base_type = self._map_type(spread.type_())
            base_name = base_type.name if isinstance(base_type, ir.IdentifiedStructType) else None
            if base_name not in self.struct_fields:
                continue
            base_unsigned = self._struct_field_unsigned.get(base_name, [])
            base_type_names = self._struct_field_type_names.get(base_name, [])
            for index, field_name in enumerate(self.struct_fields[base_name]):
                if field_name in seen or index >= len(base_type.elements):
                    continue
                seen.add(field_name)
                field_type = base_type.elements[index]
                layout.append((
                    field_name,
                    field_type,
                    base_unsigned[index] if index < len(base_unsigned) else False,
                    base_type_names[index] if index < len(base_type_names) else self._type_name_from_ir_type(field_type),
                ))
        for member in shape_ctx.typeShapeMember():
            if member.LBRACK() is not None or member.VAR_IDENTIFIER() is None:
                continue
            field_name = member.VAR_IDENTIFIER().getText()
            member_types = member.type_()
            member_types = member_types if isinstance(member_types, list) else [member_types]
            member_types = [t for t in member_types if t is not None]
            field_type = self._map_type(member_types[-1]) if member_types else ir.IntType(32)
            field_unsigned = self._type_ctx_is_unsigned(member_types[-1]) if member_types else False
            field_type_name = self._type_ctx_name(member_types[-1]) if member_types else "I32"
            if field_name in seen:
                layout = [item for item in layout if item[0] != field_name]
            seen.add(field_name)
            layout.append((field_name, field_type, field_unsigned, field_type_name))
        return layout

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
                if self._generic_type_map_stack:
                    type_map, unsigned_map, type_name_map = self._generic_type_map_stack[-1]
                    type_args = [self._map_type_with_map(t, type_map, unsigned_map, type_name_map) for t in type_arg_ctxs]
                    type_arg_unsigned = [self._type_ctx_is_unsigned_with_map(t, unsigned_map) for t in type_arg_ctxs]
                    type_arg_names = [self._type_ctx_name_with_map(t, type_map, unsigned_map, type_name_map) for t in type_arg_ctxs]
                else:
                    type_args = [self._map_type(t) for t in type_arg_ctxs]
                    type_arg_unsigned = [self._type_ctx_is_unsigned(t) for t in type_arg_ctxs]
                    type_arg_names = [self._type_ctx_name(t) for t in type_arg_ctxs]
                mono_name = self._monomorphize_struct(name, type_args, type_arg_unsigned, type_arg_names)
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
        meta_type = self.context.get_identified_type(meta_name)
        if meta_type.is_opaque:
            i8_ptr = ir.PointerType(ir.IntType(8))
            func_ptr = self._closure_type(value_type, [])
            setter_ptr = self._closure_type(ir.VoidType(), [value_type])
            meta_type.set_body(value_type, func_ptr, setter_ptr, i8_ptr, i8_ptr)
        self.structs[meta_name] = meta_type
        self.struct_fields[meta_name] = ['value', 'getter', 'setter', 't', 'name']
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
        self._decorated_globals.add(name)
        self._remember_type_name(name, value.type, value=value, global_scope=True)
        if decorator_name in self.generic_templates:
            decorator_name = self._monomorphize(
                decorator_name,
                [value.type],
                [self._type_name(value.type)],
                [False],
                [self._type_name_from_ir_type(value.type)],
            )
        decorator = self.module.globals.get(decorator_name)
        if isinstance(decorator, ir.Function):
            init_name = f"__decorator_init_{name}"
            init_type = ir.FunctionType(ir.VoidType(), [])
            init_fn = ir.Function(self.module, init_type, init_name)
            block = init_fn.append_basic_block('entry')
            builder = ir.IRBuilder(block)
            decorator_arg_types = list(decorator.function_type.args)
            meta_arg = gv
            if decorator_arg_types:
                expected = decorator_arg_types[0]
                expected_value_type = expected.pointee if isinstance(expected, ir.PointerType) else expected
                if self._is_weak_ref_type(expected_value_type) and expected_value_type.elements[1] == gv.type:
                    weak_type = expected_value_type
                    weak = ir.Constant(weak_type, ir.Undefined)
                    weak = builder.insert_value(weak, ir.Constant(ir.IntType(1), 1), 0)
                    weak = builder.insert_value(weak, gv, 1)
                    if isinstance(expected, ir.PointerType):
                        weak_slot = builder.alloca(weak_type, name='_decorator_this')
                        builder.store(weak, weak_slot)
                        meta_arg = weak_slot
                    else:
                        meta_arg = weak
                elif expected == meta_type:
                    meta_arg = builder.load(gv)
                elif expected != gv.type:
                    meta_arg = builder.bitcast(gv, expected) if isinstance(expected, ir.PointerType) else builder.load(gv)
            builder.call(decorator, [meta_arg])
            builder.ret_void()
            self._decorator_init_functions.append(init_fn)
        return gv

    def _is_meta_type(self, typ: ir.Type) -> bool:
        return isinstance(typ, ir.IdentifiedStructType) and (typ.name or '').startswith('Meta_')

    def _param_type_uses_reference(self, param_type: ir.Type, param_name: str, index: int) -> bool:
        if not isinstance(param_type, (ir.LiteralStructType, ir.IdentifiedStructType)):
            return False
        return (index == 0 and param_name == 'this') or self._is_meta_type(param_type)

    def _is_reference_param_type(self, param_type: ir.Type, param_name: str, index: int) -> bool:
        if not isinstance(param_type, ir.PointerType):
            return False
        pointee = param_type.pointee
        if not isinstance(pointee, (ir.LiteralStructType, ir.IdentifiedStructType)):
            return False
        return (index == 0 and param_name == 'this') or self._is_meta_type(pointee)

    def _meta_field_ptr(self, meta_ptr: ir.Value, field_index: int) -> ir.Value:
        return self.builder.gep(meta_ptr, [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), field_index),
        ], inbounds=True)

    def _meta_value_ptr(self, meta_ptr: ir.Value) -> ir.Value:
        return self._meta_field_ptr(meta_ptr, 0)

    def _meta_getter_ptr(self, meta_ptr: ir.Value) -> ir.Value:
        return self._meta_field_ptr(meta_ptr, 1)

    def _meta_setter_ptr(self, meta_ptr: ir.Value) -> ir.Value:
        return self._meta_field_ptr(meta_ptr, 2)

    def _load_decorated_global(self, name: str, meta_ptr: ir.Value) -> ir.Value:
        value_ptr = self._meta_value_ptr(meta_ptr)
        getter = self.builder.load(self._meta_getter_ptr(meta_ptr), name=f'_{name}_getter')
        getter_invoke = self.builder.extract_value(getter, 0, name=f'_{name}_getter_invoke')
        has_getter = self.builder.icmp_unsigned('!=', getter_invoke, ir.Constant(getter_invoke.type, None), name=f'_{name}_has_getter')
        value_type = meta_ptr.type.pointee.elements[0]
        result_ptr = self.builder.alloca(value_type, name=f'_{name}_read')
        call_block = self.builder.append_basic_block(f'{name}_getter_call')
        raw_block = self.builder.append_basic_block(f'{name}_getter_raw')
        done_block = self.builder.append_basic_block(f'{name}_getter_done')
        self.builder.cbranch(has_getter, call_block, raw_block)

        self.builder.position_at_start(call_block)
        self.builder.store(self._call_closure(getter, []), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(raw_block)
        self.builder.store(self._load_with_unsigned(value_ptr, name=name), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        value = self.builder.load(result_ptr, name=name)
        self._mark_unsigned(value, self._is_unsigned_value(value_ptr))
        return value

    def _store_decorated_global(self, name: str, meta_ptr: ir.Value, value: ir.Value, op_ctx=None) -> ir.Value:
        value_ptr = self._meta_value_ptr(meta_ptr)
        store_val = value
        if self._is_aggregate_ptr(store_val):
            store_val = self._copy_aggregate_value(store_val, name="_assign_copy")
            store_val = self.builder.load(store_val)
        if op_ctx is not None and op_ctx.ASSIGN() is None:
            current = self._load_decorated_global(name, meta_ptr)
            store_val = self._apply_assignment_operator(current, store_val, op_ctx)
        value_type = value_ptr.type.pointee
        if store_val.type != value_type:
            store_val = self._coerce_preserve_unsigned(store_val, value_type)

        setter = self.builder.load(self._meta_setter_ptr(meta_ptr), name=f'_{name}_setter')
        setter_invoke = self.builder.extract_value(setter, 0, name=f'_{name}_setter_invoke')
        has_setter = self.builder.icmp_unsigned('!=', setter_invoke, ir.Constant(setter_invoke.type, None), name=f'_{name}_has_setter')
        call_block = self.builder.append_basic_block(f'{name}_setter_call')
        raw_block = self.builder.append_basic_block(f'{name}_setter_raw')
        done_block = self.builder.append_basic_block(f'{name}_setter_done')
        self.builder.cbranch(has_setter, call_block, raw_block)

        self.builder.position_at_start(call_block)
        self._call_closure(setter, [store_val])
        self.builder.branch(done_block)

        self.builder.position_at_start(raw_block)
        self.builder.store(store_val, value_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        return store_val

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
        is_optional = (
            isinstance(ret_type, ir.LiteralStructType)
            and len(ret_type.elements) == 2
            and ret_type.elements[0] == ir.IntType(1)
        )
        if is_optional:
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
        bridged = self._c_abi_small_aggregate_return_type(ret_type)
        return bridged if bridged is not None else ret_type

    def _c_abi_small_aggregate_return_type(self, ret_type: ir.Type) -> ir.Type | None:
        """按常见 native C ABI 桥接 16 字节内的整型/指针小聚合返回。"""
        if not isinstance(ret_type, (ir.LiteralStructType, ir.IdentifiedStructType)):
            return None
        width = self._type_width(ret_type)
        if width <= 0 or width > 16:
            return None
        arch = self.target_arch
        hfa = self._c_abi_homogeneous_float_aggregate(ret_type)
        if arch in {'aarch64', 'arm64'}:
            if hfa is not None:
                return None
            if width <= 8:
                return ir.IntType(width * 8)
            return ir.ArrayType(ir.IntType(64), 2)
        if arch not in {'x86_64', 'amd64'}:
            return None

        if hfa is not None:
            hfa_ret = self._c_abi_x86_64_hfa_return_type(*hfa)
            if hfa_ret is not None:
                return hfa_ret

        layout = self._c_abi_aggregate_field_layout(ret_type)
        if layout is None:
            return None
        chunks: list[ir.Type] = []
        for start in range(0, width, 8):
            end = min(start + 8, width)
            fields = [(offset, field_type, field_width) for offset, field_type, field_width in layout if offset < end and offset + field_width > start]
            if not fields:
                continue
            if len(fields) == 1 and fields[0][0] == start:
                scalar = self._c_abi_x86_64_scalar_return_type(fields[0][1])
                if scalar is not None:
                    chunks.append(scalar)
                    continue
            if not all(self._c_abi_integer_like_field(field_type) for _, field_type, _ in fields):
                return None
            chunks.append(ir.IntType((end - start) * 8))
        if not chunks:
            return None
        if len(chunks) == 1:
            return chunks[0]
        return ir.LiteralStructType(chunks)

    def _c_abi_homogeneous_float_aggregate(self, ret_type: ir.Type) -> tuple[ir.Type, int] | None:
        """识别只由同一种 float/double 字段组成的小聚合。"""
        if not isinstance(ret_type, (ir.LiteralStructType, ir.IdentifiedStructType)):
            return None
        fields = list(ret_type.elements)
        if not fields or len(fields) > 4:
            return None
        first = fields[0]
        if not isinstance(first, (ir.FloatType, ir.DoubleType)):
            return None
        if not all(type(field) is type(first) for field in fields):
            return None
        return first, len(fields)

    def _c_abi_x86_64_hfa_return_type(self, elem_type: ir.Type, count: int) -> ir.Type | None:
        """x86_64 SysV/Darwin 对纯浮点小结构体使用 SSE 返回寄存器。"""
        if count <= 0:
            return None
        if isinstance(elem_type, ir.DoubleType):
            if count == 1:
                return elem_type
            if count == 2:
                return ir.LiteralStructType([elem_type, elem_type])
            return None
        if not isinstance(elem_type, ir.FloatType):
            return None
        if count == 1:
            return elem_type
        if count == 2:
            return ir.VectorType(elem_type, 2)
        if count == 3:
            return ir.LiteralStructType([ir.VectorType(elem_type, 2), elem_type])
        if count == 4:
            vec2 = ir.VectorType(elem_type, 2)
            return ir.LiteralStructType([vec2, vec2])
        return None

    def _c_abi_aggregate_field_layout(self, ret_type: ir.Type) -> list[tuple[int, ir.Type, int]] | None:
        layout: list[tuple[int, ir.Type, int]] = []
        offset = 0
        for elem in ret_type.elements:
            if isinstance(elem, (ir.LiteralStructType, ir.IdentifiedStructType, ir.ArrayType, ir.VectorType)):
                return None
            align = self._type_align(elem)
            offset = self._align_to(offset, align)
            width = self._type_width(elem)
            layout.append((offset, elem, width))
            offset += width
        return layout

    def _c_abi_integer_like_field(self, field_type: ir.Type) -> bool:
        return isinstance(field_type, (ir.IntType, ir.PointerType))

    def _c_abi_x86_64_scalar_return_type(self, field_type: ir.Type) -> ir.Type | None:
        if isinstance(field_type, ir.IntType):
            return ir.IntType(8) if field_type.width == 1 else field_type
        if isinstance(field_type, ir.PointerType):
            return field_type
        if isinstance(field_type, (ir.FloatType, ir.DoubleType)):
            return field_type
        return None

    def _restore_c_abi_return(self, func_name: str, value: ir.Value) -> ir.Value:
        bridge = self._c_abi_return_bridges.get(func_name)
        if bridge is None:
            return value
        ret_type, abi_ret_type = bridge
        slot = self.builder.alloca(ret_type, name=f"_{func_name}_abi_ret")
        raw_slot = self.builder.bitcast(slot, ir.PointerType(abi_ret_type))
        self.builder.store(value, raw_slot)
        return self.builder.load(slot, name=f"_{func_name}_ret")

    def _c_abi_param_type(self, param_type: ir.Type) -> ir.Type:
        """外部 C ABI 参数类型：聚合按指针传递，函数指针递归按 C ABI 降低。"""
        if self._is_weak_ref_type(param_type):
            return param_type.elements[1]
        if self._is_closure_type(param_type):
            signature = self._closure_signature(param_type)
            if signature is not None:
                ret_type, param_types = signature
                return self._c_abi_function_pointer_type(ir.PointerType(ir.FunctionType(ret_type, param_types)))
        if isinstance(param_type, ir.PointerType) and isinstance(param_type.pointee, ir.FunctionType):
            return self._c_abi_function_pointer_type(param_type)
        if isinstance(param_type, (ir.LiteralStructType, ir.IdentifiedStructType)):
            return ir.PointerType(param_type)
        return param_type

    def _c_abi_function_pointer_type(self, fn_ptr_type: ir.PointerType) -> ir.PointerType:
        func_type = fn_ptr_type.pointee
        ret_type = func_type.return_type
        uses_sret = self._uses_c_sret(ret_type)
        abi_ret_type = ir.VoidType() if uses_sret else self._c_abi_return_type(ret_type)
        abi_param_types = ([ir.PointerType(ret_type)] if uses_sret else []) + [
            self._c_abi_param_type(param_type) for param_type in func_type.args
        ]
        return ir.PointerType(ir.FunctionType(abi_ret_type, abi_param_types))

    def _to_c_abi_return(self, value: ir.Value, ret_type: ir.Type, abi_ret_type: ir.Type) -> ir.Value:
        if value.type == abi_ret_type:
            return value
        if self._is_aggregate_ptr(value):
            value = self.builder.load(value)
        if value.type != ret_type:
            value = self._coerce_return_value(value, ret_type)
        if abi_ret_type == ret_type:
            return value
        slot = self.builder.alloca(ret_type, name="_callback_ret_bridge")
        self.builder.store(value, slot)
        raw_slot = self.builder.bitcast(slot, ir.PointerType(abi_ret_type))
        return self.builder.load(raw_slot, name="_callback_abi_ret")

    def _coerce_call_arg(self, arg: ir.Value, target_type: ir.Type) -> ir.Value:
        if self._is_closure_type(target_type):
            if isinstance(arg, ir.Function):
                return self._closure_from_function(arg, target_type)
            if isinstance(arg, ir.Value) and arg.type == target_type:
                return arg
        callback = self._coerce_c_abi_callback_arg(arg, target_type)
        if callback is not None:
            return callback
        return self._coerce_value(arg, target_type)

    def _coerce_c_abi_callback_arg(self, arg: ir.Value, target_type: ir.Type) -> ir.Value | None:
        if not (isinstance(target_type, ir.PointerType) and isinstance(target_type.pointee, ir.FunctionType)):
            return None
        if isinstance(arg, ir.Value) and self._is_closure_type(arg.type):
            return None
        if isinstance(arg, ir.Function):
            source_ptr_type = arg.type
        elif isinstance(arg, ir.Value) and isinstance(arg.type, ir.PointerType) and isinstance(arg.type.pointee, ir.FunctionType):
            if arg.type == target_type:
                return arg
            # 没有上下文指针时，动态函数指针不能安全桥接成另一种 C ABI。
            return None
        else:
            return None
        expected_type = self._c_abi_function_pointer_type(source_ptr_type)
        if expected_type != target_type:
            return None
        return self._get_c_abi_callback_trampoline(arg, target_type)

    def _get_c_abi_callback_trampoline(self, func: ir.Function, target_type: ir.PointerType) -> ir.Function:
        key = (func.name, str(target_type))
        cached = self._c_abi_callback_trampolines.get(key)
        if cached is not None:
            return cached

        base_name = re.sub(r'[^0-9A-Za-z_]', '_', func.name)
        tramp_name = f"{base_name}_cabi_callback"
        counter = 0
        while tramp_name in self.module.globals:
            counter += 1
            tramp_name = f"{base_name}_cabi_callback_{counter}"

        source_type = func.function_type
        abi_type = target_type.pointee
        trampoline = ir.Function(self.module, abi_type, tramp_name)
        self._c_abi_callback_trampolines[key] = trampoline
        ret_type = source_type.return_type
        uses_sret = self._uses_c_sret(ret_type)
        if uses_sret and trampoline.args:
            trampoline.args[0].add_attribute('sret')

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_unsigned = self._save_unsigned_state()
        old_type_names = self._locals_type_names

        entry = trampoline.append_basic_block('entry')
        self.builder = ir.IRBuilder(entry)
        self.current_function = trampoline
        self.locals = {}
        self._locals_type_names = {}

        abi_index = 1 if uses_sret else 0
        source_args = []
        for param_type in source_type.args:
            abi_arg = trampoline.args[abi_index]
            abi_index += 1
            if isinstance(param_type, (ir.LiteralStructType, ir.IdentifiedStructType)) and isinstance(abi_arg.type, ir.PointerType):
                source_args.append(self.builder.load(abi_arg))
            elif abi_arg.type != param_type:
                source_args.append(self._coerce_value(abi_arg, param_type))
            else:
                source_args.append(abi_arg)

        if isinstance(ret_type, ir.VoidType):
            self.builder.call(func, source_args)
            self.builder.ret_void()
        else:
            result = self.builder.call(func, source_args)
            if uses_sret:
                out_ptr = trampoline.args[0]
                if self._is_aggregate_ptr(result):
                    result = self.builder.load(result)
                if result.type != ret_type:
                    result = self._coerce_return_value(result, ret_type)
                self.builder.store(result, out_ptr)
                self.builder.ret_void()
            else:
                abi_ret_type = abi_type.return_type
                self.builder.ret(self._to_c_abi_return(result, ret_type, abi_ret_type))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        return trampoline

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
        if (
            self._is_weak_ref_type(val.type)
            and isinstance(target_type, ir.PointerType)
            and val.type.elements[1] == target_type
        ):
            return self.builder.extract_value(val, 1, name='_weak_arg_ptr')
        if (
            isinstance(val.type, ir.PointerType)
            and self._is_weak_ref_type(val.type.pointee)
            and isinstance(target_type, ir.PointerType)
            and val.type.pointee.elements[1] == target_type
        ):
            ptr_slot = self.builder.gep(val, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), 1),
            ], inbounds=True)
            return self.builder.load(ptr_slot, name='_weak_arg_ptr')
        if self._is_closure_type(target_type):
            if isinstance(val, ir.Function):
                return self._closure_from_function(val, target_type)
            if isinstance(val, ir.Value) and val.type == target_type:
                return val
        if self._is_weak_ref_type(target_type):
            return self._coerce_weak_ref_value(val, target_type)
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

    def _is_aggregate_type(self, typ: ir.Type) -> bool:
        return isinstance(typ, (ir.LiteralStructType, ir.IdentifiedStructType, ir.ArrayType))

    def _pointer_to_value_as_type(self, ptr: ir.Value, target_type: ir.Type) -> ir.Value:
        typed_ptr = ptr if ptr.type.pointee == target_type else self.builder.bitcast(
            ptr,
            ir.PointerType(target_type),
            name='_type_assert_ptr',
        )
        if self._is_aggregate_type(target_type):
            return typed_ptr
        return self._load_with_unsigned(typed_ptr, name='_type_assert_load')

    def _optional_unwrapped_ir_value(self, opt_ptr: ir.Value | None) -> ir.Value | None:
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
        return self._pointer_to_value_as_type(value_ptr, opt_type.elements[1])

    def _type_assert_value(self, value: ir.Value | None, target_type: ir.Type) -> ir.Value | None:
        """实现 Type! expr：可选拆包、显式转换或等宽位级重解释。"""
        if value is None or not hasattr(value, 'type'):
            return None

        value_type = value.type.pointee if isinstance(value.type, ir.PointerType) else value.type
        if self._is_optional_type(value_type) and value_type != target_type:
            value = self._optional_unwrapped_ir_value(value)
            if value is None:
                return None

        if isinstance(value.type, ir.PointerType) and value.type == target_type:
            return value
        if isinstance(value.type, ir.PointerType) and value.type.pointee == target_type:
            return self._pointer_to_value_as_type(value, target_type)
        if value.type == target_type:
            return value

        coerced = self._coerce_value(value, target_type)
        if coerced.type == target_type:
            return coerced
        if isinstance(coerced.type, ir.PointerType) and coerced.type.pointee == target_type:
            return self._pointer_to_value_as_type(coerced, target_type)

        if isinstance(value.type, ir.IntType) and self._is_float(target_type):
            if value.type.width == self._type_width(target_type) * 8:
                return self.builder.bitcast(value, target_type, name='_type_assert_bitcast')
            return self.builder.uitofp(value, target_type) if self._is_unsigned_value(value) else self.builder.sitofp(value, target_type)
        if self._is_float(value.type) and isinstance(target_type, ir.IntType):
            if self._type_width(value.type) * 8 == target_type.width:
                return self.builder.bitcast(value, target_type, name='_type_assert_bitcast')
            return self.builder.fptoui(value, target_type) if self._is_unsigned_value(value) else self.builder.fptosi(value, target_type)
        if isinstance(value.type, ir.IntType) and isinstance(target_type, ir.PointerType):
            return self.builder.inttoptr(value, target_type, name='_type_assert_inttoptr')
        if isinstance(value.type, ir.PointerType) and isinstance(target_type, ir.IntType):
            return self.builder.ptrtoint(value, target_type, name='_type_assert_ptrtoint')
        if isinstance(value.type, ir.PointerType) and isinstance(target_type, ir.PointerType):
            return self.builder.bitcast(value, target_type, name='_type_assert_bitcast')

        if self._type_width(value.type) == self._type_width(target_type):
            if self._is_aggregate_type(target_type) or self._is_aggregate_type(value.type):
                source_ptr = value if isinstance(value.type, ir.PointerType) else self.builder.alloca(value.type, name='_type_assert_src')
                if source_ptr is not value:
                    self.builder.store(value, source_ptr)
                return self._pointer_to_value_as_type(source_ptr, target_type)
            return self.builder.bitcast(value, target_type, name='_type_assert_bitcast')

        return coerced

    def _truthy_value(self, val: ir.Value | None) -> ir.Value:
        """把条件表达式结果规范成 LLVM 分支需要的 i1。"""
        i1 = ir.IntType(1)
        if val is None:
            return ir.Constant(i1, 0)
        if self._is_aggregate_ptr(val):
            val = self.builder.load(val)
        if val.type == i1:
            return val
        if isinstance(val.type, ir.IntType):
            return self.builder.icmp_unsigned('!=', val, ir.Constant(val.type, 0))
        if self._is_float(val.type):
            return self.builder.fcmp_ordered('!=', val, ir.Constant(val.type, 0.0))
        if isinstance(val.type, ir.PointerType):
            return self.builder.icmp_unsigned('!=', val, ir.Constant(val.type, None))
        if self._is_optional_type(val.type):
            return self.builder.extract_value(val, 0)
        return ir.Constant(i1, 1)

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
        if self._is_aggregate_ptr(val) and self._type_width(val.type.pointee) <= self._type_width(variant_type):
            val = self.builder.load(val)
        if val.type != variant_type:
            if isinstance(val.type, ir.IntType) and isinstance(variant_type, ir.IntType):
                val = self._coerce_integer_value(val, variant_type)
            elif isinstance(val.type, ir.IntType) and isinstance(variant_type, ir.PointerType):
                val = self.builder.inttoptr(val, variant_type)
            elif isinstance(val.type, ir.PointerType) and isinstance(variant_type, ir.IntType):
                val = self.builder.ptrtoint(val, variant_type)
            elif isinstance(val.type, ir.PointerType) and isinstance(variant_type, ir.PointerType):
                val = self.builder.bitcast(val, variant_type)
            elif isinstance(val.type, ir.FloatType) and isinstance(variant_type, ir.DoubleType):
                val = self.builder.fpext(val, variant_type)
            elif isinstance(val.type, ir.DoubleType) and isinstance(variant_type, ir.FloatType):
                val = self.builder.fptrunc(val, variant_type)
            elif self.builder is not None and self._type_width(val.type) <= self._type_width(variant_type):
                tmp = self.builder.alloca(target_type, name='_union_pack')
                self.builder.store(self._zero_constant(target_type), tmp)
                tag_ptr = self.builder.gep(tmp, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)], inbounds=True)
                payload_ptr = self.builder.gep(tmp, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 1)], inbounds=True)
                self.builder.store(ir.Constant(ir.IntType(32), tag), tag_ptr)
                typed_payload_ptr = self.builder.bitcast(payload_ptr, ir.PointerType(val.type), name='_union_pack_payload')
                self.builder.store(val, typed_payload_ptr)
                return self.builder.load(tmp, name='_union_packed')
            else:
                return val
        return self.builder.insert_value(result, val, 1)

    def _optional_method_call(self, call_ctx, unwrap_ctx, method_name: str, args_ctx) -> ir.Value | None:
        """生成 opt?.method(...)：空值返回空可选，非空时调用方法并包装返回值。"""
        opt_val = self._eval(unwrap_ctx.postfixExpression())
        if opt_val is None or not hasattr(opt_val, 'type'):
            return None
        opt_type = opt_val.type.pointee if isinstance(opt_val.type, ir.PointerType) else opt_val.type
        is_weak = self._is_weak_ref_type(opt_type)
        if not self._is_optional_type(opt_type):
            return None
        value_type = opt_type.elements[1].pointee if is_weak else opt_type.elements[1]
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
        expected_names = self.func_param_names.get(func_name, [])
        if args_ctx is not None:
            provided, _positional_values, _placeholder_params = self._map_call_args_to_params(
                args_ctx, expected_names, implicit_this=True
            )
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
            self._coerce_call_arg(arg, abi_arg_types[i]) if i < len(abi_arg_types) and arg.type != abi_arg_types[i] else arg
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

    def _lock_policy_code(self, ctx) -> int | None:
        prefix = ctx.lockPrefix() if hasattr(ctx, 'lockPrefix') else None
        if prefix is None:
            return None
        if prefix.RP() is not None:
            return 1
        if prefix.WP() is not None:
            return 2
        return 0

    def _global_lock_policy_code(self, ctx) -> int | None:
        """用户源全局可变变量在原生可运行目标默认使用顺序锁。"""
        if ctx.CONST() is not None:
            return None
        prefix = ctx.lockPrefix() if hasattr(ctx, 'lockPrefix') else None
        if prefix is not None:
            return self._lock_policy_code(ctx)
        if self._import_depth > 0:
            return None
        if self.compile_target not in {'linux', 'macos', 'windows'}:
            return None
        return 0

    def _dict_key_text(self, field_ctx) -> str | None:
        key_ctx = field_ctx.dictKey() if hasattr(field_ctx, 'dictKey') else None
        if key_ctx is None:
            token = field_ctx.VAR_IDENTIFIER() if hasattr(field_ctx, 'VAR_IDENTIFIER') else None
            return token.getText() if token is not None else None
        if key_ctx.VAR_IDENTIFIER() is not None:
            return key_ctx.VAR_IDENTIFIER().getText()
        if key_ctx.STRING_LITERAL() is not None:
            return decode_string_literal_token(key_ctx.STRING_LITERAL().getText())
        return None

    def _field_name_text(self, ctx) -> str:
        token = ctx.VAR_IDENTIFIER() if hasattr(ctx, 'VAR_IDENTIFIER') else None
        return token.getText() if token is not None else ""

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

    def _emit_lock_metadata(self, name: str, policy_code: int | None):
        if policy_code is None:
            return None
        self._require_runtime()
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
        policy_code = self._lock_policies.get(name, 0)
        self.builder.call(self._lock_register, [name_ptr, ir.Constant(ir.IntType(32), policy_code)])
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

    def _emit_locked_assignment(self, name: str, target: ir.Value, rhs: ir.Value, op_ctx):
        def do_store():
            store_val = rhs
            if op_ctx is not None and op_ctx.ASSIGN() is None:
                current = self._load_with_unsigned(target, name="_assign_current")
                store_val = self._apply_assignment_operator(current, store_val, op_ctx)
            if store_val.type != target.type.pointee:
                store_val = self._coerce_preserve_unsigned(store_val, target.type.pointee)
            self.builder.store(store_val, target)
            return store_val

        return self._emit_lock_access(name, "write", do_store)

    def _simple_lvalue_name(self, ctx) -> str | None:
        """识别裸标识符左值名；成员和索引左值由专门路径处理。"""
        if ctx is None:
            return None
        text = ctx.getText() if hasattr(ctx, 'getText') else ''
        if _EZ_VAR_IDENTIFIER_RE.fullmatch(text):
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
        obj_ptr = self._weak_ref_pointee_ptr(obj_ptr) or obj_ptr
        pointee = obj_ptr.type.pointee if hasattr(obj_ptr.type, 'pointee') else obj_ptr.type
        if not isinstance(pointee, (ir.IdentifiedStructType, ir.LiteralStructType)):
            return None

        field_name = self._field_name_text(member_ctx)
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
            if self._is_str_type(current.type) and self._is_str_type(rhs.type):
                return self._concat_str_values(current, rhs, name_prefix='_assign_str_concat')
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
                result = self.builder.udiv(current, rhs, name="_assign_value") if unsigned else self._signed_floor_div_rem(current, rhs, "_assign_floor")[0]
            self._mark_unsigned(result, unsigned)
            return result
        if op_ctx.PERCENT_ASSIGN() is not None:
            result = self.builder.urem(current, rhs, name="_assign_value") if unsigned else self._signed_floor_div_rem(current, rhs, "_assign_floor")[1]
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

    def _signed_floor_div_rem(self, left: ir.Value, right: ir.Value, name_prefix: str = "_floor") -> tuple[ir.Value, ir.Value]:
        """生成有符号整数 floor 除法和余数，满足 a = (a // b) * b + (a % b)。"""
        trunc_q = self.builder.sdiv(left, right, name=f"{name_prefix}_trunc_q")
        trunc_r = self.builder.srem(left, right, name=f"{name_prefix}_trunc_r")
        zero = self._zero_constant(left.type)
        one = ir.Constant(left.type, 1) if isinstance(left.type, ir.IntType) else self._broadcast_scalar_to_vector(ir.Constant(left.type.element, 1), left.type)
        has_rem = self.builder.icmp_signed('!=', trunc_r, zero, name=f"{name_prefix}_has_rem")
        left_neg = self.builder.icmp_signed('<', left, zero, name=f"{name_prefix}_left_neg")
        right_neg = self.builder.icmp_signed('<', right, zero, name=f"{name_prefix}_right_neg")
        signs_differ = self.builder.xor(left_neg, right_neg, name=f"{name_prefix}_signs_differ")
        adjust = self.builder.and_(has_rem, signs_differ, name=f"{name_prefix}_adjust")
        q_minus_one = self.builder.sub(trunc_q, one, name=f"{name_prefix}_q_minus_one")
        floor_q = self.builder.select(adjust, q_minus_one, trunc_q, name=f"{name_prefix}_q")
        q_mul_rhs = self.builder.mul(floor_q, right, name=f"{name_prefix}_q_mul_rhs")
        floor_r = self.builder.sub(left, q_mul_rhs, name=f"{name_prefix}_r")
        return floor_q, floor_r

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

    def _type_name_from_ir_type_with_unsigned(self, typ: ir.Type | None, unsigned: bool) -> str:
        if isinstance(typ, ir.IntType) and typ.width in {8, 32, 64}:
            return f"U{typ.width}" if unsigned else f"I{typ.width}"
        return self._type_name_from_ir_type(typ)

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
        if self._is_optional_type(typ):
            return f"{self._type_name_from_ir_type(typ.elements[1])}?"
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

        if top_level_work or self.ensure_entrypoint:
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

        self._emit_decorator_inits()

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

    def _emit_decorator_inits(self) -> None:
        if self.builder is None:
            return
        for init_fn in self._decorator_init_functions:
            self.builder.call(init_fn, [])

    def _init_global_variable(self, ctx: EzLangParser.VariableDeclContext):
        name = self._qualified_name(ctx)
        initializer = ctx.expression()
        if initializer is None or name not in self.globals:
            return None
        gv = self.globals[name]
        dict_item_types = self._dict_item_types_from_decl(ctx.type_(), initializer)
        val = self._eval_expr_with_expected(initializer, gv.type.pointee, dict_item_types)
        if val is None:
            return None
        source_dict_types = None
        if isinstance(getattr(val, 'type', None), ir.PointerType) and val.type.pointee == self.structs.get('Dict'):
            source_dict_types = self._dict_item_types_for_value(val)
        if self._is_aggregate_ptr(val):
            val = self.builder.load(val)
        val = self._coerce_value(val, gv.type.pointee)
        if val.type != gv.type.pointee:
            return None
        self._emit_lock_access(name, "write", lambda: self.builder.store(val, gv))
        if gv.type.pointee == self.structs.get('Dict'):
            item_types = self._dict_item_types_from_decl(ctx.type_(), initializer) or source_dict_types
            if item_types is not None:
                self._mark_dict_item_types(gv, item_types[0], item_types[1])
        self.locals[name] = gv
        type_name = self._globals_type_names.get(name) or self._type_name_from_ir_type(gv.type.pointee)
        self._locals_type_names[name] = type_name
        return None

    def _infer_global_initializer_type(self, initializer, local_types: dict[str, ir.Type] | None = None) -> ir.Type:
        text = initializer.getText()
        if text.startswith('typeof'):
            return ir.IntType(32)
        if self._is_exact_flow_block_expr(initializer):
            return self._infer_flow_result_type(initializer)
        if self._is_exact_parallel_block_expr(initializer):
            return self._infer_parallel_result_type(initializer)
        bool_type = self._infer_boolean_expression_type(initializer)
        if bool_type is not None:
            return bool_type
        if text.startswith('race('):
            return self._infer_race_result_type(initializer)
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

        if _EZ_VAR_IDENTIFIER_RE.fullmatch(text):
            if local_types is not None and text in local_types:
                return local_types[text]
            storage = self.locals.get(text) or self.globals.get(text)
            if storage is not None and not isinstance(storage, ir.Function):
                return storage.type.pointee if isinstance(storage.type, ir.PointerType) else storage.type

        dict_index_type = self._infer_dict_index_value_type(initializer)
        if dict_index_type is not None:
            return dict_index_type

        method_call_name = self._expr_method_call_name(initializer)
        if method_call_name is not None and method_call_name in self.module.globals:
            if method_call_name in self._sret_functions:
                return self._sret_functions[method_call_name]
            callee = self.module.globals[method_call_name]
            func_type = callee.type.pointee if isinstance(callee.type, ir.PointerType) else None
            if isinstance(func_type, ir.FunctionType):
                return func_type.return_type

        call_name = self._expr_call_name(initializer)
        generic_arg_ctxs = self._expr_call_generic_arg_ctxs(initializer)
        generic_args = [self._map_type(t) for t in generic_arg_ctxs]
        if call_name is not None and generic_args:
            call_name = self._monomorphize(
                call_name,
                generic_args,
                [self._type_ctx_suffix(t) for t in generic_arg_ctxs],
                [self._type_ctx_is_unsigned(t) for t in generic_arg_ctxs],
                [self._type_ctx_name(t) for t in generic_arg_ctxs],
            )
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
            if list_builtin == 'randomShuffle':
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

    def _is_exact_flow_block_expr(self, ctx) -> bool:
        """判断初始化表达式是否完整就是 `flow { ... }`。"""
        if ctx is None:
            return False
        if isinstance(ctx, EzLangParser.FlowBlockExprContext):
            return True
        if hasattr(ctx, 'flowBlock') and ctx.flowBlock() is not None and ctx.getChildCount() == 1:
            return True
        if hasattr(ctx, 'getChildCount') and ctx.getChildCount() == 1:
            return self._is_exact_flow_block_expr(ctx.getChild(0))
        return False

    def _infer_flow_result_type(self, ctx) -> ir.Type:
        """从 flow 块中的 return 推断表达式结果类型。"""
        if isinstance(ctx, EzLangParser.FlowBlockExprContext):
            return self._infer_block_return_type(ctx.flowBlock().block())
        if hasattr(ctx, 'flowBlock') and ctx.flowBlock() is not None:
            return self._infer_block_return_type(ctx.flowBlock().block())
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._infer_flow_result_type(ctx.getChild(i))
                if not isinstance(result, ir.IntType) or result.width != 32:
                    return result
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

    def _is_exact_parallel_block_expr(self, ctx) -> bool:
        """判断初始化表达式是否完整就是 `parallel { ... }`，避免截断组合表达式。"""
        if ctx is None:
            return False
        if isinstance(ctx, EzLangParser.ParallelBlockExprContext):
            return True
        if hasattr(ctx, 'parallelBlock') and ctx.parallelBlock() is not None and ctx.getChildCount() == 1:
            return True
        if hasattr(ctx, 'getChildCount') and ctx.getChildCount() == 1:
            return self._is_exact_parallel_block_expr(ctx.getChild(0))
        return False

    def _infer_boolean_expression_type(self, ctx) -> ir.Type | None:
        """识别当前表达式本身会产生 Bool 的常见运算。"""
        node = ctx
        while hasattr(node, 'getChildCount') and node.getChildCount() == 1:
            child = node.getChild(0)
            if not hasattr(child, 'getChildCount'):
                break
            node = child

        i1 = ir.IntType(1)
        if isinstance(node, EzLangParser.OrExpressionContext) and len(node.andExpression()) > 1:
            return i1
        if isinstance(node, EzLangParser.AndExpressionContext) and len(node.equalityExpression()) > 1:
            return i1
        if isinstance(node, EzLangParser.EqualityExpressionContext) and len(node.relationalExpression()) > 1:
            return i1
        if isinstance(node, EzLangParser.RelationalExpressionContext) and len(node.bitOrExpression()) > 1:
            return i1
        if isinstance(node, EzLangParser.UnaryExpressionContext) and hasattr(node, 'BANG') and node.BANG() is not None:
            return i1
        return None

    def _infer_race_result_type(self, ctx) -> ir.Type:
        """从 race(pl = [() => T, ...]) 分支推断表达式结果类型。"""
        array_lit = self._find_array_literal_ctx(ctx)
        branches = self._function_literals_in_array(array_lit)
        if not branches:
            return ir.IntType(32)
        return self._merge_ir_union_types([
            self._infer_function_literal_return_type(branch)
            for branch in branches
        ])

    def _infer_block_return_type(self, block_ctx) -> ir.Type:
        if block_ctx is None:
            return ir.VoidType()
        return_types = self._collect_block_return_types(block_ctx)
        if return_types:
            return self._merge_ir_union_types(return_types)
        return ir.VoidType()

    def _merge_ir_union_types(self, types: list[ir.Type]) -> ir.Type:
        """把多个 LLVM 类型合并为单一结果类型；不同类型用 EzLang union ABI。"""
        concrete = [t for t in types if not isinstance(t, ir.VoidType)]
        if not concrete:
            return ir.VoidType()
        unique: list[ir.Type] = []
        for type_ in concrete:
            if not any(type_ == existing for existing in unique):
                unique.append(type_)
        if len(unique) == 1:
            return unique[0]
        max_type = max(unique, key=lambda t: self._type_width(t))
        return ir.LiteralStructType([ir.IntType(32), max_type])

    def _ir_union_variant_tag_for_types(self, union_type: ir.Type, variant_types: list[ir.Type], value_type: ir.Type) -> int:
        if not self._is_union_type(union_type):
            return 0
        unique: list[ir.Type] = []
        for type_ in variant_types:
            if isinstance(type_, ir.VoidType):
                continue
            if not any(type_ == existing for existing in unique):
                unique.append(type_)
        for index, type_ in enumerate(unique):
            if type_ == value_type:
                return index
        return 0

    def _collect_block_return_types(self, block_ctx) -> list[ir.Type]:
        """收集当前 flow/parallel/race 函数体内的 return 类型，不跨越嵌套函数或并发块。"""
        result: list[ir.Type] = []
        local_types: dict[str, ir.Type] = {}

        def walk(node) -> None:
            if node is None:
                return
            if node is not block_ctx and isinstance(node, (
                EzLangParser.FunctionLiteralContext,
                EzLangParser.FlowBlockContext,
                EzLangParser.ParallelBlockContext,
                EzLangParser.CatchBlockContext,
            )):
                return
            ret = node.returnStatement() if hasattr(node, 'returnStatement') else None
            if ret is not None:
                if ret.expression() is not None:
                    result.append(self._infer_global_initializer_type(ret.expression(), local_types))
                else:
                    result.append(ir.VoidType())
                return
            if isinstance(node, EzLangParser.ReturnStatementContext):
                if node.expression() is not None:
                    result.append(self._infer_global_initializer_type(node.expression(), local_types))
                else:
                    result.append(ir.VoidType())
                return
            decl = node.declaration() if hasattr(node, 'declaration') else None
            var_decl = decl.variableDecl() if decl is not None and hasattr(decl, 'variableDecl') else None
            if var_decl is not None:
                qname = var_decl.qualifiedVarName()
                if qname is not None and len(qname.VAR_IDENTIFIER()) == 1:
                    name = qname.VAR_IDENTIFIER(0).getText()
                    if var_decl.type_() is not None:
                        local_types[name] = self._map_type(var_decl.type_())
                    elif var_decl.expression() is not None:
                        local_types[name] = self._infer_global_initializer_type(var_decl.expression(), local_types)
            if hasattr(node, 'getChildCount'):
                for i in range(node.getChildCount()):
                    walk(node.getChild(i))

        walk(block_ctx)
        return result

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

    def _expr_method_call_name(self, ctx) -> str | None:
        if isinstance(ctx, EzLangParser.CallContext):
            return self._method_call_function_name(ctx.postfixExpression())
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._expr_method_call_name(ctx.getChild(i))
                if result is not None:
                    return result
        return None

    def _method_call_function_name(self, target) -> str | None:
        if not isinstance(target, EzLangParser.MemberAccessContext):
            return None
        method_name = target.VAR_IDENTIFIER().getText()
        static_owner = self._static_struct_member_owner(target.postfixExpression())
        if static_owner is not None:
            return self.struct_methods.get(static_owner, {}).get(method_name)

        receiver_type = self._method_receiver_struct_name(target.postfixExpression())
        if receiver_type is None:
            return None
        return self.struct_methods.get(receiver_type, {}).get(method_name)

    def _collection_method_call_info(self, target) -> tuple[str, ir.Value] | None:
        """识别 List/Dict 对象方法糖，并返回对应内建函数名和接收者。"""
        if not isinstance(target, EzLangParser.MemberAccessContext):
            return None
        method_name = target.VAR_IDENTIFIER().getText()
        receiver = self._eval(target.postfixExpression())
        if receiver is None or not hasattr(receiver, 'type'):
            return None
        receiver_type = receiver.type.pointee if isinstance(receiver.type, ir.PointerType) else receiver.type
        if self._is_list_type(receiver_type):
            list_ptr = self._as_list_ptr(receiver)
            if list_ptr is None:
                return None
            elem_type = self._list_elem_type(list_ptr)
            suffix = self._type_name_from_ir_type(elem_type)
            mapping = {
                'len': 'listLen',
                'push': 'listPush',
                'pop': 'listPop',
                'shift': 'listShift',
                'unshift': 'listUnshift',
                'slice': 'listSlice',
                'sort': 'listSort',
                'filter': 'listFilter',
                'map': 'listMap',
                'find': 'listFind',
            }
            base = mapping.get(method_name)
            if base is not None:
                return f"{base}_{suffix}", self._weak_ref_value(list_ptr, list_ptr.type.pointee)
        if receiver_type == self.structs.get('Dict'):
            key_type, value_type = self._dict_item_types_for_value(receiver)
            key_suffix = self._type_name_from_ir_type(key_type)
            value_suffix = self._type_name_from_ir_type(value_type)
            mapping = {
                'len': 'dictLen',
                'has': 'dictHas',
                'delete': 'dictDelete',
                'keys': 'dictKeys',
                'values': 'dictValues',
            }
            base = mapping.get(method_name)
            if base is not None:
                dict_ptr = self._as_dict_ptr(receiver)
                if dict_ptr is None:
                    return None
                return f"{base}_{key_suffix}_{value_suffix}", self._weak_ref_value(dict_ptr, dict_ptr.type.pointee)
        return None

    def _method_receiver_struct_name(self, ctx) -> str | None:
        if isinstance(ctx, EzLangParser.CallContext):
            inferred = self._infer_global_initializer_type(ctx)
            if isinstance(inferred, ir.IdentifiedStructType) and inferred.name in self.struct_methods:
                return inferred.name
        struct_name = self._expr_struct_literal_name(ctx)
        if struct_name is not None and struct_name in self.struct_methods:
            return struct_name
        ident = self._leftmost_identifier_ctx(ctx)
        if ident is None or ident.getText() != (ctx.getText() if hasattr(ctx, 'getText') else ''):
            return None
        token = ident.VAR_IDENTIFIER() or ident.TYPE_IDENTIFIER()
        name = token.getText() if token is not None else None
        if name is None:
            return None
        type_name = self._locals_type_names.get(name) or self._globals_type_names.get(name)
        if type_name in self.struct_methods:
            return type_name
        value = self.locals.get(name) or self.globals.get(name)
        if value is not None:
            value_type = value.type.pointee if isinstance(value.type, ir.PointerType) else value.type
            if isinstance(value_type, ir.IdentifiedStructType) and value_type.name in self.struct_methods:
                return value_type.name
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

    def _expr_call_generic_arg_ctxs(self, ctx) -> list:
        if isinstance(ctx, EzLangParser.CallContext):
            ident = self._leftmost_identifier_ctx(ctx.postfixExpression())
            if ident is not None and ident.genericArgs() is not None:
                return list(ident.genericArgs().type_())
            return []
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._expr_call_generic_arg_ctxs(ctx.getChild(i))
                if result:
                    return result
        return []

    def _expr_call_generic_args(self, ctx) -> list[ir.Type]:
        return [self._map_type(t) for t in self._expr_call_generic_arg_ctxs(ctx)]

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
            ret_dict_types = self._dict_types_from_type_ctx(fn_type.type_())
            if ret_dict_types is not None:
                self.func_return_dict_types[name] = ret_dict_types
            param_types = []
            params = fn_type.paramTypeList()
            if params is not None:
                for p in params.paramType():
                    pt = self._map_type(p.type_())
                    param_types.append(self._c_abi_param_type(pt))
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
            param_type_ctxs = []
            if params is not None:
                for p in params.paramType():
                    param_names.append(p.VAR_IDENTIFIER().getText())
                    param_type_ctxs.append(p.type_())
            self.func_param_names[name] = param_names
            self.func_param_type_ctxs[name] = param_type_ctxs
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
        raw_lib_path = decode_string_literal_token(ctx.STRING_LITERAL().getText())
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
            self._add_active_extern_lib(lib_path)
            if suffix == '.js' and (target == 'emcc' or self.compile_target == 'emcc'):
                self._emcc_js_libs.append(lib_path)
        return None

    def visitImportDecl(self, ctx: EzLangParser.ImportDeclContext):
        """import 模块导入：编译被导入文件，合并符号到当前模块"""
        path = decode_string_literal_token(ctx.STRING_LITERAL().getText())

        # 解析路径：优先相对当前源码文件目录，保留旧的 examples/packages fallback。
        search_dirs = []
        current_dir = self._source_dir_stack[-1] if self._source_dir_stack else self.base_dir
        search_dirs.append(current_dir)
        search_dirs.extend([
            Path(__file__).resolve().parents[3] / 'examples',
            Path(__file__).resolve().parents[3] / 'packages',
        ])
        source = None
        resolved_file: Path | None = None
        for d in search_dirs:
            raw = (Path(d) / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
            candidates = [raw]
            if raw.suffix != '.ez':
                candidates.extend([Path(str(raw) + '.ez'), raw / 'index.ez'])
            resolved_file = next((candidate for candidate in candidates if candidate.is_file()), None)
            if resolved_file is not None:
                source = resolved_file.read_text(encoding='utf-8')
                break

        if source is None:
            return None

        # 编译导入文件到同一个模块（避免循环导入）
        if not hasattr(self, '_imported'):
            self._imported = set()
        import_key = str(resolved_file.resolve()) if resolved_file is not None else path
        if import_key in self._imported:
            return None
        self._imported.add(import_key)

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
        self._import_depth += 1
        if resolved_file is not None:
            self._source_dir_stack.append(resolved_file.parent)
        try:
            for i in range(tree.getChildCount()):
                child = tree.getChild(i)
                if hasattr(child, 'accept') and child.getChildCount() > 0:
                    child.accept(self)
        finally:
            if resolved_file is not None:
                self._source_dir_stack.pop()
            self._import_depth -= 1

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
        lock_policy_code = self._global_lock_policy_code(ctx) if self.builder is None else self._lock_policy_code(ctx)
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
            dict_item_types = self._dict_item_types_from_decl(type_ctx, initializer)
            if dict_item_types is not None:
                self._mark_dict_item_types(gv, dict_item_types[0], dict_item_types[1])
            self._mark_unsigned(gv, self._type_ctx_is_unsigned(type_ctx))
            if type_ctx is not None:
                self._mark_list_elem_unsigned(gv, self._type_ctx_is_unsigned(type_ctx))
        else:
            # 局部变量
            if type_ctx is not None:
                llvm_type = self._map_type(type_ctx)
                parallel_block = self._parallel_block_from_initializer(initializer) if self._is_exact_parallel_block_expr(initializer) else None
                if parallel_block is not None and self._flow_depth > 0 and self._type_ctx_name(type_ctx) == 'I32':
                    future_handle = self._start_flow_parallel_i32_future(name, parallel_block)
                    if future_handle is not None:
                        alloca = self.builder.alloca(llvm_type, name=name)
                        self.builder.store(self._zero_constant(llvm_type), alloca)
                        self.locals[name] = alloca
                        self._remember_type_name(name, llvm_type, type_ctx)
                        self._mark_unsigned(alloca, self._type_ctx_is_unsigned(type_ctx))
                        self._mark_list_elem_unsigned(alloca, self._type_ctx_is_unsigned(type_ctx))
                        return None
                alloca = self.builder.alloca(llvm_type, name=name)
                self.locals[name] = alloca
                self._remember_type_name(name, llvm_type, type_ctx)
                dict_item_types = self._dict_types_from_type_ctx(type_ctx)
                if dict_item_types is not None:
                    self._mark_dict_item_types(alloca, dict_item_types[0], dict_item_types[1])
                self._mark_unsigned(alloca, self._type_ctx_is_unsigned(type_ctx))
                self._mark_list_elem_unsigned(alloca, self._type_ctx_is_unsigned(type_ctx))
                if initializer is not None:
                    val = self._eval_expr_with_expected(initializer, llvm_type, dict_item_types)
                    if val is not None:
                        if self._is_aggregate_ptr(val) and val.type.pointee == llvm_type:
                            loaded_val = self.builder.load(val)
                            self._emit_lock_access(name, "write", lambda: self.builder.store(loaded_val, alloca))
                            if llvm_type == self.structs.get('Dict'):
                                source_dict_types = self._dict_item_types_for_value(val)
                                self._mark_dict_item_types(alloca, source_dict_types[0], source_dict_types[1])
                        else:
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
                parallel_block = self._parallel_block_from_initializer(initializer) if self._is_exact_parallel_block_expr(initializer) else None
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
            if dynamic_members:
                member = dynamic_members[0]
                member_types = member.type_()
                member_types = member_types if isinstance(member_types, list) else [member_types]
                member_types = [t for t in member_types if t is not None]
                key_type = self._map_type(member_types[0]) if member_types else ir.PointerType(ir.IntType(8))
                value_type = self._map_type(member_types[-1]) if len(member_types) > 1 else ir.PointerType(ir.IntType(8))
                self.type_aliases[name] = self.structs['Dict']
                self._type_alias_dict_item_types[name] = (key_type, value_type)
                return None

            field_names = []
            alias_field_types = []
            alias_field_unsigned = []
            alias_field_type_names = []
            for field_name, field_type, field_unsigned, field_type_name in self._shape_fixed_field_layout(shape):
                field_names.append(field_name)
                alias_field_types.append(field_type)
                alias_field_unsigned.append(field_unsigned)
                alias_field_type_names.append(field_type_name)
            alias_struct = self.context.get_identified_type(name)
            if alias_struct.is_opaque:
                alias_struct.set_body(*alias_field_types)
            self.structs[name] = alias_struct
            self.struct_fields[name] = field_names
            self._struct_field_unsigned[name] = alias_field_unsigned
            self._struct_field_type_names[name] = alias_field_type_names
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

        struct_type = self.context.get_identified_type(name)
        self.structs[name] = struct_type
        field_names = []
        field_types = []
        field_unsigned = []
        field_type_names = []

        defaults = {}
        methods = []
        self._struct_type_build_stack.append(name)
        try:
            for member_ctx in ctx.structMember():
                # 字段
                field_ctx = member_ctx.structField()
                if field_ctx is not None:
                    fname = self._field_name_text(field_ctx)
                    ftype = self._map_type(field_ctx.type_())
                    field_names.append(fname)
                    field_types.append(ftype)
                    field_unsigned.append(self._type_ctx_is_unsigned(field_ctx.type_()))
                    field_type_names.append(self._type_ctx_name(field_ctx.type_()))
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
                                    base_type_names = self._struct_field_type_names.get(base_name, [])
                                    field_type_names.append(base_type_names[bf_idx] if bf_idx < len(base_type_names) else self._type_name_from_ir_type(base_struct.elements[bf_idx]))
                # 方法: methodName = (this: Type, ...) => body
                method_ctx = member_ctx.structMethod()
                if method_ctx is not None:
                    mname = self._field_name_text(method_ctx)
                    if name not in self.struct_methods:
                        self.struct_methods[name] = {}
                    self.struct_methods[name][mname] = f"{name}_{mname}"
                    methods.append((mname, method_ctx.functionLiteral(), method_ctx.functionSignature()))
        finally:
            self._struct_type_build_stack.pop()

        if struct_type.is_opaque:
            struct_type.set_body(*field_types)
        self.structs[name] = struct_type
        self.struct_fields[name] = field_names
        self._struct_field_unsigned[name] = field_unsigned
        self._struct_field_type_names[name] = field_type_names
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
        param_type_ctxs = []
        params = sig_ctx.paramList()
        if params is not None:
            for index, p in enumerate(params.param()):
                pname = p.VAR_IDENTIFIER().getText()
                ptype = self._map_type(p.type_())
                if self._param_type_uses_reference(ptype, pname, index):
                    ptype = ir.PointerType(ptype)
                else:
                    ptype = self._c_abi_param_type(ptype)
                param_types.append(ptype)
                param_names.append(pname)
                param_type_ctxs.append(p.type_())
        if func_name in self.module.globals:
            return self.module.globals[func_name]
        func = ir.Function(self.module, ir.FunctionType(ret_type, param_types), func_name)
        for i, pn in enumerate(param_names):
            func.args[i].name = pn
        self.func_param_names[func_name] = param_names
        self.func_param_type_ctxs[func_name] = param_type_ctxs
        return func

    def _gen_method_func(self, func_name: str, fn_lit_ctx, struct_name: str,
                         generic_context: tuple[dict[str, ir.Type], dict[str, bool], dict[str, str]] | None = None):
        """生成结构体方法对应的 LLVM 函数"""
        pushed_context = generic_context is not None
        if pushed_context:
            self._generic_type_map_stack.append(generic_context)
        try:
            ret_type = self._map_type(fn_lit_ctx.type_())
            self.func_return_unsigned[func_name] = self._type_ctx_is_unsigned(fn_lit_ctx.type_())
            ret_dict_types = self._dict_types_from_type_ctx(fn_lit_ctx.type_())
            if ret_dict_types is not None:
                self.func_return_dict_types[func_name] = ret_dict_types
            param_types = []
            param_names = []
            param_type_ctxs = []
            params = fn_lit_ctx.paramList()
            if params is not None:
                for index, p in enumerate(params.param()):
                    pname = p.VAR_IDENTIFIER().getText()
                    ptype = self._map_type(p.type_())
                    if self._param_type_uses_reference(ptype, pname, index):
                        ptype = ir.PointerType(ptype)
                    param_types.append(ptype)
                    param_names.append(pname)
                    param_type_ctxs.append(p.type_())

            func_type = ir.FunctionType(ret_type, param_types)
            func = ir.Function(self.module, func_type, func_name)
            for i, pn in enumerate(param_names):
                func.args[i].name = pn

            self.func_param_names[func_name] = param_names
            self.func_param_type_ctxs[func_name] = param_type_ctxs
            self.func_defaults[func_name] = {}
        finally:
            if pushed_context:
                self._generic_type_map_stack.pop()

        # 生成函数体
        body = fn_lit_ctx.block() or fn_lit_ctx.expression()
        if body is not None:
            entry = func.append_basic_block('entry')
            prev_unsigned = self._save_unsigned_state()
            prev_codegen_state = self._enter_function_codegen_state(ir.IRBuilder(entry), func)
            if pushed_context:
                self._generic_type_map_stack.append(generic_context)
            throw_exit = func.append_basic_block('throw_exit')
            self._function_throw_exit_stack.append(throw_exit)
            self._function_return_type_ctx_stack.append(fn_lit_ctx.type_())

            for i, pn in enumerate(param_names):
                alloca = self._bind_function_param(pn, param_types[i], func.args[i], this_ref=self._is_reference_param_type(param_types[i], pn, i))
                param_ctx = params.param()[i] if params is not None else None
                self._remember_type_name(pn, param_types[i], param_ctx.type_() if param_ctx is not None else None)
                if param_ctx is not None:
                    self._mark_unsigned(alloca, self._type_ctx_is_unsigned(param_ctx.type_()))
                    self._mark_list_elem_unsigned(alloca, self._type_ctx_is_unsigned(param_ctx.type_()))

            val = self._eval(body)
            self._finish_function_with_throw_exit(ret_type, val)
            self._function_return_type_ctx_stack.pop()
            if pushed_context:
                self._generic_type_map_stack.pop()

            self._restore_function_codegen_state(prev_codegen_state)
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
        param_type_ctxs = []
        if params is not None:
            for index, p in enumerate(params.param()):
                pname = p.VAR_IDENTIFIER().getText()
                ptype = self._map_type(p.type_())
                if self._param_type_uses_reference(ptype, pname, index):
                    ptype = ir.PointerType(ptype)
                param_types.append(ptype)
                param_names.append(pname)
                param_type_ctxs.append(p.type_())

        func_type = ir.FunctionType(ret_type, param_types)
        func = ir.Function(self.module, func_type, name)

        for i, pn in enumerate(param_names):
            func.args[i].name = pn

        # 记录参数名和默认值（供调用时具名参数重排和默认参数注入）
        self.func_param_names[name] = param_names
        self.func_param_type_ctxs[name] = param_type_ctxs
        if params is not None:
            defaults = {}
            for p in params.param():
                if p.expression() is not None:
                    defaults[p.VAR_IDENTIFIER().getText()] = p.expression()
            if defaults:
                self.func_defaults[name] = defaults

        # 生成函数体
        block = func.append_basic_block(name="entry")
        old_unsigned = self._save_unsigned_state()
        old_codegen_state = self._enter_function_codegen_state(ir.IRBuilder(block), func)
        throw_exit = func.append_basic_block('throw_exit')
        self._function_throw_exit_stack.append(throw_exit)
        self._function_return_type_ctx_stack.append(fn_lit_ctx.type_())

        if name == 'main':
            self._emit_decorator_inits()

        # 参数 alloca
        for i, pn in enumerate(param_names):
            alloca = self._bind_function_param(pn, param_types[i], func.args[i], this_ref=self._is_reference_param_type(param_types[i], pn, i))
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

        self._restore_function_codegen_state(old_codegen_state)
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
        """解析字符串插值: "Hello {{name + suffix}}!" → text / expr 片段。"""
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
        """生成字符串插值的 LLVM IR：按实际长度分配并逐段拼接。"""
        i8 = ir.IntType(8)
        i64 = ir.IntType(64)

        memcpy = self.module.get_global('llvm.memcpy.p0.p0.i64')
        strlen = self._get_or_define_strlen()

        segments: list[tuple[ir.Value, ir.Value]] = []
        for seg_type, seg_content in parts:
            if seg_type == "text" and seg_content:
                src = self._make_global_string(seg_content, prefix="_interp_seg")
                seg_len = ir.Constant(i64, len(bytearray(seg_content, 'utf-8')))
            elif seg_type == "expr" and self.builder:
                src_val = self._eval_interpolation_expr(seg_content.strip())
                if src_val is not None and isinstance(src_val.type, ir.PointerType) and src_val.type.pointee == i8:
                    src = src_val
                    seg_len = self.builder.call(strlen, [src], name="_interp_len")
                else:
                    continue
            else:
                continue
            segments.append((src, seg_len))

        total_len = ir.Constant(i64, 0)
        for _, seg_len in segments:
            total_len = self.builder.add(total_len, seg_len, name="_interp_total")
        alloc_len = self.builder.add(total_len, ir.Constant(i64, 1), name="_interp_alloc_len")
        buf_base = self.builder.call(self._arena_alloc, [alloc_len, ir.Constant(i64, 1)], name="_interp_buf")

        pos = ir.Constant(i64, 0)
        for src, seg_len in segments:
            dst_ptr = self.builder.gep(buf_base, [pos], inbounds=True)
            self.builder.call(memcpy, [
                dst_ptr, src,
                seg_len,
                ir.Constant(ir.IntType(1), 0)
            ])
            pos = self.builder.add(pos, seg_len, name="_interp_pos")

        null_ptr = self.builder.gep(buf_base, [pos], inbounds=True)
        self.builder.store(ir.Constant(i8, 0), null_ptr)
        return buf_base

    def _eval_interpolation_expr(self, expr_text: str) -> ir.Value | None:
        """按 EzLang 表达式语法生成字符串插值内部表达式。"""
        if not expr_text:
            return None
        stream = CommonTokenStream(EzLangLexer(InputStream(expr_text)))
        parser = EzLangParser(stream)
        parser.removeErrorListeners()
        expr = parser.expression()
        if parser.getNumberOfSyntaxErrors() > 0 or stream.LA(1) != Token.EOF:
            return None
        return self._eval(expr)

    def _get_or_define_strlen(self) -> ir.Function:
        """定义内部 strlen，避免依赖平台 size_t ABI。"""
        existing = self.module.globals.get('__ez_strlen')
        if isinstance(existing, ir.Function):
            return existing

        i8 = ir.IntType(8)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        func = ir.Function(self.module, ir.FunctionType(i64, [i8_ptr]), '__ez_strlen')
        text = func.args[0]
        entry = func.append_basic_block('entry')
        loop = func.append_basic_block('loop')
        done = func.append_basic_block('done')
        builder = ir.IRBuilder(entry)
        builder.branch(loop)

        builder.position_at_start(loop)
        index = builder.phi(i64, name='_strlen_i')
        index.add_incoming(ir.Constant(i64, 0), entry)
        ch_ptr = builder.gep(text, [index], inbounds=True)
        ch = builder.load(ch_ptr, name='_strlen_ch')
        is_end = builder.icmp_unsigned('==', ch, ir.Constant(i8, 0), name='_strlen_end')
        next_index = builder.add(index, ir.Constant(i64, 1), name='_strlen_next')
        index.add_incoming(next_index, loop)
        builder.cbranch(is_end, done, loop)

        builder.position_at_start(done)
        builder.ret(index)
        return func

    def _fmt_struct_serializable(self, typ: ir.Type, seen: set[str] | None = None) -> bool:
        """JSON/MessagePack 只递归支持普通用户结构体，跳过运行时 ABI 结构体。"""
        if not isinstance(typ, ir.IdentifiedStructType):
            return False
        struct_name = typ.name
        if struct_name in {'Blob', 'Dict', 'Error', 'Date'}:
            return False
        fields = self.struct_fields.get(struct_name, [])
        if len(fields) != len(typ.elements):
            return False
        seen = set(seen or set())
        if struct_name in seen:
            return False
        seen.add(struct_name)
        return all(
            self._fmt_field_serializable(field_type, struct_name, index, seen)
            for index, field_type in enumerate(typ.elements)
        )

    def _fmt_field_serializable(self, field_type: ir.Type, struct_name: str, index: int, seen: set[str]) -> bool:
        source_name = self._fmt_source_type_name(field_type, struct_name, index)
        return self._fmt_value_serializable(field_type, source_name, seen)

    def _fmt_value_serializable(self, value_type: ir.Type, source_name: str, seen: set[str]) -> bool:
        if source_name in {'Bool', 'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str'}:
            return True
        if self._is_optional_type(value_type):
            return self._fmt_optional_serializable(value_type, source_name, seen)
        if self._is_list_type(value_type):
            return self._fmt_list_serializable(value_type, source_name, seen)
        if self._is_dict_type(value_type):
            return self._fmt_dict_serializable(value_type, source_name, seen)
        if self._is_union_type(value_type):
            return self._fmt_union_serializable(value_type, source_name, seen)
        return self._fmt_struct_serializable(value_type, set(seen))

    def _fmt_list_serializable(self, list_type: ir.Type, source_name: str, seen: set[str]) -> bool:
        if not self._is_list_type(list_type):
            return False
        elem_type = list_type.elements[0].pointee.pointee
        elem_source = self._fmt_list_elem_source_name(source_name, elem_type)
        return self._fmt_value_serializable(elem_type, elem_source, set(seen))

    def _fmt_optional_serializable(self, opt_type: ir.Type, source_name: str, seen: set[str]) -> bool:
        if not self._is_optional_type(opt_type):
            return False
        inner_type = opt_type.elements[1]
        inner_source = self._fmt_optional_inner_source_name(source_name, inner_type)
        return self._fmt_value_serializable(inner_type, inner_source, set(seen))

    def _is_dict_type(self, typ: ir.Type) -> bool:
        return typ == self.structs.get('Dict')

    @staticmethod
    def _fmt_split_top_level(text: str, delimiter: str) -> list[str]:
        parts: list[str] = []
        start = 0
        angle_depth = 0
        paren_depth = 0
        bracket_depth = 0
        for index, ch in enumerate(text):
            if ch == '<':
                angle_depth += 1
            elif ch == '>' and angle_depth > 0:
                angle_depth -= 1
            elif ch == '(':
                paren_depth += 1
            elif ch == ')' and paren_depth > 0:
                paren_depth -= 1
            elif ch == '[':
                bracket_depth += 1
            elif ch == ']' and bracket_depth > 0:
                bracket_depth -= 1
            elif ch == delimiter and angle_depth == 0 and paren_depth == 0 and bracket_depth == 0:
                parts.append(text[start:index].strip())
                start = index + 1
        parts.append(text[start:].strip())
        return parts

    def _fmt_union_parts(self, source_name: str) -> list[str] | None:
        name = (source_name or '').strip()
        if not name:
            return None
        parts = self._fmt_split_top_level(name, '|')
        if len(parts) < 2 or any(not part for part in parts):
            return None
        return parts

    def _fmt_union_variant_types_from_source_name(self, source_name: str) -> tuple[list[str], list[ir.Type]] | None:
        parts = self._fmt_union_parts(source_name)
        if parts is None:
            return None
        return parts, [self._fmt_type_from_source_name(part) for part in parts]

    def _fmt_union_variant_packable(self, union_type: ir.Type, variant_type: ir.Type) -> bool:
        if not self._is_union_type(union_type):
            return False
        payload_type = union_type.elements[1]
        if payload_type == variant_type:
            return True
        if isinstance(payload_type, ir.IntType) and isinstance(variant_type, ir.IntType):
            return True
        if isinstance(payload_type, ir.PointerType) and isinstance(variant_type, (ir.IntType, ir.PointerType)):
            return True
        if isinstance(payload_type, ir.IntType) and isinstance(variant_type, ir.PointerType):
            return True
        if isinstance(payload_type, (ir.FloatType, ir.DoubleType)) and isinstance(variant_type, (ir.FloatType, ir.DoubleType)):
            return True
        if self._type_width(variant_type) <= self._type_width(payload_type):
            return True
        return False

    def _fmt_union_serializable(self, union_type: ir.Type, source_name: str, seen: set[str]) -> bool:
        if not self._is_union_type(union_type):
            return False
        variants = self._fmt_union_variant_types_from_source_name(source_name)
        if variants is None:
            return False
        variant_sources, variant_types = variants
        return all(
            self._fmt_union_variant_packable(union_type, variant_type)
            and self._fmt_value_serializable(variant_type, variant_source, set(seen))
            for variant_source, variant_type in zip(variant_sources, variant_types)
        )

    def _fmt_dict_parts(self, source_name: str) -> tuple[str, str] | None:
        name = (source_name or '').strip()
        if not name.startswith('Dict<') or not name.endswith('>'):
            return None
        parts = self._fmt_split_top_level(name[5:-1], ',')
        if len(parts) != 2:
            return None
        return parts[0], parts[1]

    def _fmt_dict_value_source_name(self, dict_source_name: str, value_type: ir.Type) -> str:
        parts = self._fmt_dict_parts(dict_source_name)
        if parts is not None:
            return parts[1]
        return self._type_name_from_ir_type(value_type)

    def _fmt_dict_key_source_name(self, dict_source_name: str, key_type: ir.Type) -> str:
        parts = self._fmt_dict_parts(dict_source_name)
        if parts is not None:
            return parts[0]
        return self._type_name_from_ir_type(key_type)

    def _fmt_dict_key_serializable(self, key_type: ir.Type, source_name: str) -> bool:
        """Dict 键只承诺语言字典已有稳定值比较语义的类型。"""
        return source_name in {'Bool', 'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str'}

    def _fmt_dict_serializable(self, dict_type: ir.Type, source_name: str, seen: set[str]) -> bool:
        if not self._is_dict_type(dict_type):
            return False
        parts = self._fmt_dict_parts(source_name)
        if parts is None:
            return False
        key_type, value_type = self._fmt_dict_item_types_from_source_name(source_name)
        return (
            self._fmt_dict_key_serializable(key_type, parts[0])
            and self._fmt_value_serializable(value_type, parts[1], set(seen))
        )

    def _fmt_dict_has_string_key(self, source_name: str) -> bool:
        parts = self._fmt_dict_parts(source_name)
        return parts is not None and parts[0] == 'Str'

    def _fmt_dict_item_types_from_source_name(self, source_name: str) -> tuple[ir.Type, ir.Type]:
        parts = self._fmt_dict_parts(source_name)
        if parts is None:
            return ir.PointerType(ir.IntType(8)), ir.PointerType(ir.IntType(8))
        key_type = self._fmt_type_from_source_name(parts[0])
        value_type = self._fmt_type_from_source_name(parts[1])
        return key_type, value_type

    def _fmt_type_from_source_name(self, source_name: str) -> ir.Type:
        name = (source_name or '').strip()
        if name == 'Bool':
            return ir.IntType(1)
        if name in {'I8', 'U8'}:
            return ir.IntType(8)
        if name in {'I32', 'U32'}:
            return ir.IntType(32)
        if name in {'I64', 'U64'}:
            return ir.IntType(64)
        if name == 'F32':
            return ir.FloatType()
        if name == 'F64':
            return ir.DoubleType()
        if name == 'Str':
            return ir.PointerType(ir.IntType(8))
        union_parts = self._fmt_union_parts(name)
        if union_parts is not None:
            variant_types = [self._fmt_type_from_source_name(part) for part in union_parts]
            max_type = max(variant_types, key=lambda t: self._type_width(t))
            return ir.LiteralStructType([ir.IntType(32), max_type])
        if name.endswith('?'):
            inner = self._fmt_type_from_source_name(name[:-1])
            return ir.LiteralStructType([ir.IntType(1), inner])
        if name.endswith('[]'):
            inner = self._fmt_type_from_source_name(name[:-2])
            return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])
        list_match = re.fullmatch(r'List<(.+)>', name)
        if list_match:
            inner = self._fmt_type_from_source_name(list_match.group(1).strip())
            return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])
        if name.startswith('Dict<'):
            return self.structs['Dict']
        if name in self.structs:
            return self.structs[name]
        return ir.IntType(32)

    def _fmt_list_elem_source_name(self, list_source_name: str, elem_type: ir.Type) -> str:
        if list_source_name.endswith('[]'):
            return list_source_name[:-2]
        match = re.fullmatch(r'List<(.+)>', list_source_name)
        if match:
            return match.group(1)
        return self._type_name_from_ir_type(elem_type)

    def _fmt_optional_inner_source_name(self, opt_source_name: str, inner_type: ir.Type) -> str:
        if opt_source_name.endswith('?'):
            return opt_source_name[:-1]
        return self._type_name_from_ir_type(inner_type)

    def _fmt_list_function_suffix(self, list_type: ir.Type, source_name: str) -> str:
        return self._type_suffix_from_name(source_name if source_name and source_name != 'unknown' else self._type_name(list_type))

    def _fmt_optional_function_suffix(self, opt_type: ir.Type, source_name: str) -> str:
        fallback = self._type_name_from_ir_type(opt_type)
        return self._type_suffix_from_name(source_name if source_name and source_name != 'unknown' else fallback)

    def _fmt_dict_function_suffix(self, dict_type: ir.Type, source_name: str) -> str:
        return self._type_suffix_from_name(source_name if source_name and source_name != 'unknown' else self._type_name(dict_type))

    def _fmt_union_function_suffix(self, union_type: ir.Type, source_name: str) -> str:
        fallback = self._type_name_from_ir_type(union_type)
        return self._type_suffix_from_name(source_name if source_name and source_name != 'unknown' else fallback)

    def _fmt_union_value_for_variant(self, union_value: ir.Value, union_type: ir.Type, variant_type: ir.Type) -> ir.Value:
        payload = self.builder.extract_value(union_value, 1, name='_fmt_union_payload')
        if payload.type == variant_type:
            return payload
        if isinstance(payload.type, ir.IntType) and isinstance(variant_type, ir.IntType):
            return self._coerce_integer_value(payload, variant_type)
        if isinstance(payload.type, ir.IntType) and isinstance(variant_type, ir.PointerType):
            return self.builder.inttoptr(payload, variant_type)
        if isinstance(payload.type, ir.PointerType) and isinstance(variant_type, ir.IntType):
            return self.builder.ptrtoint(payload, variant_type)
        if isinstance(payload.type, ir.PointerType) and isinstance(variant_type, ir.PointerType):
            return self.builder.bitcast(payload, variant_type)
        if isinstance(payload.type, ir.FloatType) and isinstance(variant_type, ir.DoubleType):
            return self.builder.fpext(payload, variant_type)
        if isinstance(payload.type, ir.DoubleType) and isinstance(variant_type, ir.FloatType):
            return self.builder.fptrunc(payload, variant_type)
        if self._type_width(variant_type) <= self._type_width(payload.type):
            payload_ptr = self.builder.alloca(payload.type, name='_fmt_union_payload_ptr')
            self.builder.store(payload, payload_ptr)
            variant_ptr = self.builder.bitcast(payload_ptr, ir.PointerType(variant_type), name='_fmt_union_variant_ptr')
            return self.builder.load(variant_ptr, name='_fmt_union_variant')
        return payload

    def _fmt_arg_for_wrapper(self, value: ir.Value, wrapper_arg_type: ir.Type) -> ir.Value:
        arg = value
        if arg.type == wrapper_arg_type:
            return arg
        if isinstance(wrapper_arg_type, ir.PointerType) and arg.type == wrapper_arg_type.pointee:
            ptr = self._arena_allocate(arg.type, name='_fmt_wrapper_arg_ptr')
            self.builder.store(arg, ptr)
            return ptr
        if isinstance(arg.type, ir.PointerType) and arg.type.pointee == wrapper_arg_type:
            return self.builder.load(arg, name='_fmt_wrapper_arg_value')
        return self._coerce_value(arg, wrapper_arg_type)

    def _fmt_join_json_key_value_entry(self, key_text: ir.Value, value_text: ir.Value, name_prefix: str) -> ir.Value:
        strlen = self._get_or_define_strlen()
        segments: list[tuple[ir.Value, ir.Value]] = []
        self._append_json_literal_segment(segments, '{"key":')
        segments.append((key_text, self.builder.call(strlen, [key_text], name=f'{name_prefix}_key_len')))
        self._append_json_literal_segment(segments, ',"value":')
        segments.append((value_text, self.builder.call(strlen, [value_text], name=f'{name_prefix}_value_len')))
        self._append_json_literal_segment(segments, '}')
        return self._join_c_string_segments(segments, name_prefix=name_prefix)

    def _fmt_generate_json_stringify_wrapper(self, wrapper_name: str, value_type: ir.Type, source_name: str) -> ir.Function | None:
        if self._is_optional_type(value_type) and self._fmt_optional_serializable(value_type, source_name, set()):
            return self._gen_json_stringify_optional_function(wrapper_name, value_type, source_name)
        if self._is_list_type(value_type) and self._fmt_list_serializable(value_type, source_name, set()):
            return self._gen_json_stringify_list_function(wrapper_name, value_type, source_name)
        if self._is_dict_type(value_type) and self._fmt_dict_serializable(value_type, source_name, set()):
            return self._gen_json_stringify_dict_function(wrapper_name, value_type, source_name)
        if self._is_union_type(value_type) and self._fmt_union_serializable(value_type, source_name, set()):
            return self._gen_json_stringify_union_function(wrapper_name, value_type, source_name)
        if isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type):
            return self._gen_json_stringify_struct_function(wrapper_name, value_type)
        return None

    def _fmt_generate_json_parse_wrapper(self, wrapper_name: str, value_type: ir.Type, source_name: str) -> ir.Function | None:
        if self._is_optional_type(value_type) and self._fmt_optional_serializable(value_type, source_name, set()):
            return self._gen_json_parse_optional_function(wrapper_name, value_type, source_name)
        if self._is_list_type(value_type) and self._fmt_list_serializable(value_type, source_name, set()):
            return self._gen_json_parse_list_function(wrapper_name, value_type, source_name)
        if self._is_dict_type(value_type) and self._fmt_dict_serializable(value_type, source_name, set()):
            return self._gen_json_parse_dict_function(wrapper_name, value_type, source_name)
        if self._is_union_type(value_type) and self._fmt_union_serializable(value_type, source_name, set()):
            return self._gen_json_parse_union_function(wrapper_name, value_type, source_name)
        if isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type):
            return self._gen_json_parse_struct_function(wrapper_name, value_type)
        return None

    def _fmt_generate_msgpack_encode_wrapper(self, wrapper_name: str, value_type: ir.Type, source_name: str) -> ir.Function | None:
        if self._is_optional_type(value_type) and self._fmt_optional_serializable(value_type, source_name, set()):
            return self._gen_msgpack_encode_optional_function(wrapper_name, value_type, source_name)
        if self._is_list_type(value_type) and self._fmt_list_serializable(value_type, source_name, set()):
            return self._gen_msgpack_encode_list_function(wrapper_name, value_type, source_name)
        if self._is_dict_type(value_type) and self._fmt_dict_serializable(value_type, source_name, set()):
            return self._gen_msgpack_encode_dict_function(wrapper_name, value_type, source_name)
        if self._is_union_type(value_type) and self._fmt_union_serializable(value_type, source_name, set()):
            return self._gen_msgpack_encode_union_function(wrapper_name, value_type, source_name)
        if isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type):
            return self._gen_msgpack_encode_struct_function(wrapper_name, value_type)
        return None

    def _fmt_generate_msgpack_decode_wrapper(self, wrapper_name: str, value_type: ir.Type, source_name: str) -> ir.Function | None:
        if self._is_optional_type(value_type) and self._fmt_optional_serializable(value_type, source_name, set()):
            return self._gen_msgpack_decode_optional_function(wrapper_name, value_type, source_name)
        if self._is_list_type(value_type) and self._fmt_list_serializable(value_type, source_name, set()):
            return self._gen_msgpack_decode_list_function(wrapper_name, value_type, source_name)
        if self._is_dict_type(value_type) and self._fmt_dict_serializable(value_type, source_name, set()):
            return self._gen_msgpack_decode_dict_function(wrapper_name, value_type, source_name)
        if self._is_union_type(value_type) and self._fmt_union_serializable(value_type, source_name, set()):
            return self._gen_msgpack_decode_union_function(wrapper_name, value_type, source_name)
        if isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type):
            return self._gen_msgpack_decode_struct_function(wrapper_name, value_type)
        return None

    def _fmt_value_from_raw_ptr(self, raw: ir.Value, value_type: ir.Type, wrapper_arg_type: ir.Type) -> ir.Value:
        if isinstance(value_type, ir.PointerType) and value_type == wrapper_arg_type:
            return raw
        value_ptr = self.builder.bitcast(raw, ir.PointerType(value_type), name='_fmt_raw_value_ptr')
        if value_ptr.type == wrapper_arg_type:
            return value_ptr
        value = self.builder.load(value_ptr, name='_fmt_raw_value')
        if value.type != wrapper_arg_type:
            return self._coerce_value(value, wrapper_arg_type)
        return value

    def _fmt_source_type_name(self, field_type: ir.Type, struct_name: str, index: int) -> str:
        field_type_names = self._struct_field_type_names.get(struct_name, [])
        if index < len(field_type_names):
            return field_type_names[index]
        field_unsigned = self._struct_field_unsigned.get(struct_name, [])
        return self._type_name_from_ir_type_with_unsigned(
            field_type,
            index < len(field_unsigned) and field_unsigned[index],
        )

    def _json_stringify_struct_supported(self, typ: ir.Type) -> bool:
        """当前编译期 JSON 结构体编码覆盖基础字段与嵌套用户结构体。"""
        return self._fmt_struct_serializable(typ)

    def _json_stringify_field_function_name(self, field_type: ir.Type, struct_name: str, index: int) -> str | None:
        source_name = self._fmt_source_type_name(field_type, struct_name, index)
        if source_name == 'Bool':
            return 'jsonStringify_I1'
        if source_name in {'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str'}:
            return f"jsonStringify_{source_name}"
        if self._is_optional_type(field_type) and self._fmt_optional_serializable(field_type, source_name, set()):
            return f"jsonStringify_{self._fmt_optional_function_suffix(field_type, source_name)}"
        if self._is_list_type(field_type) and self._fmt_list_serializable(field_type, source_name, set()):
            return f"jsonStringify_{self._fmt_list_function_suffix(field_type, source_name)}"
        if self._is_dict_type(field_type) and self._fmt_dict_serializable(field_type, source_name, set()):
            return f"jsonStringify_{self._fmt_dict_function_suffix(field_type, source_name)}"
        if self._is_union_type(field_type) and self._fmt_union_serializable(field_type, source_name, set()):
            return f"jsonStringify_{self._fmt_union_function_suffix(field_type, source_name)}"
        if self._fmt_struct_serializable(field_type):
            return f"jsonStringify_{field_type.name}"
        return None

    def _json_parse_struct_supported(self, typ: ir.Type) -> bool:
        """当前编译期 JSON 结构体解析覆盖基础字段与嵌套用户结构体。"""
        return self._fmt_struct_serializable(typ)

    def _json_parse_field_function_name(self, field_type: ir.Type, struct_name: str, index: int) -> str | None:
        source_name = self._fmt_source_type_name(field_type, struct_name, index)
        if source_name == 'Bool':
            return 'jsonParse_I1'
        if source_name in {'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str'}:
            return f"jsonParse_{source_name}"
        if self._is_optional_type(field_type) and self._fmt_optional_serializable(field_type, source_name, set()):
            return f"jsonParse_{self._fmt_optional_function_suffix(field_type, source_name)}"
        if self._is_list_type(field_type) and self._fmt_list_serializable(field_type, source_name, set()):
            return f"jsonParse_{self._fmt_list_function_suffix(field_type, source_name)}"
        if self._is_dict_type(field_type) and self._fmt_dict_serializable(field_type, source_name, set()):
            return f"jsonParse_{self._fmt_dict_function_suffix(field_type, source_name)}"
        if self._is_union_type(field_type) and self._fmt_union_serializable(field_type, source_name, set()):
            return f"jsonParse_{self._fmt_union_function_suffix(field_type, source_name)}"
        if self._fmt_struct_serializable(field_type):
            return f"jsonParse_{field_type.name}"
        return None

    def _json_stringify_function_type(self, func_name: str, arg_type: ir.Type) -> ir.FunctionType:
        if func_name == 'jsonStringify_I1':
            arg_type = ir.IntType(1)
        elif isinstance(arg_type, ir.IdentifiedStructType) or self._is_list_type(arg_type) or self._is_optional_type(arg_type) or self._is_dict_type(arg_type) or self._is_union_type(arg_type):
            arg_type = ir.PointerType(arg_type)
        return ir.FunctionType(ir.PointerType(ir.IntType(8)), [arg_type])

    def _json_parse_function_type(self, func_name: str, ret_type: ir.Type) -> ir.FunctionType:
        if func_name == 'jsonParse_I1':
            ret_type = ir.IntType(1)
        elif isinstance(ret_type, ir.IdentifiedStructType) or self._is_list_type(ret_type) or self._is_optional_type(ret_type) or self._is_dict_type(ret_type) or self._is_union_type(ret_type):
            ret_type = ir.PointerType(ret_type)
        return ir.FunctionType(ret_type, [ir.PointerType(ir.IntType(8))])

    def _json_value_stringify_wrapper(self, value_type: ir.Type, source_name: str) -> tuple[str, ir.FunctionType, ir.Function | None]:
        if source_name == 'Bool':
            wrapper_name = 'jsonStringify_I1'
        elif source_name in {'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str'}:
            wrapper_name = f'jsonStringify_{source_name}'
        elif self._is_optional_type(value_type) and self._fmt_optional_serializable(value_type, source_name, set()):
            wrapper_name = f'jsonStringify_{self._fmt_optional_function_suffix(value_type, source_name)}'
        elif self._is_list_type(value_type) and self._fmt_list_serializable(value_type, source_name, set()):
            wrapper_name = f'jsonStringify_{self._fmt_list_function_suffix(value_type, source_name)}'
        elif self._is_dict_type(value_type) and self._fmt_dict_serializable(value_type, source_name, set()):
            wrapper_name = f'jsonStringify_{self._fmt_dict_function_suffix(value_type, source_name)}'
        elif self._is_union_type(value_type) and self._fmt_union_serializable(value_type, source_name, set()):
            wrapper_name = f'jsonStringify_{self._fmt_union_function_suffix(value_type, source_name)}'
        elif isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type):
            wrapper_name = f'jsonStringify_{value_type.name}'
        else:
            wrapper_name = ''
        wrapper_type = self._json_stringify_function_type(wrapper_name, value_type)
        wrapper = self._fmt_generate_json_stringify_wrapper(wrapper_name, value_type, source_name)
        return wrapper_name, wrapper_type, wrapper

    def _json_value_parse_wrapper(self, value_type: ir.Type, source_name: str) -> tuple[str, ir.FunctionType, ir.Function | None]:
        if source_name == 'Bool':
            wrapper_name = 'jsonParse_I1'
        elif source_name in {'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str'}:
            wrapper_name = f'jsonParse_{source_name}'
        elif self._is_optional_type(value_type) and self._fmt_optional_serializable(value_type, source_name, set()):
            wrapper_name = f'jsonParse_{self._fmt_optional_function_suffix(value_type, source_name)}'
        elif self._is_list_type(value_type) and self._fmt_list_serializable(value_type, source_name, set()):
            wrapper_name = f'jsonParse_{self._fmt_list_function_suffix(value_type, source_name)}'
        elif self._is_dict_type(value_type) and self._fmt_dict_serializable(value_type, source_name, set()):
            wrapper_name = f'jsonParse_{self._fmt_dict_function_suffix(value_type, source_name)}'
        elif self._is_union_type(value_type) and self._fmt_union_serializable(value_type, source_name, set()):
            wrapper_name = f'jsonParse_{self._fmt_union_function_suffix(value_type, source_name)}'
        elif isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type):
            wrapper_name = f'jsonParse_{value_type.name}'
        else:
            wrapper_name = ''
        wrapper_type = self._json_parse_function_type(wrapper_name, value_type)
        wrapper = self._fmt_generate_json_parse_wrapper(wrapper_name, value_type, source_name)
        return wrapper_name, wrapper_type, wrapper

    def _json_parse_validator_for_value(self, wrapper_name: str, value_type: ir.Type) -> str | None:
        validator_name = self._json_parse_validator_name(wrapper_name)
        if validator_name is None and self._is_optional_type(value_type) and self._fmt_optional_serializable(value_type, '', set()):
            return '__ez_json_valid_value'
        if validator_name is None and self._is_list_type(value_type) and self._fmt_list_serializable(value_type, '', set()):
            return '__ez_json_valid_array'
        if validator_name is None and self._is_dict_type(value_type):
            return '__ez_json_valid_object'
        if validator_name is None and self._is_union_type(value_type):
            return '__ez_json_valid_object'
        if validator_name is None and isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type):
            return '__ez_json_valid_object'
        return validator_name

    def _fmt_parse_wrapper_may_throw(self, value_type: ir.Type) -> bool:
        return (
            self._is_optional_type(value_type)
            or self._is_list_type(value_type)
            or self._is_dict_type(value_type)
            or self._is_union_type(value_type)
            or (isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type))
        )

    def _gen_json_stringify_optional_function(self, func_name: str, opt_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(ir.IntType(8)), [ir.PointerType(opt_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i32 = ir.IntType(32)
        inner_type = opt_type.elements[1]
        inner_source = self._fmt_optional_inner_source_name(source_name, inner_type)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names

        entry = func.append_basic_block('entry')
        value_block = func.append_basic_block('json_optional_value')
        null_block = func.append_basic_block('json_optional_null')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}

        ok_ptr = self.builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        ok = self.builder.load(ok_ptr, name='_json_optional_ok')
        self.builder.cbranch(ok, value_block, null_block)

        self.builder.position_at_start(null_block)
        self.builder.ret(self._make_global_string('null', prefix='_json_null'))

        self.builder.position_at_start(value_block)
        value_ptr = self.builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
        wrapper_name, wrapper_type, wrapper = self._json_value_stringify_wrapper(inner_type, inner_source)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        value_arg = value_ptr if value_ptr.type == wrapper_type.args[0] else self.builder.load(value_ptr, name='_json_optional_value')
        if value_arg.type != wrapper_type.args[0]:
            value_arg = self._coerce_value(value_arg, wrapper_type.args[0])
        text = self.builder.call(wrapper, [value_arg], name='_json_optional_text')
        self.builder.ret(text)

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_json_parse_optional_function(self, func_name: str, opt_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(opt_type), [ir.PointerType(ir.IntType(8))]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i1 = ir.IntType(1)
        i8_ptr = ir.PointerType(ir.IntType(8))
        result_type = ir.PointerType(opt_type)
        inner_type = opt_type.elements[1]
        inner_source = self._fmt_optional_inner_source_name(source_name, inner_type)
        func.args[0].name = 's'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_unsigned = self._save_unsigned_state()

        entry = func.append_basic_block('entry')
        null_block = func.append_basic_block('json_optional_null')
        value_block = func.append_basic_block('json_optional_value')
        throw_exit = func.append_basic_block('throw_exit')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._function_throw_exit_stack.append(throw_exit)

        def require_json_ok(ok: ir.Value) -> None:
            fail_bb = self.builder.append_basic_block('json_optional_parse_invalid')
            cont_bb = self.builder.append_basic_block('json_optional_parse_valid')
            self.builder.cbranch(ok, cont_bb, fail_bb)
            self.builder.position_at_start(fail_bb)
            self._raise_error(4, 'json parse failed')
            self.builder.position_at_start(cont_bb)

        result = self._arena_allocate(opt_type, name='_json_optional_value_ptr')
        self.builder.store(self._zero_constant(opt_type), result)
        valid_value = self._get_or_declare_function('__ez_json_valid_value', ir.FunctionType(i1, [i8_ptr]))
        valid_ok = self.builder.call(valid_value, [func.args[0]], name='_json_optional_valid')
        require_json_ok(valid_ok)
        valid_null = self._get_or_declare_function('__ez_json_valid_null', ir.FunctionType(i1, [i8_ptr]))
        is_null = self.builder.call(valid_null, [func.args[0]], name='_json_optional_is_null')
        self.builder.cbranch(is_null, null_block, value_block)

        self.builder.position_at_start(null_block)
        self.builder.ret(result)

        self.builder.position_at_start(value_block)
        wrapper_name, wrapper_type, wrapper = self._json_value_parse_wrapper(inner_type, inner_source)
        validator_name = self._json_parse_validator_for_value(wrapper_name, inner_type)
        validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [i8_ptr]))
        value_ok = self.builder.call(validator, [func.args[0]], name='_json_optional_inner_ok')
        require_json_ok(value_ok)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        value = self.builder.call(wrapper, [func.args[0]], name='_json_optional_inner')
        if self._fmt_parse_wrapper_may_throw(inner_type):
            self._emit_throw_check_after_call()
        if self.builder is not None and not self.builder.block.is_terminated:
            if value.type != inner_type:
                value = self._coerce_value(value, inner_type)
            self.builder.store(self._optional_value(inner_type, True, value), result)
            self.builder.ret(result)

        popped_throw_exit = self._function_throw_exit_stack.pop()
        if not popped_throw_exit.is_terminated:
            self.builder.position_at_start(popped_throw_exit)
            self.builder.ret(ir.Constant(result_type, None))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_json_stringify_union_function(self, func_name: str, union_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(ir.IntType(8)), [ir.PointerType(union_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        variants = self._fmt_union_variant_types_from_source_name(source_name)
        if variants is None:
            return func
        variant_sources, variant_types = variants
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names

        entry = func.append_basic_block('entry')
        invalid_block = func.append_basic_block('json_union_invalid')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}

        tag_ptr = self.builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        tag = self.builder.load(tag_ptr, name='_json_union_tag')
        for index, (variant_source, variant_type) in enumerate(zip(variant_sources, variant_types)):
            is_tag = self.builder.icmp_signed('==', tag, ir.Constant(i32, index), name='_json_union_tag_match')
            match_block = func.append_basic_block(f'json_union_tag_{index}')
            next_block = invalid_block if index == len(variant_types) - 1 else func.append_basic_block(f'json_union_next_{index}')
            self.builder.cbranch(is_tag, match_block, next_block)

            self.builder.position_at_start(match_block)
            union_value = self.builder.load(func.args[0], name='_json_union_value')
            variant_value = self._fmt_union_value_for_variant(union_value, union_type, variant_type)
            wrapper_name, wrapper_type, wrapper = self._json_value_stringify_wrapper(variant_type, variant_source)
            if wrapper is None:
                wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
            variant_arg = self._fmt_arg_for_wrapper(variant_value, wrapper_type.args[0])
            value_text = self.builder.call(wrapper, [variant_arg], name='_json_union_value_text')
            tag_text = self.builder.call(
                self._get_or_declare_function('jsonStringify_I32', ir.FunctionType(i8_ptr, [i32])),
                [ir.Constant(i32, index)],
                name='_json_union_tag_text',
            )
            strlen = self._get_or_define_strlen()
            segments: list[tuple[ir.Value, ir.Value]] = []
            self._append_json_literal_segment(segments, '{"tag":')
            segments.append((tag_text, self.builder.call(strlen, [tag_text], name='_json_union_tag_len')))
            self._append_json_literal_segment(segments, ',"value":')
            segments.append((value_text, self.builder.call(strlen, [value_text], name='_json_union_value_len')))
            self._append_json_literal_segment(segments, '}')
            self.builder.ret(self._join_c_string_segments(segments, name_prefix='_json_union'))

            if next_block is not invalid_block:
                self.builder.position_at_start(next_block)

        self.builder.position_at_start(invalid_block)
        self.builder.ret(self._make_global_string('{"tag":-1,"value":null}', prefix='_json_union_invalid'))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_json_parse_union_function(self, func_name: str, union_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(union_type), [ir.PointerType(ir.IntType(8))]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i1 = ir.IntType(1)
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        result_type = ir.PointerType(union_type)
        variants = self._fmt_union_variant_types_from_source_name(source_name)
        if variants is None:
            return func
        variant_sources, variant_types = variants
        func.args[0].name = 's'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_unsigned = self._save_unsigned_state()

        entry = func.append_basic_block('entry')
        invalid_block = func.append_basic_block('json_union_invalid')
        throw_exit = func.append_basic_block('throw_exit')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._function_throw_exit_stack.append(throw_exit)

        def require_json_ok(ok: ir.Value) -> None:
            if self.builder is None or self.builder.block.is_terminated:
                return
            fail_bb = self.builder.append_basic_block('json_union_parse_invalid')
            cont_bb = self.builder.append_basic_block('json_union_parse_valid')
            self.builder.cbranch(ok, cont_bb, fail_bb)
            self.builder.position_at_start(fail_bb)
            self._raise_error(4, 'json parse failed')
            self.builder.position_at_start(cont_bb)

        result = self._arena_allocate(union_type, name='_json_union_value_ptr')
        self.builder.store(self._zero_constant(union_type), result)
        valid_object = self._get_or_declare_function('__ez_json_valid_object', ir.FunctionType(i1, [i8_ptr]))
        require_json_ok(self.builder.call(valid_object, [func.args[0]], name='_json_union_object_ok'))
        field_count_fn = self._get_or_declare_function('__ez_json_object_field_count', ir.FunctionType(i64, [i8_ptr]))
        field_count = self.builder.call(field_count_fn, [func.args[0]], name='_json_union_field_count')
        require_json_ok(self.builder.icmp_signed('==', field_count, ir.Constant(i64, 2), name='_json_union_field_count_ok'))
        field_fn = self._get_or_declare_function('__ez_json_object_field', ir.FunctionType(i8_ptr, [i8_ptr, i8_ptr]))
        null_str = ir.Constant(i8_ptr, None)
        tag_raw = self.builder.call(field_fn, [func.args[0], self._make_global_string('tag', prefix='_json_union_key')], name='_json_union_tag_raw')
        value_raw = self.builder.call(field_fn, [func.args[0], self._make_global_string('value', prefix='_json_union_key')], name='_json_union_value_raw')
        require_json_ok(self.builder.icmp_unsigned('!=', tag_raw, null_str, name='_json_union_tag_found'))
        require_json_ok(self.builder.icmp_unsigned('!=', value_raw, null_str, name='_json_union_value_found'))
        tag_validator = self._get_or_declare_function('__ez_json_valid_I32', ir.FunctionType(i1, [i8_ptr]))
        require_json_ok(self.builder.call(tag_validator, [tag_raw], name='_json_union_tag_ok'))
        tag_parser = self._get_or_declare_function('jsonParse_I32', ir.FunctionType(i32, [i8_ptr]))
        tag = self.builder.call(tag_parser, [tag_raw], name='_json_union_tag')

        for index, (variant_source, variant_type) in enumerate(zip(variant_sources, variant_types)):
            is_tag = self.builder.icmp_signed('==', tag, ir.Constant(i32, index), name='_json_union_tag_match')
            match_block = func.append_basic_block(f'json_union_parse_tag_{index}')
            next_block = invalid_block if index == len(variant_types) - 1 else func.append_basic_block(f'json_union_parse_next_{index}')
            self.builder.cbranch(is_tag, match_block, next_block)

            self.builder.position_at_start(match_block)
            wrapper_name, wrapper_type, wrapper = self._json_value_parse_wrapper(variant_type, variant_source)
            validator_name = self._json_parse_validator_for_value(wrapper_name, variant_type)
            validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [i8_ptr]))
            require_json_ok(self.builder.call(validator, [value_raw], name='_json_union_value_ok'))
            if wrapper is None:
                wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
            value = self.builder.call(wrapper, [value_raw], name='_json_union_variant_value')
            if self._fmt_parse_wrapper_may_throw(variant_type):
                self._emit_throw_check_after_call()
            if self.builder is not None and not self.builder.block.is_terminated:
                if value.type != variant_type:
                    value = self._coerce_value(value, variant_type)
                union_value = self._coerce_union_value(value, union_type, index)
                self.builder.store(union_value, result)
                self.builder.ret(result)

            if next_block is not invalid_block:
                self.builder.position_at_start(next_block)

        self.builder.position_at_start(invalid_block)
        self._raise_error(4, 'json parse failed')

        popped_throw_exit = self._function_throw_exit_stack.pop()
        if not popped_throw_exit.is_terminated:
            self.builder.position_at_start(popped_throw_exit)
            self.builder.ret(ir.Constant(result_type, None))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_json_stringify_list_function(self, func_name: str, list_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(ir.IntType(8)), [ir.PointerType(list_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i1 = ir.IntType(1)
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        i8_ptr_ptr = ir.PointerType(i8_ptr)
        elem_type = list_type.elements[0].pointee.pointee
        elem_source = self._fmt_list_elem_source_name(source_name, elem_type)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names

        entry = func.append_basic_block('entry')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}

        strlen = self._get_or_define_strlen()
        memcpy = self.module.get_global('llvm.memcpy.p0.p0.i64')
        length = self._list_length(func.args[0])
        table_bytes = self.builder.mul(length, ir.Constant(i64, 8), name='_json_list_table_bytes')
        has_items = self.builder.icmp_unsigned('>', length, ir.Constant(i64, 0), name='_json_list_has_items')
        table_alloc_bytes = self.builder.select(has_items, table_bytes, ir.Constant(i64, 8), name='_json_list_table_alloc_bytes')
        table_raw = self.builder.call(self._arena_alloc, [table_alloc_bytes, ir.Constant(i64, 8)], name='_json_list_table_raw')
        text_table = self.builder.bitcast(table_raw, i8_ptr_ptr, name='_json_list_texts')
        total_ptr = self.builder.alloca(i64, name='_json_list_total_ptr')
        self.builder.store(ir.Constant(i64, 2), total_ptr)
        index_ptr = self.builder.alloca(i64, name='_json_list_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)

        loop_cond = self.builder.append_basic_block('json_list_len_cond')
        loop_body = self.builder.append_basic_block('json_list_len_body')
        loop_done = self.builder.append_basic_block('json_list_len_done')
        self.builder.branch(loop_cond)
        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_json_list_i_val')
        more = self.builder.icmp_unsigned('<', index, length, name='_json_list_more')
        self.builder.cbranch(more, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        elem_ptr = self._list_element_ptr(func.args[0], index)
        wrapper_name, wrapper_type, wrapper = self._json_value_stringify_wrapper(elem_type, elem_source)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        elem_arg = elem_ptr if elem_ptr.type == wrapper_type.args[0] else self.builder.load(elem_ptr, name='_json_list_item')
        if elem_arg.type != wrapper_type.args[0]:
            elem_arg = self._coerce_value(elem_arg, wrapper_type.args[0])
        text = self.builder.call(wrapper, [elem_arg], name='_json_list_text')
        text_slot = self.builder.gep(text_table, [index], inbounds=True)
        self.builder.store(text, text_slot)
        text_len = self.builder.call(strlen, [text], name='_json_list_text_len')
        current_total = self.builder.load(total_ptr, name='_json_list_total')
        with_text = self.builder.add(current_total, text_len, name='_json_list_total_text')
        self.builder.store(with_text, total_ptr)
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        comma_count = self.builder.select(has_items, self.builder.sub(length, ir.Constant(i64, 1)), ir.Constant(i64, 0), name='_json_list_commas')
        total = self.builder.add(self.builder.load(total_ptr), comma_count, name='_json_list_total_with_commas')
        alloc_len = self.builder.add(total, ir.Constant(i64, 1), name='_json_list_alloc_len')
        result = self.builder.call(self._arena_alloc, [alloc_len, ir.Constant(i64, 1)], name='_json_list_buf')
        pos_ptr = self.builder.alloca(i64, name='_json_list_pos')
        self.builder.store(ir.Constant(i8, ord('[')), result)
        self.builder.store(ir.Constant(i64, 1), pos_ptr)
        self.builder.store(ir.Constant(i64, 0), index_ptr)

        copy_cond = self.builder.append_basic_block('json_list_copy_cond')
        copy_body = self.builder.append_basic_block('json_list_copy_body')
        copy_done = self.builder.append_basic_block('json_list_copy_done')
        self.builder.branch(copy_cond)
        self.builder.position_at_start(copy_cond)
        copy_index = self.builder.load(index_ptr, name='_json_list_copy_i')
        copy_more = self.builder.icmp_unsigned('<', copy_index, length, name='_json_list_copy_more')
        self.builder.cbranch(copy_more, copy_body, copy_done)

        self.builder.position_at_start(copy_body)
        non_first = self.builder.icmp_unsigned('>', copy_index, ir.Constant(i64, 0), name='_json_list_non_first')
        comma_bb = self.builder.append_basic_block('json_list_comma')
        item_bb = self.builder.append_basic_block('json_list_item')
        self.builder.cbranch(non_first, comma_bb, item_bb)
        self.builder.position_at_start(comma_bb)
        comma_pos = self.builder.load(pos_ptr, name='_json_list_comma_pos')
        comma_ptr = self.builder.gep(result, [comma_pos], inbounds=True)
        self.builder.store(ir.Constant(i8, ord(',')), comma_ptr)
        self.builder.store(self.builder.add(comma_pos, ir.Constant(i64, 1)), pos_ptr)
        self.builder.branch(item_bb)
        self.builder.position_at_start(item_bb)
        item_text = self.builder.load(self.builder.gep(text_table, [copy_index], inbounds=True), name='_json_list_item_text')
        item_len = self.builder.call(strlen, [item_text], name='_json_list_item_len')
        item_pos = self.builder.load(pos_ptr, name='_json_list_item_pos')
        dst = self.builder.gep(result, [item_pos], inbounds=True)
        self.builder.call(memcpy, [dst, item_text, item_len, ir.Constant(i1, 0)])
        self.builder.store(self.builder.add(item_pos, item_len), pos_ptr)
        self.builder.store(self.builder.add(copy_index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(copy_cond)

        self.builder.position_at_start(copy_done)
        end_pos = self.builder.load(pos_ptr, name='_json_list_end_pos')
        end_ptr = self.builder.gep(result, [end_pos], inbounds=True)
        self.builder.store(ir.Constant(i8, ord(']')), end_ptr)
        null_ptr = self.builder.gep(result, [self.builder.add(end_pos, ir.Constant(i64, 1))], inbounds=True)
        self.builder.store(ir.Constant(i8, 0), null_ptr)
        self.builder.ret(result)

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_json_parse_list_function(self, func_name: str, list_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(list_type), [ir.PointerType(ir.IntType(8))]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i1 = ir.IntType(1)
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        result_type = ir.PointerType(list_type)
        elem_type = list_type.elements[0].pointee.pointee
        elem_source = self._fmt_list_elem_source_name(source_name, elem_type)
        func.args[0].name = 's'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_unsigned = self._save_unsigned_state()

        entry = func.append_basic_block('entry')
        throw_exit = func.append_basic_block('throw_exit')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._function_throw_exit_stack.append(throw_exit)

        def require_json_ok(ok: ir.Value) -> None:
            fail_bb = self.builder.append_basic_block('json_list_parse_invalid')
            cont_bb = self.builder.append_basic_block('json_list_parse_valid')
            self.builder.cbranch(ok, cont_bb, fail_bb)
            self.builder.position_at_start(fail_bb)
            self._raise_error(4, 'json parse failed')
            self.builder.position_at_start(cont_bb)

        valid_array = self._get_or_declare_function('__ez_json_valid_array', ir.FunctionType(i1, [i8_ptr]))
        array_ok = self.builder.call(valid_array, [func.args[0]], name='_json_list_ok')
        require_json_ok(array_ok)
        length_fn = self._get_or_declare_function('__ez_json_array_length', ir.FunctionType(i64, [i8_ptr]))
        length = self.builder.call(length_fn, [func.args[0]], name='_json_list_len')
        len_ok = self.builder.icmp_signed('>=', length, ir.Constant(i64, 0), name='_json_list_len_ok')
        require_json_ok(len_ok)
        result = self._list_new(elem_type, length)
        self._mark_list_elem_unsigned(result, elem_source in {'U8', 'U32', 'U64'})
        item_fn = self._get_or_declare_function('__ez_json_array_item', ir.FunctionType(i8_ptr, [i8_ptr, i64]))
        null_str = ir.Constant(i8_ptr, None)
        index_ptr = self.builder.alloca(i64, name='_json_list_parse_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        loop_cond = self.builder.append_basic_block('json_list_parse_cond')
        loop_body = self.builder.append_basic_block('json_list_parse_body')
        loop_done = self.builder.append_basic_block('json_list_parse_done')
        self.builder.branch(loop_cond)
        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_json_list_parse_i_val')
        more = self.builder.icmp_unsigned('<', index, length, name='_json_list_parse_more')
        self.builder.cbranch(more, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        raw = self.builder.call(item_fn, [func.args[0], index], name='_json_list_raw')
        found = self.builder.icmp_unsigned('!=', raw, null_str, name='_json_list_item_found')
        require_json_ok(found)
        wrapper_name, wrapper_type, wrapper = self._json_value_parse_wrapper(elem_type, elem_source)
        validator_name = self._json_parse_validator_for_value(wrapper_name, elem_type)
        validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [i8_ptr]))
        value_ok = self.builder.call(validator, [raw], name='_json_list_item_ok')
        require_json_ok(value_ok)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        value = self.builder.call(wrapper, [raw], name='_json_list_item_value')
        if self._fmt_parse_wrapper_may_throw(elem_type):
            self._emit_throw_check_after_call()
        if self.builder is not None and not self.builder.block.is_terminated:
            if value.type != elem_type:
                value = self._coerce_value(value, elem_type)
            self.builder.store(value, self._list_element_ptr(result, index))
            self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
            self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        self.builder.ret(result)
        popped_throw_exit = self._function_throw_exit_stack.pop()
        if not popped_throw_exit.is_terminated:
            self.builder.position_at_start(popped_throw_exit)
            self.builder.ret(ir.Constant(result_type, None))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_json_stringify_dict_function(self, func_name: str, dict_type: ir.IdentifiedStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(ir.IntType(8)), [ir.PointerType(dict_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i1 = ir.IntType(1)
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        i8_ptr_ptr = ir.PointerType(i8_ptr)
        key_type, value_type = self._fmt_dict_item_types_from_source_name(source_name)
        key_source = self._fmt_dict_key_source_name(source_name, key_type)
        value_source = self._fmt_dict_value_source_name(source_name, value_type)
        string_key = self._fmt_dict_has_string_key(source_name)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names

        entry = func.append_basic_block('entry')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}

        strlen = self._get_or_define_strlen()
        memcpy = self.module.get_global('llvm.memcpy.p0.p0.i64')
        count32 = self._dict_count(func.args[0])
        count = self.builder.zext(count32, i64, name='_json_dict_count')
        key_bytes = self.builder.mul(count, ir.Constant(i64, 8), name='_json_dict_key_bytes')
        has_items = self.builder.icmp_unsigned('>', count, ir.Constant(i64, 0), name='_json_dict_has_items')
        table_bytes = self.builder.select(has_items, key_bytes, ir.Constant(i64, 8), name='_json_dict_table_bytes')
        keys_raw = self.builder.call(self._arena_alloc, [table_bytes, ir.Constant(i64, 8)], name='_json_dict_keys_raw')
        values_raw = self.builder.call(self._arena_alloc, [table_bytes, ir.Constant(i64, 8)], name='_json_dict_values_raw')
        key_texts = self.builder.bitcast(keys_raw, i8_ptr_ptr, name='_json_dict_keys')
        value_texts = self.builder.bitcast(values_raw, i8_ptr_ptr, name='_json_dict_values')
        total_ptr = self.builder.alloca(i64, name='_json_dict_total_ptr')
        self.builder.store(ir.Constant(i64, 2), total_ptr)
        index_ptr = self.builder.alloca(i32, name='_json_dict_i')
        self.builder.store(ir.Constant(i32, 0), index_ptr)

        loop_cond = self.builder.append_basic_block('json_dict_len_cond')
        loop_body = self.builder.append_basic_block('json_dict_len_body')
        loop_done = self.builder.append_basic_block('json_dict_len_done')
        self.builder.branch(loop_cond)
        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_json_dict_i_val')
        more = self.builder.icmp_unsigned('<', index, count32, name='_json_dict_more')
        self.builder.cbranch(more, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        raw_key = self.builder.load(self._dict_key_slot_ptr(func.args[0], index), name='_json_dict_key_raw')
        key_value = self._dict_from_i8_ptr(raw_key, key_type)
        key_wrapper_name, key_wrapper_type, key_wrapper = self._json_value_stringify_wrapper(key_type, key_source)
        if key_wrapper is None:
            key_wrapper = self._get_or_declare_function(key_wrapper_name, key_wrapper_type)
        key_arg = self._fmt_arg_for_wrapper(key_value, key_wrapper_type.args[0])
        key_text = self.builder.call(key_wrapper, [key_arg], name='_json_dict_key_text')
        raw_value = self.builder.load(self._dict_value_slot_ptr(func.args[0], index), name='_json_dict_value_raw')
        wrapper_name, wrapper_type, wrapper = self._json_value_stringify_wrapper(value_type, value_source)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        value_arg = self._fmt_value_from_raw_ptr(raw_value, value_type, wrapper_type.args[0])
        raw_value_text = self.builder.call(wrapper, [value_arg], name='_json_dict_raw_value_text')
        value_text = raw_value_text
        if not string_key:
            value_text = self._fmt_join_json_key_value_entry(key_text, raw_value_text, '_json_dict_entry')
        index64 = self.builder.zext(index, i64, name='_json_dict_i64')
        self.builder.store(key_text, self.builder.gep(key_texts, [index64], inbounds=True))
        self.builder.store(value_text, self.builder.gep(value_texts, [index64], inbounds=True))
        key_len = self.builder.call(strlen, [key_text], name='_json_dict_key_len')
        value_len = self.builder.call(strlen, [value_text], name='_json_dict_value_len')
        current_total = self.builder.load(total_ptr, name='_json_dict_total')
        object_entry_len = self.builder.add(self.builder.add(key_len, value_len), ir.Constant(i64, 1), name='_json_dict_object_entry_len')
        entry_len = value_len if not string_key else object_entry_len
        self.builder.store(self.builder.add(current_total, entry_len), total_ptr)
        self.builder.store(self.builder.add(index, ir.Constant(i32, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        comma_count = self.builder.select(has_items, self.builder.sub(count, ir.Constant(i64, 1)), ir.Constant(i64, 0), name='_json_dict_commas')
        total = self.builder.add(self.builder.load(total_ptr), comma_count, name='_json_dict_total_with_commas')
        result = self.builder.call(self._arena_alloc, [self.builder.add(total, ir.Constant(i64, 1)), ir.Constant(i64, 1)], name='_json_dict_buf')
        pos_ptr = self.builder.alloca(i64, name='_json_dict_pos')
        start_ch = ord('{') if string_key else ord('[')
        self.builder.store(ir.Constant(i8, start_ch), result)
        self.builder.store(ir.Constant(i64, 1), pos_ptr)
        self.builder.store(ir.Constant(i32, 0), index_ptr)

        copy_cond = self.builder.append_basic_block('json_dict_copy_cond')
        copy_body = self.builder.append_basic_block('json_dict_copy_body')
        copy_done = self.builder.append_basic_block('json_dict_copy_done')
        self.builder.branch(copy_cond)
        self.builder.position_at_start(copy_cond)
        copy_index = self.builder.load(index_ptr, name='_json_dict_copy_i')
        copy_more = self.builder.icmp_unsigned('<', copy_index, count32, name='_json_dict_copy_more')
        self.builder.cbranch(copy_more, copy_body, copy_done)

        self.builder.position_at_start(copy_body)
        copy_index64 = self.builder.zext(copy_index, i64, name='_json_dict_copy_i64')
        non_first = self.builder.icmp_unsigned('>', copy_index, ir.Constant(i32, 0), name='_json_dict_non_first')
        comma_bb = self.builder.append_basic_block('json_dict_comma')
        item_bb = self.builder.append_basic_block('json_dict_item')
        self.builder.cbranch(non_first, comma_bb, item_bb)
        self.builder.position_at_start(comma_bb)
        comma_pos = self.builder.load(pos_ptr, name='_json_dict_comma_pos')
        self.builder.store(ir.Constant(i8, ord(',')), self.builder.gep(result, [comma_pos], inbounds=True))
        self.builder.store(self.builder.add(comma_pos, ir.Constant(i64, 1)), pos_ptr)
        self.builder.branch(item_bb)
        self.builder.position_at_start(item_bb)

        key_item = self.builder.load(self.builder.gep(key_texts, [copy_index64], inbounds=True), name='_json_dict_key_item')
        key_len_copy = self.builder.call(strlen, [key_item], name='_json_dict_key_item_len')
        key_pos = self.builder.load(pos_ptr, name='_json_dict_key_pos')
        value_item = self.builder.load(self.builder.gep(value_texts, [copy_index64], inbounds=True), name='_json_dict_value_item')
        value_len_copy = self.builder.call(strlen, [value_item], name='_json_dict_value_item_len')
        if string_key:
            self.builder.call(memcpy, [self.builder.gep(result, [key_pos], inbounds=True), key_item, key_len_copy, ir.Constant(i1, 0)])
            after_key = self.builder.add(key_pos, key_len_copy, name='_json_dict_after_key')
            self.builder.store(ir.Constant(i8, ord(':')), self.builder.gep(result, [after_key], inbounds=True))
            after_colon = self.builder.add(after_key, ir.Constant(i64, 1), name='_json_dict_after_colon')
            self.builder.call(memcpy, [self.builder.gep(result, [after_colon], inbounds=True), value_item, value_len_copy, ir.Constant(i1, 0)])
            self.builder.store(self.builder.add(after_colon, value_len_copy), pos_ptr)
        else:
            self.builder.call(memcpy, [self.builder.gep(result, [key_pos], inbounds=True), value_item, value_len_copy, ir.Constant(i1, 0)])
            self.builder.store(self.builder.add(key_pos, value_len_copy), pos_ptr)
        self.builder.store(self.builder.add(copy_index, ir.Constant(i32, 1)), index_ptr)
        self.builder.branch(copy_cond)

        self.builder.position_at_start(copy_done)
        end_pos = self.builder.load(pos_ptr, name='_json_dict_end_pos')
        end_ch = ord('}') if string_key else ord(']')
        self.builder.store(ir.Constant(i8, end_ch), self.builder.gep(result, [end_pos], inbounds=True))
        self.builder.store(ir.Constant(i8, 0), self.builder.gep(result, [self.builder.add(end_pos, ir.Constant(i64, 1))], inbounds=True))
        self.builder.ret(result)

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_json_parse_dict_function(self, func_name: str, dict_type: ir.IdentifiedStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(dict_type), [ir.PointerType(ir.IntType(8))]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i1 = ir.IntType(1)
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        result_type = ir.PointerType(dict_type)
        key_type, value_type = self._fmt_dict_item_types_from_source_name(source_name)
        key_source = self._fmt_dict_key_source_name(source_name, key_type)
        value_source = self._fmt_dict_value_source_name(source_name, value_type)
        string_key = self._fmt_dict_has_string_key(source_name)
        func.args[0].name = 's'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_unsigned = self._save_unsigned_state()

        entry = func.append_basic_block('entry')
        throw_exit = func.append_basic_block('throw_exit')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._function_throw_exit_stack.append(throw_exit)

        def require_json_ok(ok: ir.Value) -> None:
            fail_bb = self.builder.append_basic_block('json_dict_parse_invalid')
            cont_bb = self.builder.append_basic_block('json_dict_parse_valid')
            self.builder.cbranch(ok, cont_bb, fail_bb)
            self.builder.position_at_start(fail_bb)
            self._raise_error(4, 'json parse failed')
            self.builder.position_at_start(cont_bb)

        result = self._arena_allocate(dict_type, name='_json_dict_value')
        self.builder.store(self._zero_constant(dict_type), result)
        self._mark_dict_item_types(result, key_type, value_type)
        if string_key:
            valid_top = self._get_or_declare_function('__ez_json_valid_object', ir.FunctionType(i1, [i8_ptr]))
            top_ok = self.builder.call(valid_top, [func.args[0]], name='_json_dict_ok')
            require_json_ok(top_ok)
            length_fn = self._get_or_declare_function('__ez_json_object_field_count', ir.FunctionType(i64, [i8_ptr]))
            length = self.builder.call(length_fn, [func.args[0]], name='_json_dict_len')
            key_at_fn = self._get_or_declare_function('__ez_json_object_key_at', ir.FunctionType(i8_ptr, [i8_ptr, i64]))
            value_at_fn = self._get_or_declare_function('__ez_json_object_value_at', ir.FunctionType(i8_ptr, [i8_ptr, i64]))
            field_fn = None
            item_fn = None
        else:
            valid_top = self._get_or_declare_function('__ez_json_valid_array', ir.FunctionType(i1, [i8_ptr]))
            top_ok = self.builder.call(valid_top, [func.args[0]], name='_json_dict_entries_ok')
            require_json_ok(top_ok)
            length_fn = self._get_or_declare_function('__ez_json_array_length', ir.FunctionType(i64, [i8_ptr]))
            length = self.builder.call(length_fn, [func.args[0]], name='_json_dict_len')
            key_at_fn = None
            value_at_fn = None
            field_fn = self._get_or_declare_function('__ez_json_object_field', ir.FunctionType(i8_ptr, [i8_ptr, i8_ptr]))
            item_fn = self._get_or_declare_function('__ez_json_array_item', ir.FunctionType(i8_ptr, [i8_ptr, i64]))
        len_ok = self.builder.icmp_signed('>=', length, ir.Constant(i64, 0), name='_json_dict_len_ok')
        require_json_ok(len_ok)
        null_str = ir.Constant(i8_ptr, None)
        index_ptr = self.builder.alloca(i64, name='_json_dict_parse_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        loop_cond = self.builder.append_basic_block('json_dict_parse_cond')
        loop_body = self.builder.append_basic_block('json_dict_parse_body')
        loop_done = self.builder.append_basic_block('json_dict_parse_done')
        self.builder.branch(loop_cond)
        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_json_dict_parse_i_val')
        more = self.builder.icmp_unsigned('<', index, length, name='_json_dict_parse_more')
        self.builder.cbranch(more, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        if string_key:
            key = self.builder.call(key_at_fn, [func.args[0], index], name='_json_dict_key')
            raw = self.builder.call(value_at_fn, [func.args[0], index], name='_json_dict_raw')
        else:
            entry_raw = self.builder.call(item_fn, [func.args[0], index], name='_json_dict_entry_raw')
            entry_found = self.builder.icmp_unsigned('!=', entry_raw, null_str, name='_json_dict_entry_found')
            require_json_ok(entry_found)
            valid_entry_object = self._get_or_declare_function('__ez_json_valid_object', ir.FunctionType(i1, [i8_ptr]))
            entry_ok = self.builder.call(valid_entry_object, [entry_raw], name='_json_dict_entry_ok')
            require_json_ok(entry_ok)
            entry_field_count_fn = self._get_or_declare_function('__ez_json_object_field_count', ir.FunctionType(i64, [i8_ptr]))
            entry_field_count = self.builder.call(entry_field_count_fn, [entry_raw], name='_json_dict_entry_field_count')
            entry_field_count_ok = self.builder.icmp_signed('==', entry_field_count, ir.Constant(i64, 2), name='_json_dict_entry_field_count_ok')
            require_json_ok(entry_field_count_ok)
            key = self.builder.call(field_fn, [entry_raw, self._make_global_string('key', prefix='_json_dict_entry_key')], name='_json_dict_key_raw')
            raw = self.builder.call(field_fn, [entry_raw, self._make_global_string('value', prefix='_json_dict_entry_key')], name='_json_dict_raw')
            key_wrapper_name, _, _ = self._json_value_parse_wrapper(key_type, key_source)
            key_validator_name = self._json_parse_validator_for_value(key_wrapper_name, key_type)
            key_validator = self._get_or_declare_function(key_validator_name, ir.FunctionType(i1, [i8_ptr]))
            key_ok = self.builder.call(key_validator, [key], name='_json_dict_key_ok')
            require_json_ok(key_ok)
            key_wrapper_name, key_wrapper_type, key_wrapper = self._json_value_parse_wrapper(key_type, key_source)
            if key_wrapper is None:
                key_wrapper = self._get_or_declare_function(key_wrapper_name, key_wrapper_type)
            parsed_key = self.builder.call(key_wrapper, [key], name='_json_dict_key_value')
            if self._fmt_parse_wrapper_may_throw(key_type):
                self._emit_throw_check_after_call()
            if self.builder is not None and not self.builder.block.is_terminated:
                if parsed_key.type != key_type:
                    parsed_key = self._coerce_value(parsed_key, key_type)
                key = parsed_key
        key_found = self.builder.icmp_unsigned('!=', key, null_str, name='_json_dict_key_found') if string_key else ir.Constant(i1, 1)
        require_json_ok(key_found)
        value_found = self.builder.icmp_unsigned('!=', raw, null_str, name='_json_dict_value_found')
        require_json_ok(value_found)
        wrapper_name, wrapper_type, wrapper = self._json_value_parse_wrapper(value_type, value_source)
        validator_name = self._json_parse_validator_for_value(wrapper_name, value_type)
        validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [i8_ptr]))
        value_ok = self.builder.call(validator, [raw], name='_json_dict_item_ok')
        require_json_ok(value_ok)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        value = self.builder.call(wrapper, [raw], name='_json_dict_item_value')
        if self._fmt_parse_wrapper_may_throw(value_type):
            self._emit_throw_check_after_call()
        if self.builder is not None and not self.builder.block.is_terminated:
            if value.type != value_type:
                value = self._coerce_value(value, value_type)
            self._gen_dict_upsert_value(result, key, value, key_type, value_type)
            self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
            self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        self.builder.ret(result)
        popped_throw_exit = self._function_throw_exit_stack.pop()
        if not popped_throw_exit.is_terminated:
            self.builder.position_at_start(popped_throw_exit)
            self.builder.ret(ir.Constant(result_type, None))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        self._fmt_generation_stack.discard(func_name)
        return func

    def _msgpack_encode_struct_supported(self, typ: ir.Type) -> bool:
        """当前编译期 MessagePack 结构体编码覆盖基础字段与嵌套用户结构体。"""
        return self._fmt_struct_serializable(typ)

    def _msgpack_decode_struct_supported(self, typ: ir.Type) -> bool:
        """当前编译期 MessagePack 结构体解析覆盖基础字段与嵌套用户结构体。"""
        return self._fmt_struct_serializable(typ)

    def _fmt_top_level_list_source_name(self, type_suffixes: list[str] | None, list_type: ir.Type) -> str:
        if type_suffixes:
            return type_suffixes[0]
        return self._type_name_from_ir_type(list_type)

    def _fmt_monomorphize_top_level_list(self, base_name: str, mono_name: str, list_type: ir.Type,
                                         type_suffixes: list[str] | None) -> bool:
        if not self._is_list_type(list_type):
            return False
        source_name = self._fmt_top_level_list_source_name(type_suffixes, list_type)
        if not self._fmt_list_serializable(list_type, source_name, set()):
            return False
        if base_name == 'jsonStringify':
            self._gen_json_stringify_list_function(mono_name, list_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'jsonParse':
            self._gen_json_parse_list_function(mono_name, list_type, source_name)
            self.func_param_names[mono_name] = ['s']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'msgpackEncode':
            self._gen_msgpack_encode_list_function(mono_name, list_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'msgpackDecode':
            self._gen_msgpack_decode_list_function(mono_name, list_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        return False

    def _fmt_top_level_optional_source_name(self, type_suffixes: list[str] | None, opt_type: ir.Type) -> str:
        if type_suffixes:
            return type_suffixes[0]
        return self._type_name_from_ir_type(opt_type)

    def _fmt_monomorphize_top_level_optional(self, base_name: str, mono_name: str, opt_type: ir.Type,
                                             type_suffixes: list[str] | None) -> bool:
        if not self._is_optional_type(opt_type):
            return False
        source_name = self._fmt_top_level_optional_source_name(type_suffixes, opt_type)
        if not self._fmt_optional_serializable(opt_type, source_name, set()):
            return False
        if base_name == 'jsonStringify':
            self._gen_json_stringify_optional_function(mono_name, opt_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'jsonParse':
            self._gen_json_parse_optional_function(mono_name, opt_type, source_name)
            self.func_param_names[mono_name] = ['s']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'msgpackEncode':
            self._gen_msgpack_encode_optional_function(mono_name, opt_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'msgpackDecode':
            self._gen_msgpack_decode_optional_function(mono_name, opt_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        return False

    def _fmt_top_level_dict_source_name(self, type_suffixes: list[str] | None, dict_type: ir.Type) -> str:
        if type_suffixes:
            return type_suffixes[0]
        return self._type_name_from_ir_type(dict_type)

    def _fmt_monomorphize_top_level_dict(self, base_name: str, mono_name: str, dict_type: ir.Type,
                                         type_suffixes: list[str] | None) -> bool:
        if not self._is_dict_type(dict_type):
            return False
        source_name = self._fmt_top_level_dict_source_name(type_suffixes, dict_type)
        if not self._fmt_dict_serializable(dict_type, source_name, set()):
            return False
        if base_name == 'jsonStringify':
            self._gen_json_stringify_dict_function(mono_name, dict_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'jsonParse':
            self._gen_json_parse_dict_function(mono_name, dict_type, source_name)
            self.func_param_names[mono_name] = ['s']
            self.func_return_unsigned[mono_name] = False
            self.func_return_dict_types[mono_name] = self._fmt_dict_item_types_from_source_name(source_name)
            return True
        if base_name == 'msgpackEncode':
            self._gen_msgpack_encode_dict_function(mono_name, dict_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'msgpackDecode':
            self._gen_msgpack_decode_dict_function(mono_name, dict_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            self.func_return_dict_types[mono_name] = self._fmt_dict_item_types_from_source_name(source_name)
            return True
        return False

    def _fmt_top_level_union_source_name(self, type_suffixes: list[str] | None, union_type: ir.Type) -> str:
        if type_suffixes:
            return type_suffixes[0]
        return self._type_name_from_ir_type(union_type)

    def _fmt_monomorphize_top_level_union(self, base_name: str, mono_name: str, union_type: ir.Type,
                                          type_suffixes: list[str] | None) -> bool:
        if not self._is_union_type(union_type):
            return False
        source_name = self._fmt_top_level_union_source_name(type_suffixes, union_type)
        if not self._fmt_union_serializable(union_type, source_name, set()):
            return False
        if base_name == 'jsonStringify':
            self._gen_json_stringify_union_function(mono_name, union_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'jsonParse':
            self._gen_json_parse_union_function(mono_name, union_type, source_name)
            self.func_param_names[mono_name] = ['s']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'msgpackEncode':
            self._gen_msgpack_encode_union_function(mono_name, union_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        if base_name == 'msgpackDecode':
            self._gen_msgpack_decode_union_function(mono_name, union_type, source_name)
            self.func_param_names[mono_name] = ['data']
            self.func_return_unsigned[mono_name] = False
            return True
        return False

    def _msgpack_source_type_name(self, field_type: ir.Type, struct_name: str, index: int) -> str:
        return self._fmt_source_type_name(field_type, struct_name, index)

    def _msgpack_encode_field_function_name(self, field_type: ir.Type, struct_name: str, index: int) -> str | None:
        source_name = self._msgpack_source_type_name(field_type, struct_name, index)
        if source_name == 'Bool':
            return 'msgpackEncode_I1'
        if source_name in {'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str'}:
            return f"msgpackEncode_{source_name}"
        if self._is_optional_type(field_type) and self._fmt_optional_serializable(field_type, source_name, set()):
            return f"msgpackEncode_{self._fmt_optional_function_suffix(field_type, source_name)}"
        if self._is_list_type(field_type) and self._fmt_list_serializable(field_type, source_name, set()):
            return f"msgpackEncode_{self._fmt_list_function_suffix(field_type, source_name)}"
        if self._is_dict_type(field_type) and self._fmt_dict_serializable(field_type, source_name, set()):
            return f"msgpackEncode_{self._fmt_dict_function_suffix(field_type, source_name)}"
        if self._is_union_type(field_type) and self._fmt_union_serializable(field_type, source_name, set()):
            return f"msgpackEncode_{self._fmt_union_function_suffix(field_type, source_name)}"
        if self._fmt_struct_serializable(field_type):
            return f"msgpackEncode_{field_type.name}"
        return None

    def _msgpack_decode_field_function_name(self, field_type: ir.Type, struct_name: str, index: int) -> str | None:
        source_name = self._msgpack_source_type_name(field_type, struct_name, index)
        if source_name == 'Bool':
            return 'msgpackDecode_I1'
        if source_name in {'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str'}:
            return f"msgpackDecode_{source_name}"
        if self._is_optional_type(field_type) and self._fmt_optional_serializable(field_type, source_name, set()):
            return f"msgpackDecode_{self._fmt_optional_function_suffix(field_type, source_name)}"
        if self._is_list_type(field_type) and self._fmt_list_serializable(field_type, source_name, set()):
            return f"msgpackDecode_{self._fmt_list_function_suffix(field_type, source_name)}"
        if self._is_dict_type(field_type) and self._fmt_dict_serializable(field_type, source_name, set()):
            return f"msgpackDecode_{self._fmt_dict_function_suffix(field_type, source_name)}"
        if self._is_union_type(field_type) and self._fmt_union_serializable(field_type, source_name, set()):
            return f"msgpackDecode_{self._fmt_union_function_suffix(field_type, source_name)}"
        if self._fmt_struct_serializable(field_type):
            return f"msgpackDecode_{field_type.name}"
        return None

    def _msgpack_function_scalar_type(self, func_name: str, field_type: ir.Type) -> ir.Type:
        if func_name.endswith('_I1'):
            return ir.IntType(1)
        if isinstance(field_type, ir.IdentifiedStructType) or self._is_list_type(field_type) or self._is_optional_type(field_type) or self._is_dict_type(field_type) or self._is_union_type(field_type):
            return ir.PointerType(field_type)
        return field_type

    def _msgpack_encode_function_type(self, func_name: str, arg_type: ir.Type) -> ir.FunctionType:
        blob_type = self.structs['Blob']
        arg_type = self._msgpack_function_scalar_type(func_name, arg_type)
        if self._uses_c_sret(blob_type):
            return ir.FunctionType(ir.VoidType(), [ir.PointerType(blob_type), arg_type])
        return ir.FunctionType(blob_type, [arg_type])

    def _msgpack_decode_function_type(self, func_name: str, ret_type: ir.Type) -> ir.FunctionType:
        ret_type = self._msgpack_function_scalar_type(func_name, ret_type)
        return ir.FunctionType(ret_type, [ir.PointerType(self.structs['Blob'])])

    def _msgpack_value_encode_wrapper(self, value_type: ir.Type, source_name: str) -> tuple[str, ir.FunctionType, ir.Function | None]:
        if source_name == 'Bool':
            wrapper_name = 'msgpackEncode_I1'
        elif source_name in {'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str'}:
            wrapper_name = f'msgpackEncode_{source_name}'
        elif self._is_optional_type(value_type) and self._fmt_optional_serializable(value_type, source_name, set()):
            wrapper_name = f'msgpackEncode_{self._fmt_optional_function_suffix(value_type, source_name)}'
        elif self._is_list_type(value_type) and self._fmt_list_serializable(value_type, source_name, set()):
            wrapper_name = f'msgpackEncode_{self._fmt_list_function_suffix(value_type, source_name)}'
        elif self._is_dict_type(value_type) and self._fmt_dict_serializable(value_type, source_name, set()):
            wrapper_name = f'msgpackEncode_{self._fmt_dict_function_suffix(value_type, source_name)}'
        elif self._is_union_type(value_type) and self._fmt_union_serializable(value_type, source_name, set()):
            wrapper_name = f'msgpackEncode_{self._fmt_union_function_suffix(value_type, source_name)}'
        elif isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type):
            wrapper_name = f'msgpackEncode_{value_type.name}'
        else:
            wrapper_name = ''
        wrapper_type = self._msgpack_encode_function_type(wrapper_name, value_type)
        wrapper = self._fmt_generate_msgpack_encode_wrapper(wrapper_name, value_type, source_name)
        return wrapper_name, wrapper_type, wrapper

    def _msgpack_value_decode_wrapper(self, value_type: ir.Type, source_name: str) -> tuple[str, ir.FunctionType, ir.Function | None]:
        if source_name == 'Bool':
            wrapper_name = 'msgpackDecode_I1'
        elif source_name in {'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str'}:
            wrapper_name = f'msgpackDecode_{source_name}'
        elif self._is_optional_type(value_type) and self._fmt_optional_serializable(value_type, source_name, set()):
            wrapper_name = f'msgpackDecode_{self._fmt_optional_function_suffix(value_type, source_name)}'
        elif self._is_list_type(value_type) and self._fmt_list_serializable(value_type, source_name, set()):
            wrapper_name = f'msgpackDecode_{self._fmt_list_function_suffix(value_type, source_name)}'
        elif self._is_dict_type(value_type) and self._fmt_dict_serializable(value_type, source_name, set()):
            wrapper_name = f'msgpackDecode_{self._fmt_dict_function_suffix(value_type, source_name)}'
        elif self._is_union_type(value_type) and self._fmt_union_serializable(value_type, source_name, set()):
            wrapper_name = f'msgpackDecode_{self._fmt_union_function_suffix(value_type, source_name)}'
        elif isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type):
            wrapper_name = f'msgpackDecode_{value_type.name}'
        else:
            wrapper_name = ''
        wrapper_type = self._msgpack_decode_function_type(wrapper_name, value_type)
        wrapper = self._fmt_generate_msgpack_decode_wrapper(wrapper_name, value_type, source_name)
        return wrapper_name, wrapper_type, wrapper

    def _msgpack_decode_validator_for_value(self, wrapper_name: str, value_type: ir.Type) -> str | None:
        validator_name = self._msgpack_decode_validator_name(wrapper_name)
        if validator_name is None and self._is_optional_type(value_type) and self._fmt_optional_serializable(value_type, '', set()):
            return '__ez_msgpack_valid_value'
        if validator_name is None and self._is_list_type(value_type) and self._fmt_list_serializable(value_type, '', set()):
            return '__ez_msgpack_valid_array'
        if validator_name is None and self._is_dict_type(value_type):
            return '__ez_msgpack_valid_map'
        if validator_name is None and self._is_union_type(value_type):
            return '__ez_msgpack_valid_map'
        if validator_name is None and isinstance(value_type, ir.IdentifiedStructType) and self._fmt_struct_serializable(value_type):
            return '__ez_msgpack_valid_map'
        return validator_name

    def _gen_msgpack_encode_optional_function(self, func_name: str, opt_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        blob_type = self.structs['Blob']
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(blob_type, [ir.PointerType(opt_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        inner_type = opt_type.elements[1]
        inner_source = self._fmt_optional_inner_source_name(source_name, inner_type)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names

        entry = func.append_basic_block('entry')
        value_block = func.append_basic_block('msgpack_optional_value')
        nil_block = func.append_basic_block('msgpack_optional_nil')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}

        ok_ptr = self.builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        ok = self.builder.load(ok_ptr, name='_msgpack_optional_ok')
        self.builder.cbranch(ok, value_block, nil_block)

        self.builder.position_at_start(nil_block)
        raw = self.builder.call(self._arena_alloc, [ir.Constant(i64, 1), ir.Constant(i64, 1)], name='_msgpack_optional_nil_raw')
        self.builder.store(ir.Constant(i8, 0xC0), raw)
        blob = ir.Constant(blob_type, ir.Undefined)
        blob = self.builder.insert_value(blob, raw, 0)
        blob = self.builder.insert_value(blob, ir.Constant(i64, 1), 1)
        self.builder.ret(blob)

        self.builder.position_at_start(value_block)
        value_ptr = self.builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
        wrapper_name, wrapper_type, wrapper = self._msgpack_value_encode_wrapper(inner_type, inner_source)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        value_arg = value_ptr if value_ptr.type == wrapper_type.args[-1] else self.builder.load(value_ptr, name='_msgpack_optional_value')
        if value_arg.type != wrapper_type.args[-1]:
            value_arg = self._coerce_value(value_arg, wrapper_type.args[-1])
        encoded = self._msgpack_call_blob_returning_function(wrapper, [value_arg], name='_msgpack_optional_blob')
        self.builder.ret(encoded)

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_msgpack_decode_optional_function(self, func_name: str, opt_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        blob_type = self.structs['Blob']
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(opt_type), [ir.PointerType(blob_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i1 = ir.IntType(1)
        i32 = ir.IntType(32)
        blob_ptr = ir.PointerType(blob_type)
        result_type = ir.PointerType(opt_type)
        inner_type = opt_type.elements[1]
        inner_source = self._fmt_optional_inner_source_name(source_name, inner_type)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_unsigned = self._save_unsigned_state()

        entry = func.append_basic_block('entry')
        nil_block = func.append_basic_block('msgpack_optional_nil')
        value_block = func.append_basic_block('msgpack_optional_value')
        throw_exit = func.append_basic_block('throw_exit')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._function_throw_exit_stack.append(throw_exit)

        def require_msgpack_ok(ok: ir.Value) -> None:
            fail_bb = self.builder.append_basic_block('msgpack_optional_decode_invalid')
            cont_bb = self.builder.append_basic_block('msgpack_optional_decode_valid')
            self.builder.cbranch(ok, cont_bb, fail_bb)
            self.builder.position_at_start(fail_bb)
            self._raise_error(4, 'msgpack decode failed')
            self.builder.position_at_start(cont_bb)

        result = self._arena_allocate(opt_type, name='_msgpack_optional_value_ptr')
        self.builder.store(self._zero_constant(opt_type), result)
        valid_value = self._get_or_declare_function('__ez_msgpack_valid_value', ir.FunctionType(i1, [blob_ptr]))
        valid_ok = self.builder.call(valid_value, [func.args[0]], name='_msgpack_optional_valid')
        require_msgpack_ok(valid_ok)
        valid_nil = self._get_or_declare_function('__ez_msgpack_valid_nil', ir.FunctionType(i1, [blob_ptr]))
        is_nil = self.builder.call(valid_nil, [func.args[0]], name='_msgpack_optional_is_nil')
        self.builder.cbranch(is_nil, nil_block, value_block)

        self.builder.position_at_start(nil_block)
        self.builder.ret(result)

        self.builder.position_at_start(value_block)
        wrapper_name, wrapper_type, wrapper = self._msgpack_value_decode_wrapper(inner_type, inner_source)
        validator_name = self._msgpack_decode_validator_for_value(wrapper_name, inner_type)
        validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [blob_ptr]))
        value_ok = self.builder.call(validator, [func.args[0]], name='_msgpack_optional_inner_ok')
        require_msgpack_ok(value_ok)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        value = self.builder.call(wrapper, [func.args[0]], name='_msgpack_optional_inner')
        if self._fmt_parse_wrapper_may_throw(inner_type):
            self._emit_throw_check_after_call()
        if self.builder is not None and not self.builder.block.is_terminated:
            if value.type != inner_type:
                value = self._coerce_value(value, inner_type)
            self.builder.store(self._optional_value(inner_type, True, value), result)
            self.builder.ret(result)

        popped_throw_exit = self._function_throw_exit_stack.pop()
        if not popped_throw_exit.is_terminated:
            self.builder.position_at_start(popped_throw_exit)
            self.builder.ret(ir.Constant(result_type, None))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_msgpack_encode_union_function(self, func_name: str, union_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        blob_type = self.structs['Blob']
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(blob_type, [ir.PointerType(union_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(ir.IntType(8))
        variants = self._fmt_union_variant_types_from_source_name(source_name)
        if variants is None:
            return func
        variant_sources, variant_types = variants
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names

        entry = func.append_basic_block('entry')
        invalid_block = func.append_basic_block('msgpack_union_invalid')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}

        tag_ptr = self.builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        tag = self.builder.load(tag_ptr, name='_msgpack_union_tag')
        for index, (variant_source, variant_type) in enumerate(zip(variant_sources, variant_types)):
            is_tag = self.builder.icmp_signed('==', tag, ir.Constant(i32, index), name='_msgpack_union_tag_match')
            match_block = func.append_basic_block(f'msgpack_union_tag_{index}')
            next_block = invalid_block if index == len(variant_types) - 1 else func.append_basic_block(f'msgpack_union_next_{index}')
            self.builder.cbranch(is_tag, match_block, next_block)

            self.builder.position_at_start(match_block)
            union_value = self.builder.load(func.args[0], name='_msgpack_union_value')
            variant_value = self._fmt_union_value_for_variant(union_value, union_type, variant_type)
            wrapper_name, wrapper_type, wrapper = self._msgpack_value_encode_wrapper(variant_type, variant_source)
            if wrapper is None:
                wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
            variant_arg = self._fmt_arg_for_wrapper(variant_value, wrapper_type.args[-1])
            value_blob = self._msgpack_call_blob_returning_function(wrapper, [variant_arg], name='_msgpack_union_value_blob')
            keys = self.builder.alloca(ir.ArrayType(i8_ptr, 2), name='_msgpack_union_keys')
            values = self.builder.alloca(ir.ArrayType(blob_type, 2), name='_msgpack_union_values')
            keys_ptr = self.builder.gep(keys, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
            values_ptr = self.builder.gep(values, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
            self.builder.store(self._make_global_string('tag', prefix='_msgpack_union_key'), self.builder.gep(keys, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True))
            self.builder.store(self._make_global_string('value', prefix='_msgpack_union_key'), self.builder.gep(keys, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True))
            tag_encoder = self._get_or_declare_function('msgpackEncode_I32', self._msgpack_encode_function_type('msgpackEncode_I32', i32))
            tag_blob = self._msgpack_call_blob_returning_function(tag_encoder, [ir.Constant(i32, index)], name='_msgpack_union_tag_blob')
            self.builder.store(tag_blob, self.builder.gep(values, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True))
            self.builder.store(value_blob, self.builder.gep(values, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True))
            helper_arg_types = [i64, ir.PointerType(i8_ptr), ir.PointerType(blob_type)]
            if self._uses_c_sret(blob_type):
                helper_type = ir.FunctionType(ir.VoidType(), [ir.PointerType(blob_type)] + helper_arg_types)
            else:
                helper_type = ir.FunctionType(blob_type, helper_arg_types)
            helper = self._get_or_declare_function('__ez_msgpack_encode_map', helper_type)
            result = self._msgpack_call_blob_returning_function(helper, [ir.Constant(i64, 2), keys_ptr, values_ptr], name='_msgpack_union_blob')
            self.builder.ret(result)

            if next_block is not invalid_block:
                self.builder.position_at_start(next_block)

        self.builder.position_at_start(invalid_block)
        raw = self.builder.call(self._arena_alloc, [ir.Constant(i64, 1), ir.Constant(i64, 1)], name='_msgpack_union_invalid_raw')
        self.builder.store(ir.Constant(ir.IntType(8), 0xC0), raw)
        blob = ir.Constant(blob_type, ir.Undefined)
        blob = self.builder.insert_value(blob, raw, 0)
        blob = self.builder.insert_value(blob, ir.Constant(i64, 1), 1)
        self.builder.ret(blob)

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_msgpack_decode_union_function(self, func_name: str, union_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        blob_type = self.structs['Blob']
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(union_type), [ir.PointerType(blob_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i1 = ir.IntType(1)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(ir.IntType(8))
        blob_ptr = ir.PointerType(blob_type)
        result_type = ir.PointerType(union_type)
        variants = self._fmt_union_variant_types_from_source_name(source_name)
        if variants is None:
            return func
        variant_sources, variant_types = variants
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_unsigned = self._save_unsigned_state()

        entry = func.append_basic_block('entry')
        invalid_block = func.append_basic_block('msgpack_union_invalid')
        throw_exit = func.append_basic_block('throw_exit')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._function_throw_exit_stack.append(throw_exit)

        def require_msgpack_ok(ok: ir.Value) -> None:
            if self.builder is None or self.builder.block.is_terminated:
                return
            fail_bb = self.builder.append_basic_block('msgpack_union_decode_invalid')
            cont_bb = self.builder.append_basic_block('msgpack_union_decode_valid')
            self.builder.cbranch(ok, cont_bb, fail_bb)
            self.builder.position_at_start(fail_bb)
            self._raise_error(4, 'msgpack decode failed')
            self.builder.position_at_start(cont_bb)

        result = self._arena_allocate(union_type, name='_msgpack_union_value_ptr')
        self.builder.store(self._zero_constant(union_type), result)
        valid_map = self._get_or_declare_function('__ez_msgpack_valid_map', ir.FunctionType(i1, [blob_ptr]))
        require_msgpack_ok(self.builder.call(valid_map, [func.args[0]], name='_msgpack_union_map_ok'))
        field_count_fn = self._get_or_declare_function('__ez_msgpack_map_field_count', ir.FunctionType(i64, [blob_ptr]))
        field_count = self.builder.call(field_count_fn, [func.args[0]], name='_msgpack_union_field_count')
        require_msgpack_ok(self.builder.icmp_signed('==', field_count, ir.Constant(i64, 2), name='_msgpack_union_field_count_ok'))
        if self._uses_c_sret(blob_type):
            field_fn_type = ir.FunctionType(ir.VoidType(), [blob_ptr, blob_ptr, i8_ptr])
        else:
            field_fn_type = ir.FunctionType(blob_type, [blob_ptr, i8_ptr])
        field_fn = self._get_or_declare_function('__ez_msgpack_map_field', field_fn_type)
        tag_blob_ptr = self.builder.alloca(blob_type, name='_msgpack_union_tag_blob_ptr')
        value_blob_ptr = self.builder.alloca(blob_type, name='_msgpack_union_value_blob_ptr')
        tag_key = self._make_global_string('tag', prefix='_msgpack_union_key')
        value_key = self._make_global_string('value', prefix='_msgpack_union_key')
        if self._uses_c_sret(blob_type):
            self.builder.call(field_fn, [tag_blob_ptr, func.args[0], tag_key])
            self.builder.call(field_fn, [value_blob_ptr, func.args[0], value_key])
        else:
            self.builder.store(self.builder.call(field_fn, [func.args[0], tag_key], name='_msgpack_union_tag_raw'), tag_blob_ptr)
            self.builder.store(self.builder.call(field_fn, [func.args[0], value_key], name='_msgpack_union_value_raw'), value_blob_ptr)
        tag_size = self.builder.load(self.builder.gep(tag_blob_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True), name='_msgpack_union_tag_size')
        value_size = self.builder.load(self.builder.gep(value_blob_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True), name='_msgpack_union_value_size')
        require_msgpack_ok(self.builder.icmp_signed('>=', tag_size, ir.Constant(i64, 0), name='_msgpack_union_tag_found'))
        require_msgpack_ok(self.builder.icmp_signed('>=', value_size, ir.Constant(i64, 0), name='_msgpack_union_value_found'))
        tag_validator = self._get_or_declare_function('__ez_msgpack_valid_I32', ir.FunctionType(i1, [blob_ptr]))
        require_msgpack_ok(self.builder.call(tag_validator, [tag_blob_ptr], name='_msgpack_union_tag_ok'))
        tag_parser = self._get_or_declare_function('msgpackDecode_I32', self._msgpack_decode_function_type('msgpackDecode_I32', i32))
        tag = self.builder.call(tag_parser, [tag_blob_ptr], name='_msgpack_union_tag')

        for index, (variant_source, variant_type) in enumerate(zip(variant_sources, variant_types)):
            is_tag = self.builder.icmp_signed('==', tag, ir.Constant(i32, index), name='_msgpack_union_tag_match')
            match_block = func.append_basic_block(f'msgpack_union_parse_tag_{index}')
            next_block = invalid_block if index == len(variant_types) - 1 else func.append_basic_block(f'msgpack_union_parse_next_{index}')
            self.builder.cbranch(is_tag, match_block, next_block)

            self.builder.position_at_start(match_block)
            wrapper_name, wrapper_type, wrapper = self._msgpack_value_decode_wrapper(variant_type, variant_source)
            validator_name = self._msgpack_decode_validator_for_value(wrapper_name, variant_type)
            validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [blob_ptr]))
            require_msgpack_ok(self.builder.call(validator, [value_blob_ptr], name='_msgpack_union_value_ok'))
            if wrapper is None:
                wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
            value = self.builder.call(wrapper, [value_blob_ptr], name='_msgpack_union_variant_value')
            if self._fmt_parse_wrapper_may_throw(variant_type):
                self._emit_throw_check_after_call()
            if self.builder is not None and not self.builder.block.is_terminated:
                if value.type != variant_type:
                    value = self._coerce_value(value, variant_type)
                union_value = self._coerce_union_value(value, union_type, index)
                self.builder.store(union_value, result)
                self.builder.ret(result)

            if next_block is not invalid_block:
                self.builder.position_at_start(next_block)

        self.builder.position_at_start(invalid_block)
        self._raise_error(4, 'msgpack decode failed')

        popped_throw_exit = self._function_throw_exit_stack.pop()
        if not popped_throw_exit.is_terminated:
            self.builder.position_at_start(popped_throw_exit)
            self.builder.ret(ir.Constant(result_type, None))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_msgpack_encode_list_function(self, func_name: str, list_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(self.structs['Blob'], [ir.PointerType(list_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        blob_type = self.structs['Blob']
        elem_type = list_type.elements[0].pointee.pointee
        elem_source = self._fmt_list_elem_source_name(source_name, elem_type)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names

        entry = func.append_basic_block('entry')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}

        length = self._list_length(func.args[0])
        values_bytes = self.builder.mul(length, ir.Constant(i64, max(self._type_width(blob_type), 1)), name='_msgpack_list_values_bytes')
        has_items = self.builder.icmp_unsigned('>', length, ir.Constant(i64, 0), name='_msgpack_list_has_items')
        alloc_bytes = self.builder.select(has_items, values_bytes, ir.Constant(i64, max(self._type_width(blob_type), 1)), name='_msgpack_list_values_alloc_bytes')
        raw_values = self.builder.call(self._arena_alloc, [alloc_bytes, ir.Constant(i64, 8)], name='_msgpack_list_values_raw')
        values = self.builder.bitcast(raw_values, ir.PointerType(blob_type), name='_msgpack_list_values')
        index_ptr = self.builder.alloca(i64, name='_msgpack_list_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)

        loop_cond = self.builder.append_basic_block('msgpack_list_encode_cond')
        loop_body = self.builder.append_basic_block('msgpack_list_encode_body')
        loop_done = self.builder.append_basic_block('msgpack_list_encode_done')
        self.builder.branch(loop_cond)
        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_msgpack_list_i_val')
        more = self.builder.icmp_unsigned('<', index, length, name='_msgpack_list_more')
        self.builder.cbranch(more, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        elem_ptr = self._list_element_ptr(func.args[0], index)
        wrapper_name, wrapper_type, wrapper = self._msgpack_value_encode_wrapper(elem_type, elem_source)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        elem_arg = elem_ptr if elem_ptr.type == wrapper_type.args[-1] else self.builder.load(elem_ptr, name='_msgpack_list_item')
        if elem_arg.type != wrapper_type.args[-1]:
            elem_arg = self._coerce_value(elem_arg, wrapper_type.args[-1])
        encoded = self._msgpack_call_blob_returning_function(wrapper, [elem_arg], name='_msgpack_list_item_blob')
        value_slot = self.builder.gep(values, [index], inbounds=True)
        self.builder.store(encoded, value_slot)
        self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        helper_args = [i64, ir.PointerType(blob_type)]
        if self._uses_c_sret(blob_type):
            helper_type = ir.FunctionType(ir.VoidType(), [ir.PointerType(blob_type)] + helper_args)
        else:
            helper_type = ir.FunctionType(blob_type, helper_args)
        helper = self._get_or_declare_function('__ez_msgpack_encode_array', helper_type)
        result = self._msgpack_call_blob_returning_function(helper, [length, values], name='_msgpack_list_blob')
        self.builder.ret(result)

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_msgpack_decode_list_function(self, func_name: str, list_type: ir.LiteralStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(list_type), [ir.PointerType(self.structs['Blob'])]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i1 = ir.IntType(1)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        blob_type = self.structs['Blob']
        blob_ptr = ir.PointerType(blob_type)
        result_type = ir.PointerType(list_type)
        elem_type = list_type.elements[0].pointee.pointee
        elem_source = self._fmt_list_elem_source_name(source_name, elem_type)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_unsigned = self._save_unsigned_state()

        entry = func.append_basic_block('entry')
        throw_exit = func.append_basic_block('throw_exit')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._function_throw_exit_stack.append(throw_exit)

        def require_msgpack_ok(ok: ir.Value) -> None:
            fail_bb = self.builder.append_basic_block('msgpack_list_decode_invalid')
            cont_bb = self.builder.append_basic_block('msgpack_list_decode_valid')
            self.builder.cbranch(ok, cont_bb, fail_bb)
            self.builder.position_at_start(fail_bb)
            self._raise_error(4, 'msgpack decode failed')
            self.builder.position_at_start(cont_bb)

        valid_array = self._get_or_declare_function('__ez_msgpack_valid_array', ir.FunctionType(i1, [blob_ptr]))
        array_ok = self.builder.call(valid_array, [func.args[0]], name='_msgpack_list_ok')
        require_msgpack_ok(array_ok)
        length_fn = self._get_or_declare_function('__ez_msgpack_array_length', ir.FunctionType(i64, [blob_ptr]))
        length = self.builder.call(length_fn, [func.args[0]], name='_msgpack_list_len')
        len_ok = self.builder.icmp_signed('>=', length, ir.Constant(i64, 0), name='_msgpack_list_len_ok')
        require_msgpack_ok(len_ok)
        result = self._list_new(elem_type, length)
        self._mark_list_elem_unsigned(result, elem_source in {'U8', 'U32', 'U64'})
        if self._uses_c_sret(blob_type):
            item_fn_type = ir.FunctionType(ir.VoidType(), [blob_ptr, blob_ptr, i64])
        else:
            item_fn_type = ir.FunctionType(blob_type, [blob_ptr, i64])
        item_fn = self._get_or_declare_function('__ez_msgpack_array_item', item_fn_type)
        index_ptr = self.builder.alloca(i64, name='_msgpack_list_parse_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        loop_cond = self.builder.append_basic_block('msgpack_list_parse_cond')
        loop_body = self.builder.append_basic_block('msgpack_list_parse_body')
        loop_done = self.builder.append_basic_block('msgpack_list_parse_done')
        self.builder.branch(loop_cond)
        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_msgpack_list_parse_i_val')
        more = self.builder.icmp_unsigned('<', index, length, name='_msgpack_list_parse_more')
        self.builder.cbranch(more, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        item_blob_ptr = self.builder.alloca(blob_type, name='_msgpack_list_item_blob_ptr')
        if self._uses_c_sret(blob_type):
            self.builder.call(item_fn, [item_blob_ptr, func.args[0], index])
        else:
            item_blob = self.builder.call(item_fn, [func.args[0], index], name='_msgpack_list_item_raw')
            self.builder.store(item_blob, item_blob_ptr)
        size_ptr = self.builder.gep(item_blob_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
        size = self.builder.load(size_ptr, name='_msgpack_list_item_size')
        found = self.builder.icmp_signed('>=', size, ir.Constant(i64, 0), name='_msgpack_list_item_found')
        require_msgpack_ok(found)
        wrapper_name, wrapper_type, wrapper = self._msgpack_value_decode_wrapper(elem_type, elem_source)
        validator_name = self._msgpack_decode_validator_for_value(wrapper_name, elem_type)
        validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [blob_ptr]))
        value_ok = self.builder.call(validator, [item_blob_ptr], name='_msgpack_list_item_ok')
        require_msgpack_ok(value_ok)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        value = self.builder.call(wrapper, [item_blob_ptr], name='_msgpack_list_item_value')
        if self._fmt_parse_wrapper_may_throw(elem_type):
            self._emit_throw_check_after_call()
        if self.builder is not None and not self.builder.block.is_terminated:
            if value.type != elem_type:
                value = self._coerce_value(value, elem_type)
            self.builder.store(value, self._list_element_ptr(result, index))
            self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
            self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        self.builder.ret(result)
        popped_throw_exit = self._function_throw_exit_stack.pop()
        if not popped_throw_exit.is_terminated:
            self.builder.position_at_start(popped_throw_exit)
            self.builder.ret(ir.Constant(result_type, None))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_msgpack_encode_dict_function(self, func_name: str, dict_type: ir.IdentifiedStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        blob_type = self.structs['Blob']
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(blob_type, [ir.PointerType(dict_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        key_type, value_type = self._fmt_dict_item_types_from_source_name(source_name)
        key_source = self._fmt_dict_key_source_name(source_name, key_type)
        value_source = self._fmt_dict_value_source_name(source_name, value_type)
        string_key = self._fmt_dict_has_string_key(source_name)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names

        entry = func.append_basic_block('entry')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}

        count32 = self._dict_count(func.args[0])
        count = self.builder.zext(count32, i64, name='_msgpack_dict_count')
        has_items = self.builder.icmp_unsigned('>', count, ir.Constant(i64, 0), name='_msgpack_dict_has_items')
        value_bytes = self.builder.mul(count, ir.Constant(i64, max(self._type_width(blob_type), 1)), name='_msgpack_dict_value_bytes')
        values_alloc_bytes = self.builder.select(has_items, value_bytes, ir.Constant(i64, max(self._type_width(blob_type), 1)), name='_msgpack_dict_values_alloc_bytes')
        if string_key:
            key_bytes = self.builder.mul(count, ir.Constant(i64, 8), name='_msgpack_dict_key_bytes')
            keys_alloc_bytes = self.builder.select(has_items, key_bytes, ir.Constant(i64, 8), name='_msgpack_dict_keys_alloc_bytes')
        else:
            key_blob_bytes = self.builder.mul(count, ir.Constant(i64, max(self._type_width(blob_type), 1)), name='_msgpack_dict_key_blob_bytes')
            keys_alloc_bytes = self.builder.select(has_items, key_blob_bytes, ir.Constant(i64, max(self._type_width(blob_type), 1)), name='_msgpack_dict_keys_alloc_bytes')
        keys_raw = self.builder.call(self._arena_alloc, [keys_alloc_bytes, ir.Constant(i64, 8)], name='_msgpack_dict_keys_raw')
        values_raw = self.builder.call(self._arena_alloc, [values_alloc_bytes, ir.Constant(i64, 8)], name='_msgpack_dict_values_raw')
        keys = self.builder.bitcast(keys_raw, ir.PointerType(i8_ptr if string_key else blob_type), name='_msgpack_dict_keys')
        values = self.builder.bitcast(values_raw, ir.PointerType(blob_type), name='_msgpack_dict_values')
        index_ptr = self.builder.alloca(i32, name='_msgpack_dict_i')
        self.builder.store(ir.Constant(i32, 0), index_ptr)

        loop_cond = self.builder.append_basic_block('msgpack_dict_encode_cond')
        loop_body = self.builder.append_basic_block('msgpack_dict_encode_body')
        loop_done = self.builder.append_basic_block('msgpack_dict_encode_done')
        self.builder.branch(loop_cond)
        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_msgpack_dict_i_val')
        more = self.builder.icmp_unsigned('<', index, count32, name='_msgpack_dict_more')
        self.builder.cbranch(more, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        raw_key = self.builder.load(self._dict_key_slot_ptr(func.args[0], index), name='_msgpack_dict_key_raw')
        key_value = self._dict_from_i8_ptr(raw_key, key_type)
        index64 = self.builder.zext(index, i64, name='_msgpack_dict_i64')
        if string_key:
            self.builder.store(key_value, self.builder.gep(keys, [index64], inbounds=True))
        else:
            key_wrapper_name, key_wrapper_type, key_wrapper = self._msgpack_value_encode_wrapper(key_type, key_source)
            if key_wrapper is None:
                key_wrapper = self._get_or_declare_function(key_wrapper_name, key_wrapper_type)
            key_arg = self._fmt_arg_for_wrapper(key_value, key_wrapper_type.args[-1])
            key_blob = self._msgpack_call_blob_returning_function(key_wrapper, [key_arg], name='_msgpack_dict_key_blob')
            self.builder.store(key_blob, self.builder.gep(keys, [index64], inbounds=True))
        raw_value = self.builder.load(self._dict_value_slot_ptr(func.args[0], index), name='_msgpack_dict_value_raw')
        wrapper_name, wrapper_type, wrapper = self._msgpack_value_encode_wrapper(value_type, value_source)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        value_arg = self._fmt_value_from_raw_ptr(raw_value, value_type, wrapper_type.args[-1])
        encoded = self._msgpack_call_blob_returning_function(wrapper, [value_arg], name='_msgpack_dict_item_blob')
        self.builder.store(encoded, self.builder.gep(values, [index64], inbounds=True))
        self.builder.store(self.builder.add(index, ir.Constant(i32, 1)), index_ptr)
        self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        helper_arg_types = [i64, ir.PointerType(i8_ptr if string_key else blob_type), ir.PointerType(blob_type)]
        if self._uses_c_sret(blob_type):
            helper_type = ir.FunctionType(ir.VoidType(), [ir.PointerType(blob_type)] + helper_arg_types)
        else:
            helper_type = ir.FunctionType(blob_type, helper_arg_types)
        helper_name = '__ez_msgpack_encode_map' if string_key else '__ez_msgpack_encode_map_raw'
        helper = self._get_or_declare_function(helper_name, helper_type)
        result = self._msgpack_call_blob_returning_function(helper, [count, keys, values], name='_msgpack_dict_blob')
        self.builder.ret(result)

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_msgpack_decode_dict_function(self, func_name: str, dict_type: ir.IdentifiedStructType, source_name: str) -> ir.Function:
        existing = self.module.globals.get(func_name)
        blob_type = self.structs['Blob']
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(dict_type), [ir.PointerType(blob_type)]), func_name)
        if func_name in self._fmt_generation_stack:
            return func
        self._fmt_generation_stack.add(func_name)

        i1 = ir.IntType(1)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(ir.IntType(8))
        blob_ptr = ir.PointerType(blob_type)
        result_type = ir.PointerType(dict_type)
        key_type, value_type = self._fmt_dict_item_types_from_source_name(source_name)
        key_source = self._fmt_dict_key_source_name(source_name, key_type)
        value_source = self._fmt_dict_value_source_name(source_name, value_type)
        string_key = self._fmt_dict_has_string_key(source_name)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_unsigned = self._save_unsigned_state()

        entry = func.append_basic_block('entry')
        throw_exit = func.append_basic_block('throw_exit')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._function_throw_exit_stack.append(throw_exit)

        def require_msgpack_ok(ok: ir.Value) -> None:
            fail_bb = self.builder.append_basic_block('msgpack_dict_decode_invalid')
            cont_bb = self.builder.append_basic_block('msgpack_dict_decode_valid')
            self.builder.cbranch(ok, cont_bb, fail_bb)
            self.builder.position_at_start(fail_bb)
            self._raise_error(4, 'msgpack decode failed')
            self.builder.position_at_start(cont_bb)

        result = self._arena_allocate(dict_type, name='_msgpack_dict_value')
        self.builder.store(self._zero_constant(dict_type), result)
        self._mark_dict_item_types(result, key_type, value_type)
        valid_map_name = '__ez_msgpack_valid_map' if string_key else '__ez_msgpack_valid_map_any'
        valid_map = self._get_or_declare_function(valid_map_name, ir.FunctionType(i1, [blob_ptr]))
        map_ok = self.builder.call(valid_map, [func.args[0]], name='_msgpack_dict_ok')
        require_msgpack_ok(map_ok)
        field_count_fn = self._get_or_declare_function('__ez_msgpack_map_field_count', ir.FunctionType(i64, [blob_ptr]))
        length = self.builder.call(field_count_fn, [func.args[0]], name='_msgpack_dict_len')
        len_ok = self.builder.icmp_signed('>=', length, ir.Constant(i64, 0), name='_msgpack_dict_len_ok')
        require_msgpack_ok(len_ok)
        if string_key:
            key_at_fn = self._get_or_declare_function('__ez_msgpack_map_key_at', ir.FunctionType(i8_ptr, [blob_ptr, i64]))
        else:
            if self._uses_c_sret(blob_type):
                key_at_type = ir.FunctionType(ir.VoidType(), [blob_ptr, blob_ptr, i64])
            else:
                key_at_type = ir.FunctionType(blob_type, [blob_ptr, i64])
            key_at_fn = self._get_or_declare_function('__ez_msgpack_map_key_blob_at', key_at_type)
        if self._uses_c_sret(blob_type):
            value_at_type = ir.FunctionType(ir.VoidType(), [blob_ptr, blob_ptr, i64])
        else:
            value_at_type = ir.FunctionType(blob_type, [blob_ptr, i64])
        value_at_fn = self._get_or_declare_function('__ez_msgpack_map_value_at', value_at_type)
        null_str = ir.Constant(i8_ptr, None)
        index_ptr = self.builder.alloca(i64, name='_msgpack_dict_parse_i')
        self.builder.store(ir.Constant(i64, 0), index_ptr)
        loop_cond = self.builder.append_basic_block('msgpack_dict_parse_cond')
        loop_body = self.builder.append_basic_block('msgpack_dict_parse_body')
        loop_done = self.builder.append_basic_block('msgpack_dict_parse_done')
        self.builder.branch(loop_cond)
        self.builder.position_at_start(loop_cond)
        index = self.builder.load(index_ptr, name='_msgpack_dict_parse_i_val')
        more = self.builder.icmp_unsigned('<', index, length, name='_msgpack_dict_parse_more')
        self.builder.cbranch(more, loop_body, loop_done)

        self.builder.position_at_start(loop_body)
        if string_key:
            key = self.builder.call(key_at_fn, [func.args[0], index], name='_msgpack_dict_key')
            key_found = self.builder.icmp_unsigned('!=', key, null_str, name='_msgpack_dict_key_found')
            require_msgpack_ok(key_found)
        else:
            key_blob_ptr = self.builder.alloca(blob_type, name='_msgpack_dict_key_blob_ptr')
            if self._uses_c_sret(blob_type):
                self.builder.call(key_at_fn, [key_blob_ptr, func.args[0], index])
            else:
                raw_key_blob = self.builder.call(key_at_fn, [func.args[0], index], name='_msgpack_dict_key_raw_blob')
                self.builder.store(raw_key_blob, key_blob_ptr)
            key_size_ptr = self.builder.gep(key_blob_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
            key_size = self.builder.load(key_size_ptr, name='_msgpack_dict_key_size')
            key_found = self.builder.icmp_signed('>=', key_size, ir.Constant(i64, 0), name='_msgpack_dict_key_found')
            require_msgpack_ok(key_found)
            key_wrapper_name, key_wrapper_type, key_wrapper = self._msgpack_value_decode_wrapper(key_type, key_source)
            key_validator_name = self._msgpack_decode_validator_for_value(key_wrapper_name, key_type)
            key_validator = self._get_or_declare_function(key_validator_name, ir.FunctionType(i1, [blob_ptr]))
            key_ok = self.builder.call(key_validator, [key_blob_ptr], name='_msgpack_dict_key_ok')
            require_msgpack_ok(key_ok)
            if key_wrapper is None:
                key_wrapper = self._get_or_declare_function(key_wrapper_name, key_wrapper_type)
            key = self.builder.call(key_wrapper, [key_blob_ptr], name='_msgpack_dict_key_value')
            if self._fmt_parse_wrapper_may_throw(key_type):
                self._emit_throw_check_after_call()
        value_blob_ptr = self.builder.alloca(blob_type, name='_msgpack_dict_item_blob_ptr')
        if self._uses_c_sret(blob_type):
            self.builder.call(value_at_fn, [value_blob_ptr, func.args[0], index])
        else:
            raw_blob = self.builder.call(value_at_fn, [func.args[0], index], name='_msgpack_dict_item_raw')
            self.builder.store(raw_blob, value_blob_ptr)
        size_ptr = self.builder.gep(value_blob_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
        size = self.builder.load(size_ptr, name='_msgpack_dict_item_size')
        found = self.builder.icmp_signed('>=', size, ir.Constant(i64, 0), name='_msgpack_dict_item_found')
        require_msgpack_ok(found)
        wrapper_name, wrapper_type, wrapper = self._msgpack_value_decode_wrapper(value_type, value_source)
        validator_name = self._msgpack_decode_validator_for_value(wrapper_name, value_type)
        validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [blob_ptr]))
        value_ok = self.builder.call(validator, [value_blob_ptr], name='_msgpack_dict_item_ok')
        require_msgpack_ok(value_ok)
        if wrapper is None:
            wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
        value = self.builder.call(wrapper, [value_blob_ptr], name='_msgpack_dict_item_value')
        if self._fmt_parse_wrapper_may_throw(value_type):
            self._emit_throw_check_after_call()
        if self.builder is not None and not self.builder.block.is_terminated:
            if key.type != key_type:
                key = self._coerce_value(key, key_type)
            if value.type != value_type:
                value = self._coerce_value(value, value_type)
            self._gen_dict_upsert_value(result, key, value, key_type, value_type)
            self.builder.store(self.builder.add(index, ir.Constant(i64, 1)), index_ptr)
            self.builder.branch(loop_cond)

        self.builder.position_at_start(loop_done)
        self.builder.ret(result)
        popped_throw_exit = self._function_throw_exit_stack.pop()
        if not popped_throw_exit.is_terminated:
            self.builder.position_at_start(popped_throw_exit)
            self.builder.ret(ir.Constant(result_type, None))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        self._fmt_generation_stack.discard(func_name)
        return func

    def _gen_json_stringify_struct_function(self, func_name: str, struct_type: ir.IdentifiedStructType) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(ir.IntType(8)), [ir.PointerType(struct_type)]), func_name)

        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names

        entry = func.append_basic_block('entry')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}

        strlen = self._get_or_define_strlen()
        segments: list[tuple[ir.Value, ir.Value]] = []
        self._append_json_literal_segment(segments, '{')
        field_names = self.struct_fields.get(struct_type.name, [])
        for index, field_name in enumerate(field_names):
            if index > 0:
                self._append_json_literal_segment(segments, ',')
            self._append_json_literal_segment(segments, '"' + field_name + '":')
            field_type = struct_type.elements[index]
            field_ptr = self.builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, index)], inbounds=True)
            field_value = self.builder.load(field_ptr, name=f"_json_{field_name}")
            wrapper_name = self._json_stringify_field_function_name(field_type, struct_type.name, index)
            wrapper_type = self._json_stringify_function_type(wrapper_name, field_type)
            source_name = self._fmt_source_type_name(field_type, struct_type.name, index)
            wrapper = self._fmt_generate_json_stringify_wrapper(wrapper_name, field_type, source_name)
            if wrapper is None:
                wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
            field_value = self._fmt_arg_for_wrapper(field_value, wrapper_type.args[0])
            text = self.builder.call(wrapper, [field_value], name=f"_json_{field_name}_text")
            length = self.builder.call(strlen, [text], name=f"_json_{field_name}_len")
            segments.append((text, length))
        self._append_json_literal_segment(segments, '}')

        result = self._join_c_string_segments(segments, name_prefix='_json_struct')
        self.builder.ret(result)

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        return func

    def _gen_json_parse_struct_function(self, func_name: str, struct_type: ir.IdentifiedStructType) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(struct_type), [ir.PointerType(ir.IntType(8))]), func_name)

        i1 = ir.IntType(1)
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i8_ptr = ir.PointerType(i8)
        result_type = ir.PointerType(struct_type)
        func.args[0].name = 's'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_unsigned = self._save_unsigned_state()

        entry = func.append_basic_block('entry')
        throw_exit = func.append_basic_block('throw_exit')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._function_throw_exit_stack.append(throw_exit)

        def require_json_ok(ok: ir.Value) -> None:
            fail_bb = self.builder.append_basic_block('json_parse_invalid')
            cont_bb = self.builder.append_basic_block('json_parse_valid')
            self.builder.cbranch(ok, cont_bb, fail_bb)
            self.builder.position_at_start(fail_bb)
            self._raise_error(4, 'json parse failed')
            self.builder.position_at_start(cont_bb)

        result = self._arena_allocate(struct_type, name=f'_json_{struct_type.name}_value')
        self.builder.store(self._zero_constant(struct_type), result)

        valid_object = self._get_or_declare_function('__ez_json_valid_object', ir.FunctionType(i1, [i8_ptr]))
        object_ok = self.builder.call(valid_object, [func.args[0]], name='_json_object_ok')
        require_json_ok(object_ok)

        field_names = self.struct_fields.get(struct_type.name, [])
        field_count_fn = self._get_or_declare_function('__ez_json_object_field_count', ir.FunctionType(ir.IntType(64), [i8_ptr]))
        field_count = self.builder.call(field_count_fn, [func.args[0]], name='_json_object_field_count')
        field_count_ok = self.builder.icmp_signed('==', field_count, ir.Constant(ir.IntType(64), len(field_names)), name='_json_object_field_count_ok')
        require_json_ok(field_count_ok)

        field_fn = self._get_or_declare_function('__ez_json_object_field', ir.FunctionType(i8_ptr, [i8_ptr, i8_ptr]))
        null_str = ir.Constant(i8_ptr, None)
        for index, field_name in enumerate(field_names):
            key = self._make_global_string(field_name, prefix='_json_key')
            raw = self.builder.call(field_fn, [func.args[0], key], name=f'_json_{field_name}_raw')
            found = self.builder.icmp_unsigned('!=', raw, null_str, name=f'_json_{field_name}_found')
            require_json_ok(found)

            field_type = struct_type.elements[index]
            wrapper_name = self._json_parse_field_function_name(field_type, struct_type.name, index)
            validator_name = self._json_parse_validator_for_value(wrapper_name, field_type)
            validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [i8_ptr]))
            value_ok = self.builder.call(validator, [raw], name=f'_json_{field_name}_ok')
            require_json_ok(value_ok)

            wrapper_type = self._json_parse_function_type(wrapper_name, field_type)
            source_name = self._fmt_source_type_name(field_type, struct_type.name, index)
            wrapper = self._fmt_generate_json_parse_wrapper(wrapper_name, field_type, source_name)
            if wrapper is None:
                wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
            nested_struct = self._fmt_parse_wrapper_may_throw(field_type)
            value = self.builder.call(wrapper, [raw], name=f'_json_{field_name}')
            if nested_struct:
                self._emit_throw_check_after_call()
                if self.builder is None or self.builder.block.is_terminated:
                    continue
            if value.type != field_type:
                value = self._coerce_value(value, field_type)
            field_ptr = self.builder.gep(result, [ir.Constant(i32, 0), ir.Constant(i32, index)], inbounds=True)
            self.builder.store(value, field_ptr)

        if self.builder is not None and not self.builder.block.is_terminated:
            self.builder.ret(result)
        popped_throw_exit = self._function_throw_exit_stack.pop()
        if not popped_throw_exit.is_terminated:
            self.builder.position_at_start(popped_throw_exit)
            self.builder.ret(ir.Constant(result_type, None))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        return func

    def _msgpack_call_blob_returning_function(self, func: ir.Function, args: list[ir.Value], name: str) -> ir.Value:
        blob_type = self.structs['Blob']
        if isinstance(func.function_type.return_type, ir.VoidType):
            ret_slot = self.builder.alloca(blob_type, name=f'{name}_slot')
            self.builder.call(func, [ret_slot] + args)
            return self.builder.load(ret_slot, name=name)
        return self.builder.call(func, args, name=name)

    def _gen_msgpack_encode_struct_function(self, func_name: str, struct_type: ir.IdentifiedStructType) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(self.structs['Blob'], [ir.PointerType(struct_type)]), func_name)

        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        blob_type = self.structs['Blob']
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names

        entry = func.append_basic_block('entry')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}

        field_names = self.struct_fields.get(struct_type.name, [])
        field_count = len(field_names)
        if field_count > 0:
            key_array_type = ir.ArrayType(i8_ptr, field_count)
            value_array_type = ir.ArrayType(blob_type, field_count)
            keys = self.builder.alloca(key_array_type, name='_msgpack_keys')
            values = self.builder.alloca(value_array_type, name='_msgpack_values')
            keys_ptr = self.builder.gep(keys, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
            values_ptr = self.builder.gep(values, [ir.Constant(i32, 0), ir.Constant(i32, 0)], inbounds=True)
        else:
            keys_ptr = ir.Constant(ir.PointerType(i8_ptr), None)
            values_ptr = ir.Constant(ir.PointerType(blob_type), None)

        for index, field_name in enumerate(field_names):
            key_slot = self.builder.gep(keys, [ir.Constant(i32, 0), ir.Constant(i32, index)], inbounds=True)
            self.builder.store(self._make_global_string(field_name, prefix='_msgpack_key'), key_slot)

            field_type = struct_type.elements[index]
            field_ptr = self.builder.gep(func.args[0], [ir.Constant(i32, 0), ir.Constant(i32, index)], inbounds=True)
            field_value = self.builder.load(field_ptr, name=f'_msgpack_{field_name}')
            wrapper_name = self._msgpack_encode_field_function_name(field_type, struct_type.name, index)
            wrapper_type = self._msgpack_encode_function_type(wrapper_name, field_type)
            source_name = self._msgpack_source_type_name(field_type, struct_type.name, index)
            wrapper = self._fmt_generate_msgpack_encode_wrapper(wrapper_name, field_type, source_name)
            if wrapper is None:
                wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
            field_value = self._fmt_arg_for_wrapper(field_value, wrapper_type.args[-1])
            encoded = self._msgpack_call_blob_returning_function(wrapper, [field_value], name=f'_msgpack_{field_name}_blob')
            value_slot = self.builder.gep(values, [ir.Constant(i32, 0), ir.Constant(i32, index)], inbounds=True)
            self.builder.store(encoded, value_slot)

        helper_arg_types = [i64, ir.PointerType(i8_ptr), ir.PointerType(blob_type)]
        if self._uses_c_sret(blob_type):
            helper_type = ir.FunctionType(ir.VoidType(), [ir.PointerType(blob_type)] + helper_arg_types)
        else:
            helper_type = ir.FunctionType(blob_type, helper_arg_types)
        helper = self._get_or_declare_function('__ez_msgpack_encode_map', helper_type)
        result = self._msgpack_call_blob_returning_function(
            helper,
            [ir.Constant(i64, field_count), keys_ptr, values_ptr],
            name='_msgpack_struct_blob',
        )
        self.builder.ret(result)

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        return func

    def _msgpack_decode_validator_name(self, func_name: str) -> str | None:
        prefix = 'msgpackDecode_'
        if not func_name.startswith(prefix):
            return None
        suffix = func_name[len(prefix):]
        if suffix == 'I1':
            suffix = 'Bool'
        if suffix in {'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str', 'Bool'}:
            return f'__ez_msgpack_valid_{suffix}'
        return None

    def _gen_msgpack_decode_struct_function(self, func_name: str, struct_type: ir.IdentifiedStructType) -> ir.Function:
        existing = self.module.globals.get(func_name)
        if isinstance(existing, ir.Function):
            if len(existing.blocks) > 0:
                return existing
            func = existing
        else:
            func = ir.Function(self.module, ir.FunctionType(ir.PointerType(struct_type), [ir.PointerType(self.structs['Blob'])]), func_name)

        i1 = ir.IntType(1)
        i8 = ir.IntType(8)
        i32 = ir.IntType(32)
        i64 = ir.IntType(64)
        i8_ptr = ir.PointerType(i8)
        blob_type = self.structs['Blob']
        blob_ptr = ir.PointerType(blob_type)
        result_type = ir.PointerType(struct_type)
        func.args[0].name = 'data'

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_unsigned = self._save_unsigned_state()

        entry = func.append_basic_block('entry')
        throw_exit = func.append_basic_block('throw_exit')
        self.builder = ir.IRBuilder(entry)
        self.current_function = func
        self.locals = {}
        self._locals_type_names = {}
        self._function_throw_exit_stack.append(throw_exit)

        def require_msgpack_ok(ok: ir.Value) -> None:
            fail_bb = self.builder.append_basic_block('msgpack_decode_invalid')
            cont_bb = self.builder.append_basic_block('msgpack_decode_valid')
            self.builder.cbranch(ok, cont_bb, fail_bb)
            self.builder.position_at_start(fail_bb)
            self._raise_error(4, 'msgpack decode failed')
            self.builder.position_at_start(cont_bb)

        result = self._arena_allocate(struct_type, name=f'_msgpack_{struct_type.name}_value')
        self.builder.store(self._zero_constant(struct_type), result)

        valid_map = self._get_or_declare_function('__ez_msgpack_valid_map', ir.FunctionType(i1, [blob_ptr]))
        map_ok = self.builder.call(valid_map, [func.args[0]], name='_msgpack_map_ok')
        require_msgpack_ok(map_ok)

        field_names = self.struct_fields.get(struct_type.name, [])
        field_count_fn = self._get_or_declare_function('__ez_msgpack_map_field_count', ir.FunctionType(i64, [blob_ptr]))
        field_count = self.builder.call(field_count_fn, [func.args[0]], name='_msgpack_map_field_count')
        field_count_ok = self.builder.icmp_signed('==', field_count, ir.Constant(i64, len(field_names)), name='_msgpack_map_field_count_ok')
        require_msgpack_ok(field_count_ok)

        if self._uses_c_sret(blob_type):
            field_fn_type = ir.FunctionType(ir.VoidType(), [blob_ptr, blob_ptr, i8_ptr])
        else:
            field_fn_type = ir.FunctionType(blob_type, [blob_ptr, i8_ptr])
        field_fn = self._get_or_declare_function('__ez_msgpack_map_field', field_fn_type)

        for index, field_name in enumerate(field_names):
            key = self._make_global_string(field_name, prefix='_msgpack_key')
            field_blob_ptr = self.builder.alloca(blob_type, name=f'_msgpack_{field_name}_blob_ptr')
            if self._uses_c_sret(blob_type):
                self.builder.call(field_fn, [field_blob_ptr, func.args[0], key])
            else:
                raw_blob = self.builder.call(field_fn, [func.args[0], key], name=f'_msgpack_{field_name}_raw')
                self.builder.store(raw_blob, field_blob_ptr)
            size_ptr = self.builder.gep(field_blob_ptr, [ir.Constant(i32, 0), ir.Constant(i32, 1)], inbounds=True)
            size = self.builder.load(size_ptr, name=f'_msgpack_{field_name}_size')
            found = self.builder.icmp_signed('>=', size, ir.Constant(i64, 0), name=f'_msgpack_{field_name}_found')
            require_msgpack_ok(found)

            field_type = struct_type.elements[index]
            wrapper_name = self._msgpack_decode_field_function_name(field_type, struct_type.name, index)
            validator_name = self._msgpack_decode_validator_for_value(wrapper_name, field_type)
            validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [blob_ptr]))
            value_ok = self.builder.call(validator, [field_blob_ptr], name=f'_msgpack_{field_name}_ok')
            require_msgpack_ok(value_ok)

            wrapper_type = self._msgpack_decode_function_type(wrapper_name, field_type)
            source_name = self._msgpack_source_type_name(field_type, struct_type.name, index)
            wrapper = self._fmt_generate_msgpack_decode_wrapper(wrapper_name, field_type, source_name)
            if wrapper is None:
                wrapper = self._get_or_declare_function(wrapper_name, wrapper_type)
            nested_struct = self._fmt_parse_wrapper_may_throw(field_type)
            value = self.builder.call(wrapper, [field_blob_ptr], name=f'_msgpack_{field_name}')
            if nested_struct:
                self._emit_throw_check_after_call()
                if self.builder is None or self.builder.block.is_terminated:
                    continue
            if value.type != field_type:
                value = self._coerce_value(value, field_type)
            field_ptr = self.builder.gep(result, [ir.Constant(i32, 0), ir.Constant(i32, index)], inbounds=True)
            self.builder.store(value, field_ptr)

        if self.builder is not None and not self.builder.block.is_terminated:
            self.builder.ret(result)
        popped_throw_exit = self._function_throw_exit_stack.pop()
        if not popped_throw_exit.is_terminated:
            self.builder.position_at_start(popped_throw_exit)
            self.builder.ret(ir.Constant(result_type, None))

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._restore_unsigned_state(old_unsigned)
        return func

    def _append_json_literal_segment(self, segments: list[tuple[ir.Value, ir.Value]], text: str) -> None:
        segments.append((self._make_global_string(text, prefix='_json_seg'), ir.Constant(ir.IntType(64), len(bytearray(text, 'utf-8')))))

    def _join_c_string_segments(self, segments: list[tuple[ir.Value, ir.Value]], name_prefix: str = '_str_join') -> ir.Value:
        i8 = ir.IntType(8)
        i64 = ir.IntType(64)
        memcpy = self.module.get_global('llvm.memcpy.p0.p0.i64')

        total_len = ir.Constant(i64, 0)
        for _, seg_len in segments:
            total_len = self.builder.add(total_len, seg_len, name=f'{name_prefix}_total')
        alloc_len = self.builder.add(total_len, ir.Constant(i64, 1), name=f'{name_prefix}_alloc_len')
        buf_base = self.builder.call(self._arena_alloc, [alloc_len, ir.Constant(i64, 1)], name=f'{name_prefix}_buf')

        pos = ir.Constant(i64, 0)
        for src, seg_len in segments:
            dst_ptr = self.builder.gep(buf_base, [pos], inbounds=True)
            self.builder.call(memcpy, [dst_ptr, src, seg_len, ir.Constant(ir.IntType(1), 0)])
            pos = self.builder.add(pos, seg_len, name=f'{name_prefix}_pos')

        null_ptr = self.builder.gep(buf_base, [pos], inbounds=True)
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
            ptr = self._make_global_string(decode_string_literal_token(text))
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
            text = decode_string_literal_token(lit.STRING_LITERAL().getText())
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
        if id_token is None and ctx.VOID() is not None:
            return ir.Constant(ir.IntType(32), self._type_id("Void"))
        name = id_token.getText()

        # 泛型实例化: func<T1, T2>
        if ctx.genericArgs() is not None:
            type_arg_ctxs = list(ctx.genericArgs().type_())
            type_args = [self._map_type(t) for t in type_arg_ctxs]
            name = self._monomorphize(
                name,
                type_args,
                [self._type_ctx_suffix(t) for t in type_arg_ctxs],
                [self._type_ctx_is_unsigned(t) for t in type_arg_ctxs],
                [self._type_ctx_name(t) for t in type_arg_ctxs],
            )

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
            if name in self._decorated_globals and self._is_meta_type(gv.type.pointee):
                return self._emit_lock_access(name, "read", lambda: self._load_decorated_global(name, gv))
            if isinstance(gv.type.pointee, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
                return gv
            return self._emit_lock_access(name, "read", lambda: self._load_with_unsigned(gv, name=name))
        if name in self.structs or name in self.type_aliases or name in {"I8", "I32", "I64", "U8", "U32", "U64", "F32", "F64", "Str", "Bool", "Void", "List", "Dict", "Vec"}:
            return ir.Constant(ir.IntType(32), self._type_id(name))
        return ir.Constant(ir.IntType(32), 0)

    def _monomorphize(self, base_name: str, type_args: list[ir.Type],
                      type_suffixes: list[str] | None = None,
                      type_arg_unsigned: list[bool] | None = None,
                      type_source_names: list[str] | None = None) -> str:
        """为泛型函数生成特定类型的单态化版本"""
        suffix = '_'.join(type_suffixes if type_suffixes is not None else [self._type_name(t) for t in type_args])
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
        # 创建类型替换映射
        type_map = dict(zip(param_names, type_args))
        unsigned_map = dict(zip(param_names, type_arg_unsigned or [False] * len(param_names)))

        # 判断是否为泛型 declare（GenericParamFunctionTypeContext）
        if hasattr(template_ctx, 'paramTypeList'):
            # 泛型 declare：只生成外部函数声明（无函数体）
            fmt_source_names = type_source_names or type_suffixes
            if len(type_args) == 1 and self._fmt_monomorphize_top_level_list(base_name, mono_name, type_args[0], fmt_source_names):
                return mono_name

            if len(type_args) == 1 and self._fmt_monomorphize_top_level_optional(base_name, mono_name, type_args[0], fmt_source_names):
                return mono_name

            if len(type_args) == 1 and self._fmt_monomorphize_top_level_dict(base_name, mono_name, type_args[0], fmt_source_names):
                return mono_name

            if len(type_args) == 1 and self._fmt_monomorphize_top_level_union(base_name, mono_name, type_args[0], fmt_source_names):
                return mono_name

            if base_name == 'jsonStringify' and len(type_args) == 1 and self._json_stringify_struct_supported(type_args[0]):
                self._gen_json_stringify_struct_function(mono_name, type_args[0])
                self.func_param_names[mono_name] = ['data']
                self.func_return_unsigned[mono_name] = False
                return mono_name

            if base_name == 'jsonParse' and len(type_args) == 1 and self._json_parse_struct_supported(type_args[0]):
                self._gen_json_parse_struct_function(mono_name, type_args[0])
                self.func_param_names[mono_name] = ['s']
                self.func_return_unsigned[mono_name] = False
                return mono_name

            if base_name == 'msgpackEncode' and len(type_args) == 1 and self._msgpack_encode_struct_supported(type_args[0]):
                self._gen_msgpack_encode_struct_function(mono_name, type_args[0])
                self.func_param_names[mono_name] = ['data']
                self.func_return_unsigned[mono_name] = False
                return mono_name

            if base_name == 'msgpackDecode' and len(type_args) == 1 and self._msgpack_decode_struct_supported(type_args[0]):
                self._gen_msgpack_decode_struct_function(mono_name, type_args[0])
                self.func_param_names[mono_name] = ['data']
                self.func_return_unsigned[mono_name] = False
                return mono_name

            gen_ctx = template_ctx
            ret_type = self._map_type_with_map(gen_ctx.type_(), type_map)
            self.func_return_unsigned[mono_name] = self._type_ctx_is_unsigned_with_map(gen_ctx.type_(), unsigned_map)
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
                    orig_param_names.append(pname)
                    param_types.append(self._c_abi_param_type(ptype))

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
        self.func_return_unsigned[mono_name] = self._type_ctx_is_unsigned_with_map(fn_lit.type_(), unsigned_map)
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
            prev_unsigned = self._save_unsigned_state()
            prev_codegen_state = self._enter_function_codegen_state(ir.IRBuilder(entry), func)
            type_name_map = dict(zip(param_names, type_suffixes or [self._type_name_from_ir_type_with_unsigned(t, unsigned_map.get(name, False)) for name, t in zip(param_names, type_args)]))
            self._generic_type_map_stack.append((type_map, unsigned_map, type_name_map))
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

            self._restore_function_codegen_state(prev_codegen_state)
            self._restore_unsigned_state(prev_unsigned)

        return mono_name

    def _map_type_with_map(self, ctx, type_map: dict[str, ir.Type],
                           unsigned_map: dict[str, bool] | None = None,
                           type_name_map: dict[str, str] | None = None) -> ir.Type:
        prev_mapping = self._mapping_with_map
        self._mapping_with_map = True
        try:
            return self._map_type_with_map_impl(ctx, type_map, unsigned_map or {}, type_name_map or {})
        finally:
            self._mapping_with_map = prev_mapping

    def _map_type_with_map_impl(self, ctx, type_map: dict[str, ir.Type],
                                unsigned_map: dict[str, bool],
                                type_name_map: dict[str, str]) -> ir.Type:
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
                    type_args = [self._map_type_with_map(t, type_map, unsigned_map, type_name_map) for t in args]
                    type_arg_unsigned = [self._type_ctx_is_unsigned_with_map(t, unsigned_map) for t in args]
                    type_arg_names = [self._type_ctx_name_with_map(t, type_map, unsigned_map, type_name_map) for t in args]
                    mono_name = self._monomorphize_struct(name, type_args, type_arg_unsigned, type_arg_names)
                    return self.structs.get(mono_name, self.structs.get(name, ir.IntType(32)))
                if name == 'Dict':
                    return self.structs['Dict']
                if name == 'List':
                    inner = self._map_type_with_map(args[0], type_map, unsigned_map, type_name_map) if args else ir.IntType(32)
                    return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])
                if name == 'Meta':
                    inner = self._map_type_with_map(args[0], type_map, unsigned_map, type_name_map) if args else ir.IntType(32)
                    return self._get_meta_type(inner)
            return self._map_type(ctx)

        # 可选类型: T? → {i1, T}
        if isinstance(ctx, P.OptionalTypeContext):
            inner = self._map_type_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)
            if self._struct_type_build_stack and inner == self.structs.get(self._struct_type_build_stack[-1]):
                inner = ir.PointerType(inner)
            return ir.LiteralStructType([ir.IntType(1), inner])

        if isinstance(ctx, P.WeakTypeContext):
            inner = self._map_type_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)
            return ir.LiteralStructType([ir.IntType(1), ir.PointerType(inner)])

        # List 类型: List<T> → { pages, length, capacity, page_count }
        if isinstance(ctx, P.ListTypeContext):
            inner = self._map_type_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)
            return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])

        # 数组类型: T[] → { pages, length, capacity, page_count }
        if isinstance(ctx, P.ArrayTypeContext):
            inner = self._map_type_with_map(ctx.type_(), type_map, unsigned_map, type_name_map)
            return ir.LiteralStructType([ir.PointerType(ir.PointerType(inner)), ir.IntType(64), ir.IntType(64), ir.IntType(64)])

        if isinstance(ctx, P.UnionTypeContext):
            types = [self._map_type_with_map(t, type_map, unsigned_map, type_name_map) for t in self._union_type_ctxs(ctx)]
            max_type = max(types, key=lambda t: self._type_width(t))
            return ir.LiteralStructType([ir.IntType(32), max_type])

        if isinstance(ctx, P.FunctionTypeRefContext):
            fn_ctx = ctx.functionType()
            ret_type = self._map_type_with_map(fn_ctx.type_(), type_map, unsigned_map, type_name_map)
            param_types = []
            ptl = fn_ctx.paramTypeList()
            if ptl is not None:
                for p in ptl.paramType():
                    param_types.append(self._map_type_with_map(p.type_(), type_map, unsigned_map, type_name_map))
            return self._closure_type(ret_type, param_types)

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
            type_arg_ctxs = list(generic_args.type_())
            type_args = [self._map_type(t) for t in type_arg_ctxs]
            func_name = self._monomorphize(
                func_name,
                type_args,
                [self._type_ctx_suffix(t) for t in type_arg_ctxs],
                [self._type_ctx_is_unsigned(t) for t in type_arg_ctxs],
                [self._type_ctx_name(t) for t in type_arg_ctxs],
            )
        result = self._gen_pipeline_function_call(func_name, left, ctx.pipelineArgList())
        if result is None:
            return left
        return result

    def _gen_pipeline_function_call(self, func_name: str, pipe_val: ir.Value, arg_list) -> ir.Value | None:
        """生成管道调用，按函数形参名重排并注入默认参数。"""
        try:
            func = self.module.get_global(func_name)
        except KeyError:
            return None
        if func is None or not isinstance(func, ir.Function):
            return None

        expected_names = self.func_param_names.get(func_name, [])
        defaults = self.func_defaults.get(func_name, {})
        provided: dict[str, ir.Value] = {}
        positional_args: list[ir.Value] = []
        has_percent = False

        if arg_list is not None:
            for a in arg_list.pipelineArg():
                if a.VAR_IDENTIFIER() is None:
                    continue
                pname = a.VAR_IDENTIFIER().getText()
                if a.PERCENT() is not None:
                    provided[pname] = pipe_val
                    positional_args.append(pipe_val)
                    has_percent = True
                elif a.expression() is not None:
                    val = self._eval(a.expression())
                    if val is not None:
                        provided[pname] = val
                        positional_args.append(val)

        call_args: list[ir.Value] = []
        if expected_names:
            if not has_percent:
                provided[expected_names[0]] = pipe_val
            for pname in expected_names:
                if pname in provided:
                    call_args.append(provided[pname])
                elif pname in defaults:
                    default_value = self._eval(defaults[pname])
                    call_args.append(default_value if default_value is not None else ir.Constant(ir.IntType(32), 0))
                else:
                    call_args.append(ir.Constant(ir.IntType(32), 0))
        else:
            call_args = list(positional_args)
            if not has_percent:
                call_args.insert(0, pipe_val)

        intrinsic_result = self._try_gen_intrinsic_call(func_name, call_args)
        if intrinsic_result is not None:
            if intrinsic_result is self._void_intrinsic_result:
                return None
            return intrinsic_result

        func_type = func.type.pointee if isinstance(func.type, ir.PointerType) else None
        sret_type = self._sret_functions.get(func_name)
        abi_arg_types = list(func_type.args) if func_type is not None else []
        if sret_type is not None:
            ret_slot = self._arena_allocate(sret_type, name=f"_{func_name}_ret")
            call_args = [ret_slot] + call_args

        if func_type is not None:
            call_args = [
                self._coerce_call_arg(arg, abi_arg_types[i]) if i < len(abi_arg_types) else arg
                for i, arg in enumerate(call_args)
            ]
            call_args = [
                self._load_if_aggregate_ptr(arg)
                if i < len(abi_arg_types) and arg.type != abi_arg_types[i] and self._is_aggregate_ptr(arg)
                else arg
                for i, arg in enumerate(call_args)
            ]

        self._json_parse_validate_or_throw(func_name, call_args)
        if self.builder is not None and self.builder.block.is_terminated:
            return self._zero_constant(func_type.return_type if func_type is not None else ir.IntType(32))

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
                fname = self._field_name_text(init_ctx)
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

                fname = self._field_name_text(init_ctx)
                if fname in field_names and init_ctx.expression() is not None:
                    val = precomputed_values.get(id(init_ctx))
                    if val is None:
                        field_type = struct_type.elements[field_names.index(fname)]
                        val = self._eval_expr_with_expected(init_ctx.expression(), field_type)
                    _set_field(fname, val)
                    provided_fields.add(fname)

        # 对未提供的字段应用默认值
        defaults = self.struct_defaults.get(name, {})
        for fname, default_expr in defaults.items():
            if fname not in provided_fields:
                val = self._eval(default_expr)
                _set_field(fname, val)

        if name == 'Error':
            file_value, line_value, column_value, trace_value = self._error_location_values(ctx)
            default_error_fields = {
                'file': file_value,
                'line': line_value,
                'column': column_value,
                'trace': trace_value,
            }
            for fname, val in default_error_fields.items():
                if fname not in provided_fields:
                    _set_field(fname, val)
                    provided_fields.add(fname)

        return alloca

    def visitStructLiteralExpr(self, ctx: EzLangParser.StructLiteralExprContext):
        return self.visitStructLiteral(ctx.structLiteral())

    def _optional_safe_member_access(self, optional_ctx, field_name: str) -> ir.Value | None:
        """生成 opt?.field：空值返回空可选，非空时读取字段并包装。"""
        opt_val = self._eval(optional_ctx.postfixExpression())
        if opt_val is None or not hasattr(opt_val, 'type'):
            return None
        opt_type = opt_val.type.pointee if isinstance(opt_val.type, ir.PointerType) else opt_val.type
        is_weak = self._is_weak_ref_type(opt_type)
        if not self._is_optional_type(opt_type):
            return None
        value_type = opt_type.elements[1].pointee if is_weak else opt_type.elements[1]
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
        if is_weak:
            value_ptr = self.builder.load(value_ptr, name='_weak_chain_ptr')
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
            for raw_name, expr_ctx in self._call_arg_items(args):
                if raw_name is None or expr_ctx is None:
                    continue
                fname = raw_name
                val = self._eval(expr_ctx)
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
        if args is not None:
            positional_index = 0
            for raw_name, expr_ctx in self._call_arg_items(args):
                if expr_ctx is None:
                    continue
                if raw_name is None:
                    if positional_index >= len(field_names):
                        continue
                    fname = field_names[positional_index]
                    positional_index += 1
                else:
                    fname = raw_name
                val = precomputed_values.get(fname)
                if val is None:
                    field_type = struct_type.elements[field_names.index(fname)] if fname in field_names else None
                    val = self._eval_expr_with_expected(expr_ctx, field_type)
                _set_field(fname, val)
                provided.add(fname)

        if struct_name == 'Error':
            file_value, line_value, column_value, trace_value = self._error_location_values(call_ctx)
            default_error_fields = {
                'file': file_value,
                'line': line_value,
                'column': column_value,
                'trace': trace_value,
            }
            for fname, val in default_error_fields.items():
                if fname not in provided:
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
        field_name = self._field_name_text(ctx)
        static_struct_name = self._static_struct_member_owner(ctx.postfixExpression())
        if static_struct_name is not None:
            methods = self.struct_methods.get(static_struct_name, {})
            func_name = methods.get(field_name)
            if func_name is not None:
                try:
                    return self.module.get_global(func_name)
                except KeyError:
                    return None

        if isinstance(ctx.postfixExpression(), EzLangParser.OptionalUnwrapContext):
            safe_value = self._optional_safe_member_access(ctx.postfixExpression(), field_name)
            if safe_value is not None:
                return safe_value

        obj_ptr = self._eval(ctx.postfixExpression())
        if obj_ptr is None:
            return None
        if self._member_target_is_weak_ref(ctx.postfixExpression()):
            obj_ptr = self._weak_ref_pointee_ptr(obj_ptr) or obj_ptr
        if (
            not isinstance(obj_ptr.type, ir.PointerType)
            and isinstance(obj_ptr.type, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType))
        ):
            tmp = self.builder.alloca(obj_ptr.type, name='_member_tmp')
            self.builder.store(obj_ptr, tmp)
            obj_ptr = tmp

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
                func_name = methods[field_name]
                if struct_name == 'Date':
                    func = self._get_or_declare_date_method(func_name)
                else:
                    func = self.module.get_global(func_name)
                if func is not None:
                    self._method_this = self._weak_ref_value(obj_ptr, obj_ptr.type.pointee)
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
                    self._method_this = self._weak_ref_value(obj_ptr, obj_ptr.type.pointee)
                return value

        return None

    def _member_target_is_weak_ref(self, ctx) -> bool:
        """判断成员访问接收者在语言层是否是弱引用，避免把 Optional<Struct> 误当 #Struct。"""
        if isinstance(ctx, EzLangParser.WeakRefExpressionContext):
            return True
        ident = self._leftmost_identifier_ctx(ctx)
        if ident is not None and ident.getText() == ctx.getText():
            token = ident.VAR_IDENTIFIER() or ident.TYPE_IDENTIFIER()
            name = token.getText() if token is not None else ""
            type_name = self._locals_type_names.get(name) or self._globals_type_names.get(name)
            return bool(type_name and type_name.startswith('#'))
        return False

    def _static_struct_member_owner(self, ctx) -> str | None:
        """识别 StructName.method 这种类型级结构体成员访问。"""
        primary = ctx.primaryExpression() if hasattr(ctx, 'primaryExpression') else None
        if primary is None or not isinstance(primary, EzLangParser.IdentifierExprContext):
            return None
        token = primary.TYPE_IDENTIFIER()
        if token is None:
            return None
        name = token.getText()
        return name if name in self.structs or name in self.struct_generic_templates else None

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
                if self._is_aggregate_ptr(v):
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

    def _shape_field_names(self, shape_type: ir.Type) -> list[str]:
        if isinstance(shape_type, ir.IdentifiedStructType):
            return self.struct_fields.get(shape_type.name, [])
        return []

    def _gen_shape_literal(self, ctx: EzLangParser.DictLiteralContext, shape_type: ir.Type):
        field_names = self._shape_field_names(shape_type)
        if not field_names:
            return None
        alloca = self._arena_allocate(shape_type, name="_tmp_shape")
        self.builder.store(self._zero_constant(shape_type), alloca)
        fields = ctx.dictField() if ctx.dictField() else []
        for field in fields:
            field_name = self._dict_key_text(field)
            if field_name not in field_names:
                continue
            index = field_names.index(field_name)
            if index >= len(shape_type.elements):
                continue
            field_type = shape_type.elements[index]
            val = self._eval_expr_with_expected(field.expression(), field_type)
            if val is None:
                continue
            if self._is_aggregate_ptr(val) and val.type.pointee == field_type:
                val = self.builder.load(val)
            if val.type != field_type:
                val = self._coerce_preserve_unsigned(val, field_type)
            ptr = self.builder.gep(alloca, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), index),
            ], inbounds=True)
            self.builder.store(val, ptr)
        return alloca

    def visitDictLiteral(self, ctx: EzLangParser.DictLiteralContext):
        """字典字面量 { key: Type = value } → Dict 分页结构"""
        fields = ctx.dictField() if ctx.dictField() else []
        expected_type = self._expected_expr_type()
        if isinstance(expected_type, (ir.IdentifiedStructType, ir.LiteralStructType)) and expected_type != self.structs['Dict']:
            return self._gen_shape_literal(ctx, expected_type)

        dict_type = self.structs['Dict']
        alloca = self._arena_allocate(dict_type, name="_tmp_dict")
        self.builder.store(self._zero_constant(dict_type), alloca)
        expected_item_types = self._expected_dict_item_types()
        key_type = expected_item_types[0] if expected_item_types is not None else ir.PointerType(ir.IntType(8))
        value_type = expected_item_types[1] if expected_item_types is not None else ir.PointerType(ir.IntType(8))
        saw_value_type = expected_item_types is not None
        for f in fields:
            key = self._dict_key_value(f)
            if key.type != key_type:
                key = self._coerce_preserve_unsigned(key, key_type)
            if expected_item_types is None and key.type != ir.PointerType(ir.IntType(8)):
                key_type = key.type
            field_expected_type = self._map_type(f.type_()) if f.type_() is not None else (value_type if expected_item_types is not None else None)
            val = self._eval_expr_with_expected(f.expression(), field_expected_type)
            if isinstance(val, ir.AllocaInstr):
                val = self.builder.load(val)
            type_ctx = f.type_()
            if type_ctx is not None:
                annotated_type = self._map_type(type_ctx)
                value_type = annotated_type
                saw_value_type = True
                if val is not None and val.type != annotated_type:
                    val = self._coerce_preserve_unsigned(val, annotated_type)
            elif val is not None and not saw_value_type:
                value_type = val.type
                saw_value_type = True
            elif val is not None and val.type != value_type:
                val = self._coerce_preserve_unsigned(val, value_type)
            self._gen_dict_set(alloca, key, val)
        self._mark_dict_item_types(alloca, key_type, value_type)
        return alloca

    def visitDictExpr(self, ctx: EzLangParser.DictExprContext):
        return self.visitDictLiteral(ctx.dictLiteral())

    # ==================== 占位符 ====================

    def visitPlaceholderExpr(self, ctx: EzLangParser.PlaceholderExprContext):
        """? 在 Optional<T> 期望上下文中表示空值；调用实参中仍作为柯里化占位符。"""
        expected_type = self._expected_expr_type()
        if expected_type is not None and self._is_optional_type(expected_type):
            return self._optional_value(expected_type.elements[1], False)
        self._extern_diagnostics.append(
            f"行 {ctx.start.line}: '?' 只能作为函数调用的柯里化占位参数使用"
        )
        # 错误恢复：返回零值让后续 IR 构造继续完成，诊断会阻止产物被当作成功编译。
        return ir.Constant(ir.IntType(32), 0)

    # ==================== 标记字面量 ====================

    def visitMarkupExpr(self, ctx: EzLangParser.MarkupExprContext):
        return self.visitMarkupLiteral(ctx.markupLiteral())

    def _markup_attr_value(self, attr) -> ir.Value | None:
        if attr.expression() is not None:
            return self._eval(attr.expression())
        if attr.STRING_LITERAL() is not None:
            text = decode_string_literal_token(attr.STRING_LITERAL().getText())
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
            return self._make_global_string(decode_string_literal_token(child.STRING_LITERAL().getText()), prefix="_markup_child")
        return None

    def _markup_children_expected_elem_type(self, expected_type: ir.Type | None) -> ir.Type | None:
        if expected_type is None:
            return None
        if isinstance(expected_type, ir.PointerType):
            expected_type = expected_type.pointee
        if self._is_list_type(expected_type):
            return expected_type.elements[0].pointee.pointee
        return None

    def _markup_children_expected_elem_ctx(self, expected_ctx):
        if expected_ctx is None:
            return None
        if isinstance(expected_ctx, (EzLangParser.ArrayTypeContext, EzLangParser.ListTypeContext)):
            elem_ctx = expected_ctx.type_()
            while isinstance(elem_ctx, EzLangParser.ParenTypeContext):
                elem_ctx = elem_ctx.type_()
            return elem_ctx
        return None

    def _markup_children_array(self, children, expected_type: ir.Type | None = None,
                               line: int | None = None, expected_elem_ctx=None) -> ir.Value:
        values = []
        for child in children:
            value = self._markup_child_value(child)
            if value is None:
                continue
            if isinstance(value, ir.AllocaInstr):
                value = self.builder.load(value)
            values.append((child, value))

        elem_type = self._markup_children_expected_elem_type(expected_type)
        if elem_type is None:
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
                if expected_elem_ctx is not None and isinstance(expected_elem_ctx, EzLangParser.UnionTypeContext) and self._is_union_type(elem_type):
                    coerced = self._coerce_union_value(value, elem_type, self._union_variant_tag(expected_elem_ctx, value.type))
                else:
                    coerced = self._coerce_value(value, elem_type)
                if coerced.type != elem_type:
                    self._extern_diagnostics.append(
                        f"行 {line or child.start.line}: 参数 'children' 类型不匹配"
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
        expected_type_ctxs = self.func_param_type_ctxs.get(tag_name, [])
        expected_name_set = set(expected_names)
        provided = {}
        for attr in ctx.markupAttr():
            attr_name = attr.VAR_IDENTIFIER().getText()
            value = self._markup_attr_value(attr)
            if value is not None:
                provided[attr_name] = value
        for pname in provided:
            if pname not in expected_name_set:
                self._extern_diagnostics.append(f"行 {ctx.start.line}: 未知参数 '{pname}'")
        if ctx.markupChild() and 'children' not in expected_name_set:
            self._extern_diagnostics.append(f"行 {ctx.start.line}: 未知参数 'children'")

        call_args = []
        defaults = self.func_defaults.get(tag_name, {})
        abi_arg_types = list(func.function_type.args)
        if expected_names:
            for index, pname in enumerate(expected_names):
                param_type = abi_arg_types[index] if index < len(abi_arg_types) else ir.IntType(32)
                if pname == 'children' and ctx.markupChild() and pname in expected_name_set:
                    param_ctx = expected_type_ctxs[index] if index < len(expected_type_ctxs) else None
                    expected_elem_ctx = self._markup_children_expected_elem_ctx(param_ctx)
                    provided[pname] = self._markup_children_array(
                        ctx.markupChild(), param_type, ctx.start.line, expected_elem_ctx
                    )
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
                for arg_name, expr_ctx in self._call_arg_items(args_ctx):
                    if arg_name != 'pl' or expr_ctx is None:
                        continue
                    array_expr = expr_ctx.getText().strip()
                    array_ctx = expr_ctx
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

        def legacy_race_hook():
            return self.builder.call(self._flow_race, [task_arg, timeout_arg])

        if pl_array is None:
            return legacy_race_hook()

        async_result = self._gen_race_i32_runtime_call(pl_array, timeout_arg)
        if async_result is not None:
            return async_result

        branches = self._function_literals_in_array(pl_array)
        if not branches:
            return legacy_race_hook()
        first_branch = branches[0]
        params = first_branch.paramList()
        if params is not None and params.param():
            return legacy_race_hook()

        branch_types = [self._infer_function_literal_return_type(branch) for branch in branches]
        first_branch_type = branch_types[0]
        result_type = self._merge_ir_union_types(branch_types)
        if isinstance(result_type, ir.VoidType):
            return legacy_race_hook()
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
            if branch_value is not None and not isinstance(first_branch_type, ir.VoidType):
                if self._is_aggregate_ptr(branch_value):
                    branch_value = self.builder.load(branch_value)
                if self._is_union_type(result_type):
                    tag = self._ir_union_variant_tag_for_types(result_type, branch_types, branch_value.type)
                    branch_value = self._coerce_union_value(branch_value, result_type, tag)
                else:
                    branch_value = self._coerce_value(branch_value, result_type)
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

    def _gen_parallel_i32_branch_function(self, block_ctx, env_type: ir.Type, metadata: list[dict]) -> ir.Function:
        """生成带捕获环境的 parallel I32 分支函数。"""
        i8_ptr = ir.PointerType(ir.IntType(8))
        i32 = ir.IntType(32)
        name = f"__ez_parallel_branch_{self._parallel_branch_counter}"
        self._parallel_branch_counter += 1
        func = ir.Function(self.module, ir.FunctionType(i32, [i8_ptr]), name)
        func.args[0].name = '__env'

        entry = func.append_basic_block('entry')
        prev_unsigned = self._save_unsigned_state()
        prev_state = self._enter_function_codegen_state(ir.IRBuilder(entry), func)
        self._flow_depth = max(prev_state.get('flow_depth', 0), 1)
        self._bind_capture_env_locals(func.args[0], env_type, metadata)
        throw_exit = func.append_basic_block('throw_exit')
        self._function_throw_exit_stack.append(throw_exit)
        self._function_return_type_ctx_stack.append(None)

        value = self._eval(block_ctx) if block_ctx is not None else ir.Constant(i32, 0)
        self._finish_function_with_throw_exit(i32, value)
        self._function_return_type_ctx_stack.pop()

        self._restore_function_codegen_state(prev_state)
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
        result_type = self._infer_block_return_type(parallel_block.block())
        if result_type != ir.IntType(32):
            return None
        capture_names = self._ctx_capture_names(parallel_block.block())
        for cap_name in capture_names:
            storage = self.locals.get(cap_name)
            if storage is not None and self._is_aggregate_ptr(storage):
                return None
        if capture_names:
            env_type, env_ptr, metadata = self._build_parallel_capture_env(capture_names)
            branch = self._gen_parallel_i32_branch_function(parallel_block.block(), env_type, metadata)
            self._require_runtime()
            i8_ptr = ir.PointerType(ir.IntType(8))
            start_type = ir.FunctionType(i8_ptr, [ir.PointerType(ir.FunctionType(ir.IntType(32), [i8_ptr])), i8_ptr])
            start = self._get_or_declare_function('__ezrt_task_start_env_i32', start_type)
            handle = self.builder.call(start, [branch, env_ptr], name=f'_{name}_future')
            self._flow_future_stack[-1][name] = {'handle': handle, 'joined': False}
            return handle
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

    def _function_literal_param_info(self, fn_lit) -> tuple[ir.Type, list[str], list[ir.Type]]:
        ret_type = self._map_type(fn_lit.type_()) if fn_lit.type_() is not None else self._infer_function_literal_return_type(fn_lit)
        param_names: list[str] = []
        param_types: list[ir.Type] = []
        params = fn_lit.paramList()
        if params is not None:
            for param in params.param():
                param_names.append(param.VAR_IDENTIFIER().getText())
                param_types.append(self._map_type(param.type_()) if param.type_() is not None else ir.IntType(32))
        return ret_type, param_names, param_types

    def _function_literal_capture_names(self, fn_lit, param_names: set[str]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()

        def add(name: str) -> None:
            if name in seen or name in param_names:
                return
            if name in self.locals:
                seen.add(name)
                names.append(name)

        def walk(node) -> None:
            if node is None:
                return
            if node is not fn_lit and isinstance(node, EzLangParser.FunctionLiteralContext):
                return
            if isinstance(node, EzLangParser.IdentifierExprContext):
                token = node.VAR_IDENTIFIER() or node.TYPE_IDENTIFIER()
                if token is not None:
                    add(token.getText())
                return
            if hasattr(node, 'getChildCount'):
                for i in range(node.getChildCount()):
                    walk(node.getChild(i))

        walk(fn_lit.block() or fn_lit.expression())
        return names

    def _ctx_capture_names(self, ctx, param_names: set[str] | None = None) -> list[str]:
        """收集后台任务体需要从外层捕获的局部变量。"""
        names: list[str] = []
        seen: set[str] = set()
        scopes: list[set[str]] = [set(param_names or set())]

        def is_local_declared(name: str) -> bool:
            return any(name in scope for scope in reversed(scopes))

        def declare_from_var_decl(node) -> None:
            qname = node.qualifiedVarName() if hasattr(node, 'qualifiedVarName') else None
            if qname is None:
                return
            parts = qname.VAR_IDENTIFIER()
            if len(parts) == 1:
                scopes[-1].add(parts[0].getText())

        def add(name: str) -> None:
            if name in seen or is_local_declared(name):
                return
            if name in self.locals:
                seen.add(name)
                names.append(name)

        def walk(node) -> None:
            if node is None:
                return
            if isinstance(node, EzLangParser.BlockContext):
                scopes.append(set())
                for stmt in node.statement():
                    walk(stmt)
                scopes.pop()
                return
            if isinstance(node, EzLangParser.FunctionLiteralContext):
                scopes.append(set())
                if node.paramList() is not None:
                    for param in node.paramList().param():
                        scopes[-1].add(param.VAR_IDENTIFIER().getText())
                        if param.expression() is not None:
                            walk(param.expression())
                walk(node.block() or node.expression())
                scopes.pop()
                return
            if isinstance(node, EzLangParser.VariableDeclContext):
                if node.expression() is not None:
                    walk(node.expression())
                declare_from_var_decl(node)
                return
            if isinstance(node, EzLangParser.FunctionDeclContext):
                return
            if isinstance(node, EzLangParser.ParamContext):
                if node.expression() is not None:
                    walk(node.expression())
                return
            if isinstance(node, EzLangParser.IdentifierExprContext):
                token = node.VAR_IDENTIFIER() or node.TYPE_IDENTIFIER()
                if token is not None:
                    add(token.getText())
                return
            if hasattr(node, 'getChildCount'):
                for i in range(node.getChildCount()):
                    walk(node.getChild(i))

        walk(ctx)
        return names

    def _build_parallel_capture_env(self, capture_names: list[str]) -> tuple[ir.Type, ir.Value, list[dict]]:
        capture_types: list[ir.Type] = []
        capture_values: list[ir.Value] = []
        metadata: list[dict] = []
        for name in capture_names:
            self._join_flow_future(name)
            storage = self._capture_shared_storage(name)
            if storage is None:
                continue
            value = storage
            capture_types.append(value.type)
            capture_values.append(value)
            storage_type = storage.type.pointee if isinstance(storage.type, ir.PointerType) else storage.type
            metadata.append({
                'name': name,
                'unsigned': self._ptr_unsigned.get(id(storage), self._is_unsigned_value(storage)),
                'type_name': self._locals_type_names.get(name),
                'dict_types': self._dict_item_types_for_value(storage) if storage_type == self.structs.get('Dict') else None,
                'list_unsigned': self._list_type_is_unsigned(storage.type),
            })
        env_type = ir.LiteralStructType(capture_types) if capture_types else ir.LiteralStructType([])
        if not capture_values:
            return env_type, ir.Constant(ir.PointerType(ir.IntType(8)), None), metadata
        env_ptr = self._heap_allocate(env_type, name='_parallel_env')
        for index, value in enumerate(capture_values):
            slot = self.builder.gep(env_ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)], inbounds=True)
            self.builder.store(value, slot)
        return env_type, self.builder.bitcast(env_ptr, ir.PointerType(ir.IntType(8))), metadata

    def _bind_capture_env_locals(self, env_arg: ir.Value, env_type: ir.Type, metadata: list[dict]) -> None:
        if not metadata:
            return
        typed_env = self.builder.bitcast(env_arg, ir.PointerType(env_type), name='_parallel_env_typed')
        for index, item in enumerate(metadata):
            name = item['name']
            slot = self.builder.gep(typed_env, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)], inbounds=True)
            local_storage = self.builder.load(slot, name=name)
            self.locals[name] = local_storage
            self._mark_unsigned(local_storage, bool(item.get('unsigned')))
            type_name = item.get('type_name')
            if type_name is not None:
                self._locals_type_names[name] = type_name
            dict_types = item.get('dict_types')
            if dict_types is not None:
                self._mark_dict_item_types(slot, dict_types[0], dict_types[1])
            self._mark_list_elem_unsigned(slot, bool(item.get('list_unsigned')))

    def visitFnLiteralExpr(self, ctx: EzLangParser.FnLiteralExprContext):
        return self._gen_function_literal_closure(ctx.functionLiteral())

    def _gen_function_literal_closure(self, fn_lit) -> ir.Value:
        ret_type, param_names, param_types = self._function_literal_param_info(fn_lit)
        closure_type = self._closure_type(ret_type, param_types)
        capture_names = self._function_literal_capture_names(fn_lit, set(param_names))
        capture_types: list[ir.Type] = []
        capture_values: list[ir.Value] = []
        capture_unsigned: list[bool] = []
        capture_type_names: list[str | None] = []
        capture_dict_types: list[tuple[ir.Type, ir.Type] | None] = []
        capture_list_unsigned: list[bool] = []
        for name in capture_names:
            self._join_flow_future(name)
            storage = self._capture_shared_storage(name)
            if storage is None:
                continue
            value = storage
            capture_types.append(value.type)
            capture_values.append(value)
            capture_unsigned.append(self._ptr_unsigned.get(id(storage), self._is_unsigned_value(storage)))
            capture_type_names.append(self._locals_type_names.get(name))
            storage_type = storage.type.pointee if isinstance(storage.type, ir.PointerType) else storage.type
            capture_dict_types.append(self._dict_item_types_for_value(storage) if storage_type == self.structs.get('Dict') else None)
            capture_list_unsigned.append(self._list_type_is_unsigned(storage.type))

        env_type = ir.LiteralStructType(capture_types) if capture_types else ir.LiteralStructType([])
        env_ptr = self._arena_allocate(env_type, name='_closure_env')
        for index, value in enumerate(capture_values):
            slot = self.builder.gep(env_ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)], inbounds=True)
            self.builder.store(value, slot)
        env_i8 = self.builder.bitcast(env_ptr, ir.PointerType(ir.IntType(8)))

        invoke_type = closure_type.elements[0].pointee
        name = f"__lambda_{self._function_literal_counter}"
        self._function_literal_counter += 1
        invoke = ir.Function(self.module, invoke_type, name)
        invoke.args[0].name = '__env'
        for index, pname in enumerate(param_names):
            invoke.args[index + 1].name = pname

        old_builder = self.builder
        old_func = self.current_function
        old_locals = self.locals
        old_type_names = self._locals_type_names
        old_method_this = self._method_this
        old_stack = self._function_return_type_ctx_stack

        block = invoke.append_basic_block('entry')
        self.builder = ir.IRBuilder(block)
        self.current_function = invoke
        self.locals = {}
        self._locals_type_names = {}
        self._method_this = None
        self._function_return_type_ctx_stack = [fn_lit.type_()]
        throw_exit = invoke.append_basic_block('throw_exit')
        self._function_throw_exit_stack.append(throw_exit)

        typed_env = self.builder.bitcast(invoke.args[0], ir.PointerType(env_type), name='_closure_env_typed')
        for index, cap_name in enumerate(capture_names):
            slot = self.builder.gep(typed_env, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)], inbounds=True)
            captured_storage = self.builder.load(slot, name=cap_name)
            self.locals[cap_name] = captured_storage
            self._shared_capture_locals.add(cap_name)
            self._mark_unsigned(captured_storage, capture_unsigned[index] if index < len(capture_unsigned) else False)
            if index < len(capture_type_names) and capture_type_names[index] is not None:
                self._locals_type_names[cap_name] = capture_type_names[index]
            if index < len(capture_dict_types) and capture_dict_types[index] is not None:
                key_type, value_type = capture_dict_types[index]
                self._mark_dict_item_types(captured_storage, key_type, value_type)
            if index < len(capture_list_unsigned):
                self._mark_list_elem_unsigned(captured_storage, capture_list_unsigned[index])
        for index, pname in enumerate(param_names):
            self._bind_function_param(pname, param_types[index], invoke.args[index + 1])

        body = fn_lit.block() or fn_lit.expression()
        value = self._eval(body) if body is not None else None
        self._finish_function_with_throw_exit(ret_type, value)

        self.builder = old_builder
        self.current_function = old_func
        self.locals = old_locals
        self._locals_type_names = old_type_names
        self._method_this = old_method_this
        self._function_return_type_ctx_stack = old_stack

        closure = ir.Constant(closure_type, ir.Undefined)
        closure = self.builder.insert_value(closure, invoke, 0)
        closure = self.builder.insert_value(closure, env_i8, 1)
        return closure

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

        list_ptr = self._as_list_ptr(obj_ptr)
        if list_ptr is not None:
            elem_ptr = self._list_element_ptr(list_ptr, index_val)
            self._mark_unsigned(elem_ptr, self._list_type_is_unsigned(list_ptr.type))
            return self._load_with_unsigned(elem_ptr)

        # 兼容旧裸数组指针
        if not isinstance(obj_ptr.type, ir.PointerType):
            return None
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
        if self._is_weak_ref_type(opt_type):
            if not isinstance(opt_ptr.type, ir.PointerType):
                tmp = self.builder.alloca(opt_type, name='_weak_tmp')
                self.builder.store(opt_ptr, tmp)
                opt_ptr = tmp
            value_ptr = self.builder.gep(opt_ptr, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), 1),
            ], inbounds=True)
            ref_ptr = self.builder.load(value_ptr, name='_weak_value_ptr')
            pointee = opt_type.elements[1].pointee
            if isinstance(pointee, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
                return ref_ptr
            is_null = self.builder.icmp_unsigned('==', ref_ptr, ir.Constant(ref_ptr.type, None), name='_weak_is_null')
            value = self.builder.load(ref_ptr, name='_weak_value')
            return self.builder.select(is_null, self._zero_constant(pointee), value, name='_weak_unwrapped')
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

    def _weak_ref_pointee_ptr(self, value: ir.Value) -> ir.Value | None:
        """弱引用值或弱引用槽解包为内部对象指针。"""
        if value is None or not hasattr(value, 'type'):
            return None
        value_type = value.type.pointee if isinstance(value.type, ir.PointerType) else value.type
        if not self._is_weak_ref_type(value_type):
            return None
        if isinstance(value.type, ir.PointerType):
            ptr_slot = self.builder.gep(value, [
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(ir.IntType(32), 1),
            ], inbounds=True)
            return self.builder.load(ptr_slot, name='_weak_pointee_ptr')
        return self.builder.extract_value(value, 1, name='_weak_pointee_ptr')

    def _weak_ref_calculation_value(self, value: ir.Value) -> ir.Value:
        """弱引用在计算上下文中自动解包为内部值。"""
        value_type = value.type.pointee if isinstance(value.type, ir.PointerType) else value.type
        if not self._is_weak_ref_type(value_type):
            return value
        ref_ptr = self._weak_ref_pointee_ptr(value)
        if ref_ptr is None:
            return value
        pointee = value_type.elements[1].pointee
        if isinstance(pointee, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType)):
            return ref_ptr
        is_null = self.builder.icmp_unsigned('==', ref_ptr, ir.Constant(ref_ptr.type, None), name='_weak_calc_is_null')
        result_ptr = self.builder.alloca(pointee, name='_weak_calc_unwrapped_slot')
        null_block = self.builder.append_basic_block('_weak_calc_null')
        value_block = self.builder.append_basic_block('_weak_calc_value_block')
        done_block = self.builder.append_basic_block('_weak_calc_done')
        self.builder.cbranch(is_null, null_block, value_block)

        self.builder.position_at_start(null_block)
        self.builder.store(self._zero_constant(pointee), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(value_block)
        self.builder.store(self.builder.load(ref_ptr, name='_weak_calc_value'), result_ptr)
        self.builder.branch(done_block)

        self.builder.position_at_start(done_block)
        result = self.builder.load(result_ptr, name='_weak_calc_unwrapped')
        self._mark_unsigned(result, self._is_unsigned_value(value))
        return result

    def _weak_ref_calculation_operands(self, left: ir.Value, right: ir.Value) -> tuple[ir.Value, ir.Value]:
        return self._weak_ref_calculation_value(left), self._weak_ref_calculation_value(right)

    def visitTypeAssertion(self, ctx: EzLangParser.TypeAssertionContext):
        return self._optional_unwrapped_value(ctx.postfixExpression())

    def visitOptionalUnwrap(self, ctx: EzLangParser.OptionalUnwrapContext):
        return self._optional_unwrapped_value(ctx.postfixExpression())

    def visitWeakRefExpression(self, ctx: EzLangParser.WeakRefExpressionContext):
        if not self._is_weak_ref_target(ctx.unaryExpression()):
            self._extern_diagnostics.append(
                f"行 {ctx.start.line}: 弱引用 '#' 只能用于变量、字段或索引等可寻址表达式"
            )
            return self._weak_ref_value(None, ir.IntType(32))
        inner = self._eval(ctx.unaryExpression())
        if inner is None or not hasattr(inner, 'type'):
            return self._weak_ref_value(None, ir.IntType(32))
        if isinstance(inner.type, ir.PointerType):
            return self._weak_ref_value(inner, inner.type.pointee)
        ptr = self._arena_allocate(inner.type, name='_weak_tmp')
        self.builder.store(inner, ptr)
        return self._weak_ref_value(ptr, inner.type)

    def _is_weak_ref_target(self, ctx) -> bool:
        """#expr 只能捕获有稳定地址的表达式；字面量和临时计算结果没有弱引用意义。"""
        if ctx is None:
            return False
        if isinstance(ctx, EzLangParser.PostfixUnaryExpressionContext):
            return self._is_weak_ref_target(ctx.postfixExpression())
        if isinstance(ctx, EzLangParser.PrimaryExprContext):
            return self._is_weak_ref_target(ctx.primaryExpression())
        if isinstance(ctx, EzLangParser.IdentifierExprContext):
            return ctx.VAR_IDENTIFIER() is not None or ctx.VOID() is not None
        if isinstance(ctx, (EzLangParser.MemberAccessContext, EzLangParser.IndexContext)):
            return True
        if isinstance(ctx, (EzLangParser.TypeAssertionContext, EzLangParser.OptionalUnwrapContext)):
            return self._is_weak_ref_target(ctx.postfixExpression())
        if isinstance(ctx, EzLangParser.ParenExprContext):
            return self._is_weak_ref_target(ctx.expression())
        if hasattr(ctx, 'getChildCount') and ctx.getChildCount() == 1:
            return self._is_weak_ref_target(ctx.getChild(0))
        return False

    def _call_arg_items(self, arg_list_ctx) -> list[tuple[Optional[str], object]]:
        """返回调用实参；name 为 None 表示位置参数。"""
        if arg_list_ctx is None:
            return []
        if hasattr(arg_list_ctx, 'callArg'):
            items = []
            for arg in arg_list_ctx.callArg():
                named = arg.namedArg() if hasattr(arg, 'namedArg') else None
                if named is not None:
                    token = named.VAR_IDENTIFIER()
                    items.append((token.getText() if token is not None else None, named.expression()))
                else:
                    items.append((None, arg.expression() if hasattr(arg, 'expression') else None))
            return items
        return [
            (arg.VAR_IDENTIFIER().getText(), arg.expression())
            for arg in arg_list_ctx.namedArg()
            if arg.VAR_IDENTIFIER() is not None
        ]

    def _map_call_args_to_params(
        self,
        arg_list_ctx,
        expected_names: list[str],
        implicit_this: bool = False,
        skip_names: set[str] | None = None,
    ) -> tuple[dict[str, ir.Value], list[ir.Value], list[str]]:
        """按语言语义绑定调用实参：具名参数按名绑定，位置参数只按顺序补位。"""
        provided: dict[str, ir.Value] = {}
        positional_values: list[ir.Value] = []
        placeholder_params: list[str] = []
        skipped = skip_names or set()
        positional_index = 1 if implicit_this and expected_names else 0

        for raw_name, expr_ctx in self._call_arg_items(arg_list_ctx):
            is_placeholder = expr_ctx is not None and expr_ctx.getText().strip() == '?'
            if raw_name is None:
                if expected_names and positional_index < len(expected_names):
                    pname = expected_names[positional_index]
                    positional_index += 1
                    if pname in skipped:
                        continue
                    if is_placeholder:
                        placeholder_params.append(pname)
                        continue
                    val = self._eval(expr_ctx) if expr_ctx is not None else None
                    if val is not None and pname not in provided:
                        provided[pname] = val
                    continue
                if is_placeholder:
                    continue
                val = self._eval(expr_ctx) if expr_ctx is not None else None
                if val is not None:
                    positional_values.append(val)
                continue

            if raw_name in skipped:
                continue
            if is_placeholder:
                placeholder_params.append(raw_name)
                continue
            val = self._eval(expr_ctx) if expr_ctx is not None else None
            if val is not None and raw_name not in provided:
                provided[raw_name] = val

        return provided, positional_values, placeholder_params

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

        collection_method = self._collection_method_call_info(target_expr)
        if collection_method is not None:
            func_name, receiver = collection_method
            expected_names_by_base = {
                'listLen': ['this'],
                'listPush': ['this', 'item'],
                'listPop': ['this'],
                'listShift': ['this'],
                'listUnshift': ['this', 'item'],
                'listSlice': ['this', 'start', 'end'],
                'listSort': ['this', 'cmp'],
                'listFilter': ['this', 'pred'],
                'listMap': ['this', 'f'],
                'listFind': ['this', 'pred'],
                'dictLen': ['this'],
                'dictHas': ['this', 'key'],
                'dictDelete': ['this', 'key'],
                'dictKeys': ['this'],
                'dictValues': ['this'],
            }
            base_name = self._list_builtin_base(func_name) or self._dict_builtin_base(func_name)
            expected_names = expected_names_by_base.get(base_name, ['this'])
            provided: dict[str, ir.Value] = {}
            positional_values: list[ir.Value] = []
            if ctx.namedArgList() is not None:
                provided, positional_values, _placeholder_params = self._map_call_args_to_params(
                    ctx.namedArgList(), expected_names
                )
            call_args = [receiver]
            for pname in expected_names[1:]:
                if pname in provided:
                    call_args.append(provided[pname])
                elif positional_values:
                    call_args.append(positional_values.pop(0))
            if base_name == 'listMap' and len(call_args) >= 2:
                list_ptr = self._as_list_ptr(receiver)
                elem_type = self._list_elem_type(list_ptr) if list_ptr is not None else ir.IntType(32)
                result_type = self._callable_return_type(call_args[1]) or ir.IntType(32)
                elem_suffix = self._type_name_from_ir_type(elem_type) or 'unknown'
                result_suffix = self._type_name_from_ir_type(result_type) or 'unknown'
                func_name = f'listMap_{elem_suffix}_{result_suffix}'
                self._collection_mono_types[func_name] = ('listMap', [elem_type, result_type])
            intrinsic_result = self._try_gen_intrinsic_call(func_name, call_args)
            if intrinsic_result is self._void_intrinsic_result:
                return None
            if intrinsic_result is not None:
                return intrinsic_result

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
                        type_arg_ctxs = list(id_ctx.genericArgs().type_())
                        type_args = [self._map_type(t) for t in type_arg_ctxs]
                        name = self._monomorphize(
                            name,
                            type_args,
                            [self._type_ctx_suffix(t) for t in type_arg_ctxs],
                            [self._type_ctx_is_unsigned(t) for t in type_arg_ctxs],
                            [self._type_ctx_name(t) for t in type_arg_ctxs],
                        )
            elif hasattr(inner, 'VAR_IDENTIFIER') and inner.VAR_IDENTIFIER():
                name = inner.VAR_IDENTIFIER().getText()
                # 泛型函数调用（primaryExpression 直接返回 IdentifierExprContext 时不走上面分支）
                if hasattr(inner, 'genericArgs') and inner.genericArgs() is not None:
                    if name in self.struct_generic_templates:
                        name = self._struct_name_from_generic_args(name, inner.genericArgs())
                    else:
                        type_arg_ctxs = list(inner.genericArgs().type_())
                        type_args = [self._map_type(t) for t in type_arg_ctxs]
                        name = self._monomorphize(
                            name,
                            type_args,
                            [self._type_ctx_suffix(t) for t in type_arg_ctxs],
                            [self._type_ctx_is_unsigned(t) for t in type_arg_ctxs],
                            [self._type_ctx_name(t) for t in type_arg_ctxs],
                        )
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

        is_compiler_builtin = name and any(
            name == base or name.startswith(f'{base}_') for base in self._compiler_builtin_declares
        )

        if curried_target is None and (func is None or not self._is_callable_value(func)):
            # 编译器内建函数不生成外部声明。
            if is_compiler_builtin:
                func = None
            elif name in self.generic_templates:
                func = None
            elif name:
                args = ctx.namedArgList()
                nargs = len(self._call_arg_items(args)) if args is not None else 0
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
            if not expected_names and curried_target is None and name in self.generic_templates and func_name == name:
                expected_names = self._generic_template_param_names(name)

        if self._should_drop_log_call(func_name, ctx.namedArgList()):
            return None

        # 获取函数期望的参数名列表和默认值
        defaults = self.func_defaults.get(func_name, {})

        # 解析调用时提供的具名参数，检测 ? 占位符（柯里化）
        provided: dict[str, any] = {}
        positional_values: list[ir.Value] = []
        placeholder_params: list[str] = []  # 柯里化：需要延迟绑定的参数名
        args = ctx.namedArgList()
        if args is not None:
            provided, positional_values, placeholder_params = self._map_call_args_to_params(
                args,
                expected_names,
                implicit_this=method_this is not None and bool(expected_names) and expected_names[0] == 'this',
                skip_names={'pl'} if self._flow_depth > 0 and func_name == 'race' else None,
            )

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
            inject_method_this = method_this is not None and bool(expected_names) and expected_names[0] == 'this'
            if inject_method_this:
                call_args.append(method_this)
            for pname in expected_names:
                if inject_method_this and pname == expected_names[0]:
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
            call_args.extend(positional_values)
            call_args.extend(provided.values())

        closure_call = self._call_closure(func, call_args)
        if closure_call is not None:
            self._emit_throw_check_after_call()
            return closure_call

        # 检查是否为编译器内建函数
        intrinsic_result = self._try_gen_intrinsic_call(func_name, call_args)
        if intrinsic_result is not None:
            if intrinsic_result is self._void_intrinsic_result:
                return None
            return intrinsic_result

        if func is None:
            return self._zero_constant(self._call_return_type(ctx))

        func_type = func.type.pointee if isinstance(func.type, ir.PointerType) else None
        if self._flow_depth > 0:
            self._require_flow_suspend_source(func_name)
        if func_name in self.func_param_names and self._date_method_abi_type(func_name) is not None:
            self._require_std_time()
        if self._flow_depth > 0 and func_name == 'sleep' and call_args:
            sleep_arg = self._coerce_value(call_args[0], ir.IntType(64))
            return self.builder.call(self._require_flow_sleep(), [sleep_arg])
        sret_type = self._sret_functions.get(func_name)
        abi_arg_types = list(func_type.args) if func_type is not None else []
        if sret_type is not None:
            ret_slot = self._arena_allocate(sret_type, name=f"_{func_name}_ret")
            call_args = [ret_slot] + call_args

        if func_type is not None:
            call_args = [
                self._coerce_call_arg(arg, abi_arg_types[i]) if i < len(abi_arg_types) else arg
                for i, arg in enumerate(call_args)
            ]
            call_args = [
                self._load_if_aggregate_ptr(arg)
                if i < len(abi_arg_types) and arg.type != abi_arg_types[i] and self._is_aggregate_ptr(arg)
                else arg
                for i, arg in enumerate(call_args)
            ]

        self._json_parse_validate_or_throw(func_name, call_args)
        if self.builder is not None and self.builder.block.is_terminated:
            return self._zero_constant(self._call_return_type(ctx))

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

    def _json_parse_validator_name(self, func_name: str) -> str | None:
        prefix = 'jsonParse_'
        if not func_name.startswith(prefix):
            return None
        suffix = func_name[len(prefix):]
        if suffix == 'I1':
            suffix = 'Bool'
        if suffix in {'I8', 'I32', 'I64', 'U8', 'U32', 'U64', 'F32', 'F64', 'Str', 'Bool'}:
            return f'__ez_json_valid_{suffix}'
        return None

    def _json_parse_validate_or_throw(self, func_name: str, call_args: list[ir.Value]) -> None:
        validator_name = self._json_parse_validator_name(func_name)
        if validator_name is None or not call_args or self.builder is None:
            return
        i1 = ir.IntType(1)
        i8_ptr = ir.PointerType(ir.IntType(8))
        validator = self._get_or_declare_function(validator_name, ir.FunctionType(i1, [i8_ptr]))
        arg = call_args[0]
        if arg.type != i8_ptr:
            arg = self._coerce_value(arg, i8_ptr)
        ok = self.builder.call(validator, [arg], name='_json_parse_ok')
        fail_bb = self.builder.append_basic_block('json_parse_invalid')
        cont_bb = self.builder.append_basic_block('json_parse_valid')
        self.builder.cbranch(ok, cont_bb, fail_bb)
        self.builder.position_at_start(fail_bb)
        self._raise_error(4, 'json parse failed')
        self.builder.position_at_start(cont_bb)

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
        if isinstance(type_ctx, P.WeakTypeContext):
            if self._is_weak_ref_type(actual_type):
                self._infer_generic_type_from_ctx(type_ctx.type_(), actual_type.elements[1].pointee, type_map, generic_names)
            return
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
        if not generic_names:
            return None
        params = None
        if hasattr(template_ctx, 'paramTypeList'):
            params = template_ctx.paramTypeList()
        if params is None and hasattr(template_ctx, 'functionLiteral'):
            fn_lit = template_ctx.functionLiteral()
            params = fn_lit.paramList() if fn_lit is not None else None
        if params is None:
            return None
        type_map: dict[str, ir.Type] = {}
        generic_set = set(generic_names)
        param_items = params.paramType() if hasattr(params, 'paramType') else params.param()
        for param in param_items:
            pname = param.VAR_IDENTIFIER().getText()
            if pname not in provided:
                continue
            actual_type = self._value_type_for_generic_inference(provided[pname])
            self._infer_generic_type_from_ctx(param.type_(), actual_type, type_map, generic_set)
        if any(name not in type_map for name in generic_names):
            return None
        return [type_map[name] for name in generic_names]

    def _generic_template_param_names(self, base_name: str) -> list[str]:
        template = self.generic_templates.get(base_name)
        if template is None or len(template) < 2:
            return []
        template_ctx = template[1]
        if hasattr(template_ctx, 'paramTypeList'):
            params = template_ctx.paramTypeList()
            if params is not None:
                return [param.VAR_IDENTIFIER().getText() for param in params.paramType()]
        if not hasattr(template_ctx, 'functionLiteral'):
            return []
        fn_lit = template_ctx.functionLiteral()
        if fn_lit is None or fn_lit.paramList() is None:
            return []
        return [param.VAR_IDENTIFIER().getText() for param in fn_lit.paramList().param()]

    @staticmethod
    def _is_callable_value(value) -> bool:
        if isinstance(value, ir.Function):
            return True
        if isinstance(value, ir.Value) and isinstance(value.type, ir.PointerType) and isinstance(value.type.pointee, ir.FunctionType):
            return True
        return isinstance(value, ir.Value) and LLVMCodeGenerator._static_is_closure_value_type(value.type)

    @staticmethod
    def _static_is_closure_value_type(typ: ir.Type) -> bool:
        if isinstance(typ, ir.PointerType):
            typ = typ.pointee
        if not isinstance(typ, ir.LiteralStructType) or len(typ.elements) != 2:
            return False
        invoke_ptr, env_ptr = typ.elements
        return (
            isinstance(invoke_ptr, ir.PointerType)
            and isinstance(invoke_ptr.pointee, ir.FunctionType)
            and len(invoke_ptr.pointee.args) >= 1
            and invoke_ptr.pointee.args[0] == ir.PointerType(ir.IntType(8))
            and env_ptr == ir.PointerType(ir.IntType(8))
        )

    def _call_closure(self, closure: ir.Value, args: list[ir.Value]) -> ir.Value | None:
        if closure is None or not isinstance(closure, ir.Value):
            return None
        if isinstance(closure.type, ir.PointerType) and self._is_closure_type(closure.type.pointee):
            closure_value = self.builder.load(closure, name='_closure_value')
        elif self._is_closure_type(closure.type):
            closure_value = closure
        else:
            return None
        invoke = self.builder.extract_value(closure_value, 0, name='_closure_invoke')
        env = self.builder.extract_value(closure_value, 1, name='_closure_env')
        invoke_type = invoke.type.pointee
        coerced = [self._coerce_call_arg(arg, invoke_type.args[i + 1]) if i + 1 < len(invoke_type.args) else arg for i, arg in enumerate(args)]
        return self.builder.call(invoke, [env] + coerced)

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
        if list_builtin == 'randomShuffle' and len(call_args) >= 2:
            return self._gen_random_shuffle(name, call_args[0], call_args[1])

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
        for arg_name, expr_ctx in self._call_arg_items(args_ctx):
            if arg_name != 'level' or expr_ctx is None:
                continue
            text = expr_ctx.getText().strip()
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
        value_type = value.type.pointee if isinstance(value.type, ir.PointerType) else value.type
        if self._is_weak_ref_type(value_type) and self._is_list_type(value_type.elements[1].pointee):
            if isinstance(value.type, ir.PointerType):
                ptr_slot = self.builder.gep(value, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), 1),
                ], inbounds=True)
                return self.builder.load(ptr_slot, name='_weak_list_ptr')
            return self.builder.extract_value(value, 1, name='_weak_list_ptr')
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

    def _weak_ref_value(self, ptr: ir.Value | None, pointee_type: ir.Type) -> ir.Value:
        weak_type = ir.LiteralStructType([ir.IntType(1), ir.PointerType(pointee_type)])
        result = ir.Constant(weak_type, ir.Undefined)
        ok = ptr is not None
        result = self.builder.insert_value(result, ir.Constant(ir.IntType(1), int(ok)), 0)
        if ptr is None:
            ptr = ir.Constant(ir.PointerType(pointee_type), None)
        elif ptr.type != ir.PointerType(pointee_type):
            ptr = self.builder.bitcast(ptr, ir.PointerType(pointee_type))
        return self.builder.insert_value(result, ptr, 1)

    def _coerce_weak_ref_value(self, value: ir.Value, target_type: ir.Type) -> ir.Value:
        pointee_type = target_type.elements[1].pointee
        if value.type == target_type:
            return value
        if isinstance(value.type, ir.PointerType) and value.type.pointee == pointee_type:
            return self._weak_ref_value(value, pointee_type)
        if value.type == pointee_type:
            ptr = self._arena_allocate(pointee_type, name='_weak_tmp')
            self.builder.store(value, ptr)
            return self._weak_ref_value(ptr, pointee_type)
        if self._is_aggregate_ptr(value) and value.type.pointee == pointee_type:
            return self._weak_ref_value(value, pointee_type)
        return self._zero_constant(target_type)

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

    @staticmethod
    def _u64_constant(value: int) -> ir.Constant:
        value &= (1 << 64) - 1
        if value >= (1 << 63):
            value -= 1 << 64
        return ir.Constant(ir.IntType(64), value)

    def _random_source_state_ptr(self, source_value: ir.Value) -> ir.Value:
        i64 = ir.IntType(64)
        random_type = self.structs.get('RandomSource')
        if random_type is not None:
            if self._is_weak_ref_type(source_value.type) and source_value.type.elements[1].pointee == random_type:
                source_value = self.builder.extract_value(source_value, 1, name='_random_source_ptr')
            if isinstance(source_value.type, ir.PointerType) and source_value.type.pointee == random_type:
                return self.builder.gep(source_value, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), 0),
                ], inbounds=True)
            if source_value.type == random_type:
                tmp = self.builder.alloca(random_type, name='_random_source_tmp')
                self.builder.store(source_value, tmp)
                return self.builder.gep(tmp, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), 0),
                ], inbounds=True)
        tmp = self.builder.alloca(i64, name='_random_source_state')
        self.builder.store(ir.Constant(i64, 0), tmp)
        return tmp

    def _random_next_u64(self, state_ptr: ir.Value) -> ir.Value:
        i64 = ir.IntType(64)
        zero = ir.Constant(i64, 0)
        x = self.builder.load(state_ptr, name='_random_state')
        is_zero = self.builder.icmp_unsigned('==', x, zero, name='_random_state_zero')
        x = self.builder.select(is_zero, self._u64_constant(0xE220A8397B1DCDAF), x, name='_random_state_seeded')
        x = self.builder.xor(x, self.builder.lshr(x, ir.Constant(i64, 12)), name='_random_xor_12')
        x = self.builder.xor(x, self.builder.shl(x, ir.Constant(i64, 25)), name='_random_xor_25')
        x = self.builder.xor(x, self.builder.lshr(x, ir.Constant(i64, 27)), name='_random_xor_27')
        self.builder.store(x, state_ptr)
        return self.builder.mul(x, self._u64_constant(0x2545F4914F6CDD1D), name='_random_next')

    def _random_index_below(self, state_ptr: ir.Value, span: ir.Value) -> ir.Value:
        i64 = ir.IntType(64)
        zero = ir.Constant(i64, 0)
        threshold = self.builder.urem(self.builder.sub(zero, span), span, name='_random_threshold')
        value_ptr = self.builder.alloca(i64, name='_random_value')
        draw_block = self.builder.append_basic_block('random_range_draw')
        done_block = self.builder.append_basic_block('random_range_done')
        self.builder.branch(draw_block)

        self.builder.position_at_start(draw_block)
        value = self._random_next_u64(state_ptr)
        self.builder.store(value, value_ptr)
        too_low = self.builder.icmp_unsigned('<', value, threshold, name='_random_reject')
        self.builder.cbranch(too_low, draw_block, done_block)

        self.builder.position_at_start(done_block)
        accepted = self.builder.load(value_ptr, name='_random_accepted')
        return self.builder.urem(accepted, span, name='_random_index')

    def _gen_random_shuffle(self, name: str, source_value: ir.Value, list_value: ir.Value) -> ir.Value:
        list_ptr = self._as_list_ptr(list_value)
        if list_ptr is None:
            type_args = self._collection_type_args(name)
            elem_type = type_args[0] if type_args else ir.IntType(32)
            return self._list_new(elem_type, ir.Constant(ir.IntType(64), 0))

        i64 = ir.IntType(64)
        result = self._copy_list_value(list_ptr, name='_random_shuffle_result')
        length = self._list_length(result)
        state_ptr = self._random_source_state_ptr(source_value)
        index_ptr = self.builder.alloca(i64, name='_random_shuffle_i')

        init_block = self.builder.append_basic_block('random_shuffle_init')
        cond_block = self.builder.append_basic_block('random_shuffle_cond')
        body_block = self.builder.append_basic_block('random_shuffle_body')
        done_block = self.builder.append_basic_block('random_shuffle_done')
        has_items = self.builder.icmp_unsigned('>', length, ir.Constant(i64, 1), name='_random_shuffle_has_items')
        self.builder.cbranch(has_items, init_block, done_block)

        self.builder.position_at_start(init_block)
        self.builder.store(self.builder.sub(length, ir.Constant(i64, 1), name='_random_shuffle_last'), index_ptr)
        self.builder.branch(cond_block)

        self.builder.position_at_start(cond_block)
        index = self.builder.load(index_ptr, name='_random_shuffle_i_val')
        keep_shuffling = self.builder.icmp_unsigned('>', index, ir.Constant(i64, 0), name='_random_shuffle_more')
        self.builder.cbranch(keep_shuffling, body_block, done_block)

        self.builder.position_at_start(body_block)
        span = self.builder.add(index, ir.Constant(i64, 1), name='_random_shuffle_span')
        swap_index = self._random_index_below(state_ptr, span)
        item_ptr = self._list_element_ptr(result, index)
        swap_ptr = self._list_element_ptr(result, swap_index)
        tmp = self.builder.load(item_ptr, name='_random_shuffle_tmp')
        self.builder.store(self.builder.load(swap_ptr, name='_random_shuffle_other'), item_ptr)
        self.builder.store(tmp, swap_ptr)
        self.builder.store(self.builder.sub(index, ir.Constant(i64, 1), name='_random_shuffle_prev'), index_ptr)
        self.builder.branch(cond_block)

        self.builder.position_at_start(done_block)
        return result

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
        value_type = value.type.pointee if isinstance(value.type, ir.PointerType) else value.type
        if self._is_weak_ref_type(value_type) and value_type.elements[1].pointee == dict_type:
            if isinstance(value.type, ir.PointerType):
                ptr_slot = self.builder.gep(value, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), 1),
                ], inbounds=True)
                return self.builder.load(ptr_slot, name='_weak_dict_ptr')
            return self.builder.extract_value(value, 1, name='_weak_dict_ptr')
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
            left, right = self._weak_ref_calculation_operands(left, right)
            left, right = self._prepare_vector_binary_operands(left, right)
            unsigned = self._binary_result_unsigned(left, right)
            if op == '+' and self._is_str_type(left.type) and self._is_str_type(right.type):
                left = self._concat_str_values(left, right)
                continue
            left, right = self._coerce_float_binary_operands(left, right)
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
            left, right = self._weak_ref_calculation_operands(left, right)
            left, right = self._prepare_vector_binary_operands(left, right)
            unsigned = self._binary_result_unsigned(left, right)
            left, right = self._coerce_float_binary_operands(left, right)
            if self._is_float_or_float_vector(left.type):
                if op == '*': left = self.builder.fmul(left, right)
                elif op == '/': left = self.builder.fdiv(left, right)
            else:
                if op == '*': left = self.builder.mul(left, right)
                elif op == '/': left = self.builder.udiv(left, right) if unsigned else self._signed_floor_div_rem(left, right, "_floor_div")[0]
                elif op == '%': left = self.builder.urem(left, right) if unsigned else self._signed_floor_div_rem(left, right, "_floor_rem")[1]
            self._mark_unsigned(left, unsigned)
        return left

    @staticmethod
    def _is_zero_int_constant(val: ir.Value) -> bool:
        return isinstance(val, ir.Constant) and isinstance(val.type, ir.IntType) and val.constant == 0

    def _coerce_float_binary_operands(self, left: ir.Value, right: ir.Value) -> tuple[ir.Value, ir.Value]:
        """把混合浮点运算/比较统一到同一个浮点类型。"""
        scalar_types = (ir.IntType, ir.FloatType, ir.DoubleType)
        if not isinstance(left.type, scalar_types) or not isinstance(right.type, scalar_types):
            return left, right
        left_is_float = isinstance(left.type, (ir.FloatType, ir.DoubleType))
        right_is_float = isinstance(right.type, (ir.FloatType, ir.DoubleType))
        if not left_is_float and not right_is_float:
            return left, right
        target_type = ir.DoubleType() if isinstance(left.type, ir.DoubleType) or isinstance(right.type, ir.DoubleType) else ir.FloatType()

        def coerce(value: ir.Value) -> ir.Value:
            if value.type == target_type:
                return value
            if isinstance(value.type, ir.IntType):
                return self.builder.uitofp(value, target_type) if self._is_unsigned_value(value) else self.builder.sitofp(value, target_type)
            if isinstance(value.type, ir.FloatType) and isinstance(target_type, ir.DoubleType):
                return self.builder.fpext(value, target_type)
            if isinstance(value.type, ir.DoubleType) and isinstance(target_type, ir.FloatType):
                return self.builder.fptrunc(value, target_type)
            return value

        return coerce(left), coerce(right)

    @staticmethod
    def _aggregate_value_type(val: ir.Value) -> ir.Type:
        return val.type.pointee if isinstance(val.type, ir.PointerType) else val.type

    def _is_equality_aggregate_type(self, typ: ir.Type) -> bool:
        return isinstance(typ, (ir.IdentifiedStructType, ir.LiteralStructType, ir.ArrayType))

    def _is_equality_aggregate_value(self, val: ir.Value) -> bool:
        return self._is_equality_aggregate_type(self._aggregate_value_type(val))

    def _as_aggregate_ptr_for_compare(self, val: ir.Value, name: str) -> ir.Value:
        typ = self._aggregate_value_type(val)
        if isinstance(val.type, ir.PointerType) and val.type.pointee == typ:
            return val
        ptr = self.builder.alloca(typ, name=name)
        self.builder.store(val, ptr)
        return ptr

    def _aggregate_element_value(self, owner: ir.Value, owner_type: ir.Type, index: int, name: str) -> ir.Value:
        i32 = ir.IntType(32)
        if isinstance(owner_type, ir.ArrayType):
            elem_type = owner_type.element
            if isinstance(owner.type, ir.PointerType):
                elem_ptr = self.builder.gep(owner, [ir.Constant(i32, 0), ir.Constant(i32, index)], inbounds=True)
                return elem_ptr if self._is_equality_aggregate_type(elem_type) else self.builder.load(elem_ptr, name=name)
            return self.builder.extract_value(owner, index, name=name)

        elem_type = owner_type.elements[index]
        if isinstance(owner.type, ir.PointerType):
            elem_ptr = self.builder.gep(owner, [ir.Constant(i32, 0), ir.Constant(i32, index)], inbounds=True)
            return elem_ptr if self._is_equality_aggregate_type(elem_type) else self.builder.load(elem_ptr, name=name)
        return self.builder.extract_value(owner, index, name=name)

    def _aggregate_layout_matches(self, left_type: ir.Type, right_type: ir.Type) -> bool:
        if isinstance(left_type, ir.ArrayType) and isinstance(right_type, ir.ArrayType):
            return left_type.count == right_type.count and str(left_type.element) == str(right_type.element)
        if not isinstance(left_type, (ir.IdentifiedStructType, ir.LiteralStructType)):
            return False
        if not isinstance(right_type, (ir.IdentifiedStructType, ir.LiteralStructType)):
            return False
        if len(left_type.elements) != len(right_type.elements):
            return False
        return all(str(a) == str(b) for a, b in zip(left_type.elements, right_type.elements))

    def _aggregate_field_count(self, typ: ir.Type) -> int:
        if isinstance(typ, ir.ArrayType):
            return typ.count
        return len(typ.elements)

    def _gen_optional_equality(self, left: ir.Value, right: ir.Value) -> ir.Value:
        i1 = ir.IntType(1)
        left_type = self._aggregate_value_type(left)
        right_type = self._aggregate_value_type(right)
        left_ptr = self._as_aggregate_ptr_for_compare(left, '_eq_opt_left')
        right_ptr = self._as_aggregate_ptr_for_compare(right, '_eq_opt_right')
        left_ok = self._aggregate_element_value(left_ptr, left_type, 0, '_eq_left_ok')
        right_ok = self._aggregate_element_value(right_ptr, right_type, 0, '_eq_right_ok')
        ok_equal = self.builder.icmp_unsigned('==', left_ok, right_ok, name='_eq_optional_ok')
        both_present = self.builder.and_(left_ok, right_ok, name='_eq_optional_present')
        left_value = self._aggregate_element_value(left_ptr, left_type, 1, '_eq_left_value')
        right_value = self._aggregate_element_value(right_ptr, right_type, 1, '_eq_right_value')
        value_equal = self._gen_equality_comparison(left_value, right_value, '==')
        value_allowed = self.builder.or_(self.builder.not_(both_present), value_equal, name='_eq_optional_value_allowed')
        return self.builder.and_(ok_equal, value_allowed, name='_eq_optional')

    def _gen_union_equality(self, left: ir.Value, right: ir.Value) -> ir.Value:
        left_type = self._aggregate_value_type(left)
        right_type = self._aggregate_value_type(right)
        left_ptr = self._as_aggregate_ptr_for_compare(left, '_eq_union_left')
        right_ptr = self._as_aggregate_ptr_for_compare(right, '_eq_union_right')
        left_tag = self._aggregate_element_value(left_ptr, left_type, 0, '_eq_left_tag')
        right_tag = self._aggregate_element_value(right_ptr, right_type, 0, '_eq_right_tag')
        if left_tag.type != right_tag.type:
            right_tag = self._coerce_value(right_tag, left_tag.type)
        tag_equal = self.builder.icmp_signed('==', left_tag, right_tag, name='_eq_union_tag')
        left_value = self._aggregate_element_value(left_ptr, left_type, 1, '_eq_left_union_value')
        right_value = self._aggregate_element_value(right_ptr, right_type, 1, '_eq_right_union_value')
        value_equal = self._gen_equality_comparison(left_value, right_value, '==')
        return self.builder.and_(tag_equal, value_equal, name='_eq_union')

    def _gen_aggregate_equality(self, left: ir.Value, right: ir.Value) -> ir.Value:
        i1 = ir.IntType(1)
        left_type = self._aggregate_value_type(left)
        right_type = self._aggregate_value_type(right)
        if self._is_optional_type(left_type) and self._is_optional_type(right_type):
            return self._gen_optional_equality(left, right)
        if self._is_union_type(left_type) and self._is_union_type(right_type):
            return self._gen_union_equality(left, right)
        if not self._aggregate_layout_matches(left_type, right_type):
            return ir.Constant(i1, 0)
        left_owner = self._as_aggregate_ptr_for_compare(left, '_eq_left') if not isinstance(left.type, ir.PointerType) else left
        right_owner = self._as_aggregate_ptr_for_compare(right, '_eq_right') if not isinstance(right.type, ir.PointerType) else right
        result = ir.Constant(i1, 1)
        for index in range(self._aggregate_field_count(left_type)):
            left_field = self._aggregate_element_value(left_owner, left_type, index, f'_eq_left_{index}')
            right_field = self._aggregate_element_value(right_owner, right_type, index, f'_eq_right_{index}')
            field_equal = self._gen_equality_comparison(left_field, right_field, '==')
            result = self.builder.and_(result, field_equal, name=f'_eq_field_{index}')
        return result

    def _coerce_equality_operands(self, left: ir.Value, right: ir.Value) -> tuple[ir.Value, ir.Value]:
        if isinstance(left.type, ir.PointerType) and self._is_zero_int_constant(right):
            return left, ir.Constant(left.type, None)
        if isinstance(right.type, ir.PointerType) and self._is_zero_int_constant(left):
            return ir.Constant(right.type, None), right
        if isinstance(left.type, ir.PointerType) and isinstance(right.type, ir.PointerType) and left.type != right.type:
            right = self.builder.bitcast(right, left.type)
            return left, right
        if isinstance(left.type, ir.IntType) and isinstance(right.type, ir.IntType) and left.type != right.type:
            target = left.type if left.type.width >= right.type.width else right.type
            left = self._coerce_integer_value(left, target)
            right = self._coerce_integer_value(right, target)
        return left, right

    def _gen_equality_comparison(self, left: ir.Value, right: ir.Value, op: str) -> ir.Value:
        left, right = self._weak_ref_calculation_operands(left, right)
        left, right = self._prepare_vector_binary_operands(left, right)
        if self._is_equality_aggregate_value(left) or self._is_equality_aggregate_value(right):
            equal = self._gen_aggregate_equality(left, right)
            return self.builder.not_(equal) if op == '!=' else equal
        left, right = self._coerce_equality_operands(left, right)
        left, right = self._coerce_float_binary_operands(left, right)
        if self._is_float_or_float_vector(left.type):
            return self.builder.fcmp_ordered(op, left, right)
        if isinstance(left.type, ir.PointerType):
            return self.builder.icmp_unsigned(op, left, right)
        return self.builder.icmp_signed(op, left, right)

    def _typeof_void_weak_check(self, left_ctx, right_ctx, op: str) -> ir.Value | None:
        """生成 typeof weakRef == Void / != Void 的空引用判断。"""
        def _typeof_operand(ctx):
            if ctx is None or not hasattr(ctx, 'getChildCount'):
                return None
            if isinstance(ctx, EzLangParser.TypeofPrimaryExprContext):
                return ctx.typeofExpr().unaryExpression()
            if hasattr(ctx, 'typeofExpr') and ctx.typeofExpr() is not None:
                return ctx.typeofExpr().unaryExpression()
            if ctx.getChildCount() == 1:
                return _typeof_operand(ctx.getChild(0))
            if isinstance(ctx, EzLangParser.ParenExprContext):
                return _typeof_operand(ctx.expression())
            return None

        def _is_void_type(ctx) -> bool:
            if ctx is None:
                return False
            operand = _typeof_operand(ctx)
            if operand is not None:
                return operand.getText() == 'Void'
            if hasattr(ctx, 'getChildCount') and ctx.getChildCount() == 1:
                return _is_void_type(ctx.getChild(0))
            if isinstance(ctx, EzLangParser.ParenExprContext):
                return _is_void_type(ctx.expression())
            return hasattr(ctx, 'getText') and ctx.getText() == 'Void'

        def _weak_ok(expr_ctx):
            operand = _typeof_operand(expr_ctx)
            if operand is None:
                return None
            value = self._eval(operand)
            if value is None or not hasattr(value, 'type'):
                return None
            value_type = value.type.pointee if isinstance(value.type, ir.PointerType) else value.type
            if not self._is_weak_ref_type(value_type):
                return None
            if isinstance(value.type, ir.PointerType):
                ok_ptr = self.builder.gep(value, [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), 0),
                ], inbounds=True)
                return self.builder.load(ok_ptr, name='_weak_ok')
            return self.builder.extract_value(value, 0, name='_weak_ok')

        left_ok = _weak_ok(left_ctx)
        right_is_void = _is_void_type(right_ctx)
        if left_ok is not None and right_is_void:
            is_void = self.builder.not_(left_ok)
            return self.builder.not_(is_void) if op == '!=' else is_void
        right_ok = _weak_ok(right_ctx)
        left_is_void = _is_void_type(left_ctx)
        if right_ok is not None and left_is_void:
            is_void = self.builder.not_(right_ok)
            return self.builder.not_(is_void) if op == '!=' else is_void
        return None

    def visitEqualityExpression(self, ctx: EzLangParser.EqualityExpressionContext):
        if len(ctx.relationalExpression()) == 1:
            return self._eval(ctx.relationalExpression(0))

        left = None
        for i in range(1, len(ctx.relationalExpression())):
            op = ctx.getChild((i * 2) - 1).getText()
            if left is None:
                weak_typeof = self._typeof_void_weak_check(ctx.relationalExpression(0), ctx.relationalExpression(i), op)
                if weak_typeof is not None:
                    left = weak_typeof
                    continue
                left = self._eval(ctx.relationalExpression(0))
            right = self._eval(ctx.relationalExpression(i))
            if left is None or right is None: continue
            left = self._gen_equality_comparison(left, right, op)
        return left

    def visitRelationalExpression(self, ctx: EzLangParser.RelationalExpressionContext):
        left = self._eval(ctx.bitOrExpression(0))
        for i in range(1, len(ctx.bitOrExpression())):
            right = self._eval(ctx.bitOrExpression(i))
            if left is None or right is None: continue
            op = ctx.getChild((i * 2) - 1).getText()
            left, right = self._weak_ref_calculation_operands(left, right)
            left, right = self._prepare_vector_binary_operands(left, right)
            left, right = self._coerce_float_binary_operands(left, right)
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
            left, right = self._weak_ref_calculation_operands(left, right)
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
            left, right = self._weak_ref_calculation_operands(left, right)
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
            left, right = self._weak_ref_calculation_operands(left, right)
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
            left, right = self._weak_ref_calculation_operands(left, right)
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
        left = self._truthy_value(left)

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
            right = self._truthy_value(right)
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
            left = self._truthy_value(left)

        return left

    def visitAndExpression(self, ctx: EzLangParser.AndExpressionContext):
        lhs_list = ctx.equalityExpression()
        if len(lhs_list) == 0:
            return None
        if_like = self._if_like_operand(lhs_list[-1]) if len(lhs_list) > 1 else None
        if if_like is not None:
            left = self._eval(lhs_list[0])
            for item in lhs_list[1:-1]:
                left = self._short_circuit(left, [item], 'and')
            if_ctx, negated = if_like
            cond = self._short_circuit_eval(
                left,
                [lambda if_ctx=if_ctx, negated=negated: self._eval_if_like_condition(if_ctx, negated)],
                'and',
            )
            return self._eval_if_like_with_condition(if_ctx, cond)
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
        inner = self._weak_ref_calculation_value(inner)

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

    def visitPostfixUnaryExpression(self, ctx: EzLangParser.PostfixUnaryExpressionContext):
        return self._eval(ctx.postfixExpression())

    def visitPrefixUnaryExpression(self, ctx: EzLangParser.PrefixUnaryExpressionContext):
        inner = self._eval(ctx.unaryExpression())
        if inner is None:
            return None
        inner = self._weak_ref_calculation_value(inner)

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

    def visitPrefixTypeAssertion(self, ctx: EzLangParser.PrefixTypeAssertionContext):
        target_type = self._map_type(ctx.type_())
        result = self._type_assert_value(self._eval(ctx.unaryExpression()), target_type)
        self._mark_unsigned(result, self._type_ctx_is_unsigned(ctx.type_()))
        return result

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
            type_arg_ctxs = list(generic_args.type_())
            type_args = [self._map_type(t) for t in type_arg_ctxs]
            func_name = self._monomorphize(
                func_name,
                type_args,
                [self._type_ctx_suffix(t) for t in type_arg_ctxs],
                [self._type_ctx_is_unsigned(t) for t in type_arg_ctxs],
                [self._type_ctx_name(t) for t in type_arg_ctxs],
            )
        return self._gen_pipeline_function_call(func_name, pipe_val, ctx.pipelineArgList())

    # 条件表达式（三元）
    def visitConditionalExpression(self, ctx: EzLangParser.ConditionalExpressionContext):
        if ctx.QUESTION() is None:
            return self._eval(ctx.rangeExpression())

        if self._is_misparsed_prefix_not_conditional(ctx):
            return self._eval(ctx.rangeExpression())

        cond = self._eval(ctx.rangeExpression())
        if cond is None:
            return None
        cond = self._truthy_value(cond)

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

    def _is_misparsed_prefix_not_conditional(self, ctx) -> bool:
        """识别 `!(cond) ? a : b` 被解析成 `!((cond) ? a : b)` 的兼容形状。"""
        if not isinstance(ctx, EzLangParser.ConditionalExpressionContext) or ctx.QUESTION() is None:
            return False
        text = ctx.getText() if hasattr(ctx, 'getText') else ''
        return text.startswith('!(')

    def _control_flow_dict_literal(self, ctx):
        if isinstance(ctx, EzLangParser.DictExprContext):
            return ctx.dictLiteral()
        if hasattr(ctx, 'getChildCount') and ctx.getChildCount() == 1:
            return self._control_flow_dict_literal(ctx.getChild(0))
        return None

    def _eval_control_flow_body(self, ctx):
        literal = self._control_flow_dict_literal(ctx)
        if literal is None:
            return self._eval(ctx)
        last_value = None
        for field in literal.dictField():
            key = field.dictKey()
            if key is None or key.VAR_IDENTIFIER() is None or field.type_() is not None:
                return self._eval(ctx)
            name = key.VAR_IDENTIFIER().getText()
            val = self._eval(field.expression())
            if val is None:
                continue
            store_val = self.builder.load(val) if self._is_aggregate_ptr(val) else val
            target = self.locals.get(name) or self.globals.get(name)
            if target is None:
                continue
            store_val = self._emit_locked_assignment(name, target, store_val, None)
            last_value = store_val
        return last_value

    def _if_like_operand(self, ctx):
        if ctx is None:
            return None
        if isinstance(ctx, EzLangParser.IfLikeExprContext):
            return ctx, False
        if isinstance(ctx, EzLangParser.IfLikePrimaryExprContext):
            return ctx.ifLikeExpr(), False
        if isinstance(ctx, EzLangParser.PrefixUnaryExpressionContext) and ctx.BANG() is not None:
            inner = self._if_like_operand(ctx.unaryExpression())
            if inner is not None:
                if_ctx, negated = inner
                return if_ctx, not negated
            return None
        if hasattr(ctx, 'getChildCount') and ctx.getChildCount() == 1:
            return self._if_like_operand(ctx.getChild(0))
        return None

    def _eval_if_like_condition(self, ctx: EzLangParser.IfLikeExprContext, negated: bool = False):
        cond = self._eval(ctx.expression(0))
        cond = self._truthy_value(cond)
        return self.builder.not_(cond) if negated else cond

    def _eval_if_like_with_condition(self, ctx: EzLangParser.IfLikeExprContext, cond):
        if cond is None:
            return None
        cond = self._truthy_value(cond)

        then_bb = self.builder.append_basic_block(name="if_then")
        else_bb = self.builder.append_basic_block(name="if_else")
        merge_bb = self.builder.append_basic_block(name="if_merge")

        self.builder.cbranch(cond, then_bb, else_bb)
        then_ctx, else_ctx = self._if_like_branch_ctxs(ctx)
        eval_branch = self._eval_control_flow_body if else_ctx is None else self._eval

        self.builder.position_at_start(then_bb)
        then_val = eval_branch(then_ctx) if then_ctx is not None else None
        then_block = self.builder.block
        if not then_block.is_terminated:
            self.builder.branch(merge_bb)

        self.builder.position_at_start(else_bb)
        else_val = eval_branch(else_ctx) if else_ctx is not None else None
        else_block = self.builder.block
        if not else_block.is_terminated:
            self.builder.branch(merge_bb)

        self.builder.position_at_start(merge_bb)
        if else_ctx is None:
            return None
        if then_val and else_val and then_val.type == else_val.type:
            phi = self.builder.phi(then_val.type)
            phi.add_incoming(then_val, then_block)
            phi.add_incoming(else_val, else_block)
            return phi
        return then_val or else_val

    def _short_circuit_eval(self, left, rhs_evaluators, op: str):
        if self.builder is None or not rhs_evaluators:
            return left

        b_false = ir.Constant(ir.IntType(1), 0)
        b_true = ir.Constant(ir.IntType(1), 1)
        left = self._truthy_value(left)

        for i, rhs_eval in enumerate(rhs_evaluators):
            rhs_bb = self.builder.append_basic_block(name=f"{op}_rhs")
            merge_bb = self.builder.append_basic_block(name=f"{op}_merge")

            if op == 'and':
                skip_val = b_false
                self.builder.cbranch(left, rhs_bb, merge_bb)
            else:
                skip_val = b_true
                self.builder.cbranch(left, merge_bb, rhs_bb)

            from_block = self.builder.block
            self.builder.position_at_start(rhs_bb)
            right = rhs_eval()
            right = self._truthy_value(right)
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
            left = self._truthy_value(left)

        return left

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
                store_val = self._emit_locked_assignment(name, target, store_val, op_ctx)
            elif name in self.globals:
                target = self.globals[name]
                if name in self._decorated_globals and self._is_meta_type(target.type.pointee):
                    store_val = self._emit_lock_access(
                        name,
                        "write",
                        lambda: self._store_decorated_global(name, target, store_val, op_ctx),
                    )
                else:
                    store_val = self._emit_locked_assignment(name, target, store_val, op_ctx)

        return store_val if name and val is not None else val

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
            if (
                self.current_function is not None
                and self.current_function.name == 'main'
                and not isinstance(self.current_function.function_type.return_type, ir.VoidType)
            ):
                self.builder.ret(self._zero_constant(self.current_function.function_type.return_type))
            else:
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
            var_name = ctx.VAR_IDENTIFIER().getText()
            range_ctx = ctx.rangeExpression()
            range_exprs = range_ctx.orExpression()

            if range_ctx.ELLIPSIS() is None:
                iterable = self._eval(range_exprs[0]) if range_exprs else None
                list_ptr = self._as_list_ptr(iterable) if iterable is not None else None
                if list_ptr is not None:
                    i64 = ir.IntType(64)
                    elem_type = self._list_elem_type(list_ptr)
                    loop_var = self.builder.alloca(elem_type, name=var_name)
                    index_ptr = self.builder.alloca(i64, name=f"_{var_name}_index")
                    self.builder.store(ir.Constant(i64, 0), index_ptr)
                    self.locals[var_name] = loop_var
                    self._remember_type_name(var_name, elem_type)
                    loop_step_bb = self.builder.append_basic_block(name="loop_step")

                    self.builder.branch(loop_header_bb)
                    self.builder.position_at_start(loop_header_bb)
                    index_val = self.builder.load(index_ptr, name=f"{var_name}_index")
                    length = self._list_length(list_ptr)
                    cond = self.builder.icmp_unsigned('<', index_val, length)
                    self.builder.cbranch(cond, loop_body_bb, loop_exit_bb)

                    self.builder.position_at_start(loop_body_bb)
                    item = self.builder.load(self._list_element_ptr(list_ptr, index_val), name=var_name)
                    self.builder.store(item, loop_var)
                    self.loop_exit_blocks.append(loop_exit_bb)
                    self.loop_continue_blocks.append(loop_step_bb)
                    self._eval(body_ctx)
                    self.loop_exit_blocks.pop()
                    self.loop_continue_blocks.pop()
                    if not self.builder.block.is_terminated:
                        self.builder.branch(loop_step_bb)

                    self.builder.position_at_start(loop_step_bb)
                    index_val = self.builder.load(index_ptr, name=f"{var_name}_index")
                    next_val = self.builder.add(index_val, ir.Constant(i64, 1))
                    self.builder.store(next_val, index_ptr)
                    self.builder.branch(loop_header_bb)

                    self.locals.pop(var_name, None)
                    self._locals_type_names.pop(var_name, None)
                    self.builder.position_at_start(loop_exit_bb)
                    return None

            # 范围循环: loop i in start...end { ... }
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
        """match { (pat) ? body, ... }：命中后默认继续检查下一分支。"""
        if self.builder is None:
            return None

        clauses = list(ctx.matchClause())
        if not clauses:
            return None

        merge_bb = self.builder.append_basic_block(name="match_merge")

        self.loop_exit_blocks.append(merge_bb)
        try:
            for i, clause in enumerate(clauses):
                is_last = (i == len(clauses) - 1)
                next_bb = merge_bb if is_last else self.builder.append_basic_block(name="match_next")
                body_bb = self.builder.append_basic_block(name="match_body")

                cond = self._eval(clause.expression())
                cond = self._truthy_value(cond)
                self.builder.cbranch(cond, body_bb, next_bb)

                self.builder.position_at_start(body_bb)
                self.loop_continue_blocks.append(next_bb)
                try:
                    if clause.statement() is not None:
                        self._eval_control_flow_body(clause.statement())
                    elif clause.block() is not None:
                        self._eval(clause.block())
                finally:
                    self.loop_continue_blocks.pop()

                if not self.builder.block.is_terminated:
                    self.builder.branch(next_bb)

                if not is_last:
                    self.builder.position_at_start(next_bb)
        finally:
            self.loop_exit_blocks.pop()

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

    def _if_like_branch_ctxs(self, ctx: EzLangParser.IfLikeExprContext):
        """返回类 if 的 then/else 分支节点；分支可为 expression 或 block。"""
        then_ctx = ctx.getChild(4) if ctx.getChildCount() > 4 else None
        else_ctx = ctx.getChild(6) if ctx.COLON() is not None and ctx.getChildCount() > 6 else None
        return then_ctx, else_ctx

    def visitIfLikeExpr(self, ctx: EzLangParser.IfLikeExprContext):
        """(cond) ? expr : expr 或 (cond) ? { block } : { block }"""
        if self.builder is None:
            return None

        # 条件
        cond = self._eval(ctx.expression(0))
        if cond is None:
            return None
        cond = self._truthy_value(cond)

        then_bb = self.builder.append_basic_block(name="if_then")
        else_bb = self.builder.append_basic_block(name="if_else")
        merge_bb = self.builder.append_basic_block(name="if_merge")

        self.builder.cbranch(cond, then_bb, else_bb)
        then_ctx, else_ctx = self._if_like_branch_ctxs(ctx)

        # then 分支
        self.builder.position_at_start(then_bb)
        then_val = None
        if then_ctx is not None:
            then_val = self._eval_control_flow_body(then_ctx) if else_ctx is None else self._eval(then_ctx)
        then_block = self.builder.block
        if not then_block.is_terminated:
            self.builder.branch(merge_bb)

        # else 分支
        self.builder.position_at_start(else_bb)
        else_val = None
        if else_ctx is not None:
            else_val = self._eval(else_ctx)
        else_block = self.builder.block
        if not else_block.is_terminated:
            self.builder.branch(merge_bb)

        # 合并
        self.builder.position_at_start(merge_bb)
        if else_ctx is None:
            return None
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
                   target_arch: Optional[str] = None, log_compile_min_level: Optional[int] = None,
                   ensure_entrypoint: bool = False, base_dir: Optional[Path | str] = None,
                   source_name: Optional[Path | str] = None):
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

    effective_base_dir = base_dir
    if effective_base_dir is None and source_name is not None:
        effective_base_dir = Path(source_name).parent

    codegen = LLVMCodeGenerator(
        module_name,
        compile_target=compile_target,
        target_arch=target_arch,
        log_compile_min_level=log_compile_min_level,
        ensure_entrypoint=ensure_entrypoint,
        base_dir=effective_base_dir,
        source_name=source_name,
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
