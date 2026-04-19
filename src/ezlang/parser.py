"""
EzLang Parser Module
"""

from antlr4 import CommonTokenStream
from .antlr_generated.EzLangParser import EzLangParser
from .antlr_generated.EzLangListener import EzLangListener

class EzLangParserWrapper:
    def __init__(self, tokens):
        self.tokens = tokens
        self.parser = EzLangParser(self.tokens)
        self.tree = self.parser.program()

    def get_ast(self):
        return self.tree