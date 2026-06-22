# EzLang Programming Language

[中文](README.md)

## Why EzLang

- **Fewer memory pitfalls without giving up speed**: common memory risks are handled by the language and toolchain as much as possible, so developers can focus on behavior and performance.
- **One codebase for more platforms**: from native programs to mobile targets and WebAssembly, EzLang aims to cover more environments with the same way of writing code.
- **Code that reads like intent**: control flow, data structures, and function calls compose naturally, making programs easier to understand and change.
- **AI can write it, humans can own it**: code stays clear, explicit, and easy to reason about, so people can review, take over, and maintain it over time.
- **Systems programming, made lighter**: EzLang brings reliability, performance, concurrency, and cross-platform output into a development experience that feels simple and practical.

## Core Features

EzLang is an expression-oriented systems programming language that defaults to value semantics. It combines a modern type system, an Arena memory model, and Flow concurrency semantics for high-performance system-level development, with cross-platform output for native targets, mobile platforms, and WebAssembly.

- **Expression-first syntax**: variables, control flow, `match`, function calls, and other constructs compose naturally.
- **Modern type system**: generics, optional types `?`, weak references `#`, union types `|`, function types, `List`/`Vec`, `Dict`, structs, and type aliases.
- **Value semantics with Arena memory**: values are copied by default, and temporary memory is reclaimed automatically when scopes exit.
- **Struct composition and methods**: `...Base` composition, default field values, named initialization, and explicit `this` receiver methods.
- **Flow concurrency runtime**: built-in `flow {}` / `parallel {}` / `race(pl)`, with suspend-point semantics on native and emcc targets.
- **External ABI linking**: `extern "lib" for target` plus `declare` calls into C, JS, and platform libraries.
- **Unified standard library**: `std/io`, `std/fs`, `std/net/*`, `std/fmt`, `std/collections`, and more share consistent interfaces across targets.
- **Complete toolchain**: the repository includes the CLI, formatter, LSP, VS Code extension, and project dependency management.

## Installation

Base requirements: Python 3.9+, `git`, and a native C compiler named `cc`. The install script prepares a virtual environment, installs the EzLang CLI and compiler, and runs a minimal compile check.

```bash
# Recommended: install or update from the official repository
curl -fsSL https://raw.githubusercontent.com/ZYF93/EzLang/main/install.sh | sh

# From an already cloned repository
sh install.sh --local

# Optional: custom install directory or skip PATH registration
EZLANG_INSTALL_DIR="$HOME/.ezlang" EZLANG_REGISTER_PATH=0 sh install.sh

# Optional: try installing Python/git/cc through the system package manager
EZLANG_INSTALL_DEPS=1 sh install.sh
```

After installation, open a new shell or load the environment manually:

```bash
source ~/.ezlang/env
ez --version
```

For source development, editable installation is also supported:

```bash
pip install -e .
```

If the system Python enforces PEP 668, use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Initialize a Project

Create a new project:

```bash
ez init my-app
cd my-app
```

The generated layout is:

```text
my-app/
|-- project.toml
`-- src/
    `-- main.ez
```

Common commands:

```bash
ez build              # Build outputs declared in project.toml
ez run                # Build and run the current project
ez run src/main.ez    # Run a single .ez file directly
ez test               # Compile and run tests
ez fmt                # Format .ez files under the current directory
ez install            # Install dependencies declared in project.toml
```

Minimal example:

```ez
from "std/io" import { println };

let name: Str = "EzLang";
println(msg = "Hello {{name}}");
```

String interpolation supports expressions whose result type is `Str`:

```ez
let first: Str = "Ez";
let last: Str = "Lang";
let greeting: Str = "Hello {{first + last}}";
```

## VS Code Extension

The VS Code extension lives in `editors/vscode` and provides:

- `.ez` syntax highlighting
- syntax and semantic diagnostics
- keyword, type, symbol, and standard-library import completion
- hover
- go to definition
- document outline
- document formatting

Local development or packaging:

```bash
cd editors/vscode
npm install
npm run compile
npm run package
```

Packaging creates `ezlang-vscode-0.1.0.vsix`, which can be installed into VS Code:

```bash
code --install-extension ezlang-vscode-0.1.0.vsix
```

In repository development mode, the extension starts the LSP with `python3 -m lsp`. After packaging, it uses the LSP runtime embedded in the VSIX and falls back to `ez-lsp` on `PATH` if needed. To use a custom virtual environment or entrypoint, configure VS Code settings:

```json
{
  "ezlang.server.command": "/path/to/python3",
  "ezlang.server.args": ["-m", "lsp"]
}
```

Enable format on save:

```json
{
  "[ezlang]": {
    "editor.defaultFormatter": "ezlang.ezlang-vscode",
    "editor.formatOnSave": true
  }
}
```

## Documentation Index

The Chinese documentation index is in [README.md](README.md).

- [Quick tutorial](docs/en/tutorial.md): variables, functions, structs, control flow, standard library, and Flow examples.
- [Language specification](docs/en/doc.md): type system, functions, structs, control flow, modules, external linking, and syntax sugar.
- [CLI manual](docs/en/cli-manual.md): `ez init`, `build`, `run`, `test`, `fmt`, `release`, and related commands.
- [Toolchain and project configuration](docs/en/toolchain.md): `project.toml`, dependencies, workspaces, multi-target output, LSP, and the VS Code extension.
- [Standard library design](docs/en/stdlib.md): capability matrix, platform adaptation, and module design.
- [Standard library API](docs/en/stdlib-api.md): API list for `std/io`, `std/fs`, `std/str`, `std/fmt`, `std/net/*`, and more.
- [Runtime design](docs/en/runtime-design.md): Arena, Flow ABI, blocking calls, and error handling.
- [Compiler architecture](docs/en/compiler-architecture.md): parsing, semantic analysis, LLVM IR generation, and runtime cooperation.
- [Web UI package](docs/en/ez-web-ui.md): DOM bindings and Web UI API.
- [Android UI package](docs/en/ez-android-ui.md): Android native View bindings.
- [iOS UI package](docs/en/ez-ios-ui.md): UIKit bindings.

## Project Layout

```text
EzLang/
|-- cli/             # ez command-line entrypoint
|-- compiler/        # Compiler core: ANTLR4 parsing, semantic analysis, LLVM IR generation
|-- docs/            # Language, toolchain, runtime, and standard-library documentation
|-- editors/vscode/  # VS Code extension
|-- examples/        # EzLang examples
|-- grammar/         # ANTLR4 grammar
|-- lsp/             # EzLang LSP server
|-- packages/        # Standard library and UI packages
`-- project.toml     # Example project configuration for this repository
```

## Example Code

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

## License

This project uses the [MIT](LICENSE) license.

## Contact

Add me on WeChat for EzLang usage questions, feedback, and collaboration.

![WeChat QR code](wechat.png "WeChat QR code")
