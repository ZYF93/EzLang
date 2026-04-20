"""
Integrated Acceptance Tests for EzLang.
Loads and compiles all .ez files in the examples directory.
"""

import pytest
import os
from ezlang.compiler import EzLangCompiler

EXAMPLES_DIR = "examples"

def get_example_files():
    files = []
    if os.path.exists(EXAMPLES_DIR):
        for f in os.listdir(EXAMPLES_DIR):
            if f.endswith(".ez"):
                files.append(f)
    return files

@pytest.mark.parametrize("filename", get_example_files())
def test_acceptance_compile(filename):
    """验证示例文件能否成功编译生成 IR"""
    path = os.path.join(EXAMPLES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    
    compiler = EzLangCompiler()
    # 如果编译过程中抛出异常，测试将失败
    ir_code = compiler.compile(source)
    
    assert ir_code is not None
    assert "target triple" in ir_code
    print(f"\nSuccessfully compiled {filename}")
