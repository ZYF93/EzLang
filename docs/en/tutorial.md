# EzLang Tutorial

[中文](../tutorial.md)

This tutorial shows the basic EzLang syntax.

## Variables

```ez
let x: I32 = 42;
const name: Str = "EzLang";
```

`let` declares a mutable binding. `const` declares an immutable binding.

## Functions

```ez
const add = (a: I32, b: I32): I32 => {
    return a + b;
};

let result = add(a = 1, b = 2);
```

Function calls use named arguments.

## Structs

```ez
struct Point {
    x: I32;
    y: I32 = 0;
};

let p = Point(x = 10);
```

Fields can define default values.

## Conditions and Match

```ez
let x = 1;
match {
    (x == 0) ? x = 10,
    (true) ? x = 20
};
```

## Loops

```ez
let sum: I32 = 0;
loop i in 0...10 {
    sum = sum + i;
};
```

## Standard Library

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

Blocking calls inside `flow` are marked as suspend points.

## Build a Project

Create `project.toml`:

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

Run:

```bash
ez build --project project.toml
```
