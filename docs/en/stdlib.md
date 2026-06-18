# EzLang Standard Library Design

[中文](../stdlib.md)

The EzLang standard library follows a design strategy of "unified high-level APIs with platform-aware low-level implementations." The compiler selects the low-level linked libraries and system calls dynamically from the targets defined in `project.toml`. Blocking I/O follows the semantic goal of Flow concurrency: inside `flow {}` it can act as a suspend point, while outside Flow it is equivalent to synchronous blocking. The emcc target suspends and resumes through Asyncify. Native wrappers that are not yet connected to event sources still use blocking syscalls and document those limitations.

This page explains module responsibilities, platform capabilities, and design constraints. Per-function signatures are authoritative in the [Standard Library API Reference](stdlib-api.md).

---

## 0. Design Principles

1. **Unified API**: users call the same standard-library interface regardless of compilation target.
2. **Platform awareness**: implementations automatically choose syscalls or platform libraries according to `os` and `arch`.
3. **Explicit safe degradation**: unsupported APIs must fail according to their signature, such as by returning an empty optional, `false`, `errUnsupported`, or a diagnostic error. They must not silently pretend to succeed.
4. **Flow first**: blocking I/O is designed as a Flow suspend point. Current scheduled points include `sleep`, `race(pl)`, selected `parallel` tasks, and on emcc HTTP, TCP/UDP, WebSocket, stdin, fs, process, and stream I/O.
5. **UI decoupling**: mobile UI capability is provided by separate packages; `std` does not bind to any UI framework.

---

## Compilation Targets

| Target | Platform | Low-Level Implementation |
| ------ | -------- | ------------------------ |
| `windows` | Windows x86/x64/arm64 | Win32 API + MSVCRT |
| `macos` | macOS x64/arm64 | libc + Darwin syscall |
| `linux` | Linux x64/arm64 | libc + Linux syscall |
| `android` | Android arm64/x86_64 | Bionic libc + Android NDK |
| `ios` | iOS arm64 | Apple libc + XNU syscall |
| `emcc` | WebAssembly (Emscripten) | Emscripten libc + JS bindings |

> **Mobile UI**: Android UI is provided by the independent `ez-android-ui` package. iOS UI is provided by `ez-ios-ui`. The standard library covers system capabilities only and does not include UI.

---

## Standard Library Capability Matrix

| Module | Capability Type | Linux/macOS | Windows | Android/iOS | WebAssembly | freestanding |
| ------ | --------------- | ----------- | ------- | ----------- | ----------- | ------------ |
| `std/mem` | compiler builtin | full | full | full | full | low-level primitives |
| `std/io` | native/JS wrapper | stdout/stderr/stdin | stdout/stderr/stdin | system log; synchronous stdin | console; Node stdin; browser stdin empty optional | unsupported |
| `std/fs` | native/JS wrapper | filesystem | basic filesystem | sandbox paths | MEMFS/IDBFS | unsupported |
| `std/os` | native/JS wrapper | process/env/platform | process/env/platform | sandbox environment; partial info | Node preferred; browser explicit failure | unsupported |
| `std/time` | native/JS wrapper | millisecond time/date/sleep | millisecond time/date/sleep | millisecond time/date/sleep | millisecond time/date/Asyncify sleep | unsupported |
| `std/fmt` | pure logic + wrapper | full | full | full | full | unsupported |
| `std/collections` | compiler lowering | full | full | full | full | unsupported |
| `std/net/http` | native/JS wrapper | HTTP/HTTPS client; basic server | plain HTTP client; basic server | plain HTTP client; basic server | fetch + Asyncify client; Node basic server; synchronous XHR fallback without Asyncify | unsupported |
| `std/net/tcp` | native/JS wrapper | blocking TCP/UDP sockets + timeout variants; TCP TLS client | blocking TCP/UDP sockets + timeout variants | blocking TCP/UDP sockets + timeout variants | Node net/tls/dgram + Asyncify; browser explicit failure | unsupported |
| `std/net/ws` | native/JS wrapper | ws/wss client, fragmentation, ping-pong | ws client, fragmentation, ping-pong | ws client, fragmentation, ping-pong | WebSocket + Asyncify client | unsupported |
| `std/str` | pure logic + wrapper | UTF-8 basics | UTF-8 basics | UTF-8 basics | UTF-8 basics | unsupported |
| `std/math` | native/JS wrapper | libm/checked arithmetic | system math/checked arithmetic | system math/checked arithmetic | JS Math/BigInt | unsupported |
| `std/path` | pure logic wrapper | POSIX/Darwin paths | Windows paths | platform path rules | POSIX-like paths | unsupported |
| `std/random` | native/JS wrapper | deterministic source + system entropy | deterministic source + system entropy | deterministic source + system entropy | deterministic source + Web/Node entropy | unsupported |
| `std/hash` | pure logic wrapper | FNV/CRC32 | FNV/CRC32 | FNV/CRC32 | FNV/CRC32 | unsupported |
| `std/platform` | native/JS wrapper | platform capability query | platform capability query | platform capability query | JS environment capability query | unsupported |
| `std/process` | native/JS wrapper | exec/spawn/wait/pipe streams | exec/spawn/wait/pipe streams | Android exec/spawn/wait/pipe streams; iOS explicit failure | Node spawn + Asyncify; stdout/stderr streams; browser explicit failure | unsupported |
| `std/uri` | pure logic wrapper | URL parse/build/encoding | URL parse/build/encoding | URL parse/build/encoding | URL parse/build/encoding | unsupported |
| `std/debug` | native/JS wrapper | diagnostics/best-effort stack | diagnostics/best-effort stack | diagnostics/best-effort address stack | console/Error stack | unsupported |
| `std/log` | std/io + std/time | stdout/stderr/file | stdout/stderr/file | system log/file | console; Emscripten FS/Node file target | unsupported |
| `std/stream` | runtime ABI wrapper | memory/Blob, file streams, TCP streams, process pipe streams | memory/Blob, file streams, TCP streams, process pipe streams | memory/Blob, file streams, TCP streams, process pipe streams | memory/Blob, file streams, Node TCP streams, Node process pipe streams | unsupported |
| `std/test` | runtime test wrapper | `ez test` native execution | mostly compile checks | mostly compile checks | mostly compile checks | unsupported |
| `std/regex` | native/JS wrapper | POSIX extended regex | built-in lightweight regex | POSIX/platform best effort | JS RegExp | unsupported |
| `std/crypto` | platform crypto wrapper + sync fallback | Linux dynamic OpenSSL; macOS CommonCrypto; SHA-2/HMAC fallback | Windows BCrypt; SHA-2/HMAC fallback | iOS CommonCrypto; Android SHA-2/HMAC fallback | Node crypto; sync SHA-2/HMAC fallback | unsupported |
| `std/compress` | platform compression wrapper | zlib/gzip/deflate | zlib/gzip/deflate | Android/iOS zlib/gzip/deflate | Node zlib; CompressionStream + Asyncify | unsupported |

Capability type notes: `compiler builtin` is implemented by the compiler and does not depend on standard-library declarations or external symbols. `compiler lowering` is exposed through standard-library API declarations but lowered by the compiler without external symbols. `pure logic wrapper` does not access system resources. `native/JS wrapper` uses C or Emscripten JS ABI for platform capability. `runtime ABI wrapper` fixes language runtime data layout while allowing file, network, process, or other backends later.

Memory rule: wrapper functions returning `Str`, `Blob`, lists, or dictionaries allocate result memory in the current platform wrapper, and language code takes over lifetime through the Arena/runtime ABI. One-shot `Blob` APIs do not promise zero copy. Error rule: unsupported platforms must return empty optionals, `false`, `-1`, zero handles, or `errUnsupported` diagnostics; they must not fake success. Flow rule: blocking I/O inside `flow {}` is a semantic suspend point; wrappers that are not yet connected to full scheduling keep synchronous ABI and document the platform limitation.

---

## 0.1 Built-In Language Types

These types are compiler-predeclared and can be used without `from "std/..." import`:

```ez
struct Date {
    timestamp: I64
}

struct Error {
    code: I32
    message: Str
    file: Str
    line: I32
    column: I32
    trace: Str
}

struct Blob {
    data: *U8
    size: I64
}

struct Meta<T> {
    value: T
    getter: () => T
    setter: (value: T) => Void
    t: Str
    name: Str
}
```

- `Date`, `Error`, and `Blob` are ABI types shared by standard-library modules. `std/time`, `std/mem`, `std/fs`, `std/net/*`, `std/stream`, and others use them directly.
- `List<T>` / `T[]` and `Dict<K, V>` are also compiler-built compound types. `std/collections` provides operation functions only and does not define the underlying types.
- `Meta<T>` is used by decorators. `@Dec let value = ...` wraps a top-level variable as `Meta<T>`, and decorators can set `getter` / `setter` closures to intercept reads and writes. `t` and `name` expose compiler-generated type and variable names.
- Full semantics are documented in [Language Specification](doc.md), especially "Structs, Composition, and Built-In Objects" and "Metaprogramming, Syntax Sugar, and Safety."

---

## 0.2 External ABI Linking (`extern`)

The standard library uses `extern` for cross-platform low-level library linking. Users do not need to configure this manually.

```text
// Standard-library internal example
extern "@std/native/net/http.c" for linux
extern "pthread" for linux
extern "dl" for linux
extern "@std/emcc/net/http.js" for emcc

// Symbols exposed by the wrapper layer
declare const fetch: (url: Str) => HttpResponse?
declare const fetchEx: (req: HttpRequest) => HttpResponse?
```

User code imports standard-library APIs directly. The compiler selects the correct `extern` libraries and `declare` symbols for the target platform. Low-level C/JS symbols are not additional public Ez APIs.

---

## 1. Memory and Error Handling (`std/mem`)

```ez
declare const copy:     (dst: Blob, src: Blob, count: I64) => Void  // llvm.memcpy wrapper
declare const set:      (dst: Blob, value: U8, count: I64) => Void  // llvm.memset wrapper
declare const allocRaw: (size: I64) => Blob                         // Raw memory view allocated in the current Arena
```

```ez
const errCancel:      I32 = 1   // Flow cancel / race cancellation
const errTimeout:     I32 = 2   // race timeout
const errUnsupported: I32 = 3   // API unsupported on current platform
const errIO:          I32 = 4   // General I/O error
const errNotFound:    I32 = 5   // File/resource not found
const errPermission:  I32 = 6   // Permission denied
```

- `copy`: memory block copy, wrapping `llvm.memcpy`.
- `set`: memory fill, wrapping `llvm.memset`.
- `allocRaw`: allocates raw memory at the current Arena cursor and returns a `Blob` view. Memory is automatically reclaimed when the scope exits.
- The `Error` struct is defined by the language spec. `code` uses these constants or application-defined positive business codes; no extra `type` field is needed.

## 1.1 Test Framework (`std/test`)

`std/test` provides assertion, skip, throw-checking, and case-registration helpers. `ez test` scans project `tests/` by default, executes native test files with `main`, compile-checks files without `main`, and includes functions named with `test*` or `*_test` in the summary. Registered case names can be mapped back to source lines for CI diagnostics.

## 1.2 Stream I/O Abstraction (`std/stream`)

`std/stream` defines `Stream { handle: I64, kind: I32 }` and stream kind constants for memory, file-read, file-write, TCP, and process stdin/stdout/stderr streams. It supports creating streams from Blob data, TCP handles, and files; reading, writing, copying, flushing, converting to Blob, and closing.

Current support includes memory/Blob streams, file read/write streams, TCP connection streams, and process pipe streams. `std/compress` streaming APIs reuse the same ABI. Files use platform filesystems or WebAssembly MEMFS. TCP streams use blocking socket behavior on native targets and the Asyncify TCP bridge in emcc Node-style runtime. Process pipe streams come from `std/process`.

---

## 2. Input and Output (`std/io`)

`std/io` exposes `print`, `println`, `error`, and `readLine`.

| API | Description | android/ios | emcc |
| --- | ----------- | ----------- | ---- |
| `print` | write string to stdout | logcat / os_log | Node `stdout.write` without newline; buffers until next `println` if stdout is missing |
| `println` | write string to stdout with newline | logcat / os_log | Node `stdout.write` with newline; flushes buffered `print` content |
| `error` | write string to stderr | logcat / os_log error | `console.error` |
| `readLine` | read one stdin line as `Str?` | synchronous read; empty optional on EOF/no stdin | Node fd 0; browser empty optional |

---

## 3. Filesystem (`std/fs`)

`std/fs` exposes `FileStat` plus file read/write/append/remove, directory create/remove/list, existence/type checks, stat, and absolute path conversion.

Platform notes:

- Empty paths or invalid `Blob` input fail according to the signature.
- **android / ios**: sandboxed to app-private data directories. External storage access should be requested in the UI package and passed in as path handles.
- **emcc**: uses the Emscripten virtual filesystem, default `MEMFS`, with optional `IDBFS` persistence mounted at `/ezdata`.

---

## 4. Operating System Interface (`std/os`)

`std/os` provides process arguments, environment access, current working directory, exit, pid, platform, and architecture.

| API | android | ios | emcc |
| --- | ------- | --- | ---- |
| `args` | empty list | empty list | Emscripten startup arguments, default empty |
| `env` / `setEnv` | libc wrapper | libc wrapper | Node `process.env`; browser empty optional/`false` |
| `cwd` | libc wrapper; empty if unavailable | libc wrapper; empty if unavailable | Node `process.cwd()`; browser `/` |
| `pid` | libc wrapper | libc wrapper | Node `process.pid`; browser `-1` |
| `exit` | normal | normal | JS `process.exit`, Node only |

## 4.1 Path Handling (`std/path`)

`std/path` performs lexical path handling only. It does not access the filesystem.

| Target | Rules |
| ------ | ----- |
| `windows` | default separator `\`, recognizes drive letters and UNC paths |
| `linux`/`macos`/mobile | default separator `/`, also accepts `\` as input separator |
| `emcc` | POSIX-like rules, separator `/` |

`pathToFileUrl` / `pathFromFileUrl` only handle `file://` URLs and path-byte percent encoding. Full URL parsing and query handling belongs to `std/uri`.

## 4.2 String Handling (`std/str`)

`std/str` provides UTF-8 lexical operations. Byte indexes use UTF-8 bytes; character indexes use Unicode scalar value boundaries. Binary data must be validated with `strFromBytes`, and NUL bytes cannot be represented in Ez `Str` ABI.

Important rules:

- `strByteLen` / `strIndexOf` return UTF-8 byte length/offset; not found is `-1`.
- `strCharLen` / `strCharAt` traverse character boundaries; out-of-range returns empty optional.
- `strSliceBytes` does not guarantee character-boundary output.
- `strSliceChars` slices on character boundaries.
- `strFromBytes` returns empty optional for invalid `Blob`, invalid UTF-8, or NUL bytes.
- `strSplit(s, sep = "")` splits by character.
- `strTrim` trims Unicode White_Space.
- Case conversion uses deterministic simple mappings, not locale rules or full case folding.

## 4.3 Math and Numeric Tools (`std/math`)

`std/math` provides constants, integer helpers, floating math, checked integer operations, and float-to-integer conversions. Linux native links `libm`; WebAssembly uses JS `Math` and `BigInt`.

Important rules:

- `mathAbsI32/I64` saturate to max positive value for the minimum negative input.
- `mathClampI32` swaps bounds if `minValue > maxValue`.
- `mathLcmI64` saturates to `I64` max on overflow.
- `mathRound` rounds `.5` away from zero.
- Checked arithmetic returns empty optional on overflow, division by zero, or invalid conversion.
- `mathF64ToI32/I64` only accepts finite values whose truncated integer fits the target type.

## 4.4 Random Numbers (`std/random`)

`std/random` separates deterministic pseudo-random sources from secure system random sources. Deterministic APIs use a stable xorshift64* sequence for tests and reproducibility. Secure APIs read only system/browser entropy and return empty optionals when unavailable.

## 4.5 Hashes and Checksums (`std/hash`)

`std/hash` provides non-cryptographic FNV-1a and CRC32 helpers for hash tables, sharding, cache keys, and file checks. SHA-2 and HMAC live in `std/crypto`.

FNV and CRC32 are not security algorithms and must not be used for passwords, signatures, tokens, or tamper-proof checks.

## 4.6 Platform Capability Detection (`std/platform`)

`std/platform` provides low-level platform information and capability checks for conservative branches in library and application code. Higher-level OS operations remain in `std/os`.

WebAssembly detects DOM, network, crypto, thread, and subprocess capability from the current JS runtime. Node reads CPU count and memory limit from `os` when available; missing capabilities return `false` or `-1` instead of assuming support.

## 4.7 Process Invocation (`std/process`)

`std/process` is only for external program execution, process waiting, and standard stream capture. It does not expose threads, thread pools, mutexes, or condition variables. Language-level concurrency stays in `flow`, `parallel`, `race`, `rp`, and `wp`.

`Command.env` uses `KEY=VALUE` strings for environment overrides. `Command.stdin` must be a valid `Blob`; invalid input returns an empty optional. `ProcessResult.ok` means exit code `0`.

Current Linux/macOS/Windows/Android native targets implement subprocess calls and pipe stream transfer. emcc Node-style runtime uses `child_process.spawn` with Asyncify when available, and falls back to `spawnSync` without live stdin otherwise. Browser WebAssembly and iOS fail explicitly.

## 4.8 URL and URI (`std/uri`)

`std/uri` provides lexical URL parsing, construction, query handling, and percent encode/decode. It does not access the network and does not handle filesystem path rules.

Query APIs operate on bare query strings without a leading `?`, preserving duplicate keys, empty keys, order, and original encoding boundaries. Applications can convert to `Dict` at a higher layer when structured access is needed.

## 4.9 Debugging and Diagnostics (`std/debug`)

`std/debug` provides low-level diagnostic helpers reused by the CLI, uncaught exception reporting, and debug output. Stack capture is best effort: desktop platforms prefer symbols, Android/iOS return address frames, and unsupported platforms return empty optionals.

## 4.10 Structured Logging (`std/log`)

`std/log` provides compile-time/runtime level filtering, unified log format, source location, and key-value fields. Fields are represented as `Str[]` with even-position `key, value` pairs, allowing native/JS wrappers to output in order and preserve repeated keys.

Project configuration `[log].compile_min_level` sets a compile-time minimum level from `0..4`. Statically known calls below the threshold are removed; dynamic `level` values continue through runtime filtering.

## 4.11 Lightweight Regex Matching (`std/regex`)

`std/regex` provides a cross-platform lightweight pattern API. POSIX native platforms use extended regex. Windows uses a synchronous built-in lightweight fallback. WebAssembly uses JavaScript `RegExp`.

The module is not a full PCRE-compatible implementation. To reduce catastrophic backtracking risk, `regexCompile` rejects overly long patterns, too many capture groups, large bounded repeats, nested variable repeats, and variable repeats over branching groups.

## 4.12 Cryptographic Hashes and MAC (`std/crypto`)

`std/crypto` prefers mature platform crypto libraries and falls back to synchronous SHA-2/HMAC. Ordinary non-cryptographic hashes remain in `std/hash`.

Linux dynamically loads OpenSSL `libcrypto`; macOS/iOS prefer CommonCrypto; Windows prefers BCrypt; emcc prefers Node `crypto`. Missing platform libraries use the built-in synchronous fallback.

## 4.13 Compression and Decompression (`std/compress`)

`std/compress` provides gzip, zlib, and raw deflate one-shot `Blob` encoding/decoding and streaming compression/decompression through `std/stream.Stream { handle, kind }`.

Native targets use system zlib. WebAssembly prefers Node `zlib`; browsers/Workers can use `CompressionStream` / `DecompressionStream` with Asyncify. Missing Web APIs or Asyncify return empty optionals or `-1`.

---

## 5. Time (`std/time`)

`std/time` provides `Duration`, `now`, `timestamp`, `sleep`, `Date` field accessors, date arithmetic, and date formatting.

- `sleep(ms)`: outside Flow, it is a synchronous ABI; inside Flow, it is a suspend point. emcc restores the wasm stack through Asyncify. Current `race` timeouts return a timeout zero value and do not immediately interrupt branches already in synchronous code.
- `add(this, ...)` / `sub(this, ...)`: mutate the passed `Date` in place and return `Void`.
- `format(this, fmt)`: supports `YYYY`, `MM`, `DD`, `HH`, `mm`, `SS`, plus `%Y`, `%m`, `%d`, `%H`, `%M`, `%S`. Minutes use `mm` or `%M`; months use `MM` or `%m`.

---

## 6. Networking (`std/net`)

`std/net/http` supports native `http://` clients and, on Linux/macOS with a dynamically available OpenSSL TLS backend plus valid system CAs and certificate/hostname verification, `https://`. It also provides a basic HTTP server. emcc uses browser/Worker `fetch` + Asyncify for clients, synchronous XHR fallback without Asyncify, and a Node-style `http.createServer` server when available.

`std/net/tcp` / `std/net/ws` create native socket handles and provide blocking TCP/UDP/WebSocket basics. TCP/UDP APIs include one-shot `timeoutMs` variants. Linux/macOS support TCP TLS and `wss://` under the same TLS conditions. emcc supports TCP/TLS/UDP in Node-style runtimes through `net` / `tls` / `dgram` + Asyncify and supports WebSocket clients in browser/Worker environments through WebSocket + Asyncify. Browser-native TCP/UDP and native event-source Flow suspension remain future work. Unsupported entries return empty optionals or zero handles and never pretend that a request or connection succeeded.

HTTP response bodies remain raw bytes in `HttpResponse.body`; `HttpResponse.text()` returns text only when the body is valid UTF-8 without NUL bytes.

Future native event-source Flow suspension will keep current signatures. Current network APIs are synchronous blocking outside Flow; emcc HTTP, Node TCP/UDP, and WebSocket clients suspend/resume with Asyncify when available, while native TCP/UDP/WS still use blocking socket calls.

### 6.1 HTTP Client

`std/net/http` defines `Headers`, `HttpRequest`, `HttpResponse`, and convenience functions `fetch` and `fetchEx`.

Platform behavior:

| Target | Behavior |
| ------ | -------- |
| linux / macos | `fetch` / `fetchEx` support `http://`, valid ports, userinfo, IPv6 literals, basic request/response headers, and chunked response bodies; `https://` works when TLS backend and verification are available; parse or TLS failure returns empty optional |
| windows / android / ios | native wrapper supports plain `http://` clients and per-connection worker server; `https://` returns empty optional |
| emcc | browser/Worker `fetch` + Asyncify client; synchronous XHR fallback without Asyncify; empty optional when unavailable; Node-style runtime supports basic server |

### 6.2 HTTP Server

The native HTTP server is basic: `createServer` creates a handle, `on` registers exact path routes, `start` listens on the current thread and dispatches accepted connections to workers, and `stop` closes the listener and waits for dispatched work to finish. emcc Node-style runtime uses `http.createServer` + Asyncify. Browser/Worker runtimes without port listening return a zero handle.

`HttpServer` reuses `std/net/http`'s `HttpRequest`, `HttpResponse`, and `RouteHandler`. A server handler receives the full `HttpRequest { method, url, headers, body }` and returns the full `HttpResponse { status, headers, body }`.

### 6.3 TCP

Native desktop TCP APIs create real blocking socket handles, support connect/listen/accept/read/write/close, and include one-shot timeout variants. Linux/macOS support TCP TLS clients when OpenSSL TLS and verification are available. TLS uses separate `TcpTlsConn` handles. Android/iOS reuse the native wrapper. emcc Node-style runtime supports TCP/TLS through `net` / `tls` + Asyncify. Browser/Worker returns failure values. Native event-source Flow suspension is still future work.

TCP connections can be converted to generic streams with `std/stream.streamFromTcpHandle(handle = conn.handle)`. A connection should be closed through either `streamClose` or `tcpClose`, not both.

### 6.4 UDP

Native UDP APIs create blocking UDP socket handles and support bind, send, receive, receive-with-source, close, and one-shot timeout variants. Ports must be in `0..65535`; invalid bind ports return empty optional, invalid send ports return `-1`; `timeoutMs < 0` is invalid, while `timeoutMs == 0` polls once without waiting. emcc Node-style runtime uses `dgram` + Asyncify; browser/Worker returns failure values. Native event-source Flow suspension is still future work.

### 6.5 WebSocket

Native `wsConnect` supports `ws://` handshake validation and connection handles. Linux/macOS support `wss://` when OpenSSL TLS and verification are available. URLs support valid ports, userinfo stripping, root query preservation, fragment stripping, and IPv6 literals. `wsSend` sends client-masked binary messages; `wsRecv` handles text/binary messages, fragmented frames, and ping/pong control frames; `wsClose` sends a close frame and closes the connection. Android/iOS reuse the wrapper but return empty optional for `wss://`. emcc uses browser/Worker WebSocket + Asyncify for `ws://` / `wss://` clients.

---

## 7. Data Structure Extensions (`std/collections`)

`List` and `Dict` are compiler-predeclared built-in types. `std/collections` exposes extension functions whose first parameter is `this` with type `#List<T>` / `#Dict<K, V>`, so they can be called explicitly with `this = #value` or through method sugar such as `value.fn(...)`.

Collection extensions are compiler-lowered. `List` uses the paged array ABI `{ pages, length, capacity, page_count }`. `Dict` keeps paged key-value storage for native/JS standard-library boundaries and maintains open-addressing hash indexes for compiler-built `Str` and primitive scalar key dictionaries. `dictKeys` / `dictValues` return insertion order; compatible external dictionaries without the internal hash marker fall back to paged linear scanning.

---

## 8. Formatting and Encoding (`std/fmt`)

`std/fmt` includes string/value conversion, integer/float parsing, placeholder formatting, Base64, JSON, MessagePack, and URL encoding/decoding.

JSON and MessagePack support primitive types, ordinary user structs, optionals, nested lists, dictionaries with `Str` or primitive scalar keys, and union types. Struct parsing requires an exact field set and throws `Error(code = errIO)` for mismatches. Decoded strings containing NUL cannot be represented as Ez `Str` and fail according to the specific API.

---

## 9. Design Guidelines

1. **Value semantics first**: APIs prefer returning new values or `Blob`s and rely on Arena lifetime management instead of manual free.
2. **Flow first**: blocking I/O uses Flow suspend-point semantics as its target. Outside Flow it behaves like synchronous blocking. The language does not add `async/await`; concurrency remains expressed through `flow`, `parallel`, and `race`. emcc suspends/resumes through Asyncify; native wrappers that are not connected to event sources keep blocking syscall ABI.
3. **Platform-aware, never silently successful**: unsupported APIs must fail according to their signatures, and platform limitations must be documented.
4. **UI decoupling**: mobile UI lives in `ez-android-ui` and `ez-ios-ui`; `std` does not bind to UI frameworks.
5. **Zero allocation overhead where possible**: avoid heap allocation outside the Arena when practical, and place temporary data in the current scope Arena.
