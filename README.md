# EzLang 编程语言

[English](README.en.md)

## 为什么是 EzLang

- **少踩内存坑，也不牺牲速度**：把常见的内存风险尽量交给语言和工具链处理，让开发者把精力放回业务和性能本身。
- **一套代码，走向更多平台**：从本地程序到移动端、WebAssembly，尽量用同一种写法覆盖更多运行环境。
- **读起来像你想的那样**：语法贴近表达意图，控制流、数据结构和函数调用都能自然组合，降低理解和修改成本。
- **AI 能写，人也接得住**：代码保持清晰、显式、可推理，方便人类审查、接手和长期维护。
- **让系统编程变得更轻松**：EzLang 希望把可靠性、性能、并发和跨平台能力放进一套简单顺手的开发体验里。

## 核心特性

EzLang 是一门以表达式为中心、采用值语义为主的系统编程语言。它结合现代类型系统、Arena 内存模型与 Flow 并发语义，面向高性能系统级开发，并支持跨平台编译到本地、移动端和 WebAssembly。

- **表达式优先**：变量、控制流、match、函数调用等语法可自然组合。
- **现代类型系统**：支持泛型、可选类型 `?`、弱引用 `#`、联合类型 `|`、函数类型、List/Vec、Dict、结构体和类型别名。
- **值语义与 Arena 内存模型**：默认按值拷贝，作用域结束自动回收临时内存。
- **结构体组合与方法**：支持 `...Base` 组合、字段默认值、命名初始化和显式 `this` 绑定方法。
- **Flow 并发运行时**：内置 `flow {}` / `parallel {}` / `race(pl)`，native 与 emcc 目标均支持挂起点语义。
- **外部 ABI 链接**：`extern "lib" for target` 配合 `declare` 可调用 C/JS/平台库。
- **统一标准库**：`std/io`、`std/fs`、`std/net/*`、`std/fmt`、`std/collections` 等接口在多目标上保持一致。
- **完整工具链**：CLI、格式化、LSP、VS Code 插件和项目依赖管理都在仓库内提供。

## 安装

基础依赖：Python 3.9+、`git`、本机 C 编译器 `cc`。安装脚本会准备虚拟环境、安装 EzLang CLI 与编译器，并执行一次最小编译校验。

```bash
# 推荐：从官方仓库安装或更新
curl -fsSL https://raw.githubusercontent.com/ZYF93/EzLang/main/install.sh | sh

# 已经 clone 仓库时，从当前源码安装
sh install.sh --local

# 可选：自定义安装目录或跳过 PATH 写入
EZLANG_INSTALL_DIR="$HOME/.ezlang" EZLANG_REGISTER_PATH=0 sh install.sh

# 可选：缺少 Python/git/cc 时尝试用系统包管理器安装基础依赖
EZLANG_INSTALL_DEPS=1 sh install.sh
```

安装完成后打开新的 shell，或手动加载环境：

```bash
source ~/.ezlang/env
ez --version
```

开发源码时也可以使用 editable 安装：

```bash
pip install -e .
```

如果系统 Python 启用了 PEP 668，建议使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 初始化项目

创建新项目：

```bash
ez init my-app
cd my-app
```

初始化后会生成：

```text
my-app/
├── project.toml
└── src/
    └── main.ez
```

常用命令：

```bash
ez build              # 构建 project.toml 声明的输出目标
ez run                # 构建并运行当前项目
ez run src/main.ez    # 直接运行单个 .ez 文件
ez test               # 编译并执行测试
ez fmt                # 格式化当前目录下的 .ez 文件
ez install            # 安装 project.toml 中的依赖
```

最小示例：

```ez
from "std/io" import { println };

let name: Str = "EzLang";
println(msg = "Hello {{name}}");
```

字符串插值支持表达式，表达式结果必须是 `Str`：

```ez
let first: Str = "Ez";
let last: Str = "Lang";
let greeting: Str = "Hello {{first + last}}";
```

## VS Code 插件

VS Code 插件源码位于 `editors/vscode`，提供：

- `.ez` 语法高亮
- 语法诊断和语义诊断
- 关键字、类型、符号和标准库导入补全
- hover
- 跳转定义
- 文档大纲
- 文档格式化

本地开发或打包：

```bash
cd editors/vscode
npm install
npm run compile
npm run package
```

打包后会生成 `ezlang-vscode-0.1.0.vsix`，可在 VS Code 中安装：

```bash
code --install-extension ezlang-vscode-0.1.0.vsix
```

插件在仓库开发态会优先用 `python3 -m lsp` 启动 LSP；打包安装后会使用 VSIX 内置的 LSP 运行文件，找不到内置服务时再调用 PATH 中的 `ez-lsp`。如果你使用自定义虚拟环境，可在 VS Code 设置中指定：

```json
{
  "ezlang.server.command": "/path/to/python3",
  "ezlang.server.args": ["-m", "lsp"]
}
```

开启保存时格式化：

```json
{
  "[ezlang]": {
    "editor.defaultFormatter": "ezlang.ezlang-vscode",
    "editor.formatOnSave": true
  }
}
```

## 文档索引

英文文档入口见 [README.en.md](README.en.md)。

- [快速教程](docs/tutorial.md)：变量、函数、结构体、控制流、标准库和 Flow 示例。
- [语言规格](docs/doc.md)：类型系统、函数、结构体、控制流、模块、外部链接和语法糖。
- [CLI 使用手册](docs/cli-manual.md)：`ez init`、`build`、`run`、`test`、`fmt`、`release` 等命令。
- [工具链与项目配置](docs/toolchain.md)：`project.toml`、依赖、工作区、多目标输出、LSP 和 VS Code 插件。
- [标准库设计](docs/stdlib.md)：标准库能力矩阵、平台适配和模块设计。
- [标准库 API](docs/stdlib-api.md)：`std/io`、`std/fs`、`std/str`、`std/fmt`、`std/net/*` 等 API 列表。
- [运行时设计](docs/runtime-design.md)：Arena、Flow ABI、阻塞调用和错误处理。
- [编译器架构](docs/compiler-architecture.md)：解析、语义分析、LLVM IR 生成和运行时协作。
- [Web UI 包](docs/ez-web-ui.md)：DOM 绑定和 Web UI API。
- [Android UI 包](docs/ez-android-ui.md)：Android 原生 View 绑定。
- [iOS UI 包](docs/ez-ios-ui.md)：UIKit 绑定。

## 项目结构

```text
EzLang/
├── cli/             # ez 命令行入口
├── compiler/        # 编译器核心：ANTLR4 解析、语义分析、LLVM IR 生成
├── docs/            # 语言、工具链、运行时和标准库文档
├── editors/vscode/  # VS Code 插件
├── examples/        # EzLang 示例
├── grammar/         # ANTLR4 文法
├── lsp/             # EzLang LSP 服务端
├── packages/        # 标准库与 UI 包
└── project.toml     # 本仓库示例项目配置
```

## 示例代码

```ez
from "std/io" import { print };

type Named = { name: Str };
struct User { name: Str; age: I32 }

let user = User(name = "Alice", age = 42);
let person: Named = user;

struct Pair<T, U> {
    first: T;
    second: U;
    swap = (this: #Pair<T, U>) => Pair<U, T>(first = this.second, second = this.first);
}

let p = Pair(first = 42, second = "hello");
let swapped = p.swap();
swapped.first -> print(msg = %);
```

## 许可证

本项目采用 [MIT](LICENSE) 许可证。

## 联系方式

可以加我微信交流 EzLang 使用、反馈和协作。有北京的好的工作机会也可以加我, 失业快 1 年了。

![微信二维码](wechat.png "微信二维码")
