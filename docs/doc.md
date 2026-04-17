# EzLang 语言规格说明书

## 0. 语言总体 (Language Overview)

### 注释
* 单行注释：`// 注释内容`
* 块注释：`/* 注释内容 */`

### 标识符与关键字
* 关键字：`let`, `const`, `static`, `struct`, `type`, `declare`, `loop`, `await`, `async`, `break`, `continue`, `import`, `export`, `from`, `match`
* 区分大小写
* 所有类型名、标识符和关键字均不允许有空白字符

### 表达式与语句
* 绝大多数控制结构和函数调用都是表达式；表达式可以作为语句使用。
* 语句末尾使用 `;` 作为分隔符。

---

## 1. 类型系统 (Type System)

### 语法
* **数值类型**：`I8`, `I32`, `I64`, `U8`, `U32`, `U64`, `F32`, `F64`
* **基础类型**：`Str`, `Bool`, `Void`, **`Blob`** (原始字节块)
* **数组类型**：`Type[]`（动态数组）或 `Type[n]`（定长数组），其中 `Type` 可以是基本类型、结构体、联合类型、泛型等。
* **字符串插值**：`"Hello {{expr}}"` 用于在字符串内嵌表达式结果
* **函数类型 (`Fn`)**：语法为 `(ParamName: Type, ...) => ReturnType`
* **可选类型**：`Type?` (如 `I32?`)
* **联合类型**：`Type1 | Type2` (如 `I32 | Str`)
* **泛型**：`<T, K>` 占位符
* **类型别名**：`type Alias = Shape`

### 命名规则
* **类型名称** 必须以大写字母开头，例如 `User`, `Result`, `Option`。
* **变量名称** 必须以小写字母开头，例如 `user`, `count`, `result`。

### 示例
* 类型定义：`struct User { id: I32; name: Str; }`
* 类型别名：`type Point = { x: I32; y: I32; }`
* 泛型类型：`struct Result<T> { ok: T; err: Str; }`
* 函数类型：`(x: I32, y: I32) => I32`
* 可选类型：`I32?`, `Str?`
* 联合类型：`I32 | Str`, `Bool | Void`
* 无符号类型：`U8`, `U32`, `U64`
* 数组类型：`I32[]`, `Str[]`, `User[100]`, `(I32 | Str)[]`

### 含义与规范
* **Str**：表示 UTF-8 字符串，按值传递。
* **字符串插值**：`"Hello {{expr}}"` 在编译时展开为字符串拼接或缓冲区构建，表达式结果转换为字符串后插入。
* **Void**：仅能用作函数返回类型，不能作为变量类型。
* **Blob**：代表一块连续的、长度可变的原始内存。它不支持字段访问，仅支持索引访问单个字节（返回 `I8`）或通过 `!` 强制转换为结构体。
* **数组类型**：`Type[n]` 表示定长数组，`Type[]` 表示动态数组，按值传递。`Type` 可以是基本类型、结构体、联合类型等。
* **类型别名**：`type Name = Shape` 为编译期别名，表示一组字段形状，不生成实际运行时类型。
* **`typeof`**：返回实际运行时类型的 TypeID 或结构体类型，而不是 `type` 别名。
* **联合类型**：`Type1 | Type2` 表示值可以是 Type1 或 Type2 中的任意一种。访问时需要通过模式匹配或类型检查来确定具体类型。
* **无符号类型**：`U8`, `U32`, `U64` 表示无符号整数，范围从 0 到最大值，无负数。
* **泛型单态化**：编译器会为每种具体的泛型组合生成独立的 LLVM 代码（Monomorphization），确保执行效率。
* **可选类型**：底层为 `Option<T>` 容器。访问值时必须使用安全拆包 `expr?` 或强制拆包 `Type ! expr`。

### LLVM 实现
* **Blob**: `{ i64 size, i8* data }`。
* **定长数组**: `Type[n]` 映射为 LLVM `[Type x n]` 数组类型。
* **动态数组**: `Type[]` 映射为 `{ i64 len, i64 cap, Type* data }`，支持 `Type` 为结构体、联合类型、泛型等。
* **Fn**: 函数指针 `ptr`。
* **可选类型**: `{ i1 has_value, T value }`。
* **联合类型**: `{ i32 tag, { T1, T2, ... } data }`，其中 tag 用于标识具体类型。
* **无符号类型**: `U8` -> `i8`, `U32` -> `i32`, `U64` -> `i64` (无符号)。

---

## 2. 变量声明与值语义 (Variables & Value Semantics)

### 语法
```ez
@Decorator? (static | const | let) Identifier<T>? (':' Type)? '=' expression ';';
```

### 示例
```ez
let count: I32 = 10;
const max: I32 = 100;
static config: Str = "release";
let copy = count;
```

### 含义与规范
* **`let`**：可变局部变量，存储在当前 Arena 空间内。
* **`const`**：只读局部变量，存储在当前 Arena 空间内。
* **`static`**：全局静态变量，生命周期贯穿程序始终，不属于任何 Arena。
* **强制值语义**：赋值 `a = b` 永远是全量内存拷贝。修改 `a` 不会影响 `b`。
* **作用域**：块级作用域。变量在退出所属代码块时随 Arena 游标重置而失效。
* **装饰器**：`@Decorator` 作用于声明，可用于包装或拦截变量访问。

### LLVM 实现
* 局部变量映射为 `alloca` 或从 Arena 游标处 `getelementptr`。
* 拷贝操作使用 `llvm.memcpy`。
* `static` 变量映射为全局常量或全局可变区。

---

## 3. 结构体与组合规约 (Structs)

### 语法
* **定义**：`struct Name<T> { ...Base?; field: Type = default_value?; method = (this: Type, args...) => expr?; }`
* **展开实例化**：`Name(...instance, field = value)`
* **命名初始化**：`Name(field = value)`

### 示例
* `let user = User(name = "s", id = 1)`
* `let user2 = User(id = 2)` // name 使用默认值 ""

```ez
struct User {
    name: Str = "default"
    id: I32
    say = (this: User) => this.name
}
```

### 含义与规范
* **字段平铺 (`...Base`)**：将 `Base` 的所有字段展开并插入到当前结构布局起始处，实现非继承式的布局复用。
* **TypeID**：每个结构体头部隐式包含一个 `I32` 类型标识，用于 `typeof` 识别和运行时类型检查。
* **实例化**：展开实例化时先复制基础结构的内存，再写入新增字段。
* **命名参数**：结构体实例化使用名称参数，如 `User(name = "s")`。
* **默认值**：字段可以指定默认值，如果实例化时未提供该字段，则使用默认值。
* **方法**：结构体可以包含方法定义，方法是内联函数，`this` 绑定到结构体实例。

### LLVM 实现
* 结构体映射为平铺的 `type { i32, ... }`。
* 实例化扩展先 `memcpy` 旧实例，再针对新字段执行 `store`。
* 方法映射为函数指针字段，初始化时绑定到相应函数。

---

## 4. 流程控制 (Control Flow)

### 语法
* **循环**：
    * 无限循环：`loop { ... }`
    * 范围循环：`loop i in 0...10 { ... }`
    * 迭代循环：`loop item in list { ... }`
* **条件选择**：
    * 表达式：`condition ? expression1 : expression2`
    * 代码块：`condition ? { block1 } : { block2 }`
* **模式匹配**：`match { (condition) ? expression_or_block, ... };`
* **异步**：`await async_function()`

### 含义与规范
* **无 `if/else` 关键字**：统一使用 `? :` 语法，既是表达式也是流程控制。
* **三点范围**：`0...10` 表示从 `0` 到 `9` 的半开区间。
* **循环中断**：支持 `break` 和 `continue`。`break` 退出 `match` 语句，`continue` 跳过当前分支并继续匹配下一条分支。
* **迭代器**：`loop item in list` 要求目标对象实现 `next()` 方法，返回可选值；当返回空值时循环结束。
* **匹配语句**：`match` 会从上到下依次评估每个条件表达式。当某个条件为 `true` 时，执行对应的表达式或代码块，并停止匹配，除非使用 `continue`。
* **块表达式**：`{ ... }` 中最后一个表达式的值即为整个块的结果；无结果时为 `Void`。

### 示例
```ez
let i = 0;
match {
    (i == 0) ? i = 100,
    (i > 0) ? { (i > 10) ? continue; i = i - 1; },
    (i > 0) ? { i = i + 1; break; },
    (true) ? { i = i - 100; }
};
i; // 101
```

### LLVM 实现
* **循环**：映射为 `br` 指令与多个 Label (`loop_cond`, `loop_body`, `loop_end`)。
* **选择**：映射为 `phi` 指令或基于 `br` 的分支跳转。

---

## 5. 函数架构与 Context 绑定 (Functions)

### 语法
* **定义**：`let fn = (this: Type, args...) => expression` 或 `let fn = (this: Type, args...) => { block }`
* **异步定义**：`async let fn = (this: Type, args...) => expression` 或 `async let fn = (this: Type, args...) => { block }`
* **参数占位**：`?` 可用于参数占位，支持部分应用与科里化。

### 示例
* `fn(a = 1, b = 2)`

### 含义与规范
* **显式 `this`**：没有隐式上下文。必须手动声明 `this` 参数。`fn(this = obj)`。
* **调用转换**：`obj.fn()` 等价于 `fn(this = obj)`。
* **命名调用**：函数调用使用名称参数，如 `fn(a = 1, b = 2)`。
* **async 函数**：使用 `async` 关键字定义异步函数，可以在函数体内使用 `await` 调用其他异步函数。
* **不可变视图**：`this` 传入时在语言层视为不可变，字段可变，底层通过指针传递以减少拷贝。
* **柯里化**：`fn(a = ?, b = 2)` 生成一个新的函数，保留 `b = 2`，等待传入剩余参数，再执行原函数。

### LLVM 实现
* 具名参数在编译期根据签名顺序重排，生成 `call`。
* 科里化生成闭包结构体并在 Arena 存储捕获变量。

---

## 6. 元编程：装饰器与 Meta (Decorators)

### 含义与规范
* **变量劫持**：`@Dec` 将变量包装进 `Meta<T>`。
* **`Meta<T>`**：包含字段 `value`, `getter`, `setter`，`type`，`name`，用于拦截和定制读写行为。
* **拦截读写**：通过 `this.getter` 和 `this.setter` 函数指针接管对变量的一切访问。
* **声明语义**：`@Dec let x = value;` 由编译器在初始化阶段创建 `Meta<T>` 并应用装饰器。

### 示例
```ez
const log = (this: Meta<I32>) => {
    this.setter = (v: I32) => {
        print(msg = "writing...");
        this.value = v;
    };
};

@log let x = 1;
x = 2; // 触发拦截打印
```

### LLVM 实现
* 装饰器值映射为 `Meta<T>` 结构体并存储 getter/setter 函数指针。
* 变量访问通过调用 `getter`/`setter` 函数指针实现，可在编译时内联优化。
* `Meta<T>` 结构体按值传递，拦截代码在 LLVM IR 中表现为 `call` 指令。

---

## 7. 安全机制与链接 (Safety & Linkage)

### 语法与规范
* **强制断言 (`Type! expr`)**：无运行时开销的类型转换。用于数值截断或从 `Blob` 恢复结构体。
* **类型检查 (`typeof`)**：基于结构体头部隐式 `TypeID` 的快速判断。
* **声明 (`declare`)**：链接外部 C 符号，声明外部函数、全局变量或常量。

### 示例
```ez
declare const malloc: (size: I64) => Blob;

let b: Blob = malloc(size = 10);
let user = User! b; // 将内存块断言为 User 结构
```

### LLVM 实现
* `declare` 语句生成 LLVM `declare` 外部函数或全局符号声明。
* `Type! expr` 生成无检查的位级重解释或结构体加载，依赖 `llvm.bitcast` 和 `load`。
* `typeof` 使用结构体头部的 `TypeID` 字段与常量比较，实现快速类型判断。

---

## 8. 内存模型：Arena 机制 (Arena Memory)

### 语法与规范
* **批量回收**：每个作用域（函数/循环/代码块）对应一个 Arena 游标。
* **零碎空间消除**：所有临时分配都在连续内存上进行，作用域退出时游标回退到进入该作用域前的位置。
* **无手动释放**：语言层不提供显式 `free`，由 Arena 机制自动管理非 `static` 内存。
* **并发模型**：线程独占 Arena，配合值语义实现无锁并发。

### LLVM 实现
* Arena 分配通过单一底层缓冲区和游标管理实现。
* 作用域结束时仅需移动游标，无需逐个析构对象。

---

## 9. 语法糖：标记语法 (Tag Syntax)

### 标记语法 示例
```ez
let ui = <text color="blue">
    "Welcome"
    <div id=1 />
    {1+2}
</text>;
// 等同于 text(color = "blue", children = ["Welcome", div(id=1), 1+2])
```

### 语法糖示例
* **管道语法**：`value -> fn(a = %)` 等同于 `fn(a = value)`。
* **科里化语法**：`fn(a=?, b=2)` 生成一个新的函数，等待补全剩余参数后再调用原函数。
* **字符串插值**：`"Hello {{name}}, count is {{count}}"` 生成拼接后的 `Str`。

### LLVM 实现
* 标记语法解析为普通函数调用和结构体/数组构造，不保留额外运行时开销。
* 管道语法按编译器生成临时变量并重写为常规命名参数调用。
* 科里化语法生成闭包结构体与包装函数，捕获已绑定参数并在调用时传递剩余参数。
* 字符串插值编译为字符串缓冲区构建与拼接逻辑，生成最少的内存复制。

---

## 10. 模块系统 (Modules)

### 语法
* **导入**：`from "path" import {item1, item2}` 或 `import item from "path"`
* **导出**：`export let x = 1;` 或 `export struct Foo { ... }`
* **外部声明**：`declare const func: (args...) => ReturnType;`

### 示例
```ez
from "./std.ez" import {console}
import math from "./math.ez"
from "../libs/mylib.c" import {func}  // 自动从 mylib.d.ez 导入 declare

// 链接其他语言库的示例
declare const python_func: (arg: I32) => I32;  // 通过 Python C API
declare const java_method: (obj: Blob) => Void;  // 通过 JNI
declare const go_func: (arg: I32) => I32;  // 通过 cgo
```

### 含义与规范
* **模块路径**：相对路径或绝对路径，指向 `.ez`, `.c`, `.cpp`, `.rs` 文件。
* **导入**：将外部模块的导出项引入当前作用域。对于 C/C++/Rust 文件，自动从同路径的 `.d.ez` 文件导入对应的 `declare` 声明。
* **导出**：将变量、函数、结构体等标记为可导出，供其他模块导入。
* **编译时解析**：模块导入在编译时解析，不影响运行时性能。
* **外部集成**：`.d.ez` 文件包含外部库的 `declare` 声明，用于链接 C/C++/Rust 代码。此外，通过 `declare` 可以链接任何具有 C ABI 的外部库，包括其他编程语言的库（如 Python 的 C API, Java 的 JNI, Go 的 cgo 等）或系统库。

### LLVM 实现
* 模块导入通过编译时符号链接实现，无额外运行时开销。
* 外部链接通过 `.d.ez` 中的 `declare` 声明生成相应的 LLVM extern 声明。
* 对于其他语言，通过 C ABI 的 `declare` 生成 extern 调用，支持链接任何兼容的外部库。
