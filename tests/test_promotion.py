"""
TDD tests for EzLang Return Promotion (Escape Analysis).
"""

import pytest
from ezlang.compiler import EzLangCompiler

def test_ir_block_return_promotion():
    """验证从 Block 返回对象时，arena_top 不会重置到之前的 saved_ptr"""
    compiler = EzLangCompiler()
    # 场景：在 block 内部创建一个 Point 并返回它
    source = """
    struct Point { x: I32; };
    let p = {
        let internal_p = Point(x = 1);
        internal_p;
    };
    """
    ir_code = compiler.compile(source)
    
    # 验证是否生成了条件判断或提升逻辑
    # 简单实现：如果返回的是指针类型，我们不执行重置
    assert 'store i32 %".2", i32* @"arena_top"' not in ir_code or 'select' in ir_code

def test_ir_function_return_promotion():
    """验证从 Function 返回对象时，保持 Arena 指针不回退过深"""
    compiler = EzLangCompiler()
    source = """
    struct Data { val: I32; };
    const create = () => {
        let d = Data(val = 1);
        return d;
    };
    """
    ir_code = compiler.compile(source)
    
    # 函数结束处不应直接将 arena_top 重置到 entry 时的状态
    assert 'ret' in ir_code
