"""编译器端到端测试"""

import re
import shutil
import subprocess
import sys
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
        for token in ["YYYY", "MM", "DD", "HH", "SS", "%Y", "%m", "%d", "%H", "%M", "%S"]:
            assert token in text, f"{doc_path.relative_to(ROOT)} 缺少 time format token {token}"
        assert "分钟使用 `%M`" in text


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


def test_e2e_native_io_wrapper_uses_mobile_logs_and_empty_mobile_stdin():
    io_c = (ROOT / "packages" / "std" / "native" / "io.c").read_text(encoding="utf-8")
    assert "__android_log_write" in io_c
    assert "ANDROID_LOG_INFO" in io_c
    assert "ANDROID_LOG_ERROR" in io_c
    assert "os_log_with_type" in io_c
    assert "OS_LOG_TYPE_INFO" in io_c
    assert "OS_LOG_TYPE_ERROR" in io_c
    assert "#if defined(__ANDROID__) || (defined(__APPLE__) && TARGET_OS_IPHONE)" in io_c
    assert "return (OptStr){false, NULL};" in io_c


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
    assert 'declare %"Blob" @"strToBytes"' in ir_text
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
        'from "std/random" import { RandomSource, randomSeed, randomNextU32, randomNextU64, randomRangeI64, randomRangeF64, randomShuffleBytes, randomEntropy, randomSecureBytes, randomSecureU64 };\n\n'
        'let source = randomSeed(seed = 42);\n'
        'let n32 = randomNextU32(this = source);\n'
        'let n64 = randomNextU64(this = source);\n'
        'let ranged_i = randomRangeI64(this = source, minValue = 1, maxValue = 10);\n'
        'let ranged_f = randomRangeF64(this = source, minValue = 0.0, maxValue = 1.0);\n'
        'let shuffled = randomShuffleBytes(this = source, data = Blob(data = "abcd", size = 4));\n'
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
    assert 'declare %"RandomSource" @"randomSeed"' in ir_text
    assert 'declare i32 @"randomNextU32"' in ir_text
    assert 'declare %"Blob" @"randomShuffleBytes"' in ir_text
    assert 'declare void @"randomSecureBytes"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
    assert_native_optional_return(ir_text, "randomSecureU64", "i64")


def test_e2e_random_wrappers_use_secure_entropy_without_prng_fallback():
    native = (ROOT / "packages" / "std" / "native" / "random.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "random.js").read_text(encoding="utf-8")

    for marker in ["CryptGenRandom", "arc4random_buf", "getrandom", 'open("/dev/urandom"', "return (OptBlob){false"]:
        assert marker in native
    secure_read = native[native.index("static bool ez_random_read_system"):native.index("OptBlob randomSecureBytes")]
    assert "ez_random_next" not in secure_read
    assert "ez_random_mix_seed" not in secure_read

    for marker in ["cryptoObj.getRandomValues", "require('crypto')", "randomBytes", "return null"]:
        assert marker in emcc
    secure_bytes = emcc[emcc.index("function secureBytes"):emcc.index("mergeInto(LibraryManager.library")]
    assert "next(" not in secure_bytes
    assert "mixSeed" not in secure_bytes


def test_e2e_std_hash_imports_and_builds(tmp_path):
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
    assert "TARGET_OS_IPHONE" in native
    assert "return false;" in native[native.index("bool platformHasSubprocess"):]
    for marker in ["stringToNewUTF8('emcc')", "stringToNewUTF8('wasm32')", "return 65536n", "SharedArrayBuffer", "typeof FS", "typeof fetch", "getRandomValues", "typeof document", "return 0;"]:
        assert marker in emcc


def test_e2e_std_process_imports_and_builds(tmp_path):
    source = tmp_path / "std_process.ez"
    source.write_text(
        'from "std/process" import { Command, Process, ProcessResult, processExec, processSpawn, processWait, processTerminate, processCurrentPath };\n\n'
        'let args: Str[] = ["-c", "printf hello"];\n'
        'let envs: Str[] = ["EZLANG_PROCESS_TEST=1"];\n'
        'let empty: Str[] = [];\n'
        'let command = Command(program = "/bin/sh", args = args, cwd = "", env = envs, stdin = Blob(data = "", size = 0));\n'
        'let result = processExec(command = command);\n'
        'let spawned = processSpawn(command = Command(program = "/bin/sh", args = args, cwd = "", env = empty, stdin = Blob(data = "", size = 0)));\n'
        'let waited = processWait(process = Process(handle = 0, pid = 0));\n'
        'let killed = processTerminate(process = Process(handle = 0, pid = 0));\n'
        'let current = processCurrentPath();\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert '%"Command" = type' in ir_text
    assert '%"ProcessResult" = type' in ir_text
    assert 'declare void @"processExec"({i1, %"ProcessResult"}* sret({i1, %"ProcessResult"})' in ir_text
    assert 'declare void @"processSpawn"({i1, %"Process"}* sret({i1, %"Process"})' in ir_text
    assert_native_optional_return(ir_text, "processCurrentPath", "i8*")


def test_e2e_process_wrappers_cover_windows_and_unsupported_targets():
    native = (ROOT / "packages" / "std" / "native" / "process.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "process.js").read_text(encoding="utf-8")
    for marker in ["CreateProcessW", "WaitForSingleObject", "TerminateProcess", "GetModuleFileNameW"]:
        assert marker in native
    assert "#if !defined(_WIN32) && !defined(__ANDROID__) && !(defined(__APPLE__) && TARGET_OS_IPHONE)" in native
    assert "return (OptProcessResult){false, {0}};" in native
    assert "return (OptProcess){false, {0}};" in native
    assert "writeOptProcessResult(ret, false)" in emcc
    assert "writeOptProcess(ret, false)" in emcc
    assert "writeOptStr(ret, null)" in emcc


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
    for marker in ["ez_scheme_valid", "ez_percent_encode", "ez_percent_decode", "ez_normalize_path", "uriQueryGet", "uriQuerySet"]:
        assert marker in native
    assert "query_mode && ch == ' '" in native
    assert "ez_query_key_matches" in native
    for marker in ["validScheme", "percentEncodeString", "percentDecodeString", "normalizePath", "queryKeyMatches", "querySet"]:
        assert marker in emcc
    assert "queryMode && ch === '+'" in emcc
    assert "entries.push(encodedKey + '=' + encodedValue)" in emcc


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
    for marker in ["abort();", "backtrace(frames", "backtrace_symbols", "ezlang native/windows", "ezlang native/linux"]:
        assert marker in native
    assert 'static const char hex[] = "0123456789abcdef"' in native
    for marker in ["console.error", "throw new Error", "new Error().stack", "padStart(2, '0')", "ezlang emcc/wasm32"]:
        assert marker in emcc


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
    assert 'declare %"LogConfig" @"logDefaultConfig"' in ir_text
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


def test_e2e_log_wrappers_cover_file_target_mobile_logs_and_emcc_console():
    """std/log 应覆盖文件目标、移动端系统日志与 emcc console 边界。"""
    native = (ROOT / "packages" / "std" / "native" / "log.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "log.js").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")

    for marker in ["EZ_LOG_TARGET_FILE", "fopen(path, \"a\")", "logSetFile", "fflush(out)"]:
        assert marker in native
    assert "__android_log_write" in native
    assert "os_log_with_type" in native
    assert "WebAssembly 同步日志不支持本地文件目标" in emcc
    assert "return 0;" in emcc_js_function_body(emcc, "logSetFile")
    assert "console.error" in emcc and "console.warn" in emcc and "console.log" in emcc
    assert "原生平台支持 stderr/stdout/file" in docs
    assert "移动端非文件目标同步写系统日志" in docs


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
    assert 'declare %"Regex" @"regexCompile"' in ir_text
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


def test_e2e_std_compress_imports_and_builds(tmp_path):
    source = tmp_path / "std_compress.ez"
    source.write_text(
        'from "std/compress" import { compressGzip, decompressGzip, compressZlib, decompressZlib, compressDeflate, decompressDeflate };\n\n'
        'let data = Blob(data = "hello", size = 5);\n'
        'let gz = compressGzip(data = data);\n'
        'let raw_gz = decompressGzip(data = gz.value);\n'
        'let z = compressZlib(data = data);\n'
        'let raw_z = decompressZlib(data = z.value);\n'
        'let d = compressDeflate(data = data);\n'
        'let raw_d = decompressDeflate(data = d.value);\n',
        encoding="utf-8",
    )
    project_toml = write_project(tmp_path, source)

    assert ez.main(["build", "--project", str(project_toml)]) == 0
    ir_file = tmp_path / "dist" / "native" / "e2e.ll"
    ir_text = ir_file.read_text(encoding="utf-8")
    assert 'declare void @"compressGzip"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
    assert 'declare void @"decompressGzip"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text
    assert 'declare void @"compressDeflate"({i1, %"Blob"}* sret({i1, %"Blob"})' in ir_text


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
        'from "std/time" import { now, timestamp, sleep, getYear, getMonth, getDay, getHour, getMinute, getSecond, add, sub, format };\n\nlet current = now();\nlet ts = timestamp();\nsleep(ms = 1);\nlet year = getYear(this = current);\nlet month = getMonth(this = current);\nlet day = getDay(this = current);\nlet hour = getHour(this = current);\nlet minute = getMinute(this = current);\nlet second = getSecond(this = current);\nadd(this = current, year = 1, month = 0, day = 0, hour = 0, minute = 0, second = 0);\nsub(this = current, year = 0, month = 1, day = 0, hour = 0, minute = 0, second = 0);\nlet formatted = format(this = current, fmt = "YYYY-MM-DD");\n',
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
    assert 'declare i32 @"getHour"' in ir_text
    assert 'declare void @"add"' in ir_text
    assert 'declare i8* @"format"' in ir_text


def test_e2e_time_wrappers_use_millisecond_clock_sleep_and_utc_fields():
    native = (ROOT / "packages" / "std" / "native" / "time.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "time.js").read_text(encoding="utf-8")
    for marker in ["/ 10000ULL", "gettimeofday", "nanosleep", "gmtime_r", "timegm", "ez_format_percent_token"]:
        assert marker in native
    for marker in ["Date.now()", "Atomics.wait", "while (Date.now() < end)", "getUTCFullYear", "setUTCFullYear", ".replace(/%Y|YYYY/g"]:
        assert marker in emcc


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
    assert 'declare %"HttpServer" @"createServer"' in ir_text
    assert 'on' in ir_text
    assert 'start' in ir_text
    assert 'stop' in ir_text


def test_e2e_std_net_http_marks_server_unsupported_and_client_supported():
    """HTTP 客户端有实现；服务端接口必须明确标记为不支持。"""
    native = (ROOT / "packages" / "std" / "native" / "net" / "http.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "net" / "http.js").read_text(encoding="utf-8")
    interface = (ROOT / "packages" / "std" / "net" / "http.ez").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8")

    assert "ez_http_fetch" in native
    assert "getaddrinfo" in native
    assert "send(sock" in native
    assert "recv(sock" in native
    assert "HTTP_SERVER_UNSUPPORTED_HANDLE" in emcc
    assert "EZ_HTTP_SERVER_UNSUPPORTED_HANDLE" in native
    assert "`createServer` 返回 `handle = 0`" in docs
    assert "HTTP 服务端当前明确不支持" in interface
    assert "return (HttpServer){0};" not in native
    assert "return 0n;" not in emcc


def test_e2e_std_net_tcp_udp_ws_support_boundaries_are_explicit():
    """TCP/UDP/WebSocket 应明确区分原生支持范围和不支持入口。"""
    tcp_native = (ROOT / "packages" / "std" / "native" / "net" / "tcp.c").read_text(encoding="utf-8")
    ws_native = (ROOT / "packages" / "std" / "native" / "net" / "ws.c").read_text(encoding="utf-8")
    tcp_emcc = (ROOT / "packages" / "std" / "emcc" / "net" / "tcp.js").read_text(encoding="utf-8")
    ws_emcc = (ROOT / "packages" / "std" / "emcc" / "net" / "ws.js").read_text(encoding="utf-8")
    tcp_interface = (ROOT / "packages" / "std" / "net" / "tcp.ez").read_text(encoding="utf-8")
    ws_interface = (ROOT / "packages" / "std" / "net" / "ws.ez").read_text(encoding="utf-8")
    api_docs = (ROOT / "docs" / "stdlib-api.md").read_text(encoding="utf-8")

    for marker in ["socket(", "connect(", "bind(", "listen(", "accept(", "recv(", "send(", "sendto(", "recvfrom("]:
        assert marker in tcp_native
    for marker in ["ws://", "Sec-WebSocket-Key", "0x82", "opcode", "0x8"]:
        assert marker in ws_native
    assert 'const char *prefix = "ws://";' in ws_native
    assert 'const char *prefix = "wss://";' not in ws_native

    for marker in ["HEAPU8[ret] = 0;", "return -1;", "return 0;"]:
        assert marker in tcp_emcc
        assert marker in ws_emcc
    assert "emcc 明确不支持" in tcp_interface
    assert "wss://、分片帧和 emcc" in ws_interface
    assert "emcc 当前明确不支持 TCP/UDP" in api_docs
    assert "`wss://`、分片帧" in api_docs


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
        'from "std/collections" import { listLen, listPush, listPop, listShift, listUnshift, listSlice };\n\nlet nums: List<I32> = [1, 2, 3];\nlistPush<I32>(list = nums, item = 4);\nlistUnshift<I32>(list = nums, item = 0);\nlet tail = listPop<I32>(list = nums);\nlet head = listShift<I32>(list = nums);\nlet part: List<I32> = listSlice<I32>(list = nums, start = 0, end = 2);\nlet n: I64 = listLen<I32>(list = part);\n',
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
        'listPush<I32>(list = nums, item = 10);\n'
        'let n: I64 = listLen<I32>(list = nums);\n',
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
        'from "std/collections" import { listSort, listFilter, listMap, listFind, listLen, dictKeys, dictValues, dictHas, dictDelete, dictLen };\n\nconst pred = (item: I32): Bool => { return item > 1; };\nconst mapper = (item: I32): I64 => { return item; };\nconst cmp = (a: I32, b: I32): I32 => { return a - b; };\nlet nums: List<I32> = [3, 1, 2];\nlistSort<I32>(list = nums, cmp = cmp);\nlet found = listFind<I32>(list = nums, pred = pred);\nlet filtered: List<I32> = listFilter<I32>(list = nums, pred = pred);\nlet mapped: List<I64> = listMap<I32, I64>(list = filtered, f = mapper);\nlet mapped_len: I64 = listLen<I64>(list = mapped);\nlet meta = { name: Str = "ez", lang: Str = "EzLang" };\nlet has_name: Bool = dictHas<Str, Str>(dict = meta, key = "name");\nlet keys: List<Str> = dictKeys<Str, Str>(dict = meta);\nlet values: List<Str> = dictValues<Str, Str>(dict = meta);\nlet removed: Bool = dictDelete<Str, Str>(dict = meta, key = "name");\nlet remaining: I64 = dictLen<Str, Str>(dict = meta);\n',
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
    assert 'declare i8* @"format"' in ir_text
    assert 'declare i8* @"b64Encode"' in ir_text
    assert 'declare i8* @"jsonStringify_I32"' in ir_text
    assert 'declare i32 @"jsonParse_I32"' in ir_text
    assert 'declare i8* @"urlEncode"' in ir_text
    assert_native_optional_return(ir_text, "urlDecode", "i8*")


def test_e2e_fmt_wrappers_implement_parse_format_encoding_json_and_msgpack():
    native = (ROOT / "packages" / "std" / "native" / "fmt.c").read_text(encoding="utf-8")
    emcc = (ROOT / "packages" / "std" / "emcc" / "fmt.js").read_text(encoding="utf-8")
    for marker in ["strtol", "strtoll", "strtod", "ez_b64_is_valid_input", "jsonStringify_Str", "jsonParse_Str", "msgpackEncode_I64", "msgpackDecode_Str", "urlEncode", "urlDecode"]:
        assert marker in native
    assert "ez_list_get(args, arg_index++)" in native
    assert "EZ_B64" in native
    for marker in ["Number.parseInt", "BigInt(text)", "isStrictBase64", "JSON.stringify", "JSON.parse", "msgpackEncode_I64", "msgpackDecode_Str", "encodeURIComponent", "decodeURIComponent"]:
        assert marker in emcc
    assert "listGet(argsPtr, index++)" in emcc


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
    assert "readFile: function (ret, path)" in fs_js
    assert "listDir: function (ret, path)" in fs_js
    assert "stat: function (ret, path)" in fs_js


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
    ]:
        assert marker in native_path
    for marker in [
        "/^[A-Za-z]:[\\\\/]/",
        "/^[\\\\/]{2}/",
        "return stringToNewUTF8('/');",
        "encodeURIComponent",
        "decodeURIComponent",
        "writePathParts",
    ]:
        assert marker in emcc_path


def test_e2e_str_wrappers_validate_utf8_bytes():
    native_str = (ROOT / "packages" / "std" / "native" / "str.c").read_text(encoding="utf-8")
    emcc_str = (ROOT / "packages" / "std" / "emcc" / "str.js").read_text(encoding="utf-8")

    for marker in [
        "ez_utf8_validate_len",
        "if (width < 0 || i + (size_t)width > len) return false;",
        "if (ch == 0xED && b1 >= 0xA0) return false;",
        "if (ch == 0xF4 && b1 > 0x8F) return false;",
    ]:
        assert marker in native_str
    for marker in [
        "function validUtf8Bytes",
        "else return false;",
        "if (width === 3 && ch === 0xed && bytes[i + 1] >= 0xa0) return false;",
        "if (width === 4 && ch === 0xf4 && bytes[i + 1] > 0x8f) return false;",
        "HEAPU8[ret] = 0;",
    ]:
        assert marker in emcc_str


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
    assert "Number.parseFloat" not in fmt_js
    assert "Number(text)" in fmt_js
    for name in ["msgpackEncode_I1", "msgpackDecode_I1", "msgpackEncode_Str", "msgpackDecode_Str", "msgpackEncode_F64", "msgpackDecode_F64"]:
        assert name in fmt_js


def test_e2e_emcc_time_wrapper_covers_named_and_percent_format_tokens():
    time_js = (ROOT / "packages" / "std" / "emcc" / "time.js").read_text(encoding="utf-8")
    for token in ["%Y|YYYY", "%m|MM", "%d|DD", "%H|HH", "%M", "%S|SS"]:
        assert token in time_js


def test_e2e_emcc_os_args_use_runtime_arguments():
    os_js = (ROOT / "packages" / "std" / "emcc" / "os.js").read_text(encoding="utf-8")
    assert "function writeStrList" in os_js
    assert "Module.arguments" in os_js
    assert "arguments_" in os_js
    assert "writeStrList(ret, runtimeArgs())" in os_js
    assert "function nodeProcess" in os_js
    assert "proc.env" in os_js
    assert "proc.pid" in os_js
    assert "return proc && proc.pid ? proc.pid | 0 : -1;" in emcc_js_function_body(os_js, "pid")


def test_e2e_emcc_io_readline_returns_empty_optional():
    """WebAssembly 目标不支持同步 stdin 时，readLine 应显式返回空可选值。"""
    io_js = (ROOT / "packages" / "std" / "emcc" / "io.js").read_text(encoding="utf-8")
    body = emcc_js_function_body(io_js, "readLine")
    assert "HEAPU8[ret] = 0;" in body
    assert "setValue(ret + 8, 0, '*');" in body


def test_e2e_emcc_stub_wrappers_are_marked_unsupported():
    """公开 wrapper 只有失败占位时，必须写明平台不支持。"""
    cases = {
        "packages/std/emcc/io.js": ["readLine"],
        "packages/std/emcc/net/http.js": ["fetch", "fetchEx", "createServer"],
        "packages/std/emcc/net/tcp.js": [
            "tcpConnect", "tcpListen", "tcpAccept", "tcpRead", "tcpWrite", "tcpClose",
            "tcpListenerClose", "udpBind", "udpSend", "udpRecv", "udpClose",
        ],
        "packages/std/emcc/net/ws.js": ["wsConnect", "wsSend", "wsRecv", "wsClose"],
        "packages/std/emcc/process.js": [
            "processExec", "processSpawn", "processWait", "processTerminate", "processCurrentPath",
        ],
    }
    unsupported_marker = re.compile(r"不支持|不可用|unsupported|unavailable", re.I)
    failure_markers = [
        "HEAPU8[ret] = 0;",
        "writeOptProcessResult(ret, false)",
        "writeOptProcess(ret, false)",
        "writeOptStr(ret, null)",
        "return -1;",
        "return 0;",
        "return 0n;",
        "HTTP_SERVER_UNSUPPORTED_HANDLE",
    ]

    for rel_path, names in cases.items():
        text = (ROOT / rel_path).read_text(encoding="utf-8")
        assert unsupported_marker.search(text), f"{rel_path} 的占位 wrapper 缺少不支持说明"
        for name in names:
            body = emcc_js_function_body(text, name)
            assert any(marker in body for marker in failure_markers), f"{rel_path}:{name} 未显式失败"


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
    assert "tcpListen: function (ret, host, port)" in tcp_js
    assert "udpBind: function (ret, host, port)" in tcp_js
    assert "wsConnect: function (ret, url)" in ws_js


def emcc_js_function_body(text: str, name: str) -> str:
    pattern = rf"{name}: function \([^)]*\) \{{(?P<body>.*?)\n\s*\}},"
    match = re.search(pattern, text, re.S)
    assert match, f"找不到 emcc JS wrapper 函数 {name}"
    return match.group("body")


def test_e2e_emcc_tcp_udp_ws_wrappers_fail_explicitly():
    """emcc 暂不支持 TCP/UDP/WS 时应显式返回失败值，不能伪装成功。"""
    tcp_js = (ROOT / "packages" / "std" / "emcc" / "net" / "tcp.js").read_text(encoding="utf-8")
    ws_js = (ROOT / "packages" / "std" / "emcc" / "net" / "ws.js").read_text(encoding="utf-8")

    for name in ["tcpConnect", "tcpListen", "tcpAccept", "tcpRead", "udpBind", "udpRecv"]:
        assert "HEAPU8[ret] = 0;" in emcc_js_function_body(tcp_js, name)
    assert "HEAPU8[ret] = 0;" in emcc_js_function_body(ws_js, "wsConnect")
    assert "HEAPU8[ret] = 0;" in emcc_js_function_body(ws_js, "wsRecv")

    for name in ["tcpWrite", "udpSend"]:
        assert "return -1;" in emcc_js_function_body(tcp_js, name)
    assert "return -1;" in emcc_js_function_body(ws_js, "wsSend")

    for name in ["tcpClose", "tcpListenerClose", "udpClose"]:
        assert "return 0;" in emcc_js_function_body(tcp_js, name)
    assert "return 0;" in emcc_js_function_body(ws_js, "wsClose")


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
        ("random", 'from "std/random" import { randomSeed, randomNextU32 };\nlet source = randomSeed(seed = 1);\nlet n = randomNextU32(this = source);\n', ["native/random.c", "emcc/random.js"]),
        ("hash", 'from "std/hash" import { crc32Str };\nlet n = crc32Str(s = "hello");\n', ["native/hash.c", "emcc/hash.js"]),
        ("platform", 'from "std/platform" import { platformOS };\nlet os_name = platformOS();\n', ["native/platform.c", "emcc/platform.js"]),
        ("uri", 'from "std/uri" import { uriNormalize };\nlet normalized = uriNormalize(url = "https://example.com/a/../b");\n', ["native/uri.c", "emcc/uri.js"]),
        ("debug", 'from "std/debug" import { debugRuntimeInfo };\nlet info = debugRuntimeInfo();\n', ["native/debug.c", "emcc/debug.js"]),
        ("log", 'from "std/log" import { logInfoMsg };\nlogInfoMsg(msg = "hello");\n', ["native/log.c", "emcc/log.js"]),
        ("regex", 'from "std/regex" import { regexCompile, regexTest };\nlet re = regexCompile(pattern = "a+", flags = 0);\nlet ok = regexTest(regex = re, input = "aaa");\n', ["native/regex.c", "emcc/regex.js"]),
        ("crypto", 'from "std/crypto" import { cryptoSha256 };\nlet data = Blob(data = "hello", size = 5);\nlet digest = cryptoSha256(data = data);\n', ["native/crypto.c", "emcc/crypto.js"]),
        ("compress", 'from "std/compress" import { compressGzip };\nlet data = Blob(data = "hello", size = 5);\nlet compressed = compressGzip(data = data);\n', ["native/compress.c", "emcc/compress.js"]),
        ("process", 'from "std/process" import { processCurrentPath };\nlet path = processCurrentPath();\n', ["native/process.c", "emcc/process.js"]),
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
