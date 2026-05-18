# EzLang 编程语言

EzLang 是一门以表达式为中心、采用值语义为主的系统编程语言。它结合现代类型系统、Arena 内存模型与 Flow 并发语义，面向高性能系统级开发，并支持跨平台编译到本地和 WebAssembly。

## 🚀 核心特性

- **表达式优先**：几乎所有语法结构都可作为表达式使用，支持更紧凑的组合逻辑。
- **值语义与 Arena 内存模型**：默认按值拷贝，Arena 自动回收临时内存，实现无显式释放的高效内存管理。
- **现代类型系统**：支持泛型、可选类型 `?`、联合类型 `|`、函数类型、List/Vec、Dict、结构体和类型别名。
- **鸭子类型验证**：`type` 定义的形状可与任意包含所需字段的结构或字典自动匹配。
- **结构体组合与方法**：支持 `...Base` 结构体展开、字段默认值、命名初始化与显式 `this` 绑定方法。
- **Flow 并发运行时**：内置 `flow {}` 并发模型，可将阻塞 I/O 转为 suspend point，实现协作式调度。
- **统一标准库设计**：标准库接口在不同目标平台上保持一致，底层实现基于平台感知系统调用。
- **跨平台编译**：支持 `x86_64` / `aarch64` / `arm` / `wasm32`，可构建 Windows、macOS、Linux、Android、iOS 和 Emscripten 目标。

## 📘 语言与运行时亮点

- **类型系统**：包含基本数值类型、字符串、布尔、Void、列表、SIMD 向量、可选与联合类型。
- **函数与柯里化**：支持命名参数、默认参数和部分应用，`?` 可作为占位符生成待定函数。
- **结构体与组合**：结构体支持泛型、字段展开、方法定义与默认值；内置 `Date`、`Error`、`Blob` 等系统结构体。
- **Arena 语义**：每个作用域对应 Arena 游标，作用域结束时回退游标，跨作用域返回自动复制到父级 Arena。
- **平台无关标准库**：统一 I/O、文件系统、网络、OS、时间等接口，移动端 UI 由独立包 `ez-android-ui` / `ez-ios-ui` / `ez-web-ui` 提供。

## 🧭 项目结构

```text
EzLang/
├── compiler/       # 编译器核心：ANTLR4 语法、词法、语义和 LLVM IR 生成
├── docs/           # 语言规格、工具链与标准库设计文档
├── packages/       # 标准库、UI库等
├── grammar/        # ANTLR4 文法定义文件
├── examples/       # EzLang 语法与语言特性示例
├── tests/          # 测试套件
├── LICENSE         # MIT 许可证
├── project.toml    # 项目配置与编译目标定义
└── README.md       # 项目说明文档
```

## 🛠 工具链概览

EzLang 使用 `project.toml` 作为项目清单，`ez` CLI 提供完整的构建和发布体验。

- `ez install`：解析 `project.toml` 的 `[deps]` 节点，安装本地依赖、远程版本依赖或 Workspace 内部模块。
- `ez build`：根据 `[[output]]` 目标编译项目，生成多平台产物。
- `ez run`：构建并执行本地可执行程序。
- `ez fmt`：格式化所有 `.ez` 源码。
- `ez release`：将包发布到远端注册表。

### `project.toml` 关键字段

- `[project]`：`name`, `version`, `description`, `main`, `public`, `registry`, `optimize`
- `[workspace]`：`members` 用于 Monorepo 子包管理
- `[[output]]`：定义 `arch`, `os`, `dir`, `sdk` 等多平台编译目标
- `[[plugins]]`：编译器插件配置
- `[deps]`：本地、远端和 Workspace 依赖声明

## 📦 标准库设计

EzLang 标准库遵循“统一 API，平台感知实现”的设计理念：

- 所有平台共享相同接口
- 底层实现根据目标平台自动选择系统调用或运行时绑定
- 阻塞 I/O 在 `flow {}` 内为 suspend point，在 `flow` 外作为同步阻塞行为
- 移动端 UI 通过 `ez-android-ui`、`ez-ios-ui` 和 `ez-web-ui` 提供独立的原生/DOM 绑定

## 🔧 快速开始

### 依赖安装
```bash
pip install -r compiler/requirements.txt
```

### 构建项目
```bash
ez build
```

### 运行示例
```bash
ez run
```

## 📝 示例代码

```ez
type Named = { name: Str }
struct User { ...Named; age: I32 }
let person: Named = { name = "Alice", extra = "data" }

struct Pair<T, U> {
    first: T
    second: U
    swap = (this: Pair<T, U>) => Pair<U, T>(first = this.second, second = this.first)
}

const main = () => {
    let p = Pair(first = 42, second = "hello")
    let swapped = p.swap()
    swapped.first -> print(msg = %)
}
```

## 📚 进一步阅读

详见 `docs/doc.md`、`docs/toolchain.md` 与 `docs/stdlib.md`，了解完整语言规格、工具链配置和标准库设计。

## 📜 许可证

本项目采用 [MIT](LICENSE) 许可证。
