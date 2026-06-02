// ez-android-ui ABI 占位封装：当前未接入 JNI，显式返回不可用结果。

#include <stdbool.h>
#include <stdint.h>

typedef struct { int32_t id; } Node;
typedef struct { int32_t value; } Color;
typedef struct { bool ok; Node value; } OptNode;

static Node no_node(void) { return (Node){0}; }
static OptNode no_opt_node(void) { return (OptNode){false, {0}}; }
static const char *empty_str(void) { return ""; }

Node createView(void) { return no_node(); }
Node createLinearLayout(const char *orientation) { (void)orientation; return no_node(); }
Node createFrameLayout(void) { return no_node(); }
Node createScrollView(void) { return no_node(); }
Node createTextView(void) { return no_node(); }
Node createEditText(void) { return no_node(); }
Node createButton(void) { return no_node(); }
Node createImageView(void) { return no_node(); }
void destroyNode(const Node *node) { (void)node; }

void addView(const Node *parent, const Node *child) { (void)parent; (void)child; }
void addViewAt(const Node *parent, const Node *child, int32_t index) { (void)parent; (void)child; (void)index; }
void removeView(const Node *parent, const Node *child) { (void)parent; (void)child; }
void removeAllViews(const Node *parent) { (void)parent; }
OptNode getChildAt(const Node *parent, int32_t index) { (void)parent; (void)index; return no_opt_node(); }
int32_t getChildCount(const Node *parent) { (void)parent; return 0; }
OptNode getParent(const Node *node) { (void)node; return no_opt_node(); }

void setLayoutWidth(const Node *node, int32_t value) { (void)node; (void)value; }
void setLayoutHeight(const Node *node, int32_t value) { (void)node; (void)value; }
void setMargin(const Node *node, int32_t left, int32_t top, int32_t right, int32_t bottom) { (void)node; (void)left; (void)top; (void)right; (void)bottom; }
void setPadding(const Node *node, int32_t left, int32_t top, int32_t right, int32_t bottom) { (void)node; (void)left; (void)top; (void)right; (void)bottom; }
void setGravity(const Node *node, int32_t gravity) { (void)node; (void)gravity; }

void setText(const Node *node, const char *text) { (void)node; (void)text; }
const char *getText(const Node *node) { (void)node; return empty_str(); }
void setTextSize(const Node *node, float sp) { (void)node; (void)sp; }
void setTextColor(const Node *node, const Color *color) { (void)node; (void)color; }
void setBackgroundColor(const Node *node, const Color *color) { (void)node; (void)color; }
void setVisibility(const Node *node, int32_t v) { (void)node; (void)v; }
void setEnabled(const Node *node, bool enabled) { (void)node; (void)enabled; }

void setOnClick(const Node *node, void (*handler)(void)) { (void)node; (void)handler; }
void clearOnClick(const Node *node) { (void)node; }

void runOnMainThread(void (*work)(void)) { if (work) work(); }
int64_t postFrame(void (*work)(void)) { (void)work; return 0; }
void cancelFrame(int64_t token) { (void)token; }
int64_t postDelayed(void (*work)(void), int64_t ms) { (void)work; (void)ms; return 0; }
void cancelDelayed(int64_t token) { (void)token; }
bool isMainThread(void) { return false; }

Node getRootView(void) { return no_node(); }
float getScreenDensity(void) { return 0.0f; }
int32_t getScreenWidth(void) { return 0; }
int32_t getScreenHeight(void) { return 0; }

bool requestPermission(const char *perm) { (void)perm; return false; }
const char *queryPermission(const char *perm) { (void)perm; return "unsupported"; }
