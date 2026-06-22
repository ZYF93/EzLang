# EzLang Compiler Architecture

[中文](../compiler-architecture.md)

The EzLang compiler uses a small layered architecture. Its goal is to turn `.ez` source code into LLVM IR, while the CLI drives object and platform artifact generation.

## Compilation Stages

1. **Lexing and parsing**
   - The single grammar source is [grammar/EzLang.g4](../../grammar/EzLang.g4).
   - ANTLR4 generates the Python parser into [compiler/src/parser/](../../compiler/src/parser/). `EzLang*.py`, `*.tokens`, and `*.interp` files in that directory are generated artifacts.
   - The parser entrypoint is `compilationUnit`.

2. **Semantic analysis**
   - Implemented in [compiler/src/semantic/analyzer.py](../../compiler/src/semantic/analyzer.py).
   - Handles symbol tables, scopes, type checking, Flow suspend-point analysis, and `extern` / `declare` association.
   - Symbol and type structures live in [compiler/src/semantic/symbols.py](../../compiler/src/semantic/symbols.py).

3. **LLVM IR generation**
   - Implemented in [compiler/src/codegen/llvm_codegen.py](../../compiler/src/codegen/llvm_codegen.py).
   - Uses llvmlite to build modules, functions, basic blocks, and instructions.
   - Built-in Arena, Dict, Flow hooks, and selected standard-library intrinsics are generated at this layer.

4. **CLI toolchain**
   - Implemented in [cli/ez.py](../../cli/ez.py).
   - Reads `project.toml`, discovers import dependencies, runs semantic analysis and codegen, writes `.ll` / `.o`, and links/runs native targets.

## Data Flow

```text
.ez source
  -> ANTLR Lexer/Parser
  -> Parse Tree
  -> SemanticAnalyzer
  -> LLVMCodeGenerator
  -> LLVM IR
  -> object / executable
```

## Modules and Standard Library

- User code imports modules with `from "path" import { ... }`.
- The CLI expands the dependency graph first, then merges sources in dependency order for compilation.
- The standard library is in [packages/std/](../../packages/std/).
- Standard-library `.ez` files expose the unified API. Platform implementations are wrapped through `@std/native/*.c` or `@std/emcc/*.js`.

## Memory Model

- The compiler has a built-in Arena allocator for aggregate values and temporaries.
- Entering a block scope saves the Arena cursor; leaving the block restores it.
- Aggregate values returned across scopes are loaded by value to avoid pointers into reclaimed Arena regions.

## Flow Model

- `flow {}` records blocking calls and dependencies in semantic analysis.
- LLVM generation inserts runtime hooks such as `__ezrt_flow_enter`, `__ezrt_flow_exit`, `__ezrt_sleep`, `__ezrt_race_i32`, `__ezrt_task_start_i32`, `__ezrt_task_start_env_i32`, and `__ezrt_task_join_i32`.
- Linux/macOS/Windows/Android/iOS use `packages/std/native/runtime.c` for the minimal task runtime behind `sleep`, `race(pl)`, and `I32` `parallel` inside Flow. emcc uses `packages/std/emcc/runtime.js` plus Asyncify for suspendable and resumable coroutine behavior. `parallel` with outer captures uses a shared-storage task environment; compound expressions or non-`I32` return types keep synchronous cooperative lowering.
- These hooks are stable ABI boundaries, so a more complete platform scheduler can replace them without changing EzLang syntax.

## External Linking

- `extern "..." for target` is filtered by semantic analysis and codegen according to the target.
- `declare` binds to the nearest active extern by default.
- `std/mem` functions `copy`, `set`, and `allocRaw` are compiler builtins and do not need extern declarations.
- `std/collections` `List`/`Dict` generic extensions are exposed as standard-library API declarations, then monomorphized and lowered by the compiler. They do not need external C/JS externs.
- `std/stream` currently exposes a fixed `Stream { handle, kind }` ABI for memory/Blob streams, file streams, TCP connection streams, and process pipe streams. `std/compress` streaming compression/decompression reuses the same structure.
