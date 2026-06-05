// ez-android-ui 最小原生句柄层。
// Android 宿主可在此层替换为 JNI GlobalRef；当前实现维护可测试的 View 树与属性状态。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int32_t id; } Node;
typedef struct { int32_t value; } Color;
typedef struct { bool ok; Node value; } OptNode;

typedef struct UiNode {
    int32_t id;
    char *kind;
    char *text;
    int32_t width;
    int32_t height;
    int32_t gravity;
    bool enabled;
    struct UiNode *parent;
    struct UiNode **children;
    int32_t child_count;
    int32_t child_capacity;
} UiNode;

static UiNode **g_nodes = NULL;
static int32_t g_capacity = 0;
static int32_t g_next_id = 1;
static UiNode *g_root = NULL;

static char *ez_ui_strdup(const char *text) {
    if (!text) text = "";
    size_t len = strlen(text) + 1;
    char *copy = (char *)malloc(len);
    if (!copy) return NULL;
    memcpy(copy, text, len);
    return copy;
}

static bool ensure_node_capacity(int32_t id) {
    if (id < g_capacity) return true;
    int32_t next = g_capacity > 0 ? g_capacity : 64;
    while (next <= id) next *= 2;
    UiNode **nodes = (UiNode **)realloc(g_nodes, (size_t)next * sizeof(UiNode *));
    if (!nodes) return false;
    for (int32_t i = g_capacity; i < next; ++i) nodes[i] = NULL;
    g_nodes = nodes;
    g_capacity = next;
    return true;
}

static UiNode *lookup(Node node) {
    if (node.id <= 0 || node.id >= g_capacity) return NULL;
    return g_nodes[node.id];
}

static Node store_node(const char *kind) {
    int32_t id = g_next_id++;
    if (!ensure_node_capacity(id)) return (Node){0};
    UiNode *node = (UiNode *)calloc(1, sizeof(UiNode));
    if (!node) return (Node){0};
    node->id = id;
    node->kind = ez_ui_strdup(kind);
    node->text = ez_ui_strdup("");
    node->width = -2;
    node->height = -2;
    node->enabled = true;
    g_nodes[id] = node;
    return (Node){id};
}

static Node root_node(void) {
    if (g_root) return (Node){g_root->id};
    Node root = store_node("RootView");
    g_root = lookup(root);
    return root;
}

static bool ensure_child_capacity(UiNode *node, int32_t required) {
    if (!node) return false;
    if (required <= node->child_capacity) return true;
    int32_t next = node->child_capacity > 0 ? node->child_capacity : 4;
    while (next < required) next *= 2;
    UiNode **children = (UiNode **)realloc(node->children, (size_t)next * sizeof(UiNode *));
    if (!children) return false;
    node->children = children;
    node->child_capacity = next;
    return true;
}

static void detach(UiNode *child) {
    if (!child || !child->parent) return;
    UiNode *parent = child->parent;
    for (int32_t i = 0; i < parent->child_count; ++i) {
        if (parent->children[i] != child) continue;
        for (int32_t j = i + 1; j < parent->child_count; ++j) parent->children[j - 1] = parent->children[j];
        parent->child_count -= 1;
        break;
    }
    child->parent = NULL;
}

static void add_child_at(UiNode *parent, UiNode *child, int32_t index) {
    if (!parent || !child) return;
    detach(child);
    if (index < 0 || index > parent->child_count) index = parent->child_count;
    if (!ensure_child_capacity(parent, parent->child_count + 1)) return;
    for (int32_t i = parent->child_count; i > index; --i) parent->children[i] = parent->children[i - 1];
    parent->children[index] = child;
    parent->child_count += 1;
    child->parent = parent;
}

static void free_node(UiNode *node) {
    if (!node) return;
    while (node->child_count > 0) detach(node->children[node->child_count - 1]);
    detach(node);
    if (node->id > 0 && node->id < g_capacity) g_nodes[node->id] = NULL;
    free(node->children);
    free(node->kind);
    free(node->text);
    free(node);
}

static const char *node_text(UiNode *node) { return node && node->text ? node->text : ""; }

Node createView(void) { return store_node("View"); }
Node createLinearLayout(const char *orientation) { (void)orientation; return store_node("LinearLayout"); }
Node createFrameLayout(void) { return store_node("FrameLayout"); }
Node createScrollView(void) { return store_node("ScrollView"); }
Node createTextView(void) { return store_node("TextView"); }
Node createEditText(void) { return store_node("EditText"); }
Node createButton(void) { return store_node("Button"); }
Node createImageView(void) { return store_node("ImageView"); }
void destroyNode(const Node *node) { if (node) free_node(lookup(*node)); }

void addView(const Node *parent, const Node *child) { if (parent && child) add_child_at(lookup(*parent), lookup(*child), -1); }
void addViewAt(const Node *parent, const Node *child, int32_t index) { if (parent && child) add_child_at(lookup(*parent), lookup(*child), index); }
void removeView(const Node *parent, const Node *child) { (void)parent; if (child) detach(lookup(*child)); }
void removeAllViews(const Node *parent) {
    UiNode *p = parent ? lookup(*parent) : NULL;
    while (p && p->child_count > 0) detach(p->children[p->child_count - 1]);
}
OptNode getChildAt(const Node *parent, int32_t index) {
    UiNode *p = parent ? lookup(*parent) : NULL;
    if (!p || index < 0 || index >= p->child_count) return (OptNode){false, {0}};
    return (OptNode){true, {p->children[index]->id}};
}
int32_t getChildCount(const Node *parent) { UiNode *p = parent ? lookup(*parent) : NULL; return p ? p->child_count : 0; }
OptNode getParent(const Node *node) {
    UiNode *n = node ? lookup(*node) : NULL;
    return n && n->parent ? (OptNode){true, {n->parent->id}} : (OptNode){false, {0}};
}

void setLayoutWidth(const Node *node, int32_t value) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->width = value; }
void setLayoutHeight(const Node *node, int32_t value) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->height = value; }
void setMargin(const Node *node, int32_t left, int32_t top, int32_t right, int32_t bottom) { (void)node; (void)left; (void)top; (void)right; (void)bottom; }
void setPadding(const Node *node, int32_t left, int32_t top, int32_t right, int32_t bottom) { (void)node; (void)left; (void)top; (void)right; (void)bottom; }
void setGravity(const Node *node, int32_t gravity) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->gravity = gravity; }

void setText(const Node *node, const char *text) {
    UiNode *n = node ? lookup(*node) : NULL;
    if (!n) return;
    char *copy = ez_ui_strdup(text);
    if (!copy) return;
    free(n->text);
    n->text = copy;
}
const char *getText(const Node *node) { return node_text(node ? lookup(*node) : NULL); }
void setTextSize(const Node *node, float sp) { (void)node; (void)sp; }
void setTextColor(const Node *node, const Color *color) { (void)node; (void)color; }
void setBackgroundColor(const Node *node, const Color *color) { (void)node; (void)color; }
void setVisibility(const Node *node, int32_t v) { (void)node; (void)v; }
void setEnabled(const Node *node, bool enabled) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->enabled = enabled; }

void setOnClick(const Node *node, void (*handler)(void)) { (void)node; (void)handler; }
void setOnTouch(const Node *node, void (*handler)(void *)) { (void)node; (void)handler; }
void setOnTextChanged(const Node *node, void (*handler)(void *)) { (void)node; (void)handler; }
void clearOnClick(const Node *node) { (void)node; }

void runOnMainThread(void (*work)(void)) { if (work) work(); }
int64_t postFrame(void (*work)(void)) { if (work) work(); return 1; }
void cancelFrame(int64_t token) { (void)token; }
int64_t postDelayed(void (*work)(void), int64_t ms) { (void)ms; if (work) work(); return 1; }
void cancelDelayed(int64_t token) { (void)token; }
bool isMainThread(void) { return true; }

Node getRootView(void) { return root_node(); }
float getScreenDensity(void) { return 1.0f; }
int32_t getScreenWidth(void) { return 0; }
int32_t getScreenHeight(void) { return 0; }

bool requestPermission(const char *perm) { (void)perm; return false; }
const char *queryPermission(const char *perm) { (void)perm; return "unsupported"; }
