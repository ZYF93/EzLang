"""
Acceptance tests for EzLang Parser using .ez files.
"""

import pytest
from ezlang.lexer import EzLangLexerWrapper
from ezlang.parser import EzLangParserWrapper

def parse_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    lexer = EzLangLexerWrapper(source)
    parser = EzLangParserWrapper(lexer.tokens)
    return parser

def test_parser_types_ez():
    parser = parse_file('examples/types.ez')
    assert not parser.has_errors(), f"Types parsing errors: {parser.get_errors()}"

def test_parser_vars_ez():
    parser = parse_file('examples/vars.ez')
    assert not parser.has_errors(), f"Vars parsing errors: {parser.get_errors()}"

def test_parser_structs_ez():
    parser = parse_file('examples/structs.ez')
    assert not parser.has_errors(), f"Structs parsing errors: {parser.get_errors()}"

def test_parser_control_ez():
    parser = parse_file('examples/control.ez')
    assert not parser.has_errors(), f"Control parsing errors: {parser.get_errors()}"

def test_parser_wasi_test_ez():
    parser = parse_file('examples/wasi_test.ez')
    assert not parser.has_errors(), f"WASI test parsing errors: {parser.get_errors()}"
