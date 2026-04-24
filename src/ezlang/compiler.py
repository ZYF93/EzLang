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
            "project": {"entry": "src/main.ez", "name": "unknown"},
            "targets": [{"name": "default", "arch": "wasm32", "os": "wasi", "optimization_level": "O2", "output": "dist/output.wasm"}]
        }

    def compile(self, source_code: str, target_config=None) -> str:
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
        target_os = "wasi"
        if target_config:
            target_os = target_config.get("os", "wasi")
        backend = LLVMBackend(ir_code, target=target_os)
        
        llvm_ir = backend.generate_llvm_ir()

        return llvm_ir

    def resolve_dependency(self, dep_name: str) -> str:
        """初步的依赖模块路径检索逻辑"""
        dependencies = self.config.get("dependencies", {})
        if dep_name in dependencies:
            # 假定依赖的存放路径或缓存路径，例如 ez_modules
            dep_path = os.path.join(os.getcwd(), "ez_modules", dep_name)
            return dep_path
        raise Exception(f"Dependency not found in config: {dep_name}")

    def build_project(self, target_name=None):
        """根据 config.json 编译整个项目"""
        project = self.config.get("project", {})
        entry_path = project.get("entry", "src/main.ez")
        
        if not os.path.exists(entry_path):
            raise Exception(f"Entry file not found: {entry_path}")
            
        with open(entry_path, 'r') as f:
            source = f.read()
            
        targets = self.config.get("targets", [])
        if not targets:
            raise Exception("No targets defined in config.")
            
        target_to_build = targets[0]
        if target_name:
            for t in targets:
                if t.get("name") == target_name:
                    target_to_build = t
                    break
                    
        llvm_ir = self.compile(source, target_config=target_to_build)
        
        output_path = target_to_build.get("output", "dist/output.ll")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(llvm_ir)
            
        print(f"Successfully compiled {project.get('name', 'unknown')} to {output_path} (Target: {target_to_build.get('name')})")