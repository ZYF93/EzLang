# EzLang 开发任务清单

> 本清单采用 TDD 模式设计：先制定测试用例，再编写实现。编译器相关任务的测试用例优先以 `examples/` 下的 `.ez` 文件形式编写，然后在测试代码中引用验证。

## 1. 编译器开发（Compiler）

- [ ] 1.1 设计基础语法测试
  - [ ] 在 `examples/` 中创建 `syntax-basic.ez`，覆盖变量、表达式、函数、结构体、List、Dict、泛型等基本语法。
  - [ ] 在测试文件中引用 `examples/syntax-basic.ez`，验证前端词法、解析、类型检查与 AST 生成。

- [ ] 1.2 更新 `grammar/EzLang.g4`
  - [ ] 每次语法变更前先修改 `grammar/EzLang.g4`。
  - [ ] 生成新的 ANTLR 词法与语法文件，并将生成命令写入 `README.md` 或 `compiler/` 文档中。
  - [ ] 为新增语法节点增加对应的 `.ez` 示例用例。

- [ ] 1.3 语言特性扩展测试
  - [ ] 在 `examples/` 中添加 `syntax-flow.ez`、`syntax-match.ez`、`syntax-error.ez`、`syntax-generic.ez` 等测试输入。
  - [ ] 编写测试用例验证 `flow {}`、`race`、`match`、`catch/throw`、`?` 占位符和泛型函数的语义。
  - [ ] 在语法变更时，优先执行 `grammar/EzLang.g4` 更新与 ANTLR 重新生成。

- [ ] 1.4 LLVM IR 与后端验证
  - [ ] 在 `examples/` 中新增 `backend-ir.ez`、`backend-struct.ez` 等，验证结构体布局、函数调用与内存模型映射。
  - [ ] 测试生成的 LLVM IR 是否满足预期类型映射与 Arena 内存策略。

- [ ] 1.5 错误处理与异常测试
  - [ ] 编写 `examples/error-handling.ez`，覆盖 `throw`、`catch`、`Error(code=...)` 与运行时错误路径。
  - [ ] 在测试里验证语法错误、类型错误、未定义符号等编译期错误消息。

## 2. 命令行工具（CLI）

- [ ] 2.1 `ez` 命令基础测试
  - [ ] 在 `examples/` 中创建 `cli-run.ez` 和 `cli-build.ez` 执行路径测试。
  - [ ] 编写测试验证 `ez build`、`ez run`、`ez fmt`、`ez install` 的基础工作流程。

- [ ] 2.2 `project.toml` 解析与目标管理
  - [ ] 编写 `examples/project-targets.ez` 以及对应 `project.toml` 测试用例，验证多 `[[output]]`、`os`、`arch`、`sdk` 等字段解析。
  - [ ] 测试 `ez build` 自动根据 `project.toml` 输出目标编译结果。

- [ ] 2.3 依赖与包管理
  - [ ] 增加测试用例 `examples/dep-install.ez` 或 `examples/dep-manifest.ez`，模拟 `[deps]` 安装行为。
  - [ ] 验证 `ez install` 能正确识别本地依赖、远程版本和 workspace module。

- [ ] 2.4 输出与发布流程
  - [ ] 编写测试验证 `ez release` 及 `[[output]]` 目标产物目录结构。
  - [ ] 确认 `ez fmt` 能在示例代码上进行格式化，且不改变语义。

## 3. 标准库开发（Standard Library）

- [ ] 3.1 `std/io` 与平台行为测试
  - [ ] 在 `examples/` 中新增 `stdlib-io.ez`，覆盖 `print`、`println`、`error`、`readLine`。
  - [ ] 编写测试验证不同平台行为文档约定，尤其 `android/ios/emcc` 的 `readLine` / `stdin` 兼容性。

- [ ] 3.2 `std/fs` 与文件系统测试
  - [ ] 在 `examples/` 中新增 `stdlib-fs.ez`，包含 `readFile`、`writeFile`、`mkdir`、`listDir`、`exists`、`stat` 等场景。
  - [ ] 编写跨平台测试，验证 `emcc` 虚拟文件系统与移动端沙盒行为。

- [ ] 3.3 `std/os` 与环境接口测试
  - [ ] 编写 `examples/stdlib-os.ez`，测试 `args()`、`env()`、`cwd()`、`exit()`、`platform()`、`arch()` 等接口。
  - [ ] 验证文档中提到的平台限制：`android/ios` 的 `env` / `cwd` / `pid` 应触发 `panic` 或抛出明确错误。

- [ ] 3.4 `std/time` 与并发测试
  - [ ] 新增 `examples/stdlib-time.ez`，覆盖 `now()`、`timestamp()`、`sleep()` 的 `flow`/非 `flow` 语义。
  - [ ] 编写测试验证 `sleep` 在 `flow` 内是挂起点、超时取消与 `race` 配合行为。

- [ ] 3.5 `std/net` 网络接口测试
  - [ ] 在 `examples/` 中新增 `stdlib-http.ez`、`stdlib-ws.ez`、`stdlib-tcp.ez`，验证 HTTP、WebSocket、TCP/UDP 行为。
  - [ ] 测试 `emcc` 对 `fetch` 的支持与 `tcpListen` / `udpBind` 在不支持平台上的 `panic`。

- [ ] 3.6 `std/collections` 与格式化测试
  - [ ] 编写 `examples/stdlib-collections.ez` 和 `examples/stdlib-fmt.ez`，验证 `List` / `Dict` 扩展方法、`toString`、`parseInt`、`jsonParse` 等功能。
  - [ ] 通过测试确保 JSON、Base64、MessagePack 等语义一致性。

## 4. UI 包与跨平台绑定

- [ ] 4.1 `ez-web-ui` 视觉与 DOM 绑定测试
  - [ ] 编写 `examples/ui-web.ez`，测试 `createElement`、`appendChild`、`setAttribute`、`addEventListener` 等绑定。
  - [ ] 在文档中标记 `project.toml` `os = "emcc"` 的前提要求，并设计测试验证 `getHostNode()`、`scheduleFrame()` 行为。

- [ ] 4.2 `ez-ios-ui` 视图与主线程绑定测试
  - [ ] 在 `examples/ui-ios.ez` 中设计 `createView`、`setText`、`addTarget`、`runOnMainThread` 等用例。
  - [ ] 测试主线程调度、UIView 树操作与 `TextChangedEvent`、手势绑定语义。

- [ ] 4.3 `ez-android-ui` 绑定测试
  - [ ] 在 `examples/ui-android.ez` 中覆盖 Android UI 创建与属性设置场景。
  - [ ] 文档任务中注明独立 UI 包与标准库解耦原则，确保移动端 UI 仅在对应目标下启用。

## 5. 工具链与生成流程

- [ ] 5.1 ANTLR 生成流程文档化
  - [ ] 在 `compiler/` 或 `README.md` 中记录 ANTLR 生成命令，例如：
    - `antlr4 -Dlanguage=JavaScript grammar/EzLang.g4 -o compiler/generated`
    - 或项目实际使用的命令行语法。
  - [ ] 每次修改 `grammar/EzLang.g4` 后执行命令并将结果提交。

- [ ] 5.2 语法变更优先级
  - [ ] 任何语法扩展或修复必须先修改 `grammar/EzLang.g4`，再更新测试示例。
  - [ ] 确认 `examples/` 中对应 `.ez` 文件覆盖新增语法，保证回归测试完整。

- [ ] 5.3 自动化测试执行
  - [ ] 为 `compiler`、`cli`、`stdlib` 和 `ui` 任务分别建立测试套件入口。
  - [ ] 设计测试命令，例如：
    - `python -m pytest tests/compiler`
    - `python -m pytest tests/cli`
    - `python -m pytest tests/stdlib`

## 6. 文档与规范

- [ ] 6.1 维护开发文档
  - [ ] 根据 `README.md`、`doc.md`、`stdlib.md`、`ez-ios-ui.md`、`ez-web-ui.md`、`ez-android-ui.md` 内容更新任务说明。
  - [ ] 将实现与测试结果补充到对应文档，确保规范与代码保持一致。

- [ ] 6.2 任务分阶段完成
  - [ ] 第一阶段：搭建基础语法、CLI 与标准库核心 I/O 测试。
  - [ ] 第二阶段：完善语言特性、后端 IR、Flow 并发与错误处理。
  - [ ] 第三阶段：补全跨平台标准库、UI 包绑定与自动化生成流程。

## 7. 任务优先级建议

- [ ] 7.1 优先级 A：语法 + 编译器前端测试、ANTLR 生成流程、`examples/` 示例测试
- [ ] 7.2 优先级 B：命令行工具解析、`project.toml` 输出与依赖管理
- [ ] 7.3 优先级 C：标准库核心接口、`flow` 与网络基础测试
- [ ] 7.4 优先级 D：平台 UI 包绑定与跨平台兼容性测试

---

## 附录：TDD 开发模式说明

1. 在 `examples/` 下先写 `.ez` 示例用例，表示功能需求与输入语法。
2. 编写测试代码引用这些 `.ez` 文件，验证解析、类型检查、后端生成或运行时行为。
3. 修改 `grammar/EzLang.g4` 与生成 ANTLR 输出（如有语法变更）。
4. 实现编译器/CLI/标准库代码，使测试通过。
5. 将成功测试结果纳入持续集成，并保持 `task.md` 中每项可打钩完成。
