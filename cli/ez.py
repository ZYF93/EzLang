"""EzLang 命令行工具入口"""

from __future__ import annotations

import argparse
import glob
import importlib
import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

llvm = None
_llvm_import_error: ModuleNotFoundError | ImportError | None = None
_analyze = None
_compile_source = None
_compiler_import_error: ModuleNotFoundError | ImportError | None = None
_parser_modules = None

VERSION = "0.1.0"
NATIVE_UNSUPPORTED = {"android", "ios", "emcc", "freestanding"}
VALID_ARCHES = {"x86_64", "aarch64", "arm", "wasm32", "riscv64"}
VALID_OSES = {"linux", "macos", "windows", "android", "ios", "emcc", "freestanding"}
TARGET_TRIPLES = {
    ("x86_64", "linux"): "x86_64-unknown-linux-gnu",
    ("aarch64", "linux"): "aarch64-unknown-linux-gnu",
    ("arm", "linux"): "armv7-unknown-linux-gnueabihf",
    ("riscv64", "linux"): "riscv64-unknown-linux-gnu",
    ("x86_64", "windows"): "x86_64-pc-windows-msvc",
    ("x86_64", "macos"): "x86_64-apple-darwin",
    ("aarch64", "macos"): "aarch64-apple-darwin",
    ("aarch64", "android"): "aarch64-linux-android",
    ("arm", "android"): "armv7-linux-androideabi",
    ("aarch64", "ios"): "arm64-apple-ios",
    ("wasm32", "emcc"): "wasm32-unknown-emscripten",
    ("x86_64", "freestanding"): "x86_64-unknown-none",
    ("aarch64", "freestanding"): "aarch64-unknown-none",
    ("riscv64", "freestanding"): "riscv64-unknown-none-elf",
}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
IMPORT_RE = re.compile(r'\bfrom\s+"([^"]+)"\s+import\s*\{')
IMPORT_DECL_RE = re.compile(r'\bfrom\s+"([^"]+)"\s+import\s*\{([^}]*)\}\s*;?')
DEFAULT_ENTRY_CANDIDATES = (
    "src/main.ez",
    "src/index.ez",
    "main.ez",
    "index.ez",
)


@dataclass
class OutputConfig:
    arch: str
    os: str
    dir: Path
    triple: str
    sdk: Path | None = None


@dataclass
class PluginConfig:
    name: str
    args: list[str] = field(default_factory=list)


@dataclass
class LoadedPlugin:
    config: PluginConfig
    module: ModuleType


@dataclass
class ProjectConfig:
    path: Path
    root: Path
    name: str
    version: str
    description: str = ""
    main: Path | None = None
    optimize: int = 0
    public: bool = True
    registry: str | None = None
    outputs: list[OutputConfig] = field(default_factory=list)
    deps: dict[str, str] = field(default_factory=dict)
    extern_search_paths: dict[str, list[Path]] = field(default_factory=dict)
    workspace_members: list[str] = field(default_factory=list)
    plugins: list[PluginConfig] = field(default_factory=list)
    log_compile_min_level: int | None = None
    warnings: list[str] = field(default_factory=list)


class CliError(Exception):
    pass


class EzArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = EzArgumentParser(prog="ez", description="EzLang 工具链")
    parser.add_argument("--version", action="store_true", help="显示版本号")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="输出更多诊断")
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init", help="初始化 EzLang 项目")
    init.add_argument("path", nargs="?", default=".", help="项目目录，默认当前目录")
    init.add_argument("--name", help="项目名称，默认使用目录名")
    init.add_argument("--template", help="从远程 git 仓库拉取模板初始化")
    init.set_defaults(func=cmd_init)

    build = subparsers.add_parser("build", help="编译项目并生成目标产物")
    _add_project_arg(build)
    build.set_defaults(func=cmd_build)

    run = subparsers.add_parser("run", help="编译并运行本地目标")
    _add_project_arg(run)
    run.add_argument("path", nargs="?", help="要运行的 .ez 文件；省略时运行 project.toml 的入口")
    run.set_defaults(func=cmd_run)

    test = subparsers.add_parser("test", help="编译并执行 EzLang 测试")
    _add_project_arg(test)
    test.add_argument("paths", nargs="*", help="测试文件或目录，默认查找 tests/ 下的 .ez 文件")
    test.set_defaults(func=cmd_test)

    install = subparsers.add_parser("install", help="安装 project.toml 声明的依赖")
    _add_project_arg(install)
    install.add_argument("-g", "--global", action="store_true", dest="global_install", help="把版本依赖安装到全局缓存")
    install.set_defaults(func=cmd_install)

    fmt = subparsers.add_parser("fmt", help="格式化 EzLang 源文件")
    _add_project_arg(fmt)
    fmt.add_argument("paths", nargs="*", help="要检查的文件或目录")
    fmt.add_argument("--dry-run", "--check", action="store_true", dest="check", help="只检查不修改")
    fmt.set_defaults(func=cmd_fmt)

    release = subparsers.add_parser("release", help="打包并发布当前项目")
    _add_project_arg(release)
    release.add_argument("--dry-run", action="store_true", help="只校验不发布")
    release.set_defaults(func=cmd_release)
    return parser


def _add_project_arg(parser: argparse.ArgumentParser):
    parser.add_argument("--project", help="project.toml 路径；默认从当前目录向上查找")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.version:
            print(f"ezlang {VERSION}")
            return 0
        if not hasattr(args, "func"):
            parser.print_help()
            return 0
        return args.func(args)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _load_compiler_modules():
    global _analyze, _compile_source, _compiler_import_error
    if _analyze is not None and _compile_source is not None:
        return _analyze, _compile_source
    try:
        from semantic.analyzer import analyze as loaded_analyze
        from codegen.llvm_codegen import compile_source as loaded_compile_source
    except (ModuleNotFoundError, ImportError) as first_exc:
        compiler_src = ROOT / "compiler" / "src"
        if str(compiler_src) not in sys.path:
            sys.path.insert(0, str(compiler_src))
        try:
            from semantic.analyzer import analyze as loaded_analyze
            from codegen.llvm_codegen import compile_source as loaded_compile_source
        except (ModuleNotFoundError, ImportError) as exc:
            _compiler_import_error = exc
            missing = getattr(exc, "name", None) or str(exc)
            raise CliError(f"编译器依赖不可用: {missing}。请先在仓库根目录执行 `pip install -e .`") from first_exc
    _analyze = loaded_analyze
    _compile_source = loaded_compile_source
    _compiler_import_error = None
    return _analyze, _compile_source


class _SyntaxErrorCollector:
    """收集 ANTLR 语法错误，避免 fmt 输出原始 traceback。"""

    def __init__(self):
        from antlr4.error.ErrorListener import ErrorListener

        class Collector(ErrorListener):
            def __init__(self):
                self.errors: list[str] = []

            def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
                self.errors.append(f"行 {line}:{column} - {msg}")

            def reportAmbiguity(self, recognizer, dfa, startIndex, stopIndex, exact, ambigAlts, configs):
                pass

            def reportAttemptingFullContext(self, recognizer, dfa, startIndex, stopIndex, conflictingAlts, configs):
                pass

            def reportContextSensitivity(self, recognizer, dfa, startIndex, stopIndex, prediction, configs):
                pass

        self.listener = Collector()

    @property
    def errors(self) -> list[str]:
        return self.listener.errors


def _load_parser_modules():
    global _parser_modules
    if _parser_modules is not None:
        return _parser_modules
    try:
        from antlr4 import CommonTokenStream, InputStream
        from parser.EzLangLexer import EzLangLexer
        from parser.EzLangParser import EzLangParser
    except (ModuleNotFoundError, ImportError) as first_exc:
        compiler_src = ROOT / "compiler" / "src"
        if str(compiler_src) not in sys.path:
            sys.path.insert(0, str(compiler_src))
        try:
            from antlr4 import CommonTokenStream, InputStream
            from parser.EzLangLexer import EzLangLexer
            from parser.EzLangParser import EzLangParser
        except (ModuleNotFoundError, ImportError) as exc:
            missing = getattr(exc, "name", None) or str(exc)
            raise CliError(f"解析器依赖不可用: {missing}。请先在仓库根目录执行 `pip install -e .`") from first_exc
    _parser_modules = (CommonTokenStream, InputStream, EzLangLexer, EzLangParser)
    return _parser_modules


def _parse_ez_source_errors(source: str) -> list[str]:
    CommonTokenStream, InputStream, EzLangLexer, EzLangParser = _load_parser_modules()
    errors = _SyntaxErrorCollector()
    lexer = EzLangLexer(InputStream(source))
    lexer.removeErrorListeners()
    lexer.addErrorListener(errors.listener)
    parser = EzLangParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(errors.listener)
    parser.compilationUnit()
    return errors.errors


def _load_llvm_binding():
    global llvm, _llvm_import_error
    if llvm is not None:
        return llvm
    try:
        from llvmlite import binding as loaded_llvm
    except (ModuleNotFoundError, ImportError) as exc:
        _llvm_import_error = exc
        return None
    llvm = loaded_llvm
    _llvm_import_error = None
    return llvm


def cmd_init(args) -> int:
    target = _resolve_path(Path.cwd(), args.path)
    if args.template:
        _init_from_git_template(target, args.template)
    else:
        _init_default_project(target, args.name)
    print(f"initialized {target}")
    return 0


def _init_default_project(target: Path, name: str | None):
    if target.exists() and not target.is_dir():
        raise CliError(f"项目路径不是目录: {target}")
    target.mkdir(parents=True, exist_ok=True)
    project_file = target / "project.toml"
    main_file = target / "src" / "main.ez"
    if project_file.exists():
        raise CliError(f"project.toml 已存在: {project_file}")
    if main_file.exists():
        raise CliError(f"入口文件已存在: {main_file}")
    project_name = (name or target.name or "ez_project").strip()
    if not project_name:
        raise CliError("项目名称不能为空")
    main_file.parent.mkdir(parents=True, exist_ok=True)
    project_file.write_text(
        f"""
[project]
name = "{project_name}"
version = "0.1.0"
main = "src/main.ez"
public = false
optimize = 2

[[output]]
arch = "{_native_arch()}"
os = "{_native_os()}"
dir = "dist/{_native_os()}-{_native_arch()}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    main_file.write_text(
        'from "std/io" import { println };\n\n'
        f'println(msg = "Hello from {project_name}");\n',
        encoding="utf-8",
    )


def _init_from_git_template(target: Path, template: str):
    if target.exists() and not target.is_dir():
        raise CliError(f"项目路径不是目录: {target}")
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ez-init-") as temp_dir:
        clone_dir = Path(temp_dir) / "template"
        completed = subprocess.run(
            ["git", "clone", "--depth", "1", template, str(clone_dir)],
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise CliError(f"模板拉取失败: {detail}")
        _copy_template_contents(clone_dir, target)


def _copy_template_contents(source: Path, target: Path):
    for child in source.iterdir():
        if child.name == ".git":
            continue
        destination = target / child.name
        if destination.exists():
            raise CliError(f"目标路径已存在，无法写入模板文件: {destination}")
        if child.is_dir():
            shutil.copytree(child, destination)
        else:
            shutil.copy2(child, destination)


def cmd_build(args) -> int:
    config = load_project(args.project, require_main=True)
    for warning in config.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    plugins = _load_plugins(config)
    source_plan = discover_sources(config)
    for output in config.outputs:
        context = _plugin_context(config, output, source_plan)
        _run_plugin_hook(plugins, "before_build", context)
        module, libs = _compile_project(config, output.os, source_plan, target_arch=output.arch, ensure_entrypoint=True)
        output.dir.mkdir(parents=True, exist_ok=True)
        _apply_target_triple(module, output.triple)
        out_file = output.dir / f"{config.name}.ll"
        out_file.write_text(str(module), encoding="utf-8")
        print(f"built {output.os}/{output.arch} {out_file}")
        obj_file = None
        exe_file = None
        sdk_artifact = None
        if _can_emit_object(output):
            obj_file = output.dir / f"{config.name}.o"
            obj_file.write_bytes(_emit_object(module, config.optimize, output.triple))
            print(f"object: {obj_file}")
            if _can_emit_native_object(output) and _module_defines_main(module):
                exe_file = output.dir / config.name
                _link_executable(obj_file, exe_file, libs, output.dir, output.os)
                print(f"executable: {exe_file}")
            elif output.sdk is not None and output.os in {"android", "ios", "emcc"}:
                sdk_artifact = _link_sdk_artifact(obj_file, output, libs, output.dir, config.name)
                print(f"sdk artifact: {sdk_artifact}")
                ui_bridge = _emit_mobile_ui_bridge(output, libs, output.dir, config.name, sdk_artifact)
                if ui_bridge is not None:
                    print(f"ui bridge: {ui_bridge}")
        context.update(
            {
                "ir": str(out_file),
                "object": str(obj_file) if obj_file is not None else None,
                "executable": str(exe_file) if exe_file is not None else None,
                "sdk_artifact": str(sdk_artifact) if sdk_artifact is not None else None,
                "extern_libs": [str(lib[0] if isinstance(lib, tuple) else lib) for lib in libs],
            }
        )
        _run_plugin_hook(plugins, "after_build", context)
        print(f"sources: {_format_sources(config, source_plan)}")
        if libs:
            print(f"extern libs: {_format_libs(libs)}")
    return 0


def cmd_run(args) -> int:
    config = _load_run_config(args.path, args.project)
    output = _select_run_output(config)
    if output.os != _native_os() or output.os in NATIVE_UNSUPPORTED:
        print(f"error: ez run only supports native target {_native_os()}, got {output.os}", file=sys.stderr)
        return 1
    if not _can_emit_native_object(output):
        print(f"error: ez run only supports native target {_native_os()}/{_native_arch()}, got {output.os}/{output.arch}", file=sys.stderr)
        return 1
    source_plan = discover_sources(config)
    module, libs = _compile_project(config, output.os, source_plan, target_arch=output.arch, ensure_entrypoint=True)
    _apply_target_triple(module, output.triple)
    output.dir.mkdir(parents=True, exist_ok=True)
    obj_file = output.dir / f"{config.name}.o"
    exe_file = output.dir / config.name
    obj_file.write_bytes(_emit_object(module, config.optimize, output.triple))
    _link_executable(obj_file, exe_file, libs, output.dir, output.os)
    completed = subprocess.run([str(exe_file)])
    return completed.returncode


def _load_run_config(path: str | None, project_path: str | Path) -> ProjectConfig:
    if path is None:
        return load_project(project_path, require_main=True)

    source = _resolve_path(Path.cwd(), path)
    if not source.exists():
        raise CliError(f"运行文件不存在: {source}")
    if source.suffix != ".ez":
        raise CliError(f"ez run 只支持 .ez 文件: {source}")

    project_file = _optional_project_file(project_path, source)
    if project_file is None:
        config = _single_file_run_config(source)
    else:
        config = load_project(project_file, require_main=False)
    config.main = source
    config.outputs = [_native_run_output(config.root, source)]
    return config


def _optional_project_file(project_path: str | Path | None, source: Path) -> Path | None:
    if project_path is not None:
        return _resolve_project_file(project_path)
    return find_project(source.parent)


def _single_file_run_config(source: Path) -> ProjectConfig:
    name = _run_module_name(source)
    return ProjectConfig(
        path=source,
        root=source.parent,
        name=name,
        version="0.0.0",
        description="",
        main=source,
        optimize=0,
        public=False,
        outputs=[],
    )


def _native_run_output(root: Path, source: Path) -> OutputConfig:
    arch = _native_arch()
    os_name = _native_os()
    return OutputConfig(
        arch=arch,
        os=os_name,
        dir=root / ".ez" / "run" / _run_module_name(source),
        triple=_target_triple(arch, os_name),
    )


def _run_module_name(source: Path) -> str:
    name = re.sub(r"\W+", "_", source.stem).strip("_")
    return name or "main"


def cmd_test(args) -> int:
    config = load_project(args.project, require_main=False)
    output = _select_test_output(config)
    test_files = _collect_test_files(config, args.paths)
    if not test_files:
        print("no tests")
        return 0

    passed = 0
    failed = 0
    for test_file in test_files:
        try:
            test_source = test_file.read_text(encoding="utf-8")
            test_locations = _test_registration_locations(test_source)
            source_plan = _discover_sources_from(config, test_file)
            module, libs = _compile_source_plan(
                config,
                output.os,
                source_plan,
                test_file.parent,
                target_arch=output.arch,
            )
            test_count = max(_count_test_symbols(test_file.read_text(encoding="utf-8")), 1)
            ran = False
            if _can_emit_native_object(output) and 'define i32 @"main"' in str(module):
                test_dir = config.root / ".ez" / "test" / re.sub(r"\W+", "_", test_file.stem)
                test_dir.mkdir(parents=True, exist_ok=True)
                _apply_target_triple(module, output.triple)
                obj_file = test_dir / f"{test_file.stem}.o"
                exe_file = test_dir / test_file.stem
                obj_file.write_bytes(_emit_object(module, config.optimize, output.triple))
                _link_executable(obj_file, exe_file, libs, test_dir, output.os)
                completed = subprocess.run([str(exe_file)], text=True, capture_output=True)
                ran = True
                if completed.returncode != 0:
                    detail = completed.stderr.strip() or completed.stdout.strip()
                    detail = _annotate_test_failure_detail(detail, test_file, test_locations, config.root)
                    suffix = f": {detail}" if detail else ""
                    raise CliError(f"运行失败，退出码 {completed.returncode}{suffix}")
            passed += test_count
            suffix = "run" if ran else "compile"
            print(f"ok {test_file.relative_to(config.root) if test_file.is_relative_to(config.root) else test_file} ({test_count} tests, {suffix})")
        except CliError as exc:
            failed += 1
            print(f"fail {test_file.relative_to(config.root) if test_file.is_relative_to(config.root) else test_file}: {exc}", file=sys.stderr)

    print(f"test result: {passed} passed; {failed} failed")
    return 0 if failed == 0 else 1


def cmd_install(args) -> int:
    config = load_project(args.project, require_main=False)
    for name, spec in config.deps.items():
        if spec == "@workspace":
            if args.global_install:
                raise CliError(f"workspace 依赖 {name} 不能全局安装")
            members = _expand_workspace_members(config)
            print(f"workspace {name} {','.join(str(p) for p in members)}")
        elif spec.startswith(".") or spec.startswith("/"):
            if args.global_install:
                raise CliError(f"本地路径依赖 {name} 不能全局安装")
            path = _resolve_path(config.root, spec)
            if not path.exists():
                raise CliError(f"依赖 {name} 路径不存在: {path}")
            print(f"local {name} {path}")
        else:
            if not SEMVER_RE.match(spec):
                raise CliError(f"依赖 {name} 版本号无效: {spec}")
            install_dir = _install_remote_dependency(config, name, spec, global_install=args.global_install)
            print(f"remote {name} {spec} {install_dir}")
    if not config.deps:
        print("no dependencies")
    return 0


def cmd_fmt(args) -> int:
    config = load_project(args.project, require_main=False)
    files = _collect_fmt_files(config, args.paths)
    changed: list[Path] = []
    for file in files:
        source = file.read_text(encoding="utf-8")
        errors = _parse_ez_source_errors(source)
        if errors:
            raise CliError(f"{file}: {'; '.join(errors)}")
        formatted = _format_ez_source(source)
        if formatted != source:
            changed.append(file)
            if not args.check:
                file.write_text(formatted, encoding="utf-8")
    if args.check:
        if changed:
            raise CliError("需要格式化: " + ", ".join(str(path) for path in changed))
        print(f"checked {len(files)} file{'s' if len(files) != 1 else ''}")
    else:
        print(f"formatted {len(files)} file{'s' if len(files) != 1 else ''}")
    return 0


def cmd_release(args) -> int:
    config = load_project(args.project, require_main=False)
    _validate_semver(config.version, "project.version")
    if not config.registry:
        raise CliError("release 需要 [project].registry")
    if not config.public:
        raise CliError("public = false 的包不能发布")
    package_name = f"{config.name}-{config.version}.zip"
    if args.dry_run:
        print(f"release dry-run {config.name} {config.version} -> {config.registry}")
        return 0
    package_data = _create_release_package(config)
    destination = _publish_release_package(config, package_name, package_data)
    print(f"released {config.name} {config.version} {destination}")
    return 0


def find_project(start: str | Path | None = None) -> Path | None:
    start_path = Path.cwd() if start is None else Path(start).expanduser()
    start_path = start_path.resolve()
    if start_path.is_file():
        start_path = start_path.parent
    for directory in (start_path, *start_path.parents):
        candidate = directory / "project.toml"
        if candidate.exists():
            return candidate.resolve()
    return None


def _resolve_project_file(path: str | Path | None) -> Path:
    if path is None:
        project_path = find_project()
        if project_path is None:
            raise CliError("未找到 project.toml，请先执行 ez init")
        return project_path
    project_path = Path(path).expanduser()
    if not project_path.is_absolute():
        project_path = Path.cwd() / project_path
    project_path = project_path.resolve()
    if project_path.is_dir():
        project_path = project_path / "project.toml"
    return project_path


def load_project(path: str | Path | None, *, require_main: bool) -> ProjectConfig:
    if tomllib is None:
        raise CliError("当前 Python 缺少 tomllib，请使用 Python 3.11+ 或安装 tomli")
    project_path = _resolve_project_file(path)
    if not project_path.exists():
        raise CliError(f"project.toml 不存在: {project_path}")
    with project_path.open("rb") as f:
        data = tomllib.load(f)
    root = project_path.parent
    project = data.get("project")
    if not isinstance(project, dict):
        raise CliError("缺少 [project]")
    name = _required_str(project, "name", "project.name")
    version = _required_str(project, "version", "project.version")
    description = project.get("description", "")
    if description is not None and not isinstance(description, str):
        raise CliError("project.description 必须是字符串")
    _validate_semver(version, "project.version")
    optimize = int(project.get("optimize", 2))
    if optimize < 0 or optimize > 3:
        raise CliError("project.optimize 必须在 0..3 之间")
    public = bool(project.get("public", True))
    registry = project.get("registry")
    main_value = project.get("main")
    main = _resolve_path(root, main_value) if isinstance(main_value, str) else None
    if main is None and require_main:
        main = _discover_default_main(root)
    if require_main:
        if main is None:
            raise CliError("未找到入口文件；请添加 src/main.ez、src/index.ez，或在 [project].main 中指定入口")
        if not main.exists():
            raise CliError(f"入口文件不存在: {main}")
    outputs = _parse_outputs(data.get("output"), root)
    extern_search_paths = _parse_extern_config(data.get("extern"), root)
    log_compile_min_level = _parse_log_config(data.get("log"))
    return ProjectConfig(
        path=project_path,
        root=root,
        name=name,
        version=version,
        description=description or "",
        main=main,
        optimize=optimize,
        public=public,
        registry=registry if isinstance(registry, str) else None,
        outputs=outputs[0],
        deps={k: str(v) for k, v in data.get("deps", {}).items()},
        extern_search_paths=extern_search_paths,
        workspace_members=list(data.get("workspace", {}).get("members", [])),
        plugins=_parse_plugins(data.get("plugins", [])),
        log_compile_min_level=log_compile_min_level,
        warnings=outputs[1],
    )


def _discover_default_main(root: Path) -> Path | None:
    matches = [_resolve_path(root, candidate) for candidate in DEFAULT_ENTRY_CANDIDATES if _resolve_path(root, candidate).exists()]
    if len(matches) > 1:
        names = ", ".join(str(path.relative_to(root)) for path in matches)
        raise CliError(f"发现多个默认入口文件: {names}；请在 [project].main 中指定一个")
    return matches[0] if matches else None


def _parse_log_config(raw_log) -> int | None:
    if raw_log is None:
        return None
    if not isinstance(raw_log, dict):
        raise CliError("[log] 必须是表")
    value = raw_log.get("compile_min_level")
    if value is None:
        return None
    level = int(value)
    if level < 0 or level > 4:
        raise CliError("log.compile_min_level 必须在 0..4 之间")
    return level


def _parse_plugins(raw_plugins) -> list[PluginConfig]:
    if raw_plugins is None:
        return []
    if not isinstance(raw_plugins, list):
        raise CliError("[[plugins]] 必须是表数组")
    plugins: list[PluginConfig] = []
    for raw in raw_plugins:
        if not isinstance(raw, dict):
            raise CliError("[[plugins]] 必须是表")
        name = _required_str(raw, "name", "plugins.name")
        args = raw.get("args", [])
        if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
            raise CliError("plugins.args 必须是字符串数组")
        plugins.append(PluginConfig(name=name, args=list(args)))
    return plugins



def _parse_outputs(raw_outputs, root: Path) -> tuple[list[OutputConfig], list[str]]:
    warnings: list[str] = []
    if raw_outputs is None:
        raw_outputs = [{"arch": _native_arch(), "os": _native_os(), "dir": "dist"}]
    if not isinstance(raw_outputs, list) or not raw_outputs:
        raise CliError("[[output]] 必须至少配置一个输出目标")
    outputs: list[OutputConfig] = []
    for raw in raw_outputs:
        if not isinstance(raw, dict):
            raise CliError("[[output]] 必须是表")
        arch = _required_str(raw, "arch", "output.arch")
        if arch == "wasm":
            warnings.append("arch 'wasm' is deprecated; use 'wasm32'")
            arch = "wasm32"
        os_name = _required_str(raw, "os", "output.os")
        if arch not in VALID_ARCHES:
            raise CliError(f"不支持的 arch: {arch}")
        if os_name not in VALID_OSES:
            raise CliError(f"不支持的 os: {os_name}")
        triple = _target_triple(arch, os_name)
        out_dir = _resolve_path(root, str(raw.get("dir", "dist")))
        sdk_value = raw.get("sdk")
        sdk = _resolve_path(root, sdk_value) if isinstance(sdk_value, str) else None
        if os_name in {"android", "ios"} and sdk is None:
            warnings.append(f"{os_name} target has no output.sdk; platform SDK integration will be unavailable")
        if sdk is not None and not sdk.exists():
            raise CliError(f"output.sdk 路径不存在: {sdk}")
        outputs.append(OutputConfig(arch=arch, os=os_name, dir=out_dir, triple=triple, sdk=sdk))
    return outputs, warnings


def _parse_extern_config(raw_extern, root: Path) -> dict[str, list[Path]]:
    """解析 [extern] 与 [extern.<platform>] 的搜索路径。"""
    result: dict[str, list[Path]] = {"*": []}
    if raw_extern is None:
        return result
    if not isinstance(raw_extern, dict):
        raise CliError("[extern] 必须是表")

    def parse_paths(value, label: str) -> list[Path]:
        if value is None:
            return []
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise CliError(f"{label}.search_paths 必须是字符串数组")
        return [_resolve_path(root, item) for item in value]

    result["*"] = parse_paths(raw_extern.get("search_paths"), "extern")
    for os_name in VALID_OSES:
        section = raw_extern.get(os_name)
        if section is None:
            continue
        if not isinstance(section, dict):
            raise CliError(f"[extern.{os_name}] 必须是表")
        result[os_name] = parse_paths(section.get("search_paths"), f"extern.{os_name}")
    return result


def discover_sources(config: ProjectConfig) -> list[Path]:
    if config.main is None:
        return []
    return _discover_sources_from(config, config.main)


def _discover_sources_from(config: ProjectConfig, entry: Path) -> list[Path]:
    ordered: list[Path] = []
    visiting: set[Path] = set()
    visited: set[Path] = set()

    def visit(path: Path):
        path = path.resolve()
        if path in visited:
            return
        if path in visiting:
            raise CliError(f"import 循环依赖: {path}")
        if not path.exists():
            raise CliError(f"import 路径不存在: {path}")
        visiting.add(path)
        source = path.read_text(encoding="utf-8")
        for import_path in IMPORT_RE.findall(source):
            visit(_resolve_import(path.parent, import_path, config))
        visiting.remove(path)
        visited.add(path)
        ordered.append(path)

    visit(entry)
    return ordered


def _compile_source_plan(config: ProjectConfig, compile_target: str, source_plan: list[Path], base_dir: Path,
                         target_arch: str | None = None, ensure_entrypoint: bool = False):
    analyze, compile_source = _load_compiler_modules()
    source = _merge_source_plan(config, source_plan)
    analyzer = analyze(
        source,
        base_dir=base_dir,
        compile_target=compile_target,
        allow_top_level_return=ensure_entrypoint,
    )
    if analyzer.symbols.has_errors():
        resolved_errors = _resolve_extern_errors(analyzer.symbols.errors, config, compile_target, base_dir)
        if resolved_errors:
            raise CliError("语义错误: " + "; ".join(resolved_errors))
    module, errors, libs = compile_source(
        source,
        module_name=config.name,
        compile_target=compile_target,
        target_arch=target_arch,
        log_compile_min_level=config.log_compile_min_level,
        ensure_entrypoint=ensure_entrypoint,
        base_dir=base_dir,
        source_name=source_plan[-1] if source_plan else None,
    )
    errors = _resolve_extern_errors(errors, config, compile_target, base_dir)
    if errors:
        raise CliError("编译错误: " + "; ".join(errors))
    libs = _resolve_extern_libs(libs, config, compile_target, base_dir)
    return module, libs


def _plugin_context(config: ProjectConfig, output: OutputConfig, source_plan: list[Path]) -> dict[str, Any]:
    return {
        "project": config.name,
        "version": config.version,
        "description": config.description,
        "root": str(config.root),
        "project_file": str(config.path),
        "main": str(config.main) if config.main is not None else None,
        "optimize": config.optimize,
        "output": {
            "arch": output.arch,
            "os": output.os,
            "dir": str(output.dir),
            "triple": output.triple,
            "sdk": str(output.sdk) if output.sdk is not None else None,
        },
        "sources": [str(path) for path in source_plan],
    }



def _load_plugins(config: ProjectConfig) -> list[LoadedPlugin]:
    plugins: list[LoadedPlugin] = []
    for plugin in config.plugins:
        module = _load_plugin_module(config, plugin.name)
        plugins.append(LoadedPlugin(config=plugin, module=module))
    return plugins



def _load_plugin_module(config: ProjectConfig, name: str) -> ModuleType:
    local_path = _resolve_plugin_path(config, name)
    if local_path is not None:
        return _load_plugin_file(local_path, name)
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise CliError(f"插件加载失败 {name}: {exc}") from exc



def _resolve_plugin_path(config: ProjectConfig, name: str) -> Path | None:
    dep_spec = config.deps.get(name)
    candidate_name = dep_spec if dep_spec and (dep_spec.startswith(".") or dep_spec.startswith("/") or dep_spec.endswith(".py")) else name
    path = Path(candidate_name).expanduser()
    if path.is_absolute() or candidate_name.startswith(".") or candidate_name.endswith(".py"):
        candidate = path if path.is_absolute() else config.root / path
        if not candidate.exists():
            raise CliError(f"插件不存在: {candidate.resolve()}")
        return candidate.resolve()
    return None



def _load_plugin_file(path: Path, name: str) -> ModuleType:
    if path.is_dir():
        path = path / "plugin.py"
    if path.suffix != ".py" or not path.exists():
        raise CliError(f"插件必须是 Python 文件: {path}")
    module_name = "ez_plugin_" + re.sub(r"\W+", "_", name)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise CliError(f"插件加载失败: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise CliError(f"插件加载失败 {path}: {exc}") from exc
    return module



def _run_plugin_hook(plugins: list[LoadedPlugin], hook_name: str, context: dict[str, Any]):
    for plugin in plugins:
        hook = getattr(plugin.module, hook_name, None)
        if hook is None:
            continue
        if not callable(hook):
            raise CliError(f"插件 {plugin.config.name} 的 {hook_name} 不是可调用对象")
        hook_context = dict(context)
        hook_context["plugin"] = plugin.config.name
        hook_context["args"] = list(plugin.config.args)
        try:
            hook(hook_context)
        except Exception as exc:
            raise CliError(f"插件 {plugin.config.name} 执行 {hook_name} 失败: {exc}") from exc



def _compile_project(config: ProjectConfig, compile_target: str, source_plan: list[Path] | None = None,
                     target_arch: str | None = None, ensure_entrypoint: bool = False):
    source_plan = source_plan or discover_sources(config)
    base_dir = config.main.parent if config.main is not None else config.root
    return _compile_source_plan(
        config,
        compile_target,
        source_plan,
        base_dir,
        target_arch=target_arch,
        ensure_entrypoint=ensure_entrypoint,
    )


def _can_emit_native_object(output: OutputConfig) -> bool:
    return output.os == _native_os() and output.arch == _native_arch() and _load_llvm_binding() is not None


def _can_emit_object(output: OutputConfig) -> bool:
    return _load_llvm_binding() is not None and output.triple != ""


def _module_defines_main(module) -> bool:
    return 'define i32 @"main"' in str(module)


def _extern_search_roots(config: ProjectConfig, compile_target: str, base_dir: Path) -> list[Path]:
    roots: list[Path] = [base_dir, config.root]
    roots.extend(config.extern_search_paths.get("*", []))
    roots.extend(config.extern_search_paths.get(compile_target, []))
    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _is_system_extern(lib: str) -> bool:
    path = Path(lib)
    return not path.is_absolute() and path.parent == Path(".") and path.suffix == ""


def _resolve_extern_lib(lib, config: ProjectConfig, compile_target: str, base_dir: Path) -> str:
    raw = str(lib[0] if isinstance(lib, tuple) else lib)
    if _is_system_extern(raw):
        return raw
    path = Path(raw).expanduser()
    if path.is_absolute():
        return str(path.resolve())
    matches: list[Path] = []
    for root in _extern_search_roots(config, compile_target, base_dir):
        candidate = (root / path).resolve()
        if candidate.exists():
            matches.append(candidate)
    unique = sorted(dict.fromkeys(matches))
    if len(unique) > 1:
        raise CliError(f"extern 路径存在歧义: {raw} -> {', '.join(str(p) for p in unique)}")
    if len(unique) == 1:
        return str(unique[0])
    return str((base_dir / path).resolve())


def _resolve_extern_libs(libs, config: ProjectConfig, compile_target: str, base_dir: Path) -> list[str]:
    return [_resolve_extern_lib(lib, config, compile_target, base_dir) for lib in libs]


def _resolve_extern_errors(errors: list[str], config: ProjectConfig, compile_target: str, base_dir: Path) -> list[str]:
    """如果 extern 缺失可由 project.toml 搜索路径解析，则消除旧诊断。"""
    resolved_errors: list[str] = []
    pattern = re.compile(r"extern 路径不存在：'([^']+)'")
    for error in errors:
        match = pattern.search(error)
        if match is None:
            resolved_errors.append(error)
            continue
        raw = match.group(1)
        resolved = _resolve_extern_lib(raw, config, compile_target, base_dir)
        if Path(resolved).exists() or _is_system_extern(resolved):
            continue
        resolved_errors.append(error + f"。已搜索: {', '.join(str(p) for p in _extern_search_roots(config, compile_target, base_dir))}")
    return resolved_errors


def _target_triple(arch: str, os_name: str) -> str:
    triple = TARGET_TRIPLES.get((arch, os_name))
    if triple is None:
        raise CliError(f"不支持的目标组合: {os_name}/{arch}")
    return triple


def _apply_target_triple(module, triple: str):
    module.triple = triple


def _emit_object(module, optimize: int, triple: str) -> bytes:
    loaded_llvm = _load_llvm_binding()
    if loaded_llvm is None:
        raise CliError("llvmlite binding 不可用，无法生成对象文件")
    try:
        loaded_llvm.initialize_all_targets()
        loaded_llvm.initialize_all_asmprinters()
        llvm_module = loaded_llvm.parse_assembly(str(module))
        llvm_module.verify()
        target = loaded_llvm.Target.from_triple(triple)
        machine = target.create_target_machine(opt=optimize)
        return machine.emit_object(llvm_module)
    except RuntimeError as exc:
        raise CliError(f"对象文件生成失败: {exc}") from exc


def _link_executable(obj_file: Path, exe_file: Path, libs: list[str] | None = None, build_dir: Path | None = None, compile_target: str | None = None):
    libs = libs or []
    build_dir = build_dir or obj_file.parent
    link_inputs = [str(obj_file)]
    generated_objects: list[Path] = []
    for lib in libs:
        path = Path(lib)
        if _is_system_extern(lib):
            link_inputs.append(f"-l{lib}")
            continue
        if path.suffix == ".c":
            compiled = _compile_c_extern(path, build_dir, compile_target)
            generated_objects.append(compiled)
            link_inputs.append(str(compiled))
            continue
        if path.suffix == ".framework":
            link_inputs.extend(["-framework", path.stem])
            continue
        if path.suffix == ".js":
            continue
        link_inputs.append(str(path))
    completed = subprocess.run(
        ["cc", *link_inputs, "-o", str(exe_file)],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CliError(f"链接失败: {detail}")


def _link_sdk_artifact(obj_file: Path, output: OutputConfig, libs: list[str], build_dir: Path, name: str) -> Path:
    if output.sdk is None:
        raise CliError(f"{output.os} 目标需要 output.sdk 才能执行 SDK 链接")
    if output.os == "emcc":
        artifact = build_dir / f"{name}.js"
        cmd = [str(_sdk_tool(output.sdk, ["emcc", "upstream/emscripten/emcc"])), str(obj_file), "-o", str(artifact)]
        if _emcc_needs_asyncify(libs):
            cmd.append("-sASYNCIFY")
        for lib in libs:
            path = Path(lib)
            if path.suffix == ".js":
                cmd.extend(["--js-library", str(path)])
            elif _is_system_extern(lib):
                cmd.append(f"-l{lib}")
            else:
                cmd.append(str(path))
        _run_sdk_command(cmd, "emcc SDK 链接失败")
        return artifact

    if output.os == "android":
        artifact = build_dir / f"lib{name}.so"
        clang = _sdk_tool(output.sdk, [
            f"toolchains/llvm/prebuilt/{_ndk_host_tag()}/bin/{output.triple}21-clang",
            f"toolchains/llvm/prebuilt/{_ndk_host_tag()}/bin/clang",
            "bin/clang",
            "clang",
        ])
        link_inputs = _sdk_native_link_inputs(libs, build_dir, output.os, clang)
        if _uses_mobile_ui("android", libs):
            entry = _write_android_jni_entry(build_dir)
            link_inputs.append(str(_compile_c_extern(entry, build_dir, output.os, cc=str(clang))))
        _run_sdk_command([str(clang), "-shared", str(obj_file), *link_inputs, "-o", str(artifact)], "Android SDK 链接失败")
        return artifact

    if output.os == "ios":
        artifact = build_dir / f"lib{name}.dylib"
        clang = _sdk_tool(output.sdk, ["usr/bin/clang", "Toolchains/XcodeDefault.xctoolchain/usr/bin/clang", "bin/clang", "clang"])
        link_inputs = _sdk_native_link_inputs(libs, build_dir, output.os, clang)
        _run_sdk_command([str(clang), "-dynamiclib", str(obj_file), *link_inputs, "-o", str(artifact)], "iOS SDK 链接失败")
        return artifact

    raise CliError(f"{output.os} 目标暂不支持 SDK 链接")


def _emcc_needs_asyncify(libs: list[str]) -> bool:
    """emcc suspend source 与 flow runtime 依赖 Asyncify 恢复执行栈。"""
    async_libs = {
        "packages/std/emcc/runtime.js",
        "packages/std/emcc/time.js",
        "packages/std/emcc/io.js",
        "packages/std/emcc/fs.js",
        "packages/std/emcc/stream.js",
        "packages/std/emcc/process.js",
        "packages/std/emcc/compress.js",
        "packages/std/emcc/net/http.js",
        "packages/std/emcc/net/tcp.js",
        "packages/std/emcc/net/ws.js",
    }
    for lib in libs:
        path = Path(lib).as_posix()
        if any(path.endswith(item) for item in async_libs):
            return True
    return False


def _emit_mobile_ui_bridge(output: OutputConfig, libs: list[str], build_dir: Path, name: str, artifact: Path) -> Path | None:
    """为移动 UI 包生成宿主桥接模板，供平台工程直接接入动态库。"""
    if _uses_mobile_ui("android", libs) and output.os == "android":
        return _emit_android_ui_bridge(build_dir, name, artifact)
    if _uses_mobile_ui("ios", libs) and output.os == "ios":
        return _emit_ios_ui_bridge(build_dir, name, artifact)
    return None


def _uses_mobile_ui(os_name: str, libs: list[str]) -> bool:
    marker = "ez-android-ui" if os_name == "android" else "ez-ios-ui"
    return marker in "\n".join(str(lib) for lib in libs)


def _write_android_jni_entry(build_dir: Path) -> Path:
    source = build_dir / ".ez" / "android_jni_entry.c"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        '// EzLang Android 宿主入口：把 Kotlin Activity 的 native main 转发到 EzLang main。\n'
        '#include <jni.h>\n\n'
        'extern int main(void);\n\n'
        'extern void ezAndroidSetScreenMetrics(int width, int height, float density);\n\n'
        'JNIEXPORT jint JNICALL Java_dev_ezlang_EzLangActivity_main(JNIEnv *env, jclass cls) {\n'
        '    (void)env;\n'
        '    (void)cls;\n'
        '    return (jint)main();\n'
        '}\n'
        'JNIEXPORT void JNICALL Java_dev_ezlang_EzLangActivity_ezAndroidSetScreenMetrics(JNIEnv *env, jclass cls, jint width, jint height, jfloat density) {\n'
        '    (void)env;\n'
        '    (void)cls;\n'
        '    ezAndroidSetScreenMetrics((int)width, (int)height, (float)density);\n'
        '}\n',
        encoding="utf-8",
    )
    return source


def _emit_android_ui_bridge(build_dir: Path, name: str, artifact: Path) -> Path:
    bridge_dir = build_dir / "ez-android-ui-bridge"
    src_dir = bridge_dir / "app" / "src" / "main" / "java" / "dev" / "ezlang"
    src_dir.mkdir(parents=True, exist_ok=True)
    jni_dir = bridge_dir / "app" / "src" / "main" / "jniLibs" / "arm64-v8a"
    jni_dir.mkdir(parents=True, exist_ok=True)
    if artifact.exists():
        shutil.copy2(artifact, jni_dir / artifact.name)
    manifest = bridge_dir / "app" / "src" / "main" / "AndroidManifest.xml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '  <application android:theme="@style/AppTheme" android:label="EzLang">\n'
        '    <activity android:name=".EzLangActivity" android:exported="true">\n'
        '      <intent-filter>\n'
        '        <action android:name="android.intent.action.MAIN" />\n'
        '        <category android:name="android.intent.category.LAUNCHER" />\n'
        '      </intent-filter>\n'
        '    </activity>\n'
        '  </application>\n'
        '</manifest>\n',
        encoding="utf-8",
    )
    (src_dir / "EzLangActivity.kt").write_text(
        'package dev.ezlang\n\n'
        'import android.app.Activity\n'
        'import android.os.Bundle\n'
        'import android.widget.FrameLayout\n\n'
        'class EzLangActivity : Activity() {\n'
        '    companion object {\n'
        f'        init {{ System.loadLibrary("{artifact.stem.removeprefix("lib")}") }}\n'
        '        @JvmStatic external fun main(): Int\n'
        '        @JvmStatic external fun ezAndroidSetScreenMetrics(width: Int, height: Int, density: Float)\n'
        '    }\n\n'
        '    override fun onCreate(savedInstanceState: Bundle?) {\n'
        '        super.onCreate(savedInstanceState)\n'
        '        val root = FrameLayout(this)\n'
        '        setContentView(root)\n'
        '        val metrics = resources.displayMetrics\n'
        '        ezAndroidSetScreenMetrics(metrics.widthPixels, metrics.heightPixels, metrics.density)\n'
        '        main()\n'
        '    }\n'
        '}\n',
        encoding="utf-8",
    )
    (bridge_dir / "CMakeLists.txt").write_text(
        'cmake_minimum_required(VERSION 3.22)\n'
        f'project({name}_android_bridge)\n'
        '# EzLang 产物由 CLI 生成在同级 dist 目录；Android 工程可把 lib 复制到 jniLibs。\n',
        encoding="utf-8",
    )
    (bridge_dir / "README.md").write_text(
        f'# EzLang Android UI Bridge\n\n动态库: `{artifact.name}`\n\n'
        '把 `app/src/main` 合并到 Android 工程，确保动态库位于 `jniLibs/<abi>/`。\n',
        encoding="utf-8",
    )
    return bridge_dir


def _emit_ios_ui_bridge(build_dir: Path, name: str, artifact: Path) -> Path:
    bridge_dir = build_dir / "ez-ios-ui-bridge"
    sources = bridge_dir / "Sources" / "EzLangBridge"
    sources.mkdir(parents=True, exist_ok=True)
    libs_dir = bridge_dir / "Libraries"
    libs_dir.mkdir(parents=True, exist_ok=True)
    if artifact.exists():
        shutil.copy2(artifact, libs_dir / artifact.name)
    (sources / "EzLangViewController.swift").write_text(
        'import UIKit\n\n'
        '@_silgen_name("main") private func ezlangMain() -> Int32\n\n'
        '@_silgen_name("ezIosSetScreenMetrics") private func ezIosSetScreenMetrics(_ width: Float, _ height: Float, _ scale: Float, _ safeTop: Float, _ safeLeft: Float, _ safeBottom: Float, _ safeRight: Float, _ statusBarHeight: Float)\n\n'
        'public final class EzLangViewController: UIViewController {\n'
        '    public override func viewDidLoad() {\n'
        '        super.viewDidLoad()\n'
        '        view.backgroundColor = .systemBackground\n'
        '        let bounds = UIScreen.main.bounds\n'
        '        let insets = view.safeAreaInsets\n'
        '        ezIosSetScreenMetrics(Float(bounds.width), Float(bounds.height), Float(UIScreen.main.scale), Float(insets.top), Float(insets.left), Float(insets.bottom), Float(insets.right), Float(view.window?.windowScene?.statusBarManager?.statusBarFrame.height ?? 0))\n'
        '        _ = ezlangMain()\n'
        '    }\n'
        '}\n',
        encoding="utf-8",
    )
    (bridge_dir / "Package.swift").write_text(
        '// swift-tools-version: 5.9\n'
        'import PackageDescription\n\n'
        f'let package = Package(name: "{name}IOSBridge", products: [\n'
        '    .library(name: "EzLangBridge", targets: ["EzLangBridge"])\n'
        '], targets: [\n'
        '    .target(name: "EzLangBridge")\n'
        '])\n',
        encoding="utf-8",
    )
    (bridge_dir / "Info.plist").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict><key>UILaunchStoryboardName</key><string>LaunchScreen</string></dict></plist>\n',
        encoding="utf-8",
    )
    (bridge_dir / "README.md").write_text(
        f'# EzLang iOS UI Bridge\n\n动态库: `{artifact.name}`\n\n'
        '把 `Sources/EzLangBridge` 加入 Xcode 工程，并把动态库加入 Link Binary With Libraries。\n',
        encoding="utf-8",
    )
    return bridge_dir


def _sdk_native_link_inputs(libs: list[str], build_dir: Path, compile_target: str, clang: Path) -> list[str]:
    inputs: list[str] = []
    for lib in libs:
        path = Path(lib)
        if _is_system_extern(lib):
            inputs.append(f"-l{lib}")
        elif path.suffix == ".c":
            inputs.append(str(_compile_c_extern(path, build_dir, compile_target, cc=str(clang))))
        elif path.suffix == ".framework":
            inputs.extend(["-framework", path.stem])
        elif path.suffix == ".js":
            continue
        else:
            inputs.append(str(path))
    return inputs


def _sdk_tool(sdk: Path, candidates: list[str]) -> Path:
    for candidate in candidates:
        path = (sdk / candidate).resolve()
        if path.exists() and path.is_file():
            return path
    joined = ", ".join(candidates)
    raise CliError(f"output.sdk 缺少工具: {joined}")


def _ndk_host_tag() -> str:
    if sys.platform == "darwin":
        return "darwin-x86_64"
    if sys.platform.startswith("linux"):
        return "linux-x86_64"
    if sys.platform.startswith("win"):
        return "windows-x86_64"
    return "linux-x86_64"


def _run_sdk_command(cmd: list[str], label: str):
    completed = subprocess.run(cmd, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CliError(f"{label}: {detail}")


def _compile_c_extern(source: Path, build_dir: Path, compile_target: str | None, cc: str = "cc") -> Path:
    if not source.exists():
        raise CliError(f"extern C 源码不存在: {source}")
    extern_dir = build_dir / ".extern"
    extern_dir.mkdir(parents=True, exist_ok=True)
    obj_name = re.sub(r"\W+", "_", str(source.resolve())) + ".o"
    obj_file = extern_dir / obj_name
    cmd = [cc, "-c", str(source), "-o", str(obj_file)]
    if compile_target in {"linux", "macos", "windows", "android", "ios"}:
        cmd.insert(1, f"-DEZ_TARGET_{compile_target.upper()}=1")
    completed = subprocess.run(cmd, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CliError(f"extern C 编译失败 {source}: {detail}")
    return obj_file


def _resolve_import(base_dir: Path, import_path: str, config: ProjectConfig) -> Path:
    path = Path(import_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    candidate = (base_dir / path).resolve()
    if candidate.exists():
        return candidate
    if import_path.startswith("std/"):
        std_candidate = (ROOT / "packages" / f"{import_path}.ez").resolve()
        if std_candidate.exists():
            return std_candidate
    package_candidate = _resolve_package_import(import_path, config)
    if package_candidate is not None:
        return package_candidate
    return (config.root / path).resolve()


def _resolve_package_import(import_path: str, config: ProjectConfig) -> Path | None:
    """解析 from "pkg" / from "pkg/sub" 形式的依赖包入口。"""
    if import_path.startswith(".") or import_path.endswith(".ez"):
        return None
    parts = import_path.split("/", 1)
    package_name = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    roots = _dependency_roots(config, package_name)
    for root in roots:
        entry = _package_entry(root, package_name, rest)
        if entry is not None:
            return entry
    return None


def _dependency_roots(config: ProjectConfig, package_name: str) -> list[Path]:
    roots: list[Path] = []
    bundled_root = ROOT / "packages" / package_name
    if bundled_root.exists():
        roots.append(bundled_root)
    dep_spec = config.deps.get(package_name)
    if dep_spec:
        if dep_spec == "@workspace":
            for member in _expand_workspace_members(config):
                if _workspace_member_name(member) == package_name or member.name == package_name:
                    roots.append(member)
        elif dep_spec.startswith(".") or dep_spec.startswith("/"):
            roots.append(_resolve_path(config.root, dep_spec))
        elif SEMVER_RE.match(dep_spec):
            roots.append(config.root / ".ez" / "deps" / package_name / dep_spec)
            roots.append(_global_dependency_dir(package_name, dep_spec))

    installed_root = config.root / ".ez" / "deps" / package_name
    if installed_root.exists():
        if _package_entry(installed_root, package_name, "") is not None:
            roots.append(installed_root)
        else:
            versions = [p for p in installed_root.iterdir() if p.is_dir()]
            if len(versions) == 1:
                roots.append(versions[0])
    global_installed_root = _ez_home() / "deps" / package_name
    if global_installed_root.exists():
        if _package_entry(global_installed_root, package_name, "") is not None:
            roots.append(global_installed_root)
        else:
            versions = [p for p in global_installed_root.iterdir() if p.is_dir()]
            if len(versions) == 1:
                roots.append(versions[0])
    return sorted(dict.fromkeys(p.resolve() for p in roots))


def _workspace_member_name(member: Path) -> str | None:
    project_file = member / "project.toml"
    if not project_file.exists() or tomllib is None:
        return None
    try:
        with project_file.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return None
    project = data.get("project")
    if isinstance(project, dict) and isinstance(project.get("name"), str):
        return project["name"]
    return None


def _package_entry(root: Path, package_name: str, rest: str) -> Path | None:
    root = root.resolve()
    if root.is_file():
        return root if not rest else None
    if not root.exists() or not root.is_dir():
        return None
    if rest:
        sub = root / rest
        candidates = [sub]
        if sub.suffix != ".ez":
            candidates.extend([sub.with_suffix(".ez"), sub / "index.ez", sub / f"{sub.name}.ez"])
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        return None

    project_file = root / "project.toml"
    if project_file.exists() and tomllib is not None:
        try:
            with project_file.open("rb") as f:
                data = tomllib.load(f)
            main_value = data.get("project", {}).get("main")
            if isinstance(main_value, str):
                candidate = _resolve_path(root, main_value)
                if candidate.exists() and candidate.is_file():
                    return candidate
        except Exception:
            pass

    for candidate in [root / f"{package_name}.ez", root / "index.ez", root / "src" / "index.ez"]:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _strip_imports(source: str) -> str:
    return "\n".join(line for line in source.splitlines() if IMPORT_RE.search(line) is None) + "\n"


def _merge_source_plan(config: ProjectConfig, source_plan: list[Path]) -> str:
    if not source_plan:
        return ""
    requested: dict[Path, dict[str, str] | None] = {path.resolve(): {} for path in source_plan[:-1]}
    for importer in source_plan:
        for import_path, specs in _parse_import_decls(importer.read_text(encoding="utf-8")):
            module_path = _resolve_import(importer.parent, import_path, config).resolve()
            module_specs = requested.setdefault(module_path, {})
            if module_specs is not None:
                module_specs.update(specs)

    chunks: list[str] = []
    entry = source_plan[-1].resolve()
    for path in source_plan:
        resolved = path.resolve()
        source = path.read_text(encoding="utf-8")
        if resolved == entry:
            chunks.append(_strip_imports(source))
        else:
            chunks.append(_filter_imported_source(source, requested.get(resolved)))
    return "\n".join(chunks)


def _parse_import_decls(source: str) -> list[tuple[str, dict[str, str]]]:
    imports: list[tuple[str, dict[str, str]]] = []
    for match in IMPORT_DECL_RE.finditer(source):
        specs: dict[str, str] = {}
        for raw_spec in match.group(2).split(','):
            spec = raw_spec.strip()
            if not spec:
                continue
            parts = re.split(r'\s+as\s+', spec, maxsplit=1)
            name = parts[0].strip()
            alias = parts[1].strip() if len(parts) == 2 else name
            if name:
                specs[name] = alias
        imports.append((match.group(1), specs))
    return imports


def _filter_imported_source(source: str, requested: dict[str, str] | None) -> str:
    if requested is None:
        return _strip_imports(source)
    private_chunks: list[str] = []
    exports: dict[str, str] = {}
    for stmt in _top_level_statements(source):
        stripped = stmt.lstrip()
        if not stripped or IMPORT_RE.search(stripped):
            continue
        export_name = _exported_decl_name(stripped)
        if export_name is not None:
            exports[export_name] = stmt
            continue
        private_chunks.append(stmt)

    selected = {name for name in requested if name in exports}
    changed = True
    while changed:
        changed = False
        selected_text = "\n".join(exports[name] for name in selected)
        for name in exports:
            if name in selected:
                continue
            if re.search(rf'\b{re.escape(name)}\b', selected_text):
                selected.add(name)
                changed = True

    chunks = private_chunks + [
        _rename_exported_decl(exports[name], name, requested.get(name, name)) if name in requested else exports[name]
        for name in exports
        if name in selected
    ]
    return "\n".join(chunks) + "\n"


def _top_level_statements(source: str) -> list[str]:
    statements: list[str] = []
    start = 0
    brace_depth = 0
    paren_depth = 0
    bracket_depth = 0
    in_line_comment = False
    in_block_comment = False
    in_string = False
    escape = False
    index = 0
    length = len(source)

    while index < length:
        char = source[index]
        nxt = source[index + 1] if index + 1 < length else ""
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            if char == "*" and nxt == "/":
                in_block_comment = False
                index += 2
            else:
                index += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == "/" and nxt == "/":
            in_line_comment = True
            index += 2
            continue
        if char == "/" and nxt == "*":
            in_block_comment = True
            index += 2
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
            if brace_depth == 0 and paren_depth == 0 and bracket_depth == 0:
                end = index + 1
                while end < length and source[end] in " \t\r\n;":
                    end += 1
                statements.append(source[start:end].strip())
                start = end
                index = end
                continue
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif char == ";" and brace_depth == 0 and paren_depth == 0 and bracket_depth == 0:
            end = index + 1
            statements.append(source[start:end].strip())
            start = end
        index += 1
    tail = source[start:].strip()
    if tail:
        statements.append(tail)
    return statements


def _exported_decl_name(stmt: str) -> str | None:
    text = _strip_leading_comments(stmt).strip()
    if not text.startswith("export"):
        return None
    rest = text[len("export"):].lstrip()
    match = re.match(r'(?:declare\s+)?(?:const|let|static)\s+([A-Za-z_][A-Za-z0-9_]*)\b', rest)
    if match:
        return match.group(1)
    match = re.match(r'struct\s+([A-Z][A-Za-z0-9_]*)\b', rest)
    if match:
        return match.group(1)
    match = re.match(r'type\s+([A-Z][A-Za-z0-9_]*)\b', rest)
    if match:
        return match.group(1)
    return None


def _rename_exported_decl(stmt: str, name: str, alias: str) -> str:
    if not alias or alias == name:
        return stmt
    offset = stmt.find("export")
    if offset < 0:
        return stmt
    head = stmt[:offset]
    body = stmt[offset:]
    body = re.sub(
        rf'\b((?:export\s+)?(?:declare\s+)?(?:const|let|static)\s+){re.escape(name)}\b',
        rf'\1{alias}',
        body,
        count=1,
    )
    body = re.sub(
        rf'\b((?:export\s+)?struct\s+){re.escape(name)}\b',
        rf'\1{alias}',
        body,
        count=1,
    )
    body = re.sub(
        rf'\b((?:export\s+)?type\s+){re.escape(name)}\b',
        rf'\1{alias}',
        body,
        count=1,
    )
    return head + body


def _strip_leading_comments(text: str) -> str:
    while True:
        stripped = text.lstrip()
        if stripped.startswith("//"):
            newline = stripped.find("\n")
            if newline < 0:
                return ""
            text = stripped[newline + 1:]
            continue
        if stripped.startswith("/*"):
            end = stripped.find("*/", 2)
            if end < 0:
                return ""
            text = stripped[end + 2:]
            continue
        return stripped


def _format_sources(config: ProjectConfig, sources: list[Path]) -> str:
    return ", ".join(str(path.relative_to(config.root)) if path.is_relative_to(config.root) else str(path) for path in sources)


def _collect_fmt_files(config: ProjectConfig, paths: list[str]) -> list[Path]:
    roots = [_resolve_path(Path.cwd(), p) for p in paths] if paths else [Path.cwd()]
    files: list[Path] = []
    for root in roots:
        if root is None:
            continue
        if root.is_dir():
            files.extend(_iter_fmt_files(root))
        elif root.is_file() and root.suffix == ".ez":
            files.append(root)
        else:
            raise CliError(f"fmt 只支持 .ez 文件或目录: {root}")
    return sorted(dict.fromkeys(path.resolve() for path in files))


_FMT_SKIP_DIRS = {".ez", ".git", ".venv", "venv", "node_modules", "dist", "out", "__pycache__"}


def _iter_fmt_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _FMT_SKIP_DIRS]
        current_path = Path(current)
        for filename in filenames:
            if filename.endswith(".ez"):
                files.append(current_path / filename)
    return sorted(files)


def _collect_test_files(config: ProjectConfig, paths: list[str]) -> list[Path]:
    roots = [_resolve_path(Path.cwd(), p) for p in paths]
    if not roots:
        tests_dir = config.root / "tests"
        roots = [tests_dir] if tests_dir.exists() else ([config.main] if config.main else [])
    files: list[Path] = []
    for root in roots:
        if root is None:
            continue
        if root.is_dir():
            files.extend(sorted(root.rglob("*.ez")))
        elif root.suffix == ".ez":
            files.append(root)
        else:
            raise CliError(f"test 只支持 .ez 文件或目录: {root}")
    return sorted(dict.fromkeys(path.resolve() for path in files))


def _count_test_symbols(source: str) -> int:
    names = set(re.findall(r'\b(?:const|let)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(', source))
    names.update(re.findall(r'\bfn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(', source))
    return sum(1 for name in names if name.startswith("test") or name.endswith("_test"))


def _test_registration_locations(source: str) -> dict[str, int]:
    locations: dict[str, int] = {}
    register_re = re.compile(r'\btestRegister\s*\([^)]*\bname\s*=\s*"([^"]+)"')
    param_re = re.compile(r'\btestRegisterParam\s*\([^)]*\bname\s*=\s*"([^"]+)"[^)]*\bparam\s*=\s*"([^"]+)"')
    for line_no, line in enumerate(source.splitlines(), start=1):
        for match in register_re.finditer(line):
            locations.setdefault(match.group(1), line_no)
        for match in param_re.finditer(line):
            locations.setdefault(f"{match.group(1)}[{match.group(2)}]", line_no)
    return locations


def _annotate_test_failure_detail(detail: str, test_file: Path, locations: dict[str, int], root: Path) -> str:
    if not detail or not locations:
        return detail
    display = test_file.relative_to(root) if test_file.is_relative_to(root) else test_file

    def repl(match: re.Match) -> str:
        name = match.group(1)
        line = locations.get(name)
        if line is None:
            return match.group(0)
        return f"test failed: {display}:{line} {name}:"

    return re.sub(r'test failed:\s+([^:\n]+):', repl, detail, count=1)



def _format_ez_source(source: str) -> str:
    raw_lines = source.splitlines()
    formatted: list[str] = []
    indent = 0
    index = 0
    in_block_comment = False
    while index < len(raw_lines):
        line = raw_lines[index]
        stripped = line.strip()
        if not stripped:
            formatted.append("")
            index += 1
            continue

        if in_block_comment:
            formatted.append("    " * indent + stripped)
            if "*/" in stripped:
                in_block_comment = False
            index += 1
            continue

        if stripped.startswith("/*"):
            formatted.append("    " * indent + stripped)
            in_block_comment = "*/" not in stripped
            index += 1
            continue

        if stripped.startswith("//"):
            comment, code = _split_comment_code_line(stripped)
            formatted.append("    " * indent + comment)
            if not code:
                index += 1
                continue
            stripped = code

        if _starts_multiline_import(stripped):
            import_lines = [stripped]
            index += 1
            while index < len(raw_lines):
                import_lines.append(raw_lines[index].strip())
                if "}" in raw_lines[index]:
                    break
                index += 1
            formatted.append("    " * indent + _format_import_lines(import_lines))
            index += 1
            continue

        leading_closes = _leading_format_closes(stripped)
        if leading_closes:
            indent = max(indent - leading_closes, 0)
        if stripped.startswith("}"):
            indent = max(indent - 1, 0)
        formatted_line = _format_ez_line(stripped)
        formatted.append("    " * indent + formatted_line)
        indent += _format_line_indent_delta(formatted_line)
        index += 1
    while formatted and formatted[-1] == "":
        formatted.pop()
    return "\n".join(line.rstrip() for line in formatted) + "\n"


def _split_comment_code_line(line: str) -> tuple[str, str]:
    code_match = re.search(
        r"\s((?:export\s+)?(?:from\s+\"|extern\s+\"|declare\b|struct\b|type\b|let\b|const\b|static\b))",
        line[2:],
    )
    if code_match is None:
        return line, ""
    start = 2 + code_match.start(1)
    return line[:start].rstrip(), line[start:].strip()


def _starts_multiline_import(line: str) -> bool:
    return bool(re.match(r'from\s+"[^"]+"\s+import\s*\{\s*$', line))


def _format_import_lines(lines: list[str]) -> str:
    text = " ".join(line.strip() for line in lines)
    match = re.match(r'from\s+("[^"]+")\s+import\s*\{(.*?)\}\s*;?$', text)
    if match is None:
        return _format_ez_line(text)
    names = [name.strip() for name in match.group(2).split(",") if name.strip()]
    return f"from {match.group(1)} import {{ {', '.join(names)} }};"


def _format_ez_line(line: str) -> str:
    trailing_comment = ""
    code = line
    comment_index = _line_comment_index(line)
    if comment_index is not None:
        code = line[:comment_index].rstrip()
        trailing_comment = " " + line[comment_index:].strip()
    code = _normalize_ez_code_spacing(code.strip())
    return (code + trailing_comment).rstrip()


def _leading_format_closes(line: str) -> int:
    count = 0
    for ch in line:
        if ch in ")]":
            return 1
            continue
        break
    return count


def _format_line_indent_delta(line: str) -> int:
    code = line
    comment_index = _line_comment_index(line)
    if comment_index is not None:
        code = line[:comment_index]
    opens = 0
    closes = 0
    in_string = False
    escape = False
    for ch in code:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in "{[(":
            opens += 1
        elif ch in "}])":
            closes += 1
    return 1 if opens > closes else 0


def _line_comment_index(line: str) -> int | None:
    in_string = False
    escape = False
    for index in range(len(line) - 1):
        ch = line[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if line[index:index + 2] == "//":
            return index
    return None


def _normalize_ez_code_spacing(code: str) -> str:
    if not code:
        return code
    code, strings = _protect_format_strings(code)
    code, compound_ops = _protect_format_compound_ops(code)
    code = re.sub(r"\s+", " ", code)
    code = re.sub(r"\s*\.\s*", ".", code)
    code = re.sub(r"\s*,\s*", ", ", code)
    code = re.sub(r"\s*;\s*$", ";", code)
    code = re.sub(r"\(\s+", "(", code)
    code = re.sub(r"\s+\)", ")", code)
    code = re.sub(r"\[\s+", "[", code)
    code = re.sub(r"\s+\]", "]", code)
    code = re.sub(r"\{\s+", "{ ", code)
    code = re.sub(r"\s+\}", " }", code)
    code = re.sub(r"\s*(==|!=|<=|>=|&&|\|\||=>|->|=)\s*", r" \1 ", code)
    code = re.sub(r"\s*([+\-*/%])\s*", r" \1 ", code)
    code = _compact_unary_minus(code)
    code = re.sub(r"\s*:\s*", ": ", code)
    code = re.sub(r"(?<=\s)\?\s*([^:;]+?):\s*", r"? \1 : ", code)
    code = re.sub(r"\s*\?\s*(?=[,);])", "?", code)
    code = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+)\s*<\s*([^<>\n]+?)\s*>\s*(?=\()", _compact_generic_match, code)
    code = re.sub(r"\b(List|Dict|Vec)\s*<\s*([^<>\n]+?)\s*>", _compact_generic_match, code)
    code = re.sub(r"\s+", " ", code).strip()
    code = re.sub(r"\( ", "(", code)
    code = re.sub(r" \)", ")", code)
    code = re.sub(r"\[ ", "[", code)
    code = re.sub(r" \]", "]", code)
    code = _restore_format_compound_ops(code, compound_ops)
    return _restore_format_strings(code, strings)


def _protect_format_strings(code: str) -> tuple[str, list[str]]:
    strings: list[str] = []

    def repl(match: re.Match) -> str:
        strings.append(match.group(0))
        return f"__EZ_FMT_STRING_{len(strings) - 1}__"

    return re.sub(r'"(?:[^"\\\r\n]|\\.)*"', repl, code), strings


def _restore_format_strings(code: str, strings: list[str]) -> str:
    for index, value in enumerate(strings):
        code = code.replace(f"__EZ_FMT_STRING_{index}__", value)
    return code


def _protect_format_compound_ops(code: str) -> tuple[str, list[str]]:
    operators: list[str] = []

    def repl(match: re.Match) -> str:
        operators.append(match.group(0))
        return f"__EZ_FMT_OP_{len(operators) - 1}__"

    return re.sub(r"\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<=|>>=", repl, code), operators


def _restore_format_compound_ops(code: str, operators: list[str]) -> str:
    for index, value in enumerate(operators):
        code = code.replace(f"__EZ_FMT_OP_{index}__", value)
    return code


def _compact_unary_minus(code: str) -> str:
    unary_prefix = r"(^|(?:[=(\[{,:?]|=>|return|throw)\s+)"
    return re.sub(rf"{unary_prefix}-\s+([A-Za-z_$0-9])", r"\1-\2", code)


def _compact_generic_match(match: re.Match) -> str:
    inner = re.sub(r"\s*,\s*", ", ", match.group(2).strip())
    return f"{match.group(1)}<{inner}>"



def _tokenize_format_source(source: str) -> list[str]:
    pattern = re.compile(
        r'"(?:[^"\\\r\n]|\\.)*"|//[^\n]*|/\*.*?\*/|\.\.\.|==|!=|<=|>=|<<=|>>=|&&|\|\||\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<|>>|=>|->|(?:[A-Za-z_][A-Za-z0-9_]*|\$[A-Za-z0-9_]+)|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|0x[0-9A-Fa-f_]+|0b[01_]+|0o[0-7_]+|.',
        re.DOTALL,
    )
    tokens: list[str] = []
    for match in pattern.finditer(source):
        token = match.group(0)
        if token.isspace():
            continue
        tokens.append(token)
    return tokens



def _append_token(current: str, token: str) -> str:
    if not current:
        return token
    if token in {",", ";", ")", "]", "}"}:
        return current.rstrip() + token
    if token == "(":
        stripped = current.rstrip()
        if re.search(r"(?:=|=>|\?|\bin|\breturn|\bthrow)$", stripped):
            return stripped + " " + token
        return stripped + token
    if token == "[":
        return current.rstrip() + token
    if token == ":":
        return current.rstrip() + ": "
    if token == ".":
        return current.rstrip() + "."
    if current.endswith(": ") or current.endswith("."):
        return current + token
    return current.rstrip() + " " + token


def _create_release_package(config: ProjectConfig) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(config.path, "project.toml")
        for source in _collect_release_sources(config):
            archive.write(source, source.relative_to(config.root).as_posix())
    return buffer.getvalue()



def _collect_release_sources(config: ProjectConfig) -> list[Path]:
    sources: set[Path] = set()
    if config.main is not None:
        sources.update(discover_sources(config))
    for path in config.root.rglob("*.ez"):
        if ".ez" in path.relative_to(config.root).parts:
            continue
        sources.add(path.resolve())
    return sorted(sources)



def _publish_release_package(config: ProjectConfig, package_name: str, package_data: bytes) -> str:
    if _is_http_url(config.registry or ""):
        url = config.registry.rstrip("/") + f"/{config.name}/{config.version}/{package_name}"
        request = urllib.request.Request(url, data=package_data, method="PUT", headers={"Content-Type": "application/zip"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            raise CliError(f"release 上传失败 {url}: {exc}") from exc
        return url
    release_dir = _resolve_path(config.root, config.registry or "") / config.name / config.version
    release_dir.mkdir(parents=True, exist_ok=True)
    package_path = release_dir / package_name
    package_path.write_bytes(package_data)
    return str(package_path)



def _install_remote_dependency(config: ProjectConfig, name: str, version: str, *, global_install: bool = False) -> Path:
    if not config.registry:
        raise CliError(f"远端依赖 {name} 需要 [project].registry")
    install_dir = _global_dependency_dir(name, version) if global_install else config.root / ".ez" / "deps" / name / version
    if _is_http_url(config.registry):
        _download_remote_package(config.registry, name, version, install_dir)
    else:
        source_dir = _resolve_path(config.root, config.registry) / name / version
        if not source_dir.exists():
            raise CliError(f"远端依赖不存在: {source_dir}")
        package_zip = source_dir / f"{name}-{version}.zip"
        if package_zip.exists():
            _extract_package_zip(package_zip.read_bytes(), install_dir)
        else:
            _copy_package_dir(source_dir, install_dir)
    return install_dir



def _ez_home() -> Path:
    return Path(os.environ.get("EZLANG_HOME", "~/.ez")).expanduser().resolve()



def _global_dependency_dir(name: str, version: str) -> Path:
    return _ez_home() / "deps" / name / version



def _download_remote_package(registry: str, name: str, version: str, install_dir: Path):
    zip_url = registry.rstrip("/") + f"/{name}/{version}/{name}-{version}.zip"
    legacy_url = registry.rstrip("/") + f"/{name}/{version}/{name}.ez"
    try:
        with urllib.request.urlopen(zip_url, timeout=30) as response:
            package_data = response.read()
        _extract_package_zip(package_data, install_dir)
        return
    except (urllib.error.URLError, TimeoutError) as zip_exc:
        try:
            with urllib.request.urlopen(legacy_url, timeout=30) as response:
                source_data = response.read()
        except (urllib.error.URLError, TimeoutError) as legacy_exc:
            raise CliError(f"远端依赖下载失败 {zip_url} 或 {legacy_url}: {legacy_exc}") from zip_exc

    if install_dir.exists():
        shutil.rmtree(install_dir)
    install_dir.mkdir(parents=True, exist_ok=True)
    (install_dir / f"{name}.ez").write_bytes(source_data)



def _copy_package_dir(source_dir: Path, install_dir: Path):
    if install_dir.exists():
        shutil.rmtree(install_dir)
    shutil.copytree(source_dir, install_dir)



def _extract_package_zip(package_data: bytes, install_dir: Path):
    if install_dir.exists():
        shutil.rmtree(install_dir)
    install_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(BytesIO(package_data)) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                member_path = PurePosixPath(member.filename)
                if (
                    member_path.is_absolute()
                    or ".." in member_path.parts
                    or "\\" in member.filename
                    or re.match(r"^[A-Za-z]:", member.filename)
                ):
                    raise CliError(f"远端依赖包包含非法路径: {member.filename}")
                target = install_dir / Path(*member_path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source:
                    target.write_bytes(source.read())
    except zipfile.BadZipFile as exc:
        raise CliError("远端依赖包不是有效 zip 文件") from exc



def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")



def _expand_workspace_members(config: ProjectConfig) -> list[Path]:
    members: list[Path] = []
    for pattern in config.workspace_members:
        matches = glob.glob(str(config.root / pattern))
        members.extend(Path(match).resolve() for match in matches)
    return sorted(members)


def _select_run_output(config: ProjectConfig) -> OutputConfig:
    native = _native_os()
    native_arch = _native_arch()
    for output in config.outputs:
        if output.os == native and output.arch == native_arch:
            return output
    for output in config.outputs:
        if output.os == native:
            return output
    return config.outputs[0]


def _select_test_output(config: ProjectConfig) -> OutputConfig:
    return _select_run_output(config)


def _required_str(mapping: dict[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise CliError(f"缺少 {label}")
    return value


def _validate_semver(value: str, label: str):
    if not SEMVER_RE.match(value):
        raise CliError(f"{label} 版本号无效: {value}")


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _format_libs(libs) -> str:
    return ", ".join(str(lib[0] if isinstance(lib, tuple) else lib) for lib in libs)


def _native_os() -> str:
    name = platform.system().lower()
    if name == "darwin":
        return "macos"
    if name.startswith("win"):
        return "windows"
    return "linux"


def _native_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "aarch64"
    return "x86_64"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
