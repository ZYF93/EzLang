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

## std/time

- `now() -> Date`
- `timestamp() -> I64`
- `sleep(ms: I64) -> Void`
- `getYear(this: Date) -> I32`
- `getMonth(this: Date) -> I32`
- `getDay(this: Date) -> I32`
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
- `udpBind(host: Str, port: I32) -> UdpSocket?`

## std/net/ws

- `wsConnect(url: Str) -> WsConn?`

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

当前只保留 API 声明。未实现的泛型集合扩展在调用时会报编译错误，避免生成悬空 LLVM 外部符号。后续应在编译器内建 lowering 或专用运行时中实现。
