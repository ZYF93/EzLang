# EzLang 标准库设计文档 (Standard Library Design)

EzLang 标准库采用"统一上层 API，平台感知底层实现"的设计策略。编译器根据 `project.toml` 中定义的目标平台（target）动态切换底层链接库与系统调用。所有阻塞 I/O 操作均遵循 Flow 并发语义：在 `flow {}` 内自动转为非阻塞调度点，在 `flow` 外等价于同步阻塞。

---

## 0. 设计理念

1. **统一 API**：无论编译目标为何，用户均调用相同的标准库接口。
2. **平台感知**：底层实现根据 `os` 和 `arch` 自动选择 syscall 或平台库函数。
3. **安全降级**：某平台不支持的 API 调用时触发 `panic`，并在文档中明确标注平台限制，不做静默失败。
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

## 1. 内存与错误处理 (`std/mem`)

```ez
declare const copy:     (dst: *I8, src: *I8, count: I64) => Void  // 封装 llvm.memcpy
declare const memset:   (dst: *I8, value: I8, count: I64) => Void  // 封装 llvm.memset
declare const allocRaw: (size: I64) => *I8                          // 在当前 Arena 分配原始内存
```

```ez
// 系统级 error code 常量（负值区间，与业务正值错误码不冲突）
const errCancel:      I32 = -1   // flow cancel / race 取消
const errTimeout:     I32 = -2   // race timeout 超时
const errUnsupported: I32 = -3   // 当前平台不支持该 API
const errIO:          I32 = -4   // 通用 I/O 错误
const errNotFound:    I32 = -5   // 文件/资源不存在
const errPermission:  I32 = -6   // 权限不足
```

- `copy`：内存块拷贝，封装 `llvm.memcpy`。
- `memset`：内存填充，封装 `llvm.memset`。
- `allocRaw`：在当前 Arena 游标处分配原始内存，作用域结束时自动回收，无需手动释放。
- `Error` 结构体已在 doc.md §3 中定义，`code` 字段使用上述常量或自定义正值业务码，无需额外 `type` 字段。

---

## 2. 输入输出 (`std/io`)

```ez
declare const print:    (msg: Str) => Void
declare const println:  (msg: Str) => Void
declare const error:    (msg: Str) => Void
declare const readLine: () => Str?
```

| API        | 说明                           | android/ios    | emcc            |
| ---------- | ------------------------------ | -------------- | --------------- |
| `print`    | 向 stdout 输出字符串           | logcat         | `console.log`   |
| `println`  | 向 stdout 输出字符串并换行     | logcat         | `console.log`   |
| `error`    | 向 stderr 输出字符串           | logcat (error) | `console.error` |
| `readLine` | 从 stdin 读取一行，返回 `Str?` | ❌ panic        | ❌ panic         |

---

## 3. 文件系统 (`std/fs`)

```ez
struct FileStat {
    size:     I64
    isDir:    Bool
    modified: I64   // Unix 时间戳（毫秒）
    created:  I64
}

declare const readFile:   (path: Str) => Blob?
declare const writeFile:  (path: Str, content: Blob) => Bool
declare const appendFile: (path: Str, content: Blob) => Bool
declare const removeFile: (path: Str) => Bool
declare const mkdir:      (path: Str) => Bool
declare const removeDir:  (path: Str, recursive: Bool) => Bool
declare const listDir:    (path: Str) => Str[]?
declare const exists:     (path: Str) => Bool
declare const isDir:      (path: Str) => Bool
declare const stat:       (path: Str) => FileStat?
declare const absPath:    (path: Str) => Str?
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
declare const arch:     () => Str   // "x64" | "arm64" | "x86" | "wasm32"
```

**平台说明**：

| API              | android    | ios        | emcc                                      |
| ---------------- | ---------- | ---------- | ----------------------------------------- |
| `args`           | 返回空列表 | 返回空列表 | 返回空列表                                |
| `env` / `setEnv` | ❌ panic    | ❌ panic    | ❌ panic                                   |
| `cwd`            | ❌ panic    | ❌ panic    | 返回 `/`                                  |
| `pid`            | ❌ panic    | ❌ panic    | ❌ panic                                   |
| `exit`           | 正常       | 正常       | 调用 JS `process.exit`（仅 Node.js 有效） |

---

## 5. 时间 (`std/time`)

```ez
struct Duration {
    ms: I64

    fromSec  = (s: I64) => Duration
    fromMin  = (m: I64) => Duration
    toString = (this: Duration) => Str
}

declare const now:       () => Date    // 返回内置 Date 结构体（见 doc.md §3）
declare const timestamp: () => I64     // 自 Unix 纪元以来的毫秒数
declare const sleep:     (ms: I64) => Void
```

- `sleep(ms)`：**flow 外**为同步阻塞当前线程；**flow 内**为 suspend point，runtime 挂起当前执行点并调度其它可运行逻辑，可被 `race` 的 `timeout` 取消（`throw Error(code = errCancel)`）。

---

## 6. 网络 (`std/net`)

网络 API 均为阻塞操作：在 `flow {}` 内由 runtime 并发调度，在 `flow` 外为同步阻塞，无需额外标注。

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

**平台说明**：

| 目标                    | 底层实现                                       |
| ----------------------- | ---------------------------------------------- |
| linux / macos / windows | libcurl 或系统 TLS                             |
| android                 | libcurl 或 Android NDK HttpURLConnection       |
| ios                     | libcurl 或 NSURLSession                        |
| emcc                    | Emscripten `fetch` JS 绑定（需满足 CORS 策略） |

---

### 6.2 HTTP 服务端

> 仅支持 `linux / macos / windows` 平台，在 `android / ios / emcc` 调用触发 `panic`。

```ez
type RouteHandler = (req: HttpRequest) => HttpResponse

struct HttpServer {
    on    = (this: HttpServer, path: Str, handler: RouteHandler) => Void
    start = (this: HttpServer) => Void    // 阻塞，推荐在 flow {} 内调用
    stop  = (this: HttpServer) => Void
}

declare const createServer: (host: Str, port: I32) => HttpServer
```

**使用示例**：

```ez
const server = createServer(host = "0.0.0.0", port = 8080)

server.on(path = "/hello", handler = (req: HttpRequest) => {
    return HttpResponse(
        status = 200,
        headers = { "Content-Type" = "text/plain" },
        body = Blob(...)
    )
})

flow {
    server.start()    // suspend point，不阻塞主流程
}
```

---

### 6.3 TCP

> `emcc` 不支持原生 TCP socket，调用触发 `panic`。

```ez
struct TcpConn {
    read  = (this: TcpConn, size: I64) => Blob?
    write = (this: TcpConn, data: Blob) => I64
    close = (this: TcpConn) => Void
}

struct TcpListener {
    accept = (this: TcpListener) => TcpConn?
    close  = (this: TcpListener) => Void
}

declare const tcpConnect: (host: Str, port: I32) => TcpConn?
declare const tcpListen:  (host: Str, port: I32) => TcpListener?
```

---

### 6.4 UDP

> `emcc` 不支持原生 UDP socket，调用触发 `panic`。

```ez
struct UdpSocket {
    send  = (this: UdpSocket, data: Blob, host: Str, port: I32) => I64
    recv  = (this: UdpSocket, size: I64) => Blob?
    close = (this: UdpSocket) => Void
}

declare const udpBind: (host: Str, port: I32) => UdpSocket?
```

---

### 6.5 WebSocket

> `emcc` 底层使用 JS WebSocket API；其余平台使用 libwebsockets 或系统 TLS。

```ez
struct WsConn {
    send  = (this: WsConn, msg: Str) => Void
    recv  = (this: WsConn) => Str?             // flow 内为 suspend point
    close = (this: WsConn) => Void
}

declare const wsConnect: (url: Str) => WsConn?
```

---

## 7. 数据结构扩展 (`std/collections`)

`List` 和 `Dict` 是语言内置类型，标准库在此基础上提供扩展方法。

```ez
// List<T> 扩展
struct List<T> {
    push:    <T>(this: List<T>, item: T) => Void
    pop:     <T>(this: List<T>) => T?
    shift:   <T>(this: List<T>) => T?
    unshift: <T>(this: List<T>, item: T) => Void
    sort:    <T>(this: List<T>, cmp: (a: T, b: T) => I32) => Void
    filter:  <T>(this: List<T>, pred: (item: T) => Bool) => List<T>
    map:     <T, U>(this: List<T>, f: (item: T) => U) => List<U>
    find:    <T>(this: List<T>, pred: (item: T) => Bool) => T?
    len:     <T>(this: List<T>) => I64
    slice:   <T>(this: List<T>, start: I64, end: I64) => List<T>
}

// Dict<K, V> 扩展
struct Dict<K, V> {
    keys:    <K, V>(this: { [key: K]: V }) => K[]
    values:  <K, V>(this: { [key: K]: V }) => V[]
    has:     <K, V>(this: { [key: K]: V }, key: K) => Bool
    delete:  <K, V>(this: { [key: K]: V }, key: K) => Bool
    len:     <K, V>(this: { [key: K]: V }) => I64
}
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
// 与 JSON 语义一致，但使用二进制编码，更紧凑更快。解析失败时 throw Error(code = errIO)
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
3. **平台感知，不静默失败**：不支持的 API 在对应平台调用时 `throw Error(code = errUnsupported)`，平台限制在文档中明确标注。
4. **UI 解耦**：移动端 UI 能力下沉至 `ez-android-ui` 和 `ez-ios-ui` 独立包，`std` 不绑定 UI 框架。
5. **零分配开销**：在可能的情况下，避免 Arena 之外的额外堆分配，所有临时数据优先在当前作用域 Arena 上分配。
