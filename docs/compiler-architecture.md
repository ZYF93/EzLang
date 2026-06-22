# EzLang 编译器架构

[English](en/compiler-architecture.md)

EzLang 编译器采用小型分层结构，目标是把 `.ez` 源码转换为 LLVM IR，并由 CLI 进一步生成目标平台对象文件。

## 编译阶段

1. **词法与语法分析**
   - 语法定义唯一源文件位于 [grammar/EzLang.g4](../grammar/EzLang.g4)。
   - 使用 ANTLR4 生成 Python 解析器到 [compiler/src/parser/](../compiler/src/parser/)，该目录下的 `EzLang*.py` / `*.tokens` / `*.interp` 是生成物。
   - 解析入口是 `compilationUnit`。

2. **语义分析**
   - 实现位于 [compiler/src/semantic/analyzer.py](../compiler/src/semantic/analyzer.py)。
   - 负责符号表、作用域、类型检查、flow suspend point 分析、extern 与 declare 关联。
   - 符号和类型结构位于 [compiler/src/semantic/symbols.py](../compiler/src/semantic/symbols.py)。

3. **LLVM IR 生成**
   - 实现位于 [compiler/src/codegen/llvm_codegen.py](../compiler/src/codegen/llvm_codegen.py)。
   - 使用 llvmlite 构建 Module、Function、BasicBlock 与指令。
   - 内建 Arena、Dict、Flow hook 和部分标准库 intrinsic 在此层生成。

4. **CLI 工具链**
   - 实现位于 [cli/ez.py](../cli/ez.py)。
   - 负责读取 `project.toml`、发现 import 依赖、调用语义分析和 codegen、写出 `.ll` / `.o`，并在本机目标下链接运行。

## 重要数据流

```text
.ez 源码
  -> ANTLR Lexer/Parser
  -> Parse Tree
  -> SemanticAnalyzer
  -> LLVMCodeGenerator
  -> LLVM IR
  -> object / executable
```

## 模块与标准库

- 用户源码通过 `from "path" import { ... }` 导入模块。
- CLI 会先展开依赖图，再把源码按依赖顺序合并编译。
- 标准库位于 [packages/std/](../packages/std/)。
- 标准库上层 `.ez` 文件只暴露统一 API；平台实现通过 `@std/native/*.c` 或 `@std/emcc/*.js` 封装。

## 内存模型

- 编译器内建 Arena 分配器，默认用于聚合值和临时结构。
- 块作用域进入时保存 Arena 游标，退出时恢复。
- 跨作用域返回聚合值时按值加载，避免返回已回收区域的指针。

## Flow 模型

- `flow {}` 在语义层记录阻塞调用和依赖关系。
- LLVM 层插入 `__ezrt_flow_enter`、`__ezrt_flow_exit`、`__ezrt_sleep`、`__ezrt_race_i32`、`__ezrt_task_start_i32` / `__ezrt_task_start_env_i32` / `__ezrt_task_join_i32` 等运行时 hook。
- Linux/macOS/Windows/Android/iOS 通过 `packages/std/native/runtime.c` 提供 `sleep`、`race(pl)` 和 flow 内 `I32` `parallel` 的基础任务运行时；emcc 通过 `packages/std/emcc/runtime.js` 与 Asyncify 提供可挂起和恢复的协程运行时。捕获外层局部变量的 `parallel` 会使用共享存储槽任务环境；组合表达式或非 `I32` 返回类型保持同步协作 lowering。
- 这些 hook 是稳定 ABI 边界，后续可在不改变 EzLang 语法的前提下替换为更完整的平台调度器。

## 外部链接

- `extern "..." for target` 会被语义层和 codegen 按目标过滤。
- `declare` 默认绑定到最近的 active extern。
- `std/mem` 的 `copy` / `set` / `allocRaw` 是 compiler builtin，不需要 extern。
- `std/collections` 的 `List`/`Dict` 泛型扩展通过标准库公开 API 声明，由编译器单态化并 lowering，不需要外部 C/JS extern。
- `std/stream` 当前使用固定 `Stream { handle, kind }` ABI 暴露内存/Blob 流、文件流和 TCP 连接流，以及进程管道流；`std/compress` 的流式压缩/解压复用同一结构。
