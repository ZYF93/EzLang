// ez-web-ui 非 Web 目标占位封装：显式返回不可用结果。

#include <stdbool.h>
#include <stdint.h>

typedef struct { int32_t id; } Node;
typedef struct { float x; float y; float width; float height; } Rect;
typedef struct { bool ok; Node value; } OptNode;
typedef struct { bool ok; const char *value; } OptStr;

static Node no_node(void) { return (Node){0}; }
static OptNode no_opt_node(void) { return (OptNode){false, {0}}; }
static const char *empty_str(void) { return ""; }

Node createElement(const char *tag) { (void)tag; return no_node(); }
Node createTextNode(const char *content) { (void)content; return no_node(); }
void destroyNode(const Node *node) { (void)node; }
void appendChild(const Node *parent, const Node *child) { (void)parent; (void)child; }
void insertBefore(const Node *parent, const Node *child, const Node *ref) { (void)parent; (void)child; (void)ref; }
void removeChild(const Node *parent, const Node *child) { (void)parent; (void)child; }
void replaceChild(const Node *parent, const Node *newChild, const Node *oldChild) { (void)parent; (void)newChild; (void)oldChild; }
OptNode getParent(const Node *node) { (void)node; return no_opt_node(); }
OptNode getHostNode(const char *selector) { (void)selector; return no_opt_node(); }
OptStr getAttribute(const Node *node, const char *key) { (void)node; (void)key; return (OptStr){false, 0}; }
void setAttribute(const Node *node, const char *key, const char *value) { (void)node; (void)key; (void)value; }
void removeAttribute(const Node *node, const char *key) { (void)node; (void)key; }
const char *getProperty(const Node *node, const char *key) { (void)node; (void)key; return empty_str(); }
void setProperty(const Node *node, const char *key, const char *value) { (void)node; (void)key; (void)value; }
const char *getStyle(const Node *node, const char *prop) { (void)node; (void)prop; return empty_str(); }
void setStyle(const Node *node, const char *prop, const char *value) { (void)node; (void)prop; (void)value; }
void addClass(const Node *node, const char *name) { (void)node; (void)name; }
void removeClass(const Node *node, const char *name) { (void)node; (void)name; }
bool hasClass(const Node *node, const char *name) { (void)node; (void)name; return false; }
void setClassName(const Node *node, const char *name) { (void)node; (void)name; }
const char *getComputedStyle(const Node *node, const char *prop) { (void)node; (void)prop; return empty_str(); }
const char *getTextContent(const Node *node) { (void)node; return empty_str(); }
void setTextContent(const Node *node, const char *text) { (void)node; (void)text; }
const char *getInnerHTML(const Node *node) { (void)node; return empty_str(); }
void setInnerHTML(const Node *node, const char *html) { (void)node; (void)html; }
Rect getBoundingRect(const Node *node) { (void)node; return (Rect){0, 0, 0, 0}; }
float getScrollTop(const Node *node) { (void)node; return 0.0f; }
float getScrollLeft(const Node *node) { (void)node; return 0.0f; }
void setScrollTop(const Node *node, float value) { (void)node; (void)value; }
void focus_(const Node *node) { (void)node; }
void blur_(const Node *node) { (void)node; }
int32_t scheduleFrame(void (*cb)(void)) { (void)cb; return 0; }
void cancelFrame(int32_t id) { (void)id; }
void scheduleMicrotask(void (*cb)(void)) { (void)cb; }
int32_t scheduleIdle(void (*cb)(double)) { (void)cb; return 0; }
void cancelIdle(int32_t id) { (void)id; }
bool requestPermission(const char *perm) { (void)perm; return false; }
const char *queryPermission(const char *perm) { (void)perm; return "unsupported"; }
float getWindowWidth(void) { return 0.0f; }
float getWindowHeight(void) { return 0.0f; }
Node getDocumentNode(void) { return no_node(); }
Node getBodyNode(void) { return no_node(); }
const char *getLocation(void) { return empty_str(); }
void setLocation(const char *url) { (void)url; }
void historyPush(const char *url) { (void)url; }
void historyReplace(const char *url) { (void)url; }
