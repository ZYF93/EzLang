"""
TDD tests for EzLang Operators and Expressions.
"""

import pytest
from ezlang.compiler import EzLangCompiler

def test_arithmetic_operators():
    compiler = EzLangCompiler()
    # 验证基础算术运算在 IR 中生成了正确的指令
    source = "let x = 10 + 5; let y = x * 2;"
    ir_code = compiler.compile(source)
    
    # 注意：我们的 IRGenerator 目前还没实现这些运算，所以这里预期会失败（Red phase of TDD）
    assert 'add i32' in ir_code
    assert 'mul i32' in ir_code

def test_comparison_operators():
    compiler = EzLangCompiler()
    source = "let res = (10 > 5);"
    ir_code = compiler.compile(source)
    assert 'icmp sgt' in ir_code

def test_logical_operators():
    compiler = EzLangCompiler()
    source = "let b = true && false;"
    ir_code = compiler.compile(source)
    # 逻辑与通常生成分支或 phi
    assert 'phi' in ir_code or 'br' in ir_code

def test_compound_assignment():
    compiler = EzLangCompiler()
    source = "let a = 1; a += 5;"
    ir_code = compiler.compile(source)
    assert 'add i32' in ir_code
    assert 'store' in ir_code
