"""EzLang LLVM IR 代码生成测试"""

import sys
import os
import re
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

ROOT = Path(__file__).resolve().parents[2]
STD_ROOT = ROOT / 'packages' / 'std'

from llvmlite import ir, binding
from codegen.llvm_codegen import compile_source


def function_ir(ir_text: str, name: str) -> str:
    """提取单个 LLVM 函数文本。"""
    match = re.search(rf'^define\b.* @"{re.escape(name)}"\(', ir_text, re.MULTILINE)
    if match is not None:
        start = match.start()
        idx = start
    else:
        marker = f' @"{name}"'
        idx = ir_text.index(marker)
        start = ir_text.rfind('define ', 0, idx)
    end = ir_text.index('\n}\n', idx) + 3
    return ir_text[start:end]


def assert_optional_return_bridge(ir_text: str, name: str, value_type: str, arch: str):
    """断言 native 小可选返回按目标架构桥接，并还原为 Ez 内部布局。"""
    internal_type = f"{{i1, {value_type}}}"
    if value_type == "i32":
        assert f'declare i64 @"{name}"' in ir_text
    elif arch == "aarch64":
        assert f'declare [2 x i64] @"{name}"' in ir_text
    elif arch == "x86_64":
        assert f'declare {{i8, {value_type}}} @"{name}"' in ir_text
    else:
        assert f'declare {internal_type} @"{name}"' in ir_text
        return
    assert f'%"_{name}_abi_ret" = alloca {internal_type}' in ir_text
    assert f'%"_{name}_ret" = load {internal_type}' in ir_text


def assert_regex_compile_return_bridge(ir_text: str, arch: str):
    """Regex 小结构返回应按 native C ABI 桥接，并还原为 Ez 内部布局。"""
    if arch == "aarch64":
        assert 'declare [2 x i64] @"regexCompile"' in ir_text
    elif arch == "x86_64":
        assert 'declare {i8*, i64} @"regexCompile"' in ir_text
    else:
        assert 'declare %"Regex" @"regexCompile"' in ir_text
        return
    assert '%"_regexCompile_abi_ret" = alloca %"Regex"' in ir_text
    assert '%"_regexCompile_ret" = load %"Regex"' in ir_text


def assert_small_struct_return_bridge(ir_text: str, name: str, struct_name: str, abi_return: str):
    """断言 native 小结构返回按 C ABI 桥接，并还原为 Ez 结构布局。"""
    assert f'declare {abi_return} @"{name}"' in ir_text
    assert f'%"_{name}_abi_ret" = alloca %"{struct_name}"' in ir_text
    assert f'%"_{name}_ret" = load %"{struct_name}"' in ir_text


class TestCodegen:

    def test_empty_source(self):
        """空源码生成空模块"""
        module, errors, _ = compile_source('')
        assert module is not None
        assert len(errors) == 0

    def test_ensure_entrypoint_generates_empty_main_without_top_level_work(self):
        """入口编译模式下，即使源码只有声明也应生成空宿主 main。"""
        source = 'const helper = (): I32 => { return 1; };'

        module, errors, _ = compile_source(source, ensure_entrypoint=True)

        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define i32 @"helper"' in ir_text
        assert 'define i32 @"main"' in ir_text
        assert 'ret i32 0' in function_ir(ir_text, 'main')

    def test_global_constant(self):
        """全局常量声明"""
        source = 'const x: I32 = 42;'
        module, errors, _ = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        # 检查模块中有 x
        gv = module.get_global('x')
        assert gv is not None

    def test_global_variable(self):
        """全局变量声明"""
        source = 'let y: I32 = 10;'
        module, errors, _ = compile_source(source)
        assert module is not None
        gv = module.get_global('y')
        assert gv is not None

    def test_variable_identifier_can_start_with_dollar(self):
        """$ 开头变量名可生成全局符号，并由顶层顺序入口执行。"""
        source = 'let $count: I32 = 1; $count = $count + 1;'
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert module.get_global('$count') is not None
        ir_text = str(module)
        assert 'define i32 @"main"' in ir_text
        assert '@"$count"' in ir_text

    def test_compile_source_uses_isolated_struct_context(self):
        """连续编译同名不同布局结构体时，LLVM 类型上下文不能互相污染。"""
        first = 'struct User { name: Str; age: U32; }; const make = (): User => { return User(name = "A", age = 1); };'
        second = 'struct User { name: Str; active: Bool; }; const make = (): User => { return User(name = "B", active = true); };'

        first_module, first_errors, _ = compile_source(first)
        second_module, second_errors, _ = compile_source(second)

        assert first_module is not None
        assert second_module is not None
        assert len(first_errors) == 0, f'编译错误: {first_errors}'
        assert len(second_errors) == 0, f'编译错误: {second_errors}'
        first_ir = str(first_module)
        second_ir = str(second_module)
        binding.parse_assembly(first_ir).verify()
        binding.parse_assembly(second_ir).verify()
        assert '%"User" = type {i8*, i32}' in first_ir
        assert '%"User" = type {i8*, i1}' in second_ir

    def test_variable_decl_without_initializer_zero_initializes(self):
        """无初始化器的显式类型变量应写入类型零值。"""
        source = '''
        const main = (): I32 => {
            let count: I32;
            let arr: I32[]?;
            return arr.ok ? 1 : count;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'store i32 0, i32* %"count"' in ir_text
        assert 'store {i1, {i32**, i64, i64, i64}} {i1 0' in ir_text

    def test_prefix_type_assertion_codegen(self):
        """Type! expr 应生成目标类型值，并支持从可选值拆包。"""
        source = '''
        const widen = (): I64 => {
            return I64! 42;
        };
        const unwrap = (value: I32?): I32 => {
            return I32! value;
        };
        '''

        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define i64 @"widen"' in ir_text
        assert 'sext i32 42 to i64' in function_ir(ir_text, 'widen')
        assert '_type_assert_load' in function_ir(ir_text, 'unwrap')

    def test_simple_function(self):
        """简单函数代码生成"""
        source = '''
	const add = (a: I32, b: I32) => {
	    return a + b;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('add')
        assert func is not None
        assert isinstance(func, ir.Function)

    def test_return_function(self):
        """带返回值的函数"""
        source = '''
	const get_value = () => {
	    return 42;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('get_value')
        assert func is not None

    def test_decorator_meta_wrapper(self):
        """装饰器变量生成 Meta<T> 包装结构"""
        source = '''
        const log = (this: #Meta<I32>): Void => { return; };
        @log let watched = 1;
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0
        ir_text = str(module)
        assert '%"Meta_i32"' in ir_text
        assert '@"watched" = global %"Meta_i32"' in ir_text
        assert 'call void @"log"({i1, %"Meta_i32"*}* %"_decorator_this")' in ir_text

    def test_decorator_meta_getter_setter_ir(self):
        """装饰器变量读写应通过 Meta getter/setter 函数指针拦截"""
        source = '''
        const get_watched = (): I32 => { return 11; };
        const set_watched = (v: I32): Void => { return; };
        const log = (this: #Meta<I32>): Void => {
            let typeName: Str = this.t;
            this.getter = get_watched;
            this.setter = set_watched;
        };
        @log let watched = 1;
        const main = (): I32 => {
            watched = 2;
            return watched;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '_meta_type' in ir_text
        assert 'store {i32 (i8*)*, i8*}' in ir_text
        assert 'store {void (i8*, i32)*, i8*}' in ir_text
        assert 'call void %"_closure_invoke"(i8* %"_closure_env", i32 2)' in ir_text
        assert 'call i32 %"_closure_invoke.1"(i8* %"_closure_env.1")' in ir_text

    def test_functions_example_codegen(self):
        """functions.ez 应可生成函数相关 IR"""
        source = (Path(__file__).parent.parent.parent / 'examples' / 'functions.ez').read_text(encoding='utf-8')
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0
        assert module.get_global('add') is not None
        assert module.get_global('run') is not None

    def test_basic_module(self):
        """基本模块生成"""
        source = '''
	let x: I32 = 100;
	let y: I32 = 200;
	const add = (a: I32, b: I32) => {
	    return a + b;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        # 验证全局变量
        assert module.get_global('x') is not None
        assert module.get_global('y') is not None
        # 验证函数
        assert module.get_global('add') is not None

    def test_string_literal(self):
        """字符串字面量"""
        source = 'let msg: Str = "Hello";'
        module, errors, _ = compile_source(source)
        assert module is not None
        assert module.get_global('msg') is not None

    def test_module_ir_output(self):
        """输出 LLVM IR 文本"""
        source = '''
	let value: I32 = 42;
	const get = () => {
	    return value;
	};
	'''
        module, errors, _ = compile_source(source)
        ir_text = str(module)
        assert 'value' in ir_text
        assert 'get' in ir_text

    def test_logical_and(self):
        """逻辑与运算符 &&"""
        source = '''
	const test_and = (a: I32, b: I32) => {
	    return (a > 0) && (b > 0);
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_and')
        assert func is not None
        assert isinstance(func, ir.Function)

    def test_logical_or(self):
        """逻辑或运算符 ||"""
        source = '''
	const test_or = (a: I32, b: I32) => {
	    return (a > 0) || (b > 0);
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_or')
        assert func is not None

    def test_bitwise_ops(self):
        """位运算符 & | ^ << >>"""
        source = '''
	const test_bitwise = () => {
	    let shift: U32 = 2;
	    let a: I32 = 0b1010 & 0b1100;
	    let b: I32 = 0b1010 | 0b0101;
	    let c: I32 = 0b1010 ^ 0b1100;
	    let d: I32 = 1 << shift;
	    let e: I32 = 100 >> shift;
	    return a;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_bitwise')
        assert func is not None
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'shl i32' in ir_text
        assert 'ashr i32' in ir_text

    def test_unary_ops(self):
        """一元运算符 ! - ~"""
        source = '''
	const test_unary = (a: I32) => {
	    let b: Bool = !(a > 0);
	    let c: I32 = -a;
	    let d: I32 = ~a;
	    return c;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_unary')
        assert func is not None

    def test_infinite_loop(self):
        """无限循环 loop {}"""
        source = '''
	const test_loop = () => {
	    loop {
	        break;
	    };
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_loop')
        assert func is not None

    def test_ranged_loop(self):
        """范围循环 loop i in 0...10 {}"""
        source = '''
	const test_range_loop = () => {
	    let sum: I32 = 0;
	    loop i in 0...10 {
	        sum = sum + i;
	    };
	    return sum;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_range_loop')
        assert func is not None

    def test_list_loop_binds_element_value(self):
        """集合循环 loop item in list 应按元素值生成循环变量。"""
        source = '''
        const sum_list = (): I32 => {
            let total: I32 = 0;
            let nums: I32[] = [1, 2, 3];
            loop item in nums {
                total = total + item;
            };
            return total;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '_list_len' in ir_text

    def test_ir_correctness(self):
        """验证 IR 输出包含正确的运算指令"""
        source = '''
	const compute = (x: I32, y: I32) => {
	    let result: I32 = x + y;
	    return result;
	};
	'''
        module, errors, _ = compile_source(source)
        ir_text = str(module)
        assert 'add' in ir_text
        assert 'ret' in ir_text

    def test_comparison_ir(self):
        """验证比较运算生成正确的 icmp 指令"""
        source = '''
	const compare = (a: I32, b: I32) => {
	    return a > b;
	};
	'''
        module, errors, _ = compile_source(source)
        ir_text = str(module)
        assert 'icmp' in ir_text

    def test_if_like_expr(self):
        """类 if 表达式 (cond) ? expr : expr"""
        source = '''
	const test_if = (a: I32) => {
	    return (a > 0) ? a : 0;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_if')
        assert func is not None

    def test_if_like_block(self):
        """类 if 表达式 (cond) ? { block } : { block }"""
        source = '''
	const test_if_block = (a: I32) => {
	    (a > 0) ? {
	        return a;
	    } : {
	        return 0;
	    };
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_if_block')
        assert func is not None

    def test_if_like_statement_without_else_skips_false_branch(self):
        """无 else 条件块为假时不应执行 then 块。"""
        source = '''
        const test_if_statement = (): I32 => {
            (false) ? {
                return 2;
            };
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'br i1 0, label %"if_then"' in ir_text
        assert 'ret i32 2' in ir_text
        assert 'ret i32 0' in ir_text

    def test_struct_decl(self):
        """结构体声明"""
        source = '''
	struct Point {
	    x: I32;
	    y: I32 = 0;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        ir_text = str(module)
        assert 'Point' in ir_text

    def test_struct_literal_and_access(self):
        """结构体字面量与字段访问"""
        source = '''
	struct Point {
	    x: I32;
	    y: I32;
	};

	const run = () => {
	    let p = Point(x = 10, y = 20);
	    return p.x;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None

    def test_struct_duck_type_alias_rebuilds_layout_by_fields(self):
        """结构体赋给同字段形状别名时应按字段名重组布局。"""
        source = '''
        type PointShape = { x: I32; y: I32; };
        struct Point { x: I32; y: I32; };
        const run = (): I32 => {
            const p: PointShape = Point(x = 10, y = 20);
            return p.x + p.y;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '%"PointShape" = type {i32, i32}' in ir_text
        assert 'insertvalue %"PointShape"' in ir_text

    def test_array_literal(self):
        """数组字面量 [1, 2, 3]"""
        source = '''
	const test_array = () => {
	    let arr = [1, 2, 3];
	    return 42;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_array')
        assert func is not None

    def test_markup_literal_codegen(self):
        """无同名工厂函数的标记字面量应返回编译错误。"""
        source = '''
	const test_markup = () => {
	    let ui = <text color="blue" />;
	    return 0;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert any("同名工厂函数 'text'" in e for e in errors), f'应有缺少工厂函数错误: {errors}'
        ir_text = str(module)
        assert 'c"text\\00"' not in ir_text

    def test_markup_literal_lowers_to_factory_call(self):
        """存在同名工厂函数时，标记字面量 lower 为普通函数调用。"""
        source = '''
        const text = (color: Str, children: Str[]): I32 => {
            return 7;
        };

        const test_markup_factory = () => {
            let ui = <text color="blue">"Welcome"</text>;
            return ui;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call i32 @"text"' in ir_text
        assert '_markup_children' in ir_text
        assert '_markup_attr' in ir_text

    def test_markup_literal_lowers_union_children(self):
        """联合元素 children 应按工厂函数形参类型打包，允许异构子节点。"""
        source = '''
        struct Node {
            id: I32;
        }
        const div = (id: I32): Node => {
            return Node(id = id);
        };
        const text = (color: Str, children: (Str | Node | I32)[]): Node => {
            return Node(id = 1);
        };
        const test_markup_union_children = (): I32 => {
            let ui = <text color="blue">"Welcome"<div id=1 />{1 + 2}</text>;
            return ui.id;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call %"Node" @"text"' in ir_text
        assert '_union_pack_payload' in ir_text
        assert '_markup_children' in ir_text
        assert re.search(r'insertvalue \{i32, i8\*\} undef, i32 0, 0', ir_text), ir_text
        assert re.search(r'store i32 1, i32\* %"\.\d+"', ir_text), ir_text
        assert re.search(r'insertvalue \{i32, i8\*\} undef, i32 2, 0', ir_text), ir_text

    def test_markup_literal_codegen_reports_attr_type_mismatch(self):
        """直接 codegen 路径也应报告标记属性类型不匹配。"""
        source = '''
        const text = (color: I32): I32 => {
            return color;
        };

        const test_markup_attr = () => {
            let ui = <text color="blue" />;
            return ui;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert any("参数 'color' 类型不匹配" in e for e in errors), errors

    def test_markup_literal_codegen_reports_children_type_mismatch(self):
        """直接 codegen 路径也应报告 children 类型不匹配。"""
        source = '''
        const text = (children: I32[]): I32 => {
            return 1;
        };

        const test_markup_children = () => {
            let ui = <text>"Welcome"</text>;
            return ui;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert any("参数 'children' 类型不匹配" in e for e in errors), errors

    def test_markup_literal_codegen_reports_children_without_parameter(self):
        """直接 codegen 路径也应报告未知 children 参数。"""
        source = '''
        const text = (): I32 => {
            return 1;
        };

        const test_markup_children = () => {
            let ui = <text>"Welcome"</text>;
            return ui;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert any("未知参数 'children'" in e for e in errors), errors

    def test_array_index(self):
        """数组索引访问 arr[0]"""
        source = '''
	const test_index = () => {
	    let arr = [10, 20, 30];
	    return arr[0];
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_index')
        assert func is not None

    def test_array_literal_uses_sparse_pages(self):
        """数组/List 字面量应使用页表结构而不是裸连续数组"""
        source = '''
	const test_pages = () => {
	    let arr = [10, 20, 30, 40, 50, 60, 70, 80, 90];
	    return arr[8];
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0
        ir_text = str(module)
        assert '_tmp_arr_pages' in ir_text
        assert '_tmp_arr_page' in ir_text
        assert 'udiv' in ir_text
        assert 'urem' in ir_text

    def test_list_type_maps_to_sparse_pages(self):
        """List<T> 类型注解应映射为页表结构"""
        source = '''
	const test_list = () => {
	    let list: List<I32> = [10, 20, 30];
	    return list[1];
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '_tmp_arr_pages' in ir_text

    def test_match_block(self):
        """match 模式匹配"""
        source = '''
	const test_match = () => {
	    let result: I32 = 0;
	    match {
	        (1 > 0) ? { result = 1; },
	        (false) ? { result = 2; },
	        (true) ? { result = 3; }
	    };
	    return result;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_match')
        assert func is not None
        ir_text = str(module)
        assert 'match' in ir_text.lower()

    def test_throw_catch(self):
        """throw / catch 异常处理"""
        source = '''
	struct Error {
	    code: I32;
	    message: Str;
	};

	const test_catch = () => {
	    let result: Str = "ok";
	    catch {
	        throw Error(code = 404, message = "Not Found");
	    };
	    return 42;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_catch')
        assert func is not None

    def test_catch_no_throw(self):
        """catch 块无异常时正常返回"""
        source = '''
	const test_no_throw = () => {
	    let result: I32 = 0;
	    catch {
	        result = 42;
	    };
	    return result;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_no_throw')
        assert func is not None

    def test_uncaught_throw_terminates_ir(self):
        """未捕获 throw 应生成终止路径，而不是继续执行后续语句。"""
        source = '''
        const main = (): I32 => {
            throw Error(code = 7, message = "boom");
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'define void @"__ezrt_uncaught_throw"' in ir_text
        assert 'call void @"__ezrt_uncaught_throw"()' in ir_text
        assert 'unreachable' in ir_text
        assert 'ret i32 0' not in ir_text

    def test_throw_propagates_across_function_call_ir(self):
        """函数内 throw 应通过异常槽传播到调用点的 catch。"""
        source = '''
        const fail = (): Void => {
            throw Error(code = 17, message = "nested");
        };
        const run = (body: () => Void): I32 => {
            const err = catch { body(); };
            return err.code;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '@"__ezrt_throw_active" = internal global i1 0' in ir_text
        assert '@"__ezrt_throw_value" = internal global %"Error"' in ir_text
        assert 'br i1 %"_throw_active", label %"call_throw", label %"call_continue"' in ir_text
        assert 'br label %"catch_exit"' in ir_text
        assert 'load %"Error", %"Error"* @"__ezrt_throw_value"' in ir_text

    def test_throw_propagates_through_flow_parallel_and_race_ir(self):
        """当前同步 lowering 下 flow/parallel/race 内 throw 也应交给外层 catch。"""
        source = '''
        const run = (): I32 => {
            const flowErr = catch {
                const value = flow {
                    throw Error(code = 31, message = "flow");
                    return 1;
                };
            };
            const parallelErr = catch {
                const value = parallel {
                    throw Error(code = 32, message = "parallel");
                    return 1;
                };
            };
            const raceErr = catch {
                const value = flow {
                    return race(pl = [() => { throw Error(code = 33, message = "race"); return 1; }, () => { return 2; }], timeout = 10);
                };
            };
            return flowErr.code + parallelErr.code + raceErr.code;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'call void @"__ezrt_flow_enter"()' in ir_text
        assert 'call void @"__ezrt_parallel_enter"()' in ir_text
        assert 'call i32 @"__ezrt_race_i32"' in ir_text
        assert 'call i32 @"__ezrt_race"(i32 2, i32 10)' not in ir_text
        assert 'store %"Error"' in ir_text
        assert 'store i1 1, i1* @"__ezrt_throw_active"' in ir_text
        assert 'load %"Error", %"Error"* @"__ezrt_throw_value"' in ir_text

    def test_default_params(self):
        """函数默认参数"""
        source = '''
	const greet = (name: Str = "World") => {
	    return name;
	};

	const main = () => {
	    let r = greet(name = "Hello");
	    return 42;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('greet')
        assert func is not None
        main_func = module.get_global('main')
        assert main_func is not None

    def test_declare_function(self):
        """declare 外部函数声明"""
        source = '''
	declare const printf: (fmt: Str) => I32;

	const main = () => {
	    printf(fmt = "hello");
	    return 0;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('printf')
        assert func is not None
        assert isinstance(func, ir.Function)

    def test_declare_variable(self):
        """declare 外部变量声明"""
        source = '''
	declare static errno: I32;

	const main = () => {
	    return errno;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        gv = module.get_global('errno')
        assert gv is not None

    def test_export_function(self):
        """export 导出函数"""
        source = '''
	export const add = (a: I32, b: I32) => {
	    return a + b;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('add')
        assert func is not None
        assert isinstance(func, ir.Function)

    def test_optional_type(self):
        """可选类型 T? 映射为 {i1, T}"""
        source = 'let x: I32? = 42;'
        module, errors, _ = compile_source(source)
        assert module is not None
        gv = module.get_global('x')
        assert gv is not None
        ir_text = str(module)
        assert '{i1, i32}' in ir_text

    def test_weak_reference_type_and_value(self):
        """#T 弱引用类型映射为 {i1, T*}，使用方式按 T 透明访问。"""
        source = '''
        struct Box { value: I32; };
        const run = (): I32 => {
            let box = Box(value = 7);
            let ref: #Box = #box;
            return (typeof ref == Void) ? 0 : ref.value;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '{i1, %"Box"*}' in ir_text

    def test_weak_reference_method_call_and_not_void_check(self):
        """#T 弱引用可像值引用一样调用方法，并支持 typeof ref != Void 判空。"""
        source = '''
        struct Box {
            value: I32;
            get = (this: #Box): I32 => { return this.value; };
        };
        const run = (): I32 => {
            let box = Box(value = 9);
            let ref: #Box = #box;
            return (typeof ref != Void) ? ref.get() : 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '{i1, %"Box"*}' in ir_text

    def test_weak_reference_unwraps_for_calculation(self):
        """#I32 在计算时解包为 I32 值。"""
        source = '''
        const run = (): I32 => {
            let value: I32 = 40;
            let ref: #I32 = #value;
            return ref + 2;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '_weak_calc_unwrapped' in ir_text

    def test_weak_reference_rejects_literals_and_temporary_values(self):
        """codegen 入口也应拒绝字面量和临时值弱引用。"""
        source = '''
        let a = #1;
        let b = #"text";
        let value: I32 = 1;
        let c = #(value + 1);
        '''
        _, errors, _ = compile_source(source)
        assert len(errors) == 3
        assert all("弱引用 '#' 只能用于变量、字段或索引等可寻址表达式" in err for err in errors)

    def test_union_type(self):
        """联合类型 T1 | T2 映射为 {i32, T_max}"""
        source = 'let y: I32 | Str = 42;'
        module, errors, _ = compile_source(source)
        assert module is not None
        gv = module.get_global('y')
        assert gv is not None
        ir_text = str(module)
        assert '{i32, i8*}' in ir_text

    def test_union_return_uses_variant_tag(self):
        """函数返回联合类型时，应按返回类型声明顺序写入 tag。"""
        source = '''
        const make = (): I32 | Str => {
            return "ez";
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'insertvalue {i32, i8*} undef, i32 1, 0' in ir_text

    def test_optional_unwrap(self):
        """可选拆包 expr? 提取值"""
        source = '''
        const test_unwrap = () => {
            let x: I32? = 42;
            return x?;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_unwrap')
        assert func is not None

    def test_type_assertion(self):
        """类型断言 expr! 强制类型"""
        source = '''
        const test_assert = (x: I32?) => {
            return x!;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('test_assert')
        assert func is not None

    def test_optional_in_function(self):
        """函数内使用可选类型"""
        source = '''
        const maybe_add = (a: I32?, b: I32) => {
            (a?) ? {
                return a? + b;
            } : {
                return b;
            };
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('maybe_add')
        assert func is not None

    def test_simd_vector_type(self):
        """SIMD 向量类型 Vec<T>[N] 映射为 <N x T>"""
        source = 'let v: Vec<I32>[4] = Vec[1, 2, 3, 4];'
        module, errors, _ = compile_source(source)
        assert module is not None
        ir_text = str(module)
        assert '<4 x i32>' in ir_text

    def test_function_pointer_type(self):
        """函数类型映射为函数指针"""
        source = '''
        declare const callback: (a: I32, b: I32) => I32;
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('callback')
        assert func is not None

    def test_extern_callback_returning_large_struct_uses_c_abi_trampoline(self):
        """外部 C 回调返回大结构体时，函数指针应使用隐藏 sret ABI。"""
        source = '''
        extern "libnative.a";
        struct Pair { a: I64; b: I64; c: I64; };
        declare const call_pair: (cb: (x: I32) => Pair) => I32;
        const make_pair = (x: I32): Pair => {
            return Pair(a = x, b = x + 1, c = x + 2);
        };
        const main = (): I32 => { return call_pair(cb = make_pair); };
        '''
        module, errors, _ = compile_source(source, compile_target='macos', target_arch='aarch64')
        assert module is not None
        text = str(module)
        assert 'declare i32 @"call_pair"(void (%"Pair"*, i32)*' in text
        assert 'define void @"make_pair_cabi_callback"(%"Pair"* sret(%"Pair")' in text
        assert 'call i32 @"call_pair"(void (%"Pair"*, i32)* @"make_pair_cabi_callback")' in text

    def test_struct_spread_decl(self):
        """结构体展开声明 ...Base"""
        source = '''
        struct Point {
            x: I32;
            y: I32;
        };

        struct Point3D {
            ...Point;
            z: I32;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        ir_text = str(module)
        assert 'Point' in ir_text
        assert 'Point3D' in ir_text

    def test_struct_instance_spread(self):
        """结构体实例展开 ...instance"""
        source = '''
        struct Point {
            x: I32;
            y: I32;
        };

        const run = () => {
            let p = Point(x = 10, y = 20);
            let p2 = Point(...p, y = 30);
            return p2.x;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None

    def test_struct_method(self):
        """结构体方法定义与调用"""
        source = '''
        struct Point {
            x: I32;
            y: I32;
            distance = (this: #Point, other: Point): I32 => {
                let dx: I32 = this.x - other.x;
                let dy: I32 = this.y - other.y;
                return dx * dx + dy * dy;
            };
        };

        const run = () => {
            let p = Point(x = 3, y = 4);
            return p.x;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('Point_distance')
        assert func is not None
        assert isinstance(func, ir.Function)

    def test_pipeline_expression(self):
        """管道表达式 expr -> fn(x = %)"""
        source = '''
        const sub = (a: I32, b: I32): I32 => {
            return a - b;
        };

        const with_default = (a: I32, b: I32 = 7): I32 => {
            return a + b;
        };

        const run = () => {
            let ordered = 10 -> sub(b = %, a = 20);
            let defaulted = 3 -> with_default();
            return ordered + defaulted;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        func = module.get_global('run')
        assert func is not None
        ir_text = str(module)
        assert 'call i32 @"sub"(i32 20, i32 10)' in ir_text
        assert 'call i32 @"with_default"(i32 3, i32 7)' in ir_text

    def test_simd_vector_ops(self):
        """SIMD 向量运算（加/减/乘）"""
        source = '''
        const run = () => {
            let a = Vec[1, 2, 3, 4];
            let b = Vec[5, 6, 7, 8];
            let c = a + b;
            return c;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None
        ir_text = str(module)
        assert 'add' in ir_text

    def test_simd_vector_mul(self):
        """SIMD 向量乘法"""
        source = '''
        const run = () => {
            let a = Vec[2, 4, 6, 8];
            let b = Vec[1, 2, 3, 4];
            return a * b;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None

    def test_simd_vector_scalar_broadcast(self):
        """SIMD 向量与标量混合运算时应广播标量。"""
        source = '''
        const run = (): Vec<I32>[4] => {
            let a = Vec[1, 2, 3, 4];
            return a + 2;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'add <4 x i32>' in ir_text
        assert ir_text.count('insertelement <4 x i32>') >= 4

    def test_simd_vector_comparison_mask(self):
        """SIMD 向量比较应生成向量 mask。"""
        source = '''
        const run = () => {
            let a = Vec[1, 2, 3, 4];
            let b = Vec[2, 2, 2, 2];
            let mask = a < b;
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'icmp slt <4 x i32>' in ir_text
        assert '<4 x i1>' in ir_text

    def test_struct_value_copy(self):
        """结构体值语义拷贝（let p2 = p1; 拷贝全部字段）"""
        source = '''
        struct Point {
            x: I32;
            y: I32;
        };

        const run = () => {
            let p1 = Point(x = 10, y = 20);
            let p2 = p1;
            return p2.x + p2.y;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None

    def test_llvm_memcpy_declared(self):
        """llvm.memcpy 内建函数已声明"""
        source = 'const x: I32 = 1;'
        module, errors, _ = compile_source(source)
        memcpy = module.get_global('llvm.memcpy.p0.p0.i64')
        assert memcpy is not None
        assert isinstance(memcpy, ir.Function)

    def test_builtin_struct_error(self):
        """内置结构体 Error"""
        source = '''
        const run = () => {
            let e = Error(code = 404, message = "Not Found");
            return e.code;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None

    def test_builtin_struct_date(self):
        """内置结构体 Date"""
        source = '''
        const run = () => {
            let d = Date(timestamp = 1700000000);
            return 42;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None

    def test_builtin_struct_blob(self):
        """内置结构体 Blob"""
        source = '''
        const run = () => {
            let b = Blob(data = "hello", size = 5);
            return 42;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None

    def test_import_module(self):
        """import 模块导入"""
        source = '''
        from "test_lib.ez" import { pi, add };

        const run = () => {
            return add(a = 1, b = 2);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert module.get_global('pi') is not None
        assert module.get_global('add') is not None
        func = module.get_global('run')
        assert func is not None

    def test_import_with_alias(self):
        """import 模块导入带重命名"""
        source = '''
        from "test_lib.ez" import { pi as PI_VALUE };

        const run = () => {
            return 42;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert module.get_global('PI_VALUE') is not None

    def test_generic_function(self):
        """泛型函数单态化"""
        source = '''
        const id<T> = (x: T): T => {
            return x;
        };

        const run = () => {
            let r = id<I32>(x = 42);
            return r;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        # 单态化版本应该存在
        assert module.get_global('id_I32') is not None
        func = module.get_global('run')
        assert func is not None

    def test_generic_function_infers_type_args_from_named_arguments(self):
        """泛型函数调用可从命名实参推导类型参数。"""
        source = '''
        const id<T> = (x: T): T => {
            return x;
        };

        const run = () => {
            let n = id(x = 42);
            let s = id(x = "ez");
            return n;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert module.get_global('id_I32') is not None
        assert module.get_global('id_Str') is not None

    def test_generic_expression_function_infers_type_args_from_positional_arguments(self):
        """表达式体泛型函数可从位置实参推导类型参数。"""
        source = '''
        const identity = <T>(value: T) => value;

        const run = (): I32 => {
            let inferred = identity(7);
            return inferred;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert module.get_global('identity_I32') is not None
        ir_text = str(module)
        assert 'call i32 @"identity_I32"(i32 7)' in ir_text
        assert 'store i32 0, i32* %"inferred"' not in ir_text

    def test_function_named_args_do_not_degrade_to_positional_call(self):
        """函数具名参数 codegen 必须按名称重排，不能退化为位置参数。"""
        source = '''
        const sub = (a: I32, b: I32): I32 => {
            return a - b;
        };
        const run = (): I32 => {
            return sub(b = 1, a = 3);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'call i32 @"sub"(i32 3, i32 1)' in ir_text
        assert 'call i32 @"sub"(i32 1, i32 3)' not in ir_text

    def test_struct_named_args_do_not_degrade_to_positional_init(self):
        """结构体具名构造必须按字段名写入，不能退化为位置参数。"""
        source = '''
        struct Pair {
            left: I32;
            right: I32;
        }
        const run = (): I32 => {
            let p = Pair(right = 1, left = 3);
            return p.left - p.right;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        run_ir = function_ir(ir_text, 'run')
        assert re.search(r'getelementptr inbounds %"Pair", %"Pair"\* %"_tmp_Pair", i32 0, i32 1\n  store i32 1, i32\*', run_ir), run_ir
        assert re.search(r'getelementptr inbounds %"Pair", %"Pair"\* %"_tmp_Pair", i32 0, i32 0\n  store i32 3, i32\*', run_ir), run_ir

    def test_generic_struct_explicit_args_monomorphize_layout(self):
        """显式泛型结构体实参应生成具体字段布局。"""
        source = '''
        struct Pair<T, U> { first: T; second: U; };
        const run = (): I32 => {
            const p = Pair<I32, Str>(first = 42, second = "ez");
            return p.first;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '%"Pair_I32_Str" = type {i32, i8*}' in ir_text
        assert '@"run"' in ir_text

    def test_nested_generic_args_close_with_adjacent_angles(self):
        """嵌套泛型显式实参不需要在连续右尖括号之间加空格。"""
        source = '''
        struct Box<T> { value: T; };
        const unwrap = (box: Box<Box<U32>>): U32 => {
            return box.value.value;
        };
        const run = (): U32 => {
            const inner = Box<U32>(value = 42);
            const outer = Box<Box<U32>>(value = inner);
            return unwrap(box = outer);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '%"Box_U32" = type {i32}' in ir_text
        assert '%"Box_Box_U32" = type {%"Box_U32"}' in ir_text
        assert '@"unwrap"' in ir_text

    def test_generic_struct_infers_type_args_from_constructor_fields(self):
        """泛型结构体构造可从字段值推导具体布局。"""
        source = '''
        struct Pair<T, U> { first: T; second: U; };
        const run = (): I32 => {
            const p = Pair(first = 42, second = "ez");
            return p.first;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '%"Pair_I32_Str" = type {i32, i8*}' in ir_text
        assert 'getelementptr inbounds %"Pair_I32_Str"' in ir_text

    def test_generic_struct_method_monomorphizes_for_concrete_struct(self):
        """泛型结构体方法应随具体结构体类型单态化。"""
        source = '''
        struct Pair<T, U> {
            first: T;
            second: U;
            swap = (this: #Pair<T, U>): Pair<U, T> => {
                return Pair<U, T>(first = this.second, second = this.first);
            };
        };
        const run = (): I32 => {
            const p = Pair(first = 42, second = "ez");
            const swapped = p.swap();
            return swapped.second;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define %"Pair_Str_I32" @"Pair_I32_Str_swap"' in ir_text
        assert 'call %"Pair_Str_I32" @"Pair_I32_Str_swap"' in ir_text

    def test_top_level_static_struct_method_infers_global_type(self):
        """顶层静态结构体方法调用应把全局变量预声明为方法返回类型。"""
        source = '''
        struct Duration {
            ms: I64;
            fromSec = (s: I64): Duration => {
                return Duration(ms = s);
            };
            toText = (this: #Duration): Str => {
                return "ok";
            };
        };
        let seconds = Duration.fromSec(s = 2);
        let text = seconds.toText();
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '@"seconds" = global %"Duration"' in ir_text
        assert '@"text" = global i8*' in ir_text
        assert 'call %"Duration" @"Duration_fromSec"' in ir_text
        assert 'call i8* @"Duration_toText"' in ir_text

    def test_dict_literal(self):
        """字典字面量 { key: Type = value }"""
        source = '''
        const run = () => {
            let config = {
                name: Str = "hello",
                age: I32 = 30
            };
            return 42;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None
        ir_text = str(module)
        assert 'LiteralStructType' in ir_text or 'i8*' in ir_text

    def test_flow_block(self):
        """flow 并发块应插入运行时 enter/exit stub，并保持同步块行为"""
        source = '''
        const run = () => {
            let result: I32 = 0;
            flow {
                result = 42;
            };
            return result;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None
        ir_text = str(module)
        assert '@"__ezrt_flow_enter"' in ir_text
        assert '@"__ezrt_flow_exit"' in ir_text
        assert 'call void @"__ezrt_flow_enter"()' in ir_text
        assert 'call void @"__ezrt_flow_exit"()' in ir_text

    def test_flow_sleep_lowers_to_runtime_stub(self):
        """flow 内 sleep 应 lowering 到运行时 sleep stub"""
        source = '''
        declare const sleep: (ms: I64) => Void;

        const run = () => {
            flow {
                sleep(ms = 1);
            };
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '@"__ezrt_sleep"' in ir_text
        assert 'call void @"__ezrt_sleep"' in ir_text
        assert 'call void @"sleep"' not in ir_text

    def test_emcc_flow_sleep_auto_links_time_js(self):
        """emcc 下 flow sleep 需要自动携带 Asyncify time.js helper。"""
        source = '''
        declare const sleep: (ms: I64) => Void;

        const run = (): I32 => {
            flow {
                sleep(ms = 1);
            };
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call void @"__ezrt_sleep"' in ir_text
        assert 'declare void @"__ezrt_emcc_sleep"' in ir_text
        assert libs == [str(STD_ROOT / 'emcc' / 'time.js')]
        time_js = (STD_ROOT / 'emcc' / 'time.js').read_text(encoding='utf-8')
        assert "sleep__async: 'auto'" in time_js
        assert "__ezrt_emcc_sleep__async: 'auto'" in time_js
        assert 'return sleepMs(ms);' in time_js

    def test_emcc_flow_without_sleep_links_parallel_runtime_only(self):
        """emcc 下 flow 内 parallel 应自动携带协程 runtime，但不引入 sleep helper。"""
        source = '''
        const run = (): I32 => {
            const result = flow {
                const p = parallel { return 7; };
                return p + 1;
            };
            return result;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '__ezrt_emcc_sleep' not in ir_text
        assert '__ezrt_sleep' not in ir_text
        assert libs == [str(STD_ROOT / 'emcc' / 'runtime.js')]

    def test_emcc_flow_std_suspend_sources_link_asyncify_runtime(self):
        """emcc 下 flow 内标准库 suspend source 应触发 Asyncify runtime 链接准备。"""
        source = '''
        from "./std/io.ez" import { readLine };
        from "./std/net/http.ez" import { fetch };
        from "./std/fs.ez" import { readFile };
        from "./std/process.ez" import { Command, processExec };
        from "./std/stream.ez" import { streamFromBlob, streamRead, streamWrite };

        const run = (): I32 => {
            flow {
                const line = readLine();
                const resp = fetch(url = "https://example.com");
                const file = readFile(path = "missing.txt");
                const cmd = Command(program = "echo", args = ["ok"], cwd = "", env = ["EZ=1"], stdin = Blob(data = "", size = 0));
                const proc = processExec(command = cmd);
                const stream = streamFromBlob(data = Blob(data = "ok", size = 2));
                const chunk = streamRead(stream = stream.value, maxBytes = 1);
                const written = streamWrite(stream = stream.value, data = Blob(data = "!", size = 1));
            };
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        binding.parse_assembly(str(module)).verify()
        lib_names = {str(lib) for lib in libs}
        assert str(STD_ROOT / 'emcc' / 'runtime.js') in lib_names
        assert str(STD_ROOT / 'emcc' / 'io.js') in lib_names
        assert str(STD_ROOT / 'emcc' / 'net' / 'http.js') in lib_names
        assert str(STD_ROOT / 'emcc' / 'fs.js') in lib_names
        assert str(STD_ROOT / 'emcc' / 'process.js') in lib_names
        assert str(STD_ROOT / 'emcc' / 'stream.js') in lib_names

    def test_flow_race_lowers_to_runtime_stub(self):
        """flow 内 race 应 lowering 到运行时 race stub"""
        source = '''
        declare const race: (task: I32, timeout: I32) => I32;

        const run = (): I32 => {
            const result = flow {
                return race(task = 1, timeout = 10);
            };
            return result;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '@"__ezrt_race"' in ir_text
        assert 'call i32 @"__ezrt_race"' in ir_text
        assert 'call i32 @"race"' not in ir_text

    def test_flow_race_pl_lowers_to_runtime_stub(self):
        """文档接口 race(pl=[...], timeout=...) 应直接调用并发运行时。"""
        source = '''
        const run = (): I32 => {
            const result = flow {
                return race(pl = [() => { return 1; }, () => { return 2; }], timeout = 10);
            };
            return result;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'define i32 @"__ez_race_branch_' in ir_text
        assert 'call i32 @"__ezrt_race_i32"' in ir_text
        assert 'call i32 @"__ezrt_race"(i32 2, i32 10)' not in ir_text
        assert 'call i32 @"race"' not in ir_text

    def test_emcc_flow_race_pl_uses_asyncify_runtime(self):
        """emcc 目标下 race(pl) 应接入 JS 协程运行时，不再退回同步首分支。"""
        source = '''
        const run = (): I32 => {
            const result = flow {
                return race(pl = [() => { return 1; }, () => { return 2; }], timeout = 10);
            };
            return result;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call i32 @"__ezrt_race_i32"' in ir_text
        assert 'call i32 @"__ezrt_race"' not in ir_text
        assert 'call i32 @"race"' not in ir_text
        assert 'define i32 @"__ez_race_branch_' in ir_text
        assert str(STD_ROOT / 'emcc' / 'runtime.js') in {str(lib) for lib in libs}
        runtime_js = (STD_ROOT / 'emcc' / 'runtime.js').read_text(encoding='utf-8')
        assert "__ezrt_task_join_i32__async: 'auto'" in runtime_js
        assert "__ezrt_race_i32__async: 'auto'" in runtime_js
        assert not any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)
        assert 'pthread' not in {str(lib) for lib in libs}

    def test_flow_race_pl_non_i32_uses_typed_synchronous_fallback(self):
        """非 I32 race(pl) 应使用分支返回类型，而不是固定成 I32。"""
        source = '''
        const run = (): Str => {
            const result = flow {
                return race(pl = [() => { return "a"; }, () => { return "b"; }], timeout = 10);
            };
            return result;
        };
        '''
        module, errors, libs = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define i8* @"run"' in ir_text
        assert 'call i32 @"__ezrt_race_i32"' not in ir_text
        assert 'call i32 @"__ezrt_race"' not in ir_text
        assert not any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)

    def test_flow_parallel_nested_return_type_codegen(self):
        """flow/parallel 返回槽应支持嵌套块里的 return 类型。"""
        source = '''
        const run = (): I32 => {
            const a = flow {
                (true) ? { return 3; };
                return 1;
            };
            const b = parallel {
                { return 4; };
                return 2;
            };
            return a + b;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '%"_flow_result" = alloca i32' in ir_text
        assert '%"_parallel_result" = alloca i32' in ir_text

    def test_flow_parallel_return_local_str_type_codegen(self):
        """flow/parallel return 本块局部变量时应推断为局部变量类型。"""
        source = '''
        const run = (): Str => {
            return flow {
                const text = parallel {
                    const inner = "ok";
                    return inner;
                };
                return text;
            };
        };
        '''
        module, errors, _ = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define i8* @"run"' in ir_text
        assert '%"_flow_result" = alloca i8*' in ir_text
        assert '%"_parallel_result" = alloca i8*' in ir_text

    def test_flow_parallel_combined_initializer_is_not_truncated(self):
        """只有完整 `parallel {}` 初始化才应启动后台 future，组合表达式必须同步求完整值。"""
        source = '''
        const run = (): I32 => {
            const result = flow {
                const value = parallel { return 7; } + 1;
                return value;
            };
            return result;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call i8* @"__ezrt_task_start_i32"' not in ir_text
        assert 'add i32' in function_ir(ir_text, 'run')

    def test_top_level_flow_comparison_initializer_infers_bool(self):
        """顶层 flow 组合表达式不能被误推断为 flow 块内部返回类型。"""
        source = '''
        const same = flow { return 7; } == 7;
        '''
        module, errors, _ = compile_source(source, ensure_entrypoint=True)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '@"same" = global i1 0' in ir_text

    def test_emcc_flow_parallel_i32_uses_asyncify_runtime(self):
        """emcc 目标下 flow 内 parallel I32 应接入 JS 协程任务 runtime。"""
        source = '''
        const run = (): I32 => {
            const result = flow {
                const p = parallel { return 7; };
                return p + 1;
            };
            return result;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call i8* @"__ezrt_task_start_i32"' in ir_text
        assert 'call i32 @"__ezrt_task_join_i32"' in ir_text
        assert 'define i32 @"__ez_race_branch_' in ir_text
        assert 'call void @"__ezrt_parallel_enter"()' not in ir_text
        assert str(STD_ROOT / 'emcc' / 'runtime.js') in {str(lib) for lib in libs}
        assert not any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)
        assert 'pthread' not in {str(lib) for lib in libs}

    def test_flow_parallel_typed_i32_initializer_starts_future(self):
        """显式 I32 类型的 parallel 初始化也应接入 native 后台任务。"""
        source = '''
        declare const sleep: (ms: I64) => Void;

        const run = (): I32 => {
            const result = flow {
                const p: I32 = parallel { sleep(ms = 1); return 7; };
                return p + 1;
            };
            return result;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call i8* @"__ezrt_task_start_i32"' in ir_text
        assert 'call i32 @"__ezrt_task_join_i32"' in ir_text
        assert 'define i32 @"__ez_race_branch_' in ir_text
        assert any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)
        assert 'pthread' in {str(lib) for lib in libs}

    def test_flow_parallel_local_capture_starts_shared_env_future(self):
        """捕获外层局部变量的 parallel 应共享外层存储槽并启动后台任务。"""
        source = '''
        const run = (): I32 => {
            const result = flow {
                const offset = 5;
                const p: I32 = parallel { return offset + 2; };
                return p;
            };
            return result;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call i8* @"__ezrt_task_start_env_i32"' in ir_text
        assert 'call i32 @"__ezrt_task_join_i32"' in ir_text
        assert 'define i32 @"__ez_parallel_branch_' in ir_text
        assert '_offset_shared' in ir_text
        assert 'call void @"__ezrt_parallel_enter"()' not in ir_text
        assert any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)
        assert 'pthread' in {str(lib) for lib in libs}

    def test_closure_capture_shares_outer_mutation_slot(self):
        """闭包捕获应共享外层变量槽，支持内外双向修改。"""
        source = '''
        const run = (): I32 => {
            let counter: I32 = 1;
            let bump: () => I32 = (): I32 => {
                counter += 1;
                return counter;
            };
            counter = 10;
            const afterInner = bump();
            return afterInner + counter;
        };
        '''
        module, errors, _ = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '_counter_shared' in ir_text
        lambda_ir = function_ir(ir_text, '__lambda_0')
        assert 'load i32*' in lambda_ir
        assert 'store i32' in lambda_ir

    def test_flow_parallel_capture_writes_back_to_outer_slot(self):
        """parallel 捕获普通局部变量后，内部赋值应写回外层共享槽。"""
        source = '''
        const run = (): I32 => {
            let total: I32 = 1;
            const result = flow {
                const p: I32 = parallel {
                    total += 4;
                    return total;
                };
                return p + total;
            };
            return result;
        };
        '''
        module, errors, _ = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '_total_shared' in ir_text
        branch_ir = function_ir(ir_text, '__ez_parallel_branch_0')
        assert 'load i32*' in branch_ir
        assert 'store i32' in branch_ir
        assert 'call i8* @"__ezrt_task_start_env_i32"' in ir_text

    def test_flow_parallel_locked_local_capture_uses_lock_hooks_in_future(self):
        """parallel 后台任务读写捕获的锁局部变量时应沿用现有锁 hook。"""
        source = '''
        const run = (): I32 => {
            wp let total: I32 = 0;
            const result = flow {
                const delta = 2;
                const p: I32 = parallel {
                    total += delta;
                    return total;
                };
                return p;
            };
            return result;
        };
        '''
        module, errors, _ = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        branch_ir = function_ir(ir_text, '__ez_parallel_branch_0')
        assert 'call void @"__ezrt_lock_write_acquire"' in branch_ir
        assert 'call void @"__ezrt_lock_write_release"' in branch_ir
        assert 'call void @"__ezrt_lock_read_acquire"' in branch_ir
        assert 'call void @"__ezrt_lock_read_release"' in branch_ir
        assert 'call i8* @"__ezrt_task_start_env_i32"' in ir_text

    def test_flow_parallel_non_i32_explicit_type_uses_synchronous_fallback(self):
        """当前 native 后台任务 ABI 仅覆盖显式 I32，I64 等类型保持同步 fallback。"""
        source = '''
        const run = (): I64 => {
            const result = flow {
                const p: I64 = parallel { return 7; };
                return p;
            };
            return result;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call i8* @"__ezrt_task_start_i32"' not in ir_text
        assert 'call i32 @"__ezrt_task_join_i32"' not in ir_text
        assert 'call void @"__ezrt_parallel_enter"()' in ir_text
        assert not any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)

    def test_emcc_flow_parallel_typed_i32_uses_asyncify_runtime(self):
        """emcc 下显式 I32 parallel 同样接入 JS 协程任务 runtime。"""
        source = '''
        const run = (): I32 => {
            const result = flow {
                const p: I32 = parallel { return 7; };
                return p + 1;
            };
            return result;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call i8* @"__ezrt_task_start_i32"' in ir_text
        assert 'call i32 @"__ezrt_task_join_i32"' in ir_text
        assert 'define i32 @"__ez_race_branch_' in ir_text
        assert 'call void @"__ezrt_parallel_enter"()' not in ir_text
        assert str(STD_ROOT / 'emcc' / 'runtime.js') in {str(lib) for lib in libs}
        assert not any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)
        assert 'pthread' not in {str(lib) for lib in libs}

    def test_flow_parallel_and_race_codegen_target_matrix(self):
        """flow/parallel/race 语法应在所有当前编译目标生成可链接语义。"""
        source = '''
        const run = (): I32 => {
            const result = flow {
                const p = parallel { return 7; };
                return p + race(pl = [() => { return 1; }, () => { return 2; }], timeout = 10);
            };
            return result;
        };
        '''
        for target in ('linux', 'macos', 'windows', 'android', 'ios', 'emcc'):
            module, errors, libs = compile_source(source, compile_target=target)
            assert module is not None, target
            assert len(errors) == 0, f'{target}: {errors}'
            ir_text = str(module)
            binding.parse_assembly(ir_text).verify()
            lib_names = {str(lib) for lib in libs}
            uses_native_runtime = any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)
            if target == 'emcc':
                assert 'call i8* @"__ezrt_task_start_i32"' in ir_text
                assert 'call i32 @"__ezrt_race_i32"' in ir_text
                assert not uses_native_runtime
                assert 'pthread' not in lib_names
                assert str(STD_ROOT / 'emcc' / 'runtime.js') in lib_names
            else:
                assert 'call i8* @"__ezrt_task_start_i32"' in ir_text
                assert 'call i32 @"__ezrt_race_i32"' in ir_text
                assert uses_native_runtime
                if target != 'windows':
                    assert 'pthread' in lib_names

    def test_flow_nested_function_return_does_not_capture_outer_flow_result(self):
        """flow 内声明的函数应使用独立返回路径，不能跳到外层 flow_exit。"""
        source = '''
        const run = (): I32 => {
            const result = flow {
                const f = (): I32 => { return 1; };
                return f();
            };
            return result;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        f_ir = function_ir(ir_text, 'f')
        assert 'flow_exit' not in f_ir
        assert 'ret i32 1' in f_ir

    def test_typeof_expr(self):
        """typeof 表达式（编译时类型查询）"""
        source = '''
        const run = () => {
            let t = typeof 42;
            return t;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None
        ir_text = str(module)
        run_ir = function_ir(ir_text, 'run')
        assert re.search(r'store i32 [1-9][0-9]*, i32\* %"t"', run_ir)
        assert 'ret i32 %"t.1"' in run_ir

    def test_typeof_type_has_stable_nonzero_id(self):
        """typeof Type[] 应返回稳定非零类型 ID"""
        source = '''
        struct User { id: I32; };
        const run = (): I32 => {
            return typeof User[];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        run_ir = function_ir(str(module), 'run')
        assert re.search(r'ret i32 [1-9][0-9]*', run_ir)

    def test_typeof_struct_value_supports_bitmask_comparison(self):
        """typeof err & Error == Error 应按 TypeID 位与比较生成 IR。"""
        source = '''
        const run = (): Bool => {
            const err = Error(code = 1, message = "x");
            return typeof err & Error == Error;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        run_ir = function_ir(str(module), 'run')
        assert 'and i32' in run_ir
        assert 'icmp' in run_ir
        assert 'ret i1 %' in run_ir

    def test_builtin_error_to_string_method_codegen(self):
        """文档声明的 Error.toString() 应作为内置方法生成可链接 IR。"""
        source = '''
        const run = (): Str => {
            const err = Error(code = 7, message = "boom");
            return err.toString();
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'define i8* @"Error_toString"(%"Error"* %"this")' in ir_text
        assert 'call i8* @"Error_toString"' in function_ir(ir_text, 'run')

    def test_builtin_blob_methods_codegen(self):
        """文档声明的 Blob.get/slice 应作为内置方法生成可链接 IR。"""
        source = '''
        const read = (): I8 => {
            const data = Blob(data = "hello", size = 5);
            return data.get(index = 1);
        };
        const part = (): Blob => {
            const data = Blob(data = "hello", size = 5);
            return data.slice(start = 1, len = 3);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'define i8 @"Blob_get"(%"Blob"* %"this", i64 %"index")' in ir_text
        assert 'define %"Blob" @"Blob_slice"(%"Blob"* %"this", i64 %"start", i64 %"len")' in ir_text
        assert 'call i8 @"Blob_get"' in function_ir(ir_text, 'read')
        assert 'call %"Blob" @"Blob_slice"' in function_ir(ir_text, 'part')

    def test_builtin_date_methods_use_namespaced_abi(self):
        """Date 方法应调用专用 ABI 符号，避免和 std/fmt.format 等自由函数冲突。"""
        source = '''
        const run = (): Str => {
            const d = Date(timestamp = 0);
            return d.format(fmt = "YYYY");
        };
        '''
        module, errors, libs = compile_source(source, compile_target='macos')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'declare i8* @"dateFormat"(%"Date"*' in ir_text
        assert 'call i8* @"dateFormat"' in function_ir(ir_text, 'run')
        assert any(str(lib).endswith('packages/std/native/time.c') for lib in libs)

    def test_comprehensive_module(self):
        """综合测试：结构体、方法、可选类型、泛型、管道、字典"""
        source = '''
        struct Point {
            x: I32;
            y: I32;
            distance = (this: #Point, other: Point): I32 => {
                let dx: I32 = this.x - other.x;
                let dy: I32 = this.y - other.y;
                return dx * dx + dy * dy;
            };
        };

        const id<T> = (x: T): T => {
            return x;
        };

        const run = () => {
            let p1 = Point(x = 3, y = 4);
            let p2: Point? = Point(x = 0, y = 0);
            let result = 5 -> id<I32>(x = %);
            let val: I32 | I64 = 42;
            let config = {
                debug: Bool = true,
                max: I32 = 100
            };
            return result;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        # 验证所有符号
        assert module.get_global('Point_distance') is not None
        assert module.get_global('id_I32') is not None
        assert module.get_global('run') is not None

    def test_string_interpolation(self):
        """字符串插值 "Hello {{name}}!" """
        source = '''
        const run = () => {
            let name: Str = "World";
            let greeting: Str = "Hello {{name}}!";
            return greeting;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None
        ir_text = str(module)
        # 应该包含字符串片段和拼接逻辑
        assert 'Hello ' in ir_text or 'World' in ir_text

    def test_currying_closure(self):
        """柯里化：add(a = 2, b = ?) 返回闭包"""
        source = '''
        const add = (a: I32, b: I32): I32 => {
            return a + b;
        };

        const run = () => {
            let add2 = add(a = 2, b = ?);
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        # 应该生成跳板函数 add_curried
        assert module.get_global('add_curried') is not None

    def test_placeholder_expression_reports_error(self):
        """独立 ? 不能作为普通表达式降级成 0。"""
        module, errors, _ = compile_source('const x = ?;')
        assert module is not None
        assert any('柯里化占位参数' in error for error in errors)

    def test_placeholder_expression_can_initialize_optional_none(self):
        """Optional<T> 期望上下文中的 ? 应生成空可选值。"""
        source = 'let x: I32? = ?;'
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'insertvalue {i1, i32} undef, i1 0, 0' in ir_text

    def test_struct_optional_field_accepts_placeholder_none(self):
        """结构体 Optional 字段的 field = ? 应生成空可选值。"""
        source = '''
        struct Node { value: I32; next: Node?; };
        const make = (): Node => {
            return Node(value = 1, next = ?);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '%"Node" = type {i32, {i1, %"Node"*}}' in ir_text
        assert 'insertvalue {i1, %"Node"*} undef, i1 0, 0' in ir_text

    def test_optional_struct_field_ok_is_not_treated_as_weak_ref(self):
        """Optional<Struct>.ok 应读取 ok 位，不能因 {i1, T*} 形状被当作弱引用解包。"""
        source = '''
        struct Node { value: I32; next: Node?; };
        const run = (): I32 => {
            let node = Node(value = 1, next = ?);
            return node.next.ok ? 1 : 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'getelementptr inbounds {i1, %"Node"*}, {i1, %"Node"*}*' in ir_text
        assert 'i32 0, i32 0' in ir_text

    # ==================== 标准库测试 ====================

    def test_stdlib_mem_copy(self):
        """std/mem copy → llvm.memcpy 内建函数"""
        source = '''
        from "./std/mem.ez" import { copy };

        const do_copy = (dst: Blob, src: Blob, n: I64): Void => {
            return copy(dst = dst, src = src, count = n);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        # 应包含 llvm.memcpy 调用，且不保留 copy 外部符号
        assert 'llvm.memcpy' in ir_text, f'未找到 llvm.memcpy 调用:\n{ir_text}'
        assert re.search(r'getelementptr inbounds %"Blob", %"Blob"\* %"dst\.\d+"', ir_text), ir_text
        assert re.search(r'getelementptr inbounds %"Blob", %"Blob"\* %"src\.\d+"', ir_text), ir_text
        assert 'bitcast %"Blob"' not in ir_text
        assert '@"copy"' not in ir_text

    def test_stdlib_mem_set(self):
        """std/mem set → llvm.memset 内建函数"""
        source = '''
        from "./std/mem.ez" import { set };

        const do_set = (dst: Blob, val: U8, n: I64): Void => {
            return set(dst = dst, value = val, count = n);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        # 应包含 llvm.memset 调用，且不保留 set 外部符号
        assert 'llvm.memset' in ir_text, f'未找到 llvm.memset 调用:\n{ir_text}'
        assert re.search(r'getelementptr inbounds %"Blob", %"Blob"\* %"dst\.\d+"', ir_text), ir_text
        assert 'bitcast %"Blob"' not in ir_text
        assert '@"set"' not in ir_text

    def test_stdlib_mem_set_alloc_raw_uses_blob_data(self):
        """allocRaw 返回的 Blob 值传给 set 时，应写入 Blob.data 指向的字节。"""
        source = '''
        from "./std/mem.ez" import { allocRaw, set };

        const do_set = (): Void => {
            const buf = allocRaw(size = 1);
            return set(dst = buf, value = 255, count = 1);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'getelementptr inbounds %"Blob", %"Blob"* %"buf", i32 0, i32 0' in ir_text
        assert 'llvm.memset' in ir_text
        assert 'bitcast %"Blob"' not in ir_text

    def test_member_assignment_and_compound_assignment(self):
        """结构体字段赋值和复合赋值应写回字段。"""
        source = '''
        struct Counter {
            value: I32;
        };

        const update = (): I32 => {
            let c = Counter(value = 1);
            c.value = 2;
            c.value += 3;
            return c.value;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'store i32 2' in ir_text

    def test_index_assignment_and_compound_assignment(self):
        """数组索引赋值和复合赋值应写回元素。"""
        source = '''
        const update = (): I32 => {
            let arr = [1, 2, 3];
            arr[0] = 2;
            arr[0] += 3;
            return arr[0];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'store i32 2' in ir_text
        assert '_assign_value' in ir_text

    def test_unsigned_integer_ops_use_unsigned_llvm_instructions(self):
        """U* 整数除法、取余、右移应使用无符号 LLVM 指令。"""
        source = '''
        const calc = (a: U32, b: U32): U32 => {
            let shift: U32 = 1;
            let x: U32 = a / b;
            let y: U32 = a % b;
            let z: U32 = a >> shift;
            x /= b;
            y %= b;
            z >>= shift;
            return x + y + z;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'udiv i32' in ir_text
        assert 'urem i32' in ir_text
        assert 'lshr i32' in ir_text
        assert 'sdiv i32' not in ir_text
        assert 'srem i32' not in ir_text
        assert 'ashr i32' not in ir_text
        assert 'store i32 %"_assign_value"' in ir_text

    def test_signed_integer_division_uses_floor_semantics(self):
        """有符号整数除法应按文档使用向下取整语义。"""
        source = '''
        const calc = (a: I32, b: I32): I32 => {
            let q = a / b;
            let r = a % b;
            q /= b;
            r %= b;
            return q + r;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'sdiv i32' in ir_text
        assert 'srem i32' in ir_text
        assert '_floor_div_adjust' in ir_text
        assert '_floor_rem_adjust' in ir_text
        assert '_assign_floor_adjust' in ir_text

    def test_unsigned_bitwise_results_keep_logical_shift(self):
        """U* 位运算表达式结果继续按无符号值生成逻辑右移。"""
        source = '''
        const calc = (a: U32, b: U32, shift: U32): U32 => {
            let x: U32 = (a & b) >> shift;
            let y: U32 = (a | b) >> shift;
            let z: U32 = (a ^ b) >> shift;
            x &= b;
            x >>= shift;
            return x + y + z;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert ir_text.count('lshr i32') >= 4
        assert 'ashr i32' not in ir_text

    def test_unsigned_relational_ops_use_unsigned_icmp(self):
        """U* 关系比较应使用无符号 icmp。"""
        source = '''
        const less = (a: U32, b: U32): Bool => {
            return a < b;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'icmp ult i32' in ir_text
        assert 'icmp slt i32' not in ir_text

    def test_stdlib_mem_error_codes(self):
        """std/mem 错误码常量"""
        source = '''
        from "./std/mem.ez" import { errIO, errNotFound };

        const check_error = (): I32 => {
            return errIO;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'

    def test_stdlib_mem_alloc_raw(self):
        """std/mem allocRaw → Arena 分配 Blob"""
        source = '''
        from "./std/mem.ez" import { allocRaw };

        const make_buf = (): Blob => {
            return allocRaw(size = 64);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'call i8* @"__arena_alloc"' in ir_text
        assert 'insertvalue %"Blob"' in ir_text
        assert '@"allocRaw"' not in ir_text

    def test_stdlib_io_import(self):
        """std/io 声明导入"""
        source = '''
        from "./std/io.ez" import { print, println, error, readLine };

        const say_hello = (): Void => {
            print(msg = "Hello");
            println(msg = "World");
            error(msg = "Oops");
            const line = readLine();
            return;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert str(STD_ROOT / 'native' / 'io.c') in libs
        assert module.get_global('print') is not None
        assert module.get_global('println') is not None
        assert module.get_global('error') is not None
        assert module.get_global('readLine') is not None

    def test_stdlib_io_target_filter(self):
        """std/io extern 应按目标平台过滤"""
        source = 'from "./std/io.ez" import { print };'
        _, _, android_libs = compile_source(source, compile_target='android')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        assert android_libs == [str(STD_ROOT / 'native' / 'io.c')]
        assert ios_libs == [str(STD_ROOT / 'native' / 'io.c')]

    def test_stdlib_os_import(self):
        """std/os 声明导入"""
        source = '''
        from "./std/os.ez" import { args, env, setEnv, cwd, exit, pid, platform, arch };

        const get_info = (): Str => {
            const argv = args();
            const home = env(key = "HOME");
            const updated = setEnv(key = "EZLANG", value = "1");
            const dir = cwd();
            const proc = pid();
            const os_name = platform();
            const arch_name = arch();
            return os_name;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'os.c')]
        for name in ['args', 'env', 'setEnv', 'cwd', 'exit', 'pid', 'platform', 'arch']:
            assert module.get_global(name) is not None

    def test_stdlib_os_target_filter(self):
        """std/os extern 应按桌面目标过滤"""
        source = 'from "./std/os.ez" import { platform };'
        _, _, macos_libs = compile_source(source, compile_target='macos')
        _, _, android_libs = compile_source(source, compile_target='android')
        assert macos_libs == [str(STD_ROOT / 'native' / 'os.c')]
        assert android_libs == [str(STD_ROOT / 'native' / 'os.c')]

    def test_stdlib_import_does_not_enable_default_global_lock_runtime(self):
        """导入模块内部声明不应触发用户源默认全局锁运行时。"""
        source = 'from "./std/os.ez" import { platform };'
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'os.c')]
        assert not any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)

    def test_stdlib_fs_import(self):
        """std/fs 文件系统导入"""
        source = '''
        from "./std/fs.ez" import {
            readFile, writeFile, appendFile, removeFile,
            mkdir, removeDir, listDir, exists, isDir, stat, absPath
        };

        const check = (path: Str, content: Blob): Bool => {
            const data = readFile(path = path);
            writeFile(path = path, content = content);
            appendFile(path = path, content = content);
            removeFile(path = path);
            mkdir(path = path);
            removeDir(path = path, recursive = true);
            const names = listDir(path = path);
            const ok = exists(path = path);
            const dir = isDir(path = path);
            const info = stat(path = path);
            const full = absPath(path = path);
            return ok;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'fs.c')]
        for name in ['readFile', 'writeFile', 'appendFile', 'removeFile', 'mkdir',
                     'removeDir', 'listDir', 'exists', 'isDir', 'stat', 'absPath']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert 'FileStat' in ir_text
        assert 'sret({i1, %"FileStat"})' in ir_text

    def test_stdlib_fs_target_filter(self):
        """std/fs extern 应按桌面目标过滤"""
        source = 'from "./std/fs.ez" import { exists };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, android_libs = compile_source(source, compile_target='android')
        assert linux_libs == [str(STD_ROOT / 'native' / 'fs.c')]
        assert windows_libs == [str(STD_ROOT / 'native' / 'fs.c')]
        assert android_libs == [str(STD_ROOT / 'native' / 'fs.c')]

    def test_stdlib_path_import(self):
        """std/path 路径库导入"""
        source = '''
        from "./std/path.ez" import {
            PathParts, pathSeparator, pathJoin, pathNormalize, pathDir, pathBase,
            pathExt, pathIsAbs, pathRelative, pathParse, pathToFileUrl, pathFromFileUrl
        };

        const check_path = (): I32 => {
            const sep = pathSeparator();
            const parts: Str[] = ["/tmp", "ez", "../main.ez"];
            const joined = pathJoin(parts = parts);
            const normalized = pathNormalize(path = joined);
            const dir = pathDir(path = normalized);
            const base = pathBase(path = normalized);
            const ext = pathExt(path = normalized);
            const abs = pathIsAbs(path = normalized);
            const rel = pathRelative(fromPath = "/tmp", toPath = normalized);
            const parsed = pathParse(path = normalized);
            const url = pathToFileUrl(path = normalized);
            const back = pathFromFileUrl(url = url);
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'path.c')]
        for name in ['pathSeparator', 'pathJoin', 'pathNormalize', 'pathDir', 'pathBase',
                     'pathExt', 'pathIsAbs', 'pathRelative', 'pathParse', 'pathToFileUrl', 'pathFromFileUrl']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert 'PathParts' in ir_text
        assert 'sret(%."PathParts")' in ir_text or 'sret(%"PathParts")' in ir_text

    def test_stdlib_path_target_filter(self):
        """std/path extern 应按目标过滤"""
        source = 'from "./std/path.ez" import { pathNormalize };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'path.c')]
        assert ios_libs == [str(STD_ROOT / 'native' / 'path.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'path.js')]

    def test_stdlib_str_import(self):
        """std/str UTF-8 字符串库导入"""
        source = '''
        from "./std/str.ez" import {
            strByteLen, strCharLen, strIsEmpty, strIsValidUtf8,
            strSliceBytes, strSliceChars, strCharAt, strToBytes, strFromBytes,
            strContains, strStartsWith, strEndsWith, strIndexOf,
            strSplit, strJoin, strTrim, strReplace, strToLower, strToUpper
        };

        const check_str = (): I32 => {
            const text = " EzLang ";
            const byte_len = strByteLen(s = text);
            const char_len = strCharLen(s = text);
            const empty = strIsEmpty(s = "");
            const valid = strIsValidUtf8(s = text);
            const byte_slice = strSliceBytes(s = text, start = 1, end = 3);
            const char_slice = strSliceChars(s = text, start = 1, end = 3);
            const ch = strCharAt(s = text, index = 1);
            const bytes = strToBytes(s = text);
            const restored = strFromBytes(data = bytes);
            const has = strContains(s = text, needle = "Ez");
            const starts = strStartsWith(s = text, prefix = " ");
            const ends = strEndsWith(s = text, suffix = " ");
            const idx = strIndexOf(s = text, needle = "Lang");
            const parts = strSplit(s = text, sep = " ");
            const joined = strJoin(parts = parts, sep = "-");
            const trimmed = strTrim(s = text);
            const replaced = strReplace(s = text, old = "Ez", newValue = "Easy");
            const lower = strToLower(s = text);
            const upper = strToUpper(s = text);
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'str.c')]
        for name in ['strByteLen', 'strCharLen', 'strIsEmpty', 'strIsValidUtf8', 'strSliceBytes',
                     'strSliceChars', 'strCharAt', 'strToBytes', 'strFromBytes', 'strContains',
                     'strStartsWith', 'strEndsWith', 'strIndexOf', 'strSplit', 'strJoin',
                     'strTrim', 'strReplace', 'strToLower', 'strToUpper']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert_small_struct_return_bridge(ir_text, 'strToBytes', 'Blob', '{i8*, i64}')
        assert 'declare void @"strSplit"({i8***, i64, i64, i64}* sret({i8***, i64, i64, i64})' in ir_text

    def test_stdlib_str_target_filter(self):
        """std/str extern 应按目标过滤"""
        source = 'from "./std/str.ez" import { strByteLen };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, android_libs = compile_source(source, compile_target='android')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'str.c')]
        assert android_libs == [str(STD_ROOT / 'native' / 'str.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'str.js')]

    def test_stdlib_math_import(self):
        """std/math 数学库导入"""
        source = '''
        from "./std/math.ez" import {
            mathPI, mathE, mathAbsI32, mathAbsI64, mathMinI32, mathMaxI32,
            mathClampI32, mathGcdI64, mathLcmI64, mathSqrt, mathPow, mathSin,
            mathCos, mathTan, mathLog, mathExp, mathFloor, mathCeil, mathRound,
            mathIsNaN, mathIsInf, mathAddI64Checked, mathSubI64Checked,
            mathMulI64Checked, mathDivI64Checked, mathF64ToI32, mathF64ToI64, mathI64ToF64
        };

        const check_math = (): I32 => {
            const abs32 = mathAbsI32(value = -3);
            const abs64 = mathAbsI64(value = -4);
            const minv = mathMinI32(a = 1, b = 2);
            const maxv = mathMaxI32(a = 1, b = 2);
            const clamped = mathClampI32(value = 5, minValue = 0, maxValue = 3);
            const gcd = mathGcdI64(a = 18, b = 24);
            const lcm = mathLcmI64(a = 6, b = 8);
            const root = mathSqrt(value = 4.0);
            const power = mathPow(base = 2.0, exp = 8.0);
            const sinv = mathSin(value = mathPI);
            const cosv = mathCos(value = 0.0);
            const tanv = mathTan(value = 0.0);
            const logv = mathLog(value = mathE);
            const expv = mathExp(value = 1.0);
            const floorv = mathFloor(value = 1.9);
            const ceilv = mathCeil(value = 1.1);
            const roundv = mathRound(value = 1.5);
            const nan = mathIsNaN(value = root);
            const inf = mathIsInf(value = root);
            const sum = mathAddI64Checked(a = 1, b = 2);
            const diff = mathSubI64Checked(a = 1, b = 2);
            const product = mathMulI64Checked(a = 2, b = 3);
            const quotient = mathDivI64Checked(a = 6, b = 3);
            const i32v = mathF64ToI32(value = 42.0);
            const i64v = mathF64ToI64(value = 42.0);
            const f64v = mathI64ToF64(value = 42);
            return abs32;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'math.c'), 'm']
        for name in ['mathAbsI32', 'mathAbsI64', 'mathMinI32', 'mathMaxI32', 'mathClampI32',
                     'mathGcdI64', 'mathLcmI64', 'mathSqrt', 'mathPow', 'mathSin', 'mathCos',
                     'mathTan', 'mathLog', 'mathExp', 'mathFloor', 'mathCeil', 'mathRound',
                     'mathIsNaN', 'mathIsInf', 'mathAddI64Checked', 'mathSubI64Checked',
                     'mathMulI64Checked', 'mathDivI64Checked', 'mathF64ToI32', 'mathF64ToI64', 'mathI64ToF64']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert_optional_return_bridge(ir_text, 'mathAddI64Checked', 'i64', 'x86_64')
        assert_optional_return_bridge(ir_text, 'mathF64ToI32', 'i32', 'x86_64')
        assert_optional_return_bridge(ir_text, 'mathF64ToI64', 'i64', 'x86_64')

        aarch64_module, aarch64_errors, _ = compile_source(source, compile_target='linux', target_arch='aarch64')
        assert aarch64_module is not None
        assert len(aarch64_errors) == 0, f'编译错误: {aarch64_errors}'
        aarch64_ir = str(aarch64_module)
        assert_optional_return_bridge(aarch64_ir, 'mathAddI64Checked', 'i64', 'aarch64')
        assert_optional_return_bridge(aarch64_ir, 'mathF64ToI64', 'i64', 'aarch64')

    def test_stdlib_math_target_filter(self):
        """std/math extern 应按目标过滤"""
        source = 'from "./std/math.ez" import { mathSqrt };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, macos_libs = compile_source(source, compile_target='macos')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'math.c'), 'm']
        assert macos_libs == [str(STD_ROOT / 'native' / 'math.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'math.js')]

    def test_stdlib_random_import(self):
        """std/random 随机数库导入"""
        source = '''
        from "./std/random.ez" import {
            RandomSource, randomSeed, randomNextU32, randomNextU64, randomRangeI64,
            randomRangeF64, randomShuffleBytes, randomShuffle, randomEntropy,
            randomSecureBytes, randomSecureU64
        };

        const check_random = (): I32 => {
            let source = randomSeed(seed = 42);
            const n32 = randomNextU32(this = #source);
            const n64 = randomNextU64(this = #source);
            const ranged_i = randomRangeI64(this = #source, minValue = 1, maxValue = 10);
            const ranged_f = randomRangeF64(this = #source, minValue = 0.0, maxValue = 1.0);
            const shuffled = randomShuffleBytes(this = #source, data = Blob(data = "abcd", size = 4));
            let nums: List<I32> = [1, 2, 3, 4];
            let shuffled_nums: List<I32> = randomShuffle<I32>(this = #source, list = nums);
            const entropy = randomEntropy(size = 8);
            const secure = randomSecureBytes(size = 8);
            const secure64 = randomSecureU64();
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'random.c')]
        for name in ['randomSeed', 'randomNextU32', 'randomNextU64', 'randomRangeI64',
                     'randomRangeF64', 'randomShuffleBytes', 'randomEntropy',
                     'randomSecureBytes', 'randomSecureU64']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert '%"RandomSource" = type {i64}' in ir_text
        assert_small_struct_return_bridge(ir_text, 'randomSeed', 'RandomSource', 'i64')
        assert 'declare i64 @"randomNextU64"' in ir_text
        assert_small_struct_return_bridge(ir_text, 'randomShuffleBytes', 'Blob', '{i8*, i64}')
        assert 'randomShuffle_I32' not in ir_text
        assert 'random_shuffle_cond' in ir_text
        assert 'declare void @"randomSecureBytes"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
        assert_optional_return_bridge(ir_text, 'randomSecureU64', 'i64', 'x86_64')

        aarch64_module, aarch64_errors, _ = compile_source(source, compile_target='linux', target_arch='aarch64')
        assert aarch64_module is not None
        assert len(aarch64_errors) == 0, f'编译错误: {aarch64_errors}'
        aarch64_ir = str(aarch64_module)
        assert_small_struct_return_bridge(aarch64_ir, 'randomSeed', 'RandomSource', 'i64')
        assert_small_struct_return_bridge(aarch64_ir, 'randomShuffleBytes', 'Blob', '[2 x i64]')
        assert_optional_return_bridge(str(aarch64_module), 'randomSecureU64', 'i64', 'aarch64')

    def test_stdlib_random_target_filter(self):
        """std/random extern 应按目标过滤"""
        source = 'from "./std/random.ez" import { randomSeed };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'random.c')]
        assert ios_libs == [str(STD_ROOT / 'native' / 'random.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'random.js')]
        module, errors, _ = compile_source('from "./std/random.ez" import { randomSeed, randomSecureU64 }; let source = randomSeed(seed = 1); let n = randomSecureU64();', compile_target='emcc')
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'declare void @"randomSeed"(%"RandomSource"* sret(%"RandomSource")' in ir_text
        assert 'declare void @"randomSecureU64"({i1, i64}* sret({i1, i64})' in ir_text

    def test_stdlib_hash_import(self):
        """std/hash 非加密哈希库导入"""
        source = '''
        from "./std/hash.ez" import {
            hashFnv1a32, hashFnv1a64, hashStrFnv1a32, hashStrFnv1a64,
            hashCombineU64, crc32, crc32Str
        };

        const check_hash = (): U32 => {
            const data = Blob(data = "hello", size = 5);
            const h32 = hashFnv1a32(data = data);
            const h64 = hashFnv1a64(data = data);
            const sh32 = hashStrFnv1a32(s = "hello");
            const sh64 = hashStrFnv1a64(s = "hello");
            const combined = hashCombineU64(seed = h64, value = sh64);
            const c1 = crc32(data = data);
            const c2 = crc32Str(s = "hello");
            return h32;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'hash.c')]
        for name in ['hashFnv1a32', 'hashFnv1a64', 'hashStrFnv1a32', 'hashStrFnv1a64',
                     'hashCombineU64', 'crc32', 'crc32Str']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert 'declare i32 @"hashFnv1a32"' in ir_text
        assert 'declare i64 @"hashFnv1a64"' in ir_text
        assert 'declare i32 @"crc32Str"' in ir_text

    def test_stdlib_hash_target_filter(self):
        """std/hash extern 应按目标过滤"""
        source = 'from "./std/hash.ez" import { crc32Str };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, android_libs = compile_source(source, compile_target='android')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'hash.c')]
        assert android_libs == [str(STD_ROOT / 'native' / 'hash.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'hash.js')]

    def test_stdlib_platform_import(self):
        """std/platform 平台能力检测库导入"""
        source = '''
        from "./std/platform.ez" import {
            platformOS, platformArch, platformIsLittleEndian, platformPointerBits,
            platformPageSize, platformCpuCount, platformMemoryLimit,
            platformHasThreads, platformHasFileSystem, platformHasNetwork,
            platformHasCrypto, platformHasDom, platformHasSubprocess
        };

        const check_platform = (): I32 => {
            const os = platformOS();
            const arch = platformArch();
            const little = platformIsLittleEndian();
            const ptr = platformPointerBits();
            const page = platformPageSize();
            const cpus = platformCpuCount();
            const mem = platformMemoryLimit();
            const threads = platformHasThreads();
            const fs = platformHasFileSystem();
            const net = platformHasNetwork();
            const crypto = platformHasCrypto();
            const dom = platformHasDom();
            const proc = platformHasSubprocess();
            return ptr;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'platform.c')]
        for name in ['platformOS', 'platformArch', 'platformIsLittleEndian', 'platformPointerBits',
                     'platformPageSize', 'platformCpuCount', 'platformMemoryLimit', 'platformHasThreads',
                     'platformHasFileSystem', 'platformHasNetwork', 'platformHasCrypto', 'platformHasDom',
                     'platformHasSubprocess']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert 'declare i8* @"platformOS"' in ir_text
        assert 'declare i1 @"platformIsLittleEndian"' in ir_text
        assert 'declare i64 @"platformPageSize"' in ir_text
        assert 'declare i32 @"platformCpuCount"' in ir_text

    def test_stdlib_platform_target_filter(self):
        """std/platform extern 应按目标过滤"""
        source = 'from "./std/platform.ez" import { platformOS };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'platform.c')]
        assert ios_libs == [str(STD_ROOT / 'native' / 'platform.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'platform.js')]

    def test_stdlib_process_import(self):
        """std/process 外部进程库导入"""
        source = '''
        from "./std/process.ez" import {
            Command, Process, ProcessResult, processExec, processSpawn,
            processWait, processTerminate, processStdin, processStdout, processStderr,
            processCurrentPath
        };

        const check_process = (): I32 => {
            const args: Str[] = ["-c", "printf hello"];
            const envs: Str[] = ["EZLANG_PROCESS_TEST=1"];
            const empty: Str[] = [];
            const command = Command(program = "/bin/sh", args = args, cwd = "", env = envs, stdin = Blob(data = "", size = 0));
            const result = processExec(command = command);
            const spawned = processSpawn(command = Command(program = "/bin/sh", args = args, cwd = "", env = empty, stdin = Blob(data = "", size = 0)));
            const waited = processWait(process = Process(handle = 0, pid = 0));
            const killed = processTerminate(process = Process(handle = 0, pid = 0));
            const in_stream = processStdin(process = Process(handle = 0, pid = 0));
            const out_stream = processStdout(process = Process(handle = 0, pid = 0));
            const err_stream = processStderr(process = Process(handle = 0, pid = 0));
            const path = processCurrentPath();
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'process.c')]
        for name in ['processExec', 'processSpawn', 'processWait', 'processTerminate', 'processStdin', 'processStdout', 'processStderr', 'processCurrentPath']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert '%"Command" = type' in ir_text
        assert '%"Process" = type {i64, i64}' in ir_text
        assert '%"ProcessResult" = type' in ir_text
        assert '%"Stream" = type {i64, i32}' in ir_text
        assert 'declare void @"processExec"({i1, %"ProcessResult"}* sret({i1, %"ProcessResult"})' in ir_text
        assert 'declare void @"processSpawn"({i1, %"Process"}* sret({i1, %"Process"})' in ir_text
        assert 'declare void @"processWait"({i1, %"ProcessResult"}* sret({i1, %"ProcessResult"})' in ir_text
        assert 'declare i1 @"processTerminate"(%"Process"*' in ir_text
        assert 'declare void @"processStdin"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
        assert 'declare void @"processStdout"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
        assert 'declare void @"processStderr"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
        assert_optional_return_bridge(ir_text, 'processCurrentPath', 'i8*', 'x86_64')

        aarch64_module, aarch64_errors, _ = compile_source(source, compile_target='linux', target_arch='aarch64')
        assert aarch64_module is not None
        assert len(aarch64_errors) == 0, f'编译错误: {aarch64_errors}'
        assert_optional_return_bridge(str(aarch64_module), 'processCurrentPath', 'i8*', 'aarch64')

    def test_stdlib_process_target_filter(self):
        """std/process extern 应覆盖桌面、移动端与 emcc 目标"""
        source = 'from "./std/process.ez" import { processCurrentPath };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, android_libs = compile_source(source, compile_target='android')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'process.c')]
        assert windows_libs == [str(STD_ROOT / 'native' / 'stream.c'), 'ws2_32', str(STD_ROOT / 'native' / 'process.c')]
        assert android_libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'process.c')]
        assert ios_libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'process.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'stream.js'), str(STD_ROOT / 'emcc' / 'process.js')]
        module, errors, _ = compile_source(source + '\nlet path = processCurrentPath();\n', compile_target='emcc')
        assert len(errors) == 0, f'编译错误: {errors}'
        assert 'declare void @"processCurrentPath"({i1, i8*}* sret({i1, i8*})' in str(module)

    def test_imports_resolve_nested_relative_struct_types(self, tmp_path):
        """导入文件内部的相对导入应按该文件目录解析，供 declare 签名使用。"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "stream.ez").write_text(
            "export struct Stream { handle: I64; kind: I32; };\n",
            encoding="utf-8",
        )
        (lib_dir / "process.ez").write_text(
            'from "./stream.ez" import { Stream };\n'
            'extern "native.c" for linux;\n'
            'export declare const pipe: () => Stream?;\n',
            encoding="utf-8",
        )
        (tmp_path / "native.c").write_text("", encoding="utf-8")
        source = 'from "./lib/process.ez" import { pipe };\nlet s = pipe();\n'

        module, errors, libs = compile_source(source, compile_target="linux", base_dir=tmp_path)

        assert module is not None
        assert len(errors) == 0, f"编译错误: {errors}"
        ir_text = str(module)
        assert '%"Stream" = type {i64, i32}' in ir_text
        assert 'declare void @"pipe"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text

    def test_stdlib_uri_import(self):
        """std/uri URL 解析库导入"""
        source = '''
        from "./std/uri.ez" import {
            UriParts, uriParse, uriBuild, uriNormalize, uriScheme, uriHost, uriPort,
            uriPath, uriQuery, uriFragment, uriEncodeQuery, uriDecodeQuery,
            uriEncodePathSegment, uriDecodePathSegment, uriQueryGet, uriQuerySet
        };

        const check_uri = (): I32 => {
            const url = "https://user@example.com:443/a/../b?q=a%20b#top";
            const parts = uriParse(url = url);
            const rebuilt = uriBuild(parts = UriParts(scheme = "https", userInfo = "", host = "example.com", port = -1, path = "/b", query = "", fragment = ""));
            const normalized = uriNormalize(url = url);
            const scheme = uriScheme(url = url);
            const host = uriHost(url = url);
            const port = uriPort(url = url);
            const path = uriPath(url = url);
            const query = uriQuery(url = url);
            const fragment = uriFragment(url = url);
            const encoded = uriEncodeQuery(s = "a b");
            const decoded = uriDecodeQuery(s = encoded);
            const seg = uriEncodePathSegment(s = "a/b");
            const raw = uriDecodePathSegment(s = seg);
            const next_query = uriQuerySet(query = "a=1", key = "b", value = "two words");
            const value = uriQueryGet(query = next_query, key = "b");
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'uri.c')]
        for name in ['uriParse', 'uriBuild', 'uriNormalize', 'uriScheme', 'uriHost', 'uriPort',
                     'uriPath', 'uriQuery', 'uriFragment', 'uriEncodeQuery', 'uriDecodeQuery',
                     'uriEncodePathSegment', 'uriDecodePathSegment', 'uriQueryGet', 'uriQuerySet']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert '%"UriParts" = type' in ir_text
        assert 'declare void @"uriParse"({i1, %"UriParts"}* sret({i1, %"UriParts"})' in ir_text
        assert 'declare i8* @"uriBuild"(%"UriParts"*' in ir_text
        assert_optional_return_bridge(ir_text, 'uriScheme', 'i8*', 'x86_64')
        assert_optional_return_bridge(ir_text, 'uriHost', 'i8*', 'x86_64')
        assert_optional_return_bridge(ir_text, 'uriPort', 'i32', 'x86_64')

        aarch64_module, aarch64_errors, _ = compile_source(source, compile_target='linux', target_arch='aarch64')
        assert aarch64_module is not None
        assert len(aarch64_errors) == 0, f'编译错误: {aarch64_errors}'
        aarch64_ir = str(aarch64_module)
        assert_optional_return_bridge(aarch64_ir, 'uriScheme', 'i8*', 'aarch64')
        assert_optional_return_bridge(aarch64_ir, 'uriHost', 'i8*', 'aarch64')

    def test_stdlib_uri_target_filter(self):
        """std/uri extern 应按目标过滤"""
        source = 'from "./std/uri.ez" import { uriNormalize };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, android_libs = compile_source(source, compile_target='android')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'uri.c')]
        assert android_libs == [str(STD_ROOT / 'native' / 'uri.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'uri.js')]

    def test_stdlib_debug_import(self):
        """std/debug 调试诊断库导入"""
        source = '''
        from "./std/debug.ez" import {
            debugPrint, debugAssert, debugCrash, debugLocation, debugRuntimeInfo, debugHex, debugStack
        };

        const check_debug = (): I32 => {
            debugPrint(msg = "hello");
            debugAssert(condition = true, msg = "ok");
            const loc = debugLocation(file = "main.ez", line = 1, column = 2);
            const info = debugRuntimeInfo();
            const hex = debugHex(data = Blob(data = "ab", size = 2));
            const stack = debugStack();
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'debug.c')]
        for name in ['debugPrint', 'debugAssert', 'debugCrash', 'debugLocation', 'debugRuntimeInfo', 'debugHex', 'debugStack']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert 'declare void @"debugPrint"' in ir_text
        assert 'declare i8* @"debugLocation"' in ir_text
        assert 'declare i8* @"debugHex"(%"Blob"*' in ir_text
        assert_optional_return_bridge(ir_text, 'debugStack', 'i8*', 'x86_64')

        aarch64_module, aarch64_errors, _ = compile_source(source, compile_target='linux', target_arch='aarch64')
        assert aarch64_module is not None
        assert len(aarch64_errors) == 0, f'编译错误: {aarch64_errors}'
        assert_optional_return_bridge(str(aarch64_module), 'debugStack', 'i8*', 'aarch64')

    def test_stdlib_debug_target_filter(self):
        """std/debug extern 应按目标过滤"""
        source = 'from "./std/debug.ez" import { debugRuntimeInfo };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'debug.c')]
        assert windows_libs == [str(STD_ROOT / 'native' / 'debug.c'), 'dbghelp']
        assert ios_libs == [str(STD_ROOT / 'native' / 'debug.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'debug.js')]

    def test_stdlib_log_import(self):
        """std/log 结构化日志库导入"""
        source = '''
        from "./std/log.ez" import {
            logTrace, logDebug, logInfo, logWarn, logError, logTargetStderr, logTargetFile, LogConfig,
            logDefaultConfig, logConfigure, logSetLevel, logSetFile, logWrite, logWriteFields, logWriteAt,
            logInfoMsg, logWarnMsg, logErrorMsg
        };

        const check_log = (): I32 => {
            const cfg = logDefaultConfig();
            logConfigure(config = LogConfig(minLevel = logDebug, target = logTargetStderr, includeTimestamp = true, includeLocation = true));
            logSetLevel(level = logTrace);
            const file_ok = logSetFile(path = "build.log");
            logConfigure(config = LogConfig(minLevel = logDebug, target = logTargetFile, includeTimestamp = true, includeLocation = true));
            logWrite(level = logInfo, msg = "hello");
            logWriteFields(level = logWarn, msg = "warn", fields = ["key", "value"]);
            logWriteAt(level = logError, msg = "err", file = "main.ez", line = 1, column = 2, fields = ["code", "1"]);
            logInfoMsg(msg = "info");
            logWarnMsg(msg = "warn");
            logErrorMsg(msg = "error");
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'log.c')]
        for name in ['logDefaultConfig', 'logConfigure', 'logSetLevel', 'logSetFile', 'logWrite', 'logWriteFields',
                     'logWriteAt', 'logInfoMsg', 'logWarnMsg', 'logErrorMsg']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert '%"LogConfig" = type' in ir_text
        assert_small_struct_return_bridge(ir_text, 'logDefaultConfig', 'LogConfig', '{i64, i32}')
        assert 'declare void @"logConfigure"(%"LogConfig"*' in ir_text
        assert 'declare i1 @"logSetFile"' in ir_text
        assert 'declare void @"logWriteFields"(i32' in ir_text

    def test_stdlib_log_target_filter(self):
        """std/log extern 应按目标过滤"""
        source = 'from "./std/log.ez" import { logInfoMsg };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, android_libs = compile_source(source, compile_target='android')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'log.c')]
        assert android_libs == [str(STD_ROOT / 'native' / 'log.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'log.js')]

    def test_stdlib_log_compile_min_level_drops_static_low_level_calls(self):
        """std/log 编译期级别过滤应删除静态低级别调用。"""
        source = '''
        from "./std/log.ez" import {
            logTrace, logWarn, logError, logDebugMsg, logInfoMsg, logWarnMsg, logWrite
        };

        const check_log = (): I32 => {
            logDebugMsg(msg = "drop-debug");
            logInfoMsg(msg = "drop-info");
            logWarnMsg(msg = "keep-warn");
            logWrite(level = logTrace, msg = "drop-write");
            logWrite(level = logError, msg = "keep-write");
            logWrite(level = logWarn, msg = "keep-warn-write");
            return 0;
        };
        '''
        module, errors, _ = compile_source(
            source,
            compile_target='linux',
            target_arch='x86_64',
            log_compile_min_level=3,
        )

        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'drop-debug' not in ir_text
        assert 'drop-info' not in ir_text
        assert 'drop-write' not in ir_text
        assert 'keep-warn' in ir_text
        assert 'keep-write' in ir_text
        assert 'keep-warn-write' in ir_text
        assert 'call void @"logDebugMsg"' not in ir_text
        assert 'call void @"logInfoMsg"' not in ir_text
        assert ir_text.count('call void @"logWrite"') == 2

    def test_stdlib_regex_import(self):
        """std/regex 轻量正则库导入"""
        source = '''
        from "./std/regex.ez" import {
            regexIgnoreCase, Regex, RegexMatch, regexCompile, regexIsValid, regexTest,
            regexFind, regexFindAll, regexReplace, regexSplit
        };

        const check_regex = (): I32 => {
            const re = regexCompile(pattern = "([a-z]+)", flags = regexIgnoreCase);
            const valid = regexIsValid(regex = re);
            const matched = regexTest(regex = re, input = "Hello 42");
            const found = regexFind(regex = re, input = "Hello 42");
            const all = regexFindAll(regex = re, input = "a b c");
            const replaced = regexReplace(regex = re, input = "abc", replacement = "x");
            const parts = regexSplit(regex = re, input = "a,b,c");
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'regex.c')]
        for name in ['regexCompile', 'regexIsValid', 'regexTest', 'regexFind', 'regexFindAll', 'regexReplace', 'regexSplit']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert '%"Regex" = type' in ir_text
        assert '%"RegexMatch" = type' in ir_text
        assert_regex_compile_return_bridge(ir_text, 'x86_64')
        assert 'declare void @"regexFind"({i1, %"RegexMatch"}* sret({i1, %"RegexMatch"})' in ir_text
        assert 'declare void @"regexFindAll"({i8***, i64, i64, i64}* sret({i8***, i64, i64, i64})' in ir_text

    def test_stdlib_regex_compile_return_bridge_for_aarch64(self):
        """aarch64 native 下 Regex 小结构返回应按 [2 x i64] 桥接。"""
        source = 'from "./std/regex.ez" import { regexCompile }; let re = regexCompile(pattern = "a", flags = 0);'

        module, errors, _ = compile_source(source, compile_target='macos', target_arch='aarch64')

        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert_regex_compile_return_bridge(str(module), 'aarch64')

    def test_stdlib_regex_target_filter(self):
        """std/regex extern 应按目标过滤"""
        source = 'from "./std/regex.ez" import { regexCompile };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'regex.c')]
        assert windows_libs == [str(STD_ROOT / 'native' / 'regex.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'regex.js')]
        module, errors, _ = compile_source('from "./std/regex.ez" import { regexCompile }; let re = regexCompile(pattern = "a", flags = 0);', compile_target='emcc')
        assert len(errors) == 0, f'编译错误: {errors}'
        assert 'declare void @"regexCompile"(%"Regex"* sret(%"Regex")' in str(module)

    def test_stdlib_crypto_import(self):
        """std/crypto 加密哈希库导入"""
        source = '''
        from "./std/crypto.ez" import { cryptoSha256, cryptoSha512, cryptoHmacSha256, cryptoHmacSha512 };

        const check_crypto = (): I32 => {
            const data = Blob(data = "hello", size = 5);
            const key = Blob(data = "key", size = 3);
            const sha256 = cryptoSha256(data = data);
            const sha512 = cryptoSha512(data = data);
            const h256 = cryptoHmacSha256(key = key, data = data);
            const h512 = cryptoHmacSha512(key = key, data = data);
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'crypto.c'), 'dl']
        for name in ['cryptoSha256', 'cryptoSha512', 'cryptoHmacSha256', 'cryptoHmacSha512']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert 'declare void @"cryptoSha256"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
        assert 'declare void @"cryptoHmacSha512"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text

    def test_stdlib_crypto_target_filter(self):
        """std/crypto extern 应按目标过滤"""
        source = 'from "./std/crypto.ez" import { cryptoSha256 };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'crypto.c'), 'dl']
        assert windows_libs == [str(STD_ROOT / 'native' / 'crypto.c'), 'bcrypt']
        assert ios_libs == [str(STD_ROOT / 'native' / 'crypto.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'crypto.js')]

    def test_stdlib_compress_import(self):
        """std/compress 压缩库导入"""
        source = '''
        from "./std/stream.ez" import { streamFromBlob };
        from "./std/compress.ez" import {
            compressGzip, decompressGzip, compressZlib, decompressZlib,
            compressDeflate, decompressDeflate,
            compressGzipStream, decompressGzipStream, compressZlibStream, decompressZlibStream,
            compressDeflateStream, decompressDeflateStream
        };

        const check_compress = (): I32 => {
            const data = Blob(data = "hello", size = 5);
            const gz = compressGzip(data = data);
            const raw_gz = decompressGzip(data = gz.value);
            const z = compressZlib(data = data);
            const raw_z = decompressZlib(data = z.value);
            const d = compressDeflate(data = data);
            const raw_d = decompressDeflate(data = d.value);
            const src = streamFromBlob(data = data);
            const dst = streamFromBlob(data = Blob(data = "", size = 0));
            const streamed = compressGzipStream(dst = dst.value, src = src.value, bufferSize = 2);
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'compress.c'), 'z']
        for name in [
            'compressGzip', 'decompressGzip', 'compressZlib', 'decompressZlib', 'compressDeflate', 'decompressDeflate',
            'compressGzipStream', 'decompressGzipStream', 'compressZlibStream', 'decompressZlibStream',
            'compressDeflateStream', 'decompressDeflateStream'
        ]:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert 'declare void @"compressGzip"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
        assert 'declare void @"decompressDeflate"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
        assert 'declare i64 @"compressGzipStream"(%"Stream"*' in ir_text

    def test_stdlib_compress_target_filter(self):
        """std/compress extern 应按目标过滤"""
        source = 'from "./std/compress.ez" import { compressGzip };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, macos_libs = compile_source(source, compile_target='macos')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, android_libs = compile_source(source, compile_target='android')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'compress.c'), 'z']
        assert macos_libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'compress.c'), 'z']
        assert windows_libs == [str(STD_ROOT / 'native' / 'stream.c'), 'ws2_32', str(STD_ROOT / 'native' / 'compress.c'), 'z']
        assert android_libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'compress.c'), 'z']
        assert ios_libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'compress.c'), 'z']
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'stream.js'), str(STD_ROOT / 'emcc' / 'compress.js')]

    def test_stdlib_test_import(self):
        """std/test 测试框架导入"""
        source = '''
        from "./std/test.ez" import {
            testAssert, testEqualI64, testNotEqualI64, testEqualStr,
            testSkip, testThrows, testRegister, testRegisterParam, testCount, testName,
            testPassed, testFailed, testSkipped, testReset
        };

        const fail = (): Void => {
            throw Error(code = 7, message = "boom");
        };

        const check_test = (): I32 => {
            testReset();
            testRegister(name = "check_test");
            testRegisterParam(name = "case", param = "1");
            testAssert(condition = true, msg = "truth");
            testEqualI64(actual = 42, expected = 42, msg = "i64");
            testNotEqualI64(actual = 1, expected = 2, msg = "neq");
            testEqualStr(actual = "ez", expected = "ez", msg = "str");
            testThrows(body = fail, expectedCode = 7, msg = "throws");
            testSkip(msg = "later");
            const count = testCount();
            const name = testName(index = 1);
            const passed = testPassed();
            const failed = testFailed();
            const skipped = testSkipped();
            return passed;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'test.c')]
        for name in ['testAssert', 'testEqualI64', 'testNotEqualI64', 'testEqualStr', 'testSkip', 'testRegister', 'testRegisterParam', 'testCount', 'testName', 'testPassed', 'testFailed', 'testSkipped', 'testReset']:
            assert module.get_global(name) is not None
        assert module.get_global('testThrows') is not None

    def test_stdlib_test_target_filter(self):
        """std/test extern 应按目标过滤"""
        source = 'from "./std/test.ez" import { testAssert };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'test.c')]
        assert ios_libs == [str(STD_ROOT / 'native' / 'test.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'test.js')]

    def test_stdlib_stream_import(self):
        """std/stream 流 ABI 导入"""
        source = '''
        from "./std/stream.ez" import {
            streamKindMemory, streamKindFileRead, streamKindFileWrite, streamKindTcp,
            streamKindProcessStdin, streamKindProcessStdout, streamKindProcessStderr, Stream,
            streamFromBlob, streamFromTcpHandle, streamOpenFileRead, streamOpenFileWrite,
            streamRead, streamWrite, streamToBlob, streamCopy, streamFlush, streamClose
        };

        const check_stream = (): I64 => {
            const data = Blob(data = "hello", size = 5);
            const src = streamFromBlob(data = data);
            const tcp = streamFromTcpHandle(handle = 0);
            const dst = streamFromBlob(data = Blob(data = "", size = 0));
            const input = streamOpenFileRead(path = "input.bin");
            const output = streamOpenFileWrite(path = "output.bin");
            const first = streamRead(stream = src.value, maxBytes = 2);
            const written = streamWrite(stream = dst.value, data = first.value);
            const copied = streamCopy(dst = dst.value, src = src.value, bufferSize = 4);
            const out = streamToBlob(stream = dst.value);
            const flushed = streamFlush(stream = dst.value);
            const closed = streamClose(stream = dst.value);
            return copied;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'stream.c')]
        ir_text = str(module)
        assert '%"Stream" = type {i64, i32}' in ir_text
        for name in ['streamKindMemory', 'streamKindFileRead', 'streamKindFileWrite', 'streamKindTcp', 'streamKindProcessStdin', 'streamKindProcessStdout', 'streamKindProcessStderr']:
            assert module.get_global(name) is not None
        assert 'declare void @"streamFromBlob"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
        assert_small_struct_return_bridge(ir_text, 'streamFromTcpHandle', 'Stream', '{i64, i32}')
        assert 'declare void @"streamOpenFileRead"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
        assert 'declare void @"streamOpenFileWrite"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
        assert 'declare void @"streamRead"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
        for name in ['streamWrite', 'streamToBlob', 'streamCopy', 'streamFlush', 'streamClose']:
            assert module.get_global(name) is not None

    def test_stdlib_stream_target_filter(self):
        """std/stream extern 应按目标过滤"""
        source = 'from "./std/stream.ez" import { streamFromBlob };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'stream.c')]
        assert windows_libs == [str(STD_ROOT / 'native' / 'stream.c'), 'ws2_32']
        assert ios_libs == [str(STD_ROOT / 'native' / 'stream.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'stream.js')]

    def test_stdlib_time_import(self):
        """std/time 时间库导入"""
        source = '''
        from "./std/time.ez" import {
            Duration, durationToString,
            now, timestamp, sleep, getYear, getMonth, getDay, getHour, getMinute, getSecond,
            add, sub, format
        };

        const check_time = (): I32 => {
            const seconds = Duration.fromSec(s = 2);
            const minutes = Duration.fromMin(m = 1);
            const duration_text = seconds.toString();
            const duration_fn_text = durationToString(value = minutes);
            const d = now();
            const ts = timestamp();
            sleep(ms = 1);
            const y = getYear(this = #d);
            const y2 = d.getYear();
            const m = getMonth(this = #d);
            const day = getDay(this = #d);
            const hour = getHour(this = #d);
            const minute = getMinute(this = #d);
            const second = getSecond(this = #d);
            add(this = #d, year = 1, month = 1, day = 1, hour = 1, minute = 1, second = 1);
            sub(this = #d, year = 1, month = 1, day = 1, hour = 1, minute = 1, second = 1);
            d.add(year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);
            d.sub(year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);
            const s = format(this = #d, fmt = "yyyy-MM-dd");
            const s2 = d.format(fmt = "yyyy-MM-dd");
            return y;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'time.c')]
        for name in ['Duration_fromSec', 'Duration_fromMin', 'Duration_toString', 'durationToString', '__durationToString', 'now', 'timestamp', 'sleep', 'getYear', 'getMonth', 'getDay', 'getHour', 'getMinute', 'getSecond', 'add', 'sub', 'format']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'call %"Duration" @"Duration_fromSec"' in ir_text
        assert 'call %"Duration" @"Duration_fromMin"' in ir_text
        assert 'call i8* @"Duration_toString"' in ir_text
        assert 'call i8* @"durationToString"' in ir_text
        check_ir = function_ir(ir_text, 'check_time')
        assert 'call i32 @"getYear"' in check_ir
        assert 'call i32 @"dateGetYear"' in check_ir
        assert 'call void @"add"' in check_ir
        assert 'call void @"dateAdd"' in check_ir
        assert 'call void @"sub"' in check_ir
        assert 'call void @"dateSub"' in check_ir
        assert 'call i8* @"format"' in check_ir
        assert 'call i8* @"dateFormat"' in check_ir
        assert 'declare i8* @"__durationToString"' in ir_text

    def test_stdlib_time_target_filter(self):
        """std/time extern 应按桌面目标过滤"""
        source = 'from "./std/time.ez" import { timestamp };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'time.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'time.js')]

    def test_stdlib_collections_import(self):
        """std/collections 仅导入不应生成悬空外部符号"""
        source = '''
        from "./std/collections.ez" import {
            listPush, listPop, listShift, listUnshift, listSort, listFilter,
            listMap, listFind, listLen, listSlice,
            dictKeys, dictValues, dictHas, dictDelete, dictLen
        };
        '''
        module, errors, _ = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert 'listLen_' not in str(module)
        assert 'dictHas_' not in str(module)

    def test_stdlib_fmt_import(self):
        """std/fmt 格式化与编码导入"""
        source = '''
        from "./std/fmt.ez" import {
            toString, parseInt, parseI64, parseF64, format,
            b64Encode, b64Decode, jsonStringify, jsonParse,
            msgpackEncode, msgpackDecode, urlEncode, urlDecode
        };

        const check_fmt = (): I32? => {
            const i = parseInt(s = "42");
            const n = parseI64(s = "42");
            const f = parseF64(s = "3.14");
            const encoded = b64Encode(data = Blob());
            const decoded = b64Decode(s = encoded);
            const escaped = urlEncode(s = "a b");
            const raw = urlDecode(s = escaped);
            return i;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'fmt.c')]
        for name in ['parseInt', 'parseI64', 'parseF64', 'format', 'b64Encode', 'b64Decode', 'urlEncode', 'urlDecode']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert_optional_return_bridge(ir_text, 'parseInt', 'i32', 'x86_64')
        assert_optional_return_bridge(ir_text, 'parseI64', 'i64', 'x86_64')
        assert_optional_return_bridge(ir_text, 'parseF64', 'double', 'x86_64')
        assert_optional_return_bridge(ir_text, 'urlDecode', 'i8*', 'x86_64')

        aarch64_module, aarch64_errors, _ = compile_source(source, compile_target='linux', target_arch='aarch64')
        assert aarch64_module is not None
        assert len(aarch64_errors) == 0, f'编译错误: {aarch64_errors}'
        aarch64_ir = str(aarch64_module)
        assert_optional_return_bridge(aarch64_ir, 'parseI64', 'i64', 'aarch64')
        assert_optional_return_bridge(aarch64_ir, 'parseF64', 'double', 'aarch64')
        assert_optional_return_bridge(aarch64_ir, 'urlDecode', 'i8*', 'aarch64')

    def test_stdlib_fmt_generic_import(self):
        """std/fmt 泛型编码声明可导入"""
        source = '''
        from "./std/fmt.ez" import { toString, jsonStringify, jsonParse, msgpackEncode, msgpackDecode };

        const check_msgpack = (): Str => {
            const i8_text = toString<I8>(value = -128);
            const u8_text = toString<U8>(value = 255);
            const ji8 = jsonParse<I8>(s = jsonStringify<I8>(data = -128));
            const ju8 = jsonParse<U8>(s = jsonStringify<U8>(data = 255));
            const mi8 = msgpackDecode<I8>(data = msgpackEncode<I8>(data = ji8));
            const mu8 = msgpackDecode<U8>(data = msgpackEncode<U8>(data = ju8));
            const u32_text = toString<U32>(value = 4294967295);
            const u64_text = toString<U64>(value = 123456789);
            const ju32 = jsonParse<U32>(s = jsonStringify<U32>(data = 4294967295));
            const ju64 = jsonParse<U64>(s = jsonStringify<U64>(data = 123456789));
            const mu32 = msgpackDecode<U32>(data = msgpackEncode<U32>(data = ju32));
            const mu64 = msgpackDecode<U64>(data = msgpackEncode<U64>(data = ju64));
            const b = msgpackDecode<Bool>(data = msgpackEncode<Bool>(data = true));
            const s = msgpackDecode<Str>(data = msgpackEncode<Str>(data = "EzLang"));
            const jf = jsonParse<F32>(s = jsonStringify<F32>(data = 3.0));
            const mf = msgpackDecode<F32>(data = msgpackEncode<F32>(data = jf));
            const f = msgpackDecode<F64>(data = msgpackEncode<F64>(data = 3.0));
            return s;
        };
        '''
        module, errors, _ = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        for name in ['toString_I8', 'toString_U8', 'jsonStringify_I8', 'jsonParse_I8', 'jsonStringify_U8', 'jsonParse_U8', 'msgpackEncode_I8', 'msgpackDecode_I8', 'msgpackEncode_U8', 'msgpackDecode_U8', 'toString_U32', 'toString_U64', 'jsonStringify_U32', 'jsonParse_U32', 'jsonStringify_U64', 'jsonParse_U64', 'msgpackEncode_U32', 'msgpackDecode_U32', 'msgpackEncode_U64', 'msgpackDecode_U64', 'jsonStringify_F32', 'jsonParse_F32', 'msgpackEncode_I1', 'msgpackDecode_I1', 'msgpackEncode_Str', 'msgpackDecode_Str', 'msgpackEncode_F32', 'msgpackDecode_F32', 'msgpackEncode_F64', 'msgpackDecode_F64']:
            assert module.get_global(name) is not None

    def test_stdlib_fmt_json_stringify_struct_basic_fields(self):
        """jsonStringify<Struct> 对基础字段生成内部 JSON 编码函数。"""
        source = '''
        from "./std/fmt.ez" import { jsonStringify };

        struct User { name: Str; age: U32; active: Bool; score: F64; };
        struct Empty {};

        const encode = (): Str => {
            const u = User(name = "Ez", age = 42, active = true, score = 1.5);
            const empty = Empty();
            const ignored = jsonStringify<Empty>(data = empty);
            return jsonStringify<User>(data = u);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define i8* @"jsonStringify_User"(%"User"* %"data")' in ir_text
        assert 'define i8* @"jsonStringify_Empty"(%"Empty"* %"data")' in ir_text
        assert 'declare i8* @"jsonStringify_User"' not in ir_text
        start = ir_text.index('define i8* @"jsonStringify_User"')
        user_ir = ir_text[start:ir_text.index('\n}\n', start) + 3]
        for name in ['jsonStringify_Str', 'jsonStringify_U32', 'jsonStringify_I1', 'jsonStringify_F64']:
            assert name in user_ir

    def test_stdlib_fmt_json_stringify_struct_does_not_treat_blob_data_as_str(self):
        """Blob.data 是 *U8，不应因 LLVM 同为 i8* 被当作 Str 字段编码。"""
        source = '''
        from "./std/fmt.ez" import { jsonStringify };

        const encode = (): Str => {
            const b = Blob(data = "x", size = 1);
            return jsonStringify<Blob>(data = b);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define i8* @"jsonStringify_Blob"' not in ir_text
        assert 'declare i8* @"jsonStringify_Blob"(%"Blob"* %"data")' in ir_text

    def test_stdlib_fmt_json_parse_struct_basic_fields(self):
        """jsonParse<Struct> 对基础字段生成内部 JSON 解析函数。"""
        source = r'''
        from "./std/fmt.ez" import { jsonParse };

        struct User { name: Str; age: U32; active: Bool; score: F64; };
        struct Empty {};

        const decode = (): Str => {
            const u = jsonParse<User>(s = "{\"name\":\"Ez\",\"age\":42,\"active\":true,\"score\":1.5}");
            const empty = jsonParse<Empty>(s = "{}");
            return u.name;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define %"User"* @"jsonParse_User"(i8* %"s")' in ir_text
        assert 'define %"Empty"* @"jsonParse_Empty"(i8* %"s")' in ir_text
        assert 'declare %"User"* @"jsonParse_User"' not in ir_text
        user_ir = function_ir(ir_text, 'jsonParse_User')
        for name in ['__ez_json_valid_object', '__ez_json_object_field_count', '__ez_json_object_field']:
            assert name in user_ir
        for name in ['jsonParse_Str', 'jsonParse_U32', 'jsonParse_I1', 'jsonParse_F64']:
            assert name in user_ir

    def test_stdlib_fmt_json_parse_struct_does_not_treat_blob_data_as_str(self):
        """Blob.data 是 *U8，不应因 LLVM 同为 i8* 被当作 Str 字段解析。"""
        source = r'''
        from "./std/fmt.ez" import { jsonParse };

        const decode = (): Blob => {
            return jsonParse<Blob>(s = "{\"data\":\"x\",\"size\":1}");
        };
        '''
        module, errors, _ = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define %"Blob"* @"jsonParse_Blob"' not in ir_text
        assert_small_struct_return_bridge(ir_text, 'jsonParse_Blob', 'Blob', '{i8*, i64}')

    def test_stdlib_fmt_json_struct_nested_fields(self):
        """jsonStringify/jsonParse 支持字段为用户结构体的嵌套结构。"""
        source = r'''
        from "./std/fmt.ez" import { jsonStringify, jsonParse };

        struct Address { city: Str; zip: U32; };
        struct User { name: Str; address: Address; active: Bool; };

        const roundtrip = (): Str => {
            const user = User(name = "Ez", address = Address(city = "Shenzhen", zip = 518000), active = true);
            const json = jsonStringify<User>(data = user);
            const decoded = jsonParse<User>(s = json);
            return decoded.address.city;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define i8* @"jsonStringify_User"(%"User"* %"data")' in ir_text
        assert 'define i8* @"jsonStringify_Address"(%"Address"* %"data")' in ir_text
        assert 'define %"User"* @"jsonParse_User"(i8* %"s")' in ir_text
        assert 'define %"Address"* @"jsonParse_Address"(i8* %"s")' in ir_text
        user_encode = function_ir(ir_text, 'jsonStringify_User')
        user_decode = function_ir(ir_text, 'jsonParse_User')
        assert 'jsonStringify_Address' in user_encode
        assert 'jsonParse_Address' in user_decode
        assert 'declare i8* @"jsonStringify_Address"' not in ir_text
        assert 'declare %"Address"* @"jsonParse_Address"' not in ir_text

    def test_stdlib_fmt_json_and_msgpack_struct_list_fields(self):
        """JSON/MessagePack 支持结构体字段中的一层 List<T> / T[]。"""
        source = r'''
        from "./std/fmt.ez" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };

        struct Payload { nums: List<I32>; names: Str[]; };

        const roundtrip = (): I32 => {
            const payload = Payload(nums = [1, 2], names = ["a", "b"]);
            const json = jsonStringify<Payload>(data = payload);
            const parsed = jsonParse<Payload>(s = json);
            const packed = msgpackEncode<Payload>(data = parsed);
            const decoded = msgpackDecode<Payload>(data = packed);
            return decoded.nums[0];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        for name in [
            'jsonStringify_Payload',
            'jsonParse_Payload',
            'msgpackEncode_Payload',
            'msgpackDecode_Payload',
            'jsonStringify_List_I32',
            'jsonParse_List_I32',
            'msgpackEncode_List_I32',
            'msgpackDecode_List_I32',
            'jsonStringify_StrArray',
            'jsonParse_StrArray',
            'msgpackEncode_StrArray',
            'msgpackDecode_StrArray',
        ]:
            assert name in ir_text
        for helper in ['__ez_json_valid_array', '__ez_json_array_item', '__ez_msgpack_valid_array', '__ez_msgpack_array_item']:
            assert helper in ir_text

    def test_stdlib_fmt_json_and_msgpack_top_level_list(self):
        """JSON/MessagePack 泛型入口支持顶层一层 List<T> / T[]。"""
        source = r'''
        from "./std/fmt.ez" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };

        const roundtrip = (): I32 => {
            const nums: List<I32> = [1, 2];
            const json = jsonStringify<List<I32>>(data = nums);
            const parsed = jsonParse<List<I32>>(s = json);
            const packed = msgpackEncode<List<I32>>(data = parsed);
            const decoded = msgpackDecode<List<I32>>(data = packed);
            return decoded[0];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        for name in ['jsonStringify_List_I32', 'jsonParse_List_I32', 'msgpackEncode_List_I32', 'msgpackDecode_List_I32']:
            assert function_ir(ir_text, name).startswith('define ')
            assert re.search(rf'^declare\b.* @"{re.escape(name)}"\(', ir_text, re.MULTILINE) is None

    def test_stdlib_fmt_json_and_msgpack_nested_list(self):
        """JSON/MessagePack 泛型入口支持递归嵌套 List<T> / T[]。"""
        source = r'''
        from "./std/fmt.ez" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };

        const roundtrip = (): I32 => {
            const rows: List<List<I32>> = [[1, 2], [3, 4]];
            const json = jsonStringify<List<List<I32>>>(data = rows);
            const parsed = jsonParse<List<List<I32>>>(s = json);
            const packed = msgpackEncode<List<List<I32>>>(data = parsed);
            const decoded = msgpackDecode<List<List<I32>>>(data = packed);
            return decoded[1][0];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        for name in [
            'jsonStringify_List_List_I32',
            'jsonParse_List_List_I32',
            'msgpackEncode_List_List_I32',
            'msgpackDecode_List_List_I32',
            'jsonStringify_List_I32',
            'jsonParse_List_I32',
            'msgpackEncode_List_I32',
            'msgpackDecode_List_I32',
        ]:
            assert function_ir(ir_text, name).startswith('define ')
            assert re.search(rf'^declare\b.* @"{re.escape(name)}"\(', ir_text, re.MULTILINE) is None

    def test_stdlib_fmt_json_and_msgpack_struct_nested_list_fields(self):
        """JSON/MessagePack 支持结构体字段中的递归嵌套 List<T> / T[]。"""
        source = r'''
        from "./std/fmt.ez" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };

        struct Payload { rows: List<List<I32>>; };

        const roundtrip = (): I32 => {
            const payload = Payload(rows = [[1, 2], [3, 4]]);
            const json = jsonStringify<Payload>(data = payload);
            const parsed = jsonParse<Payload>(s = json);
            const packed = msgpackEncode<Payload>(data = parsed);
            const decoded = msgpackDecode<Payload>(data = packed);
            return decoded.rows[1][0];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        for name in [
            'jsonStringify_Payload',
            'jsonParse_Payload',
            'msgpackEncode_Payload',
            'msgpackDecode_Payload',
            'jsonStringify_List_List_I32',
            'jsonParse_List_List_I32',
            'msgpackEncode_List_List_I32',
            'msgpackDecode_List_List_I32',
            'jsonStringify_List_I32',
            'jsonParse_List_I32',
            'msgpackEncode_List_I32',
            'msgpackDecode_List_I32',
        ]:
            assert function_ir(ir_text, name).startswith('define ')
            assert re.search(rf'^declare\b.* @"{re.escape(name)}"\(', ir_text, re.MULTILINE) is None

    def test_stdlib_fmt_json_and_msgpack_optional(self):
        """JSON/MessagePack 支持 Optional<T> / T? 及其列表、结构体字段组合。"""
        source = r'''
        from "./std/fmt.ez" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };

        struct Payload { value: I32?; };

        const roundtrip = (): I32 => {
            const some: I32? = 42;
            let none: I32?;
            const json_some = jsonStringify<I32?>(data = some);
            const json_none = jsonStringify<I32?>(data = none);
            const parsed_some = jsonParse<I32?>(s = json_some);
            const parsed_none = jsonParse<I32?>(s = json_none);
            const decoded_some = msgpackDecode<I32?>(data = msgpackEncode<I32?>(data = parsed_some));
            const decoded_none = msgpackDecode<I32?>(data = msgpackEncode<I32?>(data = parsed_none));
            const payload = Payload(value = decoded_some);
            const payload_json = jsonStringify<Payload>(data = payload);
            const payload_parsed = jsonParse<Payload>(s = payload_json);
            const payload_decoded = msgpackDecode<Payload>(data = msgpackEncode<Payload>(data = payload_parsed));
            const list: List<I32?> = [decoded_some, decoded_none];
            const list_parsed = jsonParse<List<I32?>>(s = jsonStringify<List<I32?>>(data = list));
            const list_decoded = msgpackDecode<List<I32?>>(data = msgpackEncode<List<I32?>>(data = list));
            if payload_decoded.value.ok && list_parsed[0].ok && !list_parsed[1].ok && list_decoded[0].ok && !list_decoded[1].ok {
                return payload_decoded.value.value + list_parsed[0].value;
            }
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        for name in [
            'jsonStringify_I32Opt',
            'jsonParse_I32Opt',
            'msgpackEncode_I32Opt',
            'msgpackDecode_I32Opt',
            'jsonStringify_Payload',
            'jsonParse_Payload',
            'msgpackEncode_Payload',
            'msgpackDecode_Payload',
            'jsonStringify_List_I32Opt',
            'jsonParse_List_I32Opt',
            'msgpackEncode_List_I32Opt',
            'msgpackDecode_List_I32Opt',
        ]:
            assert function_ir(ir_text, name).startswith('define ')
            assert re.search(rf'^declare\b.* @"{re.escape(name)}"\(', ir_text, re.MULTILINE) is None
        for helper in ['__ez_json_valid_null', '__ez_json_valid_value', '__ez_msgpack_valid_nil', '__ez_msgpack_valid_value']:
            assert helper in ir_text

    def test_stdlib_fmt_json_and_msgpack_dict_str_keys(self):
        """JSON/MessagePack 支持 Dict<Str, T>，T 可递归使用已支持的值类型。"""
        source = r'''
        from "./std/fmt.ez" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };

        const roundtrip = (): I32 => {
            const scores: Dict<Str, I32> = { a: I32 = 1, b: I32 = 2 };
            const score_json = jsonStringify<Dict<Str, I32>>(data = scores);
            const score_parsed = jsonParse<Dict<Str, I32>>(s = score_json);
            const score_decoded = msgpackDecode<Dict<Str, I32>>(data = msgpackEncode<Dict<Str, I32>>(data = score_parsed));
            const groups: Dict<Str, List<I32>> = { nums: List<I32> = [3, 4] };
            const group_decoded = msgpackDecode<Dict<Str, List<I32>>>(data = msgpackEncode<Dict<Str, List<I32>>>(data = jsonParse<Dict<Str, List<I32>>>(s = jsonStringify<Dict<Str, List<I32>>>(data = groups))));
            return score_decoded["a"] + group_decoded["nums"][1];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        for name in [
            'jsonStringify_Dict_Str_I32',
            'jsonParse_Dict_Str_I32',
            'msgpackEncode_Dict_Str_I32',
            'msgpackDecode_Dict_Str_I32',
            'jsonStringify_Dict_Str_List_I32',
            'jsonParse_Dict_Str_List_I32',
            'msgpackEncode_Dict_Str_List_I32',
            'msgpackDecode_Dict_Str_List_I32',
        ]:
            assert function_ir(ir_text, name).startswith('define ')
            assert re.search(rf'^declare\b.* @"{re.escape(name)}"\(', ir_text, re.MULTILINE) is None

    def test_stdlib_fmt_json_and_msgpack_dict_non_str_keys(self):
        """JSON/MessagePack 支持非字符串键 Dict<K, V>，JSON 使用 key/value 条目数组。"""
        source = r'''
        from "./std/fmt.ez" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };

        const roundtrip = (): I32 => {
            const scores: Dict<I32, Str> = { [1]: Str = "one", [2]: Str = "two" };
            const score_json = jsonStringify<Dict<I32, Str>>(data = scores);
            const score_parsed = jsonParse<Dict<I32, Str>>(s = score_json);
            const score_decoded = msgpackDecode<Dict<I32, Str>>(data = msgpackEncode<Dict<I32, Str>>(data = score_parsed));
            return 1;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        for name in [
            'jsonStringify_Dict_I32_Str',
            'jsonParse_Dict_I32_Str',
            'msgpackEncode_Dict_I32_Str',
            'msgpackDecode_Dict_I32_Str',
        ]:
            assert function_ir(ir_text, name).startswith('define ')
            assert re.search(rf'^declare\b.* @"{re.escape(name)}"\(', ir_text, re.MULTILINE) is None

    def test_stdlib_fmt_dict_rejects_complex_key_types(self):
        """复杂 Dict 键没有稳定值比较语义时，不生成 fmt 单态化实现。"""
        source = r'''
        from "./std/fmt.ez" import { jsonStringify };

        const render = (scores: Dict<List<I32>, Str>): Str => {
            return jsonStringify<Dict<List<I32>, Str>>(data = scores);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert re.search(r'^declare\b.* @"jsonStringify_Dict_List_I32_Str"\(', ir_text, re.MULTILINE) is not None
        assert re.search(r'^define\b.* @"jsonStringify_Dict_List_I32_Str"\(', ir_text, re.MULTILINE) is None

    def test_stdlib_fmt_json_and_msgpack_union(self):
        """JSON/MessagePack 支持 Union，编码为 tag/value 对象或 map。"""
        source = r'''
        from "./std/fmt.ez" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };

        struct Payload { value: I32 | Str; };

        const roundtrip = (): I32 => {
            const number: I32 | Str = 42;
            const text: I32 | Str = "ez";
            const number_json = jsonStringify<I32 | Str>(data = number);
            const text_parsed = jsonParse<I32 | Str>(s = "{\"tag\":1,\"value\":\"ok\"}");
            const text_decoded = msgpackDecode<I32 | Str>(data = msgpackEncode<I32 | Str>(data = text));
            const payload = Payload(value = text_parsed);
            const payload_decoded = msgpackDecode<Payload>(data = msgpackEncode<Payload>(data = jsonParse<Payload>(s = jsonStringify<Payload>(data = payload))));
            const list: List<I32 | Str> = [number, text_decoded];
            const list_decoded = msgpackDecode<List<I32 | Str>>(data = msgpackEncode<List<I32 | Str>>(data = jsonParse<List<I32 | Str>>(s = jsonStringify<List<I32 | Str>>(data = list))));
            const number_roundtrip = jsonStringify<I32 | Str>(data = jsonParse<I32 | Str>(s = number_json));
            if payload_decoded.value.tag == 1 && list_decoded[0].tag == 0 && list_decoded[1].tag == 1 && number_roundtrip == number_json {
                return 42;
            }
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        for name in [
            'jsonStringify_I32_Str',
            'jsonParse_I32_Str',
            'msgpackEncode_I32_Str',
            'msgpackDecode_I32_Str',
            'jsonStringify_Payload',
            'jsonParse_Payload',
            'msgpackEncode_Payload',
            'msgpackDecode_Payload',
            'jsonStringify_List_I32_Str',
            'jsonParse_List_I32_Str',
            'msgpackEncode_List_I32_Str',
            'msgpackDecode_List_I32_Str',
        ]:
            assert function_ir(ir_text, name).startswith('define ')
            assert re.search(rf'^declare\b.* @"{re.escape(name)}"\(', ir_text, re.MULTILINE) is None
        for helper in [
            '__ez_json_object_field',
            '__ez_json_object_field_count',
            '__ez_msgpack_map_field',
            '__ez_msgpack_map_field_count',
        ]:
            assert helper in ir_text

    def test_stdlib_fmt_msgpack_struct_basic_fields(self):
        """msgpackEncode/Decode<Struct> 对基础字段生成内部 map 编解码函数。"""
        source = '''
        from "./std/fmt.ez" import { msgpackEncode, msgpackDecode };

        struct User { name: Str; age: U32; active: Bool; score: F64; };
        struct Empty {};

        const roundtrip = (): Str => {
            const u = User(name = "Ez", age = 42, active = true, score = 1.5);
            const packed = msgpackEncode<User>(data = u);
            const decoded = msgpackDecode<User>(data = packed);
            const ignored = msgpackDecode<Empty>(data = msgpackEncode<Empty>(data = Empty()));
            return decoded.name;
        };
        '''
        module, errors, _ = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define %"Blob" @"msgpackEncode_User"(%"User"* %"data")' in ir_text
        assert 'define %"User"* @"msgpackDecode_User"(%"Blob"* %"data")' in ir_text
        assert 'define %"Blob" @"msgpackEncode_Empty"(%"Empty"* %"data")' in ir_text
        assert 'define %"Empty"* @"msgpackDecode_Empty"(%"Blob"* %"data")' in ir_text
        encode_ir = function_ir(ir_text, 'msgpackEncode_User')
        decode_ir = function_ir(ir_text, 'msgpackDecode_User')
        for name in ['__ez_msgpack_encode_map', 'msgpackEncode_Str', 'msgpackEncode_U32', 'msgpackEncode_I1', 'msgpackEncode_F64']:
            assert name in encode_ir
        for name in ['__ez_msgpack_valid_map', '__ez_msgpack_map_field_count', '__ez_msgpack_map_field']:
            assert name in decode_ir
        for name in ['msgpackDecode_Str', 'msgpackDecode_U32', 'msgpackDecode_I1', 'msgpackDecode_F64']:
            assert name in decode_ir

    def test_stdlib_fmt_msgpack_struct_does_not_treat_blob_data_as_str(self):
        """Blob.data 是 *U8，不应因 LLVM 同为 i8* 被当作 Str 字段编解码。"""
        source = '''
        from "./std/fmt.ez" import { msgpackEncode, msgpackDecode };

        const encode = (): Blob => {
            const b = Blob(data = "x", size = 1);
            return msgpackEncode<Blob>(data = b);
        };

        const decode = (data: Blob): Blob => {
            return msgpackDecode<Blob>(data = data);
        };
        '''
        module, errors, _ = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define %"Blob" @"msgpackEncode_Blob"' not in ir_text
        assert 'define %"Blob"* @"msgpackDecode_Blob"' not in ir_text
        assert_small_struct_return_bridge(ir_text, 'msgpackEncode_Blob', 'Blob', '{i8*, i64}')
        assert_small_struct_return_bridge(ir_text, 'msgpackDecode_Blob', 'Blob', '{i8*, i64}')

    def test_stdlib_fmt_msgpack_struct_nested_fields(self):
        """msgpackEncode/msgpackDecode 支持字段为用户结构体的嵌套结构。"""
        source = '''
        from "./std/fmt.ez" import { msgpackEncode, msgpackDecode };

        struct Address { city: Str; zip: U32; };
        struct User { name: Str; address: Address; active: Bool; };

        const roundtrip = (): Str => {
            const user = User(name = "Ez", address = Address(city = "Shenzhen", zip = 518000), active = true);
            const packed = msgpackEncode<User>(data = user);
            const decoded = msgpackDecode<User>(data = packed);
            return decoded.address.city;
        };
        '''
        module, errors, _ = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'define %"Blob" @"msgpackEncode_User"(%"User"* %"data")' in ir_text
        assert 'define %"Blob" @"msgpackEncode_Address"(%"Address"* %"data")' in ir_text
        assert 'define %"User"* @"msgpackDecode_User"(%"Blob"* %"data")' in ir_text
        assert 'define %"Address"* @"msgpackDecode_Address"(%"Blob"* %"data")' in ir_text
        user_encode = function_ir(ir_text, 'msgpackEncode_User')
        user_decode = function_ir(ir_text, 'msgpackDecode_User')
        assert 'msgpackEncode_Address' in user_encode
        assert 'msgpackDecode_Address' in user_decode
        assert 'declare %"Blob" @"msgpackEncode_Address"' not in ir_text
        assert 'declare %"Address"* @"msgpackDecode_Address"' not in ir_text

    def test_stdlib_fmt_emcc_to_string_f32_and_bool_declare_wrappers(self):
        """emcc 平台的 toString<F32/Bool> 应有对应 JS 封装符号。"""
        source = '''
        from "./std/fmt.ez" import { toString };
        let text = toString<F32>(value = 3.5);
        let flag = toString<Bool>(value = true);
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'emcc' / 'fmt.js')]
        assert module.get_global('toString_F32') is not None
        assert module.get_global('toString_I1') is not None

    def test_stdlib_net_http_import(self):
        """std/net/http 导入"""
        source = '''
        from "./std/net/http.ez" import { Headers, HttpRequest, HttpResponse, fetch, fetchEx };

        const call_http = (): Str => {
            const headers = { accept: Str = "application/json" };
            const req = HttpRequest(method = "GET", url = "https://example.com", headers = headers, body = ?);
            const via_req = fetchEx(req = req);
            const resp = fetch(url = "https://example.com");
            return resp.ok ? resp.value.text() : "";
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'http.c'), 'pthread', 'dl']
        assert module.get_global('fetch') is not None
        assert module.get_global('fetchEx') is not None
        assert module.get_global('HttpResponse_text') is not None
        ir_text = str(module)
        assert 'HttpRequest' in ir_text
        assert '%"HttpRequest" = type {i8*, i8*, %"Dict", {i1, %"Blob"}}' in ir_text
        assert 'HttpResponse' in ir_text
        assert 'sret({i1, %"HttpResponse"})' in ir_text
        assert 'call i8* @"HttpResponse_text"' in ir_text

    def test_stdlib_net_http_target_filter(self):
        """std/net/http extern 应按目标过滤"""
        source = 'from "./std/net/http.ez" import { fetch };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, android_libs = compile_source(source, compile_target='android')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'net' / 'http.c'), 'pthread', 'dl']
        assert windows_libs == [str(STD_ROOT / 'native' / 'net' / 'http.c'), 'ws2_32']
        assert android_libs == [str(STD_ROOT / 'native' / 'net' / 'http.c'), 'pthread']
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'net' / 'http.js')]

    def test_stdlib_net_http_server_import(self):
        """std/net/http 服务端 API 导入"""
        source = '''
        from "./std/net/http.ez" import { RouteHandler, HttpServer, createServer };

        const make_server = (): HttpServer => {
            const server = createServer(host = "0.0.0.0", port = 8080);
            return server;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'http.c'), 'pthread', 'dl']
        assert module.get_global('createServer') is not None
        assert 'HttpServer' in str(module)

    def test_stdlib_net_tcp_udp_import(self):
        """std/net TCP/UDP API 导入"""
        source = '''
        from "./std/net/tcp.ez" import {
            TcpConn, TcpListener, UdpSocket, UdpPacket, tcpConnect, tcpListen, tcpAccept,
            tcpRead, tcpWrite, tcpClose, tcpListenerClose, udpBind, udpSend,
            udpRecvFrom, udpRecv, udpClose
        };

        const open_tcp = (): TcpConn? => {
            return tcpConnect(host = "127.0.0.1", port = 80);
        };

        const open_listener = (): TcpListener? => {
            return tcpListen(host = "127.0.0.1", port = 8080);
        };

        const open_udp = (): UdpSocket? => {
            return udpBind(host = "127.0.0.1", port = 5353);
        };

        const use_tcp = (conn: TcpConn, listener: TcpListener): I64 => {
            const accepted = tcpAccept(listener = listener);
            const chunk = tcpRead(conn = conn, maxBytes = 16);
            const written = tcpWrite(conn = conn, data = Blob(data = "ping", size = 4));
            const closed_conn = tcpClose(conn = conn);
            const closed_listener = tcpListenerClose(listener = listener);
            return written;
        };

        const use_udp = (socket: UdpSocket): I64 => {
            const sent = udpSend(socket = socket, host = "127.0.0.1", port = 5353, data = Blob(data = "u", size = 1));
            const packet = udpRecvFrom(socket = socket, maxBytes = 16);
            const received = udpRecv(socket = socket, maxBytes = 16);
            const closed = udpClose(socket = socket);
            return sent;
        };

        const packet_port = (packet: UdpPacket): I32 => {
            return packet.port;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'tcp.c'), 'dl']
        for name in [
            'tcpConnect', 'tcpListen', 'tcpAccept', 'tcpRead', 'tcpWrite', 'tcpClose',
            'tcpListenerClose', 'udpBind', 'udpSend', 'udpRecvFrom', 'udpRecv', 'udpClose'
        ]:
            assert module.get_global(name) is not None
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'TcpConn' in ir_text
        assert 'TcpListener' in ir_text
        assert 'UdpSocket' in ir_text
        assert 'UdpPacket' in ir_text
        assert 'sret({i1, %"UdpPacket"})' in ir_text
        assert 'sret({i1, %"Blob"})' in ir_text

    def test_stdlib_net_tcp_stream_uses_std_stream_abi(self):
        """TCP 连接可交给 std/stream 通用函数。"""
        source = '''
        from "./std/stream.ez" import { Stream, streamFromTcpHandle, streamRead, streamWrite, streamClose };
        from "./std/net/tcp.ez" import { TcpConn };

        const use_tcp_stream = (conn: TcpConn): I64 => {
            const stream = streamFromTcpHandle(handle = conn.handle);
            const written = streamWrite(stream = stream, data = Blob(data = "ping", size = 4));
            const chunk = streamRead(stream = stream, maxBytes = 4);
            const closed = streamClose(stream = stream);
            return written;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'net' / 'tcp.c'), 'dl']
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '%"Stream" = type {i64, i32}' in ir_text
        assert module.get_global('streamFromTcpHandle') is not None
        assert module.get_global('streamRead') is not None

        _, windows_errors, windows_libs = compile_source(source, compile_target='windows')
        assert len(windows_errors) == 0, f'编译错误: {windows_errors}'
        assert windows_libs == [str(STD_ROOT / 'native' / 'stream.c'), 'ws2_32', str(STD_ROOT / 'native' / 'net' / 'tcp.c')]

    def test_stdlib_net_tcp_udp_target_filter(self):
        """std/net TCP/UDP extern 应按目标过滤"""
        source = 'from "./std/net/tcp.ez" import { tcpConnect, udpBind };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'net' / 'tcp.c'), 'dl']
        assert windows_libs == [str(STD_ROOT / 'native' / 'net' / 'tcp.c'), 'ws2_32']
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'net' / 'tcp.js')]

    def test_stdlib_net_ws_import(self):
        """std/net WebSocket API 导入"""
        source = '''
        from "./std/net/ws.ez" import { WsConn, wsConnect, wsSend, wsRecv, wsClose };

        const connect_ws = (): WsConn? => {
            return wsConnect(url = "wss://example.com/socket");
        };

        const use_ws = (conn: WsConn): I64 => {
            const sent = wsSend(conn = conn, data = Blob(data = "ping", size = 4));
            const chunk = wsRecv(conn = conn, maxBytes = 16);
            const closed = wsClose(conn = conn);
            return sent;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'ws.c'), 'dl']
        for name in ['wsConnect', 'wsSend', 'wsRecv', 'wsClose']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'WsConn' in ir_text
        assert 'sret({i1, %"Blob"})' in ir_text

    def test_stdlib_net_ws_target_filter(self):
        """std/net WebSocket extern 应按目标过滤"""
        source = 'from "./std/net/ws.ez" import { wsConnect };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'net' / 'ws.c'), 'dl']
        assert windows_libs == [str(STD_ROOT / 'native' / 'net' / 'ws.c'), 'ws2_32', 'bcrypt']
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'net' / 'ws.js')]

    # ==================== 泛型 declare 单态化测试 ====================

    def test_generic_declare_simple(self):
        """泛型 declare: <T>(this: #List<T>, item: T) => Void"""
        source = '''
        declare const listPush: <T>(this: #List<T>, item: T) => Void;
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0
        ir_text = str(module)
        # 泛型 declare 仅注册模板，不生成 LLVM 函数（调用时单态化）

    def test_generic_declare_multi_param(self):
        """泛型 declare: <K, V>(this: #Dict<K, V>, key: K) => Bool — 多参数模板注册"""
        source = '''
        declare const dictHas: <K, V>(this: #Dict<K, V>, key: K) => Bool;
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0

    def test_stdlib_collections_basic_list_builtins(self):
        """std/collections 基础 List 函数应由编译器内建 lowering"""
        source = '''
        from "./std/collections.ez" import {
            listLen, listPush, listPop, listShift, listUnshift, listSlice
        };

        const test_list = (): I64 => {
            let nums: List<I32> = [1, 2, 3];
            listPush<I32>(this = #nums, item = 4);
            listUnshift<I32>(this = #nums, item = 0);
            const tail = listPop<I32>(this = #nums);
            const head = listShift<I32>(this = #nums);
            let part: List<I32> = listSlice<I32>(this = #nums, start = 0, end = 2);
            return listLen<I32>(this = #part);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        for name in ['listLen_I32', 'listPush_I32', 'listPop_I32', 'listShift_I32', 'listUnshift_I32', 'listSlice_I32']:
            assert name not in ir_text
        assert 'list_grow' in ir_text
        assert 'list_slice_cond' in ir_text

    def test_stdlib_collections_higher_order_and_dict_builtins(self):
        """高阶 List 与 Dict 函数应由编译器内建 lowering"""
        source = '''
        from "./std/collections.ez" import {
            listSort, listFilter, listMap, listFind, listLen,
            dictKeys, dictValues, dictHas, dictDelete, dictLen
        };

        const pred = (item: I32): Bool => {
            return item > 1;
        };

        const mapper = (item: I32): I64 => {
            return item;
        };

        const cmp = (a: I32, b: I32): I32 => {
            return a - b;
        };

        const test_list = (): I64 => {
            let nums: List<I32> = [3, 1, 2];
            listSort<I32>(this = #nums, cmp = cmp);
            let found = listFind<I32>(this = #nums, pred = pred);
            let filtered: List<I32> = listFilter<I32>(this = #nums, pred = pred);
            let mapped: List<I64> = listMap<I32, I64>(this = #filtered, f = mapper);
            return listLen<I64>(this = #mapped);
        };

        const test_dict = (): I64 => {
            let meta = { name: Str = "ez", lang: Str = "EzLang" };
            let has_name = dictHas<Str, Str>(this = #meta, key = "name");
            let keys: List<Str> = dictKeys<Str, Str>(this = #meta);
            let values: List<Str> = dictValues<Str, Str>(this = #meta);
            let removed = dictDelete<Str, Str>(this = #meta, key = "name");
            return dictLen<Str, Str>(this = #meta);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        for name in ['listFind_I32', 'listFilter_I32', 'listMap_I32_I64', 'listSort_I32', 'dictHas_Str_Str', 'dictDelete_Str_Str', 'dictKeys_Str_Str', 'dictValues_Str_Str', 'dictLen_Str_Str']:
            assert name not in ir_text
        assert 'list_find_cond' in ir_text
        assert 'list_filter_cond' in ir_text
        assert 'list_map_cond' in ir_text
        assert 'list_sort_outer_cond' in ir_text
        assert 'dict_find_cond' in ir_text
        assert 'dict_list_cond' in ir_text

    def test_stdlib_collections_object_methods(self):
        """List/Dict 标准库函数支持对象方法糖调用"""
        source = '''
        from "./std/collections.ez" import {
            listMap
        };

        const pred = (item: I32): Bool => {
            return item > 1;
        };

        const mapper = (item: I32): I64 => {
            return item;
        };

        const test_list = (): I64 => {
            let nums: List<I32> = [3, 1, 2];
            nums.push(item = 4);
            nums.unshift(item = 0);
            const tail = nums.pop();
            const head = nums.shift();
            let part: List<I32> = nums.slice(start = 0, end = 2);
            let filtered: List<I32> = part.filter(pred = pred);
            let mapped: List<I64> = filtered.map(f = mapper);
            return mapped.len();
        };

        const test_dict = (): I64 => {
            let meta = { name: Str = "ez", lang: Str = "EzLang" };
            let has_name = meta.has(key = "name");
            let keys: List<Str> = meta.keys();
            let values: List<Str> = meta.values();
            let removed = meta.delete(key = "name");
            return meta.len();
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'list_map_cond' in ir_text
        assert 'dict_find_cond' in ir_text

    # ==================== Arena 分配器测试 ====================

    def test_arena_infrastructure(self):
        """Arena 基础设施应始终生成：buffer + cursor + alloc + save + restore"""
        module, errors, _ = compile_source('')
        assert module is not None
        ir_text = str(module)
        assert '__arena_buffer' in ir_text
        assert '__arena_capacity' in ir_text
        assert '__arena_cursor' in ir_text
        assert '__arena_alloc' in ir_text
        assert '__arena_save' in ir_text
        assert '__arena_restore' in ir_text

    def test_arena_uses_thread_local_expandable_storage(self):
        """Arena 状态应是线程本地的，并在容量不足时通过 realloc 扩容。"""
        module, errors, _ = compile_source('let x: I32 = 42;')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '@"__arena_buffer" = internal thread_local global i8* null' in ir_text
        assert '@"__arena_capacity" = internal thread_local global i64 0' in ir_text
        assert '@"__arena_cursor" = internal thread_local global i64 0' in ir_text
        assert 'declare i8* @"realloc"(i8* %".1", i64 %".2")' in ir_text
        assert 'call i8* @"realloc"' in ir_text
        assert 'call void @"llvm.trap"()' in ir_text

    def test_arena_alloc_is_function(self):
        """__arena_alloc 应为 LLVM 函数"""
        module, errors, _ = compile_source('let x: I32 = 42;')
        assert module is not None
        func = module.get_global('__arena_alloc')
        assert func is not None
        assert isinstance(func, ir.Function)
        # 应有两个参数: size, align
        assert len(func.args) == 2

    def test_arena_block_save_restore_ir(self):
        """块作用域应保存并恢复 Arena 游标"""
        source = '''
        struct Data { val: I32; };
        const run = () => {
            {
                let d = Data(val = 1);
            }
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'call i64 @"__arena_save"()' in ir_text
        assert 'call void @"__arena_restore"' in ir_text

    def test_arena_restore_before_early_return_ir(self):
        """块内提前 return 前应恢复当前 Arena 游标。"""
        source = '''
        struct Data { val: I32; };
        const run = (): I32 => {
            {
                let d = Data(val = 1);
                return d.val;
            }
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        run_ir = ir_text[ir_text.find('define i32 @"run"'):]
        restore_idx = run_ir.find('call void @"__arena_restore"')
        ret_idx = run_ir.find('ret i32')
        assert restore_idx != -1
        assert ret_idx != -1
        assert restore_idx < ret_idx

    def test_arena_return_aggregate_by_value_ir(self):
        """返回 Arena 聚合值前应 load 成值语义返回"""
        source = '''
        struct Data { val: I32; };
        const create = (): Data => {
            let d = Data(val = 42);
            return d;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'define %"Data" @"create"()' in ir_text
        assert 'load %"Data"' in ir_text

    def test_arena_allocation_uses_alignment_ir(self):
        """Arena 分配应传入对齐参数"""
        source = '''
        struct Data { val: I32; };
        const run = () => {
            let d = Data(val = 1);
            return d.val;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert '@"__arena_alloc"(i64 4, i64 8)' in str(module)

    def test_arena_example_codegen(self):
        """arena.ez 应通过代码生成"""
        source = (Path(__file__).parent.parent.parent / 'examples' / 'arena.ez').read_text()
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'

    # ==================== 结构体字段默认值 ====================

    def test_struct_field_defaults(self):
        """结构体字段默认值：省略有默认值的字段时自动填充"""
        source = '''
        struct Config {
            debug: Bool = true;
            max: I32 = 100;
            name: Str = "default";
        };
        const c = Config(name = "myapp");
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        # Config 应有 3 个字段
        # 验证 Config 作为 identified type 存在
        ir_text = str(module)
        assert 'Config' in ir_text

    def test_struct_instance_spread_ir(self):
        """结构体实例展开应按字段名复制可兼容字段"""
        source = '''
        struct Point { x: I32; y: I32 = 0; };
        struct Point3D { ...Point; z: I32; };
        const run = () => {
            let p = Point(x = 1, y = 2);
            let p2 = Point(...p, y = 3);
            let p3 = Point3D(...p, z = 4);
            return p3.x;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'Point3D' in ir_text
        assert 'getelementptr' in ir_text

    def test_struct_field_defaults_ir(self):
        """结构体字段默认值应出现在生成的 IR 中"""
        source = '''
        struct Point {
            x: I32 = 10;
            y: I32 = 20;
        };
        const run = () => {
            let p = Point(y = 5);
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        ir_text = str(module)
        # 默认值 x=10 应作为常量出现在 IR 中
        assert '10' in ir_text

    # ==================== extern 库路径测试 ====================

    def test_extern_lib_collection(self):
        """extern 声明应被收集到 extern_libs 列表"""
        source = '''
        extern "libc" for linux;
        extern "libc" for macos;
        extern "libcurl" for linux;
        '''
        module, errors, libs = compile_source(source)
        assert module is not None
        assert len(libs) == 3
        assert ('libc', 'linux') in libs
        assert ('libc', 'macos') in libs
        assert ('libcurl', 'linux') in libs

    def test_extern_no_target(self):
        """extern 无 for target 子句时 target 为 None"""
        source = 'extern "libc";'
        module, errors, libs = compile_source(source)
        assert len(libs) == 1
        assert libs[0] == ('libc', None)

    def test_extern_target_filter_codegen(self):
        """extern 应按编译目标过滤链接输入"""
        source = '''
        extern "liball.a";
        extern "liblinux.so" for linux;
        extern "libwin.lib" for windows;
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert libs == ['liball.a', 'liblinux.so']

    def test_extern_supported_formats_codegen(self):
        """extern 应记录所有支持的外部链接格式"""
        source = '''
        extern "liba.a";
        extern "libso.so";
        extern "libdyn.dylib";
        extern "win.lib";
        extern "obj.o";
        extern "ir.ll";
        extern "bitcode.bc";
        extern "Apple.framework";
        extern "bindings.js" for emcc;
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert libs == ['liba.a', 'libso.so', 'libdyn.dylib', 'win.lib', 'obj.o', 'ir.ll', 'bitcode.bc', 'Apple.framework', 'bindings.js']

    def test_declare_without_extern_codegen_warning(self):
        """declare 无 extern 关联时生成链接诊断"""
        module, errors, libs = compile_source('declare const native_add: () => I32;')
        assert module is not None
        assert any('没有关联 extern 库' in e for e in errors)

    def test_declare_with_extern_codegen_no_warning(self):
        """declare 有 extern 关联时不产生链接诊断"""
        source = '''
        extern "libnative.a";
        declare const native_add: () => I32;
        '''
        module, errors, libs = compile_source(source)
        assert module is not None
        assert not any('没有关联 extern 库' in e for e in errors)

    def test_emcc_js_binding_generation(self):
        """emcc 目标下 JS extern 应生成绑定元数据"""
        source = '''
        extern "bindings.js" for emcc;
        declare const console_log: (msg: Str) => Void;
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0
        assert libs == ['bindings.js']
        ir_text = str(module)
        assert '@"__emcc_js_binding_0"' in ir_text
        assert 'bindings.js' in ir_text
        assert 'console_log' in ir_text

    # ==================== Dict 内置类型测试 ====================

    def test_dict_type_exists(self):
        """Dict 应为内置结构体类型"""
        source = '''
        const d = Dict();
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        ir_text = str(module)
        assert 'Dict' in ir_text
        assert 'i8***' in ir_text

    def test_dict_create_and_set(self):
        """Dict 创建和 dict_set 操作（Blob 类型参数）"""
        source = '''
        declare const dict_set: (dict: Dict, key: Blob, val: Blob) => Void;
        const test = () => {
            let d = Dict();
            let k = Blob(data = "name", size = 4);
            let v = Blob(data = "EzLang", size = 6);
            dict_set(dict = d, key = k, val = v);
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'dict_grow' in ir_text
        assert 'dict_insert' in ir_text

    def test_dict_literal_uses_builtin_dict_pages(self):
        """字典字面量应使用 Dict 分页结构"""
        source = '''
        const test = () => {
            let d = { name = "EzLang", lang = "ez" };
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert 'Dict' in ir_text
        assert 'dict_grow' in ir_text
        assert '_dict_key' in ir_text

    def test_dict_get(self):
        """Dict 创建和 dict_get 操作（Blob 类型参数）"""
        source = '''
        declare const dict_get: (dict: Dict, key: Blob) => Blob;
        const test = () => {
            let d = Dict();
            let k = Blob(data = "name", size = 4);
            let val = dict_get(dict = d, key = k);
            return 0;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'

    def test_dict_index_lookup_uses_requested_key(self):
        """Dict 索引读取应生成按 key 扫描逻辑。"""
        source = '''
        const test = (): Str => {
            let d = { name = "EzLang", lang = "ez" };
            return d["lang"];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'dict_find_cond' in ir_text
        assert 'dict_lookup_value_val' in ir_text

    def test_dict_index_assignment_upserts_key(self):
        """Dict 索引赋值应更新已有 key，缺失时插入新 key。"""
        source = '''
        const test = (): Str => {
            let d = { name = "old" };
            d["name"] = "new";
            d["lang"] = "EzLang";
            return d["lang"];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'dict_upsert_update' in ir_text
        assert 'dict_upsert_insert' in ir_text

    def test_dynamic_dict_shape_annotation_keeps_codegen_key_type(self):
        """动态键类型结构注解应传给 Dict 索引 codegen。"""
        source = '''
        const test = (): Str => {
            let d: { [key: I32]: Str } = { [1] = "one" };
            d[2] = "two";
            return d[2];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'dict_find_cond' in ir_text
        assert 'dict_upsert_insert' in ir_text

    def test_shape_dict_literal_codegen_uses_named_fields(self):
        """Shape 注解的对象字面量应按字段名写入结构体字段。"""
        source = '''
        type Shape = { name: Str; side: Str; };
        const test = (): Str => {
            let s: Shape = { side = "10"; name = "Square" };
            return s.name;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '%"Shape" = type {i8*, i8*}' in ir_text
        assert '_tmp_shape' in ir_text

    def test_mixed_dynamic_shape_literal_codegen_keeps_dict_types(self):
        """混合固定字段和动态键的 Shape 应按 Dict 键值类型生成。"""
        source = '''
        type Shape = { name: Str; [dynamic: Str]: Str; };
        const test = (): Str => {
            let s: Shape = { name = "Square"; side = "10" };
            return s["side"];
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'dict_find_cond' in ir_text
        assert 'dict_lookup_value_val' in ir_text

    def test_type_shape_spread_codegen_flattens_layout(self):
        """type Shape 的 `...Base` 扩展应展平成目标结构体布局。"""
        source = '''
        type Named = { name: Str; };
        type UserShape = { ...Named; age: I32; };
        const test = (): I32 => {
            let u: UserShape = { name = "s"; age = 42 };
            return u.age;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '%"UserShape" = type {i8*, i32}' in ir_text
        assert '_tmp_shape' in ir_text

    def test_p0_documented_syntax_codegen(self):
        """P0 文档语法应能生成 IR 或明确占位 ABI"""
        source = '''
        struct Date {
            timestamp: I64;
            add(this: #Date, year: I32?) => Void;
        };
        type Headers = { [key: Str]: Str };
        const permission.camera: Str = "camera";
        rp let cache: I32[] = [];
        wp let queue: I32[] = [];
        const test = (): I32 => {
            let arr: I32[]?;
            let headers = { "Content-Type" = "text/plain", ["Accept"] = "application/json" };
            let ptr: *I8;
            const p = parallel { return 1; };
            return p;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '@"permission.camera"' in ir_text
        assert '@"__ez_lock_cache"' in ir_text
        assert '@"__ez_lock_queue"' in ir_text
        assert 'define void @"__ezrt_parallel_enter"' in ir_text
        assert 'Content-Type' in ir_text

    def test_locked_variables_emit_read_write_hooks(self):
        """rp/wp 变量直接读写应 lowering 为运行时锁 hook。"""
        source = '''
        rp let cache: I32 = 0;
        wp let queue: I32 = 0;
        const test = (): I32 => {
            cache = 1;
            queue = 2;
            return cache + queue;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '@"__ez_lock_cache" = internal global i32 1' in ir_text
        assert '@"__ez_lock_queue" = internal global i32 2' in ir_text
        assert 'declare void @"__ezrt_lock_register"' in ir_text
        assert 'define void @"__ezrt_lock_register"' not in ir_text
        assert re.search(r'call void @"__ezrt_lock_register"\(i8\* %"[^"]+", i32 1\)', ir_text)
        assert re.search(r'call void @"__ezrt_lock_register"\(i8\* %"[^"]+", i32 2\)', ir_text)
        assert ir_text.count('call void @"__ezrt_lock_write_acquire"') >= 2
        assert ir_text.count('call void @"__ezrt_lock_write_release"') >= 2
        assert ir_text.count('call void @"__ezrt_lock_read_acquire"') >= 2
        assert ir_text.count('call void @"__ezrt_lock_read_release"') >= 2
        assert 'define void @"__ezrt_lock_write_acquire"' not in ir_text

    def test_locked_compound_assignment_keeps_read_modify_write_inside_write_lock(self):
        """锁变量复合赋值应在同一个写锁内完成读改写。"""
        source = '''
        wp let total: I32 = 0;
        const test = (): I32 => {
            total += 1;
            return total;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        write_pos = ir_text.index('call void @"__ezrt_lock_write_acquire"')
        load_pos = ir_text.index('load i32, i32* @"total"', write_pos)
        store_pos = ir_text.index('store i32 %"_assign_value", i32* @"total"', load_pos)
        release_pos = ir_text.index('call void @"__ezrt_lock_write_release"', store_pos)
        assert write_pos < load_pos < store_pos < release_pos

    def test_global_let_defaults_to_ordered_lock(self):
        """全局可变 let 未声明 rp/wp 时应使用默认顺序锁。"""
        source = '''
        let total: I32 = 0;
        const test = (): I32 => {
            total += 1;
            return total;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='macos')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '@"__ez_lock_total" = internal global i32 0' in ir_text
        assert re.search(r'call void @"__ezrt_lock_register"\(i8\* %"[^"]+", i32 0\)', ir_text)
        assert 'call void @"__ezrt_lock_write_acquire"' in ir_text
        assert any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)

    def test_emcc_global_let_does_not_link_native_lock_runtime(self):
        """emcc 目标暂不启用 native 全局默认锁运行时。"""
        source = '''
        let total: I32 = 0;
        const test = (): I32 => {
            total += 1;
            return total;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '@"__ez_lock_total"' not in ir_text
        assert 'call void @"__ezrt_lock_register"' not in ir_text
        assert not any(str(lib).endswith('packages/std/native/runtime.c') for lib in libs)
