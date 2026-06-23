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

## 闭包引用计数 heap

逃逸闭包不使用普通 Arena 生命周期。编译器会在每个 LLVM module 中生成闭包专用 heap helper：

- `__ez_heap_alloc(size, destructor)`：分配带引用计数头的 heap 对象，返回用户数据指针。
- `__ez_heap_retain(ptr)`：增加引用计数；`null` 指针为 no-op。
- `__ez_heap_release(ptr)`：减少引用计数；最后一个引用释放时先调用对象析构函数，再释放 heap block。

捕获变量会被提升为 heap 捕获槽，闭包环境保存这些捕获槽指针并 retain 它们；闭包环境析构时 release 捕获槽。变量、字段和全局闭包槽覆盖时会 release 旧闭包并按所有权规则 retain 或转移新闭包；局部作用域退出会 release 本作用域拥有的闭包值；直接返回局部闭包会转移所有权给调用方。

## Flow 运行时 ABI

Flow 并发相关 hook：

- `__ezrt_flow_enter()`：进入 flow 块。
- `__ezrt_flow_exit()`：离开 flow 块。
- `__ezrt_sleep(ms)`：flow 内 sleep suspend point。
- `__ezrt_race_i32(branches, count, timeout, timed_out)`：零捕获 `() => I32` race 分支的兼容快路径。
- `__ezrt_race_value(branches, envs, count, timeout, result, scratch, result_size, timed_out)`：并发运行带捕获或非 `I32` 的 `race(pl)` 分支，并把首个完成的 out 指针结果复制到调用方结果槽。
- `__ezrt_task_start(branch, env, out)` / `__ezrt_task_join(handle)`：flow 内 `parallel { ... return ... }` 初始化的后台任务启动与依赖读取等待。返回值使用调用方提供的 out 存储，覆盖非 `I32`、聚合、推断类型和显式声明。
- `__ezrt_task_start_i32(branch)` / `__ezrt_task_start_env_i32(branch, env)` / `__ezrt_task_join_i32(handle)`：保留给旧 I32 任务 ABI 使用的兼容 hook。

当前 codegen 保持旧 I32 hook 的 ABI 稳定，同时用 out 指针 hook 覆盖通用值。Linux/macOS/Windows/Android/iOS 通过 `packages/std/native/runtime.c` 提供 `race` 和 `parallel` 的最小任务运行时；emcc 目标通过 `packages/std/emcc/runtime.js` 提供 Asyncify 协程 backend，`race(pl)` 与 flow 内 `parallel` 都会表现为可挂起和可恢复的执行点。flow 内 `parallel` 捕获的外层局部变量和任务环境分配在 flow 保护的调用方 Arena 生命周期内，所有 pending future join 后再恢复；`race(pl)` 的结果槽和分支 scratch 分配在调用方 Arena，runtime 返回前完成或取消并 join 分支。逃逸闭包环境不放在 Arena 中，而由闭包引用计数 heap 管理。runtime 只拥有任务句柄和调度状态。读写锁变量仍走既有锁 hook。emcc 不把 `parallel` 返回值暴露成 JS `Promise`，而是在 wasm 栈内由 Asyncify 恢复 EzLang 顺序语义；`sleep`、HTTP `fetch`、TCP/UDP、WebSocket `wsConnect` / `wsRecv`、stdin、文件系统、进程和流式 I/O 也通过 Asyncify 挂起后恢复。后续可通过 JSPI 或 wasm pthread 替换 runtime backend；native 阻塞 I/O 后续可替换为 epoll、kqueue、IOCP 或 WASI 等平台等待源。

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
