"""编译器端到端测试"""

import re
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "compiler" / "src"))

from cli import ez


def test_e2e_stdlib_documents_exported_declares():
    """标准库 API 文档应覆盖源码导出的公开符号。"""
    documents = {
        "docs/stdlib-api.md": (ROOT / "docs" / "stdlib-api.md").read_text(encoding="utf-8"),
        "docs/stdlib.md": (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8"),
    }

    def compact(signature: str) -> str:
        return re.sub(r"\s+", "", signature.replace("=>", "->"))

    api_entries = set()
    for line in documents["docs/stdlib-api.md"].splitlines():
        match = re.match(r"\s*-\s+`([^`]+)`\s*$", line)
        if match and "(" in match.group(1) and "->" in match.group(1):
            api_entries.add(compact(match.group(1)))
    missing_names = []
    missing_signatures = []
    for source in sorted((ROOT / "packages" / "std").glob("**/*.ez")):
        text = source.read_text(encoding="utf-8")
        for match in re.finditer(r"export\s+struct\s+([A-Z][A-Za-z0-9_]*)\s*\{", text):
            name = match.group(1)
            for doc_name, docs in documents.items():
                if name not in docs:
                    missing_names.append(f"{doc_name} 缺少 {source.relative_to(ROOT)}:{name}")
        for match in re.finditer(r"export\s+(?:const|let)\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", text):
            name = match.group(1)
            for doc_name, docs in documents.items():
                if name not in docs:
                    missing_names.append(f"{doc_name} 缺少 {source.relative_to(ROOT)}:{name}")
        for match in re.finditer(r"export\s+const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(([^)]*)\)\s*:\s*([^=]+)=>", text):
            name = match.group(1)
            params = re.sub(r"\s+", " ", match.group(2).strip())
            ret_type = match.group(3).strip()
            expected = f"{name}({params}) -> {ret_type}"
            for doc_name, docs in documents.items():
                if name not in docs:
                    missing_names.append(f"{doc_name} 缺少 {source.relative_to(ROOT)}:{name}")
            if compact(expected) not in api_entries:
                missing_signatures.append(f"docs/stdlib-api.md 缺少 {source.relative_to(ROOT)}:{expected}")
        for match in re.finditer(r"export\s+declare\s+const\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^;]+);", text):
            name = match.group(1)
            source_sig = match.group(2).strip()
            if source_sig.startswith("<"):
                expected = f"{name}{source_sig}".replace("=>", "->")
            else:
                expected = f"{name}{source_sig}".replace("=>", "->")
            for doc_name, docs in documents.items():
                if name not in docs:
                    missing_names.append(f"{doc_name} 缺少 {source.relative_to(ROOT)}:{name}")
            if compact(expected) not in api_entries:
                missing_signatures.append(f"docs/stdlib-api.md 缺少 {source.relative_to(ROOT)}:{expected}")
    assert not missing_names, "标准库文档缺少公开接口: " + ", ".join(missing_names)
    assert not missing_signatures, "标准库 API 文档缺少公开签名: " + ", ".join(missing_signatures)


def test_e2e_stdlib_does_not_expose_low_level_concurrency_primitives():
    """标准库不能公开线程、锁、原子、通道等底层并发接口。"""
    forbidden = re.compile(r"\b(thread|mutex|rwlock|atomic|channel|condvar|condition)\b", re.I)
    allowed_names = {"platformHasThreads"}
    for source in sorted((ROOT / "packages" / "std").glob("**/*.ez")):
        text = source.read_text(encoding="utf-8")
        assert not forbidden.search(source.stem), f"标准库不应公开底层并发模块: {source.relative_to(ROOT)}"
        for match in re.finditer(r"export\s+(?:declare\s+const|const|struct)\s+([A-Za-z_][A-Za-z0-9_]*)", text):
            name = match.group(1)
            if name in allowed_names:
                continue
            assert not forbidden.search(name), f"标准库不应公开底层并发接口: {source.relative_to(ROOT)}:{name}"


def test_e2e_stdlib_time_format_tokens_are_documented():
    """std/time format 的跨平台格式占位符应写入两份标准库文档。"""
    for doc_path in [ROOT / "docs" / "stdlib-api.md", ROOT / "docs" / "stdlib.md"]:
        text = doc_path.read_text(encoding="utf-8")
        for token in ["YYYY", "MM", "DD", "HH", "mm", "SS", "%Y", "%m", "%d", "%H", "%M", "%S"]:
            assert token in text, f"{doc_path.relative_to(ROOT)} 缺少 time format token {token}"
        assert "分钟使用 `mm` 或 `%M`" in text


def test_e2e_stdlib_mem_names_and_error_codes_are_documented():
    """std/mem 应统一使用 set 名称和正值错误码。"""
    mem_source = (ROOT / "packages" / "std" / "mem.ez").read_text(encoding="utf-8")
    docs = [
        (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8"),
        (ROOT / "docs" / "stdlib-api.md").read_text(encoding="utf-8"),
    ]

    assert "export declare const set" in mem_source
    assert "export declare const memset" not in mem_source
    for text in docs:
        assert "set(dst: Blob" in text or "declare const set:" in text
        assert "memset(dst" not in text
        for name, value in [
            ("errCancel", 1),
            ("errTimeout", 2),
            ("errUnsupported", 3),
            ("errIO", 4),
            ("errNotFound", 5),
            ("errPermission", 6),
        ]:
            assert re.search(rf"{name}[^\n=]*=\s*{value}\b", mem_source)
            assert re.search(rf"{name}[^\n=]*=\s*{value}\b", text)


def test_e2e_stdlib_capability_matrix_covers_modules():
    """标准库能力矩阵应覆盖每个公开模块。"""
    docs = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")
    assert "## 标准库能力矩阵" in docs
    modules = []
    for source in sorted((ROOT / "packages" / "std").glob("**/*.ez")):
        rel = source.relative_to(ROOT / "packages" / "std").with_suffix("")
        modules.append("std/" + rel.as_posix())
    missing = [module for module in modules if f"`{module}`" not in docs]
    assert not missing, "标准库能力矩阵缺少模块: " + ", ".join(missing)
    for phrase in ["能力类型说明", "内存规则", "错误规则", "Flow 规则"]:
        assert phrase in docs


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


def assert_native_optional_return(ir_text: str, name: str, value_type: str):
    """断言 native 小可选返回值按当前架构桥接，并还原为 Ez 内部布局。"""
    internal_type = f"{{i1, {value_type}}}"
    if value_type == "i32":
        assert f'declare i64 @"{name}"' in ir_text
    elif ez._native_arch() == "aarch64":
        assert f'declare [2 x i64] @"{name}"' in ir_text
    elif ez._native_arch() == "x86_64":
        assert f'declare {{i8, {value_type}}} @"{name}"' in ir_text
    else:
        assert f'declare {internal_type} @"{name}"' in ir_text
        return
    assert f'%"_{name}_abi_ret" = alloca {internal_type}' in ir_text


def assert_native_small_struct_return(ir_text: str, name: str, struct_name: str, abi_return: str):
    """断言 native 小结构返回按当前架构桥接，并还原为 Ez 内部布局。"""
    if ez._native_arch() in {"aarch64", "x86_64"}:
        assert f'declare {abi_return} @"{name}"' in ir_text
        assert f'%"_{name}_abi_ret" = alloca %"{struct_name}"' in ir_text
    else:
        assert f'declare %"{struct_name}" @"{name}"' in ir_text


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
    assert_native_optional_return(ir_text, "readLine", "i8*")


def test_e2e_native_io_wrapper_uses_mobile_logs_and_shared_stdin():
    io_c = (ROOT / "packages" / "std" / "native" / "io.c").read_text(encoding="utf-8")
    assert "__android_log_write" in io_c
    assert "ANDROID_LOG_INFO" in io_c
    assert "ANDROID_LOG_ERROR" in io_c
    assert "os_log_with_type" in io_c
    assert "OS_LOG_TYPE_INFO" in io_c
    assert "OS_LOG_TYPE_ERROR" in io_c
    readline_body = io_c[io_c.index("OptStr readLine"):]
    assert "fgetc(stdin)" in readline_body
    assert "defined(__ANDROID__) || (defined(__APPLE__) && TARGET_OS_IPHONE)" not in readline_body
    assert "return (OptStr){false, NULL};" in readline_body
    assert "static char buffer[4096]" not in io_c


def test_e2e_mobile_io_readline_compiles_shared_stdin_branch(tmp_path):
    """Android/iOS readLine 应复用 native stdin 读取逻辑，而不是预处理失败。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证移动端 std/io wrapper")

    android_obj = tmp_path / "io_android.o"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-D__ANDROID__=1",
            "-c",
            str(ROOT / "packages" / "std" / "native" / "io.c"),
            "-o",
            str(android_obj),
        ],
        check=True,
    )


def test_e2e_native_io_readline_reads_long_crlf_lines(tmp_path):
    """原生 readLine 读取完整行，并兼容 CRLF 行尾。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/io wrapper")

    harness = tmp_path / "readline_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    bool ok;
    const char *value;
} OptStr;

OptStr readLine(void);

int main(void) {
    OptStr line = readLine();
    if (!line.ok || line.value == NULL) return 2;
    printf("%zu:%s", strlen(line.value), line.value);
    free((void *)line.value);
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "readline_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "io.c"),
            "-o",
            str(exe),
        ],
        check=True,
    )

    line = "x" * 5000
    result = subprocess.run(
        [str(exe)],
        input=(line + "\r\nignored").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert result.stdout.decode("utf-8") == f"5000:{line}"


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
    blob_abi = "[2 x i64]" if ez._native_arch() == "aarch64" else "{i8*, i64}"
    assert_native_small_struct_return(ir_text, "readFile", "Blob", blob_abi)
    assert 'declare i1 @"writeFile"' in ir_text
    assert 'declare i1 @"exists"' in ir_text
    assert 'declare void @"stat"({i1, %"FileStat"}* sret({i1, %"FileStat"})' in ir_text


def test_e2e_std_path_imports_and_builds(tmp_path):
    source = tmp_path / "std_path.ez"
    source.write_text(
        'from "std/path" import { pathSeparator, pathJoin, pathNormalize, pathDir, pathBase, pathExt, pathIsAbs, pathRelative, pathParse, pathToFileUrl, pathFromFileUrl };\n\n'
        'let parts: Str[] = ["/tmp", "ez", "../main.ez"];\n'
        'let sep = pathSeparator();\n'
        'let joined = pathJoin(parts = parts);\n'
        'let normalized = pathNormalize(path = joined);\n'
        'let dir = pathDir(path = normalized);\n'
        'let base = pathBase(path = normalized);\n'
        'let ext = pathExt(path = normalized);\n'
        'let abs = pathIsAbs(path = normalized);\n'
        'let rel = pathRelative(fromPath = "/tmp", toPath = normalized);\n'
        'let parsed = pathParse(path = normalized);\n'
        'let url = pathToFileUrl(path = normalized);\n'
        'let back = pathFromFileUrl(url = url);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert '%"PathParts" = type' in ir_text
    assert 'declare i8* @"pathNormalize"' in ir_text
    assert 'declare i1 @"pathIsAbs"' in ir_text
    assert 'declare void @"pathParse"(%"PathParts"* sret(%"PathParts")' in ir_text
    assert_native_optional_return(ir_text, "pathFromFileUrl", "i8*")


def test_e2e_std_str_imports_and_builds(tmp_path):
    source = tmp_path / "std_str.ez"
    source.write_text(
        'from "std/str" import { strByteLen, strCharLen, strIsEmpty, strIsValidUtf8, strSliceBytes, strSliceChars, strCharAt, strToBytes, strFromBytes, strContains, strStartsWith, strEndsWith, strIndexOf, strSplit, strJoin, strTrim, strReplace, strToLower, strToUpper };\n\n'
        'let text = " EzLang ";\n'
        'let byte_len = strByteLen(s = text);\n'
        'let char_len = strCharLen(s = text);\n'
        'let empty = strIsEmpty(s = "");\n'
        'let valid = strIsValidUtf8(s = text);\n'
        'let byte_slice = strSliceBytes(s = text, start = 1, end = 3);\n'
        'let char_slice = strSliceChars(s = text, start = 1, end = 3);\n'
        'let ch = strCharAt(s = text, index = 1);\n'
        'let bytes = strToBytes(s = text);\n'
        'let restored = strFromBytes(data = bytes);\n'
        'let has = strContains(s = text, needle = "Ez");\n'
        'let starts = strStartsWith(s = text, prefix = " ");\n'
        'let ends = strEndsWith(s = text, suffix = " ");\n'
        'let idx = strIndexOf(s = text, needle = "Lang");\n'
        'let parts = strSplit(s = text, sep = " ");\n'
        'let joined = strJoin(parts = parts, sep = "-");\n'
        'let trimmed = strTrim(s = text);\n'
        'let replaced = strReplace(s = text, old = "Ez", newValue = "Easy");\n'
        'let lower = strToLower(s = text);\n'
        'let upper = strToUpper(s = text);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare i64 @"strByteLen"' in ir_text
    assert 'declare i8* @"strSliceChars"' in ir_text
    assert_native_optional_return(ir_text, "strCharAt", "i8*")
    blob_abi = "[2 x i64]" if ez._native_arch() == "aarch64" else "{i8*, i64}"
    assert_native_small_struct_return(ir_text, "strToBytes", "Blob", blob_abi)
    assert 'declare void @"strSplit"({i8***, i64, i64, i64}* sret({i8***, i64, i64, i64})' in ir_text


def test_e2e_std_math_imports_and_builds(tmp_path):
    source = tmp_path / "std_math.ez"
    source.write_text(
        'from "std/math" import { mathPI, mathE, mathAbsI32, mathAbsI64, mathMinI32, mathMaxI32, mathClampI32, mathGcdI64, mathLcmI64, mathSqrt, mathPow, mathSin, mathCos, mathTan, mathLog, mathExp, mathFloor, mathCeil, mathRound, mathIsNaN, mathIsInf, mathAddI64Checked, mathSubI64Checked, mathMulI64Checked, mathDivI64Checked, mathF64ToI32, mathF64ToI64, mathI64ToF64 };\n\n'
        'let abs32 = mathAbsI32(value = -3);\n'
        'let abs64 = mathAbsI64(value = -4);\n'
        'let minv = mathMinI32(a = 1, b = 2);\n'
        'let maxv = mathMaxI32(a = 1, b = 2);\n'
        'let clamped = mathClampI32(value = 5, minValue = 0, maxValue = 3);\n'
        'let gcd = mathGcdI64(a = 18, b = 24);\n'
        'let lcm = mathLcmI64(a = 6, b = 8);\n'
        'let root = mathSqrt(value = 4.0);\n'
        'let power = mathPow(base = 2.0, exp = 8.0);\n'
        'let sinv = mathSin(value = mathPI);\n'
        'let cosv = mathCos(value = 0.0);\n'
        'let tanv = mathTan(value = 0.0);\n'
        'let logv = mathLog(value = mathE);\n'
        'let expv = mathExp(value = 1.0);\n'
        'let floorv = mathFloor(value = 1.9);\n'
        'let ceilv = mathCeil(value = 1.1);\n'
        'let roundv = mathRound(value = 1.5);\n'
        'let nan = mathIsNaN(value = root);\n'
        'let inf = mathIsInf(value = root);\n'
        'let sum = mathAddI64Checked(a = 1, b = 2);\n'
        'let diff = mathSubI64Checked(a = 1, b = 2);\n'
        'let product = mathMulI64Checked(a = 2, b = 3);\n'
        'let quotient = mathDivI64Checked(a = 6, b = 3);\n'
        'let i32v = mathF64ToI32(value = 42.0);\n'
        'let i64v = mathF64ToI64(value = 42.0);\n'
        'let f64v = mathI64ToF64(value = 42);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare i32 @"mathAbsI32"' in ir_text
    assert 'declare double @"mathSqrt"' in ir_text
    assert 'declare i1 @"mathIsNaN"' in ir_text
    assert_native_optional_return(ir_text, "mathAddI64Checked", "i64")
    assert 'declare i64 @"mathF64ToI32"' in ir_text
    assert '%"_mathF64ToI32_abi_ret" = alloca {i1, i32}' in ir_text
    assert_native_optional_return(ir_text, "mathF64ToI64", "i64")


def test_e2e_std_random_imports_and_builds(tmp_path):
    source = tmp_path / "std_random.ez"
    source.write_text(
        'from "std/random" import { RandomSource, randomSeed, randomNextU32, randomNextU64, randomRangeI64, randomRangeF64, randomShuffleBytes, randomShuffle, randomEntropy, randomSecureBytes, randomSecureU64 };\n\n'
        'let source = randomSeed(seed = 42);\n'
        'let n32 = randomNextU32(this = #source);\n'
        'let n64 = randomNextU64(this = #source);\n'
        'let ranged_i = randomRangeI64(this = #source, minValue = 1, maxValue = 10);\n'
        'let ranged_f = randomRangeF64(this = #source, minValue = 0.0, maxValue = 1.0);\n'
        'let shuffled = randomShuffleBytes(this = #source, data = Blob(data = "abcd", size = 4));\n'
        'let nums: List<I32> = [1, 2, 3, 4];\n'
        'let shuffled_nums: List<I32> = randomShuffle<I32>(this = #source, list = nums);\n'
        'let entropy = randomEntropy(size = 8);\n'
        'let secure = randomSecureBytes(size = 8);\n'
        'let secure64 = randomSecureU64();\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert '%"RandomSource" = type {i64}' in ir_text
    assert_native_small_struct_return(ir_text, "randomSeed", "RandomSource", "i64")
    assert 'declare i32 @"randomNextU32"' in ir_text
    blob_abi = "[2 x i64]" if ez._native_arch() == "aarch64" else "{i8*, i64}"
    assert_native_small_struct_return(ir_text, "randomShuffleBytes", "Blob", blob_abi)
    assert 'randomShuffle_I32' not in ir_text
    assert 'random_shuffle_cond' in ir_text
    assert 'declare void @"randomSecureBytes"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
    assert_native_optional_return(ir_text, "randomSecureU64", "i64")


def test_e2e_random_wrappers_use_secure_entropy_without_prng_fallback():
    native = (ROOT / "packages" / "std" / "native" / "random.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "random.js").read_text(encoding="utf-8")

    for marker in ["CryptGenRandom", "arc4random_buf", "getrandom", 'open("/dev/urandom"', "return (OptBlob){false"]:
        assert marker in native
    for marker in ["static bool ez_random_size", "requested < 0", "> (uint64_t)SIZE_MAX", "UINT32_MAX", "offset == size"]:
        assert marker in native
    secure_read = native[native.index("static bool ez_random_read_system"):native.index("OptBlob randomSecureBytes")]
    assert "ez_random_next" not in secure_read
    assert "ez_random_mix_seed" not in secure_read

    for marker in ["cryptoObj.getRandomValues", "require('crypto')", "randomBytes", "return null"]:
        assert marker in emcc
    secure_bytes = emcc[emcc.index("function secureBytes"):emcc.index("mergeInto(LibraryManager.library")]
    assert "next(" not in secure_bytes
    assert "mixSeed" not in secure_bytes


def test_e2e_random_range_i64_preserves_cross_platform_sequence(tmp_path):
    """randomRangeI64 的拒绝采样不能因平台实现差异多消耗随机数。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 std/random 确定性序列")
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/random emcc wrapper")

    native = (ROOT / "packages" / "std" / "native" / "random.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "random.js").read_text(encoding="utf-8")
    assert "threshold = (uint64_t)(0ULL - span) % span" in native
    assert "var threshold = (MOD64 - span) % span" in emcc
    assert "value < threshold" in emcc
    assert "MOD64 - (MOD64 % span)" not in emcc

    source = ROOT / "compiler" / "tests" / "fixtures" / "random_determinism_check.c"
    exe = tmp_path / "random_determinism_check"
    subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)], check=True)
    result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    assert result.stdout.splitlines() == ["1", "10418571485319073430"]

    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const HEAP32 = new Int32Array(memory);
const HEAP64 = new BigInt64Array(memory);
const library = {};

vm.runInNewContext(code, {
  BigInt,
  BigInt64Array,
  Uint8Array,
  HEAPU8,
  HEAP64,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

const source = 8;
HEAP64[source >> 3] = BigInt.asIntN(64, 0xA8D395BE4B19CCE8n);
const ranged = library.randomRangeI64(source, 0n, 1n);
const next = library.randomNextU64(source);

assert.strictEqual(ranged, 1n);
assert.strictEqual(BigInt.asUintN(64, next).toString(), '10418571485319073430');
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "random.js")], check=True)


def test_e2e_random_shuffle_bytes_rejects_invalid_blob_inputs(tmp_path):
    """randomShuffleBytes 遇到非法 Blob ABI 应返回空 Blob，不能读越界或截断。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 std/random wrapper")

    harness = tmp_path / "random_invalid_blob_harness.c"
    harness.write_text(
        r'''
#include <stdint.h>

typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { uint64_t state; } RandomSource;

RandomSource randomSeed(uint64_t seed);
Blob randomShuffleBytes(RandomSource *source, const Blob *data);

int main(void) {
    uint8_t one = 1;
    RandomSource source = randomSeed(1);
    Blob missing = {0, 1};
    Blob negative = {0, -1};
    Blob huge = {&one, INT64_MAX};
    Blob empty = {0, 0};
    Blob ok = {&one, 1};

    if (randomShuffleBytes(&source, 0).size != 0) return 2;
    if (randomShuffleBytes(&source, &missing).size != 0) return 3;
    if (randomShuffleBytes(&source, &negative).size != 0) return 4;
    if (randomShuffleBytes(&source, &huge).size != 0) return 5;
    if (randomShuffleBytes(&source, &empty).size != 0) return 6;
    Blob shuffled = randomShuffleBytes(&source, &ok);
    if (shuffled.size != 1 || !shuffled.data || shuffled.data[0] != 1) return 7;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "random_invalid_blob_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "random.c"),
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_emcc_random_shuffle_bytes_rejects_invalid_blob_inputs():
    """emcc randomShuffleBytes 应拒绝越界 Blob，不能把它截断成短输入。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/random emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const HEAP64 = new BigInt64Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}

const library = {};
vm.runInNewContext(code, {
  BigInt,
  BigInt64Array,
  Uint8Array,
  HEAPU8,
  HEAP64,
  _malloc,
  getValue,
  setValue,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function blob(dataPtr, size) {
  const ptr = _malloc(16);
  setValue(ptr, dataPtr, '*');
  setValue(ptr + 8, size, 'i64');
  return ptr;
}
function shuffle(blobPtr) {
  const source = _malloc(8);
  const ret = _malloc(16);
  library.randomSeed(source, 1n);
  library.randomShuffleBytes(ret, source, blobPtr);
  return { ptr: getValue(ret, '*'), size: getValue(ret + 8, 'i64') };
}

const data = _malloc(2);
HEAPU8[data] = 1;
HEAPU8[data + 1] = 2;

assert.strictEqual(shuffle(0).size, 0);
assert.strictEqual(shuffle(blob(0, -1)).size, 0);
assert.strictEqual(shuffle(blob(0, 1)).size, 0);
assert.strictEqual(shuffle(blob(HEAPU8.length - 1, 2)).size, 0);
const ok = shuffle(blob(data, 2));
assert.strictEqual(ok.size, 2);
assert.notStrictEqual(ok.ptr, 0);
assert.deepStrictEqual(Array.from(HEAPU8.slice(ok.ptr, ok.ptr + ok.size)).sort(), [1, 2]);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "random.js")], check=True)


def test_e2e_emcc_random_secure_entropy_sources_and_failures():
    """emcc 安全随机应使用真实熵源，不可用时返回空可选值。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/random emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');

function loadLibrary(extra = {}) {
  const memory = new ArrayBuffer(65536);
  const HEAPU8 = new Uint8Array(memory);
  const HEAP64 = new BigInt64Array(memory);
  const view = new DataView(memory);
  let heap = 1024;

  function align(value) { return (value + 7) & ~7; }
  function _malloc(size) {
    const ptr = heap;
    heap = align(heap + Math.max(1, size));
    if (heap > HEAPU8.length) throw new Error('oom');
    return ptr;
  }
  function setValue(ptr, value, type) {
    if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
    if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
    throw new Error('unsupported setValue type ' + type);
  }
  const library = {};
  vm.runInNewContext(code, Object.assign({
    BigInt,
    BigInt64Array,
    Uint8Array,
    HEAPU8,
    HEAP64,
    _malloc,
    setValue,
    LibraryManager: { library },
    mergeInto(target, source) { Object.assign(target, source); },
  }, extra), { filename: process.argv[1] });
  return { library, HEAPU8, view, malloc: _malloc };
}

function optBlob(env, fn, size) {
  const ret = env.malloc(32);
  env.library[fn](ret, BigInt(size));
  const ok = env.HEAPU8[ret] === 1;
  const ptr = env.view.getUint32(ret + 8, true);
  const length = Number(env.view.getBigInt64(ret + 16, true));
  return { ok, ptr, length, bytes: Array.from(env.HEAPU8.slice(ptr, ptr + length)) };
}

function optU64(env) {
  const ret = env.malloc(16);
  env.library.randomSecureU64(ret);
  return { ok: env.HEAPU8[ret] === 1, value: env.view.getBigInt64(ret + 8, true) };
}

const unavailable = loadLibrary();
assert.deepStrictEqual(optBlob(unavailable, 'randomSecureBytes', 4), { ok: false, ptr: 0, length: 0, bytes: [] });
assert.deepStrictEqual(optBlob(unavailable, 'randomEntropy', 4), { ok: false, ptr: 0, length: 0, bytes: [] });
assert.deepStrictEqual(optU64(unavailable), { ok: false, value: 0n });

let counter = 1;
const available = loadLibrary({
  crypto: {
    getRandomValues(target) {
      for (let i = 0; i < target.length; i++) target[i] = counter++ & 0xff;
      return target;
    },
  },
});
const secureBytes = optBlob(available, 'randomSecureBytes', 4);
assert.strictEqual(secureBytes.ok, true);
assert.notStrictEqual(secureBytes.ptr, 0);
assert.strictEqual(secureBytes.length, 4);
assert.deepStrictEqual(secureBytes.bytes, [1, 2, 3, 4]);
const entropyBytes = optBlob(available, 'randomEntropy', 4);
assert.strictEqual(entropyBytes.ok, true);
assert.notStrictEqual(entropyBytes.ptr, 0);
assert.strictEqual(entropyBytes.length, 4);
assert.deepStrictEqual(entropyBytes.bytes, [5, 6, 7, 8]);
assert.deepStrictEqual(optBlob(available, 'randomSecureBytes', 0), { ok: true, ptr: 0, length: 0, bytes: [] });
assert.deepStrictEqual(optBlob(available, 'randomEntropy', -1), { ok: false, ptr: 0, length: 0, bytes: [] });
assert.deepStrictEqual(optU64(available), { ok: true, value: 0x100f0e0d0c0b0a09n });
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "random.js")], check=True)


def test_e2e_std_hash_imports_and_builds(tmp_path):
    docs = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")
    source = tmp_path / "std_hash.ez"
    source.write_text(
        'from "std/hash" import { hashFnv1a32, hashFnv1a64, hashStrFnv1a32, hashStrFnv1a64, hashCombineU64, crc32, crc32Str };\n\n'
        'let data = Blob(data = "hello", size = 5);\n'
        'let h32 = hashFnv1a32(data = data);\n'
        'let h64 = hashFnv1a64(data = data);\n'
        'let sh32 = hashStrFnv1a32(s = "hello");\n'
        'let sh64 = hashStrFnv1a64(s = "hello");\n'
        'let combined = hashCombineU64(seed = h64, value = sh64);\n'
        'let c1 = crc32(data = data);\n'
        'let c2 = crc32Str(s = "hello");\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare i32 @"hashFnv1a32"' in ir_text
    assert 'declare i64 @"hashFnv1a64"' in ir_text
    assert 'declare i32 @"hashStrFnv1a32"' in ir_text
    assert 'declare i64 @"hashCombineU64"' in ir_text
    assert 'declare i32 @"crc32Str"' in ir_text
    assert "SHA-2、HMAC 等安全算法由 `std/crypto` 独立提供" in docs
    assert "后续 `std/crypto`" not in docs


def test_e2e_hash_invalid_blob_inputs_are_treated_as_empty(tmp_path):
    """非可选 hash Blob API 遇到非法 Blob 时按空输入计算。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 std/hash wrapper")

    harness = tmp_path / "hash_invalid_blob_harness.c"
    harness.write_text(
        r'''
#include <stdint.h>

typedef struct { uint8_t *data; int64_t size; } Blob;

uint32_t hashFnv1a32(const Blob *data);
uint64_t hashFnv1a64(const Blob *data);
uint32_t crc32(const Blob *data);

int main(void) {
    uint8_t one = 1;
    Blob missing = {0, 1};
    Blob negative = {0, -1};
    Blob empty = {0, 0};

    uint32_t empty32 = hashFnv1a32(&empty);
    uint64_t empty64 = hashFnv1a64(&empty);
    uint32_t empty_crc = crc32(&empty);
    if (empty32 != 2166136261u) return 2;
    if (empty64 != 14695981039346656037ULL) return 3;
    if (empty_crc != 0u) return 4;
    Blob one_byte = {&one, 1};
    if (hashFnv1a32(0) != empty32 || hashFnv1a32(&missing) != empty32 || hashFnv1a32(&negative) != empty32) return 5;
    if (hashFnv1a64(0) != empty64 || hashFnv1a64(&missing) != empty64 || hashFnv1a64(&negative) != empty64) return 6;
    if (crc32(0) != empty_crc || crc32(&missing) != empty_crc || crc32(&negative) != empty_crc) return 7;
    if (hashFnv1a32(&one_byte) == empty32 || hashFnv1a64(&one_byte) == empty64 || crc32(&one_byte) == empty_crc) return 8;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "hash_invalid_blob_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "hash.c"),
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_emcc_hash_invalid_blob_inputs_are_treated_as_empty():
    """emcc hash Blob API 遇到越界 Blob 时也按空输入计算。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/hash emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}

const library = {};
vm.runInNewContext(code, {
  BigInt,
  Uint8Array,
  HEAPU8,
  getValue,
  setValue,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function blob(dataPtr, size) {
  const ptr = _malloc(16);
  setValue(ptr, dataPtr, '*');
  setValue(ptr + 8, size, 'i64');
  return ptr;
}

const empty = blob(0, 0);
const missing = blob(0, 1);
const negative = blob(0, -1);
const outOfBounds = blob(HEAPU8.length - 1, 2);
const empty32 = library.hashFnv1a32(empty);
const empty64 = library.hashFnv1a64(empty);
const emptyCrc = library.crc32(empty);

assert.strictEqual(empty32 >>> 0, 2166136261);
assert.strictEqual(empty64, BigInt.asIntN(64, 14695981039346656037n));
assert.strictEqual(emptyCrc, 0);
for (const ptr of [0, missing, negative, outOfBounds]) {
  assert.strictEqual(library.hashFnv1a32(ptr), empty32);
  assert.strictEqual(library.hashFnv1a64(ptr), empty64);
  assert.strictEqual(library.crc32(ptr), emptyCrc);
}
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "hash.js")], check=True)


def test_e2e_std_platform_imports_and_builds(tmp_path):
    source = tmp_path / "std_platform.ez"
    source.write_text(
        'from "std/platform" import { platformOS, platformArch, platformIsLittleEndian, platformPointerBits, platformPageSize, platformCpuCount, platformMemoryLimit, platformHasThreads, platformHasFileSystem, platformHasNetwork, platformHasCrypto, platformHasDom, platformHasSubprocess };\n\n'
        'let os = platformOS();\n'
        'let arch = platformArch();\n'
        'let little = platformIsLittleEndian();\n'
        'let ptr = platformPointerBits();\n'
        'let page = platformPageSize();\n'
        'let cpus = platformCpuCount();\n'
        'let mem = platformMemoryLimit();\n'
        'let threads = platformHasThreads();\n'
        'let fs = platformHasFileSystem();\n'
        'let net = platformHasNetwork();\n'
        'let crypto = platformHasCrypto();\n'
        'let dom = platformHasDom();\n'
        'let proc = platformHasSubprocess();\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare i8* @"platformOS"' in ir_text
    assert 'declare i8* @"platformArch"' in ir_text
    assert 'declare i1 @"platformIsLittleEndian"' in ir_text
    assert 'declare i64 @"platformMemoryLimit"' in ir_text
    assert 'declare i1 @"platformHasSubprocess"' in ir_text


def test_e2e_platform_wrappers_probe_native_and_emcc_capabilities():
    native = (ROOT / "packages" / "std" / "native" / "platform.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "platform.js").read_text(encoding="utf-8")
    for marker in ["GetSystemInfo", "GlobalMemoryStatusEx", "sysconf(_SC_PAGESIZE)", "sysconf(_SC_NPROCESSORS_ONLN)", "sysctlbyname(\"hw.memsize\""]:
        assert marker in native
    assert "INT64_MAX / (uint64_t)page_size" in native
    assert "TARGET_OS_IPHONE" in native
    assert "return false;" in native[native.index("bool platformHasSubprocess"):]
    for marker in ["stringToNewUTF8('emcc')", "stringToNewUTF8('wasm32')", "return 65536n", "requireNodeModule('os')", "Math.min(cpus.length, 2147483647)", "Math.floor(concurrency)", "SharedArrayBuffer", "typeof FS", "typeof fetch", "getRandomValues", "requireNodeModule('crypto')", "typeof document", "childProcess.spawn"]:
        assert marker in emcc
    assert "navigator.hardwareConcurrency) return navigator.hardwareConcurrency | 0" not in emcc


def test_e2e_emcc_platform_probes_node_capabilities_and_browser_fallback():
    """emcc platform 能力查询应反映 Node 同步运行时能力，浏览器环境保持保守。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/platform emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');

function makeRuntime(extra) {
  const library = {};
  vm.runInNewContext(code, Object.assign({
    BigInt,
    stringToNewUTF8(text) { return String(text); },
    LibraryManager: { library },
    mergeInto(target, source) { Object.assign(target, source); },
  }, extra || {}), { filename: process.argv[1] });
  return library;
}

let library = makeRuntime({ require });
assert.strictEqual(library.platformOS(), 'emcc');
assert.strictEqual(library.platformArch(), 'wasm32');
assert.strictEqual(library.platformCpuCount(), Math.min(os.cpus().length, 2147483647));
assert.strictEqual(library.platformMemoryLimit(), BigInt(os.totalmem()));
assert.strictEqual(library.platformHasCrypto(), 1);
assert.strictEqual(library.platformHasSubprocess(), 1);

library = makeRuntime({});
assert.strictEqual(library.platformHasSubprocess(), 0);
assert.strictEqual(library.platformMemoryLimit(), -1n);

library = makeRuntime({ navigator: { hardwareConcurrency: 9007199254740991 } });
assert.strictEqual(library.platformCpuCount(), 2147483647);
library = makeRuntime({ navigator: { hardwareConcurrency: 3.9 } });
assert.strictEqual(library.platformCpuCount(), 3);
library = makeRuntime({ navigator: { hardwareConcurrency: 0 } });
assert.strictEqual(library.platformCpuCount(), 1);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "platform.js")], check=True)


def test_e2e_std_process_imports_and_builds(tmp_path):
    source = tmp_path / "std_process.ez"
    source.write_text(
        'from "std/process" import { Command, Process, ProcessResult, processExec, processSpawn, processWait, processTerminate, processStdin, processStdout, processStderr, processCurrentPath };\n\n'
        'let args: Str[] = ["-c", "printf hello"];\n'
        'let envs: Str[] = ["EZLANG_PROCESS_TEST=1"];\n'
        'let empty: Str[] = [];\n'
        'let command = Command(program = "/bin/sh", args = args, cwd = "", env = envs, stdin = Blob(data = "", size = 0));\n'
        'let result = processExec(command = command);\n'
        'let spawned = processSpawn(command = Command(program = "/bin/sh", args = args, cwd = "", env = empty, stdin = Blob(data = "", size = 0)));\n'
        'let waited = processWait(process = Process(handle = 0, pid = 0));\n'
        'let killed = processTerminate(process = Process(handle = 0, pid = 0));\n'
        'let stdin_stream = processStdin(process = Process(handle = 0, pid = 0));\n'
        'let stdout_stream = processStdout(process = Process(handle = 0, pid = 0));\n'
        'let stderr_stream = processStderr(process = Process(handle = 0, pid = 0));\n'
        'let current = processCurrentPath();\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert '%"Command" = type' in ir_text
    assert '%"ProcessResult" = type' in ir_text
    assert '%"Stream" = type' in ir_text
    assert 'declare void @"processExec"({i1, %"ProcessResult"}* sret({i1, %"ProcessResult"})' in ir_text
    assert 'declare void @"processSpawn"({i1, %"Process"}* sret({i1, %"Process"})' in ir_text
    assert 'declare void @"processStdin"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
    assert 'declare void @"processStdout"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
    assert 'declare void @"processStderr"({i1, %"Stream"}* sret({i1, %"Stream"})' in ir_text
    assert_native_optional_return(ir_text, "processCurrentPath", "i8*")


def test_e2e_process_wrappers_cover_windows_and_unsupported_targets():
    native = (ROOT / "packages" / "std" / "native" / "process.c").read_text(encoding="utf-8")
    platform_native = (ROOT / "packages" / "std" / "native" / "platform.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "process.js").read_text(encoding="utf-8")
    stdlib_doc = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")
    stdlib_api_doc = (ROOT / "docs" / "stdlib-api.md").read_text(encoding="utf-8")
    for marker in ["CreateProcessW", "WaitForSingleObject", "TerminateProcess", "GetModuleFileNameW"]:
        assert marker in native
    for marker in ["processStdin", "processStdout", "processStderr", "STREAM_KIND_PROCESS_STDIN", "STREAM_KIND_PROCESS_STDOUT", "STREAM_KIND_PROCESS_STDERR"]:
        assert marker in native
    assert "EZ_PROCESS_POSIX_SUPPORTED" in native
    assert "#if defined(_WIN32)" in native
    assert "#elif EZ_PROCESS_POSIX_SUPPORTED" in native
    assert "!defined(__ANDROID__)" not in native[native.index("#if !defined(_WIN32)"):native.index("#if EZ_PROCESS_POSIX_SUPPORTED")]
    assert "return (OptProcessResult){false, {0}};" in native
    assert "return (OptProcess){false, {0}};" in native
    assert "defined(__APPLE__) && TARGET_OS_IPHONE" in platform_native[platform_native.index("bool platformHasSubprocess"):]
    assert "defined(__ANDROID__)" not in platform_native[platform_native.index("bool platformHasSubprocess"):]
    for marker in ["child_process", "childProcess.spawn(", "spawnSync", "running[handle]", "completed[handle]", "process.execPath", "浏览器显式失败"]:
        assert marker in emcc
    for marker in ["processStdin", "processStdout", "processStderr", "__ez_stream_bridge", "takeCompletedStream", "fromProcessPipe"]:
        assert marker in emcc
    assert "保留 `stdin`/`stdout`/`stderr` 管道" not in stdlib_doc
    assert "processWait` 挂起等待退出" in stdlib_doc
    assert "进程管道流" in stdlib_doc
    assert "Linux/macOS/Windows/Android native 目标实现子进程调用" in stdlib_doc
    assert "iOS 目标当前仍显式失败" in stdlib_doc
    assert "processWait` 返回捕获的 `stdout`/`stderr`" in stdlib_api_doc
    assert "Linux/macOS/Windows/Android native 目标实现子进程调用" in stdlib_api_doc


def test_e2e_android_process_uses_posix_subprocess_branch(tmp_path):
    """Android native process wrapper 应复用 POSIX fork/exec 分支。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 Android process 预处理分支")

    process_obj = tmp_path / "process_android.o"
    platform_obj = tmp_path / "platform_android.o"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-D__ANDROID__=1",
            "-c",
            str(ROOT / "packages" / "std" / "native" / "process.c"),
            "-o",
            str(process_obj),
        ],
        check=True,
    )
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-D__ANDROID__=1",
            "-c",
            str(ROOT / "packages" / "std" / "native" / "platform.c"),
            "-o",
            str(platform_obj),
        ],
        check=True,
    )


def test_e2e_emcc_process_spawn_falls_back_when_async_spawn_unavailable():
    """emcc processSpawn 在 Asyncify spawn 不可用时回退同步结果句柄。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/process emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function stringToUTF8(text, ptr, maxBytes) {
  const bytes = Buffer.from(String(text || ''), 'utf8');
  const size = Math.max(0, Math.min(bytes.length, maxBytes - 1));
  HEAPU8.set(bytes.slice(0, size), ptr);
  HEAPU8[ptr + size] = 0;
}
function lengthBytesUTF8(text) {
  return Buffer.byteLength(String(text || ''), 'utf8');
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}
function writeList(ptr, values) {
  const pages = values.length === 0 ? 0 : _malloc(4);
  if (values.length > 0) {
    const page = _malloc(32);
    setValue(pages, page, '*');
    values.forEach((value, index) => setValue(page + index * 4, stringToNewUTF8(value), '*'));
  }
  setValue(ptr, pages, '*');
  setValue(ptr + 8, values.length, 'i64');
  setValue(ptr + 16, values.length === 0 ? 0 : 8, 'i64');
  setValue(ptr + 24, values.length === 0 ? 0 : 1, 'i64');
}

let spawnCalls = 0;
const fakeChildProcess = {
  spawn(program, args) {
    spawnCalls += 1;
    assert.strictEqual(program, 'tool');
    assert.deepStrictEqual(Array.from(args), ['arg']);
    return null;
  },
  spawnSync(program, args, options) {
    assert.strictEqual(Buffer.from(options.input).toString('utf8'), 'in');
    return { status: 0, stdout: Buffer.from('out'), stderr: Buffer.from(''), error: null };
  },
};

const library = {};
vm.runInNewContext(code, {
  BigInt,
  Buffer,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  lengthBytesUTF8,
  stringToUTF8,
  UTF8ToString,
  stringToNewUTF8,
  Asyncify: { handleSleep(fn) { let value; fn((result) => { value = result; }); return value; } },
  require(name) { return name === 'child_process' ? fakeChildProcess : null; },
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

const input = stringToNewUTF8('in');
const command = _malloc(96);
setValue(command, stringToNewUTF8('tool'), '*');
writeList(command + 8, ['arg']);
setValue(command + 40, 0, '*');
writeList(command + 48, []);
setValue(command + 80, input, '*');
setValue(command + 88, 2, 'i64');

const spawned = _malloc(32);
library.processSpawn(spawned, command);
assert.strictEqual(HEAPU8[spawned], 1);
assert.strictEqual(spawnCalls, 1);
assert.strictEqual(library.processTerminate(spawned + 8), 0);

const waited = _malloc(80);
library.processWait(waited, spawned + 8);
assert.strictEqual(HEAPU8[waited], 1);
assert.strictEqual(view.getInt32(waited + 8, true), 0);
assert.strictEqual(HEAPU8[waited + 48], 1);
const stdoutPtr = getValue(waited + 16, '*');
const stdoutSize = getValue(waited + 24, 'i64');
assert.strictEqual(Buffer.from(HEAPU8.slice(stdoutPtr, stdoutPtr + stdoutSize)).toString('utf8'), 'out');
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "process.js")], check=True)


def test_e2e_emcc_process_rejects_invalid_stdin_blob_before_spawn():
    """emcc processExec/processSpawn 遇到非法 stdin Blob 应失败，不能把它当空输入执行。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/process emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}
function writeList(ptr, values) {
  const pages = values.length === 0 ? 0 : _malloc(4);
  if (values.length > 0) {
    const page = _malloc(32);
    setValue(pages, page, '*');
    values.forEach((value, index) => setValue(page + index * 4, stringToNewUTF8(value), '*'));
  }
  setValue(ptr, pages, '*');
  setValue(ptr + 8, values.length, 'i64');
  setValue(ptr + 16, values.length === 0 ? 0 : 8, 'i64');
  setValue(ptr + 24, values.length === 0 ? 0 : 1, 'i64');
}

let spawnCalls = 0;
const fakeChildProcess = {
  spawnSync() { spawnCalls += 1; return { status: 0, stdout: Buffer.from(''), stderr: Buffer.from(''), error: null }; },
};

const library = {};
vm.runInNewContext(code, {
  BigInt,
  Buffer,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  require(name) { return name === 'child_process' ? fakeChildProcess : null; },
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

const command = _malloc(96);
setValue(command, stringToNewUTF8('tool'), '*');
writeList(command + 8, []);
setValue(command + 40, 0, '*');
writeList(command + 48, []);
setValue(command + 80, 0, '*');
setValue(command + 88, -1, 'i64');

const execRet = _malloc(80);
library.processExec(execRet, command);
assert.strictEqual(HEAPU8[execRet], 0);

const spawnRet = _malloc(32);
library.processSpawn(spawnRet, command);
assert.strictEqual(HEAPU8[spawnRet], 0);
assert.strictEqual(spawnCalls, 0);

setValue(command + 80, HEAPU8.length - 1, '*');
setValue(command + 88, 2, 'i64');
library.processExec(execRet, command);
assert.strictEqual(HEAPU8[execRet], 0);
library.processSpawn(spawnRet, command);
assert.strictEqual(HEAPU8[spawnRet], 0);
assert.strictEqual(spawnCalls, 0);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "process.js")], check=True)


def test_e2e_emcc_process_completed_stdout_can_transfer_to_stream():
    """emcc processStdout 可把已完成 spawn 结果转交给 std/stream。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/process emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const streamCode = fs.readFileSync(process.argv[1], 'utf8');
const processCode = fs.readFileSync(process.argv[2], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function _free() {}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i32') return view.getInt32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}
function writeList(ptr, values) {
  const pages = values.length === 0 ? 0 : _malloc(4);
  if (values.length > 0) {
    const page = _malloc(32);
    setValue(pages, page, '*');
    values.forEach((value, index) => setValue(page + index * 4, stringToNewUTF8(value), '*'));
  }
  setValue(ptr, pages, '*');
  setValue(ptr + 8, values.length, 'i64');
  setValue(ptr + 16, values.length === 0 ? 0 : 8, 'i64');
  setValue(ptr + 24, values.length === 0 ? 0 : 1, 'i64');
}

const fakeChildProcess = {
  spawnSync() { return { status: 0, stdout: Buffer.from('pipe'), stderr: Buffer.from('err'), error: null }; },
};

const library = {};
const context = {
  BigInt,
  Buffer,
  HEAPU8,
  FS: {},
  _malloc,
  _free,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  require(name) { return name === 'child_process' ? fakeChildProcess : null; },
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
};
vm.runInNewContext(streamCode, context, { filename: process.argv[1] });
vm.runInNewContext(processCode, context, { filename: process.argv[2] });

const command = _malloc(96);
setValue(command, stringToNewUTF8('tool'), '*');
writeList(command + 8, []);
setValue(command + 40, 0, '*');
writeList(command + 48, []);
setValue(command + 80, 0, '*');
setValue(command + 88, 0, 'i64');

const spawned = _malloc(32);
library.processSpawn(spawned, command);
assert.strictEqual(HEAPU8[spawned], 1);

const stdinOpt = _malloc(24);
library.processStdin(stdinOpt, spawned + 8);
assert.strictEqual(HEAPU8[stdinOpt], 0);

const streamOpt = _malloc(24);
library.processStdout(streamOpt, spawned + 8);
assert.strictEqual(HEAPU8[streamOpt], 1);
assert.strictEqual(getValue(streamOpt + 16, 'i32'), 6);

const chunk = _malloc(24);
library.streamRead(chunk, streamOpt + 8, 4);
assert.strictEqual(HEAPU8[chunk], 1);
const dataPtr = getValue(chunk + 8, '*');
const size = getValue(chunk + 16, 'i64');
assert.strictEqual(Buffer.from(HEAPU8.slice(dataPtr, dataPtr + size)).toString('utf8'), 'pipe');
assert.strictEqual(library.streamClose(streamOpt + 8), 1);

const waited = _malloc(80);
library.processWait(waited, spawned + 8);
assert.strictEqual(HEAPU8[waited], 1);
assert.strictEqual(getValue(waited + 24, 'i64'), 0);
assert.strictEqual(getValue(waited + 40, 'i64'), 3);
'''
    subprocess.run(
        [node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "stream.js"), str(ROOT / "packages" / "std" / "emcc" / "process.js")],
        check=True,
    )


def test_e2e_emcc_process_live_pipe_streams_roundtrip():
    """emcc Asyncify processSpawn 应暴露活 stdin/stdout 管道流。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/process emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const { EventEmitter } = require('events');
const vm = require('vm');

const streamCode = fs.readFileSync(process.argv[1], 'utf8');
const processCode = fs.readFileSync(process.argv[2], 'utf8');
const memory = new ArrayBuffer(131072);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function _free() {}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i32') return view.getInt32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}
function writeList(ptr, values) {
  const pages = values.length === 0 ? 0 : _malloc(4);
  if (values.length > 0) {
    const page = _malloc(32);
    setValue(pages, page, '*');
    values.forEach((value, index) => setValue(page + index * 4, stringToNewUTF8(value), '*'));
  }
  setValue(ptr, pages, '*');
  setValue(ptr + 8, values.length, 'i64');
  setValue(ptr + 16, values.length === 0 ? 0 : 8, 'i64');
  setValue(ptr + 24, values.length === 0 ? 0 : 1, 'i64');
}
function makeBlob(text) {
  const bytes = Buffer.from(text, 'utf8');
  const data = _malloc(bytes.length || 1);
  HEAPU8.set(bytes, data);
  const blob = _malloc(16);
  setValue(blob, data, '*');
  setValue(blob + 8, bytes.length, 'i64');
  return blob;
}
function blobText(ptr) {
  const dataPtr = getValue(ptr, '*');
  const size = getValue(ptr + 8, 'i64');
  return Buffer.from(HEAPU8.slice(dataPtr, dataPtr + size)).toString('utf8');
}

class FakeReadable extends EventEmitter {
  constructor() {
    super();
    this.queue = [];
    this.readableEnded = false;
    this.destroyed = false;
  }
  pushData(text) {
    this.queue.push(Buffer.from(text));
    this.emit('data', Buffer.from(text));
  }
  read(max) {
    if (this.queue.length === 0) return null;
    const chunk = this.queue.shift();
    if (chunk.length > max) {
      this.queue.unshift(chunk.slice(max));
      return chunk.slice(0, max);
    }
    return chunk;
  }
  end() {
    this.readableEnded = true;
    this.emit('end');
    this.emit('close');
  }
  destroy() { this.destroyed = true; this.emit('close'); }
}

class FakeWritable extends EventEmitter {
  constructor(child) {
    super();
    this.child = child;
    this.destroyed = false;
  }
  write(data) {
    this.child.stdout.pushData('echo:' + Buffer.from(data).toString('utf8'));
    return true;
  }
  end() { this.child.stdout.end(); }
  destroy() { this.destroyed = true; }
}

class FakeChild extends EventEmitter {
  constructor() {
    super();
    this.pid = 42;
    this.stdout = new FakeReadable();
    this.stderr = new FakeReadable();
    this.stdin = new FakeWritable(this);
  }
  kill() {
    this.emit('close', 143, null);
    return true;
  }
}

const child = new FakeChild();
const fakeChildProcess = { spawn() { return child; } };

const library = {};
const context = {
  require(name) { return name === 'child_process' ? fakeChildProcess : null; },
  BigInt,
  Buffer,
  ArrayBuffer,
  DataView,
  Uint8Array,
  HEAPU8,
  FS: {},
  _malloc,
  _free,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  Asyncify: { handleSleep(fn) { let value; fn((result) => { value = result; }); return value; } },
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
};
vm.runInNewContext(streamCode, context, { filename: process.argv[1] });
vm.runInNewContext(processCode, context, { filename: process.argv[2] });

const command = _malloc(96);
setValue(command, stringToNewUTF8('tool'), '*');
writeList(command + 8, []);
setValue(command + 40, 0, '*');
writeList(command + 48, []);
setValue(command + 80, 0, '*');
setValue(command + 88, 0, 'i64');

const spawned = _malloc(32);
library.processSpawn(spawned, command);
assert.strictEqual(HEAPU8[spawned], 1);
assert.strictEqual(getValue(spawned + 16, 'i64'), 42);

const stdinOpt = _malloc(24);
library.processStdin(stdinOpt, spawned + 8);
assert.strictEqual(HEAPU8[stdinOpt], 1);
const stdoutOpt = _malloc(24);
library.processStdout(stdoutOpt, spawned + 8);
assert.strictEqual(HEAPU8[stdoutOpt], 1);

assert.strictEqual(library.streamWrite(stdinOpt + 8, makeBlob('pipe')), 4);
const chunk = _malloc(24);
library.streamRead(chunk, stdoutOpt + 8, 16);
assert.strictEqual(HEAPU8[chunk], 1);
assert.strictEqual(blobText(chunk + 8), 'echo:pipe');
assert.strictEqual(library.streamClose(stdinOpt + 8), 1);
assert.strictEqual(library.streamClose(stdoutOpt + 8), 1);

child.emit('close', 0, null);
const waited = _malloc(80);
library.processWait(waited, spawned + 8);
assert.strictEqual(HEAPU8[waited], 1);
assert.strictEqual(getValue(waited + 16, 'i64'), 0);
assert.strictEqual(getValue(waited + 40, 'i64'), 0);
assert.strictEqual(HEAPU8[waited + 48], 1);
'''
    subprocess.run(
        [node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "stream.js"), str(ROOT / "packages" / "std" / "emcc" / "process.js")],
        check=True,
    )


def test_e2e_std_uri_imports_and_builds(tmp_path):
    source = tmp_path / "std_uri.ez"
    source.write_text(
        'from "std/uri" import { UriParts, uriParse, uriBuild, uriNormalize, uriScheme, uriHost, uriPort, uriPath, uriQuery, uriFragment, uriEncodeQuery, uriDecodeQuery, uriEncodePathSegment, uriDecodePathSegment, uriQueryGet, uriQuerySet };\n\n'
        'let url = "https://user@example.com:443/a/../b?q=a%20b#top";\n'
        'let parts = uriParse(url = url);\n'
        'let rebuilt = uriBuild(parts = UriParts(scheme = "https", userInfo = "", host = "example.com", port = -1, path = "/b", query = "", fragment = ""));\n'
        'let normalized = uriNormalize(url = url);\n'
        'let scheme = uriScheme(url = url);\n'
        'let host = uriHost(url = url);\n'
        'let port = uriPort(url = url);\n'
        'let path = uriPath(url = url);\n'
        'let query = uriQuery(url = url);\n'
        'let fragment = uriFragment(url = url);\n'
        'let encoded = uriEncodeQuery(s = "a b");\n'
        'let decoded = uriDecodeQuery(s = encoded);\n'
        'let seg = uriEncodePathSegment(s = "a/b");\n'
        'let raw = uriDecodePathSegment(s = seg);\n'
        'let next_query = uriQuerySet(query = "a=1", key = "b", value = "two words");\n'
        'let value = uriQueryGet(query = next_query, key = "b");\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert '%"UriParts" = type' in ir_text
    assert 'declare void @"uriParse"({i1, %"UriParts"}* sret({i1, %"UriParts"})' in ir_text
    assert 'declare i8* @"uriNormalize"' in ir_text
    assert_native_optional_return(ir_text, "uriHost", "i8*")
    assert 'declare i64 @"uriPort"' in ir_text
    assert '%"_uriPort_abi_ret" = alloca {i1, i32}' in ir_text


def test_e2e_uri_wrappers_cover_parsing_percent_encoding_and_query_ops():
    native = (ROOT / "packages" / "std" / "native" / "uri.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "uri.js").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")
    for marker in ["ez_scheme_valid", "ez_percent_encode", "ez_percent_decode", "ez_normalize_path", "uriQueryGet", "uriQuerySet"]:
        assert marker in native
    assert "ez_utf8_validate_len" in native
    assert "ez_parse_port" in native
    assert "byte == 0" in native
    assert "atoi(" not in native
    assert "query_mode && ch == ' '" in native
    assert "ez_query_key_matches" in native
    for marker in ["validScheme", "percentEncodeString", "percentDecodeString", "normalizePath", "hasAuthorityMarker", "queryKeyMatches", "querySet"]:
        assert marker in emcc
    assert "appendCodePointUtf8" in emcc
    assert "validUtf8Bytes(bytes)" in emcc
    assert "parsePort" in emcc
    assert "bytes.indexOf(0) >= 0" in emcc
    assert "Number.parseInt" not in emcc
    assert "完整 URL 解析、构造和查询参数处理由 `std/uri` 模块承担" in docs
    assert "后续 `std/uri`" not in docs
    assert "queryMode && ch === '+'" in emcc
    assert "entries.push(encodedKey + '=' + encodedValue)" in emcc


def test_e2e_emcc_uri_normalize_preserves_empty_authority_and_empty_path():
    """emcc uriNormalize 应保留原 URL 的空 authority 和无 authority 空 path 语义。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/uri emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}
function getValue() { throw new Error('getValue not used'); }
function setValue() { throw new Error('setValue not used'); }

const library = {};
vm.runInNewContext(code, {
  HEAPU8,
  POINTER_SIZE: 4,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function normalize(url) {
  return UTF8ToString(library.uriNormalize(stringToNewUTF8(url)));
}

assert.strictEqual(normalize('FILE:///tmp/./Ez/../main.ez'), 'file:///tmp/main.ez');
assert.strictEqual(normalize('foo:'), 'foo:');
assert.strictEqual(normalize('foo:?q=1#top'), 'foo:?q=1#top');
assert.strictEqual(normalize('https://EXAMPLE.com/a/../b'), 'https://example.com/b');
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "uri.js")], check=True)


def test_e2e_emcc_uri_decode_rejects_nul_percent_bytes():
    """emcc URI 百分号解码拒绝 Ez Str ABI 无法表达的 NUL。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/uri emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function stringToUTF8(text, ptr, maxBytes) {
  const bytes = Buffer.from(String(text || ''), 'utf8');
  const size = Math.max(0, Math.min(bytes.length, maxBytes - 1));
  HEAPU8.set(bytes.slice(0, size), ptr);
  HEAPU8[ptr + size] = 0;
}
function lengthBytesUTF8(text) {
  return Buffer.byteLength(String(text || ''), 'utf8');
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

const library = {};
vm.runInNewContext(code, {
  HEAPU8,
  POINTER_SIZE: 4,
  _malloc,
  getValue,
  setValue,
  lengthBytesUTF8,
  stringToUTF8,
  UTF8ToString,
  stringToNewUTF8,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function optString(call, args) {
  const ret = _malloc(16);
  library[call](ret, ...args.map(stringToNewUTF8));
  return { ok: HEAPU8[ret] === 1, value: UTF8ToString(getValue(ret + 8, '*')) };
}

function querySet(query, key, value) {
  return UTF8ToString(library.uriQuerySet(stringToNewUTF8(query), stringToNewUTF8(key), stringToNewUTF8(value)));
}

assert.deepStrictEqual(optString('uriDecodeQuery', ['two+words']), { ok: true, value: 'two words' });
assert.deepStrictEqual(optString('uriDecodePathSegment', ['%E4%B8%AD']), { ok: true, value: '中' });
assert.strictEqual(optString('uriDecodeQuery', ['%00']).ok, false);
assert.strictEqual(optString('uriDecodePathSegment', ['a%00b']).ok, false);
assert.strictEqual(optString('uriQueryGet', ['a=%00', 'a']).ok, false);
assert.strictEqual(optString('uriQueryGet', ['a=1&&b=2&', '']).ok, false);
assert.deepStrictEqual(optString('uriQueryGet', ['=empty&a=1', '']), { ok: true, value: 'empty' });
assert.strictEqual(querySet('a=1&&b=2&', 'c', '3'), 'a=1&b=2&c=3');
assert.strictEqual(querySet('a=1&&b=2&', 'b', 'x'), 'a=1&b=x');
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "uri.js")], check=True)


def test_e2e_native_uri_query_set_grows_when_replacing_short_value(tmp_path):
    """native uriQuerySet 替换短参数时必须动态扩容，不能按原 query 长度写溢出。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/uri wrapper")

    harness = tmp_path / "uri_query_set_harness.c"
    harness.write_text(
        r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>

const char *uriQuerySet(const char *query, const char *key, const char *value);

int main(void) {
    const char *long_value = "two words / and symbols";
    const char *replaced = uriQuerySet("a=1&b=x", "b", long_value);
    if (!replaced) return 2;
    if (strcmp(replaced, "a=1&b=two+words+%2F+and+symbols") != 0) {
        fprintf(stderr, "%s\n", replaced);
        return 3;
    }

    const char *added = uriQuerySet("a=1", "space key", "v/v");
    if (!added) return 4;
    if (strcmp(added, "a=1&space+key=v%2Fv") != 0) {
        fprintf(stderr, "%s\n", added);
        return 5;
    }
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "uri_query_set_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "uri.c"),
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_native_uri_decode_rejects_nul_percent_bytes(tmp_path):
    """native URI 百分号解码拒绝 Ez Str ABI 无法表达的 NUL。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/uri wrapper")

    harness = tmp_path / "uri_decode_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

typedef struct { bool ok; const char *value; } OptStr;

OptStr uriDecodeQuery(const char *s);
OptStr uriDecodePathSegment(const char *s);
OptStr uriQueryGet(const char *query, const char *key);

static int expect_value(OptStr got, const char *expected, int code) {
    if (!got.ok || !got.value) return code;
    if (strcmp(got.value, expected) != 0) return code + 1;
    free((void *)got.value);
    return 0;
}

static int expect_empty(OptStr got, int code) {
    if (got.ok || got.value) return code;
    return 0;
}

int main(void) {
    int err = expect_value(uriDecodeQuery("two+words"), "two words", 2);
    if (err != 0) return err;
    err = expect_value(uriDecodePathSegment("%E4%B8%AD"), "\xE4\xB8\xAD", 4);
    if (err != 0) return err;

    err = expect_empty(uriDecodeQuery("%00"), 6);
    if (err != 0) return err;
    err = expect_empty(uriDecodePathSegment("a%00b"), 7);
    if (err != 0) return err;
    err = expect_empty(uriQueryGet("a=%00", "a"), 8);
    if (err != 0) return err;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "uri_decode_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "uri.c"),
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_std_debug_imports_and_builds(tmp_path):
    source = tmp_path / "std_debug.ez"
    source.write_text(
        'from "std/debug" import { debugPrint, debugAssert, debugLocation, debugRuntimeInfo, debugHex, debugStack };\n\n'
        'debugPrint(msg = "hello");\n'
        'debugAssert(condition = true, msg = "ok");\n'
        'let loc = debugLocation(file = "main.ez", line = 1, column = 2);\n'
        'let info = debugRuntimeInfo();\n'
        'let hex = debugHex(data = Blob(data = "ab", size = 2));\n'
        'let stack = debugStack();\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare void @"debugPrint"' in ir_text
    assert 'declare void @"debugAssert"' in ir_text
    assert 'declare i8* @"debugRuntimeInfo"' in ir_text
    assert_native_optional_return(ir_text, "debugStack", "i8*")


def test_e2e_debug_wrappers_cover_crash_hex_and_stack_paths():
    native = (ROOT / "packages" / "std" / "native" / "debug.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "debug.js").read_text(encoding="utf-8")
    ez = (ROOT / "packages" / "std" / "debug.ez").read_text(encoding="utf-8")
    for marker in ["abort();", "backtrace(frames", "backtrace_symbols", "CaptureStackBackTrace", "SymFromAddr", "ezlang native/windows", "ezlang native/linux"]:
        assert marker in native
    for marker in ["EZ_DEBUG_HAS_EXECINFO 0", "EZ_DEBUG_HAS_UNWIND 1", "_Unwind_Backtrace", "ez_debug_unwind_frame", "ezlang native/ios"]:
        assert marker in native
    assert "移动端堆栈显式失败" not in (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")
    assert 'extern "dbghelp" for windows;' in ez
    assert 'static const char hex[] = "0123456789abcdef"' in native
    for marker in ["console.error", "throw new Error", "new Error().stack", "padStart(2, '0')", "ezlang emcc/wasm32", "HEAPU8.length - dataPtr"]:
        assert marker in emcc
    assert "stack.length > 0" in emcc


def test_e2e_mobile_debug_stack_uses_unwind_branch(tmp_path):
    """Android/iOS debugStack 应编译到 _Unwind_Backtrace 地址栈 fallback。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证移动端 debugStack 预处理分支")

    android_obj = tmp_path / "debug_android.o"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-D__ANDROID__=1",
            "-c",
            str(ROOT / "packages" / "std" / "native" / "debug.c"),
            "-o",
            str(android_obj),
        ],
        check=True,
    )


def test_e2e_emcc_debug_stack_returns_none_without_stack_text():
    """emcc debugStack 没有可捕获堆栈文本时应返回空可选值。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/debug emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');

function makeRuntime(ErrorCtor) {
  const memory = new ArrayBuffer(65536);
  const HEAPU8 = new Uint8Array(memory);
  const view = new DataView(memory);
  let heap = 1024;

  function align(value) { return (value + 7) & ~7; }
  function _malloc(size) {
    const ptr = heap;
    heap = align(heap + Math.max(1, size));
    if (heap > HEAPU8.length) throw new Error('oom');
    return ptr;
  }
  function getValue(ptr, type) {
    if (type === '*') return view.getUint32(ptr, true);
    if (type === 'i64') return Number(view.getBigInt64(ptr, true));
    throw new Error('unsupported getValue type ' + type);
  }
  function setValue(ptr, value, type) {
    if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
    if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
    throw new Error('unsupported setValue type ' + type);
  }
  function stringToNewUTF8(text) {
    const bytes = Buffer.from(text, 'utf8');
    const ptr = _malloc(bytes.length + 1);
    HEAPU8.set(bytes, ptr);
    HEAPU8[ptr + bytes.length] = 0;
    return ptr;
  }
  function UTF8ToString(ptr) {
    if (!ptr) return '';
    let end = ptr;
    while (HEAPU8[end] !== 0) end++;
    return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
  }

  const library = {};
  vm.runInNewContext(code, {
    Buffer,
    Error: ErrorCtor || Error,
    HEAPU8,
    _malloc,
    getValue,
    setValue,
    UTF8ToString,
    stringToNewUTF8,
    console: { error() {} },
    LibraryManager: { library },
    mergeInto(target, source) { Object.assign(target, source); },
  }, { filename: process.argv[1] });
  return { library, HEAPU8, view, _malloc, UTF8ToString };
}

function debugStack(runtime) {
  const ret = runtime._malloc(16);
  runtime.library.debugStack(ret);
  const ok = runtime.HEAPU8[ret] !== 0;
  const valuePtr = runtime.view.getUint32(ret + 8, true);
  return { ok, valuePtr };
}

function makeBlob(runtime, dataPtr, size) {
  const blob = runtime._malloc(16);
  runtime.view.setUint32(blob, dataPtr, true);
  runtime.view.setBigInt64(blob + 8, BigInt(size), true);
  return blob;
}

function makeByteBlob(runtime, bytes) {
  const data = runtime._malloc(bytes.length);
  runtime.HEAPU8.set(bytes, data);
  return makeBlob(runtime, data, bytes.length);
}

function debugHex(runtime, blob) {
  return runtime.library.debugHex(blob);
}

let runtime = makeRuntime();
assert.strictEqual(runtime.UTF8ToString(debugHex(runtime, makeByteBlob(runtime, [0xab, 0xcd]))), 'abcd');
assert.strictEqual(runtime.UTF8ToString(debugHex(runtime, makeBlob(runtime, 0, 1))), '');
assert.strictEqual(runtime.UTF8ToString(debugHex(runtime, makeBlob(runtime, runtime.HEAPU8.length - 1, 2))), '');

let result = debugStack(runtime);
assert.strictEqual(result.ok, true);
assert.notStrictEqual(result.valuePtr, 0);

function EmptyStackError(message) {
  this.message = message || '';
  this.stack = '';
}
EmptyStackError.prototype = Object.create(Error.prototype);
EmptyStackError.prototype.constructor = EmptyStackError;

result = debugStack(makeRuntime(EmptyStackError));
assert.strictEqual(result.ok, false);
assert.strictEqual(result.valuePtr, 0);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "debug.js")], check=True)


def test_e2e_std_log_imports_and_builds(tmp_path):
    source = tmp_path / "std_log.ez"
    source.write_text(
        'from "std/log" import { logTrace, logDebug, logInfo, logWarn, logError, logTargetStderr, logTargetFile, LogConfig, logDefaultConfig, logConfigure, logSetLevel, logSetFile, logWrite, logWriteFields, logWriteAt, logInfoMsg, logWarnMsg, logErrorMsg };\n\n'
        'let cfg = logDefaultConfig();\n'
        'logConfigure(config = LogConfig(minLevel = logDebug, target = logTargetStderr, includeTimestamp = true, includeLocation = true));\n'
        'logSetLevel(level = logTrace);\n'
        'let fileOk = logSetFile(path = "build.log");\n'
        'logConfigure(config = LogConfig(minLevel = logTrace, target = logTargetFile, includeTimestamp = false, includeLocation = true));\n'
        'logWrite(level = logInfo, msg = "hello");\n'
        'logWriteFields(level = logWarn, msg = "warn", fields = ["key", "value"]);\n'
        'logWriteAt(level = logError, msg = "err", file = "main.ez", line = 1, column = 2, fields = ["code", "1"]);\n'
        'logInfoMsg(msg = "info");\n'
        'logWarnMsg(msg = "warn");\n'
        'logErrorMsg(msg = "error");\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert '%"LogConfig" = type' in ir_text
    log_config_abi = "[2 x i64]" if ez._native_arch() == "aarch64" else "{i64, i32}"
    assert_native_small_struct_return(ir_text, "logDefaultConfig", "LogConfig", log_config_abi)
    assert 'declare void @"logWrite"' in ir_text
    assert 'declare void @"logWriteAt"' in ir_text
    assert 'declare i1 @"logSetFile"' in ir_text


def test_e2e_std_test_supports_exceptions_parameters_and_diagnostics(tmp_path):
    source = tmp_path / "std_test.ez"
    source.write_text(
        'from "std/test" import { testReset, testRegister, testRegisterParam, testCount, testName, testThrows, testEqualStr, testPassed };\n\n'
        'const fail = (): Void => { throw Error(code = 4, message = "boom"); };\n'
        'const check = (): I32 => {\n'
        '    testReset();\n'
        '    testRegister(name = "check");\n'
        '    testRegisterParam(name = "table", param = "4");\n'
        '    testThrows(body = fail, expectedCode = 4, msg = "throws");\n'
        '    testEqualStr(actual = testName(index = 1), expected = "table[4]", msg = "param name");\n'
        '    return testPassed() + testCount();\n'
        '};\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_text = (tmp_path / "dist" / "native" / "e2e.ll").read_text(encoding="utf-8")
    for marker in [
        'define void @"testThrows"',
        'declare void @"testRegisterParam"',
        'declare i32 @"testCount"',
        'declare i8* @"testName"',
        '@"__ezrt_throw_active" = internal global i1 0',
    ]:
        assert marker in ir_text

    native = (ROOT / "packages" / "std" / "native" / "test.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "test.js").read_text(encoding="utf-8")
    for marker in ["remember_test_name", "testRegisterParam", "testName", "g_current_test"]:
        assert marker in native
    for marker in ["var tests = []", "testRegisterParam", "testName", "currentTest"]:
        assert marker in emcc
    assert "function i64Value" in emcc


def test_e2e_emcc_test_i64_assertions_compare_bigint_exactly():
    """emcc testEqualI64/testNotEqualI64 不能把 I64 降成 Number 后比较。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/test emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

const errors = [];
const library = {};
vm.runInNewContext(code, {
  BigInt,
  Buffer,
  HEAPU8,
  UTF8ToString,
  stringToNewUTF8,
  console: { error(msg) { errors.push(String(msg)); }, warn() {} },
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

const label = stringToNewUTF8('wide i64');
library.testReset();
library.testEqualI64(9007199254740993n, 9007199254740993n, label);
library.testNotEqualI64(9007199254740992n, 9007199254740993n, label);
assert.strictEqual(library.testPassed(), 2);

assert.throws(() => library.testEqualI64(9007199254740992n, 9007199254740993n, label), /wide i64/);
assert.ok(errors[0].includes('expected 9007199254740993, got 9007199254740992'));
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "test.js")], check=True)


def test_e2e_log_wrappers_cover_file_target_mobile_logs_and_emcc_console():
    """std/log 应覆盖文件目标、移动端系统日志与 emcc console 边界。"""
    native = (ROOT / "packages" / "std" / "native" / "log.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "log.js").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")

    for marker in ["EZ_LOG_TARGET_FILE", "fopen(path, \"a\")", "logSetFile", "fflush(out)"]:
        assert marker in native
    assert "__android_log_write" in native
    assert "os_log_with_type" in native
    assert "appendFileSync" in emcc
    assert "FS.writeFile" in emcc
    assert "config.target = TARGET_FILE" in emcc_js_function_body(emcc, "logSetFile")
    assert "function runtimeConsole" in emcc
    assert "out.error" in emcc and "out.warn" in emcc and "out.log" in emcc
    assert "原生平台支持 stderr/stdout/file" in docs
    assert "Emscripten FS 或 Node 同步文件系统" in docs
    assert "移动端非文件目标同步写系统日志" in docs


def test_e2e_emcc_log_set_file_supports_node_fs_and_browser_fallback(tmp_path):
    """emcc 日志在 Node 下同步追加写文件；无同步文件系统时显式失败。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/log emcc wrapper")
    log_path = tmp_path / "runtime.log"
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const logPath = process.argv[2];

function makeRuntime(extra) {
  const memory = new ArrayBuffer(65536);
  const HEAPU8 = new Uint8Array(memory);
  const view = new DataView(memory);
  let heap = 1024;
  function align(value) { return (value + 7) & ~7; }
  function _malloc(size) {
    const ptr = heap;
    heap = align(heap + Math.max(1, size));
    if (heap > HEAPU8.length) throw new Error('oom');
    return ptr;
  }
  function getValue(ptr, type) {
    if (type === '*') return view.getUint32(ptr, true);
    if (type === 'i64') return Number(view.getBigInt64(ptr, true));
    if (type === 'i32') return view.getInt32(ptr, true);
    throw new Error('unsupported getValue type ' + type);
  }
  function setValue(ptr, value, type) {
    if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
    if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
    if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
    throw new Error('unsupported setValue type ' + type);
  }
  function stringToNewUTF8(text) {
    const bytes = Buffer.from(text, 'utf8');
    const ptr = _malloc(bytes.length + 1);
    HEAPU8.set(bytes, ptr);
    HEAPU8[ptr + bytes.length] = 0;
    return ptr;
  }
  function UTF8ToString(ptr) {
    if (!ptr) return '';
    let end = ptr;
    while (HEAPU8[end] !== 0) end++;
    return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
  }
  const library = {};
  const context = Object.assign({
    Buffer,
    HEAPU8,
    POINTER_SIZE: 4,
    _malloc,
    getValue,
    setValue,
    UTF8ToString,
    stringToNewUTF8,
    console: { log() {}, warn() {}, error() {} },
    LibraryManager: { library },
    mergeInto(target, source) { Object.assign(target, source); },
  }, extra || {});
  vm.runInNewContext(code, context, { filename: process.argv[1] });
  return { library, HEAPU8, _malloc, setValue, stringToNewUTF8 };
}

let runtime = makeRuntime({ require });
const cfg = runtime._malloc(16);
runtime.setValue(cfg, 0, 'i32');
runtime.setValue(cfg + 4, 3, 'i32');
runtime.HEAPU8[cfg + 8] = 0;
runtime.HEAPU8[cfg + 9] = 1;
assert.strictEqual(runtime.library.logSetFile(runtime.stringToNewUTF8(logPath)), 1);
runtime.library.logConfigure(cfg);
runtime.library.logWriteAt(
  4,
  runtime.stringToNewUTF8('err'),
  runtime.stringToNewUTF8('main.ez'),
  1,
  2,
  0
);
assert.strictEqual(fs.readFileSync(logPath, 'utf8'), 'ERROR err @ main.ez:1:2\n');

runtime = makeRuntime({});
assert.strictEqual(runtime.library.logSetFile(runtime.stringToNewUTF8(logPath + '.browser')), 0);

runtime = makeRuntime({ console: undefined });
assert.doesNotThrow(() => runtime.library.logWrite(4, runtime.stringToNewUTF8('without console')));
'''
    subprocess.run(
        [node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "log.js"), str(log_path)],
        check=True,
    )


def test_e2e_std_regex_imports_and_builds(tmp_path):
    source = tmp_path / "std_regex.ez"
    source.write_text(
        'from "std/regex" import { regexIgnoreCase, Regex, RegexMatch, regexCompile, regexIsValid, regexTest, regexFind, regexFindAll, regexReplace, regexSplit };\n\n'
        'let re = regexCompile(pattern = "([a-z]+)", flags = regexIgnoreCase);\n'
        'let valid = regexIsValid(regex = re);\n'
        'let matched = regexTest(regex = re, input = "Hello 42");\n'
        'let found = regexFind(regex = re, input = "Hello 42");\n'
        'let all = regexFindAll(regex = re, input = "a b c");\n'
        'let replaced = regexReplace(regex = re, input = "abc", replacement = "x");\n'
        'let parts = regexSplit(regex = re, input = "a,b,c");\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert '%"Regex" = type' in ir_text
    assert '%"RegexMatch" = type' in ir_text
    regex_abi = "[2 x i64]" if ez._native_arch() == "aarch64" else "{i8*, i64}"
    assert_native_small_struct_return(ir_text, "regexCompile", "Regex", regex_abi)
    assert 'declare void @"regexFind"({i1, %"RegexMatch"}* sret({i1, %"RegexMatch"})' in ir_text
    assert 'declare i8* @"regexReplace"' in ir_text


def test_e2e_std_crypto_imports_and_builds(tmp_path):
    source = tmp_path / "std_crypto.ez"
    source.write_text(
        'from "std/crypto" import { cryptoSha256, cryptoSha512, cryptoHmacSha256, cryptoHmacSha512 };\n\n'
        'let data = Blob(data = "hello", size = 5);\n'
        'let key = Blob(data = "key", size = 3);\n'
        'let sha256 = cryptoSha256(data = data);\n'
        'let sha512 = cryptoSha512(data = data);\n'
        'let h256 = cryptoHmacSha256(key = key, data = data);\n'
        'let h512 = cryptoHmacSha512(key = key, data = data);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare void @"cryptoSha256"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
    assert 'declare void @"cryptoSha512"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
    assert 'declare void @"cryptoHmacSha256"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text


def test_e2e_crypto_wrappers_provide_sync_fallbacks():
    native = (ROOT / "packages" / "std" / "native" / "crypto.c").read_text(encoding="utf-8")
    portable = (ROOT / "packages" / "std" / "native" / "crypto_portable.inc").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "crypto.js").read_text(encoding="utf-8")
    for marker in ["CommonCrypto", "dlopen", "EVP_sha256", "HMAC", "bcrypt.h", "EZ_CRYPTO_HAS_PORTABLE", "crypto_portable.inc"]:
        assert marker in native
    for marker in ["EZ_CRYPTO_FORCE_PORTABLE", "ez_sha256_transform", "ez_sha512_transform", "ez_hmac_sha512_alloc", "ez_rotr64"]:
        assert marker in native or marker in portable
    for marker in ["require('crypto')", "createHash", "createHmac", "sha256Bytes", "sha512Bytes", "hmacBytes", "HEAPU8.length - dataPtr"]:
        assert marker in emcc


def test_e2e_native_crypto_platform_vectors(tmp_path):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 std/crypto 平台库封装")
    source = ROOT / "compiler" / "tests" / "fixtures" / "crypto_platform_check.c"
    exe = tmp_path / "crypto_platform_check"
    cmd = [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)]
    if sys.platform.startswith("linux"):
        cmd.append("-lcrypto")
    elif sys.platform == "win32":
        cmd.append("-lbcrypt")
    elif sys.platform != "darwin":
        pytest.skip("当前平台没有 std/crypto 原生平台库向量测试配置")
    subprocess.run(cmd, check=True)
    result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    assert result.stdout.splitlines() == [
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        "9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043",
        "9307b3b915efb5171ff14d8cb55fbcc798c6c0ef1456d66ded1a6aa723a58b7b",
        "ff06ab36757777815c008d32c8e14a705b4e7bf310351a06a23b612dc4c7433e7757d20525a5593b71020ea2ee162d2311b247e9855862b270122419652c0c92",
    ]


def test_e2e_native_crypto_portable_vectors(tmp_path):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 std/crypto portable fallback")
    source = ROOT / "compiler" / "tests" / "fixtures" / "crypto_portable_check.c"
    exe = tmp_path / "crypto_portable_check"
    subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)], check=True)
    result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    assert result.stdout.splitlines() == [
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        "9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043",
        "9307b3b915efb5171ff14d8cb55fbcc798c6c0ef1456d66ded1a6aa723a58b7b",
        "ff06ab36757777815c008d32c8e14a705b4e7bf310351a06a23b612dc4c7433e7757d20525a5593b71020ea2ee162d2311b247e9855862b270122419652c0c92",
    ]


def test_e2e_native_crypto_linux_dlopen_failure_uses_portable_vectors(tmp_path):
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux 动态 OpenSSL fallback 测试仅在 Linux 运行")
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 std/crypto Linux fallback")
    source = ROOT / "compiler" / "tests" / "fixtures" / "crypto_platform_check.c"
    exe = tmp_path / "crypto_linux_fallback_check"
    subprocess.run([
        cc,
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-DEZ_CRYPTO_TEST_NO_OPENSSL_DLOPEN=1",
        str(source),
        "-ldl",
        "-o",
        str(exe),
    ], check=True)
    result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    assert result.stdout.splitlines() == [
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        "9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043",
        "9307b3b915efb5171ff14d8cb55fbcc798c6c0ef1456d66ded1a6aa723a58b7b",
        "ff06ab36757777815c008d32c8e14a705b4e7bf310351a06a23b612dc4c7433e7757d20525a5593b71020ea2ee162d2311b247e9855862b270122419652c0c92",
    ]


def test_e2e_std_compress_imports_and_builds(tmp_path):
    source = tmp_path / "std_compress.ez"
    source.write_text(
        'from "std/compress" import { compressGzip, decompressGzip, compressZlib, decompressZlib, compressDeflate, decompressDeflate, compressGzipStream, decompressGzipStream, compressZlibStream, decompressZlibStream, compressDeflateStream, decompressDeflateStream };\n'
        'from "std/stream" import { streamFromBlob };\n\n'
        'let data = Blob(data = "hello", size = 5);\n'
        'let gz = compressGzip(data = data);\n'
        'let raw_gz = decompressGzip(data = gz.value);\n'
        'let z = compressZlib(data = data);\n'
        'let raw_z = decompressZlib(data = z.value);\n'
        'let d = compressDeflate(data = data);\n'
        'let raw_d = decompressDeflate(data = d.value);\n'
        'let src = streamFromBlob(data = data);\n'
        'let dst = streamFromBlob(data = Blob(data = "", size = 0));\n'
        'let streamed_gz = compressGzipStream(dst = dst.value, src = src.value, bufferSize = 2);\n'
        'let streamed_raw_gz = decompressGzipStream(dst = dst.value, src = src.value, bufferSize = 2);\n'
        'let streamed_z = compressZlibStream(dst = dst.value, src = src.value, bufferSize = 2);\n'
        'let streamed_raw_z = decompressZlibStream(dst = dst.value, src = src.value, bufferSize = 2);\n'
        'let streamed_d = compressDeflateStream(dst = dst.value, src = src.value, bufferSize = 2);\n'
        'let streamed_raw_d = decompressDeflateStream(dst = dst.value, src = src.value, bufferSize = 2);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare void @"compressGzip"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
    assert 'declare void @"decompressGzip"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
    assert 'declare void @"compressDeflate"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
    assert 'declare i64 @"compressGzipStream"(%"Stream"*' in ir_text


def test_e2e_compress_wrappers_use_zlib_and_reject_invalid_blobs():
    native = (ROOT / "packages" / "std" / "native" / "compress.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "compress.js").read_text(encoding="utf-8")
    stream_interface = (ROOT / "packages" / "std" / "stream.ez").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")
    api_docs = (ROOT / "docs" / "stdlib-api.md").read_text(encoding="utf-8")
    architecture_docs = (ROOT / "docs" / "compiler-architecture.md").read_text(encoding="utf-8")

    for marker in ["defined(_WIN32)", "#include <zlib.h>", "deflateInit2", "inflateInit2", "!ez_blob_bytes", "ez_zlib_stream_run", "streamRead", "streamWrite"]:
        assert marker in native
    for marker in [
        "require('zlib')", "gzipSync", "inflateRawSync", "CompressionStream", "DecompressionStream",
        "Asyncify.handleAsync", "compressGzip__async: 'auto'", "decompressGzipStream__async: 'auto'",
        "input === null", "writeOptBlob", "HEAPU8.length - dataPtr", "runStream", "streamRead", "streamWrite",
    ]:
        assert marker in emcc
    assert "Windows native 当前返回空可选值" not in api_docs
    assert "Windows native 当前返回空可选值" not in docs
    assert "流式压缩接口等待" not in api_docs
    assert "流式压缩接口等待" not in docs
    for text in [stream_interface, docs, api_docs, architecture_docs]:
        assert "压缩流后续" not in text
        assert "后续进程管道和压缩流" not in text
    assert "compressGzipStream" in api_docs
    assert "compressGzipStream" in docs
    assert "std/compress" in stream_interface
    assert "std/compress" in api_docs
    assert "| `std/stream` | 运行时 ABI 封装 | 内存/Blob、文件流、TCP 流" in docs
    assert "native 目标使用系统 zlib" in api_docs
    assert "CompressionStream` / `DecompressionStream`" in api_docs


def test_e2e_native_compress_zlib_vectors(tmp_path):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 std/compress zlib 封装")
    source = ROOT / "compiler" / "tests" / "fixtures" / "compress_zlib_check.c"
    exe = tmp_path / "compress_zlib_check"
    subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(source), str(ROOT / "packages" / "std" / "native" / "stream.c"), "-o", str(exe), "-lz"], check=True)
    result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    lines = result.stdout.splitlines()
    assert len(lines) == 2
    assert all(re.fullmatch(r"[0-9a-f]+", line) for line in lines)


def test_e2e_emcc_compress_node_zlib_vectors():
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/compress emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const zlib = require('zlib');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(0, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  if (type === 'i32') return view.getInt32(ptr, true);
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}

const library = {};
vm.runInNewContext(code, {
  require,
  Buffer,
  Uint8Array,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function allocBlob(bytes) {
  const blob = _malloc(16);
  let dataPtr = 0;
  if (bytes.length > 0) {
    dataPtr = _malloc(bytes.length);
    HEAPU8.set(bytes, dataPtr);
  }
  setValue(blob, dataPtr, '*');
  setValue(blob + 8, bytes.length, 'i64');
  return blob;
}
function call(name, blob) {
  const ret = _malloc(32);
  library[name](ret, blob);
  const ok = HEAPU8[ret] !== 0;
  const dataPtr = getValue(ret + 8, '*');
  const size = getValue(ret + 16, 'i64');
  return { ok, bytes: HEAPU8.slice(dataPtr, dataPtr + size) };
}
function text(result) { return Buffer.from(result.bytes).toString('utf8'); }
const streamSources = new Map();
function allocStream(bytes) {
  const stream = _malloc(16);
  const data = Buffer.from(bytes || []);
  streamSources.set(stream, { data, cursor: 0 });
  return { ptr: stream, chunks: [] };
}
function streamBytes(stream) {
  return Buffer.concat(stream.chunks.map((chunk) => Buffer.from(chunk)));
}

const plain = Buffer.from('hello hello hello');
const plainBlob = allocBlob(plain);
const gz = call('compressGzip', plainBlob);
const z = call('compressZlib', plainBlob);
const raw = call('compressDeflate', plainBlob);
assert(gz.ok && z.ok && raw.ok);
assert.strictEqual(zlib.gunzipSync(Buffer.from(gz.bytes)).toString('utf8'), 'hello hello hello');
assert.strictEqual(zlib.inflateSync(Buffer.from(z.bytes)).toString('utf8'), 'hello hello hello');
assert.strictEqual(zlib.inflateRawSync(Buffer.from(raw.bytes)).toString('utf8'), 'hello hello hello');

assert.strictEqual(text(call('decompressGzip', allocBlob(zlib.gzipSync(plain)))), 'hello hello hello');
assert.strictEqual(text(call('decompressZlib', allocBlob(zlib.deflateSync(plain)))), 'hello hello hello');
assert.strictEqual(text(call('decompressDeflate', allocBlob(zlib.deflateRawSync(plain)))), 'hello hello hello');

const invalidData = allocBlob(Buffer.from('not gzip'));
assert.strictEqual(call('decompressGzip', invalidData).ok, false);
assert.strictEqual(call('decompressZlib', invalidData).ok, false);
assert.strictEqual(call('decompressDeflate', invalidData).ok, false);
const invalidBlob = _malloc(16);
setValue(invalidBlob, 0, '*');
setValue(invalidBlob + 8, 1, 'i64');
const outOfBoundsBlob = _malloc(16);
setValue(outOfBoundsBlob, HEAPU8.length - 1, '*');
setValue(outOfBoundsBlob + 8, 2, 'i64');
assert.strictEqual(call('compressGzip', invalidBlob).ok, false);
assert.strictEqual(call('compressZlib', invalidBlob).ok, false);
assert.strictEqual(call('compressDeflate', invalidBlob).ok, false);
assert.strictEqual(call('compressGzip', outOfBoundsBlob).ok, false);
assert.strictEqual(call('compressZlib', outOfBoundsBlob).ok, false);
assert.strictEqual(call('compressDeflate', outOfBoundsBlob).ok, false);

library.streamRead = function (ret, srcPtr, maxBytes) {
  const source = streamSources.get(srcPtr);
  if (!source) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, '*');
    setValue(ret + 16, 0, 'i64');
    return;
  }
  const cursor = source.cursor;
  const size = source.data.length;
  const count = Math.min(Math.max(Number(maxBytes), 0), Math.max(size - cursor, 0));
  const outPtr = count > 0 ? _malloc(count) : 0;
  if (count > 0) HEAPU8.set(source.data.slice(cursor, cursor + count), outPtr);
  source.cursor += count;
  HEAPU8[ret] = 1;
  setValue(ret + 8, outPtr, '*');
  setValue(ret + 16, count, 'i64');
};
const streamSinks = new Map();
library.streamWrite = function (dstPtr, blobPtr) {
  const dataPtr = getValue(blobPtr, '*');
  const size = getValue(blobPtr + 8, 'i64');
  if (size < 0 || (size > 0 && !dataPtr)) return -1;
  const sink = streamSinks.get(dstPtr);
  if (!sink) return -1;
  sink.chunks.push(HEAPU8.slice(dataPtr, dataPtr + size));
  return size;
};
library.streamFlush = function (dstPtr) {
  return streamSinks.has(dstPtr) ? 1 : 0;
};
function callStream(compressName, decompressName, nodeDecode) {
  const src = allocStream(plain);
  const compressed = allocStream([]);
  streamSinks.set(compressed.ptr, compressed);
  const written = library[compressName](compressed.ptr, src.ptr, 3);
  assert(written > 0, compressName);
  const compressedBytes = streamBytes(compressed);
  assert.strictEqual(nodeDecode(compressedBytes).toString('utf8'), 'hello hello hello');
  const roundtripSrc = allocStream(compressedBytes);
  const restored = allocStream([]);
  streamSinks.set(restored.ptr, restored);
  assert.strictEqual(library[decompressName](restored.ptr, roundtripSrc.ptr, 2), plain.length, decompressName);
  assert.strictEqual(streamBytes(restored).toString('utf8'), 'hello hello hello');
}
callStream('compressGzipStream', 'decompressGzipStream', (bytes) => zlib.gunzipSync(bytes));
callStream('compressZlibStream', 'decompressZlibStream', (bytes) => zlib.inflateSync(bytes));
callStream('compressDeflateStream', 'decompressDeflateStream', (bytes) => zlib.inflateRawSync(bytes));
assert.strictEqual(library.decompressGzipStream(allocStream([]).ptr, allocStream(Buffer.from('not gzip')).ptr, 2), -1);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "compress.js")], check=True)


def test_e2e_emcc_compress_web_streams_bridge():
    """emcc compress 在浏览器/Worker 能通过 CompressionStream + Asyncify 桥接。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/compress emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;
const calls = [];

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(0, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function _free() {}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  if (type === 'i32') return view.getInt32(ptr, true);
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
class SyncPromise {
  constructor(executor) {
    this.value = undefined;
    this.error = undefined;
    executor(
      (value) => { this.value = value instanceof SyncPromise ? value.value : value; },
      (error) => { this.error = error; }
    );
  }
  then(onFulfilled, onRejected) {
    return new SyncPromise((resolve, reject) => {
      try {
        if (this.error !== undefined) resolve(onRejected ? onRejected(this.error) : undefined);
        else resolve(onFulfilled ? onFulfilled(this.value) : this.value);
      } catch (error) {
        reject(error);
      }
    });
  }
}
class FakeBlob {
  constructor(parts) { this.bytes = Buffer.concat(parts.map((part) => Buffer.from(part))); }
  stream() { return { bytes: this.bytes, pipeThrough(transform) { return { bytes: transform.apply(this.bytes) }; } }; }
}
class FakeCompressionStream {
  constructor(format) { this.format = format; calls.push(['c', format]); }
  apply(bytes) { return Buffer.concat([Buffer.from('C:' + this.format + ':'), Buffer.from(bytes)]); }
}
class FakeDecompressionStream {
  constructor(format) { this.format = format; calls.push(['d', format]); }
  apply(bytes) { return Buffer.concat([Buffer.from('D:' + this.format + ':'), Buffer.from(bytes)]); }
}
class FakeResponse {
  constructor(stream) { this.stream = stream; }
  arrayBuffer() { return new SyncPromise((resolve) => resolve(this.stream.bytes.buffer.slice(this.stream.bytes.byteOffset, this.stream.bytes.byteOffset + this.stream.bytes.byteLength))); }
}

const library = {};
const context = {
  Buffer,
  Uint8Array,
  HEAPU8,
  _malloc,
  _free,
  getValue,
  setValue,
  Promise: SyncPromise,
  Blob: FakeBlob,
  Response: FakeResponse,
  CompressionStream: FakeCompressionStream,
  DecompressionStream: FakeDecompressionStream,
  Asyncify: { handleAsync(fn) { const value = fn(); return value instanceof SyncPromise ? value.value : value; } },
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
};
vm.runInNewContext(code, context, { filename: process.argv[1] });

function allocBlob(text) {
  const bytes = Buffer.from(text, 'utf8');
  const blob = _malloc(16);
  const data = _malloc(bytes.length);
  HEAPU8.set(bytes, data);
  setValue(blob, data, '*');
  setValue(blob + 8, bytes.length, 'i64');
  return blob;
}
function call(name, blob) {
  const ret = _malloc(32);
  library[name](ret, blob);
  const ok = HEAPU8[ret] !== 0;
  const dataPtr = getValue(ret + 8, '*');
  const size = getValue(ret + 16, 'i64');
  return { ok, text: Buffer.from(HEAPU8.slice(dataPtr, dataPtr + size)).toString('utf8') };
}
assert.deepStrictEqual(call('compressGzip', allocBlob('x')), { ok: true, text: 'C:gzip:x' });
assert.deepStrictEqual(call('decompressZlib', allocBlob('y')), { ok: true, text: 'D:deflate:y' });
assert.deepStrictEqual(call('compressDeflate', allocBlob('z')), { ok: true, text: 'C:deflate-raw:z' });
assert.deepStrictEqual(calls, [['c', 'gzip'], ['d', 'deflate'], ['c', 'deflate-raw']]);

const noAsync = {};
vm.runInNewContext(code, Object.assign({}, context, { Asyncify: undefined, LibraryManager: { library: noAsync } }), { filename: process.argv[1] });
const ret = _malloc(32);
noAsync.compressGzip(ret, allocBlob('x'));
assert.strictEqual(HEAPU8[ret], 0);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "compress.js")], check=True)


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
    assert 'declare void @"args"({i8***, i64, i64, i64}* sret({i8***, i64, i64, i64})' in ir_text
    assert_native_optional_return(ir_text, "env", "i8*")
    assert 'declare i1 @"setEnv"' in ir_text
    assert 'declare i8* @"cwd"' in ir_text
    assert 'declare void @"exit"' in ir_text
    assert 'declare i32 @"pid"' in ir_text
    assert 'declare i8* @"platform"' in ir_text
    assert 'declare i8* @"arch"' in ir_text


def test_e2e_std_time_imports_and_builds(tmp_path):
    source = tmp_path / "std_time.ez"
    source.write_text(
        'from "std/time" import { Duration, durationToString, now, timestamp, sleep, getYear, getMonth, getDay, getHour, getMinute, getSecond, add, sub, format };\n\nlet seconds = Duration.fromSec(s = 2);\nlet minutes = Duration.fromMin(m = 1);\nlet duration_text = seconds.toString();\nlet duration_fn_text = durationToString(value = minutes);\nlet current = now();\nlet ts = timestamp();\nsleep(ms = 1);\nlet year = getYear(this = #current);\nlet month = getMonth(this = #current);\nlet day = getDay(this = #current);\nlet hour = getHour(this = #current);\nlet minute = getMinute(this = #current);\nlet second = getSecond(this = #current);\nadd(this = #current, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\nsub(this = #current, year = 0, month = 1, day = 0, hour = 0, minute = 0, second = 0);\nlet formatted = format(this = #current, fmt = "YYYY-MM-DD");\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert_native_small_struct_return(ir_text, "now", "Date", "i64")
    assert 'declare i64 @"timestamp"' in ir_text
    assert 'declare void @"sleep"' in ir_text
    assert 'define i32 @"getYear"' in ir_text
    assert 'declare i32 @"dateGetYear"' in ir_text
    assert 'define i32 @"getHour"' in ir_text
    assert 'declare i32 @"dateGetHour"' in ir_text
    assert 'define void @"add"' in ir_text
    assert 'declare void @"dateAdd"' in ir_text
    assert 'declare i8* @"dateFormat"' in ir_text
    assert 'define %"Duration" @"Duration_fromSec"' in ir_text
    assert 'define i8* @"Duration_toString"' in ir_text
    assert 'declare i8* @"__durationToString"' in ir_text


def test_e2e_time_wrappers_use_millisecond_clock_sleep_and_utc_fields():
    native = (ROOT / "packages" / "std" / "native" / "time.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "time.js").read_text(encoding="utf-8")
    for marker in ["/ 10000ULL", "gettimeofday", "nanosleep", "gmtime_r", "timegm", "ez_reserve", "ez_format_percent_token", "__durationToString"]:
        assert marker in native
    for marker in ["__durationToString", "Date.now()", "Atomics.wait", "while (Date.now() < end)", "getUTCFullYear", "setUTCFullYear", "percentToken", "namedToken"]:
        assert marker in emcc


def test_e2e_std_net_http_client_imports_and_builds(tmp_path):
    source = tmp_path / "std_http_client.ez"
    source.write_text(
        'from "std/net/http" import { fetch, fetchEx, HttpRequest, HttpResponse };\n\nlet headers = { accept: Str = "application/json" };\nlet empty_body = Blob(data = "", size = 0);\nlet req = HttpRequest(method = "GET", url = "https://example.com", headers = headers, body = empty_body);\nlet req_without_body = HttpRequest(method = "GET", url = "https://example.com", headers = headers, body = ?);\nlet res1 = fetch(url = "https://example.com");\nlet res2 = fetchEx(req = req);\nlet res3 = fetchEx(req = req_without_body);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert '%"HttpRequest" = type' in ir_text
    assert '%"HttpRequest" = type {i8*, i8*, %"Dict", {i1, %"Blob"}}' in ir_text
    assert '%"HttpResponse" = type' in ir_text
    assert 'declare void @"fetch"({i1, %"HttpResponse"}* sret({i1, %"HttpResponse"})' in ir_text
    assert 'declare void @"fetchEx"({i1, %"HttpResponse"}* sret({i1, %"HttpResponse"})' in ir_text



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
    assert_native_small_struct_return(ir_text, "createServer", "HttpServer", "i64")
    assert 'on' in ir_text
    assert 'start' in ir_text
    assert 'stop' in ir_text


def test_e2e_std_net_http_native_and_emcc_server_support_are_explicit():
    """HTTP 原生服务端与 emcc Node 服务端都有真实实现，浏览器环境仍失败。"""
    native = (ROOT / "packages" / "std" / "native" / "net" / "http.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "net" / "http.js").read_text(encoding="utf-8")
    interface = (ROOT / "packages" / "std" / "net" / "http.ez").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")

    assert "ez_http_fetch" in native
    assert "getaddrinfo" in native
    assert "send(sock" in native
    assert "recv(sock" in native
    assert "ez_decode_chunked_body" in native
    assert '"https://"' in native
    assert 'strcpy(out->port, tls ? "443" : "80")' in native
    assert "ez_http_load_tls" in native
    assert "OPENSSL_init_ssl" in native
    assert "X509_VERIFY_PARAM_set1_host" in native
    assert "X509_VERIFY_PARAM_set1_ip_asc" in native
    assert "SSL_get_verify_result" in native
    assert "ez_http_conn_send_all" in native
    assert 'extern "dl" for linux;' in interface
    assert "fragment_start" in native
    assert "*authority_end == '?'" in native
    assert "ez_parse_http_port" in native
    assert "ez_make_host_header" in native
    assert "memchr(host_start, ']'" in native
    for marker in ["XMLHttpRequest", "xhr.open(req.method || 'GET', req.url, false)", "parseResponseHeaders", "writeOptResponse"]:
        assert marker in emcc
    for marker in ["nodeRequire('http')", "http.createServer", "HttpServer_start__async: 'auto'", "callHandler"]:
        assert marker in emcc
    for marker in ["HttpServer_on", "HttpServer_start", "HttpServer_stop", "ez_http_handle_client", "ez_http_listen_socket"]:
        assert marker in native
    for marker in ["ez_http_client_worker", "active_workers", "pthread_create", "CreateThread", "ez_http_wait_workers"]:
        assert marker in native
    assert "HTTP 服务端当前明确不支持" not in interface
    assert "原生平台支持基础 HTTP 服务端" in docs
    assert "HTTP/HTTPS 客户端；基础服务端" in docs
    assert "可加载 OpenSSL TLS 后端且证书链与主机名校验通过时支持 `https://`" in docs
    assert "复用原生封装，支持明文 `http://` 客户端和每连接 worker 服务端" in docs
    assert 'extern "ws2_32" for windows;' in interface
    assert 'extern "pthread" for linux;' in interface
    assert "chunked 响应体" in docs
    assert "后续接入真实网络实现" not in docs
    assert "`fetch` + Asyncify 挂起客户端请求" in docs
    assert "Node 风格运行时支持基础 HTTP 服务端" in docs
    assert "后续接入 TLS、超时配置和 native 事件源式 flow 挂起" not in docs
    assert "后续接入超时配置和 native 事件源式 flow 挂起" not in docs
    assert "后续接入 native 事件源式 flow 挂起" in docs
    assert "HTTP 服务端并发 worker" not in docs
    create_server_body = native[native.index("HttpServer createServer"):native.index("void HttpServer_on")]
    assert "calloc" in create_server_body
    assert "return (HttpServer){(int64_t)(uintptr_t)server};" in create_server_body


def test_e2e_native_http_fetch_ex_rejects_invalid_body_blob_before_connect(tmp_path):
    """fetchEx 遇到非法请求体 Blob 应直接失败，不发起网络连接。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/net/http wrapper")

    harness = tmp_path / "http_invalid_body_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stddef.h>

typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { bool ok; Blob value; } OptBlob;
typedef struct { char ***key_pages; char ***value_pages; int32_t count; int32_t capacity; int32_t page_count; } Dict;
typedef struct { int32_t status; Dict headers; Blob body; } HttpResponse;
typedef struct { const char *method; const char *url; Dict headers; OptBlob body; } HttpRequest;
typedef struct { bool ok; HttpResponse value; } OptHttpResponse;

OptHttpResponse fetchEx(const HttpRequest *req);

int main(void) {
    HttpRequest none = {"POST", "http://127.0.0.1:1/", {0}, {false, {0, 0}}};
    HttpRequest negative = {"POST", "http://127.0.0.1:1/", {0}, {true, {0, -1}}};
    HttpRequest missing_data = {"POST", "http://127.0.0.1:1/", {0}, {true, {0, 1}}};
    if (fetchEx(&none).ok) return 1;
    if (fetchEx(&negative).ok) return 2;
    if (fetchEx(&missing_data).ok) return 3;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "http_invalid_body_harness"
    extra_libs = ["-ldl"] if sys.platform.startswith("linux") else []
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "net" / "http.c"),
            "-pthread",
            *extra_libs,
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_native_http_https_fails_without_tls_backend(tmp_path):
    """HTTPS 客户端不应在 TLS 后端不可用时伪装成功或回退明文。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/net/http wrapper")

    harness = tmp_path / "http_https_no_tls_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdint.h>

typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { char ***key_pages; char ***value_pages; int32_t count; int32_t capacity; int32_t page_count; } Dict;
typedef struct { int32_t status; Dict headers; Blob body; } HttpResponse;
typedef struct { bool ok; HttpResponse value; } OptHttpResponse;

OptHttpResponse fetch(const char *url);

int main(int argc, char **argv) {
    return fetch(argc > 1 ? argv[1] : "https://127.0.0.1:1/").ok ? 2 : 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "http_https_no_tls_harness"
    extra_libs = ["-ldl"] if sys.platform.startswith("linux") else []
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-DEZ_HTTP_TEST_NO_OPENSSL_DLOPEN=1",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "net" / "http.c"),
            "-pthread",
            *extra_libs,
            "-o",
            str(exe),
        ],
        check=True,
    )

    ready = threading.Event()
    captured = []

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            captured.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                conn.settimeout(2)
                try:
                    data = conn.recv(128)
                except socket.timeout:
                    data = b""
                captured.append(data)

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)
    subprocess.run([str(exe), f"https://127.0.0.1:{captured[0]}/"], check=True, timeout=5)
    thread.join(timeout=3)
    assert len(captured) >= 2
    assert not captured[1].startswith(b"GET /")


def test_e2e_native_http_server_handles_connections_concurrently(tmp_path):
    """原生 HTTP 服务端应将已接受连接交给 worker 并发处理。"""
    if sys.platform.startswith("win"):
        pytest.skip("POSIX harness 用于验证 pthread HTTP worker")
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/net/http wrapper")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    harness = tmp_path / "http_concurrent_server_harness.c"
    harness.write_text(
        r'''
#define _DEFAULT_SOURCE
#define _DARWIN_C_SOURCE

#include <arpa/inet.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { bool ok; Blob value; } OptBlob;
typedef struct { char ***key_pages; char ***value_pages; int32_t count; int32_t capacity; int32_t page_count; } Dict;
typedef struct { int32_t status; Dict headers; Blob body; } HttpResponse;
typedef struct { const char *method; const char *url; Dict headers; OptBlob body; } HttpRequest;
typedef struct { int64_t handle; } HttpServer;
typedef HttpResponse (*RouteHandler)(const HttpRequest *req);

HttpServer createServer(const char *host, int32_t port);
void HttpServer_on(HttpServer *value, const char *path, RouteHandler handler);
void HttpServer_start(HttpServer *value);
void HttpServer_stop(HttpServer *value);

static HttpServer server;
static pthread_mutex_t state_lock = PTHREAD_MUTEX_INITIALIZER;
static int active_requests = 0;
static int max_active_requests = 0;
static int handled_requests = 0;

static HttpResponse route(const HttpRequest *req) {
    (void)req;
    pthread_mutex_lock(&state_lock);
    active_requests++;
    handled_requests++;
    if (active_requests > max_active_requests) max_active_requests = active_requests;
    int seen = handled_requests;
    pthread_mutex_unlock(&state_lock);

    usleep(250000);

    pthread_mutex_lock(&state_lock);
    active_requests--;
    pthread_mutex_unlock(&state_lock);
    if (seen >= 2) HttpServer_stop(&server);
    return (HttpResponse){200, {0}, {(uint8_t *)"ok", 2}};
}

static void *run_server(void *arg) {
    (void)arg;
    HttpServer_start(&server);
    return NULL;
}

static int connect_with_retry(void) {
    for (int i = 0; i < 100; ++i) {
        int sock = socket(AF_INET, SOCK_STREAM, 0);
        if (sock < 0) return -1;
        struct sockaddr_in addr;
        memset(&addr, 0, sizeof(addr));
        addr.sin_family = AF_INET;
        addr.sin_port = htons(EZ_TEST_PORT);
        inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
        if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) == 0) return sock;
        close(sock);
        usleep(20000);
    }
    return -1;
}

static void *run_client(void *arg) {
    (void)arg;
    int sock = connect_with_retry();
    if (sock < 0) return (void *)(intptr_t)2;
    const char *req = "GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 0\r\n\r\n";
    if (send(sock, req, strlen(req), 0) < 0) {
        close(sock);
        return (void *)(intptr_t)3;
    }
    char buffer[256];
    int saw_ok = 0;
    for (;;) {
        ssize_t n = recv(sock, buffer, sizeof(buffer), 0);
        if (n < 0) {
            close(sock);
            return (void *)(intptr_t)4;
        }
        if (n == 0) break;
        for (ssize_t i = 0; i + 1 < n; ++i) {
            if (buffer[i] == 'o' && buffer[i + 1] == 'k') saw_ok = 1;
        }
    }
    close(sock);
    return (void *)(intptr_t)(saw_ok ? 0 : 5);
}

int main(void) {
    server = createServer("127.0.0.1", EZ_TEST_PORT);
    if (!server.handle) return 10;
    HttpServer_on(&server, "/", route);

    pthread_t server_thread;
    if (pthread_create(&server_thread, NULL, run_server, NULL) != 0) return 11;
    usleep(100000);

    pthread_t first;
    pthread_t second;
    if (pthread_create(&first, NULL, run_client, NULL) != 0) return 12;
    if (pthread_create(&second, NULL, run_client, NULL) != 0) return 13;

    void *first_status = NULL;
    void *second_status = NULL;
    pthread_join(first, &first_status);
    pthread_join(second, &second_status);
    pthread_join(server_thread, NULL);

    if ((intptr_t)first_status != 0 || (intptr_t)second_status != 0) return 20;
    if (handled_requests != 2) return 21;
    if (max_active_requests < 2) return 22;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "http_concurrent_server_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-DEZ_TEST_PORT={port}",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "net" / "http.c"),
            "-pthread",
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_std_net_tcp_udp_ws_support_boundaries_are_explicit():
    """TCP/UDP/WebSocket 应明确区分原生支持范围和不支持入口。"""
    tcp_native = (ROOT / "packages" / "std" / "native" / "net" / "tcp.c").read_text(encoding="utf-8")
    ws_native = (ROOT / "packages" / "std" / "native" / "net" / "ws.c").read_text(encoding="utf-8")
    tcp_emcc = (ROOT / "packages" / "std" / "emcc" / "net" / "tcp.js").read_text(encoding="utf-8")
    ws_emcc = (ROOT / "packages" / "std" / "emcc" / "net" / "ws.js").read_text(encoding="utf-8")
    tcp_interface = (ROOT / "packages" / "std" / "net" / "tcp.ez").read_text(encoding="utf-8")
    ws_interface = (ROOT / "packages" / "std" / "net" / "ws.ez").read_text(encoding="utf-8")
    api_docs = (ROOT / "docs" / "stdlib-api.md").read_text(encoding="utf-8")
    stdlib_docs = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")

    for marker in ["socket(", "connect(", "bind(", "listen(", "accept(", "recv(", "send(", "sendto(", "recvfrom(", "select("]:
        assert marker in tcp_native
    for marker in ["tcpConnectTimeout", "tcpAcceptTimeout", "tcpReadTimeout", "tcpWriteTimeout", "udpSendTimeout", "udpRecvFromTimeout", "udpRecvTimeout"]:
        assert marker in tcp_native
        assert marker in tcp_interface
    for marker in ["TcpTlsConn", "tcpTlsConnect", "tcpTlsRead", "tcpTlsWrite", "tcpTlsClose"]:
        assert marker in tcp_native
        assert marker in tcp_interface
    for marker in ["ez_tcp_load_tls", "OPENSSL_init_ssl", "X509_VERIFY_PARAM_set1_host", "SSL_get_verify_result"]:
        assert marker in tcp_native
    for marker in ["UdpPacket", "udpRecvFrom", "sockaddr_storage", "getnameinfo", "NI_NUMERICHOST", "NI_NUMERICSERV"]:
        assert marker in tcp_native
    for marker in ["ws://", "wss://", "Sec-WebSocket-Key", "ez_ws_send_frame", "ez_ws_handle_control_frame", "opcode", "0x8"]:
        assert marker in ws_native
    for marker in ["Sec-WebSocket-Accept", "ez_ws_expected_accept", "ez_ws_handshake_response_valid", "ez_ws_sha1_final"]:
        assert marker in ws_native
    for marker in ["ez_ws_load_tls", "OPENSSL_init_ssl", "X509_VERIFY_PARAM_set1_host", "SSL_get_verify_result", "ez_ws_conn_send_all"]:
        assert marker in ws_native
    assert "fragment_start" in ws_native
    assert "*authority_end == '?'" in ws_native
    assert "ez_parse_ws_port" in ws_native
    assert "ez_make_ws_host_header" in ws_native
    assert "memchr(host_start, ']'" in ws_native
    assert 'extern "ws2_32" for windows;' in tcp_interface
    assert 'extern "dl" for linux;' in tcp_interface
    assert 'extern "ws2_32" for windows;' in ws_interface
    assert 'extern "bcrypt" for windows;' in ws_interface
    assert 'extern "dl" for linux;' in ws_interface
    assert '"ws://"' in ws_native
    assert '"wss://"' in ws_native

    for marker in [
        "net/tls/dgram + Asyncify", "tcpConnect__async: 'auto'", "tcpAccept__async: 'auto'",
        "tcpWrite__async: 'auto'", "udpSend__async: 'auto'", "tcpConnectTimeout__async: 'auto'",
        "udpRecvFromTimeout__async: 'auto'", "nodeRequire('net')", "nodeRequire('dgram')",
        "tcpTlsConnect__async: 'auto'", "nodeRequire('tls')",
    ]:
        assert marker in tcp_emcc
    for marker in ["WebSocket + Asyncify", "wsConnect__async: 'auto'", "new WebSocket", "socket.send", "wsRecv__async: 'auto'"]:
        assert marker in ws_emcc
    assert "emcc Node 风格运行时" in tcp_interface
    assert "UdpPacket" in tcp_interface
    assert "udpRecvFrom" in tcp_interface
    assert "WebSocket + Asyncify" in ws_interface
    assert "Node 风格运行时通过 `net` / `tls` / `dgram` + Asyncify" in api_docs
    assert "udpRecvFrom(socket: UdpSocket, maxBytes: I64) -> UdpPacket?" in api_docs
    assert "tcpConnectTimeout(host: Str, port: I32, timeoutMs: I32) -> TcpConn?" in api_docs
    assert "TCP TLS 客户端" in api_docs
    assert "当前接口不提供 TCP TLS" not in api_docs
    assert "当前接口不返回远端地址" not in api_docs
    assert "接收数据及来源地址" in stdlib_docs
    assert "当前接收接口不返回远端地址" not in stdlib_docs
    assert "通过 WebSocket + Asyncify 支持 `ws://` / `wss://`" in api_docs
    assert "Linux/macOS 在可动态加载 OpenSSL TLS 后端、系统 CA 可用且证书链与主机名校验通过时支持 `wss://`" in api_docs


def test_e2e_cli_build_links_externs_and_records_emcc_js_libraries():
    """工具链应把 extern 接入构建链接流程，并保留 emcc JS library 输入。"""
    cli = (ROOT / "cli" / "ez.py").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")

    for marker in ["_link_executable(obj_file, exe_file, libs", "_compile_c_extern", "-framework", "-l{lib}"]:
        assert marker in cli
    assert "_module_defines_main(module)" in cli
    assert 'if path.suffix == ".js":\n            continue' in cli
    assert "_link_sdk_artifact" in cli
    assert "--js-library" in cli
    assert "lib{name}.so" in cli
    assert "lib{name}.dylib" in cli
    assert '"extern_libs"' in cli
    assert '"executable"' in cli
    assert '"sdk_artifact"' in cli
    assert "本机可执行目标会生成 LLVM IR、对象文件和同名可执行文件" in docs
    assert "`extern \"*.js\" for emcc`" in docs
    assert "SDK 链接产物" in docs


def test_e2e_toolchain_docs_cover_test_and_release_install_zip_contract():
    """工具链文档应覆盖测试命令、全局安装、单文件运行和包格式闭环。"""
    toolchain = (ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    manual = (ROOT / "docs" / "cli-manual.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    cli = (ROOT / "cli" / "ez.py").read_text(encoding="utf-8")

    assert "### `ez test`" in toolchain
    assert "## 测试" in manual
    assert "`ez test`" in readme
    assert "ez install -g" in toolchain
    assert "ez install -g" in manual
    assert "EZLANG_HOME" in toolchain
    assert "ez run path/to/file.ez" in toolchain
    assert "ez run path/to/file.ez" in manual
    assert "path/to/file.ez" in readme
    assert "<name>-<version>.zip" in toolchain
    assert "name-version.zip" in manual
    assert f'{{name}}-{{version}}.zip' in cli
    assert "_extract_package_zip" in cli
    assert "global_install" in cli
    assert "_load_run_config" in cli


def test_e2e_toolchain_docs_match_cli_defaults_and_targets():
    """工具链文档应与 CLI 默认配置、支持架构和支持系统保持一致。"""
    docs = (ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    cli = (ROOT / "cli" / "ez.py").read_text(encoding="utf-8")

    assert 'project.get("optimize", 2)' in cli
    assert "优化等级，0–3，默认值为 2" in docs
    for arch in ["x86_64", "aarch64", "arm", "wasm32", "riscv64"]:
        assert f'"{arch}"' in cli
        assert f'`"{arch}"`' in docs
    for os_name in ["windows", "macos", "linux", "android", "ios", "emcc", "freestanding"]:
        assert f'"{os_name}"' in cli
        assert f'`"{os_name}"`' in docs
    for marker in ["LLVM IR、对象文件和同名可执行文件", "SDK 链接产物", "未配置 `output.sdk` 时仍保留 IR/对象文件输出"]:
        assert marker in docs

def test_e2e_std_collections_basic_list_builds(tmp_path):
    source = tmp_path / "std_collections.ez"
    source.write_text(
        'from "std/collections" import { listLen, listPush, listPop, listShift, listUnshift, listSlice };\n\nlet nums: List<I32> = [1, 2, 3];\nlistPush<I32>(this = #nums, item = 4);\nlistUnshift<I32>(this = #nums, item = 0);\nlet tail = listPop<I32>(this = #nums);\nlet head = listShift<I32>(this = #nums);\nlet part: List<I32> = listSlice<I32>(this = #nums, start = 0, end = 2);\nlet n: I64 = listLen<I32>(this = #part);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_text = (tmp_path / "dist" / "native" / "e2e.ll").read_text(encoding="utf-8")
    assert 'list_grow' in ir_text
    assert 'list_slice_cond' in ir_text
    assert 'listLen_I32' not in ir_text


def test_e2e_array_list_layout_is_paged_across_docs_codegen_and_wrappers(tmp_path):
    """数组/List ABI 应在文档、代码生成和平台封装中统一为分页布局。"""
    for doc_path in [ROOT / "docs" / "doc.md", ROOT / "docs" / "stdlib.md", ROOT / "docs" / "stdlib-api.md"]:
        text = doc_path.read_text(encoding="utf-8")
        assert "分页" in text, f"{doc_path.relative_to(ROOT)} 未写明分页数组 ABI"
        for field in ["pages", "length", "capacity", "page_count"]:
            assert field in text, f"{doc_path.relative_to(ROOT)} 未写明数组 ABI 字段 {field}"

    source = tmp_path / "list_layout.ez"
    source.write_text(
        'from "std/collections" import { listLen, listPush };\n\n'
        'let nums: List<I32> = [1, 2, 3, 4, 5, 6, 7, 8, 9];\n'
        'listPush<I32>(this = #nums, item = 10);\n'
        'let n: I64 = listLen<I32>(this = #nums);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_text = (tmp_path / "dist" / "native" / "e2e.ll").read_text(encoding="utf-8")
    assert "{i32**, i64, i64, i64}" in ir_text
    assert "_tmp_arr_pages" in ir_text
    assert "_tmp_arr_page" in ir_text
    assert "list_grow" in ir_text
    assert "listLen_I32" not in ir_text

    for wrapper_path in [
        ROOT / "packages" / "std" / "native" / "str.c",
        ROOT / "packages" / "std" / "native" / "fs.c",
        ROOT / "packages" / "std" / "native" / "os.c",
        ROOT / "packages" / "std" / "emcc" / "str.js",
    ]:
        wrapper = wrapper_path.read_text(encoding="utf-8")
        assert "page_count" in wrapper or "pageCount" in wrapper, f"{wrapper_path.relative_to(ROOT)} 未使用分页列表布局"


def test_e2e_operator_semantics_match_docs_and_codegen(tmp_path):
    """文档要求的核心运算符语义应有对应代码生成形态。"""
    docs = (ROOT / "docs" / "doc.md").read_text(encoding="utf-8")
    for marker in ["无符号类型的除法", "逻辑运算支持短路求值", "标量自动广播", "向量比较生成同宽布尔 mask", "避免重复求值"]:
        assert marker in docs

    source = tmp_path / "operators.ez"
    source.write_text(
        'const calc = (a: U32, b: U32, shift: U32): U32 => {\n'
        '    let masked: U32 = (a & b) >> shift;\n'
        '    masked /= b;\n'
        '    masked %= b;\n'
        '    masked >>= shift;\n'
        '    return masked;\n'
        '};\n\n'
        'const logic = (a: Bool, b: Bool): Bool => {\n'
        '    return (a && b) || (!a && !b);\n'
        '};\n\n'
        'const simd = (): Vec<Bool>[4] => {\n'
        '    let v = Vec[1, 2, 3, 4];\n'
        '    return (v + 2) < Vec[4, 4, 4, 4];\n'
        '};\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_text = (tmp_path / "dist" / "native" / "e2e.ll").read_text(encoding="utf-8")
    assert "udiv i32" in ir_text
    assert "urem i32" in ir_text
    assert ir_text.count("lshr i32") >= 2
    assert "ashr i32" not in ir_text
    assert "br i1" in ir_text
    assert re.search(r"phi\s+i1", ir_text)
    assert "insertelement <4 x i32>" in ir_text
    assert "icmp slt <4 x i32>" in ir_text
    assert "<4 x i1>" in ir_text


def test_e2e_std_collections_higher_order_and_dict_build(tmp_path):
    source = tmp_path / "std_collections_more.ez"
    source.write_text(
        'from "std/collections" import { listSort, listFilter, listMap, listFind, listLen, dictKeys, dictValues, dictHas, dictDelete, dictLen };\n\nconst pred = (item: I32): Bool => { return item > 1; };\nconst mapper = (item: I32): I64 => { return item; };\nconst cmp = (a: I32, b: I32): I32 => { return a - b; };\nlet nums: List<I32> = [3, 1, 2];\nlistSort<I32>(this = #nums, cmp = cmp);\nlet found = listFind<I32>(this = #nums, pred = pred);\nlet filtered: List<I32> = listFilter<I32>(this = #nums, pred = pred);\nlet mapped: List<I64> = listMap<I32, I64>(this = #filtered, f = mapper);\nlet mapped_len: I64 = listLen<I64>(this = #mapped);\nlet meta = { name: Str = "ez", lang: Str = "EzLang" };\nlet has_name: Bool = dictHas<Str, Str>(this = #meta, key = "name");\nlet keys: List<Str> = dictKeys<Str, Str>(this = #meta);\nlet values: List<Str> = dictValues<Str, Str>(this = #meta);\nlet removed: Bool = dictDelete<Str, Str>(this = #meta, key = "name");\nlet remaining: I64 = dictLen<Str, Str>(this = #meta);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_text = (tmp_path / "dist" / "native" / "e2e.ll").read_text(encoding="utf-8")
    assert 'list_sort_outer_cond' in ir_text
    assert 'list_find_cond' in ir_text
    assert 'list_filter_cond' in ir_text
    assert 'list_map_cond' in ir_text
    assert 'dict_find_cond' in ir_text
    assert 'dict_list_cond' in ir_text
    assert 'dictHas_Str_Str' not in ir_text


def test_e2e_dict_literal_string_and_expression_keys_build(tmp_path):
    source = tmp_path / "dict_keys.ez"
    source.write_text(
        'from "std/collections" import { dictHas, dictLen };\n'
        'from "std/str" import { strEqual };\n\n'
        'let headerName = "Accept";\n'
        'let headers = { "Content-Type" = "text/plain", [headerName] = "application/json" };\n'
        'let contentType = headers["Content-Type"];\n'
        'let accept = headers[headerName];\n'
        'let hasAccept = dictHas<Str, Str>(this = #headers, key = "Accept");\n'
        'let count = dictLen<Str, Str>(this = #headers);\n'
        'let ok = strEqual(a = contentType, b = "text/plain") && strEqual(a = accept, b = "application/json") && hasAccept && count == 2;\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_text = (tmp_path / "dist" / "native" / "e2e.ll").read_text(encoding="utf-8")
    assert "Content-Type" in ir_text
    assert "dict_find_cond" in ir_text
    assert "dict_insert" in ir_text


def test_e2e_native_stream_tcp_supports_windows_handles():
    native = (ROOT / "packages" / "std" / "native" / "stream.c").read_text(encoding="utf-8")
    interface = (ROOT / "packages" / "std" / "stream.ez").read_text(encoding="utf-8")
    api_docs = (ROOT / "docs" / "stdlib-api.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "compiler-architecture.md").read_text(encoding="utf-8")
    assert "STREAM_TCP_UNSUPPORTED" not in native
    for marker in ["winsock2.h", "typedef SOCKET stream_socket_t", "recv(sock, (char *)data", "send(sock, (const char *)data->data"]:
        assert marker in native
    assert 'extern "ws2_32" for windows;' in interface
    assert "文件读写流与 TCP 连接流" in api_docs
    assert "内存/Blob 流、文件流和 TCP 连接流" in architecture


def test_e2e_native_stream_write_empty_blob_requires_valid_stream(tmp_path):
    """原生 streamWrite 写合法空 Blob 时仍必须先确认目标流有效。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/stream wrapper")

    harness = tmp_path / "stream_empty_write_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { int64_t handle; int32_t kind; } Stream;
typedef struct { bool ok; Stream value; } OptStream;
typedef struct { bool ok; Blob value; } OptBlob;

OptStream streamFromBlob(const Blob *data);
OptStream streamOpenFileRead(const char *path);
OptStream streamOpenFileWrite(const char *path);
OptBlob streamRead(const Stream *stream_value, int64_t maxBytes);
int64_t streamWrite(const Stream *stream_value, const Blob *data);
OptBlob streamToBlob(const Stream *stream_value);
bool streamFlush(const Stream *stream_value);
bool streamClose(const Stream *stream_value);

int main(void) {
    Blob empty = {NULL, 0};
    uint8_t one = 1;
    Blob huge = {&one, INT64_MAX};
    Stream zero = {0, 0};
    Stream memory_without_handle = {0, 1};

    if (streamWrite(NULL, &empty) != -1) return 2;
    if (streamWrite(&zero, &empty) != -1) return 3;
    if (streamWrite(&memory_without_handle, &empty) != -1) return 4;
    if (streamFromBlob(&huge).ok) return 5;

    OptStream stream = streamFromBlob(&empty);
    if (!stream.ok) return 6;
    if (streamWrite(&stream.value, &empty) != 0) return 7;
    if (streamWrite(&stream.value, &huge) != -1) return 8;
    if (!streamClose(&stream.value)) return 9;
    if (streamWrite(&stream.value, &empty) != -1) return 10;
    if (streamRead(&stream.value, 1).ok) return 11;
    if (streamToBlob(&stream.value).ok) return 12;
    if (streamFlush(&stream.value)) return 13;
    if (streamClose(&stream.value)) return 14;

    OptStream file = streamOpenFileWrite("stream-close-tombstone.bin");
    if (!file.ok) return 15;
    if (!streamClose(&file.value)) return 16;
    if (streamWrite(&file.value, &empty) != -1) return 17;
    if (streamFlush(&file.value)) return 18;
    if (streamClose(&file.value)) return 19;

    OptStream reader = streamOpenFileRead("stream-close-tombstone.bin");
    if (!reader.ok) return 20;
    if (streamRead(&reader.value, INT64_MAX).ok) return 21;
    if (!streamClose(&reader.value)) return 22;

    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "stream_empty_write_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "stream.c"),
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True, cwd=tmp_path)


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
    assert 'declare i64 @"parseInt"' in ir_text
    assert '%"_parseInt_abi_ret" = alloca {i1, i32}' in ir_text
    assert_native_optional_return(ir_text, "parseI64", "i64")
    assert_native_optional_return(ir_text, "parseF64", "double")
    assert 'declare i8* @"fmtFormat"' in ir_text
    assert 'declare i8* @"b64Encode"' in ir_text
    assert 'declare i8* @"jsonStringify_I32"' in ir_text
    assert 'declare i32 @"jsonParse_I32"' in ir_text
    assert 'declare i1 @"__ez_json_valid_I32"' in ir_text
    assert 'call i1 @"__ez_json_valid_I32"' in ir_text
    assert 'declare i8* @"urlEncode"' in ir_text
    assert_native_optional_return(ir_text, "urlDecode", "i8*")


def test_e2e_fmt_wrappers_implement_parse_format_encoding_json_and_msgpack():
    native = (ROOT / "packages" / "std" / "native" / "fmt.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "fmt.js").read_text(encoding="utf-8")
    for marker in ["ez_parse_decimal_i64_span", "ez_parse_trim_span", "strtod", "ez_b64_is_valid_input", "jsonStringify_Str", "jsonParse_Str", "jsonStringify_I8", "jsonParse_U8", "jsonStringify_U64", "jsonParse_U64", "msgpackEncode_U8", "msgpackDecode_U8", "msgpackEncode_U64", "msgpackDecode_U64", "msgpackDecode_Str", "urlEncode", "urlDecode"]:
        assert marker in native
    for marker in ["ez_json_append_utf8", "ez_json_hex4", "ez_utf8_validate_len", "esc == 'u'", "0xD800", "0x10FFFF"]:
        assert marker in native
    assert "ez_contains_nul_byte" in native
    assert "byte == 0" in native
    for marker in ["ez_json_number_span", "ez_json_parse_integer_value", "ez_json_parse_unsigned_integer_value", "ez_json_trim_span"]:
        assert marker in native
    for marker in ["__ez_json_valid_I8", "__ez_json_valid_I32", "__ez_json_valid_U8", "__ez_json_valid_U64", "__ez_json_valid_Str", "ez_json_parse_string_span"]:
        assert marker in native
    assert 'isfinite(value) ? toString_F64(value) : ez_strdup_safe("null")' in native
    for marker in ["ez_msgpack_decode_integer", "ez_msgpack_decode_unsigned_integer", "0xCC", "0xCF", "0xD0", "0xCA"]:
        assert marker in native
    assert "ez_list_get(args, arg_index++)" in native
    assert "EZ_B64" in native
    for marker in ["parseDecimalInteger", "I8_MIN", "U8_MAX", "I64_MAX", "U64_MAX", "isStrictBase64", "JSON.stringify", "JSON.parse", "msgpackEncode_U8", "msgpackDecode_U8", "msgpackEncode_U64", "msgpackDecode_U64", "msgpackDecode_Str", "encodeURIComponent", "decodeURIComponent"]:
        assert marker in emcc
    assert "Number.parseInt" not in emcc
    for marker in ["decodeInteger", "decodeUnsignedInteger", "tag === 0xcc", "tag === 0xcf", "tag === 0xd0", "getFloat32"]:
        assert marker in emcc
    for marker in ["jsonNumberSyntax", "parseJsonInteger", "typeof value === 'string'", "validUtf8Bytes"]:
        assert marker in emcc
    assert "hasNulString" in emcc
    assert "hasNulBytes" in emcc
    for marker in ["__ez_json_valid_I8", "__ez_json_valid_I32", "__ez_json_valid_U8", "__ez_json_valid_U64", "__ez_json_valid_Str", "jsonStringSyntax"]:
        assert marker in emcc
    assert "listGet(argsPtr, index++)" in emcc

    codegen = (ROOT / "compiler" / "src" / "codegen" / "llvm_codegen.py").read_text(encoding="utf-8")
    assert "_json_parse_validate_or_throw" in codegen


def test_e2e_native_fmt_b64encode_rejects_invalid_blob_without_null_string(tmp_path):
    """b64Encode 返回 Str，非法 Blob 不能把 NULL 暴露给语言侧。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/fmt wrapper")

    harness = tmp_path / "fmt_b64_harness.c"
    harness.write_text(
        r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

const char *b64Encode(const Blob *data);

static int expect(const char *got, const char *expected) {
    int ok = got != NULL && strcmp(got, expected) == 0;
    free((void *)got);
    return ok ? 0 : 1;
}

int main(void) {
    uint8_t hello[] = {'h', 'e', 'l', 'l', 'o'};
    Blob valid = {hello, 5};
    Blob empty = {NULL, 0};
    Blob bad_negative = {NULL, -1};
    Blob bad_missing_data = {NULL, 1};

    if (expect(b64Encode(&valid), "aGVsbG8=") != 0) return 2;
    if (expect(b64Encode(&empty), "") != 0) return 3;
    if (expect(b64Encode(&bad_negative), "") != 0) return 4;
    if (expect(b64Encode(&bad_missing_data), "") != 0) return 5;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "fmt_b64_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "fmt.c"),
            "-lm",
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_native_fmt_parse_f64_uses_decimal_syntax(tmp_path):
    """原生 parseF64 应和 emcc 一样只接受十进制浮点语法。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/fmt wrapper")

    harness = tmp_path / "fmt_parse_f64_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <math.h>

typedef struct { bool ok; double value; } OptF64;

OptF64 parseF64(const char *s);

static int expect_ok(const char *text, double expected) {
    OptF64 got = parseF64(text);
    return got.ok && fabs(got.value - expected) < 0.0000001 ? 0 : 1;
}

static int expect_bad(const char *text) {
    OptF64 got = parseF64(text);
    return got.ok ? 1 : 0;
}

int main(void) {
    if (expect_ok("3.5", 3.5) != 0) return 2;
    if (expect_ok("+3.5", 3.5) != 0) return 3;
    if (expect_ok(" +.5 ", 0.5) != 0) return 4;
    if (expect_ok("\xC2\xA0+.5\xE3\x80\x80", 0.5) != 0) return 17;
    if (expect_ok("1.", 1.0) != 0) return 5;
    if (expect_ok("1e+2", 100.0) != 0) return 6;
    if (expect_ok("1e-3", 0.001) != 0) return 7;
    if (expect_ok("1e-4000", 0.0) != 0) return 8;
    if (expect_bad("0x1p2") != 0) return 9;
    if (expect_bad("nan") != 0) return 10;
    if (expect_bad("inf") != 0) return 11;
    if (expect_bad("1e+") != 0) return 12;
    if (expect_bad(".") != 0) return 13;
    if (expect_bad("+") != 0) return 14;
    if (expect_bad("3.5x") != 0) return 15;
    if (expect_bad("1e309") != 0) return 16;
    if (expect_bad("\xEF\xBB\xBF" "3.5") != 0) return 18;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "fmt_parse_f64_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "fmt.c"),
            "-lm",
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_native_fmt_string_decoders_reject_nul_bytes(tmp_path):
    """native fmt 的字符串解码入口不能返回包含 NUL 的 Ez Str。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/fmt wrapper")

    harness = tmp_path / "fmt_string_nul_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { bool ok; const char *value; } OptStr;

bool __ez_json_valid_Str(const char *s);
const char *jsonParse_Str(const char *s);
const char *msgpackDecode_Str(const Blob *data);
OptStr urlDecode(const char *s);

static int expect_string(const char *got, const char *expected, int code) {
    if (!got) return code;
    if (strcmp(got, expected) != 0) return code + 1;
    free((void *)got);
    return 0;
}

int main(void) {
    uint8_t msgpack_valid[] = {0xA1, 'x'};
    uint8_t msgpack_nul[] = {0xA1, 0x00};
    Blob valid = {msgpack_valid, 2};
    Blob nul = {msgpack_nul, 2};

    if (!__ez_json_valid_Str("\"x\"")) return 2;
    if (__ez_json_valid_Str("\"\\u0000\"")) return 3;
    int err = expect_string(jsonParse_Str("\"x\""), "x", 4);
    if (err != 0) return err;
    err = expect_string(jsonParse_Str("\"\\u0000\""), "", 6);
    if (err != 0) return err;
    err = expect_string(msgpackDecode_Str(&valid), "x", 8);
    if (err != 0) return err;
    err = expect_string(msgpackDecode_Str(&nul), "", 10);
    if (err != 0) return err;

    OptStr decoded = urlDecode("a%20b");
    if (!decoded.ok || !decoded.value || strcmp(decoded.value, "a b") != 0) return 12;
    free((void *)decoded.value);
    OptStr decoded_nul = urlDecode("%00");
    if (decoded_nul.ok || decoded_nul.value) return 13;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "fmt_string_nul_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "fmt.c"),
            "-lm",
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_emcc_fmt_scalar_wrappers_handle_edges():
    """emcc fmt 标量 wrapper 应严格处理整数、布尔字符串化和 MessagePack 字符串边界。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/fmt emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const HEAP32 = new Int32Array(memory);
const HEAP64 = new BigInt64Array(memory);
const HEAPF64 = new Float64Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  if (type === 'i32') return view.getInt32(ptr, true);
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

const library = {};
vm.runInNewContext(code, {
  BigInt,
  Buffer,
  DataView,
  Uint8Array,
  HEAPU8,
  HEAP32,
  HEAP64,
  HEAPF64,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  lengthBytesUTF8(text) { return Buffer.byteLength(text, 'utf8'); },
  UTF8ArrayToString(bytes) { return Buffer.from(bytes).toString('utf8'); },
  btoa(text) { return Buffer.from(text, 'binary').toString('base64'); },
  atob(text) { return Buffer.from(text, 'base64').toString('binary'); },
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function parseI32(text) {
  const ret = _malloc(16);
  library.parseInt(ret, stringToNewUTF8(text));
  return { ok: HEAPU8[ret] !== 0, value: HEAP32[(ret + 4) >> 2] };
}
function parseI64(text) {
  const ret = _malloc(16);
  library.parseI64(ret, stringToNewUTF8(text));
  return { ok: HEAPU8[ret] !== 0, value: HEAP64[(ret + 8) >> 3] };
}
function parseF64(text) {
  const ret = _malloc(16);
  library.parseF64(ret, stringToNewUTF8(text));
  return { ok: HEAPU8[ret] !== 0, value: HEAPF64[(ret + 8) >> 3] };
}

function toStringBool(value) {
  return UTF8ToString(library.toString_I1(value ? 1 : 0));
}

function makeBlob(bytes) {
  const blob = _malloc(16);
  const data = _malloc(bytes.length || 1);
  HEAPU8.set(bytes, data);
  setValue(blob, data, '*');
  setValue(blob + 8, bytes.length, 'i64');
  return blob;
}

function makeRawBlob(dataPtr, size) {
  const blob = _malloc(16);
  setValue(blob, dataPtr, '*');
  setValue(blob + 8, size, 'i64');
  return blob;
}

function blobBytes(blob) {
  const data = getValue(blob, '*');
  const size = getValue(blob + 8, 'i64');
  return Array.from(HEAPU8.slice(data, data + size));
}

function msgpackStr(bytes) {
  return UTF8ToString(library.msgpackDecode_Str(makeBlob(Uint8Array.from(bytes))));
}

function jsonStr(text) {
  return UTF8ToString(library.jsonParse_Str(stringToNewUTF8(text)));
}

function jsonValidStr(text) {
  return library.__ez_json_valid_Str(stringToNewUTF8(text));
}

function urlDecode(text) {
  const ret = _malloc(16);
  library.urlDecode(ret, stringToNewUTF8(text));
  return { ok: HEAPU8[ret] !== 0, value: UTF8ToString(getValue(ret + 8, '*')) };
}

function msgpackF32(value) {
  const ret = _malloc(16);
  library.msgpackEncode_F32(ret, value);
  return blobBytes(ret);
}

function msgpackI8(value) {
  const ret = _malloc(16);
  library.msgpackEncode_I8(ret, value);
  return blobBytes(ret);
}

function msgpackU8(value) {
  const ret = _malloc(16);
  library.msgpackEncode_U8(ret, value);
  return blobBytes(ret);
}

function msgpackU64(value) {
  const ret = _malloc(16);
  library.msgpackEncode_U64(ret, value);
  return blobBytes(ret);
}

assert.strictEqual(toStringBool(true), 'true');
assert.strictEqual(toStringBool(false), 'false');
assert.strictEqual(UTF8ToString(library.jsonStringify_F32(1.5)), '1.5');
assert.strictEqual(UTF8ToString(library.toString_I8(0x80)), '-128');
assert.strictEqual(UTF8ToString(library.toString_U8(0xff)), '255');
assert.strictEqual(UTF8ToString(library.jsonStringify_I8(0x80)), '-128');
assert.strictEqual(UTF8ToString(library.jsonStringify_U8(0xff)), '255');
assert.strictEqual(UTF8ToString(library.toString_U32(0xffffffff)), '4294967295');
assert.strictEqual(UTF8ToString(library.toString_U64(18446744073709551615n)), '18446744073709551615');
assert.strictEqual(UTF8ToString(library.jsonStringify_U64(18446744073709551615n)), '18446744073709551615');
assert.strictEqual(UTF8ToString(library.b64Encode(makeBlob(Uint8Array.from([0x68, 0x69])))), 'aGk=');
assert.strictEqual(UTF8ToString(library.b64Encode(makeRawBlob(0, 1))), '');
assert.strictEqual(UTF8ToString(library.b64Encode(makeRawBlob(HEAPU8.length - 1, 2))), '');
assert.strictEqual(library.__ez_json_valid_F32(stringToNewUTF8('1.5')), 1);
assert.strictEqual(library.__ez_json_valid_F32(stringToNewUTF8('1e+')), 0);
assert.strictEqual(library.__ez_json_valid_I8(stringToNewUTF8('-128')), 1);
assert.strictEqual(library.__ez_json_valid_I8(stringToNewUTF8('128')), 0);
assert.strictEqual(library.__ez_json_valid_U8(stringToNewUTF8('255')), 1);
assert.strictEqual(library.__ez_json_valid_U8(stringToNewUTF8('256')), 0);
assert.strictEqual(library.__ez_json_valid_U8(stringToNewUTF8('-1')), 0);
assert.strictEqual(library.__ez_json_valid_U32(stringToNewUTF8('4294967295')), 1);
assert.strictEqual(library.__ez_json_valid_U32(stringToNewUTF8('4294967296')), 0);
assert.strictEqual(library.__ez_json_valid_U64(stringToNewUTF8('18446744073709551615')), 1);
assert.strictEqual(library.__ez_json_valid_U64(stringToNewUTF8('-1')), 0);
assert.strictEqual(library.__ez_json_valid_U64(stringToNewUTF8('18446744073709551616')), 0);
assert.strictEqual(jsonValidStr('"x"'), 1);
assert.strictEqual(jsonValidStr('"\\u0000"'), 0);
assert.strictEqual(library.jsonParse_F32(stringToNewUTF8('1.5')), 1.5);
assert.strictEqual(library.jsonParse_I8(stringToNewUTF8('-128')), -128);
assert.strictEqual(library.jsonParse_U8(stringToNewUTF8('255')), 255);
assert.strictEqual(library.jsonParse_U32(stringToNewUTF8('4294967295')), 0xffffffff);
assert.strictEqual(library.jsonParse_U64(stringToNewUTF8('18446744073709551615')), 18446744073709551615n);
assert.strictEqual(jsonStr('"x"'), 'x');
assert.strictEqual(jsonStr('"\\u0000"'), '');
assert.deepStrictEqual(msgpackF32(1.5), [0xca, 0x3f, 0xc0, 0x00, 0x00]);
assert.deepStrictEqual(msgpackI8(-128), [0xd0, 0x80]);
assert.deepStrictEqual(msgpackU8(255), [0xcc, 0xff]);
assert.deepStrictEqual(msgpackU64(18446744073709551615n), [0xcf, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff]);
assert.strictEqual(library.msgpackDecode_F32(makeBlob(Uint8Array.from([0xca, 0x3f, 0xc0, 0x00, 0x00]))), 1.5);
assert.strictEqual(library.msgpackDecode_I8(makeBlob(Uint8Array.from([0xd0, 0x80]))), -128);
assert.strictEqual(library.msgpackDecode_I8(makeBlob(Uint8Array.from([0xcc, 0x80]))), 0);
assert.strictEqual(library.msgpackDecode_U8(makeBlob(Uint8Array.from([0xcc, 0xff]))), 255);
assert.strictEqual(library.msgpackDecode_U8(makeBlob(Uint8Array.from([0xd0, 0xff]))), 0);
assert.strictEqual(library.msgpackDecode_U32(makeBlob(Uint8Array.from([0xce, 0xff, 0xff, 0xff, 0xff]))), 0xffffffff);
assert.strictEqual(library.msgpackDecode_U32(makeBlob(Uint8Array.from([0xcf, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]))), 0);
assert.strictEqual(library.msgpackDecode_U64(makeBlob(Uint8Array.from([0xcf, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff]))), 18446744073709551615n);
assert.strictEqual(library.msgpackDecode_U64(makeBlob(Uint8Array.from([0xd0, 0xff]))), 0n);
assert.strictEqual(msgpackStr([0xa1, 0x78]), 'x');
assert.strictEqual(msgpackStr([0xa1, 0x78, 0xff]), '');
assert.strictEqual(msgpackStr([0xa1, 0xff]), '');
assert.strictEqual(msgpackStr([0xa1, 0x00]), '');
assert.deepStrictEqual(urlDecode('a%20b'), { ok: true, value: 'a b' });
assert.deepStrictEqual(urlDecode('%00'), { ok: false, value: '' });

assert.deepStrictEqual(parseI32('2147483647'), { ok: true, value: 2147483647 });
assert.deepStrictEqual(parseI32('2147483648'), { ok: false, value: 0 });
assert.deepStrictEqual(parseI32('-2147483648'), { ok: true, value: -2147483648 });
assert.deepStrictEqual(parseI32('-2147483649'), { ok: false, value: 0 });
assert.strictEqual(parseI32('9007199254740993').ok, false);
assert.deepStrictEqual(parseI32('\u00A0+42\u3000'), { ok: true, value: 42 });
assert.strictEqual(parseI32('\uFEFF42').ok, false);
assert.strictEqual(parseI32('0x10').ok, false);

assert.deepStrictEqual(parseI64('9223372036854775807'), { ok: true, value: 9223372036854775807n });
assert.deepStrictEqual(parseI64('9223372036854775808'), { ok: false, value: 0n });
assert.deepStrictEqual(parseI64('-9223372036854775808'), { ok: true, value: -9223372036854775808n });
assert.deepStrictEqual(parseI64('-9223372036854775809'), { ok: false, value: 0n });
assert.strictEqual(parseI64('+42').value, 42n);
assert.strictEqual(parseI64('42x').ok, false);
assert.deepStrictEqual(parseI64('\u2007-123456789\u202F'), { ok: true, value: -123456789n });
assert.strictEqual(parseI64('42.0').ok, false);

assert.strictEqual(parseF64('\u205F+.5\u3000').ok, true);
assert.strictEqual(parseF64('\u205F+.5\u3000').value, 0.5);
assert.strictEqual(parseF64('\uFEFF3.5').ok, false);
assert.strictEqual(parseF64('0x1p2').ok, false);
assert.strictEqual(parseF64('nan').ok, false);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "fmt.js")], check=True)


def test_e2e_string_literal_decoding_is_shared_by_semantic_and_codegen():
    semantic = (ROOT / "compiler" / "src" / "semantic" / "analyzer.py").read_text(encoding="utf-8")
    codegen = (ROOT / "compiler" / "src" / "codegen" / "llvm_codegen.py").read_text(encoding="utf-8")
    helper = (ROOT / "compiler" / "src" / "parser" / "string_literals.py").read_text(encoding="utf-8")
    from parser.string_literals import decode_string_literal_token

    assert "decode_string_literal_token" in semantic
    assert "decode_string_literal_token" in codegen
    for marker in ["0xD800", "0xDBFF", "0xDC00", "0xDFFF"]:
        assert marker in helper
    decoded = decode_string_literal_token('"\\uD800\\U0000DFFF"')
    assert decoded == "\uFFFD\uFFFD"
    decoded.encode("utf-8")


def test_e2e_regex_wrappers_preserve_input_on_zero_width_global_replace():
    native = (ROOT / "packages" / "std" / "native" / "regex.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "regex.js").read_text(encoding="utf-8")
    for marker in ["ez_utf8_advance_one", "ez_regex_has_end_anchor", "REG_NOTBOL"]:
        assert marker in native
    assert native.count("REG_NOTBOL") >= 2
    for marker in ["replaceLiteral", "byteLengthPrefix", "advanceOne", "splitNoCaptures", "m[0].length === 0"]:
        assert marker in emcc


def test_e2e_emcc_regex_matches_native_literal_replace_and_byte_offsets():
    """emcc regex 应匹配 native 的字面替换、字节偏移和 split 规则。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/regex emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i32') return view.getInt32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function lengthBytesUTF8(text) { return Buffer.byteLength(text, 'utf8'); }
function stringToUTF8(text, ptr, maxBytes) {
  const bytes = Buffer.from(text, 'utf8');
  HEAPU8.set(bytes.slice(0, Math.max(0, maxBytes - 1)), ptr);
  HEAPU8[ptr + Math.min(bytes.length, Math.max(0, maxBytes - 1))] = 0;
}
function stringToNewUTF8(text) {
  const len = lengthBytesUTF8(text);
  const ptr = _malloc(len + 1);
  stringToUTF8(text, ptr, len + 1);
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

const library = {};
vm.runInNewContext(code, {
  BigInt,
  Buffer,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  lengthBytesUTF8,
  stringToNewUTF8,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function compile(pattern, flags) {
  const ret = _malloc(16);
  library.regexCompile(ret, stringToNewUTF8(pattern), flags);
  assert.strictEqual(HEAPU8[ret + 8], 1, 'regex should compile');
  return ret;
}
function compileInvalid(pattern, flags) {
  const ret = _malloc(16);
  library.regexCompile(ret, stringToNewUTF8(pattern), flags);
  assert.strictEqual(HEAPU8[ret + 8], 0, 'regex should be rejected');
  assert.strictEqual(library.regexIsValid(ret), 0);
  return ret;
}
function replace(pattern, flags, input, replacement) {
  return UTF8ToString(library.regexReplace(compile(pattern, flags), stringToNewUTF8(input), stringToNewUTF8(replacement)));
}
function find(pattern, flags, input) {
  const ret = _malloc(72);
  library.regexFind(ret, compile(pattern, flags), stringToNewUTF8(input));
  const groupPages = getValue(ret + 32, '*');
  const groupLength = getValue(ret + 40, 'i64');
  const firstGroupPage = groupPages ? getValue(groupPages, '*') : 0;
  return {
    ok: HEAPU8[ret] !== 0,
    start: getValue(ret + 8, 'i64'),
    end: getValue(ret + 16, 'i64'),
    text: UTF8ToString(getValue(ret + 24, '*')),
    group0: groupLength > 0 && firstGroupPage ? UTF8ToString(getValue(firstGroupPage, '*')) : '',
  };
}
function split(pattern, flags, input) {
  const ret = _malloc(32);
  library.regexSplit(ret, compile(pattern, flags), stringToNewUTF8(input));
  const pages = getValue(ret, '*');
  const length = getValue(ret + 8, 'i64');
  const out = [];
  for (let i = 0; i < length; i++) {
    const page = getValue(pages + Math.floor(i / 8) * 4, '*');
    out.push(UTF8ToString(getValue(page + (i % 8) * 4, '*')));
  }
  return out;
}

assert.strictEqual(replace('([A-Z]+)', 0, 'ABC DEF', '$1'), '$1 DEF');
assert.strictEqual(replace('[0-9]', 4, 'a1b2c3', '$&'), 'a$&b$&c$&');
assert.deepStrictEqual(find('(Ez)', 0, '中Ez'), { ok: true, start: 3, end: 5, text: 'Ez', group0: 'Ez' });
assert.deepStrictEqual(split('([,])', 4, 'a,b,c'), ['a', 'b', 'c']);
assert.strictEqual(find('^b', 2, 'a\nb').ok, true);
assert.strictEqual(find('^b', 0, 'a\nb').ok, false);
assert.strictEqual(find('a.b', 0, 'a b').ok, true);
assert.strictEqual(find('a.b', 0, 'a\nb').ok, false);
compileInvalid('(a+)+$', 0);
compileInvalid('(a|aa)+$', 0);
compileInvalid('a{0,2048}', 0);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "regex.js")], check=True)


def test_e2e_native_regex_portable_fallback_vectors(tmp_path):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 std/regex portable fallback")
    native = (ROOT / "packages" / "std" / "native" / "regex.c").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")
    for marker in ["EZ_REGEX_USE_PORTABLE", "ez_rx_compile_pattern", "ez_rx_search", "ez_rx_find_portable", "ez_regex_complexity_ok", "EZ_REGEX_MAX_BOUNDED_REPEAT"]:
        assert marker in native
    assert "Windows 原生目标使用内置同步轻量正则 fallback" in docs
    assert "嵌套可变重复" in docs
    assert "Windows 原生目标当前显式返回不可用结果" not in docs

    source = ROOT / "compiler" / "tests" / "fixtures" / "regex_portable_check.c"
    exe = tmp_path / "regex_portable_check"
    subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)], check=True)
    result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    assert result.stdout.splitlines() == ["EzLang", "a#b#c#", "|ab|"]


def test_e2e_std_str_emcc_matches_native_edge_cases():
    emcc = (ROOT / "packages" / "std" / "emcc" / "str.js").read_text(encoding="utf-8")
    assert "oldText === ''" in emcc
    assert "Math.max(0, Number(start))" in emcc
    assert "if (finish < begin) finish = begin" in emcc


def test_e2e_std_math_float_to_int_uses_truncation_bounds():
    native = (ROOT / "packages" / "std" / "native" / "math.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "math.js").read_text(encoding="utf-8")
    assert "value <= (double)INT32_MIN - 1.0" in native
    assert "value >= (double)INT32_MAX + 1.0" in native
    assert "value < -0x1p63" in native
    assert "value >= 0x1p63" in native
    assert "Math.trunc(value)" in emcc
    assert "value > I32_MIN - 1 && value < I32_MAX + 1" in emcc
    assert "value >= I64_MIN_F64 && value < I64_LIMIT_F64" in emcc
    assert "Math.round(value)" not in emcc
    assert "value < 0 ? -Math.floor(-value + 0.5) : Math.floor(value + 0.5)" in emcc


def test_e2e_emcc_math_round_and_lcm_match_native_edges():
    """emcc mathRound 应匹配 C round 的 half-away-from-zero 语义。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/math emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const HEAP32 = new Int32Array(memory);
const HEAP64 = new BigInt64Array(memory);
const library = {};

vm.runInNewContext(code, {
  HEAPU8,
  HEAP32,
  HEAP64,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

assert.strictEqual(library.mathRound(1.5), 2);
assert.strictEqual(library.mathRound(-1.5), -2);
assert.strictEqual(library.mathRound(-1.4), -1);
assert.strictEqual(library.mathGcdI64(-(1n << 63n), 2n), 2n);
assert.strictEqual(library.mathLcmI64(-6n, 8n), 24n);
assert.strictEqual(library.mathLcmI64(3037000500n, 3037000500n), 3037000500n);

function optI32(value) {
  library.mathF64ToI32(0, value);
  return { ok: HEAPU8[0] === 1, value: HEAP32[1] };
}

function optI64(value) {
  library.mathF64ToI64(16, value);
  return { ok: HEAPU8[16] === 1, value: HEAP64[3] };
}

assert.deepStrictEqual(optI32(2147483647.0), { ok: true, value: 2147483647 });
assert.deepStrictEqual(optI32(-2147483648.0), { ok: true, value: -2147483648 });
assert.deepStrictEqual(optI32(2147483647.9), { ok: true, value: 2147483647 });
assert.deepStrictEqual(optI32(-2147483648.9), { ok: true, value: -2147483648 });
assert.deepStrictEqual(optI32(42.9), { ok: true, value: 42 });
assert.deepStrictEqual(optI32(2147483648.0), { ok: false, value: 0 });
assert.deepStrictEqual(optI32(-2147483649.0), { ok: false, value: 0 });
assert.deepStrictEqual(optI64(-9223372036854775808.0), { ok: true, value: -9223372036854775808n });
assert.deepStrictEqual(optI64(9223372036854775808.0), { ok: false, value: 0n });
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "math.js")], check=True)


def test_e2e_flow_example_builds_with_runtime_hooks(tmp_path):
    project_toml = write_project(tmp_path, ROOT / "examples" / "flow.ez")

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'define void @"__ezrt_flow_enter"' in ir_text
    assert 'define void @"__ezrt_flow_exit"' in ir_text
    assert 'define void @"__ezrt_sleep"' in ir_text
    assert 'call void @"__ezrt_flow_enter"' in ir_text
    assert 'declare i32 @"__ezrt_race_i32"' in ir_text
    assert 'call i32 @"__ezrt_race_i32"' in ir_text
    assert 'call i32 @"__ezrt_race"' not in ir_text


def test_e2e_native_runtime_wp_lock_prefers_waiting_writer(tmp_path):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 native runtime 锁策略")
    source = tmp_path / "lock_policy.c"
    source.write_text(
        r'''
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

void __ezrt_lock_register(const char *name, int32_t policy);
void __ezrt_lock_read_acquire(const char *name);
void __ezrt_lock_read_release(const char *name);
void __ezrt_lock_write_acquire(const char *name);
void __ezrt_lock_write_release(const char *name);

static int order[2];
static int pos = 0;

static void *writer(void *arg) {
    (void)arg;
    __ezrt_lock_write_acquire("queue");
    order[pos++] = 1;
    __ezrt_lock_write_release("queue");
    return 0;
}

static void *late_reader(void *arg) {
    (void)arg;
    __ezrt_lock_read_acquire("queue");
    order[pos++] = 2;
    __ezrt_lock_read_release("queue");
    return 0;
}

int main(void) {
    pthread_t w;
    pthread_t r;
    __ezrt_lock_register("queue", 2);
    __ezrt_lock_read_acquire("queue");
    pthread_create(&w, 0, writer, 0);
    usleep(20000);
    pthread_create(&r, 0, late_reader, 0);
    usleep(20000);
    __ezrt_lock_read_release("queue");
    pthread_join(w, 0);
    pthread_join(r, 0);
    return (pos == 2 && order[0] == 1 && order[1] == 2) ? 0 : 1;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "lock_policy"
    runtime = ROOT / "packages" / "std" / "native" / "runtime.c"
    subprocess.run([cc, str(source), str(runtime), "-pthread", "-o", str(exe)], check=True)
    assert subprocess.run([str(exe)]).returncode == 0


def test_e2e_native_runtime_rp_lock_promotes_starved_writer(tmp_path):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 native runtime 锁策略")
    source = tmp_path / "lock_rp_policy.c"
    source.write_text(
        r'''
#include <pthread.h>
#include <stdint.h>
#include <unistd.h>

void __ezrt_lock_register(const char *name, int32_t policy);
void __ezrt_lock_read_acquire(const char *name);
void __ezrt_lock_read_release(const char *name);
void __ezrt_lock_write_acquire(const char *name);
void __ezrt_lock_write_release(const char *name);

static int order[2];
static int pos = 0;

static void *writer(void *arg) {
    (void)arg;
    __ezrt_lock_write_acquire("cache");
    order[pos++] = 1;
    __ezrt_lock_write_release("cache");
    return 0;
}

static void *late_reader(void *arg) {
    (void)arg;
    __ezrt_lock_read_acquire("cache");
    order[pos++] = 2;
    __ezrt_lock_read_release("cache");
    return 0;
}

int main(void) {
    pthread_t w;
    pthread_t r;
    __ezrt_lock_register("cache", 1);
    __ezrt_lock_read_acquire("cache");
    pthread_create(&w, 0, writer, 0);
    usleep(5000);
    pthread_create(&r, 0, late_reader, 0);
    usleep(20000);
    __ezrt_lock_read_release("cache");
    pthread_join(w, 0);
    pthread_join(r, 0);
    return (pos == 2 && order[0] == 1 && order[1] == 2) ? 0 : 1;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "lock_rp_policy"
    runtime = ROOT / "packages" / "std" / "native" / "runtime.c"
    subprocess.run([cc, str(source), str(runtime), "-pthread", "-o", str(exe)], check=True)
    assert subprocess.run([str(exe)]).returncode == 0


def test_e2e_native_runtime_rp_lock_allows_reader_before_starvation(tmp_path):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 native runtime 锁策略")
    source = tmp_path / "lock_rp_reader.c"
    source.write_text(
        r'''
#include <pthread.h>
#include <stdint.h>
#include <unistd.h>

void __ezrt_lock_register(const char *name, int32_t policy);
void __ezrt_lock_read_acquire(const char *name);
void __ezrt_lock_read_release(const char *name);
void __ezrt_lock_write_acquire(const char *name);
void __ezrt_lock_write_release(const char *name);

static int order[2];
static int pos = 0;

static void *writer(void *arg) {
    (void)arg;
    __ezrt_lock_write_acquire("cache2");
    order[pos++] = 1;
    __ezrt_lock_write_release("cache2");
    return 0;
}

static void *late_reader(void *arg) {
    (void)arg;
    __ezrt_lock_read_acquire("cache2");
    order[pos++] = 2;
    __ezrt_lock_read_release("cache2");
    return 0;
}

int main(void) {
    pthread_t w;
    pthread_t r;
    __ezrt_lock_register("cache2", 1);
    __ezrt_lock_read_acquire("cache2");
    pthread_create(&w, 0, writer, 0);
    pthread_create(&r, 0, late_reader, 0);
    usleep(20000);
    __ezrt_lock_read_release("cache2");
    pthread_join(w, 0);
    pthread_join(r, 0);
    return (pos == 2 && order[0] == 2 && order[1] == 1) ? 0 : 1;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "lock_rp_reader"
    runtime = ROOT / "packages" / "std" / "native" / "runtime.c"
    subprocess.run([cc, str(source), str(runtime), "-pthread", "-o", str(exe)], check=True)
    assert subprocess.run([str(exe)]).returncode == 0


def test_e2e_native_runtime_race_timeout_cancels_slow_branches(tmp_path):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 native runtime race 超时")
    source = tmp_path / "race_timeout.c"
    source.write_text(
        r'''
#include <stdint.h>
#include <sys/time.h>
#include <unistd.h>

typedef int32_t (*EzRaceI32Branch)(void);

int32_t __ezrt_race_i32(EzRaceI32Branch *branches, int32_t count, int32_t timeout_ms, int32_t *timed_out);

static int32_t slow_a(void) {
    usleep(300000);
    return 1;
}

static int32_t slow_b(void) {
    usleep(300000);
    return 2;
}

static int64_t now_ms(void) {
    struct timeval tv;
    gettimeofday(&tv, 0);
    return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

int main(void) {
    EzRaceI32Branch branches[2] = { slow_a, slow_b };
    int32_t timed_out = 0;
    int64_t start = now_ms();
    int32_t result = __ezrt_race_i32(branches, 2, 20, &timed_out);
    int64_t elapsed = now_ms() - start;
    return (result == 0 && timed_out == 1 && elapsed < 180) ? 0 : 1;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "race_timeout"
    runtime = ROOT / "packages" / "std" / "native" / "runtime.c"
    subprocess.run([cc, str(source), str(runtime), "-pthread", "-o", str(exe)], check=True)
    assert subprocess.run([str(exe)]).returncode == 0



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
    assert "function pathValue" in fs_js
    assert "text.length === 0 ? null : text" in fs_js
    assert "if (target === null)" in fs_js
    assert "FS.writeFile" in fs_js
    assert "FS.readFile" in fs_js
    assert "FS.mkdirTree" in fs_js
    assert "IDBFS" in fs_js
    assert "FS.syncfs" in fs_js
    assert "lexicalAbsPath" in fs_js
    assert "Math.floor(size) !== size" in fs_js
    assert "size > HEAPU8.length - dataPtr" in fs_js
    assert "throw new Error('invalid blob')" in fs_js
    assert "readFile: function (ret, path)" in fs_js
    assert "listDir: function (ret, path)" in fs_js
    assert "stat: function (ret, path)" in fs_js


def test_e2e_emcc_fs_rejects_invalid_blob_writes():
    """emcc writeFile/appendFile 对非法 Blob ABI 应返回失败且不创建文件。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/fs emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

const files = new Map();
const FS = {
  writeFile(path, data) { files.set(path, Uint8Array.from(data)); },
  readFile(path) { if (!files.has(path)) throw new Error('missing'); return files.get(path); },
  mkdir() {},
  mkdirTree() {},
  stat(path) { if (!files.has(path)) throw new Error('missing'); return { mode: 0, size: files.get(path).length }; },
  isDir() { return false; },
};

const library = {};
vm.runInNewContext(code, {
  HEAPU8,
  POINTER_SIZE: 4,
  FS,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function blob(dataPtr, size) {
  const ptr = _malloc(16);
  setValue(ptr, dataPtr, '*');
  setValue(ptr + 8, size, 'i64');
  return ptr;
}

const path = stringToNewUTF8('/bad.bin');
assert.strictEqual(library.writeFile(path, blob(0, -1)), 0);
assert.strictEqual(library.appendFile(path, blob(0, 1)), 0);
assert.strictEqual(library.writeFile(path, blob(HEAPU8.length - 1, 2)), 0);
assert.strictEqual(files.has('/bad.bin'), false);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "fs.js")], check=True)


def test_e2e_emcc_fs_abs_path_normalizes_missing_paths():
    """emcc absPath 对不存在路径也应返回词法规范化绝对路径。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/fs emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  if (type === 'i8') { view.setInt8(ptr, Number(value)); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

const library = {};
vm.runInNewContext(code, {
  HEAPU8,
  POINTER_SIZE: 4,
  FS: {},
  IDBFS: undefined,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function absPath(path) {
  return UTF8ToString(library.absPath(stringToNewUTF8(path)));
}

assert.strictEqual(absPath('a/../b'), '/b');
assert.strictEqual(absPath('/tmp/./x/../y'), '/tmp/y');
assert.strictEqual(absPath(''), '');
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "fs.js")], check=True)


def test_e2e_emcc_stream_flush_calls_fs_flush_hooks():
    """emcc 文件写流 flush 应尝试刷新 Emscripten FS，而不是只返回成功。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/stream emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i32') return view.getInt32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function lengthBytesUTF8(text) { return Buffer.byteLength(text, 'utf8'); }
function stringToUTF8(text, ptr, maxBytes) {
  const bytes = Buffer.from(text, 'utf8');
  HEAPU8.set(bytes.slice(0, Math.max(0, maxBytes - 1)), ptr);
  HEAPU8[ptr + Math.min(bytes.length, Math.max(0, maxBytes - 1))] = 0;
}
function stringToNewUTF8(text) {
  const len = lengthBytesUTF8(text);
  const ptr = _malloc(len + 1);
  stringToUTF8(text, ptr, len + 1);
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

let fsyncCalls = 0;
let syncfsCalls = 0;
const fakeFS = {
  mkdir(path) {},
  open(path, mode) { return { path, mode }; },
  fsync(file) { fsyncCalls += 1; assert.strictEqual(file.path, '/tmp/out.bin'); },
  syncfs(populate, cb) { syncfsCalls += 1; assert.strictEqual(populate, false); if (cb) cb(); },
};

const library = {};
vm.runInNewContext(code, {
  BigInt,
  Buffer,
  HEAPU8,
  FS: fakeFS,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

const writeOpt = _malloc(24);
library.streamOpenFileWrite(writeOpt, stringToNewUTF8('/tmp/out.bin'));
assert.strictEqual(HEAPU8[writeOpt], 1);
assert.strictEqual(library.streamFlush(writeOpt + 8), 1);
assert.strictEqual(fsyncCalls, 1);
assert.strictEqual(syncfsCalls, 1);

const readOpt = _malloc(24);
library.streamOpenFileRead(readOpt, stringToNewUTF8('/tmp/in.bin'));
assert.strictEqual(HEAPU8[readOpt], 1);
assert.strictEqual(library.streamFlush(readOpt + 8), 0);

const blob = _malloc(16);
setValue(blob, 0, '*');
setValue(blob + 8, 0, 'i64');
const memOpt = _malloc(24);
library.streamFromBlob(memOpt, blob);
assert.strictEqual(HEAPU8[memOpt], 1);
assert.strictEqual(library.streamFlush(memOpt + 8), 1);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "stream.js")], check=True)


def test_e2e_emcc_stream_rejects_invalid_blob_inputs():
    """emcc streamFromBlob/streamWrite 应拒绝非法 Blob ABI，但接受合法空 Blob。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/stream emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function _free() {}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i32') return view.getInt32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function UTF8ToString() { return ''; }

const library = {};
vm.runInNewContext(code, {
  HEAPU8,
  POINTER_SIZE: 4,
  _malloc,
  _free,
  getValue,
  setValue,
  UTF8ToString,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function blob(dataPtr, size) {
  const ptr = _malloc(16);
  setValue(ptr, dataPtr, '*');
  setValue(ptr + 8, size, 'i64');
  return ptr;
}
function streamFromBlob(blobPtr) {
  const ret = _malloc(24);
  library.streamFromBlob(ret, blobPtr);
  return ret;
}

const invalidNegative = blob(0, -1);
const invalidMissingData = blob(0, 1);
const invalidOutOfBounds = blob(HEAPU8.length - 1, 2);
const empty = blob(0, 0);
const bad = streamFromBlob(invalidNegative);
assert.strictEqual(HEAPU8[bad], 0);
assert.strictEqual(HEAPU8[streamFromBlob(invalidOutOfBounds)], 0);

const good = streamFromBlob(empty);
assert.strictEqual(HEAPU8[good], 1);
const streamPtr = good + 8;
assert.strictEqual(library.streamWrite(streamPtr, invalidNegative), -1);
assert.strictEqual(library.streamWrite(streamPtr, invalidMissingData), -1);
assert.strictEqual(library.streamWrite(streamPtr, invalidOutOfBounds), -1);
assert.strictEqual(library.streamWrite(streamPtr, empty), 0);
assert.strictEqual(library.streamClose(streamPtr), 1);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "stream.js")], check=True)


def test_e2e_native_fs_wrapper_covers_windows_and_mobile_branches():
    fs_c = (ROOT / "packages" / "std" / "native" / "fs.c").read_text(encoding="utf-8")

    for marker in [
        "#include <TargetConditionals.h>",
        "defined(__APPLE__) && TARGET_OS_IPHONE",
        "FindFirstFileA",
        "FindNextFileA",
        "DeleteFileA",
        "recursive ? ez_fs_remove_tree(real_path)",
        "_access(real_path, 0)",
        "_fullpath(NULL, real_path, 0)",
        "struct _stat64",
        "_stat64(real_path, &st)",
        "static bool ez_fs_valid_path",
        "if (!ez_fs_valid_path(path)) return NULL;",
        "if (!real_path) return ez_fs_copy_str(\"\");",
    ]:
        assert marker in fs_c
    assert "return (StrList){pages, (int64_t)count, page_count * 8, page_count}" in fs_c
    assert "(void)path;\n    return (StrList){0};" not in fs_c
    assert "strdup(" not in fs_c


def test_e2e_path_wrappers_cover_platform_path_edges():
    native_path = (ROOT / "packages" / "std" / "native" / "path.c").read_text(encoding="utf-8")
    emcc_path = (ROOT / "packages" / "std" / "emcc" / "path.js").read_text(encoding="utf-8")

    for marker in [
        "ez_is_windows_drive",
        "ez_root_len",
        "ez_path_is_abs_raw",
        "ez_normalize_raw",
        "pathToFileUrl",
        "pathFromFileUrl",
        "byte == 0",
    ]:
        assert marker in native_path
    for marker in [
        "/^[A-Za-z]:[\\\\/]/",
        "/^[\\\\/]{2}/",
        "return stringToNewUTF8('/');",
        "fileUrlByte",
        "codePointAt",
        "hexValue",
        "cStringFromBytes",
        "bytes.indexOf(0) >= 0",
        "writePathParts",
    ]:
        assert marker in emcc_path
    assert "encodeURIComponent" not in emcc_path
    assert "decodeURIComponent" not in emcc_path


def test_e2e_emcc_path_from_file_url_decodes_percent_bytes():
    """emcc pathFromFileUrl 应按路径字节解码百分号，不按 UTF-8 URI 解码拒绝原始字节。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/path emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

const library = {};
vm.runInNewContext(code, {
  HEAPU8,
  POINTER_SIZE: 4,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function fromFileUrl(url) {
  const ret = _malloc(16);
  library.pathFromFileUrl(ret, stringToNewUTF8(url));
  const ok = HEAPU8[ret] !== 0;
  const dataPtr = view.getUint32(ret + 8, true);
  const bytes = [];
  if (dataPtr) {
    for (let i = dataPtr; HEAPU8[i] !== 0; i++) bytes.push(HEAPU8[i]);
  }
  return { ok, dataPtr, bytes };
}
function toFileUrl(path) {
  return UTF8ToString(library.pathToFileUrl(stringToNewUTF8(path)));
}

assert.strictEqual(toFileUrl('/tmp/😀.txt'), 'file:///tmp/%F0%9F%98%80.txt');
assert.strictEqual(toFileUrl('/tmp/中 space.txt'), 'file:///tmp/%E4%B8%AD%20space.txt');
assert.strictEqual(toFileUrl('C:/Temp/中 space.txt'), 'file:///C:/Temp/%E4%B8%AD%20space.txt');

let decoded = fromFileUrl('file:///%FF');
assert.strictEqual(decoded.ok, true);
assert.deepStrictEqual(decoded.bytes, [0x2f, 0xff]);

decoded = fromFileUrl('file:///tmp/%E4%B8%AD');
assert.strictEqual(decoded.ok, true);
assert.deepStrictEqual(decoded.bytes, Array.from(Buffer.from('/tmp/中', 'utf8')));

decoded = fromFileUrl('file:///C:/Temp/%E4%B8%AD');
assert.strictEqual(decoded.ok, true);
assert.deepStrictEqual(decoded.bytes, Array.from(Buffer.from('C:/Temp/中', 'utf8')));

let invalid = fromFileUrl('file:///tmp/%');
assert.strictEqual(invalid.ok, false);
assert.strictEqual(invalid.dataPtr, 0);

invalid = fromFileUrl('file:///tmp/%00x');
assert.strictEqual(invalid.ok, false);
assert.strictEqual(invalid.dataPtr, 0);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "path.js")], check=True)


def test_e2e_emcc_path_root_parts_match_native_contract():
    """emcc path 根路径拆分应和 native 词法契约一致。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/path emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

const library = {};
vm.runInNewContext(code, {
  HEAPU8,
  POINTER_SIZE: 4,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function callStr(name, text) {
  return UTF8ToString(library[name](stringToNewUTF8(text)));
}

function parse(path) {
  const ret = _malloc(20);
  library.pathParse(ret, stringToNewUTF8(path));
  return {
    root: UTF8ToString(getValue(ret, '*')),
    dir: UTF8ToString(getValue(ret + 4, '*')),
    base: UTF8ToString(getValue(ret + 8, '*')),
    name: UTF8ToString(getValue(ret + 12, '*')),
    ext: UTF8ToString(getValue(ret + 16, '*')),
  };
}

assert.strictEqual(callStr('pathDir', '/'), '/');
assert.strictEqual(callStr('pathBase', '/'), '');
assert.deepStrictEqual(parse('/'), { root: '/', dir: '/', base: '', name: '', ext: '' });

assert.strictEqual(callStr('pathDir', 'C:/'), 'C:/');
assert.strictEqual(callStr('pathBase', 'C:/'), '');
assert.deepStrictEqual(parse('C:/'), { root: 'C:/', dir: 'C:/', base: '', name: '', ext: '' });

assert.strictEqual(callStr('pathDir', '//server/share'), '//server/share');
assert.strictEqual(callStr('pathBase', '//server/share'), '');
assert.deepStrictEqual(parse('//server/share'), {
  root: '//server/share',
  dir: '//server/share',
  base: '',
  name: '',
  ext: '',
});
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "path.js")], check=True)


def test_e2e_native_path_from_file_url_decodes_percent_bytes_and_rejects_nul(tmp_path):
    """native pathFromFileUrl 按字节解码百分号，但拒绝 Ez Str 无法表达的 NUL。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证 std/path native wrapper")

    harness = tmp_path / "path_file_url_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

#if defined(_WIN32)
#define EXPECTED_SEP '\\'
#else
#define EXPECTED_SEP '/'
#endif

typedef struct { bool ok; const char *value; } OptStr;

OptStr pathFromFileUrl(const char *url);

int main(void) {
    OptStr raw = pathFromFileUrl("file:///%FF");
    if (!raw.ok || !raw.value) return 2;
    if ((unsigned char)raw.value[0] != (unsigned char)EXPECTED_SEP) return 3;
    if ((unsigned char)raw.value[1] != 0xff) return 4;
    if (raw.value[2] != '\0') return 5;
    free((void *)raw.value);

    OptStr nul = pathFromFileUrl("file:///tmp/%00x");
    if (nul.ok || nul.value) return 6;

    OptStr invalid = pathFromFileUrl("file:///tmp/%");
    if (invalid.ok || invalid.value) return 7;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "path_file_url_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "path.c"),
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_str_wrappers_validate_utf8_bytes():
    native_str = (ROOT / "packages" / "std" / "native" / "str.c").read_text(encoding="utf-8")
    emcc_str = (ROOT / "packages" / "std" / "emcc" / "str.js").read_text(encoding="utf-8")

    for marker in [
        "ez_utf8_validate_len",
        "memchr(data->data, 0",
        "if (width < 0 || i + (size_t)width > len) return false;",
        "if (ch == 0xED && b1 >= 0xA0) return false;",
        "if (ch == 0xF4 && b1 > 0x8F) return false;",
    ]:
        assert marker in native_str
    for marker in [
        "function validUtf8Bytes",
        "function unicodeCase",
        "latinExtACasePairs",
        "function byteLengthPrefix",
        "else return false;",
        "if (width === 3 && ch === 0xed && bytes[i + 1] >= 0xa0) return false;",
        "if (width === 4 && ch === 0xf4 && bytes[i + 1] > 0x8f) return false;",
        "bytes.indexOf(0) >= 0",
        "HEAPU8[ret] = 0;",
    ]:
        assert marker in emcc_str


def test_e2e_emcc_str_matches_native_unicode_case_and_byte_index():
    """emcc str 大小写转换和 strIndexOf 应匹配 native 的 Unicode simple case/字节偏移规则。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/str emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function lengthBytesUTF8(text) { return Buffer.byteLength(text, 'utf8'); }
function stringToUTF8(text, ptr, maxBytes) {
  const bytes = Buffer.from(text, 'utf8');
  HEAPU8.set(bytes.slice(0, Math.max(0, maxBytes - 1)), ptr);
  HEAPU8[ptr + Math.min(bytes.length, Math.max(0, maxBytes - 1))] = 0;
}
function stringToNewUTF8(text) {
  const len = lengthBytesUTF8(text);
  const ptr = _malloc(len + 1);
  stringToUTF8(text, ptr, len + 1);
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}
function UTF8ArrayToString(bytes) {
  return Buffer.from(bytes).toString('utf8');
}

const library = {};
vm.runInNewContext(code, {
  BigInt,
  Buffer,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  UTF8ArrayToString,
  lengthBytesUTF8,
  stringToUTF8,
  stringToNewUTF8,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function lower(text) { return UTF8ToString(library.strToLower(stringToNewUTF8(text))); }
function upper(text) { return UTF8ToString(library.strToUpper(stringToNewUTF8(text))); }
function trim(text) { return UTF8ToString(library.strTrim(stringToNewUTF8(text))); }
function indexOf(text, needle) { return library.strIndexOf(stringToNewUTF8(text), stringToNewUTF8(needle)); }
function makeBlob(dataPtr, size) {
  const blob = _malloc(16);
  setValue(blob, dataPtr, '*');
  setValue(blob + 8, size, 'i64');
  return blob;
}
function makeByteBlob(bytes) {
  const data = _malloc(bytes.length);
  HEAPU8.set(bytes, data);
  return makeBlob(data, bytes.length);
}
function strFromBlob(blob) {
  const ret = _malloc(16);
  library.strFromBytes(ret, blob);
  const ok = HEAPU8[ret] !== 0;
  return { ok, value: ok ? UTF8ToString(getValue(ret + 8, '*')) : '' };
}

assert.strictEqual(lower('Ä中Ez ΣЖ Ÿ'), 'ä中ez σж ÿ');
assert.strictEqual(upper('ä中Ez σςж ÿ ß'), 'Ä中EZ ΣΣЖ Ÿ ẞ');
assert.strictEqual(trim('\u00A0\u3000EzLang\u2003\u202F'), 'EzLang');
assert.strictEqual(trim('\uFEFFEzLang\uFEFF'), '\uFEFFEzLang\uFEFF');
assert.strictEqual(indexOf('中Ez', 'Ez'), 3);
assert.strictEqual(indexOf('中Ez', 'missing'), -1);
assert.deepStrictEqual(strFromBlob(makeBlob(0, 0)), { ok: true, value: '' });
assert.deepStrictEqual(strFromBlob(makeByteBlob([0xe4, 0xb8, 0xad])), { ok: true, value: '中' });
assert.deepStrictEqual(strFromBlob(makeByteBlob([0])), { ok: false, value: '' });
assert.deepStrictEqual(strFromBlob(makeByteBlob([0x61, 0, 0x62])), { ok: false, value: '' });
assert.deepStrictEqual(strFromBlob(makeBlob(0, -1)), { ok: false, value: '' });
assert.deepStrictEqual(strFromBlob(makeBlob(0, 1)), { ok: false, value: '' });
assert.deepStrictEqual(strFromBlob(makeBlob(HEAPU8.length - 1, 2)), { ok: false, value: '' });
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "str.js")], check=True)


def test_e2e_native_str_from_bytes_rejects_nul_bytes(tmp_path):
    """native strFromBytes 校验 UTF-8 后仍要拒绝 Str ABI 无法表达的 NUL。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/str wrapper")

    harness = tmp_path / "str_from_bytes_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { bool ok; const char *value; } OptStr;

OptStr strFromBytes(const Blob *data);

static int expect_value(Blob blob, const char *expected, int code) {
    OptStr got = strFromBytes(&blob);
    if (!got.ok || !got.value) return code;
    if (strcmp(got.value, expected) != 0) return code + 1;
    free((void *)got.value);
    return 0;
}

static int expect_empty(Blob blob, int code) {
    OptStr got = strFromBytes(&blob);
    if (got.ok || got.value) return code;
    return 0;
}

int main(void) {
    uint8_t valid_utf8[] = {0xE4, 0xB8, 0xAD};
    uint8_t one_nul[] = {0};
    uint8_t inner_nul[] = {'a', 0, 'b'};
    uint8_t invalid_utf8[] = {0xFF};
    Blob empty = {NULL, 0};

    int err = expect_value(empty, "", 2);
    if (err != 0) return err;
    err = expect_value((Blob){valid_utf8, 3}, "\xE4\xB8\xAD", 4);
    if (err != 0) return err;
    err = expect_empty((Blob){one_nul, 1}, 6);
    if (err != 0) return err;
    err = expect_empty((Blob){inner_nul, 3}, 7);
    if (err != 0) return err;
    err = expect_empty((Blob){invalid_utf8, 1}, 8);
    if (err != 0) return err;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "str_from_bytes_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "str.c"),
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_math_wrappers_cover_checked_edges_and_emcc_bigint():
    native_math = (ROOT / "packages" / "std" / "native" / "math.c").read_text(encoding="utf-8")
    emcc_math = (ROOT / "packages" / "std" / "emcc" / "math.js").read_text(encoding="utf-8")

    for marker in [
        "value == INT32_MIN ? INT32_MAX",
        "value == INT64_MIN ? INT64_MAX",
        "__builtin_add_overflow",
        "__builtin_mul_overflow",
        "b == 0 || (a == INT64_MIN && b == -1)",
        "!isfinite(value)",
    ]:
        assert marker in native_math
    for marker in [
        "var I64_MIN = -(1n << 63n);",
        "var I64_MAX = (1n << 63n) - 1n;",
        "function checkedI64",
        "a === I64_MIN && b === -1n",
        "Number.isFinite(value)",
        "BigInt(Math.trunc(value))",
    ]:
        assert marker in emcc_math


def test_e2e_emcc_fmt_wrapper_covers_f32_and_strict_f64_parse():
    fmt_js = (ROOT / "packages" / "std" / "emcc" / "fmt.js").read_text(encoding="utf-8")
    assert "toString_F32: function" in fmt_js
    assert "toString_I1: function" in fmt_js
    assert "Number.parseFloat" not in fmt_js
    assert "Number(text)" in fmt_js
    for name in ["msgpackEncode_I1", "msgpackDecode_I1", "msgpackEncode_Str", "msgpackDecode_Str", "msgpackEncode_F64", "msgpackDecode_F64"]:
        assert name in fmt_js


def test_e2e_emcc_time_wrapper_covers_named_and_percent_format_tokens():
    time_js = (ROOT / "packages" / "std" / "emcc" / "time.js").read_text(encoding="utf-8")
    for token in ["'YYYY'", "'mm'", "ch === 'Y'", "ch === 'm'", "ch === 'd'", "ch === 'H'", "ch === 'M'", "ch === 'S'", "ch === '%'", "'%' + ch"]:
        assert token in time_js


def test_e2e_emcc_time_format_matches_native_token_scanner():
    """emcc time.format 应和 native 一样逐 token 解析，包含 %% 与负时间戳。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/time emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const HEAP32 = new Int32Array(memory);
const HEAP64 = new BigInt64Array(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

const library = {};
vm.runInNewContext(code, {
  BigInt,
  Buffer,
  Date,
  Int32Array,
  SharedArrayBuffer,
  Atomics,
  HEAPU8,
  HEAP32,
  HEAP64,
  stringToNewUTF8,
  UTF8ToString,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function datePtr(ms) {
  const ptr = _malloc(8);
  HEAP64[ptr >> 3] = BigInt(ms);
  return ptr;
}
function optI32(value) {
  const ptr = _malloc(8);
  HEAPU8[ptr] = 1;
  HEAP32[(ptr + 4) >> 2] = value;
  return ptr;
}
function format(ms, fmt) {
  return UTF8ToString(library.format(datePtr(ms), stringToNewUTF8(fmt)));
}

assert.strictEqual(format(0, 'YYYY-MM-DD HH:%M:SS'), '1970-01-01 00:00:00');
assert.strictEqual(format(0, 'YYYY-MM-DD HH:mm:SS'), '1970-01-01 00:00:00');
assert.strictEqual(format(0, '%Y-%m-%d %% %Q'), '1970-01-01 % %Q');
assert.strictEqual(format(-1, '%Y-%m-%d %H:%M:%S'), '1969-12-31 23:59:59');
assert.strictEqual(format(0, 'x'.repeat(160) + 'YYYY-MM-DD'), 'x'.repeat(160) + '1970-01-01');

const mutable = datePtr(0);
library.add(mutable, optI32(1), 0, 0, 0, 0, 0);
assert.strictEqual(UTF8ToString(library.format(mutable, stringToNewUTF8('%Y-%m-%d'))), '1971-01-01');
library.sub(mutable, optI32(1), 0, 0, 0, 0, 0);
assert.strictEqual(UTF8ToString(library.format(mutable, stringToNewUTF8('%Y-%m-%d'))), '1970-01-01');
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "time.js")], check=True)


def test_e2e_emcc_os_args_use_runtime_arguments():
    os_js = (ROOT / "packages" / "std" / "emcc" / "os.js").read_text(encoding="utf-8")
    assert "function writeStrList" in os_js
    assert "Module.arguments" in os_js
    assert "arguments_" in os_js
    assert "writeStrList(ret, runtimeArgs())" in os_js
    assert "function nodeProcess" in os_js
    assert "proc.env" in os_js
    assert "if (!name)" in os_js
    assert "proc.cwd()" in emcc_js_function_body(os_js, "cwd")
    assert "proc.pid" in os_js
    assert "return proc && proc.pid ? proc.pid | 0 : -1;" in emcc_js_function_body(os_js, "pid")


def test_e2e_native_os_cwd_uses_dynamic_buffer():
    native = (ROOT / "packages" / "std" / "native" / "os.c").read_text(encoding="utf-8")
    body = native[native.index("const char *cwd(void)"):native.index("void exit")]
    assert "getcwd(NULL, 0)" in body
    assert "while (cap <= 1024 * 1024)" in body
    assert "errno != ERANGE" in body
    assert "malloc(4096)" not in body
    assert 'return ez_strdup_safe("")' in body


def test_e2e_native_os_env_returns_allocated_snapshot(tmp_path):
    """原生 env 返回的字符串应由封装层复制，不能暴露 getenv 的内部存储。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/os wrapper")
    harness = tmp_path / "os_env_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <string.h>

typedef struct { bool ok; const char *value; } OptStr;

OptStr env(const char *key);
bool setEnv(const char *key, const char *value);

int main(void) {
    const char *key = "EZLANG_OS_ENV_COPY_TEST";
    if (!setEnv(key, "first")) return 1;
    OptStr first = env(key);
    if (!first.ok || !first.value || strcmp(first.value, "first") != 0) return 2;
    if (!setEnv(key, "second-longer-value")) return 3;
    if (strcmp(first.value, "first") != 0) return 4;
    OptStr second = env(key);
    if (!second.ok || !second.value || strcmp(second.value, "second-longer-value") != 0) return 5;
    return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "os_env_harness"
    subprocess.run(
        [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(harness), str(ROOT / "packages" / "std" / "native" / "os.c"), "-o", str(exe)],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_emcc_os_cwd_uses_node_process_and_browser_root():
    """emcc Node 运行时返回真实 cwd；浏览器风格环境返回虚拟根目录。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/os emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');

function makeRuntime(extra) {
  const memory = new ArrayBuffer(65536);
  const HEAPU8 = new Uint8Array(memory);
  const view = new DataView(memory);
  let heap = 1024;
  function align(value) { return (value + 7) & ~7; }
  function _malloc(size) {
    const ptr = heap;
    heap = align(heap + Math.max(1, size));
    if (heap > HEAPU8.length) throw new Error('oom');
    return ptr;
  }
  function setValue(ptr, value, type) {
    if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
    if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
    throw new Error('unsupported setValue type ' + type);
  }
  function stringToNewUTF8(text) {
    const bytes = Buffer.from(text, 'utf8');
    const ptr = _malloc(bytes.length + 1);
    HEAPU8.set(bytes, ptr);
    HEAPU8[ptr + bytes.length] = 0;
    return ptr;
  }
  function UTF8ToString(ptr) {
    if (!ptr) return '';
    let end = ptr;
    while (HEAPU8[end] !== 0) end++;
    return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
  }
  const library = {};
  vm.runInNewContext(code, Object.assign({
    Buffer,
    HEAPU8,
    _malloc,
    setValue,
    UTF8ToString,
    stringToNewUTF8,
    LibraryManager: { library },
    mergeInto(target, source) { Object.assign(target, source); },
  }, extra || {}), { filename: process.argv[1] });
  return { library, UTF8ToString, stringToNewUTF8, _malloc, HEAPU8, view };
}

let runtime = makeRuntime({ process });
assert.strictEqual(runtime.UTF8ToString(runtime.library.cwd()), process.cwd());
let ret = runtime._malloc(16);
assert.strictEqual(runtime.library.setEnv(runtime.stringToNewUTF8(''), runtime.stringToNewUTF8('bad')), 0);
runtime.library.env(ret, runtime.stringToNewUTF8(''));
assert.strictEqual(runtime.HEAPU8[ret], 0);
assert.strictEqual(runtime.view.getUint32(ret + 8, true), 0);
assert.strictEqual(Object.prototype.hasOwnProperty.call(process.env, ''), false);

runtime = makeRuntime({});
assert.strictEqual(runtime.UTF8ToString(runtime.library.cwd()), '/');
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "os.js")], check=True)


def test_e2e_emcc_io_readline_supports_node_stdin_and_browser_fallback():
    """Node 风格 emcc 运行时可通过 Asyncify 挂起读取 stdin；浏览器无 stdin 时显式返回空可选值。"""
    io_js = (ROOT / "packages" / "std" / "emcc" / "io.js").read_text(encoding="utf-8")
    body = emcc_js_function_body(io_js, "readLine")
    for marker in ["writeStdout", "process.stdout.write", "stdoutPending"]:
        assert marker in io_js
    for marker in ["readLine__async: 'auto'", "Asyncify.handleSleep", "fs.readFile(0, 'utf8'", "fs.readFileSync(0, 'utf8')"]:
        assert marker in io_js
    for marker in ["stdinIndex++", "writeOptStr(ret, true"]:
        assert marker in body
    assert "writeOptStr(ret, false" in body


def test_e2e_emcc_suspend_source_wrappers_are_asyncify_aware():
    """emcc 阻塞标准库入口应带 Asyncify 元数据，避免浏览器主线程同步等待。"""
    http_js = (ROOT / "packages" / "std" / "emcc" / "net" / "http.js").read_text(encoding="utf-8")
    fs_js = (ROOT / "packages" / "std" / "emcc" / "fs.js").read_text(encoding="utf-8")
    process_js = (ROOT / "packages" / "std" / "emcc" / "process.js").read_text(encoding="utf-8")
    stream_js = (ROOT / "packages" / "std" / "emcc" / "stream.js").read_text(encoding="utf-8")
    tcp_js = (ROOT / "packages" / "std" / "emcc" / "net" / "tcp.js").read_text(encoding="utf-8")
    ws_js = (ROOT / "packages" / "std" / "emcc" / "net" / "ws.js").read_text(encoding="utf-8")
    for marker in ["fetch__async: 'auto'", "fetchEx__async: 'auto'", "Asyncify.handleAsync", "await fetch"]:
        assert marker in http_js
    assert "xhr.open(req.method || 'GET', req.url, false)" in http_js
    for marker in ["readFile__async: 'auto'", "writeFile__async: 'auto'", "appendFile__async: 'auto'", "Asyncify.handleSleep"]:
        assert marker in fs_js
    for marker in ["processExec__async: 'auto'", "processSpawn__async: 'auto'", "processWait__async: 'auto'", "childProcess.spawn(", "Asyncify.handleSleep"]:
        assert marker in process_js
    for marker in [
        "streamOpenFileRead__async: 'auto'", "streamRead__async: 'auto'", "streamWrite__async: 'auto'",
        "streamCopy__async: 'auto'", "bridge.read = streamReadImpl", "Asyncify.handleSleep",
    ]:
        assert marker in stream_js
    for marker in [
        "tcpConnect__async: 'auto'", "tcpAccept__async: 'auto'", "tcpRead__async: 'auto'",
        "tcpWrite__async: 'auto'", "udpBind__async: 'auto'", "udpSend__async: 'auto'",
        "udpRecvFrom__async: 'auto'", "udpRecv__async: 'auto'", "Asyncify.handleAsync",
        "tcpConnectTimeout__async: 'auto'", "tcpAcceptTimeout__async: 'auto'",
        "tcpReadTimeout__async: 'auto'", "tcpWriteTimeout__async: 'auto'",
        "udpSendTimeout__async: 'auto'", "udpRecvFromTimeout__async: 'auto'", "udpRecvTimeout__async: 'auto'",
        "tcpTlsConnect__async: 'auto'", "tcpTlsRead__async: 'auto'", "tcpTlsWrite__async: 'auto'",
    ]:
        assert marker in tcp_js
    for marker in ["wsConnect__async: 'auto'", "wsRecv__async: 'auto'", "Asyncify.handleAsync", "new WebSocket"]:
        assert marker in ws_js


def test_e2e_emcc_io_print_preserves_no_newline_when_stdout_write_exists():
    """emcc print 和 println 应保留无换行/有换行差异。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/io emcc wrapper")
    stdlib_doc = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")
    stdlib_api_doc = (ROOT / "docs" / "stdlib-api.md").read_text(encoding="utf-8")
    assert "Node `stdout.write` 无换行" in stdlib_doc
    assert "连续 `print` 内容并在下一次 `println`" in stdlib_api_doc
    assert "| `print`    | 向 stdout 输出字符串           | logcat / os_log      | `console.log`" not in stdlib_doc
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');

function makeRuntime(extra) {
  const memory = new ArrayBuffer(65536);
  const HEAPU8 = new Uint8Array(memory);
  const view = new DataView(memory);
  let heap = 1024;
  function align(value) { return (value + 7) & ~7; }
  function _malloc(size) {
    const ptr = heap;
    heap = align(heap + Math.max(1, size));
    if (heap > HEAPU8.length) throw new Error('oom');
    return ptr;
  }
  function setValue(ptr, value, type) {
    if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
    throw new Error('unsupported setValue type ' + type);
  }
  function stringToNewUTF8(text) {
    const bytes = Buffer.from(text, 'utf8');
    const ptr = _malloc(bytes.length + 1);
    HEAPU8.set(bytes, ptr);
    HEAPU8[ptr + bytes.length] = 0;
    return ptr;
  }
  function UTF8ToString(ptr) {
    if (!ptr) return '';
    let end = ptr;
    while (HEAPU8[end] !== 0) end++;
    return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
  }
  const library = {};
  vm.runInNewContext(code, Object.assign({
    HEAPU8,
    _malloc,
    setValue,
    UTF8ToString,
    stringToNewUTF8,
    LibraryManager: { library },
    mergeInto(target, source) { Object.assign(target, source); },
  }, extra || {}), { filename: process.argv[1] });
  return { library, stringToNewUTF8 };
}

let stdout = '';
let runtime = makeRuntime({ process: { stdout: { write(value) { stdout += value; } } } });
runtime.library.print(runtime.stringToNewUTF8('a'));
runtime.library.println(runtime.stringToNewUTF8('b'));
assert.strictEqual(stdout, 'ab\n');

const lines = [];
runtime = makeRuntime({ out(value) { lines.push(value); } });
runtime.library.print(runtime.stringToNewUTF8('x'));
runtime.library.print(runtime.stringToNewUTF8('y'));
assert.deepStrictEqual(lines, []);
runtime.library.println(runtime.stringToNewUTF8('z'));
assert.deepStrictEqual(lines, ['xyz']);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "io.js")], check=True)


def test_e2e_emcc_http_server_wrapper_is_not_legacy_stub():
    """emcc HTTP createServer 不应退回旧的统一失败占位。"""
    text = (ROOT / "packages" / "std" / "emcc" / "net" / "http.js").read_text(encoding="utf-8")
    body = emcc_js_function_body(text, "createServer")
    assert "HTTP_SERVER_UNSUPPORTED_HANDLE" not in text
    assert "nodeRequire('http')" in body
    assert "http.createServer" in body
    assert "return BigInt(handle);" in body


def test_e2e_emcc_optional_and_struct_returns_use_sret(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.ez").write_text(
        'from "std/fmt" import { parseInt, b64Decode, urlDecode };\n'
        'from "std/io" import { readLine };\n'
        'from "std/os" import { args, env };\n'
        'from "std/fs" import { readFile, listDir, stat };\n'
        'let n = parseInt(s = "42");\n'
        'let blob = b64Decode(s = "aGVsbG8=");\n'
        'let text = urlDecode(s = "a%20b");\n'
        'let line = readLine();\n'
        'let argv = args();\n'
        'let home = env(key = "HOME");\n'
        'let file = readFile(path = "missing.txt");\n'
        'let names = listDir(path = ".");\n'
        'let info = stat(path = "missing.txt");\n',
        encoding="utf-8",
    )
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        "[project]\n"
        "name = \"emcc_sret\"\n"
        "version = \"0.1.0\"\n"
        "main = \"src/index.ez\"\n\n"
        "[[output]]\n"
        "arch = \"wasm32\"\n"
        "os = \"emcc\"\n"
        "dir = \"dist\"\n",
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_text = (tmp_path / "dist" / "emcc_sret.ll").read_text(encoding="utf-8")
    assert 'declare void @"parseInt"({i1, i32}* sret({i1, i32})' in ir_text
    assert 'declare void @"readLine"({i1, i8*}* sret({i1, i8*})' in ir_text
    assert 'declare void @"args"({i8***, i64, i64, i64}* sret({i8***, i64, i64, i64})' in ir_text
    assert 'declare void @"readFile"(%"Blob"* sret(%"Blob")' in ir_text
    assert 'declare void @"stat"({i1, %"FileStat"}* sret({i1, %"FileStat"})' in ir_text


def test_e2e_emcc_net_wrappers_use_optional_sret():
    http_js = (ROOT / "packages" / "std" / "emcc" / "net" / "http.js").read_text(encoding="utf-8")
    tcp_js = (ROOT / "packages" / "std" / "emcc" / "net" / "tcp.js").read_text(encoding="utf-8")
    ws_js = (ROOT / "packages" / "std" / "emcc" / "net" / "ws.js").read_text(encoding="utf-8")
    assert "fetch: function (ret, url)" in http_js
    assert "fetchEx: function (ret, req)" in http_js
    assert "HttpResponse_text: function" in http_js
    assert "tcpConnect: function (ret, host, port)" in tcp_js
    assert "tcpConnectTimeout: function (ret, host, port, timeoutMs)" in tcp_js
    assert "tcpTlsConnect: function (ret, host, port)" in tcp_js
    assert "tcpTlsRead: function (ret, connPtr, maxBytes)" in tcp_js
    assert "tcpTlsWrite: function (connPtr, dataPtr)" in tcp_js
    assert "tcpListen: function (ret, host, port)" in tcp_js
    assert "tcpAcceptTimeout: function (ret, listenerPtr, timeoutMs)" in tcp_js
    assert "tcpReadTimeout: function (ret, connPtr, maxBytes, timeoutMs)" in tcp_js
    assert "tcpWriteTimeout: function (connPtr, dataPtr, timeoutMs)" in tcp_js
    assert "udpBind: function (ret, host, port)" in tcp_js
    assert "udpSendTimeout: function (socketPtr, host, port, dataPtr, timeoutMs)" in tcp_js
    assert "udpRecvFrom: function (ret, socketPtr, maxBytes)" in tcp_js
    assert "udpRecvFromTimeout: function (ret, socketPtr, maxBytes, timeoutMs)" in tcp_js
    assert "udpRecvTimeout: function (ret, socketPtr, maxBytes, timeoutMs)" in tcp_js
    assert "wsConnect: function (ret, url)" in ws_js


def test_e2e_emcc_http_fetch_ex_rejects_invalid_body_blob_before_xhr():
    """emcc fetchEx 遇到非法请求体 Blob 应失败，不能调用 XHR.send。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/net/http emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;
let sendCalls = [];

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i32') return view.getInt32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

class FakeXHR {
  open(method, url, sync) {
    this.method = method;
    this.url = url;
    this.sync = sync;
    this.status = 200;
    this.response = new ArrayBuffer(0);
    this.responseText = '';
  }
  setRequestHeader() {}
  getAllResponseHeaders() { return ''; }
  send(body) { sendCalls.push(body); }
}

const library = {};
vm.runInNewContext(code, {
  BigInt,
  ArrayBuffer,
  TextDecoder,
  TextEncoder,
  Uint8Array,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  XMLHttpRequest: FakeXHR,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function makeRequest(bodyPtr, bodySize) {
  const req = _malloc(64);
  setValue(req, stringToNewUTF8('POST'), '*');
  setValue(req + 8, stringToNewUTF8('http://example.test/'), '*');
  setValue(req + 16, 0, '*');
  setValue(req + 24, 0, '*');
  setValue(req + 32, 0, 'i32');
  setValue(req + 36, 0, 'i32');
  setValue(req + 40, 0, 'i32');
  HEAPU8[req + 40] = 1;
  setValue(req + 48, bodyPtr, '*');
  setValue(req + 56, bodySize, 'i64');
  return req;
}
function makeRequestWithoutBody() {
  const req = makeRequest(0, 0);
  HEAPU8[req + 40] = 0;
  return req;
}
function fetchEx(req) {
  const ret = _malloc(64);
  library.fetchEx(ret, req);
  return HEAPU8[ret] !== 0;
}

assert.strictEqual(fetchEx(makeRequest(0, -1)), false);
assert.strictEqual(fetchEx(makeRequest(0, 1)), false);
assert.strictEqual(fetchEx(makeRequest(HEAPU8.length - 1, 2)), false);
assert.deepStrictEqual(sendCalls, []);
assert.strictEqual(fetchEx(makeRequestWithoutBody()), true);
assert.strictEqual(fetchEx(makeRequest(0, 0)), true);
assert.strictEqual(sendCalls.length, 2);
assert.strictEqual(sendCalls[0], null);
assert.strictEqual(sendCalls[1], null);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "net" / "http.js")], check=True)


def test_e2e_emcc_http_response_text_rejects_nul_and_invalid_utf8():
    """emcc HttpResponse.text 遇到不能表示为 Str 的响应体应返回空字符串。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/net/http emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i32') return view.getInt32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

const library = {};
vm.runInNewContext(code, {
  BigInt,
  ArrayBuffer,
  DataView,
  TextDecoder,
  TextEncoder,
  Uint8Array,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function makeResponse(bytes) {
  const resp = _malloc(48);
  const body = _malloc(bytes.length || 1);
  HEAPU8.set(bytes, body);
  setValue(resp, 200, 'i32');
  setValue(resp + 8, 0, '*');
  setValue(resp + 16, 0, '*');
  setValue(resp + 24, 0, 'i32');
  setValue(resp + 28, 0, 'i32');
  setValue(resp + 32, 0, 'i32');
  setValue(resp + 32, body, '*');
  setValue(resp + 40, bytes.length, 'i64');
  return resp;
}
function text(bytes) {
  return UTF8ToString(library.HttpResponse_text(makeResponse(Uint8Array.from(bytes))));
}

assert.strictEqual(text([111, 107]), 'ok');
assert.strictEqual(text([97, 0, 98]), '');
assert.strictEqual(text([255]), '');
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "net" / "http.js")], check=True)


def test_e2e_emcc_http_server_uses_node_http_bridge():
    """emcc Node 风格运行时应创建基础 HTTP 服务端并调用 Ez 路由回调。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/net/http emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(131072);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i32') return view.getInt32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}
function blobText(ptr) {
  const dataPtr = getValue(ptr, '*');
  const size = getValue(ptr + 8, 'i64');
  return Buffer.from(HEAPU8.slice(dataPtr, dataPtr + size)).toString('utf8');
}
function dictValue(dictPtr, key) {
  const keyPages = getValue(dictPtr, '*');
  const valuePages = getValue(dictPtr + 8, '*');
  const count = getValue(dictPtr + 16, 'i32');
  for (let i = 0; i < count; i++) {
    const keyPage = getValue(keyPages + Math.floor(i / 8) * 4, '*');
    const valuePage = getValue(valuePages + Math.floor(i / 8) * 4, '*');
    const slot = i % 8;
    if (UTF8ToString(getValue(keyPage + slot * 4, '*')) === key) {
      return UTF8ToString(getValue(valuePage + slot * 4, '*'));
    }
  }
  return '';
}
function writeBlob(ptr, text) {
  const bytes = Buffer.from(text, 'utf8');
  const data = _malloc(bytes.length || 1);
  HEAPU8.set(bytes, data);
  setValue(ptr, data, '*');
  setValue(ptr + 8, bytes.length, 'i64');
}
function writeDict(ptr, entries) {
  const pages = entries.length ? _malloc(4) : 0;
  const values = entries.length ? _malloc(4) : 0;
  const keyPage = entries.length ? _malloc(32) : 0;
  const valuePage = entries.length ? _malloc(32) : 0;
  if (entries.length) {
    setValue(pages, keyPage, '*');
    setValue(values, valuePage, '*');
    entries.forEach((entry, index) => {
      setValue(keyPage + index * 4, stringToNewUTF8(entry[0]), '*');
      setValue(valuePage + index * 4, stringToNewUTF8(entry[1]), '*');
    });
  }
  setValue(ptr, pages, '*');
  setValue(ptr + 8, values, '*');
  setValue(ptr + 16, entries.length, 'i32');
  setValue(ptr + 20, entries.length ? 8 : 0, 'i32');
  setValue(ptr + 24, entries.length ? 1 : 0, 'i32');
}

class SyncPromise {
  constructor(executor) {
    this.value = undefined;
    this.error = undefined;
    executor(
      (value) => { this.value = value instanceof SyncPromise ? value.value : value; },
      (error) => { this.error = error; }
    );
  }
  then(onFulfilled, onRejected) {
    return new SyncPromise((resolve, reject) => {
      try {
        if (this.error !== undefined) resolve(onRejected ? onRejected(this.error) : undefined);
        else resolve(onFulfilled ? onFulfilled(this.value) : this.value);
      } catch (error) {
        reject(error);
      }
    });
  }
}

class FakeRequest {
  constructor() {
    this.method = 'POST';
    this.url = '/hello?name=ez';
    this.headers = { 'x-ez': 'ping' };
    this.events = Object.create(null);
  }
  on(name, fn) {
    (this.events[name] || (this.events[name] = [])).push(fn);
    if (name === 'data') fn(Buffer.from('data'));
    if (name === 'end') fn();
    return this;
  }
}
class FakeResponse {
  constructor() { this.status = 0; this.headers = {}; this.body = Buffer.alloc(0); }
  writeHead(status, headers) { this.status = status; this.headers = headers; }
  end(body) { this.body = Buffer.from(body || []); }
}
class FakeServer {
  constructor(handler) { this.handler = handler; this.events = Object.create(null); this.closed = false; this.response = new FakeResponse(); }
  once(name, fn) { (this.events[name] || (this.events[name] = [])).push(fn); return this; }
  emit(name) { (this.events[name] || []).slice().forEach((fn) => fn()); }
  listen(options) { this.options = options; this.emit('listening'); this.handler(new FakeRequest(), this.response); }
  close() { this.closed = true; }
}

let fakeServer = null;
const fakeHttp = { createServer(handler) { fakeServer = new FakeServer(handler); return fakeServer; } };
const library = {};
function handler(respPtr, reqPtr) {
  assert.strictEqual(UTF8ToString(getValue(reqPtr, '*')), 'POST');
  assert.strictEqual(UTF8ToString(getValue(reqPtr + 8, '*')), '/hello?name=ez');
  assert.strictEqual(dictValue(reqPtr + 16, 'x-ez'), 'ping');
  assert.strictEqual(HEAPU8[reqPtr + 40], 1);
  assert.strictEqual(blobText(reqPtr + 48), 'data');
  setValue(respPtr, 201, 'i32');
  writeDict(respPtr + 8, [['X-Ez', 'pong'], ['Content-Length', '999']]);
  writeBlob(respPtr + 32, 'ok');
}

vm.runInNewContext(code, {
  BigInt,
  Buffer,
  ArrayBuffer,
  DataView,
  TextDecoder,
  TextEncoder,
  Uint8Array,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  Promise: SyncPromise,
  wasmTable: { get(index) { assert.strictEqual(index, 7); return handler; } },
  Asyncify: { handleAsync(fn) { const value = fn(); return value instanceof SyncPromise ? value.value : value; } },
  require(name) { return name === 'http' ? fakeHttp : null; },
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

const handle = library.createServer(stringToNewUTF8('127.0.0.1'), 8080);
assert.strictEqual(typeof handle, 'bigint');
assert.notStrictEqual(handle, 0n);
const serverPtr = _malloc(8);
setValue(serverPtr, handle, 'i64');
library.HttpServer_on(serverPtr, stringToNewUTF8('/hello'), 7);
library.HttpServer_start(serverPtr);
assert.strictEqual(fakeServer.options.host, '127.0.0.1');
assert.strictEqual(fakeServer.options.port, 8080);
assert.strictEqual(fakeServer.response.status, 201);
assert.strictEqual(fakeServer.response.headers['X-Ez'], 'pong');
assert.strictEqual(fakeServer.response.headers['Content-Length'], '2');
assert.strictEqual(fakeServer.response.body.toString('utf8'), 'ok');
library.HttpServer_stop(serverPtr);
assert.strictEqual(fakeServer.closed, true);
assert.strictEqual(getValue(serverPtr, 'i64'), 0);

const browserOnly = {};
vm.runInNewContext(code, {
  BigInt,
  ArrayBuffer,
  DataView,
  TextDecoder,
  TextEncoder,
  Uint8Array,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  Asyncify: { handleAsync(fn) { return fn(); } },
  LibraryManager: { library: browserOnly },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });
assert.strictEqual(browserOnly.createServer(stringToNewUTF8('127.0.0.1'), 8080), 0n);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "net" / "http.js")], check=True)


def emcc_js_function_body(text: str, name: str) -> str:
    pattern = rf"{name}: function \([^)]*\) \{{(?P<body>.*?)\n\s*\}},"
    match = re.search(pattern, text, re.S)
    assert match, f"找不到 emcc JS wrapper 函数 {name}"
    return match.group("body")


def test_e2e_emcc_tcp_udp_wrapper_uses_node_asyncify_bridge():
    """emcc TCP/TLS/UDP wrapper 应通过 Node net/tls/dgram + Asyncify 桥接，浏览器缺能力时失败。"""
    tcp_js = (ROOT / "packages" / "std" / "emcc" / "net" / "tcp.js").read_text(encoding="utf-8")
    for marker in [
        "nodeRequire('net')", "nodeRequire('tls')", "nodeRequire('dgram')", "net.createConnection", "net.createServer",
        "dgram.createSocket", "tcpConnect__async: 'auto'", "tcpAccept__async: 'auto'",
        "tcpRead__async: 'auto'", "tcpWrite__async: 'auto'", "udpBind__async: 'auto'",
        "udpSend__async: 'auto'", "udpRecvFrom__async: 'auto'", "udpRecv__async: 'auto'",
        "tcpConnectTimeout__async: 'auto'", "tcpAcceptTimeout__async: 'auto'",
        "tcpReadTimeout__async: 'auto'", "tcpWriteTimeout__async: 'auto'",
        "tcpTlsConnect__async: 'auto'", "tcpTlsRead__async: 'auto'", "tcpTlsWrite__async: 'auto'",
        "udpSendTimeout__async: 'auto'", "udpRecvFromTimeout__async: 'auto'", "udpRecvTimeout__async: 'auto'",
    ]:
        assert marker in tcp_js

    expectations = {
        "tcpConnect": "connectAsync",
        "tcpConnectTimeout": "connectTimeoutAsync",
        "tcpTlsConnect": "tlsConnectAsync",
        "tcpTlsRead": "readTcpAsync",
        "tcpTlsWrite": "streamBridge.writeTcp",
        "tcpListen": "listenAsync",
        "tcpAccept": "acceptAsync",
        "tcpAcceptTimeout": "acceptTimeoutAsync",
        "tcpRead": "readTcpAsync",
        "tcpReadTimeout": "readTcpTimeoutAsync",
        "tcpWrite": "streamBridge.writeTcp",
        "tcpWriteTimeout": "writeTcpTimeoutAsync",
        "udpBind": "bindUdpAsync",
        "udpSend": "sendUdpAsync",
        "udpSendTimeout": "sendUdpTimeoutAsync",
        "udpRecvFrom": "recvUdpAsync",
        "udpRecvFromTimeout": "recvUdpTimeoutAsync",
        "udpRecv": "recvUdpAsync",
        "udpRecvTimeout": "recvUdpTimeoutAsync",
    }
    for name, marker in expectations.items():
        assert marker in emcc_js_function_body(tcp_js, name)


def test_e2e_emcc_tcp_udp_wrapper_node_bridge_roundtrip():
    """emcc TCP/UDP wrapper 在 Node 风格运行时应完成基础连接、收发和关闭。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/net/tcp emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const tcpCode = fs.readFileSync(process.argv[1], 'utf8');
const streamCode = fs.readFileSync(process.argv[2], 'utf8');
const memory = new ArrayBuffer(262144);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i32') return view.getInt32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}
function makeBlob(bytes) {
  const data = _malloc(bytes.length || 1);
  HEAPU8.set(Uint8Array.from(bytes), data);
  const blob = _malloc(16);
  setValue(blob, data, '*');
  setValue(blob + 8, bytes.length, 'i64');
  return blob;
}
function bytesFromBlob(ptr) {
  const dataPtr = getValue(ptr, '*');
  const size = getValue(ptr + 8, 'i64');
  return Array.from(HEAPU8.slice(dataPtr, dataPtr + size));
}
function ptrHandle(ptr) { return getValue(ptr, 'i64'); }

class SyncPromise {
  constructor(executor) {
    this.value = undefined;
    this.error = undefined;
    executor(
      (value) => { this.value = value instanceof SyncPromise ? value.value : value; },
      (error) => { this.error = error; }
    );
  }
  then(onFulfilled, onRejected) {
    return new SyncPromise((resolve, reject) => {
      try {
        if (this.error !== undefined) resolve(onRejected ? onRejected(this.error) : undefined);
        else resolve(onFulfilled ? onFulfilled(this.value) : this.value);
      } catch (error) {
        reject(error);
      }
    });
  }
}

class FakeTcpSocket {
  constructor() {
    this.events = Object.create(null);
    this.closed = false;
  }
  on(name, fn) {
    (this.events[name] || (this.events[name] = [])).push(fn);
    return this;
  }
  once(name, fn) {
    if (name === 'connect' || name === 'secureConnect') fn();
    else this.on(name, fn);
    return this;
  }
  removeListener(name, fn) {
    this.events[name] = (this.events[name] || []).filter((item) => item !== fn);
    return this;
  }
  emit(name, value) {
    (this.events[name] || []).slice().forEach((fn) => fn(value));
  }
  write(data, cb) {
    const payload = Buffer.from(data);
    this.emit('data', Buffer.concat([Buffer.from('pong:'), payload]));
    if (cb) cb();
    return true;
  }
  end() { this.closed = true; this.emit('end'); }
  destroy() { this.closed = true; this.emit('close'); }
}

class FakeServer {
  constructor(handler) {
    this.handler = handler;
    this.events = Object.create(null);
    this.closed = false;
  }
  on(name, fn) { (this.events[name] || (this.events[name] = [])).push(fn); return this; }
  once(name, fn) { return this.on(name, fn); }
  emit(name, value) { (this.events[name] || []).slice().forEach((fn) => fn(value)); }
  listen() {
    this.emit('listening');
    this.handler(new FakeTcpSocket());
  }
  close() { this.closed = true; this.emit('close'); }
}

class FakeUdpSocket {
  constructor() {
    this.events = Object.create(null);
    this.closed = false;
  }
  on(name, fn) { (this.events[name] || (this.events[name] = [])).push(fn); return this; }
  once(name, fn) { return this.on(name, fn); }
  emit(name, ...args) { (this.events[name] || []).slice().forEach((fn) => fn(...args)); }
  bind() { this.emit('listening'); }
  send(data, port, host, cb) {
    this.emit('message', Buffer.concat([Buffer.from('u:'), Buffer.from(data)]), { address: host, port });
    if (cb) cb();
  }
  close() { this.closed = true; this.emit('close'); }
}

const fakeNet = {
  createConnection() { return new FakeTcpSocket(); },
  createServer(handler) { return new FakeServer(handler); },
};
const fakeTls = { connect() { return new FakeTcpSocket(); } };
const fakeDgram = { createSocket() { return new FakeUdpSocket(); } };
function fakeRequire(name) {
  if (name === 'net') return fakeNet;
  if (name === 'tls') return fakeTls;
  if (name === 'dgram') return fakeDgram;
  throw new Error('unexpected require ' + name);
}

const library = {};
const context = {
  require: fakeRequire,
  BigInt,
  Buffer,
  ArrayBuffer,
  DataView,
  Uint8Array,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  Promise: SyncPromise,
  Asyncify: { handleAsync(fn) { const value = fn(); return value instanceof SyncPromise ? value.value : value; } },
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
};
vm.runInNewContext(streamCode, context, { filename: process.argv[2] });
vm.runInNewContext(tcpCode, context, { filename: process.argv[1] });

const ret = _malloc(24);
library.tcpConnect(ret, stringToNewUTF8('127.0.0.1'), 9000);
assert.strictEqual(HEAPU8[ret], 1);
const conn = ret + 8;
assert.strictEqual(library.tcpWrite(conn, makeBlob([112, 105, 110, 103])), 4);
const tcpRead = _malloc(24);
library.tcpRead(tcpRead, conn, 16);
assert.strictEqual(HEAPU8[tcpRead], 1);
assert.deepStrictEqual(bytesFromBlob(tcpRead + 8), Array.from(Buffer.from('pong:ping')));

const timeoutRet = _malloc(24);
library.tcpConnectTimeout(timeoutRet, stringToNewUTF8('127.0.0.1'), 9000, 1);
assert.strictEqual(HEAPU8[timeoutRet], 1);
const timeoutConn = timeoutRet + 8;
assert.strictEqual(library.tcpWriteTimeout(timeoutConn, makeBlob([111, 107]), 1), 2);
const tcpTimeoutRead = _malloc(24);
library.tcpReadTimeout(tcpTimeoutRead, timeoutConn, 16, 1);
assert.strictEqual(HEAPU8[tcpTimeoutRead], 1);
assert.deepStrictEqual(bytesFromBlob(tcpTimeoutRead + 8), Array.from(Buffer.from('pong:ok')));
assert.strictEqual(library.tcpClose(timeoutConn), 1);

const tlsRet = _malloc(24);
library.tcpTlsConnect(tlsRet, stringToNewUTF8('example.com'), 443);
assert.strictEqual(HEAPU8[tlsRet], 1);
const tlsConn = tlsRet + 8;
assert.strictEqual(library.tcpTlsWrite(tlsConn, makeBlob([116, 108, 115])), 3);
const tlsRead = _malloc(24);
library.tcpTlsRead(tlsRead, tlsConn, 16);
assert.strictEqual(HEAPU8[tlsRead], 1);
assert.deepStrictEqual(bytesFromBlob(tlsRead + 8), Array.from(Buffer.from('pong:tls')));
assert.strictEqual(library.tcpTlsClose(tlsConn), 1);

const stream = _malloc(16);
library.streamFromTcpHandle(stream, ptrHandle(conn));
assert.strictEqual(library.streamWrite(stream, makeBlob([50])), 1);
const streamRead = _malloc(24);
library.streamRead(streamRead, stream, 16);
assert.strictEqual(HEAPU8[streamRead], 1);
assert.deepStrictEqual(bytesFromBlob(streamRead + 8), Array.from(Buffer.from('pong:2')));
assert.strictEqual(library.streamClose(stream), 1);

const listenerRet = _malloc(24);
library.tcpListen(listenerRet, stringToNewUTF8('127.0.0.1'), 8080);
assert.strictEqual(HEAPU8[listenerRet], 1);
const acceptedRet = _malloc(24);
library.tcpAccept(acceptedRet, listenerRet + 8);
assert.strictEqual(HEAPU8[acceptedRet], 1);
assert.strictEqual(library.tcpListenerClose(listenerRet + 8), 1);

const timeoutListenerRet = _malloc(24);
library.tcpListen(timeoutListenerRet, stringToNewUTF8('127.0.0.1'), 8081);
assert.strictEqual(HEAPU8[timeoutListenerRet], 1);
const acceptedTimeoutRet = _malloc(24);
library.tcpAcceptTimeout(acceptedTimeoutRet, timeoutListenerRet + 8, 1);
assert.strictEqual(HEAPU8[acceptedTimeoutRet], 1);
assert.strictEqual(library.tcpListenerClose(timeoutListenerRet + 8), 1);

const udpRet = _malloc(24);
library.udpBind(udpRet, stringToNewUTF8('127.0.0.1'), 0);
assert.strictEqual(HEAPU8[udpRet], 1);
const udpSocket = udpRet + 8;
assert.strictEqual(library.udpSend(udpSocket, stringToNewUTF8('127.0.0.1'), 9001, makeBlob([120])), 1);
const packet = _malloc(40);
library.udpRecvFrom(packet, udpSocket, 16);
assert.strictEqual(HEAPU8[packet], 1);
assert.deepStrictEqual(bytesFromBlob(packet + 8), Array.from(Buffer.from('u:x')));
assert.strictEqual(UTF8ToString(getValue(packet + 24, '*')), '127.0.0.1');
assert.strictEqual(getValue(packet + 32, 'i32'), 9001);
assert.strictEqual(library.udpSendTimeout(udpSocket, stringToNewUTF8('127.0.0.1'), 9002, makeBlob([121]), 1), 1);
const packetTimeout = _malloc(40);
library.udpRecvFromTimeout(packetTimeout, udpSocket, 16, 1);
assert.strictEqual(HEAPU8[packetTimeout], 1);
assert.deepStrictEqual(bytesFromBlob(packetTimeout + 8), Array.from(Buffer.from('u:y')));
assert.strictEqual(UTF8ToString(getValue(packetTimeout + 24, '*')), '127.0.0.1');
assert.strictEqual(getValue(packetTimeout + 32, 'i32'), 9002);
assert.strictEqual(library.udpSendTimeout(udpSocket, stringToNewUTF8('127.0.0.1'), 9003, makeBlob([122]), 1), 1);
const udpBlobTimeout = _malloc(24);
library.udpRecvTimeout(udpBlobTimeout, udpSocket, 16, 1);
assert.strictEqual(HEAPU8[udpBlobTimeout], 1);
assert.deepStrictEqual(bytesFromBlob(udpBlobTimeout + 8), Array.from(Buffer.from('u:z')));
assert.strictEqual(library.udpClose(udpSocket), 1);

const badRet = _malloc(24);
library.tcpConnect(badRet, stringToNewUTF8('127.0.0.1'), 65536);
assert.strictEqual(HEAPU8[badRet], 0);
'''
    subprocess.run([
        node,
        "-e",
        script,
        str(ROOT / "packages" / "std" / "emcc" / "net" / "tcp.js"),
        str(ROOT / "packages" / "std" / "emcc" / "stream.js"),
    ], check=True)


def test_e2e_emcc_ws_wrapper_uses_websocket_bridge():
    """emcc WebSocket wrapper 应通过 WebSocket 桥接完成连接、发送、接收和关闭。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("需要 Node 验证 std/net/ws emcc wrapper")
    script = r'''
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync(process.argv[1], 'utf8');
const memory = new ArrayBuffer(65536);
const HEAPU8 = new Uint8Array(memory);
const view = new DataView(memory);
let heap = 1024;

function align(value) { return (value + 7) & ~7; }
function _malloc(size) {
  const ptr = heap;
  heap = align(heap + Math.max(1, size));
  if (heap > HEAPU8.length) throw new Error('oom');
  return ptr;
}
function getValue(ptr, type) {
  if (type === '*') return view.getUint32(ptr, true);
  if (type === 'i32') return view.getInt32(ptr, true);
  if (type === 'i64') return Number(view.getBigInt64(ptr, true));
  throw new Error('unsupported getValue type ' + type);
}
function setValue(ptr, value, type) {
  if (type === '*') { view.setUint32(ptr, Number(value), true); return; }
  if (type === 'i32') { view.setInt32(ptr, Number(value), true); return; }
  if (type === 'i64') { view.setBigInt64(ptr, BigInt(value), true); return; }
  throw new Error('unsupported setValue type ' + type);
}
function stringToNewUTF8(text) {
  const bytes = Buffer.from(text, 'utf8');
  const ptr = _malloc(bytes.length + 1);
  HEAPU8.set(bytes, ptr);
  HEAPU8[ptr + bytes.length] = 0;
  return ptr;
}
function UTF8ToString(ptr) {
  if (!ptr) return '';
  let end = ptr;
  while (HEAPU8[end] !== 0) end++;
  return Buffer.from(HEAPU8.slice(ptr, end)).toString('utf8');
}

class SyncPromise {
  constructor(executor) {
    this.value = undefined;
    this.error = undefined;
    executor(
      (value) => { this.value = value instanceof SyncPromise ? value.value : value; },
      (error) => { this.error = error; }
    );
  }
  then(onFulfilled, onRejected) {
    return new SyncPromise((resolve, reject) => {
      try {
        if (this.error !== undefined) resolve(onRejected ? onRejected(this.error) : undefined);
        else resolve(onFulfilled ? onFulfilled(this.value) : this.value);
      } catch (error) {
        reject(error);
      }
    });
  }
  static resolve(value) { return new SyncPromise((resolve) => resolve(value)); }
}

class FakeWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.sent = [];
    FakeWebSocket.instances.push(this);
  }
  set onopen(fn) {
    this._onopen = fn;
    if (!this._opened && fn) {
      this._opened = true;
      this.readyState = 1;
      fn();
    }
  }
  get onopen() { return this._onopen; }
  send(data) { this.sent.push(Array.from(data)); }
  close() {
    this.readyState = 3;
    if (this.onclose) this.onclose({});
  }
  emit(data) { this.onmessage({ data }); }
}
FakeWebSocket.instances = [];

const library = {};
vm.runInNewContext(code, {
  BigInt,
  ArrayBuffer,
  DataView,
  TextDecoder,
  TextEncoder,
  Uint8Array,
  HEAPU8,
  _malloc,
  getValue,
  setValue,
  UTF8ToString,
  stringToNewUTF8,
  Promise: SyncPromise,
  WebSocket: FakeWebSocket,
  Asyncify: { handleAsync(fn) { const value = fn(); return value instanceof SyncPromise ? value.value : value; } },
  LibraryManager: { library },
  mergeInto(target, source) { Object.assign(target, source); },
}, { filename: process.argv[1] });

function makeBlob(bytes) {
  const data = _malloc(bytes.length || 1);
  HEAPU8.set(Uint8Array.from(bytes), data);
  const blob = _malloc(16);
  setValue(blob, data, '*');
  setValue(blob + 8, bytes.length, 'i64');
  return blob;
}

const ret = _malloc(24);
library.wsConnect(ret, stringToNewUTF8('wss://example.test/socket'));
assert.strictEqual(HEAPU8[ret], 1);
const conn = ret + 8;
const socket = FakeWebSocket.instances[0];
assert.strictEqual(socket.url, 'wss://example.test/socket');

assert.strictEqual(library.wsSend(conn, makeBlob([1, 2, 3])), 3);
assert.deepStrictEqual(socket.sent, [[1, 2, 3]]);

socket.emit(new Uint8Array([4, 5]).buffer);
const recv = _malloc(24);
library.wsRecv(recv, conn, 16);
assert.strictEqual(HEAPU8[recv], 1);
const dataPtr = getValue(recv + 8, '*');
const size = getValue(recv + 16, 'i64');
assert.strictEqual(size, 2);
assert.deepStrictEqual(Array.from(HEAPU8.slice(dataPtr, dataPtr + size)), [4, 5]);

assert.strictEqual(library.wsClose(conn), 1);
'''
    subprocess.run([node, "-e", script, str(ROOT / "packages" / "std" / "emcc" / "net" / "ws.js")], check=True)


def test_e2e_native_tcp_udp_write_accepts_empty_blob_and_rejects_invalid_blob(tmp_path):
    """原生 TCP/UDP 写入应接受合法空 Blob，并拒绝非法 Blob ABI。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/net/tcp wrapper")

    harness = tmp_path / "tcp_empty_blob_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#if !defined(_WIN32)
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

typedef struct { int64_t handle; } TcpConn;
typedef struct { int64_t handle; } UdpSocket;
typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { Blob data; const char *host; int32_t port; } UdpPacket;
typedef struct { bool ok; UdpSocket value; } OptUdpSocket;
typedef struct { bool ok; UdpPacket value; } OptUdpPacket;

int64_t tcpWrite(const TcpConn *conn, const Blob *data);
OptUdpSocket udpBind(const char *host, int32_t port);
int64_t udpSend(const UdpSocket *socket_value, const char *host, int32_t port, const Blob *data);
OptUdpPacket udpRecvFrom(const UdpSocket *socket_value, int64_t maxBytes);
bool udpClose(const UdpSocket *socket_value);

int main(void) {
#if defined(_WIN32)
    return 0;
#else
    int pair[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, pair) != 0) return 2;

    TcpConn conn = {(int64_t)pair[0]};
    Blob empty = {NULL, 0};
    Blob bad_negative = {NULL, -1};
    Blob bad_missing_data = {NULL, 1};

    if (tcpWrite(&conn, &empty) != 0) return 3;
    if (tcpWrite(&conn, &bad_negative) != -1) return 4;
    if (tcpWrite(&conn, &bad_missing_data) != -1) return 5;

    close(pair[0]);
    close(pair[1]);

    OptUdpSocket udp = udpBind("127.0.0.1", 0);
    if (!udp.ok || udp.value.handle == 0) return 6;
    if (udpSend(&udp.value, "127.0.0.1", 9, &empty) != 0) return 7;
    if (udpSend(&udp.value, "127.0.0.1", 9, &bad_negative) != -1) return 8;
    if (udpSend(&udp.value, "127.0.0.1", 9, &bad_missing_data) != -1) return 9;

    OptUdpSocket peer = udpBind("127.0.0.1", 0);
    if (!peer.ok || peer.value.handle == 0) return 10;
    struct sockaddr_storage addr;
    socklen_t addr_len = sizeof(addr);
    if (getsockname((int)udp.value.handle, (struct sockaddr *)&addr, &addr_len) != 0) return 11;
    uint16_t udp_port = ntohs(((struct sockaddr_in *)&addr)->sin_port);
    addr_len = sizeof(addr);
    if (getsockname((int)peer.value.handle, (struct sockaddr *)&addr, &addr_len) != 0) return 12;
    uint16_t peer_port = ntohs(((struct sockaddr_in *)&addr)->sin_port);
    Blob payload = {(uint8_t *)"ab", 2};
    if (udpSend(&peer.value, "127.0.0.1", udp_port, &payload) != 2) return 13;
    OptUdpPacket packet = udpRecvFrom(&udp.value, 8);
    if (!packet.ok) return 14;
    if (!packet.value.data.data || packet.value.data.size != 2) return 15;
    if (packet.value.data.data[0] != 'a' || packet.value.data.data[1] != 'b') return 16;
    if (!packet.value.host || packet.value.host[0] == '\0') return 17;
    if (packet.value.port != (int32_t)peer_port) return 18;
    free(packet.value.data.data);
    free((void *)packet.value.host);
    if (!udpClose(&peer.value)) return 19;
    if (!udpClose(&udp.value)) return 20;

    return 0;
#endif
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "tcp_empty_blob_harness"
    extra_libs = ["-ldl"] if sys.platform.startswith("linux") else []
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "net" / "tcp.c"),
            *extra_libs,
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_native_tcp_udp_timeout_variants_poll_without_blocking(tmp_path):
    """原生 TCP/UDP timeout 变体应支持零等待轮询和有限等待收发。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/net/tcp timeout wrapper")

    harness = tmp_path / "tcp_udp_timeout_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !defined(_WIN32)
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

typedef struct { int64_t handle; } TcpConn;
typedef struct { int64_t handle; } TcpListener;
typedef struct { int64_t handle; } UdpSocket;
typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { Blob data; const char *host; int32_t port; } UdpPacket;
typedef struct { bool ok; TcpConn value; } OptTcpConn;
typedef struct { bool ok; TcpListener value; } OptTcpListener;
typedef struct { bool ok; UdpSocket value; } OptUdpSocket;
typedef struct { bool ok; Blob value; } OptBlob;
typedef struct { bool ok; UdpPacket value; } OptUdpPacket;

OptTcpConn tcpAcceptTimeout(const TcpListener *listener, int32_t timeoutMs);
OptTcpListener tcpListen(const char *host, int32_t port);
OptBlob tcpReadTimeout(const TcpConn *conn, int64_t maxBytes, int32_t timeoutMs);
int64_t tcpWriteTimeout(const TcpConn *conn, const Blob *data, int32_t timeoutMs);
bool tcpListenerClose(const TcpListener *listener);
OptUdpSocket udpBind(const char *host, int32_t port);
int64_t udpSendTimeout(const UdpSocket *socket_value, const char *host, int32_t port, const Blob *data, int32_t timeoutMs);
OptUdpPacket udpRecvFromTimeout(const UdpSocket *socket_value, int64_t maxBytes, int32_t timeoutMs);
OptBlob udpRecvTimeout(const UdpSocket *socket_value, int64_t maxBytes, int32_t timeoutMs);
bool udpClose(const UdpSocket *socket_value);

static int bound_port(int64_t handle) {
    struct sockaddr_storage addr;
    socklen_t addr_len = sizeof(addr);
    if (getsockname((int)handle, (struct sockaddr *)&addr, &addr_len) != 0) return -1;
    if (addr.ss_family != AF_INET) return -1;
    return (int)ntohs(((struct sockaddr_in *)&addr)->sin_port);
}

int main(void) {
#if defined(_WIN32)
    return 0;
#else
    int pair[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, pair) != 0) return 2;
    TcpConn conn = {(int64_t)pair[0]};

    OptBlob empty_read = tcpReadTimeout(&conn, 4, 0);
    if (empty_read.ok) return 3;

    if (write(pair[1], "ab", 2) != 2) return 4;
    OptBlob read_data = tcpReadTimeout(&conn, 4, 100);
    if (!read_data.ok || !read_data.value.data || read_data.value.size != 2) return 5;
    if (read_data.value.data[0] != 'a' || read_data.value.data[1] != 'b') return 6;
    free(read_data.value.data);

    Blob tcp_payload = {(uint8_t *)"cd", 2};
    if (tcpWriteTimeout(&conn, &tcp_payload, 100) != 2) return 7;
    char tcp_buf[2];
    if (read(pair[1], tcp_buf, sizeof(tcp_buf)) != 2) return 8;
    if (tcp_buf[0] != 'c' || tcp_buf[1] != 'd') return 9;
    close(pair[0]);
    close(pair[1]);

    OptTcpListener listener = tcpListen("127.0.0.1", 0);
    if (!listener.ok || listener.value.handle == 0) return 10;
    OptTcpConn accepted = tcpAcceptTimeout(&listener.value, 0);
    if (accepted.ok) return 11;
    if (!tcpListenerClose(&listener.value)) return 12;

    OptUdpSocket udp = udpBind("127.0.0.1", 0);
    if (!udp.ok || udp.value.handle == 0) return 13;
    OptUdpPacket missing_packet = udpRecvFromTimeout(&udp.value, 8, 0);
    if (missing_packet.ok) return 14;

    OptUdpSocket peer = udpBind("127.0.0.1", 0);
    if (!peer.ok || peer.value.handle == 0) return 15;
    int udp_port = bound_port(udp.value.handle);
    int peer_port = bound_port(peer.value.handle);
    if (udp_port <= 0 || peer_port <= 0) return 16;

    Blob udp_payload = {(uint8_t *)"xy", 2};
    if (udpSendTimeout(&peer.value, "127.0.0.1", udp_port, &udp_payload, 100) != 2) return 17;
    OptUdpPacket packet = udpRecvFromTimeout(&udp.value, 8, 100);
    if (!packet.ok || !packet.value.data.data || packet.value.data.size != 2) return 18;
    if (packet.value.data.data[0] != 'x' || packet.value.data.data[1] != 'y') return 19;
    if (!packet.value.host || packet.value.host[0] == '\0') return 20;
    if (packet.value.port != peer_port) return 21;
    free(packet.value.data.data);
    free((void *)packet.value.host);

    Blob udp_payload_2 = {(uint8_t *)"z", 1};
    if (udpSendTimeout(&peer.value, "127.0.0.1", udp_port, &udp_payload_2, 100) != 1) return 22;
    OptBlob udp_blob = udpRecvTimeout(&udp.value, 8, 100);
    if (!udp_blob.ok || !udp_blob.value.data || udp_blob.value.size != 1) return 23;
    if (udp_blob.value.data[0] != 'z') return 24;
    free(udp_blob.value.data);

    if (!udpClose(&peer.value)) return 25;
    if (!udpClose(&udp.value)) return 26;
    return 0;
#endif
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "tcp_udp_timeout_harness"
    extra_libs = ["-ldl"] if sys.platform.startswith("linux") else []
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "net" / "tcp.c"),
            *extra_libs,
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_native_tcp_tls_fails_without_tls_backend(tmp_path):
    """TCP TLS 客户端不应在 TLS 后端不可用时伪装成功或回退明文。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/net/tcp TLS wrapper")

    harness = tmp_path / "tcp_tls_no_tls_harness.c"
    harness.write_text(
        r'''
	#include <stdbool.h>
	#include <stdint.h>
	#include <stdlib.h>

	typedef struct { int64_t handle; } TcpTlsConn;
typedef struct { bool ok; TcpTlsConn value; } OptTcpTlsConn;

OptTcpTlsConn tcpTlsConnect(const char *host, int32_t port);

int main(int argc, char **argv) {
    int port = argc > 1 ? (int)strtol(argv[1], NULL, 10) : 1;
    return tcpTlsConnect("127.0.0.1", port).ok ? 2 : 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "tcp_tls_no_tls_harness"
    extra_libs = ["-ldl"] if sys.platform.startswith("linux") else []
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-DEZ_TCP_TEST_NO_OPENSSL_DLOPEN=1",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "net" / "tcp.c"),
            *extra_libs,
            "-o",
            str(exe),
        ],
        check=True,
    )

    ready = threading.Event()
    captured = []

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            captured.append(server.getsockname()[1])
            ready.set()
            server.settimeout(2)
            try:
                conn, _ = server.accept()
            except socket.timeout:
                captured.append(b"")
                return
            with conn:
                conn.settimeout(2)
                try:
                    captured.append(conn.recv(128))
                except socket.timeout:
                    captured.append(b"")

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)
    subprocess.run([str(exe), str(captured[0])], check=True, timeout=5)
    thread.join(timeout=3)
    assert len(captured) >= 2
    assert captured[1] == b""


def test_e2e_native_ws_send_accepts_empty_blob_and_rejects_invalid_blob(tmp_path):
    """wsSend 应入口拒绝非法 Blob，避免向对端写出半个帧。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/net/ws wrapper")

    harness = tmp_path / "ws_empty_blob_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#if !defined(_WIN32)
#include <sys/socket.h>
#include <unistd.h>
#endif

typedef struct { int64_t handle; } WsConn;
typedef struct { uint8_t *data; int64_t size; } Blob;

int64_t wsSend(const WsConn *conn, const Blob *data);

int main(void) {
#if defined(_WIN32)
    return 0;
#else
    int pair[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, pair) != 0) return 2;

    WsConn conn = {(int64_t)pair[0]};
    Blob empty = {NULL, 0};
    Blob bad_negative = {NULL, -1};
    Blob bad_missing_data = {NULL, 1};

    if (wsSend(&conn, &empty) != 0) return 3;
    unsigned char frame[6];
    ssize_t got = recv(pair[1], frame, sizeof(frame), 0);
    if (got != 6) return 4;
    if ((frame[0] & 0x0f) != 0x2 || (frame[1] & 0x7f) != 0 || (frame[1] & 0x80) == 0) return 5;

    if (wsSend(&conn, &bad_negative) != -1) return 6;
    if (wsSend(&conn, &bad_missing_data) != -1) return 7;

    struct timeval timeout;
    timeout.tv_sec = 0;
    timeout.tv_usec = 10000;
    setsockopt(pair[1], SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    got = recv(pair[1], frame, sizeof(frame), 0);
    if (got > 0) return 8;

    close(pair[0]);
    close(pair[1]);
    return 0;
#endif
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "ws_empty_blob_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "net" / "ws.c"),
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_e2e_native_ws_wss_fails_without_tls_backend(tmp_path):
    """wss 客户端不应在 TLS 后端不可用时伪装成功或回退明文握手。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证原生 std/net/ws wrapper")

    harness = tmp_path / "ws_wss_no_tls_harness.c"
    harness.write_text(
        r'''
#include <stdbool.h>
#include <stdint.h>

typedef struct { int64_t handle; } WsConn;
typedef struct { bool ok; WsConn value; } OptWsConn;

OptWsConn wsConnect(const char *url);

int main(int argc, char **argv) {
    return wsConnect(argc > 1 ? argv[1] : "wss://127.0.0.1:1/").ok ? 2 : 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "ws_wss_no_tls_harness"
    extra_libs = ["-ldl"] if sys.platform.startswith("linux") else []
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-DEZ_WS_TEST_NO_OPENSSL_DLOPEN=1",
            str(harness),
            str(ROOT / "packages" / "std" / "native" / "net" / "ws.c"),
            *extra_libs,
            "-o",
            str(exe),
        ],
        check=True,
    )

    ready = threading.Event()
    captured = []

    def serve_once():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            captured.append(server.getsockname()[1])
            ready.set()
            conn, _ = server.accept()
            with conn:
                conn.settimeout(2)
                try:
                    data = conn.recv(128)
                except socket.timeout:
                    data = b""
                captured.append(data)

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)
    subprocess.run([str(exe), f"wss://127.0.0.1:{captured[0]}/"], check=True, timeout=5)
    thread.join(timeout=3)
    assert len(captured) >= 2
    assert not captured[1].startswith(b"GET /")


def test_e2e_public_emcc_wrappers_do_not_use_legacy_null_stubs():
    checks = {
        "fmt.js": ["parseInt", "b64Decode", "urlDecode"],
        "io.js": ["readLine"],
        "os.js": ["args", "env"],
        "fs.js": ["readFile", "listDir", "stat"],
        "path.js": ["pathParse", "pathFromFileUrl"],
        "str.js": ["strCharAt", "strToBytes", "strFromBytes", "strSplit"],
        "math.js": ["mathAddI64Checked", "mathF64ToI32"],
        "random.js": ["randomSeed", "randomSecureBytes", "randomSecureU64"],
        "hash.js": ["hashFnv1a32", "crc32Str"],
        "platform.js": ["platformOS", "platformHasSubprocess"],
        "uri.js": ["uriParse", "uriDecodeQuery", "uriQuerySet"],
        "debug.js": ["debugPrint", "debugStack"],
        "log.js": ["logDefaultConfig", "logSetFile", "logWriteAt"],
        "regex.js": ["regexCompile", "regexFind"],
        "crypto.js": ["cryptoSha256", "cryptoHmacSha256"],
        "compress.js": ["compressGzip", "decompressDeflate"],
        "process.js": ["processExec", "processCurrentPath"],
        "stream.js": ["streamFromBlob", "streamRead", "streamCopy"],
        "test.js": ["testAssert", "testEqualI64", "testRegisterParam", "testName", "testPassed"],
        "net/http.js": ["fetch", "fetchEx"],
        "net/tcp.js": ["tcpConnect", "tcpListen", "udpBind"],
        "net/ws.js": ["wsConnect"],
    }
    for relative, names in checks.items():
        text = (ROOT / "packages" / "std" / "emcc" / relative).read_text(encoding="utf-8")
        for name in names:
            assert f"{name}: function () {{ return 0; }}" not in text
            assert f"{name}: function (" in text


def test_e2e_ui_packages_import_by_package_name_and_build(tmp_path, capsys):
    cases = [
        (
            "web",
            'from "ez-web-ui" import { Node, createElement, setTextContent, appendChild, getBodyNode, scheduleFrame, requestPermission };\n'
            'const onFrame = (): Void => { return; };\n'
            'let node = createElement(tag = "button");\n'
            'setTextContent(node = node, text = "camera");\n'
            'appendChild(parent = getBodyNode(), child = node);\n'
            'let frame = scheduleFrame(cb = onFrame);\n'
            'let ok = requestPermission(perm = "camera");\n',
            ["ez-web-ui/emcc/web_ui.js"],
            ("wasm32", "emcc"),
        ),
        (
            "android",
            'from "ez-android-ui" import { Node, createTextView, setText, addView, getRootView, runOnMainThread, requestPermission };\n'
            'const work = (): Void => { return; };\n'
            'let label = createTextView();\n'
            'setText(node = label, text = "android.permission.CAMERA");\n'
            'addView(parent = getRootView(), child = label);\n'
            'runOnMainThread(work = work);\n'
            'let ok = requestPermission(perm = "android.permission.CAMERA");\n',
            ["ez-android-ui/native/android_ui.c"],
            ("aarch64", "android"),
        ),
        (
            "ios",
            'from "ez-ios-ui" import { Node, createLabel, setText, addSubview, getRootView, runOnMainThread, requestPermission };\n'
            'const work = (): Void => { return; };\n'
            'let label = createLabel();\n'
            'setText(node = label, text = "camera");\n'
            'addSubview(parent = getRootView(), child = label);\n'
            'runOnMainThread(work = work);\n'
            'let ok = requestPermission(perm = "camera");\n',
            ["ez-ios-ui/native/ios_ui.c"],
            ("aarch64", "ios"),
        ),
    ]

    for name, source, expected_libs, (arch, os_name) in cases:
        case_dir = tmp_path / name
        src_dir = case_dir / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "index.ez").write_text(source, encoding="utf-8")
        project_toml = case_dir / "project.toml"
        project_toml.write_text(
            "[project]\n"
            f"name = \"ui_{name}\"\n"
            "version = \"0.1.0\"\n"
            "main = \"src/index.ez\"\n\n"
            "[[output]]\n"
            f"arch = \"{arch}\"\n"
            f"os = \"{os_name}\"\n"
            f"dir = \"dist/{os_name}\"\n",
            encoding="utf-8",
        )

        assert ez.main(["build", "--project", str(project_toml)]) == 0, name
        out = capsys.readouterr().out
        for expected in expected_libs:
            assert str(ROOT / "packages" / expected) in out, name


def test_e2e_web_ui_emcc_wrapper_covers_dom_contract():
    """ez-web-ui emcc 绑定应覆盖 DOM 节点、事件、帧调度和批量属性接口。"""
    text = (ROOT / "packages" / "ez-web-ui" / "emcc" / "web_ui.js").read_text(encoding="utf-8")
    for name in [
        "createElement", "appendChild", "getChildren", "setAttributes", "setStyles",
        "addEventListener", "removeEventListener", "delegateEvent", "scheduleFrame",
        "scheduleMicrotask", "requestPermission", "getBodyNode",
    ]:
        assert f"{name}: function (" in text
    for marker in ["function readNodeId", "function readDict", "function writeNodeList", "function callEvent"]:
        assert marker in text
    assert "dynCall_vi" in text or "wasmTable" in text


def test_e2e_mobile_ui_native_wrappers_keep_minimal_state():
    """移动 UI 原生层至少应维护可测试的节点、文本和层级状态。"""
    checks = {
        "ez-android-ui/native/android_ui.c": ["createTextView", "createButton", "addView", "getChildCount", "runOnMainThread"],
        "ez-ios-ui/native/ios_ui.c": ["createLabel", "createButton", "addSubview", "getSubviewCount", "runOnMainThread"],
    }
    for relative, names in checks.items():
        text = (ROOT / "packages" / relative).read_text(encoding="utf-8")
        assert "ABI 占位封装" not in text
        assert "return no_node();" not in text
        assert "static UiNode" in text
        for name in names:
            assert f"{name}(" in text


def test_e2e_mobile_ui_screen_metrics_and_attributed_text_state(tmp_path):
    """移动 UI 状态层应保存宿主注入的屏幕指标和富文本可见文本。"""
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("需要 C 编译器验证移动 UI 状态层")

    android_harness = tmp_path / "android_ui_metrics_harness.c"
    android_harness.write_text(
        r'''
#include <math.h>
#include <stdint.h>

void ezAndroidSetScreenMetrics(int32_t width, int32_t height, float density);
float getScreenDensity(void);
int32_t getScreenWidth(void);
int32_t getScreenHeight(void);

int main(void) {
    if (getScreenWidth() != 0 || getScreenHeight() != 0) return 2;
    ezAndroidSetScreenMetrics(1080, 2400, 2.75f);
    if (getScreenWidth() != 1080 || getScreenHeight() != 2400) return 3;
    if (fabsf(getScreenDensity() - 2.75f) > 0.001f) return 4;
    ezAndroidSetScreenMetrics(-1, -1, -1.0f);
    if (getScreenWidth() != 0 || getScreenHeight() != 0) return 5;
    if (fabsf(getScreenDensity() - 1.0f) > 0.001f) return 6;
    return 0;
}
''',
        encoding="utf-8",
    )
    android_exe = tmp_path / "android_ui_metrics_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(android_harness),
            str(ROOT / "packages" / "ez-android-ui" / "native" / "android_ui.c"),
            "-o",
            str(android_exe),
        ],
        check=True,
    )
    subprocess.run([str(android_exe)], check=True)

    ios_harness = tmp_path / "ios_ui_metrics_harness.c"
    ios_harness.write_text(
        r'''
#include <math.h>
#include <stdint.h>
#include <string.h>

typedef struct { int32_t id; } Node;
typedef struct { float top; float left; float bottom; float right; } Insets;

Node createLabel(void);
void setAttributedText(const Node *node, const char *html);
const char *getText(const Node *node);
void ezIosSetScreenMetrics(float width, float height, float scale, float safeTop, float safeLeft, float safeBottom, float safeRight, float statusBarHeight);
float getScreenWidth(void);
float getScreenHeight(void);
float getScreenScale(void);
Insets getSafeAreaInsets(void);
float getStatusBarHeight(void);

int main(void) {
    Node label = createLabel();
    setAttributedText(&label, "<b>Hello</b>&nbsp;&amp;&lt;world&gt;");
    if (strcmp(getText(&label), "Hello &<world>") != 0) return 2;
    ezIosSetScreenMetrics(393.0f, 852.0f, 3.0f, 59.0f, 1.0f, 34.0f, 2.0f, 47.0f);
    if (fabsf(getScreenWidth() - 393.0f) > 0.001f) return 3;
    if (fabsf(getScreenHeight() - 852.0f) > 0.001f) return 4;
    if (fabsf(getScreenScale() - 3.0f) > 0.001f) return 5;
    Insets insets = getSafeAreaInsets();
    if (fabsf(insets.top - 59.0f) > 0.001f || fabsf(insets.bottom - 34.0f) > 0.001f) return 6;
    if (fabsf(getStatusBarHeight() - 47.0f) > 0.001f) return 7;
    return 0;
}
''',
        encoding="utf-8",
    )
    ios_exe = tmp_path / "ios_ui_metrics_harness"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(ios_harness),
            str(ROOT / "packages" / "ez-ios-ui" / "native" / "ios_ui.c"),
            "-o",
            str(ios_exe),
        ],
        check=True,
    )
    subprocess.run([str(ios_exe)], check=True)


def test_e2e_mobile_ui_packages_export_documented_apis():
    """移动 UI 包的 index.ez 与 native C 应覆盖文档中声明的公开 API。"""
    cases = [
        ("ez-android-ui", "android_ui.c"),
        ("ez-ios-ui", "ios_ui.c"),
    ]
    declare_pattern = re.compile(r"declare const\s+([A-Za-z_][A-Za-z0-9_]*)\s*:")
    export_pattern = re.compile(r"export declare const\s+([A-Za-z_][A-Za-z0-9_]*)\s*:")
    c_pattern = re.compile(r"^(?:const\s+char\s*\*\s*|[A-Za-z_][A-Za-z0-9_]*|void|bool|int32_t|int64_t|float|double|Node|OptNode|OptStr|Rect|Insets|Dict)\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)

    for package, native_name in cases:
        doc_apis = set(declare_pattern.findall((ROOT / "docs" / f"{package}.md").read_text(encoding="utf-8")))
        index_apis = set(export_pattern.findall((ROOT / "packages" / package / "index.ez").read_text(encoding="utf-8")))
        native_apis = set(c_pattern.findall((ROOT / "packages" / package / "native" / native_name).read_text(encoding="utf-8")))
        assert doc_apis - index_apis == set(), package
        assert doc_apis - native_apis == set(), package


def test_e2e_std_platform_externs_cover_mobile_and_emcc(tmp_path, capsys):
    std_root = ROOT / "packages" / "std"
    cases = [
        ("io", 'from "std/io" import { print };\nprint(msg = "hello");\n', ["native/io.c", "emcc/io.js"]),
        ("fs", 'from "std/fs" import { exists };\nlet ok = exists(path = "tmp.txt");\n', ["native/fs.c", "emcc/fs.js"]),
        ("os", 'from "std/os" import { platform };\nlet os_name = platform();\n', ["native/os.c", "emcc/os.js"]),
        ("time", 'from "std/time" import { timestamp };\nlet ts = timestamp();\n', ["native/time.c", "emcc/time.js"]),
        ("fmt", 'from "std/fmt" import { urlEncode };\nlet encoded = urlEncode(s = "a b");\n', ["native/fmt.c", "emcc/fmt.js"]),
        ("path", 'from "std/path" import { pathNormalize };\nlet normalized = pathNormalize(path = "a/../b");\n', ["native/path.c", "emcc/path.js"]),
        ("str", 'from "std/str" import { strByteLen };\nlet n = strByteLen(s = "hello");\n', ["native/str.c", "emcc/str.js"]),
        ("math", 'from "std/math" import { mathSqrt };\nlet root = mathSqrt(value = 4.0);\n', ["native/math.c", "emcc/math.js"]),
        ("random", 'from "std/random" import { randomSeed, randomNextU32 };\nlet source = randomSeed(seed = 1);\nlet n = randomNextU32(this = #source);\n', ["native/random.c", "emcc/random.js"]),
        ("hash", 'from "std/hash" import { crc32Str };\nlet n = crc32Str(s = "hello");\n', ["native/hash.c", "emcc/hash.js"]),
        ("platform", 'from "std/platform" import { platformOS };\nlet os_name = platformOS();\n', ["native/platform.c", "emcc/platform.js"]),
        ("uri", 'from "std/uri" import { uriNormalize };\nlet normalized = uriNormalize(url = "https://example.com/a/../b");\n', ["native/uri.c", "emcc/uri.js"]),
        ("debug", 'from "std/debug" import { debugRuntimeInfo };\nlet info = debugRuntimeInfo();\n', ["native/debug.c", "emcc/debug.js"]),
        ("log", 'from "std/log" import { logInfoMsg };\nlogInfoMsg(msg = "hello");\n', ["native/log.c", "emcc/log.js"]),
        ("regex", 'from "std/regex" import { regexCompile, regexTest };\nlet re = regexCompile(pattern = "a+", flags = 0);\nlet ok = regexTest(regex = re, input = "aaa");\n', ["native/regex.c", "emcc/regex.js"]),
        ("crypto", 'from "std/crypto" import { cryptoSha256 };\nlet data = Blob(data = "hello", size = 5);\nlet digest = cryptoSha256(data = data);\n', ["native/crypto.c", "emcc/crypto.js"]),
        ("compress", 'from "std/compress" import { compressGzip };\nlet data = Blob(data = "hello", size = 5);\nlet compressed = compressGzip(data = data);\n', ["native/compress.c", "emcc/compress.js"]),
        ("process", 'from "std/process" import { processCurrentPath };\nlet path = processCurrentPath();\n', ["native/stream.c", "native/process.c", "emcc/stream.js", "emcc/process.js"]),
        ("stream", 'from "std/stream" import { streamFromBlob };\nlet s = streamFromBlob(data = Blob(data = "", size = 0));\n', ["native/stream.c", "emcc/stream.js"]),
        ("test", 'from "std/test" import { testAssert, testRegisterParam, testName };\ntestRegisterParam(name = "case", param = "1");\ntestAssert(condition = testName(index = 0) == "case[1]", msg = "ok");\n', ["native/test.c", "emcc/test.js"]),
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
