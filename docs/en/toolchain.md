# EzLang Toolchain and Project Configuration Guide

[中文](../toolchain.md)

EzLang provides an out-of-the-box command-line toolchain and uses `project.toml` as the standard project manifest for metadata, build outputs, plugin hooks, and dependencies.

This page focuses on `project.toml`, target platforms, and editor integration. For a command quick reference, see the [CLI Manual](cli-manual.md).

---

## 1. Command-Line Tools

### `ez init`

Initializes an EzLang project. By default it creates `project.toml` and `src/main.ez` in the target directory, using the directory name as the project name. `--name` overrides the name. `--template <git-url>` shallow-clones a template repository and copies everything except `.git`.

### `ez install`

Reads `project.toml` in the project root, especially `[deps]`, and installs dependencies. It supports local files, remote packages by version, and internal workspace modules. Remote version dependencies prefer the `<name>-<version>.zip` package produced by `ez release`; the older single-file `<name>.ez` format remains supported for compatibility.

`ez install -g` installs version dependencies into the global cache `$EZLANG_HOME/deps/<name>/<version>`. If `EZLANG_HOME` is not set, the fallback is `~/.ez/deps/<name>/<version>`. `-g` does not accept local path or workspace dependencies. Build and run resolution search both project-local `.ez/deps` and the global cache.

### `ez build`

Reads `project.toml` and builds the project. Each `[[output]]` target can cross-compile for a different architecture and operating system and writes artifacts into its configured `dir`. Python build hooks from `[[plugins]]` run before and after each output target through `before_build(context)` / `after_build(context)`.

Native executable targets produce LLVM IR, object files, and a same-name executable. The link step compiles `extern "*.c"` sources and links object files, static libraries, dynamic libraries, frameworks, and system libraries. With `output.sdk`, the `emcc` target calls Emscripten `emcc` and passes `extern "*.js" for emcc` as `--js-library`. When Flow sleep, `race(pl)`, `I32` `parallel`, or emcc standard-library suspend sources introduce coroutine runtime code, the CLI automatically adds `-sASYNCIFY`. Android/iOS targets call SDK `clang` to compile C externs and link platform dynamic libraries. Without `output.sdk`, IR/object outputs are still kept for external build systems.

### `ez run`

Builds and immediately runs the current project. This only applies to native executable artifacts, not `emcc`, `android`, or `ios`. The entrypoint uses `[project].main` first; when omitted, the CLI searches `src/main.ez`, `src/index.ez`, `main.ez`, or `index.ez`. Top-level statements in the entry file execute in source order; a user-defined `main` function is not required.

`ez run` first selects a `[[output]]` matching both host `os` and `arch`, then falls back to a same-`os` output.

It can also run one file directly: `ez run path/to/file.ez`. If the current directory has `project.toml`, that mode reuses project dependencies, externs, and optimization settings while temporarily overriding the entrypoint and writing output to `.ez/run/<file-name>/`. Without a project file, it uses a minimal native temporary configuration.

### `ez test`

Compiles and runs EzLang tests. Without paths it scans `.ez` files under `tests/`; when no test directory exists it falls back to the project entrypoint. One or more test files or directories can be specified.

### `ez fmt`

Formats EzLang code. File or directory arguments restrict processing to `.ez` files under those paths. Without paths, it recursively formats `.ez` files under the command working directory. `--check` / `--dry-run` only checks formatting and does not write files.

### `ez release`

Packages the current project as a module for a registry. The output package is `<name>-<version>.zip` and includes `project.toml` plus project sources. If `[project].registry` is a local path, the artifact is written to `<registry>/<name>/<version>/<name>-<version>.zip`. If it is an HTTP(S) URL, the CLI uploads with `PUT <registry>/<name>/<version>/<name>-<version>.zip` and `Content-Type: application/zip`. `public = false` packages cannot be released. `--dry-run` validates metadata and target only.

### `ez-lsp`

Starts the EzLang Language Server over standard input/output. It currently provides syntax highlighting support, syntax and semantic diagnostics, basic completion, hover, go to definition, document outline, and full-document formatting for `.ez` files.

```bash
ez-lsp
```

From the repository root it can also start as a Python module:

```bash
python3 -m lsp
```

The VS Code extension source is in `editors/vscode`:

```bash
cd editors/vscode
npm install
npm run compile
npm run package
```

In repository development mode, the extension starts the server with `python3 -m lsp`. After packaging, it uses the LSP runtime embedded in the VSIX and falls back to `ez-lsp` on `PATH` if the embedded server is unavailable. To use another interpreter, virtual environment, or server entrypoint, configure `ezlang.server.command` and `ezlang.server.args` in VS Code settings.

Formatting is implemented by the LSP using the internal formatter shared with `ez fmt`. VS Code can run "Format Document" manually or format on save:

```json
{
  "[ezlang]": {
    "editor.defaultFormatter": "ezlang.ezlang-vscode",
    "editor.formatOnSave": true
  }
}
```

---

## 2. `project.toml` Fields and Enumerations

`project.toml` is the core EzLang manifest and supports multi-target output plus dependencies.

### `[project]`

Project metadata and release configuration.

- `name` (string): project name.
- `version` (string): project version, such as `"0.1.0"`.
- `description` (string): short project description.
- `main` (string, optional): main entry file, such as `"index.ez"`. If omitted, EzLang searches `src/main.ez`, `src/index.ez`, `main.ez`, or `index.ez`.
- `public` (boolean): whether the package can be published externally with `ez release`.
- `registry` (string): package registry URL or local release target.
- `optimize` (number): optimization level `0` to `3`, default `2`.

### `[log]`

Compile-time configuration for the standard log module.

- `compile_min_level` (number, optional): compile-time minimum log level, `0` to `4`, corresponding to `logTrace` through `logError`. Standard `std/log` calls below this statically known level are removed before codegen; dynamic `level` arguments remain runtime-filtered.

### `[extern]`

Global external-library search paths for all modules.

- `search_paths` (string array): external library search paths in lookup order.
- Target-specific sections are supported: `[extern.linux]`, `[extern.macos]`, `[extern.windows]`, `[extern.android]`, `[extern.ios]`, `[extern.emcc]`.

```toml
[extern]
search_paths = ["./libs", "/usr/local/lib"]

[extern.linux]
search_paths = ["./libs/linux"]

[extern.windows]
search_paths = ["C:/Program Files/MyLib/lib"]
```

### `[workspace]`

Monorepo package management.

- `members` (string array): workspace member path patterns, with glob syntax such as `["./packages/**", "./apps/**"]`.

### `[[output]]`

Build output target. It can be declared multiple times.

- `arch` (string): target CPU architecture.

  | Value | Description |
  | ----- | ----------- |
  | `"x86_64"` | 64-bit x86 for Windows / Linux / macOS |
  | `"aarch64"` | 64-bit ARM for macOS Apple Silicon / Linux / Android / iOS |
  | `"arm"` | 32-bit ARM for older Android devices |
  | `"wasm32"` | 32-bit WebAssembly, used with `os = "emcc"` |
  | `"riscv64"` | RISC-V 64-bit, experimental |

  Compatibility alias: old `"wasm"` is normalized to `"wasm32"` and emits a deprecation warning. New projects should use `"wasm32"` directly.

- `os` (string): target operating environment.

  | Value | Platform | Base | Notes |
  | ----- | -------- | ---- | ----- |
  | `"windows"` | Windows | Win32 API + MSVCRT | |
  | `"macos"` | macOS | libc + Darwin syscall | |
  | `"linux"` | Linux | libc + Linux syscall | |
  | `"android"` | Android | Bionic libc + NDK | UI is provided by `ez-android-ui` |
  | `"ios"` | iOS | Apple libc + XNU | Cross-compile from macOS; UI is provided by `ez-ios-ui` |
  | `"emcc"` | WebAssembly (Emscripten) | Emscripten libc + JS bindings | |
  | `"freestanding"` | Bare metal | no system | no `std` support |

- `dir` (string): output directory, such as `"./dist/linux"`.

- `sdk` (string, optional): platform SDK path. Android uses the NDK root, iOS uses the Xcode/SDK root, and emcc uses the Emscripten SDK or a directory containing `emcc`.

  ```toml
  [[output]]
  arch = "aarch64"
  os   = "android"
  dir  = "./dist/android"
  sdk  = "/path/to/ndk"
  ```

### `[[plugins]]`

Python hooks for `ez build`. The plugin interface does not replace the frontend or backend; it observes build context before and after each output target.

- `name` (string): Python module name, Python file path, or directory containing `plugin.py`. Relative paths are resolved against the project root; non-path names are loaded through Python import.
- `args` (string array, optional): plugin arguments, provided as `context["args"]`.

Optional exported functions:

- `before_build(context)`: called before compiling the current output target.
- `after_build(context)`: called after writing IR/object/executable or SDK artifacts for the current target.

`context` contains `project`, `version`, `description`, `root`, `project_file`, `main`, `optimize`, `output`, and `sources`. `after_build` also contains `ir`, `object`, `executable`, `sdk_artifact`, and `extern_libs`. Each hook call also includes the current `plugin` and its `args`.

### `[deps]`

Declares dependencies and their resolution strategy.

1. **Local path dependency**: points directly to a local file or module directory, for example `std = "./lib/std.ez"`.
2. **Remote version dependency**: names a semantic version fetched from a registry, for example `utils = "0.1.0"`.
3. **Workspace dependency**: uses the special marker `@workspace` to refer to another local package in the same `[workspace]`, for example `packageA = "@workspace"`.

---

## 3. Complete `project.toml` Example

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

# Desktop - Linux x64
[[output]]
arch = "x86_64"
os   = "linux"
dir  = "./dist/linux"

# Desktop - macOS Apple Silicon
[[output]]
arch = "aarch64"
os   = "macos"
dir  = "./dist/macos"

# Desktop - Windows x64
[[output]]
arch = "x86_64"
os   = "windows"
dir  = "./dist/windows"

# Mobile - Android
[[output]]
arch = "aarch64"
os   = "android"
dir  = "./dist/android"
sdk  = "/opt/android-ndk"

# Mobile - iOS, built from macOS
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

## 4. Cross-Compilation Notes

| Target | Requirements |
| ------ | ------------ |
| `linux` / `windows` / `macos` | Native host or any LLVM-capable host |
| `android` | Android NDK, with `sdk` pointing to the NDK root |
| `ios` | Must build from a macOS host, with `sdk` pointing to the Xcode SDK path |
| `emcc` | Emscripten SDK (`emsdk`) installed and `emcc` available on `PATH` |
| `freestanding` | No system dependency, but `std` is unavailable except low-level `std/mem` primitives |

> **Mobile UI**: `android` / `ios` targets compile system-level logic only. For UI, depend on `ez-android-ui` or `ez-ios-ui` and use the package-specific bridge configuration.

### SDK Link Artifacts

| Target | SDK Tool Lookup | Artifact |
| ------ | --------------- | -------- |
| `emcc` | `emcc` or `upstream/emscripten/emcc` | `<name>.js`, with wasm generated by emcc |
| `android` | `toolchains/llvm/prebuilt/<host>/bin/<triple>21-clang` or `clang` | `lib<name>.so` |
| `ios` | `usr/bin/clang`, `Toolchains/XcodeDefault.xctoolchain/usr/bin/clang`, or `clang` | `lib<name>.dylib` |

When SDK linking fails, the CLI reports missing tools, C extern compilation failures, or link failures. `extern "*.js"` participates only in emcc SDK linking; native linking ignores JS library inputs. The emcc Flow coroutine runtime is added automatically to the JS library list, so users do not need to declare it manually in `project.toml`.
