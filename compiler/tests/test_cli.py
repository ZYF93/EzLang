"""ez CLI 工具链测试"""

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


def test_unknown_command_returns_error(capsys):
    assert ez.main(["missing"]) == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err


@pytest.mark.parametrize("command", ["build", "run", "test", "install", "fmt", "release"])
def test_subcommand_help(command, capsys):
    assert ez.main([command, "--help"]) == 0
    out = capsys.readouterr().out
    assert command in out


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
        'from "std/test" import { testReset, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const current = now();\n'
        '    const year = getYear(this = current);\n'
        '    const month = getMonth(this = current);\n'
        '    const day = getDay(this = current);\n'
        '    const hour = getHour(this = current);\n'
        '    const minute = getMinute(this = current);\n'
        '    const second = getSecond(this = current);\n'
        '    add(this = current, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\n'
        '    sub(this = current, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\n'
        '    const epoch = Date(timestamp = 0);\n'
        '    testEqualStr(actual = format(this = epoch, fmt = "YYYY-MM-DD HH:%M:SS"), expected = "1970-01-01 00:00:00", msg = "mixed time format");\n'
        '    testEqualStr(actual = format(this = epoch, fmt = "%Y-%m-%d %H:%M:%S"), expected = "1970-01-01 00:00:00", msg = "strftime time format");\n'
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
        '    const bad_i32 = parseInt(s = "bad");\n'
        '    const bad_f64 = parseF64(s = "bad");\n'
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
        '    testAssert(condition = !bad_i32.ok, msg = "parse i32 invalid");\n'
        '    testAssert(condition = !bad_f64.ok, msg = "parse f64 invalid");\n'
        '    return testFailed();\n'
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


def test_run_std_fmt_json_and_msgpack_basic_roundtrip(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/fmt" import { jsonStringify, jsonParse, msgpackEncode, msgpackDecode };\n'
        'from "std/test" import { testReset, testAssert, testEqualI64, testEqualStr, testFailed };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    const json_i32 = jsonStringify<I32>(data = 42);\n'
        '    const parsed_i32 = jsonParse<I32>(s = json_i32);\n'
        '    const json_i64 = jsonStringify<I64>(data = 123456789);\n'
        '    const parsed_i64 = jsonParse<I64>(s = json_i64);\n'
        '    const json_bool = jsonStringify<Bool>(data = true);\n'
        '    const parsed_bool = jsonParse<Bool>(s = json_bool);\n'
        '    const json_str = jsonStringify<Str>(data = "EzLang");\n'
        '    const parsed_str = jsonParse<Str>(s = json_str);\n'
        '    const packed = msgpackEncode<I64>(data = parsed_i64);\n'
        '    const unpacked = msgpackDecode<I64>(data = packed);\n'
        '    const packed_bool = msgpackEncode<Bool>(data = parsed_bool);\n'
        '    const unpacked_bool = msgpackDecode<Bool>(data = packed_bool);\n'
        '    const packed_str = msgpackEncode<Str>(data = parsed_str);\n'
        '    const unpacked_str = msgpackDecode<Str>(data = packed_str);\n'
        '    const packed_f64 = msgpackEncode<F64>(data = 3.0);\n'
        '    const unpacked_f64 = msgpackDecode<F64>(data = packed_f64);\n'
        '    testEqualI64(actual = parsed_i32, expected = 42, msg = "json i32");\n'
        '    testEqualI64(actual = parsed_i64, expected = 123456789, msg = "json i64");\n'
        '    testAssert(condition = parsed_bool, msg = "json bool");\n'
        '    testEqualStr(actual = parsed_str, expected = "EzLang", msg = "json str");\n'
        '    testEqualI64(actual = unpacked, expected = 123456789, msg = "msgpack i64");\n'
        '    testAssert(condition = unpacked_bool, msg = "msgpack bool");\n'
        '    testEqualStr(actual = unpacked_str, expected = "EzLang", msg = "msgpack str");\n'
        '    testAssert(condition = unpacked_f64 == 3.0, msg = "msgpack f64");\n'
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
        '    testEqualStr(actual = strReplace(s = "Ez Ez", old = "Ez", newValue = "Easy"), expected = "Easy Easy", msg = "replace all");\n'
        '    testEqualStr(actual = strToLower(s = "EzLANG"), expected = "ezlang", msg = "lower ascii");\n'
        '    testEqualStr(actual = strToUpper(s = "EzLang"), expected = "EZLANG", msg = "upper ascii");\n'
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
        '    const decoded = pathFromFileUrl(url = "file:///tmp/Ez%20Lang/main.ez");\n'
        '    testAssert(condition = decoded.ok, msg = "file url decode ok");\n'
        '    testEqualStr(actual = decoded.value, expected = "/tmp/Ez Lang/main.ez", msg = "file url decodes spaces");\n'
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
        '    const nanv = mathSqrt(value = -1.0);\n'
        '    const infv = mathLog(value = 0.0);\n'
        '    const sum = mathAddI64Checked(a = 1, b = 2);\n'
        '    const diff = mathSubI64Checked(a = 1, b = 2);\n'
        '    const product = mathMulI64Checked(a = 2, b = 3);\n'
        '    const quotient = mathDivI64Checked(a = 6, b = 3);\n'
        '    const add_overflow = mathAddI64Checked(a = 9223372036854775807, b = 1);\n'
        '    const mul_overflow = mathMulI64Checked(a = 3037000500, b = 3037000500);\n'
        '    const div_zero = mathDivI64Checked(a = 1, b = 0);\n'
        '    const narrowed = mathF64ToI32(value = 42.0);\n'
        '    const narrowed_i64 = mathF64ToI64(value = 42.0);\n'
        '    const too_wide = mathF64ToI32(value = 2147483648.0);\n'
        '    const back_to_f64 = mathI64ToF64(value = 42);\n'
        '    testEqualI64(actual = abs32, expected = 3, msg = "abs i32");\n'
        '    testEqualI64(actual = abs64, expected = 4, msg = "abs i64");\n'
        '    testEqualI64(actual = minv, expected = 2, msg = "min i32");\n'
        '    testEqualI64(actual = maxv, expected = 7, msg = "max i32");\n'
        '    testEqualI64(actual = clamped, expected = 5, msg = "clamp max");\n'
        '    testEqualI64(actual = swapped, expected = 1, msg = "clamp swapped bounds");\n'
        '    testEqualI64(actual = gcd, expected = 6, msg = "gcd");\n'
        '    testEqualI64(actual = lcm, expected = 24, msg = "lcm");\n'
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
        '    testAssert(condition = mathIsNaN(value = nanv), msg = "nan");\n'
        '    testAssert(condition = mathIsInf(value = infv), msg = "inf");\n'
        '    testAssert(condition = sum.ok && diff.ok && product.ok && quotient.ok, msg = "checked ok");\n'
        '    testEqualI64(actual = sum.value, expected = 3, msg = "checked add");\n'
        '    testEqualI64(actual = diff.value, expected = -1, msg = "checked sub");\n'
        '    testEqualI64(actual = product.value, expected = 6, msg = "checked mul");\n'
        '    testEqualI64(actual = quotient.value, expected = 2, msg = "checked div");\n'
        '    testAssert(condition = !add_overflow.ok && !mul_overflow.ok && !div_zero.ok, msg = "checked rejects invalid");\n'
        '    testAssert(condition = narrowed.ok && narrowed_i64.ok && !too_wide.ok, msg = "float convert ok flags");\n'
        '    testEqualI64(actual = narrowed.value, expected = 42, msg = "f64 to i32");\n'
        '    testEqualI64(actual = narrowed_i64.value, expected = 42, msg = "f64 to i64");\n'
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
        'from "std/random" import { randomSeed, randomNextU32, randomNextU64, randomRangeI64, randomRangeF64, randomShuffleBytes, randomSecureBytes, randomSecureU64 };\n'
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
        '    const empty_secure = randomSecureBytes(size = 0);\n'
        '    const bad_secure = randomSecureBytes(size = -1);\n'
        '    const secure = randomSecureBytes(size = 8);\n'
        '    const secure64 = randomSecureU64();\n'
        '    testEqualI64(actual = n32, expected = 833678567, msg = "seeded u32 stable");\n'
        '    testEqualI64(actual = same_n32, expected = 833678567, msg = "same seed stable");\n'
        '    testEqualI64(actual = n64, expected = -8068018748417085693, msg = "seeded u64 bits stable");\n'
        '    testEqualI64(actual = ranged_i, expected = 10, msg = "range i64 swaps bounds");\n'
        '    testAssert(condition = ranged_f >= 0.0 && ranged_f < 1.0, msg = "range f64 swaps bounds");\n'
        '    testEqualI64(actual = shuffled.size, expected = 4, msg = "shuffle preserves byte count");\n'
        '    testAssert(condition = empty_secure.ok && empty_secure.value.size == 0 && !bad_secure.ok, msg = "secure byte edge sizes");\n'
        '    testAssert(condition = secure.ok && secure.value.size == 8, msg = "secure bytes from system entropy");\n'
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
        '    const invalid = uriDecodeQuery(s = "%zz");\n'
        '    testAssert(condition = !invalid.ok, msg = "invalid percent rejected");\n'
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
        'from "std/regex" import { regexGlobal, regexCompile, regexIsValid, regexTest, regexFind, regexFindAll, regexReplace, regexSplit };\n'
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
        '    const all = regexFindAll(regex = word, input = "one two three");\n'
        '    testEqualI64(actual = all.length, expected = 3, msg = "regex find all length");\n'
        '    testEqualStr(actual = all[2], expected = "three", msg = "regex find all value");\n'
        '    const first_only = regexReplace(regex = regexCompile(pattern = "[[:digit:]]", flags = 0), input = "a1b2c3", replacement = "#");\n'
        '    testEqualStr(actual = first_only, expected = "a#b2c3", msg = "regex replace first");\n'
        '    const all_digits = regexReplace(regex = regexCompile(pattern = "[[:digit:]]", flags = regexGlobal), input = "a1b2c3", replacement = "#");\n'
        '    testEqualStr(actual = all_digits, expected = "a#b#c#", msg = "regex replace global");\n'
        '    const parts = regexSplit(regex = regexCompile(pattern = ",", flags = regexGlobal), input = "a,b,c");\n'
        '    testEqualI64(actual = parts.length, expected = 3, msg = "regex split length");\n'
        '    testEqualStr(actual = parts[1], expected = "b", msg = "regex split middle");\n'
        '    const invalid = regexCompile(pattern = "(", flags = 0);\n'
        '    testAssert(condition = !regexIsValid(regex = invalid), msg = "invalid regex rejected");\n'
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
        if ez._native_os() == "macos"
        else '    testAssert(condition = !sha256.ok && !sha512.ok && !h256.ok && !h512.ok, msg = "crypto unavailable returns none");\n'
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
        'from "std/compress" import { compressGzip, decompressGzip, compressZlib, decompressZlib, compressDeflate, decompressDeflate };\n'
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
        '    const resp = fetch(url = "http://127.0.0.1/");\n'
        '    const server = createServer(host = "127.0.0.1", port = 0);\n'
        '    const tcp = tcpConnect(host = "127.0.0.1", port = 1);\n'
        '    const listener = tcpListen(host = "127.0.0.1", port = 0);\n'
        '    const udp = udpBind(host = "127.0.0.1", port = 0);\n'
        '    const ws = wsConnect(url = "ws://127.0.0.1/");\n'
        '    return (!resp.ok && server.handle == 0 && !tcp.ok && listener.ok && udp.ok && !ws.ok) ? 0 : 1;\n'
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
        'from "std/net/tcp" import { udpBind, udpSend, udpRecv, udpClose };\n'
        'const main = (): I32 => {\n'
        '    const socket = udpBind(host = "127.0.0.1", port = 0);\n'
        f'    const sent = udpSend(socket = socket.value, host = "127.0.0.1", port = {port}, data = Blob(data = "u", size = 1));\n'
        '    const chunk = udpRecv(socket = socket.value, maxBytes = 8);\n'
        '    const closed = udpClose(socket = socket.value);\n'
        '    return (socket.ok && sent == 1 && chunk.ok && chunk.value.size == 3 && closed) ? 0 : 1;\n'
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
                conn.recv(2048)
                conn.sendall(
                    b"HTTP/1.1 101 Switching Protocols\r\n"
                    b"Upgrade: websocket\r\n"
                    b"Connection: Upgrade\r\n\r\n"
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
        f'    const conn = wsConnect(url = "ws://127.0.0.1:{port}/ws");\n'
        '    return (conn.ok && conn.value.handle != 0) ? 0 : 1;\n'
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
                conn.recv(2048)
                conn.sendall(
                    b"HTTP/1.1 101 Switching Protocols\r\n"
                    b"Upgrade: websocket\r\n"
                    b"Connection: Upgrade\r\n\r\n"
                )
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
        'const main = (): I32 => {\n'
        '    const err = catch {\n'
        '        throw Error(code = 9, message = "boom");\n'
        '    };\n'
        '    return err.code == 9 ? 0 : 1;\n'
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


def test_run_uncaught_throw_exits_nonzero(tmp_path):
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
            'from "ez-android-ui" import { createTextView, createButton, setText, getText, addView, getRootView, getChildCount, isMainThread, requestPermission };\n'
            'const main = (): I32 => {\n'
            '    const root = getRootView();\n'
            '    const label = createTextView();\n'
            '    const button = createButton();\n'
            '    setText(node = label, text = "hello");\n'
            '    addView(parent = root, child = label);\n'
            '    addView(parent = root, child = button);\n'
            '    return (root.id != 0 && label.id != 0 && button.id != 0 && getChildCount(parent = root) == 2 && strEqual(a = getText(node = label), b = "hello") && isMainThread() && !requestPermission(perm = "android.permission.CAMERA")) ? 0 : 1;\n'
            '};\n',
        ),
        (
            "ios",
            'from "std/str" import { strEqual };\n'
            'from "ez-ios-ui" import { createLabel, createButton, setText, getText, addSubview, getRootView, getSubviewCount, isMainThread, requestPermission };\n'
            'const main = (): I32 => {\n'
            '    const root = getRootView();\n'
            '    const label = createLabel();\n'
            '    const button = createButton();\n'
            '    setText(node = label, text = "hello");\n'
            '    addSubview(parent = root, child = label);\n'
            '    addSubview(parent = root, child = button);\n'
            '    return (root.id != 0 && label.id != 0 && button.id != 0 && getSubviewCount(parent = root) == 2 && strEqual(a = getText(node = label), b = "hello") && isMainThread() && !requestPermission(perm = "camera")) ? 0 : 1;\n'
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
        'const main = (): I32 => {\n'
        '    const args: Str[] = ["-c", "printf hello"];\n'
        '    const exit_args: Str[] = ["-c", "exit 0"];\n'
        '    const envs: Str[] = ["EZLANG_PROCESS_TEST=1"];\n'
        '    const empty: Str[] = [];\n'
        '    const result = processExec(command = Command(program = "/bin/sh", args = args, cwd = "", env = envs, stdin = Blob(data = "", size = 0)));\n'
        '    const stdout_size = result.value.stdout.size;\n'
        '    const current = processCurrentPath();\n'
        '    const proc = processSpawn(command = Command(program = "/bin/sh", args = exit_args, cwd = "", env = empty, stdin = Blob(data = "", size = 0)));\n'
        '    const waited = processWait(process = Process(handle = 0, pid = 0));\n'
        '    const killed = processTerminate(process = Process(handle = 0, pid = 0));\n'
        '    return 0;\n'
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
        '    const dir = cwd();\n'
        '    const proc = pid();\n'
        '    const os_name = platform();\n'
        '    const arch_name = arch();\n'
        f'    const os_ok = strEqual(a = os_name, b = "{ez._native_os()}");\n'
        f'    const arch_ok = strEqual(a = arch_name, b = "{ez._native_arch()}");\n'
        '    return (changed && value.ok && strEqual(a = value.value, b = "ok") && dir != "" && proc > 0 && os_ok && arch_ok) ? 0 : 1;\n'
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
    assert 'System.loadLibrary("demo")' in activity.read_text(encoding="utf-8")
    calls = (clang.parent / "calls.txt").read_text(encoding="utf-8")
    assert "android_jni_entry.c" in calls


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
    assert "ezlangMain" in view_controller.read_text(encoding="utf-8")


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
    source.write_text("let   x:I32=1;\nconst main=():I32=>{return x;}\n", encoding="utf-8")

    assert ez.main(["fmt", "--project", str(project_toml), str(source)]) == 0

    assert source.read_text(encoding="utf-8") == "let x: I32 = 1;\nconst main = (): I32 => {\n    return x;\n}\n"
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
