"""ez CLI 工具链测试"""

import os
import socket
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
        'const main = (): I32 => {\n'
        '    const current = now();\n'
        '    const year = getYear(this = current);\n'
        '    const month = getMonth(this = current);\n'
        '    const day = getDay(this = current);\n'
        '    const hour = getHour(this = current);\n'
        '    const minute = getMinute(this = current);\n'
        '    const second = getSecond(this = current);\n'
        '    add(this = current, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\n'
        '    sub(this = current, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\n'
        '    const text = format(this = current, fmt = "%Y-%m-%d");\n'
        '    return 0;\n'
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
        'from "std/fmt" import { parseInt, b64Encode, b64Decode, urlEncode, urlDecode };\n'
        'const main = (): I32 => {\n'
        '    const parsed = parseInt(s = "42");\n'
        '    const blob = Blob(data = "hello", size = 5);\n'
        '    const encoded = b64Encode(data = blob);\n'
        '    const decoded = b64Decode(s = encoded);\n'
        '    const url = urlEncode(s = "a b");\n'
        '    const raw = urlDecode(s = url);\n'
        '    return 0;\n'
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
        '    testEqualI64(actual = parsed_i32, expected = 42, msg = "json i32");\n'
        '    testEqualI64(actual = parsed_i64, expected = 123456789, msg = "json i64");\n'
        '    testAssert(condition = parsed_bool, msg = "json bool");\n'
        '    testEqualStr(actual = parsed_str, expected = "EzLang", msg = "json str");\n'
        '    testEqualI64(actual = unpacked, expected = 123456789, msg = "msgpack i64");\n'
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
        'from "std/str" import { strByteLen, strCharLen, strSliceChars, strCharAt, strToBytes, strFromBytes, strSplit, strJoin, strTrim, strReplace, strToLower, strToUpper };\n'
        'const main = (): I32 => {\n'
        '    const text = " EzLang ";\n'
        '    const byte_len = strByteLen(s = text);\n'
        '    const char_len = strCharLen(s = text);\n'
        '    const slice = strSliceChars(s = text, start = 1, end = 3);\n'
        '    const ch = strCharAt(s = text, index = 1);\n'
        '    const bytes = strToBytes(s = text);\n'
        '    const restored = strFromBytes(data = bytes);\n'
        '    const parts = strSplit(s = text, sep = " ");\n'
        '    const joined = strJoin(parts = parts, sep = "-");\n'
        '    const trimmed = strTrim(s = text);\n'
        '    const replaced = strReplace(s = text, old = "Ez", newValue = "Easy");\n'
        '    const lower = strToLower(s = text);\n'
        '    const upper = strToUpper(s = text);\n'
        '    return 0;\n'
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
        'from "std/math" import { mathAbsI32, mathGcdI64, mathSqrt, mathPow, mathAddI64Checked, mathF64ToI32 };\n'
        'const main = (): I32 => {\n'
        '    const abs32 = mathAbsI32(value = -3);\n'
        '    const gcd = mathGcdI64(a = 18, b = 24);\n'
        '    const root = mathSqrt(value = 4.0);\n'
        '    const power = mathPow(base = 2.0, exp = 8.0);\n'
        '    const sum = mathAddI64Checked(a = 1, b = 2);\n'
        '    const narrowed = mathF64ToI32(value = 42.0);\n'
        '    return 0;\n'
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
        'const main = (): I32 => {\n'
        '    let source = randomSeed(seed = 42);\n'
        '    const n32 = randomNextU32(this = source);\n'
        '    const n64 = randomNextU64(this = source);\n'
        '    const ranged_i = randomRangeI64(this = source, minValue = 1, maxValue = 10);\n'
        '    const ranged_f = randomRangeF64(this = source, minValue = 0.0, maxValue = 1.0);\n'
        '    const shuffled = randomShuffleBytes(this = source, data = Blob(data = "abcd", size = 4));\n'
        '    const secure = randomSecureBytes(size = 8);\n'
        '    const secure64 = randomSecureU64();\n'
        '    return 0;\n'
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
        'const main = (): I32 => {\n'
        '    const data = Blob(data = "hello", size = 5);\n'
        '    const h32 = hashFnv1a32(data = data);\n'
        '    const h64 = hashFnv1a64(data = data);\n'
        '    const sh32 = hashStrFnv1a32(s = "hello");\n'
        '    const sh64 = hashStrFnv1a64(s = "hello");\n'
        '    const combined = hashCombineU64(seed = h64, value = sh64);\n'
        '    const c1 = crc32(data = data);\n'
        '    const c2 = crc32Str(s = "hello");\n'
        '    return 0;\n'
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
        'const main = (): I32 => {\n'
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
        '    return 0;\n'
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


def test_run_links_std_debug_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/debug" import { debugPrint, debugAssert, debugLocation, debugRuntimeInfo, debugHex, debugStack };\n'
        'const main = (): I32 => {\n'
        '    debugPrint(msg = "hello");\n'
        '    debugAssert(condition = true, msg = "ok");\n'
        '    const loc = debugLocation(file = "main.ez", line = 1, column = 2);\n'
        '    const info = debugRuntimeInfo();\n'
        '    const hex = debugHex(data = Blob(data = "ab", size = 2));\n'
        '    const stack = debugStack();\n'
        '    return 0;\n'
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
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/log" import { logTrace, logDebug, logInfo, logWarn, logError, logTargetStderr, LogConfig, logDefaultConfig, logConfigure, logSetLevel, logWrite, logWriteFields, logWriteAt, logInfoMsg, logWarnMsg, logErrorMsg };\n'
        'const main = (): I32 => {\n'
        '    const cfg = logDefaultConfig();\n'
        '    logConfigure(config = LogConfig(minLevel = logDebug, target = logTargetStderr, includeTimestamp = true, includeLocation = true));\n'
        '    logSetLevel(level = logTrace);\n'
        '    logWrite(level = logInfo, msg = "hello");\n'
        '    logWriteFields(level = logWarn, msg = "warn", fields = ["key", "value"]);\n'
        '    logWriteAt(level = logError, msg = "err", file = "main.ez", line = 1, column = 2, fields = ["code", "1"]);\n'
        '    logInfoMsg(msg = "info");\n'
        '    logWarnMsg(msg = "warn");\n'
        '    logErrorMsg(msg = "error");\n'
        '    return 0;\n'
        '};\n',
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


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


def test_run_links_std_crypto_basic_native_functions(tmp_path):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        'from "std/crypto" import { cryptoSha256, cryptoSha512, cryptoHmacSha256, cryptoHmacSha512 };\n'
        'const main = (): I32 => {\n'
        '    const data = Blob(data = "hello", size = 5);\n'
        '    const key = Blob(data = "key", size = 3);\n'
        '    const sha256 = cryptoSha256(data = data);\n'
        '    const sha512 = cryptoSha512(data = data);\n'
        '    const h256 = cryptoHmacSha256(key = key, data = data);\n'
        '    const h512 = cryptoHmacSha512(key = key, data = data);\n'
        '    return 0;\n'
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
        'from "std/test" import { testReset, testAssert, testEqualI64, testNotEqualI64, testEqualStr, testSkip, testPassed, testFailed, testSkipped };\n'
        'const main = (): I32 => {\n'
        '    testReset();\n'
        '    testAssert(condition = true, msg = "truth");\n'
        '    testEqualI64(actual = 42, expected = 42, msg = "i64");\n'
        '    testNotEqualI64(actual = 1, expected = 2, msg = "neq");\n'
        '    testEqualStr(actual = "ez", expected = "ez", msg = "str");\n'
        '    testSkip(msg = "later");\n'
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
            'const main = (): I32 => {\n'
            f'    const resp = fetch(url = "http://127.0.0.1:{port}/hello");\n'
            '    return (resp.ok && resp.value.status == 200 && resp.value.body.size == 2) ? 0 : 1;\n'
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
        '    let q: U32 = a / b;\n'
        '    let r: U32 = a % b;\n'
        '    let s: U32 = a >> 1;\n'
        '    q /= b;\n'
        '    r %= b;\n'
        '    s >>= 1;\n'
        '    return q == 536870912 && r == 0 && s == 536870912 ? 0 : 1;\n'
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


def test_run_ui_native_placeholders_report_unsupported(tmp_path):
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
            'from "ez-android-ui" import { createTextView, requestPermission };\n'
            'const main = (): I32 => {\n'
            '    const node = createTextView();\n'
            '    return (node.id == 0 && !requestPermission(perm = "android.permission.CAMERA")) ? 0 : 1;\n'
            '};\n',
        ),
        (
            "ios",
            'from "ez-ios-ui" import { createLabel, requestPermission };\n'
            'const main = (): I32 => {\n'
            '    const node = createLabel();\n'
            '    return (node.id == 0 && !requestPermission(perm = "camera")) ? 0 : 1;\n'
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
        'from "std/test" import { testEqualI64 };\n'
        'const test_math = (): I32 => {\n'
        '    testEqualI64(actual = 2 + 2, expected = 4, msg = "math");\n'
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


def test_output_sdk_is_parsed_and_exposed_to_plugins(tmp_path):
    project_toml = write_project(tmp_path, os_name="android", arch="aarch64")
    sdk_dir = tmp_path / "android-ndk"
    sdk_dir.mkdir()
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
