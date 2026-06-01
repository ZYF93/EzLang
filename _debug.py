import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'compiler', 'src'))
from codegen.llvm_codegen import compile_source

# Simple test
module, errors = compile_source('const x: I32 = 42;')
print("Module:", str(module))
print("Globals:", list(module.globals.keys()) if hasattr(module, 'globals') else 'N/A')
