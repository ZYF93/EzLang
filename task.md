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
  - 验收：针对基础语法和关键字的 `.ez` 示例，lexer 能正确生成 token 序列。
  - 例：`types.ez`、`vars.ez` 中的关键语法构件必须被正确识别。
- [x] 语法分析（parser）
  - 验收：parser 能生成正确 AST，且语法错误能被准确定位。
  - 例：`structs.ez`、`control.ez` 中的结构体、循环、条件语句应生成有效 AST。
- [ ] 语义分析（semantic analyzer）
  - 验收：类型检查、作用域解析、变量声明校验、`this` 绑定、泛型推断等语义规则通过。
  - 例：`functions.ez`、`safety.ez` 中的类型检查和调用规则应返回正确结果。
- [ ] 中间表示与优化（IR/优化）
  - 验收：AST 转换为中间表示，支持必要的类型信息传递和简易优化。
  - 例：`operators.ez` 和 `simd.ez` 的表达式应生成合理 IR。
- [ ] 后端生成（LLVM backend）
  - 验收：生成 LLVM IR 或汇编，并且能编译/链接成可执行或目标文件。
  - 例：`arena.ez`、`modules.ez` 等示例在 LLVM 生成阶段不能报错。
- [ ] 测试驱动实现
  - 验收：每个分层任务至少有一个测试用例直接引用 `.ez` 文件，并验证该层输出或错误信息。

## 任务清单

- [ ] 为每个 `.ez` 验收文件编写测试用例，使测试直接引用或加载对应 `*.ez` 文件并验证编译器行为。

### 0. 环境与 WASI 适配层
- [x] 实现最小 WASI 运行时模拟（用于测试），支持 `print` 和内存分配（`memory.grow`）。
- [x] 编写 `wasi_test.ez`，验证 `print` 函数调用和基本内存操作。
- [x] 确保测试环境能跑通 `print` 和内存分配，否则后续任务无法验证结果。

### 1. 类型系统与系统接口
- [x] 编写 `types.ez`，验证基本类型 `I8/I32/I64/U8/U32/U64/F32/F64` 解析与使用。
- [x] 在 `types.ez` 中验证 `Str/Bool/Void` 类型识别与类型注解。
- [x] 在 `types.ez` 中验证 `Type[]` 与 `Type[n]` 的数组语法。
- [x] 在 `types.ez` 中验证 `Vec<Type>[N]` SIMD 向量类型解析。
- [x] 在 `types.ez` 中验证 `Type?` 可选类型和 `Type1 | Type2` 联合类型。
- [ ] 验证 WASI 核心函数 `fd_write` 的内置声明。
- [ ] 实现类型系统解析，使 `types.ez` 通过编译，并确保基础类型与 WASI I/O 兼容。

### 2. 变量声明与值语义
- [x] 编写 `vars.ez`，验证 `let/const/static` 声明语法。
- [x] 在 `vars.ez` 中验证显式类型注解 `: Type` 和默认初始化。
- [x] 在 `vars.ez` 中验证值语义拷贝 `let copy = count`。
- [ ] 实现作用域与 Arena 回退机制，确保 `vars.ez` 编译通过且资源安全。

### 3. 结构体与组合语法
- [ ] 编写 `structs.ez`，验证 `struct Name { ... }` 定义和字段初始化。
- [ ] 在 `structs.ez` 中验证默认字段值和命名初始化 `Name(field = value)`。
- [ ] 在 `structs.ez` 中验证 `...Base` 字段展开行为。
- [ ] 在 `structs.ez` 中验证方法定义与 `this` 调用语义。
- [ ] 实现结构体语义，使 `structs.ez` 编译通过。

### 4. 控制流与表达式
- [ ] 编写 `control.ez`，验证 `loop { ... }` 和 `loop i in 0...10 { ... }`。
- [ ] 在 `control.ez` 中验证条件表达式 `cond ? expr : expr` 与单分支语句。
- [ ] 在 `control.ez` 中验证 `match { ... }` 和顺序匹配行为。
- [ ] 在 `control.ez` 中验证 `break/continue` 与 `catch { throw ... }`。
- [ ] 实现控制流逻辑，让 `control.ez` 编译通过。

### 5. 函数与上下文绑定
- [ ] 编写 `functions.ez`，验证普通函数和 `async` 函数语法。
- [ ] 在 `functions.ez` 中验证 `this` 显式绑定与 `obj.fn()` 调用等价性。
- [ ] 在 `functions.ez` 中验证命名参数、默认参数和占位柯里化语法。
- [ ] 实现函数调用语义，使 `functions.ez` 编译通过。

### 6. 元编程与装饰器
- [ ] 编写 `decorators.ez`，验证 `@Dec let x = value` 的语法解析。
- [ ] 在 `decorators.ez` 中验证 `Meta<T>` getter/setter 拦截行为。
- [ ] 实现装饰器语义，使 `decorators.ez` 编译通过并触发拦截逻辑。

### 7. 安全机制与链接
- [ ] 编写 `safety.ez`，验证 `Type! expr` 类型断言语法。
- [ ] 在 `safety.ez` 中验证 `typeof` 运行时类型判断。
- [ ] 在 `safety.ez` 中验证 `declare` 外部符号声明语法。
- [ ] 实现安全机制与外部链接，使 `safety.ez` 编译通过。

### 8. Arena 内存模型
- [ ] 编写 `arena.ez`，验证作用域内存分配与回退。
- [ ] 在 `arena.ez` 中验证临时值作用域结束回收。
- [ ] 在 `arena.ez` 中验证跨作用域返回值复制到父 Arena。
- [ ] 在语义分析器中实现“生存期标记（Lifetime Tagging）”，决定 IR 阶段是否插入 `memcpy` 指令。
- [ ] 实现 Arena 内存管理，使 `arena.ez` 编译通过且无悬垂引用。

### 9. 语法糖与标记语法
- [ ] 编写 `syntax_sugar.ez`，验证管道语法 `value -> fn(a = %)` 重写。
- [ ] 在 `syntax_sugar.ez` 中验证字符串插值 `"Hello {{name}}, count is {{count}}"`。
- [ ] 在 `syntax_sugar.ez` 中验证标记语法 `<text color="blue"> ... </text>` 转换。
- [ ] 实现语法糖支持，使 `syntax_sugar.ez` 编译通过。

### 10. 模块系统
- [ ] 编写 `modules.ez`，验证 `from "./path" import {item}` 和别名导入。
- [ ] 在 `modules.ez` 中验证 `export` 导出项。
- [ ] 在 `modules.ez` 中验证 `.d.ez` 自动导入外部声明。
- [ ] 实现模块解析与链接，使 `modules.ez` 编译通过。

### 11. 运算符与表达式
- [ ] 编写 `operators.ez`，验证算术运算 `+ - * / %`。
- [ ] 在 `operators.ez` 中验证位运算 `& | ^ << >>`。
- [ ] 在 `operators.ez` 中验证逻辑短路 `&& || !`。
- [ ] 在 `operators.ez` 中验证比较运算 `== != < > <= >=`。
- [ ] 在 `operators.ez` 中验证复合赋值 `+= -= *= /= %= &= |= ^= <<= >>=`。
- [ ] 实现运算符语义，使 `operators.ez` 编译通过。

### 12. SIMD 语法
- [ ] 编写 `simd.ez`，验证 `Vec<Type>[N]` 向量类型解析。
- [ ] 在 `simd.ez` 中验证 `Vec[1, 2, 3, 4]` 字面量和类型推断。
- [ ] 在 `simd.ez` 中验证向量与向量、向量与标量运算。
- [ ] 在 `simd.ez` 中验证内存对齐校验，确保 Arena 分配器处理 `Vec` 时正确对齐（如 16 或 32 字节）。
- [ ] 实现 SIMD 支持，使 `simd.ez` 编译通过。

## 交付说明
- 每个任务完成后，在 `task.md` 中打勾对应项。
- 使用对应 `.ez` 示例文件作为验收标准，并确保编译器能成功编译这些文件。
- 所有任务项打勾后，整体验收通过。
- **开发优先级顺序（按依赖关系）**：
  1. 基础设施：Lexer -> Parser -> 基础 IR 生成。
  2. 内存骨架：任务 8 (Arena) 必须尽早开始，因为变量（任务 2）和结构体（任务 3）的分配都依赖它。
  3. 计算核心：任务 11 (运算符) -> 任务 1 (类型系统)。
  4. 高级逻辑：任务 4 (控制流) -> 任务 5 (函数)。
  5. 跨平台/集成：任务 10 (模块) -> 任务 12 (SIMD)。
  6. 语法糖/美化：任务 9 (语法糖) -> 任务 6 (装饰器)。
