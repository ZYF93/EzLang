# EzLang CLI 使用手册

EzLang CLI 入口位于 [cli/ez.py](../cli/ez.py)。常用命令如下。

## 查看帮助

```bash
python -m cli.ez --help
python -m cli.ez build --help
```

## 项目配置

默认读取 `project.toml`：

```toml
[project]
name = "demo"
version = "0.1.0"
main = "src/index.ez"
optimize = 0
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

支持的 `arch` 包括：

- `x86_64`
- `aarch64`
- `wasm32`

## 构建

```bash
python -m cli.ez build --project project.toml
```

构建流程：

1. 读取 `project.toml`。
2. 根据 import 发现源文件依赖图。
3. 运行语义分析。
4. 生成 LLVM IR。
5. 写出 `.ll`。
6. 可用时写出 `.o`。

## 运行

```bash
python -m cli.ez run --project project.toml
```

`run` 只支持本机目标。非本机目标会给出错误。

## 安装依赖

```bash
python -m cli.ez install --project project.toml
```

支持：

- 本地路径依赖
- workspace 依赖
- 远端 registry 版本依赖

## 格式化

```bash
python -m cli.ez fmt --project project.toml src/index.ez
python -m cli.ez fmt --project project.toml --check src/index.ez
```

## 发布

```bash
python -m cli.ez release --project project.toml
python -m cli.ez release --project project.toml --dry-run
```

发布会校验版本号、`public` 配置，并打包源码上传到 registry 或本地目录。

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
