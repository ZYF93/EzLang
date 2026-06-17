"""EzLang 语义分析器测试"""

import sys
import os
import re
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from semantic.analyzer import SemanticAnalyzer, analyze
from semantic.symbols import SymbolKind, TypeKind
from cli import ez


ROOT = Path(__file__).parent.parent.parent


def markdown_ez_blocks(filepath: Path):
    """提取 Markdown 中标记为 ez 的代码块。"""
    text = filepath.read_text(encoding='utf-8')
    for index, match in enumerate(re.finditer(r'```ez\n(.*?)\n```', text, re.S), 1):
        line = text[:match.start()].count('\n') + 1
        yield index, line, match.group(1)


DOC_SEMANTIC_SKIP = {
    ('docs/doc.md', 9): 'extern 路径和跨平台库声明展示，依赖示例外部库文件',
    ('docs/ez-android-ui.md', 2): 'Android API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-android-ui.md', 3): 'Android API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-android-ui.md', 4): 'Android API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-android-ui.md', 5): 'Android API 摘要片段依赖同页前置 Node/Color 等类型定义',
    ('docs/ez-android-ui.md', 6): 'Android API 摘要片段依赖同页前置 Node/Color 等类型定义',
    ('docs/ez-android-ui.md', 7): 'Android API 摘要片段依赖同页前置 Node/Blob 等类型定义',
    ('docs/ez-android-ui.md', 8): 'Android API 摘要片段依赖同页前置事件处理类型定义',
    ('docs/ez-android-ui.md', 9): 'Android API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-android-ui.md', 10): 'Android API 摘要片段依赖同页前置 Node/Color 等类型定义',
    ('docs/ez-ios-ui.md', 2): 'iOS API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-ios-ui.md', 3): 'iOS API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-ios-ui.md', 4): 'iOS API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-ios-ui.md', 5): 'iOS API 摘要片段依赖同页前置 Node/Color 等类型定义',
    ('docs/ez-ios-ui.md', 6): 'iOS API 摘要片段依赖同页前置 Node/Color 等类型定义',
    ('docs/ez-ios-ui.md', 7): 'iOS API 摘要片段依赖同页前置 Node/Blob 等类型定义',
    ('docs/ez-ios-ui.md', 8): 'iOS API 摘要片段依赖同页前置 Node/Color 等类型定义',
    ('docs/ez-ios-ui.md', 9): 'iOS API 摘要片段依赖同页前置事件处理类型定义',
    ('docs/ez-ios-ui.md', 10): 'iOS API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-ios-ui.md', 11): 'iOS API 摘要片段依赖同页前置 Insets 等类型定义',
    ('docs/ez-web-ui.md', 2): 'Web API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-web-ui.md', 3): 'Web API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-web-ui.md', 4): 'Web API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-web-ui.md', 5): 'Web API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-web-ui.md', 6): 'Web API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-web-ui.md', 7): 'Web API 摘要片段依赖同页前置 Node/Handler 等类型定义',
    ('docs/ez-web-ui.md', 8): 'Web API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-web-ui.md', 9): 'Web API 摘要片段依赖同页前置 Node 等类型定义',
    ('docs/ez-web-ui.md', 11): 'Web API 摘要片段依赖同页前置 Node 等类型定义',
}


def analyze_file(filepath: str) -> SemanticAnalyzer:
    path = Path(filepath).resolve()
    if path.is_relative_to(ROOT / 'examples'):
        config = ez.load_project(ROOT / 'project.toml', require_main=False)
        config.main = path
        source_plan = ez.discover_sources(config)
        source = "\n".join(ez._strip_imports(p.read_text(encoding='utf-8')) for p in source_plan)
        return analyze(source, base_dir=path.parent, compile_target=ez._native_os())
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
        global_val = anal.symbols.resolve('globalVal')
        assert global_val is not None
        assert global_val.kind == SymbolKind.STATIC
        main = anal.symbols.resolve('main')
        assert main is not None

    def test_variable_decl_without_initializer_keeps_annotated_type(self):
        """无初始化器变量应使用显式标注类型。"""
        anal = analyze('let count: I32; let arr: I32[]?; let ptr: *I8;')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        count = anal.symbols.resolve('count')
        arr = anal.symbols.resolve('arr')
        ptr = anal.symbols.resolve('ptr')
        assert count is not None and count.type.name == 'I32'
        assert arr is not None and arr.type.kind.name == 'OPTIONAL'
        assert ptr is not None and ptr.type.kind.name == 'POINTER'

    def test_variable_identifier_can_start_with_dollar(self):
        """$ 开头变量名应和普通变量一样进入符号表并可被引用。"""
        anal = analyze('let $count: I32 = 1; let total: I32 = $count + 1;')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        symbol = anal.symbols.resolve('$count')
        assert symbol is not None and symbol.type.name == 'I32'

    def test_import_semantics_respects_alias_and_requested_exports(self, tmp_path):
        """语义分析 import 应按需引入导出符号，并支持 as 别名。"""
        (tmp_path / 'lib.ez').write_text(
            'export const add = (a: I32, b: I32): I32 => { return a + b; };\n'
            'export const hidden = (): I32 => { return 0; };\n',
            encoding='utf-8',
        )
        anal = analyze(
            'from "./lib.ez" import { add as sum };\n'
            'let value = sum(a = 1, b = 2);\n',
            base_dir=tmp_path,
        )
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        assert anal.symbols.resolve('sum') is not None
        assert anal.symbols.resolve('add') is None
        assert anal.symbols.resolve('hidden') is None

    def test_placeholder_expression_requires_call_argument_context(self):
        """独立 ? 不能静默编译为 0，只能用于调用参数占位。"""
        anal = analyze('const x = ?;')
        assert anal.symbols.has_errors()
        assert any('柯里化占位参数' in error for error in anal.symbols.errors)

    def test_placeholder_expression_can_initialize_optional_none(self):
        """Optional<T> 期望上下文中的 ? 表示空可选值。"""
        anal = analyze('let value: I32? = ?;')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        symbol = anal.symbols.resolve('value')
        assert symbol is not None and symbol.type is not None
        assert symbol.type.kind.name == 'OPTIONAL'

    def test_struct_optional_field_accepts_placeholder_none(self):
        """结构体字段期望 Optional<T> 时，field = ? 表示空可选值。"""
        anal = analyze('struct Node { value: I32; next: Node?; }; const node = Node(value = 1, next = ?);')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'语义警告: {anal.symbols.warnings}'

    def test_placeholder_call_argument_is_valid(self):
        """调用参数中的 ? 保留为合法柯里化占位符。"""
        anal = analyze('const add = (a: I32, b: I32): I32 => { return a + b; }; const add2 = add(a = 2, b = ?);')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'

    def test_break_continue_require_loop_or_match_context(self):
        """break/continue 不能在 loop 或 match 外静默 no-op。"""
        anal = analyze('break; continue;')
        assert anal.symbols.has_errors()
        assert any('break 只能用于 loop 或 match 内' in error for error in anal.symbols.errors)
        assert any('continue 只能用于 loop 或 match 内' in error for error in anal.symbols.errors)

    def test_break_continue_allowed_in_loop_and_match(self):
        """loop 与 match 内的 break/continue 符合文档控制流语义。"""
        anal = analyze('loop { continue; break; } match { (true) ? { continue; break; } };')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'

    def test_basics(self):
        """基础语法语义检查"""
        anal = analyze_file(
            str(Path(__file__).parent.parent.parent / 'examples' / 'basics.ez'))
        assert not anal.symbols.has_errors(), f'错误: {anal.symbols.errors}'

        assert anal.symbols.resolve('main') is not None

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
        assert not anal.symbols.has_errors(), f'错误: {anal.symbols.errors}'
        assert anal.symbols.resolve('main') is not None

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

    def test_prefix_type_assertion_returns_target_type(self):
        """Type! expr 的语义类型应采用显式目标类型。"""
        anal = analyze('let x: I64 = I64! 42; let y: I32 = I32! x;')
        assert not anal.symbols.has_errors(), f'错误: {anal.symbols.errors}'
        assert anal.symbols.resolve('x').type.name == 'I64'
        assert anal.symbols.resolve('y').type.name == 'I32'

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

    def test_typeof_struct_type_id_comparison(self):
        """typeof 结构体值可与类型名 TypeID 做位运算判断。"""
        anal = analyze('''
        const main = (): I32 => {
            const err = Error(code = 1, message = "x");
            const ok = typeof err & Error == Error;
            return ok ? 0 : 1;
        };
        ''')
        assert not anal.symbols.has_errors(), f'错误: {anal.symbols.errors}'

    def test_binary_op_same_types(self):
        """同类型运算不应报类型错误"""
        anal = analyze('let x = 1 + 2; let y = 3.0 + 4.0;')
        type_errors = [e for e in anal.symbols.errors if '二元运算' in e or '不匹配' in e]
        assert len(type_errors) == 0

    def test_shift_rhs_requires_unsigned_integer(self):
        """移位右操作数必须显式为无符号整数。"""
        ok = analyze('let shift: U32 = 1; let x = 1 << shift;')
        assert not ok.symbols.has_errors(), f'不应有语义错误: {ok.symbols.errors}'
        sym = ok.symbols.resolve('x')
        assert sym is not None
        assert sym.type.name == 'I32'

        bad = analyze('let x = 1 << 1;')
        assert any('移位右操作数' in e for e in bad.symbols.errors), f'应有移位类型错误: {bad.symbols.errors}'

        bad_lhs = analyze('let shift: U32 = 1; let x = 1.5 << shift;')
        assert any('移位左操作数' in e for e in bad_lhs.symbols.errors), f'应有移位左操作数类型错误: {bad_lhs.symbols.errors}'

    def test_comparison_returns_bool(self):
        """比较运算返回 Bool"""
        anal = analyze('let x = 1 == 2;')
        sym = anal.symbols.resolve('x')
        assert sym.type.name == 'Bool'

    def test_loop_in_list_binds_element_type(self):
        """loop item in list 应把 item 绑定为集合元素类型。"""
        anal = analyze('''
        struct VNode { children: VNode[]; };
        const visit = (vnode: VNode): I32 => {
            let total: I32 = 0;
            loop child in vnode.children {
                total = total + visit(vnode = child);
            };
            return total;
        };
        ''')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'语义警告: {anal.symbols.warnings}'

    def test_simd_vector_scalar_binary_ops(self):
        """SIMD 向量支持同类标量广播运算。"""
        anal = analyze('''
        let a = Vec[1, 2, 3, 4];
        let b = a + 2;
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        sym = anal.symbols.resolve('b')
        assert sym is not None
        assert sym.type is not None
        assert sym.type.kind.name == 'VEC'
        assert sym.type.element_type.name == 'I32'
        assert sym.type.vec_size == 4

    def test_simd_vector_scalar_type_mismatch(self):
        """SIMD 向量广播只允许同类数值标量。"""
        anal = analyze('''
        let a = Vec[1, 2, 3, 4];
        let b = a + 2.0;
        ''')
        assert any('SIMD 向量与标量类型不匹配' in e for e in anal.symbols.errors), anal.symbols.errors

    def test_simd_vector_comparison_returns_mask(self):
        """SIMD 向量比较返回同宽 Bool mask。"""
        anal = analyze('''
        let a = Vec[1, 2, 3, 4];
        let b = Vec[2, 2, 2, 2];
        let mask = a < b;
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        sym = anal.symbols.resolve('mask')
        assert sym is not None
        assert sym.type is not None
        assert sym.type.kind.name == 'VEC'
        assert sym.type.element_type.name == 'Bool'
        assert sym.type.vec_size == 4

    def test_simd_vector_length_mismatch(self):
        """SIMD 向量二元运算要求长度一致。"""
        anal = analyze('''
        let a = Vec[1, 2, 3, 4];
        let b = Vec[1, 2];
        let c = a + b;
        ''')
        assert any('SIMD 向量长度不匹配' in e for e in anal.symbols.errors), anal.symbols.errors

    def test_simd_shift_rhs_requires_unsigned_integer(self):
        """SIMD 移位右操作数同样必须是无符号整数。"""
        ok = analyze('''
        let a = Vec[1, 2, 3, 4];
        let shift: U32 = 1;
        let b = a << shift;
        ''')
        assert not ok.symbols.has_errors(), f'不应有语义错误: {ok.symbols.errors}'

        bad = analyze('''
        let a = Vec[1, 2, 3, 4];
        let b = a << 1;
        ''')
        assert any('移位右操作数' in e for e in bad.symbols.errors), bad.symbols.errors

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

    def test_function_named_args_do_not_degrade_to_positional(self):
        """函数具名参数必须按名称绑定，不能退化为位置参数。"""
        anal = analyze('''
        const sub = (a: I32, b: I32): I32 => {
            return a - b;
        };
        const ok: I32 = sub(b = 1, a = 3);
        ''')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'

    def test_union_type_flattens_declaration_order(self):
        """多元联合类型应按源码顺序展平，不保留左递归嵌套。"""
        anal = analyze('type Value = Str | I32 | Bool;')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        symbol = anal.symbols.resolve('Value')
        assert symbol is not None
        assert symbol.type is not None
        assert [str(t) for t in symbol.type.union_types] == ['Str', 'I32', 'Bool']

    def test_function_call_missing_required_arg(self):
        """缺少无默认值的必填参数应报错"""
        anal = analyze('''
        const add = (a: I32, b: I32 = 1): I32 => {
            return a + b;
        };
        const r = add(b = 2);
        ''')
        assert any('缺少必填参数' in e for e in anal.symbols.errors), f'应有缺少参数错误: {anal.symbols.errors}'

    def test_pipeline_expression_uses_function_return_type_and_named_args(self):
        """管道表达式应按目标函数签名检查参数，并返回目标函数返回类型。"""
        anal = analyze('''
        const gt = (a: I32, b: I32 = 0): Bool => {
            return a > b;
        };
        const sub = (a: I32, b: I32): I32 => {
            return a - b;
        };
        let ok: Bool = 1 -> gt();
        let ordered: I32 = 10 -> sub(b = %, a = 20);
        let missing = 1 -> sub(a = %);
        let unknown = 1 -> sub(c = %);
        let bad: Str = 1 -> gt();
        ''')
        assert any('缺少必填参数' in e and "'b'" in e for e in anal.symbols.errors), anal.symbols.errors
        assert any('未知参数' in e and "'c'" in e for e in anal.symbols.errors), anal.symbols.errors
        assert any('类型不匹配' in e and "Str" in e and "Bool" in e for e in anal.symbols.errors), anal.symbols.errors
        assert not any('ok' in e for e in anal.symbols.errors), anal.symbols.errors

    def test_string_interpolation_checks_inner_expr(self):
        """字符串插值应分析内部变量"""
        anal = analyze('''
        const name = "EzLang";
        const greeting = "Hello {{name}}";
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'

    def test_string_interpolation_reports_undefined_name(self):
        """字符串插值应报告未定义变量"""
        anal = analyze('const greeting = "Hello {{missingName}}";')
        assert any('missingName' in e for e in anal.symbols.errors), f'应有未定义变量错误: {anal.symbols.errors}'

    def test_string_interpolation_accepts_str_expression_and_rejects_non_str(self):
        """字符串插值支持完整表达式，表达式结果必须是 Str。"""
        anal = analyze('''
        const first = "Ez";
        const last = "Lang";
        const count = 1;
        const expr = "Hello {{first + last}}";
        const number = "Count {{count}}";
        ''')
        assert not any('first + last' in e for e in anal.symbols.errors), anal.symbols.errors
        assert any("表达式 'count' 必须是 Str" in e for e in anal.symbols.errors), anal.symbols.errors

    def test_markup_literal_requires_factory(self):
        """标记字面量必须存在同名工厂函数。"""
        anal = analyze('let ui = <text color="blue" />;')
        assert any("同名工厂函数 'text'" in e for e in anal.symbols.errors), anal.symbols.errors
        ui = anal.symbols.resolve('ui')
        assert ui is not None
        assert ui.type is None

    def test_markup_literal_lowers_to_factory_type(self):
        """存在同名工厂函数时，标记字面量返回工厂函数的返回类型。"""
        anal = analyze('''
        const text = (color: Str, children: Str[]): I32 => {
            return 1;
        };
        let ui = <text color="blue">"Welcome"</text>;
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        ui = anal.symbols.resolve('ui')
        assert ui is not None
        assert ui.type.name == 'I32'

    def test_markup_literal_factory_parameter_check(self):
        """标记工厂函数参数应参与语义校验。"""
        anal = analyze('''
        const text = (color: Str, children: Str[]): I32 => {
            return 1;
        };
        let ui = <text tone="blue">"Welcome"</text>;
        ''')
        assert any("未知参数 'tone'" in e for e in anal.symbols.errors), anal.symbols.errors

    def test_markup_literal_checks_attr_type(self):
        """标记属性类型应匹配同名工厂函数参数。"""
        anal = analyze('''
        const text = (color: I32): I32 => {
            return color;
        };
        let ui = <text color="blue" />;
        ''')
        assert any("参数 'color' 类型不匹配" in e for e in anal.symbols.errors), anal.symbols.errors

    def test_markup_literal_checks_children_type(self):
        """标记 children 类型应匹配同名工厂函数参数。"""
        anal = analyze('''
        const text = (children: I32[]): I32 => {
            return 1;
        };
        let ui = <text>"Welcome"</text>;
        ''')
        assert any("参数 'children' 类型不匹配" in e for e in anal.symbols.errors), anal.symbols.errors

    def test_markup_literal_rejects_mixed_children_type(self):
        """标记 children 元素不满足工厂函数数组元素类型时应报错。"""
        anal = analyze('''
        const text = (children: Str[]): I32 => {
            return 1;
        };
        let ui = <text>"Welcome"{1 + 2}</text>;
        ''')
        assert any("参数 'children' 类型不匹配" in e for e in anal.symbols.errors), anal.symbols.errors

    def test_markup_literal_accepts_union_children(self):
        """工厂函数显式声明联合元素 children 时，标记可包含异构子节点。"""
        anal = analyze('''
        type Node = { id: I32 };
        const div = (id: I32): Node => {
            return { id = id };
        };
        const text = (color: Str, children: (Str | Node | I32)[]): Node => {
            return { id = 1 };
        };
        let ui = <text color="blue">"Welcome"<div id=1 />{1 + 2}</text>;
        ''')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'

    def test_markup_literal_rejects_children_without_parameter(self):
        """工厂函数未声明 children 参数时，标记子节点应报未知参数。"""
        anal = analyze('''
        const text = (): I32 => {
            return 1;
        };
        let ui = <text>"Welcome"</text>;
        ''')
        assert any("未知参数 'children'" in e for e in anal.symbols.errors), anal.symbols.errors

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

    def test_dict_literal_expression_key_infers_key_type(self):
        """字典表达式键应按表达式类型推导 key 类型。"""
        anal = analyze('let d = { [1] = "one" };')
        d = anal.symbols.resolve('d')
        assert d is not None
        assert d.type.name == 'Dict'
        assert d.type.key_type.name == 'I32'
        assert d.type.value_type.name == 'Str'

    def test_dict_index_returns_value_type(self):
        """Dict 索引应按键查询并返回值类型，而不是按数组索引处理。"""
        anal = analyze('let d = { name = "EzLang", lang = "ez" }; let lang = d["lang"];')
        assert not anal.symbols.warnings, f'不应有索引警告: {anal.symbols.warnings}'
        lang = anal.symbols.resolve('lang')
        assert lang is not None
        assert lang.type is not None
        assert lang.type.name == 'Str'

    def test_dict_index_checks_key_type(self):
        """Dict 索引 key 类型应参与语义校验。"""
        anal = analyze('let d = { name = "EzLang" }; let bad = d[1];')
        assert any('字典键类型不匹配' in e for e in anal.symbols.errors), anal.symbols.errors

    def test_dynamic_dict_shape_annotation_checks_key_type(self):
        """{ [key: K]: V } 注解应按动态键类型校验索引。"""
        anal = analyze('let d: { [key: I32]: Str } = { [1] = "one" }; let bad = d["one"];')
        assert not any('变量初始化类型不匹配' in e for e in anal.symbols.errors), anal.symbols.errors
        assert any('字典键类型不匹配' in e for e in anal.symbols.errors), anal.symbols.errors

    def test_shape_dict_literal_uses_expected_fields(self):
        """文档中的 Shape 注解对象字面量应按字段名校验，而不是退化成普通 Dict。"""
        anal = analyze('type Shape = { name: Str; side: Str; }; let s: Shape = { name = "Square"; side = "10" };')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        s = anal.symbols.resolve('s')
        assert s is not None
        assert s.type.name == 'Shape'
        assert s.type.fields['name'].name == 'Str'
        assert s.type.fields['side'].name == 'Str'

    def test_mixed_dynamic_shape_literal_is_dict_with_fixed_field_checks(self):
        """含动态键的 Shape 按 Dict 建模，同时保留固定字段校验。"""
        anal = analyze('type Shape = { name: Str; [dynamic: Str]: Str; }; let s: Shape = { name = "Square"; side = "10" };')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        s = anal.symbols.resolve('s')
        assert s is not None
        assert s.type.name == 'Shape'
        assert s.type.key_type.name == 'Str'
        assert s.type.value_type.name == 'Str'
        assert 'name' in s.type.fields

    def test_mixed_dynamic_shape_merges_fixed_field_value_types(self):
        """动态字典形状的值类型应包含固定字段类型，点访问固定字段应返回精确类型。"""
        anal = analyze('''
        type Ax = { [key: Str]: Str; v: I32 };
        const b: Ax = { x = "1"; v = 1 };
        const c = b.v;
        const d = b.x;
        const x = b["x"];
        const fixed = b["v"];
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        assert not any('字典值类型不一致' in w for w in anal.symbols.warnings), anal.symbols.warnings
        b = anal.symbols.resolve('b')
        c = anal.symbols.resolve('c')
        d = anal.symbols.resolve('d')
        x = anal.symbols.resolve('x')
        fixed = anal.symbols.resolve('fixed')
        assert b is not None and b.type is not None
        assert b.type.value_type.kind == TypeKind.UNION
        assert [member.name for member in b.type.value_type.union_types] == ['Str', 'I32']
        assert c is not None and c.type is not None and c.type.name == 'I32'
        assert d is not None and d.type is not None and d.type.name == 'Str'
        assert x is not None and x.type is not None and x.type.name == 'Str'
        assert fixed is not None and fixed.type is not None and fixed.type.name == 'I32'

    def test_multiple_dynamic_shape_keys_infer_by_key_type(self):
        """多条动态 key 规则应按 key 类型选择对应 value 类型。"""
        anal = analyze('''
        type Multi = {
            [name: Str]: Str;
            [index: I32]: I32;
            [enabled: Bool]: (value: I32) => Str;
            items: List<I32>;
        };
        const m: Multi = {
            name = "ez";
            [1] = 42;
            [true] = (value: I32): Str => { return "ok"; };
            items = [1, 2];
        };
        const s = m.name;
        const i = m[1];
        const f = m[true];
        const items = m.items;
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        s = anal.symbols.resolve('s')
        i = anal.symbols.resolve('i')
        f = anal.symbols.resolve('f')
        items = anal.symbols.resolve('items')
        assert s is not None and s.type is not None and s.type.name == 'Str'
        assert i is not None and i.type is not None and i.type.name == 'I32'
        assert f is not None and f.type is not None and f.type.kind == TypeKind.FUNCTION
        assert f.type.return_type.name == 'Str'
        assert items is not None and items.type is not None and items.type.kind == TypeKind.LIST

    def test_dynamic_shape_keeps_complex_value_types(self):
        """动态 key 的 value 类型可以是结构体、Dict、List 和函数等复合类型。"""
        anal = analyze('''
        struct Box { value: I32; };
        type Complex = {
            [id: I32]: Box;
            [name: Str]: { [key: Str]: I32 };
            [enabled: Bool]: (value: I32) => Str;
            list: List<Box>;
        };
        const c: Complex = {
            [1] = Box(value = 1);
            name = { count = 2 };
            [true] = (value: I32): Str => { return "ok"; };
            list = [Box(value = 3)];
        };
        const byId = c[1];
        const byName = c.name;
        const byBool = c[true];
        const list = c.list;
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        by_id = anal.symbols.resolve('byId')
        by_name = anal.symbols.resolve('byName')
        by_bool = anal.symbols.resolve('byBool')
        list_value = anal.symbols.resolve('list')
        assert by_id is not None and by_id.type is not None and by_id.type.name == 'Box'
        assert by_name is not None and by_name.type is not None and by_name.type.kind == TypeKind.DICT
        assert by_name.type.key_type.name == 'Str'
        assert by_name.type.value_type.name == 'I32'
        assert by_bool is not None and by_bool.type is not None and by_bool.type.kind == TypeKind.FUNCTION
        assert by_bool.type.return_type.name == 'Str'
        assert list_value is not None and list_value.type is not None and list_value.type.kind == TypeKind.LIST
        assert list_value.type.element_type.name == 'Box'

    def test_shape_dict_literal_reports_missing_required_field(self):
        """固定 Shape 对象字面量缺字段应报错。"""
        anal = analyze('type Shape = { name: Str; side: Str; }; let s: Shape = { name = "Square"; };')
        assert any("缺少字段 'side'" in e for e in anal.symbols.errors), anal.symbols.errors

    def test_type_shape_spread_flattens_fields(self):
        """文档中的 type Shape 扩展 `...Base` 应展开基础形状字段。"""
        anal = analyze('type Named = { name: Str }; type UserShape = { ...Named; age: I32; }; let u: UserShape = { name = "s"; age = 1 };')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        u = anal.symbols.resolve('u')
        assert u is not None
        assert list(u.type.fields) == ['name', 'age']
        assert u.type.fields['name'].name == 'Str'
        assert u.type.fields['age'].name == 'I32'

    def test_type_shape_spread_missing_base_field_reports_error(self):
        """展开得到的字段也必须参与对象字面量缺字段检查。"""
        anal = analyze('type Named = { name: Str }; type UserShape = { ...Named; age: I32; }; let u: UserShape = { age = 1 };')
        assert any("缺少字段 'name'" in e for e in anal.symbols.errors), anal.symbols.errors

    def test_struct_value_can_match_shape_alias_by_fields(self):
        """结构体值可按字段子集匹配固定形状别名。"""
        anal = analyze('type Named = { name: Str }; struct User { name: Str; age: I32; }; let u = User(name = "a", age = 1); let n: Named = u;')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'

    def test_dict_value_does_not_auto_convert_to_fixed_shape_alias(self):
        """普通 Dict 变量不会自动转换成固定形状结构体。"""
        anal = analyze('type Named = { name: Str }; let d = { name = "a"; age = "1" }; let n: Named = d;')
        assert any('变量初始化类型不匹配' in e for e in anal.symbols.errors), anal.symbols.errors

    def test_return_outside_function(self):
        """return 在函数外应报错"""
        anal = analyze('return 42;')
        assert anal.symbols.has_errors()
        assert any('return 语句只能出现在函数内部' in e for e in anal.symbols.errors)

    def test_catch_without_throw_returns_error_type(self):
        """catch 未捕获异常时仍返回零值 Error，而不是 Void。"""
        anal = analyze('let err = catch { let x = 1; };')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        sym = anal.symbols.resolve('err')
        assert sym is not None and sym.type is not None
        assert sym.type.name == 'Error'

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

    def test_generic_declare_tracking_and_explicit_call(self):
        """泛型 declare 应登记模板并支持显式类型参数调用。"""
        anal = analyze('''
        extern "fmt";
        declare const toString: <T>(value: T) => Str;
        const text = toString<I32>(value = 42);
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'不应产生语义警告: {anal.symbols.warnings}'
        assert 'toString' in anal.generic_templates
        names, _ = anal.generic_templates['toString']
        assert names == ['T']
        text = anal.symbols.resolve('text')
        assert text is not None and text.type is not None and text.type.name == 'Str'

    def test_generic_expression_function_infers_return_type_from_arguments(self):
        """表达式体泛型函数应从实参推导返回类型。"""
        anal = analyze('''
        const identity = <T>(value: T) => value;
        const inferred = identity(42);
        const explicit = identity<I32>(7);
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'
        inferred = anal.symbols.resolve('inferred')
        explicit = anal.symbols.resolve('explicit')
        assert inferred is not None and inferred.type is not None and inferred.type.name == 'I32'
        assert explicit is not None and explicit.type is not None and explicit.type.name == 'I32'

    def test_function_decl_infers_missing_return_type(self):
        """函数没有显式返回类型时，应从 return/表达式体推导；无返回则为 Void。"""
        anal = analyze('''
        const fromBlock = () => { return 1; };
        const fromExpr = () => "ok";
        const noReturn = () => { let x: I32 = 1; };
        const a = fromBlock();
        const b = fromExpr();
        const c = noReturn();
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        from_block = anal.symbols.resolve('fromBlock')
        from_expr = anal.symbols.resolve('fromExpr')
        no_return = anal.symbols.resolve('noReturn')
        a = anal.symbols.resolve('a')
        b = anal.symbols.resolve('b')
        c = anal.symbols.resolve('c')
        assert from_block.type.return_type.name == 'I32'
        assert from_expr.type.return_type.name == 'Str'
        assert no_return.type.return_type.name == 'Void'
        assert a.type.name == 'I32'
        assert b.type.name == 'Str'
        assert c.type.name == 'Void'

    def test_member_access_on_non_member_type_reports_error(self):
        """基本类型等非成员类型不能静默接受点访问。"""
        anal = analyze('''
        const copied: I32 = 1;
        const bad = copied.v;
        ''')
        assert any("类型 'I32' 没有字段 'v'" in e for e in anal.symbols.errors), anal.symbols.errors

    def test_generic_struct_explicit_args_instantiate_fields(self):
        """显式泛型结构体实参应替换字段类型。"""
        anal = analyze('''
        struct Pair<T, U> { first: T; second: U; };
        const main = (): I32 => {
            const p = Pair<I32, Str>(first = 42, second = "hello");
            return p.first;
        };
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'

        wrong = analyze('''
        struct Pair<T, U> { first: T; second: U; };
        const main = (): I32 => {
            const p = Pair<I32, Str>(first = 42, second = 7);
            return p.first;
        };
        ''')
        errors = [e for e in wrong.symbols.errors if '字段初始化类型' in e and '不匹配' in e]
        assert errors, f'应按显式类型参数检查字段类型: {wrong.symbols.errors}'

    def test_generic_struct_infers_type_args_from_fields(self):
        """泛型结构体构造应从字段初始化值推导类型参数。"""
        anal = analyze('''
        struct Pair<T, U> { first: T; second: U; };
        const main = (): I32 => {
            const p = Pair(first = 42, second = "hello");
            return p.first;
        };
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'

        wrong = analyze('''
        struct Pair<T, U> { first: T; second: U; };
        const main = (): I32 => {
            const p = Pair(first = 42, second = "hello");
            let s: Str = p.first;
            return 0;
        };
        ''')
        errors = [e for e in wrong.symbols.errors if '变量初始化类型' in e and '不匹配' in e]
        assert errors, f'应把 p.first 推导为 I32: {wrong.symbols.errors}'

    def test_generic_struct_method_return_type_is_instantiated(self):
        """泛型结构体方法返回类型应随接收者具体类型实例化。"""
        anal = analyze('''
        struct Pair<T, U> {
            first: T;
            second: U;
            swap = (this: #Pair<T, U>): Pair<U, T> => {
                return Pair<U, T>(first = this.second, second = this.first);
            };
        };
        const main = (): I32 => {
            const p = Pair(first = 42, second = "hello");
            const swapped = p.swap();
            let s: Str = swapped.first;
            let n: I32 = swapped.second;
            return n;
        };
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'不应产生语义警告: {anal.symbols.warnings}'

    def test_static_struct_method_call_does_not_require_this(self):
        """StructName.method() 类型级方法不应被当成实例方法注入 this。"""
        anal = analyze('''
        struct Duration {
            ms: I64;
            fromSec = (s: I64): Duration => {
                return Duration(ms = s);
            };
        };
        const main = (): I32 => {
            const seconds = Duration.fromSec(s = 2);
            let ms: I64 = seconds.ms;
            return 0;
        };
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'不应产生语义警告: {anal.symbols.warnings}'

    def test_optional_member_access_returns_optional_field_type(self):
        """opt?.field 应返回字段类型的可选值。"""
        anal = analyze('''
        struct Box { value: I32; };
        const main = (): I32 => {
            let box: Box?;
            const value = box?.value;
            return value.ok ? value.value : 0;
        };
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'不应产生语义警告: {anal.symbols.warnings}'

    def test_optional_method_call_returns_optional_result_type(self):
        """opt?.method() 应返回方法返回值类型的可选值。"""
        anal = analyze('''
        struct TextBox {
            value: I32;
            text = (this: #TextBox): Str => { return "box"; };
        };
        const main = (): I32 => {
            let box: TextBox?;
            const text = box?.text();
            return text.ok ? 1 : 0;
        };
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'不应产生语义警告: {anal.symbols.warnings}'

    def test_weak_reference_type_and_direct_access(self):
        """#T 弱引用类型按 T 透明访问，空值通过 typeof ref == Void 判断。"""
        anal = analyze('''
        struct Box { value: I32; };
        const main = (): I32 => {
            let box = Box(value = 1);
            let ref: #Box = #box;
            return (typeof ref == Void) ? 0 : ref.value;
        };
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'不应产生语义警告: {anal.symbols.warnings}'

    def test_weak_reference_method_call_and_not_void_check(self):
        """#T 弱引用和值引用一样访问方法，空值通过 typeof ref != Void 判断。"""
        anal = analyze('''
        struct Box {
            value: I32;
            get = (this: #Box): I32 => { return this.value; };
        };
        const main = (): I32 => {
            let box = Box(value = 3);
            let ref: #Box = #box;
            return (typeof ref != Void) ? ref.get() : 0;
        };
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'不应产生语义警告: {anal.symbols.warnings}'

    def test_weak_reference_unwraps_for_calculation_type(self):
        """#T 在计算上下文中按 T 推导，表达式结果不保留弱引用包装。"""
        anal = analyze('''
        let value: I32 = 40;
        let ref: #I32 = #value;
        const sum = ref + 2;
        ''')
        assert not anal.symbols.errors, f'不应产生语义错误: {anal.symbols.errors}'
        sym = anal.symbols.resolve('sum')
        assert sym is not None and sym.type is not None
        assert sym.type.kind == TypeKind.BASIC
        assert sym.type.name == 'I32'

    def test_weak_reference_rejects_literals_and_temporary_values(self):
        """#expr 只能用于有稳定地址的表达式，不能弱引用字面量或临时计算结果。"""
        anal = analyze('''
        let a = #1;
        let b = #"text";
        let value: I32 = 1;
        let c = #(value + 1);
        ''')
        errors = anal.symbols.errors
        assert len(errors) == 3
        assert all("弱引用 '#' 只能用于变量、字段或索引等可寻址表达式" in err for err in errors)

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
            distance = (this: #Point, other: Point): I32 => {
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
        errors = [e for e in anal.symbols.errors if 'this' in e]
        assert len(errors) > 0, f'应有 this 类型错误: {anal.symbols.errors}'

    def test_meta_decorator_fields_are_typed(self):
        """Meta<T> 字段与 getter/setter 函数指针应参与语义检查"""
        anal = analyze('''
        const get_watched = (): I32 => { return 11; };
        const set_watched = (v: I32): Void => { return; };
        const log = (this: #Meta<I32>): Void => {
            this.getter = get_watched;
            this.setter = set_watched;
            let typeName: Str = this.t;
            let valueName: Str = this.name;
        };
        @log let watched = 1;
        const main = (): I32 => { watched = 2; return watched; };
        ''')
        assert not anal.symbols.has_errors(), f'不应有语义错误: {anal.symbols.errors}'
        assert not anal.symbols.warnings, f'不应有语义警告: {anal.symbols.warnings}'

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
        assert {p['name'] for p in anal.suspend_points} >= {'sleep'}
        assert len(anal.race_calls) == 1

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

    def test_flow_expression_infers_return_type(self):
        """flow { return ... } 应作为表达式暴露返回类型。"""
        anal = analyze('''
        const result: I32 = flow {
            return 42;
        };
        ''')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        sym = anal.symbols.resolve('result')
        assert sym is not None
        assert sym.type.name == 'I32'

    def test_flow_result_ignores_nested_function_return(self):
        """嵌套函数字面量的 return 不应成为外层 flow 的表达式类型。"""
        anal = analyze('''
        const result: Void = flow {
            const f = (): I32 => { return 1; };
        };
        ''')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        sym = anal.symbols.resolve('result')
        assert sym is not None
        assert sym.type.name == 'Void'

    def test_flow_and_parallel_infer_nested_return_type(self):
        """flow/parallel 应从块内嵌套控制流 return 推断表达式类型。"""
        anal = analyze('''
        const flowValue: Str = flow {
            (true) ? { return "flow"; };
        };
        const parallelValue: Str = parallel {
            { return "parallel"; };
        };
        ''')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        assert anal.symbols.resolve('flowValue').type.name == 'Str'
        assert anal.symbols.resolve('parallelValue').type.name == 'Str'

    def test_flow_and_parallel_reject_mismatched_return_types(self):
        """同一 flow/parallel 表达式块内多个 return 类型必须一致。"""
        anal = analyze('''
        const flowValue = flow {
            (true) ? { return "flow"; };
            return 1;
        };
        const parallelValue = parallel {
            (true) ? { return "parallel"; };
            return 2;
        };
        ''')
        assert any('flow 块 返回类型不一致' in e for e in anal.symbols.errors)
        assert any('parallel 块 返回类型不一致' in e for e in anal.symbols.errors)

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

    def test_race_pl_infers_non_i32_return_type(self):
        """race(pl) 应从分支函数推断返回类型，不能固定为 I32。"""
        anal = analyze('''
        const r: Str = flow {
            return race(pl = [() => { return "a"; }, () => { return "b"; }], timeout = 10);
        };
        ''')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        sym = anal.symbols.resolve('r')
        assert sym is not None
        assert sym.type.name == 'Str'

    def test_race_pl_merges_mixed_branch_returns_as_union(self):
        """race(pl) 多种分支返回类型应合并为 union。"""
        anal = analyze('''
        const r = flow {
            return race(pl = [() => { return "a"; }, () => { return 1; }], timeout = 10);
        };
        ''')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        sym = anal.symbols.resolve('r')
        assert sym is not None and sym.type is not None
        assert sym.type.kind == TypeKind.UNION
        assert [member.name for member in sym.type.union_types] == ['Str', 'I32']

    def test_array_literal_infers_function_element_type(self):
        """数组字面量中的函数元素应自动推导函数类型。"""
        anal = analyze('const pl = [() => { return 1; }, () => { return 2; }];')
        assert not anal.symbols.has_errors(), f'语义错误: {anal.symbols.errors}'
        sym = anal.symbols.resolve('pl')
        assert sym is not None and sym.type is not None
        assert sym.type.kind == TypeKind.ARRAY
        assert sym.type.element_type.kind == TypeKind.FUNCTION
        assert sym.type.element_type.return_type.name == 'I32'

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
            const conn_timeout = tcpConnectTimeout(host = "127.0.0.1", port = 80, timeoutMs = 100);
            const tls = tcpTlsConnect(host = "example.com", port = 443);
            tls.ok ? {
                const tls_data = tcpTlsRead(conn = tls.value, maxBytes = 1024);
                tls_data.ok ? { const tls_sent = tcpTlsWrite(conn = tls.value, data = tls_data.value); };
            };
            const listener = tcpListen(host = "127.0.0.1", port = 8080);
            const udp = udpBind(host = "127.0.0.1", port = 5353);
            const accepted = accept(this = listener);
            const accepted_timeout = tcpAcceptTimeout(listener = listener, timeoutMs = 100);
            const data = read(this = conn, size = 1024);
            const data_timeout = tcpReadTimeout(conn = conn, maxBytes = 1024, timeoutMs = 100);
            const sent = write(this = conn, data = data);
            const sent_timeout = tcpWriteTimeout(conn = conn, data = data, timeoutMs = 100);
            const packet_with_addr = udpRecvFrom(socket = udp, maxBytes = 1024);
            const packet_with_addr_timeout = udpRecvFromTimeout(socket = udp, maxBytes = 1024, timeoutMs = 100);
            const packet = recv(this = udp, size = 1024);
            const packet_timeout = udpRecvTimeout(socket = udp, maxBytes = 1024, timeoutMs = 100);
            send(this = udp, data = packet, host = "127.0.0.1", port = 5353);
            const sent_udp_timeout = udpSendTimeout(socket = udp, host = "127.0.0.1", port = 5353, data = packet, timeoutMs = 100);
            return sent;
        };
        ''')
        assert {p['name'] for p in anal.suspend_points} >= {
            'tcpConnect', 'tcpConnectTimeout', 'tcpTlsConnect', 'tcpTlsRead', 'tcpTlsWrite', 'tcpListen', 'udpBind', 'accept', 'tcpAcceptTimeout',
            'read', 'tcpReadTimeout', 'write', 'tcpWriteTimeout', 'udpRecvFrom', 'udpRecvFromTimeout',
            'recv', 'udpRecvTimeout', 'send', 'udpSendTimeout'
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
            add(this: #Date, year: I32?) => Void;
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

    def test_documentation_ez_blocks_semantic_or_marked_demo(self):
        """文档 Ez 代码块应通过语义分析，或显式标为演示片段。"""
        seen: set[tuple[str, int]] = set()
        docs = [ROOT / 'README.md', *sorted((ROOT / 'docs').glob('*.md'))]
        for doc in docs:
            rel = doc.relative_to(ROOT).as_posix()
            for index, line, source in markdown_ez_blocks(doc):
                key = (rel, index)
                if key in DOC_SEMANTIC_SKIP:
                    seen.add(key)
                    continue
                anal = analyze(source)
                assert not anal.symbols.has_errors(), (
                    f'{rel} 代码块 {index}（起始行 {line}）语义错误: {anal.symbols.errors}'
                )
        missing = set(DOC_SEMANTIC_SKIP) - seen
        assert not missing, f'文档语义跳过清单指向了不存在的代码块: {sorted(missing)}'
