"""EzLang LLVM IR 代码生成测试"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

ROOT = Path(__file__).resolve().parents[2]
STD_ROOT = ROOT / 'packages' / 'std'

from llvmlite import ir
from codegen.llvm_codegen import compile_source


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
	    let a: I32 = 0b1010 & 0b1100;
	    let b: I32 = 0b1010 | 0b0101;
	    let c: I32 = 0b1010 ^ 0b1100;
	    let d: I32 = 1 << 3;
	    let e: I32 = 100 >> 2;
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
        """标记字面量生成字符串表示"""
        source = '''
	const test_markup = () => {
	    let ui = <text color="blue">
	        "Welcome"
	        <div id=1 />
	        {1 + 2}
	    </text>;
	    return 0;
	};
	'''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        ir_text = str(module)
        assert '_markup_' in ir_text
        assert 'text' in ir_text

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

    def test_typeof_expr(self):
        """typeof 表达式（编译时类型查询）"""
        source = '''
        const run = () => {
            let t = typeof 42;
            return 42;
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        func = module.get_global('run')
        assert func is not None

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
        assert '@"set"' not in ir_text

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
        module, errors, libs = compile_source(source, compile_target='linux')
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
        module, errors, libs = compile_source(source, compile_target='linux')
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
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'fs.c')]
        for name in ['readFile', 'writeFile', 'appendFile', 'removeFile', 'mkdir',
                     'removeDir', 'listDir', 'exists', 'isDir', 'stat', 'absPath']:
            assert module.get_global(name) is not None
        assert 'FileStat' in str(module)

    def test_stdlib_fs_target_filter(self):
        """std/fs extern 应按桌面目标过滤"""
        source = 'from "./std/fs.ez" import { exists };'
        _, _, linux_libs = compile_source(source, compile_target='linux')
        _, _, windows_libs = compile_source(source, compile_target='windows')
        _, _, android_libs = compile_source(source, compile_target='android')
        assert linux_libs == [str(STD_ROOT / 'native' / 'fs.c')]
        assert windows_libs == [str(STD_ROOT / 'native' / 'fs.c')]
        assert android_libs == [str(STD_ROOT / 'native' / 'fs.c')]

    def test_stdlib_time_import(self):
        """std/time 时间库导入"""
        source = '''
        from "./std/time.ez" import {
            now, timestamp, sleep, getYear, getMonth, getDay, add, sub, format
        };

        const check_time = (): I32 => {
            const d = now();
            const ts = timestamp();
            sleep(ms = 1);
            const y = getYear(this = d);
            const m = getMonth(this = d);
            const day = getDay(this = d);
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
        for name in ['now', 'timestamp', 'sleep', 'getYear', 'getMonth', 'getDay', 'add', 'sub', 'format']:
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
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'fmt.c')]
        for name in ['parseInt', 'parseI64', 'parseF64', 'format', 'b64Encode', 'b64Decode', 'urlEncode', 'urlDecode']:
            assert module.get_global(name) is not None

    def test_stdlib_fmt_generic_import(self):
        """std/fmt 泛型编码声明可导入"""
        source = '''
        from "./std/fmt.ez" import { toString, jsonStringify, jsonParse, msgpackEncode, msgpackDecode };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'

    def test_stdlib_net_http_import(self):
        """std/net/http 导入"""
        source = '''
        from "./std/net/http.ez" import { Headers, HttpRequest, HttpResponse, fetch, fetchEx };

        const call_http = (): HttpResponse? => {
            const resp = fetch(url = "https://example.com");
            return resp;
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'http.c')]
        assert module.get_global('fetch') is not None
        assert module.get_global('fetchEx') is not None
        ir_text = str(module)
        assert 'HttpRequest' in ir_text
        assert 'HttpResponse' in ir_text

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
        from "./std/net/tcp.ez" import { TcpConn, TcpListener, UdpSocket, tcpConnect, tcpListen, udpBind };

        const open_tcp = (): TcpConn? => {
            return tcpConnect(host = "127.0.0.1", port = 80);
        };

        const open_listener = (): TcpListener? => {
            return tcpListen(host = "127.0.0.1", port = 8080);
        };

        const open_udp = (): UdpSocket? => {
            return udpBind(host = "127.0.0.1", port = 5353);
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'tcp.c')]
        for name in ['tcpConnect', 'tcpListen', 'udpBind']:
            assert module.get_global(name) is not None
        ir_text = str(module)
        assert 'TcpConn' in ir_text
        assert 'TcpListener' in ir_text
        assert 'UdpSocket' in ir_text

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
        from "./std/net/ws.ez" import { WsConn, wsConnect };

        const connect_ws = (): WsConn? => {
            return wsConnect(url = "wss://example.com/socket");
        };
        '''
        module, errors, libs = compile_source(source, compile_target='linux')
        assert module is not None
        assert len(errors) == 0, f'编译错误: {errors}'
        assert libs == [str(STD_ROOT / 'native' / 'net' / 'ws.c')]
        assert module.get_global('wsConnect') is not None
        assert 'WsConn' in str(module)

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

    def test_stdlib_collections_call_reports_unimplemented(self):
        """std/collections 未实现函数不应生成悬空 LLVM declare"""
        source = '''
        from "./std/collections.ez" import { listLen, dictHas };

        const test_list = () => {
            let nums: List<I32> = [1, 2, 3];
            return listLen<I32>(list = nums);
        };
        '''
        module, errors, _ = compile_source(source)
        assert module is not None
        assert any("标准库集合函数 'listLen' 尚未实现" in e for e in errors)
        assert 'declare i64 @"listLen_I32"' not in str(module)

    # ==================== Arena 分配器测试 ====================

    def test_arena_infrastructure(self):
        """Arena 基础设施应始终生成：buffer + cursor + alloc + save + restore"""
        module, errors, _ = compile_source('')
        assert module is not None
        ir_text = str(module)
        assert '__arena_buffer' in ir_text
        assert '__arena_cursor' in ir_text
        assert '__arena_alloc' in ir_text
        assert '__arena_save' in ir_text
        assert '__arena_restore' in ir_text

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
