# EzLang Language Specification

[中文](../doc.md)

EzLang is an expression-oriented systems programming language that defaults to value semantics. It supports strong typing, generics, built-in structs, optional types, union types, metaprogramming, and the Flow concurrency runtime, combined with an Arena memory model for efficient memory management and high performance.

## 1. Language Overview and Basic Rules

### Syntax

```ez
// Line comment
/* Block comment */
let a = 1; // Statements are separated by ; and expressions may be used as statements
```

### Semantics and Rules

- **Case-sensitive**.
- Identifiers, keywords, and type names cannot contain whitespace.
- **Keywords**: `let`, `const`, `static`, `struct`, `type`, `declare`, `loop`, `break`, `continue`, `import`, `export`, `from`, `match`, `catch`, `throw`, `flow`, `parallel`, `rp`, `wp`, `typeof`, `return`, `in`, `for`, `as`, `extern`.
- **Reserved lexical units**: primitive type names `I8`, `I32`, `I64`, `U8`, `U32`, `U64`, `F32`, `F64`, `Str`, `Bool`, `Void`, compound type constructors `Vec`, `List`, boolean literals `true` / `false`, and target platform names `linux`, `macos`, `windows`, `android`, `ios`, `emcc` are fixed tokens and cannot be used as ordinary identifiers. `Dict`, `Date`, `Error`, `Blob`, and `Meta` are compiler-predeclared type names.
- **Naming convention**: type names should start with an uppercase letter, such as `User` or `Result`; variable names may start with a lowercase letter, underscore, or `$`, such as `user`, `_count`, or `$state`.

### LLVM Mapping

- Basic syntax, lexical parsing, and naming checks are handled by the compiler frontend and have no direct runtime LLVM mapping.

---

## 2. Type System and Generics

### Syntax

```ez
// Primitive types, optional types, and union types
struct User { name: Str; }
let user = User(name = "Ada");
let a: I32? = 10;
let value: I32 | Str = "hello";
let weakUser: #User = #user;

// List, dynamic arrays, and SIMD vectors
let arr: User[]?;                    // Dynamic array, List
let arr2: User[] = [];               // Empty array initialization
let listType = typeof User[]         // Returns the List type
let vec: Vec<I32>[4] = Vec[1, 2, 3, 4];

// Type aliases and generic structs
type Point = { x: I32; y: I32; }
struct Result<T> { ok: T; err: Str; }

// Dict types and dynamic keys
type Shape = {
    name: Str;
    [dynamic: Str]: Str // Dynamic key declaration: [keyName: keyType]: valueType
}
let dictType = typeof { prop: I32 = 1 } // Returns the Dict type

// Literal initialization and automatic shape inference
let s: Shape = {
    name = "Square";
    side = "10"
}
const a_obj = { props: I32 = 1 } // Explicit type annotation
const b_obj = { x = 10, y = 20 } // Inferred as { x: I32; y: I32 }
const keyword_key = { "type": Str = "I32" } // Keywords must be written as string keys

// Type extension
type Named = { name: Str }
type UserShape = {
    ...Named;
    age: I32
}

// Generic structs and methods
struct Pair<T, U> {
    first: T
    second: U
    swap = (this: #Pair<T, U>) => Pair<U, T>(first = this.second, second = this.first)
}
let p = Pair<I32, Str>(first = 42, second = "hello")
let swapped = p.swap()  // Pair<Str, I32>
let p2 = Pair(first = 42, second = "s")  // Inferred as Pair<I32, Str>

// Generic functions
const identity = <T>(value: T) => value
let num = identity<I32>(42)
let str = identity<Str>("world")
let inferred = identity(42)  // Inferred as I32
```

### Semantics and Rules

- **Primitive types**: numeric types (`I8`, `I32`, `I64`, `U8`, `U32`, `U64`, `F32`, `F64`) and basic types (`Str`, `Bool`, `Void`).
  - `Str` represents a UTF-8 string and is passed by value.
  - `Void` is only used as a function return type and cannot be used as a variable type.
- **Compound types**:
  - List arrays: all arrays are dynamic arrays. `List<Type>` is supported, and the syntax can also use `Type[]` directly. `typeof Type[]` explicitly obtains the `List` type.
  - Vectors: `Vec<Type>[N]`, where `N` is 2, 4, 8, or 16 and `Type` is numeric. This represents an in-register SIMD vector.
  - Function types: `(name: Type, ...) => ReturnType`. Function values are closure values and can store ordinary functions, anonymous functions, curried results, and functions that capture outer variables.
  - Optional types: `Type?`. The underlying form is `Option<T>`; access uses `expr?` or forced unwrap `Type! expr`.
  - Weak references: `#Type`. `#expr` creates a weak reference value pointing to `expr`, semantically meaning a `Type` reference that may become invalid when its Arena lifetime ends. Weak references are used transparently as `Type`: `#var.field`, `#var.method()`, `var.field`, and `var.method()` have the same spelling. Null checks use `typeof ref == Void`.
  - Union types: `Type1 | Type2`. Concrete branches must be distinguished through pattern matching or type checks.
- **Type aliases and shape matching**:
  - `type Alias = { ... }` defines a fixed shape and records its field set. A struct value can be assigned to that shape alias when it contains the required fields with compatible types.
  - Object literals with an expected shape type are checked by field name and lowered to the corresponding static layout, such as `let s: Shape = { name = "Square"; side = "10" }`.
  - `Dict` values can be created with literals such as `{ prop: Type = value }`, `{ prop = value }`, or dynamic keys `{ [expr] = value }`. Fixed field checks and dynamic key type declarations are supported. However, ordinary `Dict` variables are not automatically converted into fixed-shape structs.
  - Bare field names and bare dictionary keys must be ordinary variable identifiers. Keywords, reserved type names, or keys with special characters must be written as string keys, such as `{ "type": Str = "I32" }`. Dynamic expression keys use `[expr] = value`.
  - `typeof { prop: Type = value }` obtains the corresponding `Dict` type.
- **Type extension**: `...BaseType` expands the fields of a base shape into the current definition.
- **Generic system**:
  - Type parameters enable reuse and support multiple type parameters such as `<T, K>`.
  - The compiler supports local type inference when context is sufficient, such as local variables and function calls.
  - Type parameters are monomorphized at compile time, producing independent code with no runtime overhead.

### LLVM Mapping

- Unsigned types map to corresponding unsigned LLVM integers.
- `Type[]` / `List<Type>` maps to a paged array ABI: `{ Type** pages, i64 length, i64 capacity, i64 page_count }`. Indexing first locates the fixed-size page, then the element inside the page.
- `Vec<Type>[N]` maps to LLVM `<N x Type>`.
- Function types map internally to closure values `{ invoke, env }`. `invoke` is the call entrypoint with an environment pointer; `env` stores captured state. A zero-capture ordinary function passed to an external C ABI `declare` can lower to a C function pointer.
- Optional types map to `{ i1 has_value, T value }`.
- Weak references map to `{ i1 ok, T* ptr }`. The language does not expose `.ok/.value`; field access and method calls resolve directly to the inner `T`. `typeof ref == Void` maps to checking the `ok` bit. The compiler already provides type, access, and call ABI representation; unified invalidation after Arena destruction is introduced progressively as runtime support grows.
- Union types map to tagged variant structs.
- Generics are implemented by monomorphization. Each concrete type instance generates independent LLVM functions or type substitutions at compile time.
- `Dict` maps to a hash table.

---

## 3. Structs, Composition, and Built-In Objects

### Syntax

```ez
// Struct definition and inheritance-like expansion
struct Person {
    name: Str = "default";
    id: I32;
    say = (this: #Person): Str => { return this.name; };
}

struct User {
    ...Person;
    age: I32 = 0;
}

// Spread instantiation and named initialization
let user = User(name = "s", id = 1);
let user2 = User(id = 2); // name uses the default value
let user3 = User(...user, age = 20);

// Built-in structs: Date, Error, Blob, Meta<T>
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
    code:    I32;    // Positive values are business errors; negative values are system errors
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

### Semantics and Rules

- **Struct basics**: definitions support `struct Name<T> { ...Base?; field: Type = default?; method = (this: #Type, args...) => expr?; }`. Named argument initialization and default field values are supported. Structs use static layout.
- **Composition and reuse**: `...Base` flattens base-struct fields into the beginning of the current struct, enabling layout reuse. Instantiation copies the base struct memory and writes new fields.
- **Type checks and methods**: `typeof` returns a stable `I32` TypeID generated by the compiler for a type name. `typeof ref == Void` / `typeof ref != Void` on a weak reference checks the weak reference validity bit. Struct instances do not store an extra TypeID field. Methods compile to independent functions named like `Struct_method` and are registered in the struct method table. Object method calls pass a weak reference to the receiver as the first `this` argument. Direct calls may write `method(this = #value)` explicitly.
- **Built-in structs and types**: these provide language-level common data containers and are compiler-predeclared; no standard-library import is needed.
  - `Date` stores timestamps and provides basic time arithmetic and formatting.
  - `Error` stores error code, message, throw-site file/line/column, and a lightweight call-stack fragment for unified exception handling and diagnostics.
  - `Blob` provides binary block length and low-level pointer access.
  - `Dict<K, V>` is the runtime carrier for dictionaries. Users normally use shape syntax `{ key: Type; ... }` or `Dict<K, V>`; `std/collections` exposes functions such as `dictHas` and `dictKeys` with `this: #Dict<K, V>` as the first parameter.
  - `List<T>` / `T[]` is the dynamic array type. `std/collections` exposes functions such as `listPush`, `listLen`, and `listMap` with `this: #List<T>` as the first parameter.
  - `Meta<T>` is the meta-object type for decorated variables. It stores the raw value, read/write interceptor closures, type name, and variable name. The type-name field is `t` to avoid exposing the keyword `type` as a field name.

### LLVM Mapping

- Structs map to flattened LLVM struct types.
- Spread instantiation first `memcpy`s the base instance, then `store`s new fields.
- Methods are not stored in instance fields. The compiler maintains a struct method table at compile time; method bodies map to independent LLVM functions, and `obj.method(...)` lowers to a function call with `this` inserted.
- Built-in struct mappings:
  - `Date` can be optimized as a single timestamp value, usually i64.
  - `Error` maps to `{ i32 code, i8* message, i8* file, i32 line, i32 column, i8* trace }`.
  - `Blob` maps to `{ i8* data, i64 size }`.
  - `Meta<T>` maps to `{ T value, Closure<T()> getter, Closure<Void(T)> setter, i8* t, i8* name }`.

---

## 4. Variables, Scope, and Memory Model

### Syntax

```ez
struct User { name: Str }
let count: I32 = 10
rp let cache: User[] = []  // Read-priority lock
wp let queue: I32[] = []   // Write-priority lock
let ordered: I32 = 0       // Default sequential lock
const max: I32 = 100
static config: Str = "release"
let copy = count
```

### Semantics and Rules

- `let`: mutable local variable. `const`: read-only local variable. Both live in the current Arena space.
- `rp let variable = ...`: declares a read-priority variable lock. Reads are prioritized when read requests exist. Writes wait for current reads to finish. A writer fallback wait time of 1 ms prevents long-term writer starvation by moving a writer ahead of later reads after that wait.
- `wp let variable = ...`: declares a write-priority variable lock. Writes are prioritized when write requests exist; reads may starve.
- Sequential lock: ordinary variables without `rp` / `wp` use the default sequential lock, serving read and write requests in arrival order.
- `static`: global static variable with program-long lifetime.
- **Value semantics**: assignment defaults to full value copy. Function parameters are passed by value by default, except `this`, which uses reference semantics.
- **Arena memory model**:
  - Each scope corresponds to an Arena cursor. Temporary allocations use a contiguous memory region; leaving the scope rolls the cursor back. The language does not expose explicit `free`.
  - Values returned across scopes are copied to memory governed by the parent Arena cursor, avoiding dangling references.
  - Arenas are thread-exclusive. Combined with value semantics, this enables lock-free concurrency for ordinary data. Allocations are automatically aligned to `alignof(T)`.
  - The Arena can reuse memory intelligently. For example, reassignment may allocate a new block when the new value requires more space than the old value, and mark the old memory as reusable.

### LLVM Mapping

- Local variables map to `alloca` or Arena addresses. Copies use `llvm.memcpy`.
- `static` variables map to global constants or global mutable storage.
- Arena uses thread-local buffer, capacity, and cursor state. When capacity is insufficient it expands as needed. Leaving a scope only moves the cursor and does not destruct objects one by one.
- Variable-lock policies `rp`/`wp` are recorded during semantic analysis. LLVM IR emits `__ezrt_lock_read_*` / `__ezrt_lock_write_*` hooks for direct variable reads/writes. The native runtime provides read/write locks indexed by variable name, covering sequential, read-priority, and write-priority scheduling. With `rp`, a writer waiting more than 1 ms blocks later readers from cutting ahead, avoiding long-term starvation.
- The Arena allocator aligns memory by type `alignof`, ensuring SIMD and large structs satisfy target architecture requirements.

---

## 5. Functions and Context Binding

### Syntax

```ez
// Default parameters and explicit return
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

// Currying and parameter placeholder
let addTwo = fn(a = 2, b = ?)

// Capturing closure
const makeAdder = (base: I32): (x: I32) => I32 => {
    return (x: I32): I32 => {
        return base + x
    }
}
let add10 = makeAdder(base = 10)
let value = add10(x = 5)
```

### Semantics and Rules

- Explicit `this` parameters must use a weak reference type `#Type`. `obj.fn()` automatically passes `#obj` as `this`, so users do not need to fill it in. Direct calls may write `fn(this = #obj)`. Ordinary variables still use value semantics.
- Function calls support mixed positional and named arguments, such as `fn(1, c = 3)`. Positional arguments must come before named arguments.
- Parameters may define default values; omitted arguments use those defaults.
- When a function body uses a `{ ... }` block, it must return through an explicit `return`. The last expression is not implicitly returned.
- Anonymous functions can capture local variables used from the current scope and produce closure values. Captured environments live in the current Arena, so closures follow ordinary Arena lifetime rules and should not be stored across scopes after their capture environment has ended.
- The `?` placeholder supports partial application and currying, producing a closure that waits for remaining arguments.

### LLVM Mapping

- Named arguments are reordered at compile time to emit a standard `call`.
- Function values produce closure structs `{ invoke, env }`. Anonymous functions and curried results store captured variables in the Arena; calls load `invoke` and `env` before executing.

---

## 6. Flow Concurrency Runtime

### Syntax

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

### Semantics and Rules

- **flow**: `flow { ... }` is a concurrency scheduling scope. It does not change sequential program semantics. Code inside Flow is semantically executed in source order, but the runtime may optimize scheduling for independent blocking operations, and such scheduling must not change observable behavior.
- **Current implementation**: the compiler records Flow/parallel/suspend-point metadata and emits linkable hooks such as `__ezrt_flow_*`, `__ezrt_parallel_*`, `__ezrt_sleep`, `__ezrt_race_i32`, `__ezrt_task_start_i32`, and `__ezrt_task_join_i32` in LLVM IR. `__ezrt_sleep` actually suspends the current execution point. `race(pl = [...], timeout = ...)` runs zero-capture `() => I32` branches concurrently through the C task runtime on native targets and through `packages/std/emcc/runtime.js` + Asyncify on emcc. `return` inside `flow` / `parallel` blocks is captured as the expression result and does not return early from the outer function. `return` inside nested control flow also participates in expression return-type inference.
- **Blocking operations**: outside Flow, calls such as `fetch()` feel synchronous to the user. Inside Flow, `sleep`, `race(pl)`, zero-capture `I32` `parallel`, and on emcc `fetch`, TCP/UDP, WebSocket, stdin, file system, process, and stream I/O can act as suspend sources that suspend and resume. Platforms without a capability return documented failure values or continue using blocking syscalls; they must not busy-wait on the CPU.
- **parallel blocks**: `const ret = parallel { code... return... }` or `const ret: I32 = parallel { code... return... }` starts a background task when inside Flow, the initializer expression itself is a `parallel` block, it has zero captures, and it returns `I32`. Reading `ret` waits for task completion, and exiting Flow joins unread tasks to ensure side effects are committed. Native, Android, and iOS targets use the C task runtime; emcc uses the JS coroutine runtime. Compound expressions, other return types, or captures of outer locals keep synchronous cooperative lowering.
- **Automatic dependency waiting**: reading an unfinished `parallel` result inside Flow automatically joins it. Current dependency waiting covers native, Android, iOS, and emcc zero-capture `I32` tasks, including inferred and explicit `I32` declarations. emcc standard-library suspend sources restore the wasm stack through Asyncify and preserve sequential ABI.
- **Flow return**: before returning, Flow must ensure all preceding semantic operations are complete and all side effects are committed.
- **race function**: native, Android, iOS, and emcc targets run zero-capture `() => I32` branches from `pl` concurrently, return the first completed value, and cancel or ignore remaining branches. Timeout returns a zero value and marks the timeout slot. Exceptions are returned through the runtime exception slot to the outer `catch`. Capturing closures and non-`I32` return values use synchronous cooperative fallback.
- **cancel**: cancellation does not immediately terminate synchronous code. It only interrupts suspend sources such as I/O, sleep, timer, or wait. When a low-level suspend source is canceled, it throws `Error(code = errCancel, message = "operation cancelled")` and propagates through the synchronous call stack. `catch {}` can check `err.code == errCancel` for special handling.
- **Non-blocking synchronous code**: ordinary synchronous CPU code is not interrupted.
- **Side-effect consistency**: the runtime must not change side-effect order, lock semantics, or observable behavior.

### LLVM Mapping

- **Current**: lowering uses runtime hooks plus Flow/parallel return slots. `sleep`, `race(pl)`, and zero-capture `I32` `parallel` inside Flow are connected to the native task runtime; Android/iOS reuse the same C runtime; emcc uses the Asyncify JS coroutine runtime for suspendable behavior. emcc standard-library `sleep`, HTTP `fetch`, TCP/UDP, WebSocket `wsConnect` / `wsRecv`, stdin, fs, process, and stream I/O carry Asyncify metadata. The CLI automatically adds `-sASYNCIFY`. Future backends can replace the emcc runtime with JSPI or wasm pthreads without changing EzLang syntax.
- **Goal**: native blocking I/O can later be replaced by state machines, platform wait sources such as epoll, io_uring, kqueue, and timerfd, result storage, wakeups, and fuller captured-closure scheduling.

---

## 7. Control Flow

### Syntax

```ez
from "std/fmt" import { toString }
from "std/io" import { print }

// Loops and ranges
loop i in 0...10 { 
    print(msg = toString<I32>(value = i))
}

// Block conditional statements
let x = 5
(x > 0) ? print(msg = "positive")
(x < 0) ? {
  print(msg = "negative")
} : (x == 0) ? {
  print(msg = "zero")
}

// Pattern matching
let i = 0
match {
    (i == 0) ? i = 100,
    (i > 0) ? { (i > 10) ? continue; i = i - 1; },
    (i > 0) ? { i = i + 1; break; },
    (true) ? { i = i - 100; }
}

// Exception catching
const err = catch {
    throw Error(code = 1, message = "hello")
}
(typeof err & Error == Error) ? print(msg = err.message)
```

### Semantics and Rules

- **Conditional expression**: `condition ? expr : expr`. It is both an expression and a control-flow form; there is no `if/else`. `condition ? expression` or `condition ? { block }` is a conditional statement that executes when the condition is true.
- **loop**: `0...10` means the half-open range `[0, 10)`.
- Block expressions `{ ... }` return `Void`.
- **match**: evaluates from top to bottom. After a matching branch executes, it continues checking later branches unless `break` is used explicitly.
- **continue**: in `loop`, jumps to the next iteration; in `match`, skips the rest of the current branch and continues checking later branches.
- **break**: exits the current `loop` or `match`.
- **throw**: writes the `Error` exception slot and jumps to the nearest `catch {}` exit. Without an active `catch`, an uncaught exception diagnostic is printed and the process terminates with exit code 1. Synchronous function call boundaries check the exception slot and keep propagating outward.
- **catch**: returns the exception value thrown inside the block or by called functions. If no exception is captured, it returns a zero `Error` (`code = 0`). `Error` carries throw-site file, line, column, and a lightweight stack fragment that can be read through `err.file`, `err.line`, `err.column`, and `err.trace`.

### LLVM Mapping

- Loops map to `br` and `phi` node structures.
- Conditional selection maps to `phi` nodes or branch jumps.

---

## 8. Operators, Expressions, and SIMD

### Syntax

```ez
// Arithmetic, bitwise, and logical operators
let a: I32 = 10; let b: I32 = 3
let sum = a + b; let rem = a % b
let logic = (a > b) && !(a == b)
let shiftBy: U32 = 1
let shift = a << shiftBy
let bit = a & 0b1111

// Compound assignment
a += 5
a &= 0b1111

// SIMD vector syntax
let v1: Vec<I32>[4] = Vec[1, 2, 3, 4]
let v2: Vec<I32>[4] = Vec[5, 6, 7, 8]
let vSum = v1 + v2
let scaled = v1 * 2  // Scalar broadcast
let masked = (v1 < v2) ? v1 : v2
```

### Semantics and Rules

- **Arithmetic and bitwise operators**: supports `+`, `-`, `*`, `/`, `%`, and `&`, `|`, `^`, `<<`, `>>`. Integer division floors. Floating-point operations follow IEEE 754. Unsigned division, remainder, and right shift generate unsigned operations; signed right shift is arithmetic. Shift right operands must be unsigned types.
- **Logical and comparison operators**: supports `&&`, `||`, `!`, and `==`, `!=`, `<`, `>`, `<=`, `>=`. Logical operations short-circuit. Struct, optional, and union values support `==`/`!=` by recursively comparing fields with the same layout. `Str` fields currently use pointer equality; use standard-library string functions for content comparison. Aggregate types do not support `<`, `>`, `<=`, or `>=`.
- **Compound assignment**: operators such as `+=` and `<<=` are equivalent to expanded operations. The current implementation generates load, operation, and store sequences for bare variables, struct fields, and array/List index lvalues, while avoiding duplicate evaluation of the base object or index expression.
- **Precedence**: `!` > `*`, `/`, `%` > `+`, `-` > `<<`, `>>` > `&` > `^` > `|` > comparisons > `&&` > `||`. Bitwise `&` has higher precedence than comparison `==` but lower than shifts. Parentheses are recommended to avoid ambiguity.
- **SIMD semantics**: `Vec<Type>[N]` operations execute element-wise in parallel. Vector lengths must match. Mixed scalar/vector operations broadcast the scalar to an equal-width vector before computing. Vector comparisons produce equal-width boolean masks.

### LLVM Mapping

- Basic operators map to corresponding LLVM instructions, such as `add`, `sub`, `icmp`, `fcmp`, `shl`, `ashr`/`lshr`, `and`, `sdiv`/`udiv`, and `srem`/`urem`.
- Logical operations map to conditional branches and `phi` nodes for short-circuiting.
- Compound assignment maps to load, operation, and store sequences.
- Vector types map to LLVM vector types, such as `<4 x i32>`, and operations map to SIMD instructions like `add <4 x i32>` and `icmp <4 x i32>`. Mixed vector/scalar operations broadcast through `insertelement` first.

---

## 9. Module System and External Linking

### Syntax

```ez
// Module import/export
from "./std.ez" import {print as log}
export let x = 1

// extern syntax: reference external ABI libraries per target platform
// Supported: static libraries (.a/.lib), dynamic libraries (.so/.dylib/.dll), object files (.o/.bc), LLVM IR (.ll), frameworks (.framework)
// Link this library on all targets
extern "./libs/libcrypto.a"
// Link only for linux
extern "./libs/libssl.so" for linux
// Multiple target examples
extern "./libs/win32.lib" for windows
// Android/iOS libraries
extern "./libs/android/libjni.a" for android
extern "./libs/ios/objc.framework" for ios
// WebAssembly imports a JS module
extern "./js/bindings.js" for emcc
// Link LLVM IR module or bytecode
extern "./runtime.ll"
extern "./runtime.bc" for macos

// Declare external symbols, used with extern
// All external symbols must be declared explicitly and support type-safe C ABI calls
declare const crypto_hash: (data: Blob, len: I64) => Blob
declare const ssl_connect: (host: Str, port: I32) => I32
declare const curl_easy_init: () => Blob
declare static version: Str
```

### Semantics and Rules

- **import / export**: compile-time import brings exported items from another EzLang module into the current scope. `export` exposes symbols to other modules.
  - Only `.ez` source-file imports are supported; binary object files are not imported directly.
- **extern**: references external ABI libraries or build artifacts, with optional filtering by compile target.
  - Without a `for` clause, the library links on all targets.
  - `for target` links only when compiling that target. Supported targets are `linux`, `macos`, `windows`, `android`, `ios`, and `emcc`.
  - Supported formats: static libraries (`.a`, `.lib`), dynamic libraries (`.so`, `.dylib`, `.dll`), object files (`.o`), LLVM IR (`.ll`), LLVM bytecode (`.bc`), frameworks (`.framework`), and JS modules (`.js` for emcc).
  - On the `emcc` target, imported JS modules are converted to Emscripten bindings at compile time.
- **declare**: declares external library symbols for type checking and link-time symbol resolution.
  - Functions, global variables, and static variables can be declared.
  - `declare` should be paired with at least one active `extern` for the current target. Without an associated `extern`, the compiler reports a link diagnostic.
  - The compiler does not pre-scan binary symbol tables; whether a symbol actually exists is verified by the backend linker.
  - All external symbols must be explicit, enabling C ABI-compatible external library calls.
- EzLang executes top-level statements in the entry file in source order. Users are not required to define `main` explicitly. If source defines `main`, the host entrypoint uses it; other functions in the file must still be called explicitly.

### LLVM Mapping

- EzLang module import is implemented through compile-time symbol resolution and source merging.
- `extern` library paths are passed to the LLVM/linker pipeline, and `for target` clauses are filtered at compile time.
- `declare` emits LLVM `external global` or `declare` declarations with the C ABI calling convention.
- `extern` plus `declare` gives zero-overhead external library linking with no runtime performance cost.

---

## 10. Metaprogramming, Syntax Sugar, and Safety

### Syntax

```ez
from "std/io" import { print }

// Metaprogramming: decorators
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
x = 2 // Triggers the interceptor print

// Markup syntax and syntax sugar
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
</text> // Equivalent to text(color = "blue", children = ["Welcome", div(id = 1), 1+2])

const add = (a: I32, b: I32): I32 => {
    return a + b
}
let val = 10 -> add(a = %, b = 5) // Pipeline syntax, equivalent to add(a = 10, b = 5)
let name = "EzLang"
let msg = "Hello {{name}}"        // Interpolation expression result must be Str

// Safety mechanisms: type assertions and runtime checks
declare const malloc: (size: I32) => Blob
type User = Blob
let b: Blob = malloc(size = 10)
let user = User! b
let err = Error(code = 1, message = "boom")
let isError = typeof err & Error == Error
```

### Semantics and Rules

- **Metaprogramming and decorators**: `@Dec` wraps a top-level variable as `Meta<T>` and calls the decorator function during module initialization. The decorator receives `Meta<T>` or `this: #Meta<T>` and can read/write `value`, `getter`, `setter`, `t`, and `name`.
  - `value` is the real storage of the decorated variable.
  - `getter` is a `() => T` closure. If unset, reads return `value` directly.
  - `setter` is a `(value: T) => Void` closure. If unset, writes update `value` directly.
  - `t` and `name` are compiler-generated type and variable names for diagnostics, logging, and metaprogramming.
  - Decorators may be generic functions; the compiler monomorphizes them by decorated variable type.
- **Markup syntax**: XML-style markup only lowers to ordinary function calls. A factory function of the same name must exist in scope. The compiler passes attributes as named arguments and packs child nodes into a `children` array. Missing factories, attribute type mismatches, or `children` type mismatches are semantic errors.
- **Pipeline and interpolation**: pipeline `->` with `%` rewrites to a named-argument call, such as `a -> fn(x = %)` becoming `fn(x = a)`. String interpolation uses `{{expr}}`; the inner expression is parsed as EzLang expression syntax and must produce `Str`, such as `{{first + last}}`.
- **Type-safety mechanisms**:
  - `Type! expr`: unchecked type assertion, useful for forced unwrap or bit-level reinterpretation.
  - `typeof`: returns the stable `I32` TypeID generated for an expression or type name. Equality/inequality against `Void` for weak references lowers to reading the weak reference validity bit.

### LLVM Mapping

- Decorators generate `Meta<T>` structs. `getter`/`setter` closures are stored in closure slots. Reads/writes of decorated variables call the closure when the entrypoint is not empty; otherwise they access `value` directly.
- Markup syntax must find a same-name factory function and emit an ordinary `call`. Attributes are reordered by function parameter name, and child nodes are passed to `children` through the current array/List ABI. Missing factories or parameter type mismatches are compile errors. Pipeline syntax is expanded in the frontend. String interpolation lowers static text and `Str` expression segments into memory-copy concatenation logic.
- `Type! expr` maps to bit-level reinterpretation (`bitcast`) or `load` operations.
- `typeof` maps to stable TypeID constants. `typeof weakRef == Void` / `typeof weakRef != Void` maps to reading the `ok` bit of weak references `{ ok, ptr }`.
