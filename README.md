# EzLang 编程语言

EzLang 是一门以表达式为中心、采用值语义为主的系统编程语言。它旨在结合高性能的系统级编程能力与现代化的语言特性，支持强类型、泛型、内置结构体、可选类型、联合类型、异步编程与元编程，并采用高效的 Arena 内存模型进行内存管理。

## 🚀 核心特性

- **以表达式为中心**：几乎所有语法结构都是表达式，支持简洁的流式编程。
- **值语义优先**：默认采用值拷贝，通过 Arena 内存模型实现无锁并发与高效内存回收。
- **现代类型系统**：支持泛型、联合类型 (`|`)、可选类型 (`?`)，以及所有类型别名 (`type Alias`) 均支持的鸭子类型验证（Duck Typing）。
- **高性能后端**：基于 LLVM 实现，支持 SIMD 指令集优化，可编译为 Native 汇编或 WASM。
- **强大的元编程**：内置装饰器与标记语法（XML 风格），支持管道操作符 (`->`)。

## 🛠 技术实现

EzLang 的第一版（v1）采用以下技术栈开发：
- **语法解析**：使用 **ANTLR4** 定义严谨的语言文法。
- **逻辑实现**：使用 **Python 3** 编写编译器前端、语义分析及类型检查。
- **后端生成**：通过 **llvmlite** 直接生成 LLVM IR，确保生成的二进制产物具有极致性能。

## 📦 项目架构 (Monorepo)

本项目采用 Monorepo 仓库管理模式，包含以下核心组件：

```text
EzLang/
├── compiler/           # 编译器核心：包含 ANTLR4 文法、语义分析器与 LLVM IR 生成器
├── toolchain/          # 工具链 (ez CLI)：提供安装、构建、格式化及发布功能
├── stdlib/             # 标准库：统一的 API 封装，支持 Native 与 WASI 双目标
├── extensions/         # 开发辅助：包含 LSP (语言服务器) 与 VSCode 插件
├── docs/               # 文档中心：语言规格说明、标准库设计及工具链指南
├── grammar/            # ANTLR4 文法定义
└── examples/           # 示例代码：展示 EzLang 的语法特性与应用场景
```

### 组件说明
1.  **编译器 (`compiler/`)**：负责将 `.ez` 源代码转换为 LLVM IR，处理复杂的泛型单态化与类型推断。
2.  **工具链 (`toolchain/`)**：提供 `ez build`、`ez install` 等命令，基于 `project.toml` 管理项目依赖与多平台产出。
3.  **标准库 (`stdlib/`)**：提供跨平台的内存管理、I/O、文件系统及数据结构扩展。
4.  **LSP & VSCode 插件 (`extensions/`)**：为开发者提供语法高亮、代码补全、错误诊断等现代化编程体验。

## ⌨️ 代码示例

```ez
// 类型别名与鸭子类型验证
type Named = { name: Str }
struct User { ...Named; age: I32 }
let person: Named = { name = "Alice", extra = "data" } // Dict 自动匹配 Named 形状

// 结构体与泛型示例
struct Pair<T, U> {
    first: T
    second: U
    swap = (this: Pair<T, U>) => Pair<U, T>(first = this.second, second = this.first)
}

// 异步与流程控制
async const main = () => {
    let p = Pair(first = 42, second = "hello")
    let swapped = p.swap()
    
    // 使用管道语法打印
    swapped.first -> print(msg = %)
}
```

## 🏗 开始使用

### 安装依赖
确保系统中已安装 Python 3.10+、ANTLR4 和 LLVM 环境。
```bash
pip install -r compiler/requirements.txt
```

### 构建项目
使用工具链进行编译：
```bash
ez build
```

## 📜 许可证

本项目采用 [MIT](LICENSE) 许可证。
