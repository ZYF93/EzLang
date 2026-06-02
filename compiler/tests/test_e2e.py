"""编译器端到端测试"""

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "compiler" / "src"))

from cli import ez


def test_e2e_stdlib_documents_exported_declares():
    """标准库文档应覆盖源码导出的公开 declare 函数。"""
    documents = {
        "docs/stdlib-api.md": (ROOT / "docs" / "stdlib-api.md").read_text(encoding="utf-8"),
        "docs/stdlib.md": (ROOT / "docs" / "stdlib.md").read_text(encoding="utf-8"),
    }
    missing = []
    for source in sorted((ROOT / "packages" / "std").glob("**/*.ez")):
        text = source.read_text(encoding="utf-8")
        for match in re.finditer(r"export\s+declare\s+const\s+([A-Za-z_][A-Za-z0-9_]*)", text):
            name = match.group(1)
            for doc_name, docs in documents.items():
                if name not in docs:
                    missing.append(f"{doc_name} 缺少 {source.relative_to(ROOT)}:{name}")
    assert not missing, "标准库文档缺少公开接口: " + ", ".join(missing)


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
    assert 'declare {i1, i8*} @"pathFromFileUrl"' in ir_text


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
    assert 'declare {i1, i8*} @"strCharAt"' in ir_text
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
    assert 'declare {i1, i64} @"mathAddI64Checked"' in ir_text
    assert 'declare {i1, i32} @"mathF64ToI32"' in ir_text


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
    assert 'declare {i1, i64} @"randomSecureU64"' in ir_text


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
    assert 'declare {i1, i8*} @"processCurrentPath"' in ir_text


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
    assert 'declare {i1, i8*} @"uriHost"' in ir_text
    assert 'declare {i1, i32} @"uriPort"' in ir_text


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
    assert 'declare {i1, i8*} @"debugStack"' in ir_text


def test_e2e_std_log_imports_and_builds(tmp_path):
    source = tmp_path / "std_log.ez"
    source.write_text(
        'from "std/log" import { logTrace, logDebug, logInfo, logWarn, logError, logTargetStderr, LogConfig, logDefaultConfig, logConfigure, logSetLevel, logWrite, logWriteFields, logWriteAt, logInfoMsg, logWarnMsg, logErrorMsg };\n\n'
        'let cfg = logDefaultConfig();\n'
        'logConfigure(config = LogConfig(minLevel = logDebug, target = logTargetStderr, includeTimestamp = true, includeLocation = true));\n'
        'logSetLevel(level = logTrace);\n'
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
    assert 'define void @"__ezrt_flow_enter"' in ir_text
    assert 'define void @"__ezrt_flow_exit"' in ir_text
    assert 'define void @"__ezrt_sleep"' in ir_text
    assert 'define i32 @"__ezrt_race"' in ir_text
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
    assert "readFile: function (ret, path)" in fs_js
    assert "listDir: function (ret, path)" in fs_js
    assert "stat: function (ret, path)" in fs_js


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
    assert "tcpConnect: function (ret, host, port)" in tcp_js
    assert "tcpListen: function (ret, host, port)" in tcp_js
    assert "udpBind: function (ret, host, port)" in tcp_js
    assert "wsConnect: function (ret, url)" in ws_js


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
        "log.js": ["logDefaultConfig", "logWriteAt"],
        "regex.js": ["regexCompile", "regexFind"],
        "crypto.js": ["cryptoSha256", "cryptoHmacSha256"],
        "compress.js": ["compressGzip", "decompressDeflate"],
        "process.js": ["processExec", "processCurrentPath"],
        "stream.js": ["streamFromBlob", "streamRead", "streamCopy"],
        "test.js": ["testAssert", "testEqualI64", "testPassed"],
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
        ("test", 'from "std/test" import { testAssert };\ntestAssert(condition = true, msg = "ok");\n', ["native/test.c", "emcc/test.js"]),
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
