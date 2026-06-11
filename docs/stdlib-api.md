# EzLang 标准库 API 文档

标准库源码位于 [packages/std/](../packages/std/)。标准库 `.ez` 文件提供稳定 API，平台实现放在 native C wrapper 或 emcc JS wrapper 中。

## std/mem

导入：

```ez
from "std/mem" import { copy, set, allocRaw, errCancel, errTimeout, errUnsupported, errIO, errNotFound, errPermission };
```

API：

- `copy(dst: Blob, src: Blob, count: I64) -> Void`
- `set(dst: Blob, value: U8, count: I64) -> Void`
- `allocRaw(size: I64) -> Blob`
- `errCancel: I32 = 1`
- `errTimeout: I32 = 2`
- `errUnsupported: I32 = 3`
- `errIO: I32 = 4`
- `errNotFound: I32 = 5`
- `errPermission: I32 = 6`

这些函数是 compiler builtin，会 lowering 到 LLVM intrinsic 或 Arena 分配器。错误码使用正值区间；业务错误码由应用自行分配。

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

`testThrows` 调用传入函数并断言其抛出的 `Error.code` 等于 `expectedCode`；无异常时捕获到零值 `Error`，断言会失败。`testRegisterParam` 将参数化用例登记为 `name[param]`，`testCount` / `testName` 可按注册顺序检索用例名。

`ez test` 默认扫描项目 `tests/` 目录下的 `.ez` 文件，执行带 `main` 的本机测试文件；没有 `main` 的测试文件会做编译检查。测试函数名以 `test` 开头或 `_test` 结尾时计入 CLI 摘要。运行失败时，CLI 会输出测试文件路径、退出码，并把 `testRegister` / `testRegisterParam` 登记的用例名映射回源码行号，适合持续集成环境收集诊断。

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

当前提供内存/Blob 流、文件读写流与 TCP 连接流，以及进程管道流；`std/compress` 的 `*Stream` 压缩/解压 API 复用该结构。进程管道流由 `std/process` 的 `processStdin`、`processStdout` 和 `processStderr` 创建；stdin 流可写，stdout/stderr 流可读。`streamWrite` 对非法 `Blob` 输入返回 `-1`，合法空 `Blob` 写入返回 `0`；`streamCopy` 从源流当前游标开始复制到目标流，返回复制字节数，失败返回 `-1`。

## std/io

- `print(msg: Str) -> Void`
- `println(msg: Str) -> Void`
- `error(msg: Str) -> Void`
- `readLine() -> Str?`

原生桌面目标从 stdin 同步读取一行；Android/iOS 返回空可选值。emcc 在 Node 风格运行时通过 Asyncify 异步读取 fd 0，缺少 Asyncify 时回退同步读取；浏览器/Worker 无 stdin 时返回空可选值。

`print` 不追加换行，`println` 追加换行；emcc Node 风格运行时优先写入 `process.stdout.write`，无 stdout 时会暂存连续 `print` 内容并在下一次 `println` 统一输出。

## std/fs

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

平台说明：

- 空路径或非法 `Blob` 输入按接口签名返回失败值：读文件返回空 `Blob`，写入/追加返回 `false`，状态查询返回空可选值或 `false`。
- Android/iOS 相对路径映射到沙盒目录。
- emcc 默认使用 MEMFS，并在可用时挂载 `/ezdata` 到 IDBFS。

## std/os

- `args() -> Str[]`
- `env(key: Str) -> Str?`
- `setEnv(key: Str, value: Str) -> Bool`
- `cwd() -> Str`
- `exit(code: I32) -> Void`
- `pid() -> I32`
- `platform() -> Str`
- `arch() -> Str`

平台说明：native `cwd` 不可探测时返回空字符串；emcc 目标在 Node 风格运行时读取 `Module.arguments` / `process.env` / `process.cwd()` / `process.pid`；浏览器缺少对应能力时按签名返回空列表、空可选值、`false`、`/` 或 `-1`。

## std/path

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

平台说明：

- `std/path` 不访问文件系统，只按目标平台规则进行词法处理。
- Windows 目标默认使用 `\` 并识别盘符/UNC 路径；其它目标默认使用 `/`。
- emcc 使用类 POSIX 路径规则。
- `pathToFileUrl` / `pathFromFileUrl` 只做 `file://` 与路径字节的百分号编码互转；POSIX 绝对路径输出为 `file:///tmp/a`，Windows 盘符路径输出为 `file:///C:/a`。解码结果包含 NUL 字节时返回空可选值，因为 Ez `Str` 与文件路径 ABI 均不能安全表达内嵌 NUL。
- 根路径拆分保持根本身：`pathDir("/")` 返回 `/`，`pathBase("/")` 返回空字符串；Windows 盘符根 `C:/` 与 UNC 根 `//server/share` 同样保留为 `dir/root`，`base/name/ext` 为空。

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

平台说明：

- 字节索引以 UTF-8 字节为单位，字符索引按 Unicode 标量值边界遍历。
- `strFromBytes` 会校验 UTF-8；非法 `Blob`、非法 UTF-8 或包含 NUL 字节时返回空可选值。
- `strTrim` 裁剪首尾 Unicode White_Space 空白字符。
- `strToLower` / `strToUpper` 使用确定性的 Unicode simple case 映射，覆盖 ASCII、Latin-1、Latin Extended-A、Greek 和 Cyrillic 常见大小写；不执行 locale 相关规则或全文 case folding。

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

平台说明：

- Linux 原生目标会额外链接系统数学库 `libm`。
- WebAssembly 目标使用 JavaScript `Math` 与 `BigInt` 封装。
- `mathRound` 的 `.5` 按远离 0 方向取整，匹配 C `round` 语义。
- checked 运算在溢出、除零或非法转换时返回空可选值。
- `mathF64ToI32` / `mathF64ToI64` 只接受有限数，且按 C/JS 规则截断后的整数必须位于目标整数范围内。

## std/random

类型：

- `RandomSource { state: U64 }`

API：

- `randomSeed(seed: U64) -> RandomSource`
- `randomNextU32(this: RandomSource) -> U32`
- `randomNextU64(this: RandomSource) -> U64`
- `randomRangeI64(this: RandomSource, minValue: I64, maxValue: I64) -> I64`
- `randomRangeF64(this: RandomSource, minValue: F64, maxValue: F64) -> F64`
- `randomShuffleBytes(this: RandomSource, data: Blob) -> Blob`
- `randomShuffle<T>(this: RandomSource, list: List<T>) -> List<T>`
- `randomEntropy(size: I64) -> Blob?`
- `randomSecureBytes(size: I64) -> Blob?`
- `randomSecureU64() -> U64?`

平台说明：

- 确定性随机源使用稳定算法，同种子跨平台序列一致。
- 安全随机接口只使用系统/浏览器熵源，失败返回空可选值。
- `randomShuffleBytes` 与 `randomShuffle<T>` 返回新值，不修改传入数据或列表。

## std/hash

- `hashFnv1a32(data: Blob) -> U32`
- `hashFnv1a64(data: Blob) -> U64`
- `hashStrFnv1a32(s: Str) -> U32`
- `hashStrFnv1a64(s: Str) -> U64`
- `hashCombineU64(seed: U64, value: U64) -> U64`
- `crc32(data: Blob) -> U32`
- `crc32Str(s: Str) -> U32`

平台说明：

- FNV-1a 与 CRC32 均为非加密算法，不可用于安全场景。
- `hashStr*` 与 `crc32Str` 按字符串 UTF-8 字节计算。
- `hashFnv1a32` / `hashFnv1a64` / `crc32` 是非可选返回值接口；可判定的非法 `Blob` 元数据（如 `NULL`、负长度或缺少 `data`；emcc 还包括 HEAP 越界）按空输入计算。原生目标要求非空 `data` 指针对应 `size` 字节可读。

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

平台说明：

- `platformMemoryLimit` 与 `platformPageSize` 不可探测时返回 `-1`。
- WebAssembly 目标按当前 JS 环境检测 DOM、网络、加密、线程和子进程能力；Node 环境下 CPU 数、内存上限、加密和子进程能力优先读取 `os` / `crypto` / `child_process`。

## std/process

类型：

- `Command { program: Str, args: Str[], cwd: Str, env: Str[], stdin: Blob }`
- `Process { handle: I64, pid: I64 }`
- `ProcessResult { exitCode: I32, stdout: Blob, stderr: Blob, ok: Bool }`

API：

- `processExec(command: Command) -> ProcessResult?`
- `processSpawn(command: Command) -> Process?`
- `processWait(process: Process) -> ProcessResult?`
- `processTerminate(process: Process) -> Bool`
- `processStdin(process: Process) -> Stream?`
- `processStdout(process: Process) -> Stream?`
- `processStderr(process: Process) -> Stream?`
- `processCurrentPath() -> Str?`

平台说明：

- `std/process` 只用于外部程序调用，不暴露线程、线程池、互斥锁、条件变量等底层并发接口。
- `Command.stdin` 必须是合法 `Blob`；非法 `Blob` 输入会让 `processExec` / `processSpawn` 返回空可选值。
- Linux/macOS/Windows native 目标实现子进程调用；emcc 的 Node 风格运行时在 Asyncify 可用时使用 `child_process.spawn` 挂起等待，缺少 Asyncify 时回退 `child_process.spawnSync`；Android、iOS 与浏览器 WebAssembly 当前返回空可选值或 `false`。
- `processExec` 会写入 `stdin` 并捕获 `stdout`/`stderr`；`processSpawn` 默认保留旧语义，由后续 `processWait` 返回捕获的 `stdout`/`stderr`。调用 `processStdin`、`processStdout` 或 `processStderr` 会把对应管道转交给 `Stream`，转交后 `processWait` 不再自动写该 stdin 或捕获该 stdout/stderr；对应结果 Blob 为空。`Process.handle` 是标准库内部不透明句柄。emcc 的 `processSpawn` 保存已完成结果，`processStdout`/`processStderr` 可把已完成输出转成可读流，`processStdin` 返回空可选值。
- `Command.env` 使用 `KEY=VALUE` 字符串数组表示环境覆盖；`ProcessResult.ok` 表示退出码是否为 `0`。
- `flow` 内的 emcc 进程入口会通过 Asyncify 挂起后恢复；native 当前仍使用阻塞进程等待 syscall。

## std/uri

类型：

- `UriParts { scheme: Str, userInfo: Str, host: Str, port: I32, path: Str, query: Str, fragment: Str }`

API：

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

平台说明：

- `std/uri` 只做词法解析和百分号编解码，不访问网络。
- `uriNormalize` 会小写 scheme/host、折叠 path 中的 `.`/`..`，并保留显式 `//` authority 与无 authority 空 path。
- `uriQueryGet/Set` 操作不带前导 `?` 的裸 query；传入的 `key`/`value` 是未编码文本，接口会按 query 规则解码匹配、编码写回；开头、连续或尾随 `&` 产生的空项会被忽略，显式 `=` 可表示空 key 或空 value。
- 查询参数接口使用裸 query 字符串，不包含前导 `?`。
- 非法百分号转义、解码后非法 UTF-8 或包含 NUL 字节会让解码函数返回空可选值。

## std/debug

- `debugPrint(msg: Str) -> Void`
- `debugAssert(condition: Bool, msg: Str) -> Void`
- `debugCrash(msg: Str) -> Void`
- `debugLocation(file: Str, line: I32, column: I32) -> Str`
- `debugRuntimeInfo() -> Str`
- `debugHex(data: Blob) -> Str`
- `debugStack() -> Str?`

平台说明：

- `debugStack` 为尽力捕获，不支持的平台返回空可选值。
- `debugCrash` 和失败的 `debugAssert` 会终止当前程序或 WebAssembly 模块执行。

## std/log

常量：

- `logTrace: I32`
- `logDebug: I32`
- `logInfo: I32`
- `logWarn: I32`
- `logError: I32`
- `logTargetStderr: I32`
- `logTargetStdout: I32`
- `logTargetConsole: I32`
- `logTargetFile: I32`

类型：

- `LogConfig { minLevel: I32, target: I32, includeTimestamp: Bool, includeLocation: Bool }`

API：

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

原生平台支持 stderr/stdout/file 目标；Android/iOS 非文件目标同时写入系统日志入口；emcc 默认输出到 console，文件目标使用 Emscripten FS 或 Node 同步文件系统；缺少同步文件系统时 `logSetFile` 返回 `false`。

平台说明：

- 原生平台当前输出到 stdout/stderr/file；WebAssembly 输出到 console，或在 Emscripten FS/Node 环境追加写文件。
- `fields` 使用偶数位 `key, value` 字符串数组，末尾孤立 key 会被忽略。
- 运行时级别由 `LogConfig.minLevel` 或 `logSetLevel` 控制。
- 项目配置 `[log].compile_min_level` 可启用编译期级别过滤，范围为 `0..4`。
- 编译期过滤只删除静态可判定且低于阈值的标准日志调用；动态 `level` 参数继续走运行时过滤。

## std/regex

常量：

- `regexIgnoreCase: I32`
- `regexMultiline: I32`
- `regexGlobal: I32`

类型：

- `Regex { pattern: Str, flags: I32, ok: Bool }`
- `RegexMatch { start: I64, end: I64, text: Str, groups: Str[] }`

API：

- `regexCompile(pattern: Str, flags: I32) -> Regex`
- `regexIsValid(regex: Regex) -> Bool`
- `regexTest(regex: Regex, input: Str) -> Bool`
- `regexFind(regex: Regex, input: Str) -> RegexMatch?`
- `regexFindAll(regex: Regex, input: Str) -> Str[]`
- `regexReplace(regex: Regex, input: Str, replacement: Str) -> Str`
- `regexSplit(regex: Regex, input: Str) -> Str[]`

平台说明：

- POSIX 原生平台使用扩展正则，Windows 原生目标使用内置同步轻量正则 fallback，WebAssembly 使用 JavaScript `RegExp`。
- `RegexMatch.start/end` 使用 UTF-8 字节偏移；`regexReplace` 的 replacement 按字面字符串处理。
- `regexMultiline` 让 `^`/`$` 匹配每行的开始/结束；未设置时只匹配整个输入的开始/结束。`.` 默认不匹配换行符。
- Windows 内置 fallback 支持字面量、`.`、`^`/`$`、分组、`|`、字符类/范围、常用 POSIX 字符类、`?`/`*`/`+` 量词、捕获组、全局查找/替换和分割。
- 当前不是完整 PCRE 实现，复杂语法是否可用取决于底层引擎。

## std/crypto

- `cryptoSha256(data: Blob) -> Blob?`
- `cryptoSha512(data: Blob) -> Blob?`
- `cryptoHmacSha256(key: Blob, data: Blob) -> Blob?`
- `cryptoHmacSha512(key: Blob, data: Blob) -> Blob?`

平台说明：

- 优先封装成熟平台加密库；平台库不可用时使用同步 SHA-2/HMAC 回退。
- Linux native 运行时动态加载 OpenSSL `libcrypto`，不要求 OpenSSL 开发头或构建时 `-lcrypto`；macOS/iOS native 优先使用 CommonCrypto；Windows native 优先使用 BCrypt；没有可用平台库或定义 `EZ_CRYPTO_FORCE_PORTABLE` 时使用内置同步回退。
- emcc 同步 ABI 下优先使用 Node `crypto`；不可用时使用同步 JS SHA-2/HMAC 回退。

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

平台说明：

- native 目标使用系统 zlib；对应工具链需要提供 zlib 开发库。
- emcc 同步 ABI 下优先使用 Node `zlib`；浏览器同步环境当前没有同步压缩 API，一次性 API 返回空可选值，流式 API 返回 `-1`。
- 一次性 API 处理完整 `Blob`；`*Stream` API 从 `src` 当前游标读到 EOF，压缩或解压后写入 `dst`，返回写入字节数，失败返回 `-1`。

## std/time

类型：

- `Duration { ms: I64 }`

- `Duration.fromSec(s: I64) -> Duration`
- `Duration.fromMin(m: I64) -> Duration`
- `Duration.toString(this: Duration) -> Str`
- `durationToString(value: Duration) -> Str`
- `now() -> Date`
- `timestamp() -> I64`
- `sleep(ms: I64) -> Void`
- `getYear(this: Date) -> I32`
- `getMonth(this: Date) -> I32`
- `getDay(this: Date) -> I32`
- `getHour(this: Date) -> I32`
- `getMinute(this: Date) -> I32`
- `getSecond(this: Date) -> I32`
- `add(this: Date, year: I32?, month: I32?, day: I32?, hour: I32?, minute: I32?, second: I32?) -> Void`
- `sub(this: Date, year: I32?, month: I32?, day: I32?, hour: I32?, minute: I32?, second: I32?) -> Void`
- `format(this: Date, fmt: Str) -> Str`

`add` / `sub` 原地修改传入的 `Date`，不会返回新 `Date`。

`sleep` 在 `flow {}` 内是 suspend point；emcc 目标通过 Asyncify 挂起并恢复 wasm 执行栈，flow 外仍保持同步 ABI。

`format` 支持 `YYYY`、`MM`、`DD`、`HH`、`mm`、`SS` 命名占位符，以及 `%Y`、`%m`、`%d`、`%H`、`%M`、`%S`。分钟使用 `mm` 或 `%M`，月份使用 `MM` 或 `%m`。

## std/net/http

- `fetch(url: Str) -> HttpResponse?`
- `fetchEx(req: HttpRequest) -> HttpResponse?`
- `createServer(host: Str, port: I32) -> HttpServer`

类型：

- `Headers`
- `HttpRequest`
- `HttpResponse`
- `RouteHandler`
- `HttpServer`

原生桌面平台支持明文 `http://` 客户端请求、合法端口、userinfo 剥离、IPv6 字面量、基础请求/响应头和 `Transfer-Encoding: chunked` 响应体解码，也支持基础阻塞式 HTTP 服务端：`createServer` 创建句柄，`HttpServer.on` 注册精确路径路由，`start` 监听并处理连接，`stop` 关闭服务端。emcc 在浏览器/Worker 环境优先使用 `fetch` + Asyncify 挂起客户端请求，无 Asyncify 时保留同步 `XMLHttpRequest` fallback；服务端仍返回空句柄。`HttpResponse.text()` 仅在响应体是不含空字节的合法 UTF-8 时返回文本，否则返回空字符串。HTTPS、Android/iOS、无 `fetch` 且无同步 XHR 的 emcc 环境返回空可选值。

## std/net/tcp

- `tcpConnect(host: Str, port: I32) -> TcpConn?`
- `tcpListen(host: Str, port: I32) -> TcpListener?`
- `tcpAccept(listener: TcpListener) -> TcpConn?`
- `tcpRead(conn: TcpConn, maxBytes: I64) -> Blob?`
- `tcpWrite(conn: TcpConn, data: Blob) -> I64`
- `tcpClose(conn: TcpConn) -> Bool`
- `tcpListenerClose(listener: TcpListener) -> Bool`
- `udpBind(host: Str, port: I32) -> UdpSocket?`
- `udpSend(socket: UdpSocket, host: Str, port: I32, data: Blob) -> I64`
- `udpRecvFrom(socket: UdpSocket, maxBytes: I64) -> UdpPacket?`
- `udpRecv(socket: UdpSocket, maxBytes: I64) -> Blob?`
- `udpClose(socket: UdpSocket) -> Bool`

`UdpPacket` 包含 `data: Blob`、`host: Str` 和 `port: I32`；`udpRecv` 保留为只返回数据的兼容接口。原生目标提供阻塞式 TCP/UDP socket 基础能力；TCP 连接句柄可通过 `std/stream.streamFromTcpHandle` 交给通用读写和拷贝函数。端口必须在 `0..65535` 范围内，非法连接、监听或绑定端口返回空可选值，非法发送端口返回 `-1`。emcc 当前明确不支持 TCP/UDP，返回空可选值、`-1` 或 `false`，不会同步等待网络。当前接口不提供超时、TLS 或 native 事件源式 flow 挂起。

## std/net/ws

- `wsConnect(url: Str) -> WsConn?`
- `wsSend(conn: WsConn, data: Blob) -> I64`
- `wsRecv(conn: WsConn, maxBytes: I64) -> Blob?`
- `wsClose(conn: WsConn) -> Bool`

原生目标支持 `ws://` 握手校验、合法端口、userinfo 剥离、IPv6 字面量、客户端掩码、文本/二进制消息、分片帧重组和 ping/pong 自动处理；`wss://` 与 emcc WebSocket 桥接当前明确不支持，失败时返回空可选值或 `-1`。

## std/fmt

- `toString<T>(value: T) -> Str`
- `parseInt(s: Str) -> I32?`
- `parseI64(s: Str) -> I64?`
- `parseF64(s: Str) -> F64?`
- `format(template: Str, args: Str[]) -> Str`

`format` 按顺序替换 `{}` 占位符，`{{` 和 `}}` 分别输出字面 `{`、`}`；为了兼容旧代码，`%s`、`%d`、`%f` 也按顺序消费字符串参数，`%%` 输出字面 `%`。

`parseInt` / `parseI64` 只接受可选 `+`/`-` 加 ASCII 十进制数字，超出目标整数范围或包含小数、指数、十六进制前缀时返回空可选值。`parseF64` 只接受 ASCII 十进制浮点语法（可选符号、小数点、指数），拒绝 `NaN`、`Infinity` 和十六进制浮点。三者会裁剪 Unicode `White_Space` 集合中的首尾空白；`U+FEFF` 不属于该集合，不会被裁剪。

- `b64Encode(data: Blob) -> Str`
- `b64Decode(s: Str) -> Blob?`
- `jsonStringify<T>(data: T) -> Str`
- `jsonParse<T>(s: Str) -> T`
- `msgpackEncode<T>(data: T) -> Blob`
- `msgpackDecode<T>(data: Blob) -> T`
- `urlEncode(s: Str) -> Str`
- `urlDecode(s: Str) -> Str?`

JSON 与 MessagePack 当前覆盖 `I8`、`I32`、`I64`、`U8`、`U32`、`U64`、`F32`、`F64`、`Bool`、`Str` 基础类型；`jsonStringify<T>` / `jsonParse<T>` 和 `msgpackEncode<T>` / `msgpackDecode<T>` 额外支持普通用户结构体，以及顶层或结构体字段中的 `Optional<T>` / `T?`、`List<T>` / `T[]`、`Dict<K, V>`、联合类型 `A | B`。`Optional<T>` 的空值编码为 JSON `null` 或 MessagePack `nil`，非空值按内部 `T` 递归编码。`List` 可递归嵌套。`Dict<K, V>` 的键 `K` 必须是 `Str` 或基础标量类型，值类型 `V` 可递归使用这些已支持类型；`Dict<Str, V>` 的 JSON 编码为对象，非字符串键 `Dict<K, V>` 的 JSON 编码为无损条目数组 `[{"key":K,"value":V}]`；MessagePack 字典统一编码为 map，键和值都按各自类型递归编码。联合类型编码为包含 `tag` 与 `value` 两个字段的 JSON 对象或 MessagePack map；`tag` 是联合声明顺序下标，`value` 按对应分支类型递归编码，解析时要求 tag 合法且 value 符合对应分支类型。结构体字段可为这些基础类型、可选值、其它普通用户结构体、上述列表、字典或联合类型。JSON 按字段声明顺序或字典插入顺序输出对象/条目数组；MessagePack 按字段声明顺序或字典插入顺序输出 map，列表编码为 array。结构体解析要求输入字段集合与结构体声明完全一致，字段顺序可不同，缺字段、未知字段、重复字段、字段类型不合法、数组元素类型不合法或嵌套结构体不匹配都会抛 `Error(code = errIO)`；字典解析按输入对象、条目数组或 map 顺序插入，重复键以后出现的值为准。字符串解码结果包含 NUL 字节时不能作为 Ez `Str` 返回：`jsonParse<Str>` 视为解析失败，`msgpackDecode<Str>` 返回空字符串，`urlDecode` 返回空可选值。

## std/collections

`std/collections` 的公开接口由编译器内建 lowering 实现，不需要外部运行时链接。

- `listPush<T>(list: List<T>, item: T) -> Void`
- `listPop<T>(list: List<T>) -> T?`
- `listShift<T>(list: List<T>) -> T?`
- `listUnshift<T>(list: List<T>, item: T) -> Void`
- `listSort<T>(list: List<T>, cmp: (a: T, b: T) -> I32) -> Void`
- `listFilter<T>(list: List<T>, pred: (item: T) -> Bool) -> List<T>`
- `listMap<T, U>(list: List<T>, f: (item: T) -> U) -> List<U>`
- `listFind<T>(list: List<T>, pred: (item: T) -> Bool) -> T?`
- `listLen<T>(list: List<T>) -> I64`
- `listSlice<T>(list: List<T>, start: I64, end: I64) -> List<T>`
- `dictKeys<K, V>(dict: Dict<K, V>) -> K[]`
- `dictValues<K, V>(dict: Dict<K, V>) -> V[]`
- `dictHas<K, V>(dict: Dict<K, V>, key: K) -> Bool`
- `dictDelete<K, V>(dict: Dict<K, V>, key: K) -> Bool`
- `dictLen<K, V>(dict: Dict<K, V>) -> I64`

`List<T>` 支持 `listLen`、`listPush`、`listPop`、`listShift`、`listUnshift`、`listSlice`、`listSort`、`listFilter`、`listMap`、`listFind`。当前数组/List ABI 使用分页布局 `{ pages, length, capacity, page_count }`，`push/unshift/filter` 会按需扩页。

`Dict<K, V>` 支持 `dictKeys`、`dictValues`、`dictHas`、`dictDelete`、`dictLen`。当前字典实现基于现有分页键值存储做线性扫描；`Str` 键按 C 字符串内容比较，标量键按值比较。后续哈希表布局落地后可替换为更高效实现。

## std/net

`std/net/http`、`std/net/tcp`、`std/net/ws` 的接口声明和 ABI 已可编译链接。原生目标当前支持明文 `http://` 客户端请求、基础字符串请求/响应头、chunked 响应体解码、基础阻塞式 HTTP 服务端、阻塞式 TCP/UDP 基础收发，以及 `ws://` WebSocket 握手、合法端口、userinfo 剥离、IPv6 字面量、客户端掩码、分片重组和 ping/pong 自动处理。emcc HTTP 客户端在 Asyncify 可用时通过 `fetch` 挂起后恢复，TCP/UDP/WS 当前明确不支持且不会同步等待网络。HTTPS、HTTP 服务端并发 worker、WebSocket `wss://`、超时配置和 native 事件源式 flow 挂起仍待后续运行时接入；不支持的入口返回空可选值、失败值或零句柄。
