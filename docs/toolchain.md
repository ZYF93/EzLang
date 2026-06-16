# EzLang 工具链与项目配置指南

EzLang 提供了开箱即用的命令行工具链（CLI），并采用 `project.toml` 作为标准的项目配置文件，用于管理项目元数据、编译产物、插件扩展和依赖关系。

---

## 1. 命令行工具 (CLI)

### `ez init`
初始化 EzLang 项目。默认在目标目录创建 `project.toml` 和 `src/main.ez`，项目名使用目录名；可通过 `--name` 指定项目名。传入 `--template <git-url>` 时会浅克隆模板仓库并复制除 `.git` 外的内容。

### `ez install`
读取项目根目录下的 `project.toml` 文件（重点解析 `[deps]` 节点），自动下载并安装所有项目依赖。支持安装本地文件、特定版本号的远端包，以及工作区（Workspace）内的内部模块。远端版本依赖优先安装 registry 中的 `<name>-<version>.zip`，该文件也是 `ez release` 生成的包格式；旧的单文件 `<name>.ez` 仍作为兼容格式支持。

`ez install -g` 会把版本依赖安装到全局缓存 `$EZLANG_HOME/deps/<name>/<version>`；未设置 `EZLANG_HOME` 时使用 `~/.ez/deps/<name>/<version>`。`-g` 不接受本地路径依赖或 Workspace 依赖。编译和运行解析版本依赖时会同时查找项目本地 `.ez/deps` 与全局缓存。

### `ez build`
读取 `project.toml`，执行项目的编译与构建。该命令会根据配置中的 `[[output]]` 节点执行交叉编译，生成对应架构和操作系统的产物，并输出到指定的 `dir` 目录中。同时也会根据 `[[plugins]]` 配置项加载 Python 构建 hook，在每个输出目标的构建前后调用 `before_build(context)` / `after_build(context)`。

本机可执行目标会生成 LLVM IR、对象文件和同名可执行文件；链接阶段会编译 `extern "*.c"` 源码，链接对象文件、静态库、动态库、framework 与系统库。配置 `output.sdk` 后，`emcc` 目标会调用 Emscripten `emcc` 并把 `extern "*.js" for emcc` 作为 `--js-library` 传入；当 flow sleep、`race(pl)`、零捕获 `I32` `parallel` 或 emcc 标准库 suspend source 引入协程运行时时，CLI 会自动追加 `-sASYNCIFY`。Android/iOS 目标会调用 SDK 内的 `clang` 编译 C extern 并链接平台动态库。未配置 `output.sdk` 时仍保留 IR/对象文件输出，便于外部构建系统接手。

### `ez run`
构建并立即执行当前项目（仅适用于本地可执行产物）。不适用于 `emcc` / `android` / `ios` 目标。入口文件会优先使用 `[project].main`；未配置时自动查找 `src/main.ez`、`src/index.ez`、`main.ez` 或 `index.ez`。入口文件顶层语句会按源码顺序执行，不要求显式定义 `main` 函数。

`ez run` 会优先选择与宿主机 `os` 和 `arch` 同时匹配的 `[[output]]`，再回退到同 `os` 的输出目标。

也可以直接运行单个文件：`ez run path/to/file.ez`。若当前目录存在 `project.toml`，该模式会复用项目依赖、extern 和优化配置，但把入口临时覆盖为传入文件，并把输出写到 `.ez/run/<文件名>/`；若没有项目文件，则使用本机目标的最小临时配置运行该文件。

### `ez test`
编译并执行 EzLang 测试。未指定路径时默认查找 `tests/` 下的 `.ez` 文件；没有测试目录时回退到项目入口文件。可指定一个或多个测试文件或目录。

### `ez fmt`
代码格式化工具。传入文件或目录时只处理这些路径下的 `.ez` 文件；未传路径时递归格式化执行命令所在目录下的 `.ez` 文件。`--check` / `--dry-run` 只检查是否需要格式化，不写回文件。

### `ez release`
包发布工具。结合 `project.toml` 中的配置，将当前项目作为模块发布到远端的包管理服务中，供他人或外部项目下载使用。发布产物为 `<name>-<version>.zip`，包含 `project.toml` 与项目源码。
`[project].registry` 为本地路径时，产物写入 `<registry>/<name>/<version>/<name>-<version>.zip`；为 HTTP(S) URL 时，CLI 使用 `PUT <registry>/<name>/<version>/<name>-<version>.zip` 上传 zip，Content-Type 为 `application/zip`。`public = false` 的包不能发布，`--dry-run` 只校验元数据和发布目标，不写文件或上传。

---

## 2. `project.toml` 字段与枚举说明

`project.toml` 是 EzLang 的核心清单文件，支持配置多目标输出和依赖关系。

### `[project]`
项目的基本元数据描述及发布配置。
* `name` (字符串)：项目名称。
* `version` (字符串)：项目的版本号（如 `"0.1.0"`）。
* `description` (字符串)：项目的简短说明。
* `main` (字符串，可选)：包的主入口文件路径（如 `"index.ez"`）。省略时自动查找 `src/main.ez`、`src/index.ez`、`main.ez` 或 `index.ez`。
* `public` (布尔值)：是否将该包对外公开。为 `true` 时，配合 `ez release` 可发布到远端。
* `registry` (字符串)：包管理远端服务的具体地址（如 `"https://www.xxx.com"`），指定本包发布的目标中心仓库或拉取依赖的源。
* `optimize` (数字)：优化等级，0–3，默认值为 2。

### `[log]`
标准日志模块的编译期配置。
* `compile_min_level` (数字，可选)：编译期最低日志级别，范围 0–4，对应 `logTrace` 到 `logError`。低于该级别且级别可静态确定的 `std/log` 标准日志调用会在代码生成前删除；动态 `level` 参数仍由运行时过滤。

### `[extern]`
全局外部库配置，为所有模块提供默认的 extern 搜索路径。
* `search_paths` (字符串数组)：外部库搜索路径列表，编译器按顺序查找 `extern` 引用的库文件。
* 支持按目标平台配置：`[extern.linux]`, `[extern.macos]`, `[extern.windows]`, `[extern.android]`, `[extern.ios]`, `[extern.emcc]`

```toml
[extern]
search_paths = ["./libs", "/usr/local/lib"]

[extern.linux]
search_paths = ["./libs/linux"]

[extern.windows]
search_paths = ["C:/Program Files/MyLib/lib"]
```

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

  兼容别名：旧配置中的 `"wasm"` 会被 CLI 归一化为 `"wasm32"`，并输出废弃警告；新项目应直接使用 `"wasm32"`。

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

* `sdk` (字符串，可选)：平台 SDK 路径。`android` 目标指定 NDK 根目录，`ios` 目标指定 Xcode/SDK 根目录，`emcc` 目标指定 Emscripten SDK 或包含 `emcc` 的目录。

  ```toml
  [[output]]
  arch = "aarch64"
  os   = "android"
  dir  = "./dist/android"
  sdk  = "/path/to/ndk"
  ```

### `[[plugins]]`
配置 `ez build` 构建过程中使用的 Python hook（数组对象）。当前插件接口不替换编译器前端或后端，只在每个输出目标构建前后观察构建上下文并执行自定义脚本。
* `name` (字符串)：插件模块名、Python 文件路径或包含 `plugin.py` 的目录。相对路径按项目根目录解析；非路径名称通过 Python import 加载。
* `args` (字符串数组 - 可选)：传递给插件的参数。调用 hook 时会通过 `context["args"]` 提供。

插件模块可导出以下可选函数：
* `before_build(context)`：编译当前输出目标前调用。
* `after_build(context)`：当前输出目标写出 IR/对象文件、可执行文件或 SDK 产物后调用。

`context` 包含 `project`、`version`、`description`、`root`、`project_file`、`main`、`optimize`、`output`、`sources`；`after_build` 还包含 `ir`、`object`、`executable`、`sdk_artifact`、`extern_libs`，并在每次 hook 调用时附加当前 `plugin` 与该插件的 `args`。

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

[log]
compile_min_level = 2

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
sdk  = "/opt/emsdk"

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

### SDK 链接产物

| 目标       | SDK 工具查找                                                    | 产物                         |
| ---------- | --------------------------------------------------------------- | ---------------------------- |
| `emcc`    | `emcc` 或 `upstream/emscripten/emcc`                            | `<name>.js`，同时由 emcc 生成 wasm |
| `android` | `toolchains/llvm/prebuilt/<host>/bin/<triple>21-clang` 或 `clang` | `lib<name>.so`               |
| `ios`     | `usr/bin/clang`、`Toolchains/XcodeDefault.xctoolchain/usr/bin/clang` 或 `clang` | `lib<name>.dylib`            |

SDK 链接失败时，CLI 会输出缺失工具、C extern 编译失败或链接失败的具体诊断。`extern "*.js"` 只参与 `emcc` SDK 链接；native 链接阶段会忽略 JS library 输入。emcc flow 协程 runtime 由编译器自动加入 JS library 列表，无需用户在 `project.toml` 中手动声明。
