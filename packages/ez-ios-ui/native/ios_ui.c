// ez-ios-ui ABI 占位封装：当前未接入 UIKit，显式返回不可用结果。

#include <stdbool.h>
#include <stdint.h>

typedef struct { int32_t id; } Node;
typedef struct { float r; float g; float b; float a; } Color;
typedef struct { float x; float y; float width; float height; } Rect;
typedef struct { float top; float left; float bottom; float right; } Insets;
typedef struct { bool ok; Node value; } OptNode;

static Node no_node(void) { return (Node){0}; }
static OptNode no_opt_node(void) { return (OptNode){false, {0}}; }
static const char *empty_str(void) { return ""; }

Node createView(void) { return no_node(); }
Node createStackView(const char *axis) { (void)axis; return no_node(); }
Node createScrollView(void) { return no_node(); }
Node createLabel(void) { return no_node(); }
Node createTextField(void) { return no_node(); }
Node createTextView(void) { return no_node(); }
Node createButton(void) { return no_node(); }
Node createSwitch(void) { return no_node(); }
Node createSlider(void) { return no_node(); }
Node createImageView(void) { return no_node(); }
void destroyNode(const Node *node) { (void)node; }

void addSubview(const Node *parent, const Node *child) { (void)parent; (void)child; }
void insertSubviewAt(const Node *parent, const Node *child, int32_t index) { (void)parent; (void)child; (void)index; }
void removeFromSuperview(const Node *node) { (void)node; }
OptNode getSubviewAt(const Node *parent, int32_t index) { (void)parent; (void)index; return no_opt_node(); }
int32_t getSubviewCount(const Node *parent) { (void)parent; return 0; }
OptNode getSuperview(const Node *node) { (void)node; return no_opt_node(); }
Node getRootView(void) { return no_node(); }

void setFrame(const Node *node, const Rect *rect) { (void)node; (void)rect; }
Rect getFrame(const Node *node) { (void)node; return (Rect){0, 0, 0, 0}; }
void pinToEdges(const Node *node, const Insets *insets) { (void)node; (void)insets; }
void centerInParent(const Node *node) { (void)node; }
void setWidth(const Node *node, float width) { (void)node; (void)width; }
void setHeight(const Node *node, float height) { (void)node; (void)height; }

void setText(const Node *node, const char *text) { (void)node; (void)text; }
const char *getText(const Node *node) { (void)node; return empty_str(); }
void setTextColor(const Node *node, const Color *color) { (void)node; (void)color; }
void setBackgroundColor(const Node *node, const Color *color) { (void)node; (void)color; }
void setAlpha(const Node *node, float alpha) { (void)node; (void)alpha; }
void setHidden(const Node *node, bool hidden) { (void)node; (void)hidden; }
void setContentMode(const Node *node, int32_t mode) { (void)node; (void)mode; }

void addTarget(const Node *node, int32_t event, void (*handler)(void)) { (void)node; (void)event; (void)handler; }
void removeTarget(const Node *node, int32_t event) { (void)node; (void)event; }
void addTapGesture(const Node *node, int32_t taps, void (*handler)(void)) { (void)node; (void)taps; (void)handler; }
void removeTapGesture(const Node *node) { (void)node; }

void runOnMainThread(void (*work)(void)) { if (work) work(); }
void postToMain(void (*work)(void)) { if (work) work(); }
int64_t postDelayed(void (*work)(void), double ms) { (void)work; (void)ms; return 0; }
void cancelDelayed(int64_t token) { (void)token; }
int64_t scheduleFrame(void (*work)(void)) { (void)work; return 0; }
void cancelFrame(int64_t token) { (void)token; }
bool isMainThread(void) { return false; }

float getScreenWidth(void) { return 0.0f; }
float getScreenHeight(void) { return 0.0f; }
float getScreenScale(void) { return 0.0f; }
Insets getSafeAreaInsets(void) { return (Insets){0, 0, 0, 0}; }
float getStatusBarHeight(void) { return 0.0f; }

bool requestPermission(const char *perm) { (void)perm; return false; }
const char *queryPermission(const char *perm) { (void)perm; return "unsupported"; }
