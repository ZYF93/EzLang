"""
EzLang LLVM Backend Module
"""

class LLVMBackend:
    # 常用目标三元组定义
    TARGET_TRIPLES = {
        "wasi": "wasm32-unknown-wasi",
        "wasm": "wasm32-unknown-unknown",
        "native": "x86_64-pc-windows-msvc", # 默认 Windows，可根据运行环境动态调整
        "linux": "x86_64-unknown-linux-gnu"
    }

    def __init__(self, ir_code, target="wasi"):
        self.ir_code = ir_code
        self.target = target

    def generate_llvm_ir(self):
        triple = self.TARGET_TRIPLES.get(self.target, self.target)
        
        # 在 IR 字符串中注入目标三元组
        # 如果 IR 已经包含 target triple，我们需要替换它
        header = f'target triple = "{triple}"\n'
        
        # 针对 WASM 的特殊配置 (DataLayout)
        if "wasm32" in triple:
            header += 'target datalayout = "e-m:e-p:32:32-i64:64-n32:64-S128"\n'
        
        # 将 header 插入到 IR 代码的最前面
        # 如果原始 IR 已经有 target triple，先去掉它
        lines = self.ir_code.splitlines()
        filtered_lines = [l for l in lines if not l.startswith("target triple") and not l.startswith("target datalayout")]
        
        return header + "\n".join(filtered_lines)