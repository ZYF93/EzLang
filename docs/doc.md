# EzLang 语言规格说明书

## 0. 语言概览

EzLang 是一门以表达式为中心、采用值语义为主的系统编程语言。它支持强类型、泛型、内置结构体、可选类型、联合类型、异步与元编程，并结合 Arena 内存模型实现高效内存管理。

### 基本规则
* 注释：`// 单行注释`、`/* 块注释 */`
* 区分大小写
* 标识符、关键字、类型名不允许包含空白字符
* 语句由 `;` 分隔，表达式可以直接作为语句使用

### 关键字
`let`, `const`, `static`, `struct`, `type`, `declare`, `loop`, `await`, `async`, `break`, `continue`, `import`, `export`, `from`, `match`, `catch`, `throw`, `typeof`

---

## 1. 类型系统

### 1.1 基本类型
* 数值类型：`I8`, `I32`, `I64`, `U8`, `U32`, `U64`, `F32`, `F64`
* 基础类型：`Str`, `Bool`, `Void`
* 内置结构体：`Date`, `Error`, `Blob`

### 1.2 复合类型
* 数组：`Type[]`（动态数组），`Type[n]`（定长数组）
* 向量：`Vec<Type>[N]`（SIMD 向量），其中 N 为 2, 4, 8, 16，Type 为数值类型。`Vec<Type>[N]` 与 `Type[N]` 不同，前者表示寄存器内的 SIMD 向量，而后者表示连续内存中的定长数组。
* 函数类型：`(name: Type, ...) => ReturnType`
* 可选类型：`Type?`
* 联合类型：`Type1 | Type2`
* 交叉类型：`Type1 & Type2`
* 泛型：`<T, K>`
* 类型别名：`type Alias = Shape`
* Dict类型：通过 `{ prop: Type; ... }` 创建。支持固定字段和动态键（如 `[key: Str]: Type`）。
  * 字面量结构：支持 `{ prop: Type = value; ... }` 或 `{ prop = value; ... }` 创建。
* 自动形状推断：字面量对象如 `{ props = 1 }` 会被自动推断为 `{ props: I32 }`。

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
let vec: Vec<I32>[4] = Vec[1, 2, 3, 4]

type Shape = {
    name: Str;
    [dynamic: Str]: Str // 动态键声明：[键名: 键类型]: 值类型
}

// 字面量初始化：支持 { prop = value } 形式，便于推断
let s: Shape = {
    name = "Square";
    side = "10"
}

// 支持显式类型指定：{ prop: Type = value }
const a = { props: I32 = 1 } 
const b = { x = 10, y = 20 } // 自动推断为 { x: I32; y: I32 }
```

### 1.5 语义说明
* `Str` 表示 UTF-8 字符串，按值传递
* `Void` 仅用于函数返回类型，不能用作变量类型
* `typeof` 返回运行时类型标识或结构体类型，而非类型别名
* `type Alias = Shape` 定义的形状采用鸭子类型（Duck Typing）进行验证。
* 任何结构（包括 Struct 或 Dict）只要包含形状要求的字段，即可视为匹配该类型。
* 联合类型必须通过模式匹配或类型检查来区分具体分支
* 交叉类型 `ShapeA & ShapeB` 要求对象必须同时满足两者的约定
* 声明的 Dict 形状本质上是用于验证类型的鸭子类型模板。
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
* `Vec<Type>[N]` 映射为 LLVM `<N x Type>`
* `Fn` 映射为函数指针
* 可选类型映射为 `{ i1 has_value, T value }`
* 联合类型映射为带 tag 的变体结构
* 无符号类型 `U8`, `U32`, `U64` 映射为相应无符号 LLVM 整数

### 1.8 泛型系统

#### 语法
* 类型参数：`<T, U, ...>`，在类型名、结构体定义、函数定义后声明。
* 泛型实例化：`Type<T>` 或 `Struct<T>(...)`。

#### 语义说明
* 泛型允许类型参数化，实现代码复用。
* 类型参数在编译时单态化，每个具体类型生成独立代码。
* 支持多类型参数，如 `<T, U>`。
* 泛型类型通常会在编译期单态化生成独立代码。为了提升可用性，编译器支持局部类型推断。
* 当上下文足够时，显式类型参数可以省略，如 `let p = Pair(first = 42, second = "s")` 将推断为 `Pair<I32, Str>`。
* 结构体泛型：在结构体名后声明 `<T>`，字段和方法可使用 T。
* 函数泛型：在函数定义中声明 `<T>`，参数和返回值可使用 T。
* 变量泛型：变量声明可使用 `<T>` 指定类型参数，但通常通过推断。

#### 示例
```ez
// 泛型结构体
struct Pair<T, U> {
    first: T
    second: U
    swap = (this: Pair<T, U>) => Pair<U, T>(first = this.second, second = this.first)
}

let p = Pair<I32, Str>(first = 42, second = "hello")
let swapped = p.swap()  // Pair<Str, I32>
let p2 = Pair(first = 42, second = "s")  // 推断为 Pair<I32, Str>

// 泛型函数
const identity = <T>(value: T) => value
let num = identity<I32>(42)
let str = identity<Str>("world")
let inferred = identity(42)  // 推断为 I32

// 泛型变量（类型推断）
let list: Vec<I32>[4] = Vec[1, 2, 3, 4]  // 推断为 Vec<I32>[4]
```

#### LLVM 映射
* 泛型通过单态化实现，每个具体类型实例生成独立 LLVM 函数或类型。
* 编译时替换类型参数为具体类型，无运行时开销。

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
(typeof err & Error == Error) ? print(msg = err.msg)
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
* 默认参数：`const fn = (a: I32, b: I32 = 1) => a + b`
* 参数占位：`?` 支持部分应用与柯里化
* 显式返回：在 block 函数体中使用 `return expression`

### 5.2 语义说明
* 显式声明 `this`，没有隐式上下文
* `obj.fn()` 等价于 `fn(this = obj)`
* 调用支持命名参数，如 `fn(a = 1, b = 2)`
* 函数调用仅支持命名参数；`fn(1, 2)` 非法
* 形参可声明默认值；调用时若省略该参数，则使用默认值
* `=> expression` 形式仍然有效；若函数体使用 `{ ... }` block，则必须通过 `return` 显式返回，最后一个表达式不会隐式成为返回值
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
* 由于 EzLang 采用值语义，跨作用域返回的值不会出现悬垂引用：返回时会将值复制到父级 Arena 游标所管理的空间。

### 8.2 LLVM 映射
* Arena 使用单一底层缓冲区和游标管理
* 作用域结束时仅需移动游标，无需逐个析构对象
* Arena 分配器会根据类型的 `alignof` 自动进行内存对齐，确保 SIMD 向量和大型结构体符合目标架构对齐要求
* 跨作用域返回时，值被拷贝至父级 Arena 游标处。

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
* EzLang 不存在隐式入口函数；文件内定义的任意函数都不会自动执行，需在代码中显式调用

### 10.4 LLVM 映射
* 模块导入通过编译时符号链接实现
* 外部链接通过 `.d.ez` 生成 LLVM extern 声明
* C ABI `declare` 支持任何兼容外部库调用

---

## 11. 运算符与表达式

### 11.1 算术运算
* 加法：`a + b`
* 减法：`a - b`
* 乘法：`a * b`
* 除法：`a / b`
* 取模：`a % b`

#### 语义说明
* 算术运算符适用于数值类型（I8, I32, I64, U8, U32, U64, F32, F64）。
* 整数除法向下取整，无符号类型无符号除法。
* 浮点运算遵循 IEEE 754 标准。
* 类型必须匹配，否则编译错误。

#### 示例
```ez
let a: I32 = 10
let b: I32 = 3
let sum = a + b  // 13
let diff = a - b  // 7
let prod = a * b  // 30
let quot = a / b  // 3
let rem = a % b   // 1
```

#### LLVM 映射
* 映射为相应 LLVM 指令：`add`, `sub`, `mul`, `sdiv`/`udiv`, `srem`/`urem`。

### 11.2 位运算
* 按位与：`a & b`
* 按位或：`a | b`
* 按位异或：`a ^ b`
* 左移：`a << b`
* 右移：`a >> b`

#### 语义说明
* 位运算符适用于整数类型（I8, I32, I64, U8, U32, U64）。
* 移位操作符右操作数必须为无符号类型，左移填充零，右移根据符号填充。
* 无符号类型右移填充零，有符号类型算术右移。

#### 示例
```ez
let a: U8 = 0b1010
let b: U8 = 0b1100
let and = a & b  // 0b1000
let or = a | b   // 0b1110
let xor = a ^ b  // 0b0110
let lsh = a << 1 // 0b10100
let rsh = a >> 1 // 0b0101
```

#### LLVM 映射
* 映射为 LLVM 位运算指令：`and`, `or`, `xor`, `shl`, `lshr`/`ashr`。

### 11.3 逻辑运算
* 逻辑与：`a && b`
* 逻辑或：`a || b`
* 逻辑非：`!a`

#### 语义说明
* 逻辑运算符适用于 Bool 类型。
* 短路求值：`&&` 在左操作数为 false 时不求值右操作数，`||` 在左操作数为 true 时不求值右操作数。
* `!` 取反。

#### 示例
```ez
let a: Bool = true
let b: Bool = false
let and = a && b  // false
let or = a || b   // true
let not = !a      // false
```

#### LLVM 映射
* 映射为条件分支和 phi 节点，实现短路求值。

### 11.4 比较运算
* 等于：`a == b`
* 不等于：`a != b`
* 小于：`a < b`
* 大于：`a > b`
* 小于等于：`a <= b`
* 大于等于：`a >= b`

#### 语义说明
* 比较运算符适用于数值类型和 Str。
* 返回 Bool 类型。
* 对于结构体和联合类型，不支持直接比较，除非实现相应方法。

#### 示例
```ez
let a: I32 = 5
let b: I32 = 10
let eq = a == b  // false
let ne = a != b  // true
let lt = a < b   // true
let gt = a > b   // false
let le = a <= b  // true
let ge = a >= b  // false
```

#### LLVM 映射
* 映射为 LLVM 比较指令：`icmp` 或 `fcmp`，返回 i1。

### 11.5 运算符优先级
* `!`（逻辑非）
* `*`, `/`, `%`
* `+`, `-`
* `<<`, `>>`
* `&`
* `^`
* `|`
* `==`, `!=`, `<`, `>`, `<=`, `>=`
* `&&`
* `||`

#### 语义说明
* EzLang 中，位运算 `&` 的优先级高于比较运算 `==`，但低于移位运算。
* 为避免混合位运算、比较运算和逻辑运算时的歧义，建议在表达式中显式使用括号。
* 例如：`(a & b) == c` 和 `a & (b == c)` 在语义上不同。

### 11.6 复合赋值
* 加赋值：`a += b`
* 减赋值：`a -= b`
* 乘赋值：`a *= b`
* 除赋值：`a /= b`
* 模赋值：`a %= b`
* 位与赋值：`a &= b`
* 位或赋值：`a |= b`
* 位异或赋值：`a ^= b`
* 左移赋值：`a <<= b`
* 右移赋值：`a >>= b`

#### 语义说明
* 复合赋值等价于 `a = a op b`，但 `a` 只求值一次。
* 适用于可变变量（let）。

#### 示例
```ez
let a: I32 = 10
a += 5  // a = 15
a &= 0b1111  // a = 15 & 15 = 15
```

#### LLVM 映射
* 映射为加载、运算、存储序列。

---

## 12. SIMD 语法

### 12.1 语法
* 向量类型：`Vec<Type>[N]`，其中 N 为向量长度（2, 4, 8, 16），Type 为基本数值类型。
* 向量与定长数组区分：`Type[N]` 表示连续内存中的数组，`Vec<Type>[N]` 表示寄存器中的 SIMD 向量。
* 向量字面量：`Vec<Type>[1, 2, 3, 4]` 或 `Vec[1, 2, 3, 4]`，根据上下文推断类型或指定类型参数。
* 向量操作：支持算术运算、位运算、比较运算的向量版本。

### 12.2 语义说明
* SIMD 操作并行应用于向量元素。
* 向量长度必须匹配，否则编译错误，如 `Vec<I32>[4] + Vec<I32>[2]` 为非法表达式。
* 支持向量与标量的混合操作，标量将广播成等长向量后再执行运算。`v1 * 2` 等价于 `v1 * Vec<I32>[2, 2, 2, 2]`。

#### 示例
```ez
let v1: Vec<I32>[4] = Vec[1, 2, 3, 4]
let v2: Vec<I32>[4] = Vec[5, 6, 7, 8]
let sum = v1 + v2  // Vec<I32>[4] with elements [6, 8, 10, 12]
let scaled = v1 * 2  // Vec<I32>[4] with elements [2, 4, 6, 8]
let masked = (v1 < v2) ? v1 : v2  // 条件选择
```

### 12.3 LLVM 映射
* 向量类型映射为 LLVM 向量类型，如 `<4 x i32>`。
* 操作映射为 LLVM SIMD 指令，如 `add <4 x i32>`。
