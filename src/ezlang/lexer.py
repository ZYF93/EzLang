"""
EzLang Lexer Module
"""

from antlr4 import InputStream, CommonTokenStream
from .antlr_generated.EzLangLexer import EzLangLexer

class EzLangLexerWrapper:
    def __init__(self, input_stream):
        self.input_stream = InputStream(input_stream)
        self.lexer = EzLangLexer(self.input_stream)
        self.tokens = CommonTokenStream(self.lexer)

    def get_tokens(self):
        self.tokens.fill()
        return self.tokens.tokens