# ez-ios-ui 包文档

`ez-ios-ui` 提供面向 `ios` 目标的**原生 UIKit View 底层绑定**（基于 Objective-C runtime 桥接）。包本身不做框架和调度——这些由使用者自行实现。**View 树修改必须在主线程执行**，包提供主线程调度桥接。

> **当前实现状态**：仓库内已提供可编译链接的原生句柄状态层，可维护根视图、节点表、父子关系、文本、富文本可见文本、frame、可见性、屏幕尺寸、缩放比例和安全区等基础状态；配置 `output.sdk` 构建 iOS 目标且项目导入 `ez-ios-ui` 时，CLI 会随 `lib<name>.dylib` 生成 `ez-ios-ui-bridge/` 宿主模板（Swift ViewController、Package.swift、Info.plist），用于把动态库接入 Xcode/UIKit 工程，并在 ViewController 启动时把 `UIScreen` 与 `safeAreaInsets` 注入原生状态层。`runOnMainThread` / `scheduleFrame` 在最小句柄层内同步执行回调；真实 iOS 主线程队列、事件分发与权限查询由宿主模板扩展实现，公开签名保持稳定。

> **使用前提**：`project.toml` 中 `os = "ios"`，`sdk` 指向 Xcode SDK；构建产物中的 `ez-ios-ui-bridge/` 可加入 Xcode 工程。

---

## 1. 核心类型

```ez
// 不透明 UIView 句柄（Objective-C 对象引用的整数 ID）
struct Node {
    id: I32
}

// 事件类型
struct TouchEvent {
    phase: Str   // "began" | "moved" | "ended" | "cancelled"
    x: F32
    y: F32
}

struct TextChangedEvent {
    text:  Str
    range: I32   // 修改起始位置
}

// 通用事件处理函数类型
type ActionHandler     = () => Void
type TouchHandler      = (e: TouchEvent) => Void
type TextChangeHandler = (e: TextChangedEvent) => Void
type ValueChangeHandler= (value: F32) => Void

// 颜色（RGBA，各分量 0.0–1.0）
struct Color {
    r: F32    g: F32    b: F32    a: F32

    fromHex  = (hex: Str) => Color
    fromRGBA = (r: F32, g: F32, b: F32, a: F32) => Color
    white    = () => Color
    black    = () => Color
    clear    = () => Color
}

struct Rect {
    x: F32    y: F32    width: F32    height: F32
}

struct Insets {
    top: F32    left: F32    bottom: F32    right: F32
}

// contentMode 常量
const contentMode.scaleToFill:        I32 = 0
const contentMode.scaleAspectFit:     I32 = 1
const contentMode.scaleAspectFill:    I32 = 2
const contentMode.center:             I32 = 4
```

---

## 2. View 创建

```ez
// 基础 View（对应 UIView）
declare const createView:           () => Node

// 布局容器
declare const createStackView:      (axis: Str) => Node   // "vertical" | "horizontal"
declare const createScrollView:     () => Node

// 文本
declare const createLabel:          () => Node
declare const createTextField:      () => Node
declare const createTextView:       () => Node            // 多行文本输入

// 交互
declare const createButton:         () => Node
declare const createSwitch:         () => Node
declare const createSlider:         () => Node
declare const createSegmentControl: (segments: Str[]) => Node
declare const createStepper:        () => Node
declare const createActivityIndicator: () => Node

// 图像
declare const createImageView:      () => Node

// 列表
declare const createTableView:      () => Node
declare const createCollectionView: () => Node

// 销毁（释放 ObjC 强引用）
declare const destroyNode:          (node: Node) => Void
```

---

## 3. View 树操作

```ez
declare const addSubview:        (parent: Node, child: Node) => Void
declare const insertSubviewAt:   (parent: Node, child: Node, index: I32) => Void
declare const insertSubviewAbove:(parent: Node, child: Node, ref: Node) => Void
declare const insertSubviewBelow:(parent: Node, child: Node, ref: Node) => Void
declare const removeFromSuperview:(node: Node) => Void
declare const bringToFront:      (node: Node) => Void
declare const sendToBack:        (node: Node) => Void
declare const getSubviewAt:      (parent: Node, index: I32) => Node?
declare const getSubviewCount:   (parent: Node) => I32
declare const getSuperview:      (node: Node) => Node?

// 获取根 UIWindow 的 rootView（挂载 UI 树的起点）
declare const getRootView:       () => Node

// 设置 TableView / CollectionView 数据源（框架回调）
declare const setTableAdapter: (
    table:      Node,
    rowCount:   (section: I32) => I32,
    createCell: (reuseId: Str) => Node,
    bindCell:   (cell: Node, row: I32, section: I32) => Void,
    cellHeight: (row: I32, section: I32) => F32
) => Void
```

---

## 4. 布局（Frame / Auto Layout）

```ez
// Frame 直接定位
declare const setFrame:           (node: Node, rect: Rect) => Void
declare const getFrame:           (node: Node) => Rect
declare const setBounds:          (node: Node, rect: Rect) => Void
declare const getBounds:          (node: Node) => Rect

// Auto Layout 约束（简化接口）
declare const pinToEdges:         (node: Node, insets: Insets) => Void  // 相对于 superview
declare const centerInParent:     (node: Node) => Void
declare const setWidth:           (node: Node, width: F32) => Void
declare const setHeight:          (node: Node, height: F32) => Void
declare const sizeToFit:          (node: Node) => Void

// StackView 布局参数
declare const setSpacing:         (node: Node, spacing: F32) => Void
declare const setAlignment:       (node: Node, align: I32) => Void   // UIStackViewAlignment
declare const setDistribution:    (node: Node, dist: I32) => Void    // UIStackViewDistribution
```

---

## 5. 通用 View 属性

```ez
declare const setBackgroundColor: (node: Node, color: Color) => Void
declare const setAlpha:           (node: Node, alpha: F32) => Void    // 0.0–1.0
declare const setHidden:          (node: Node, hidden: Bool) => Void
declare const setUserInteraction: (node: Node, enabled: Bool) => Void
declare const setClipsToBounds:   (node: Node, clips: Bool) => Void
declare const setCornerRadius:    (node: Node, radius: F32) => Void
declare const setBorderWidth:     (node: Node, width: F32) => Void
declare const setBorderColor:     (node: Node, color: Color) => Void
declare const setShadow:          (node: Node, color: Color, offset: Rect, radius: F32, opacity: F32) => Void
declare const setTag_:            (node: Node, tag: I32) => Void
declare const getTag_:            (node: Node) => I32
declare const setAccessLabel:     (node: Node, label: Str) => Void

// 强制布局
declare const layoutIfNeeded:     (node: Node) => Void
declare const setNeedsLayout:     (node: Node) => Void
```

---

## 6. 文本属性（UILabel / UITextField / UITextView）

```ez
declare const setText:            (node: Node, text: Str) => Void
declare const getText:            (node: Node) => Str
declare const setAttributedText:  (node: Node, html: Str) => Void   // HTML 富文本；状态层会同步保存去标签可见文本
declare const setFont:            (node: Node, name: Str, size: F32) => Void
declare const setSystemFont:      (node: Node, size: F32, weight: F32) => Void  // UIFontWeight
declare const setTextColor:       (node: Node, color: Color) => Void
declare const setTextAlign:       (node: Node, align: I32) => Void   // 0=left 1=center 2=right
declare const setNumberOfLines:   (node: Node, n: I32) => Void
declare const setLineBreakMode:   (node: Node, mode: I32) => Void
declare const setPlaceholder:     (node: Node, text: Str) => Void
declare const setKeyboardType:    (node: Node, type_: I32) => Void   // UIKeyboardType
declare const setSecureEntry:     (node: Node, secure: Bool) => Void
declare const setReturnKeyType:   (node: Node, type_: I32) => Void
```

---

## 7. 图像属性（UIImageView）

```ez
declare const setImageUrl:        (node: Node, url: Str) => Void       // 异步加载（flow 内）
declare const setImageName:       (node: Node, name: Str) => Void      // Assets.xcassets 图片名
declare const setSystemImage:     (node: Node, sfName: Str) => Void    // SF Symbol 名
declare const setImageBlob:       (node: Node, data: Blob) => Void     // 原始像素数据
declare const setContentMode:     (node: Node, mode: I32) => Void      // ContentMode 常量
declare const setTintColor:       (node: Node, color: Color) => Void
```

---

## 8. 交互组件属性

```ez
// UIButton
declare const setButtonTitle:     (node: Node, title: Str, state: I32) => Void  // state: 0=normal
declare const setButtonImage:     (node: Node, name: Str, state: I32) => Void
declare const setButtonEnabled:   (node: Node, enabled: Bool) => Void

// UISwitch
declare const setSwitchOn:        (node: Node, on: Bool, animated: Bool) => Void
declare const getSwitchOn:        (node: Node) => Bool
declare const setSwitchTintColor: (node: Node, color: Color) => Void

// UISlider
declare const setSliderValue:     (node: Node, value: F32, animated: Bool) => Void
declare const getSliderValue:     (node: Node) => F32
declare const setSliderRange:     (node: Node, min: F32, max: F32) => Void

// UIActivityIndicator
declare const startAnimating:     (node: Node) => Void
declare const stopAnimating:      (node: Node) => Void
```

---

## 9. 事件监听（Target-Action + Gesture）

```ez
// UIControl 事件（Button、Switch、Slider 等）
declare const addTarget:          (node: Node, event: I32, handler: ActionHandler) => Void
declare const removeTarget:       (node: Node, event: I32) => Void

// UIControlEvent 常量
const controlEvent.touchUpInside: I32 = 0x40
const controlEvent.valueChanged:  I32 = 0x1000
const controlEvent.editingChanged: I32 = 0x100

// 文本变化（UITextField / UITextView）
declare const setOnTextChanged:   (node: Node, handler: TextChangeHandler) => Void
declare const setOnReturn:        (node: Node, handler: ActionHandler) => Void

// 手势识别器
declare const addTapGesture:      (node: Node, taps: I32, handler: ActionHandler) => Void
declare const addLongPressGesture:(node: Node, minDuration: F32, handler: ActionHandler) => Void
declare const addPanGesture:      (node: Node, handler: TouchHandler) => Void
declare const addSwipeGesture:    (node: Node, direction: I32, handler: ActionHandler) => Void  // 1=right 2=left 4=up 8=down
declare const removeTapGesture:   (node: Node) => Void

// 键盘
declare const becomeFirstResponder: (node: Node) => Void
declare const resignFirstResponder: (node: Node) => Void
```

---

## 10. 主线程调度桥接（Fiber Commit 阶段必须使用）

```ez
// 在主线程同步执行（任何 UIView 修改必须通过此函数）
declare const runOnMainThread:    (work: () => Void) => Void

// 在主线程下一个 RunLoop 周期执行（对应 DispatchQueue.main.async）
declare const postToMain:         (work: () => Void) => Void

// 延迟执行
declare const postDelayed:        (work: () => Void, ms: F64) => I64
declare const cancelDelayed:      (token: I64) => Void

// 下一帧（对应 CADisplayLink）
declare const scheduleFrame:      (work: () => Void) => I64
declare const cancelFrame:        (token: I64) => Void

// 查询是否在主线程
declare const isMainThread:       () => Bool
```

> **Fiber 调度模式**：reconcile 阶段在 `flow {}` 内并发运行，计算出 effect list 后，通过 `runOnMainThread` 将所有 UIView 修改批量提交到主线程。

---

## 11. 屏幕信息

```ez
declare const getScreenWidth:     () => F32   // pt（逻辑像素）
declare const getScreenHeight:    () => F32
declare const getScreenScale:     () => F32   // 2.0 / 3.0（物理像素倍数）
declare const getSafeAreaInsets:  () => Insets
declare const getStatusBarHeight: () => F32
```

---

## 12. 权限

```ez
const permission.camera:          Str = "camera"
const permission.photoLibrary:    Str = "photoLibrary"
const permission.microphone:      Str = "microphone"
const permission.location:        Str = "location"
const permission.locationAlways:  Str = "locationAlways"
const permission.notifications:   Str = "notifications"
const permission.contacts:        Str = "contacts"
const permission.faceID:          Str = "faceID"
const permission.calendar:        Str = "calendar"

// 授权返回 true，拒绝 throw Error(code = errPermission)
declare const requestPermission:  (perm: Str) => Bool
// "authorized" | "denied" | "notDetermined" | "restricted"
declare const queryPermission:    (perm: Str) => Str
```

---

## 附：Fiber 骨架示例

```ez
from "ez-ios-ui" import {
    Node, createLabel, createView,
    setText, addSubview, runOnMainThread, getRootView
}

struct Fiber {
    kind:      Str;
    props:     { [key: Str]: Str };
    children:  Fiber[];
    stateNode: Node?;      // 对应真实 UIView
    effectTag: I32;        // 0=NONE 1=PLACEMENT 2=UPDATE 3=DELETION
    next:      Fiber?;
}

// reconcile 在 flow 内并发运行（不触碰 UIView）
const reconcile = (fiber: Fiber): Void => {
    // 计算子树差量，收集 effect list ...
};

// commit 必须在主线程
const commitEffects = (effectList: Fiber[]): Void => {
    runOnMainThread(work = () => {
        loop effect in effectList {
            (effect.effectTag == 1) ? {
                // PLACEMENT
                let view = createLabel();
                setText(node = view, text = effect.props["text"]!);
                addSubview(parent = getRootView(), child = view);
            }
        }
    });
};

const workLoop = (): Void => {
    flow {
        let root = Fiber(kind = "root", props = {}, children = [], stateNode = getRootView(), effectTag = 0, next = ?);
        reconcile(fiber = root);
        commitEffects(effectList = []);
    }
};
```
