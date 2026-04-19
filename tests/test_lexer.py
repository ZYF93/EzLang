"""
Test Lexer
"""

import pytest
from ezlang.lexer import EzLangLexerWrapper

def test_lexer_basic():
    source = "let x = 42;"
    lexer = EzLangLexerWrapper(source)
    tokens = lexer.get_tokens()
    assert len(tokens) > 0