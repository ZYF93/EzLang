# ez-android-ui Package Documentation

[中文](../ez-android-ui.md)

`ez-android-ui` provides low-level native View bindings for the `android` target, based on Android NDK + JNI. The package does not provide a framework or scheduling; users implement those layers themselves. All UI primitives are synchronous JNI calls. **View tree mutations must run on the main thread**, and this package provides a main-thread scheduling bridge.

> **Current implementation status**: the repository provides a compilable/linkable native handle state layer. It can maintain root view, node table, parent/child relationships, text, frame, visibility, screen size, density, and related base state. When building an Android target with `output.sdk` and importing `ez-android-ui`, the CLI emits an `ez-android-ui-bridge/` host template next to `lib<name>.so` with Activity, Manifest, and CMake entrypoints. The template connects the dynamic library to an Android project and injects real `DisplayMetrics` into the native state layer when Activity starts. `runOnMainThread` / `scheduleFrame` execute callbacks synchronously in the minimal handle layer. Real Android main-thread message queue, event dispatch, and permission requests are extension points in the host template; public signatures stay stable.

> **Fiber scheduling feasibility**: fully feasible. EzLang `flow` is already a cooperative scheduler. The reconcile phase can run concurrently inside `flow`, while the commit phase bridges back to the UI thread through `runOnMainThread`, matching the architecture of React Native Fabric.

> **Requirement**: `project.toml` must use `os = "android"`, and `sdk` must point to the NDK path. The generated `ez-android-ui-bridge/` can be merged into a Gradle/Android Studio project.

---

## 1. Core Types

```ez
// Opaque View handle, integer ID for JNI GlobalRef
struct Node {
    id: I32
}

// Event types
struct TouchEvent {
    action: Str    // "down" | "up" | "move" | "cancel"
    x: F32
    y: F32
}

struct TextChangedEvent {
    text:   Str
    start:  I32
    count:  I32
}

// General event handler types
type ClickHandler       = () => Void
type TouchHandler       = (e: TouchEvent) => Void
type TextChangeHandler  = (e: TextChangedEvent) => Void
type CheckChangeHandler = (checked: Bool) => Void
type ScrollHandler      = (dx: I32, dy: I32) => Void
type FocusHandler       = (focused: Bool) => Void
type AdapterItemCount   = () => I32
type AdapterCreateItem  = (viewType: I32) => Node
type AdapterBindItem    = (item: Node, index: I32) => Void
type AdapterGetItemType = (index: I32) => I32

// Color, ARGB 32-bit integer
struct Color {
    value: I32   // 0xAARRGGBB

    fromARGB = (a: I32, r: I32, g: I32, b: I32) => Color
    fromHex  = (hex: Str) => Color   // "#RRGGBB" or "#AARRGGBB"
}

// Units
const dp: Str = "dp"
const sp: Str = "sp"
const px: Str = "px"

// LayoutParams constants
const matchParent: I32 = -1
const wrapContent: I32 = -2
```

---

## 2. View Creation

```ez
// Generic View, blank container corresponding to android.view.View
declare const createView:         () => Node

// Layout containers
declare const createLinearLayout: (orientation: Str) => Node   // "vertical" | "horizontal"
declare const createFrameLayout:  () => Node
declare const createScrollView:   () => Node                   // Vertical scroll
declare const createHScrollView:  () => Node                   // Horizontal scroll
declare const createRecyclerView: () => Node                   // List container

// Text
declare const createTextView:     () => Node
declare const createEditText:     () => Node

// Buttons
declare const createButton:       () => Node
declare const createImageButton:  () => Node
declare const createCheckBox:     () => Node
declare const createRadioButton:  () => Node
declare const createSwitch:       () => Node

// Images
declare const createImageView:    () => Node

// Progress / input
declare const createProgressBar:  () => Node
declare const createSeekBar:      () => Node

// Destroy, releasing JNI GlobalRef
declare const destroyNode:        (node: Node) => Void
```

---

## 3. View Tree Operations

```ez
declare const addView:       (parent: Node, child: Node) => Void
declare const addViewAt:     (parent: Node, child: Node, index: I32) => Void
declare const removeView:    (parent: Node, child: Node) => Void
declare const removeAllViews:(parent: Node) => Void
declare const getChildAt:    (parent: Node, index: I32) => Node?
declare const getChildCount: (parent: Node) => I32
declare const getParent:     (node: Node) => Node?

// Set RecyclerView Adapter, framework callback
declare const setAdapter: (
    recycler: Node,
    itemCount:   AdapterItemCount,
    createItem:  AdapterCreateItem,
    bindItem:    AdapterBindItem,
    getItemType: AdapterGetItemType
) => Void
```

---

## 4. LayoutParams

```ez
declare const setLayoutWidth:    (node: Node, value: I32) => Void   // matchParent / wrapContent / px value
declare const setLayoutHeight:   (node: Node, value: I32) => Void
declare const setMargin:         (node: Node, left: I32, top: I32, right: I32, bottom: I32) => Void
declare const setPadding:        (node: Node, left: I32, top: I32, right: I32, bottom: I32) => Void
declare const setWeight:         (node: Node, weight: F32) => Void   // LinearLayout weight
declare const setGravity:        (node: Node, gravity: I32) => Void  // gravity constants

// gravity constants, composable with | operations
const gravity.left:   I32 = 0x03
const gravity.right:  I32 = 0x05
const gravity.top:    I32 = 0x30
const gravity.bottom: I32 = 0x50
const gravity.centerH: I32 = 0x01
const gravity.centerV: I32 = 0x10
const gravity.center:   I32 = 0x11
```

---

## 5. Common View Properties

```ez
declare const setBackgroundColor:   (node: Node, color: Color) => Void
declare const setBackgroundDrawable:(node: Node, resId: I32) => Void
declare const setAlpha:             (node: Node, alpha: F32) => Void    // 0.0-1.0
declare const setVisibility:        (node: Node, v: I32) => Void        // 0=VISIBLE 4=INVISIBLE 8=GONE
declare const setEnabled:           (node: Node, enabled: Bool) => Void
declare const setElevation:         (node: Node, dp: F32) => Void
declare const setCornerRadius:      (node: Node, dp: F32) => Void       // Requires API 21+
declare const setTag:               (node: Node, key: Str, value: Str) => Void
declare const getTag:               (node: Node, key: Str) => Str?
declare const setContentDesc:       (node: Node, desc: Str) => Void

// Size queries, px
declare const getWidth:             (node: Node) => I32
declare const getHeight:            (node: Node) => I32
declare const getMeasuredWidth:     (node: Node) => I32
declare const getMeasuredHeight:    (node: Node) => I32
```

---

## 6. Text Properties for TextView / Button / EditText

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

// inputType constants, composable by bit operations
const inputType.text:     I32 = 0x00000001
const inputType.number:   I32 = 0x00000002
const inputType.phone:    I32 = 0x00000003
const inputType.email:    I32 = 0x00000021
const inputType.password: I32 = 0x00000081
```

---

## 7. Image Properties for ImageView / ImageButton

```ez
declare const setImageUrl:      (node: Node, url: Str) => Void     // Async load inside Flow
declare const setImageRes:      (node: Node, resId: I32) => Void   // Local resource ID
declare const setImageBlob:     (node: Node, data: Blob) => Void   // Raw pixel data
declare const setScaleType:     (node: Node, type_: Str) => Void   // "fitCenter" | "centerCrop" | "fitXY"
```

---

## 8. Event Listeners

```ez
declare const setOnClick:        (node: Node, handler: ClickHandler) => Void
declare const setOnLongClick:    (node: Node, handler: ClickHandler) => Void
declare const setOnTouch:        (node: Node, handler: TouchHandler) => Void
declare const setOnTextChanged:  (node: Node, handler: TextChangeHandler) => Void   // EditText
declare const setOnCheckedChange:(node: Node, handler: CheckChangeHandler) => Void  // CheckBox / Switch
declare const setOnScroll:       (node: Node, handler: ScrollHandler) => Void
declare const setOnFocus:        (node: Node, handler: FocusHandler) => Void

// Remove events
declare const clearOnClick:      (node: Node) => Void
declare const clearOnTouch:      (node: Node) => Void
declare const clearOnTextChanged:(node: Node) => Void
```

---

## 9. Main Thread Scheduling Bridge for Fiber Commit

```ez
// Run synchronously on the UI main thread; all View mutations must go through this function
declare const runOnMainThread:    (work: () => Void) => Void

// Run on the next UI frame, corresponding to View.post / Choreographer
declare const postFrame:          (work: () => Void) => I64   // Returns token
declare const cancelFrame:        (token: I64) => Void

// Run on the UI thread after delay(ms)
declare const postDelayed:        (work: () => Void, ms: I64) => I64
declare const cancelDelayed:      (token: I64) => Void

// Query whether the current thread is the main thread, useful for assertions
declare const isMainThread:       () => Bool
```

> **Fiber scheduling model**: reconcile runs concurrently inside `flow {}` and computes an effect list. Commit work is batched onto the UI thread through `runOnMainThread`.

---

## 10. Activity / Window Access

```ez
// Get the Activity root DecorView, the mount point for the UI tree
declare const getRootView:        () => Node

// Set status bar color, API 21+
declare const setStatusBarColor:  (color: Color) => Void

// Soft keyboard
declare const showKeyboard:       (node: Node) => Void
declare const hideKeyboard:       () => Void

// Screen density, px per dp
declare const getScreenDensity:   () => F32
declare const getScreenWidth:     () => I32    // px
declare const getScreenHeight:    () => I32    // px
```

---

## 11. Permissions

```ez
const permission.camera:         Str = "android.permission.CAMERA"
const permission.recordAudio:    Str = "android.permission.RECORD_AUDIO"
const permission.readMedia:      Str = "android.permission.READ_MEDIA_IMAGES"
const permission.fineLocation:   Str = "android.permission.ACCESS_FINE_LOCATION"
const permission.coarseLocation: Str = "android.permission.ACCESS_COARSE_LOCATION"
const permission.notifications:  Str = "android.permission.POST_NOTIFICATIONS"
const permission.readContacts:   Str = "android.permission.READ_CONTACTS"
const permission.useBiometric:   Str = "android.permission.USE_BIOMETRIC"

// Returns true when granted; denial throws Error(code = errPermission)
declare const requestPermission:  (perm: Str) => Bool
// Batch request, returns permission status map
declare const requestPermissions: (perms: Str[]) => Dict<Str, Bool>
// "granted" | "denied" | "shouldShowRationale"
declare const queryPermission:    (perm: Str) => Str
```

---

## Appendix: Fiber Skeleton

```ez
from "ez-android-ui" import {
    Node, createTextView, createLinearLayout,
    setText, addView, runOnMainThread, getRootView
}

// User-defined Fiber work unit
struct Fiber {
    kind:      Str;
    props:     { [key: Str]: Str };
    children:  Fiber[];
    stateNode: Node?;      // Corresponding real View
    effectTag: I32;        // 0=NONE 1=PLACEMENT 2=UPDATE 3=DELETION
    next:      Fiber?;     // Next fiber to process
}

// reconcile runs concurrently inside Flow
const reconcile = (fiber: Fiber): Void => {
    // Compute subtree diff ...
};

// commit must run on the main thread
const commitEffects = (effectList: Fiber[]): Void => {
    runOnMainThread(work = () => {
        loop effect in effectList {
            (effect.effectTag == 1) ? {
                // PLACEMENT: create and mount
            }
        }
    });
};

const workLoop = (): Void => {
    const root = Fiber(kind = "root", props = {}, children = [], stateNode = getRootView(), effectTag = 0, next = ?);
    flow {
        reconcile(fiber = root);
        // Commit after collecting effectList
        commitEffects(effectList = []);
    }
};
```
