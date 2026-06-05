"""EzLang LLVM IR 代码生成测试"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

ROOT = Path(__file__).resolve().parents[2]
STD_ROOT = ROOT / 'packages' / 'std'

from llvmlite import ir, binding
from codegen.llvm_codegen import compile_source


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


class TestCodegen:

    def test_empty_source(self):
        """空源码生成空模块"""
        module, errors, _ = compile_source('')
        assert module is not None
        assert len(errors) == 0

    def test_global_constant(self):
        """全局常量声明"""
        source = 'const x: I32 = 42;'
        module, errors, _ = compile_source(source)
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
        const log = (this: Meta<I32>): Void => { return; };
        @log let watched = 1;
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0
        ir_text = str(module)
        assert '%"Meta_i32"' in ir_text
        assert '@"watched" = global %"Meta_i32"' in ir_text
        assert 'call void @"log"(%"Meta_i32"' in ir_text

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
        assert 'call i32 @"__ezrt_race"(i32 2, i32 10)' in ir_text
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
            distance = (this: Point, other: Point): I32 => {
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
        const add = (a: I32, b: I32): I32 => {
            return a + b;
        };

        const run = () => {
            return 10 -> add(b = 20);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None
        ir_text = str(module)
        assert 'add' in ir_text

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
            swap = (this: Pair<T, U>): Pair<U, T> => {
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
        """文档接口 race(pl=[...], timeout=...) 应调用 hook 并同步执行首个分支。"""
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
        assert '@"__ezrt_race"' in ir_text
        assert 'call i32 @"__ezrt_race"(i32 2, i32 10)' in ir_text
        assert 'define i32 @"__ez_race_branch_' in ir_text
        assert 'call i32 @"__ezrt_race_i32"' in ir_text
        assert 'call i32 @"race"' not in ir_text

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
        assert 'ret i32 0' not in ir_text
        assert 'store i32 0' not in ir_text

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
        ir_text = str(module)
        assert 'ret i32 0' not in ir_text
        assert 'ret i32' in ir_text

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
        ir_text = str(module)
        assert 'and i32' in ir_text
        assert 'icmp' in ir_text
        assert 'ret i1 0' not in ir_text

    def test_comprehensive_module(self):
        """综合测试：结构体、方法、可选类型、泛型、管道、字典"""
        source = '''
        struct Point {
            x: I32;
            y: I32;
            distance = (this: Point, other: Point): I32 => {
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
        # 应该生成跳板函数 add_curried
        assert module.get_global('add_curried') is not None

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
        assert 'getelementptr inbounds %"Blob", %"Blob"* %"dst.1", i32 0, i32 0' in ir_text
        assert 'getelementptr inbounds %"Blob", %"Blob"* %"src.1", i32 0, i32 0' in ir_text
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
        assert 'getelementptr inbounds %"Blob", %"Blob"* %"dst.1", i32 0, i32 0' in ir_text
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
        assert 'declare %"Blob" @"strToBytes"' in ir_text
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
            randomRangeF64, randomShuffleBytes, randomEntropy, randomSecureBytes, randomSecureU64
        };

        const check_random = (): I32 => {
            let source = randomSeed(seed = 42);
            const n32 = randomNextU32(this = source);
            const n64 = randomNextU64(this = source);
            const ranged_i = randomRangeI64(this = source, minValue = 1, maxValue = 10);
            const ranged_f = randomRangeF64(this = source, minValue = 0.0, maxValue = 1.0);
            const shuffled = randomShuffleBytes(this = source, data = Blob(data = "abcd", size = 4));
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
        assert 'declare %"RandomSource" @"randomSeed"' in ir_text
        assert 'declare i64 @"randomNextU64"' in ir_text
        assert 'declare %"Blob" @"randomShuffleBytes"' in ir_text
        assert 'declare void @"randomSecureBytes"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
        assert_optional_return_bridge(ir_text, 'randomSecureU64', 'i64', 'x86_64')

        aarch64_module, aarch64_errors, _ = compile_source(source, compile_target='linux', target_arch='aarch64')
        assert aarch64_module is not None
        assert len(aarch64_errors) == 0, f'编译错误: {aarch64_errors}'
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
        module, errors, libs = compile_source(source, compile_target='linux')
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
        module, errors, libs = compile_source(source, compile_target='linux')
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
            processWait, processTerminate, processCurrentPath
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
            const path = processCurrentPath();
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux', target_arch='x86_64')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'process.c')]
        for name in ['processExec', 'processSpawn', 'processWait', 'processTerminate', 'processCurrentPath']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert '%"Command" = type' in ir_text
        assert '%"Process" = type {i64, i64}' in ir_text
        assert '%"ProcessResult" = type' in ir_text
        assert 'declare void @"processExec"({i1, %"ProcessResult"}* sret({i1, %"ProcessResult"})' in ir_text
        assert 'declare void @"processSpawn"({i1, %"Process"}* sret({i1, %"Process"})' in ir_text
        assert 'declare void @"processWait"({i1, %"ProcessResult"}* sret({i1, %"ProcessResult"})' in ir_text
        assert 'declare i1 @"processTerminate"(%"Process"*' in ir_text
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
        assert linux_libs == [str(STD_ROOT / 'native' / 'process.c')]
        assert windows_libs == [str(STD_ROOT / 'native' / 'process.c')]
        assert android_libs == [str(STD_ROOT / 'native' / 'process.c')]
        assert ios_libs == [str(STD_ROOT / 'native' / 'process.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'process.js')]
        module, errors, _ = compile_source(source + '\nlet path = processCurrentPath();\n', compile_target='emcc')
        assert len(errors) == 0, f'编译错误: {errors}'
        assert 'declare void @"processCurrentPath"({i1, i8*}* sret({i1, i8*})' in str(module)

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
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'debug.c')]
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
        assert 'declare %"LogConfig" @"logDefaultConfig"' in ir_text
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
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'regex.c')]
        for name in ['regexCompile', 'regexIsValid', 'regexTest', 'regexFind', 'regexFindAll', 'regexReplace', 'regexSplit']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert '%"Regex" = type' in ir_text
        assert '%"RegexMatch" = type' in ir_text
        assert 'declare %"Regex" @"regexCompile"' in ir_text
        assert 'declare void @"regexFind"({i1, %"RegexMatch"}* sret({i1, %"RegexMatch"})' in ir_text
        assert 'declare void @"regexFindAll"({i8***, i64, i64, i64}* sret({i8***, i64, i64, i64})' in ir_text

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
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'crypto.c')]
        for name in ['cryptoSha256', 'cryptoSha512', 'cryptoHmacSha256', 'cryptoHmacSha512']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert 'declare void @"cryptoSha256"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
        assert 'declare void @"cryptoHmacSha512"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text

    def test_stdlib_crypto_target_filter(self):
        """std/crypto extern 应按目标过滤"""
        source = 'from "./std/crypto.ez" import { cryptoSha256 };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'crypto.c')]
        assert ios_libs == [str(STD_ROOT / 'native' / 'crypto.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'crypto.js')]

    def test_stdlib_compress_import(self):
        """std/compress 压缩库导入"""
        source = '''
        from "./std/compress.ez" import {
            compressGzip, decompressGzip, compressZlib, decompressZlib,
            compressDeflate, decompressDeflate
        };

        const check_compress = (): I32 => {
            const data = Blob(data = "hello", size = 5);
            const gz = compressGzip(data = data);
            const raw_gz = decompressGzip(data = gz.value);
            const z = compressZlib(data = data);
            const raw_z = decompressZlib(data = z.value);
            const d = compressDeflate(data = data);
            const raw_d = decompressDeflate(data = d.value);
            return 0;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'compress.c'), 'z']
        for name in ['compressGzip', 'decompressGzip', 'compressZlib', 'decompressZlib', 'compressDeflate', 'decompressDeflate']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert 'declare void @"compressGzip"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
        assert 'declare void @"decompressDeflate"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text

    def test_stdlib_compress_target_filter(self):
        """std/compress extern 应按目标过滤"""
        source = 'from "./std/compress.ez" import { compressGzip };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, macos_libs = compile_source(source, compile_target='macos')
        _, _, android_libs = compile_source(source, compile_target='android')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'compress.c'), 'z']
        assert macos_libs == [str(STD_ROOT / 'native' / 'compress.c'), 'z']
        assert android_libs == [str(STD_ROOT / 'native' / 'compress.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'compress.js')]

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
            streamKindMemory, streamKindFileRead, streamKindFileWrite, streamKindTcp, Stream,
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
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'stream.c')]
        ir_text = str(module)
        assert '%"Stream" = type {i64, i32}' in ir_text
        assert 'declare void @"streamFromBlob"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
        assert 'declare %"Stream" @"streamFromTcpHandle"(i64' in ir_text
        assert 'declare void @"streamOpenFileRead"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
        assert 'declare void @"streamOpenFileWrite"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
        assert 'declare void @"streamRead"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
        for name in ['streamWrite', 'streamToBlob', 'streamCopy', 'streamFlush', 'streamClose']:
            assert module.get_global(name) is not None

    def test_stdlib_stream_target_filter(self):
        """std/stream extern 应按目标过滤"""
        source = 'from "./std/stream.ez" import { streamFromBlob };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, ios_libs = compile_source(source, compile_target='ios')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'stream.c')]
        assert ios_libs == [str(STD_ROOT / 'native' / 'stream.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'stream.js')]

    def test_stdlib_time_import(self):
        """std/time 时间库导入"""
        source = '''
        from "./std/time.ez" import {
            now, timestamp, sleep, getYear, getMonth, getDay, getHour, getMinute, getSecond,
            add, sub, format
        };

        const check_time = (): I32 => {
            const d = now();
            const ts = timestamp();
            sleep(ms = 1);
            const y = getYear(this = d);
            const m = getMonth(this = d);
            const day = getDay(this = d);
            const hour = getHour(this = d);
            const minute = getMinute(this = d);
            const second = getSecond(this = d);
            add(this = d, year = 1, month = 1, day = 1, hour = 1, minute = 1, second = 1);
            sub(this = d, year = 1, month = 1, day = 1, hour = 1, minute = 1, second = 1);
            const s = format(this = d, fmt = "yyyy-MM-dd");
            return y;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'time.c')]
        for name in ['now', 'timestamp', 'sleep', 'getYear', 'getMonth', 'getDay', 'getHour', 'getMinute', 'getSecond', 'add', 'sub', 'format']:
            assert module.get_global(name) is not None

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
        module, errors, _ = compile_source(source)
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
            const b = msgpackDecode<Bool>(data = msgpackEncode<Bool>(data = true));
            const s = msgpackDecode<Str>(data = msgpackEncode<Str>(data = "EzLang"));
            const f = msgpackDecode<F64>(data = msgpackEncode<F64>(data = 3.0));
            return s;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        for name in ['msgpackEncode_I1', 'msgpackDecode_I1', 'msgpackEncode_Str', 'msgpackDecode_Str', 'msgpackEncode_F64', 'msgpackDecode_F64']:
            assert module.get_global(name) is not None

    def test_stdlib_fmt_emcc_to_string_f32_declares_wrapper(self):
        """emcc 平台的 toString<F32> 应有对应 JS 封装符号。"""
        source = '''
        from "./std/fmt.ez" import { toString };
        let text = toString<F32>(value = 3.5);
        '''
        module, errors, libs = compile_source(source, compile_target='emcc')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'emcc' / 'fmt.js')]
        assert module.get_global('toString_F32') is not None

    def test_stdlib_net_http_import(self):
        """std/net/http 导入"""
        source = '''
        from "./std/net/http.ez" import { Headers, HttpRequest, HttpResponse, fetch, fetchEx };

        const call_http = (): Str => {
            const resp = fetch(url = "https://example.com");
            return resp.ok ? resp.value.text() : "";
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'http.c')]
        assert module.get_global('fetch') is not None
        assert module.get_global('fetchEx') is not None
        assert module.get_global('HttpResponse_text') is not None
        ir_text = str(module)
        assert 'HttpRequest' in ir_text
        assert 'HttpResponse' in ir_text
        assert 'sret({i1, %"HttpResponse"})' in ir_text
        assert 'call i8* @"HttpResponse_text"' in ir_text

    def test_stdlib_net_http_target_filter(self):
        """std/net/http extern 应按目标过滤"""
        source = 'from "./std/net/http.ez" import { fetch };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, android_libs = compile_source(source, compile_target='android')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'net' / 'http.c')]
        assert android_libs == [str(STD_ROOT / 'native' / 'net' / 'http.c')]
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
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'http.c')]
        assert module.get_global('createServer') is not None
        assert 'HttpServer' in str(module)

    def test_stdlib_net_tcp_udp_import(self):
        """std/net TCP/UDP API 导入"""
        source = '''
        from "./std/net/tcp.ez" import {
            TcpConn, TcpListener, UdpSocket, tcpConnect, tcpListen, tcpAccept,
            tcpRead, tcpWrite, tcpClose, tcpListenerClose, udpBind, udpSend,
            udpRecv, udpClose
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
            const received = udpRecv(socket = socket, maxBytes = 16);
            const closed = udpClose(socket = socket);
            return sent;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'tcp.c')]
        for name in [
            'tcpConnect', 'tcpListen', 'tcpAccept', 'tcpRead', 'tcpWrite', 'tcpClose',
            'tcpListenerClose', 'udpBind', 'udpSend', 'udpRecv', 'udpClose'
        ]:
            assert module.get_global(name) is not None
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert 'TcpConn' in ir_text
        assert 'TcpListener' in ir_text
        assert 'UdpSocket' in ir_text
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
        assert libs == [str(STD_ROOT / 'native' / 'stream.c'), str(STD_ROOT / 'native' / 'net' / 'tcp.c')]
        ir_text = str(module)
        binding.parse_assembly(ir_text).verify()
        assert '%"Stream" = type {i64, i32}' in ir_text
        assert module.get_global('streamFromTcpHandle') is not None
        assert module.get_global('streamRead') is not None

    def test_stdlib_net_tcp_udp_target_filter(self):
        """std/net TCP/UDP extern 应按目标过滤"""
        source = 'from "./std/net/tcp.ez" import { tcpConnect, udpBind };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, emcc_libs = compile_source(source, compile_target='emcc')
        assert linux_libs == [str(STD_ROOT / 'native' / 'net' / 'tcp.c')]
        assert windows_libs == [str(STD_ROOT / 'native' / 'net' / 'tcp.c')]
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
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'ws.c')]
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
        assert linux_libs == [str(STD_ROOT / 'native' / 'net' / 'ws.c')]
        assert windows_libs == [str(STD_ROOT / 'native' / 'net' / 'ws.c')]
        assert emcc_libs == [str(STD_ROOT / 'emcc' / 'net' / 'ws.js')]

    # ==================== 泛型 declare 单态化测试 ====================

    def test_generic_declare_simple(self):
        """泛型 declare: <T>(list: List<T>, item: T) => Void"""
        source = '''
        declare const listPush: <T>(list: List<T>, item: T) => Void;
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0
        ir_text = str(module)
        # 泛型 declare 仅注册模板，不生成 LLVM 函数（调用时单态化）

    def test_generic_declare_multi_param(self):
        """泛型 declare: <K, V>(dict: Dict<K, V>, key: K) => Bool — 多参数模板注册"""
        source = '''
        declare const dictHas: <K, V>(dict: Dict<K, V>, key: K) => Bool;
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
            listPush<I32>(list = nums, item = 4);
            listUnshift<I32>(list = nums, item = 0);
            const tail = listPop<I32>(list = nums);
            const head = listShift<I32>(list = nums);
            let part: List<I32> = listSlice<I32>(list = nums, start = 0, end = 2);
            return listLen<I32>(list = part);
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
            listSort<I32>(list = nums, cmp = cmp);
            let found = listFind<I32>(list = nums, pred = pred);
            let filtered: List<I32> = listFilter<I32>(list = nums, pred = pred);
            let mapped: List<I64> = listMap<I32, I64>(list = filtered, f = mapper);
            return listLen<I64>(list = mapped);
        };

        const test_dict = (): I64 => {
            let meta = { name: Str = "ez", lang: Str = "EzLang" };
            let has_name = dictHas<Str, Str>(dict = meta, key = "name");
            let keys: List<Str> = dictKeys<Str, Str>(dict = meta);
            let values: List<Str> = dictValues<Str, Str>(dict = meta);
            let removed = dictDelete<Str, Str>(dict = meta, key = "name");
            return dictLen<Str, Str>(dict = meta);
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

    def test_p0_documented_syntax_codegen(self):
        """P0 文档语法应能生成 IR 或明确占位 ABI"""
        source = '''
        struct Date {
            timestamp: I64;
            add(this: Date, year: I32?) => Void;
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
        assert ir_text.count('call void @"__ezrt_lock_write_acquire"') >= 2
        assert ir_text.count('call void @"__ezrt_lock_write_release"') >= 2
        assert ir_text.count('call void @"__ezrt_lock_read_acquire"') >= 2
        assert ir_text.count('call void @"__ezrt_lock_read_release"') >= 2
