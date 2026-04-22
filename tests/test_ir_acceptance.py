"""
Acceptance tests for EzLang IR Generation and Arena Memory Model.
"""

import pytest
from ezlang.compiler import EzLangCompiler

def test_ir_arena_scope_management():
    """验证 IR 中是否包含作用域开始时的 load arena_top 和结束时的 store arena_top"""
    compiler = EzLangCompiler()
    source = "{ let x = 1; }"
    ir_code = compiler.compile(source)
    
    # 验证是否包含全局指针
    assert '@"arena_top" = internal global i32 0' in ir_code
    
    # 验证初始化函数中是否有作用域管理
    # 至少应该有一次 load 和一次 store 回退
    assert 'load i32, i32* @"arena_top"' in ir_code
    assert 'store i32 %".2", i32* @"arena_top"' in ir_code

def test_ir_struct_allocation():
    """验证结构体实例化是否触发了 arena_alloc 调用"""
    compiler = EzLangCompiler()
    source = "struct Point { x: I32; }; let p = Point(x = 0);"
    ir_code = compiler.compile(source)
    
    # 验证是否定义了分配函数
    assert 'define i32 @"arena_alloc"(i32 %".1")' in ir_code
    # 验证是否调用了分配函数（假设结构体分配 64 字节）
    assert 'call i32 @"arena_alloc"(i32 64)' in ir_code

def test_ir_alignment_logic():
    """验证 arena_alloc 内部是否包含 8 字节对齐逻辑"""
    compiler = EzLangCompiler()
    # 任意代码都会生成 arena_alloc 定义
    ir_code = compiler.compile("let x = 1;")
    
    # 对齐逻辑特征：add 7, and -8
    assert 'add i32 %".3", 7' in ir_code
    assert 'and i32 %".4", -8' in ir_code

def test_ir_arena_acceptance_file():
    """验证 arena.ez 验收文件是否能成功生成 IR"""
    compiler = EzLangCompiler()
    with open('examples/arena.ez', 'r', encoding='utf-8') as f:
        source = f.read()
    
    ir_code = compiler.compile(source)
    assert ir_code is not None
    assert 'define i32 @"run"()' in ir_code
    # 验证 run 函数内有多个作用域管理（对应 arena.ez 中的 block 和函数调用）
    assert ir_code.count('store i32 %') >= 2
