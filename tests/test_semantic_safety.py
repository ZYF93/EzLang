"""
Tests for EzLang Semantic Analyzer Initialization Safety.
"""

import pytest
from antlr4 import InputStream, CommonTokenStream
from ezlang.antlr_generated.EzLangLexer import EzLangLexer
from ezlang.antlr_generated.EzLangParser import EzLangParser
from ezlang.semantic_analyzer import SemanticAnalyzer

def test_semantic_uninitialized_struct_field():
    """验证实例化时必须提供没有默认值的字段"""
    source = """
    struct Data { val: I32; };
    let d = Data(); // 应该报错，因为 val 没有默认值
    """
    lexer = EzLangLexer(InputStream(source))
    stream = CommonTokenStream(lexer)
    parser = EzLangParser(stream)
    tree = parser.program()
    
    analyzer = SemanticAnalyzer(tree)
    with pytest.raises(Exception, match="Field 'val' of struct 'Data' must be initialized"):
        analyzer.analyze()

def test_semantic_initialized_struct_field_success():
    """验证提供了字段时通过"""
    source = """
    struct Data { val: I32; };
    let d = Data(val = 10);
    """
    lexer = EzLangLexer(InputStream(source))
    stream = CommonTokenStream(lexer)
    parser = EzLangParser(stream)
    tree = parser.program()
    
    analyzer = SemanticAnalyzer(tree)
    analyzer.analyze() # 不应报错

def test_semantic_default_value_success():
    """验证有默认值时可以不提供"""
    source = """
    struct Data { val: I32 = 0; };
    let d = Data();
    """
    lexer = EzLangLexer(InputStream(source))
    stream = CommonTokenStream(lexer)
    parser = EzLangParser(stream)
    tree = parser.program()
    
    analyzer = SemanticAnalyzer(tree)
    analyzer.analyze() # 不应报错
