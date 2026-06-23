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

## Closure Reference-Counted Heap

Escaping closures do not use the ordinary Arena lifetime. The compiler emits closure-specific heap helpers in each LLVM module:

- `__ez_heap_alloc(size, destructor)`: allocate a heap object with a reference-counted header and return the user-data pointer.
- `__ez_heap_retain(ptr)`: increment the reference count; `null` is a no-op.
- `__ez_heap_release(ptr)`: decrement the reference count; the final release calls the object's destructor and then frees the heap block.

Captured variables are promoted to heap capture slots. A closure environment stores pointers to these slots and retains them; the environment destructor releases the slots. Overwriting variable, field, or global closure slots releases the previous closure and retains or transfers the new closure according to ownership. Leaving a local scope releases closures owned by that scope. Returning a local closure transfers ownership to the caller.

## Flow Runtime ABI

Flow-related runtime hooks:

- `__ezrt_flow_enter()`: enter a Flow block.
- `__ezrt_flow_exit()`: leave a Flow block.
- `__ezrt_sleep(ms)`: Flow-local sleep suspend point.
- `__ezrt_race_i32(branches, count, timeout, timed_out)`: compatibility fast path for zero-capture `() => I32` race branches.
- `__ezrt_race_value(branches, envs, count, timeout, result, scratch, result_size, timed_out)`: run captured or non-`I32` `race(pl)` branches concurrently and copy the first completed out-pointer result into the caller-provided result slot.
- `__ezrt_task_start(branch, env, out)` / `__ezrt_task_join(handle)`: start a background task for a `parallel { ... return ... }` initializer inside Flow and wait for it when its value is read. Return values use caller-provided out storage, so non-`I32`, aggregate, inferred, and explicit result types are covered.
- `__ezrt_task_start_i32(branch)` / `__ezrt_task_start_env_i32(branch, env)` / `__ezrt_task_join_i32(handle)`: compatibility hooks retained for older I32 task ABI users.

Current codegen keeps the old I32 hooks ABI-stable while using the out-pointer hooks for general values. Linux/macOS/Windows/Android/iOS use `packages/std/native/runtime.c` for a minimal task runtime behind `race` and `parallel`. The emcc target uses `packages/std/emcc/runtime.js` with Asyncify as a coroutine backend, so `race(pl)` and `parallel` inside Flow behave as suspendable and resumable execution points. Flow-local `parallel` captures and task environments are allocated in a Flow-protected caller-side Arena lifetime and restored only after pending futures have joined; `race(pl)` result slots and branch scratch storage live in the caller Arena and cover the runtime call. Escaping closure environments are not Arena allocations; they are managed by the closure reference-counted heap. The runtime owns only task handles and scheduling state. Locked variables still use the existing lock hooks. emcc does not expose `parallel` results as JavaScript `Promise` values; it restores the wasm stack through Asyncify to preserve EzLang's sequential ABI. `sleep`, HTTP `fetch`, TCP/UDP, WebSocket `wsConnect` / `wsRecv`, stdin, file system, process, and stream I/O can also suspend through Asyncify. Future runtime backends can replace this with JSPI, wasm pthreads, or native event sources such as epoll, kqueue, IOCP, or WASI.

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
