"""
EzLang Parser Module
"""

from antlr4 import CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener
from .antlr_generated.EzLangParser import EzLangParser
from .antlr_generated.EzLangListener import EzLangListener

class EzLangErrorListener(ErrorListener):
    def __init__(self):
        super(EzLangErrorListener, self).__init__()
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(f"line {line}:{column} {msg}")

class EzLangParserWrapper:
    def __init__(self, tokens):
        self.tokens = tokens
        self.parser = EzLangParser(self.tokens)
        
        # Add error listener
        self.error_listener = EzLangErrorListener()
        self.parser.removeErrorListeners()
        self.parser.addErrorListener(self.error_listener)
        
        self.tree = self.parser.program()

    def get_ast(self):
        return self.tree

    def has_errors(self):
        return len(self.error_listener.errors) > 0

    def get_errors(self):
        return self.error_listener.errors