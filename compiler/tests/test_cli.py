"""ez CLI 工具链测试"""

import base64
import builtins
import hashlib
import os
import socket
import subprocess
import sys
import threading
import time
import zipfile
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "compiler" / "src"))

from cli import ez


def _ws_header_value(request: bytes, name: str) -> bytes:
    prefix = name.lower().encode("ascii") + b":"
    for line in request.split(b"\r\n"):
        if line.lower().startswith(prefix):
            return line[len(prefix):].strip()
    return b""


def _ws_handshake_response(request: bytes) -> bytes:
    key = _ws_header_value(request, "Sec-WebSocket-Key")
    accept = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
    return (
        b"HTTP/1.1 101 Switching Protocols\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n"
    )


def write_project(
    tmp_path: Path,
    *,
    os_name: str = "linux",
    arch: str = "x86_64",
    public: bool = True,
    optimize: int = 0,
):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.ez").write_text("let x: I32 = 42;\n", encoding="utf-8")
    public_text = "true" if public else "false"
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        f"""
[project]
name = "demo"
version = "0.1.0"
main = "src/index.ez"
optimize = {optimize}
public = {public_text}
registry = "local"

[[output]]
arch = "{arch}"
os = "{os_name}"
dir = "dist/{os_name}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return project_toml


def test_help_and_version(capsys):
    assert ez.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "usage:" in out
    assert "build" in out

    assert ez.main(["--version"]) == 0
    out = capsys.readouterr().out
    assert "ezlang 0.1.0" in out


def test_help_and_version_do_not_require_compiler_dependencies(monkeypatch, capsys):
    original_import = builtins.__import__
    blocked = {"semantic", "codegen", "antlr4", "llvmlite"}

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.split(".", 1)[0] in blocked:
            raise ModuleNotFoundError(f"No module named '{name}'", name=name)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(ez, "_analyze", None)
    monkeypatch.setattr(ez, "_compile_source", None)
    monkeypatch.setattr(ez, "llvm", None)
    monkeypatch.setattr(builtins, "__import__", guarded_import)

    assert ez.main(["--version"]) == 0
    assert "ezlang 0.1.0" in capsys.readouterr().out
    assert ez.main(["build", "--help"]) == 0
    assert "--project" in capsys.readouterr().out


def test_root_pyproject_registers_ez_console_script():
    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert '[project.scripts]' in text
    assert 'ez = "cli.ez:main"' in text
    assert 'cli = "cli"' in text
    assert 'codegen = "compiler/src/codegen"' in text


def test_unknown_command_returns_error(capsys):
    assert ez.main(["missing"]) == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err


@pytest.mark.parametrize("command", ["build", "run", "test", "install", "fmt", "release"])
def test_subcommand_help(command, capsys):
    assert ez.main([command, "--help"]) == 0
    out = capsys.readouterr().out
    assert command in out


def test_build_auto_discovers_project_from_child_directory(tmp_path, monkeypatch, capsys):
    write_project(tmp_path, os_name="linux")
    child = tmp_path / "src" / "nested"
    child.mkdir()
    monkeypatch.chdir(child)

    assert ez.main(["build"]) == 0

    out = capsys.readouterr().out
    assert "built linux/x86_64" in out
    assert (tmp_path / "dist" / "linux" / "demo.ll").exists()


def test_build_native_links_entry_without_user_main(tmp_path, capsys):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        "type Answer = { value: I32; };\n",
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    assert "executable:" in out
    assert (tmp_path / "dist" / ez._native_os() / "demo").exists()


def test_run_accepts_explicit_file_without_project(tmp_path, monkeypatch):
    source = tmp_path / "loose.ez"
    source.write_text(
        'from "std/os" import { exit };\nlet $code: I32 = 3;\n$code = $code + 1;\nexit(code = $code);\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert ez.main(["run", str(source)]) == 4

    exe_file = tmp_path / ".ez" / "run" / "loose" / "loose"
    assert exe_file.exists()


def test_run_auto_discovers_project_and_allows_entry_override(tmp_path, monkeypatch):
    write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    alt = tmp_path / "src" / "alt.ez"
    alt.write_text("const main = (): I32 => { return 0; };\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "src")

    assert ez.main(["run", "alt.ez"]) == 0


def test_run_executes_top_level_file_without_user_main(tmp_path, monkeypatch):
    write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = tmp_path / "src" / "exit_top_level.ez"
    source.write_text(
        'from "std/os" import { exit };\nexit(code = 6);\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / "src")

    assert ez.main(["run", "exit_top_level.ez"]) == 6


def test_init_creates_default_project_and_run_uses_auto_discovery(tmp_path, monkeypatch, capfd):
    target = tmp_path / "sample-app"

    assert ez.main(["init", str(target), "--name", "sample"]) == 0

    assert (target / "project.toml").exists()
    assert (target / "src" / "main.ez").exists()
    monkeypatch.chdir(target)
    assert ez.main(["run"]) == 0

    out = capfd.readouterr().out
    assert f"initialized {target}" in out
    assert "Hello from sample" in out


def test_init_template_clones_remote_git_template(tmp_path, monkeypatch, capsys):
    calls = []

    def fake_run(cmd, text=False, capture_output=False):
        calls.append((cmd, text, capture_output))
        clone_dir = Path(cmd[-1])
        clone_dir.mkdir(parents=True)
        (clone_dir / ".git").mkdir()
        (clone_dir / "src").mkdir()
        (clone_dir / "project.toml").write_text(
            '[project]\nname = "tmpl"\nversion = "0.1.0"\nmain = "src/main.ez"\n',
            encoding="utf-8",
        )
        (clone_dir / "src" / "main.ez").write_text(
            "const main = (): I32 => { return 0; };\n",
            encoding="utf-8",
        )

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(ez.subprocess, "run", fake_run)
    target = tmp_path / "templated"

    assert ez.main(["init", str(target), "--template", "https://example.com/template.git"]) == 0

    assert calls[0][0][:4] == ["git", "clone", "--depth", "1"]
    assert calls[0][0][4] == "https://example.com/template.git"
    assert (target / "project.toml").exists()
    assert (target / "src" / "main.ez").exists()
    assert not (target / ".git").exists()
    assert f"initialized {target}" in capsys.readouterr().out


def test_build_writes_ir_for_output(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    ir_file = tmp_path / "dist" / "linux" / "demo.ll"
    assert "built linux/x86_64" in out
    assert ir_file.exists()
    assert 'ModuleID = "demo"' in ir_file.read_text(encoding="utf-8")


def test_build_writes_object_for_native_output(tmp_path, capsys):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
        optimize=2,
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    obj_file = tmp_path / "dist" / ez._native_os() / "demo.o"
    assert "object:" in out
    assert obj_file.exists()
    assert obj_file.stat().st_size > 0


def test_build_emits_objects_for_multiple_cross_targets(tmp_path, capsys):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.ez").write_text("const main = (): I32 => { return 0; };\n", encoding="utf-8")
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        """
[project]
name = "demo"
version = "0.1.0"
main = "src/index.ez"
optimize = 1

[[output]]
arch = "x86_64"
os = "linux"
dir = "dist/linux"

[[output]]
arch = "wasm32"
os = "emcc"
dir = "dist/web"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    linux_ir = (tmp_path / "dist" / "linux" / "demo.ll").read_text(encoding="utf-8")
    web_ir = (tmp_path / "dist" / "web" / "demo.ll").read_text(encoding="utf-8")
    assert "target triple = \"x86_64-unknown-linux-gnu\"" in linux_ir
    assert "target triple = \"wasm32-unknown-emscripten\"" in web_ir
    assert (tmp_path / "dist" / "linux" / "demo.o").exists()
    assert (tmp_path / "dist" / "web" / "demo.o").exists()
    assert "built linux/x86_64" in out
    assert "built emcc/wasm32" in out


def test_build_rejects_invalid_optimize(tmp_path, capsys):
    project_toml = write_project(tmp_path, optimize=4)

    assert ez.main(["build", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "project.optimize" in err


def test_project_optimize_defaults_to_documented_level(tmp_path):
    project_toml = write_project(tmp_path)
    text = project_toml.read_text(encoding="utf-8")
    project_toml.write_text(text.replace("optimize = 0\n", ""), encoding="utf-8")

    config = ez.load_project(project_toml, require_main=True)

    assert config.optimize == 2


def test_build_discovers_default_entry_when_project_main_is_omitted(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    text = project_toml.read_text(encoding="utf-8")
    project_toml.write_text(text.replace('main = "src/index.ez"\n', ""), encoding="utf-8")

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    assert "built linux/x86_64" in out
    assert (tmp_path / "dist" / "linux" / "demo.ll").exists()


def test_run_executes_top_level_statements_without_user_main(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/os" import { exit };\nlet $code: I32 = 2;\n$code = $code + 3;\nexit(code = $code);\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 5

    exe_file = tmp_path / "dist" / ez._native_os() / "demo"
    assert exe_file.exists()


def test_run_executes_top_level_declarations_in_file_order_without_user_main(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/os" import { exit };\n'
        'let $code: I32 = 1;\n'
        '$code = $code + 2;\n'
        'let after: I32 = $code * 2;\n'
        '$code = after + 1;\n'
        'exit(code = $code);\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 7


def test_run_allows_top_level_return_without_user_main(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text("return 7;\n", encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 7


def test_run_aggregate_equality_compares_fields_recursively(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'struct Point { x: I32; y: I32; };\n'
        'struct Box { p: Point; ok: Bool; };\n'
        'const main = (): I32 => {\n'
        '    const a = Point(x = 1, y = 2);\n'
        '    const b = Point(x = 1, y = 2);\n'
        '    const c = Point(x = 1, y = 3);\n'
        '    const ba = Box(p = a, ok = true);\n'
        '    const bb = Box(p = b, ok = true);\n'
        '    const bc = Box(p = c, ok = true);\n'
        '    const oa: Point? = a;\n'
        '    const ob: Point? = b;\n'
        '    let oc: Point?;\n'
        '    const ua: I32 | Bool = 1;\n'
        '    const ub: I32 | Bool = 1;\n'
        '    const uc: I32 | Bool = false;\n'
        '    return (a == b && a != c && ba == bb && ba != bc && oa == ob && oa != oc && ua == ub && ua != uc) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_named_arguments_bind_by_name_for_functions_and_structs(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'struct Pair { left: I32; right: I32; };\n'
        'const pack = (first: I32, second: I32): I32 => {\n'
        '    return first * 10 + second;\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    const value = pack(second = 2, first = 7);\n'
        '    const pair = Pair(right = 4, left = 3);\n'
        '    return (value == 72 && pair.left == 3 && pair.right == 4) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_prefix_type_assertion_unwraps_and_reinterprets(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    const maybe: I32? = 42;\n'
        '    const widened: I64 = I64! maybe;\n'
        '    const scalar: F32 = 1.0;\n'
        '    const bits: I32 = I32! scalar;\n'
        '    return (widened == 42 && bits == 1065353216) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_decorator_meta_getter_setter_intercepts_global_access(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const get_watched = (meta: Meta<I32>): I32 => {\n'
        '    return meta.value + 10;\n'
        '};\n'
        'const set_watched = (meta: Meta<I32>, v: I32): Void => {\n'
        '    meta.value = v + 1;\n'
        '};\n'
        'const log = (this: Meta<I32>): Void => {\n'
        '    this.getter = get_watched;\n'
        '    this.setter = set_watched;\n'
        '};\n'
        '@log let watched = 1;\n'
        'const main = (): I32 => {\n'
        '    watched = 2;\n'
        '    return watched == 13 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0

def test_run_str_compound_add_assign_generates_valid_ir(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const append = (s: Str): Str => { let a: Str = "hello"; a += s; return a; };\n'
        'const main = (): I32 => { return 0; };\n',
        encoding="utf-8",
    )
    assert ez.main(["run", "--project", str(project_toml)]) == 0



def test_run_positional_args_mapped_to_params(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const add = (a: I32, b: I32): I32 => { return a + b; };\n'
        'const sum = (a: I32, b: I32, c: I32 = 0): I32 => { return a + b + c; };\n'
        'const main = (): I32 => {\n'
        '    const x = add(1, 2);\n'
        '    const y = add(1, b = 2);\n'
        '    const z = sum(5, c = 3, b = 2);\n'
        '    return (x == 3 && y == 3 && z == 10) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_str_concat_generates_valid_ir(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const concat = (a: Str, b: Str): Str => { return a + b; };\n'
        'const main = (): I32 => { return 0; };\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_executes_top_level_flow_parallel_without_user_main(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/os" import { exit };\n'
        'const value = flow {\n'
        '    const p = parallel { return 7; };\n'
        '    return p + 1;\n'
        '};\n'
        'exit(code = value);\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 8


def test_run_infers_top_level_flow_parallel_str_without_user_main(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/os" import { exit };\n'
        'from "std/test" import { testReset, testEqualStr, testFailed };\n'
        'testReset();\n'
        'const value = flow {\n'
        '    const p = parallel { return "ok"; };\n'
        '    return p;\n'
        '};\n'
        'testEqualStr(actual = value, expected = "ok", msg = "top-level flow str");\n'
        'exit(code = testFailed());\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_load_project_rejects_ambiguous_default_entries(tmp_path):
    project_toml = write_project(tmp_path)
    text = project_toml.read_text(encoding="utf-8")
    project_toml.write_text(text.replace('main = "src/index.ez"\n', ""), encoding="utf-8")
    (tmp_path / "src" / "main.ez").write_text("let x: I32 = 1;\n", encoding="utf-8")

    with pytest.raises(ez.CliError, match="多个默认入口"):
        ez.load_project(project_toml, require_main=True)


def test_project_log_compile_min_level_is_parsed(tmp_path):
    project_toml = write_project(tmp_path)
    text = project_toml.read_text(encoding="utf-8")
    project_toml.write_text(text + "\n[log]\ncompile_min_level = 3\n", encoding="utf-8")

    config = ez.load_project(project_toml, require_main=True)

    assert config.log_compile_min_level == 3


def test_project_rejects_invalid_log_compile_min_level(tmp_path):
    project_toml = write_project(tmp_path)
    text = project_toml.read_text(encoding="utf-8")
    project_toml.write_text(text + "\n[log]\ncompile_min_level = 5\n", encoding="utf-8")

    with pytest.raises(ez.CliError, match="log.compile_min_level"):
        ez.load_project(project_toml, require_main=True)


def test_build_accepts_wasm_arch_alias(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="emcc", arch="wasm")

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    captured = capsys.readouterr()
    assert "arch 'wasm' is deprecated" in captured.err
    assert (tmp_path / "dist" / "emcc" / "demo.ll").exists()


def test_build_discovers_import_dependency_graph(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    (tmp_path / "src" / "lib.ez").write_text("export let y: I32 = 1;\n", encoding="utf-8")
    (tmp_path / "src" / "index.ez").write_text(
        'from "./lib.ez" import { y };\nlet x: I32 = 42;\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    ir_text = (tmp_path / "dist" / "linux" / "demo.ll").read_text(encoding="utf-8")
    assert "sources: src/lib.ez, src/index.ez" in out
    assert '@"y"' in ir_text
    assert '@"x"' in ir_text


def test_build_resolves_dependency_package_import(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    dep_dir = tmp_path / "vendor" / "utils"
    dep_dir.mkdir(parents=True)
    (dep_dir / "index.ez").write_text("export let answer: I32 = 42;\n", encoding="utf-8")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[deps]\nutils = "./vendor/utils"\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "utils" import { answer };\nlet x: I32 = answer;\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    ir_text = (tmp_path / "dist" / "linux" / "demo.ll").read_text(encoding="utf-8")
    assert "vendor/utils/index.ez" in out
    assert '@"answer"' in ir_text


def test_build_resolves_installed_versioned_dependency_package_import(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    dep_dir = tmp_path / ".ez" / "deps" / "utils" / "1.2.3"
    dep_dir.mkdir(parents=True)
    (dep_dir / "index.ez").write_text("export let answer: I32 = 7;\n", encoding="utf-8")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[deps]\nutils = "1.2.3"\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "utils" import { answer };\nlet x: I32 = answer;\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    ir_text = (tmp_path / "dist" / "linux" / "demo.ll").read_text(encoding="utf-8")
    assert ".ez/deps/utils/1.2.3/index.ez" in out
    assert '@"answer"' in ir_text


def test_build_loads_python_plugin_and_calls_hooks(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    plugin = tmp_path / "plugin.py"
    plugin.write_text(
        """
from pathlib import Path


def before_build(context):
    root = Path(context["root"])
    (root / "plugin-before.txt").write_text(
        "|".join([
            context["project"],
            context["output"]["os"],
            *context["args"],
            ",".join(Path(path).name for path in context["sources"]),
        ]),
        encoding="utf-8",
    )


def after_build(context):
    root = Path(context["root"])
    (root / "plugin-after.txt").write_text(
        "|".join([
            Path(context["ir"]).name,
            context["output"]["arch"],
        ]),
        encoding="utf-8",
    )
""".lstrip(),
        encoding="utf-8",
    )
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[[plugins]]\nname = "./plugin.py"\nargs = ["release=true", "backend=llvm"]\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    captured = capsys.readouterr()
    assert "plugins are skipped" not in captured.err
    assert (tmp_path / "plugin-before.txt").read_text(encoding="utf-8") == "demo|linux|release=true|backend=llvm|index.ez"
    assert (tmp_path / "plugin-after.txt").read_text(encoding="utf-8") == "demo.ll|x86_64"


def test_build_rejects_invalid_plugin_args(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[[plugins]]\nname = "demo_plugin"\nargs = "release=true"\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "plugins.args" in err



def test_build_reports_missing_import(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    (tmp_path / "src" / "index.ez").write_text(
        'from "./missing.ez" import { y };\nlet x: I32 = 42;\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "import 路径不存在" in err


def test_run_import_alias_in_project_source_plan(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "math.ez").write_text(
        'export const add = (a: I32, b: I32): I32 => { return a + b; };\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "./math.ez" import { add as sum };\n'
        'const main = (): I32 => { return sum(a = 1, b = 2) == 3 ? 0 : 1; };\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_build_uses_extern_search_paths(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    libs_dir = tmp_path / "libs" / "linux"
    libs_dir.mkdir(parents=True)
    (libs_dir / "native.c").write_text("int native_add(void) { return 3; }\n", encoding="utf-8")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[extern]\nsearch_paths = ["libs"]\n\n[extern.linux]\nsearch_paths = ["libs/linux"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'extern "native.c";\ndeclare const native_add: () => I32;\nlet x = native_add();\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    assert str(libs_dir / "native.c") in out


def test_build_links_c_extern_into_native_executable(tmp_path, capsys):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    libs_dir = tmp_path / "libs"
    libs_dir.mkdir()
    (libs_dir / "native.c").write_text("int native_answer(void) { return 0; }\n", encoding="utf-8")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[extern]\nsearch_paths = ["libs"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'extern "native.c";\n'
        'declare const native_answer: () => I32;\n'
        'const main = (): I32 => { return native_answer(); };\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    exe_file = tmp_path / "dist" / ez._native_os() / "demo"
    assert exe_file.exists()
    assert "executable:" in out
    assert subprocess.run([str(exe_file)]).returncode == 0
    extern_objects = list((tmp_path / "dist" / ez._native_os() / ".extern").glob("*.o"))
    assert extern_objects


def test_build_reports_missing_extern_with_search_roots(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    libs_dir = tmp_path / "libs"
    libs_dir.mkdir()
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[extern]\nsearch_paths = ["libs"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'extern "missing.c";\ndeclare const native_missing: () => I32;\nlet x = native_missing();\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "extern 路径不存在：'missing.c'" in err
    assert "已搜索:" in err
    assert str(libs_dir) in err


def test_build_reports_ambiguous_extern_search_path(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    first = tmp_path / "libs" / "first"
    second = tmp_path / "libs" / "second"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "native.c").write_text("int native_add(void) { return 1; }\n", encoding="utf-8")
    (second / "native.c").write_text("int native_add(void) { return 2; }\n", encoding="utf-8")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[extern]\nsearch_paths = ["libs/first", "libs/second"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'extern "native.c";\ndeclare const native_add: () => I32;\nlet x = native_add();\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "extern 路径存在歧义: native.c" in err
    assert str(first / "native.c") in err
    assert str(second / "native.c") in err


def test_run_links_c_extern_from_search_path(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    libs_dir = tmp_path / "libs"
    libs_dir.mkdir()
    (libs_dir / "native.c").write_text("int native_exit(void) { return 9; }\n", encoding="utf-8")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[extern]\nsearch_paths = ["libs"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'extern "native.c";\ndeclare const native_exit: () => I32;\nconst main = (): I32 => { return native_exit(); };\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 9


def test_run_links_c_extern_callback_returning_large_struct(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    libs_dir = tmp_path / "libs"
    libs_dir.mkdir()
    (libs_dir / "native.c").write_text(
        """
#include <stdint.h>

typedef struct {
    int64_t a;
    int64_t b;
    int64_t c;
} Pair;

typedef Pair (*PairCallback)(int32_t);

int call_pair(PairCallback cb) {
    Pair out = cb(7);
    return (out.a == 7 && out.b == 8 && out.c == 9) ? 0 : 1;
}
""".lstrip(),
        encoding="utf-8",
    )
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[extern]\nsearch_paths = ["libs"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'extern "native.c";\n'
        'struct Pair { a: I64; b: I64; c: I64; };\n'
        'declare const call_pair: (cb: (x: I32) => Pair) => I32;\n'
        'const make_pair = (x: I32): Pair => {\n'
        '    return Pair(a = x, b = x + 1, c = x + 2);\n'
        '};\n'
        'const main = (): I32 => { return call_pair(cb = make_pair); };\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_time_extern_without_libc_sleep_conflict(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/time" import { sleep, timestamp };\n'
        'const main = (): I32 => {\n'
        '    sleep(ms = 1);\n'
        '    const ts = timestamp();\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_time_date_methods_native_abi(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/time" import { now, getYear, getMonth, getDay, getHour, getMinute, getSecond, add, sub, format };\n'
        'from "std/test" import { testReset, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const current = now();\n'
        '    const year = getYear(this = current);\n'
        '    const method_year = current.getYear();\n'
        '    const month = getMonth(this = current);\n'
        '    const day = getDay(this = current);\n'
        '    const hour = getHour(this = current);\n'
        '    const minute = getMinute(this = current);\n'
        '    const second = getSecond(this = current);\n'
        '    add(this = current, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\n'
        '    sub(this = current, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\n'
        '    let epoch = Date(timestamp = 0);\n'
        '    const before_epoch = Date(timestamp = -1);\n'
        '    testEqualStr(actual = format(this = epoch, fmt = "YYYY-MM-DD HH:%M:SS"), expected = "1970-01-01 00:00:00", msg = "mixed time format");\n'
        '    testEqualStr(actual = epoch.format(fmt = "YYYY-MM-DD"), expected = "1970-01-01", msg = "date method format");\n'
        '    testEqualStr(actual = format(this = epoch, fmt = "YYYY-MM-DD HH:mm:SS"), expected = "1970-01-01 00:00:00", msg = "named minute time format");\n'
        '    testEqualStr(actual = format(this = epoch, fmt = "%Y-%m-%d %H:%M:%S"), expected = "1970-01-01 00:00:00", msg = "strftime time format");\n'
        '    add(this = epoch, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\n'
        '    testEqualStr(actual = format(this = epoch, fmt = "%Y-%m-%d"), expected = "1971-01-01", msg = "date add mutates this");\n'
        '    sub(this = epoch, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\n'
        '    testEqualStr(actual = format(this = epoch, fmt = "%Y-%m-%d"), expected = "1970-01-01", msg = "date sub mutates this");\n'
        '    epoch.add(year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\n'
        '    testEqualStr(actual = epoch.format(fmt = "%Y-%m-%d"), expected = "1971-01-01", msg = "date method add mutates this");\n'
        '    epoch.sub(year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\n'
        '    testEqualStr(actual = epoch.format(fmt = "%Y-%m-%d"), expected = "1970-01-01", msg = "date method sub mutates this");\n'
        '    testEqualI64(actual = method_year, expected = year, msg = "date method getYear");\n'
        '    testEqualI64(actual = getYear(this = before_epoch), expected = 1969, msg = "negative timestamp year");\n'
        '    testEqualStr(actual = format(this = before_epoch, fmt = "%Y-%m-%d %H:%M:%S"), expected = "1969-12-31 23:59:59", msg = "negative timestamp floor seconds");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_time_duration_and_long_format(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    long_fmt = "x" * 160 + "YYYY-MM-DD"
    expected = "x" * 160 + "1970-01-01"
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/time" import { Duration, durationToString, format };\n'
        'from "std/test" import { testReset, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const seconds = Duration.fromSec(s = 2);\n'
        '    const minutes = Duration.fromMin(m = 1);\n'
        '    const epoch = Date(timestamp = 0);\n'
        f'    const formatted = format(this = epoch, fmt = "{long_fmt}");\n'
        '    testEqualI64(actual = seconds.ms, expected = 2000, msg = "seconds to milliseconds");\n'
        '    testEqualI64(actual = minutes.ms, expected = 60000, msg = "minutes to milliseconds");\n'
        '    testEqualStr(actual = seconds.toString(), expected = "2000ms", msg = "duration method string");\n'
        '    testEqualStr(actual = durationToString(value = minutes), expected = "60000ms", msg = "duration function string");\n'
        f'    testEqualStr(actual = formatted, expected = "{expected}", msg = "long time format not truncated");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_fmt_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { parseInt, parseI64, parseF64, b64Encode, b64Decode, urlEncode, urlDecode };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const parsed = parseInt(s = "42");\n'
        '    const parsed_i64 = parseI64(s = "123456789");\n'
        '    const parsed_f64 = parseF64(s = "3.5");\n'
        '    const unicode_i32 = parseInt(s = "\\u00A0+42\\u3000");\n'
        '    const unicode_i64 = parseI64(s = "\\u2007-123456789\\u202F");\n'
        '    const unicode_f64 = parseF64(s = "\\u205F+.5\\u3000");\n'
        '    const bad_i32 = parseInt(s = "bad");\n'
        '    const bad_i64_float = parseI64(s = "42.0");\n'
        '    const bad_i32_hex = parseInt(s = "0x10");\n'
        '    const bad_i32_feff = parseInt(s = "\\uFEFF42");\n'
        '    const bad_f64 = parseF64(s = "bad");\n'
        '    const bad_f64_hex = parseF64(s = "0x1p2");\n'
        '    const bad_f64_nan = parseF64(s = "nan");\n'
        '    const blob = Blob(data = "hello", size = 5);\n'
        '    const encoded = b64Encode(data = blob);\n'
        '    const decoded = b64Decode(s = encoded);\n'
        '    const url = urlEncode(s = "a b");\n'
        '    const raw = urlDecode(s = url);\n'
        '    testAssert(condition = parsed.ok, msg = "parse i32 ok");\n'
        '    testEqualI64(actual = parsed.value, expected = 42, msg = "parse i32 value");\n'
        '    testAssert(condition = parsed_i64.ok, msg = "parse i64 ok");\n'
        '    testEqualI64(actual = parsed_i64.value, expected = 123456789, msg = "parse i64 value");\n'
        '    testAssert(condition = parsed_f64.ok, msg = "parse f64 ok");\n'
        '    testAssert(condition = parsed_f64.value > 3.49 && parsed_f64.value < 3.51, msg = "parse f64 value");\n'
        '    testAssert(condition = unicode_i32.ok, msg = "parse i32 trims unicode space");\n'
        '    testEqualI64(actual = unicode_i32.value, expected = 42, msg = "parse i32 unicode value");\n'
        '    testAssert(condition = unicode_i64.ok, msg = "parse i64 trims unicode space");\n'
        '    testEqualI64(actual = unicode_i64.value, expected = -123456789, msg = "parse i64 unicode value");\n'
        '    testAssert(condition = unicode_f64.ok, msg = "parse f64 trims unicode space");\n'
        '    testAssert(condition = unicode_f64.value > 0.49 && unicode_f64.value < 0.51, msg = "parse f64 unicode value");\n'
        '    testAssert(condition = !bad_i32.ok, msg = "parse i32 invalid");\n'
        '    testAssert(condition = !bad_i64_float.ok, msg = "parse i64 rejects float syntax");\n'
        '    testAssert(condition = !bad_i32_hex.ok, msg = "parse i32 rejects hex syntax");\n'
        '    testAssert(condition = !bad_i32_feff.ok, msg = "parse i32 does not trim feff");\n'
        '    testAssert(condition = !bad_f64.ok, msg = "parse f64 invalid");\n'
        '    testAssert(condition = !bad_f64_hex.ok, msg = "parse f64 rejects hex float");\n'
        '    testAssert(condition = !bad_f64_nan.ok, msg = "parse f64 rejects nan");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_date_format_method_does_not_conflict_with_std_fmt(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { format };\n'
        'from "std/str" import { strEqual };\n'
        'const main = (): I32 => {\n'
        '    const d = Date(timestamp = 0);\n'
        '    const date_text = d.format(fmt = "YYYY");\n'
        '    const fmt_text = format(template = "hello {}", args = ["ez"]);\n'
        '    return (strEqual(a = date_text, b = "1970") && strEqual(a = fmt_text, b = "hello ez")) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_time_and_std_fmt_format_can_coexist(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/time" import { now };\n'
        'from "std/fmt" import { format };\n'
        'from "std/str" import { strEqual };\n'
        'const main = (): I32 => {\n'
        '    const d = now();\n'
        '    const date_text = d.format(fmt = "YYYY");\n'
        '    const fmt_text = format(template = "{}/{}", args = ["a", "b"]);\n'
        '    return (strEqual(a = date_text, b = "1970") || strEqual(a = fmt_text, b = "a/b")) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_rejects_invalid_base64(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { b64Encode, b64Decode };\n'
        'const main = (): I32 => {\n'
        '    const encoded = b64Encode(data = Blob(data = "hello", size = 5));\n'
        '    const decoded = b64Decode(s = encoded);\n'
        '    const extra_padding = b64Decode(s = "AAAA=");\n'
        '    const middle_padding = b64Decode(s = "AA=A");\n'
        '    const invalid_char = b64Decode(s = "!!!!");\n'
        '    return (decoded.ok && decoded.value.size == 5 && !extra_padding.ok && !middle_padding.ok && !invalid_char.ok) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_builtin_blob_get_and_slice_methods(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strFromBytes, strEqual };\n'
        'const main = (): I32 => {\n'
        '    const data = Blob(data = "hello", size = 5);\n'
        '    const item = data.get(index = 1);\n'
        '    const missing = data.get(index = 99);\n'
        '    const part = data.slice(start = 1, len = 3);\n'
        '    const clipped = data.slice(start = 3, len = 99);\n'
        '    const empty = data.slice(start = -1, len = 2);\n'
        '    const part_text = strFromBytes(data = part);\n'
        '    const clipped_text = strFromBytes(data = clipped);\n'
        '    return (item == 101 && missing == 0 && part_text.ok && strEqual(a = part_text.value, b = "ell") && clipped_text.ok && strEqual(a = clipped_text.value, b = "lo") && empty.size == 0) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_format_brace_placeholders(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { format };\n'
        'from "std/test" import { testReset, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const one: Str[] = ["EzLang"];\n'
        '    const two: Str[] = ["old"];\n'
        '    testEqualStr(actual = format(template = "Hello {}", args = one), expected = "Hello EzLang", msg = "brace placeholder");\n'
        '    testEqualStr(actual = format(template = "{{}} {}", args = one), expected = "{} EzLang", msg = "brace escaping");\n'
        '    testEqualStr(actual = format(template = "Hello %s", args = two), expected = "Hello old", msg = "percent placeholder");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_string_interpolation_uses_dynamic_length(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    long_text = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-extra-long-value"
    expected = f"prefix-{long_text}-suffix"
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'const main = (): I32 => {\n'
        f'    let name: Str = "{long_text}";\n'
        '    let greeting: Str = "prefix-{{name}}-suffix";\n'
        f'    return strEqual(a = greeting, b = "{expected}") ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_and_msgpack_basic_roundtrip(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { toString, jsonStringify, jsonParse, msgpackEncode, msgpackDecode };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const json_i32 = jsonStringify<I32>(data = 42);\n'
        '    const parsed_i32 = jsonParse<I32>(s = json_i32);\n'
        '    const json_i8 = jsonStringify<I8>(data = -128);\n'
        '    const parsed_i8 = jsonParse<I8>(s = json_i8);\n'
        '    const json_i64 = jsonStringify<I64>(data = 123456789);\n'
        '    const parsed_i64 = jsonParse<I64>(s = json_i64);\n'
        '    const json_u8 = jsonStringify<U8>(data = 255);\n'
        '    const parsed_u8 = jsonParse<U8>(s = json_u8);\n'
        '    const json_u32 = jsonStringify<U32>(data = 4294967295);\n'
        '    const parsed_u32 = jsonParse<U32>(s = json_u32);\n'
        '    const json_u64 = jsonStringify<U64>(data = 123456789);\n'
        '    const parsed_u64 = jsonParse<U64>(s = json_u64);\n'
        '    const json_f32 = jsonStringify<F32>(data = 1.5);\n'
        '    const parsed_f32 = jsonParse<F32>(s = json_f32);\n'
        '    const json_bool = jsonStringify<Bool>(data = true);\n'
        '    const parsed_bool = jsonParse<Bool>(s = json_bool);\n'
        '    const json_str = jsonStringify<Str>(data = "EzLang");\n'
        '    const parsed_str = jsonParse<Str>(s = json_str);\n'
        '    const packed = msgpackEncode<I64>(data = parsed_i64);\n'
        '    const unpacked = msgpackDecode<I64>(data = packed);\n'
        '    const packed_i8 = msgpackEncode<I8>(data = parsed_i8);\n'
        '    const unpacked_i8 = msgpackDecode<I8>(data = packed_i8);\n'
        '    const packed_u8 = msgpackEncode<U8>(data = parsed_u8);\n'
        '    const unpacked_u8 = msgpackDecode<U8>(data = packed_u8);\n'
        '    const packed_u32 = msgpackEncode<U32>(data = parsed_u32);\n'
        '    const unpacked_u32 = msgpackDecode<U32>(data = packed_u32);\n'
        '    const packed_u64 = msgpackEncode<U64>(data = parsed_u64);\n'
        '    const unpacked_u64 = msgpackDecode<U64>(data = packed_u64);\n'
        '    const packed_bool = msgpackEncode<Bool>(data = parsed_bool);\n'
        '    const unpacked_bool = msgpackDecode<Bool>(data = packed_bool);\n'
        '    const packed_str = msgpackEncode<Str>(data = parsed_str);\n'
        '    const unpacked_str = msgpackDecode<Str>(data = packed_str);\n'
        '    const packed_f32 = msgpackEncode<F32>(data = parsed_f32);\n'
        '    const unpacked_f32 = msgpackDecode<F32>(data = packed_f32);\n'
        '    const packed_f64 = msgpackEncode<F64>(data = 3.0);\n'
        '    const unpacked_f64 = msgpackDecode<F64>(data = packed_f64);\n'
        '    testEqualI64(actual = parsed_i32, expected = 42, msg = "json i32");\n'
        '    testEqualI64(actual = parsed_i8, expected = -128, msg = "json i8");\n'
        '    testEqualI64(actual = parsed_i64, expected = 123456789, msg = "json i64");\n'
        '    testEqualI64(actual = parsed_u8, expected = 255, msg = "json u8");\n'
        '    testEqualStr(actual = json_u32, expected = "4294967295", msg = "json u32 text");\n'
        '    testEqualI64(actual = parsed_u32, expected = 4294967295, msg = "json u32");\n'
        '    testEqualI64(actual = parsed_u64, expected = 123456789, msg = "json u64");\n'
        '    testEqualStr(actual = toString<U64>(value = parsed_u64), expected = "123456789", msg = "toString u64");\n'
        '    testAssert(condition = parsed_f32 == 1.5, msg = "json f32");\n'
        '    testAssert(condition = parsed_bool, msg = "json bool");\n'
        '    testEqualStr(actual = parsed_str, expected = "EzLang", msg = "json str");\n'
        '    testEqualI64(actual = unpacked, expected = 123456789, msg = "msgpack i64");\n'
        '    testEqualI64(actual = unpacked_i8, expected = -128, msg = "msgpack i8");\n'
        '    testEqualI64(actual = unpacked_u8, expected = 255, msg = "msgpack u8");\n'
        '    testEqualI64(actual = unpacked_u32, expected = 4294967295, msg = "msgpack u32");\n'
        '    testEqualI64(actual = unpacked_u64, expected = 123456789, msg = "msgpack u64");\n'
        '    testAssert(condition = unpacked_bool, msg = "msgpack bool");\n'
        '    testEqualStr(actual = unpacked_str, expected = "EzLang", msg = "msgpack str");\n'
        '    testAssert(condition = unpacked_f32 == 1.5, msg = "msgpack f32");\n'
        '    testAssert(condition = unpacked_f64 == 3.0, msg = "msgpack f64");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_stringify_struct_basic_fields(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { jsonStringify };\n'
        'from "std/test" import { testReset, testEqualStr, testFailed };\n'
        'struct User { name: Str; age: U32; active: Bool; score: F64; };\n'
        'struct Empty {};\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const u = User(name = "Ez", age = 42, active = true, score = 1.5);\n'
        '    const empty = Empty();\n'
        '    testEqualStr(actual = jsonStringify<User>(data = u), expected = "{\\\"name\\\":\\\"Ez\\\",\\\"age\\\":42,\\\"active\\\":true,\\\"score\\\":1.5}", msg = "json struct stringify");\n'
        '    testEqualStr(actual = jsonStringify<Empty>(data = empty), expected = "{}", msg = "json empty struct stringify");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_parse_struct_basic_fields(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/fmt" import { jsonParse };
from "std/mem" import { errIO };
from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };

struct User { name: Str; age: U32; active: Bool; score: F64; };
struct Empty {};

const main = (): I32 => {
    testReset();
    const u = jsonParse<User>(s = "{\"score\":1.5,\"active\":true,\"age\":42,\"name\":\"E\\\"z,}\"}");
    const empty = jsonParse<Empty>(s = "{}");
    testEqualStr(actual = u.name, expected = "E\"z,}", msg = "json struct str field");
    testEqualI64(actual = u.age, expected = 42, msg = "json struct u32 field");
    testAssert(condition = u.active, msg = "json struct bool field");
    testAssert(condition = u.score == 1.5, msg = "json struct f64 field");
    testEqualI64(actual = jsonParse<User>(s = "{\"name\":\"Ez\",\"age\":7,\"active\":false,\"score\":2.0}").age, expected = 7, msg = "json struct direct field");

    const missingErr = catch { const ignored = jsonParse<User>(s = "{\"name\":\"Ez\",\"age\":42,\"active\":true}"); };
    const unknownErr = catch { const ignored = jsonParse<User>(s = "{\"name\":\"Ez\",\"age\":42,\"active\":true,\"score\":1.5,\"extra\":1}"); };
    const duplicateErr = catch { const ignored = jsonParse<User>(s = "{\"name\":\"Ez\",\"name\":\"Other\",\"age\":42,\"active\":true,\"score\":1.5}"); };
    const typeErr = catch { const ignored = jsonParse<User>(s = "{\"name\":\"Ez\",\"age\":-1,\"active\":true,\"score\":1.5}"); };
    const objectErr = catch { const ignored = jsonParse<User>(s = "[]"); };

    testAssert(condition = missingErr.code == errIO && unknownErr.code == errIO && duplicateErr.code == errIO, msg = "json struct field set invalid throws errIO");
    testAssert(condition = typeErr.code == errIO && objectErr.code == errIO, msg = "json struct value invalid throws errIO");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_nested_struct_roundtrip(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/fmt" import { jsonStringify, jsonParse };
from "std/mem" import { errIO };
from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };

struct Address { city: Str; zip: U32; };
struct User { name: Str; address: Address; active: Bool; };

const main = (): I32 => {
    testReset();
    const original = User(name = "Ez", address = Address(city = "Shenzhen", zip = 518000), active = true);
    const json = jsonStringify<User>(data = original);
    testEqualStr(actual = json, expected = "{\"name\":\"Ez\",\"address\":{\"city\":\"Shenzhen\",\"zip\":518000},\"active\":true}", msg = "json nested struct stringify");
    const decoded = jsonParse<User>(s = "{\"active\":true,\"address\":{\"zip\":518000,\"city\":\"Shenzhen\"},\"name\":\"Ez\"}");
    testEqualStr(actual = decoded.address.city, expected = "Shenzhen", msg = "json nested struct field str");
    testEqualI64(actual = decoded.address.zip, expected = 518000, msg = "json nested struct field u32");
    testAssert(condition = decoded.active, msg = "json nested struct bool");

    const missingNestedErr = catch { const ignored = jsonParse<User>(s = "{\"name\":\"Ez\",\"address\":{\"city\":\"Shenzhen\"},\"active\":true}"); };
    const badNestedErr = catch { const ignored = jsonParse<User>(s = "{\"name\":\"Ez\",\"address\":[],\"active\":true}"); };
    testAssert(condition = missingNestedErr.code == errIO && badNestedErr.code == errIO, msg = "json nested invalid throws errIO");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_and_msgpack_struct_list_fields(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/fmt" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };
from "std/mem" import { errIO };
from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };

struct Payload { nums: List<I32>; names: Str[]; };

const main = (): I32 => {
    testReset();
    const original = Payload(nums = [1, 2, 3], names = ["a", "b"]);
    const json = jsonStringify<Payload>(data = original);
    testEqualStr(actual = json, expected = "{\"nums\":[1,2,3],\"names\":[\"a\",\"b\"]}", msg = "json list fields stringify");

    const parsed = jsonParse<Payload>(s = "{\"names\":[\"x\",\"y\"],\"nums\":[4,5]}");
    testEqualI64(actual = parsed.nums[0], expected = 4, msg = "json list i32 item 0");
    testEqualI64(actual = parsed.nums[1], expected = 5, msg = "json list i32 item 1");
    testEqualStr(actual = parsed.names[0], expected = "x", msg = "json str array item 0");
    testEqualStr(actual = parsed.names[1], expected = "y", msg = "json str array item 1");

    const typeErr = catch { const ignored = jsonParse<Payload>(s = "{\"nums\":[1,\"bad\"],\"names\":[\"x\"]}"); };
    testAssert(condition = typeErr.code == errIO, msg = "json list bad item throws errIO");

    const decoded = msgpackDecode<Payload>(data = msgpackEncode<Payload>(data = original));
    testEqualI64(actual = decoded.nums[2], expected = 3, msg = "msgpack list i32 item");
    testEqualStr(actual = decoded.names[1], expected = "b", msg = "msgpack str array item");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_and_msgpack_top_level_list(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/fmt" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };
from "std/test" import { testReset, testEqualI64, testEqualStr, testFailed };

const main = (): I32 => {
    testReset();
    const nums: List<I32> = [1, 2, 3];
    const json = jsonStringify<List<I32>>(data = nums);
    testEqualStr(actual = json, expected = "[1,2,3]", msg = "json top list stringify");

    const parsed = jsonParse<List<I32>>(s = "[4,5]");
    testEqualI64(actual = parsed[0], expected = 4, msg = "json top list parse");
    testEqualI64(actual = parsed[1], expected = 5, msg = "json top list parse second");

    const decoded = msgpackDecode<List<I32>>(data = msgpackEncode<List<I32>>(data = nums));
    testEqualI64(actual = decoded[2], expected = 3, msg = "msgpack top list roundtrip");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_and_msgpack_nested_list(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/fmt" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };
from "std/test" import { testReset, testEqualI64, testEqualStr, testFailed };

const main = (): I32 => {
    testReset();
    const rows: List<List<I32>> = [[1, 2], [3, 4]];
    const json = jsonStringify<List<List<I32>>>(data = rows);
    testEqualStr(actual = json, expected = "[[1,2],[3,4]]", msg = "json nested list stringify");

    const parsed = jsonParse<List<List<I32>>>(s = "[[5,6],[7,8]]");
    testEqualI64(actual = parsed[1][0], expected = 7, msg = "json nested list parse");

    const decoded = msgpackDecode<List<List<I32>>>(data = msgpackEncode<List<List<I32>>>(data = rows));
    testEqualI64(actual = decoded[1][1], expected = 4, msg = "msgpack nested list roundtrip");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_and_msgpack_struct_nested_list_fields(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/fmt" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };
from "std/test" import { testReset, testEqualI64, testEqualStr, testFailed };

struct Payload { rows: List<List<I32>>; };

const main = (): I32 => {
    testReset();
    const payload = Payload(rows = [[1, 2], [3, 4]]);
    const json = jsonStringify<Payload>(data = payload);
    testEqualStr(actual = json, expected = "{\"rows\":[[1,2],[3,4]]}", msg = "json struct nested list stringify");

    const parsed = jsonParse<Payload>(s = "{\"rows\":[[5,6],[7,8]]}");
    testEqualI64(actual = parsed.rows[1][0], expected = 7, msg = "json struct nested list parse");

    const decoded = msgpackDecode<Payload>(data = msgpackEncode<Payload>(data = payload));
    testEqualI64(actual = decoded.rows[1][1], expected = 4, msg = "msgpack struct nested list roundtrip");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_and_msgpack_optional(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/fmt" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };
from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };

struct Payload { value: I32?; };

const main = (): I32 => {
    testReset();
    const some: I32? = 42;
    let none: I32?;

    testEqualStr(actual = jsonStringify<I32?>(data = some), expected = "42", msg = "json optional some stringify");
    testEqualStr(actual = jsonStringify<I32?>(data = none), expected = "null", msg = "json optional none stringify");

    const parsed_some = jsonParse<I32?>(s = "42");
    const parsed_none = jsonParse<I32?>(s = "null");
    testAssert(condition = parsed_some.ok, msg = "json optional some ok");
    testEqualI64(actual = parsed_some.value, expected = 42, msg = "json optional some value");
    testAssert(condition = !parsed_none.ok, msg = "json optional none ok");

    const decoded_some = msgpackDecode<I32?>(data = msgpackEncode<I32?>(data = some));
    const decoded_none = msgpackDecode<I32?>(data = msgpackEncode<I32?>(data = none));
    testAssert(condition = decoded_some.ok, msg = "msgpack optional some ok");
    testEqualI64(actual = decoded_some.value, expected = 42, msg = "msgpack optional some value");
    testAssert(condition = !decoded_none.ok, msg = "msgpack optional none ok");

    const payload = Payload(value = some);
    const payload_json = jsonStringify<Payload>(data = payload);
    testEqualStr(actual = payload_json, expected = "{\"value\":42}", msg = "json optional field stringify");
    const payload_parsed = jsonParse<Payload>(s = "{\"value\":null}");
    testAssert(condition = !payload_parsed.value.ok, msg = "json optional field null parse");
    const payload_decoded = msgpackDecode<Payload>(data = msgpackEncode<Payload>(data = payload));
    testAssert(condition = payload_decoded.value.ok, msg = "msgpack optional field ok");
    testEqualI64(actual = payload_decoded.value.value, expected = 42, msg = "msgpack optional field value");

    const list: List<I32?> = [some, none];
    const list_json = jsonStringify<List<I32?>>(data = list);
    testEqualStr(actual = list_json, expected = "[42,null]", msg = "json optional list stringify");
    const list_parsed = jsonParse<List<I32?>>(s = "[1,null]");
    testAssert(condition = list_parsed[0].ok, msg = "json optional list item some ok");
    testEqualI64(actual = list_parsed[0].value, expected = 1, msg = "json optional list item some value");
    testAssert(condition = !list_parsed[1].ok, msg = "json optional list item none ok");
    const list_decoded = msgpackDecode<List<I32?>>(data = msgpackEncode<List<I32?>>(data = list));
    testAssert(condition = list_decoded[0].ok, msg = "msgpack optional list item some ok");
    testEqualI64(actual = list_decoded[0].value, expected = 42, msg = "msgpack optional list item some value");
    testAssert(condition = !list_decoded[1].ok, msg = "msgpack optional list item none ok");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_and_msgpack_dict_str_keys(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/collections" import { dictLen };
from "std/fmt" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };
from "std/test" import { testReset, testEqualI64, testEqualStr, testFailed };

const main = (): I32 => {
    testReset();
    const scores: Dict<Str, I32> = { a: I32 = 1, b: I32 = 2 };
    const json = jsonStringify<Dict<Str, I32>>(data = scores);
    testEqualStr(actual = json, expected = "{\"a\":1,\"b\":2}", msg = "json dict stringify");

    const parsed = jsonParse<Dict<Str, I32>>(s = "{\"x\":4,\"y\":5}");
    testEqualI64(actual = parsed["x"], expected = 4, msg = "json dict parse x");
    testEqualI64(actual = parsed["y"], expected = 5, msg = "json dict parse y");
    testEqualI64(actual = dictLen<Str, I32>(dict = parsed), expected = 2, msg = "json dict len");

    const decoded = msgpackDecode<Dict<Str, I32>>(data = msgpackEncode<Dict<Str, I32>>(data = scores));
    testEqualI64(actual = decoded["a"], expected = 1, msg = "msgpack dict a");
    testEqualI64(actual = decoded["b"], expected = 2, msg = "msgpack dict b");

    const groups: Dict<Str, List<I32>> = { nums: List<I32> = [3, 4] };
    const groups_json = jsonStringify<Dict<Str, List<I32>>>(data = groups);
    testEqualStr(actual = groups_json, expected = "{\"nums\":[3,4]}", msg = "json dict list stringify");
    const groups_parsed = jsonParse<Dict<Str, List<I32>>>(s = "{\"nums\":[5,6]}");
    testEqualI64(actual = groups_parsed["nums"][1], expected = 6, msg = "json dict list parse");
    const groups_decoded = msgpackDecode<Dict<Str, List<I32>>>(data = msgpackEncode<Dict<Str, List<I32>>>(data = groups));
    testEqualI64(actual = groups_decoded["nums"][0], expected = 3, msg = "msgpack dict list roundtrip");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_and_msgpack_dict_non_str_keys(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/collections" import { dictLen };
from "std/fmt" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };
from "std/test" import { testReset, testEqualI64, testEqualStr, testFailed };

const main = (): I32 => {
    testReset();
    const scores: Dict<I32, Str> = { [1]: Str = "one", [2]: Str = "two" };
    const json = jsonStringify<Dict<I32, Str>>(data = scores);
    testEqualStr(actual = json, expected = "[{\"key\":1,\"value\":\"one\"},{\"key\":2,\"value\":\"two\"}]", msg = "json dict non-str stringify");

    const parsed = jsonParse<Dict<I32, Str>>(s = "[{\"key\":3,\"value\":\"three\"},{\"key\":4,\"value\":\"four\"}]");
    testEqualStr(actual = parsed[3], expected = "three", msg = "json dict non-str parse first");
    testEqualStr(actual = parsed[4], expected = "four", msg = "json dict non-str parse second");
    testEqualI64(actual = dictLen<I32, Str>(dict = parsed), expected = 2, msg = "json dict non-str len");

    const decoded = msgpackDecode<Dict<I32, Str>>(data = msgpackEncode<Dict<I32, Str>>(data = scores));
    testEqualStr(actual = decoded[1], expected = "one", msg = "msgpack dict non-str first");
    testEqualStr(actual = decoded[2], expected = "two", msg = "msgpack dict non-str second");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_and_msgpack_union(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/fmt" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };
from "std/str" import { strEqual };
from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };

struct Payload { value: I32 | Str; };

const main = (): I32 => {
    testReset();
    const number: I32 | Str = 42;
    const text: I32 | Str = "ez";

    const number_json = jsonStringify<I32 | Str>(data = number);
    testEqualStr(actual = number_json, expected = "{\"tag\":0,\"value\":42}", msg = "json union number stringify");
    const text_json = jsonStringify<I32 | Str>(data = text);
    testEqualStr(actual = text_json, expected = "{\"tag\":1,\"value\":\"ez\"}", msg = "json union text stringify");

    const parsed = jsonParse<I32 | Str>(s = "{\"tag\":1,\"value\":\"ok\"}");
    testEqualI64(actual = parsed.tag, expected = 1, msg = "json union tag");
    testAssert(condition = strEqual(a = parsed.value, b = "ok"), msg = "json union value");

    const decoded_text = msgpackDecode<I32 | Str>(data = msgpackEncode<I32 | Str>(data = text));
    testEqualI64(actual = decoded_text.tag, expected = 1, msg = "msgpack union text tag");
    testAssert(condition = strEqual(a = decoded_text.value, b = "ez"), msg = "msgpack union text value");

    const payload = Payload(value = parsed);
    const payload_json = jsonStringify<Payload>(data = payload);
    testEqualStr(actual = payload_json, expected = "{\"value\":{\"tag\":1,\"value\":\"ok\"}}", msg = "json union field stringify");
    const payload_decoded = msgpackDecode<Payload>(data = msgpackEncode<Payload>(data = jsonParse<Payload>(s = payload_json)));
    testEqualI64(actual = payload_decoded.value.tag, expected = 1, msg = "msgpack union field tag");
    testAssert(condition = strEqual(a = payload_decoded.value.value, b = "ok"), msg = "msgpack union field value");

    const list: List<I32 | Str> = [number, text];
    const list_json = jsonStringify<List<I32 | Str>>(data = list);
    testEqualStr(actual = list_json, expected = "[{\"tag\":0,\"value\":42},{\"tag\":1,\"value\":\"ez\"}]", msg = "json union list stringify");
    const list_decoded = msgpackDecode<List<I32 | Str>>(data = msgpackEncode<List<I32 | Str>>(data = jsonParse<List<I32 | Str>>(s = list_json)));
    testEqualI64(actual = list_decoded[0].tag, expected = 0, msg = "msgpack union list first tag");
    testEqualStr(actual = jsonStringify<I32 | Str>(data = list_decoded[0]), expected = "{\"tag\":0,\"value\":42}", msg = "msgpack union list first value");
    testEqualI64(actual = list_decoded[1].tag, expected = 1, msg = "msgpack union list second tag");
    testAssert(condition = strEqual(a = list_decoded[1].value, b = "ez"), msg = "msgpack union list second value");

    const badTagErr = catch { const ignored = jsonParse<I32 | Str>(s = "{\"tag\":2,\"value\":0}"); };
    testEqualI64(actual = badTagErr.code, expected = 4, msg = "json union bad tag");
    const badValueErr = catch { const ignored = jsonParse<I32 | Str>(s = "{\"tag\":0,\"value\":\"bad\"}"); };
    testEqualI64(actual = badValueErr.code, expected = 4, msg = "json union bad value");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_msgpack_struct_basic_fields(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/fmt" import { b64Decode, msgpackEncode, msgpackDecode };
from "std/mem" import { errIO };
from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };

struct User { name: Str; age: U32; active: Bool; score: F64; };
struct Empty {};

const main = (): I32 => {
    testReset();

    const original = User(name = "Ez", age = 42, active = true, score = 1.5);
    const decoded = msgpackDecode<User>(data = msgpackEncode<User>(data = original));
    const empty = msgpackDecode<Empty>(data = msgpackEncode<Empty>(data = Empty()));
    testEqualStr(actual = decoded.name, expected = "Ez", msg = "msgpack struct str field");
    testEqualI64(actual = decoded.age, expected = 42, msg = "msgpack struct u32 field");
    testAssert(condition = decoded.active, msg = "msgpack struct bool field");
    testAssert(condition = decoded.score == 1.5, msg = "msgpack struct f64 field");

    const valid = b64Decode(s = "hKVzY29yZcs/+AAAAAAAAKZhY3RpdmXDo2FnZc4AAAAqpG5hbWWlRSJ6LH0=");
    testAssert(condition = valid.ok, msg = "msgpack struct fixture decoded");
    const fromFixture = msgpackDecode<User>(data = valid.value);
    testEqualStr(actual = fromFixture.name, expected = "E\"z,}", msg = "msgpack struct fixture str");
    testEqualI64(actual = fromFixture.age, expected = 42, msg = "msgpack struct fixture age");
    testAssert(condition = fromFixture.active && fromFixture.score == 1.5, msg = "msgpack struct fixture rest");

    const missing = b64Decode(s = "g6RuYW1lokV6o2FnZc4AAAAqpmFjdGl2ZcM=");
    const unknown = b64Decode(s = "haRuYW1lokV6o2FnZc4AAAAqpmFjdGl2ZcOlc2NvcmXLP/gAAAAAAAClZXh0cmEB");
    const duplicate = b64Decode(s = "haRuYW1lokV6pG5hbWWlT3RoZXKjYWdlzgAAACqmYWN0aXZlw6VzY29yZcs/+AAAAAAAAA==");
    const typeBad = b64Decode(s = "hKRuYW1lokV6o2FnZf+mYWN0aXZlw6VzY29yZcs/+AAAAAAAAA==");
    const nonMap = b64Decode(s = "kA==");
    testAssert(condition = missing.ok && unknown.ok && duplicate.ok && typeBad.ok && nonMap.ok, msg = "msgpack invalid fixtures decoded");

    const missingErr = catch { const ignored = msgpackDecode<User>(data = missing.value); };
    const unknownErr = catch { const ignored = msgpackDecode<User>(data = unknown.value); };
    const duplicateErr = catch { const ignored = msgpackDecode<User>(data = duplicate.value); };
    const typeErr = catch { const ignored = msgpackDecode<User>(data = typeBad.value); };
    const mapErr = catch { const ignored = msgpackDecode<User>(data = nonMap.value); };
    testAssert(condition = missingErr.code == errIO && unknownErr.code == errIO && duplicateErr.code == errIO, msg = "msgpack struct field set invalid throws errIO");
    testAssert(condition = typeErr.code == errIO && mapErr.code == errIO, msg = "msgpack struct value invalid throws errIO");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_msgpack_nested_struct_roundtrip(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    source = r'''
from "std/fmt" import { b64Decode, msgpackEncode, msgpackDecode };
from "std/mem" import { errIO };
from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };

struct Address { city: Str; zip: U32; };
struct User { name: Str; address: Address; active: Bool; };

const main = (): I32 => {
    testReset();
    const original = User(name = "Ez", address = Address(city = "Shenzhen", zip = 518000), active = true);
    const decoded = msgpackDecode<User>(data = msgpackEncode<User>(data = original));
    testEqualStr(actual = decoded.address.city, expected = "Shenzhen", msg = "msgpack nested struct field str");
    testEqualI64(actual = decoded.address.zip, expected = 518000, msg = "msgpack nested struct field u32");
    testAssert(condition = decoded.active, msg = "msgpack nested struct bool");

    const valid = b64Decode(s = "g6ZhY3RpdmXDp2FkZHJlc3OCo3ppcM4AB+dwpGNpdHmoU2hlbnpoZW6kbmFtZaJFeg==");
    testAssert(condition = valid.ok, msg = "msgpack nested fixture decoded");
    const fromFixture = msgpackDecode<User>(data = valid.value);
    testEqualStr(actual = fromFixture.address.city, expected = "Shenzhen", msg = "msgpack nested fixture city");
    testEqualI64(actual = fromFixture.address.zip, expected = 518000, msg = "msgpack nested fixture zip");

    const missingNested = b64Decode(s = "g6RuYW1lokV6p2FkZHJlc3OBpGNpdHmoU2hlbnpoZW6mYWN0aXZlww==");
    const badNested = b64Decode(s = "g6RuYW1lokV6p2FkZHJlc3OQpmFjdGl2ZcM=");
    testAssert(condition = missingNested.ok && badNested.ok, msg = "msgpack nested invalid fixtures decoded");
    const missingNestedErr = catch { const ignored = msgpackDecode<User>(data = missingNested.value); };
    const badNestedErr = catch { const ignored = msgpackDecode<User>(data = badNested.value); };
    testAssert(condition = missingNestedErr.code == errIO && badNestedErr.code == errIO, msg = "msgpack nested invalid throws errIO");
    return testFailed();
};
'''.lstrip()
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_string_escapes_and_string_literal_decoding(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { jsonStringify, jsonParse };\n'
        'from "std/mem" import { errIO };\n'
        'from "std/str" import { strByteLen, strContains };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const literal = "line\\nquote\\\" slash\\\\ tab\\t smile\\u263A";\n'
        '    testEqualI64(actual = strByteLen(s = literal), expected = 32, msg = "decoded literal byte len");\n'
        '    const json = jsonStringify<Str>(data = literal);\n'
        '    testAssert(condition = strContains(s = json, needle = "\\\\n"), msg = "json escapes newline");\n'
        '    testAssert(condition = strContains(s = json, needle = "\\\\t"), msg = "json escapes tab");\n'
        '    testAssert(condition = strContains(s = json, needle = "\\\\\\\""), msg = "json escapes quote");\n'
        '    const parsed = jsonParse<Str>(s = "\\\"line\\\\nquote\\\\\\\" slash\\\\\\\\ tab\\\\t smile\\\\u263A\\\"");\n'
        '    testEqualStr(actual = parsed, expected = literal, msg = "json string parse escapes");\n'
        '    const pair = jsonParse<Str>(s = "\\\"\\\\uD83D\\\\uDE00\\\"");\n'
        '    testEqualI64(actual = strByteLen(s = pair), expected = 4, msg = "json surrogate pair utf8 bytes");\n'
        '    const badErr = catch { const ignored = jsonParse<Str>(s = "\\\"bad\\\\q\\\""); };\n'
        '    testAssert(condition = badErr.code == errIO, msg = "invalid json escape throws errIO");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_parse_rejects_non_json_scalar_forms(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { jsonStringify, jsonParse };\n'
        'from "std/mem" import { errIO };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    testEqualI64(actual = jsonParse<I8>(s = "-128"), expected = -128, msg = "json i8 min");\n'
        '    testEqualI64(actual = jsonParse<U8>(s = "255"), expected = 255, msg = "json u8 max");\n'
        '    testEqualI64(actual = jsonParse<I32>(s = "1e2"), expected = 100, msg = "json integer accepts exponent integer");\n'
        '    testEqualI64(actual = jsonParse<I64>(s = "9223372036854775807"), expected = 9223372036854775807, msg = "json i64 max");\n'
        '    testEqualI64(actual = jsonParse<U32>(s = "4294967295"), expected = 4294967295, msg = "json u32 max");\n'
        '    testEqualStr(actual = jsonStringify<U64>(data = jsonParse<U64>(s = "18446744073709551615")), expected = "18446744073709551615", msg = "json u64 max");\n'
        '    const plusErr = catch { const ignored = jsonParse<I32>(s = "+1"); };\n'
        '    const i8OverflowErr = catch { const ignored = jsonParse<I8>(s = "128"); };\n'
        '    const u8NegativeErr = catch { const ignored = jsonParse<U8>(s = "-1"); };\n'
        '    const u8OverflowErr = catch { const ignored = jsonParse<U8>(s = "256"); };\n'
        '    const zeroErr = catch { const ignored = jsonParse<I64>(s = "01"); };\n'
        '    const overflowErr = catch { const ignored = jsonParse<I64>(s = "9223372036854775808"); };\n'
        '    const negativeUnsignedErr = catch { const ignored = jsonParse<U32>(s = "-1"); };\n'
        '    const u32OverflowErr = catch { const ignored = jsonParse<U32>(s = "4294967296"); };\n'
        '    const u64OverflowErr = catch { const ignored = jsonParse<U64>(s = "18446744073709551616"); };\n'
        '    const fractionErr = catch { const ignored = jsonParse<I64>(s = "1.5"); };\n'
        '    const dotErr = catch { const ignored = jsonParse<F64>(s = "1."); };\n'
        '    const f32Err = catch { const ignored = jsonParse<F32>(s = "1e+"); };\n'
        '    const expErr = catch { const ignored = jsonParse<F64>(s = "1e+"); };\n'
        '    const strErr = catch { const ignored = jsonParse<Str>(s = "42"); };\n'
        '    testAssert(condition = i8OverflowErr.code == errIO && u8NegativeErr.code == errIO && u8OverflowErr.code == errIO, msg = "json 8-bit invalid throws errIO");\n'
        '    testAssert(condition = plusErr.code == errIO && zeroErr.code == errIO && overflowErr.code == errIO && fractionErr.code == errIO, msg = "json integer invalid throws errIO");\n'
        '    testAssert(condition = negativeUnsignedErr.code == errIO && u32OverflowErr.code == errIO && u64OverflowErr.code == errIO, msg = "json unsigned invalid throws errIO");\n'
        '    testAssert(condition = dotErr.code == errIO && expErr.code == errIO && strErr.code == errIO, msg = "json scalar invalid throws errIO");\n'
        '    testAssert(condition = f32Err.code == errIO, msg = "json f32 invalid throws errIO");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_json_stringify_nonfinite_f64_as_json_null(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { jsonStringify };\n'
        'from "std/math" import { mathSqrt, mathLog };\n'
        'from "std/test" import { testReset, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const nanv = mathSqrt(value = -1.0);\n'
        '    const infv = mathLog(value = 0.0);\n'
        '    testEqualStr(actual = jsonStringify<F64>(data = nanv), expected = "null", msg = "json stringify nan as null");\n'
        '    testEqualStr(actual = jsonStringify<F64>(data = infv), expected = "null", msg = "json stringify infinity as null");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_msgpack_decodes_standard_integer_and_float_variants(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { b64Decode, msgpackDecode };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const fix_pos = b64Decode(s = "Kg==");\n'
        '    const fix_neg = b64Decode(s = "/w==");\n'
        '    const u8 = b64Decode(s = "zMg=");\n'
        '    const i16 = b64Decode(s = "0c/H");\n'
        '    const f32 = b64Decode(s = "ykBI9cM=");\n'
        '    testAssert(condition = fix_pos.ok && fix_neg.ok && u8.ok && i16.ok && f32.ok, msg = "msgpack fixtures decode");\n'
        '    testEqualI64(actual = msgpackDecode<I32>(data = fix_pos.value), expected = 42, msg = "msgpack positive fixint");\n'
        '    testEqualI64(actual = msgpackDecode<I32>(data = fix_neg.value), expected = -1, msg = "msgpack negative fixint");\n'
        '    testEqualI64(actual = msgpackDecode<I64>(data = u8.value), expected = 200, msg = "msgpack uint8");\n'
        '    testEqualI64(actual = msgpackDecode<I64>(data = i16.value), expected = -12345, msg = "msgpack int16");\n'
        '    const f = msgpackDecode<F64>(data = f32.value);\n'
        '    testAssert(condition = f > 3.139 && f < 3.141, msg = "msgpack float32");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fmt_string_decoders_reject_invalid_payloads(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { b64Decode, jsonParse, msgpackDecode, urlDecode };\n'
        'from "std/mem" import { errIO };\n'
        'from "std/test" import { testReset, testAssert, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const valid = b64Decode(s = "oXg=");\n'
        '    const trailing = b64Decode(s = "oXj/");\n'
        '    const invalid_utf8 = b64Decode(s = "of8=");\n'
        '    const nul_str = b64Decode(s = "oQA=");\n'
        '    const invalid_url = urlDecode(s = "%FF");\n'
        '    const nul_url = urlDecode(s = "%00");\n'
        '    testAssert(condition = valid.ok && trailing.ok && invalid_utf8.ok && nul_str.ok, msg = "msgpack str fixtures decode");\n'
        '    testEqualStr(actual = msgpackDecode<Str>(data = valid.value), expected = "x", msg = "msgpack fixstr valid");\n'
        '    testEqualStr(actual = msgpackDecode<Str>(data = trailing.value), expected = "", msg = "msgpack fixstr trailing rejected");\n'
        '    testEqualStr(actual = msgpackDecode<Str>(data = invalid_utf8.value), expected = "", msg = "msgpack str invalid utf8 rejected");\n'
        '    testEqualStr(actual = msgpackDecode<Str>(data = nul_str.value), expected = "", msg = "msgpack str nul rejected");\n'
        '    testAssert(condition = !invalid_url.ok, msg = "urlDecode invalid utf8 rejected");\n'
        '    testAssert(condition = !nul_url.ok, msg = "urlDecode nul rejected");\n'
        '    const json_nul_err = catch { const ignored = jsonParse<Str>(s = "\\\"\\\\u0000\\\""); };\n'
        '    testAssert(condition = json_nul_err.code == errIO, msg = "json string nul rejected");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_str_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strByteLen, strCharLen, strIsEmpty, strIsValidUtf8, strSliceBytes, strSliceChars, strCharAt, strToBytes, strFromBytes, strContains, strStartsWith, strEndsWith, strIndexOf, strSplit, strJoin, strTrim, strReplace, strToLower, strToUpper };\n'
        'from "std/mem" import { allocRaw, set };\n'
        'from "std/collections" import { listLen };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const text = " Ez语言 ";\n'
        '    testEqualI64(actual = strByteLen(s = text), expected = 10, msg = "utf8 byte len");\n'
        '    testEqualI64(actual = strCharLen(s = text), expected = 6, msg = "utf8 char len");\n'
        '    testAssert(condition = strIsEmpty(s = ""), msg = "empty string");\n'
        '    testAssert(condition = strIsValidUtf8(s = text), msg = "valid utf8 string");\n'
        '    testEqualStr(actual = strSliceBytes(s = text, start = 1, end = 3), expected = "Ez", msg = "byte slice ascii boundary");\n'
        '    testEqualStr(actual = strSliceChars(s = text, start = 3, end = 5), expected = "语言", msg = "char slice unicode");\n'
        '    testEqualStr(actual = strSliceChars(s = text, start = -2, end = 2), expected = " E", msg = "negative char slice clamps");\n'
        '    testEqualStr(actual = strSliceChars(s = text, start = 99, end = 100), expected = "", msg = "out of range char slice");\n'
        '    const ch = strCharAt(s = text, index = 3);\n'
        '    testAssert(condition = ch.ok, msg = "char at unicode ok");\n'
        '    testEqualStr(actual = ch.value, expected = "语", msg = "char at unicode value");\n'
        '    const missing = strCharAt(s = text, index = 99);\n'
        '    testAssert(condition = !missing.ok, msg = "char at out of range");\n'
        '    const bytes = strToBytes(s = text);\n'
        '    const restored = strFromBytes(data = bytes);\n'
        '    testAssert(condition = restored.ok, msg = "bytes roundtrip ok");\n'
        '    testEqualStr(actual = restored.value, expected = text, msg = "bytes roundtrip value");\n'
        '    const invalid_bytes = allocRaw(size = 1);\n'
        '    set(dst = invalid_bytes, value = 255, count = 1);\n'
        '    const invalid = strFromBytes(data = invalid_bytes);\n'
        '    testAssert(condition = !invalid.ok, msg = "invalid utf8 rejected");\n'
        '    const nul_bytes = allocRaw(size = 1);\n'
        '    set(dst = nul_bytes, value = 0, count = 1);\n'
        '    const nul = strFromBytes(data = nul_bytes);\n'
        '    testAssert(condition = !nul.ok, msg = "nul byte rejected");\n'
        '    testAssert(condition = strContains(s = text, needle = "Ez") && strStartsWith(s = text, prefix = " ") && strEndsWith(s = text, suffix = " "), msg = "contains starts ends");\n'
        '    testEqualI64(actual = strIndexOf(s = text, needle = "语言"), expected = 3, msg = "index byte offset");\n'
        '    const parts = strSplit(s = "a,,b", sep = ",");\n'
        '    testEqualI64(actual = listLen<Str>(list = parts), expected = 3, msg = "split preserves empty fields");\n'
        '    testEqualStr(actual = parts[1], expected = "", msg = "split empty middle");\n'
        '    testEqualStr(actual = strJoin(parts = parts, sep = "|"), expected = "a||b", msg = "join fields");\n'
        '    const chars = strSplit(s = "语言", sep = "");\n'
        '    testEqualI64(actual = listLen<Str>(list = chars), expected = 2, msg = "split empty separator by char");\n'
        '    testEqualStr(actual = chars[1], expected = "言", msg = "split unicode char");\n'
        '    testEqualStr(actual = strTrim(s = "  EzLang  "), expected = "EzLang", msg = "trim spaces");\n'
        '    testEqualStr(actual = strTrim(s = "\u00A0\u3000EzLang\u2003\u202F"), expected = "EzLang", msg = "trim unicode spaces");\n'
        '    testEqualStr(actual = strTrim(s = "\uFEFFEzLang\uFEFF"), expected = "\uFEFFEzLang\uFEFF", msg = "trim excludes bom");\n'
        '    testEqualStr(actual = strReplace(s = "Ez Ez", old = "Ez", newValue = "Easy"), expected = "Easy Easy", msg = "replace all");\n'
        '    testEqualStr(actual = strToLower(s = "EzLANG ÄÖÜ ΣЖ Ÿ"), expected = "ezlang äöü σж ÿ", msg = "lower unicode simple case");\n'
        '    testEqualStr(actual = strToUpper(s = "EzLang äöü σςж ÿ ß"), expected = "EZLANG ÄÖÜ ΣΣЖ Ÿ ẞ", msg = "upper unicode simple case");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_arena_alloc_raw_grows_beyond_initial_capacity(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/mem" import { allocRaw, set };\n'
        'const main = (): I32 => {\n'
        '    const big = allocRaw(size = 1049600);\n'
        '    set(dst = big, value = 7, count = 1049600);\n'
        '    const small = allocRaw(size = 16);\n'
        '    set(dst = small, value = 3, count = 16);\n'
        '    return (big.size == 1049600 && small.size == 16) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_arena_returned_list_survives_caller_allocations(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/mem" import { allocRaw, set };\n'
        'const make = (): List<I32> => {\n'
        '    return [11, 22, 33];\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    const xs = make();\n'
        '    const scratch = allocRaw(size = 4096);\n'
        '    set(dst = scratch, value = 0, count = 4096);\n'
        '    return (xs[0] == 11 && xs[1] == 22 && xs[2] == 33) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_arena_returned_dict_survives_caller_allocations(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/mem" import { allocRaw, set };\n'
        'const make = (): { [key: Str]: I32 } => {\n'
        '    return { a: I32 = 11, b: I32 = 22 };\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    const meta = make();\n'
        '    const scratch = allocRaw(size = 4096);\n'
        '    set(dst = scratch, value = 0, count = 4096);\n'
        '    return (meta["a"] == 11 && meta["b"] == 22) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_path_relative_and_file_url_edges(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/path" import { pathNormalize, pathDir, pathBase, pathExt, pathIsAbs, pathRelative, pathParse, pathToFileUrl, pathFromFileUrl };\n'
        'from "std/test" import { testReset, testAssert, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    testEqualStr(actual = pathNormalize(path = "/tmp/./ez/../main.ez"), expected = "/tmp/main.ez", msg = "posix normalize dot segments");\n'
        '    testEqualStr(actual = pathNormalize(path = "a/b/../"), expected = "a", msg = "relative trailing separator normalize");\n'
        '    testEqualStr(actual = pathNormalize(path = "./"), expected = ".", msg = "dot path normalize");\n'
        '    testEqualStr(actual = pathNormalize(path = "C:/Temp/../Ez/file.txt"), expected = "C:/Ez/file.txt", msg = "windows drive normalize");\n'
        '    testEqualStr(actual = pathNormalize(path = "//server/share/dir/.."), expected = "//server/share", msg = "windows unc normalize");\n'
        '    testAssert(condition = pathIsAbs(path = "/tmp") && pathIsAbs(path = "C:/Temp") && pathIsAbs(path = "//server/share") && !pathIsAbs(path = "a/b"), msg = "absolute path detection");\n'
        '    testEqualStr(actual = pathDir(path = "/"), expected = "/", msg = "dir keeps posix root");\n'
        '    testEqualStr(actual = pathBase(path = "/"), expected = "", msg = "base of posix root is empty");\n'
        '    const parsed_root = pathParse(path = "/");\n'
        '    testEqualStr(actual = parsed_root.root, expected = "/", msg = "parse posix root root");\n'
        '    testEqualStr(actual = parsed_root.dir, expected = "/", msg = "parse posix root dir");\n'
        '    testEqualStr(actual = parsed_root.base, expected = "", msg = "parse posix root base");\n'
        '    testEqualStr(actual = parsed_root.name, expected = "", msg = "parse posix root name");\n'
        '    testEqualStr(actual = parsed_root.ext, expected = "", msg = "parse posix root ext");\n'
        '    testEqualStr(actual = pathDir(path = "C:/"), expected = "C:/", msg = "dir keeps windows drive root");\n'
        '    testEqualStr(actual = pathBase(path = "C:/"), expected = "", msg = "base of windows drive root is empty");\n'
        '    testEqualStr(actual = pathDir(path = "//server/share"), expected = "//server/share", msg = "dir keeps unc root");\n'
        '    testEqualStr(actual = pathBase(path = "//server/share"), expected = "", msg = "base of unc root is empty");\n'
        '    testEqualStr(actual = pathDir(path = "/tmp/ez/main.ez"), expected = "/tmp/ez", msg = "dir posix");\n'
        '    testEqualStr(actual = pathBase(path = "/tmp/ez/main.ez"), expected = "main.ez", msg = "base posix");\n'
        '    testEqualStr(actual = pathExt(path = "/tmp/archive.tar.gz"), expected = ".gz", msg = "extension last suffix");\n'
        '    testEqualStr(actual = pathExt(path = "/tmp/.env"), expected = "", msg = "dotfile has no extension");\n'
        '    const parsed = pathParse(path = "/tmp/archive.tar.gz");\n'
        '    testEqualStr(actual = parsed.root, expected = "/", msg = "parse root");\n'
        '    testEqualStr(actual = parsed.dir, expected = "/tmp", msg = "parse dir");\n'
        '    testEqualStr(actual = parsed.base, expected = "archive.tar.gz", msg = "parse base");\n'
        '    testEqualStr(actual = parsed.name, expected = "archive.tar", msg = "parse name");\n'
        '    testEqualStr(actual = parsed.ext, expected = ".gz", msg = "parse ext");\n'
        '    testEqualStr(actual = pathRelative(fromPath = "/tmp", toPath = "/tmp/ez/main.ez"), expected = "ez/main.ez", msg = "relative child path");\n'
        '    testEqualStr(actual = pathRelative(fromPath = "/tmp/a", toPath = "/tmp/b/c"), expected = "../b/c", msg = "relative sibling path");\n'
        '    testEqualStr(actual = pathRelative(fromPath = "/tmp/ez", toPath = "/tmp/ez"), expected = ".", msg = "relative same path");\n'
        '    testEqualStr(actual = pathRelative(fromPath = "C:/a/b", toPath = "D:/x"), expected = "D:/x", msg = "relative keeps different drive absolute");\n'
        '    testEqualStr(actual = pathToFileUrl(path = "/tmp/Ez Lang/main.ez"), expected = "file:///tmp/Ez%20Lang/main.ez", msg = "file url encodes spaces");\n'
        '    testEqualStr(actual = pathToFileUrl(path = "C:/Temp/Ez Lang/main.ez"), expected = "file:///C:/Temp/Ez%20Lang/main.ez", msg = "file url encodes windows drive");\n'
        '    const decoded = pathFromFileUrl(url = "file:///tmp/Ez%20Lang/main.ez");\n'
        '    testAssert(condition = decoded.ok, msg = "file url decode ok");\n'
        '    testEqualStr(actual = decoded.value, expected = "/tmp/Ez Lang/main.ez", msg = "file url decodes spaces");\n'
        '    const decoded_drive = pathFromFileUrl(url = "file:///C:/Temp/Ez%20Lang/main.ez");\n'
        '    testAssert(condition = decoded_drive.ok, msg = "file url drive decode ok");\n'
        '    testEqualStr(actual = decoded_drive.value, expected = "C:/Temp/Ez Lang/main.ez", msg = "file url decodes windows drive");\n'
        '    const invalid = pathFromFileUrl(url = "file:///tmp/%");\n'
        '    testAssert(condition = !invalid.ok, msg = "invalid file url percent rejected");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_math_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/math" import { mathPI, mathE, mathAbsI32, mathAbsI64, mathMinI32, mathMaxI32, mathClampI32, mathGcdI64, mathLcmI64, mathSqrt, mathPow, mathSin, mathCos, mathTan, mathLog, mathExp, mathFloor, mathCeil, mathRound, mathIsNaN, mathIsInf, mathAddI64Checked, mathSubI64Checked, mathMulI64Checked, mathDivI64Checked, mathF64ToI32, mathF64ToI64, mathI64ToF64 };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const abs32 = mathAbsI32(value = -3);\n'
        '    const abs64 = mathAbsI64(value = -4);\n'
        '    const minv = mathMinI32(a = 7, b = 2);\n'
        '    const maxv = mathMaxI32(a = 7, b = 2);\n'
        '    const clamped = mathClampI32(value = 9, minValue = 0, maxValue = 5);\n'
        '    const swapped = mathClampI32(value = 1, minValue = 5, maxValue = 0);\n'
        '    const gcd = mathGcdI64(a = -18, b = 24);\n'
        '    const lcm = mathLcmI64(a = 6, b = 8);\n'
        '    const lcm_neg = mathLcmI64(a = -6, b = 8);\n'
        '    const root = mathSqrt(value = 4.0);\n'
        '    const power = mathPow(base = 2.0, exp = 8.0);\n'
        '    const sinv = mathSin(value = mathPI);\n'
        '    const cosv = mathCos(value = 0.0);\n'
        '    const tanv = mathTan(value = 0.0);\n'
        '    const logv = mathLog(value = mathE);\n'
        '    const expv = mathExp(value = 1.0);\n'
        '    const floorv = mathFloor(value = 1.9);\n'
        '    const ceilv = mathCeil(value = 1.1);\n'
        '    const roundv = mathRound(value = 1.5);\n'
        '    const round_neg = mathRound(value = -1.5);\n'
        '    const nanv = mathSqrt(value = -1.0);\n'
        '    const infv = mathLog(value = 0.0);\n'
        '    const sum = mathAddI64Checked(a = 1, b = 2);\n'
        '    const diff = mathSubI64Checked(a = 1, b = 2);\n'
        '    const product = mathMulI64Checked(a = 2, b = 3);\n'
        '    const quotient = mathDivI64Checked(a = 6, b = 3);\n'
        '    const floor_quotient = mathDivI64Checked(a = -3, b = 2);\n'
        '    const floor_quotient_neg_rhs = mathDivI64Checked(a = 3, b = -2);\n'
        '    const add_overflow = mathAddI64Checked(a = 9223372036854775807, b = 1);\n'
        '    const mul_overflow = mathMulI64Checked(a = 3037000500, b = 3037000500);\n'
        '    const div_zero = mathDivI64Checked(a = 1, b = 0);\n'
        '    const narrowed = mathF64ToI32(value = 42.0);\n'
        '    const narrowed_i64 = mathF64ToI64(value = 42.0);\n'
        '    const max_i32 = mathF64ToI32(value = 2147483647.0);\n'
        '    const min_i32 = mathF64ToI32(value = -2147483648.0);\n'
        '    const trunc_i32_hi = mathF64ToI32(value = 2147483647.9);\n'
        '    const trunc_i32_lo = mathF64ToI32(value = -2147483648.9);\n'
        '    const too_wide = mathF64ToI32(value = 2147483648.0);\n'
        '    const too_low = mathF64ToI32(value = -2147483649.0);\n'
        '    const min_i64 = mathF64ToI64(value = -9223372036854775808.0);\n'
        '    const too_wide_i64 = mathF64ToI64(value = 9223372036854775808.0);\n'
        '    const back_to_f64 = mathI64ToF64(value = 42);\n'
        '    testEqualI64(actual = abs32, expected = 3, msg = "abs i32");\n'
        '    testEqualI64(actual = abs64, expected = 4, msg = "abs i64");\n'
        '    testEqualI64(actual = minv, expected = 2, msg = "min i32");\n'
        '    testEqualI64(actual = maxv, expected = 7, msg = "max i32");\n'
        '    testEqualI64(actual = clamped, expected = 5, msg = "clamp max");\n'
        '    testEqualI64(actual = swapped, expected = 1, msg = "clamp swapped bounds");\n'
        '    testEqualI64(actual = gcd, expected = 6, msg = "gcd");\n'
        '    testEqualI64(actual = lcm, expected = 24, msg = "lcm");\n'
        '    testEqualI64(actual = lcm_neg, expected = 24, msg = "negative lcm");\n'
        '    testAssert(condition = root == 2.0, msg = "sqrt");\n'
        '    testAssert(condition = power == 256.0, msg = "pow");\n'
        '    testAssert(condition = sinv < 0.000001 && sinv > -0.000001, msg = "sin pi");\n'
        '    testAssert(condition = cosv == 1.0, msg = "cos zero");\n'
        '    testAssert(condition = tanv == 0.0, msg = "tan zero");\n'
        '    testAssert(condition = logv == 1.0, msg = "log e");\n'
        '    testAssert(condition = expv > 2.718 && expv < 2.719, msg = "exp one");\n'
        '    testAssert(condition = floorv == 1.0, msg = "floor");\n'
        '    testAssert(condition = ceilv == 2.0, msg = "ceil");\n'
        '    testAssert(condition = roundv == 2.0, msg = "round");\n'
        '    testAssert(condition = round_neg == -2.0, msg = "negative round half away from zero");\n'
        '    testAssert(condition = mathIsNaN(value = nanv), msg = "nan");\n'
        '    testAssert(condition = mathIsInf(value = infv), msg = "inf");\n'
        '    testAssert(condition = sum.ok && diff.ok && product.ok && quotient.ok && floor_quotient.ok && floor_quotient_neg_rhs.ok, msg = "checked ok");\n'
        '    testEqualI64(actual = sum.value, expected = 3, msg = "checked add");\n'
        '    testEqualI64(actual = diff.value, expected = -1, msg = "checked sub");\n'
        '    testEqualI64(actual = product.value, expected = 6, msg = "checked mul");\n'
        '    testEqualI64(actual = quotient.value, expected = 2, msg = "checked div");\n'
        '    testEqualI64(actual = floor_quotient.value, expected = -2, msg = "checked floor div");\n'
        '    testEqualI64(actual = floor_quotient_neg_rhs.value, expected = -2, msg = "checked floor div negative rhs");\n'
        '    testAssert(condition = !add_overflow.ok && !mul_overflow.ok && !div_zero.ok, msg = "checked rejects invalid");\n'
        '    testAssert(condition = narrowed.ok && narrowed_i64.ok && max_i32.ok && min_i32.ok && trunc_i32_hi.ok && trunc_i32_lo.ok && min_i64.ok, msg = "float convert ok flags");\n'
        '    testAssert(condition = !too_wide.ok && !too_low.ok && !too_wide_i64.ok, msg = "float convert rejects out of range");\n'
        '    testEqualI64(actual = narrowed.value, expected = 42, msg = "f64 to i32");\n'
        '    testEqualI64(actual = narrowed_i64.value, expected = 42, msg = "f64 to i64");\n'
        '    testEqualI64(actual = max_i32.value, expected = 2147483647, msg = "f64 to i32 max");\n'
        '    testEqualI64(actual = min_i32.value, expected = -2147483648, msg = "f64 to i32 min");\n'
        '    testEqualI64(actual = trunc_i32_hi.value, expected = 2147483647, msg = "f64 to i32 trunc high");\n'
        '    testEqualI64(actual = trunc_i32_lo.value, expected = -2147483648, msg = "f64 to i32 trunc low");\n'
        '    testAssert(condition = min_i64.value < 0, msg = "f64 to i64 min");\n'
        '    testAssert(condition = back_to_f64 == 42.0, msg = "i64 to f64");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_random_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/random" import { randomSeed, randomNextU32, randomNextU64, randomRangeI64, randomRangeF64, randomShuffleBytes, randomShuffle, randomEntropy, randomSecureBytes, randomSecureU64 };\n'
        'from "std/collections" import { listLen };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    let source = randomSeed(seed = 42);\n'
        '    let same_seed = randomSeed(seed = 42);\n'
        '    const n32 = randomNextU32(this = source);\n'
        '    const same_n32 = randomNextU32(this = same_seed);\n'
        '    const n64 = randomNextU64(this = source);\n'
        '    const ranged_i = randomRangeI64(this = source, minValue = 10, maxValue = 1);\n'
        '    const ranged_f = randomRangeF64(this = source, minValue = 1.0, maxValue = 0.0);\n'
        '    const shuffled = randomShuffleBytes(this = source, data = Blob(data = "abcd", size = 4));\n'
        '    let nums: List<I32> = [1, 2, 3, 4];\n'
        '    let list_source = randomSeed(seed = 42);\n'
        '    let shuffled_nums: List<I32> = randomShuffle<I32>(this = list_source, list = nums);\n'
        '    const empty_secure = randomSecureBytes(size = 0);\n'
        '    const bad_secure = randomSecureBytes(size = -1);\n'
        '    const secure = randomSecureBytes(size = 8);\n'
        '    const empty_entropy = randomEntropy(size = 0);\n'
        '    const bad_entropy = randomEntropy(size = -1);\n'
        '    const entropy = randomEntropy(size = 8);\n'
        '    const secure64 = randomSecureU64();\n'
        '    testEqualI64(actual = n32, expected = 833678567, msg = "seeded u32 stable");\n'
        '    testEqualI64(actual = same_n32, expected = 833678567, msg = "same seed stable");\n'
        '    testEqualI64(actual = n64, expected = -8068018748417085693, msg = "seeded u64 bits stable");\n'
        '    testEqualI64(actual = ranged_i, expected = 10, msg = "range i64 swaps bounds");\n'
        '    testAssert(condition = ranged_f >= 0.0 && ranged_f < 1.0, msg = "range f64 swaps bounds");\n'
        '    testEqualI64(actual = shuffled.size, expected = 4, msg = "shuffle preserves byte count");\n'
        '    testEqualI64(actual = listLen<I32>(list = nums), expected = 4, msg = "list shuffle keeps original length");\n'
        '    testEqualI64(actual = listLen<I32>(list = shuffled_nums), expected = 4, msg = "list shuffle preserves length");\n'
        '    testEqualI64(actual = nums[1], expected = 2, msg = "list shuffle leaves source list unchanged");\n'
        '    testEqualI64(actual = shuffled_nums[0], expected = 1, msg = "list shuffle item 0");\n'
        '    testEqualI64(actual = shuffled_nums[1], expected = 4, msg = "list shuffle item 1");\n'
        '    testEqualI64(actual = shuffled_nums[2], expected = 2, msg = "list shuffle item 2");\n'
        '    testEqualI64(actual = shuffled_nums[3], expected = 3, msg = "list shuffle item 3");\n'
        '    testAssert(condition = empty_secure.ok && empty_secure.value.size == 0 && !bad_secure.ok, msg = "secure byte edge sizes");\n'
        '    testAssert(condition = secure.ok && secure.value.size == 8, msg = "secure bytes from system entropy");\n'
        '    testAssert(condition = empty_entropy.ok && empty_entropy.value.size == 0 && !bad_entropy.ok, msg = "entropy edge sizes");\n'
        '    testAssert(condition = entropy.ok && entropy.value.size == 8, msg = "entropy from system source");\n'
        '    testAssert(condition = secure64.ok, msg = "secure u64 from system entropy");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_hash_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/hash" import { hashFnv1a32, hashFnv1a64, hashStrFnv1a32, hashStrFnv1a64, hashCombineU64, crc32, crc32Str };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const data = Blob(data = "hello", size = 5);\n'
        '    const digits = Blob(data = "123456789", size = 9);\n'
        '    const empty = Blob(data = "", size = 0);\n'
        '    const h32 = hashFnv1a32(data = data);\n'
        '    const h64 = hashFnv1a64(data = digits);\n'
        '    const sh32 = hashStrFnv1a32(s = "hello");\n'
        '    const sh64 = hashStrFnv1a64(s = "123456789");\n'
        '    const combined = hashCombineU64(seed = h64, value = sh64);\n'
        '    const c1 = crc32(data = data);\n'
        '    const c2 = crc32Str(s = "hello");\n'
        '    const c_empty = crc32(data = empty);\n'
        '    testEqualI64(actual = h32, expected = 1335831723, msg = "fnv1a32 blob hello");\n'
        '    testEqualI64(actual = sh32, expected = 1335831723, msg = "fnv1a32 str hello");\n'
        '    testEqualI64(actual = h64, expected = 492395637191921148, msg = "fnv1a64 blob digits");\n'
        '    testEqualI64(actual = sh64, expected = 492395637191921148, msg = "fnv1a64 str digits");\n'
        '    testAssert(condition = combined != 0, msg = "hash combine returns value");\n'
        '    testEqualI64(actual = c1, expected = 907060870, msg = "crc32 blob hello");\n'
        '    testEqualI64(actual = c2, expected = 907060870, msg = "crc32 str hello");\n'
        '    testEqualI64(actual = c_empty, expected = 0, msg = "crc32 empty");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_platform_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/platform" import { platformOS, platformArch, platformIsLittleEndian, platformPointerBits, platformPageSize, platformCpuCount, platformMemoryLimit, platformHasThreads, platformHasFileSystem, platformHasNetwork, platformHasCrypto, platformHasDom, platformHasSubprocess };\n'
        'from "std/str" import { strEqual };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const os = platformOS();\n'
        '    const arch = platformArch();\n'
        '    const little = platformIsLittleEndian();\n'
        '    const ptr = platformPointerBits();\n'
        '    const page = platformPageSize();\n'
        '    const cpus = platformCpuCount();\n'
        '    const mem = platformMemoryLimit();\n'
        '    const threads = platformHasThreads();\n'
        '    const fs = platformHasFileSystem();\n'
        '    const net = platformHasNetwork();\n'
        '    const crypto = platformHasCrypto();\n'
        '    const dom = platformHasDom();\n'
        '    const proc = platformHasSubprocess();\n'
        f'    testAssert(condition = strEqual(a = os, b = "{ez._native_os()}"), msg = "platform os");\n'
        f'    testAssert(condition = strEqual(a = arch, b = "{ez._native_arch()}"), msg = "platform arch");\n'
        '    testAssert(condition = little, msg = "native little endian");\n'
        '    testEqualI64(actual = ptr, expected = 64, msg = "pointer bits");\n'
        '    testAssert(condition = page > 0 && cpus > 0 && mem != 0, msg = "resource probes");\n'
        '    testAssert(condition = threads && fs && net && crypto && !dom && proc, msg = "native capabilities");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_uri_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/uri" import { UriParts, uriParse, uriBuild, uriNormalize, uriScheme, uriHost, uriPort, uriPath, uriQuery, uriFragment, uriEncodeQuery, uriDecodeQuery, uriEncodePathSegment, uriDecodePathSegment, uriQueryGet, uriQuerySet };\n'
        'const main = (): I32 => {\n'
        '    const url = "https://user@example.com:443/a/../b?q=a%20b#top";\n'
        '    const parts = uriParse(url = url);\n'
        '    const rebuilt = uriBuild(parts = UriParts(scheme = "https", userInfo = "", host = "example.com", port = -1, path = "/b", query = "", fragment = ""));\n'
        '    const normalized = uriNormalize(url = url);\n'
        '    const scheme = uriScheme(url = url);\n'
        '    const host = uriHost(url = url);\n'
        '    const port = uriPort(url = url);\n'
        '    const path = uriPath(url = url);\n'
        '    const query = uriQuery(url = url);\n'
        '    const fragment = uriFragment(url = url);\n'
        '    const encoded = uriEncodeQuery(s = "a b");\n'
        '    const decoded = uriDecodeQuery(s = encoded);\n'
        '    const seg = uriEncodePathSegment(s = "a/b");\n'
        '    const raw = uriDecodePathSegment(s = seg);\n'
        '    const next_query = uriQuerySet(query = "a=1", key = "b", value = "two words");\n'
        '    const value = uriQueryGet(query = next_query, key = "b");\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_uri_query_params_decode_keys_and_values(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/uri" import { uriDecodeQuery, uriQueryGet, uriQuerySet };\n'
        'from "std/test" import { testReset, testAssert, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const first = uriQueryGet(query = "b=two+words&c=3", key = "b");\n'
        '    testAssert(condition = first.ok, msg = "query get first ok");\n'
        '    testEqualStr(actual = first.value, expected = "two words", msg = "query get stops at ampersand");\n'
        '    const replaced = uriQuerySet(query = "a+b=old&x=1", key = "a b", value = "two words");\n'
        '    testEqualStr(actual = replaced, expected = "a+b=two+words&x=1", msg = "query set encoded key");\n'
        '    const roundtrip = uriQueryGet(query = replaced, key = "a b");\n'
        '    testAssert(condition = roundtrip.ok, msg = "query get encoded key ok");\n'
        '    testEqualStr(actual = roundtrip.value, expected = "two words", msg = "query get encoded key value");\n'
        '    const appended = uriQuerySet(query = "", key = "city name", value = "北京");\n'
        '    testEqualStr(actual = appended, expected = "city+name=%E5%8C%97%E4%BA%AC", msg = "query set encodes unicode");\n'
        '    const empty_missing = uriQueryGet(query = "a=1&&b=2&", key = "");\n'
        '    testAssert(condition = !empty_missing.ok, msg = "query get ignores separator empty entries");\n'
        '    const compact_append = uriQuerySet(query = "a=1&&b=2&", key = "c", value = "3");\n'
        '    testEqualStr(actual = compact_append, expected = "a=1&b=2&c=3", msg = "query set drops separator empty entries when appending");\n'
        '    const compact_replace = uriQuerySet(query = "a=1&&b=2&", key = "b", value = "x");\n'
        '    testEqualStr(actual = compact_replace, expected = "a=1&b=x", msg = "query set drops separator empty entries when replacing");\n'
        '    const explicit_empty = uriQueryGet(query = "=empty&a=1", key = "");\n'
        '    testAssert(condition = explicit_empty.ok, msg = "query get explicit empty key ok");\n'
        '    testEqualStr(actual = explicit_empty.value, expected = "empty", msg = "query get explicit empty key value");\n'
        '    const unicode_raw = uriDecodeQuery(s = "城市");\n'
        '    testAssert(condition = unicode_raw.ok, msg = "raw unicode decode ok");\n'
        '    testEqualStr(actual = unicode_raw.value, expected = "城市", msg = "raw unicode decode preserved");\n'
        '    const invalid = uriDecodeQuery(s = "%zz");\n'
        '    testAssert(condition = !invalid.ok, msg = "invalid percent rejected");\n'
        '    const invalid_utf8 = uriDecodeQuery(s = "%FF");\n'
        '    testAssert(condition = !invalid_utf8.ok, msg = "invalid utf8 percent rejected");\n'
        '    const invalid_nul = uriDecodeQuery(s = "%00");\n'
        '    const invalid_query_nul = uriQueryGet(query = "a=%00", key = "a");\n'
        '    testAssert(condition = !invalid_nul.ok && !invalid_query_nul.ok, msg = "nul percent rejected");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_uri_rejects_invalid_ports(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/uri" import { uriParse, uriPort };\n'
        'from "std/test" import { testReset, testAssert, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const valid = uriPort(url = "http://example.com:65535/");\n'
        '    const alpha = uriParse(url = "http://example.com:abc/");\n'
        '    const empty = uriParse(url = "http://example.com:/");\n'
        '    const large = uriParse(url = "http://example.com:65536/");\n'
        '    const ipv6_tail = uriParse(url = "http://[::1]x/");\n'
        '    testAssert(condition = valid.ok && valid.value == 65535, msg = "valid max port");\n'
        '    testAssert(condition = !alpha.ok && !empty.ok && !large.ok && !ipv6_tail.ok, msg = "invalid ports rejected");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_uri_normalize_preserves_empty_authority_and_empty_path(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/uri" import { uriNormalize };\n'
        'from "std/test" import { testReset, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    testEqualStr(actual = uriNormalize(url = "FILE:///tmp/./Ez/../main.ez"), expected = "file:///tmp/main.ez", msg = "empty file authority preserved");\n'
        '    testEqualStr(actual = uriNormalize(url = "foo:"), expected = "foo:", msg = "empty opaque path preserved");\n'
        '    testEqualStr(actual = uriNormalize(url = "foo:?q=1#top"), expected = "foo:?q=1#top", msg = "empty path with query preserved");\n'
        '    testEqualStr(actual = uriNormalize(url = "https://EXAMPLE.com/a/../b"), expected = "https://example.com/b", msg = "authority path normalized");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_debug_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/debug" import { debugPrint, debugAssert, debugLocation, debugRuntimeInfo, debugHex, debugStack };\n'
        'from "std/str" import { strContains, strEqual };\n'
        'from "std/test" import { testReset, testAssert, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    debugPrint(msg = "hello");\n'
        '    debugAssert(condition = true, msg = "ok");\n'
        '    const loc = debugLocation(file = "main.ez", line = 1, column = 2);\n'
        '    const info = debugRuntimeInfo();\n'
        '    const hex = debugHex(data = Blob(data = "ab", size = 2));\n'
        '    const stack = debugStack();\n'
        '    testEqualStr(actual = loc, expected = "main.ez:1:2", msg = "debug location");\n'
        '    testEqualStr(actual = hex, expected = "6162", msg = "debug hex");\n'
        '    testAssert(condition = strContains(s = info, needle = "ezlang native"), msg = "runtime info");\n'
        '    stack.ok ? { testAssert(condition = stack.value != "", msg = "stack text"); };\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_log_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    log_path = (tmp_path / "runtime.log").as_posix()
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/log" import { logTrace, logDebug, logInfo, logWarn, logError, logTargetStderr, logTargetFile, LogConfig, logDefaultConfig, logConfigure, logSetLevel, logSetFile, logWrite, logWriteFields, logWriteAt, logInfoMsg, logWarnMsg, logErrorMsg };\n'
        'const main = (): I32 => {\n'
        '    const cfg = logDefaultConfig();\n'
        '    logConfigure(config = LogConfig(minLevel = logDebug, target = logTargetStderr, includeTimestamp = true, includeLocation = true));\n'
        '    logSetLevel(level = logTrace);\n'
        f'    const file_ok = logSetFile(path = "{log_path}");\n'
        '    logConfigure(config = LogConfig(minLevel = logTrace, target = logTargetFile, includeTimestamp = false, includeLocation = true));\n'
        '    logWrite(level = logInfo, msg = "hello");\n'
        '    logWriteFields(level = logWarn, msg = "warn", fields = ["key", "value"]);\n'
        '    logWriteAt(level = logError, msg = "err", file = "main.ez", line = 1, column = 2, fields = ["code", "1"]);\n'
        '    logInfoMsg(msg = "info");\n'
        '    logWarnMsg(msg = "warn");\n'
        '    logErrorMsg(msg = "error");\n'
        '    return file_ok ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    text = (tmp_path / "runtime.log").read_text(encoding="utf-8")
    assert "INFO hello" in text
    assert "WARN warn key=value" in text
    assert "ERROR err @ main.ez:1:2 code=1" in text


def test_run_links_std_regex_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/regex" import { regexIgnoreCase, regexCompile, regexIsValid, regexTest, regexFind, regexFindAll, regexReplace, regexSplit };\n'
        'const main = (): I32 => {\n'
        '    const re = regexCompile(pattern = "([a-z]+)", flags = regexIgnoreCase);\n'
        '    const valid = regexIsValid(regex = re);\n'
        '    const matched = regexTest(regex = re, input = "Hello 42");\n'
        '    const found = regexFind(regex = re, input = "Hello 42");\n'
        '    const all = regexFindAll(regex = re, input = "a b c");\n'
        '    const replaced = regexReplace(regex = re, input = "abc", replacement = "x");\n'
        '    const parts = regexSplit(regex = re, input = "a,b,c");\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_regex_matches_and_global_replace(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/regex" import { regexGlobal, regexMultiline, regexCompile, regexIsValid, regexTest, regexFind, regexFindAll, regexReplace, regexSplit };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const word = regexCompile(pattern = "([[:alpha:]]+)", flags = 0);\n'
        '    testAssert(condition = regexIsValid(regex = word), msg = "regex valid");\n'
        '    testAssert(condition = regexTest(regex = word, input = "EzLang 42"), msg = "regex test");\n'
        '    const found = regexFind(regex = word, input = "EzLang 42");\n'
        '    testAssert(condition = found.ok, msg = "regex find ok");\n'
        '    testEqualStr(actual = found.value.text, expected = "EzLang", msg = "regex find text");\n'
        '    testEqualI64(actual = found.value.start, expected = 0, msg = "regex find start");\n'
        '    testEqualI64(actual = found.value.end, expected = 6, msg = "regex find end");\n'
        '    testEqualStr(actual = found.value.groups[0], expected = "EzLang", msg = "regex capture group");\n'
        '    const utf = regexFind(regex = regexCompile(pattern = "(Ez)", flags = 0), input = "中Ez");\n'
        '    testAssert(condition = utf.ok, msg = "regex utf find ok");\n'
        '    testEqualI64(actual = utf.value.start, expected = 3, msg = "regex utf byte start");\n'
        '    testEqualI64(actual = utf.value.end, expected = 5, msg = "regex utf byte end");\n'
        '    testEqualStr(actual = utf.value.groups[0], expected = "Ez", msg = "regex utf capture group");\n'
        '    const all = regexFindAll(regex = word, input = "one two three");\n'
        '    testEqualI64(actual = all.length, expected = 3, msg = "regex find all length");\n'
        '    testEqualStr(actual = all[2], expected = "three", msg = "regex find all value");\n'
        '    const first_only = regexReplace(regex = regexCompile(pattern = "[[:digit:]]", flags = 0), input = "a1b2c3", replacement = "#");\n'
        '    testEqualStr(actual = first_only, expected = "a#b2c3", msg = "regex replace first");\n'
        '    const literal = regexReplace(regex = regexCompile(pattern = "([A-Z]+)", flags = 0), input = "ABC DEF", replacement = "$1");\n'
        '    testEqualStr(actual = literal, expected = "$1 DEF", msg = "regex replacement literal");\n'
        '    const line_start = regexCompile(pattern = "^b", flags = regexMultiline);\n'
        '    testAssert(condition = regexTest(regex = line_start, input = "a\\nb"), msg = "regex multiline anchor matches line start");\n'
        '    const string_start = regexCompile(pattern = "^b", flags = 0);\n'
        '    testAssert(condition = !regexTest(regex = string_start, input = "a\\nb"), msg = "regex non-multiline anchor only matches string start");\n'
        '    const dot = regexCompile(pattern = "a.b", flags = 0);\n'
        '    testAssert(condition = regexTest(regex = dot, input = "a b") && !regexTest(regex = dot, input = "a\\nb"), msg = "regex dot does not match newline");\n'
        '    const all_digits = regexReplace(regex = regexCompile(pattern = "[[:digit:]]", flags = regexGlobal), input = "a1b2c3", replacement = "#");\n'
        '    testEqualStr(actual = all_digits, expected = "a#b#c#", msg = "regex replace global");\n'
        '    const exact_repeat = regexCompile(pattern = "ab{2}c", flags = 0);\n'
        '    testAssert(condition = regexIsValid(regex = exact_repeat), msg = "regex exact interval valid");\n'
        '    testAssert(condition = regexTest(regex = exact_repeat, input = "abbc") && !regexTest(regex = exact_repeat, input = "abc"), msg = "regex exact interval match");\n'
        '    const ranged_repeat = regexCompile(pattern = "ab{2,4}c", flags = 0);\n'
        '    testAssert(condition = regexIsValid(regex = ranged_repeat), msg = "regex ranged interval valid");\n'
        '    testAssert(condition = regexTest(regex = ranged_repeat, input = "abbc") && regexTest(regex = ranged_repeat, input = "abbbbc") && !regexTest(regex = ranged_repeat, input = "abbbbbc"), msg = "regex ranged interval match");\n'
        '    const open_repeat = regexCompile(pattern = "ab{2,}c", flags = 0);\n'
        '    testAssert(condition = regexIsValid(regex = open_repeat), msg = "regex open interval valid");\n'
        '    testAssert(condition = regexTest(regex = open_repeat, input = "abbc") && regexTest(regex = open_repeat, input = "abbbbbc") && !regexTest(regex = open_repeat, input = "abc"), msg = "regex open interval match");\n'
        '    const repeat_group = regexFind(regex = regexCompile(pattern = "(ab){2,3}", flags = 0), input = "zababx");\n'
        '    testAssert(condition = repeat_group.ok, msg = "regex interval group match");\n'
        '    testEqualStr(actual = repeat_group.value.text, expected = "abab", msg = "regex interval group text");\n'
        '    testEqualStr(actual = repeat_group.value.groups[0], expected = "ab", msg = "regex interval group capture");\n'
        '    const invalid_repeat = regexCompile(pattern = "ab{4,2}c", flags = 0);\n'
        '    testAssert(condition = !regexIsValid(regex = invalid_repeat), msg = "regex invalid interval rejected");\n'
        '    const parts = regexSplit(regex = regexCompile(pattern = ",", flags = regexGlobal), input = "a,b,c");\n'
        '    testEqualI64(actual = parts.length, expected = 3, msg = "regex split length");\n'
        '    testEqualStr(actual = parts[1], expected = "b", msg = "regex split middle");\n'
        '    const captured_parts = regexSplit(regex = regexCompile(pattern = "([,])", flags = regexGlobal), input = "a,b,c");\n'
        '    testEqualI64(actual = captured_parts.length, expected = 3, msg = "regex split ignores captured separators");\n'
        '    testEqualStr(actual = captured_parts[1], expected = "b", msg = "regex split captured middle");\n'
        '    const invalid = regexCompile(pattern = "(", flags = 0);\n'
        '    testAssert(condition = !regexIsValid(regex = invalid), msg = "invalid regex rejected");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_regex_global_zero_width_replace_preserves_input(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/regex" import { regexGlobal, regexCompile, regexReplace };\n'
        'from "std/test" import { testReset, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const boundary = regexCompile(pattern = "(^|$)", flags = regexGlobal);\n'
        '    const out = regexReplace(regex = boundary, input = "ab", replacement = "|");\n'
        '    testEqualStr(actual = out, expected = "|ab|", msg = "zero-width global replace preserves input");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_regex_find_all_zero_width_anchors_once(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/collections" import { listLen };\n'
        'from "std/regex" import { regexCompile, regexFindAll };\n'
        'from "std/test" import { testReset, testEqualI64, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const boundary = regexCompile(pattern = "^", flags = 0);\n'
        '    const found = regexFindAll(regex = boundary, input = "abc");\n'
        '    testEqualI64(actual = listLen<Str>(list = found), expected = 1, msg = "find all start anchor once");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_regex_find_all_zero_width_empty_input_once(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/collections" import { listLen };\n'
        'from "std/regex" import { regexCompile, regexFindAll };\n'
        'from "std/test" import { testReset, testEqualI64, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const starts = regexFindAll(regex = regexCompile(pattern = "^", flags = 0), input = "");\n'
        '    const ends = regexFindAll(regex = regexCompile(pattern = "$", flags = 0), input = "");\n'
        '    testEqualI64(actual = listLen<Str>(list = starts), expected = 1, msg = "find all start anchor on empty input once");\n'
        '    testEqualI64(actual = listLen<Str>(list = ends), expected = 1, msg = "find all end anchor on empty input once");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_regex_split_anchors_and_utf8_zero_width(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/collections" import { listLen };\n'
        'from "std/regex" import { regexCompile, regexSplit };\n'
        'from "std/test" import { testReset, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const anchored = regexSplit(regex = regexCompile(pattern = "^", flags = 0), input = "abc");\n'
        '    testEqualI64(actual = listLen<Str>(list = anchored), expected = 2, msg = "split start anchor only at input start");\n'
        '    testEqualStr(actual = anchored[0], expected = "", msg = "split start anchor prefix");\n'
        '    testEqualStr(actual = anchored[1], expected = "bc", msg = "split start anchor suffix after zero-width progress");\n'
        '    const utf = regexSplit(regex = regexCompile(pattern = "^", flags = 0), input = "中a");\n'
        '    testEqualI64(actual = listLen<Str>(list = utf), expected = 2, msg = "split start anchor advances by UTF-8 scalar");\n'
        '    testEqualStr(actual = utf[1], expected = "a", msg = "split start anchor skips one UTF-8 scalar");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_regex_respects_invalid_regex_flag(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/collections" import { listLen };\n'
        'from "std/regex" import { Regex, regexIsValid, regexTest, regexFind, regexFindAll, regexReplace, regexSplit };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const invalid = Regex(pattern = "a", flags = 0, ok = false);\n'
        '    const found = regexFind(regex = invalid, input = "a");\n'
        '    const all = regexFindAll(regex = invalid, input = "a");\n'
        '    const replaced = regexReplace(regex = invalid, input = "a", replacement = "x");\n'
        '    const parts = regexSplit(regex = invalid, input = "a");\n'
        '    testAssert(condition = !regexIsValid(regex = invalid), msg = "invalid regex flag stays invalid");\n'
        '    testAssert(condition = !regexTest(regex = invalid, input = "a") && !found.ok, msg = "invalid regex does not match");\n'
        '    testEqualI64(actual = listLen<Str>(list = all), expected = 0, msg = "invalid regex find all empty");\n'
        '    testEqualStr(actual = replaced, expected = "a", msg = "invalid regex replace returns input");\n'
        '    testEqualI64(actual = listLen<Str>(list = parts), expected = 1, msg = "invalid regex split returns input list");\n'
        '    testEqualStr(actual = parts[0], expected = "a", msg = "invalid regex split input value");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_global_const_initializer_values(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/regex" import { regexGlobal };\n'
        'const localFlag: I32 = 4;\n'
        'const wideFlag: I64 = 9;\n'
        'const enabled: Bool = true;\n'
        'const main = (): I32 => {\n'
        '    return localFlag == 4 ? (wideFlag == 9 ? (enabled ? (regexGlobal == 4 ? 0 : 4) : 3) : 2) : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_crypto_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    crypto_expectations = (
        '    testAssert(condition = sha256.ok && sha512.ok && h256.ok && h512.ok, msg = "crypto available");\n'
        '    testEqualStr(actual = debugHex(data = sha256.value), expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824", msg = "sha256 vector");\n'
        '    testEqualStr(actual = debugHex(data = sha512.value), expected = "9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043", msg = "sha512 vector");\n'
        '    testEqualStr(actual = debugHex(data = h256.value), expected = "9307b3b915efb5171ff14d8cb55fbcc798c6c0ef1456d66ded1a6aa723a58b7b", msg = "hmac sha256 vector");\n'
        '    testEqualStr(actual = debugHex(data = h512.value), expected = "ff06ab36757777815c008d32c8e14a705b4e7bf310351a06a23b612dc4c7433e7757d20525a5593b71020ea2ee162d2311b247e9855862b270122419652c0c92", msg = "hmac sha512 vector");\n'
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/crypto" import { cryptoSha256, cryptoSha512, cryptoHmacSha256, cryptoHmacSha512 };\n'
        'from "std/debug" import { debugHex };\n'
        'from "std/test" import { testReset, testAssert, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const data = Blob(data = "hello", size = 5);\n'
        '    const key = Blob(data = "key", size = 3);\n'
        '    const sha256 = cryptoSha256(data = data);\n'
        '    const sha512 = cryptoSha512(data = data);\n'
        '    const h256 = cryptoHmacSha256(key = key, data = data);\n'
        '    const h512 = cryptoHmacSha512(key = key, data = data);\n'
        + crypto_expectations +
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_compress_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/compress" import { compressGzip, decompressGzip, compressZlib, decompressZlib, compressDeflate, decompressDeflate };\n'
        'const main = (): I32 => {\n'
        '    const data = Blob(data = "hello", size = 5);\n'
        '    const gz = compressGzip(data = data);\n'
        '    const raw_gz = decompressGzip(data = gz.value);\n'
        '    const z = compressZlib(data = data);\n'
        '    const raw_z = decompressZlib(data = z.value);\n'
        '    const d = compressDeflate(data = data);\n'
        '    const raw_d = decompressDeflate(data = d.value);\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_test_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/test" import { testReset, testAssert, testEqualI64, testNotEqualI64, testEqualStr, testSkip, testThrows, testRegister, testRegisterParam, testCount, testName, testPassed, testFailed, testSkipped };\n'
        'const fail = (): Void => { throw Error(code = 5, message = "boom"); };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    testRegister(name = "basic");\n'
        '    testRegisterParam(name = "table", param = "one");\n'
        '    testAssert(condition = true, msg = "truth");\n'
        '    testEqualI64(actual = 42, expected = 42, msg = "i64");\n'
        '    testNotEqualI64(actual = 1, expected = 2, msg = "neq");\n'
        '    testEqualStr(actual = "ez", expected = "ez", msg = "str");\n'
        '    testThrows(body = fail, expectedCode = 5, msg = "throws");\n'
        '    testEqualStr(actual = testName(index = 1), expected = "table[one]", msg = "param name");\n'
        '    testSkip(msg = "later");\n'
        '    return testFailed() + (testPassed() == 6 ? 0 : 10) + (testSkipped() == 1 ? 0 : 20) + (testCount() == 2 ? 0 : 30);\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_ez_test_reports_runtime_failure_with_test_name(tmp_path, capsys):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "failing_test.ez").write_text(
        'from "std/test" import { testRegister, testEqualI64 };\n'
        'const main = (): I32 => {\n'
        '    testRegister(name = "bad_case");\n'
        '    testEqualI64(actual = 1, expected = 2, msg = "mismatch");\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["test", "--project", str(project_toml)]) == 1
    captured = capsys.readouterr()
    assert "fail tests/failing_test.ez" in captured.err
    assert "test failed: tests/failing_test.ez:3 bad_case: mismatch: expected 2, got 1" in captured.err


def test_run_std_compress_roundtrip_and_invalid_inputs(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/compress" import { compressGzip, decompressGzip, compressZlib, decompressZlib, compressDeflate, decompressDeflate, compressGzipStream, decompressGzipStream, compressZlibStream, decompressZlibStream, compressDeflateStream, decompressDeflateStream };\n'
        'from "std/stream" import { streamFromBlob, streamToBlob, streamClose };\n'
        'from "std/str" import { strFromBytes };\n'
        'from "std/test" import { testReset, testAssert, testEqualStr, testFailed };\n'
        'const assertText = (data: Blob, expected: Str, label: Str): Void => {\n'
        '    const text = strFromBytes(data = data);\n'
        '    testAssert(condition = text.ok, msg = label);\n'
        '    testEqualStr(actual = text.value, expected = expected, msg = label);\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const plain = Blob(data = "hello hello hello", size = 17);\n'
        '    const gz = compressGzip(data = plain);\n'
        '    testAssert(condition = gz.ok, msg = "gzip compress ok");\n'
        '    const raw_gz = decompressGzip(data = gz.value);\n'
        '    testAssert(condition = raw_gz.ok, msg = "gzip decompress ok");\n'
        '    assertText(data = raw_gz.value, expected = "hello hello hello", label = "gzip roundtrip");\n'
        '    const z = compressZlib(data = plain);\n'
        '    testAssert(condition = z.ok, msg = "zlib compress ok");\n'
        '    const raw_z = decompressZlib(data = z.value);\n'
        '    testAssert(condition = raw_z.ok, msg = "zlib decompress ok");\n'
        '    assertText(data = raw_z.value, expected = "hello hello hello", label = "zlib roundtrip");\n'
        '    const d = compressDeflate(data = plain);\n'
        '    testAssert(condition = d.ok, msg = "deflate compress ok");\n'
        '    const raw_d = decompressDeflate(data = d.value);\n'
        '    testAssert(condition = raw_d.ok, msg = "deflate decompress ok");\n'
        '    assertText(data = raw_d.value, expected = "hello hello hello", label = "deflate roundtrip");\n'
        '    const stream_src = streamFromBlob(data = plain);\n'
        '    const compressed_dst = streamFromBlob(data = Blob(data = "", size = 0));\n'
        '    const streamed = compressGzipStream(dst = compressed_dst.value, src = stream_src.value, bufferSize = 3);\n'
        '    testAssert(condition = streamed > 0, msg = "gzip stream compress ok");\n'
        '    const compressed_blob = streamToBlob(stream = compressed_dst.value);\n'
        '    const compressed_src = streamFromBlob(data = compressed_blob.value);\n'
        '    const restored_dst = streamFromBlob(data = Blob(data = "", size = 0));\n'
        '    const restored = decompressGzipStream(dst = restored_dst.value, src = compressed_src.value, bufferSize = 2);\n'
        '    testAssert(condition = restored == 17, msg = "gzip stream decompress ok");\n'
        '    const restored_blob = streamToBlob(stream = restored_dst.value);\n'
        '    assertText(data = restored_blob.value, expected = "hello hello hello", label = "gzip stream roundtrip");\n'
        '    const z_src = streamFromBlob(data = plain);\n'
        '    const z_dst = streamFromBlob(data = Blob(data = "", size = 0));\n'
        '    const z_streamed = compressZlibStream(dst = z_dst.value, src = z_src.value, bufferSize = 3);\n'
        '    testAssert(condition = z_streamed > 0, msg = "zlib stream compress ok");\n'
        '    const z_blob = streamToBlob(stream = z_dst.value);\n'
        '    const z_compressed_src = streamFromBlob(data = z_blob.value);\n'
        '    const z_restored_dst = streamFromBlob(data = Blob(data = "", size = 0));\n'
        '    const z_restored = decompressZlibStream(dst = z_restored_dst.value, src = z_compressed_src.value, bufferSize = 2);\n'
        '    testAssert(condition = z_restored == 17, msg = "zlib stream decompress ok");\n'
        '    const z_restored_blob = streamToBlob(stream = z_restored_dst.value);\n'
        '    assertText(data = z_restored_blob.value, expected = "hello hello hello", label = "zlib stream roundtrip");\n'
        '    const d_src = streamFromBlob(data = plain);\n'
        '    const d_dst = streamFromBlob(data = Blob(data = "", size = 0));\n'
        '    const d_streamed = compressDeflateStream(dst = d_dst.value, src = d_src.value, bufferSize = 3);\n'
        '    testAssert(condition = d_streamed > 0, msg = "deflate stream compress ok");\n'
        '    const d_blob = streamToBlob(stream = d_dst.value);\n'
        '    const d_compressed_src = streamFromBlob(data = d_blob.value);\n'
        '    const d_restored_dst = streamFromBlob(data = Blob(data = "", size = 0));\n'
        '    const d_restored = decompressDeflateStream(dst = d_restored_dst.value, src = d_compressed_src.value, bufferSize = 2);\n'
        '    testAssert(condition = d_restored == 17, msg = "deflate stream decompress ok");\n'
        '    const d_restored_blob = streamToBlob(stream = d_restored_dst.value);\n'
        '    assertText(data = d_restored_blob.value, expected = "hello hello hello", label = "deflate stream roundtrip");\n'
        '    streamClose(stream = stream_src.value);\n'
        '    streamClose(stream = compressed_dst.value);\n'
        '    streamClose(stream = compressed_src.value);\n'
        '    streamClose(stream = restored_dst.value);\n'
        '    streamClose(stream = z_src.value);\n'
        '    streamClose(stream = z_dst.value);\n'
        '    streamClose(stream = z_compressed_src.value);\n'
        '    streamClose(stream = z_restored_dst.value);\n'
        '    streamClose(stream = d_src.value);\n'
        '    streamClose(stream = d_dst.value);\n'
        '    streamClose(stream = d_compressed_src.value);\n'
        '    streamClose(stream = d_restored_dst.value);\n'
        '    const invalid = Blob(data = "not gzip", size = 8);\n'
        '    const bad_gz = decompressGzip(data = invalid);\n'
        '    const bad_z = decompressZlib(data = invalid);\n'
        '    const bad_d = decompressDeflate(data = invalid);\n'
        '    testAssert(condition = !bad_gz.ok && !bad_z.ok && !bad_d.ok, msg = "invalid compressed data rejected");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_stream_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/stream" import { streamFromBlob, streamRead, streamWrite, streamToBlob, streamCopy, streamFlush, streamClose };\n'
        'const main = (): I32 => {\n'
        '    const src = streamFromBlob(data = Blob(data = "hello", size = 5));\n'
        '    const dst = streamFromBlob(data = Blob(data = "", size = 0));\n'
        '    const first = streamRead(stream = src.value, maxBytes = 2);\n'
        '    const written = streamWrite(stream = dst.value, data = first.value);\n'
        '    const copied = streamCopy(dst = dst.value, src = src.value, bufferSize = 4);\n'
        '    const out = streamToBlob(stream = dst.value);\n'
        '    const flushed = streamFlush(stream = dst.value);\n'
        '    const closed = streamClose(stream = dst.value);\n'
        '    return (written == 2 && copied == 3 && out.value.size == 5 && flushed && closed) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_stream_rejects_invalid_blob_inputs(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/stream" import { streamFromBlob, streamWrite, streamClose };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const invalid = Blob(data = "", size = -1);\n'
        '    const empty = Blob(data = "", size = 0);\n'
        '    const bad_source = streamFromBlob(data = invalid);\n'
        '    const good_source = streamFromBlob(data = empty);\n'
        '    testAssert(condition = !bad_source.ok, msg = "invalid blob stream rejected");\n'
        '    testAssert(condition = good_source.ok, msg = "empty blob stream accepted");\n'
        '    const wrote_bad = streamWrite(stream = good_source.value, data = invalid);\n'
        '    const wrote_empty = streamWrite(stream = good_source.value, data = empty);\n'
        '    testEqualI64(actual = wrote_bad, expected = -1, msg = "invalid blob write rejected");\n'
        '    testEqualI64(actual = wrote_empty, expected = 0, msg = "empty blob write succeeds with zero bytes");\n'
        '    const closed = streamClose(stream = good_source.value);\n'
        '    testAssert(condition = closed, msg = "empty stream closed");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_stream_file_copy_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    input_path = tmp_path / "stream-input.txt"
    output_path = tmp_path / "stream-output.txt"
    input_path.write_text("hello stream file", encoding="utf-8")
    input_text = str(input_path).replace('\\', '\\\\').replace('"', '\\"')
    output_text = str(output_path).replace('\\', '\\\\').replace('"', '\\"')
    (tmp_path / "src" / "index.ez").write_text(
        f'''
from "std/stream" import {{ streamFromBlob, streamOpenFileRead, streamOpenFileWrite, streamCopy, streamToBlob, streamClose, streamFlush }};
from "std/str" import {{ strFromBytes, strEqual }};

const main = (): I32 => {{
    const inputPath = "{input_text}";
    const outputPath = "{output_text}";
    const src = streamOpenFileRead(path = inputPath);
    const memory = streamFromBlob(data = Blob(data = "", size = 0));
    const copiedToMemory = streamCopy(dst = memory.value, src = src.value, bufferSize = 5);
    const data = streamToBlob(stream = memory.value);
    const text = strFromBytes(data = data.value);
    const closedSrc = streamClose(stream = src.value);
    const closedMemory = streamClose(stream = memory.value);
    const src2 = streamOpenFileRead(path = inputPath);
    const dst = streamOpenFileWrite(path = outputPath);
    const copiedToFile = streamCopy(dst = dst.value, src = src2.value, bufferSize = 4);
    const flushed = streamFlush(stream = dst.value);
    const closedSrc2 = streamClose(stream = src2.value);
    const closedDst = streamClose(stream = dst.value);
    return (src.ok && memory.ok && data.ok && text.ok && copiedToMemory == 17 && strEqual(a = text.value, b = "hello stream file") && closedSrc && closedMemory && src2.ok && dst.ok && copiedToFile == 17 && flushed && closedSrc2 && closedDst) ? 0 : 1;
}};
''',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    assert output_path.read_text(encoding="utf-8") == "hello stream file"


def test_run_std_net_native_wrappers_report_unsupported_without_success(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/http" import { fetch, createServer };\n'
        'from "std/net/tcp" import { tcpConnect, tcpListen, udpBind };\n'
        'from "std/net/ws" import { wsConnect };\n'
        'const main = (): I32 => {\n'
        '    const resp = fetch(url = "http://127.0.0.1:65536/");\n'
        '    const server = createServer(host = "127.0.0.1", port = 65536);\n'
        '    const tcp = tcpConnect(host = "127.0.0.1", port = 65536);\n'
        '    const listener = tcpListen(host = "127.0.0.1", port = 65536);\n'
        '    const udp = udpBind(host = "127.0.0.1", port = 65536);\n'
        '    const ws = wsConnect(url = "ws://127.0.0.1:65536/");\n'
        '    return (!resp.ok && server.handle == 0 && !tcp.ok && !listener.ok && !udp.ok && !ws.ok) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_net_http_fetch_plain_http_success(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        project_toml = write_project(
            tmp_path,
            os_name=ez._native_os(),
            arch=ez._native_arch(),
        )
        port = server.server_address[1]
        (tmp_path / "src" / "index.ez").write_text(
            'from "std/net/http" import { fetch };\n'
            'from "std/test" import { testReset, testEqualStr, testFailed };\n'
            'const main = (): I32 => {\n'
            '    testReset();\n'
            f'    const resp = fetch(url = "http://127.0.0.1:{port}/hello");\n'
            '    resp.ok ? { testEqualStr(actual = resp.value.text(), expected = "ok", msg = "http response text"); };\n'
            '    return (resp.ok && resp.value.status == 200 && resp.value.body.size == 2) ? testFailed() : 1;\n'
            '};\n',
            encoding="utf-8",
        )

        assert ez.main(["run", "--project", str(project_toml)]) == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_run_std_net_http_response_text_rejects_nul_and_invalid_utf8(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/nul":
                body = b"a\0b"
            elif self.path == "/invalid":
                body = b"\xff"
            else:
                body = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        project_toml = write_project(
            tmp_path,
            os_name=ez._native_os(),
            arch=ez._native_arch(),
        )
        port = server.server_address[1]
        (tmp_path / "src" / "index.ez").write_text(
            'from "std/net/http" import { fetch };\n'
            'from "std/test" import { testReset, testEqualStr, testFailed };\n'
            'const main = (): I32 => {\n'
            '    testReset();\n'
            f'    const nul = fetch(url = "http://127.0.0.1:{port}/nul");\n'
            f'    const invalid = fetch(url = "http://127.0.0.1:{port}/invalid");\n'
            '    nul.ok ? { testEqualStr(actual = nul.value.text(), expected = "", msg = "nul response text"); };\n'
            '    invalid.ok ? { testEqualStr(actual = invalid.value.text(), expected = "", msg = "invalid utf8 response text"); };\n'
            '    return (nul.ok && invalid.ok && nul.value.body.size == 3 && invalid.value.body.size == 1) ? testFailed() : 1;\n'
            '};\n',
            encoding="utf-8",
        )

        assert ez.main(["run", "--project", str(project_toml)]) == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_run_std_net_http_fetch_preserves_root_query_and_strips_fragment(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/?q=ez":
                self.send_response(400)
                self.end_headers()
                self.wfile.write(self.path.encode("utf-8"))
                return
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        project_toml = write_project(
            tmp_path,
            os_name=ez._native_os(),
            arch=ez._native_arch(),
        )
        port = server.server_address[1]
        (tmp_path / "src" / "index.ez").write_text(
            'from "std/net/http" import { fetch };\n'
            'from "std/test" import { testReset, testEqualStr, testFailed };\n'
            'const main = (): I32 => {\n'
            '    testReset();\n'
            f'    const resp = fetch(url = "http://127.0.0.1:{port}?q=ez#fragment");\n'
            '    resp.ok ? { testEqualStr(actual = resp.value.text(), expected = "ok", msg = "http query response text"); };\n'
            '    return (resp.ok && resp.value.status == 200) ? testFailed() : 1;\n'
            '};\n',
            encoding="utf-8",
        )

        assert ez.main(["run", "--project", str(project_toml)]) == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_run_std_net_http_fetch_validates_authority_and_host_header(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            expected_host = f"127.0.0.1:{self.server.server_address[1]}"
            if self.path != "/hello?q=ez" or self.headers.get("Host") != expected_host:
                self.send_response(400)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        project_toml = write_project(
            tmp_path,
            os_name=ez._native_os(),
            arch=ez._native_arch(),
        )
        port = server.server_address[1]
        (tmp_path / "src" / "index.ez").write_text(
            'from "std/net/http" import { fetch };\n'
            'from "std/test" import { testReset, testEqualStr, testAssert, testFailed };\n'
            'const main = (): I32 => {\n'
            '    testReset();\n'
            f'    const good = fetch(url = "http://user:pass@127.0.0.1:{port}/hello?q=ez#fragment");\n'
            '    const alphaPort = fetch(url = "http://127.0.0.1:abc/");\n'
            '    const emptyPort = fetch(url = "http://127.0.0.1:/");\n'
            '    const largePort = fetch(url = "http://127.0.0.1:65536/");\n'
            '    good.ok ? { testEqualStr(actual = good.value.text(), expected = "ok", msg = "userinfo fetch body"); };\n'
            '    testAssert(condition = good.ok && good.value.status == 200, msg = "userinfo authority accepted");\n'
            '    testAssert(condition = !alphaPort.ok && !emptyPort.ok && !largePort.ok, msg = "invalid http ports rejected");\n'
            '    return testFailed();\n'
            '};\n',
            encoding="utf-8",
        )

        assert ez.main(["run", "--project", str(project_toml)]) == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_run_std_net_http_fetch_ipv6_literal(tmp_path):
    class V6ThreadingHTTPServer(ThreadingHTTPServer):
        address_family = socket.AF_INET6

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            expected_host = f"[::1]:{self.server.server_address[1]}"
            if self.path != "/v6" or self.headers.get("Host") != expected_host:
                self.send_response(400)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = b"v6"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    try:
        server = V6ThreadingHTTPServer(("::1", 0), Handler)
    except OSError as exc:
        pytest.skip(f"当前环境不支持 IPv6 loopback: {exc}")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        project_toml = write_project(
            tmp_path,
            os_name=ez._native_os(),
            arch=ez._native_arch(),
        )
        port = server.server_address[1]
        (tmp_path / "src" / "index.ez").write_text(
            'from "std/net/http" import { fetch };\n'
            'from "std/test" import { testReset, testEqualStr, testAssert, testFailed };\n'
            'const main = (): I32 => {\n'
            '    testReset();\n'
            f'    const resp = fetch(url = "http://[::1]:{port}/v6");\n'
            '    resp.ok ? { testEqualStr(actual = resp.value.text(), expected = "v6", msg = "ipv6 response body"); };\n'
            '    testAssert(condition = resp.ok && resp.value.status == 200, msg = "ipv6 literal fetch");\n'
            '    return testFailed();\n'
            '};\n',
            encoding="utf-8",
        )

        assert ez.main(["run", "--project", str(project_toml)]) == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_run_std_net_http_fetch_ex_headers_roundtrip(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.headers.get("X-Ez") != "ping" or body != b"data":
                self.send_response(400)
                self.end_headers()
                return
            self.send_response(201)
            self.send_header("X-Ez", "pong")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        project_toml = write_project(
            tmp_path,
            os_name=ez._native_os(),
            arch=ez._native_arch(),
        )
        port = server.server_address[1]
        (tmp_path / "src" / "index.ez").write_text(
            'from "std/net/http" import { Headers, HttpRequest, fetchEx };\n'
            'from "std/test" import { testReset, testEqualStr, testFailed };\n'
            'const main = (): I32 => {\n'
            '    testReset();\n'
            '    let headers: Headers = { "X-Ez" = "ping" };\n'
            f'    let req = HttpRequest(method = "POST", url = "http://127.0.0.1:{port}/headers", headers = headers, body = Blob(data = "data", size = 4));\n'
            '    const resp = fetchEx(req = req);\n'
            '    resp.ok ? { testEqualStr(actual = resp.value.headers["X-Ez"], expected = "pong", msg = "http response header"); };\n'
            '    resp.ok ? { testEqualStr(actual = resp.value.text(), expected = "ok", msg = "http response body"); };\n'
            '    return (resp.ok && resp.value.status == 201) ? testFailed() : 1;\n'
            '};\n',
            encoding="utf-8",
        )

        assert ez.main(["run", "--project", str(project_toml)]) == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_run_std_net_http_fetch_decodes_chunked_response(tmp_path):
    ready = threading.Event()
    port_holder = []

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port_holder.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                conn.settimeout(5)
                conn.recv(2048)
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Transfer-Encoding: chunked\r\n"
                    b"X-Ez: chunked\r\n"
                    b"\r\n"
                    b"2\r\nok\r\n"
                    b"6;ignored=true\r\n chunk\r\n"
                    b"0\r\n\r\n"
                )

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/http" import { fetch };\n'
        'from "std/test" import { testReset, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        f'    const resp = fetch(url = "http://127.0.0.1:{port}/chunked");\n'
        '    resp.ok ? { testEqualStr(actual = resp.value.headers["Transfer-Encoding"], expected = "chunked", msg = "chunked response header"); };\n'
        '    resp.ok ? { testEqualStr(actual = resp.value.text(), expected = "ok chunk", msg = "chunked response body"); };\n'
        '    return (resp.ok && resp.value.status == 200 && resp.value.body.size == 8) ? testFailed() : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    thread.join(timeout=2)


def test_run_std_net_http_server_handles_basic_route(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    source = f'''
from "std/net/http" import {{ createServer, HttpRequest, HttpResponse }};
from "std/str" import {{ strEqual }};

let server = createServer(host = "127.0.0.1", port = {port});
const handler = (req: HttpRequest): HttpResponse => {{
    const body = req.body;
    const status = !strEqual(a = req.method, b = "POST") ? 410 : (!strEqual(a = req.url, b = "/hello?name=ez") ? 411 : (!body.ok ? 412 : (body.value.size != 4 ? 412 : (!strEqual(a = req.headers["X-Ez"], b = "ping") ? 413 : 201))));
    server.stop();
    return HttpResponse(status = status, headers = {{ "X-Ez": Str = "pong" }}, body = Blob(data = "ok", size = 2));
}};
server.on(path = "/hello", handler = handler);
server.start();
'''
    (tmp_path / "src" / "index.ez").write_text(source, encoding="utf-8")

    result = {}

    def run_server():
        result["code"] = ez.main(["run", "--project", str(project_toml)])

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    deadline = time.time() + 10
    response = b""
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2) as client:
                client.sendall(
                    b"POST /hello?name=ez HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"X-Ez: ping\r\n"
                    b"Content-Length: 4\r\n"
                    b"\r\n"
                    b"data"
                )
                while True:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                break
        except OSError:
            time.sleep(0.05)

    thread.join(timeout=10)
    assert result.get("code") == 0
    assert b"HTTP/1.1 201 OK" in response
    assert b"X-Ez: pong" in response
    assert response.endswith(b"ok")


def test_run_std_net_tcp_connect_success(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        project_toml = write_project(
            tmp_path,
            os_name=ez._native_os(),
            arch=ez._native_arch(),
        )
        port = server.server_address[1]
        (tmp_path / "src" / "index.ez").write_text(
            'from "std/net/tcp" import { tcpConnect };\n'
            'const main = (): I32 => {\n'
            f'    const conn = tcpConnect(host = "127.0.0.1", port = {port});\n'
            '    return (conn.ok && conn.value.handle != 0) ? 0 : 1;\n'
            '};\n',
            encoding="utf-8",
        )

        assert ez.main(["run", "--project", str(project_toml)]) == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_run_std_net_tcp_udp_rejects_ports_above_65535(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/tcp" import { tcpConnect, tcpListen, udpBind, udpSend, udpClose };\n'
        'const main = (): I32 => {\n'
        '    const tcp = tcpConnect(host = "127.0.0.1", port = 65536);\n'
        '    const listener = tcpListen(host = "127.0.0.1", port = 65536);\n'
        '    const udpHigh = udpBind(host = "127.0.0.1", port = 65536);\n'
        '    const udp = udpBind(host = "127.0.0.1", port = 0);\n'
        '    const sent = udpSend(socket = udp.value, host = "127.0.0.1", port = 65536, data = Blob(data = "u", size = 1));\n'
        '    const sendFailed: I64 = -1;\n'
        '    const closed = udpClose(socket = udp.value);\n'
        '    return (!tcp.ok && !listener.ok && !udpHigh.ok && udp.ok && sent == sendFailed && closed) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_net_tcp_read_write_success(tmp_path):
    ready = threading.Event()
    done = threading.Event()
    port_holder = []
    received = []

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port_holder.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                conn.settimeout(5)
                received.append(conn.recv(16))
                conn.sendall(b"pong")
            done.set()

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/tcp" import { tcpConnect, tcpRead, tcpWrite, tcpClose };\n'
        'const main = (): I32 => {\n'
        f'    const conn = tcpConnect(host = "127.0.0.1", port = {port});\n'
        '    const written = tcpWrite(conn = conn.value, data = Blob(data = "ping", size = 4));\n'
        '    const chunk = tcpRead(conn = conn.value, maxBytes = 4);\n'
        '    const closed = tcpClose(conn = conn.value);\n'
        '    return (conn.ok && written == 4 && chunk.ok && chunk.value.size == 4 && closed) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    assert done.wait(timeout=2)
    thread.join(timeout=2)
    assert received == [b"ping"]


def test_run_std_net_tcp_stream_success(tmp_path):
    ready = threading.Event()
    done = threading.Event()
    port_holder = []
    received = []

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port_holder.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                conn.settimeout(5)
                received.append(conn.recv(16))
                conn.sendall(b"pong")
            done.set()

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/tcp" import { tcpConnect };\n'
        'from "std/stream" import { streamFromTcpHandle, streamRead, streamWrite, streamClose };\n'
        'const main = (): I32 => {\n'
        f'    const conn = tcpConnect(host = "127.0.0.1", port = {port});\n'
        '    const stream = streamFromTcpHandle(handle = conn.value.handle);\n'
        '    const written = streamWrite(stream = stream, data = Blob(data = "ping", size = 4));\n'
        '    const chunk = streamRead(stream = stream, maxBytes = 4);\n'
        '    const closed = streamClose(stream = stream);\n'
        '    return (conn.ok && stream.kind == 4 && written == 4 && chunk.ok && chunk.value.size == 4 && closed) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    assert done.wait(timeout=2)
    thread.join(timeout=2)
    assert received == [b"ping"]


def test_run_std_net_tcp_listen_accept_success(tmp_path):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    ready = threading.Event()
    received = []

    def connect_once():
        ready.wait(timeout=2)
        deadline = time.monotonic() + 5
        while True:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1) as conn:
                    conn.sendall(b"hello")
                    received.append(conn.recv(16))
                    return
            except OSError:
                if time.monotonic() >= deadline:
                    return
                time.sleep(0.05)

    thread = threading.Thread(target=connect_once, daemon=True)
    thread.start()

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/tcp" import { tcpListen, tcpAccept, tcpRead, tcpWrite, tcpClose, tcpListenerClose };\n'
        'const main = (): I32 => {\n'
        f'    const listener = tcpListen(host = "127.0.0.1", port = {port});\n'
        '    const accepted = tcpAccept(listener = listener.value);\n'
        '    const chunk = tcpRead(conn = accepted.value, maxBytes = 5);\n'
        '    const written = tcpWrite(conn = accepted.value, data = Blob(data = "ok", size = 2));\n'
        '    const closed_conn = tcpClose(conn = accepted.value);\n'
        '    const closed_listener = tcpListenerClose(listener = listener.value);\n'
        '    return (listener.ok && accepted.ok && chunk.ok && chunk.value.size == 5 && written == 2 && closed_conn && closed_listener) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    ready.set()
    assert ez.main(["run", "--project", str(project_toml)]) == 0
    thread.join(timeout=2)
    assert received == [b"ok"]


def test_run_std_net_udp_send_recv_success(tmp_path):
    ready = threading.Event()
    port_holder = []
    received = []

    def udp_echo_once():
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
            server.bind(("127.0.0.1", 0))
            server.settimeout(5)
            port_holder.append(server.getsockname()[1])
            ready.set()
            data, addr = server.recvfrom(64)
            received.append(data)
            server.sendto(b"uok", addr)

    thread = threading.Thread(target=udp_echo_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/tcp" import { udpBind, udpSend, udpRecvFrom, udpClose };\n'
        'from "std/str" import { strByteLen };\n'
        'const main = (): I32 => {\n'
        '    const socket = udpBind(host = "127.0.0.1", port = 0);\n'
        f'    const sent = udpSend(socket = socket.value, host = "127.0.0.1", port = {port}, data = Blob(data = "u", size = 1));\n'
        '    const packet = udpRecvFrom(socket = socket.value, maxBytes = 8);\n'
        '    const closed = udpClose(socket = socket.value);\n'
        f'    return (socket.ok && sent == 1 && packet.ok && packet.value.data.size == 3 && packet.value.port == {port} && strByteLen(s = packet.value.host) > 0 && closed) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    thread.join(timeout=2)
    assert received == [b"u"]


def test_run_std_net_ws_connect_success(tmp_path):
    ready = threading.Event()
    port_holder = []

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port_holder.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                request = conn.recv(2048)
                conn.sendall(_ws_handshake_response(request))

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/ws" import { wsConnect };\n'
        'const main = (): I32 => {\n'
        f'    const conn = wsConnect(url = "ws://127.0.0.1:{port}/ws");\n'
        '    return (conn.ok && conn.value.handle != 0) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    thread.join(timeout=2)


def test_run_std_net_ws_connect_preserves_root_query_and_strips_fragment(tmp_path):
    ready = threading.Event()
    port_holder = []
    request_lines = []

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port_holder.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                request = conn.recv(2048)
                request_lines.append(request.split(b"\r\n", 1)[0])
                conn.sendall(_ws_handshake_response(request))

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/ws" import { wsConnect, wsClose };\n'
        'const main = (): I32 => {\n'
        f'    const conn = wsConnect(url = "ws://127.0.0.1:{port}?q=ez#fragment");\n'
        '    const closed = conn.ok ? wsClose(conn = conn.value) : false;\n'
        '    return (conn.ok && closed) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    thread.join(timeout=2)
    assert request_lines == [b"GET /?q=ez HTTP/1.1"]


def test_run_std_net_ws_connect_validates_authority_and_host_header(tmp_path):
    ready = threading.Event()
    port_holder = []
    requests = []

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port_holder.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                request = conn.recv(2048)
                requests.append(request)
                conn.sendall(_ws_handshake_response(request))

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/ws" import { wsConnect, wsClose };\n'
        'const main = (): I32 => {\n'
        f'    const conn = wsConnect(url = "ws://user:pass@127.0.0.1:{port}/socket?q=ez#fragment");\n'
        '    const alphaPort = wsConnect(url = "ws://127.0.0.1:abc/");\n'
        '    const emptyPort = wsConnect(url = "ws://127.0.0.1:/");\n'
        '    const largePort = wsConnect(url = "ws://127.0.0.1:65536/");\n'
        '    const closed = conn.ok ? wsClose(conn = conn.value) : false;\n'
        '    return (conn.ok && closed && !alphaPort.ok && !emptyPort.ok && !largePort.ok) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    thread.join(timeout=2)
    assert requests
    assert requests[0].split(b"\r\n", 1)[0] == b"GET /socket?q=ez HTTP/1.1"
    assert f"Host: 127.0.0.1:{port}\r\n".encode("ascii") in requests[0]


def test_run_std_net_ws_connect_ipv6_literal(tmp_path):
    ready = threading.Event()
    port_holder = []
    requests = []

    def serve_once():
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                server.bind(("::1", 0))
            except OSError as exc:
                ready.set()
                port_holder.append(exc)
                return
            server.listen(1)
            port_holder.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                request = conn.recv(2048)
                requests.append(request)
                conn.sendall(_ws_handshake_response(request))

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)
    if port_holder and isinstance(port_holder[0], OSError):
        thread.join(timeout=2)
        pytest.skip(f"当前环境不支持 IPv6 loopback: {port_holder[0]}")

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/ws" import { wsConnect, wsClose };\n'
        'const main = (): I32 => {\n'
        f'    const conn = wsConnect(url = "ws://[::1]:{port}/v6");\n'
        '    const closed = conn.ok ? wsClose(conn = conn.value) : false;\n'
        '    return (conn.ok && closed) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    thread.join(timeout=2)
    assert requests
    assert requests[0].split(b"\r\n", 1)[0] == b"GET /v6 HTTP/1.1"
    assert f"Host: [::1]:{port}\r\n".encode("ascii") in requests[0]


def test_run_std_net_ws_connect_rejects_bad_accept_header(tmp_path):
    ready = threading.Event()
    port_holder = []

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port_holder.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                conn.recv(2048)
                conn.sendall(
                    b"HTTP/1.1 101 Switching Protocols\r\n"
                    b"Upgrade: websocket\r\n"
                    b"Connection: Upgrade\r\n"
                    b"Sec-WebSocket-Accept: invalid\r\n\r\n"
                )

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/ws" import { wsConnect };\n'
        'const main = (): I32 => {\n'
        f'    const conn = wsConnect(url = "ws://127.0.0.1:{port}/bad");\n'
        '    return conn.ok ? 1 : 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    thread.join(timeout=2)


def test_run_std_net_ws_send_recv_success(tmp_path):
    ready = threading.Event()
    port_holder = []
    received = []

    def recv_exact(conn, size):
        data = bytearray()
        while len(data) < size:
            chunk = conn.recv(size - len(data))
            if not chunk:
                raise OSError("connection closed")
            data.extend(chunk)
        return bytes(data)

    def read_client_frame(conn):
        header = recv_exact(conn, 2)
        length = header[1] & 0x7F
        if length == 126:
            length = int.from_bytes(recv_exact(conn, 2), "big")
        elif length == 127:
            length = int.from_bytes(recv_exact(conn, 8), "big")
        mask = recv_exact(conn, 4)
        payload = recv_exact(conn, length)
        return bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))

    def send_server_frame(conn, payload):
        header = bytearray([0x82])
        if len(payload) <= 125:
            header.append(len(payload))
        elif len(payload) <= 0xFFFF:
            header.extend([126, (len(payload) >> 8) & 0xFF, len(payload) & 0xFF])
        else:
            header.append(127)
            header.extend(len(payload).to_bytes(8, "big"))
        conn.sendall(bytes(header) + payload)

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port_holder.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                conn.settimeout(5)
                request = conn.recv(2048)
                conn.sendall(_ws_handshake_response(request))
                received.append(read_client_frame(conn))
                send_server_frame(conn, b"pong")
                read_client_frame(conn)

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/ws" import { wsConnect, wsSend, wsRecv, wsClose };\n'
        'const main = (): I32 => {\n'
        f'    const conn = wsConnect(url = "ws://127.0.0.1:{port}/ws");\n'
        '    const sent = wsSend(conn = conn.value, data = Blob(data = "ping", size = 4));\n'
        '    const chunk = wsRecv(conn = conn.value, maxBytes = 8);\n'
        '    const closed = wsClose(conn = conn.value);\n'
        '    return (conn.ok && sent == 4 && chunk.ok && chunk.value.size == 4 && closed) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    thread.join(timeout=2)
    assert received == [b"ping"]


def test_run_std_net_ws_fragments_ping_pong_and_random_masks(tmp_path):
    ready = threading.Event()
    port_holder = []
    received = []
    masks = []
    pongs = []

    def recv_exact(conn, size):
        data = bytearray()
        while len(data) < size:
            chunk = conn.recv(size - len(data))
            if not chunk:
                raise OSError("connection closed")
            data.extend(chunk)
        return bytes(data)

    def read_client_frame(conn):
        header = recv_exact(conn, 2)
        opcode = header[0] & 0x0F
        length = header[1] & 0x7F
        if length == 126:
            length = int.from_bytes(recv_exact(conn, 2), "big")
        elif length == 127:
            length = int.from_bytes(recv_exact(conn, 8), "big")
        mask = recv_exact(conn, 4)
        payload = recv_exact(conn, length)
        masks.append(mask)
        return opcode, bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))

    def send_server_frame(conn, opcode, payload, *, fin=True):
        first = (0x80 if fin else 0) | opcode
        header = bytearray([first])
        if len(payload) <= 125:
            header.append(len(payload))
        elif len(payload) <= 0xFFFF:
            header.extend([126, (len(payload) >> 8) & 0xFF, len(payload) & 0xFF])
        else:
            header.append(127)
            header.extend(len(payload).to_bytes(8, "big"))
        conn.sendall(bytes(header) + payload)

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port_holder.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                conn.settimeout(5)
                request = conn.recv(2048)
                conn.sendall(_ws_handshake_response(request))
                received.append(read_client_frame(conn)[1])
                received.append(read_client_frame(conn)[1])
                send_server_frame(conn, 0x9, b"?")
                opcode, payload = read_client_frame(conn)
                pongs.append((opcode, payload))
                send_server_frame(conn, 0x2, b"po", fin=False)
                send_server_frame(conn, 0x0, b"ng", fin=True)
                read_client_frame(conn)

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    port = port_holder[0]
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/net/ws" import { wsConnect, wsSend, wsRecv, wsClose };\n'
        'const main = (): I32 => {\n'
        f'    const conn = wsConnect(url = "ws://127.0.0.1:{port}/ws");\n'
        '    const first = wsSend(conn = conn.value, data = Blob(data = "one", size = 3));\n'
        '    const second = wsSend(conn = conn.value, data = Blob(data = "two", size = 3));\n'
        '    const chunk = wsRecv(conn = conn.value, maxBytes = 8);\n'
        '    const closed = wsClose(conn = conn.value);\n'
        '    return (conn.ok && first == 3 && second == 3 && chunk.ok && chunk.value.size == 4 && closed) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0
    thread.join(timeout=2)
    assert received == [b"one", b"two"]
    assert len(masks) >= 3
    assert masks[0] != masks[1]
    assert pongs == [(0xA, b"?")]


def test_run_flow_parallel_and_lock_hooks_link(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'rp let cache: I32 = 0;\n'
        'wp let queue: I32 = 0;\n'
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        const p = parallel { return 7; };\n'
        '        return p;\n'
        '    };\n'
        '    return value == 7 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_wp_lock_protects_parallel_compound_assignment(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'wp let total: I32 = 0;\n'
        'const main = (): I32 => {\n'
        '    const joined = flow {\n'
        '        const a = parallel { loop i in 0...500 { total += 1; }; return 1; };\n'
        '        const b = parallel { loop i in 0...500 { total += 1; }; return 1; };\n'
        '        const c = parallel { loop i in 0...500 { total += 1; }; return 1; };\n'
        '        const d = parallel { loop i in 0...500 { total += 1; }; return 1; };\n'
        '        return a + b + c + d;\n'
        '    };\n'
        '    return joined == 4 ? (total == 2000 ? 0 : 1) : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_global_let_default_ordered_lock_protects_parallel_assignment(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'let total: I32 = 0;\n'
        'const main = (): I32 => {\n'
        '    const joined = flow {\n'
        '        const a = parallel { loop i in 0...500 { total += 1; }; return 1; };\n'
        '        const b = parallel { loop i in 0...500 { total += 1; }; return 1; };\n'
        '        const c = parallel { loop i in 0...500 { total += 1; }; return 1; };\n'
        '        const d = parallel { loop i in 0...500 { total += 1; }; return 1; };\n'
        '        return a + b + c + d;\n'
        '    };\n'
        '    return joined == 4 ? (total == 2000 ? 0 : 1) : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_flow_race_pl_returns_first_branch(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        return race(pl = [() => { return 7; }, () => { return 9; }], timeout = 10);\n'
        '    };\n'
        '    return value == 7 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_flow_race_pl_non_i32_uses_synchronous_fallback(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/test" import { testReset, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const value = flow {\n'
        '        return race(pl = [() => { return "a"; }, () => { return "b"; }], timeout = 10);\n'
        '    };\n'
        '    testEqualStr(actual = value, expected = "a", msg = "race str fallback");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_flow_race_pl_returns_first_completed_branch(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/time" import { sleep };\n'
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        return race(pl = [\n'
        '            () => { sleep(ms = 80); return 1; },\n'
        '            () => { sleep(ms = 5); return 2; },\n'
        '        ], timeout = 500);\n'
        '    };\n'
        '    return value == 2 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_flow_race_pl_timeout_returns_zero(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/time" import { sleep };\n'
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        return race(pl = [\n'
        '            () => { sleep(ms = 80); return 1; },\n'
        '            () => { sleep(ms = 90); return 2; },\n'
        '        ], timeout = 5);\n'
        '    };\n'
        '    return value == 0 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_arena_race_branches_use_thread_local_storage(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/mem" import { allocRaw, set };\n'
        'from "std/time" import { sleep };\n'
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        return race(pl = [\n'
        '            () => { const a = allocRaw(size = 64); set(dst = a, value = 1, count = 64); sleep(ms = 20); return a.size == 64 ? 1 : 9; },\n'
        '            () => { const b = allocRaw(size = 1049600); set(dst = b, value = 2, count = 1049600); return b.size == 1049600 ? 2 : 8; },\n'
        '        ], timeout = 500);\n'
        '    };\n'
        '    return value == 2 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_flow_parallel_read_waits_for_future(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/time" import { sleep };\n'
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        const p = parallel { sleep(ms = 10); return 7; };\n'
        '        const local = 5;\n'
        '        return p + local;\n'
        '    };\n'
        '    return value == 12 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_flow_parallel_typed_i32_read_waits_for_future(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/time" import { sleep };\n'
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        const p: I32 = parallel { sleep(ms = 10); return 7; };\n'
        '        const local = 5;\n'
        '        return p + local;\n'
        '    };\n'
        '    return value == 12 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_flow_parallel_combined_expression_evaluates_rhs(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        const combined = parallel { return 7; } + 1;\n'
        '        return combined;\n'
        '    };\n'
        '    return value == 8 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_flow_parallel_joins_unread_side_effect_before_exit(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/time" import { sleep };\n'
        'let flag: I32 = 0;\n'
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        const p = parallel { sleep(ms = 10); flag = 3; return 1; };\n'
        '        return 2;\n'
        '    };\n'
        '    return value == 2 ? (flag == 3 ? 0 : 1) : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_throw_catch_propagates_through_flow_parallel_and_race(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    const flowErr = catch {\n'
        '        const value = flow {\n'
        '            throw Error(code = 31, message = "flow");\n'
        '            return 1;\n'
        '        };\n'
        '    };\n'
        '    const parallelErr = catch {\n'
        '        const value = parallel {\n'
        '            throw Error(code = 32, message = "parallel");\n'
        '            return 1;\n'
        '        };\n'
        '    };\n'
        '    const raceErr = catch {\n'
        '        const value = flow {\n'
        '            return race(pl = [() => { throw Error(code = 33, message = "race"); return 1; }, () => { return 2; }], timeout = 10);\n'
        '        };\n'
        '    };\n'
        '    return (flowErr.code == 31 && parallelErr.code == 32 && raceErr.code == 33) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_uncaught_throw_inside_flow_exits_nonzero(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        throw Error(code = 33, message = "uncaught");\n'
        '        return 1;\n'
        '    };\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 1


def test_run_member_assignment_and_compound_assignment(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'struct Counter {\n'
        '    value: I32;\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    let c = Counter(value = 1);\n'
        '    c.value = 2;\n'
        '    c.value += 3;\n'
        '    return c.value == 5 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_struct_assignment_uses_value_copy(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'struct Point {\n'
        '    x: I32;\n'
        '    y: I32;\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    let p1 = Point(x = 1, y = 2);\n'
        '    let p2 = p1;\n'
        '    p2.x = 9;\n'
        '    return (p1.x == 1 && p2.x == 9) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_struct_method_this_uses_reference_semantics(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'struct Counter {\n'
        '    value: I32;\n'
        '    set = (this: Counter, v: I32): Void => {\n'
        '        this.value = v;\n'
        '    };\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    let c = Counter(value = 1);\n'
        '    c.set(v = 5);\n'
        '    return c.value == 5 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_list_assignment_uses_value_copy(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let a = [1, 2, 3];\n'
        '    let b = a;\n'
        '    b[0] = 9;\n'
        '    return (a[0] == 1 && b[0] == 9) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_dict_assignment_uses_value_copy(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let a = { n: I32 = 1 };\n'
        '    let b = a;\n'
        '    b["n"] = 9;\n'
        '    return (a["n"] == 1 && b["n"] == 9) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_optional_ok_value_and_unwraps(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let empty: I32?;\n'
        '    let present: I32? = 42;\n'
        '    const forced = present!;\n'
        '    const safe = present?;\n'
        '    return (!empty.ok && present.ok && present.value == 42 && forced == 42 && safe == 42) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_placeholder_none_initializes_optional_values(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'struct Node { value: I32; next: Node?; };\n'
        'const main = (): I32 => {\n'
        '    let empty: I32? = ?;\n'
        '    let node = Node(value = 1, next = ?);\n'
        '    return (!empty.ok && !node.next.ok) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_optional_member_access_short_circuits(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'struct Box { value: I32; };\n'
        'const main = (): I32 => {\n'
        '    let empty: Box?;\n'
        '    let present: Box? = Box(value = 42);\n'
        '    const missing = empty?.value;\n'
        '    const value = present?.value;\n'
        '    return (!missing.ok && value.ok && value.value == 42) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_optional_method_access_short_circuits(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'struct TextBox {\n'
        '    value: Str;\n'
        '    text = (this: TextBox): Str => { return this.value; };\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    let empty: TextBox?;\n'
        '    let present: TextBox? = TextBox(value = "ok");\n'
        '    const missing = empty?.text();\n'
        '    const value = present?.text();\n'
        '    return (!missing.ok && value.ok && strEqual(a = value.value, b = "ok")) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_union_values_keep_variant_tags(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'const main = (): I32 => {\n'
        '    let n: I32 | Str = 42;\n'
        '    let s: I32 | Str = "ez";\n'
        '    return (n.tag == 0 && s.tag == 1 && strEqual(a = s.value, b = "ez")) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_union_return_keeps_variant_tag(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const make = (): I32 | Str => {\n'
        '    return "ez";\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    const value = make();\n'
        '    return value.tag == 1 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_union_match_branches_on_tag(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'const main = (): I32 => {\n'
        '    let value: I32 | Str = "ez";\n'
        '    let result: I32 = 0;\n'
        '    match {\n'
        '        (value.tag == 0) ? { result = 1; },\n'
        '        (value.tag == 1 && strEqual(a = value.value, b = "ez")) ? { result = 2; },\n'
        '    };\n'
        '    return result == 2 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_match_continues_by_default_and_supports_continue_break(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let value: I32 = 0;\n'
        '    match {\n'
        '        (true) ? { value += 1; },\n'
        '        (true) ? { value += 10; continue; value += 100; },\n'
        '        (true) ? { value += 1000; break; },\n'
        '        (true) ? { value += 10000; }\n'
        '    };\n'
        '    return value == 1011 ? 0 : value;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_if_like_expression_statement_executes_conditionally(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let value: I32 = 1;\n'
        '    (false) ? value = 10;\n'
        '    (true) ? value = value + 2;\n'
        '    return value == 3 ? 0 : value;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_generic_function_infers_type_arguments(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'const identity<T> = (value: T): T => { return value; };\n'
        'const main = (): I32 => {\n'
        '    const n = identity(value = 42);\n'
        '    const s = identity(value = "ez");\n'
        '    return (n == 42 && strEqual(a = s, b = "ez")) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_expression_generic_function_infers_type_arguments(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const identity = <T>(value: T) => value;\n'
        'const main = (): I32 => {\n'
        '    const explicit = identity<I32>(42);\n'
        '    const inferred = identity(7);\n'
        '    return (explicit == 42 && inferred == 7) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_generic_struct_explicit_type_arguments(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'struct Pair<T, U> { first: T; second: U; };\n'
        'const main = (): I32 => {\n'
        '    const p = Pair<I32, Str>(first = 42, second = "ez");\n'
        '    return (p.first == 42 && strEqual(a = p.second, b = "ez")) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_nested_generic_struct_adjacent_right_angles(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'struct Box<T> { value: T; };\n'
        'const unwrap = (box: Box<Box<U32>>): U32 => {\n'
        '    return box.value.value;\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    const inner = Box<U32>(value = 42);\n'
        '    const outer = Box<Box<U32>>(value = inner);\n'
        '    return unwrap(box = outer) == 42 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_generic_struct_infers_type_arguments(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'struct Pair<T, U> { first: T; second: U; };\n'
        'const main = (): I32 => {\n'
        '    const p = Pair(first = 42, second = "ez");\n'
        '    return (p.first == 42 && strEqual(a = p.second, b = "ez")) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_struct_duck_type_alias_accepts_struct_value(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'type PointShape = { x: I32; y: I32; };\n'
        'struct Point { x: I32; y: I32; };\n'
        'const main = (): I32 => {\n'
        '    const p: PointShape = Point(x = 10, y = 20);\n'
        '    return (p.x == 10 && p.y == 20) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_generic_struct_method_swap_monomorphizes(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'struct Pair<T, U> {\n'
        '    first: T;\n'
        '    second: U;\n'
        '    swap = (this: Pair<T, U>): Pair<U, T> => {\n'
        '        return Pair<U, T>(first = this.second, second = this.first);\n'
        '    };\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    const p = Pair(first = 42, second = "ez");\n'
        '    const swapped = p.swap();\n'
        '    return (strEqual(a = swapped.first, b = "ez") && swapped.second == 42) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_index_assignment_and_compound_assignment(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let arr = [1, 2, 3];\n'
        '    arr[0] = 2;\n'
        '    arr[0] += 3;\n'
        '    return arr[0] == 5 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_loop_in_array_iterates_element_values(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let total: I32 = 0;\n'
        '    let nums: I32[] = [1, 2, 3];\n'
        '    loop item in nums {\n'
        '        total += item;\n'
        '    };\n'
        '    return total == 6 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_array_length_member_reads_paged_layout(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strSplit };\n'
        'const main = (): I32 => {\n'
        '    const nums: I32[] = [1, 2, 3];\n'
        '    const parts = strSplit(s = "a,b,c", sep = ",");\n'
        '    return nums.length == 3 && parts.length == 3 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_variable_decl_without_initializer_uses_zero_value(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let count: I32;\n'
        '    let arr: I32[]?;\n'
        '    return count == 0 && !arr.ok ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_unsigned_integer_ops(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let a: U32 = 2147483648;\n'
        '    let b: U32 = 2;\n'
        '    let shift: U32 = 1;\n'
        '    let q: U32 = a / b;\n'
        '    let r: U32 = a % b;\n'
        '    let s: U32 = a >> shift;\n'
        '    q /= b;\n'
        '    r %= b;\n'
        '    s >>= shift;\n'
        '    return q == 536870912 && r == 0 && s == 536870912 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_signed_integer_division_uses_floor_semantics(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let a: I32 = -3;\n'
        '    let b: I32 = 2;\n'
        '    let c: I32 = 3;\n'
        '    let d: I32 = -2;\n'
        '    let q1 = a / b;\n'
        '    let r1 = a % b;\n'
        '    let q2 = c / d;\n'
        '    let r2 = c % d;\n'
        '    a /= b;\n'
        '    c %= d;\n'
        '    return (q1 == -2 && r1 == 1 && q2 == -2 && r2 == -1 && a == -2 && c == -1) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_unsigned_bitwise_expression_keeps_logical_shift(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let high: U32 = 2147483648;\n'
        '    let mask: U32 = 4294967295;\n'
        '    let shift: U32 = 1;\n'
        '    let from_and: U32 = (high & mask) >> shift;\n'
        '    let from_or: U32 = (high | 0) >> shift;\n'
        '    let from_xor: U32 = (high ^ 0) >> shift;\n'
        '    let compound: U32 = high;\n'
        '    compound &= mask;\n'
        '    compound >>= shift;\n'
        '    return from_and == 1073741824 && from_or == 1073741824 && from_xor == 1073741824 && compound == 1073741824 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_large_integer_literals_keep_i64_value(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const same = (value: I64): I64 => { return value; };\n'
        'const main = (): I32 => {\n'
        '    const inferred = 492395637191921148;\n'
        '    const annotated: I64 = 492395637191921148;\n'
        '    const passed = same(value = 492395637191921148);\n'
        '    return inferred == annotated && passed == annotated ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_unsigned_relational_ops(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let high: U32 = 2147483648;\n'
        '    let low: U32 = 1;\n'
        '    return high > low && !(high < low) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_logical_operators_short_circuit_side_effects(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'let hits: I32 = 0;\n'
        'const bump_true = (): Bool => { hits += 1; return true; };\n'
        'const bump_false = (): Bool => { hits += 100; return false; };\n'
        'const main = (): I32 => {\n'
        '    const skipped_and = false && bump_true();\n'
        '    const skipped_or = true || bump_false();\n'
        '    const eval_and = true && bump_true();\n'
        '    const eval_or = false || bump_false();\n'
        '    return (!skipped_and && skipped_or && eval_and && !eval_or && hits == 101) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_catch_expression_returns_thrown_error(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strContains, strEqual };\n'
        'const main = (): I32 => {\n'
        '    const err = catch {\n'
        '        throw Error(code = 9, message = "boom");\n'
        '    };\n'
        '    const ok = err.code == 9 && strEqual(a = err.message, b = "boom") && err.file != "" && err.line > 0 && err.column > 0 && strContains(s = err.trace, needle = "main@");\n'
        '    return ok ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_builtin_error_to_string_method(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strContains };\n'
        'const main = (): I32 => {\n'
        '    const err = Error(code = 7, message = "boom");\n'
        '    const text = err.toString();\n'
        '    const ok = strContains(s = text, needle = "code=7") && strContains(s = text, needle = "message=boom") && strContains(s = text, needle = "trace=main@");\n'
        '    return ok ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_catch_captures_error_from_called_function(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const fail = (): Void => { throw Error(code = 17, message = "nested"); };\n'
        'const run = (body: () => Void): I32 => {\n'
        '    const err = catch { body(); };\n'
        '    return err.code;\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    return run(body = fail) == 17 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_uncaught_throw_exits_nonzero(tmp_path, capfd):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    throw Error(code = 9, message = "boom");\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 1
    captured = capfd.readouterr()
    output = captured.out + captured.err
    assert "uncaught EzLang throw" in output
    assert "code=9" in output
    assert "message=boom" in output
    assert "trace=main@" in output


def test_run_uncaught_throw_from_called_function_exits_nonzero(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const fail = (): Void => { throw Error(code = 9, message = "boom"); };\n'
        'const main = (): I32 => {\n'
        '    fail();\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 1


def test_run_typeof_struct_value_matches_type_id(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    const err = Error(code = 1, message = "x");\n'
        '    return typeof err & Error == Error ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_curried_placeholder_call(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const add = (a: I32, b: I32): I32 => {\n'
        '    return a + b;\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    let add2 = add(a = 2, b = ?);\n'
        '    const value = add2(b = 3);\n'
        '    return value == 5 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_curried_placeholder_call_reorders_by_parameter_name(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const calc = (a: I32, b: I32, c: I32): I32 => {\n'
        '    return a * 100 + b * 10 + c;\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    let fill = calc(c = ?, a = ?, b = 4);\n'
        '    const value = fill(c = 7, a = 2);\n'
        '    return value == 247 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_markup_literal_lowers_to_factory_call(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'const text = (color: Str, children: Str[]): I32 => {\n'
        '    (children.length != 2) ? { return 1; };\n'
        '    (!strEqual(a = color, b = "blue")) ? { return 2; };\n'
        '    (!strEqual(a = children[0], b = "Welcome")) ? { return 3; };\n'
        '    (!strEqual(a = children[1], b = "Ez")) ? { return 4; };\n'
        '    return 7;\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    const ui = <text color="blue">"Welcome"{"Ez"}</text>;\n'
        '    return ui == 7 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_ui_native_minimal_handles_work(tmp_path):
    cases = [
        (
            "web",
            'from "ez-web-ui" import { createElement, requestPermission };\n'
            'const main = (): I32 => {\n'
            '    const node = createElement(tag = "div");\n'
            '    return (node.id == 0 && !requestPermission(perm = "camera")) ? 0 : 1;\n'
            '};\n',
        ),
        (
            "android",
            'from "std/str" import { strEqual };\n'
            'from "ez-android-ui" import { Color, createTextView, createButton, createRecyclerView, createHScrollView, createImageButton, createCheckBox, createRadioButton, createSwitch, createProgressBar, createSeekBar, setText, getText, addView, getRootView, getChildCount, setLayoutWidth, setLayoutHeight, getWidth, getHeight, getMeasuredWidth, getMeasuredHeight, setTag, getTag, setHint, setWeight, setAlpha, setBackgroundDrawable, setElevation, setCornerRadius, setContentDesc, setStatusBarColor, showKeyboard, hideKeyboard, isMainThread, requestPermission, requestPermissions };\n'
            'const main = (): I32 => {\n'
            '    const root = getRootView();\n'
            '    const label = createTextView();\n'
            '    const button = createButton();\n'
            '    const list = createRecyclerView();\n'
            '    setText(node = label, text = "hello");\n'
            '    setLayoutWidth(node = label, value = 123);\n'
            '    setLayoutHeight(node = label, value = 45);\n'
            '    setTag(node = label, key = "role", value = "title");\n'
            '    setHint(node = label, hint = "hint");\n'
            '    setWeight(node = label, weight = 1.0);\n'
            '    setAlpha(node = label, alpha = 0.5);\n'
            '    setBackgroundDrawable(node = label, resId = 7);\n'
            '    setElevation(node = label, dp = 2.0);\n'
            '    setCornerRadius(node = label, dp = 3.0);\n'
            '    setContentDesc(node = label, desc = "desc");\n'
            '    setStatusBarColor(color = Color(value = 0));\n'
            '    showKeyboard(node = label);\n'
            '    hideKeyboard();\n'
            '    const perms = requestPermissions(perms = ["android.permission.CAMERA"]);\n'
            '    addView(parent = root, child = list);\n'
            '    addView(parent = root, child = label);\n'
            '    addView(parent = root, child = button);\n'
            '    addView(parent = root, child = createHScrollView());\n'
            '    addView(parent = root, child = createImageButton());\n'
            '    addView(parent = root, child = createCheckBox());\n'
            '    addView(parent = root, child = createRadioButton());\n'
            '    addView(parent = root, child = createSwitch());\n'
            '    addView(parent = root, child = createProgressBar());\n'
            '    addView(parent = root, child = createSeekBar());\n'
            '    return (root.id != 0 && label.id != 0 && button.id != 0 && getChildCount(parent = root) == 10 && getWidth(node = label) == 123 && getHeight(node = label) == 45 && getMeasuredWidth(node = label) == 123 && getMeasuredHeight(node = label) == 45 && strEqual(a = getText(node = label), b = "hello") && strEqual(a = getTag(node = label, key = "role")!, b = "title") && perms["android.permission.CAMERA"] == false && isMainThread() && !requestPermission(perm = "android.permission.CAMERA")) ? 0 : 1;\n'
            '};\n',
        ),
        (
            "ios",
            'from "std/str" import { strEqual };\n'
            'from "ez-ios-ui" import { Color, Rect, Insets, createLabel, createButton, createSegmentControl, createStepper, createActivityIndicator, createTableView, createCollectionView, createImageView, setFrame, getFrame, setBounds, getBounds, setText, getText, addSubview, insertSubviewAbove, insertSubviewBelow, bringToFront, sendToBack, getSubviewAt, getRootView, getSubviewCount, setTag_, getTag_, setSwitchOn, getSwitchOn, setSliderValue, getSliderValue, setSliderRange, pinToEdges, centerInParent, setWidth, setHeight, sizeToFit, setSpacing, setAlignment, setDistribution, setAttributedText, setFont, setSystemFont, setTextColor, setTextAlign, setNumberOfLines, setLineBreakMode, setPlaceholder, setKeyboardType, setSecureEntry, setReturnKeyType, setBackgroundColor, setAlpha, setHidden, setUserInteraction, setClipsToBounds, setCornerRadius, setBorderWidth, setBorderColor, setShadow, setAccessLabel, setNeedsLayout, layoutIfNeeded, setImageUrl, setImageName, setSystemImage, setContentMode, setTintColor, setButtonTitle, setButtonImage, setButtonEnabled, setSwitchTintColor, startAnimating, stopAnimating, becomeFirstResponder, resignFirstResponder, isMainThread, requestPermission };\n'
            'const main = (): I32 => {\n'
            '    const root = getRootView();\n'
            '    const label = createLabel();\n'
            '    const button = createButton();\n'
            '    const table = createTableView();\n'
            '    setText(node = label, text = "hello");\n'
            '    setFrame(node = label, rect = Rect(x = 1.0, y = 2.0, width = 30.0, height = 40.0));\n'
            '    setBounds(node = label, rect = Rect(x = 0.0, y = 0.0, width = 10.0, height = 20.0));\n'
            '    setTag_(node = label, tag = 7);\n'
            '    setSwitchOn(node = button, on = true, animated = false);\n'
            '    setSliderValue(node = table, value = 0.75, animated = false);\n'
            '    setSliderRange(node = table, min = 0.0, max = 1.0);\n'
            '    pinToEdges(node = label, insets = Insets(top = 1.0, left = 2.0, bottom = 3.0, right = 4.0));\n'
            '    centerInParent(node = label);\n'
            '    setWidth(node = label, width = 50.0);\n'
            '    setHeight(node = label, height = 60.0);\n'
            '    sizeToFit(node = createLabel());\n'
            '    setSpacing(node = root, spacing = 2.0);\n'
            '    setAlignment(node = root, align = 1);\n'
            '    setDistribution(node = root, dist = 2);\n'
            '    setAttributedText(node = label, html = "<b>hello</b>");\n'
            '    setFont(node = label, name = "A", size = 12.0);\n'
            '    setSystemFont(node = label, size = 13.0, weight = 1.0);\n'
            '    setTextColor(node = label, color = Color(r = 1.0, g = 1.0, b = 1.0, a = 1.0));\n'
            '    setTextAlign(node = label, align = 1);\n'
            '    setNumberOfLines(node = label, n = 2);\n'
            '    setLineBreakMode(node = label, mode = 1);\n'
            '    setPlaceholder(node = label, text = "hint");\n'
            '    setKeyboardType(node = label, type_ = 1);\n'
            '    setSecureEntry(node = label, secure = true);\n'
            '    setReturnKeyType(node = label, type_ = 1);\n'
            '    setBackgroundColor(node = label, color = Color(r = 0.0, g = 0.0, b = 0.0, a = 1.0));\n'
            '    setAlpha(node = label, alpha = 0.5);\n'
            '    setHidden(node = label, hidden = false);\n'
            '    setUserInteraction(node = label, enabled = true);\n'
            '    setClipsToBounds(node = label, clips = true);\n'
            '    setCornerRadius(node = label, radius = 3.0);\n'
            '    setBorderWidth(node = label, width = 1.0);\n'
            '    setBorderColor(node = label, color = Color(r = 1.0, g = 0.0, b = 0.0, a = 1.0));\n'
            '    setShadow(node = label, color = Color(r = 0.0, g = 0.0, b = 0.0, a = 1.0), offset = Rect(x = 1.0, y = 1.0, width = 0.0, height = 0.0), radius = 2.0, opacity = 0.3);\n'
            '    setAccessLabel(node = label, label = "access");\n'
            '    setNeedsLayout(node = label);\n'
            '    layoutIfNeeded(node = label);\n'
            '    setImageUrl(node = label, url = "https://x");\n'
            '    setImageName(node = label, name = "asset");\n'
            '    setSystemImage(node = label, sfName = "star");\n'
            '    setContentMode(node = label, mode = 1);\n'
            '    setTintColor(node = label, color = Color(r = 0.0, g = 1.0, b = 0.0, a = 1.0));\n'
            '    setButtonTitle(node = button, title = "ok", state = 0);\n'
            '    setButtonImage(node = button, name = "ok", state = 0);\n'
            '    setButtonEnabled(node = button, enabled = true);\n'
            '    setSwitchTintColor(node = button, color = Color(r = 0.0, g = 1.0, b = 0.0, a = 1.0));\n'
            '    startAnimating(node = createActivityIndicator());\n'
            '    stopAnimating(node = createActivityIndicator());\n'
            '    becomeFirstResponder(node = label);\n'
            '    resignFirstResponder(node = label);\n'
            '    addSubview(parent = root, child = label);\n'
            '    addSubview(parent = root, child = button);\n'
            '    insertSubviewBelow(parent = root, child = createSegmentControl(segments = ["a", "b"]), ref = label);\n'
            '    insertSubviewAbove(parent = root, child = createStepper(), ref = button);\n'
            '    addSubview(parent = root, child = table);\n'
            '    addSubview(parent = root, child = createCollectionView());\n'
            '    addSubview(parent = root, child = createImageView());\n'
            '    bringToFront(node = label);\n'
            '    sendToBack(node = button);\n'
            '    const frame = getFrame(node = label);\n'
            '    const bounds = getBounds(node = label);\n'
            '    return (root.id != 0 && label.id != 0 && button.id != 0 && getSubviewCount(parent = root) == 7 && getSubviewAt(parent = root, index = 0)!.id == button.id && strEqual(a = getText(node = label), b = "hello") && getTag_(node = label) == 7 && getSwitchOn(node = button) && getSliderValue(node = table) > 0.7 && frame.width >= 5.0 && bounds.width == 10.0 && isMainThread() && !requestPermission(perm = "camera")) ? 0 : 1;\n'
            '};\n',
        ),
    ]

    for name, source in cases:
        case_dir = tmp_path / name
        case_dir.mkdir()
        project_toml = write_project(
            case_dir,
            os_name=ez._native_os(),
            arch=ez._native_arch(),
        )
        (case_dir / "src" / "index.ez").write_text(source, encoding="utf-8")

        assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_test_command_compiles_and_runs_tests(tmp_path, capsys):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "math_test.ez").write_text(
        'from "std/fmt" import { parseI64, parseF64 };\n'
        'from "std/test" import { testAssert, testEqualI64 };\n'
        'const test_math = (): I32 => {\n'
        '    testEqualI64(actual = 2 + 2, expected = 4, msg = "math");\n'
        '    const parsed_i = parseI64(s = "42");\n'
        '    testAssert(condition = parsed_i.ok, msg = "parseI64 ok");\n'
        '    testEqualI64(actual = parsed_i.value, expected = 42, msg = "parseI64 value");\n'
        '    const parsed_f = parseF64(s = "3.5");\n'
        '    testAssert(condition = parsed_f.ok, msg = "parseF64 ok");\n'
        '    testAssert(condition = parsed_f.value > 3.49 && parsed_f.value < 3.51, msg = "parseF64 value");\n'
        '    return 0;\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    return test_math();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["test", "--project", str(project_toml)]) == 0
    out = capsys.readouterr().out
    assert "ok tests/math_test.ez" in out
    assert "1 passed; 0 failed" in out


def test_run_links_std_process_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/process" import { Command, Process, processExec, processSpawn, processWait, processTerminate, processCurrentPath };\n'
        'from "std/str" import { strFromBytes };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const args: Str[] = ["-c", "printf hello"];\n'
        '    const spawn_args: Str[] = ["-c", "cat; printf err >&2; exit 7"];\n'
        '    const envs: Str[] = ["EZLANG_PROCESS_TEST=1"];\n'
        '    const empty: Str[] = [];\n'
        '    const result = processExec(command = Command(program = "/bin/sh", args = args, cwd = "", env = envs, stdin = Blob(data = "", size = 0)));\n'
        '    testAssert(condition = result.ok && result.value.ok, msg = "processExec ok");\n'
        '    const exec_stdout = strFromBytes(data = result.value.stdout);\n'
        '    testAssert(condition = exec_stdout.ok, msg = "processExec stdout utf8");\n'
        '    testEqualStr(actual = exec_stdout.value, expected = "hello", msg = "processExec captures stdout");\n'
        '    const current = processCurrentPath();\n'
        '    testAssert(condition = current.ok, msg = "current path available");\n'
        '    const proc = processSpawn(command = Command(program = "/bin/sh", args = spawn_args, cwd = "", env = empty, stdin = Blob(data = "in", size = 2)));\n'
        '    testAssert(condition = proc.ok, msg = "processSpawn ok");\n'
        '    const spawn_result = processWait(process = proc.value);\n'
        '    testAssert(condition = spawn_result.ok && !spawn_result.value.ok, msg = "processWait returns nonzero result");\n'
        '    testEqualI64(actual = spawn_result.value.exitCode, expected = 7, msg = "processWait exit code");\n'
        '    const spawn_stdout = strFromBytes(data = spawn_result.value.stdout);\n'
        '    const spawn_stderr = strFromBytes(data = spawn_result.value.stderr);\n'
        '    testAssert(condition = spawn_stdout.ok && spawn_stderr.ok, msg = "processWait streams utf8");\n'
        '    testEqualStr(actual = spawn_stdout.value, expected = "in", msg = "processWait captures stdout");\n'
        '    testEqualStr(actual = spawn_stderr.value, expected = "err", msg = "processWait captures stderr");\n'
        '    const waited = processWait(process = Process(handle = 0, pid = 0));\n'
        '    testAssert(condition = !waited.ok, msg = "invalid process wait fails");\n'
        '    const killed = processTerminate(process = Process(handle = 0, pid = 0));\n'
        '    testAssert(condition = !killed, msg = "invalid process terminate fails");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_process_stream_pipes_success(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/process" import { Command, processSpawn, processStdin, processStdout, processWait };\n'
        'from "std/stream" import { streamWrite, streamRead, streamClose };\n'
        'from "std/str" import { strFromBytes };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const args: Str[] = ["-c", "cat"];\n'
        '    const empty: Str[] = [];\n'
        '    const proc = processSpawn(command = Command(program = "/bin/sh", args = args, cwd = "", env = empty, stdin = Blob(data = "", size = 0)));\n'
        '    testAssert(condition = proc.ok, msg = "processSpawn ok");\n'
        '    const input = processStdin(process = proc.value);\n'
        '    const output = processStdout(process = proc.value);\n'
        '    testAssert(condition = input.ok && output.ok, msg = "process pipe streams ok");\n'
        '    const written = streamWrite(stream = input.value, data = Blob(data = "pipe", size = 4));\n'
        '    testEqualI64(actual = written, expected = 4, msg = "stdin stream writes bytes");\n'
        '    const closed_in = streamClose(stream = input.value);\n'
        '    testAssert(condition = closed_in, msg = "stdin stream closes");\n'
        '    const chunk = streamRead(stream = output.value, maxBytes = 4);\n'
        '    testAssert(condition = chunk.ok, msg = "stdout stream reads");\n'
        '    testEqualI64(actual = chunk.value.size, expected = 4, msg = "stdout stream size");\n'
        '    const text = strFromBytes(data = chunk.value);\n'
        '    testAssert(condition = text.ok, msg = "stdout stream utf8");\n'
        '    testEqualStr(actual = text.value, expected = "pipe", msg = "stdout stream text");\n'
        '    const closed_out = streamClose(stream = output.value);\n'
        '    testAssert(condition = closed_out, msg = "stdout stream closes");\n'
        '    const result = processWait(process = proc.value);\n'
        '    testAssert(condition = result.ok && result.value.ok, msg = "processWait ok after transfer");\n'
        '    testEqualI64(actual = result.value.stdout.size, expected = 0, msg = "transferred stdout omitted from wait");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_process_rejects_invalid_stdin_blob(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/process" import { Command, processExec, processSpawn };\n'
        'from "std/test" import { testReset, testAssert, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const args: Str[] = ["-c", "cat"];\n'
        '    const empty: Str[] = [];\n'
        '    const invalid = Blob(data = "", size = -1);\n'
        '    const exec_result = processExec(command = Command(program = "/bin/sh", args = args, cwd = "", env = empty, stdin = invalid));\n'
        '    const spawned = processSpawn(command = Command(program = "/bin/sh", args = args, cwd = "", env = empty, stdin = invalid));\n'
        '    testAssert(condition = !exec_result.ok && !spawned.ok, msg = "invalid stdin blob rejects process calls");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_links_std_fs_io_os_native_abi(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    work_dir = (tmp_path / "fs-work").as_posix()
    data_file = (tmp_path / "fs-work" / "data.txt").as_posix()
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fs" import { writeFile, readFile, exists, stat, listDir, mkdir, removeDir, removeFile };\n'
        'from "std/io" import { println };\n'
        'from "std/os" import { cwd, env, pid, platform, arch };\n'
        'const main = (): I32 => {\n'
        f'    const made = mkdir(path = "{work_dir}");\n'
        '    const content = Blob(data = "hello", size = 5);\n'
        f'    const wrote = writeFile(path = "{data_file}", content = content);\n'
        f'    const data = readFile(path = "{data_file}");\n'
        f'    const ok = exists(path = "{data_file}");\n'
        f'    const info = stat(path = "{data_file}");\n'
        f'    const entries = listDir(path = "{work_dir}");\n'
        '    const here = cwd();\n'
        '    const home = env(key = "HOME");\n'
        '    const proc = pid();\n'
        '    const os_name = platform();\n'
        '    const arch_name = arch();\n'
        '    println(msg = os_name);\n'
        f'    const removed_file = removeFile(path = "{data_file}");\n'
        f'    const removed_dir = removeDir(path = "{work_dir}", recursive = true);\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fs_recursive_dir_list_and_millisecond_stat(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    root = (tmp_path / "fs-recursive").as_posix()
    nested_file = (tmp_path / "fs-recursive" / "nested" / "data.txt").as_posix()
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fs" import { writeFile, listDir, stat, exists, isDir, removeDir };\n'
        'from "std/collections" import { listLen };\n'
        'const main = (): I32 => {\n'
        f'    const root = "{root}";\n'
        f'    const nested_file = "{nested_file}";\n'
        '    const wrote = writeFile(path = nested_file, content = Blob(data = "data", size = 4));\n'
        '    const entries = listDir(path = root);\n'
        '    const info = stat(path = nested_file);\n'
        '    const root_exists = exists(path = root);\n'
        '    const root_is_dir = isDir(path = root);\n'
        '    const removed = removeDir(path = root, recursive = true);\n'
        '    const gone = !exists(path = root);\n'
        '    return (wrote && root_exists && root_is_dir && listLen<Str>(list = entries) > 0 && info.ok && info.value.size == 4 && info.value.modified > 1000000000000 && removed && gone) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fs_empty_path_returns_failure_values(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fs" import { readFile, writeFile, appendFile, removeFile, mkdir, removeDir, listDir, exists, isDir, stat, absPath };\n'
        'from "std/collections" import { listLen };\n'
        'from "std/str" import { strIsEmpty };\n'
        'const main = (): I32 => {\n'
        '    const empty = "";\n'
        '    const content = Blob(data = "x", size = 1);\n'
        '    const data = readFile(path = empty);\n'
        '    const names = listDir(path = empty);\n'
        '    const info = stat(path = empty);\n'
        '    const absolute = absPath(path = empty);\n'
        '    const ok = !writeFile(path = empty, content = content) && !appendFile(path = empty, content = content) && !removeFile(path = empty) && !mkdir(path = empty) && !removeDir(path = empty, recursive = true) && !exists(path = empty) && !isDir(path = empty);\n'
        '    return (ok && data.size == 0 && listLen<Str>(list = names) == 0 && !info.ok && strIsEmpty(s = absolute)) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fs_rejects_invalid_blob_writes(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    target = (tmp_path / "invalid-blob.bin").as_posix()
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fs" import { appendFile, exists, writeFile };\n'
        'from "std/test" import { testReset, testAssert, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const invalid = Blob(data = "", size = -1);\n'
        f'    const wrote = writeFile(path = "{target}", content = invalid);\n'
        f'    const appended = appendFile(path = "{target}", content = invalid);\n'
        f'    testAssert(condition = !wrote && !appended && !exists(path = "{target}"), msg = "invalid blob writes fail without creating file");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fs_mkdir_existing_directory_is_success(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    target_dir = (tmp_path / "mkdir-existing").as_posix()
    target_file = (tmp_path / "mkdir-file").as_posix()
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fs" import { isDir, mkdir, removeDir, writeFile };\n'
        'from "std/test" import { testReset, testAssert, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        f'    const first = mkdir(path = "{target_dir}");\n'
        f'    const second = mkdir(path = "{target_dir}");\n'
        f'    const still_dir = isDir(path = "{target_dir}");\n'
        f'    const wrote_file = writeFile(path = "{target_file}", content = Blob(data = "x", size = 1));\n'
        f'    const file_as_dir = mkdir(path = "{target_file}");\n'
        f'    const removed = removeDir(path = "{target_dir}", recursive = true);\n'
        '    testAssert(condition = first && second && still_dir && wrote_file && !file_as_dir && removed, msg = "mkdir existing directory is success");\n'
        '    return testFailed();\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_fs_abs_path_lexical_fallback_for_missing_path(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fs" import { absPath, exists };\n'
        'from "std/path" import { pathIsAbs };\n'
        'from "std/str" import { strContains, strStartsWith };\n'
        'const main = (): I32 => {\n'
        '    const missing = "missing-dir/../missing-file.txt";\n'
        '    const full = absPath(path = missing);\n'
        '    return (!exists(path = missing) && pathIsAbs(path = full) && !strContains(s = full, needle = "/../") && !strContains(s = full, needle = "\\\\..\\\\")) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_os_args_returns_process_arguments(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/os" import { args };\n'
        'from "std/collections" import { listLen };\n'
        'const main = (): I32 => {\n'
        '    const argv = args();\n'
        '    const count = listLen<Str>(list = argv);\n'
        '    return count > 0 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_os_native_env_platform_and_process_info(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/os" import { setEnv, env, cwd, pid, platform, arch };\n'
        'from "std/str" import { strEqual };\n'
        'const main = (): I32 => {\n'
        '    const changed = setEnv(key = "EZLANG_OS_TEST", value = "ok");\n'
        '    const value = env(key = "EZLANG_OS_TEST");\n'
        '    const empty_changed = setEnv(key = "", value = "bad");\n'
        '    const empty_value = env(key = "");\n'
        '    const dir = cwd();\n'
        '    const proc = pid();\n'
        '    const os_name = platform();\n'
        '    const arch_name = arch();\n'
        f'    const os_ok = strEqual(a = os_name, b = "{ez._native_os()}");\n'
        f'    const arch_ok = strEqual(a = arch_name, b = "{ez._native_arch()}");\n'
        '    return (changed && value.ok && strEqual(a = value.value, b = "ok") && !empty_changed && !empty_value.ok && dir != "" && proc > 0 && os_ok && arch_ok) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_std_collections_public_interfaces(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/collections" import { listLen, listPush, listPop, listShift, listUnshift, listSlice, listSort, listFilter, listMap, listFind, dictKeys, dictValues, dictHas, dictDelete, dictLen };\n'
        'from "std/str" import { strEqual };\n'
        'const pred = (item: I32): Bool => { return item >= 2; };\n'
        'const mapper = (item: I32): I64 => { return item + 10; };\n'
        'const cmp = (a: I32, b: I32): I32 => { return a - b; };\n'
        'const main = (): I32 => {\n'
        '    let nums: List<I32> = [3, 1, 2];\n'
        '    listPush<I32>(list = nums, item = 4);\n'
        '    listUnshift<I32>(list = nums, item = -1);\n'
        '    listSort<I32>(list = nums, cmp = cmp);\n'
        '    const first = listShift<I32>(list = nums);\n'
        '    const last = listPop<I32>(list = nums);\n'
        '    const found = listFind<I32>(list = nums, pred = pred);\n'
        '    let filtered: List<I32> = listFilter<I32>(list = nums, pred = pred);\n'
        '    let mapped: List<I64> = listMap<I32, I64>(list = filtered, f = mapper);\n'
        '    let sliced: List<I32> = listSlice<I32>(list = nums, start = 1, end = 3);\n'
        '    let meta = { name: Str = "ez", lang: Str = "EzLang" };\n'
        '    const lang = meta["lang"];\n'
        '    const has_name = dictHas<Str, Str>(dict = meta, key = "name");\n'
        '    let keys: List<Str> = dictKeys<Str, Str>(dict = meta);\n'
        '    let values: List<Str> = dictValues<Str, Str>(dict = meta);\n'
        '    const removed = dictDelete<Str, Str>(dict = meta, key = "name");\n'
        '    const missing = dictHas<Str, Str>(dict = meta, key = "name");\n'
        '    return (first.ok && first.value == -1 && last.ok && last.value == 4 && found.ok && found.value == 2 && listLen<I32>(list = nums) == 3 && listLen<I32>(list = filtered) == 2 && listLen<I64>(list = mapped) == 2 && listLen<I32>(list = sliced) == 2 && strEqual(a = lang, b = "EzLang") && has_name && listLen<Str>(list = keys) == 2 && listLen<Str>(list = values) == 2 && removed && !missing && dictLen<Str, Str>(dict = meta) == 1) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_dict_index_assignment_updates_and_inserts(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/collections" import { dictLen };\n'
        'from "std/str" import { strEqual };\n'
        'const main = (): I32 => {\n'
        '    let meta = { name = "old" };\n'
        '    meta["name"] = "EzLang";\n'
        '    meta["lang"] = "ez";\n'
        '    const name = meta["name"];\n'
        '    const lang = meta["lang"];\n'
        '    return (strEqual(a = name, b = "EzLang") && strEqual(a = lang, b = "ez") && dictLen<Str, Str>(dict = meta) == 2) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_shape_and_dynamic_shape_dict_literals(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'type FixedShape = { name: Str; side: Str; };\n'
        'type DynamicShape = { name: Str; [dynamic: Str]: Str; };\n'
        'const main = (): I32 => {\n'
        '    let fixed: FixedShape = { side = "10"; name = "Square" };\n'
        '    let dynamic: DynamicShape = { name = "Square"; side = "10" };\n'
        '    return (strEqual(a = fixed.name, b = "Square") && strEqual(a = fixed.side, b = "10") && strEqual(a = dynamic["side"], b = "10")) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_type_shape_spread_flattens_fields(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/str" import { strEqual };\n'
        'type Named = { name: Str; };\n'
        'type UserShape = { ...Named; age: I32; };\n'
        'const main = (): I32 => {\n'
        '    let u: UserShape = { age = 42; name = "s" };\n'
        '    return (strEqual(a = u.name, b = "s") && u.age == 42) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_dynamic_dict_expression_key_return_keeps_key_value_types(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const make = (): { [key: I32]: I32 } => {\n'
        '    return { [1] = 7, [2] = 9 };\n'
        '};\n'
        'const main = (): I32 => {\n'
        '    const meta = make();\n'
        '    return (meta[1] == 7 && meta[2] == 9) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_dict_index_compound_assignment(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    let counts = { hits = 2 };\n'
        '    counts["hits"] += 3;\n'
        '    return counts["hits"] == 5 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_run_dict_hash_index_handles_delete_and_reinsert(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/collections" import { dictDelete, dictHas, dictLen };\n'
        'const main = (): I32 => {\n'
        '    let values: { [key: I32]: I32 } = { [1] = 10, [2] = 20, [3] = 30, [4] = 40, [5] = 50, [6] = 60, [7] = 70, [8] = 80, [9] = 90 };\n'
        '    const before = values[9] == 90 && dictHas<I32, I32>(dict = values, key = 2);\n'
        '    const removed = dictDelete<I32, I32>(dict = values, key = 2);\n'
        '    values[10] = 100;\n'
        '    values[9] += 1;\n'
        '    const after = !dictHas<I32, I32>(dict = values, key = 2) && values[9] == 91 && values[10] == 100;\n'
        '    return (before && removed && after && dictLen<I32, I32>(dict = values) == 9) ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_output_sdk_is_parsed_and_exposed_to_plugins(tmp_path):
    project_toml = write_project(tmp_path, os_name="android", arch="aarch64")
    sdk_dir = tmp_path / "android-ndk"
    sdk_dir.mkdir()
    clang = sdk_dir / "toolchains" / "llvm" / "prebuilt" / ez._ndk_host_tag() / "bin" / "aarch64-linux-android21-clang"
    _write_fake_sdk_tool(clang)
    plugin = tmp_path / "plugin.py"
    plugin.write_text(
        'from pathlib import Path\n'
        'def before_build(context):\n'
        '    Path(context["root"], "sdk.txt").write_text(context["output"]["sdk"] or "", encoding="utf-8")\n',
        encoding="utf-8",
    )
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('dir = "dist/android"', f'dir = "dist/android"\nsdk = "{sdk_dir}"')
        + '\n[[plugins]]\nname = "./plugin.py"\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    assert (tmp_path / "sdk.txt").read_text(encoding="utf-8") == str(sdk_dir)


def _write_fake_sdk_tool(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[0]).with_name('calls.txt').open('a', encoding='utf-8').write(' '.join(sys.argv[1:]) + '\\n')\n"
        "out = None\n"
        "for i, arg in enumerate(sys.argv):\n"
        "    if arg == '-o' and i + 1 < len(sys.argv):\n"
        "        out = sys.argv[i + 1]\n"
        "if out:\n"
        "    Path(out).parent.mkdir(parents=True, exist_ok=True)\n"
        "    Path(out).write_bytes(b'fake')\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_build_emcc_uses_sdk_and_js_libraries(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="emcc", arch="wasm32")
    sdk_dir = tmp_path / "emsdk"
    emcc = sdk_dir / "emcc"
    _write_fake_sdk_tool(emcc)
    libs_dir = tmp_path / "libs"
    libs_dir.mkdir()
    js_lib = libs_dir / "bindings.js"
    js_lib.write_text("mergeInto(LibraryManager.library, {});\n", encoding="utf-8")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('dir = "dist/emcc"', f'dir = "dist/emcc"\nsdk = "{sdk_dir}"')
        + '\n[extern]\nsearch_paths = ["libs"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'extern "bindings.js" for emcc;\nconst main = (): I32 => { return 0; };\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    artifact = tmp_path / "dist" / "emcc" / "demo.js"
    assert artifact.exists()
    assert "sdk artifact:" in out
    calls = (emcc.parent / "calls.txt").read_text(encoding="utf-8")
    assert "--js-library" in calls
    assert str(js_lib) in calls


def test_build_emcc_flow_parallel_uses_asyncify_runtime(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="emcc", arch="wasm32")
    sdk_dir = tmp_path / "emsdk"
    emcc = sdk_dir / "emcc"
    _write_fake_sdk_tool(emcc)
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('dir = "dist/emcc"', f'dir = "dist/emcc"\nsdk = "{sdk_dir}"'),
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    const result = flow {\n'
        '        const p = parallel { return 7; };\n'
        '        return p + race(pl = [() => { return 1; }, () => { return 2; }], timeout = 10);\n'
        '    };\n'
        '    return result == 8 ? 0 : 1;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    artifact = tmp_path / "dist" / "emcc" / "demo.js"
    assert artifact.exists()
    assert "sdk artifact:" in out
    calls = (emcc.parent / "calls.txt").read_text(encoding="utf-8")
    assert "-sASYNCIFY" in calls
    assert "runtime.js" in calls
    assert "runtime.c" not in calls
    assert "pthread" not in calls


def test_emcc_asyncify_detection_accepts_relative_std_paths():
    assert ez._emcc_needs_asyncify(["packages/std/emcc/runtime.js"])
    assert ez._emcc_needs_asyncify(["packages/std/emcc/time.js"])
    assert ez._emcc_needs_asyncify(["packages/std/emcc/net/http.js"])
    assert ez._emcc_needs_asyncify(["packages/std/emcc/io.js"])
    assert ez._emcc_needs_asyncify(["packages/std/emcc/fs.js"])
    assert ez._emcc_needs_asyncify(["packages/std/emcc/stream.js"])
    assert ez._emcc_needs_asyncify(["packages/std/emcc/process.js"])
    assert ez._emcc_needs_asyncify(["packages/std/emcc/compress.js"])
    assert ez._emcc_needs_asyncify(["packages/std/emcc/net/tcp.js"])
    assert ez._emcc_needs_asyncify(["packages/std/emcc/net/ws.js"])
    assert not ez._emcc_needs_asyncify(["packages/std/emcc/platform.js"])


def test_build_android_sdk_compiles_c_extern_and_links_artifact(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="android", arch="aarch64")
    sdk_dir = tmp_path / "android-ndk"
    clang = sdk_dir / "toolchains" / "llvm" / "prebuilt" / ez._ndk_host_tag() / "bin" / "aarch64-linux-android21-clang"
    _write_fake_sdk_tool(clang)
    libs_dir = tmp_path / "libs"
    libs_dir.mkdir()
    (libs_dir / "native.c").write_text("int native_answer(void) { return 0; }\n", encoding="utf-8")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('dir = "dist/android"', f'dir = "dist/android"\nsdk = "{sdk_dir}"')
        + '\n[extern]\nsearch_paths = ["libs"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'extern "native.c" for android;\n'
        'declare const native_answer: () => I32;\n'
        'const main = (): I32 => { return native_answer(); };\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    artifact = tmp_path / "dist" / "android" / "libdemo.so"
    assert artifact.exists()
    assert "sdk artifact:" in out
    calls = (clang.parent / "calls.txt").read_text(encoding="utf-8")
    assert "-DEZ_TARGET_ANDROID=1" in calls
    assert "-shared" in calls


def test_build_android_flow_runtime_links_native_helpers(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="android", arch="aarch64")
    sdk_dir = tmp_path / "android-ndk"
    clang = sdk_dir / "toolchains" / "llvm" / "prebuilt" / ez._ndk_host_tag() / "bin" / "aarch64-linux-android21-clang"
    _write_fake_sdk_tool(clang)
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('dir = "dist/android"', f'dir = "dist/android"\nsdk = "{sdk_dir}"'),
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        const p = parallel { return 7; };\n'
        '        return p + race(pl = [() => { return 1; }, () => { return 2; }], timeout = 10);\n'
        '    };\n'
        '    return value;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    capsys.readouterr()
    calls = (clang.parent / "calls.txt").read_text(encoding="utf-8")
    assert "runtime.c" in calls
    assert "-lpthread" in calls


def test_build_android_ui_sdk_emits_host_bridge(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="android", arch="aarch64")
    sdk_dir = tmp_path / "android-ndk"
    clang = sdk_dir / "toolchains" / "llvm" / "prebuilt" / ez._ndk_host_tag() / "bin" / "aarch64-linux-android21-clang"
    _write_fake_sdk_tool(clang)
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('dir = "dist/android"', f'dir = "dist/android"\nsdk = "{sdk_dir}"'),
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "ez-android-ui" import { createTextView, setText, addView, getRootView };\n'
        'const main = (): I32 => {\n'
        '    const label = createTextView();\n'
        '    setText(node = label, text = "hello");\n'
        '    addView(parent = getRootView(), child = label);\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    bridge = tmp_path / "dist" / "android" / "ez-android-ui-bridge"
    assert "ui bridge:" in out
    assert (bridge / "app" / "src" / "main" / "AndroidManifest.xml").exists()
    assert (bridge / "app" / "src" / "main" / "jniLibs" / "arm64-v8a" / "libdemo.so").exists()
    activity = bridge / "app" / "src" / "main" / "java" / "dev" / "ezlang" / "EzLangActivity.kt"
    activity_text = activity.read_text(encoding="utf-8")
    assert 'System.loadLibrary("demo")' in activity_text
    assert "ezAndroidSetScreenMetrics(metrics.widthPixels, metrics.heightPixels, metrics.density)" in activity_text
    calls = (clang.parent / "calls.txt").read_text(encoding="utf-8")
    assert "android_jni_entry.c" in calls
    jni_entry = tmp_path / "dist" / "android" / ".ez" / "android_jni_entry.c"
    assert "Java_dev_ezlang_EzLangActivity_ezAndroidSetScreenMetrics" in jni_entry.read_text(encoding="utf-8")


def test_build_ios_sdk_compiles_c_extern_and_links_artifact(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="ios", arch="aarch64")
    sdk_dir = tmp_path / "xcode-sdk"
    clang = sdk_dir / "usr" / "bin" / "clang"
    _write_fake_sdk_tool(clang)
    libs_dir = tmp_path / "libs"
    libs_dir.mkdir()
    (libs_dir / "native.c").write_text("int native_answer(void) { return 0; }\n", encoding="utf-8")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('dir = "dist/ios"', f'dir = "dist/ios"\nsdk = "{sdk_dir}"')
        + '\n[extern]\nsearch_paths = ["libs"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'extern "native.c" for ios;\n'
        'declare const native_answer: () => I32;\n'
        'const main = (): I32 => { return native_answer(); };\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    artifact = tmp_path / "dist" / "ios" / "libdemo.dylib"
    assert artifact.exists()
    assert "sdk artifact:" in out
    calls = (clang.parent / "calls.txt").read_text(encoding="utf-8")
    assert "-DEZ_TARGET_IOS=1" in calls
    assert "-dynamiclib" in calls


def test_build_ios_flow_runtime_links_native_helpers(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="ios", arch="aarch64")
    sdk_dir = tmp_path / "xcode-sdk"
    clang = sdk_dir / "usr" / "bin" / "clang"
    _write_fake_sdk_tool(clang)
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('dir = "dist/ios"', f'dir = "dist/ios"\nsdk = "{sdk_dir}"'),
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'const main = (): I32 => {\n'
        '    const value = flow {\n'
        '        const p = parallel { return 7; };\n'
        '        return p + race(pl = [() => { return 1; }, () => { return 2; }], timeout = 10);\n'
        '    };\n'
        '    return value;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    capsys.readouterr()
    calls = (clang.parent / "calls.txt").read_text(encoding="utf-8")
    assert "runtime.c" in calls
    assert "-lpthread" in calls


def test_build_ios_ui_sdk_emits_host_bridge(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="ios", arch="aarch64")
    sdk_dir = tmp_path / "xcode-sdk"
    clang = sdk_dir / "usr" / "bin" / "clang"
    _write_fake_sdk_tool(clang)
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('dir = "dist/ios"', f'dir = "dist/ios"\nsdk = "{sdk_dir}"'),
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "ez-ios-ui" import { createLabel, setText, addSubview, getRootView };\n'
        'const main = (): I32 => {\n'
        '    const label = createLabel();\n'
        '    setText(node = label, text = "hello");\n'
        '    addSubview(parent = getRootView(), child = label);\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    bridge = tmp_path / "dist" / "ios" / "ez-ios-ui-bridge"
    assert "ui bridge:" in out
    assert (bridge / "Package.swift").exists()
    assert (bridge / "Libraries" / "libdemo.dylib").exists()
    view_controller = bridge / "Sources" / "EzLangBridge" / "EzLangViewController.swift"
    view_controller_text = view_controller.read_text(encoding="utf-8")
    assert "ezlangMain" in view_controller_text
    assert "ezIosSetScreenMetrics" in view_controller_text
    assert "Float(bounds.width)" in view_controller_text


def test_build_sdk_reports_missing_tool(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="emcc", arch="wasm32")
    sdk_dir = tmp_path / "emsdk"
    sdk_dir.mkdir()
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('dir = "dist/emcc"', f'dir = "dist/emcc"\nsdk = "{sdk_dir}"'),
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text('const main = (): I32 => { return 0; };\n', encoding="utf-8")

    assert ez.main(["build", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "output.sdk 缺少工具" in err


def test_run_non_native_target_errors(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="emcc", arch="wasm32")

    assert ez.main(["run", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "ez run only supports native target" in err


def test_run_native_executes_binary_and_returns_exit_code(tmp_path, capsys):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        "const main = (): I32 => { return 7; };\n",
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 7

    captured = capsys.readouterr()
    assert 'ModuleID = "demo"' not in captured.out
    assert "native execution backend not implemented" not in captured.err
    assert (tmp_path / "dist" / ez._native_os() / "demo").exists()


def test_run_prefers_native_arch_when_multiple_same_os_outputs(tmp_path, capsys):
    other_arch = "aarch64" if ez._native_arch() == "x86_64" else "x86_64"
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.ez").write_text("const main = (): I32 => { return 0; };\n", encoding="utf-8")
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        f"""
[project]
name = "demo"
version = "0.1.0"
main = "src/index.ez"

[[output]]
arch = "{other_arch}"
os = "{ez._native_os()}"
dir = "dist/wrong-arch"

[[output]]
arch = "{ez._native_arch()}"
os = "{ez._native_os()}"
dir = "dist/native"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0

    assert (tmp_path / "dist" / "native" / "demo").exists()
    assert not (tmp_path / "dist" / "wrong-arch" / "demo").exists()


def test_run_accepts_single_ez_file_without_project(tmp_path, monkeypatch):
    source = tmp_path / "exit_code.ez"
    source.write_text("const main = (): I32 => { return 5; };\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert ez.main(["run", "exit_code.ez"]) == 5

    exe_file = tmp_path / ".ez" / "run" / "exit_code" / "exit_code"
    assert exe_file.exists()


def test_install_prints_validation_plan(tmp_path, capsys):
    (tmp_path / "local.ez").write_text("let x: I32 = 1;\n", encoding="utf-8")
    (tmp_path / "packages" / "lib").mkdir(parents=True)
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[deps]
local = "./local.ez"
workspace = "@workspace"

[workspace]
members = ["packages/*"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["install", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    assert "local local" in out
    assert "workspace workspace" in out


def test_root_install_script_supports_git_bootstrap_and_path_registration():
    script = (ROOT / "install.sh").read_text(encoding="utf-8")
    for marker in [
        "https://github.com/ZYF93/EzLang.git",
        "--local",
        "EZLANG_INSTALL_DEPS",
        "require_python",
        "require_git",
        "require_native_linker",
        "dependency_hint",
        "install_dependency",
        "git clone",
        "remote set-url origin",
        "remote add origin",
        "git -C",
        "-m venv",
        "pip install -e",
        "import llvmlite.binding",
        "无需单独安装系统 LLVM",
        "只有构建 os=\\\"emcc\\\" / wasm32 目标时才需要 Emscripten SDK",
        "Android 目标需要 Android NDK",
        "iOS 目标需要 macOS + Xcode Command Line Tools",
        "ez\" --version",
        "ez\" install --project",
        "ez\" build --project",
        "<<'EOF'\nlet $code",
        "EZLANG_REGISTER_PATH",
        "EZLANG_HOME",
        "PROFILE_SNIPPET",
        ".zshrc",
        ".zprofile",
        ".bashrc",
        ".bash_profile",
        ".profile",
        "export PATH=",
    ]:
        assert marker in script
    assert "REPO_URL=$DEFAULT_REPO_URL" in script
    assert "不支持自定义仓库参数" in script
    assert "EZLANG_REPO_URL" not in script

    ordered_markers = [
        "git clone",
        "-m venv",
        "pip install -e",
        "ez\" --version",
        "ez\" install --project",
        "ez\" build --project",
        "    register_shell_profiles",
    ]
    positions = [script.index(marker) for marker in ordered_markers]
    assert positions == sorted(positions)


def test_root_install_script_rejects_custom_repo_argument():
    completed = subprocess.run(
        ["sh", str(ROOT / "install.sh"), "https://example.com/mirror.git"],
        text=True,
        capture_output=True,
    )
    assert completed.returncode != 0
    assert "不支持自定义仓库参数" in completed.stderr
    assert "https://github.com/ZYF93/EzLang.git" in completed.stderr



def test_install_downloads_remote_version_dependency(tmp_path, capsys):
    registry = tmp_path / "registry"
    package = registry / "remote" / "1.2.3"
    package.mkdir(parents=True)
    (package / "remote.ez").write_text("export let answer: I32 = 42;\n", encoding="utf-8")
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        f"""
[project]
name = "demo"
version = "0.1.0"
registry = "{registry}"

[deps]
remote = "1.2.3"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["install", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    installed = tmp_path / ".ez" / "deps" / "remote" / "1.2.3" / "remote.ez"
    assert installed.read_text(encoding="utf-8") == "export let answer: I32 = 42;\n"
    assert f"remote remote 1.2.3 {installed.parent}" in out



def test_install_extracts_released_zip_dependency(tmp_path, capsys):
    registry = tmp_path / "registry"
    package = registry / "remote" / "1.2.3"
    package.mkdir(parents=True)
    with zipfile.ZipFile(package / "remote-1.2.3.zip", "w") as archive:
        archive.writestr("project.toml", '[project]\nname = "remote"\nversion = "1.2.3"\nmain = "src/index.ez"\n')
        archive.writestr("src/index.ez", "export let answer: I32 = 42;\n")
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        f"""
[project]
name = "demo"
version = "0.1.0"
registry = "{registry}"

[deps]
remote = "1.2.3"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["install", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    installed = tmp_path / ".ez" / "deps" / "remote" / "1.2.3"
    assert (installed / "project.toml").exists()
    assert (installed / "src" / "index.ez").read_text(encoding="utf-8") == "export let answer: I32 = 42;\n"
    assert f"remote remote 1.2.3 {installed}" in out


def test_install_global_installs_remote_dependency_to_ezlang_home(tmp_path, monkeypatch, capsys):
    ez_home = tmp_path / "home"
    monkeypatch.setenv("EZLANG_HOME", str(ez_home))
    registry = tmp_path / "registry"
    package = registry / "remote" / "1.2.3"
    package.mkdir(parents=True)
    with zipfile.ZipFile(package / "remote-1.2.3.zip", "w") as archive:
        archive.writestr("index.ez", "export let answer: I32 = 42;\n")
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        f"""
[project]
name = "demo"
version = "0.1.0"
registry = "{registry}"

[deps]
remote = "1.2.3"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["install", "-g", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    installed = ez_home / "deps" / "remote" / "1.2.3"
    assert (installed / "index.ez").read_text(encoding="utf-8") == "export let answer: I32 = 42;\n"
    assert f"remote remote 1.2.3 {installed}" in out


def test_build_resolves_global_versioned_dependency(tmp_path, monkeypatch, capsys):
    ez_home = tmp_path.parent / f"{tmp_path.name}-home"
    monkeypatch.setenv("EZLANG_HOME", str(ez_home))
    dep_dir = ez_home / "deps" / "utils" / "1.2.3"
    dep_dir.mkdir(parents=True)
    (dep_dir / "index.ez").write_text("export let answer: I32 = 7;\n", encoding="utf-8")
    project_toml = write_project(tmp_path, os_name="linux")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[deps]\nutils = "1.2.3"\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "utils" import { answer };\nlet x: I32 = answer;\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    assert str(dep_dir / "index.ez") in out


def test_install_global_rejects_local_dependencies(tmp_path, capsys):
    (tmp_path / "local.ez").write_text("let x: I32 = 1;\n", encoding="utf-8")
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[deps]
local = "./local.ez"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["install", "-g", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "本地路径依赖" in err


@pytest.mark.parametrize("member_name", ["../escape.ez", "dir\\escape.ez", "C:/escape.ez"])
def test_install_rejects_zip_path_traversal(tmp_path, capsys, member_name):
    registry = tmp_path / "registry"
    package = registry / "remote" / "1.2.3"
    package.mkdir(parents=True)
    with zipfile.ZipFile(package / "remote-1.2.3.zip", "w") as archive:
        archive.writestr(member_name, "let bad = 1;\n")
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        f"""
[project]
name = "demo"
version = "0.1.0"
registry = "{registry}"

[deps]
remote = "1.2.3"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["install", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "非法路径" in err



def test_install_remote_dependency_requires_registry(tmp_path, capsys):
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[deps]
remote = "1.2.3"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["install", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "registry" in err


def test_fmt_check_parses_ez_files(tmp_path, capsys):
    project_toml = write_project(tmp_path)
    source = tmp_path / "src" / "index.ez"

    assert ez.main(["fmt", "--project", str(project_toml), "--check", str(source)]) == 0

    out = capsys.readouterr().out
    assert "checked 1 file" in out



def test_fmt_rewrites_single_file(tmp_path, capsys):
    project_toml = write_project(tmp_path)
    source = tmp_path / "src" / "index.ez"
    source.write_text("let   $x:I32=1;\nconst main=():I32=>{return $x;}\n", encoding="utf-8")

    assert ez.main(["fmt", "--project", str(project_toml), str(source)]) == 0

    assert source.read_text(encoding="utf-8") == "let $x: I32 = 1;\nconst main = (): I32 => {\n    return $x;\n}\n"
    out = capsys.readouterr().out
    assert "formatted 1 file" in out



def test_fmt_formats_multiple_files_in_directory(tmp_path, capsys):
    project_toml = write_project(tmp_path)
    first = tmp_path / "src" / "a.ez"
    second = tmp_path / "src" / "b.ez"
    first.write_text("let   a:I32=1;\n", encoding="utf-8")
    second.write_text("let   b:I32=2;\n", encoding="utf-8")

    assert ez.main(["fmt", "--project", str(project_toml), str(tmp_path / "src")]) == 0

    assert first.read_text(encoding="utf-8") == "let a: I32 = 1;\n"
    assert second.read_text(encoding="utf-8") == "let b: I32 = 2;\n"
    out = capsys.readouterr().out
    assert "formatted 3 files" in out



def test_fmt_check_reports_unformatted_without_rewriting(tmp_path, capsys):
    project_toml = write_project(tmp_path)
    source = tmp_path / "src" / "index.ez"
    original = "let   x:I32=1;\n"
    source.write_text(original, encoding="utf-8")

    assert ez.main(["fmt", "--project", str(project_toml), "--check", str(source)]) == 1

    assert source.read_text(encoding="utf-8") == original
    err = capsys.readouterr().err
    assert "需要格式化" in err


def test_release_dry_run_validates_metadata(tmp_path, capsys):
    project_toml = write_project(tmp_path)

    assert ez.main(["release", "--project", str(project_toml), "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "release dry-run demo 0.1.0" in out


def test_release_packs_and_publishes_to_local_registry(tmp_path, capsys):
    registry = tmp_path / "registry"
    project_toml = write_project(tmp_path)
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('registry = "local"', f'registry = "{registry}"'),
        encoding="utf-8",
    )
    (tmp_path / "README.tmp").write_text("ignored\n", encoding="utf-8")

    assert ez.main(["release", "--project", str(project_toml)]) == 0

    package = registry / "demo" / "0.1.0" / "demo-0.1.0.zip"
    assert package.exists()
    with zipfile.ZipFile(package) as archive:
        assert sorted(archive.namelist()) == ["project.toml", "src/index.ez"]
        assert archive.read("src/index.ez").decode() == "let x: I32 = 42;\n"
    out = capsys.readouterr().out
    assert f"released demo 0.1.0 {package}" in out



def test_release_posts_package_to_http_registry(tmp_path, monkeypatch, capsys):
    project_toml = write_project(tmp_path)
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('registry = "local"', 'registry = "https://registry.example"'),
        encoding="utf-8",
    )
    captured = {}

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["content_type"] = request.headers["Content-type"]
        captured["data"] = request.data

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"ok"

        return Response()

    monkeypatch.setattr(ez.urllib.request, "urlopen", fake_urlopen)

    assert ez.main(["release", "--project", str(project_toml)]) == 0

    assert captured["url"] == "https://registry.example/demo/0.1.0/demo-0.1.0.zip"
    assert captured["method"] == "PUT"
    assert captured["content_type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(captured["data"])) as archive:
        assert "project.toml" in archive.namelist()
        assert "src/index.ez" in archive.namelist()
    out = capsys.readouterr().out
    assert "released demo 0.1.0 https://registry.example/demo/0.1.0/demo-0.1.0.zip" in out



def test_release_rejects_private_package(tmp_path, capsys):
    project_toml = write_project(tmp_path, public=False)

    assert ez.main(["release", "--project", str(project_toml), "--dry-run"]) == 1

    err = capsys.readouterr().err
    assert "public = false" in err
