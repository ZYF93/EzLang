"""
EzLang Compiler Main Module
"""

from .lexer import EzLangLexerWrapper
from .parser import EzLangParserWrapper
from .semantic_analyzer import SemanticAnalyzer
from .ir_generator import IRGenerator
from .llvm_backend import LLVMBackend

class EzLangCompiler:
    def __init__(self):
        pass

    def compile(self, source_code: str) -> str:
        # Lexical Analysis
        lexer = EzLangLexerWrapper(source_code)
        tokens = lexer.get_tokens()

        # Syntax Analysis
        parser = EzLangParserWrapper(lexer.tokens)
        ast = parser.get_ast()

        # Semantic Analysis
        analyzer = SemanticAnalyzer(ast)
        analyzer.analyze()

        # IR Generation
        ir_gen = IRGenerator(ast)
        ir_code = ir_gen.generate_ir()

        # LLVM Backend
        backend = LLVMBackend(ir_code)
        llvm_ir = backend.generate_llvm_ir()

        return llvm_ir