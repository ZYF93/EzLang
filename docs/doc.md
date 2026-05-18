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
* **关键字**：`let`, `const`, `static`, `struct`, `type`, `declare`, `loop`, `break`, `continue`, `import`, `export`, `from`, `match`, `catch`, `throw`, `flow`,  `typeof`
* **命名规范**：类型名应以大写字母开头（如 `User`, `Result`），变量名应以小写字母开头（如 `user`, `count`）。

### LLVM 映射
* 基础语法、词法解析与命名检查在编译前端完成，无直接运行时的 LLVM 映射。

---

## 2. 类型系统与泛型

### 语法
```ez
// 基本类型与可选、联合类型
let a: I32? = 10;
let value: I32 | Str = "hello";

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
    swap = (this: Pair<T, U>) => Pair<U, T>(first = this.second, second = this.first)
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
  * 函数类型：`(name: Type, ...) => ReturnType`。
  * 可选类型：`Type?`。底层为 `Option<T>`，访问时使用 `expr?` 或强制拆包 `Type! expr`。
  * 联合类型：`Type1 | Type2`。必须通过模式匹配或类型检查区分具体分支。
* **类型别名与鸭子类型**：
  * 使用 `type Alias = { ... }` 定义的形状采用鸭子类型（Duck Typing）进行验证。任何结构（包括 `Struct` 或 `Dict`）只要包含形状要求的字段，即可视为匹配该类型。
  * `Dict` 类型（字典）可通过字面量 `{ prop: Type; ... }` 创建，支持固定字段和动态键。
  * 支持 `{ prop = value }` 的推断初始化或 `{ prop: Type = value }`。
  * 可以使用 `typeof { prop: Type = value }` 语法来获取对应的 `Dict` 类型。
* **类型扩展**：`...BaseType` 将基础形状的字段展开并平铺到当前定义中。
* **泛型系统**：
  * 允许类型参数化实现代码复用，支持多类型参数 `<T, K>`。
  * 编译器支持局部类型推断，上下文足够时可省略显式类型参数（如局部变量与函数调用）。
  * 类型参数在编译时单态化，生成独立代码，无运行时开销。

### LLVM 映射
* 无符号类型映射为相应无符号 LLVM 整数。
* `Type[]`（List）映射为 `{ i64 len, i64 cap, Type* data }`。
* `Vec<Type>[N]` 映射为 LLVM `<N x Type>`。
* `Fn` 映射为函数指针。
* 可选类型映射为 `{ i1 has_value, T value }`。
* 联合类型映射为带 tag 的变体结构。
* 泛型通过单态化实现，每个具体类型实例在编译时生成独立 LLVM 函数或类型替换。
* `Dict` 类型映射为哈希表。

---

## 3. 结构体、组合与内置对象

### 语法
```ez
// 结构体定义与继承展开
struct Person {
    name: Str = "default"
    id: I32
    say = (this: User) => this.name
}

struct User {
    ...Person
    age: I32 = 0
}

// 展开实例化与命名初始化
let user = User(name = "s", id = 1)
let user2 = User(id = 2) // name 使用默认值
let user3 = User(...user, age = 20)

// 内置结构体：Date, Error, Blob
struct Date {
    timestamp: I64

    getYear = (this: Date) => I32
    getMonth = (this: Date) => I32
    getDay = (this: Date) => I32
    getHour = (this: Date) => I32
    getMinute = (this: Date) => I32
    getSecond = (this: Date) => I32

    add(this: Date, year: I32?, month: I32?, day: I32?, hour: I32?, minute: I32?, second: I32?) => Void
    sub(this: Date, year: I32?, month: I32?, day: I32?, hour: I32?, minute: I32?, second: I32?) => Void

    format = (this: Date, fmt: Str) => Str
}

struct Error {
    code:    I32    // 正值为业务错误，负值为系统错误（见 stdlib ErrCode 常量）
    message: Str
    data:    Blob?

    toString = (this: Error) => Str
}

struct Blob {
    size: I64
    data: *I8

    get = (this: Blob, index: I64) => I8
    slice = (this: Blob, start: I64, len: I64) => Blob
}
```

### 语义说明与规范
* **结构体基础**：定义支持 `struct Name<T> { ...Base?; field: Type = default?; method = (this: Type, args...) => expr?; }`。支持名称参数初始化与默认字段值。结构体使用静态布局。
* **组合与复用**：`...Base` 将基础结构体字段平铺到当前结构体开头，实现布局复用。实例化时复制基础结构的内存并写入新增字段。
* **类型检查与方法**：每个结构体隐式包含 `I32` 类型标识，用于 `typeof` 和运行时检查。方法是内联函数，`this` 显式绑定到实例。
* **内置结构体**：提供语言层面的通用数据结构封装。
  * `Date` 提供时间戳存储、基础的时间加减与格式化。
  * `Error` 封装错误代码与信息及可选的二进制附加数据，方便统一异常处理。
  * `Blob` 提供二进制块长度和底层指针访问能力。

### LLVM 映射
* 结构体映射为平铺的 LLVM 结构体类型。
* 展开实例化时，先 `memcpy` 基础实例，再 `store` 新字段。
* 方法映射为函数指针字段，初始化时绑定对应函数。
* 内置结构体映射：
  * `Date` 可优化为单一 timestamp 型（通常为 i64）。
  * `Error` 映射为 `{ i32 code, i8* msg, ... }`。
  * `Blob` 映射为 `{ i64 size, i8* data }`。

---

## 4. 变量、作用域与内存模型

### 语法
```ez
let count: I32 = 10
const max: I32 = 100
static config: Str = "release"
let copy = count
```

### 语义说明与规范
* `let`：可变局部变量；`const`：只读局部变量。两者均存储在当前 Arena 空间。
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
* Arena 使用单一底层缓冲区和游标管理，作用域结束仅需移动游标，无需逐个析构对象。
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
```

### 语义说明与规范
* 显式声明 `this`，没有隐式上下文。`obj.fn()` 等价于 `fn(this = obj)`。`this` 总是以引用语义传递，避免结构体拷贝。普通变量使用值语义。
* 函数调用仅支持命名参数（如 `fn(a = 1, b = 2)`），不支持匿名传参。
* 形参可声明默认值，调用时省略该参数即使用默认值。
* 函数体使用 `{ ... }` block 时，必须通过 `return` 显式返回值，最后一个表达式不会隐式作为返回值。
* `?` 占位符支持部分应用与柯里化，生成等待剩余参数的函数。

### LLVM 映射
* 具名参数在编译期重排以生成标准 `call`。
* 柯里化生成闭包结构体，并在 Arena 中存储捕获的变量。

---

## 6. Flow 并发运行时

### 语法
```ez
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
    const err = catch {
        fetch()
    }
    (typeof err & Error == Error) ? print(msg = err.message)
    return a + b + ret2
}
```

### 语义说明与规范
* **flow**：`flow { ... }` 为并发调度作用域。flow 不改变程序的顺序语义。flow 内代码在语义上严格按源码顺序执行，但 runtime 可对无依赖阻塞操作进行调度优化，且调度不得改变可观察行为。
* **阻塞操作**：flow 外部如 `fetch()` 为同步阻塞。flow 内部如 `fetch()` 允许挂起当前执行点并调度其它可运行逻辑。
* **自动依赖等待**：读取未完成阻塞结果时，runtime 自动等待依赖。
* **flow 返回**：flow 返回前必须保证所有前序语义操作完成，且所有副作用已提交。
* **race 函数**：并发运行所有分支，返回首个完成值，自动取消其它分支；`timeout` 超时则取消所有任务并 `throw Error(code = errTimeout, ...)`；`timeout` 不填默认永不超时。
* **cancel**：取消不会立即终止同步代码。取消仅中断 IO、sleep、timer、wait 等 suspend source。底层 suspend source 被取消时，`throw Error(code = errCancel, message = "操作已取消")` 并沿同步调用栈传播；可在 `catch {}` 中通过 `err.code == errCancel` 判断并特殊处理。
* **非阻塞同步代码**：普通同步 CPU 代码不会被中断。
* **副作用一致性**：runtime 不允许改变副作用顺序、锁语义、可观察行为。

### LLVM 映射
* **flow**：lowering 为状态机与调度点。
* **suspend source**：映射为 epoll、io_uring、kqueue、timerfd 等平台等待机制。
* **cancel**：取消底层等待源。

---

## 7. 流程控制

### 语法
```ez
// 循环与范围
loop i in 0...10 { 
    print(msg = i)
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
    throw Error(msg = "hello")
}
(typeof err & Error == Error) ? print(msg = err.msg)
```

### 语义说明与规范
* **条件表达式**：`condition ? expr : expr`。既是表达式也是流程控制，不使用 `if/else`。`condition ? expression` 或 `condition ? { block }` 是条件语句，条件为真执行，否则跳过。
* **loop**：`0...10` 表示左闭右开区间 `[0, 10)`。
* 块表达式 `{ ... }` 返回值为 `Void`。
* **match**：从上到下依次求值，匹配后继续下一条，除非显式 `break`。
* **continue**：跳过当前 match 的后续分支，继续执行下一条。
* **break**：退出当前 `loop` 或 `match`。
* **throw**：抛出异常，会沿同步调用栈传播，直到被 `catch` 捕获或到达程序的顶层，导致程序终止。
* **catch**：用于捕获 `throw` 抛出的异常值。

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
let shift = a << 1
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
* **算术与位运算**：支持 `+`, `-`, `*`, `/`, `%` 及 `&`, `|`, `^`, `<<`, `>>`。整数除法向下取整。浮点运算遵循 IEEE 754。无符号类型右移填充零，有符号类型算术右移。移位右操作数必须为无符号类型。
* **逻辑与比较运算**：支持 `&&`, `||`, `!` 与 `==`, `!=`, `<`, `>`, `<=`, `>=`。逻辑运算支持短路求值。不支持结构体/联合类型直接比较（除非实现相关方法）。
* **复合赋值**：如 `+=`, `<<=` 等价于展开运算，但左操作数只求值一次。
* **优先级**：`!` > `*`, `/`, `%` > `+`, `-` > `<<`, `>>` > `&` > `^` > `|` > 比较 > `&&` > `||`。位运算 `&` 优先级高于比较运算 `==` 但低于移位。建议显式加括号以避免歧义。
* **SIMD 语义**：`Vec<Type>[N]` 操作逐元素并行执行。向量长度必须匹配。标量与向量混合运算时，标量自动广播成等长向量后再计算。

### LLVM 映射
* 基本运算符映射为相应 LLVM 指令（如 `add`, `sub`, `icmp`, `fcmp`, `shl`, `and`, `sdiv`/`udiv`, `srem`/`urem` 等）。
* 逻辑运算映射为条件分支和 `phi` 节点，实现短路求值。
* 复合赋值映射为加载、运算、存储序列。
* 向量类型映射为 LLVM 向量类型（如 `<4 x i32>`），运算映射为对应的 SIMD 指令（如 `add <4 x i32>`）。

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
  * 声明的符号必须在至少一个 `extern` 库中存在，否则链接失败。
  * 所有外部符号必须显式声明，支持 C ABI 兼容的外部库调用。
* EzLang 不存在隐式入口函数，文件内定义的任意函数均需显式调用。

### LLVM 映射
* EzLang 模块导入通过编译时符号解析与合并实现。
* `extern` 库路径传递给 LLVM 链接器，`for target` 子句在编译期根据目标平台过滤。
* `declare` 生成 LLVM `external global` 或 `declare` 声明，使用 C ABI 调用约定。
* `extern` 和 `declare` 配合实现零开销外部库链接，无运行时性能损耗。

---

## 10. 元编程、语法糖与安全机制

### 语法
```ez
// 元编程：装饰器
const log = (this: Meta<I32>) => {
    this.setter = (v: I32) => {
        print(msg = "writing...")
        this.value = v
    }
}
@log let x = 1
x = 2 // 触发拦截打印

// 标记语法与语法糖
let ui = <text color="blue">
    "Welcome"
    <div id=1 />
    {1+2}
</text> // 等同于 text(color = "blue", children = ["Welcome", div(id=1), 1+2])

let val = 10 -> add(a = %, b = 5) // 管道语法，等同于 add(a = 10, b = 5)
let msg = "Hello {{name}}"        // 字符串插值

// 安全机制：类型断言与运行时检查
let b: Blob = malloc(size = 10)
let user = User! b
let isError = typeof err & Error == Error
```

### 语义说明与规范
* **元编程与装饰器**：`@Dec` 将变量包装为 `Meta<T>`。`Meta<T>` 包含 `value`, `getter`, `setter`, `type`, `name`，访问时通过函数指针调用拦截逻辑。
* **标记语法**：XML 风格标记语法被自动翻译编译为普通函数调用与结构体构造表达式。
* **管道与插值**：管道 `->` 配合 `%` 占位符重写为命名参数调用（如 `a -> fn(x = %)` 重写为 `fn(x = a)`）；字符串插值编译为最小内存复制拼接逻辑。
* **类型安全机制**：
  * `Type! expr`：无检查的类型断言，适用于强制拆包或位级重解释。
  * `typeof`：基于结构体头部的 TypeID 进行快速类型判断，返回运行时结构体类型标识或结构体类型，而非类型别名。

### LLVM 映射
* 装饰器生成 `Meta<T>` 结构体，按值传递，拦截逻辑表现为 `call` 指令调用 `getter`/`setter`。
* 标记语法、管道语法在编译前端翻译展开；字符串插值生成相应的内存复制拼接逻辑。
* `Type! expr` 映射为位级重解释（`bitcast`）或 `load` 操作。
* `typeof` 映射为通过结构体内部隐含的 TypeID 进行数值比较。
