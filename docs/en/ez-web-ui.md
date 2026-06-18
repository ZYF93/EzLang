# ez-web-ui Package Documentation

[中文](../ez-web-ui.md)

`ez-web-ui` provides low-level DOM bindings for the `emcc` target. The package does not provide a framework, diffing, or render scheduling; users implement those layers themselves. All APIs are FFI bindings to the Browser/Emscripten JavaScript side.

> **Current implementation status**: the repository provides a compilable/linkable ABI. The `emcc` wrapper is connected to core DOM operations. Non-Web native targets return zero handles, empty strings, empty optionals, `false`, or no-op behavior to explicitly indicate unavailability rather than pretending to succeed.

> **Requirement**: `project.toml` must use `os = "emcc"`.

---

## 1. Core Types

```ez
// Opaque DOM node handle, an integer ID for the JS-side Element reference
struct Node {
    id: I32
}

// Event object
struct Event {
    eventType: Str
    targetId: I32
    data:    Blob?   // Serialized raw event data, parsed through getEventData-style helpers as needed
}

type EventHandler = (e: Event) => Void
type Attrs = { [key: Str]: Str }
type Styles = { [key: Str]: Str }
```

---

## 2. Node Creation and Destruction

```ez
// Create an element with a tag, such as "div", "span", "button", or "input"
declare const createElement:     (tag: Str) => Node
// Create a text node
declare const createTextNode:    (content: Str) => Node
// Destroy a node from the internal reference table; it is not automatically removed from the DOM
declare const destroyNode:       (node: Node) => Void
```

---

## 3. Tree Operations

```ez
declare const appendChild:       (parent: Node, child: Node) => Void
declare const insertBefore:      (parent: Node, child: Node, ref: Node) => Void
declare const removeChild:       (parent: Node, child: Node) => Void
declare const replaceChild:      (parent: Node, newChild: Node, oldChild: Node) => Void

// Parent and child list queries
declare const getParent:         (node: Node) => Node?
declare const getChildren:       (node: Node) => Node[]

// Mount to a host DOM element by CSS selector; returns the host Node
declare const getHostNode:       (selector: Str) => Node?
```

---

## 4. Attributes

```ez
declare const getAttribute:      (node: Node, key: Str) => Str?
declare const setAttribute:      (node: Node, key: Str, value: Str) => Void
declare const removeAttribute:   (node: Node, key: Str) => Void

// Batch set attributes to reduce FFI calls
declare const setAttributes:     (node: Node, attrs: Attrs) => Void

// Direct DOM property access, distinct from attributes
declare const getProperty:       (node: Node, key: Str) => Str
declare const setProperty:       (node: Node, key: Str, value: Str) => Void
```

---

## 5. Style and Class Names

```ez
declare const getStyle:          (node: Node, prop: Str) => Str
declare const setStyle:          (node: Node, prop: Str, value: Str) => Void
// Batch set style; keys use camelCase, such as "backgroundColor"
declare const setStyles:         (node: Node, styles: Styles) => Void

declare const addClass:          (node: Node, name: Str) => Void
declare const removeClass:       (node: Node, name: Str) => Void
declare const hasClass:          (node: Node, name: Str) => Bool
declare const setClassName:      (node: Node, name: Str) => Void

// Get the current computed style
declare const getComputedStyle:  (node: Node, prop: Str) => Str
```

---

## 6. Text Content

```ez
declare const getTextContent:    (node: Node) => Str
declare const setTextContent:    (node: Node, text: Str) => Void
declare const getInnerHTML:      (node: Node) => Str
declare const setInnerHTML:      (node: Node, html: Str) => Void
```

---

## 7. Event System

```ez
// Register / unregister event listeners; capture indicates capture phase
declare const addEventListener:      (node: Node, event: Str, handler: EventHandler, capture: Bool) => Void
declare const removeEventListener:   (node: Node, event: Str, handler: EventHandler) => Void

// Event delegation: listen on parent and filter bubbling events by selector
declare const delegateEvent:         (parent: Node, event: Str, selector: Str, handler: EventHandler) => Void

// Parse specific fields from Event.data
declare const getEventValue:         (e: Event) => Str        // input/change value
declare const getEventKey:           (e: Event) => Str        // keydown/keyup key
declare const getEventClientX:       (e: Event) => F32        // mouse/touch X
declare const getEventClientY:       (e: Event) => F32        // mouse/touch Y
declare const preventDefault:        (e: Event) => Void
declare const stopPropagation:       (e: Event) => Void
```

---

## 8. Layout Queries

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

## 9. Scheduling Hooks for Framework Schedulers

```ez
// Run on the next frame, equivalent to requestAnimationFrame
declare const scheduleFrame:     (cb: () => Void) => I32
declare const cancelFrame:       (id: I32) => Void

// Microtask queue, equivalent to queueMicrotask
declare const scheduleMicrotask: (cb: () => Void) => Void

// Run during idle time, equivalent to requestIdleCallback
declare const scheduleIdle:      (cb: (deadline: F64) => Void) => I32
declare const cancelIdle:        (id: I32) => Void
```

---

## 10. Permissions

```ez
const permission.geolocation:   Str = "geolocation"
const permission.camera:        Str = "camera"
const permission.microphone:    Str = "microphone"
const permission.notifications: Str = "notifications"
const permission.clipboard:     Str = "clipboard-read"

// Returns true when granted; denial throws Error(code = errPermission)
declare const requestPermission: (perm: Str) => Bool
// "granted" | "denied" | "prompt"
declare const queryPermission:   (perm: Str) => Str
```

---

## 11. Globals

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

## Appendix: Custom Framework Skeleton

```ez
from "ez-web-ui" import {
    Node, Event, createElement, createTextNode,
    setAttribute, setStyles, appendChild, removeChild,
    addEventListener, scheduleFrame
}

// User-defined VNode
struct VNode {
    tag:      Str;
    props:    { [key: Str]: Str };
    children: VNode[];
    dom:      Node?;      // Corresponding real DOM node
}

// Create real DOM during mount
const createDom = (vnode: VNode): Node => {
    const dom = createElement(tag = vnode.tag);
    setStyles(node = dom, styles = vnode.props);
    loop child in vnode.children {
        appendChild(parent = dom, child = createDom(vnode = child));
    }
    return dom;
};

// diff and patch are implemented by the user...
```
