# EzLang 运行时设计

[English](en/runtime-design.md)

EzLang 运行时围绕三个核心目标设计：Arena 内存管理、Flow 并发调度、标准库平台适配。

## Arena 内存管理

编译器在每个 LLVM module 中生成 Arena 基础设施：

- `__arena_buffer`：线程本地缓冲区指针，初始为 `null`。
- `__arena_capacity`：线程本地缓冲区容量，初始为 `0`。
- `__arena_cursor`：线程本地当前分配游标。
- `__arena_alloc(size, align)`：按对齐分配内存；容量不足时通过 `realloc` 扩容，首次容量从 1MB 起步并按需翻倍。
- `__arena_save()`：保存游标。
- `__arena_restore(cursor)`：恢复游标。

块作用域自动保存和恢复游标。聚合值默认分配在 Arena 中，返回聚合值时由 codegen 生成按值 load。

## Flow 运行时 ABI

Flow 并发相关 hook：

- `__ezrt_flow_enter()`：进入 flow 块。
- `__ezrt_flow_exit()`：离开 flow 块。
- `__ezrt_sleep(ms)`：flow 内 sleep suspend point。
- `__ezrt_race_i32(branches, count, timeout, timed_out)`：并发运行零捕获 `() => I32` 分支并返回首个完成值。
- `__ezrt_task_start_i32(branch)` / `__ezrt_task_start_env_i32(branch, env)` / `__ezrt_task_join_i32(handle)`：flow 内 `parallel { ... return I32 }` 初始化的后台任务启动与依赖读取等待，覆盖零捕获、共享捕获、推断类型和显式 `I32` 声明。

当前 codegen 保持这些 hook 的 ABI 稳定。Linux/macOS/Windows/Android/iOS 通过 `packages/std/native/runtime.c` 提供 `race` 和 `parallel` 的最小任务运行时；emcc 目标通过 `packages/std/emcc/runtime.js` 提供 Asyncify 协程 backend，`race(pl)` 与 flow 内 `I32` `parallel` 都会表现为可挂起和可恢复的执行点。`parallel` 捕获外层局部变量时会提升为共享存储槽，读写锁变量仍走既有锁 hook。emcc 不把 `parallel` 返回值暴露成 JS `Promise`，而是在 wasm 栈内由 Asyncify 恢复 EzLang 顺序语义；`sleep`、HTTP `fetch`、TCP/UDP、WebSocket `wsConnect` / `wsRecv`、stdin、文件系统、进程和流式 I/O 也通过 Asyncify 挂起后恢复。后续可通过 JSPI 或 wasm pthread 替换 runtime backend；native 阻塞 I/O 后续可替换为 epoll、kqueue、IOCP 或 WASI 等平台等待源。

## 阻塞调用与 suspend point

语义分析器维护阻塞调用集合，例如：

- 文件 IO：`readFile`、`writeFile`、`appendFile`
- 网络 IO：`fetch`、`tcpConnect`、`accept`、`read`、`write`、`recv`、`send`
- 时间：`sleep`

在 `flow {}` 内出现这些调用时，会记录 suspend point 和数据依赖。emcc 目标会据此链接 Asyncify runtime，避免浏览器或 JS 主线程做忙等式等待；native 目标当前仍使用阻塞 syscall 或任务运行时，后续可替换为平台等待源。

## 标准库平台适配

标准库的 `.ez` 文件提供统一 API，底层通过 wrapper 分平台实现：

- 原生平台：`packages/std/native/*.c`
- Emscripten：`packages/std/emcc/*.js`

例如 `std/fs`：

- 桌面和移动平台走 C 封装。
- Android/iOS 相对路径会映射到沙盒根目录。
- emcc 使用 MEMFS，浏览器环境可挂载 `/ezdata` 到 IDBFS 并调用 `FS.syncfs`。

## 错误处理

标准库错误码位于 `std/mem`：

- `errCancel`
- `errTimeout`
- `errUnsupported`
- `errIO`
- `errNotFound`
- `errPermission`

语言级 `Error` 当前统一携带错误码、消息、抛出点源位置和轻量调用栈片段；原生线程栈符号化、跨线程异步栈拼接仍属于调试能力扩展。
