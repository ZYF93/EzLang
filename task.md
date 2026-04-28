# EzLang 全流程开发任务规划 (Full Project Task List)

本项目采用 **TDD (测试驱动开发)** 模式。每一项功能的实现必须伴随测试用例及 `examples/` 下的源码文件。

> [!IMPORTANT]
> **文法变更流程**：
> 每当修改 `grammar/EzLang.g4` 后，必须运行以下命令重新生成 Python 解析器代码：
> ```bash
> antlr4 -Dlanguage=Python3 -visitor -no-listener grammar/EzLang.g4 -o compiler/generated
> ```
> 确保 `compiler/` 中的逻辑与最新文法同步。

---

## 🛠 阶段一：文法定义与基础设施 (Grammar & Infra)

- [ ] **1.1 核心词法解析 (Lexer)**
  - [ ] 关键字、操作符、基础字面量 (Int, Float, Str, Bool)
  - [ ] 缩进与换行处理逻辑
- [ ] **1.2 语法规则定义 (Parser)**
  - [ ] 表达式优先级、语句块、函数声明、结构体定义
  - [ ] **验收标准**：`examples/hello.ez` 能通过 `antlr4-parse` 生成完整语法树。
- [ ] **1.3 编译器框架搭建**
  - [ ] 异常处理系统：实现带位置信息的 `CompileError`
  - [ ] LLVM 环境：初始化 `llvmlite` 模块与全局上下文 (Module, IRBuilder)
  - [ ] **验收标准**：能够打印格式化的错误日志并定位到行列。

## 🧠 阶段二：编译器核心 (Compiler Core - TDD Focus)

### 2.1 变量与类型系统
- [ ] **基础变量**：`let`, `const`, `static` 的作用域绑定与内存分配 (`alloca`)
- [ ] **基础类型**：I8/32/64, U8/32/64, F32/64, Bool, Void 映射
- [ ] **字符串**：实现 `Str` 的底层表示（i8 指针 + 长度）
- [ ] **测试文件**：`examples/vars.ez`, `examples/types.ez`
- [ ] **验收标准**：LLVM IR 正确生成变量分配指令。

### 2.2 运算符与表达式
- [ ] **算术与位运算**：实现所有基础二元及一元运算符
- [ ] **SIMD 支持**：实现 `Vec<T>[N]` 类型及并行指令映射
- [ ] **测试文件**：`examples/operators.ez`
- [ ] **验收标准**：向量加法正确生成 `vadd` 或对应 LLVM 向量指令。

### 2.3 流程控制 (无 If 模式)
- [ ] **条件表达式**：实现 `? :` 语法及短路求值逻辑
- [ ] **循环系统**：实现 `loop in` 范围遍历与无限循环
- [ ] **模式匹配**：实现 `match` 块及 `break`/`continue` 状态控制
- [ ] **测试文件**：`examples/control.ez`
- [ ] **验收标准**：通过 `lli` 运行生成的 IR，输出符合预期分支。

### 2.4 函数与高级调用
- [ ] **参数管理**：实现命名参数映射、默认值及 `this` 引用绑定
- [ ] **柯里化**：实现 `?` 占位符产生的闭包构造
- [ ] **异步编程**：实现 `async/await` 关键字及 Promise/Task 状态机
- [ ] **测试文件**：`examples/functions.ez`
- [ ] **验收标准**：验证函数部分应用后生成的匿名类/结构体符合闭包协议。

### 2.5 复杂数据类型与鸭子类型
- [ ] **结构体 (Struct)**：实现定义、实例化及字段平铺展开 (`...Base`)
- [ ] **字典 (Dict)**：实现基于哈希表的字面量初始化与动态键访问
- [ ] **类型别名 (Type Alias)**：实现形状定义与鸭子类型验证逻辑
- [ ] **复合类型**：实现 `Type?` (Option) 与 `Type1 | Type2` (Union) 的 Tagged Union 表示
- [ ] **测试文件**：`examples/structs.ez`, `examples/types.ez`
- [ ] **验收标准**：Dict 匹配 Shape 别名时无编译错误。

### 2.6 内存模型 (Arena)
- [ ] **Arena 管理器**：实现作用域相关的游标管理逻辑
- [ ] **值语义复制**：实现跨作用域返回时的全量 Deep Copy
- [ ] **验收标准**：生成的 IR 在每个 Block 结束处正确回退游标。

### 2.7 元编程与语法糖
- [ ] **装饰器**：实现 `@Dec` 语法及 `Meta<T>` 代理对象拦截
- [ ] **Tagged Syntax**：实现 XML 风格语法向函数调用的翻译
- [ ] **语法糖**：实现管道 `->`、字符串插值 `{{}}`
- [ ] **验收标准**：插值语法正确转换为 `stdlib.join` 调用。

## 📚 阶段三：标准库与模块系统 (Stdlib & Modules)

### 3.1 模块管理
- [ ] **导入导出**：实现 `import`, `export`, `from` 的符号解析
- [ ] **外部链接**：实现 `declare` 语法与 C ABI 外部符号链接
- [ ] **测试文件**：`examples/module_test.ez`

### 3.2 核心标准库
- [ ] **内建对象**：实现 `Date`, `Error`, `Blob` 结构体及内建方法
- [ ] **系统接口**：实现 `print`, `readFile`, `now`, `args`, `env` 等 API
- [ ] **WASI 支持**：实现针对 WASM 目标的系统调用映射
- [ ] **测试文件**：`examples/wasi_test.ez`
- [ ] **验收标准**：`ez build --os wasi` 产物能在 `wasmtime` 运行。

## 🔧 阶段四：工具链开发 (Toolchain)

- [ ] **4.1 CLI 核心**：实现 `ez` 基础命令解析
- [ ] **4.2 构建系统**：基于 `project.toml` 实现多目标 (`[[output]]`) 编译
- [ ] **4.3 包管理器**：实现 `ez install` 处理本地、Workspace 及远程依赖
- [ ] **4.4 代码格式化**：实现 `ez fmt` (基于 ANTLR4 Visitor 重新生成源码)
- [ ] **验收标准**：通过一条命令完成全平台的 Cross-Compile。

## 🔌 阶段五：编辑器生态 (LSP & Extension)

- [ ] **5.1 语法高亮**：完善 VSCode `.tmLanguage` 配置
- [ ] **5.2 语言服务器 (LSP)**
  - [ ] 基础：错误诊断 (Diagnostics) 与文档符号 (Symbols)
  - [ ] 进阶：自动补全 (Completion) 与悬停提示 (Hover)
- [ ] **验收标准**：VSCode 中能正确提示结构体字段及类型。

## 🚀 阶段六：发布与文档 (Release)
- [ ] 编写《EzLang 用户手册》与《标准库 API 参考》
- [ ] 实现 `ez release` 命令并配置默认中心仓库
- [ ] **验收标准**：本项目自身能够通过 `ez build` 完成自举编译。
