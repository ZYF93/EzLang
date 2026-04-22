"""
TDD tests for EzLang Advanced Type System (Member Access, Struct Types).
"""

import pytest
from ezlang.compiler import EzLangCompiler

def test_ir_struct_member_access():
    """验证结构体字段访问 p.x 生成 GEP 指令"""
    compiler = EzLangCompiler()
    source = """
    struct Point { x: I32; y: I32; };
    let p = Point(x = 0, y = 0);
    p.x = 10;
    let val = p.y;
    """
    ir_code = compiler.compile(source)
    
    # 验证是否生成了获取成员地址的逻辑
    # LLVM 中结构体成员访问通常使用 getelementptr
    assert 'getelementptr' in ir_code
    assert 'store i32 10' in ir_code

def test_ir_different_types():
    """验证 I64 和 I32 的正确处理"""
    compiler = EzLangCompiler()
    source = "let a: I64 = 100; let b: I32 = 20;"
    ir_code = compiler.compile(source)
    
    assert 'i64 100' in ir_code
    assert 'i32 20' in ir_code

def test_ir_bool_type():
    """验证 Bool 类型使用 i1"""
    compiler = EzLangCompiler()
    source = "let flag: Bool = true;"
    ir_code = compiler.compile(source)
    
    assert 'i1 1' in ir_code
