# EzLang 工具链与项目配置指南

EzLang 提供了开箱即用的命令行工具链（CLI），并采用 `project.toml` 作为标准的项目配置文件，用于管理项目元数据、编译产物、插件扩展和依赖关系。

---

## 1. 命令行工具 (CLI)

### `ez install`
读取项目根目录下的 `project.toml` 文件（重点解析 `[deps]` 节点），自动下载并安装所有项目依赖。支持安装本地文件、特定版本号的远端包，以及工作区（Workspace）内的内部模块。

### `ez build`
读取 `project.toml`，执行项目的编译与构建。该命令会根据配置中的 `[[output]]` 节点执行交叉编译，生成对应架构和操作系统的产物，并输出到指定的 `dir` 目录中。同时也会根据 `[[plugins]]` 配置项加载编译器前端或后端插件。

### `ez run`
构建并立即执行当前项目（仅适用于本地可执行产物）。不适用于 `emcc` / `android` / `ios` 目标。

### `ez fmt`
代码格式化工具。自动对当前项目或工作区内的所有 `.ez` 源代码文件进行统一格式化，确保代码风格（缩进、换行、空格等）保持一致。

### `ez release`
包发布工具。结合 `project.toml` 中的配置，将当前项目作为模块发布到远端的包管理服务中，供他人或外部项目下载使用。

---

## 2. `project.toml` 字段与枚举说明

`project.toml` 是 EzLang 的核心清单文件，支持配置多目标输出和依赖关系。

### `[project]`
项目的基本元数据描述及发布配置。
* `name` (字符串)：项目名称。
* `version` (字符串)：项目的版本号（如 `"0.1.0"`）。
* `description` (字符串)：项目的简短说明。
* `main` (字符串)：包的主入口文件路径（如 `"index.ez"`）。
* `public` (布尔值)：是否将该包对外公开。为 `true` 时，配合 `ez release` 可发布到远端。
* `registry` (字符串)：包管理远端服务的具体地址（如 `"https://www.xxx.com"`），指定本包发布的目标中心仓库或拉取依赖的源。
* `optimize` (数字)：优化等级，0–3，默认值为 2。

### `[workspace]`
用于单一代码库（Monorepo）下的多包管理。
* `members` (字符串数组)：工作区子模块的路径匹配列表，支持 glob 语法（如 `["./packages/**", "./apps/**"]`）。

### `[[output]]`
定义编译输出目标（数组对象，可多次声明以支持一次性多目标编译）。

* `arch` (字符串)：目标处理器的 CPU 架构。

  | 值          | 说明                                                          |
  | ----------- | ------------------------------------------------------------- |
  | `"x86_64"`  | 64 位 x86，适用于 Windows / Linux / macOS                     |
  | `"aarch64"` | 64 位 ARM，适用于 macOS Apple Silicon / Linux / Android / iOS |
  | `"arm"`     | 32 位 ARM，适用于旧版 Android 设备                            |
  | `"wasm32"`  | WebAssembly 32 位，配合 `os = "emcc"` 使用                    |
  | `"riscv64"` | RISC-V 64 位（实验性）                                        |

* `os` (字符串)：目标操作系统环境。

  | 值               | 平台                     | 底层                          | 备注                                          |
  | ---------------- | ------------------------ | ----------------------------- | --------------------------------------------- |
  | `"windows"`      | Windows                  | Win32 API + MSVCRT            |                                               |
  | `"macos"`        | macOS                    | libc + Darwin syscall         |                                               |
  | `"linux"`        | Linux                    | libc + Linux syscall          |                                               |
  | `"android"`      | Android                  | Bionic libc + NDK             | UI 由 `ez-android-ui` 提供                    |
  | `"ios"`          | iOS                      | Apple libc + XNU              | 需在 macOS 上交叉编译；UI 由 `ez-ios-ui` 提供 |
  | `"emcc"`         | WebAssembly (Emscripten) | Emscripten libc + JS bindings |                                               |
  | `"freestanding"` | 裸机                     | 无系统                        | 无 std 支持                                   |

* `dir` (字符串)：对应目标的编译产物存放路径（如 `"./dist/linux"`）。

* `sdk` (字符串，可选)：平台 SDK 路径。`android` 目标需要指定 NDK 路径，`ios` 目标需要指定 Xcode SDK 路径。

  ```toml
  [[output]]
  arch = "aarch64"
  os   = "android"
  dir  = "./dist/android"
  sdk  = "/path/to/ndk"
  ```

### `[[plugins]]`
配置 EzLang 编译器在编译过程中使用的插件（数组对象）。
* `name` (字符串)：插件名称，自动从依赖中加载对应的 plugin。
* `args` (字符串数组 - 可选)：传递给插件的参数。例如 `["release=true"]` 用于通知后端开启最高级别的执行优化。

### `[deps]`
声明项目依赖包及其解析方式。EzLang 支持以下三种依赖类型：
1. **本地路径依赖**：直接指向本地的文件或模块目录。
   * 用法示例：`std = "./lib/std.ez"`
2. **版本号远端依赖**：指定特定的语义化版本号，将由包管理器从中心仓库下载。
   * 用法示例：`utils = "0.1.0"`
3. **Workspace 内部依赖**：使用特殊标记，引用同一个 `[workspace]` 下的其他本地包。
   * 用法示例：`packageA = "@workspace"`

---

## 3. `project.toml` 完整示例

```toml
[project]
name        = "my-app"
version     = "0.1.0"
description = "A cross-platform EzLang application"
main        = "./src/index.ez"
public      = false
optimize    = 2

[workspace]
members = ["./packages/**"]

# 桌面 - Linux x64
[[output]]
arch = "x86_64"
os   = "linux"
dir  = "./dist/linux"

# 桌面 - macOS Apple Silicon
[[output]]
arch = "aarch64"
os   = "macos"
dir  = "./dist/macos"

# 桌面 - Windows x64
[[output]]
arch = "x86_64"
os   = "windows"
dir  = "./dist/windows"

# 移动 - Android
[[output]]
arch = "aarch64"
os   = "android"
dir  = "./dist/android"
sdk  = "/opt/android-ndk"

# 移动 - iOS（需在 macOS 上编译）
[[output]]
arch = "aarch64"
os   = "ios"
dir  = "./dist/ios"
sdk  = "/Applications/Xcode.app"

# Web - Emscripten / WASM
[[output]]
arch = "wasm32"
os   = "emcc"
dir  = "./dist/web"

[[plugins]]
name = "backend"
args = ["release=true"]

[deps]
std      = "./lib/std.ez"
utils    = "0.1.0"
core-lib = "@workspace"
```

---

## 4. 交叉编译说明

| 目标平台                      | 要求                                                       |
| ----------------------------- | ---------------------------------------------------------- |
| `linux` / `windows` / `macos` | 本机或任意支持 LLVM 的宿主均可                             |
| `android`                     | 需要 Android NDK，`sdk` 字段指定 NDK 根目录                |
| `ios`                         | 必须在 macOS 宿主上编译，`sdk` 字段指定 Xcode SDK 路径     |
| `emcc`                        | 需要安装 Emscripten SDK（`emsdk`），`PATH` 中可访问 `emcc` |
| `freestanding`                | 无系统依赖，但 `std` 不可用，只可使用 `std/mem` 的底层原语 |

> **移动端 UI**：`android` / `ios` 目标本身只编译系统级逻辑。如需 UI，分别引入 `ez-android-ui` 和 `ez-ios-ui` 依赖包，并通过各自包的配置完成界面构建。
