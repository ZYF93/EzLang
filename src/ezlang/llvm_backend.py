"""
EzLang LLVM Backend Module
"""

class LLVMBackend:
    def __init__(self, ir_code):
        self.ir_code = ir_code

    def generate_llvm_ir(self):
        # Currently, the IRGenerator already produces LLVM IR strings.
        # We just pass it through until we add optimization passes.
        return self.ir_code