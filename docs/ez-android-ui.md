# ez-android-ui 包文档

`ez-android-ui` 提供面向 `android` 目标的**原生 View 底层绑定**（基于 Android NDK + JNI）。包本身不做框架和调度——这些由使用者自行实现。所有 UI 原语均为同步 JNI 调用，**View 树修改必须在主线程执行**，包提供主线程调度桥接。

> **Fiber 调度可行性**：完全可行。EzLang 的 `flow` 已是协作式调度器，reconcile（差量计算）阶段在 `flow` 内并发运行；commit（View 修改）阶段通过 `runOnMainThread` 桥接回 UI 线程，架构与 React Native Fabric 一致。

> **使用前提**：`project.toml` 中 `os = "android"`，`sdk` 指向 NDK 路径。

---

## 1. 核心类型

```ez
// 不透明 View 句柄（JNI GlobalRef 的整数 ID）
struct Node {
    id: I32
}

// 事件类型
struct TouchEvent {
    action: Str    // "down" | "up" | "move" | "cancel"
    x: F32
    y: F32
}

struct KeyEvent {
    keyCode: I32
    action:  Str   // "down" | "up"
}

struct TextChangedEvent {
    text:   Str
    start:  I32
    count:  I32
}

// 通用事件处理函数类型
type ClickHandler       = () => Void
type TouchHandler       = (e: TouchEvent) => Void
type TextChangeHandler  = (e: TextChangedEvent) => Void
type CheckChangeHandler = (checked: Bool) => Void

// 颜色（ARGB 32 位整数）
struct Color {
    value: I32   // 0xAARRGGBB

    fromARGB = (a: I32, r: I32, g: I32, b: I32) => Color
    fromHex  = (hex: Str) => Color   // "#RRGGBB" 或 "#AARRGGBB"
}

// 尺寸单位
const dp: Str = "dp"
const sp: Str = "sp"
const px: Str = "px"

struct Size {
    value: F32
    unit:  Str   // dp | sp | px
}

// LayoutParams 常量
const matchParent: I32 = -1
const wrapContent: I32 = -2
```

---

## 2. View 创建

```ez
// 通用 View（空白容器，对应 android.view.View）
declare const createView:         () => Node

// 布局容器
declare const createLinearLayout: (orientation: Str) => Node   // "vertical" | "horizontal"
declare const createFrameLayout:  () => Node
declare const createScrollView:   () => Node                   // 垂直滚动
declare const createHScrollView:  () => Node                   // 水平滚动
declare const createRecyclerView: () => Node                   // 列表容器

// 文本
declare const createTextView:     () => Node
declare const createEditText:     () => Node

// 按钮
declare const createButton:       () => Node
declare const createImageButton:  () => Node
declare const createCheckBox:     () => Node
declare const createRadioButton:  () => Node
declare const createSwitch:       () => Node

// 图像
declare const createImageView:    () => Node

// 进度 / 输入
declare const createProgressBar:  () => Node
declare const createSeekBar:      () => Node

// 销毁（释放 JNI GlobalRef）
declare const destroyNode:        (node: Node) => Void
```

---

## 3. View 树操作

```ez
declare const addView:       (parent: Node, child: Node) => Void
declare const addViewAt:     (parent: Node, child: Node, index: I32) => Void
declare const removeView:    (parent: Node, child: Node) => Void
declare const removeAllViews:(parent: Node) => Void
declare const getChildAt:    (parent: Node, index: I32) => Node?
declare const getChildCount: (parent: Node) => I32
declare const getParent:     (node: Node) => Node?

// 设置 RecyclerView Adapter（框架回调）
declare const setAdapter: (
    recycler: Node,
    itemCount:    () => I32,
    createItem:   (viewType: I32) => Node,
    bindItem:     (item: Node, index: I32) => Void,
    getItemType:  (index: I32) => I32
) => Void
```

---

## 4. 布局参数（LayoutParams）

```ez
declare const setLayoutWidth:    (node: Node, value: I32) => Void   // matchParent / wrapContent / px 值
declare const setLayoutHeight:   (node: Node, value: I32) => Void
declare const setMargin:         (node: Node, left: I32, top: I32, right: I32, bottom: I32) => Void
declare const setPadding:        (node: Node, left: I32, top: I32, right: I32, bottom: I32) => Void
declare const setWeight:         (node: Node, weight: F32) => Void   // LinearLayout weight
declare const setGravity:        (node: Node, gravity: I32) => Void  // gravity 常量

// gravity 常量（可组合 | 运算）
const gravity.left:   I32 = 0x03
const gravity.right:  I32 = 0x05
const gravity.top:    I32 = 0x30
const gravity.bottom: I32 = 0x50
const gravity.centerH: I32 = 0x01
const gravity.centerV: I32 = 0x10
const gravity.center:   I32 = 0x11
```

---

## 5. 通用 View 属性

```ez
declare const setBackgroundColor:   (node: Node, color: Color) => Void
declare const setBackgroundDrawable:(node: Node, resId: I32) => Void
declare const setAlpha:             (node: Node, alpha: F32) => Void    // 0.0–1.0
declare const setVisibility:        (node: Node, v: I32) => Void        // 0=VISIBLE 4=INVISIBLE 8=GONE
declare const setEnabled:           (node: Node, enabled: Bool) => Void
declare const setElevation:         (node: Node, dp: F32) => Void
declare const setCornerRadius:      (node: Node, dp: F32) => Void       // 需要 API 21+
declare const setTag:               (node: Node, key: Str, value: Str) => Void
declare const getTag:               (node: Node, key: Str) => Str?
declare const setContentDesc:       (node: Node, desc: Str) => Void

// 尺寸查询（px）
declare const getWidth:             (node: Node) => I32
declare const getHeight:            (node: Node) => I32
declare const getMeasuredWidth:     (node: Node) => I32
declare const getMeasuredHeight:    (node: Node) => I32
```

---

## 6. 文本相关属性（TextView / Button / EditText）

```ez
declare const setText:         (node: Node, text: Str) => Void
declare const getText:         (node: Node) => Str
declare const setTextSize:     (node: Node, sp: F32) => Void
declare const setTextColor:    (node: Node, color: Color) => Void
declare const setHint:         (node: Node, hint: Str) => Void
declare const setHintColor:    (node: Node, color: Color) => Void
declare const setTextStyle:    (node: Node, style: I32) => Void   // 0=NORMAL 1=BOLD 2=ITALIC
declare const setMaxLines:     (node: Node, max: I32) => Void
declare const setInputType:    (node: Node, type_: I32) => Void

// inputType 常量（可按位组合）
const inputType.text:     I32 = 0x00000001
const inputType.number:   I32 = 0x00000002
const inputType.phone:    I32 = 0x00000003
const inputType.email:    I32 = 0x00000021
const inputType.password: I32 = 0x00000081
```

---

## 7. 图像属性（ImageView / ImageButton）

```ez
declare const setImageUrl:      (node: Node, url: Str) => Void     // 异步加载（flow 内）
declare const setImageRes:      (node: Node, resId: I32) => Void   // 本地资源 ID
declare const setImageBlob:     (node: Node, data: Blob) => Void   // 原始像素数据
declare const setScaleType:     (node: Node, type_: Str) => Void   // "fitCenter" | "centerCrop" | "fitXY"
```

---

## 8. 事件监听

```ez
declare const setOnClick:        (node: Node, handler: ClickHandler) => Void
declare const setOnLongClick:    (node: Node, handler: ClickHandler) => Void
declare const setOnTouch:        (node: Node, handler: TouchHandler) => Void
declare const setOnTextChanged:  (node: Node, handler: TextChangeHandler) => Void   // EditText
declare const setOnCheckedChange:(node: Node, handler: CheckChangeHandler) => Void  // CheckBox / Switch
declare const setOnScroll:       (node: Node, handler: (dx: I32, dy: I32) => Void) => Void
declare const setOnFocus:        (node: Node, handler: (focused: Bool) => Void) => Void

// 移除事件
declare const clearOnClick:      (node: Node) => Void
declare const clearOnTouch:      (node: Node) => Void
declare const clearOnTextChanged:(node: Node) => Void
```

---

## 9. 主线程调度桥接（Fiber Commit 阶段必须使用）

```ez
// 在 UI 主线程同步执行（任何 View 属性修改必须通过此函数）
declare const runOnMainThread:    (work: () => Void) => Void

// 在 UI 主线程的下一帧执行（对应 View.post / Choreographer）
declare const postFrame:          (work: () => Void) => I64   // 返回 token
declare const cancelFrame:        (token: I64) => Void

// 在 UI 线程以 delay(ms) 延迟执行
declare const postDelayed:        (work: () => Void, ms: I64) => I64
declare const cancelDelayed:      (token: I64) => Void

// 查询当前是否在主线程（用于断言）
declare const isMainThread:       () => Bool
```

> **Fiber 调度模式**：reconcile 阶段在 `flow {}` 内并发运行，计算出 effect list 后，通过 `runOnMainThread` 将 commit 工作批量提交到 UI 线程。

---

## 10. Activity / Window 访问

```ez
// 获取 Activity 根 DecorView（挂载 UI 树的起点）
declare const getRootView:        () => Node

// 设置状态栏颜色（API 21+）
declare const setStatusBarColor:  (color: Color) => Void

// 软键盘
declare const showKeyboard:       (node: Node) => Void
declare const hideKeyboard:       () => Void

// 屏幕密度（px per dp）
declare const getScreenDensity:   () => F32
declare const getScreenWidth:     () => I32    // px
declare const getScreenHeight:    () => I32    // px
```

---

## 11. 权限

```ez
const permission.camera:         Str = "android.permission.CAMERA"
const permission.recordAudio:    Str = "android.permission.RECORD_AUDIO"
const permission.readMedia:      Str = "android.permission.READ_MEDIA_IMAGES"
const permission.fineLocation:   Str = "android.permission.ACCESS_FINE_LOCATION"
const permission.coarseLocation: Str = "android.permission.ACCESS_COARSE_LOCATION"
const permission.notifications:  Str = "android.permission.POST_NOTIFICATIONS"
const permission.readContacts:   Str = "android.permission.READ_CONTACTS"
const permission.useBiometric:   Str = "android.permission.USE_BIOMETRIC"

// 授权返回 true，拒绝 throw Error(code = errPermission)
declare const requestPermission:  (perm: Str) => Bool
// 批量申请，返回各权限授权状态
declare const requestPermissions: (perms: Str[]) => { [key: Str]: Bool }
// "granted" | "denied" | "shouldShowRationale"
declare const queryPermission:    (perm: Str) => Str
```

---

## 附：Fiber 骨架示例

```ez
from "ez-android-ui" import {
    Node, createTextView, createLinearLayout,
    setText, addView, runOnMainThread, getRootView
}

// 用户定义的 Fiber 工作单元
struct Fiber {
    type:      Str
    props:     { [key: Str]: Str }
    children:  Fiber[]
    stateNode: Node?      // 对应真实 View
    effectTag: I32        // 0=NONE 1=PLACEMENT 2=UPDATE 3=DELETION
    next:      Fiber?     // 下一个待处理 fiber
}

// reconcile 在 flow 内并发运行
const reconcile = (fiber: Fiber) => Void => {
    // 计算子树差量 ...
}

// commit 必须在主线程
const commitEffects = (effectList: Fiber[]) => Void => {
    runOnMainThread(work = () => {
        loop effect in effectList {
            (effect.effectTag == 1) ? {
                // PLACEMENT：创建并挂载
            }
        }
    })
}

const workLoop = () => Void => {
    const root = Fiber(type = "root", props = {}, children = [], stateNode = getRootView(), effectTag = 0, next = ?)
    flow {
        reconcile(fiber = root)
        // 收集 effectList 后提交
        commitEffects(effectList = [])
    }
}
```
