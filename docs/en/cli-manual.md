# EzLang CLI Manual

[中文](../cli-manual.md)

The EzLang CLI entrypoint is [cli/ez.py](../../cli/ez.py). Running `pip install -e .` from the repository root registers the local `ez` command.

This page is a command behavior and option quick reference. For `project.toml` fields, targets, and VS Code/LSP configuration, see [Toolchain and Project Configuration](toolchain.md).

## Help

```bash
ez --help
ez build --help
```

## Initialize

```bash
ez init path/to/app --name app
ez init path/to/app --template https://example.com/template.git
```

Without a template, `ez init` creates `project.toml` and `src/main.ez`. With `--template`, it shallow-clones the template repository and copies its contents except `.git`.

## Project Configuration

The CLI reads `project.toml` by default:

```toml
[project]
name = "demo"
version = "0.1.0"
# main is optional; when omitted, EzLang searches src/main.ez, src/index.ez, main.ez, or index.ez
main = "src/index.ez"
optimize = 2
public = true
registry = "local"

[[output]]
arch = "x86_64"
os = "linux"
dir = "dist/linux"
```

Supported `os` values:

- `linux`
- `macos`
- `windows`
- `android`
- `ios`
- `emcc`
- `freestanding`

Supported `arch` values:

- `x86_64`
- `aarch64`
- `arm`
- `wasm32`
- `riscv64`

## Build

```bash
ez build --project project.toml
```

Build steps:

1. Read `project.toml`.
2. Discover the source dependency graph from imports.
3. Run semantic analysis.
4. Generate LLVM IR.
5. Write `.ll` output.
6. Write `.o` output when available.
7. Link a same-name executable for native targets that contain `main`; for `emcc`, `android`, and `ios` targets with `output.sdk`, call the corresponding SDK to produce platform artifacts.

## Run

```bash
ez run --project project.toml
ez run path/to/file.ez
```

Without a file argument, `run` uses `[project].main` from `project.toml`; if it is not configured, the CLI searches `src/main.ez`, `src/index.ez`, `main.ez`, or `index.ez`. When a `.ez` file is passed, the CLI uses that file as the entrypoint. If the current directory contains `project.toml`, project dependencies, externs, and optimization settings are reused, and output is written to `.ez/run/<file-name>/`. `run` only supports native executable artifacts. In project mode it selects the output target matching the host `os` and `arch` first.

## Test

```bash
ez test --project project.toml
ez test --project project.toml tests/foo.ez
```

Without explicit paths, `test` scans `.ez` files under `tests/`. If no `tests/` directory exists, it falls back to the project entrypoint.

## Install Dependencies

```bash
ez install --project project.toml
ez install -g --project project.toml
```

Supported dependency forms:

- local path dependencies
- workspace dependencies
- remote registry version dependencies. `install` prefers the `name-version.zip` package produced by `ez release`, and keeps compatibility with the older single-file `name.ez` package format.

`-g` / `--global` installs only version dependencies into `$EZLANG_HOME/deps/<name>/<version>`. If `EZLANG_HOME` is not set, the fallback is `~/.ez/deps/<name>/<version>`. Project imports of version dependencies search both project-local `.ez/deps` and the global cache.

## Format

```bash
ez fmt --project project.toml src/index.ez
ez fmt --project project.toml --check src/index.ez
```

When files or directories are passed, only those `.ez` files are processed. Without paths, the command recursively formats `.ez` files under the command's working directory. `--check` / `--dry-run` checks formatting without writing files.

## Release

```bash
ez release --project project.toml
ez release --project project.toml --dry-run
```

Release validates the version, `public` setting, and package target, then packages source code for upload to a registry or a local directory. The package file is named `<name>-<version>.zip` and can be installed by `ez install` as a version dependency.

For a local registry, output is written to `<registry>/<name>/<version>/<name>-<version>.zip`. For an HTTP(S) registry, the CLI uploads with `PUT <registry>/<name>/<version>/<name>-<version>.zip` and `Content-Type: application/zip`. `--dry-run` validates only and does not write files or upload.

## Plugin Hooks

`project.toml` can configure plugins:

```toml
[[plugins]]
name = "./plugin.py"
args = ["release=true"]
```

Plugins are Python build hooks. They do not replace the compiler frontend or backend; they observe build context before and after each output target.

Optional plugin functions:

- `before_build(context)`
- `after_build(context)`

`context` contains `project`, `version`, `description`, `root`, `project_file`, `main`, `optimize`, `output`, and `sources`. `after_build` also includes `ir`, `object`, `executable`, `sdk_artifact`, and `extern_libs`. Each hook call also includes the current `plugin` and its `args`.
