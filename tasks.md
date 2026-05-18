# EzLang 开发任务清单 (TDD 模式)

技术栈: ANTLR4 + Python3 + llvmlite

---

## 阶段 0: 项目基础设施

### 0.1 项目结构初始化
- [ ] 创建 `compiler/src/` 目录结构
- [ ] 创建 `compiler/tests/` 测试目录
- [ ] 创建 `packages/std/` 标准库目录
- [ ] 创建 `cli/` 命令行工具目录
- [ ] 创建 `tests/e2e/` 端到端测试目录

### 0.2 开发环境配置
- [ ] 编写 `compiler/setup.py` 或 `pyproject.toml`
- [ ] 配置 Python 虚拟环境
- [ ] 验证 `antlr4-tools` 安装与代码生成
- [ ] 验证 `llvmlite` LLVM 绑定可用
- [ ] 配置 pytest 测试框架

---

## 阶段 1: 编译器前端 (ANTLR4 语法与词法)

### 1.1 基础语法定义
- [ ] 编写 `grammar/EzLang.g4` 基础词法规则
  - 关键字: `let`, `const`, `static`, `struct`, `type`, `declare`, `loop`, `break`, `continue`, `import`, `export`, `from`, `match`, `catch`, `throw`, `flow`, `typeof`
  - 标识符与字面量规则
  - 注释规则 (单行 `//`, 块注释 `/* */`)
- [ ] 生成 ANTLR4 Python 解析器代码
- [ ] 编写 `examples/basics.ez` 测试用例
- [ ] 编写测试验证词法分析器正确工作

### 1.2 类型系统语法
- [ ] 扩展语法支持基本类型 (`I8`, `I32`, `I64`, `U8`, `U32`, `U64`, `F32`, `F64`, `Str`, `Bool`, `Void`)
- [ ] 支持可选类型 `Type?`
- [ ] 支持联合类型 `Type1 | Type2`
- [ ] 支持数组类型 `Type[]` / `List<Type>`
- [ ] 支持 SIMD 向量类型 `Vec<Type>[N]`
- [ ] 支持泛型参数 `<T, U>`
- [ ] 支持类型别名 `type Name = { ... }`
- [ ] 支持 `typeof` 表达式
- [ ] 编写 `examples/types.ez` 测试用例
- [ ] 编写测试验证类型语法解析

### 1.3 结构体与方法语法
- [ ] 支持 `struct Name { ... }` 定义
- [ ] 支持结构体字段与默认值 `field: Type = default`
- [ ] 支持结构体展开 `...Base`
- [ ] 支持方法定义 `method = (this: Type, args...) => expr`
- [ ] 支持命名初始化 `Struct(field = value)`
- [ ] 支持实例展开 `Struct(...instance, field = value)`
- [ ] 编写 `examples/structs.ez` 测试用例
- [ ] 编写测试验证结构体语法解析

### 1.4 函数与表达式语法
- [ ] 支持函数字面量 `(name: Type, ...) => expr`
- [ ] 支持具名参数调用 `fn(a = 1, b = 2)`
- [ ] 支持 `return` 语句
- [ ] 支持管道语法 `expr -> fn(x = %)`
- [ ] 支持柯里化占位符 `?`
- [ ] 支持字符串插值 `"Hello {{name}}"`
- [ ] 支持标记语法 `<tag attr=value>...</tag>`
- [ ] 支持装饰器 `@decorator`
- [ ] 编写 `examples/functions.ez` 测试用例
- [ ] 编写测试验证函数与表达式解析

### 1.5 流程控制语法
- [ ] 支持条件表达式 `cond ? expr : expr`
- [ ] 支持条件语句 `cond ? { block }`
- [ ] 支持 `loop` 循环与范围 `loop i in 0...10 { }`
- [ ] 支持 `match` 模式匹配
- [ ] 支持 `break` / `continue`
- [ ] 支持 `throw` / `catch` 异常处理
- [ ] 支持 `flow { }` 并发块
- [ ] 编写 `examples/control.ez` 测试用例
- [ ] 编写测试验证流程控制解析

### 1.6 运算符与 SIMD 语法
- [ ] 支持算术运算符 `+`, `-`, `*`, `/`, `%`
- [ ] 支持位运算符 `&`, `|`, `^`, `<<`, `>>`
- [ ] 支持比较运算符 `==`, `!=`, `<`, `>`, `<=`, `>=`
- [ ] 支持逻辑运算符 `&&`, `||`, `!`
- [ ] 支持复合赋值 `+=`, `-=`, `*=`, `/=`, `&=`, etc.
- [ ] 支持 SIMD 向量字面量 `Vec[1, 2, 3, 4]`
- [ ] 支持 SIMD 向量运算
- [ ] 编写 `examples/operators.ez` 测试用例
- [ ] 编写 `examples/simd.ez` 测试用例
- [ ] 编写测试验证运算符解析与优先级

### 1.7 模块系统语法
- [ ] 支持 `import` / `export` 声明
- [ ] 支持 `from "path" import { ... }`
- [ ] 支持 `declare` 外部函数/变量/类型声明
- [ ] 支持 `extern "path"` 外部库引用（所有目标）
- [ ] 支持 `extern "path" for target` 按目标平台按需引用
- [ ] 编写 `examples/modules.ez` 测试用例
- [ ] 编写 `examples/extern.ez` 外部库链接测试用例
- [ ] 编写测试验证模块系统解析
- [ ] 编写测试验证 extern 语法解析

---

## 阶段 2: 语义分析器

### 2.1 符号表与作用域
- [ ] 实现作用域栈 (Scope Stack)
- [ ] 实现符号表 (Symbol Table)
- [ ] 实现变量声明检查 (重复声明检查)
- [ ] 实现变量引用检查 (未声明变量)
- [ ] 实现 `let` / `const` / `static` 语义区分
- [ ] 编写 `examples/vars.ez` 测试用例
- [ ] 编写测试验证符号解析

### 2.2 类型检查器
- [ ] 实现基本类型推导与检查
- [ ] 实现可选类型 `?` 拆包检查
- [ ] 实现联合类型 `|` 类型检查
- [ ] 实现数组类型检查
- [ ] 实现 SIMD 向量类型检查
- [ ] 实现结构体成员访问类型检查
- [ ] 实现函数签名匹配检查
- [ ] 实现泛型单态化 (Monomorphization)
- [ ] 实现 `typeof` 类型运算
- [ ] 实现类型断言 `Type! expr` 检查
- [ ] 编写 `examples/type_checks.ez` 测试用例
- [ ] 编写测试验证类型检查

### 2.3 结构体与方法语义
- [ ] 实现结构体布局计算与对齐
- [ ] 实现结构体展开 `...Base` 语义
- [ ] 实现方法 `this` 参数绑定检查
- [ ] 实现字段默认值处理
- [ ] 实现命名初始化参数匹配
- [ ] 实现实例展开 `...instance` 语义
- [ ] 编写测试验证结构体语义

### 2.4 函数语义检查
- [ ] 实现参数命名检查与重排
- [ ] 实现默认参数处理
- [ ] 实现返回值类型检查
- [ ] 实现 `return` 语句位置检查
- [ ] 实现柯里化 `?` 占位符语义
- [ ] 实现管道语法 `-> %` 重写
- [ ] 实现字符串插值展开
- [ ] 实现标记语法 `<tag>` 翻译
- [ ] 编写测试验证函数语义

### 2.5 Arena 内存模型分析
- [ ] 实现作用域与 Arena 游标映射
- [ ] 实现跨作用域返回值拷贝分析
- [ ] 实现值语义拷贝点标记
- [ ] 实现内存对齐检查
- [ ] 编写 `examples/arena.ez` 测试用例
- [ ] 编写测试验证内存模型分析

### 2.6 Flow 并发语义分析
- [ ] 实现 `flow { }` 块检测
- [ ] 实现阻塞操作 suspend point 标记
- [ ] 实现 `race()` 函数语义分析
- [ ] 实现数据流依赖分析
- [ ] 编写 `examples/flow.ez` 测试用例
- [ ] 编写测试验证并发语义分析

### 2.7 Extern 语义分析
- [ ] 实现 `extern` 库路径解析与存在性检查
- [ ] 实现 `for target` 子句目标平台验证
- [ ] 实现 `declare` 符号与 `extern` 库的关联检查
- [ ] 实现跨模块 extern 符号导出检查
- [ ] 实现按编译目标过滤 extern 引用
- [ ] 编写测试验证 extern 语义检查

---

## 阶段 3: LLVM IR 代码生成 (llvmlite)

### 3.1 基础类型映射
- [ ] 实现整数类型映射 (I8, I32, I64, U8, etc.)
- [ ] 实现浮点类型映射 (F32, F64)
- [ ] 实现 `Str` 类型映射与内存布局
- [ ] 实现 `Bool` 类型映射
- [ ] 实现 `Void` 类型处理
- [ ] 实现可选类型 `Type?` → `{ i1 has_value, T value }`
- [ ] 实现联合类型 `Type1 | Type2` → tag + variant 结构
- [ ] 编写测试验证基础类型 IR 生成

### 3.2 复合类型映射
- [ ] 实现数组 `Type[]` → `{ i64 len, i64 cap, T* data }`
- [ ] 实现 SIMD 向量 `Vec<T>[N]` → LLVM 向量类型 `<N x T>`
- [ ] 实现字典 `Dict<K, V>` → 哈希表结构
- [ ] 实现函数类型 → 函数指针类型
- [ ] 编写测试验证复合类型 IR 生成

### 3.3 结构体与方法代码生成
- [ ] 实现结构体类型 LLVM 映射
- [ ] 实现结构体字段 `getelementptr` 访问
- [ ] 实现结构体初始化与默认值
- [ ] 实现结构体展开 `...Base` memcpy
- [ ] 实现实例展开 `...instance` memcpy
- [ ] 实现方法函数生成与 `this` 绑定
- [ ] 实现内置结构体 `Date`, `Error`, `Blob`
- [ ] 编写测试验证结构体 IR 生成

### 3.4 表达式与运算符代码生成
- [ ] 实现算术运算符 IR 生成 (`add`, `sub`, `mul`, `sdiv`/`udiv`, `srem`/`urem`)
- [ ] 实现位运算符 IR 生成 (`and`, `or`, `xor`, `shl`, `lshr`/`ashr`)
- [ ] 实现比较运算符 IR 生成 (`icmp`, `fcmp`)
- [ ] 实现逻辑运算符短路求值 (分支 + phi)
- [ ] 实现复合赋值 (load → op → store)
- [ ] 实现 SIMD 向量运算 IR 生成
- [ ] 编写测试验证表达式 IR 生成

### 3.5 变量与内存代码生成
- [ ] 实现 `let` / `const` 局部变量 `alloca`
- [ ] 实现 `static` 全局变量
- [ ] 实现值语义拷贝 `llvm.memcpy`
- [ ] 实现 Arena 分配器集成
- [ ] 实现作用域结束游标回退
- [ ] 实现跨作用域返回值拷贝
- [ ] 编写测试验证内存模型 IR 生成

### 3.6 流程控制代码生成
- [ ] 实现条件表达式 `phi` 节点
- [ ] 实现条件语句分支跳转
- [ ] 实现 `loop` 循环结构 (br + phi)
- [ ] 实现 `match` 模式匹配代码生成
- [ ] 实现 `break` / `continue` 跳转
- [ ] 实现 `throw` / `catch` 异常处理
- [ ] 编写测试验证流程控制 IR 生成

### 3.7 函数代码生成
- [ ] 实现函数定义与基本块
- [ ] 实现具名参数重排
- [ ] 实现默认参数注入
- [ ] 实现 `return` 语句
- [ ] 实现柯里化闭包结构体
- [ ] 实现管道语法重写
- [ ] 实现字符串插值拼接
- [ ] 实现标记语法翻译
- [ ] 实现装饰器 `Meta<T>` 包装
- [ ] 编写测试验证函数 IR 生成

### 3.8 模块系统代码生成
- [ ] 实现 `import` 符号解析
- [ ] 实现 `export` 符号导出
- [ ] 实现 `declare` 外部函数/变量声明
- [ ] 实现 `extern` 库路径传递给 LLVM 链接器
- [ ] 实现 `for target` 子句按编译目标过滤
- [ ] 实现所有外部格式统一链接（`.a` / `.so` / `.dylib` / `.lib` / `.o` / `.ll` / `.bc` / `.framework` / `.js`）
- [ ] 实现 `declare` 符号与 extern 库的关联验证
- [ ] 实现 Emscripten JS 模块绑定生成
- [ ] 编写测试验证模块系统
- [ ] 编写测试验证 extern 链接

---

## 阶段 4: 标准库实现 (packages/std)

### 4.1 内存与错误处理 (`std/mem`)
- [ ] 实现 `copy(dst, src, count)` → `llvm.memcpy`
- [ ] 实现 `memset(dst, value, count)` → `llvm.memset`
- [ ] 实现 `allocRaw(size)` → Arena 分配
- [ ] 定义 `errCancel`, `errTimeout`, `errUnsupported`, `errIO`, `errNotFound`, `errPermission` 常量
- [ ] 编写测试验证 `std/mem`

### 4.2 输入输出 (`std/io`)
- [ ] 实现 `print(msg)` → 平台相关输出
  - Linux/macOS/Windows: `printf` / `stdout`
  - Android: `__android_log_print`
  - iOS: `NSLog`
  - emcc: `console.log`
- [ ] 实现 `println(msg)`
- [ ] 实现 `error(msg)` → `stderr` / `console.error`
- [ ] 实现 `readLine()` → `Str?` (桌面平台)
- [ ] 编写测试验证 `std/io`

### 4.3 文件系统 (`std/fs`)
- [ ] 定义 `FileStat` 结构体
- [ ] 实现 `readFile(path)` → `Blob?`
- [ ] 实现 `writeFile(path, content)` → `Bool`
- [ ] 实现 `appendFile(path, content)` → `Bool`
- [ ] 实现 `removeFile(path)` → `Bool`
- [ ] 实现 `mkdir(path)` → `Bool`
- [ ] 实现 `removeDir(path, recursive)` → `Bool`
- [ ] 实现 `listDir(path)` → `Str[]?`
- [ ] 实现 `exists(path)` → `Bool`
- [ ] 实现 `isDir(path)` → `Bool`
- [ ] 实现 `stat(path)` → `FileStat?`
- [ ] 实现 `absPath(path)` → `Str?`
- [ ] 实现 Android/iOS 沙盒路径处理
- [ ] 实现 emcc Emscripten MEMFS/IDBFS
- [ ] 编写测试验证 `std/fs`

### 4.4 操作系统接口 (`std/os`)
- [ ] 实现 `args()` → `Str[]`
- [ ] 实现 `env(key)` → `Str?`
- [ ] 实现 `setEnv(key, value)` → `Bool`
- [ ] 实现 `cwd()` → `Str`
- [ ] 实现 `exit(code)` → `Void`
- [ ] 实现 `pid()` → `I32`
- [ ] 实现 `platform()` → `Str`
- [ ] 实现 `arch()` → `Str`
- [ ] 编写测试验证 `std/os`

### 4.5 时间 (`std/time`)
- [ ] 定义 `Duration` 结构体与方法
- [ ] 实现 `now()` → `Date`
- [ ] 实现 `timestamp()` → `I64`
- [ ] 实现 `sleep(ms)` → 同步阻塞 (flow 外) / suspend point (flow 内)
- [ ] 实现 `Date` 结构体方法 (`getYear`, `getMonth`, `getDay`, `add`, `sub`, `format`)
- [ ] 编写测试验证 `std/time`

### 4.6 网络 HTTP 客户端 (`std/net/http`)
- [ ] 定义 `Headers` 类型
- [ ] 定义 `HttpRequest` 结构体
- [ ] 定义 `HttpResponse` 结构体与 `text()` 方法
- [ ] 实现 `fetch(url)` → `HttpResponse?`
  - Linux/macOS/Windows: libcurl
  - Android: HttpURLConnection
  - iOS: NSURLSession
  - emcc: JS `fetch` 绑定
- [ ] 实现 `fetchEx(req)` → `HttpResponse?`
- [ ] 实现 flow 内 suspend point 语义
- [ ] 编写测试验证 HTTP 客户端

### 4.7 网络 HTTP 服务端 (`std/net/http`)
- [ ] 定义 `RouteHandler` 类型
- [ ] 定义 `HttpServer` 结构体与方法 (`on`, `start`, `stop`)
- [ ] 实现 `createServer(host, port)` → `HttpServer`
- [ ] 实现 flow 内并发调度
- [ ] 编写测试验证 HTTP 服务端 (桌面平台)

### 4.8 网络 TCP/UDP (`std/net`)
- [ ] 定义 `TcpConn` 结构体 (`read`, `write`, `close`)
- [ ] 定义 `TcpListener` 结构体 (`accept`, `close`)
- [ ] 实现 `tcpConnect(host, port)` → `TcpConn?`
- [ ] 实现 `tcpListen(host, port)` → `TcpListener?`
- [ ] 定义 `UdpSocket` 结构体 (`send`, `recv`, `close`)
- [ ] 实现 `udpBind(host, port)` → `UdpSocket?`
- [ ] 编写测试验证 TCP/UDP

### 4.9 WebSocket (`std/net/ws`)
- [ ] 定义 `WsConn` 结构体 (`send`, `recv`, `close`)
- [ ] 实现 `wsConnect(url)` → `WsConn?`
- [ ] 实现 flow 内 `recv()` suspend point
- [ ] 编写测试验证 WebSocket

### 4.10 数据结构扩展 (`std/collections`)
- [ ] 实现 `List<T>` 扩展方法 (`push`, `pop`, `shift`, `unshift`, `sort`, `filter`, `map`, `find`, `len`, `slice`)
- [ ] 实现 `Dict<K, V>` 扩展方法 (`keys`, `values`, `has`, `delete`, `len`)
- [ ] 编写测试验证集合扩展

### 4.11 格式化与编码 (`std/fmt`)
- [ ] 实现 `toString<T>(value)` → `Str`
- [ ] 实现 `parseInt(s)` → `I32?`
- [ ] 实现 `parseI64(s)` → `I64?`
- [ ] 实现 `parseF64(s)` → `F64?`
- [ ] 实现 `format(template, args)` → `Str`
- [ ] 实现 `b64Encode(data)` → `Str`
- [ ] 实现 `b64Decode(s)` → `Blob?`
- [ ] 实现 `jsonStringify<T>(data)` → `Str`
- [ ] 实现 `jsonParse<T>(s)` → `T`
- [ ] 实现 `msgpackEncode<T>(data)` → `Blob`
- [ ] 实现 `msgpackDecode<T>(data)` → `T`
- [ ] 实现 `urlEncode(s)` → `Str`
- [ ] 实现 `urlDecode(s)` → `Str?`
- [ ] 编写测试验证格式化与编码

---

## 阶段 5: Flow 运行时 (Runtime)

### 5.1 运行时核心
- [ ] 实现协程调度器 (协作式多任务)
- [ ] 实现 suspend point 机制
- [ ] 实现 wakeup 回调注册
- [ ] 实现事件循环 (epoll / kqueue / IOCP / WASI)
- [ ] 实现任务队列与调度
- [ ] 编写测试验证运行时核心

### 5.2 IO 事件集成
- [ ] 实现文件 IO suspend/wakeup
- [ ] 实现网络 IO suspend/wakeup (socket read/write)
- [ ] 实现 timer suspend/wakeup (`sleep`)
- [ ] 实现 flow 内自动依赖等待
- [ ] 编写测试验证 IO 事件

### 5.3 Race 与 Cancel
- [ ] 实现 `race(pl, timeout)` 函数
- [ ] 实现任务取消传播
- [ ] 实现 `errCancel` / `errTimeout` 错误抛出
- [ ] 实现 suspend source 取消
- [ ] 编写测试验证 race 与 cancel

---

## 阶段 6: CLI 工具链实现

### 6.1 `ez` 命令入口
- [ ] 实现 CLI 参数解析 (argparse / click)
- [ ] 实现子命令路由
- [ ] 实现全局选项 (`--help`, `--version`, `-v` verbose)
- [ ] 编写 `cli/ez.py` 入口文件

### 6.2 `ez build` 编译命令
- [ ] 实现 `project.toml` 解析 (`[project]`, `[[output]]`)
- [ ] 实现源文件发现与依赖图
- [ ] 实现编译管道: parse → semantic → IR → object
- [ ] 实现多目标交叉编译 (arch + os)
- [ ] 实现优化等级支持 (`optimize = 0-3`)
- [ ] 实现插件加载 (`[[plugins]]`)
- [ ] 实现输出目录管理 (`dir`)
- [ ] 编写测试验证 `ez build`

### 6.3 `ez run` 运行命令
- [ ] 实现本地可执行文件构建与运行
- [ ] 实现 stdin/stdout 重定向
- [ ] 实现退出码透传
- [ ] 验证非本地目标报错 (android/ios/emcc)
- [ ] 编写测试验证 `ez run`

### 6.4 `ez install` 依赖安装
- [ ] 实现 `[deps]` 解析
- [ ] 实现本地路径依赖 (`"./lib/std.ez"`)
- [ ] 实现 Workspace 内部依赖 (`"@workspace"`)
- [ ] 实现版本号远端依赖下载 (`"0.1.0"`)
- [ ] 实现 `[workspace].members` glob 解析
- [ ] 编写测试验证 `ez install`

### 6.5 `ez fmt` 格式化命令
- [ ] 实现 AST 到格式化源码的生成
- [ ] 实现缩进、换行、空格规范
- [ ] 实现多文件批量格式化
- [ ] 实现 dry-run 模式 (只检查不修改)
- [ ] 编写测试验证 `ez fmt`

### 6.6 `ez release` 发布命令
- [ ] 实现包元数据收集
- [ ] 实现注册表 API 调用 (`registry` 字段)
- [ ] 实现包文件打包与上传
- [ ] 实现版本号验证
- [ ] 实现 `public = false` 检查
- [ ] 编写测试验证 `ez release`

---

## 阶段 7: 端到端测试与集成

### 7.1 编译器端到端测试
- [ ] 编译 `examples/hello.ez` 并运行验证输出
- [ ] 编译 `examples/types.ez` 验证类型系统
- [ ] 编译 `examples/structs.ez` 验证结构体
- [ ] 编译 `examples/functions.ez` 验证函数
- [ ] 编译 `examples/control.ez` 验证流程控制
- [ ] 编译 `examples/operators.ez` 验证运算符
- [ ] 编译 `examples/simd.ez` 验证 SIMD
- [ ] 编译 `examples/arena.ez` 验证内存模型

### 7.2 标准库集成测试
- [ ] `std/io` 打印与输入测试
- [ ] `std/fs` 文件读写测试
- [ ] `std/os` 系统调用测试
- [ ] `std/time` 时间与睡眠测试
- [ ] `std/net` HTTP 客户端测试
- [ ] `std/net` HTTP 服务端测试
- [ ] `std/collections` 扩展方法测试
- [ ] `std/fmt` 编码解码测试

### 7.3 Flow 并发集成测试
- [ ] 测试 flow 内无依赖 IO 并发
- [ ] 测试 flow 内有依赖自动等待
- [ ] 测试 race 取首个完成结果
- [ ] 测试 race timeout 取消
- [ ] 测试 cancel 传播与错误处理

### 7.4 多平台编译测试
- [ ] Linux x86_64 编译与运行
- [ ] macOS aarch64 编译与运行
- [ ] Windows x86_64 交叉编译
- [ ] Android aarch64 交叉编译
- [ ] iOS aarch64 交叉编译
- [ ] Emscripten wasm32 编译

---

## 阶段 8: 文档与收尾

### 8.1 文档完善
- [ ] 编写编译器架构文档
- [ ] 编写运行时设计文档
- [ ] 编写 CLI 工具使用手册
- [ ] 编写标准库 API 文档
- [ ] 编写示例教程

### 8.2 性能优化
- [ ] 编译速度优化
- [ ] 生成代码性能优化
- [ ] Arena 分配器优化
- [ ] 运行时调度延迟优化

### 8.3 错误信息改善
- [ ] 语法错误位置与提示
- [ ] 类型错误详细信息
- [ ] 语义错误修复建议
- [ ] 运行时错误堆栈

---

## 里程碑

| 里程碑 | 描述              | 交付物                                    |
| ------ | ----------------- | ----------------------------------------- |
| M1     | 编译器前端完成    | ANTLR 语法, 解析器, 语义分析器            |
| M2     | LLVM 代码生成完成 | 可编译 .ez 到原生可执行文件               |
| M3     | 标准库基础完成    | std/mem, std/io, std/fs, std/os, std/time |
| M4     | Flow 运行时完成   | flow {} 并发调度与 IO suspend             |
| M5     | CLI 工具链完成    | ez build / run / install / fmt / release  |
| M6     | 标准库网络完成    | std/net HTTP/TCP/UDP/WebSocket            |
| M7     | 多平台编译完成    | Linux/macOS/Windows/Android/iOS/emcc      |
| M8     | 1.0 发布          | 完整文档, 所有测试通过                    |

---

## 开发原则

1. **TDD 优先**: 先写 `examples/*.ez` 测试用例，再写编译器代码让测试通过
2. **语法先行**: 每次语言特性或语法改动，优先修改 `grammar/EzLang.g4`，然后使用 ANTLR4 CLI 工具重新生成解析器代码
3. **小步提交**: 每个小功能完成即提交，保持主分支可运行
4. **平台抽象**: 标准库上层 API 统一，底层通过 `declare` 链接不同平台实现
5. **值语义**: 默认按值传递，利用 Arena 自动管理内存，避免显式 `free`
6. **Flow 语义**: 所有阻塞 IO 在 flow 内自动并发，flow 外同步阻塞，不引入 async/await

### ANTLR4 代码生成命令
```bash
cd grammar
antlr4 -Dlanguage=Python3 -o ../compiler/src/parser EzLang.g4
```
