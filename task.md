# EzLang TDD 开发任务

## 开发方式
- 采用 TDD（测试驱动开发）模式。
- 每个功能先写测试用例，再编写 `.ez` 验收示例文件，最后实现编译器使测试和验收示例全部通过。
- 测试用例应直接引用或加载对应 `.ez` 文件，以保证实现与示例文件一致。
- 任务拆解为可验证的最小单元，适合 AI 按步骤完成。
- **ANTLR 依赖**：Lexer 和 Parser 基于 ANTLR4 生成。每次修改语法规则时，必须先修改 `grammar/EzLang.g4`，然后执行 `antlr4 -Dlanguage=Python3 -o src/ezlang/antlr_generated grammar/EzLang.g4` 重新生成代码。禁止手动修改 `src/ezlang/antlr_generated/` 下的生成文件。

## 验收标准
- 每个任务项都有至少一个测试用例，并引入对应的 `.ez` 验收文件。
- 编译器可以成功编译对应 `.ez` 文件，且输出符合规范。
- 功能实现应符合 `docs/doc.md` 中的语言规范。
- 任务通过勾选清单方式跟踪完成状态。
- **增强验收**：每个 `.ez` 文件应包含正面和负面测试用例（如类型不匹配时应报错），以验证编译器错误处理。

## 编译器分层
- [x] 词法分析（lexer）
- [x] 语法分析（parser）
- [ ] 语义分析（semantic analyzer）
- [ ] 中间表示与优化（IR/优化）
- [ ] 后端生成（LLVM backend）
- [ ] 测试驱动实现

## 任务清单

### 0. 环境与 WASI 适配层
- [x] 实现最小 WASI 运行时模拟（用于测试），支持 `print` 和内存分配（`memory.grow`）。
- [x] 编写 `wasi_test.ez`，验证 `print` 函数调用和基本内存操作。
- [ ] 确保测试环境能跑通 `print` 和内存分配，否则后续任务无法验证结果。

### 1. 类型系统与系统接口
- [x] 编写 `types.ez`，验证基本类型 `I8/I32/I64/U8/U32/U64/F32/F64` 解析与使用。
- [x] 在 `types.ez` 中验证 `Str/Bool/Void` 类型识别与类型注解。
- [x] 验证 WASI 核心函数 `fd_write` 的内置声明。
- [x] 实现类型系统解析，使 `types.ez` 通过编译。

### 2. 变量声明与值语义
- [ ] 编写 `vars.ez`，验证 `let/const/static` 声明语法。
- [ ] 实现作用域与 Arena 回退机制，确保 `vars.ez` 编译通过。

### 3. 结构体与组合语法
- [ ] 编写 `structs.ez`，验证结构体定义、方法与 `this`。
- [ ] 实现结构体语义，使 `structs.ez` 编译通过。

### 4. 控制流与表达式
- [ ] 编写 `control.ez`，验证 `loop`, `if-else`, `match`。
- [ ] 实现控制流逻辑，让 `control.ez` 编译通过。

### 5. 函数与上下文绑定
- [ ] 编写 `functions.ez`，验证命名参数、默认参数。
- [ ] 实现函数调用语义，使 `functions.ez` 编译通过。

### 8. Arena 内存模型
- [ ] 编写 `arena.ez`，验证作用域内存分配与回退。
- [ ] 在 `arena.ez` 中验证跨作用域返回值复制到父 Arena。
- [ ] 实现 Arena 内存管理骨架。

### 10. 工程化工具链与多目标编译
- [x] 定义 `config.json` 规范。
  - `project.entry`: 入口文件。
  - `targets`: 支持 `arch` (如 wasm32/x86_64), `os` (如 wasi/linux/windows), `optimization_level` (如 O0-O3), `output`。
  - `dependencies`: 依赖模块路径映射。
- [ ] 实现编译器读取 `config.json` 自动化构建。
- [ ] 实现 `LLVMBackend` 对多目标三元组的支持。
- [ ] 实现依赖路径检索初步逻辑。
- [ ] 实现 `ezlang` 命令行工具：
  - `ezlang build [--target <name>]`: 基于 config.json 构建。
  - `ezlang run <file>`: 快速运行脚本。
  - `ezlang test / fmt / lint`: 辅助工具链雏形。

### 11. 运算符与表达式
- [ ] 编写 `operators.ez`，验证算术、逻辑、位运算。
- [ ] 实现运算符语义，使 `operators.ez` 编译通过。

## 交付说明
- 每个任务完成后，在 `task.md` 中打勾对应项。
- 使用对应 `.ez` 示例文件作为验收标准。
