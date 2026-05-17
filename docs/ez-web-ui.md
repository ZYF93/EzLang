# ez-web-ui 包文档

`ez-web-ui` 提供面向 `emcc` 目标的 **底层 DOM 绑定**。包本身不做框架、不做 diff、不做渲染调度——这些由使用者自行实现。所有 API 均为对 Browser/Emscripten JS 侧的 FFI 绑定。

> **使用前提**：`project.toml` 中 `os = "emcc"`。

---

## 1. 核心类型

```ez
// 不透明 DOM 节点句柄（对应 JS 侧 Element 引用的整数 ID）
struct Node {
    id: I32
}

// 事件对象
struct Event {
    type:    Str
    targetId: I32
    data:    Blob?   // 序列化的原始事件数据，按需通过 getEventData 解析
}

type EventHandler = (e: Event) => Void
```

---

## 2. 节点创建与销毁

```ez
// 创建指定 tag 的元素（如 "div" "span" "button" "input" 等）
declare const createElement:     (tag: Str) => Node
// 创建文本节点
declare const createTextNode:    (content: Str) => Node
// 销毁节点（从内部引用表中释放，不自动从 DOM 中移除）
declare const destroyNode:       (node: Node) => Void
```

---

## 3. 树操作

```ez
declare const appendChild:       (parent: Node, child: Node) => Void
declare const insertBefore:      (parent: Node, child: Node, ref: Node) => Void
declare const removeChild:       (parent: Node, child: Node) => Void
declare const replaceChild:      (parent: Node, newChild: Node, oldChild: Node) => Void

// 获取父节点 / 子节点列表
declare const getParent:         (node: Node) => Node?
declare const getChildren:       (node: Node) => Node[]

// 挂载到宿主 DOM 元素（CSS 选择器），返回宿主 Node
declare const getHostNode:       (selector: Str) => Node?
```

---

## 4. 属性操作

```ez
declare const getAttribute:      (node: Node, key: Str) => Str?
declare const setAttribute:      (node: Node, key: Str, value: Str) => Void
declare const removeAttribute:   (node: Node, key: Str) => Void

// 批量设置属性（减少跨 FFI 调用次数）
declare const setAttributes:     (node: Node, attrs: { [key: Str]: Str }) => Void

// 直接读写 DOM property（区别于 attribute）
declare const getProperty:       (node: Node, key: Str) => Str
declare const setProperty:       (node: Node, key: Str, value: Str) => Void
```

---

## 5. 样式与类名

```ez
declare const getStyle:          (node: Node, prop: Str) => Str
declare const setStyle:          (node: Node, prop: Str, value: Str) => Void
// 批量设置 style（驼峰 key，如 "backgroundColor"）
declare const setStyles:         (node: Node, styles: { [key: Str]: Str }) => Void

declare const addClass:          (node: Node, name: Str) => Void
declare const removeClass:       (node: Node, name: Str) => Void
declare const hasClass:          (node: Node, name: Str) => Bool
declare const setClassName:      (node: Node, name: Str) => Void

// 获取当前计算样式
declare const getComputedStyle:  (node: Node, prop: Str) => Str
```

---

## 6. 文本内容

```ez
declare const getTextContent:    (node: Node) => Str
declare const setTextContent:    (node: Node, text: Str) => Void
declare const getInnerHTML:      (node: Node) => Str
declare const setInnerHTML:      (node: Node, html: Str) => Void
```

---

## 7. 事件系统

```ez
// 注册 / 注销事件监听（capture 阶段可选）
declare const addEventListener:      (node: Node, event: Str, handler: EventHandler, capture: Bool? = false) => Void
declare const removeEventListener:   (node: Node, event: Str, handler: EventHandler) => Void

// 事件委托（在 parent 上监听冒泡，通过 selector 过滤）
declare const delegateEvent:         (parent: Node, event: Str, selector: Str, handler: EventHandler) => Void

// 从 Event.data 中解析具体字段
declare const getEventValue:         (e: Event) => Str        // input / change 事件的 value
declare const getEventKey:           (e: Event) => Str        // keydown/keyup 的 key
declare const getEventClientX:       (e: Event) => F32        // 鼠标 / touch X
declare const getEventClientY:       (e: Event) => F32        // 鼠标 / touch Y
declare const preventDefault:        (e: Event) => Void
declare const stopPropagation:       (e: Event) => Void
```

---

## 8. 布局查询

```ez
struct Rect {
    x: F32    y: F32    width: F32    height: F32
}

declare const getBoundingRect:   (node: Node) => Rect
declare const getScrollTop:      (node: Node) => F32
declare const getScrollLeft:     (node: Node) => F32
declare const setScrollTop:      (node: Node, value: F32) => Void
declare const focus_:            (node: Node) => Void
declare const blur_:             (node: Node) => Void
```

---

## 9. 调度钩子（供框架调度器使用）

```ez
// 在下一帧执行（对应 requestAnimationFrame）
declare const scheduleFrame:     (cb: () => Void) => I32
declare const cancelFrame:       (id: I32) => Void

// 微任务队列（对应 queueMicrotask）
declare const scheduleMicrotask: (cb: () => Void) => Void

// 空闲时执行（对应 requestIdleCallback）
declare const scheduleIdle:      (cb: (deadline: F64) => Void) => I32
declare const cancelIdle:        (id: I32) => Void
```

---

## 10. 权限

```ez
const permission.geolocation:   Str = "geolocation"
const permission.camera:        Str = "camera"
const permission.microphone:    Str = "microphone"
const permission.notifications: Str = "notifications"
const permission.clipboard:     Str = "clipboard-read"

// 授权返回 true，拒绝 throw Error(code = errPermission)
declare const requestPermission: (perm: Str) => Bool
// "granted" | "denied" | "prompt"
declare const queryPermission:   (perm: Str) => Str
```

---

## 11. 全局

```ez
declare const getWindowWidth:  () => F32
declare const getWindowHeight: () => F32
declare const getDocumentNode: () => Node   // document.documentElement
declare const getBodyNode:     () => Node   // document.body
declare const getLocation:     () => Str    // window.location.href
declare const setLocation:     (url: Str) => Void
declare const historyPush:     (url: Str) => Void
declare const historyReplace:  (url: Str) => Void
```

---

## 附：自定义框架骨架示例

```ez
from "ez-web-ui" import {
    Node, Event, createElement, createTextNode,
    setAttribute, setStyles, appendChild, removeChild,
    addEventListener, scheduleFrame
}

// 用户自定义 VNode
struct VNode {
    tag:      Str
    props:    { [key: Str]: Str }
    children: VNode[]
    dom:      Node?      // 对应真实 DOM 节点
}

// 创建真实 DOM（mount 阶段）
const createDom = (vnode: VNode) => Node => {
    const dom = createElement(tag = vnode.tag)
    setStyles(node = dom, styles = vnode.props)
    loop child in vnode.children {
        appendChild(parent = dom, child = createDom(vnode = child))
    }
    return dom
}

// diff 与 patch 由用户自行实现...
```
