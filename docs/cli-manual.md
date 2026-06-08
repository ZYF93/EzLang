# EzLang CLI 使用手册

EzLang CLI 入口位于 [cli/ez.py](../cli/ez.py)。在仓库根目录执行 `pip install -e .` 后会注册本地命令 `ez`。常用命令如下。

## 查看帮助

```bash
ez --help
ez build --help
```

## 项目配置

默认读取 `project.toml`：

```toml
[project]
name = "demo"
version = "0.1.0"
main = "src/index.ez"
optimize = 2
public = true
registry = "local"

[[output]]
arch = "x86_64"
os = "linux"
dir = "dist/linux"
```

支持的 `os` 包括：

- `linux`
- `macos`
- `windows`
- `android`
- `ios`
- `emcc`
- `freestanding`

支持的 `arch` 包括：

- `x86_64`
- `aarch64`
- `arm`
- `wasm32`
- `riscv64`

## 构建

```bash
ez build --project project.toml
```

构建流程：

1. 读取 `project.toml`。
2. 根据 import 发现源文件依赖图。
3. 运行语义分析。
4. 生成 LLVM IR。
5. 写出 `.ll`。
6. 可用时写出 `.o`。
7. 本机目标存在 `main` 时链接同名可执行文件；配置 `output.sdk` 的 `emcc` / `android` / `ios` 目标会调用对应 SDK 生成平台产物。

## 运行

```bash
ez run --project project.toml
ez run path/to/file.ez
```

未传文件时，`run` 读取 `project.toml` 的 `[project].main`。传入 `.ez` 文件时，CLI 会直接把该文件作为入口运行；若当前目录存在 `project.toml`，会复用项目依赖、extern 和优化配置，并把输出写到 `.ez/run/<文件名>/`。`run` 只支持本机可执行产物，项目模式下会优先选择本机 `os` + `arch` 输出目标。

## 测试

```bash
ez test --project project.toml
ez test --project project.toml tests/foo.ez
```

未指定路径时，`test` 默认查找 `tests/` 下的 `.ez` 文件；没有 `tests/` 时回退到项目入口文件。

## 安装依赖

```bash
ez install --project project.toml
ez install -g --project project.toml
```

支持：

- 本地路径依赖
- workspace 依赖
- 远端 registry 版本依赖。`install` 优先下载 `name-version.zip`（即 `ez release` 产物），并兼容旧的单文件 `name.ez` 包。

`-g` / `--global` 只安装版本依赖，目标目录为 `$EZLANG_HOME/deps/<name>/<version>`；未设置 `EZLANG_HOME` 时使用 `~/.ez/deps/<name>/<version>`。项目导入版本依赖时会同时查找项目本地 `.ez/deps` 和全局缓存。

## 格式化

```bash
ez fmt --project project.toml src/index.ez
ez fmt --project project.toml --check src/index.ez
```

## 发布

```bash
python -m cli.ez release --project project.toml
python -m cli.ez release --project project.toml --dry-run
```

发布会校验版本号、`public` 配置，并打包源码上传到 registry 或本地目录。
发布包文件名为 `<name>-<version>.zip`，可被 `ez install` 作为版本依赖安装。

## 插件 hook

`project.toml` 可配置插件：

```toml
[[plugins]]
name = "./plugin.py"
args = ["release=true"]
```

插件可实现：

- `before_build(context)`
- `after_build(context)`

context 中包含项目名、输出目标、源文件、extern libs 等信息。
