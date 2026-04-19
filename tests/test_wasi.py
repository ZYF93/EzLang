"""
Test WASI Test Example
"""

import pytest
from ezlang.lexer import EzLangLexerWrapper
from ezlang.parser import EzLangParserWrapper
from ezlang.wasi_runtime import print_function, memory_grow

def test_wasi_test_lexer():
    with open('examples/wasi_test.ez', 'r') as f:
        source = f.read()
    
    lexer = EzLangLexerWrapper(source)
    tokens = lexer.get_tokens()
    
    # Check some key tokens
    token_texts = [t.text for t in tokens if t.text not in [' ', '\n', ';']]
    assert 'declare' in token_texts
    assert 'const' in token_texts
    assert 'print' in token_texts
    assert 'let' in token_texts
    assert 'message' in token_texts
    assert '"Hello World"' in token_texts

def test_wasi_test_parser():
    with open('examples/wasi_test.ez', 'r') as f:
        source = f.read()
    
    lexer = EzLangLexerWrapper(source)
    parser = EzLangParserWrapper(lexer.tokens)
    ast = parser.get_ast()
    
    # Basic check that parsing succeeds
    assert ast is not None

def test_wasi_runtime_print():
    # Test the simulated print function
    import io
    import sys
    captured_output = io.StringIO()
    sys.stdout = captured_output
    try:
        print_function("Test message")
        output = captured_output.getvalue()
        assert "Test message" in output
    finally:
        sys.stdout = sys.__stdout__

def test_wasi_runtime_memory_grow():
    # Test memory.grow simulation
    initial_pages = 16  # assume initial 1MB = 16 pages
    result = memory_grow(1)
    assert result == initial_pages  # should return previous size in pages