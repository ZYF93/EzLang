# EzLang 标准库 API 文档

标准库源码位于 [packages/std/](../packages/std/)。标准库 `.ez` 文件提供稳定 API，平台实现放在 native C wrapper 或 emcc JS wrapper 中。

## std/mem

导入：

```ez
from "std/mem" import { copy, set, allocRaw };
```

API：

- `copy(dst: Blob, src: Blob, count: I64) -> Void`
- `set(dst: Blob, value: U8, count: I64) -> Void`
- `allocRaw(size: I64) -> Blob`

这些函数是 compiler builtin，会 lowering 到 LLVM intrinsic 或 Arena 分配器。

## std/test

- `testAssert(condition: Bool, msg: Str) -> Void`
- `testEqualI64(actual: I64, expected: I64, msg: Str) -> Void`
- `testNotEqualI64(actual: I64, expected: I64, msg: Str) -> Void`
- `testEqualStr(actual: Str, expected: Str, msg: Str) -> Void`
- `testSkip(msg: Str) -> Void`
- `testRegister(name: Str) -> Void`
- `testPassed() -> I32`
- `testFailed() -> I32`
- `testSkipped() -> I32`
- `testReset() -> Void`

`ez test` 默认扫描项目 `tests/` 目录下的 `.ez` 文件，执行带 `main` 的本机测试文件；没有 `main` 的测试文件会做编译检查。测试函数名以 `test` 开头或 `_test` 结尾时计入 CLI 摘要。

## std/stream

- `Stream { handle: I64, kind: I32 }`
- `streamKindMemory: I32`
- `streamFromBlob(data: Blob) -> Stream?`
- `streamRead(stream: Stream, maxBytes: I64) -> Blob?`
- `streamWrite(stream: Stream, data: Blob) -> I64`
- `streamToBlob(stream: Stream) -> Blob?`
- `streamCopy(dst: Stream, src: Stream, bufferSize: I64) -> I64`
- `streamFlush(stream: Stream) -> Bool`
- `streamClose(stream: Stream) -> Bool`

当前先提供内存/Blob 流，作为文件、网络、进程管道和压缩流后续接入的稳定 ABI。`streamCopy` 从源流当前游标开始复制到目标流，返回复制字节数；失败返回 `-1`。

## std/io

- `print(msg: Str) -> Void`
- `println(msg: Str) -> Void`
- `error(msg: Str) -> Void`
- `readLine() -> Str?`

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
- `strFromBytes` 会校验 UTF-8，失败返回空可选值。
- 原生 `strToLower` / `strToUpper` 当前保证 ASCII 大小写映射；非 ASCII 字节保持不变。

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
- checked 运算在溢出、除零或非法转换时返回空可选值。

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
- `randomEntropy(size: I64) -> Blob?`
- `randomSecureBytes(size: I64) -> Blob?`
- `randomSecureU64() -> U64?`

平台说明：

- 确定性随机源使用稳定算法，同种子跨平台序列一致。
- 安全随机接口只使用系统/浏览器熵源，失败返回空可选值。
- 当前提供 `Blob` 字节洗牌；泛型数组洗牌等待集合/泛型 ABI 完善后补齐。

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
- WebAssembly 目标按当前 JS 环境检测 DOM、网络、加密、线程等能力。

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
- `processCurrentPath() -> Str?`

平台说明：

- `std/process` 只用于外部程序调用，不暴露线程、线程池、互斥锁、条件变量等底层并发接口。
- Linux/macOS native 目标实现子进程调用；Windows、Android、iOS、WebAssembly 当前返回空可选值或 `false`。
- `Command.env` 使用 `KEY=VALUE` 字符串数组表示环境覆盖；`ProcessResult.ok` 表示退出码是否为 `0`。
- `flow` 调度状态机完成前，进程等待仍是同步阻塞调用。

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
- 查询参数接口使用裸 query 字符串，不包含前导 `?`。
- 非法百分号转义会让解码函数返回空可选值。

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

类型：

- `LogConfig { minLevel: I32, target: I32, includeTimestamp: Bool, includeLocation: Bool }`

API：

- `logDefaultConfig() -> LogConfig`
- `logConfigure(config: LogConfig) -> Void`
- `logSetLevel(level: I32) -> Void`
- `logWrite(level: I32, msg: Str) -> Void`
- `logWriteFields(level: I32, msg: Str, fields: Str[]) -> Void`
- `logWriteAt(level: I32, msg: Str, file: Str, line: I32, column: I32, fields: Str[]) -> Void`
- `logTraceMsg(msg: Str) -> Void`
- `logDebugMsg(msg: Str) -> Void`
- `logInfoMsg(msg: Str) -> Void`
- `logWarnMsg(msg: Str) -> Void`
- `logErrorMsg(msg: Str) -> Void`

平台说明：

- 原生平台当前输出到 stdout/stderr；WebAssembly 输出到 console。
- `fields` 使用偶数位 `key, value` 字符串数组，末尾孤立 key 会被忽略。
- 当前实现运行时级别过滤；编译期过滤等待编译器配置传递能力完善。

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

- POSIX 原生平台使用扩展正则，WebAssembly 使用 JavaScript `RegExp`。
- Windows 原生目标当前返回不可用结果，不静默伪装成功。
- 当前不是完整 PCRE 实现，复杂语法是否可用取决于底层引擎。

## std/crypto

- `cryptoSha256(data: Blob) -> Blob?`
- `cryptoSha512(data: Blob) -> Blob?`
- `cryptoHmacSha256(key: Blob, data: Blob) -> Blob?`
- `cryptoHmacSha512(key: Blob, data: Blob) -> Blob?`

平台说明：

- 只封装成熟平台加密库，不自行实现加密算法。
- macOS/iOS native 使用 CommonCrypto；其它 native 目标当前返回空可选值。
- emcc 同步 ABI 下优先使用 Node `crypto`；浏览器 WebCrypto 暂待 flow/async ABI 完善后接入。

## std/compress

- `compressGzip(data: Blob) -> Blob?`
- `decompressGzip(data: Blob) -> Blob?`
- `compressZlib(data: Blob) -> Blob?`
- `decompressZlib(data: Blob) -> Blob?`
- `compressDeflate(data: Blob) -> Blob?`
- `decompressDeflate(data: Blob) -> Blob?`

平台说明：

- Linux/macOS native 使用系统 zlib；Windows、Android、iOS native 当前返回空可选值。
- emcc 同步 ABI 下优先使用 Node `zlib`；浏览器同步环境当前返回空可选值。
- 当前接口一次性处理完整 `Blob`；流式压缩接口等待流式 IO 抽象落地后补充。

## std/time

- `now() -> Date`
- `timestamp() -> I64`
- `sleep(ms: I64) -> Void`
- `getYear(this: Date) -> I32`
- `getMonth(this: Date) -> I32`
- `getDay(this: Date) -> I32`
- `getHour(this: Date) -> I32`
- `getMinute(this: Date) -> I32`
- `getSecond(this: Date) -> I32`
- `add(...) -> Void`
- `sub(...) -> Void`
- `format(this: Date, fmt: Str) -> Str`

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
- `udpRecv(socket: UdpSocket, maxBytes: I64) -> Blob?`
- `udpClose(socket: UdpSocket) -> Bool`

## std/net/ws

- `wsConnect(url: Str) -> WsConn?`
- `wsSend(conn: WsConn, data: Blob) -> I64`
- `wsRecv(conn: WsConn, maxBytes: I64) -> Blob?`
- `wsClose(conn: WsConn) -> Bool`

## std/fmt

- `toString<T>(value: T) -> Str`
- `parseInt(s: Str) -> I32?`
- `parseI64(s: Str) -> I64?`
- `parseF64(s: Str) -> F64?`
- `format(template: Str, args: Str[]) -> Str`
- `b64Encode(data: Blob) -> Str`
- `b64Decode(s: Str) -> Blob?`
- `jsonStringify<T>(data: T) -> Str`
- `jsonParse<T>(s: Str) -> T`
- `msgpackEncode<T>(data: T) -> Blob`
- `msgpackDecode<T>(data: Blob) -> T`
- `urlEncode(s: Str) -> Str`
- `urlDecode(s: Str) -> Str?`

## std/collections

`std/collections` 的公开接口由编译器内建 lowering 实现，不需要外部运行时链接。

`List<T>` 支持 `listLen`、`listPush`、`listPop`、`listShift`、`listUnshift`、`listSlice`、`listSort`、`listFilter`、`listMap`、`listFind`。当前数组/List ABI 使用分页布局 `{ pages, length, capacity, page_count }`，`push/unshift/filter` 会按需扩页。

`Dict<K, V>` 支持 `dictKeys`、`dictValues`、`dictHas`、`dictDelete`、`dictLen`。当前字典实现基于现有分页键值存储做线性扫描；`Str` 键按 C 字符串内容比较，标量键按值比较。后续哈希表布局落地后可替换为更高效实现。

## std/net

`std/net/http`、`std/net/tcp`、`std/net/ws` 的接口声明和 ABI 已可编译链接。原生目标当前支持明文 `http://` 客户端请求、阻塞式 TCP/UDP 基础收发，以及 `ws://` WebSocket 握手和单帧消息收发。HTTPS、HTTP 服务端、WebSocket `wss://`、分片帧、超时配置和异步 flow 挂起仍待后续运行时接入；不支持的入口返回空可选值、失败值或零句柄。
