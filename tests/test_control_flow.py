"""
TDD tests for EzLang Control Flow (Loops, Match, Conditional Statements).
"""

import pytest
from ezlang.compiler import EzLangCompiler

def test_ir_conditional_statement():
    """验证条件语句 (cond) ? { block } 生成分支"""
    compiler = EzLangCompiler()
    source = "let x = 1; (x > 0) ? { x = 2; };"
    ir_code = compiler.compile(source)
    
    # 验证是否有比较指令和条件跳转
    assert 'icmp sgt' in ir_code
    assert 'br i1' in ir_code

def test_ir_infinite_loop():
    """验证无限循环 loop { ... } 生成循环结构"""
    compiler = EzLangCompiler()
    source = "loop { let x = 1; };"
    ir_code = compiler.compile(source)
    
    # 验证是否有无条件跳转回循环头
    assert 'br label' in ir_code
    assert ir_code.count('br label') >= 1

def test_ir_range_loop():
    """验证范围循环 loop i in 0...10 { ... }"""
    compiler = EzLangCompiler()
    source = "loop i in 0...10 { let x = i; };"
    ir_code = compiler.compile(source)
    
    # 应该包含初始化、比较、递增和跳转
    assert 'add i32' in ir_code # i + 1
    assert 'icmp slt' in ir_code # i < 10
    assert 'br i1' in ir_code

def test_ir_match_statement():
    """验证 match 语句生成多级条件跳转"""
    compiler = EzLangCompiler()
    source = "let x = 1; match { (x == 1) ? x = 2, (true) ? x = 3 };"
    ir_code = compiler.compile(source)
    
    # 验证有多个比较和分支
    assert ir_code.count('icmp eq') >= 1
    assert ir_code.count('br i1') >= 2
