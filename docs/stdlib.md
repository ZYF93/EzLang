# EzLang 标准库设计文档 (Standard Library Design)

EzLang 标准库采用"统一上层 API，平台感知底层实现"的设计策略。编译器根据 `project.toml` 中定义的目标平台（target）动态切换底层链接库与系统调用。所有阻塞 I/O 操作均遵循 Flow 并发语义：在 `flow {}` 内自动转为非阻塞调度点，在 `flow` 外等价于同步阻塞。

---

## 0. 设计理念

1. **统一 API**：无论编译目标为何，用户均调用相同的标准库接口。
2. **平台感知**：底层实现根据 `os` 和 `arch` 自动选择 syscall 或平台库函数。
3. **安全降级**：某平台不支持的 API 必须按接口约定显式失败，例如返回空可选值、`false`、`errUnsupported` 或诊断错误，并在文档中明确标注平台限制，不做静默成功。
4. **Flow 优先**：所有阻塞 I/O 均为 `flow` suspend point；在 `flow` 外等价于同步阻塞。
5. **UI 解耦**：移动端 UI 能力由独立包提供，标准库不绑定任何 UI 框架。

---

## 编译目标平台

| 目标      | 平台                     | 底层实现                      |
| --------- | ------------------------ | ----------------------------- |
| `windows` | Windows x86/x64/arm64    | Win32 API + MSVCRT            |
| `macos`   | macOS x64/arm64          | libc + Darwin syscall         |
| `linux`   | Linux x64/arm64          | libc + Linux syscall          |
| `android` | Android arm64/x86_64     | Bionic libc + Android NDK     |
| `ios`     | iOS arm64                | Apple libc + XNU syscall      |
| `emcc`    | WebAssembly (Emscripten) | Emscripten libc + JS bindings |

> **移动端 UI**：Android UI 由独立的 `ez-android-ui` 包提供；iOS UI 由 `ez-ios-ui` 包提供。标准库仅覆盖系统能力，不包含 UI。

---

## 标准库能力矩阵

| 模块 | 能力类型 | Linux/macOS | Windows | Android/iOS | WebAssembly | freestanding |
| ---- | -------- | ----------- | ------- | ----------- | ----------- | ------------ |
| `std/mem` | compiler builtin | 完整 | 完整 | 完整 | 完整 | 底层原语 |
| `std/io` | 原生/JS 封装 | stdout/stderr/stdin | stdout/stderr/stdin | 系统日志；stdin 空可选值 | console；stdin 空可选值 | 不支持 |
| `std/fs` | 原生/JS 封装 | 文件系统 | 基础文件系统 | 沙盒路径 | MEMFS/IDBFS | 不支持 |
| `std/os` | 原生/JS 封装 | 进程/环境/平台 | 进程/环境/平台 | 沙盒环境；部分信息 | Node 环境优先；浏览器显式失败 | 不支持 |
| `std/time` | 原生/JS 封装 | 毫秒时间/日期/睡眠 | 毫秒时间/日期/睡眠 | 毫秒时间/日期/睡眠 | 毫秒时间/日期/同步睡眠 | 不支持 |
| `std/fmt` | 纯逻辑 + 封装 | 完整 | 完整 | 完整 | 完整 | 不支持 |
| `std/collections` | compiler builtin | 完整 | 完整 | 完整 | 完整 | 不支持 |
| `std/net/http` | 原生/JS 封装 | 明文 HTTP 客户端；服务端不支持 | 明文 HTTP 客户端；服务端不支持 | 显式失败 | 同步 ABI 显式失败 | 不支持 |
| `std/net/tcp` | 原生/JS 封装 | TCP/UDP 阻塞式 socket | TCP/UDP 阻塞式 socket | TCP/UDP 阻塞式 socket | 显式失败 | 不支持 |
| `std/net/ws` | 原生/JS 封装 | 基础 ws 单帧客户端 | 基础 ws 单帧客户端 | 基础 ws 单帧客户端 | 显式失败 | 不支持 |
| `std/str` | 纯逻辑 + 封装 | UTF-8 基础操作 | UTF-8 基础操作 | UTF-8 基础操作 | UTF-8 基础操作 | 不支持 |
| `std/math` | 原生/JS 封装 | libm/checked 运算 | 系统数学库/checked 运算 | 系统数学库/checked 运算 | JS Math/BigInt | 不支持 |
| `std/path` | 纯逻辑封装 | POSIX/Darwin 路径 | Windows 路径 | 平台路径规则 | POSIX 风格路径 | 不支持 |
| `std/random` | 原生/JS 封装 | 确定性源 + 系统熵 | 确定性源 + 系统熵 | 确定性源 + 系统熵 | 确定性源 + Web/Node 熵 | 不支持 |
| `std/hash` | 纯逻辑封装 | FNV/CRC32 | FNV/CRC32 | FNV/CRC32 | FNV/CRC32 | 不支持 |
| `std/platform` | 原生/JS 封装 | 平台能力查询 | 平台能力查询 | 平台能力查询 | JS 环境能力查询 | 不支持 |
| `std/process` | 原生封装 | 子进程 exec/spawn/wait | 子进程 exec/spawn/wait | 显式失败 | 显式失败 | 不支持 |
| `std/uri` | 纯逻辑封装 | URL 解析/构造/编码 | URL 解析/构造/编码 | URL 解析/构造/编码 | URL 解析/构造/编码 | 不支持 |
| `std/debug` | 原生/JS 封装 | 诊断/堆栈尽力捕获 | 诊断/堆栈尽力捕获 | 诊断/堆栈尽力捕获 | console/Error stack | 不支持 |
| `std/log` | std/io + std/time | stdout/stderr | stdout/stderr | 系统日志入口 | console | 不支持 |
| `std/stream` | 运行时 ABI 封装 | 内存/Blob、文件流 | 内存/Blob、文件流 | 内存/Blob、文件流 | 内存/Blob、文件流 | 不支持 |
| `std/test` | 运行时测试封装 | `ez test` 本机执行 | 编译检查为主 | 编译检查为主 | 编译检查为主 | 不支持 |
| `std/regex` | 原生/JS 封装 | POSIX 扩展正则 | 显式失败 | POSIX/平台正则尽力支持 | JS RegExp | 不支持 |
| `std/crypto` | 平台加密库封装 | macOS CommonCrypto；Linux 显式失败 | 显式失败 | iOS CommonCrypto；Android 显式失败 | Node crypto；浏览器异步能力暂不接入 | 不支持 |
| `std/compress` | 平台压缩库封装 | zlib/gzip/deflate | 显式失败 | 显式失败 | Node zlib；浏览器同步 ABI 显式失败 | 不支持 |

能力类型说明：`compiler builtin` 由编译器 lowering，不依赖外部符号；`纯逻辑封装` 不访问系统资源；`原生/JS 封装` 通过 C 或 Emscripten JS ABI 访问平台能力；`运行时 ABI 封装` 固定语言运行时数据布局，后续可接入文件、网络、进程等具体后端。

内存规则：返回 `Str`、`Blob`、列表或字典的封装函数由当前平台封装分配结果内存，语言侧按 Arena/运行时 ABI 接管生命周期；一次性 `Blob` API 不承诺零拷贝。错误规则：不支持的平台必须返回空可选值、`false`、`-1`、零句柄或 `errUnsupported` 诊断，不允许伪装成功。Flow 规则：阻塞 I/O 在 `flow {}` 内是挂起点的语义目标；当前未接入完整调度的封装保持同步 ABI，并在平台说明中标注限制。

---

## 0. 外部 ABI 链接 (`extern`)

标准库通过 `extern` 语法实现跨平台底层库链接，无需用户手动配置。

```ez
// 标准库内部示例
extern "libcurl.a" for linux
extern "libcurl.dylib" for macos
extern "libcurl.lib" for windows

// 声明 CURL 库函数
declare const curl_easy_init: () => Blob
declare const curl_easy_perform: (handle: Blob) => I32
```

用户代码可直接 `import` 标准库 API，编译器根据目标平台自动选择正确的 `extern` 库和 `declare` 声明。

---

## 1. 内存与错误处理 (`std/mem`)

```ez
declare const copy:     (dst: Blob, src: Blob, count: I64) => Void  // 封装 llvm.memcpy
declare const set:      (dst: Blob, value: U8, count: I64) => Void  // 封装 llvm.memset
declare const allocRaw: (size: I64) => Blob                         // 在当前 Arena 分配原始内存视图
```

```ez
// 系统级 error code 常量（正值区间；业务错误码由应用自行分配）
const errCancel:      I32 = 1   // flow cancel / race 取消
const errTimeout:     I32 = 2   // race timeout 超时
const errUnsupported: I32 = 3   // 当前平台不支持该 API
const errIO:          I32 = 4   // 通用 I/O 错误
const errNotFound:    I32 = 5   // 文件/资源不存在
const errPermission:  I32 = 6   // 权限不足
```

- `copy`：内存块拷贝，封装 `llvm.memcpy`。
- `set`：内存填充，封装 `llvm.memset`。
- `allocRaw`：在当前 Arena 游标处分配原始内存并返回 `Blob` 视图，作用域结束时自动回收，无需手动释放。
- `Error` 结构体已在 doc.md §3 中定义，`code` 字段使用上述常量或自定义正值业务码，无需额外 `type` 字段。

---

## 1.1 测试框架 (`std/test`)

```ez
declare const testAssert:      (condition: Bool, msg: Str) => Void
declare const testEqualI64:    (actual: I64, expected: I64, msg: Str) => Void
declare const testNotEqualI64: (actual: I64, expected: I64, msg: Str) => Void
declare const testEqualStr:    (actual: Str, expected: Str, msg: Str) => Void
declare const testSkip:        (msg: Str) => Void
const testThrows:              (body: () => Void, expectedCode: I32, msg: Str) => Void

declare const testRegister:      (name: Str) => Void
declare const testRegisterParam: (name: Str, param: Str) => Void
declare const testCount:         () => I32
declare const testName:          (index: I32) => Str
declare const testPassed:        () => I32
declare const testFailed:        () => I32
declare const testSkipped:       () => I32
declare const testReset:         () => Void
```

`testThrows` 调用传入函数并断言抛出的 `Error.code` 等于预期值；无异常时捕获到零值 `Error`，断言会失败。`testRegisterParam` 将参数化用例登记为 `name[param]`，`testCount` / `testName` 可按注册顺序检索用例名。

`ez test` 默认扫描项目 `tests/` 目录下的 `.ez` 文件。包含 `main` 的本机测试文件会被编译、链接并执行；没有 `main` 的测试文件会执行编译检查。以 `test` 开头或 `_test` 结尾的函数名会计入命令行摘要。运行失败时，CLI 会输出测试文件路径、退出码，并把 `testRegister` / `testRegisterParam` 登记的用例名映射回源码行号，适合持续集成环境收集诊断。

---

## 1.2 流式 IO 抽象 (`std/stream`)

```ez
const streamKindMemory: I32 = 1
const streamKindFileRead: I32 = 2
const streamKindFileWrite: I32 = 3
const streamKindTcp: I32 = 4

struct Stream {
    handle: I64
    kind: I32
}

declare const streamFromBlob: (data: Blob) => Stream?
declare const streamFromTcpHandle: (handle: I64) => Stream
declare const streamOpenFileRead:  (path: Str) => Stream?
declare const streamOpenFileWrite: (path: Str) => Stream?
declare const streamRead:     (stream: Stream, maxBytes: I64) => Blob?
declare const streamWrite:    (stream: Stream, data: Blob) => I64
declare const streamToBlob:   (stream: Stream) => Blob?
declare const streamCopy:     (dst: Stream, src: Stream, bufferSize: I64) => I64
declare const streamFlush:    (stream: Stream) => Bool
declare const streamClose:    (stream: Stream) => Bool
```

当前提供内存/Blob 流、文件读写流，并可通过 `streamFromTcpHandle` 复用 TCP 连接句柄。`streamRead` 从当前游标读取最多 `maxBytes` 字节，EOF 时返回 `ok = true` 且空 `Blob`；`streamWrite` 追加写入目标流；`streamCopy` 从源流当前游标复制到目标流，失败返回 `-1`。文件流使用平台文件系统或 WebAssembly MEMFS；TCP 流沿用当前阻塞式 socket 行为。进程管道和压缩流后续按同一 `Stream` ABI 接入。

---

## 2. 输入输出 (`std/io`)

```ez
declare const print:    (msg: Str) => Void
declare const println:  (msg: Str) => Void
declare const error:    (msg: Str) => Void
declare const readLine: () => Str?
```

| API        | 说明                           | android/ios          | emcc            |
| ---------- | ------------------------------ | -------------------- | --------------- |
| `print`    | 向 stdout 输出字符串           | logcat / os_log      | `console.log`   |
| `println`  | 向 stdout 输出字符串并换行     | logcat / os_log      | `console.log`   |
| `error`    | 向 stderr 输出字符串           | logcat / os_log 错误 | `console.error` |
| `readLine` | 从 stdin 读取一行，返回 `Str?` | 空可选值             | 空可选值        |

---

## 3. 文件系统 (`std/fs`)

```ez
struct FileStat {
    size:     I64
    isDir:    Bool
    modified: I64   // Unix 时间戳（毫秒）
    created:  I64
}

declare const readFile:   (path: Str) => Blob
declare const writeFile:  (path: Str, content: Blob) => Bool
declare const appendFile: (path: Str, content: Blob) => Bool
declare const removeFile: (path: Str) => Bool
declare const mkdir:      (path: Str) => Bool
declare const removeDir:  (path: Str, recursive: Bool) => Bool
declare const listDir:    (path: Str) => Str[]
declare const exists:     (path: Str) => Bool
declare const isDir:      (path: Str) => Bool
declare const stat:       (path: Str) => FileStat?
declare const absPath:    (path: Str) => Str
```

**平台说明**：
- **android / ios**：受沙盒限制，仅可访问应用私有数据目录；访问外部存储需在上层 UI 包（`ez-android-ui` / `ez-ios-ui`）中申请运行时权限后传入路径句柄。
- **emcc**：使用 Emscripten 虚拟文件系统（默认 `MEMFS`，可配置 `IDBFS` 持久化），挂载于根目录 `/`。

---

## 4. 操作系统接口 (`std/os`)

```ez
declare const args:     () => Str[]
declare const env:      (key: Str) => Str?
declare const setEnv:   (key: Str, value: Str) => Bool
declare const cwd:      () => Str
declare const exit:     (code: I32) => Void
declare const pid:      () => I32
declare const platform: () => Str   // "windows" | "macos" | "linux" | "android" | "ios" | "emcc"
declare const arch:     () => Str   // "x86_64" | "aarch64" | "wasm32" | "unknown"
```

**平台说明**：

| API              | android    | ios        | emcc                                      |
| ---------------- | ---------- | ---------- | ----------------------------------------- |
| `args`           | 返回空列表 | 返回空列表 | 返回 Emscripten 启动参数，缺省为空列表    |
| `env` / `setEnv` | libc 封装  | libc 封装  | Node 环境读写 `process.env`，浏览器返回空可选值/`false` |
| `cwd`            | libc 封装  | libc 封装  | 返回 `/`                                  |
| `pid`            | libc 封装  | libc 封装  | Node 环境返回 `process.pid`，浏览器返回 `-1` 表示不可用 |
| `exit`           | 正常       | 正常       | 调用 JS `process.exit`（仅 Node.js 有效） |

---

## 4.1 路径处理 (`std/path`)

`std/path` 只做词法路径处理，不访问文件系统；路径是否存在由 `std/fs` 负责。

```ez
struct PathParts {
    root: Str
    dir:  Str
    base: Str
    name: Str
    ext:  Str
}

declare const pathSeparator:   () => Str
declare const pathJoin:        (parts: Str[]) => Str
declare const pathNormalize:   (path: Str) => Str
declare const pathDir:         (path: Str) => Str
declare const pathBase:        (path: Str) => Str
declare const pathExt:         (path: Str) => Str
declare const pathIsAbs:       (path: Str) => Bool
declare const pathRelative:    (fromPath: Str, toPath: Str) => Str
declare const pathParse:       (path: Str) => PathParts
declare const pathToFileUrl:   (path: Str) => Str
declare const pathFromFileUrl: (url: Str) => Str?
```

**平台说明**：

| 目标平台              | 路径规则                                                |
| --------------------- | ------------------------------------------------------- |
| `windows`             | 默认分隔符为 `\`，识别盘符与 UNC 路径                  |
| `linux`/`macos`/移动端 | 默认分隔符为 `/`，同时接受 `\` 作为输入分隔符          |
| `emcc`                | 使用类 POSIX 规则，默认分隔符为 `/`                    |

`pathToFileUrl` / `pathFromFileUrl` 只处理 `file://` URL 与路径字节的百分号编码；完整 URL 解析、查询参数处理由后续 `std/uri` 模块承担。

---

## 4.2 字符串处理 (`std/str`)

`std/str` 提供 UTF-8 字符串的常用词法操作。字节索引以 UTF-8 字节为单位，字符索引以 Unicode 标量值边界为单位；非法 UTF-8 的二进制数据应先通过 `strFromBytes` 校验。

```ez
declare const strByteLen:     (s: Str) => I64
declare const strCharLen:     (s: Str) => I64
declare const strIsEmpty:     (s: Str) => Bool
declare const strIsValidUtf8: (s: Str) => Bool

declare const strSliceBytes:  (s: Str, start: I64, end: I64) => Str
declare const strSliceChars:  (s: Str, start: I64, end: I64) => Str
declare const strCharAt:      (s: Str, index: I64) => Str?
declare const strToBytes:     (s: Str) => Blob
declare const strFromBytes:   (data: Blob) => Str?

declare const strEqual:      (a: Str, b: Str) => Bool
declare const strContains:   (s: Str, needle: Str) => Bool
declare const strStartsWith: (s: Str, prefix: Str) => Bool
declare const strEndsWith:   (s: Str, suffix: Str) => Bool
declare const strIndexOf:    (s: Str, needle: Str) => I64

declare const strSplit:   (s: Str, sep: Str) => Str[]
declare const strJoin:    (parts: Str[], sep: Str) => Str
declare const strTrim:    (s: Str) => Str
declare const strReplace: (s: Str, old: Str, newValue: Str) => Str
declare const strToLower: (s: Str) => Str
declare const strToUpper: (s: Str) => Str
```

**规则说明**：

| API                         | 规则                                                       |
| --------------------------- | ---------------------------------------------------------- |
| `strByteLen` / `strIndexOf`  | 返回 UTF-8 字节长度/字节偏移；未找到返回 `-1`              |
| `strCharLen` / `strCharAt`   | 按 UTF-8 字符边界遍历；越界返回 `Str?` 空值                |
| `strSliceBytes`             | 按字节切片，不保证切片结果落在字符边界                    |
| `strSliceChars`             | 按字符边界切片，适合 Unicode 文本                          |
| `strSplit(s, sep = "")`     | 空分隔符表示按字符拆分                                    |
| `strToLower` / `strToUpper`  | 原生实现当前仅保证 ASCII 大小写映射；非 ASCII 字节保持不变 |

---

## 4.3 数学与数值工具 (`std/math`)

```ez
const mathPI: F64 = 3.141592653589793
const mathE:  F64 = 2.718281828459045

declare const mathAbsI32:   (value: I32) => I32
declare const mathAbsI64:   (value: I64) => I64
declare const mathMinI32:   (a: I32, b: I32) => I32
declare const mathMaxI32:   (a: I32, b: I32) => I32
declare const mathClampI32: (value: I32, minValue: I32, maxValue: I32) => I32
declare const mathGcdI64:   (a: I64, b: I64) => I64
declare const mathLcmI64:   (a: I64, b: I64) => I64

declare const mathSqrt:  (value: F64) => F64
declare const mathPow:   (base: F64, exp: F64) => F64
declare const mathSin:   (value: F64) => F64
declare const mathCos:   (value: F64) => F64
declare const mathTan:   (value: F64) => F64
declare const mathLog:   (value: F64) => F64
declare const mathExp:   (value: F64) => F64
declare const mathFloor: (value: F64) => F64
declare const mathCeil:  (value: F64) => F64
declare const mathRound: (value: F64) => F64
declare const mathIsNaN: (value: F64) => Bool
declare const mathIsInf: (value: F64) => Bool

declare const mathAddI64Checked: (a: I64, b: I64) => I64?
declare const mathSubI64Checked: (a: I64, b: I64) => I64?
declare const mathMulI64Checked: (a: I64, b: I64) => I64?
declare const mathDivI64Checked: (a: I64, b: I64) => I64?

declare const mathF64ToI32: (value: F64) => I32?
declare const mathF64ToI64: (value: F64) => I64?
declare const mathI64ToF64: (value: I64) => F64
```

**规则说明**：

| API                     | 规则                                                          |
| ----------------------- | ------------------------------------------------------------- |
| `mathAbsI32/I64`        | 最小负值无法取正时返回对应最大正值，避免溢出                  |
| `mathClampI32`          | 若 `minValue > maxValue`，实现会先交换上下界                  |
| `mathLcmI64`            | 结果溢出时饱和为 `I64` 最大值                                 |
| `math*Checked`          | 溢出、除零、`I64_MIN / -1` 返回空可选值                       |
| `mathF64ToI32/I64`      | 非有限值或越界返回空可选值；合法值按 C/JS 截断为整数          |

Linux 原生目标会额外链接系统数学库 `libm`；WebAssembly 目标使用 JavaScript `Math` 和 `BigInt` 实现。

---

## 4.4 随机数 (`std/random`)

`std/random` 拆分确定性伪随机源与系统安全随机源。确定性接口使用稳定的 xorshift64* 序列，便于测试和跨平台复现；安全随机接口只读取系统/浏览器熵源，不可用时返回空可选值。

```ez
struct RandomSource {
    state: U64
}

declare const randomSeed:         (seed: U64) => RandomSource
declare const randomNextU32:      (this: RandomSource) => U32
declare const randomNextU64:      (this: RandomSource) => U64
declare const randomRangeI64:     (this: RandomSource, minValue: I64, maxValue: I64) => I64
declare const randomRangeF64:     (this: RandomSource, minValue: F64, maxValue: F64) => F64
declare const randomShuffleBytes: (this: RandomSource, data: Blob) => Blob

declare const randomEntropy:      (size: I64) => Blob?
declare const randomSecureBytes:  (size: I64) => Blob?
declare const randomSecureU64:    () => U64?
```

**规则说明**：

| API                         | 规则                                                       |
| --------------------------- | ---------------------------------------------------------- |
| `randomSeed`                | 同一 `seed` 在所有平台产生相同确定性序列                  |
| `randomNextU32/U64`         | 会推进 `RandomSource.state`，适合测试、模拟、采样等非安全用途 |
| `randomRangeI64`            | 端点闭区间；若 `minValue > maxValue`，实现会先交换上下界  |
| `randomRangeF64`            | 返回 `[minValue, maxValue)` 区间内的浮点值                 |
| `randomShuffleBytes`        | 返回洗牌后的新 `Blob`，不修改传入数据                      |
| `randomSecure*`             | 只使用系统熵源；失败返回空可选值，不降级为伪随机          |

移动端和 WebAssembly 目标若没有可用熵源，安全随机接口返回空可选值。泛型数组洗牌需要集合/泛型 ABI 完善后再补齐；当前先提供 `Blob` 字节洗牌。

---

## 4.5 哈希与校验和 (`std/hash`)

`std/hash` 只提供非加密哈希与校验和，适用于哈希表、分片、缓存键和文件校验。SHA、HMAC 等安全算法由后续 `std/crypto` 独立提供。

```ez
declare const hashFnv1a32:    (data: Blob) => U32
declare const hashFnv1a64:    (data: Blob) => U64
declare const hashStrFnv1a32: (s: Str) => U32
declare const hashStrFnv1a64: (s: Str) => U64
declare const hashCombineU64: (seed: U64, value: U64) => U64

declare const crc32:    (data: Blob) => U32
declare const crc32Str: (s: Str) => U32
```

**规则说明**：

| API                   | 规则                                                       |
| --------------------- | ---------------------------------------------------------- |
| `hashFnv1a32/64`      | 对 `Blob` 的原始字节计算 FNV-1a 哈希                      |
| `hashStrFnv1a32/64`   | 对字符串的 UTF-8 字节计算 FNV-1a 哈希                     |
| `hashCombineU64`      | 使用固定混合公式组合多个 `U64` 哈希值                     |
| `crc32/crc32Str`      | 使用 IEEE CRC32 多项式 `0xEDB88320`                       |

FNV 与 CRC32 都不是安全算法，不可用于密码、签名、令牌或防篡改校验。

---

## 4.6 平台能力检测 (`std/platform`)

`std/platform` 提供底层平台信息与能力检测，用于在标准库和应用代码中做保守分支。高层操作系统接口仍由 `std/os` 提供。

```ez
declare const platformOS:             () => Str
declare const platformArch:           () => Str
declare const platformIsLittleEndian: () => Bool
declare const platformPointerBits:    () => I32

declare const platformPageSize:       () => I64
declare const platformCpuCount:       () => I32
declare const platformMemoryLimit:    () => I64

declare const platformHasThreads:     () => Bool
declare const platformHasFileSystem:  () => Bool
declare const platformHasNetwork:     () => Bool
declare const platformHasCrypto:      () => Bool
declare const platformHasDom:         () => Bool
declare const platformHasSubprocess:  () => Bool
```

**规则说明**：

| API                       | 规则                                                       |
| ------------------------- | ---------------------------------------------------------- |
| `platformOS`              | 返回 `windows`、`macos`、`linux`、`android`、`ios`、`emcc` |
| `platformArch`            | 返回 `x86_64`、`aarch64`、`x86`、`wasm32` 或 `unknown`     |
| `platformPageSize`        | 返回系统页大小；不可得时返回 `-1`                         |
| `platformCpuCount`        | 返回可用 CPU 数；不可得时至少返回 `1`                     |
| `platformMemoryLimit`     | 返回可探测的内存上限；不可得时返回 `-1`                   |
| `platformHasSubprocess`   | WebAssembly、iOS、Android 目标当前返回 `false`             |

WebAssembly 目标按当前 JS 运行环境检测 DOM、网络、加密和线程能力；缺失能力返回 `false`，不静默假定可用。

---

## 4.7 进程调用 (`std/process`)

`std/process` 仅用于调用外部程序、等待进程和捕获标准流，不提供线程、线程池、互斥锁、条件变量等底层并发接口。语言级并发仍统一由 `flow`、`parallel`、`race`、`rp`、`wp` 负责。

```ez
struct Command {
    program: Str
    args:    Str[]
    cwd:     Str
    env:     Str[]
    stdin:   Blob
}

struct Process {
    handle: I64
    pid:    I64
}

struct ProcessResult {
    exitCode: I32
    stdout:   Blob
    stderr:   Blob
    ok:       Bool
}

declare const processExec:        (command: Command) => ProcessResult?
declare const processSpawn:       (command: Command) => Process?
declare const processWait:        (process: Process) => ProcessResult?
declare const processTerminate:   (process: Process) => Bool
declare const processCurrentPath: () => Str?
```

**规则说明**：

| API                    | 规则                                                       |
| ---------------------- | ---------------------------------------------------------- |
| `processExec`          | 同步执行命令，写入 `stdin`，捕获 `stdout`/`stderr`         |
| `processSpawn`         | 创建子进程并返回句柄；当前不捕获子进程标准输出/错误       |
| `processWait`          | 等待 `Process` 结束，返回退出码；`stdout`/`stderr` 为空    |
| `processTerminate`     | 请求终止子进程；POSIX 平台发送 `SIGTERM`                  |
| `processCurrentPath`   | 返回当前可执行文件路径；不可探测时返回空可选值            |

`Command.env` 使用 `KEY=VALUE` 字符串数组表示环境变量覆盖，避免依赖尚未完整实现的动态字典运行时。`ProcessResult.ok` 表示退出码是否为 `0`。

当前 Linux/macOS/Windows native 目标实现子进程调用；Android、iOS 与 WebAssembly 目标返回空可选值或 `false`，不伪装为成功。`flow` 调度状态机完成前，进程等待在运行时仍是同步阻塞调用。

---

## 4.8 URL 与 URI (`std/uri`)

`std/uri` 提供 URL 的词法解析、构造、查询参数处理和百分号编解码。该模块不访问网络，也不负责文件路径规则；文件路径与 `file://` 的轻量转换由 `std/path` 负责。

```ez
struct UriParts {
    scheme:   Str
    userInfo: Str
    host:     Str
    port:     I32
    path:     Str
    query:    Str
    fragment: Str
}

declare const uriParse:     (url: Str) => UriParts?
declare const uriBuild:     (parts: UriParts) => Str
declare const uriNormalize: (url: Str) => Str

declare const uriScheme:   (url: Str) => Str?
declare const uriHost:     (url: Str) => Str?
declare const uriPort:     (url: Str) => I32?
declare const uriPath:     (url: Str) => Str
declare const uriQuery:    (url: Str) => Str?
declare const uriFragment: (url: Str) => Str?

declare const uriEncodeQuery:       (s: Str) => Str
declare const uriDecodeQuery:       (s: Str) => Str?
declare const uriEncodePathSegment: (s: Str) => Str
declare const uriDecodePathSegment: (s: Str) => Str?

declare const uriQueryGet: (query: Str, key: Str) => Str?
declare const uriQuerySet: (query: Str, key: Str, value: Str) => Str
```

**规则说明**：

| API                         | 规则                                                       |
| --------------------------- | ---------------------------------------------------------- |
| `uriParse`                  | 需要合法 scheme；解析失败返回空可选值                     |
| `uriBuild`                  | 根据 `UriParts` 重建 URL；`port = -1` 表示不输出端口       |
| `uriNormalize`              | 小写 scheme/host，并按词法规则折叠 path 中的 `.`/`..`      |
| `uriEncodeQuery`            | 查询参数编码中空格输出为 `+`                              |
| `uriDecodeQuery`            | 查询参数解码中 `+` 还原为空格；非法 `%XX` 返回空可选值    |
| `uriEncodePathSegment`      | 路径段编码会转义 `/`，避免把段内容误当分隔符              |
| `uriQueryGet/Set`           | 对裸 query 字符串操作，不包含前导 `?`；`key`/`value` 参数使用未编码文本，接口按 query 编码规则读写键和值 |

当前查询参数接口使用字符串级 API，避免依赖尚未完整实现的动态字典运行时。HTTP 模块可复用 `UriParts` 和这些编解码规则。

---

## 4.9 调试与诊断 (`std/debug`)

`std/debug` 提供低层诊断工具，供命令行、未捕获异常报告和调试输出复用。堆栈捕获为尽力行为，不支持的平台返回空可选值。

```ez
declare const debugPrint:       (msg: Str) => Void
declare const debugAssert:      (condition: Bool, msg: Str) => Void
declare const debugCrash:       (msg: Str) => Void
declare const debugLocation:    (file: Str, line: I32, column: I32) => Str
declare const debugRuntimeInfo: () => Str
declare const debugHex:         (data: Blob) => Str
declare const debugStack:       () => Str?
```

**规则说明**：

| API                  | 规则                                                       |
| -------------------- | ---------------------------------------------------------- |
| `debugPrint`         | 输出到标准错误或平台控制台                                 |
| `debugAssert`        | 条件为 `false` 时输出消息并终止当前程序/模块               |
| `debugCrash`         | 主动终止程序/模块，消息进入诊断输出                       |
| `debugLocation`      | 按 `file:line:column` 格式构造代码位置文本                 |
| `debugHex`           | 将 `Blob` 原始字节转成小写十六进制字符串                   |
| `debugStack`         | 平台支持时返回堆栈文本；不支持时返回空可选值               |

该模块只做诊断辅助，不替代语言级异常和测试框架。

---

## 4.10 结构化日志 (`std/log`)

`std/log` 提供编译期/运行时级别过滤、统一日志格式、代码位置和键值字段输出。当前字段使用 `Str[]` 表示为偶数位 `key, value` 序列，避免依赖尚未完整落地的动态字典运行时。

```ez
const logTrace: I32 = 0
const logDebug: I32 = 1
const logInfo:  I32 = 2
const logWarn:  I32 = 3
const logError: I32 = 4

const logTargetStderr:  I32 = 0
const logTargetStdout:  I32 = 1
const logTargetConsole: I32 = 2
const logTargetFile:    I32 = 3

struct LogConfig {
    minLevel: I32
    target: I32
    includeTimestamp: Bool
    includeLocation: Bool
}

declare const logDefaultConfig: () => LogConfig
declare const logConfigure:     (config: LogConfig) => Void
declare const logSetLevel:      (level: I32) => Void
declare const logSetFile:       (path: Str) => Bool

declare const logWrite:       (level: I32, msg: Str) => Void
declare const logWriteFields: (level: I32, msg: Str, fields: Str[]) => Void
declare const logWriteAt:     (level: I32, msg: Str, file: Str, line: I32, column: I32, fields: Str[]) => Void

declare const logTraceMsg: (msg: Str) => Void
declare const logDebugMsg: (msg: Str) => Void
declare const logInfoMsg:  (msg: Str) => Void
declare const logWarnMsg:  (msg: Str) => Void
declare const logErrorMsg: (msg: Str) => Void
```

**规则说明**：

| API/字段              | 规则                                                       |
| --------------------- | ---------------------------------------------------------- |
| `minLevel`            | 低于该级别的日志在运行时丢弃                               |
| `target`              | 原生平台支持 stderr/stdout/file；移动端非文件目标同步写系统日志；WebAssembly 输出到 console |
| `includeTimestamp`    | 为日志加毫秒时间戳                                         |
| `includeLocation`     | `logWriteAt` 可输出 `file:line:column`                     |
| `fields`              | 偶数位 `key, value`；多余的末尾 key 会被忽略               |

项目配置可通过 `[log].compile_min_level` 设置编译期最低日志级别，范围为 `0..4`。编译器会删除静态可判定且低于阈值的 `logTraceMsg`/`logDebugMsg`/`logInfoMsg`/`logWarnMsg`/`logErrorMsg`，以及 `level` 为字面量或标准级别常量的 `logWrite`/`logWriteFields`/`logWriteAt` 调用。动态 `level` 参数不会被编译期删除，仍由 `LogConfig.minLevel` 或 `logSetLevel` 在运行时过滤。

`logSetFile(path)` 会把目标切换为追加写文件；WebAssembly 同步环境不支持本地文件日志，`logSetFile` 返回 `false` 并继续输出到 console。安卓/iOS 目标在 stderr/stdout/console 目标下同步写入系统日志入口，文件目标仍追加写文件。

---

## 4.11 轻量正则匹配 (`std/regex`)

`std/regex` 提供跨平台的轻量模式匹配接口。原生 POSIX 平台使用扩展正则；WebAssembly 使用 JavaScript `RegExp`；Windows 原生目标当前显式返回不可用结果，不会把占位实现伪装成成功。

```ez
const regexIgnoreCase: I32 = 1
const regexMultiline:  I32 = 2
const regexGlobal:     I32 = 4

struct Regex {
    pattern: Str
    flags: I32
    ok: Bool
}

struct RegexMatch {
    start: I64
    end: I64
    text: Str
    groups: Str[]
}

declare const regexCompile: (pattern: Str, flags: I32) => Regex
declare const regexIsValid: (regex: Regex) => Bool
declare const regexTest:    (regex: Regex, input: Str) => Bool
declare const regexFind:    (regex: Regex, input: Str) => RegexMatch?
declare const regexFindAll: (regex: Regex, input: Str) => Str[]
declare const regexReplace: (regex: Regex, input: Str, replacement: Str) => Str
declare const regexSplit:   (regex: Regex, input: Str) => Str[]
```

**规则说明**：

| API/标志            | 规则                                                       |
| ------------------- | ---------------------------------------------------------- |
| `regexCompile`      | 编译失败时返回 `Regex.ok = false`                         |
| `regexFind`         | 返回首个匹配及捕获组；无匹配返回空可选值                 |
| `regexFindAll`      | 返回所有匹配文本，不返回每个匹配的捕获组                 |
| `regexReplace`      | 默认替换首个匹配；带 `regexGlobal` 时替换所有匹配；replacement 按字面字符串处理 |
| `regexSplit`        | 按匹配分隔字符串                                           |
| `regexIgnoreCase`   | 忽略 ASCII/平台引擎支持范围内的大小写                     |
| `regexMultiline`    | 传递给底层正则引擎的多行匹配标志                         |
| `regexGlobal`       | 影响 `regexReplace` 的替换范围；`regexFindAll` 始终查找全部匹配 |

该模块不是完整 PCRE 兼容实现。复杂 Unicode 类、回溯控制、环视断言、命名捕获等语法是否可用取决于底层平台；高危正则的复杂度限制仍需后续运行时超时/取消机制配合。

---

## 4.12 加密哈希与消息认证码 (`std/crypto`)

`std/crypto` 只封装成熟平台加密库，不自行实现加密算法。普通非加密哈希仍使用 `std/hash`。

```ez
declare const cryptoSha256:     (data: Blob) => Blob?
declare const cryptoSha512:     (data: Blob) => Blob?
declare const cryptoHmacSha256: (key: Blob, data: Blob) => Blob?
declare const cryptoHmacSha512: (key: Blob, data: Blob) => Blob?
```

**规则说明**：

| API                  | 规则                                                       |
| -------------------- | ---------------------------------------------------------- |
| `cryptoSha256`       | 返回 32 字节 SHA-256 digest；平台不可用时返回空可选值      |
| `cryptoSha512`       | 返回 64 字节 SHA-512 digest；平台不可用时返回空可选值      |
| `cryptoHmacSha256`   | 返回 32 字节 HMAC-SHA256；平台不可用时返回空可选值         |
| `cryptoHmacSha512`   | 返回 64 字节 HMAC-SHA512；平台不可用时返回空可选值         |

原生 macOS/iOS 目标使用 CommonCrypto；其它原生目标当前返回空可选值，避免使用未验证的本地实现。WebAssembly 同步 ABI 下优先使用 Node `crypto`；浏览器 WebCrypto 为异步 API，需等待后续 flow/async ABI 支持后接入。

---

## 4.13 压缩与解压缩 (`std/compress`)

`std/compress` 提供 gzip、zlib 和 raw deflate 的二进制 `Blob` 编解码。当前接口一次性处理完整输入；流式压缩接口等待 `std/stream`/流式 IO 抽象落地后补充。

```ez
declare const compressGzip:      (data: Blob) => Blob?
declare const decompressGzip:    (data: Blob) => Blob?
declare const compressZlib:      (data: Blob) => Blob?
declare const decompressZlib:    (data: Blob) => Blob?
declare const compressDeflate:   (data: Blob) => Blob?
declare const decompressDeflate: (data: Blob) => Blob?
```

**规则说明**：

| API                    | 规则                                                       |
| ---------------------- | ---------------------------------------------------------- |
| `compressGzip`         | 输出 gzip 容器格式                                         |
| `decompressGzip`       | 输入必须是合法 gzip 数据；失败返回空可选值                 |
| `compressZlib`         | 输出 zlib 容器格式                                         |
| `decompressZlib`       | 输入必须是合法 zlib 数据；失败返回空可选值                 |
| `compressDeflate`      | 输出 raw deflate 数据，不带 gzip/zlib 头                   |
| `decompressDeflate`    | 输入必须是 raw deflate 数据；失败返回空可选值              |

Linux/macOS native 目标使用系统 zlib。Windows、Android、iOS native 当前返回空可选值；WebAssembly 同步 ABI 下优先使用 Node `zlib`，浏览器同步环境当前返回空可选值。

---

## 5. 时间 (`std/time`)

```ez
struct Duration {
    ms: I64;

    fromSec(s: I64) => Duration;
    fromMin(m: I64) => Duration;
    toString(this: Duration) => Str;
}

declare const now:       () => Date    // 返回内置 Date 结构体（见 doc.md §3）
declare const timestamp: () => I64     // 自 Unix 纪元以来的毫秒数
declare const sleep:     (ms: I64) => Void
declare const getYear:   (this: Date) => I32
declare const getMonth:  (this: Date) => I32
declare const getDay:    (this: Date) => I32
declare const getHour:   (this: Date) => I32
declare const getMinute: (this: Date) => I32
declare const getSecond: (this: Date) => I32
declare const add:       (this: Date, year: I32?, month: I32?, day: I32?, hour: I32?, minute: I32?, second: I32?) => Void
declare const sub:       (this: Date, year: I32?, month: I32?, day: I32?, hour: I32?, minute: I32?, second: I32?) => Void
declare const format:    (this: Date, fmt: Str) => Str
```

- `sleep(ms)`：**flow 外**为同步阻塞当前线程；**flow 内**为 suspend point，runtime 挂起当前执行点并调度其它可运行逻辑，可被 `race` 的 `timeout` 取消（`throw Error(code = errCancel)`）。
- `format(this, fmt)`：原生与 WebAssembly 均支持 `YYYY`、`MM`、`DD`、`HH`、`SS` 命名占位符，也支持 `strftime` 风格的 `%Y`、`%m`、`%d`、`%H`、`%M`、`%S`；分钟使用 `%M`，月份使用 `MM` 或 `%m`。

---

## 6. 网络 (`std/net`)

当前 `std/net/http` 在原生桌面平台支持明文 `http://` 客户端请求，并可发送/读取基础字符串请求头；HTTP 服务端接口明确不支持，`createServer` 返回 `handle = 0`。`std/net/tcp` / `std/net/ws` 可创建原生 socket 句柄，并提供基础阻塞式 TCP/UDP 读写收发与 WebSocket 单帧消息收发。HTTPS、WebSocket `wss://`、分片帧和异步 flow 挂起仍待补齐。不支持的网络入口会显式返回空可选值或零句柄，不会伪装成请求或连接成功。

后续接入真实网络实现时保留现有签名。届时网络 API 均为阻塞操作：在 `flow {}` 内由 runtime 并发调度，在 `flow` 外为同步阻塞，无需额外标注。

### 6.1 HTTP 客户端

```ez
type Headers = { [key: Str]: Str }

struct HttpRequest {
    method:  Str       // "GET" | "POST" | "PUT" | "DELETE" | "PATCH" | "HEAD"
    url:     Str
    headers: Headers
    body:    Blob?
}

struct HttpResponse {
    status:  I32
    headers: Headers
    body:    Blob

    text: (this: HttpResponse) => Str
}

// 便捷函数
declare const fetch:    (url: Str) => HttpResponse?
declare const fetchEx:  (req: HttpRequest) => HttpResponse?
```

**使用示例**：

```ez
// flow 外：同步阻塞
const resp = fetch(url = "https://api.example.com/data")
(typeof resp & HttpResponse == HttpResponse) ? {
    print(msg = resp!.text())
}

// flow 内：并发调度
const result = flow {
    const a = fetch(url = "https://api.example.com/a")
    const b = fetch(url = "https://api.example.com/b")
    return a?.text() + b?.text()
}

// 竞速：取第一个响应
const winner = race(
    pl = [
        () => fetch(url = "https://cdn1.example.com/res"),
        () => fetch(url = "https://cdn2.example.com/res")
    ],
    timeout = 5000
)
```

**当前平台行为**：

| 目标                    | 行为                                      |
| ----------------------- | ----------------------------------------- |
| linux / macos / windows | `fetch` / `fetchEx` 支持明文 `http://`；HTTPS 和解析失败返回空可选值 |
| android / ios           | `fetch` / `fetchEx` 返回空可选值          |
| emcc                    | JS wrapper 写入空可选值，不发起网络请求   |

---

### 6.2 HTTP 服务端

HTTP 服务端当前明确不支持；仅保留声明和句柄结构以稳定 ABI。`createServer` 返回 `handle = 0`，`on` / `start` / `stop` 为空操作，不会启动监听或注册路由。

```ez
type RouteHandler = (req: HttpRequest) => HttpResponse;

struct HttpServer {
    on(this: HttpServer, path: Str, handler: RouteHandler) => Void;
    start(this: HttpServer) => Void;    // 阻塞，推荐在 flow {} 内调用
    stop(this: HttpServer) => Void;
}

declare const createServer: (host: Str, port: I32) => HttpServer;
```

**使用示例**：

```ez
const server = createServer(host = "0.0.0.0", port = 8080);

server.on(path = "/hello", handler = (req: HttpRequest) => {
    return HttpResponse(
        status = 200,
        headers = { "Content-Type" = "text/plain" },
        body = Blob(data = "hello", size = 5)
    );
});

flow {
    server.start();    // suspend point，不阻塞主流程
}
```

---

### 6.3 TCP

当前原生桌面平台的 TCP API 会创建真实阻塞 socket 句柄，支持连接、监听、接收连接、基础读写和关闭。Android/iOS 复用同一原生封装入口；emcc 当前仍返回空可选值或失败值。异步 flow 挂起、超时配置、TLS 与跨平台细节仍需后续运行时接入。

```ez
struct TcpConn {
    handle: I64
}

struct TcpListener {
    handle: I64
}

declare const tcpConnect: (host: Str, port: I32) => TcpConn?
declare const tcpListen:  (host: Str, port: I32) => TcpListener?
declare const tcpAccept:  (listener: TcpListener) => TcpConn?
declare const tcpRead:    (conn: TcpConn, maxBytes: I64) => Blob?
declare const tcpWrite:   (conn: TcpConn, data: Blob) => I64
declare const tcpClose:   (conn: TcpConn) => Bool
declare const tcpListenerClose: (listener: TcpListener) => Bool
```

可用 `std/stream.streamFromTcpHandle(handle = conn.handle)` 把 TCP 连接转换为通用流，再传给 `streamRead`、`streamWrite`、`streamCopy` 和 `streamClose`。关闭同一连接时只应选择 `streamClose` 或 `tcpClose` 其中之一。

---

### 6.4 UDP

当前原生桌面平台的 UDP API 会创建真实阻塞 UDP socket 句柄，支持绑定、向指定地址发送、接收数据和关闭。Android/iOS 复用同一原生封装入口；emcc 当前仍返回空可选值或失败值。当前接收接口不返回远端地址，超时和异步 flow 挂起仍需后续运行时接入。

```ez
struct UdpSocket {
    handle: I64
}

declare const udpBind: (host: Str, port: I32) => UdpSocket?
declare const udpSend: (socket: UdpSocket, host: Str, port: I32, data: Blob) => I64
declare const udpRecv: (socket: UdpSocket, maxBytes: I64) => Blob?
declare const udpClose: (socket: UdpSocket) => Bool
```

---

### 6.5 WebSocket

当前原生桌面平台的 `wsConnect` 支持 `ws://` 握手并返回 socket 句柄，`wsSend` / `wsRecv` 支持基础单帧二进制或文本消息收发，`wsClose` 发送关闭帧后关闭 socket。Android/iOS 复用同一原生封装入口；emcc 当前仍返回空可选值或失败值。`wss://`、分片帧、ping/pong 自动处理、浏览器 WebSocket 桥接和异步 flow 挂起仍需后续接入。

```ez
struct WsConn {
    handle: I64
}

declare const wsConnect: (url: Str) => WsConn?
declare const wsSend: (conn: WsConn, data: Blob) => I64
declare const wsRecv: (conn: WsConn, maxBytes: I64) => Blob?
declare const wsClose: (conn: WsConn) => Bool
```

---

## 7. 数据结构扩展 (`std/collections`)

`List` 和 `Dict` 是语言内置类型，标准库在此基础上提供扩展函数。
当前集合扩展均由编译器内建 lowering 实现。`List` 使用分页数组 ABI `{ pages, length, capacity, page_count }`；`Dict` 先基于现有分页键值存储做线性扫描，`Str` 键按字符串内容比较，标量键按值比较。

```ez
// List<T> 扩展
declare const listPush:    <T>(list: List<T>, item: T) => Void
declare const listPop:     <T>(list: List<T>) => T?
declare const listShift:   <T>(list: List<T>) => T?
declare const listUnshift: <T>(list: List<T>, item: T) => Void
declare const listSort:    <T>(list: List<T>, cmp: (a: T, b: T) => I32) => Void
declare const listFilter:  <T>(list: List<T>, pred: (item: T) => Bool) => List<T>
declare const listMap:     <T, U>(list: List<T>, f: (item: T) => U) => List<U>
declare const listFind:    <T>(list: List<T>, pred: (item: T) => Bool) => T?
declare const listLen:     <T>(list: List<T>) => I64
declare const listSlice:   <T>(list: List<T>, start: I64, end: I64) => List<T>

// Dict<K, V> 扩展
declare const dictKeys:   <K, V>(dict: Dict<K, V>) => K[]
declare const dictValues: <K, V>(dict: Dict<K, V>) => V[]
declare const dictHas:    <K, V>(dict: Dict<K, V>, key: K) => Bool
declare const dictDelete: <K, V>(dict: Dict<K, V>, key: K) => Bool
declare const dictLen:    <K, V>(dict: Dict<K, V>) => I64
```

---

## 8. 格式化与编码 (`std/fmt`)

```ez
// 字符串与数值转换
declare const toString:   <T>(value: T) => Str
declare const parseInt:   (s: Str) => I32?
declare const parseI64:   (s: Str) => I64?
declare const parseF64:   (s: Str) => F64?
declare const format:     (template: Str, args: Str[]) => Str   // {} 占位符替换

// Base64
declare const b64Encode:  (data: Blob) => Str
declare const b64Decode:  (s: Str) => Blob?

// JSON
// 嵌套值均表示为 Blob（可通过类型断言进一步访问）。解析失败时 throw Error(code = errIO)
declare const jsonStringify: <T>(data: T) => Str
declare const jsonParse:     <T>(s: Str) => T

// MessagePack
// 当前覆盖 I32 / I64 / F64 / Bool / Str 基础类型；其它泛型结构待运行时编码器补齐。
declare const msgpackEncode: <T>(data: T) => Blob
declare const msgpackDecode: <T>(data: Blob) => T

// URL 编码
declare const urlEncode:  (s: Str) => Str
declare const urlDecode:  (s: Str) => Str?
```

---

## 9. 设计准则

1. **值语义优先**：API 倾向于返回新值或 `Blob`，利用 Arena 自动管理生命周期，避免手动释放。
2. **Flow 优先**：所有阻塞 I/O 均为 `flow` suspend point；在 `flow` 外等价于同步阻塞。语言不引入 `async/await`，并发语义统一由 `flow` / `race` 表达。
3. **平台感知，不静默成功**：不支持的 API 必须按接口约定显式失败，例如返回空可选值、`false`、`errUnsupported` 或诊断错误；平台限制在文档中明确标注。
4. **UI 解耦**：移动端 UI 能力下沉至 `ez-android-ui` 和 `ez-ios-ui` 独立包，`std` 不绑定 UI 框架。
5. **零分配开销**：在可能的情况下，避免 Arena 之外的额外堆分配，所有临时数据优先在当前作用域 Arena 上分配。
