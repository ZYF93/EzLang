# EzLang

EzLang 是一门静态类型、值语义的编程语言，设计用于高性能和安全性。它编译到 LLVM IR，支持 Arena 内存管理、显式控制流和元编程。

## 特性

- **值语义**：所有赋值都是深拷贝，无隐式共享。
- **Arena 内存**：作用域内自动内存管理，无手动释放。
- **类型系统**：强类型，支持结构体、联合、泛型、函数类型。
- **控制流**：无 `if/else`，使用 `? :` 表达式；模式匹配 `match`。
- **元编程**：装饰器 `@Dec` 包装变量，拦截访问。
- **模块**：导入/导出，支持外部链接（C、Python 等）。

## 安装

需要 Rust 和 LLVM。

```bash
git clone https://github.com/yourrepo/ezlang.git
cd ezlang
cargo build --release
```

## 用法

编译 EzLang 文件：

```bash
cargo run -- examples/hello.ez
```

输出 LLVM IR 到 `output.ll`，然后用 `lli output.ll` 运行。

## 语言规格

详见 [docs/doc.md](docs/doc.md)。

## 实现状态

- ✅ 基本语法解析（let, 表达式）
- ✅ 类型检查（基础）
- ✅ Arena 内存（模拟）
- 🚧 LLVM 代码生成（需要 LLVM 安装）
- 🚧 高级特性（match, 函数, 结构体）

## 贡献

欢迎 PR！从扩展解析器或添加代码生成开始。

## 许可证

见 LICENSE。