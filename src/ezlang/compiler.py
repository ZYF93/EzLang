"""
EzLang Compiler Main Module
"""

import json
import os
from .lexer import EzLangLexerWrapper
from .parser import EzLangParserWrapper
from .semantic_analyzer import SemanticAnalyzer
from .ir_generator import IRGenerator
from .llvm_backend import LLVMBackend

class EzLangCompiler:
    def __init__(self, config_path="config.json"):
        self.config = self._load_config(config_path)

    def _load_config(self, path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return {
            "target": "wasi",
            "optimization": "O2"
        }

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

        # LLVM Backend (根据 config 调整目标)
        target = self.config.get("target", "wasi")
        backend = LLVMBackend(ir_code, target=target)
        
        llvm_ir = backend.generate_llvm_ir()

        return llvm_ir

    def build_project(self):
        """根据 config.json 编译整个项目"""
        entry_path = self.config.get("entry", "src/main.ez")
        if not os.path.exists(entry_path):
            raise Exception(f"Entry file not found: {entry_path}")
            
        with open(entry_path, 'r') as f:
            source = f.read()
            
        llvm_ir = self.compile(source)
        
        output_path = self.config.get("output", "dist/output.ll")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(llvm_ir)
            
        print(f"Successfully compiled {self.config['name']} to {output_path} (Target: {self.config['target']})")