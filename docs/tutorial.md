# EzLang 示例教程

本教程展示 EzLang 的基本写法。

## 变量

```ez
let x: I32 = 42;
const name: Str = "EzLang";
```

`let` 可变，`const` 不可变。

## 函数

```ez
const add = (a: I32, b: I32): I32 => {
    return a + b;
};

let result = add(a = 1, b = 2);
```

函数调用使用具名参数。

## 结构体

```ez
struct Point {
    x: I32;
    y: I32 = 0;
};

let p = Point(x = 10);
```

字段可设置默认值。

## 条件与 match

```ez
let x = 1;
match {
    (x == 0) ? x = 10,
    (true) ? x = 20
};
```

## 循环

```ez
let sum: I32 = 0;
loop i in 0...10 {
    sum = sum + i;
};
```

## 标准库

```ez
from "std/io" import { println };

println(msg = "Hello EzLang");
```

## Flow

```ez
from "std/time" import { sleep };

flow {
    sleep(ms = 10);
};
```

`flow` 内阻塞调用会被标记为 suspend point。

## 构建项目

创建 `project.toml`：

```toml
[project]
name = "hello"
version = "0.1.0"
main = "src/index.ez"

[[output]]
arch = "x86_64"
os = "linux"
dir = "dist/linux"
```

运行：

```bash
python -m cli.ez build --project project.toml
```
