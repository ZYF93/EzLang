"""EzLang 命令行工具入口"""

from __future__ import annotations

import argparse
import glob
import importlib
import importlib.util
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

try:
    from llvmlite import binding as llvm
except ModuleNotFoundError:  # pragma: no cover
    llvm = None

try:
    from semantic.analyzer import analyze
    from codegen.llvm_codegen import compile_source
except ModuleNotFoundError:  # pragma: no cover
    COMPILER_SRC = ROOT / "compiler" / "src"
    if str(COMPILER_SRC) not in sys.path:
        sys.path.insert(0, str(COMPILER_SRC))
    from semantic.analyzer import analyze
    from codegen.llvm_codegen import compile_source

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


@dataclass
class OutputConfig:
    arch: str
    os: str
    dir: Path
    triple: str


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
    main: Path | None = None
    optimize: int = 0
    public: bool = True
    registry: str | None = None
    outputs: list[OutputConfig] = field(default_factory=list)
    deps: dict[str, str] = field(default_factory=dict)
    workspace_members: list[str] = field(default_factory=list)
    plugins: list[PluginConfig] = field(default_factory=list)
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

    build = subparsers.add_parser("build", help="编译项目到 LLVM IR")
    _add_project_arg(build)
    build.set_defaults(func=cmd_build)

    run = subparsers.add_parser("run", help="编译并运行本地目标")
    _add_project_arg(run)
    run.set_defaults(func=cmd_run)

    install = subparsers.add_parser("install", help="校验依赖安装计划")
    _add_project_arg(install)
    install.set_defaults(func=cmd_install)

    fmt = subparsers.add_parser("fmt", help="解析检查 EzLang 源文件")
    _add_project_arg(fmt)
    fmt.add_argument("paths", nargs="*", help="要检查的文件或目录")
    fmt.add_argument("--dry-run", "--check", action="store_true", dest="check", help="只检查不修改")
    fmt.set_defaults(func=cmd_fmt)

    release = subparsers.add_parser("release", help="校验发布元数据")
    _add_project_arg(release)
    release.add_argument("--dry-run", action="store_true", help="只校验不发布")
    release.set_defaults(func=cmd_release)
    return parser


def _add_project_arg(parser: argparse.ArgumentParser):
    parser.add_argument("--project", default="project.toml", help="project.toml 路径")


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


def cmd_build(args) -> int:
    config = load_project(args.project, require_main=True)
    for warning in config.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    plugins = _load_plugins(config)
    source_plan = discover_sources(config)
    for output in config.outputs:
        context = _plugin_context(config, output, source_plan)
        _run_plugin_hook(plugins, "before_build", context)
        module, libs = _compile_project(config, output.os, source_plan)
        output.dir.mkdir(parents=True, exist_ok=True)
        _apply_target_triple(module, output.triple)
        out_file = output.dir / f"{config.name}.ll"
        out_file.write_text(str(module), encoding="utf-8")
        print(f"built {output.os}/{output.arch} {out_file}")
        obj_file = None
        if _can_emit_object(output):
            obj_file = output.dir / f"{config.name}.o"
            obj_file.write_bytes(_emit_object(module, config.optimize, output.triple))
            print(f"object: {obj_file}")
        context.update(
            {
                "ir": str(out_file),
                "object": str(obj_file) if obj_file is not None else None,
                "extern_libs": [str(lib[0] if isinstance(lib, tuple) else lib) for lib in libs],
            }
        )
        _run_plugin_hook(plugins, "after_build", context)
        print(f"sources: {_format_sources(config, source_plan)}")
        if libs:
            print(f"extern libs: {_format_libs(libs)}")
    return 0


def cmd_run(args) -> int:
    config = load_project(args.project, require_main=True)
    output = _select_run_output(config)
    if output.os != _native_os() or output.os in NATIVE_UNSUPPORTED:
        print(f"error: ez run only supports native target {_native_os()}, got {output.os}", file=sys.stderr)
        return 1
    if not _can_emit_native_object(output):
        print(f"error: ez run only supports native target {_native_os()}/{_native_arch()}, got {output.os}/{output.arch}", file=sys.stderr)
        return 1
    source_plan = discover_sources(config)
    module, _ = _compile_project(config, output.os, source_plan)
    _apply_target_triple(module, output.triple)
    output.dir.mkdir(parents=True, exist_ok=True)
    obj_file = output.dir / f"{config.name}.o"
    exe_file = output.dir / config.name
    obj_file.write_bytes(_emit_object(module, config.optimize, output.triple))
    _link_executable(obj_file, exe_file)
    completed = subprocess.run([str(exe_file)])
    return completed.returncode


def cmd_install(args) -> int:
    config = load_project(args.project, require_main=False)
    for name, spec in config.deps.items():
        if spec == "@workspace":
            members = _expand_workspace_members(config)
            print(f"workspace {name} {','.join(str(p) for p in members)}")
        elif spec.startswith(".") or spec.startswith("/"):
            path = _resolve_path(config.root, spec)
            if not path.exists():
                raise CliError(f"依赖 {name} 路径不存在: {path}")
            print(f"local {name} {path}")
        else:
            if not SEMVER_RE.match(spec):
                raise CliError(f"依赖 {name} 版本号无效: {spec}")
            install_dir = _install_remote_dependency(config, name, spec)
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
        _, errors, _ = compile_source(source, module_name=file.stem)
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


def load_project(path: str | Path, *, require_main: bool) -> ProjectConfig:
    if tomllib is None:
        raise CliError("当前 Python 缺少 tomllib，请使用 Python 3.11+ 或安装 tomli")
    project_path = Path(path).expanduser().resolve()
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
    _validate_semver(version, "project.version")
    optimize = int(project.get("optimize", 0))
    if optimize < 0 or optimize > 3:
        raise CliError("project.optimize 必须在 0..3 之间")
    public = bool(project.get("public", True))
    registry = project.get("registry")
    main_value = project.get("main")
    main = _resolve_path(root, main_value) if isinstance(main_value, str) else None
    if require_main:
        if main is None:
            raise CliError("build/run 需要 [project].main")
        if not main.exists():
            raise CliError(f"入口文件不存在: {main}")
    outputs = _parse_outputs(data.get("output"), root)
    return ProjectConfig(
        path=project_path,
        root=root,
        name=name,
        version=version,
        main=main,
        optimize=optimize,
        public=public,
        registry=registry if isinstance(registry, str) else None,
        outputs=outputs[0],
        deps={k: str(v) for k, v in data.get("deps", {}).items()},
        workspace_members=list(data.get("workspace", {}).get("members", [])),
        plugins=_parse_plugins(data.get("plugins", [])),
        warnings=outputs[1],
    )


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
        outputs.append(OutputConfig(arch=arch, os=os_name, dir=out_dir, triple=triple))
    return outputs, warnings


def discover_sources(config: ProjectConfig) -> list[Path]:
    if config.main is None:
        return []
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

    visit(config.main)
    return ordered


def _plugin_context(config: ProjectConfig, output: OutputConfig, source_plan: list[Path]) -> dict[str, Any]:
    return {
        "project": config.name,
        "version": config.version,
        "root": str(config.root),
        "project_file": str(config.path),
        "main": str(config.main) if config.main is not None else None,
        "optimize": config.optimize,
        "output": {
            "arch": output.arch,
            "os": output.os,
            "dir": str(output.dir),
            "triple": output.triple,
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



def _compile_project(config: ProjectConfig, compile_target: str, source_plan: list[Path] | None = None):
    source_plan = source_plan or discover_sources(config)
    source = "\n".join(_strip_imports(path.read_text(encoding="utf-8")) for path in source_plan)
    base_dir = config.main.parent if config.main is not None else config.root
    analyzer = analyze(source, base_dir=base_dir, compile_target=compile_target)
    if analyzer.symbols.has_errors():
        raise CliError("语义错误: " + "; ".join(analyzer.symbols.errors))
    module, errors, libs = compile_source(source, module_name=config.name, compile_target=compile_target)
    if errors:
        raise CliError("编译错误: " + "; ".join(errors))
    return module, libs


def _can_emit_native_object(output: OutputConfig) -> bool:
    return output.os == _native_os() and output.arch == _native_arch() and llvm is not None


def _can_emit_object(output: OutputConfig) -> bool:
    return llvm is not None and output.triple != ""


def _target_triple(arch: str, os_name: str) -> str:
    triple = TARGET_TRIPLES.get((arch, os_name))
    if triple is None:
        raise CliError(f"不支持的目标组合: {os_name}/{arch}")
    return triple


def _apply_target_triple(module, triple: str):
    module.triple = triple


def _emit_object(module, optimize: int, triple: str) -> bytes:
    if llvm is None:
        raise CliError("llvmlite binding 不可用，无法生成对象文件")
    try:
        llvm.initialize_all_targets()
        llvm.initialize_all_asmprinters()
        llvm_module = llvm.parse_assembly(str(module))
        llvm_module.verify()
        target = llvm.Target.from_triple(triple)
        machine = target.create_target_machine(opt=optimize)
        return machine.emit_object(llvm_module)
    except RuntimeError as exc:
        raise CliError(f"对象文件生成失败: {exc}") from exc


def _link_executable(obj_file: Path, exe_file: Path):
    completed = subprocess.run(
        ["cc", str(obj_file), "-o", str(exe_file)],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise CliError(f"链接失败: {detail}")


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
    return (config.root / path).resolve()


def _strip_imports(source: str) -> str:
    return "\n".join(line for line in source.splitlines() if IMPORT_RE.search(line) is None) + "\n"


def _format_sources(config: ProjectConfig, sources: list[Path]) -> str:
    return ", ".join(str(path.relative_to(config.root)) if path.is_relative_to(config.root) else str(path) for path in sources)


def _collect_fmt_files(config: ProjectConfig, paths: list[str]) -> list[Path]:
    roots = [_resolve_path(Path.cwd(), p) for p in paths] if paths else ([config.main] if config.main else [config.root])
    files: list[Path] = []
    for root in roots:
        if root is None:
            continue
        if root.is_dir():
            files.extend(sorted(root.rglob("*.ez")))
        elif root.suffix == ".ez":
            files.append(root)
        else:
            raise CliError(f"fmt 只支持 .ez 文件或目录: {root}")
    return sorted(dict.fromkeys(files))



def _format_ez_source(source: str) -> str:
    tokens = _tokenize_format_source(source)
    lines: list[str] = []
    current = ""
    indent = 0
    for token in tokens:
        if token == "}":
            if current.strip():
                lines.append("    " * indent + current.strip())
                current = ""
            indent = max(indent - 1, 0)
            current = "}"
            continue
        if token == "{":
            current = _append_token(current, token)
            lines.append("    " * indent + current.strip())
            current = ""
            indent += 1
            continue
        if token == ";":
            current = _append_token(current, token)
            lines.append("    " * indent + current.strip())
            current = ""
            continue
        current = _append_token(current, token)
    if current.strip():
        lines.append("    " * indent + current.strip())
    return "\n".join(line.rstrip() for line in lines if line.strip()) + "\n"



def _tokenize_format_source(source: str) -> list[str]:
    pattern = re.compile(
        r'"(?:[^"\\\r\n]|\\.)*"|//[^\n]*|/\*.*?\*/|\.\.\.|==|!=|<=|>=|<<=|>>=|&&|\|\||\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<|>>|=>|->|[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|0x[0-9A-Fa-f_]+|0b[01_]+|0o[0-7_]+|.',
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



def _install_remote_dependency(config: ProjectConfig, name: str, version: str) -> Path:
    if not config.registry:
        raise CliError(f"远端依赖 {name} 需要 [project].registry")
    install_dir = config.root / ".ez" / "deps" / name / version
    if _is_http_url(config.registry):
        _download_remote_package(config.registry, name, version, install_dir)
    else:
        source_dir = _resolve_path(config.root, config.registry) / name / version
        if not source_dir.exists():
            raise CliError(f"远端依赖不存在: {source_dir}")
        _copy_package_dir(source_dir, install_dir)
    return install_dir



def _download_remote_package(registry: str, name: str, version: str, install_dir: Path):
    url = registry.rstrip("/") + f"/{name}/{version}/{name}.ez"
    install_dir.mkdir(parents=True, exist_ok=True)
    target = install_dir / f"{name}.ez"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            target.write_bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise CliError(f"远端依赖下载失败 {url}: {exc}") from exc



def _copy_package_dir(source_dir: Path, install_dir: Path):
    if install_dir.exists():
        shutil.rmtree(install_dir)
    shutil.copytree(source_dir, install_dir)



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
    for output in config.outputs:
        if output.os == native:
            return output
    return config.outputs[0]


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
