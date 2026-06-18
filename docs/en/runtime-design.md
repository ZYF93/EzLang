# EzLang Runtime Design

[中文](../runtime-design.md)

The EzLang runtime is built around three goals: Arena memory management, Flow concurrency scheduling, and standard-library platform adaptation.

## Arena Memory Management

The compiler generates Arena infrastructure in each LLVM module:

- `__arena_buffer`: thread-local buffer pointer, initially `null`.
- `__arena_capacity`: thread-local buffer capacity, initially `0`.
- `__arena_cursor`: thread-local current allocation cursor.
- `__arena_alloc(size, align)`: allocates aligned memory. When capacity is insufficient it expands through `realloc`; the initial capacity starts at 1 MB and doubles as needed.
- `__arena_save()`: saves the current cursor.
- `__arena_restore(cursor)`: restores a saved cursor.

Block scopes automatically save and restore the cursor. Aggregate values are allocated in the Arena by default, and returned aggregate values are loaded by value during codegen.

## Flow Runtime ABI

Flow-related runtime hooks:

- `__ezrt_flow_enter()`: enter a Flow block.
- `__ezrt_flow_exit()`: leave a Flow block.
- `__ezrt_sleep(ms)`: Flow-local sleep suspend point.
- `__ezrt_race_i32(branches, count, timeout, timed_out)`: run zero-capture `() => I32` branches concurrently and return the first completed value.
- `__ezrt_task_start_i32(branch)` / `__ezrt_task_join_i32(handle)`: start a background task for a zero-capture `parallel { ... return I32 }` initializer inside Flow and wait for it when its value is read. Both inferred and explicit `I32` declarations are covered.

Current codegen keeps these hooks ABI-stable. Linux/macOS/Windows/Android/iOS use `packages/std/native/runtime.c` for a minimal task runtime behind `race` and `parallel`. The emcc target uses `packages/std/emcc/runtime.js` with Asyncify as a coroutine backend, so `race(pl)` and zero-capture `I32` `parallel` inside Flow behave as suspendable and resumable execution points. emcc does not expose `parallel` results as JavaScript `Promise` values; it restores the wasm stack through Asyncify to preserve EzLang's sequential ABI. `sleep`, HTTP `fetch`, TCP/UDP, WebSocket `wsConnect` / `wsRecv`, stdin, file system, process, and stream I/O can also suspend through Asyncify. Future runtime backends can replace this with JSPI, wasm pthreads, or native event sources such as epoll, kqueue, IOCP, or WASI.

## Blocking Calls and Suspend Points

The semantic analyzer maintains a set of blocking calls, including:

- file I/O: `readFile`, `writeFile`, `appendFile`
- network I/O: `fetch`, `tcpConnect`, `accept`, `read`, `write`, `recv`, `send`
- time: `sleep`

Inside `flow {}`, these calls record suspend points and data dependencies. The emcc target links the Asyncify runtime from that metadata to avoid busy waiting in the browser or JS main thread. Native targets currently use blocking syscalls or the task runtime, with room for future platform event sources.

## Standard-Library Platform Adaptation

Standard-library `.ez` files provide a unified API. Platform-specific wrappers provide the implementation:

- native platforms: `packages/std/native/*.c`
- Emscripten: `packages/std/emcc/*.js`

For example, `std/fs`:

- Desktop and mobile platforms use C wrappers.
- Android/iOS relative paths map to sandbox roots.
- emcc uses MEMFS by default and can mount `/ezdata` to IDBFS when available, then call `FS.syncfs`.

## Error Handling

Standard-library error codes live in `std/mem`:

- `errCancel`
- `errTimeout`
- `errUnsupported`
- `errIO`
- `errNotFound`
- `errPermission`

The language-level `Error` currently carries an error code, message, source location, and lightweight call-stack fragment. Native thread stack symbolization and cross-thread async stack stitching remain diagnostic extensions.
