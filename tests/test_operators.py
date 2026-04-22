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
    
    assert 'add i32' in ir_code
    assert 'mul i32' in ir_code


def test_comparison_operators():
    compiler = EzLangCompiler()
    source = "let res = (10 > 5);"
    ir_code = compiler.compile(source)
    assert 'icmp sgt' in ir_code


def test_logical_operators():
    compiler = EzLangCompiler()
    source = "let b = true && false; let c = true || false;"
    ir_code = compiler.compile(source)
    assert 'phi' in ir_code or 'br' in ir_code
    assert 'or.rhs' in ir_code or 'or.exit' in ir_code or ir_code.count('phi') >= 2


def test_bitwise_and_shift_operators():
    compiler = EzLangCompiler()
    source = "let a = 0b1010 & 0b1100; let b = 0b1010 | 0b0101; let c = 0b1010 ^ 0b1100; let d = 1 << 3; let e = 100 >> 2;"
    ir_code = compiler.compile(source)

    assert 'and i32' in ir_code
    assert 'or i32' in ir_code
    assert 'xor i32' in ir_code
    assert 'shl i32' in ir_code
    assert 'ashr i32' in ir_code or 'lshr i32' in ir_code


def test_compound_assignment():
    compiler = EzLangCompiler()
    source = "let a = 1; a += 5; a *= 2;"
    ir_code = compiler.compile(source)
    assert 'add i32' in ir_code
    assert 'mul i32' in ir_code
    assert 'store' in ir_code


def test_operators_acceptance_file():
    compiler = EzLangCompiler()
    with open('examples/operators.ez', 'r', encoding='utf-8') as f:
        source = f.read()

    ir_code = compiler.compile(source)
    assert ir_code is not None
    assert 'and i32' in ir_code
    assert 'or i1' in ir_code or 'or.exit' in ir_code or 'phi' in ir_code
    assert 'xor i32' in ir_code
    assert 'shl i32' in ir_code
