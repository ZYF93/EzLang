# ez-ios-ui Package Documentation

[中文](../ez-ios-ui.md)

`ez-ios-ui` provides low-level native UIKit View bindings for the `ios` target, based on Objective-C runtime bridging. The package does not provide a framework or scheduling; users implement those layers themselves. **View tree mutations must run on the main thread**, and the package provides a main-thread scheduling bridge.

> **Current implementation status**: the repository provides a compilable/linkable native handle state layer. It can maintain root view, node table, parent/child relationships, text, visible text for attributed content, frame, visibility, screen size, scale, safe area, and related base state. When building an iOS target with `output.sdk` and importing `ez-ios-ui`, the CLI emits an `ez-ios-ui-bridge/` host template next to `lib<name>.dylib` with Swift ViewController, Package.swift, and Info.plist. The template connects the dynamic library to an Xcode/UIKit project and injects `UIScreen` and `safeAreaInsets` into the native state layer when the ViewController starts. `runOnMainThread` / `scheduleFrame` execute callbacks synchronously in the minimal handle layer. Real iOS main-thread queue, event dispatch, and permission queries are extension points in the host template; public signatures stay stable.

> **Requirement**: `project.toml` must use `os = "ios"`, and `sdk` must point to the Xcode SDK. The generated `ez-ios-ui-bridge/` can be added to an Xcode project.

---

## 1. Core Types

```ez
// Opaque UIView handle, integer ID for Objective-C object reference
struct Node {
    id: I32
}

// Event types
struct TouchEvent {
    phase: Str   // "began" | "moved" | "ended" | "cancelled"
    x: F32
    y: F32
}

struct TextChangedEvent {
    text:  Str
    range: I32   // Start position of the edit
}

// General event handler types
type ActionHandler     = () => Void
type TouchHandler      = (e: TouchEvent) => Void
type TextChangeHandler = (e: TextChangedEvent) => Void
type ValueChangeHandler= (value: F32) => Void
type TableRowCount     = (section: I32) => I32
type TableCreateCell   = (reuseId: Str) => Node
type TableBindCell     = (cell: Node, row: I32, section: I32) => Void
type TableCellHeight   = (row: I32, section: I32) => F32

// Color, RGBA components in 0.0-1.0
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

// contentMode constants
const contentMode.scaleToFill:        I32 = 0
const contentMode.scaleAspectFit:     I32 = 1
const contentMode.scaleAspectFill:    I32 = 2
const contentMode.center:             I32 = 4
```

---

## 2. View Creation

```ez
// Base View, corresponding to UIView
declare const createView:           () => Node

// Layout containers
declare const createStackView:      (axis: Str) => Node   // "vertical" | "horizontal"
declare const createScrollView:     () => Node

// Text
declare const createLabel:          () => Node
declare const createTextField:      () => Node
declare const createTextView:       () => Node            // Multiline text input

// Interactive controls
declare const createButton:         () => Node
declare const createSwitch:         () => Node
declare const createSlider:         () => Node
declare const createSegmentControl: (segments: Str[]) => Node
declare const createStepper:        () => Node
declare const createActivityIndicator: () => Node

// Images
declare const createImageView:      () => Node

// Lists
declare const createTableView:      () => Node
declare const createCollectionView: () => Node

// Destroy, releasing Objective-C strong reference
declare const destroyNode:          (node: Node) => Void
```

---

## 3. View Tree Operations

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

// Get the root UIWindow rootView, the mount point for the UI tree
declare const getRootView:       () => Node

// Set TableView / CollectionView data source, framework callback
declare const setTableAdapter: (
    table:      Node,
    rowCount:   TableRowCount,
    createCell: TableCreateCell,
    bindCell:   TableBindCell,
    cellHeight: TableCellHeight
) => Void
```

---

## 4. Layout: Frame / Auto Layout

```ez
// Direct frame positioning
declare const setFrame:           (node: Node, rect: Rect) => Void
declare const getFrame:           (node: Node) => Rect
declare const setBounds:          (node: Node, rect: Rect) => Void
declare const getBounds:          (node: Node) => Rect

// Simplified Auto Layout constraints
declare const pinToEdges:         (node: Node, insets: Insets) => Void  // Relative to superview
declare const centerInParent:     (node: Node) => Void
declare const setWidth:           (node: Node, width: F32) => Void
declare const setHeight:          (node: Node, height: F32) => Void
declare const sizeToFit:          (node: Node) => Void

// StackView layout parameters
declare const setSpacing:         (node: Node, spacing: F32) => Void
declare const setAlignment:       (node: Node, align: I32) => Void   // UIStackViewAlignment
declare const setDistribution:    (node: Node, dist: I32) => Void    // UIStackViewDistribution
```

---

## 5. Common View Properties

```ez
declare const setBackgroundColor: (node: Node, color: Color) => Void
declare const setAlpha:           (node: Node, alpha: F32) => Void    // 0.0-1.0
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

// Force layout
declare const layoutIfNeeded:     (node: Node) => Void
declare const setNeedsLayout:     (node: Node) => Void
```

---

## 6. Text Properties for UILabel / UITextField / UITextView

```ez
declare const setText:            (node: Node, text: Str) => Void
declare const getText:            (node: Node) => Str
declare const setAttributedText:  (node: Node, html: Str) => Void   // HTML attributed text; state layer stores visible text without tags
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

## 7. Image Properties for UIImageView

```ez
declare const setImageUrl:        (node: Node, url: Str) => Void       // Async load inside Flow
declare const setImageName:       (node: Node, name: Str) => Void      // Assets.xcassets image name
declare const setSystemImage:     (node: Node, sfName: Str) => Void    // SF Symbol name
declare const setImageBlob:       (node: Node, data: Blob) => Void     // Raw pixel data
declare const setContentMode:     (node: Node, mode: I32) => Void      // ContentMode constant
declare const setTintColor:       (node: Node, color: Color) => Void
```

---

## 8. Interactive Component Properties

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

## 9. Event Listeners: Target-Action + Gesture

```ez
// UIControl events, such as Button, Switch, Slider
declare const addTarget:          (node: Node, event: I32, handler: ActionHandler) => Void
declare const removeTarget:       (node: Node, event: I32) => Void

// UIControlEvent constants
const controlEvent.touchUpInside: I32 = 0x40
const controlEvent.valueChanged:  I32 = 0x1000
const controlEvent.editingChanged: I32 = 0x100

// Text changes, UITextField / UITextView
declare const setOnTextChanged:   (node: Node, handler: TextChangeHandler) => Void
declare const setOnReturn:        (node: Node, handler: ActionHandler) => Void

// Gesture recognizers
declare const addTapGesture:      (node: Node, taps: I32, handler: ActionHandler) => Void
declare const addLongPressGesture:(node: Node, minDuration: F32, handler: ActionHandler) => Void
declare const addPanGesture:      (node: Node, handler: TouchHandler) => Void
declare const addSwipeGesture:    (node: Node, direction: I32, handler: ActionHandler) => Void  // 1=right 2=left 4=up 8=down
declare const removeTapGesture:   (node: Node) => Void

// Keyboard
declare const becomeFirstResponder: (node: Node) => Void
declare const resignFirstResponder: (node: Node) => Void
```

---

## 10. Main Thread Scheduling Bridge for Fiber Commit

```ez
// Run synchronously on the main thread; all UIView mutations must go through this function
declare const runOnMainThread:    (work: () => Void) => Void

// Run on the next main RunLoop cycle, equivalent to DispatchQueue.main.async
declare const postToMain:         (work: () => Void) => Void

// Delayed execution
declare const postDelayed:        (work: () => Void, ms: F64) => I64
declare const cancelDelayed:      (token: I64) => Void

// Next frame, equivalent to CADisplayLink
declare const scheduleFrame:      (work: () => Void) => I64
declare const cancelFrame:        (token: I64) => Void

// Query whether the current thread is the main thread
declare const isMainThread:       () => Bool
```

> **Fiber scheduling model**: reconcile runs concurrently inside `flow {}` and computes an effect list. All UIView mutations are then batched onto the main thread through `runOnMainThread`.

---

## 11. Screen Information

```ez
declare const getScreenWidth:     () => F32   // pt, logical pixels
declare const getScreenHeight:    () => F32
declare const getScreenScale:     () => F32   // 2.0 / 3.0, physical pixel scale
declare const getSafeAreaInsets:  () => Insets
declare const getStatusBarHeight: () => F32
```

---

## 12. Permissions

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

// Returns true when granted; denial throws Error(code = errPermission)
declare const requestPermission:  (perm: Str) => Bool
// "authorized" | "denied" | "notDetermined" | "restricted"
declare const queryPermission:    (perm: Str) => Str
```

---

## Appendix: Fiber Skeleton

```ez
from "ez-ios-ui" import {
    Node, createLabel, createView,
    setText, addSubview, runOnMainThread, getRootView
}

struct Fiber {
    kind:      Str;
    props:     { [key: Str]: Str };
    children:  Fiber[];
    stateNode: Node?;      // Corresponding real UIView
    effectTag: I32;        // 0=NONE 1=PLACEMENT 2=UPDATE 3=DELETION
    next:      Fiber?;
}

// reconcile runs concurrently inside Flow and does not touch UIView
const reconcile = (fiber: Fiber): Void => {
    // Compute subtree diff and collect effect list ...
};

// commit must run on the main thread
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
