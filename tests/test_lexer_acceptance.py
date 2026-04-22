"""
Acceptance tests for EzLang Lexer using .ez files.
"""

import pytest
from ezlang.lexer import EzLangLexerWrapper
from ezlang.antlr_generated.EzLangLexer import EzLangLexer

def get_token_names(tokens):
    names = []
    for t in tokens:
        if t.type == -1: continue
        name = None
        # 在 ANTLR 4.13 Python 运行时，Vocabulary 对象可以通过 lexer.vocabulary 访问
        # 如果不可用，则退回到类属性
        try:
            name = EzLangLexer.symbolicNames[t.type]
        except (AttributeError, IndexError):
            pass
            
        if not name or name == "<INVALID>":
            try:
                name = EzLangLexer.literalNames[t.type].strip("'")
            except (AttributeError, IndexError):
                pass
        
        if name:
            names.append(name)
    return names

def test_lexer_types_ez():
    with open('examples/types.ez', 'r', encoding='utf-8') as f:
        source = f.read()
    
    lexer = EzLangLexerWrapper(source)
    tokens = lexer.get_tokens()
    
    token_types = [t.type for t in tokens if t.type != -1]
    assert len(token_types) > 0
    
    symbolic_names = get_token_names(tokens)
    
    # 验证关键关键字和类型是否存在
    assert 'LET' in symbolic_names
    assert 'DECLARE' in symbolic_names
    assert 'CONST' in symbolic_names
    assert 'ID' in symbolic_names
    assert 'INT' in symbolic_names
    assert 'I32' in symbolic_names
    assert 'F32' in symbolic_names
    assert 'BOOL_TYPE' in symbolic_names
    assert 'TRUE' in symbolic_names

def test_lexer_vars_ez():
    with open('examples/vars.ez', 'r', encoding='utf-8') as f:
        source = f.read()
    
    lexer = EzLangLexerWrapper(source)
    tokens = lexer.get_tokens()
    
    token_texts = [t.text for t in tokens]
    symbolic_names = get_token_names(tokens)
    
    assert 'STATIC' in symbolic_names
    assert 'CONST' in symbolic_names
    assert '10' in token_texts
    assert '20' in token_texts
    assert '3.14' in token_texts
    assert 'ASSIGN' in symbolic_names

def test_lexer_literals():
    # 测试新增的进制支持
    source = "0b1010 0xFF 123 3.14"
    lexer = EzLangLexerWrapper(source)
    tokens = [t for t in lexer.get_tokens() if t.type != -1]
    
    assert tokens[0].text == "0b1010"
    assert tokens[1].text == "0xFF"
    assert tokens[2].text == "123"
    assert tokens[3].text == "3.14"
    
    names = get_token_names(tokens)
    assert names[0] == "INT"
    assert names[1] == "INT"
    assert names[2] == "INT"
    assert names[3] == "FLOAT"
