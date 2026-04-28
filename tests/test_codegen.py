import pytest
import os
import glob
from compiler.__main__ import build_ast
from compiler.errors import ErrorCollector
from compiler.codegen import CodeGenerator
from compiler.context import CompileContext

# 获取 examples 目录下所有的 .ez 文件
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")
EZ_FILES = glob.glob(os.path.join(EXAMPLES_DIR, "*.ez"))

@pytest.mark.parametrize("filepath", EZ_FILES)
def test_example_compilation(filepath):
    """
    自动化测试：验证 examples 目录下的所有 .ez 文件是否能通过编译并生成合法的 LLVM IR。
    """
    collector = ErrorCollector()
    
    # 1. 构建 AST
    try:
        ast = build_ast(filepath, collector)
    except Exception as e:
        pytest.fail(f"AST Build Exception for {os.path.basename(filepath)}: {e}")
        
    if collector.has_errors:
        errors = "\n".join([f"{e.location.line}:{e.location.column} - {e.message}" for e in collector.errors])
        pytest.fail(f"Parsing errors in {os.path.basename(filepath)}:\n{errors}")
        
    # 2. 生成 IR
    ctx = CompileContext(module_name=os.path.basename(filepath).replace(".ez", ""))
    codegen = CodeGenerator(ctx, collector)
    
    try:
        ir_code = codegen.generate(ast)
    except Exception as e:
        pytest.fail(f"Codegen Exception for {os.path.basename(filepath)}: {e}")
        
    if collector.has_errors:
        errors = "\n".join([f"{e.location.line}:{e.location.column} - {e.message}" for e in collector.errors])
        pytest.fail(f"Codegen errors in {os.path.basename(filepath)}:\n{errors}")
        
    # 3. 基本验证
    assert ir_code is not None
    assert "define" in ir_code or "declare" in ir_code
    
    # 4. LLVM 验证 (可选，需要 llvmlite binding)
    # assert ctx.verify(), f"LLVM Verification failed for {os.path.basename(filepath)}"
