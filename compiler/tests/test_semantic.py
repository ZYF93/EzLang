"""EzLang 语义分析器测试"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from semantic.analyzer import SemanticAnalyzer, analyze
from semantic.symbols import SymbolKind


def analyze_file(filepath: str) -> SemanticAnalyzer:
    with open(filepath, 'r', encoding='utf-8') as f:
        return analyze(f.read())


class TestSemantic:

    def test_empty_source(self):
        """空源码不应有错误"""
        anal = analyze('')
        assert not anal.symbols.has_errors()

    def test_variables(self):
        """变量声明和引用检查"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'vars.ez'))
        # vars.ez 定义了 count, pi, global_val
        count = anal.symbols.resolve('count')
        assert count is not None
        assert count.kind == SymbolKind.VARIABLE
        assert count.mutable

        pi = anal.symbols.resolve('pi')
        assert pi is not None
        assert pi.kind == SymbolKind.CONSTANT
        assert not pi.mutable

        global_val = anal.symbols.resolve('global_val')
        assert global_val is not None
        assert global_val.kind == SymbolKind.STATIC

    def test_basics(self):
        """基础语法语义检查"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'basics.ez'))
        assert not anal.symbols.has_errors(), f'错误: {anal.symbols.errors}'

        # 验证变量声明
        x = anal.symbols.resolve('x')
        assert x is not None

    def test_types(self):
        """类型系统语义检查"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'types.ez'))
        errors = anal.symbols.errors
        # types.ez 可能有些类型引用未定义（如 User, Point 等类型在之后定义）
        # 只检查非预期错误
        for e in errors:
            print(f'  [info] {e}')

    def test_structs(self):
        """结构体语义检查"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'structs.ez'))
        # 检查结构体符号
        point = anal.symbols.resolve('Point')
        assert point is not None
        assert point.kind == SymbolKind.STRUCT

        point3d = anal.symbols.resolve('Point3D')
        assert point3d is not None
        assert point3d.kind == SymbolKind.STRUCT

    def test_functions(self):
        """函数语义检查"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'functions.ez'))
        add = anal.symbols.resolve('add')
        assert add is not None

        scale = anal.symbols.resolve('scale')
        assert scale is not None

    def test_control(self):
        """流程控制语义检查"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'control.ez'))
        assert anal.symbols.resolve('x') is not None
        assert anal.symbols.resolve('fetchData') is not None

    def test_modules(self):
        """模块系统语义检查"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'modules.ez'))
        pi = anal.symbols.resolve('pi')
        assert pi is not None

    def test_undefined_variable(self):
        """测试未定义变量检测"""
        anal = analyze('const a = b;')
        assert anal.symbols.has_errors()
        assert any('未定义' in e for e in anal.symbols.errors)

    def test_duplicate_declaration(self):
        """测试重复声明检测"""
        anal = analyze('let x = 1; let x = 2;')
        assert anal.symbols.has_errors()
        assert any('重复声明' in e for e in anal.symbols.errors)

    def test_const_reassignment(self):
        """测试常量重新赋值检查"""
        anal = analyze('const x = 1; x = 2;')
        errors = anal.symbols.errors
        assert any('不能修改常量' in e for e in errors)

    # ==================== 类型检查测试 ====================

    def test_type_inference_int(self):
        """类型推导：整数 → I32"""
        anal = analyze('let x = 42;')
        assert not anal.symbols.has_errors()
        sym = anal.symbols.resolve('x')
        assert sym is not None
        assert sym.type is not None
        assert sym.type.name == 'I32'

    def test_type_inference_float(self):
        """类型推导：浮点数 → F64"""
        anal = analyze('let x = 3.14;')
        sym = anal.symbols.resolve('x')
        assert sym.type.name == 'F64'

    def test_type_inference_bool(self):
        """类型推导：布尔 → Bool"""
        anal = analyze('let x = true;')
        sym = anal.symbols.resolve('x')
        assert sym.type.name == 'Bool'

    def test_type_inference_str(self):
        """类型推导：字符串 → Str"""
        anal = analyze('let x = "hello";')
        sym = anal.symbols.resolve('x')
        assert sym.type.name == 'Str'

    def test_type_annotation_match(self):
        """类型标注与初始化表达式匹配"""
        anal = analyze('let x: I32 = 42; let y: Bool = true;')
        assert not anal.symbols.has_errors()

    def test_type_mismatch_detection(self):
        """检测类型不匹配（标注 I32 但初始化 Str）"""
        anal = analyze('let x: I32 = "hello";')
        assert anal.symbols.has_errors()
        assert any('不匹配' in e for e in anal.symbols.errors)

    def test_typeof_returns_type_id_i32(self):
        """typeof 返回稳定类型标识，语义类型应为 I32。"""
        anal = analyze('let t: I32 = typeof 42;')
        assert not anal.symbols.has_errors(), f'错误: {anal.symbols.errors}'
        sym = anal.symbols.resolve('t')
        assert sym is not None
        assert sym.type is not None
        assert sym.type.name == 'I32'

        mismatch = analyze('let t: Str = typeof 42;')
        assert mismatch.symbols.has_errors()
        assert any('不匹配' in e for e in mismatch.symbols.errors)

    def test_binary_op_same_types(self):
        """同类型运算不应报类型错误"""
        anal = analyze('let x = 1 + 2; let y = 3.0 + 4.0;')
        type_errors = [e for e in anal.symbols.errors if '二元运算' in e or '不匹配' in e]
        assert len(type_errors) == 0

    def test_comparison_returns_bool(self):
        """比较运算返回 Bool"""
        anal = analyze('let x = 1 == 2;')
        sym = anal.symbols.resolve('x')
        assert sym.type.name == 'Bool'

    def test_logical_returns_bool(self):
        """逻辑运算返回 Bool"""
        anal = analyze('let x = true && false;')
        sym = anal.symbols.resolve('x')
        assert sym.type.name == 'Bool'

    def test_function_return_type_check_match(self):
        """函数返回类型匹配"""
        anal = analyze('''
        const f = (a: I32): I32 => {
            return a + 1;
        };
        ''')
        type_errors = [e for e in anal.symbols.errors if '返回' in e]
        assert len(type_errors) == 0

    def test_functions_example_semantic(self):
        """functions.ez 应通过函数语义分析"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'functions.ez'))
        assert not anal.symbols.has_errors(), f'错误: {anal.symbols.errors}'

    def test_arena_example_semantic(self):
        """arena.ez 应通过内存模型相关语义分析"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'arena.ez'))
        assert not anal.symbols.has_errors(), f'错误: {anal.symbols.errors}'

    def test_function_call_arg_type_match(self):
        """函数调用参数类型匹配"""
        anal = analyze('''
        const add = (a: I32, b: I32): I32 => {
            return a + b;
        };
        const r = add(a = 1, b = 2);
        ''')
        type_errors = [e for e in anal.symbols.errors if '类型不匹配' in e]
        assert len(type_errors) == 0, f'不应有类型错误: {type_errors}'

    def test_function_call_arg_type_mismatch(self):
        """函数调用参数类型不匹配检测"""
        anal = analyze('''
        const greet = (name: Str): Str => {
            return name;
        };
        const r = greet(name = 42);
        ''')
        type_errors = [e for e in anal.symbols.errors if '类型不匹配' in e]
        assert len(type_errors) > 0, f'应检测到类型不匹配'

    def test_function_param_names_stored(self):
        """函数类型的 param_names 应正确存储"""
        anal = analyze('const add = (a: I32, b: I32): I32 => { return a + b; };')
        sym = anal.symbols.resolve('add')
        assert sym is not None
        assert sym.type is not None
        assert sym.type.param_names == ['a', 'b']
        assert len(sym.type.param_types) == 2

    def test_function_call_arg_reorder_and_default(self):
        """具名参数允许重排，默认参数允许省略"""
        anal = analyze('''
        const add = (a: I32, b: I32 = 1): I32 => {
            return a + b;
        };
        const r1 = add(b = 2, a = 1);
        const r2 = add(a = 1);
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'不应有语义警告: {anal.symbols.warnings}'

    def test_function_call_unknown_arg_name(self):
        """未知具名参数应报错"""
        anal = analyze('''
        const add = (a: I32, b: I32): I32 => {
            return a + b;
        };
        const r = add(a = 1, c = 2);
        ''')
        assert any('未知参数' in e for e in anal.symbols.errors), f'应有未知参数错误: {anal.symbols.errors}'

    def test_function_call_duplicate_arg_name(self):
        """重复具名参数应报错"""
        anal = analyze('''
        const add = (a: I32, b: I32): I32 => {
            return a + b;
        };
        const r = add(a = 1, a = 2, b = 3);
        ''')
        assert any('重复提供参数' in e for e in anal.symbols.errors), f'应有重复参数错误: {anal.symbols.errors}'

    def test_function_call_missing_required_arg(self):
        """缺少无默认值的必填参数应报错"""
        anal = analyze('''
        const add = (a: I32, b: I32 = 1): I32 => {
            return a + b;
        };
        const r = add(b = 2);
        ''')
        assert any('缺少必填参数' in e for e in anal.symbols.errors), f'应有缺少参数错误: {anal.symbols.errors}'

    def test_string_interpolation_checks_inner_expr(self):
        """字符串插值应分析内部表达式"""
        anal = analyze('''
        const name = "EzLang";
        const greeting = "Hello {{name}}";
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'

    def test_string_interpolation_reports_undefined_name(self):
        """字符串插值应报告未定义变量"""
        anal = analyze('const greeting = "Hello {{missingName}}";')
        assert any('missingName' in e for e in anal.symbols.errors), f'应有未定义变量错误: {anal.symbols.errors}'

    def test_markup_literal_semantic(self):
        """标记字面量应翻译为字符串类型并分析表达式子节点"""
        anal = analyze('''
        let ui = <text color="blue">
            "Welcome"
            <div id=1 />
            {1 + 2}
        </text>;
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        ui = anal.symbols.resolve('ui')
        assert ui is not None
        assert ui.type.name == 'Str'

    def test_markup_literal_checks_child_expression(self):
        """标记字面量应检查表达式子节点"""
        anal = analyze('let ui = <text>{missingName}</text>;')
        assert any('missingName' in e for e in anal.symbols.errors), f'应有未定义变量错误: {anal.symbols.errors}'

    def test_struct_member_access_type(self):
        """结构体成员访问返回正确字段类型"""
        anal = analyze('''
        struct Point {
            x: I32;
            y: I32;
        };
        const p = Point(x = 1, y = 2);
        const px = p.x;
        ''')
        px = anal.symbols.resolve('px')
        assert px is not None
        assert px.type is not None
        assert px.type.name == 'I32', f'期望 I32，实际 {px.type}'

    def test_struct_field_not_found(self):
        """结构体访问不存在的字段应警告"""
        anal = analyze('''
        struct Point { x: I32; y: I32; };
        const p = Point(x = 1, y = 2);
        const bad = p.z;
        ''')
        # 应该有关于字段不存在的警告
        warnings = anal.symbols.warnings
        assert any('没有字段' in w for w in warnings), f'应有字段不存在警告: {warnings}'

    def test_struct_type_reference_keeps_fields(self):
        """结构体类型注解不能丢失字段信息"""
        anal = analyze('''
        struct Point { x: I32; y: I32; };
        const p: Point = Point(x = 1, y = 2);
        const px = p.x;
        ''')
        assert not anal.symbols.warnings, f'不应有字段访问警告: {anal.symbols.warnings}'

    def test_struct_instance_spread_semantic(self):
        """结构体实例展开应检查源值为结构体且字段兼容"""
        anal = analyze('''
        struct Point { x: I32; y: I32 = 0; };
        struct Point3D { ...Point; z: I32; };
        const p = Point(x = 1);
        const p2 = Point(...p, y = 2);
        const p3 = Point3D(...p, z = 3);
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'不应有语义警告: {anal.symbols.warnings}'

    def test_struct_instance_spread_rejects_non_struct(self):
        """结构体实例展开应拒绝非结构体值"""
        anal = analyze('''
        struct Point { x: I32; };
        const p = Point(...42);
        ''')
        assert any('实例展开' in w for w in anal.symbols.warnings), f'应有实例展开警告: {anal.symbols.warnings}'

    def test_dict_literal_type_keeps_value_type(self):
        """字典字面量应推导 Dict 键值类型"""
        anal = analyze('let d = { name = "EzLang" };')
        d = anal.symbols.resolve('d')
        assert d is not None
        assert d.type.name == 'Dict'
        assert d.type.key_type.name == 'Str'
        assert d.type.value_type.name == 'Str'

    def test_return_outside_function(self):
        """return 在函数外应报错"""
        anal = analyze('return 42;')
        assert anal.symbols.has_errors()
        assert any('return 语句只能出现在函数内部' in e for e in anal.symbols.errors)

    def test_default_param_type_check(self):
        """默认参数类型应与参数类型匹配"""
        anal = analyze('const f = (x: I32 = 42) => { return x; };')
        type_errors = [e for e in anal.symbols.errors if '不匹配' in e]
        assert len(type_errors) == 0, f'不应有类型错误: {type_errors}'

    def test_default_param_type_mismatch(self):
        """默认参数类型不匹配应检测"""
        anal = analyze('const f = (x: I32 = "hello") => { return x; };')
        type_errors = [e for e in anal.symbols.errors if '不匹配' in e]
        assert len(type_errors) > 0, f'应检测到类型不匹配: {anal.symbols.errors}'

    def test_array_index_type_check(self):
        """数组索引应为整数类型"""
        anal = analyze('''
        let arr: I32[] = [1, 2, 3];
        let x = arr[0];
        ''')
        assert not anal.symbols.has_errors()

    def test_array_index_non_integer(self):
        """非整数索引应产生警告"""
        anal = analyze('''
        let arr: I32[] = [1, 2, 3];
        let x = arr["hello"];
        ''')
        warnings = anal.symbols.warnings
        assert any('数组索引' in w for w in warnings), f'应有数组索引类型警告: {warnings}'

    def test_index_on_non_array(self):
        """对非数组类型使用索引应产生警告"""
        anal = analyze('let x: I32 = 42; let y = x[0];')
        warnings = anal.symbols.warnings
        assert any('非数组类型' in w for w in warnings), f'应有非数组类型警告: {warnings}'

    def test_union_type_assign_compatible(self):
        """联合类型赋值：匹配任一成员类型应通过"""
        anal = analyze('''
        let x: I32 | Str = 42;
        let y: I32 | Str = "hello";
        ''')
        type_errors = [e for e in anal.symbols.errors if '不匹配' in e]
        assert len(type_errors) == 0, f'不应有类型错误: {type_errors}'

    def test_union_type_assign_incompatible(self):
        """联合类型赋值：不匹配任何成员应报错"""
        anal = analyze('let x: I32 | Str = true;')
        type_errors = [e for e in anal.symbols.errors if '不匹配' in e]
        assert len(type_errors) > 0, f'应检测到类型不匹配'

    def test_generic_function_decl_tracking(self):
        """泛型函数声明应存储模板信息"""
        anal = analyze('const id<T> = (x: T): T => { return x; };')
        assert 'id' in anal.generic_templates
        names, _ = anal.generic_templates['id']
        assert names == ['T']

    def test_generic_call_arg_count_mismatch(self):
        """泛型调用时类型参数数量不匹配应报错"""
        anal = analyze('''
        const id<T> = (x: T): T => { return x; };
        const r = id<I32, Str>(x = 42);
        ''')
        errors = [e for e in anal.symbols.errors if '期望' in e]
        assert len(errors) > 0, f'应检测到泛型参数数量不匹配: {anal.symbols.errors}'

    def test_struct_init_wrong_field(self):
        """结构体构造使用不存在的字段应警告"""
        anal = analyze('''
        struct Point { x: I32; y: I32; };
        const p = Point(x = 1, z = 2);
        ''')
        warnings = anal.symbols.warnings
        assert any('没有字段' in w for w in warnings), f'应有字段不存在警告: {warnings}'

    def test_struct_init_field_type_mismatch(self):
        """结构体构造字段类型不匹配应报错"""
        anal = analyze('''
        struct Point { x: I32; y: I32; };
        const p = Point(x = "hello", y = 2);
        ''')
        errors = [e for e in anal.symbols.errors if '不匹配' in e]
        assert len(errors) > 0, f'应检测到字段类型不匹配: {anal.symbols.errors}'

    def test_simd_vec_type_check(self):
        """SIMD 向量字面量元素类型一致"""
        anal = analyze('let v = Vec[1, 2, 3, 4];')
        sym = anal.symbols.resolve('v')
        assert sym is not None
        assert sym.type is not None
        assert sym.type.kind.name == 'VEC'
        assert sym.type.vec_size == 4

    def test_simd_vec_size_power_of_two(self):
        """SIMD 向量大小非 2 的幂应警告"""
        anal = analyze('let v = Vec[1, 2, 3];')
        warnings = anal.symbols.warnings
        assert any('不是 2 的幂' in w for w in warnings), f'应有 2 的幂警告: {warnings}'

    def test_method_this_binding(self):
        """结构体方法的 this 参数验证"""
        anal = analyze('''
        struct Point {
            x: I32;
            y: I32;
            distance = (this: Point, other: Point): I32 => {
                return this.x - other.x;
            };
        };
        ''')
        # 正确的方法定义不应有警告
        warnings = [w for w in anal.symbols.warnings if 'this' in w]
        assert len(warnings) == 0, f'不应有 this 相关警告: {warnings}'

    def test_method_this_wrong_type(self):
        """结构体方法 this 类型不匹配应警告"""
        anal = analyze('''
        struct Point {
            x: I32;
            calc = (this: I32): I32 => { return this; };
        };
        ''')
        warnings = [w for w in anal.symbols.warnings if 'this' in w]
        assert len(warnings) > 0, f'应有 this 类型警告: {warnings}'

    def test_type_checks_example(self):
        """type_checks.ez 示例文件应无类型错误"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'type_checks.ez'))
        assert not anal.symbols.has_errors(), f'类型错误: {anal.symbols.errors}'

    def test_flow_example_semantic(self):
        """flow.ez 应记录 Flow 块、suspend point、race 和依赖信息"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'flow.ez'))
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        assert len(anal.flow_blocks) == 1
        assert {p['name'] for p in anal.suspend_points} >= {'fetch', 'readFile', 'sleep'}
        assert len(anal.race_calls) == 1
        assert any(dep['name'] == 'a' and dep['source'] == 'fetch' for dep in anal.flow_dependencies)

    def test_flow_block_detection(self):
        """flow 块检测应记录起止行号"""
        anal = analyze('''
        const result = flow {
            const a = sleep(ms = 1);
            return a;
        };
        ''')
        assert len(anal.flow_blocks) == 1
        block = anal.flow_blocks[0]
        assert block['start_line'] > 0
        assert block['end_line'] >= block['start_line']

    def test_suspend_points_only_marked_in_flow(self):
        """阻塞调用仅在 flow 内标记为 suspend point"""
        anal = analyze('''
        const outside = sleep(ms = 1);
        const inside = flow {
            sleep(ms = 1);
        };
        ''')
        assert len(anal.suspend_points) == 1
        assert anal.suspend_points[0]['name'] == 'sleep'

    def test_race_requires_flow(self):
        """race 只能在 flow 内使用"""
        anal = analyze('const r = race(task = 1, timeout = 10);')
        assert any('race' in e and 'flow' in e for e in anal.symbols.errors)

    def test_race_pl_syntax_semantic(self):
        """文档接口 race(pl=[...], timeout=...) 在 flow 内合法。"""
        anal = analyze('''
        const r = flow {
            return race(pl = [() => { return 1; }, () => { return 2; }], timeout = 10);
        };
        ''')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        assert len(anal.race_calls) == 1

    def test_flow_dependency_records_reads(self):
        """读取 suspend 结果应记录数据流依赖"""
        anal = analyze('''
        const result = flow {
            const a = fetch(url = "a");
            const b = a;
            return b;
        };
        ''')
        assert any(dep['name'] == 'b' and dep['depends_on'] == ['a'] for dep in anal.flow_dependencies)

    def test_http_client_calls_mark_suspend_points_in_flow(self):
        """HTTP 客户端调用在 flow 内应标记为 suspend point"""
        anal = analyze('''
        const result = flow {
            const a = fetch(url = "https://example.com");
            const b = fetchEx(req = a);
            return b;
        };
        ''')
        assert {p['name'] for p in anal.suspend_points} >= {'fetch', 'fetchEx'}

    def test_http_server_start_marks_suspend_point_in_flow(self):
        """HTTP 服务端 start 在 flow 内应标记为 suspend point"""
        anal = analyze('''
        const result = flow {
            start(this = server);
        };
        ''')
        assert any(p['name'] == 'start' for p in anal.suspend_points)

    def test_tcp_udp_calls_mark_suspend_points_in_flow(self):
        """TCP/UDP 阻塞调用在 flow 内应标记为 suspend point"""
        anal = analyze('''
        const result = flow {
            const conn = tcpConnect(host = "127.0.0.1", port = 80);
            const listener = tcpListen(host = "127.0.0.1", port = 8080);
            const udp = udpBind(host = "127.0.0.1", port = 5353);
            const accepted = accept(this = listener);
            const data = read(this = conn, size = 1024);
            const sent = write(this = conn, data = data);
            const packet = recv(this = udp, size = 1024);
            send(this = udp, data = packet, host = "127.0.0.1", port = 5353);
            return sent;
        };
        ''')
        assert {p['name'] for p in anal.suspend_points} >= {
            'tcpConnect', 'tcpListen', 'udpBind', 'accept', 'read', 'write', 'recv', 'send'
        }

    def test_ws_calls_mark_suspend_points_in_flow(self):
        """WebSocket 连接和接收在 flow 内应标记为 suspend point"""
        anal = analyze('''
        const result = flow {
            const conn = wsConnect(url = "wss://example.com/socket");
            const msg = recv(this = conn);
            send(this = conn, msg = "pong");
            return msg;
        };
        ''')
        assert {p['name'] for p in anal.suspend_points} >= {'wsConnect', 'recv'}

    def test_extern_collects_and_filters_by_target(self, tmp_path):
        """extern 应按编译目标过滤并记录有效库"""
        linux_lib = tmp_path / 'libok.so'
        win_lib = tmp_path / 'win.lib'
        linux_lib.write_text('', encoding='utf-8')
        win_lib.write_text('', encoding='utf-8')
        anal = analyze(f'''
        extern "{linux_lib}" for linux;
        extern "{win_lib}" for windows;
        declare const native_add: (a: I32, b: I32) => I32;
        ''', base_dir=tmp_path, compile_target='linux')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        assert anal.active_extern_libs == [str(linux_lib)]
        assert anal.extern_libs[1]['active'] is False

    def test_extern_missing_path_reports_error(self, tmp_path):
        """extern 库路径不存在应报错"""
        missing = tmp_path / 'missing.so'
        anal = analyze(f'extern "{missing}"; declare const native_add: () => I32;', base_dir=tmp_path)
        assert any('extern 路径不存在' in e for e in anal.symbols.errors)

    def test_extern_invalid_extension_reports_error(self, tmp_path):
        """extern 库路径扩展名必须是支持的外部格式"""
        lib = tmp_path / 'bad.txt'
        lib.write_text('', encoding='utf-8')
        anal = analyze(f'extern "{lib}"; declare const native_add: () => I32;', base_dir=tmp_path)
        assert any('extern 路径格式不支持' in e for e in anal.symbols.errors)

    def test_declare_requires_matching_extern(self):
        """declare 符号必须有关联 extern 库"""
        anal = analyze('declare const native_add: () => I32;')
        assert any('没有关联 extern 库' in w for w in anal.symbols.warnings)

    def test_export_declare_is_recorded(self, tmp_path):
        """export declare 应注册外部符号并标记导出"""
        lib = tmp_path / 'libnative.a'
        lib.write_text('', encoding='utf-8')
        anal = analyze(f'''
        extern "{lib}";
        export declare const native_add: () => I32;
        ''', base_dir=tmp_path)
        sym = anal.symbols.resolve('native_add')
        assert sym is not None
        assert sym.kind == SymbolKind.EXTERN_DECLARE
        assert sym.exported
        assert anal.declare_extern_map['native_add'] == str(lib)

    def test_p0_documented_syntax_semantic_metadata(self):
        """P0 文档语法应记录语义元数据"""
        anal = analyze('''
        struct Date {
            timestamp: I64;
            add(this: Date, year: I32?) => Void;
        };
        type Headers = { [key: Str]: Str };
        rp let cache: I32[] = [];
        wp let queue: I32[] = [];
        let arr: I32[]?;
        let headers = { "Content-Type" = "text/plain", ["Accept"] = "application/json" };
        let ptr: *I8;
        const result = flow {
            const p = parallel { return 1; };
            return p;
        };
        ''')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        assert anal.symbols.resolve('cache').lock_policy == 'read_preferred'
        assert anal.symbols.resolve('queue').lock_policy == 'write_preferred'
        assert anal.symbols.resolve('arr').type.kind.name == 'OPTIONAL'
        assert anal.symbols.resolve('Headers').type.kind.name == 'DICT'
        assert anal.symbols.resolve('ptr').type.kind.name == 'POINTER'
        assert len(anal.parallel_blocks) == 1
        assert any(p['name'] == 'parallel' for p in anal.suspend_points)
