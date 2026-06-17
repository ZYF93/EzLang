# EzLang 语言规格说明书

EzLang 是一门以表达式为中心、采用值语义为主的系统编程语言。它支持强类型、泛型、内置结构体、可选类型、联合类型、元编程与 Flow 并发运行时，并结合 Arena 内存模型实现高效内存管理与高性能。

## 1. 语言概览与基础规则

### 语法
```ez
// 单行注释
/* 块注释 */
let a = 1; // 语句由 ; 分隔，表达式可以直接作为语句使用
```

### 语义说明与规范
* **区分大小写**。
* 标识符、关键字、类型名不允许包含空白字符。
* **关键字**：`let`, `const`, `static`, `struct`, `type`, `declare`, `loop`, `break`, `continue`, `import`, `export`, `from`, `match`, `catch`, `throw`, `flow`, `parallel`, `rp`, `wp`, `typeof`, `return`, `in`, `for`, `as`, `extern`。
* **保留词法单元**：基本类型名 `I8`, `I32`, `I64`, `U8`, `U32`, `U64`, `F32`, `F64`, `Str`, `Bool`, `Void`、复合类型构造名 `Vec`, `List`、布尔字面量 `true` / `false`、目标平台名 `linux`, `macos`, `windows`, `android`, `ios`, `emcc` 也是固定词法单元，不能作为普通标识符使用。`Dict`、`Date`、`Error`、`Blob`、`Meta` 是编译器预声明类型名。
* **命名规范**：类型名应以大写字母开头（如 `User`, `Result`）；变量名可由小写字母、下划线或 `$` 开头（如 `user`, `_count`, `$state`）。

### LLVM 映射
* 基础语法、词法解析与命名检查在编译前端完成，无直接运行时的 LLVM 映射。

---

## 2. 类型系统与泛型

### 语法
```ez
// 基本类型与可选、联合类型
struct User { name: Str; }
let user = User(name = "Ada");
let a: I32? = 10;
let value: I32 | Str = "hello";
let weakUser: #User = #user;

// List (动态数组) 与 SIMD 向量
let arr: User[]?;                    // 动态数组（List）
let arr2: User[] = [];               // 初始化空数组
let listType = typeof User[]         // 返回 List 类型
let vec: Vec<I32>[4] = Vec[1, 2, 3, 4];

// 类型别名与泛型结构体
type Point = { x: I32; y: I32; }
struct Result<T> { ok: T; err: Str; }

// Dict类型与动态键
type Shape = {
    name: Str;
    [dynamic: Str]: Str // 动态键声明：[键名: 键类型]: 值类型
}
let dictType = typeof { prop: I32 = 1 } // 返回 Dict 类型

// 字面量初始化与自动形状推断
let s: Shape = {
    name = "Square";
    side = "10"
}
const a_obj = { props: I32 = 1 } // 显式类型指定
const b_obj = { x = 10, y = 20 } // 自动推断为 { x: I32; y: I32 }
const keyword_key = { "type": Str = "I32" } // 关键字只能写成字符串 key

// 类型扩展
type Named = { name: Str }
type UserShape = {
    ...Named;
    age: I32
}

// 泛型结构体与方法
struct Pair<T, U> {
    first: T
    second: U
    swap = (this: #Pair<T, U>) => Pair<U, T>(first = this.second, second = this.first)
}
let p = Pair<I32, Str>(first = 42, second = "hello")
let swapped = p.swap()  // Pair<Str, I32>
let p2 = Pair(first = 42, second = "s")  // 自动推断为 Pair<I32, Str>

// 泛型函数
const identity = <T>(value: T) => value
let num = identity<I32>(42)
let str = identity<Str>("world")
let inferred = identity(42)  // 推断为 I32
```

### 语义说明与规范
* **基本类型**：数值类型（`I8`, `I32`, `I64`, `U8`, `U32`, `U64`, `F32`, `F64`），基础类型（`Str`, `Bool`, `Void`）。
  * `Str` 表示 UTF-8 字符串，按值传递。
  * `Void` 仅用于函数返回类型，不能用作变量类型。
* **复合类型**：
  * List 数组：所有数组均为动态数组。支持 `List<Type>`，语法上可以直接使用 `Type[]`。
    可以使用 `typeof Type[]` 语法来显式获取 `List` 类型。
  * 向量：`Vec<Type>[N]`（SIMD 向量，N 为 2, 4, 8, 16，Type 为数值类型）。它表示寄存器内的 SIMD 向量。
  * 函数类型：`(name: Type, ...) => ReturnType`。函数值按闭包值处理，可保存普通函数、匿名函数、柯里化结果和捕获外层变量的函数。
  * 可选类型：`Type?`。底层为 `Option<T>`，访问时使用 `expr?` 或强制拆包 `Type! expr`。
  * 弱引用类型：`#Type`。`#expr` 生成指向 `expr` 的弱引用值，语义上表示“可能因 Arena 生命周期结束而失效的 Type 引用”。弱引用按 `Type` 透明使用：`#var.field`、`#var.method()` 与 `var.field`、`var.method()` 写法一致；判空使用 `typeof ref == Void`。
  * 联合类型：`Type1 | Type2`。必须通过模式匹配或类型检查区分具体分支。
* **类型别名与形状匹配**：
  * 使用 `type Alias = { ... }` 定义的固定形状会记录字段集合。结构体值只要包含形状要求的字段且字段类型兼容，即可赋给该形状别名。
  * 对象字面量在有形状期望类型时会按字段名校验并生成对应静态布局，例如 `let s: Shape = { name = "Square"; side = "10" }`。
  * `Dict` 类型（字典）可通过字面量 `{ prop: Type = value }`、`{ prop = value }` 或动态键 `{ [expr] = value }` 创建，支持固定字段校验和动态键类型声明；但普通 `Dict` 变量不会自动转换成固定形状结构体。
  * 裸字段名和裸字典 key 必须是普通变量标识符；关键字、保留类型名或包含特殊字符的键必须写成字符串 key，如 `{ "type": Str = "I32" }`。动态表达式 key 使用 `[expr] = value`。
  * 可以使用 `typeof { prop: Type = value }` 语法来获取对应的 `Dict` 类型。
* **类型扩展**：`...BaseType` 将基础形状的字段展开并平铺到当前定义中。
* **泛型系统**：
  * 允许类型参数化实现代码复用，支持多类型参数 `<T, K>`。
  * 编译器支持局部类型推断，上下文足够时可省略显式类型参数（如局部变量与函数调用）。
  * 类型参数在编译时单态化，生成独立代码，无运行时开销。

### LLVM 映射
* 无符号类型映射为相应无符号 LLVM 整数。
* `Type[]` / `List<Type>` 映射为分页数组 ABI：`{ Type** pages, i64 length, i64 capacity, i64 page_count }`，索引时先按固定页大小定位页，再访问页内元素。
* `Vec<Type>[N]` 映射为 LLVM `<N x Type>`。
* 函数类型在 EzLang 内部映射为闭包值：`{ invoke, env }`。`invoke` 是带环境指针的调用入口，`env` 保存捕获环境；传给 `declare` 外部 C ABI 时，零捕获普通函数可降低为 C 函数指针。
* 可选类型映射为 `{ i1 has_value, T value }`。
* 弱引用映射为 `{ i1 ok, T* ptr }`。语言层不暴露 `.ok/.value` 包装字段，字段访问和方法调用会直接解到内部 `T`；`typeof ref == Void` 映射为检查 `ok` 位。当前编译器已提供类型、访问与调用 ABI 表示，运行时 Arena 销毁后的统一失效标记仍按运行时能力逐步接入。
* 联合类型映射为带 tag 的变体结构。
* 泛型通过单态化实现，每个具体类型实例在编译时生成独立 LLVM 函数或类型替换。
* `Dict` 类型映射为哈希表。

---

## 3. 结构体、组合与内置对象

### 语法
```ez
// 结构体定义与继承展开
struct Person {
    name: Str = "default";
    id: I32;
    say = (this: #Person): Str => { return this.name; };
}

struct User {
    ...Person;
    age: I32 = 0;
}

// 展开实例化与命名初始化
let user = User(name = "s", id = 1);
let user2 = User(id = 2); // name 使用默认值
let user3 = User(...user, age = 20);

// 内置结构体：Date, Error, Blob, Meta<T>
struct Date {
    timestamp: I64;

    getYear(this: #Date) => I32;
    getMonth(this: #Date) => I32;
    getDay(this: #Date) => I32;
    getHour(this: #Date) => I32;
    getMinute(this: #Date) => I32;
    getSecond(this: #Date) => I32;

    add(this: #Date, year: I32?, month: I32?, day: I32?, hour: I32?, minute: I32?, second: I32?) => Void;
    sub(this: #Date, year: I32?, month: I32?, day: I32?, hour: I32?, minute: I32?, second: I32?) => Void;

    format(this: #Date, fmt: Str) => Str;
}

struct Error {
    code:    I32;    // 正值为业务错误，负值为系统错误（见 stdlib ErrCode 常量）
    message: Str;
    file:    Str;
    line:    I32;
    column:  I32;
    trace:   Str;

    toString(this: #Error) => Str;
}

struct Blob {
    data: *U8;
    size: I64;

    get(this: #Blob, index: I64) => U8;
    slice(this: #Blob, start: I64, len: I64) => Blob;
}

struct Meta<T> {
    value: T;
    getter: () => T;
    setter: (value: T) => Void;
    t: Str;
    name: Str;
}
```

### 语义说明与规范
* **结构体基础**：定义支持 `struct Name<T> { ...Base?; field: Type = default?; method = (this: #Type, args...) => expr?; }`。支持名称参数初始化与默认字段值。结构体使用静态布局。
* **组合与复用**：`...Base` 将基础结构体字段平铺到当前结构体开头，实现布局复用。实例化时复制基础结构的内存并写入新增字段。
* **类型检查与方法**：`typeof` 返回编译器为类型名生成的稳定 `I32` TypeID；对弱引用执行 `typeof ref == Void` / `typeof ref != Void` 时会检查弱引用的有效位。结构体实例本身不额外存储 TypeID 字段。方法会编译为 `Struct_method` 形式的独立函数并登记到结构体方法表；对象方法调用会把接收者的弱引用作为第一个 `this` 参数传入，直接调用时可显式写 `method(this = #value)`。
* **内置结构体与内置类型**：提供语言层面的通用数据结构封装。这些类型由编译器预声明，不需要从标准库导入。
  * `Date` 提供时间戳存储、基础的时间加减与格式化。
  * `Error` 封装错误代码、信息、抛出点文件/行/列和轻量调用栈片段，方便统一异常处理与诊断输出。
  * `Blob` 提供二进制块长度和底层指针访问能力。
  * `Dict<K, V>` 是字典的运行时承载类型，用户通常通过 `{ key: Type; ... }` 形状或 `Dict<K, V>` 使用；`std/collections` 暴露 `dictHas`、`dictKeys` 等扩展函数，首参为 `this: #Dict<K, V>`。
  * `List<T>` / `T[]` 是动态数组类型；`std/collections` 暴露 `listPush`、`listLen`、`listMap` 等扩展函数，首参为 `this: #List<T>`。
  * `Meta<T>` 是装饰器变量的元对象类型，保存原始值、读写拦截闭包、类型名和变量名；类型名字段使用 `t`，避免把关键字 `type` 暴露为字段名。

### LLVM 映射
* 结构体映射为平铺的 LLVM 结构体类型。
* 展开实例化时，先 `memcpy` 基础实例，再 `store` 新字段。
* 方法不写入实例字段；编译器在编译期维护结构体方法表，方法体映射为独立 LLVM 函数，`obj.method(...)` lowering 为对应函数调用并补入 `this`。
* 内置结构体映射：
  * `Date` 可优化为单一 timestamp 型（通常为 i64）。
  * `Error` 映射为 `{ i32 code, i8* message, i8* file, i32 line, i32 column, i8* trace }`。
  * `Blob` 映射为 `{ i8* data, i64 size }`。
  * `Meta<T>` 映射为 `{ T value, Closure<T()> getter, Closure<Void(T)> setter, i8* t, i8* name }`。

---

## 4. 变量、作用域与内存模型

### 语法
```ez
struct User { name: Str }
let count: I32 = 10
rp let cache: User[] = []  // 读优先锁
wp let queue: I32[] = []   // 写优先锁
let ordered: I32 = 0       // 默认顺序锁
const max: I32 = 100
static config: Str = "release"
let copy = count
```

### 语义说明与规范
* `let`：可变局部变量；`const`：只读局部变量。两者均存储在当前 Arena 空间。
* `rp let variable = ...`：声明读优先变量锁。有读请求时优先读取；写请求等待当前读取完成。写请求兜底等待时间为 1ms，超过 1ms 后，该写请求排到后续读请求之前，避免写长期饥饿。
* `wp let variable = ...`：声明写优先变量锁。有写请求时优先写入；读请求可以饥饿。
* 顺序锁：不加 `rp` / `wp` 前缀的普通变量默认使用顺序锁，按照读写请求到达顺序依次读写。
* `static`：全局静态变量，生命周期贯穿程序。
* **值语义**：赋值默认是值语义，`a = b` 会进行全量拷贝。函数参数默认按值传递（除 `this` 使用引用语义外）。
* **Arena 内存模型**：
  * 每个作用域对应一个 Arena 游标。临时分配在连续内存区完成，作用域结束时回退游标（rollback arena cursor）。语言层不提供显式 `free`。
  * 跨作用域返回时，值被复制至父级 Arena 游标所管理的空间，不会出现悬垂引用。
  * 线程独占 Arena，配合值语义实现无锁并发。自动按 `alignof(T)` 对齐。
  * Arena 会智能的调度内存，例如重新赋值时如果新值需要的内存比旧值大，则会重新分配一块新的内存，并将旧内存标记为可重新分配。

### LLVM 映射
* 局部变量映射为 `alloca` 或 Arena 内存地址。拷贝使用 `llvm.memcpy`。
* `static` 变量映射为全局常量或全局可变区。
* Arena 使用线程本地底层缓冲区、容量与游标管理；容量不足时按需扩容，作用域结束仅需移动游标，无需逐个析构对象。
* 变量锁当前会在语义阶段记录 `rp`/`wp` 策略，并在 LLVM IR 中为直接变量读写生成 `__ezrt_lock_read_*` / `__ezrt_lock_write_*` hook；原生运行时提供按变量名索引的读写锁，覆盖顺序锁、读优先锁和写优先锁的基础调度。`rp` 写者等待超过 1ms 后会阻止后续读者继续插队，避免长期饥饿。
* Arena 分配器会根据类型的 `alignof` 自动内存对齐，确保 SIMD 和大结构体符合目标架构要求。

---

## 5. 函数与上下文绑定

### 语法
```ez
// 默认参数与显式返回
const fn = (a: I32, b: I32 = 1) => a + b
const process = (x: I32) => {
    return x * 2
}
const walk = (x: I32): I32 => {
    (x > 10) ? {
        return x
    }
    return walk(x = x + 1)
}

// 柯里化与参数占位
let addTwo = fn(a = 2, b = ?)

// 捕获闭包
const makeAdder = (base: I32): (x: I32) => I32 => {
    return (x: I32): I32 => {
        return base + x
    }
}
let add10 = makeAdder(base = 10)
let value = add10(x = 5)
```

### 语义说明与规范
* 显式声明 `this` 时必须使用弱引用类型 `#Type`。`obj.fn()` 会自动把 `#obj` 传入 `this`，用户不需要显式填写；直接调用函数时可写 `fn(this = #obj)`。普通变量仍使用值语义。
* 函数调用支持位置参数和命名参数混用（如 `fn(1, c = 3)`），位置参数需位于具名参数之前。
* 形参可声明默认值，调用时省略该参数即使用默认值。
* 函数体使用 `{ ... }` block 时，必须通过 `return` 显式返回值，最后一个表达式不会隐式作为返回值。
* 匿名函数可以捕获当前作用域内使用到的局部变量，生成闭包值。捕获环境存放在当前 Arena 中，因此闭包应遵循普通 Arena 生命周期规则，不应在捕获环境已结束后跨作用域长期保存。
* `?` 占位符支持部分应用与柯里化，生成等待剩余参数的闭包。

### LLVM 映射
* 具名参数在编译期重排以生成标准 `call`。
* 函数值生成闭包结构体 `{ invoke, env }`；匿名函数和柯里化结果在 Arena 中存储捕获的变量，调用时先取出 `invoke` 与 `env` 再执行。

---

## 6. Flow 并发运行时

### 语法
```ez
from "std/io" import { print }

declare const fetchA: () => I32
declare const fetchB: () => I32
declare const fetchC: () => I32
declare const fetch: () => I32

const ret = flow {
    const a = fetchA()
    const b = fetchB()
    const ret2 = race(
        pl = [
            () => fetchA(),
            () => fetchB()
        ],
        timeout = 3000
    )
    const p = parallel {
        const c = fetchC()
        return c * 2
    }
    const err = catch {
        fetch()
    }
    (typeof err & Error == Error) ? print(msg = err.message)
    return a + b + ret2 + p
}
```

### 语义说明与规范
* **flow**：`flow { ... }` 为并发调度作用域。flow 不改变程序的顺序语义。flow 内代码在语义上严格按源码顺序执行，但 runtime 可对无依赖阻塞操作进行调度优化，且调度不得改变可观察行为。
* **当前实现**：编译器会记录 flow/parallel/suspend point 元数据，并在 LLVM IR 中生成可链接的 `__ezrt_flow_*`、`__ezrt_parallel_*`、`__ezrt_sleep`、`__ezrt_race_i32`、`__ezrt_task_start_i32` / `__ezrt_task_join_i32` hook。`__ezrt_sleep` 会真实挂起当前执行点；`race(pl = [...], timeout = ...)` 对零捕获 `() => I32` 分支在 native 目标使用 C 任务运行时并发执行，在 emcc 目标使用 `packages/std/emcc/runtime.js` + Asyncify 协程运行时挂起和恢复。`flow` / `parallel` 块内的 `return` 会被捕获为表达式结果，不会提前退出外层函数；嵌套控制流中的 `return` 也参与表达式返回类型推断。
* **阻塞操作**：flow 外部如 `fetch()` 保持用户体感上的同步调用。flow 内部的 `sleep`、`race(pl)`、零捕获 `I32` `parallel` 以及 emcc 下的 `fetch`、TCP/UDP、WebSocket、stdin、文件系统、进程和流式 I/O 会作为 suspend source 挂起后恢复；缺失能力的平台按接口约定返回失败值或继续使用阻塞 syscall，不做 CPU 忙等。
* **parallel 块**：`const ret = parallel { code... return... }` 或 `const ret: I32 = parallel { code... return... }` 在 flow 内、初始化表达式本身就是 `parallel` 块、零捕获且返回 `I32` 时会启动后台任务；读取 `ret` 会等待任务完成，flow 退出前会 join 未读取任务，确保副作用提交。native、Android、iOS 使用 C 任务运行时，emcc 使用 JS 协程运行时；组合表达式、其它返回类型或捕获外层局部变量的场景保持同步协作 lowering。
* **自动依赖等待**：读取 flow 内未完成的 `parallel` 结果会自动 join；当前依赖等待覆盖 native、Android、iOS 与 emcc 的零捕获 `I32` 任务，包括推断类型和显式 `I32` 声明。emcc 标准库 suspend source 通过 Asyncify 恢复 wasm 栈，保持顺序 ABI。
* **flow 返回**：flow 返回前必须保证所有前序语义操作完成，且所有副作用已提交。
* **race 函数**：native、Android、iOS 与 emcc 目标并发运行 `pl` 中的零捕获 `() => I32` 分支，返回首个完成值并取消或忽略其它分支；`timeout` 到期时返回零值并标记超时槽。异常通过运行时异常槽传回外层 `catch`。捕获闭包和非 `I32` 返回值使用同步协作 fallback。
* **cancel**：取消不会立即终止同步代码。取消仅中断 IO、sleep、timer、wait 等 suspend source。底层 suspend source 被取消时，`throw Error(code = errCancel, message = "操作已取消")` 并沿同步调用栈传播；可在 `catch {}` 中通过 `err.code == errCancel` 判断并特殊处理。
* **非阻塞同步代码**：普通同步 CPU 代码不会被中断。
* **副作用一致性**：runtime 不允许改变副作用顺序、锁语义、可观察行为。

### LLVM 映射
* **当前**：lowering 为 runtime hook + flow/parallel 返回值槽；`sleep`、`race(pl)` 和 flow 内零捕获 `I32` `parallel` 已接入原生任务运行时，Android/iOS 复用同一 C runtime，emcc 通过 Asyncify JS 协程 runtime 提供可挂起行为。emcc 标准库中的 `sleep`、HTTP `fetch`、TCP/UDP、WebSocket `wsConnect` / `wsRecv`、stdin、fs、process 和 stream I/O 都带 Asyncify 元数据；CLI 会自动追加 `-sASYNCIFY`。后续可继续以 JSPI 或 wasm pthread 替换 emcc backend，而不改变 EzLang 语法。
* **目标**：后续可继续把 native 阻塞 I/O 替换为状态机、平台等待源（epoll、io_uring、kqueue、timerfd 等）、结果存储、等待唤醒与更完整的捕获闭包调度。

---

## 7. 流程控制

### 语法
```ez
from "std/fmt" import { toString }
from "std/io" import { print }

// 循环与范围
loop i in 0...10 { 
    print(msg = toString<I32>(value = i))
}

// 块条件语句
let x = 5
(x > 0) ? print(msg = "positive")
(x < 0) ? {
  print(msg = "negative")
} : (x == 0) ? {
  print(msg = "zero")
}

// 模式匹配
let i = 0
match {
    (i == 0) ? i = 100,
    (i > 0) ? { (i > 10) ? continue; i = i - 1; },
    (i > 0) ? { i = i + 1; break; },
    (true) ? { i = i - 100; }
}

// 异常捕获
const err = catch {
    throw Error(code = 1, message = "hello")
}
(typeof err & Error == Error) ? print(msg = err.message)
```

### 语义说明与规范
* **条件表达式**：`condition ? expr : expr`。既是表达式也是流程控制，不使用 `if/else`。`condition ? expression` 或 `condition ? { block }` 是条件语句，条件为真执行，否则跳过。
* **loop**：`0...10` 表示左闭右开区间 `[0, 10)`。
* 块表达式 `{ ... }` 返回值为 `Void`。
* **match**：从上到下依次求值，命中分支执行后默认继续检查下一分支，除非显式 `break`。
* **continue**：在 `loop` 中跳到下一轮；在 `match` 中跳过当前分支剩余语句并继续检查下一分支。
* **break**：退出当前 `loop` 或 `match`。
* **throw**：写入 `Error` 异常槽并跳转到最近的 `catch {}` 出口；没有活动 `catch` 时会输出未捕获异常诊断并以退出码 1 终止。同步函数调用边界会检查异常槽并继续向外传播。
* **catch**：返回块内或被调用函数传播出的 `throw expr` 异常值；没有捕获到异常时返回零值 `Error`（`code = 0`）。`Error` 会携带抛出点文件、行、列和轻量调用栈片段，可通过 `err.file`、`err.line`、`err.column`、`err.trace` 读取。

### LLVM 映射
* 循环映射为 `br` 与 `phi` 节点结构。
* 条件选择映射为 `phi` 节点或分支跳转。

---

## 8. 运算符、表达式与 SIMD

### 语法
```ez
// 算术、位运算与逻辑
let a: I32 = 10; let b: I32 = 3
let sum = a + b; let rem = a % b
let logic = (a > b) && !(a == b)
let shiftBy: U32 = 1
let shift = a << shiftBy
let bit = a & 0b1111

// 复合赋值
a += 5
a &= 0b1111

// SIMD 向量语法
let v1: Vec<I32>[4] = Vec[1, 2, 3, 4]
let v2: Vec<I32>[4] = Vec[5, 6, 7, 8]
let vSum = v1 + v2
let scaled = v1 * 2  // 标量自动广播
let masked = (v1 < v2) ? v1 : v2
```

### 语义说明与规范
* **算术与位运算**：支持 `+`, `-`, `*`, `/`, `%` 及 `&`, `|`, `^`, `<<`, `>>`。整数除法向下取整。浮点运算遵循 IEEE 754。无符号类型的除法、取余与右移分别生成无符号运算，右移填充零；有符号类型右移使用算术右移。移位右操作数必须为无符号类型。
* **逻辑与比较运算**：支持 `&&`, `||`, `!` 与 `==`, `!=`, `<`, `>`, `<=`, `>=`。逻辑运算支持短路求值。结构体、可选与联合值支持 `==`/`!=`，按同布局字段递归比较；其中 `Str` 字段沿用指针相等语义，按内容比较请使用标准库字符串函数。聚合类型不支持 `<`, `>`, `<=`, `>=`。
* **复合赋值**：如 `+=`, `<<=` 等价于展开运算。当前实现对裸变量、结构体字段和数组/List 索引左值生成加载、运算、存储序列，并避免重复求值字段所属对象或索引表达式。
* **优先级**：`!` > `*`, `/`, `%` > `+`, `-` > `<<`, `>>` > `&` > `^` > `|` > 比较 > `&&` > `||`。位运算 `&` 优先级高于比较运算 `==` 但低于移位。建议显式加括号以避免歧义。
* **SIMD 语义**：`Vec<Type>[N]` 操作逐元素并行执行。向量长度必须匹配。标量与向量混合运算时，标量自动广播成等长向量后再计算；向量比较生成同宽布尔 mask。

### LLVM 映射
* 基本运算符映射为相应 LLVM 指令（如 `add`, `sub`, `icmp`, `fcmp`, `shl`, `ashr`/`lshr`, `and`, `sdiv`/`udiv`, `srem`/`urem` 等）。
* 逻辑运算映射为条件分支和 `phi` 节点，实现短路求值。
* 复合赋值映射为加载、运算、存储序列。
* 向量类型映射为 LLVM 向量类型（如 `<4 x i32>`），运算映射为对应的 SIMD 指令（如 `add <4 x i32>`、`icmp <4 x i32>`）；向量/标量混合运算会先用 `insertelement` 广播标量。

---

## 9. 模块系统与外部链接

### 语法
```ez
// 模块导入导出
from "./std.ez" import {print as log}
export let x = 1

// extern 语法：按目标平台引用外部 ABI 库
// 支持：静态库(.a/.lib), 动态库(.so/.dylib/.dll), 目标文件(.o/.bc), LLVM IR(.ll), 框架(.framework)
// 所有目标平台均链接此库
extern "./libs/libcrypto.a"
// 仅 linux 目标链接
extern "./libs/libssl.so" for linux
// 多个目标平台
extern "./libs/win32.lib" for windows
// Android/iOS 各自的库
extern "./libs/android/libjni.a" for android
extern "./libs/ios/objc.framework" for ios
// WebAssembly 导入 JS 模块
extern "./js/bindings.js" for emcc
// 链接 LLVM IR 模块或字节码
extern "./runtime.ll"
extern "./runtime.bc" for macos

// 声明外部库符号（与 extern 配合使用）
// 所有外部符号必须通过 declare 显式声明，支持类型安全的 C ABI 调用
declare const crypto_hash: (data: Blob, len: I64) => Blob
declare const ssl_connect: (host: Str, port: I32) => I32
declare const curl_easy_init: () => Blob
declare static version: Str
```

### 语义说明与规范
* **import / export**：编译期导入，将外部 EzLang 模块的导出项引入当前作用域；**export**：导出符号，将项暴露给其他模块。
  * 仅支持 `.ez` 源文件导入，不支持直接导入二进制目标文件。
* **extern**：引用外部 ABI 库或编译产物，支持按编译目标平台按需链接。
  * 无 `for` 子句时，所有目标平台均链接该库。
  * `for target` 子句指定仅在编译该目标时链接，支持 `linux`, `macos`, `windows`, `android`, `ios`, `emcc`。
  * 支持格式：静态库 (`.a`, `.lib`), 动态库 (`.so`, `.dylib`, `.dll`), 目标文件 (`.o`), LLVM IR (`.ll`), LLVM 字节码 (`.bc`), 框架 (`.framework`), JS 模块 (`.js` for emcc)。
  * `emcc` 目标导入 JS 模块时，编译时自动转换为 Emscripten 绑定。
* **declare**：声明外部库符号，用于类型检查和链接时符号解析。
  * 可声明函数、全局变量、静态变量。
  * `declare` 应配合至少一个当前目标可用的 `extern` 使用；没有关联 `extern` 时编译器会给出链接诊断。
  * 编译器不预扫描二进制库中的符号表，符号是否真实存在由后端链接器在链接阶段验证。
  * 所有外部符号必须显式声明，支持 C ABI 兼容的外部库调用。
* EzLang 按入口文件的顶层语句顺序执行；不要求用户显式定义 `main` 函数。若源码中已定义 `main`，宿主入口沿用该函数，文件内其它函数仍需显式调用。

### LLVM 映射
* EzLang 模块导入通过编译时符号解析与合并实现。
* `extern` 库路径传递给 LLVM 链接器，`for target` 子句在编译期根据目标平台过滤。
* `declare` 生成 LLVM `external global` 或 `declare` 声明，使用 C ABI 调用约定。
* `extern` 和 `declare` 配合实现零开销外部库链接，无运行时性能损耗。

---

## 10. 元编程、语法糖与安全机制

### 语法
```ez
from "std/io" import { print }

// 元编程：装饰器
const log = (this: #Meta<I32>): Void => {
    this.getter = (): I32 => {
        return this.value + 10
    }
    this.setter = (v: I32): Void => {
        print(msg = "writing...")
        this.value = v
    }
}
@log let x = 1
x = 2 // 触发拦截打印

// 标记语法与语法糖
struct Node {
    id: I32;
}
const div = (id: I32): Node => {
    return Node(id = id)
}
const text = (color: Str, children: (Str | Node | I32)[]): Node => {
    return Node(id = 1)
}
let ui = <text color="blue">
    "Welcome"
    <div id=1 />
    {1+2}
</text> // 等同于 text(color = "blue", children = ["Welcome", div(id = 1), 1+2])

const add = (a: I32, b: I32): I32 => {
    return a + b
}
let val = 10 -> add(a = %, b = 5) // 管道语法，等同于 add(a = 10, b = 5)
let name = "EzLang"
let msg = "Hello {{name}}"        // 字符串插值，当前只支持简单 Str 变量名

// 安全机制：类型断言与运行时检查
declare const malloc: (size: I32) => Blob
type User = Blob
let b: Blob = malloc(size = 10)
let user = User! b
let err = Error(code = 1, message = "boom")
let isError = typeof err & Error == Error
```

### 语义说明与规范
* **元编程与装饰器**：`@Dec` 将顶层变量包装为 `Meta<T>` 并在模块初始化阶段调用装饰器函数。装饰器函数接收 `Meta<T>` 或 `this: #Meta<T>`，可读写 `value`, `getter`, `setter`, `t`, `name`。
  * `value` 是被装饰变量的真实存储。
  * `getter` 是 `() => T` 闭包；未设置时读取直接返回 `value`。
  * `setter` 是 `(value: T) => Void` 闭包；未设置时写入直接更新 `value`。
  * `t` 与 `name` 是编译器生成的类型名和变量名，供诊断、日志和元编程使用。
  * 装饰器可以是泛型函数，编译器会按被装饰变量类型单态化。
* **标记语法**：XML 风格标记语法只会 lowering 为普通函数调用。作用域内必须存在同名工厂函数，编译器会将属性按具名参数传入，并把子节点打包为 `children` 数组；若不存在同名工厂函数、属性类型不匹配或 `children` 类型不匹配，语义分析会直接报错。
* **管道与插值**：管道 `->` 配合 `%` 占位符重写为命名参数调用（如 `a -> fn(x = %)` 重写为 `fn(x = a)`）；字符串插值使用 `{{name}}` 形式，当前只支持简单变量名，且变量类型必须是 `Str`，不支持 `{{a + b}}` 这类内联表达式。
* **类型安全机制**：
  * `Type! expr`：无检查的类型断言，适用于强制拆包或位级重解释。
  * `typeof`：返回编译器为表达式或类型名生成的稳定 `I32` TypeID；对弱引用与 `Void` 的相等/不等比较会 lowering 为弱引用有效位检查。

### LLVM 映射
* 装饰器生成 `Meta<T>` 结构体，`getter`/`setter` 使用闭包槽保存；读写被装饰变量时，如果闭包入口不为空则调用闭包，否则直接读写 `value`。
* 标记语法必须找到同名工厂函数并生成普通 `call` 指令，属性按函数参数名重排，子节点通过当前数组/List ABI 传给 `children`；无工厂函数或参数类型不匹配时是编译错误。管道语法在编译前端翻译展开；字符串插值把静态文本片段和 `Str` 变量片段生成为内存复制拼接逻辑。
* `Type! expr` 映射为位级重解释（`bitcast`）或 `load` 操作。
* `typeof` 映射为稳定 TypeID 常量；`typeof weakRef == Void` / `typeof weakRef != Void` 映射为读取弱引用 `{ ok, ptr }` 的 `ok` 位。
