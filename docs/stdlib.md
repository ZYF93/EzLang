# EzLang 标准库设计文档 (Standard Library Design)

EzLang 标准库采用“统一上层 API，动态底层实现”的设计策略。编译器会根据 `project.toml` 中定义的产出目标（output）动态切换底层的链接库（Native 目标链接 `libc`，WASM 目标链接 `wasi-libc`）。

## 0. 设计理念
1. **统一 API (Unified API)**：无论编译目标为何，用户均调用相同的 `*` 接口。
2. **目标感知 (Target Awareness)**：底层实现根据 `os` 和 `arch` 自动选择 syscall 或库函数。
3. **安全降级 (Safe Degradation)**：若 `libc` 具备的能力在 `wasi-libc` 中完全缺失且无法模拟，则在 WASI 目标下调用该 API 将直接触发 `panic` 报错。

## 1. 内存与错误处理
- `copy(dst: *I8, src: *I8, count: I64) => Void`: 封装 `llvm.memcpy`。
- `set(dst: *I8, value: I8, count: I64) => Void`: 封装 `llvm.memset`。
- `allocRaw(size: I64) => *I8`: 在当前 Arena 游标处分配原始内存。
- `panic(msg: Str) => Void`: 打印错误并终止当前进程/线程。
- `Error` 结构体：(已在 doc.md 定义) 包含 code, message, data。

---

## 2. 输入输出 (I/O)
- `print(msg: Str) => Void`: 向标准输出打印字符串。
- `println(msg: Str) => Void`: 打印字符串并追加换行符。
- `error(msg: Str) => Void`: 向标准错误打印字符串。
- `readLine() => Str?`: 从标准输入读取一行，返回可选类型。

---

## 3. 文件系统 (File System)
- `readFile(path: Str) => Blob?`: 读取整个文件到内存。
- `writeFile(path: Str, content: Blob) => Bool`: 创建并写入文件。
- `appendFile(path: Str, content: Blob) => Bool`: 追加内容到文件。
- `removeFile(path: Str) => Bool`: 删除指定文件。
- `mkdir(path: Str) => Bool`: 创建目录。
- `isDir(path: Str) => Bool`: 检查是否为目录。

---

## 4. 操作系统接口 (OS)
- `args() => List<Str>`: 获取命令行参数列表。
- `env(key: Str) => Str?`: 获取环境变量。
- `cwd() => Str`: 获取当前工作目录。
- `exit(code: I32) => Void`: 退出进程。
- `id() => I32`: 获取当前进程/线程 ID。

---

## 5. 时间与异步 (Time & Async)
- `now() => Date`: 获取当前系统时间（返回内置 `Date` 结构体）。
- `sleep(ms: I64) => Void`: 阻塞/异步休眠（取决于是否在异步上下文）。
- `timestamp() => I64`: 获取自 Unix 纪元以来的纳秒数。
- `Duration`: 结构体，表示时间间隔。

---

## 6. 数据结构扩展 (collections)

虽然 `List` 和 `Dict` 是语言内置类型，但标准库提供额外的实用工具。

- `List<T>.push(this: List<T>, item: T) => Void`: 向列表末尾添加元素。
- `List<T>.pop(this: List<T>) => T?`: 移除并返回列表末尾元素。
- `List<T>.shift(this: List<T>) => T?`: 移除并返回列表开头元素。
- `List<T>.unshift(this: List<T>, item: T) => Void`: 向列表开头添加元素。
- `List<T>.sort(this: List<T>, cmp: (T, T) => I32) => Void`: 就地排序。
- `List<T>.filter(this: List<T>, pred: (T) => Bool) => List<T>`: 过滤并返回新 List。
- `Dict<K, V>.keys(this: Dict<K, V>) => List<K>`: 获取所有键。

---

## 7. 外部链接与动态切换 (Dynamic Linkage)

标准库使用条件编译或链接策略，根据编译目标动态绑定底层符号：
- **Native 编译 (Linux/macOS/Windows)**：`*` 映射到标准 `libc` 符号。
- **WASM 编译 (WASI)**：`*` 映射到 `wasi-libc` 提供的 WASI 接口。

### 平台差异处理
对于 WASI 无法提供的能力（如进程派生 `fork`、特定的信号处理等）：
- **API 层面**：依然保留接口以维持源码级兼容。
- **运行层面**：在 WASI 目标下，此类接口的桩实现（Stub）将执行 `panic("Capability not supported on WASI target")`。

---

## 8. 设计准则
1. **值语义优先**：除 `this` 引用外，API 应倾向于返回新值或 Blob，利用 Arena 自动管理生命周期。
2. **WASI 兼容**：确保所有文件系统和系统接口的 API 在 WASM 环境下能够通过 WASI 实现完美运行。
3. **零分配开销**：在可能的情况下，避免在 Arena 之外进行不必要的堆分配。
