# EzLang 语言规格说明书

## 0. 语言概览

EzLang 是一门以表达式为中心、采用值语义为主的系统编程语言。它支持强类型、泛型、内置结构体、可选类型、联合类型、异步与元编程，并结合 Arena 内存模型实现高效内存管理。

### 基本规则
* 注释：`// 单行注释`、`/* 块注释 */`
* 区分大小写
* 标识符、关键字、类型名不允许包含空白字符
* 语句由 `;` 分隔，表达式可以直接作为语句使用

### 关键字
`let`, `const`, `static`, `struct`, `type`, `declare`, `loop`, `await`, `async`, `break`, `continue`, `import`, `export`, `from`, `match`, `catch`, `throw`

---

## 1. 类型系统

### 1.1 基本类型
* 数值类型：`I8`, `I32`, `I64`, `U8`, `U32`, `U64`, `F32`, `F64`
* 基础类型：`Str`, `Bool`, `Void`
* 内置结构体：`Date`, `Error`, `Blob`

### 1.2 复合类型
* 数组：`Type[]`（动态数组），`Type[n]`（定长数组）
* 函数类型：`(name: Type, ...) => ReturnType`
* 可选类型：`Type?`
* 联合类型：`Type1 | Type2`
* 泛型：`<T, K>`
* 类型别名：`type Alias = Shape`

### 1.3 命名规范
* 类型名应以大写字母开头，如 `User`, `Result`
* 变量名应以小写字母开头，如 `user`, `count`

### 1.4 示例
```ez
struct User { id: I32; name: Str; }
type Point = { x: I32; y: I32; }
struct Result<T> { ok: T; err: Str; }
let a: I32? = 10
let value: I32 | Str = "hello"
let arr: User[100]
```

### 1.5 语义说明
* `Str` 表示 UTF-8 字符串，按值传递
* `Void` 仅用于函数返回类型，不能用作变量类型
* `typeof` 返回运行时类型标识或结构体类型，而非类型别名
* `type Alias = Shape` 仅为编译时别名，不生成运行时类型
* 联合类型必须通过模式匹配或类型检查来区分具体分支
* 可选类型底层为 `Option<T>`，访问时使用 `expr?` 或强制拆包 `Type! expr`

### 1.6 内置结构体
#### Date
```ez
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
```

#### Error
```ez
struct Error {
    code: I32
    message: Str
    data: Blob?

    toString = (this: Error) => Str
}
```

#### Blob
```ez
struct Blob {
    size: I64
    data: *I8

    get = (this: Blob, index: I64) => I8
    slice = (this: Blob, start: I64, len: I64) => Blob
}
```

### 1.7 LLVM 映射
* `Date` 可优化为单一 timestamp 型
* `Error` 映射为 `{ i32 code, i8* msg, ... }`
* `Blob` 映射为 `{ i64 size, i8* data }`
* `Type[n]` 映射为 LLVM `[Type x n]`
* `Type[]` 映射为 `{ i64 len, i64 cap, Type* data }`
* `Fn` 映射为函数指针
* 可选类型映射为 `{ i1 has_value, T value }`
* 联合类型映射为带 tag 的变体结构
* 无符号类型 `U8`, `U32`, `U64` 映射为相应无符号 LLVM 整数

---

## 2. 变量声明与值语义

### 2.1 语法
```ez
@Decorator? (static | const | let) Identifier<T>? (':' Type)? '=' expression ';'
```

### 2.2 示例
```ez
let count: I32 = 10
const max: I32 = 100
static config: Str = "release"
let copy = count
```

### 2.3 语义说明
* `let`：可变局部变量，存储在当前 Arena 空间
* `const`：只读局部变量，存储在当前 Arena 空间
* `static`：全局静态变量，生命周期贯穿程序
* 赋值默认是值语义，`a = b` 会进行全量拷贝
* 函数参数默认按值传递
* `this` 参数在方法调用中采用引用语义以避免结构体拷贝
* 变量作用域为块级，作用域结束时 Arena 游标回退
* 装饰器 `@Dec` 可用于包装或拦截声明

### 2.4 LLVM 映射
* 局部变量映射为 `alloca` 或 Arena 内存地址
* 拷贝使用 `llvm.memcpy`
* `static` 变量映射为全局常量或全局可变区

---

## 3. 结构体与组合规约

### 3.1 语法
* 定义：`struct Name<T> { ...Base?; field: Type = default?; method = (this: Type, args...) => expr?; }`
* 展开实例化：`Name(...instance, field = value)`
* 命名初始化：`Name(field = value)`

### 3.2 示例
```ez
struct User {
    name: Str = "default"
    id: I32
    say = (this: User) => this.name
}

let user = User(name = "s", id = 1)
let user2 = User(id = 2)
```

### 3.3 语义说明
* `...Base` 将基础结构体字段平铺到当前结构体开头，实现布局复用
* 每个结构体隐式包含 `I32` 类型标识，用于 `typeof` 和运行时检查
* 实例化时会复制基础结构的内存并写入新增字段
* 支持名称参数初始化与默认字段值
* 方法是内联函数，`this` 绑定到结构体实例

### 3.4 LLVM 映射
* 结构体映射为平铺的 LLVM 结构体类型
* 展开实例化先 `memcpy` 基础实例，再 `store` 新字段
* 方法映射为函数指针字段，初始化时绑定对应函数

---

## 4. 流程控制

### 4.1 语法
* 无限循环：`loop { ... }`
* 范围循环：`loop i in 0...10 { ... }`
* 条件表达式：`condition ? expression1 : expression2`
* 条件语句：`condition ? expression` 或 `condition ? { block }`
* 块条件：`condition ? { block1 } : { block2 }`
* 异常捕获：`catch { ... }`
* 模式匹配：`match { (condition) ? expr_or_block, ... }`
* 异步调用：`await async_function()`

### 4.2 语义说明
* `? :` 既是表达式也是流程控制，不使用 `if/else`
* `condition ? expression` 或 `condition ? { block }` 是条件语句，当条件为真时执行表达式，否则跳过
* `0...10` 表示左闭右开区间 `[0, 10)`
* `break` 退出当前循环或 `match`；`continue` 跳过当前分支并继续执行
* `match` 从上到下依次求值，首次匹配后停止，除非使用 `continue`
* 块表达式返回值为 `Void`

### 4.3 示例
```ez
let i = 0
match {
    (i == 0) ? i = 100,
    (i > 0) ? { (i > 10) ? continue; i = i - 1; },
    (i > 0) ? { i = i + 1; break; },
    (true) ? { i = i - 100; }
}
i; // 101
```

```ez
const err = catch {
    throw Error(msg = "hello")
}
(typeof(o = err).includes(Error)) ? print(msg = err.msg)
```
```ez
// 条件语句示例
let x = 5
(x > 0) ? print(msg = "positive")
```
### 4.4 LLVM 映射
* 循环映射为 `br` 与标签结构
* 条件选择映射为 `phi` 或分支跳转

---

## 5. 函数与上下文绑定

### 5.1 语法
* 定义：`const fn = (this: Type, args...) => expression` 或 `const fn = (this: Type, args...) => { block }`
* 异步定义：`async const fn = (this: Type, args...) => ...`
* 参数占位：`?` 支持部分应用与柯里化

### 5.2 语义说明
* 显式声明 `this`，没有隐式上下文
* `obj.fn()` 等价于 `fn(this = obj)`
* 调用支持命名参数，如 `fn(a = 1, b = 2)`
* `async` 函数内部可使用 `await`
* `this` 总是以引用语义传递，不参与值语义拷贝
* `fn(a = ?, b = 2)` 生成等待剩余参数的柯里化函数

### 5.3 LLVM 映射
* 具名参数在编译期重排以生成 `call`
* 柯里化生成闭包结构体，并在 Arena 中存储捕获变量

---

## 6. 元编程：装饰器与 Meta

### 6.1 语义说明
* `@Dec` 将变量包装为 `Meta<T>`，并在读写时执行拦截
* `Meta<T>` 包含 `value`, `getter`, `setter`, `type`, `name`
* 访问时通过函数指针调用 getter/setter

### 6.2 示例
```ez
const log = (this: Meta<I32>) => {
    this.setter = (v: I32) => {
        print(msg = "writing...")
        this.value = v
    }
}

@log let x = 1
x = 2 // 触发拦截打印
```

### 6.3 LLVM 映射
* 装饰器生成 `Meta<T>` 结构体
* 访问时调用 getter/setter 函数指针
* `Meta<T>` 按值传递，拦截逻辑表现为 `call`

---

## 7. 安全机制与链接

### 7.1 语义说明
* `Type! expr`：无检查的类型断言，适用于位级重解释
* `typeof`：基于结构体头部 TypeID 进行快速类型判断
* `declare`：声明外部函数、全局变量或常量
* `catch`：捕获 `throw` 抛出的异常值

### 7.2 示例
```ez
declare const malloc: (size: I64) => Blob
let b: Blob = malloc(size = 10)
let user = User! b
```

### 7.3 LLVM 映射
* `declare` 生成 LLVM 外部符号声明
* `Type! expr` 生成位级重解释或 `load` 操作
* `typeof` 通过结构体 TypeID 比较实现

---

## 8. 内存模型：Arena

### 8.1 语义说明
* 每个作用域对应一个 Arena 游标
* 临时分配在连续内存区完成，作用域结束时回退游标
* 语言层不提供显式 `free`
* 线程独占 Arena，配合值语义实现无锁并发

### 8.2 LLVM 映射
* Arena 使用单一底层缓冲区和游标管理
* 作用域结束时仅需移动游标，无需逐个析构对象

---

## 9. 语法糖与标记语法

### 9.1 标记语法
```ez
let ui = <text color="blue">
    "Welcome"
    <div id=1 />
    {1+2}
</text>
// 等同于 text(color = "blue", children = ["Welcome", div(id=1), 1+2])
```

### 9.2 语法糖
* 管道语法：`value -> fn(a = %)` 等同于 `fn(a = value)`
* 柯里化语法：`fn(a=?, b=2)` 生成等待剩余参数的新函数
* 字符串插值：`"Hello {{name}}, count is {{count}}"`

### 9.3 LLVM 映射
* 标记语法编译为普通函数调用与构造表达式
* 管道语法重写为命名参数调用
* 柯里化生成闭包结构体并捕获已绑定参数
* 字符串插值生成最小内存复制的拼接逻辑

---

## 10. 模块系统

### 10.1 语法
* 导入：`from "path" import {item1, item2}` 或 `from "path" import {sum as add}`
* 导出：`export let x = 1` / `export struct Foo { ... }`
* 外部声明：`declare const func: (args...) => ReturnType`

### 10.2 示例
```ez
from "./std.ez" import {print as log}
from "./math.ez" import math
from "../libs/mylib.c" import {func}  // 自动从 mylib.d.ez 导入 declare

declare const python_func: (arg: I32) => I32
declare const java_method: (obj: Blob) => Void
declare const go_func: (arg: I32) => I32
```

### 10.3 语义说明
* 模块路径支持相对路径和绝对路径，包含 `.ez`, `.c`, `.cpp`, `.rs`
* 导入将外部导出项引入当前作用域
* 对于 C/C++/Rust 文件，自动从同路径 `.d.ez` 导入对应声明
* 导出将变量、函数、结构体等暴露给其他模块
* 模块解析在编译时完成，不影响运行时性能
* `.d.ez` 文件用于声明外部库符号，支持 C ABI 兼容库

### 10.4 LLVM 映射
* 模块导入通过编译时符号链接实现
* 外部链接通过 `.d.ez` 生成 LLVM extern 声明
* C ABI `declare` 支持任何兼容外部库调用
