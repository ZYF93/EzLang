# EzLang Standard Library API Reference

[中文](../stdlib-api.md)

The standard library source lives in [packages/std/](../../packages/std/). Standard-library `.ez` files expose stable APIs, while platform implementations live in native C wrappers or emcc JavaScript wrappers.

This page is the per-API reference. For module boundaries, platform capability matrices, and design principles, see [Standard Library Design](stdlib.md).

## std/mem

Import:

```ez
from "std/mem" import { copy, set, allocRaw, errCancel, errTimeout, errUnsupported, errIO, errNotFound, errPermission };
```

API:

- `copy(dst: Blob, src: Blob, count: I64) -> Void`
- `set(dst: Blob, value: U8, count: I64) -> Void`
- `allocRaw(size: I64) -> Blob`
- `errCancel: I32 = 1`
- `errTimeout: I32 = 2`
- `errUnsupported: I32 = 3`
- `errIO: I32 = 4`
- `errNotFound: I32 = 5`
- `errPermission: I32 = 6`

These functions are compiler builtins that lower to LLVM intrinsics or the Arena allocator. Error codes use the positive range; application business codes are assigned by the application.

## std/test

- `testAssert(condition: Bool, msg: Str) -> Void`
- `testEqualI64(actual: I64, expected: I64, msg: Str) -> Void`
- `testNotEqualI64(actual: I64, expected: I64, msg: Str) -> Void`
- `testEqualStr(actual: Str, expected: Str, msg: Str) -> Void`
- `testSkip(msg: Str) -> Void`
- `testThrows(body: () -> Void, expectedCode: I32, msg: Str) -> Void`
- `testRegister(name: Str) -> Void`
- `testRegisterParam(name: Str, param: Str) -> Void`
- `testCount() -> I32`
- `testName(index: I32) -> Str`
- `testPassed() -> I32`
- `testFailed() -> I32`
- `testSkipped() -> I32`
- `testReset() -> Void`

`testThrows` calls the provided function and asserts that the thrown `Error.code` equals `expectedCode`. If no exception is thrown, the caught value is the zero `Error` and the assertion fails. `testRegisterParam` registers parameterized cases as `name[param]`; `testCount` / `testName` can read registered case names in registration order.

`ez test` scans `.ez` files under the project `tests/` directory by default. Native test files with `main` are compiled, linked, and executed; test files without `main` are compile-checked. Function names starting with `test` or ending with `_test` are counted in the CLI summary. On failure, the CLI prints the test file path, exit code, and maps names registered by `testRegister` / `testRegisterParam` back to source lines for CI diagnostics.

## std/stream

- `Stream { handle: I64, kind: I32 }`
- `streamKindMemory: I32`
- `streamKindFileRead: I32`
- `streamKindFileWrite: I32`
- `streamKindTcp: I32`
- `streamKindProcessStdin: I32`
- `streamKindProcessStdout: I32`
- `streamKindProcessStderr: I32`
- `streamFromBlob(data: Blob) -> Stream?`
- `streamFromTcpHandle(handle: I64) -> Stream`
- `streamOpenFileRead(path: Str) -> Stream?`
- `streamOpenFileWrite(path: Str) -> Stream?`
- `streamRead(stream: Stream, maxBytes: I64) -> Blob?`
- `streamWrite(stream: Stream, data: Blob) -> I64`
- `streamToBlob(stream: Stream) -> Blob?`
- `streamCopy(dst: Stream, src: Stream, bufferSize: I64) -> I64`
- `streamFlush(stream: Stream) -> Bool`
- `streamClose(stream: Stream) -> Bool`

Current support covers memory/Blob streams, file read/write streams, TCP connection streams, and process pipe streams. `std/compress` streaming APIs reuse the same structure. Process pipe streams are created through `std/process` functions `processStdin`, `processStdout`, and `processStderr`; stdin streams are writable, stdout/stderr streams are readable. `streamWrite` returns `-1` for invalid `Blob` input and `0` for a valid empty `Blob`. `streamCopy` copies from the source stream's current cursor to the destination and returns bytes copied, or `-1` on failure.

## std/io

- `print(msg: Str) -> Void`
- `println(msg: Str) -> Void`
- `error(msg: Str) -> Void`
- `readLine() -> Str?`

Native targets read one stdin line synchronously. Android/iOS return an empty optional when the host has no stdin or EOF has been reached. emcc reads fd 0 asynchronously through Asyncify in a Node-style runtime and falls back to synchronous reading without Asyncify; browser/Worker environments without stdin return an empty optional.

`print` does not append a newline; `println` does. emcc Node-style runtimes prefer `process.stdout.write`; when stdout is missing, continuous `print` content is buffered and flushed with the next `println`.

## std/fs

Type:

- `FileStat { size: I64, isDir: Bool, modified: I64, created: I64 }`

API:

- `readFile(path: Str) -> Blob`
- `writeFile(path: Str, content: Blob) -> Bool`
- `appendFile(path: Str, content: Blob) -> Bool`
- `removeFile(path: Str) -> Bool`
- `mkdir(path: Str) -> Bool`
- `removeDir(path: Str, recursive: Bool) -> Bool`
- `listDir(path: Str) -> Str[]`
- `exists(path: Str) -> Bool`
- `isDir(path: Str) -> Bool`
- `stat(path: Str) -> FileStat?`
- `absPath(path: Str) -> Str`

Platform notes:

- Empty paths or invalid `Blob` input return failure values according to the signature: empty `Blob` for reads, `false` for writes/appends, empty optional or `false` for stat-style queries.
- Android/iOS map relative paths to the sandbox directory.
- emcc uses MEMFS by default and mounts `/ezdata` to IDBFS when available.

## std/os

- `args() -> Str[]`
- `env(key: Str) -> Str?`
- `setEnv(key: Str, value: Str) -> Bool`
- `cwd() -> Str`
- `exit(code: I32) -> Void`
- `pid() -> I32`
- `platform() -> Str`
- `arch() -> Str`

Platform notes: native `cwd` returns an empty string if it cannot be detected. emcc Node-style runtimes read `Module.arguments`, `process.env`, `process.cwd()`, and `process.pid`; browsers return the documented fallback values, such as empty lists, empty optionals, `false`, `/`, or `-1`.

## std/path

Type:

- `PathParts { root: Str, dir: Str, base: Str, name: Str, ext: Str }`

API:

- `pathSeparator() -> Str`
- `pathJoin(parts: Str[]) -> Str`
- `pathNormalize(path: Str) -> Str`
- `pathDir(path: Str) -> Str`
- `pathBase(path: Str) -> Str`
- `pathExt(path: Str) -> Str`
- `pathIsAbs(path: Str) -> Bool`
- `pathRelative(fromPath: Str, toPath: Str) -> Str`
- `pathParse(path: Str) -> PathParts`
- `pathToFileUrl(path: Str) -> Str`
- `pathFromFileUrl(url: Str) -> Str?`

Platform notes:

- `std/path` is lexical only and does not touch the filesystem.
- Windows targets default to `\` and recognize drive letters and UNC paths. Other targets default to `/`.
- emcc uses POSIX-like path rules.
- `pathToFileUrl` / `pathFromFileUrl` only convert between `file://` URLs and path-byte percent encoding. POSIX absolute paths become `file:///tmp/a`; Windows drive paths become `file:///C:/a`. Decoded results containing NUL return an empty optional because Ez `Str` and file path ABI cannot safely express embedded NUL.
- Root splitting preserves the root: `pathDir("/")` returns `/`, while `pathBase("/")` returns an empty string. Windows drive roots `C:/` and UNC roots `//server/share` similarly keep `dir/root` while leaving `base/name/ext` empty.

## std/str

- `strByteLen(s: Str) -> I64`
- `strCharLen(s: Str) -> I64`
- `strIsEmpty(s: Str) -> Bool`
- `strIsValidUtf8(s: Str) -> Bool`
- `strSliceBytes(s: Str, start: I64, end: I64) -> Str`
- `strSliceChars(s: Str, start: I64, end: I64) -> Str`
- `strCharAt(s: Str, index: I64) -> Str?`
- `strToBytes(s: Str) -> Blob`
- `strFromBytes(data: Blob) -> Str?`
- `strEqual(a: Str, b: Str) -> Bool`
- `strContains(s: Str, needle: Str) -> Bool`
- `strStartsWith(s: Str, prefix: Str) -> Bool`
- `strEndsWith(s: Str, suffix: Str) -> Bool`
- `strIndexOf(s: Str, needle: Str) -> I64`
- `strSplit(s: Str, sep: Str) -> Str[]`
- `strJoin(parts: Str[], sep: Str) -> Str`
- `strTrim(s: Str) -> Str`
- `strReplace(s: Str, old: Str, newValue: Str) -> Str`
- `strToLower(s: Str) -> Str`
- `strToUpper(s: Str) -> Str`

Platform notes:

- Byte indexes use UTF-8 bytes; character indexes traverse Unicode scalar value boundaries.
- `strFromBytes` validates UTF-8 and returns an empty optional for invalid `Blob`, invalid UTF-8, or NUL bytes.
- `strTrim` trims Unicode White_Space at both ends.
- `strToLower` / `strToUpper` use deterministic Unicode simple case mappings covering ASCII, Latin-1, Latin Extended-A, Greek, and Cyrillic common cases. They do not apply locale-specific rules or full case folding.

## std/math

- `mathPI: F64`
- `mathE: F64`
- `mathAbsI32(value: I32) -> I32`
- `mathAbsI64(value: I64) -> I64`
- `mathMinI32(a: I32, b: I32) -> I32`
- `mathMaxI32(a: I32, b: I32) -> I32`
- `mathClampI32(value: I32, minValue: I32, maxValue: I32) -> I32`
- `mathGcdI64(a: I64, b: I64) -> I64`
- `mathLcmI64(a: I64, b: I64) -> I64`
- `mathSqrt(value: F64) -> F64`
- `mathPow(base: F64, exp: F64) -> F64`
- `mathSin(value: F64) -> F64`
- `mathCos(value: F64) -> F64`
- `mathTan(value: F64) -> F64`
- `mathLog(value: F64) -> F64`
- `mathExp(value: F64) -> F64`
- `mathFloor(value: F64) -> F64`
- `mathCeil(value: F64) -> F64`
- `mathRound(value: F64) -> F64`
- `mathIsNaN(value: F64) -> Bool`
- `mathIsInf(value: F64) -> Bool`
- `mathAddI64Checked(a: I64, b: I64) -> I64?`
- `mathSubI64Checked(a: I64, b: I64) -> I64?`
- `mathMulI64Checked(a: I64, b: I64) -> I64?`
- `mathDivI64Checked(a: I64, b: I64) -> I64?`
- `mathF64ToI32(value: F64) -> I32?`
- `mathF64ToI64(value: F64) -> I64?`
- `mathI64ToF64(value: I64) -> F64`

Platform notes:

- Linux native links the system math library `libm`.
- WebAssembly uses JavaScript `Math` and `BigInt` wrappers.
- `mathRound` rounds `.5` away from zero, matching C `round`.
- Checked operations return an empty optional on overflow, division by zero, or invalid conversion. `mathDivI64Checked` floors like the language integer `/`.
- `mathF64ToI32` / `mathF64ToI64` only accept finite values whose C/JS-truncated integer fits in the target range.

## std/random

Type:

- `RandomSource { state: U64 }`

API:

- `randomSeed(seed: U64) -> RandomSource`
- `randomNextU32(this: #RandomSource) -> U32`
- `randomNextU64(this: #RandomSource) -> U64`
- `randomRangeI64(this: #RandomSource, minValue: I64, maxValue: I64) -> I64`
- `randomRangeF64(this: #RandomSource, minValue: F64, maxValue: F64) -> F64`
- `randomShuffleBytes(this: #RandomSource, data: Blob) -> Blob`
- `randomShuffle<T>(this: #RandomSource, list: List<T>) -> List<T>`
- `randomEntropy(size: I64) -> Blob?`
- `randomSecureBytes(size: I64) -> Blob?`
- `randomSecureU64() -> U64?`

Platform notes:

- The deterministic random source uses a stable algorithm; identical seeds produce identical sequences across platforms.
- Secure random APIs use only system/browser entropy and return empty optionals on failure.
- `randomShuffleBytes` and `randomShuffle<T>` return new values and do not mutate input data or lists.

## std/hash

- `hashFnv1a32(data: Blob) -> U32`
- `hashFnv1a64(data: Blob) -> U64`
- `hashStrFnv1a32(s: Str) -> U32`
- `hashStrFnv1a64(s: Str) -> U64`
- `hashCombineU64(seed: U64, value: U64) -> U64`
- `crc32(data: Blob) -> U32`
- `crc32Str(s: Str) -> U32`

Platform notes:

- FNV-1a and CRC32 are non-cryptographic algorithms and must not be used for security.
- `hashStr*` and `crc32Str` compute over string UTF-8 bytes.
- Non-optional `Blob` hash APIs treat detectable invalid `Blob` metadata, such as NULL, negative length, missing `data`, or emcc HEAP out-of-bounds, as empty input. Native targets still require readable memory for non-empty `data` and `size`.

## std/platform

- `platformOS() -> Str`
- `platformArch() -> Str`
- `platformIsLittleEndian() -> Bool`
- `platformPointerBits() -> I32`
- `platformPageSize() -> I64`
- `platformCpuCount() -> I32`
- `platformMemoryLimit() -> I64`
- `platformHasThreads() -> Bool`
- `platformHasFileSystem() -> Bool`
- `platformHasNetwork() -> Bool`
- `platformHasCrypto() -> Bool`
- `platformHasDom() -> Bool`
- `platformHasSubprocess() -> Bool`

Platform notes:

- `platformMemoryLimit` and `platformPageSize` return `-1` if unavailable.
- WebAssembly detects DOM, network, crypto, thread, and subprocess capability from the current JS environment. In Node, CPU count, memory limit, crypto, and subprocess capability prefer `os`, `crypto`, and `child_process`.

## std/process

Types:

- `Command { program: Str, args: Str[], cwd: Str, env: Str[], stdin: Blob }`
- `Process { handle: I64, pid: I64 }`
- `ProcessResult { exitCode: I32, stdout: Blob, stderr: Blob, ok: Bool }`

API:

- `processExec(command: Command) -> ProcessResult?`
- `processSpawn(command: Command) -> Process?`
- `processWait(process: Process) -> ProcessResult?`
- `processTerminate(process: Process) -> Bool`
- `processStdin(process: Process) -> Stream?`
- `processStdout(process: Process) -> Stream?`
- `processStderr(process: Process) -> Stream?`
- `processCurrentPath() -> Str?`

Platform notes:

- `std/process` is only for invoking external programs; it does not expose threads, thread pools, mutexes, condition variables, or other low-level concurrency APIs.
- `Command.stdin` must be a valid `Blob`; invalid input makes `processExec` / `processSpawn` return empty optionals.
- Linux/macOS/Windows/Android native targets implement subprocess calls. emcc Node-style runtime uses `child_process.spawn` with Asyncify to preserve live subprocesses and pipes; without Asyncify it falls back to `child_process.spawnSync` and stores completed results. iOS and browser WebAssembly return empty optionals or `false`.
- `processExec` writes stdin and captures stdout/stderr. `processSpawn` keeps the legacy behavior where `processWait` captures stdout/stderr later. Calling `processStdin`, `processStdout`, or `processStderr` transfers the pipe to `Stream`; after transfer, `processWait` no longer writes that stdin or captures that stdout/stderr, and the corresponding result `Blob` is empty. `Process.handle` is an opaque standard-library internal handle. Without Asyncify, emcc's synchronous fallback can still expose completed stdout/stderr as readable streams, but stdin is unavailable.
- `Command.env` uses `KEY=VALUE` strings for environment overrides. `ProcessResult.ok` means exit code `0`.
- emcc process APIs inside Flow suspend and resume through Asyncify; native targets currently use blocking process wait syscalls.

## std/uri

Type:

- `UriParts { scheme: Str, userInfo: Str, host: Str, port: I32, path: Str, query: Str, fragment: Str }`

API:

- `uriParse(url: Str) -> UriParts?`
- `uriBuild(parts: UriParts) -> Str`
- `uriNormalize(url: Str) -> Str`
- `uriScheme(url: Str) -> Str?`
- `uriHost(url: Str) -> Str?`
- `uriPort(url: Str) -> I32?`
- `uriPath(url: Str) -> Str`
- `uriQuery(url: Str) -> Str?`
- `uriFragment(url: Str) -> Str?`
- `uriEncodeQuery(s: Str) -> Str`
- `uriDecodeQuery(s: Str) -> Str?`
- `uriEncodePathSegment(s: Str) -> Str`
- `uriDecodePathSegment(s: Str) -> Str?`
- `uriQueryGet(query: Str, key: Str) -> Str?`
- `uriQuerySet(query: Str, key: Str, value: Str) -> Str`

Platform notes:

- `std/uri` is lexical only and does not access the network.
- `uriNormalize` lowercases scheme/host, folds `.`/`..` in the path, and preserves explicit `//` authority and authority-less empty paths.
- `uriQueryGet/Set` operate on bare query strings without a leading `?`. `key` and `value` are unencoded text; APIs decode for matching and encode on write. Empty entries from leading, repeated, or trailing `&` are ignored. Explicit `=` can represent an empty key or empty value.
- Invalid percent escapes, invalid UTF-8 after decoding, or decoded NUL bytes return empty optionals.

## std/debug

- `debugPrint(msg: Str) -> Void`
- `debugAssert(condition: Bool, msg: Str) -> Void`
- `debugCrash(msg: Str) -> Void`
- `debugLocation(file: Str, line: I32, column: I32) -> Str`
- `debugRuntimeInfo() -> Str`
- `debugHex(data: Blob) -> Str`
- `debugStack() -> Str?`

Platform notes:

- `debugStack` is best effort. Desktop platforms prefer symbolized frames; Android/iOS use `_Unwind_Backtrace` address frames; unsupported platforms return empty optionals.
- `debugCrash` and failed `debugAssert` terminate the current program or WebAssembly module.

## std/log

Constants:

- `logTrace: I32`
- `logDebug: I32`
- `logInfo: I32`
- `logWarn: I32`
- `logError: I32`
- `logTargetStderr: I32`
- `logTargetStdout: I32`
- `logTargetConsole: I32`
- `logTargetFile: I32`

Type:

- `LogConfig { minLevel: I32, target: I32, includeTimestamp: Bool, includeLocation: Bool }`

API:

- `logDefaultConfig() -> LogConfig`
- `logConfigure(config: LogConfig) -> Void`
- `logSetLevel(level: I32) -> Void`
- `logSetFile(path: Str) -> Bool`
- `logWrite(level: I32, msg: Str) -> Void`
- `logWriteFields(level: I32, msg: Str, fields: Str[]) -> Void`
- `logWriteAt(level: I32, msg: Str, file: Str, line: I32, column: I32, fields: Str[]) -> Void`
- `logTraceMsg(msg: Str) -> Void`
- `logDebugMsg(msg: Str) -> Void`
- `logInfoMsg(msg: Str) -> Void`
- `logWarnMsg(msg: Str) -> Void`
- `logErrorMsg(msg: Str) -> Void`

Native platforms support stderr/stdout/file targets. Android/iOS non-file targets also write to the system log. emcc defaults to console output; file targets use Emscripten FS or Node's synchronous filesystem. If no synchronous filesystem is available, `logSetFile` returns `false`.

Platform notes:

- `fields` uses an even-position `key, value` string array; a trailing lone key is ignored.
- Runtime level is controlled by `LogConfig.minLevel` or `logSetLevel`.
- Project configuration `[log].compile_min_level` enables compile-time level filtering over range `0..4`.
- Compile-time filtering only removes statically known standard log calls below the threshold; dynamic `level` parameters remain runtime-filtered.

## std/regex

Constants:

- `regexIgnoreCase: I32`
- `regexMultiline: I32`
- `regexGlobal: I32`

Types:

- `Regex { pattern: Str, flags: I32, ok: Bool }`
- `RegexMatch { start: I64, end: I64, text: Str, groups: Str[] }`

API:

- `regexCompile(pattern: Str, flags: I32) -> Regex`
- `regexIsValid(regex: Regex) -> Bool`
- `regexTest(regex: Regex, input: Str) -> Bool`
- `regexFind(regex: Regex, input: Str) -> RegexMatch?`
- `regexFindAll(regex: Regex, input: Str) -> Str[]`
- `regexReplace(regex: Regex, input: Str, replacement: Str) -> Str`
- `regexSplit(regex: Regex, input: Str) -> Str[]`

Platform notes:

- POSIX native platforms use extended regex; Windows native uses an internal synchronous lightweight fallback; WebAssembly uses JavaScript `RegExp`.
- `RegexMatch.start/end` are UTF-8 byte offsets. `regexReplace` treats replacement as a literal string.
- `regexMultiline` lets `^`/`$` match each line start/end; otherwise they match only the whole input start/end. `.` does not match newline by default.
- The Windows fallback supports literals, `.`, `^`/`$`, groups, `|`, character classes/ranges, common POSIX classes, `?`/`*`/`+` quantifiers, capture groups, global find/replace, and split.
- To avoid catastrophic backtracking, `regexCompile` rejects patterns longer than 4096 bytes, more than 64 capture groups, bounded repeats above 1024, nested variable repeats, and variable repeats applied to branching groups.
- This is not a complete PCRE implementation; complex syntax depends on the underlying platform engine.

## std/crypto

- `cryptoSha256(data: Blob) -> Blob?`
- `cryptoSha512(data: Blob) -> Blob?`
- `cryptoHmacSha256(key: Blob, data: Blob) -> Blob?`
- `cryptoHmacSha512(key: Blob, data: Blob) -> Blob?`

Platform notes:

- The module prefers mature platform crypto libraries and falls back to synchronous SHA-2/HMAC when unavailable.
- Linux native dynamically loads OpenSSL `libcrypto`; it does not require OpenSSL headers or build-time `-lcrypto`. macOS/iOS prefer CommonCrypto. Windows prefers BCrypt. If no platform library is available or `EZ_CRYPTO_FORCE_PORTABLE` is defined, the built-in synchronous fallback is used.
- emcc's synchronous ABI prefers Node `crypto` and falls back to synchronous JS SHA-2/HMAC when unavailable.

## std/compress

- `compressGzip(data: Blob) -> Blob?`
- `decompressGzip(data: Blob) -> Blob?`
- `compressZlib(data: Blob) -> Blob?`
- `decompressZlib(data: Blob) -> Blob?`
- `compressDeflate(data: Blob) -> Blob?`
- `decompressDeflate(data: Blob) -> Blob?`
- `compressGzipStream(dst: Stream, src: Stream, bufferSize: I64) -> I64`
- `decompressGzipStream(dst: Stream, src: Stream, bufferSize: I64) -> I64`
- `compressZlibStream(dst: Stream, src: Stream, bufferSize: I64) -> I64`
- `decompressZlibStream(dst: Stream, src: Stream, bufferSize: I64) -> I64`
- `compressDeflateStream(dst: Stream, src: Stream, bufferSize: I64) -> I64`
- `decompressDeflateStream(dst: Stream, src: Stream, bufferSize: I64) -> I64`

Platform notes:

- Native targets use system zlib; the toolchain must provide zlib development libraries.
- emcc prefers Node `zlib`. In browser/Worker environments, when Asyncify is available, `CompressionStream` / `DecompressionStream` support gzip, zlib, and raw deflate for both one-shot and streaming APIs. Missing Web APIs or Asyncify return empty optionals or `-1`.
- One-shot APIs process a complete `Blob`; `*Stream` APIs read from the current cursor of `src` to EOF, write compressed/decompressed data to `dst`, and return bytes written or `-1` on failure.

## std/time

Type:

- `Duration { ms: I64 }`

API:

- `Duration.fromSec(s: I64) -> Duration`
- `Duration.fromMin(m: I64) -> Duration`
- `Duration.toString(this: #Duration) -> Str`
- `durationToString(value: Duration) -> Str`
- `now() -> Date`
- `timestamp() -> I64`
- `sleep(ms: I64) -> Void`
- `getYear(this: #Date) -> I32`
- `getMonth(this: #Date) -> I32`
- `getDay(this: #Date) -> I32`
- `getHour(this: #Date) -> I32`
- `getMinute(this: #Date) -> I32`
- `getSecond(this: #Date) -> I32`
- `add(this: #Date, year: I32?, month: I32?, day: I32?, hour: I32?, minute: I32?, second: I32?) -> Void`
- `sub(this: #Date, year: I32?, month: I32?, day: I32?, hour: I32?, minute: I32?, second: I32?) -> Void`
- `format(this: #Date, fmt: Str) -> Str`

`add` / `sub` mutate the passed `Date` in place and do not return a new `Date`.

`sleep` is a suspend point inside `flow {}`. emcc suspends and resumes the wasm stack with Asyncify, while outside Flow it keeps a synchronous ABI.

`format` supports named placeholders `YYYY`, `MM`, `DD`, `HH`, `mm`, `SS`, and `strftime`-style `%Y`, `%m`, `%d`, `%H`, `%M`, `%S`. Minutes use `mm` or `%M`; months use `MM` or `%m`.

## std/net/http

- `fetch(url: Str) -> HttpResponse?`
- `fetchEx(req: HttpRequest) -> HttpResponse?`
- `createServer(host: Str, port: I32) -> HttpServer`

Types:

- `Headers = { [key: Str]: Str }`
- `HttpRequest { method: Str, url: Str, headers: Headers, body: Blob? }`
- `HttpResponse { status: I32, headers: Headers, body: Blob }`
- `RouteHandler = (req: HttpRequest) -> HttpResponse`
- `HttpServer { handle: I64 }`

Native platforms support `http://` client requests, valid ports, userinfo stripping, IPv6 literals, basic request/response headers, and `Transfer-Encoding: chunked` response decoding. Linux/macOS support `https://` when the OpenSSL TLS backend can be dynamically loaded, system CAs are available, and certificate chain plus hostname verification pass; otherwise APIs return empty optionals. Native platforms also support a basic HTTP server: `createServer` creates a handle, `HttpServer.on` registers exact path routes, `start` listens and dispatches accepted connections to workers, and `stop` closes the server. emcc browser/Worker clients prefer `fetch` + Asyncify, with synchronous `XMLHttpRequest` fallback without Asyncify. Node-style emcc runtime supports a basic HTTP server through `http.createServer` + Asyncify; browser/Worker server creation returns a zero handle. `HttpResponse.text()` returns text only when the body is valid UTF-8 without NUL bytes; otherwise it returns an empty string. emcc environments without `fetch` or synchronous XHR return empty optionals.

## std/net/tcp

- `tcpConnect(host: Str, port: I32) -> TcpConn?`
- `tcpConnectTimeout(host: Str, port: I32, timeoutMs: I32) -> TcpConn?`
- `tcpTlsConnect(host: Str, port: I32) -> TcpTlsConn?`
- `tcpTlsRead(conn: TcpTlsConn, maxBytes: I64) -> Blob?`
- `tcpTlsWrite(conn: TcpTlsConn, data: Blob) -> I64`
- `tcpTlsClose(conn: TcpTlsConn) -> Bool`
- `tcpListen(host: Str, port: I32) -> TcpListener?`
- `tcpAccept(listener: TcpListener) -> TcpConn?`
- `tcpAcceptTimeout(listener: TcpListener, timeoutMs: I32) -> TcpConn?`
- `tcpRead(conn: TcpConn, maxBytes: I64) -> Blob?`
- `tcpReadTimeout(conn: TcpConn, maxBytes: I64, timeoutMs: I32) -> Blob?`
- `tcpWrite(conn: TcpConn, data: Blob) -> I64`
- `tcpWriteTimeout(conn: TcpConn, data: Blob, timeoutMs: I32) -> I64`
- `tcpClose(conn: TcpConn) -> Bool`
- `tcpListenerClose(listener: TcpListener) -> Bool`
- `udpBind(host: Str, port: I32) -> UdpSocket?`
- `udpSend(socket: UdpSocket, host: Str, port: I32, data: Blob) -> I64`
- `udpSendTimeout(socket: UdpSocket, host: Str, port: I32, data: Blob, timeoutMs: I32) -> I64`
- `udpRecvFrom(socket: UdpSocket, maxBytes: I64) -> UdpPacket?`
- `udpRecvFromTimeout(socket: UdpSocket, maxBytes: I64, timeoutMs: I32) -> UdpPacket?`
- `udpRecv(socket: UdpSocket, maxBytes: I64) -> Blob?`
- `udpRecvTimeout(socket: UdpSocket, maxBytes: I64, timeoutMs: I32) -> Blob?`
- `udpClose(socket: UdpSocket) -> Bool`

`UdpPacket` contains `data: Blob`, `host: Str`, and `port: I32`; `udpRecv` remains as a compatibility API returning only data. Native targets provide blocking TCP/UDP socket basics and one-shot `timeoutMs` variants for connect/accept/read/write/send/recv. Linux/macOS support TCP TLS clients when OpenSSL TLS can be dynamically loaded, system CAs are available, and certificate/hostname checks pass. TLS connections use separate `TcpTlsConn` handles and are not disguised as raw `TcpConn`. emcc Node-style runtime uses `net` / `tls` / `dgram` + Asyncify for TCP/TLS/UDP connections, listening, reading, writing, UDP send/receive, and close. Browser/Worker environments fail explicitly. Raw TCP handles can be converted to generic streams through `std/stream.streamFromTcpHandle`. Ports must be in `0..65535`; invalid connect/listen/bind ports return empty optionals, invalid send ports return `-1`. `timeoutMs < 0` is invalid, and `timeoutMs == 0` means poll once without waiting. The current API does not provide native event-source Flow suspension.

## std/net/ws

- `wsConnect(url: Str) -> WsConn?`
- `wsSend(conn: WsConn, data: Blob) -> I64`
- `wsRecv(conn: WsConn, maxBytes: I64) -> Blob?`
- `wsClose(conn: WsConn) -> Bool`

Native targets support `ws://` handshake validation, valid ports, userinfo stripping, IPv6 literals, client masking, text/binary messages, fragmented frame reassembly, and automatic ping/pong handling. Linux/macOS support `wss://` when the OpenSSL TLS backend can be loaded and certificate/hostname verification passes; otherwise they return empty optionals. emcc browser/Worker runtime supports `ws://` / `wss://` client connect, binary send, receive, and close through WebSocket + Asyncify. Missing WebSocket or Asyncify returns empty optionals or `-1`.

## std/fmt

- `toString<T>(value: T) -> Str`
- `parseInt(s: Str) -> I32?`
- `parseI64(s: Str) -> I64?`
- `parseF64(s: Str) -> F64?`
- `format(template: Str, args: Str[]) -> Str`

`format` replaces `{}` placeholders in order. `{{` and `}}` output literal braces. For compatibility with older code, `%s`, `%d`, and `%f` also consume string arguments in order, and `%%` outputs a literal `%`.

`parseInt` / `parseI64` accept only optional `+`/`-` followed by ASCII decimal digits. Out-of-range input, decimals, exponents, or hexadecimal prefixes return empty optionals. `parseF64` accepts only ASCII decimal float syntax with optional sign, decimal point, and exponent; it rejects `NaN`, `Infinity`, and hexadecimal floats. All three trim Unicode White_Space at both ends; `U+FEFF` is not part of that set and is not trimmed.

- `b64Encode(data: Blob) -> Str`
- `b64Decode(s: Str) -> Blob?`
- `jsonStringify<T>(data: T) -> Str`
- `jsonParse<T>(s: Str) -> T`
- `msgpackEncode<T>(data: T) -> Blob`
- `msgpackDecode<T>(data: Blob) -> T`
- `urlEncode(s: Str) -> Str`
- `urlDecode(s: Str) -> Str?`

JSON and MessagePack currently cover primitive types `I8`, `I32`, `I64`, `U8`, `U32`, `U64`, `F32`, `F64`, `Bool`, and `Str`. `jsonStringify<T>` / `jsonParse<T>` and `msgpackEncode<T>` / `msgpackDecode<T>` also support ordinary user structs, plus top-level or field-level `Optional<T>` / `T?`, `List<T>` / `T[]`, `Dict<K, V>`, and union types `A | B`. Optional empty values encode as JSON `null` or MessagePack `nil`; non-empty values recursively encode the inner `T`. Lists can nest recursively. `Dict<K, V>` keys must be `Str` or primitive scalar types; values can recursively use supported types. JSON encodes `Dict<Str, V>` as objects and non-string-key dictionaries as lossless entry arrays `[ {"key": K, "value": V} ]`; MessagePack dictionaries encode as maps. Union values encode as objects/maps with `tag` and `value`; `tag` is the union declaration index and `value` recursively encodes the branch payload. Struct parsing requires exactly the declared field set; missing, unknown, duplicate, invalid-type, invalid array element, or mismatched nested struct fields throw `Error(code = errIO)`. Dictionary parsing inserts in input order, and repeated keys keep the last value. Decoded strings containing NUL cannot be returned as Ez `Str`: `jsonParse<Str>` fails, `msgpackDecode<Str>` returns an empty string, and `urlDecode` returns an empty optional.

## std/collections

`List<T>`, `T[]`, and `Dict<K, V>` are compiler-predeclared built-in types. `std/collections` exposes collection extension APIs through standard-library declarations. These generic functions are monomorphized and lowered by the compiler and do not require external C/JS runtime linking. The first parameter of each extension function is the weak-reference `this`.

- `listPush<T>(this: #List<T>, item: T) -> Void`
- `listPop<T>(this: #List<T>) -> T?`
- `listShift<T>(this: #List<T>) -> T?`
- `listUnshift<T>(this: #List<T>, item: T) -> Void`
- `listSort<T>(this: #List<T>, cmp: (a: T, b: T) -> I32) -> Void`
- `listFilter<T>(this: #List<T>, pred: (item: T) -> Bool) -> List<T>`
- `listMap<T, U>(this: #List<T>, f: (item: T) -> U) -> List<U>`
- `listFind<T>(this: #List<T>, pred: (item: T) -> Bool) -> T?`
- `listLen<T>(this: #List<T>) -> I64`
- `listSlice<T>(this: #List<T>, start: I64, end: I64) -> List<T>`
- `dictKeys<K, V>(this: #Dict<K, V>) -> K[]`
- `dictValues<K, V>(this: #Dict<K, V>) -> V[]`
- `dictHas<K, V>(this: #Dict<K, V>, key: K) -> Bool`
- `dictDelete<K, V>(this: #Dict<K, V>, key: K) -> Bool`
- `dictLen<K, V>(this: #Dict<K, V>) -> I64`

Prefer object-method sugar: `nums.push(item = 4)`, `nums.len()`, `meta.has(key = "name")`. Explicit calls use `this = #nums` / `this = #meta`.

`List<T>` supports `listLen`, `listPush`, `listPop`, `listShift`, `listUnshift`, `listSlice`, `listSort`, `listFilter`, `listMap`, and `listFind`. The current array/List ABI uses paged layout `{ pages, length, capacity, page_count }`; `push`, `unshift`, and `filter` expand pages as needed.

`Dict<K, V>` supports `dictKeys`, `dictValues`, `dictHas`, `dictDelete`, and `dictLen`. Dictionaries keep a paged key-value storage ABI for native/JS standard-library boundaries. Compiler-built dictionaries maintain open-addressing hash indexes for `Str` and primitive scalar keys; lookup, update, and delete use that hash index, while `dictKeys` / `dictValues` still return insertion order. Compatible dictionaries returned by external standard-library code without the internal hash marker automatically fall back to paged linear scanning.

## std/net

The declarations and ABI for `std/net/http`, `std/net/tcp`, and `std/net/ws` can be compiled and linked. Native targets currently support `http://` clients, basic string request/response headers, chunked response body decoding, a per-connection worker HTTP server, blocking TCP/UDP basics, one-shot TCP/UDP timeout variants, TCP TLS clients, and `ws://` WebSocket handshake, valid ports, userinfo stripping, IPv6 literals, client masking, frame reassembly, and automatic ping/pong. Linux/macOS support `https://` HTTP clients, TCP TLS clients, and `wss://` WebSocket clients when OpenSSL TLS can be dynamically loaded, system CAs are available, and certificate chain plus hostname verification pass. emcc HTTP clients use `fetch` + Asyncify when available; Node-style runtime supports a basic HTTP server through `http.createServer` + Asyncify. TCP/TLS/UDP use `net` / `tls` / `dgram` + Asyncify in Node-style runtimes. WebSocket clients use browser/Worker WebSocket + Asyncify. Browser-native TCP/UDP and native event-source Flow suspension remain future runtime work. Unsupported entries return empty optionals, failure values, or zero handles.
