"""编译器端到端测试"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "compiler" / "src"))

from cli import ez


def write_project(tmp_path: Path, source: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    main = src_dir / source.name
    shutil.copyfile(source, main)
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        f"""
[project]
name = "e2e"
version = "0.1.0"
main = "src/{source.name}"

[[output]]
arch = "{ez._native_arch()}"
os = "{ez._native_os()}"
dir = "dist/native"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return project_toml


def test_e2e_hello_builds_and_runs(tmp_path):
    project_toml = write_project(tmp_path, ROOT / "examples" / "hello.ez")

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    assert (tmp_path / "dist" / "native" / "e2e.ll").exists()
    assert ez.main(["run", "--project", str(project_toml)]) == 0



def test_e2e_top_level_statements_run_without_user_entrypoint(tmp_path):
    source = tmp_path / "top_level.ez"
    source.write_text(
        """
let x = 0;
match {
    (x == 0) ? x = 2,
    (true) ? x = 3
};
""".strip()
        + "\n",
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_e2e_std_io_imports_and_builds(tmp_path):
    source = tmp_path / "std_io.ez"
    source.write_text(
        'from "std/io" import { print, println, error, readLine };\n\nprint(msg = "hello");\nprintln(msg = "world");\nerror(msg = "oops");\nlet line = readLine();\n' ,
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare void @"print"' in ir_text
    assert 'declare void @"println"' in ir_text
    assert 'declare void @"error"' in ir_text
    assert 'declare {i1, i8*} @"readLine"' in ir_text


def test_e2e_std_fs_imports_and_builds(tmp_path):
    source = tmp_path / "std_fs.ez"
    source.write_text(
        'from "std/fs" import { readFile, writeFile, appendFile, removeFile, mkdir, removeDir, listDir, exists, isDir, stat, absPath };\n\nlet path = "tmp.txt";\nlet content = Blob(data = "hello", size = 5);\nlet ok_write = writeFile(path = path, content = content);\nlet ok_append = appendFile(path = path, content = content);\nlet blob = readFile(path = path);\nlet ok_exists = exists(path = path);\nlet ok_dir = isDir(path = path);\nlet info = stat(path = path);\nlet absolute = absPath(path = path);\nlet entries = listDir(path = ".");\nlet made = mkdir(path = "tmp-dir");\nlet removed_dir = removeDir(path = "tmp-dir", recursive = true);\nlet removed = removeFile(path = path);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare %"Blob" @"readFile"' in ir_text
    assert 'declare i1 @"writeFile"' in ir_text
    assert 'declare i1 @"exists"' in ir_text
    assert 'declare {i1, %"FileStat"} @"stat"' in ir_text


def test_e2e_std_os_imports_and_builds(tmp_path):
    source = tmp_path / "std_os.ez"
    source.write_text(
        'from "std/os" import { args, env, setEnv, cwd, exit, pid, platform, arch };\n\nlet argv = args();\nlet home = env(key = "HOME");\nlet changed = setEnv(key = "EZLANG_E2E", value = "1");\nlet here = cwd();\nlet process_id = pid();\nlet os_name = platform();\nlet arch_name = arch();\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare {i8***, i64, i64, i64} @"args"' in ir_text
    assert 'declare {i1, i8*} @"env"' in ir_text
    assert 'declare i1 @"setEnv"' in ir_text
    assert 'declare i8* @"cwd"' in ir_text
    assert 'declare void @"exit"' in ir_text
    assert 'declare i32 @"pid"' in ir_text
    assert 'declare i8* @"platform"' in ir_text
    assert 'declare i8* @"arch"' in ir_text


def test_e2e_std_time_imports_and_builds(tmp_path):
    source = tmp_path / "std_time.ez"
    source.write_text(
        'from "std/time" import { now, timestamp, sleep, getYear, getMonth, getDay, add, sub, format };\n\nlet current = now();\nlet ts = timestamp();\nsleep(ms = 1);\nlet year = getYear(this = current);\nlet month = getMonth(this = current);\nlet day = getDay(this = current);\nadd(this = current, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\nsub(this = current, year = 0, month = 1, day = 0, hour = 0, minute = 0, second = 0);\nlet formatted = format(this = current, fmt = "YYYY-MM-DD");\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare %"Date" @"now"' in ir_text
    assert 'declare i64 @"timestamp"' in ir_text
    assert 'declare void @"sleep"' in ir_text
    assert 'declare i32 @"getYear"' in ir_text
    assert 'declare void @"add"' in ir_text
    assert 'declare i8* @"format"' in ir_text


def test_e2e_std_net_http_client_imports_and_builds(tmp_path):
    source = tmp_path / "std_http_client.ez"
    source.write_text(
        'from "std/net/http" import { fetch, fetchEx, HttpRequest, HttpResponse };\n\nlet headers = { accept: Str = "application/json" };\nlet empty_body = Blob(data = "", size = 0);\nlet req = HttpRequest(method = "GET", url = "https://example.com", headers = headers, body = empty_body);\nlet res1 = fetch(url = "https://example.com");\nlet res2 = fetchEx(req = req);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert '%"HttpRequest" = type' in ir_text
    assert '%"HttpResponse" = type' in ir_text
    assert 'declare {i1, %"HttpResponse"} @"fetch"' in ir_text
    assert 'declare {i1, %"HttpResponse"} @"fetchEx"' in ir_text



def test_e2e_std_net_http_server_imports_and_builds(tmp_path):
    source = tmp_path / "std_http_server.ez"
    source.write_text(
        'from "std/net/http" import { createServer, HttpRequest, HttpResponse };\n\nlet server = createServer(host = "127.0.0.1", port = 8080);\nconst handler = (req: HttpRequest): HttpResponse => {\n    let headers = { contentType: Str = "text/plain" };\n    let body = Blob(data = "ok", size = 2);\n    return HttpResponse(status = 200, headers = headers, body = body);\n};\nserver.on(path = "/", handler = handler);\nserver.start();\nserver.stop();\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert '%"HttpServer" = type' in ir_text
    assert 'declare %"HttpServer" @"createServer"' in ir_text
    assert 'on' in ir_text
    assert 'start' in ir_text
    assert 'stop' in ir_text

def test_e2e_std_collections_unimplemented_calls_fail(tmp_path, capsys):
    source = tmp_path / "std_collections.ez"
    source.write_text(
        'from "std/collections" import { listLen };\n\nlet nums: List<I32> = [1, 2, 3];\nlet n = listLen<I32>(list = nums);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 1
    assert "标准库集合函数 'listLen' 尚未实现" in capsys.readouterr().err


def test_e2e_std_fmt_imports_and_builds(tmp_path):
    source = tmp_path / "std_fmt.ez"
    source.write_text(
        'from "std/fmt" import { toString, parseInt, parseI64, parseF64, format, b64Encode, b64Decode, jsonStringify, jsonParse, msgpackEncode, msgpackDecode, urlEncode, urlDecode };\n\nlet text = toString<I32>(value = 42);\nlet parsed_i32 = parseInt(s = "42");\nlet parsed_i64 = parseI64(s = "42");\nlet parsed_f64 = parseF64(s = "3.14");\nlet args: Str[] = ["EzLang"];\nlet formatted = format(template = "Hello %s", args = args);\nlet blob = Blob(data = "hello", size = 5);\nlet b64 = b64Encode(data = blob);\nlet decoded = b64Decode(s = b64);\nlet json = jsonStringify<I32>(data = 42);\nlet value = jsonParse<I32>(s = json);\nlet packed = msgpackEncode<I32>(data = value);\nlet unpacked = msgpackDecode<I32>(data = packed);\nlet encoded_url = urlEncode(s = "a b");\nlet decoded_url = urlDecode(s = encoded_url);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare i8* @"toString_I32"' in ir_text
    assert 'declare {i1, i32} @"parseInt"' in ir_text
    assert 'declare i8* @"format"' in ir_text
    assert 'declare i8* @"b64Encode"' in ir_text
    assert 'declare i8* @"jsonStringify_I32"' in ir_text
    assert 'declare i32 @"jsonParse_I32"' in ir_text
    assert 'declare i8* @"urlEncode"' in ir_text


def test_e2e_flow_example_builds_with_runtime_hooks(tmp_path):
    project_toml = write_project(tmp_path, ROOT / "examples" / "flow.ez")

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare void @"__ezrt_flow_enter"' in ir_text
    assert 'declare void @"__ezrt_flow_exit"' in ir_text
    assert 'declare void @"__ezrt_sleep"' in ir_text
    assert 'declare i32 @"__ezrt_race"' in ir_text
    assert 'call void @"__ezrt_flow_enter"' in ir_text
    assert 'call i32 @"__ezrt_race"' in ir_text



def test_e2e_multiplatform_build_outputs_ir(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.ez").write_text("let value = 42;\n", encoding="utf-8")
    targets = [
        ("x86_64", "linux"),
        ("x86_64", "windows"),
        ("aarch64", "android"),
        ("aarch64", "ios"),
        ("wasm32", "emcc"),
    ]
    native_target = (ez._native_arch(), ez._native_os())
    if native_target not in targets:
        targets.append(native_target)
    output_blocks = []
    for arch, os_name in targets:
        output_blocks.append(
            "[[output]]\n"
            f"arch = \"{arch}\"\n"
            f"os = \"{os_name}\"\n"
            f"dir = \"dist/{os_name}-{arch}\""
        )
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        "[project]\n"
        "name = \"multi\"\n"
        "version = \"0.1.0\"\n"
        "main = \"src/index.ez\"\n\n"
        + "\n\n".join(output_blocks)
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    for arch, os_name in targets:
        ir_file = tmp_path / "dist" / f"{os_name}-{arch}" / "multi.ll"
        assert ir_file.exists(), f"{os_name}/{arch}"
        ir_text = ir_file.read_text(encoding="utf-8")
        assert f'target triple = "{ez._target_triple(arch, os_name)}"' in ir_text


def test_e2e_native_target_runs(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.ez").write_text("let value = 42;\n", encoding="utf-8")
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        "[project]\n"
        "name = \"native_run\"\n"
        "version = \"0.1.0\"\n"
        "main = \"src/index.ez\"\n\n"
        "[[output]]\n"
        f"arch = \"{ez._native_arch()}\"\n"
        f"os = \"{ez._native_os()}\"\n"
        "dir = \"dist/native\"\n",
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 0


def test_e2e_emcc_fs_wrapper_uses_memfs_and_idbfs():
    fs_js = (ROOT / "packages" / "std" / "emcc" / "fs.js").read_text(encoding="utf-8")
    assert "FS.writeFile" in fs_js
    assert "FS.readFile" in fs_js
    assert "FS.mkdirTree" in fs_js
    assert "IDBFS" in fs_js
    assert "FS.syncfs" in fs_js


def test_e2e_std_platform_externs_cover_mobile_and_emcc(tmp_path, capsys):
    std_root = ROOT / "packages" / "std"
    cases = [
        ("io", 'from "std/io" import { print };\nprint(msg = "hello");\n', ["native/io.c", "emcc/io.js"]),
        ("fs", 'from "std/fs" import { exists };\nlet ok = exists(path = "tmp.txt");\n', ["native/fs.c", "emcc/fs.js"]),
        ("os", 'from "std/os" import { platform };\nlet os_name = platform();\n', ["native/os.c", "emcc/os.js"]),
        ("time", 'from "std/time" import { timestamp };\nlet ts = timestamp();\n', ["native/time.c", "emcc/time.js"]),
        ("fmt", 'from "std/fmt" import { urlEncode };\nlet encoded = urlEncode(s = "a b");\n', ["native/fmt.c", "emcc/fmt.js"]),
    ]

    for name, source, expected_libs in cases:
        case_dir = tmp_path / name
        src_dir = case_dir / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "index.ez").write_text(source, encoding="utf-8")
        project_toml = case_dir / "project.toml"
        project_toml.write_text(
            "[project]\n"
            f"name = \"std_platforms_{name}\"\n"
            "version = \"0.1.0\"\n"
            "main = \"src/index.ez\"\n\n"
            "[[output]]\n"
            "arch = \"aarch64\"\n"
            "os = \"android\"\n"
            "dir = \"dist/android\"\n\n"
            "[[output]]\n"
            "arch = \"aarch64\"\n"
            "os = \"ios\"\n"
            "dir = \"dist/ios\"\n\n"
            "[[output]]\n"
            "arch = \"wasm32\"\n"
            "os = \"emcc\"\n"
            "dir = \"dist/emcc\"\n",
            encoding="utf-8",
        )

        assert ez.main(["build", "--project", str(project_toml)]) == 0, name
        out = capsys.readouterr().out
        assert "extern libs:" in out, name
        for expected in expected_libs:
            assert str(std_root / expected) in out, f"{name}: {expected}"

def test_e2e_examples_build_to_ir(tmp_path):
    for name in [
        "types.ez",
        "structs.ez",
        "functions.ez",
        "control.ez",
        "operators.ez",
        "simd.ez",
        "arena.ez",
    ]:
        case_dir = tmp_path / name.removesuffix(".ez")
        case_dir.mkdir()
        project_toml = write_project(case_dir, ROOT / "examples" / name)

        assert ez.main(["build", "--project", str(project_toml)]) == 0, name
        ir_file = case_dir / "dist" / "native" / "e2e.ll"
        assert ir_file.exists(), name
        assert 'ModuleID = "e2e"' in ir_file.read_text(encoding="utf-8")
