"""
Unit tests for EzLang Semantic Analyzer.
"""

import pytest
from ezlang.lexer import EzLangLexerWrapper
from ezlang.parser import EzLangParserWrapper
from ezlang.semantic_analyzer import SemanticAnalyzer

def analyze(source):
    lexer = EzLangLexerWrapper(source)
    parser = EzLangParserWrapper(lexer.tokens)
    analyzer = SemanticAnalyzer(parser.get_ast())
    analyzer.analyze()
    return analyzer

def test_semantic_basic_types():
    # 验证基础类型解析
    source = "let x: I32 = 10; let y: Str = 'hi';"
    analyzer = analyze(source)
    assert analyzer.symbol_table.lookup("x").type_obj.name == "I32"
    assert analyzer.symbol_table.lookup("y").type_obj.name == "Str"

def test_semantic_undefined_type():
    # 验证未定义类型报错
    source = "let x: UnknownType = 10;"
    with pytest.raises(Exception) as excinfo:
        analyze(source)
    assert "Undefined type: UnknownType" in str(excinfo.value)

def test_semantic_struct_registration():
    # 验证结构体注册为类型
    source = "struct MyStruct { x: I32; }; let s: MyStruct;"
    analyzer = analyze(source)
    assert analyzer.symbol_table.lookup_type("MyStruct") is not None

def test_semantic_generic_scope():
    # 验证泛型参数在结构体内部的作用域
    source = "struct Box<T> { val: T; };"
    analyzer = analyze(source)
    # 在全局作用域查找 T 应该失败
    assert analyzer.symbol_table.lookup_type("T") is None

def test_semantic_this_binding():
    # 验证方法中的 this 绑定
    source = "struct Counter { inc = (this: Counter) => 1; };"
    analyzer = analyze(source)
    # 这里主要验证 Counter 能在 this: Counter 中被解析
    assert not analyzer.errors

def test_semantic_type_alias():
    # 验证类型别名
    source = "type MyInt = I32; let x: MyInt = 1;"
    analyzer = analyze(source)
    assert analyzer.symbol_table.lookup_type("MyInt") is not None
