"""
EzLang LLVM 上下文管理器。
负责初始化 llvmlite 模块、IRBuilder 以及目标配置。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import llvmlite.ir as ir
import llvmlite.binding as binding


# ---- 目标平台配置 ----

@dataclass
class TargetConfig:
    """编译目标平台配置，对应 project.toml 中的 [[output]]。"""
    arch: str = "x86_64"
    os: str = "linux"
    output_dir: str = "./dist"

    @property
    def triple(self) -> str:
        """生成 LLVM target triple。"""
        triples = {
            ("wasm", "wasi"):       "wasm32-unknown-wasi",
            ("wasm", "freestanding"): "wasm32-unknown-unknown",
            ("x86_64", "linux"):    "x86_64-unknown-linux-gnu",
            ("x86_64", "windows"):  "x86_64-pc-windows-msvc",
            ("x86_64", "macos"):    "x86_64-apple-darwin",
            ("aarch64", "linux"):   "aarch64-unknown-linux-gnu",
            ("aarch64", "macos"):   "aarch64-apple-darwin",
        }
        return triples.get((self.arch, self.os), f"{self.arch}-unknown-{self.os}")


# ---- LLVM 基础类型注册表 ----

class EzTypes:
    """EzLang 到 LLVM IR 的基础类型映射表。"""

    def __init__(self):
        # 整型
        self.i1 = ir.IntType(1)
        self.i8 = ir.IntType(8)
        self.i32 = ir.IntType(32)
        self.i64 = ir.IntType(64)

        # 浮点
        self.f32 = ir.FloatType()
        self.f64 = ir.DoubleType()

        # Void
        self.void = ir.VoidType()

        # 指针 (i8*) — 用于 Str 和通用指针
        self.ptr_i8 = self.i8.as_pointer()

        # Str = { i64 len, i8* data }
        self.str_type = ir.LiteralStructType([self.i64, self.ptr_i8])

        # Bool = i1
        self.bool = self.i1

        # 类型名到 LLVM 类型的映射
        self._name_map: dict[str, ir.Type] = {
            "I8":   self.i8,
            "I32":  self.i32,
            "I64":  self.i64,
            "U8":   self.i8,      # LLVM 不区分有无符号，在指令层处理
            "U32":  self.i32,
            "U64":  self.i64,
            "F32":  self.f32,
            "F64":  self.f64,
            "Bool": self.bool,
            "Str":  self.str_type,
            "Void": self.void,
        }

    def resolve(self, name: str) -> Optional[ir.Type]:
        """根据 EzLang 类型名解析为 LLVM IR 类型。"""
        return self._name_map.get(name)

    def make_optional(self, inner: ir.Type) -> ir.LiteralStructType:
        """Type? → { i1 has_value, T value }"""
        return ir.LiteralStructType([self.i1, inner])

    def make_list(self, elem: ir.Type) -> ir.LiteralStructType:
        """Type[] → { i64 len, i64 cap, T* data }"""
        return ir.LiteralStructType([self.i64, self.i64, elem.as_pointer()])

    def make_vec(self, elem: ir.Type, count: int) -> ir.VectorType:
        """Vec<T>[N] → <N x T>"""
        return ir.VectorType(elem, count)


# ---- 编译上下文 ----

class CompileContext:
    """
    全局编译上下文，管理 LLVM Module、IRBuilder 和类型系统。
    每个编译单元（源文件）对应一个 CompileContext 实例。
    """

    def __init__(self, module_name: str = "ezlang_module",
                 target: Optional[TargetConfig] = None):
        # 初始化 llvmlite 绑定层
        binding.initialize()
        binding.initialize_native_target()
        binding.initialize_native_asmprinter()

        # LLVM Module
        self.module = ir.Module(name=module_name)
        self.module.triple = (target or TargetConfig()).triple

        # 类型系统
        self.types = EzTypes()

        # 目标配置
        self.target = target or TargetConfig()

        # 符号表栈 (作用域管理)
        self._scope_stack: list[dict[str, ir.Value]] = [{}]

    # ---- 作用域管理 ----

    def push_scope(self) -> None:
        """进入新作用域。"""
        self._scope_stack.append({})

    def pop_scope(self) -> dict[str, ir.Value]:
        """退出当前作用域，返回该作用域的符号表。"""
        if len(self._scope_stack) <= 1:
            raise RuntimeError("Cannot pop global scope")
        return self._scope_stack.pop()

    def define(self, name: str, value: ir.Value) -> None:
        """在当前作用域定义变量。"""
        self._scope_stack[-1][name] = value

    def lookup(self, name: str) -> Optional[ir.Value]:
        """从当前作用域向上查找变量。"""
        for scope in reversed(self._scope_stack):
            if name in scope:
                return scope[name]
        return None

    # ---- 工具方法 ----

    def create_function(self, name: str, ret_type: ir.Type,
                        param_types: list[ir.Type],
                        param_names: Optional[list[str]] = None) -> ir.Function:
        """创建一个 LLVM 函数并返回。"""
        fn_type = ir.FunctionType(ret_type, param_types)
        func = ir.Function(self.module, fn_type, name=name)

        if param_names:
            for arg, pname in zip(func.args, param_names):
                arg.name = pname

        return func

    def create_entry_block(self, func: ir.Function, name: str = "entry") -> ir.IRBuilder:
        """为函数创建入口基本块并返回 IRBuilder。"""
        block = func.append_basic_block(name=name)
        return ir.IRBuilder(block)

    def dump_ir(self) -> str:
        """返回当前模块的 LLVM IR 文本。"""
        return str(self.module)

    def verify(self) -> bool:
        """验证模块 IR 的合法性。"""
        try:
            mod = binding.parse_assembly(str(self.module))
            mod.verify()
            return True
        except Exception:
            return False
