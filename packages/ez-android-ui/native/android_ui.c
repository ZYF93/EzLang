// ez-android-ui 原生句柄状态层。
// Android 宿主可在此层替换为 JNI GlobalRef；当前实现维护可测试的 View 树与属性状态。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int32_t id; } Node;
typedef struct { int32_t value; } Color;
typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { bool ok; Node value; } OptNode;
typedef struct { bool ok; const char *value; } OptStr;
typedef struct { char ***pages; int64_t length; int64_t capacity; int64_t page_count; } StrList;
typedef struct { char ***key_pages; char ***value_pages; int32_t count; int32_t capacity; int32_t page_count; } Dict;

typedef struct {
    const char *action;
    float x;
    float y;
} TouchEvent;

typedef struct {
    const char *text;
    int32_t start;
    int32_t count;
} TextChangedEvent;

typedef struct UiTag {
    char *key;
    char *value;
} UiTag;

typedef void (*ClickHandler)(void);
typedef void (*TouchHandler)(const TouchEvent *event);
typedef void (*TextChangeHandler)(const TextChangedEvent *event);
typedef void (*CheckChangeHandler)(bool checked);
typedef void (*ScrollHandler)(int32_t dx, int32_t dy);
typedef void (*FocusHandler)(bool focused);

typedef int32_t (*AdapterItemCount)(void);
typedef Node (*AdapterCreateItem)(int32_t view_type);
typedef void (*AdapterBindItem)(const Node *item, int32_t index);
typedef int32_t (*AdapterGetItemType)(int32_t index);

typedef struct UiNode {
    int32_t id;
    char *kind;
    char *text;
    char *hint;
    char *content_desc;
    char *image_url;
    char *scale_type;
    int32_t image_res;
    int64_t image_blob_size;
    int32_t width;
    int32_t height;
    int32_t measured_width;
    int32_t measured_height;
    int32_t margin[4];
    int32_t padding[4];
    float weight;
    int32_t gravity;
    Color text_color;
    Color hint_color;
    Color background_color;
    int32_t background_drawable;
    float alpha;
    int32_t visibility;
    bool enabled;
    float elevation;
    float corner_radius;
    int32_t text_style;
    int32_t max_lines;
    int32_t input_type;
    bool focused;
    UiTag *tags;
    int32_t tag_count;
    int32_t tag_capacity;
    ClickHandler on_click;
    ClickHandler on_long_click;
    TouchHandler on_touch;
    TextChangeHandler on_text_changed;
    CheckChangeHandler on_checked_change;
    ScrollHandler on_scroll;
    FocusHandler on_focus;
    AdapterItemCount adapter_item_count;
    AdapterCreateItem adapter_create_item;
    AdapterBindItem adapter_bind_item;
    AdapterGetItemType adapter_get_item_type;
    struct UiNode *parent;
    struct UiNode **children;
    int32_t child_count;
    int32_t child_capacity;
} UiNode;

static UiNode **g_nodes = NULL;
static int32_t g_capacity = 0;
static int32_t g_next_id = 1;
static UiNode *g_root = NULL;
static Color g_status_bar_color = {0};
static bool g_keyboard_visible = false;
static int64_t g_next_token = 1;
static int32_t g_screen_width = 0;
static int32_t g_screen_height = 0;
static float g_screen_density = 1.0f;

static char *ez_ui_strdup(const char *text) {
    if (!text) text = "";
    size_t len = strlen(text) + 1;
    char *copy = (char *)malloc(len);
    if (!copy) return NULL;
    memcpy(copy, text, len);
    return copy;
}

static bool replace_string(char **slot, const char *text) {
    char *copy = ez_ui_strdup(text);
    if (!copy) return false;
    free(*slot);
    *slot = copy;
    return true;
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
    node->hint = ez_ui_strdup("");
    node->content_desc = ez_ui_strdup("");
    node->image_url = ez_ui_strdup("");
    node->scale_type = ez_ui_strdup("");
    node->width = -2;
    node->height = -2;
    node->alpha = 1.0f;
    node->enabled = true;
    node->max_lines = -1;
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

static void free_tags(UiNode *node) {
    if (!node) return;
    for (int32_t i = 0; i < node->tag_count; ++i) {
        free(node->tags[i].key);
        free(node->tags[i].value);
    }
    free(node->tags);
    node->tags = NULL;
    node->tag_count = 0;
    node->tag_capacity = 0;
}

static void free_node(UiNode *node) {
    if (!node) return;
    while (node->child_count > 0) detach(node->children[node->child_count - 1]);
    detach(node);
    if (g_root == node) g_root = NULL;
    if (node->id > 0 && node->id < g_capacity) g_nodes[node->id] = NULL;
    free(node->children);
    free_tags(node);
    free(node->kind);
    free(node->text);
    free(node->hint);
    free(node->content_desc);
    free(node->image_url);
    free(node->scale_type);
    free(node);
}

static const char *node_text(UiNode *node) { return node && node->text ? node->text : ""; }

static int32_t visible_size(int32_t value) { return value > 0 ? value : 0; }

static UiTag *find_tag(UiNode *node, const char *key) {
    if (!node || !key) return NULL;
    for (int32_t i = 0; i < node->tag_count; ++i) {
        if (node->tags[i].key && strcmp(node->tags[i].key, key) == 0) return &node->tags[i];
    }
    return NULL;
}

static bool ensure_tag_capacity(UiNode *node, int32_t required) {
    if (!node) return false;
    if (required <= node->tag_capacity) return true;
    int32_t next = node->tag_capacity > 0 ? node->tag_capacity : 4;
    while (next < required) next *= 2;
    UiTag *tags = (UiTag *)realloc(node->tags, (size_t)next * sizeof(UiTag));
    if (!tags) return false;
    for (int32_t i = node->tag_capacity; i < next; ++i) tags[i] = (UiTag){0};
    node->tags = tags;
    node->tag_capacity = next;
    return true;
}

static const char *str_list_at(const StrList *items, int64_t index) {
    if (!items || index < 0 || index >= items->length || !items->pages) return "";
    int64_t page = index / 8;
    int64_t slot = index % 8;
    if (page < 0 || page >= items->page_count || !items->pages[page]) return "";
    const char *value = items->pages[page][slot];
    return value ? value : "";
}

static Dict make_permission_dict(const StrList *perms) {
    if (!perms || perms->length <= 0) return (Dict){0};
    int32_t count = perms->length > INT32_MAX ? INT32_MAX : (int32_t)perms->length;
    int32_t page_count = (count + 7) / 8;
    char ***key_pages = (char ***)calloc((size_t)page_count, sizeof(char **));
    char ***value_pages = (char ***)calloc((size_t)page_count, sizeof(char **));
    if (!key_pages || !value_pages) {
        free(key_pages);
        free(value_pages);
        return (Dict){0};
    }
    for (int32_t page = 0; page < page_count; ++page) {
        key_pages[page] = (char **)calloc(8, sizeof(char *));
        value_pages[page] = (char **)calloc(8, sizeof(char *));
        if (!key_pages[page] || !value_pages[page]) continue;
        for (int32_t slot = 0; slot < 8; ++slot) {
            int32_t index = page * 8 + slot;
            if (index >= count) break;
            bool *granted = (bool *)malloc(sizeof(bool));
            if (granted) *granted = false;
            key_pages[page][slot] = ez_ui_strdup(str_list_at(perms, index));
            value_pages[page][slot] = (char *)granted;
        }
    }
    return (Dict){key_pages, value_pages, count, page_count * 8, page_count};
}

Node createView(void) { return store_node("View"); }
Node createLinearLayout(const char *orientation) { (void)orientation; return store_node("LinearLayout"); }
Node createFrameLayout(void) { return store_node("FrameLayout"); }
Node createScrollView(void) { return store_node("ScrollView"); }
Node createHScrollView(void) { return store_node("HorizontalScrollView"); }
Node createRecyclerView(void) { return store_node("RecyclerView"); }
Node createTextView(void) { return store_node("TextView"); }
Node createEditText(void) { return store_node("EditText"); }
Node createButton(void) { return store_node("Button"); }
Node createImageButton(void) { return store_node("ImageButton"); }
Node createCheckBox(void) { return store_node("CheckBox"); }
Node createRadioButton(void) { return store_node("RadioButton"); }
Node createSwitch(void) { return store_node("Switch"); }
Node createImageView(void) { return store_node("ImageView"); }
Node createProgressBar(void) { return store_node("ProgressBar"); }
Node createSeekBar(void) { return store_node("SeekBar"); }
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
void setAdapter(const Node *recycler, AdapterItemCount itemCount, AdapterCreateItem createItem, AdapterBindItem bindItem, AdapterGetItemType getItemType) {
    UiNode *n = recycler ? lookup(*recycler) : NULL;
    if (!n) return;
    n->adapter_item_count = itemCount;
    n->adapter_create_item = createItem;
    n->adapter_bind_item = bindItem;
    n->adapter_get_item_type = getItemType;
}

void setLayoutWidth(const Node *node, int32_t value) {
    UiNode *n = node ? lookup(*node) : NULL;
    if (!n) return;
    n->width = value;
    n->measured_width = visible_size(value);
}
void setLayoutHeight(const Node *node, int32_t value) {
    UiNode *n = node ? lookup(*node) : NULL;
    if (!n) return;
    n->height = value;
    n->measured_height = visible_size(value);
}
void setMargin(const Node *node, int32_t left, int32_t top, int32_t right, int32_t bottom) {
    UiNode *n = node ? lookup(*node) : NULL;
    if (!n) return;
    n->margin[0] = left;
    n->margin[1] = top;
    n->margin[2] = right;
    n->margin[3] = bottom;
}
void setPadding(const Node *node, int32_t left, int32_t top, int32_t right, int32_t bottom) {
    UiNode *n = node ? lookup(*node) : NULL;
    if (!n) return;
    n->padding[0] = left;
    n->padding[1] = top;
    n->padding[2] = right;
    n->padding[3] = bottom;
}
void setWeight(const Node *node, float weight) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->weight = weight; }
void setGravity(const Node *node, int32_t gravity) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->gravity = gravity; }

void setText(const Node *node, const char *text) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->text, text); }
const char *getText(const Node *node) { return node_text(node ? lookup(*node) : NULL); }
void setTextSize(const Node *node, float sp) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->measured_height = sp > 0.0f ? (int32_t)(sp + 0.5f) : n->measured_height; }
void setTextColor(const Node *node, const Color *color) { UiNode *n = node ? lookup(*node) : NULL; if (n && color) n->text_color = *color; }
void setBackgroundColor(const Node *node, const Color *color) { UiNode *n = node ? lookup(*node) : NULL; if (n && color) n->background_color = *color; }
void setBackgroundDrawable(const Node *node, int32_t resId) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->background_drawable = resId; }
void setAlpha(const Node *node, float alpha) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->alpha = alpha; }
void setVisibility(const Node *node, int32_t v) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->visibility = v; }
void setEnabled(const Node *node, bool enabled) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->enabled = enabled; }
void setElevation(const Node *node, float dp) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->elevation = dp; }
void setCornerRadius(const Node *node, float dp) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->corner_radius = dp; }
void setTag(const Node *node, const char *key, const char *value) {
    UiNode *n = node ? lookup(*node) : NULL;
    if (!n || !key) return;
    UiTag *tag = find_tag(n, key);
    if (tag) {
        replace_string(&tag->value, value);
        return;
    }
    if (!ensure_tag_capacity(n, n->tag_count + 1)) return;
    tag = &n->tags[n->tag_count++];
    tag->key = ez_ui_strdup(key);
    tag->value = ez_ui_strdup(value);
}
OptStr getTag(const Node *node, const char *key) {
    UiTag *tag = find_tag(node ? lookup(*node) : NULL, key);
    return tag && tag->value ? (OptStr){true, tag->value} : (OptStr){false, NULL};
}
void setContentDesc(const Node *node, const char *desc) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->content_desc, desc); }
int32_t getWidth(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; return n ? visible_size(n->width) : 0; }
int32_t getHeight(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; return n ? visible_size(n->height) : 0; }
int32_t getMeasuredWidth(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; return n ? n->measured_width : 0; }
int32_t getMeasuredHeight(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; return n ? n->measured_height : 0; }

void setHint(const Node *node, const char *hint) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->hint, hint); }
void setHintColor(const Node *node, const Color *color) { UiNode *n = node ? lookup(*node) : NULL; if (n && color) n->hint_color = *color; }
void setTextStyle(const Node *node, int32_t style) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->text_style = style; }
void setMaxLines(const Node *node, int32_t max) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->max_lines = max; }
void setInputType(const Node *node, int32_t type_) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->input_type = type_; }

void setImageUrl(const Node *node, const char *url) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->image_url, url); }
void setImageRes(const Node *node, int32_t resId) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->image_res = resId; }
void setImageBlob(const Node *node, const Blob *data) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->image_blob_size = data ? data->size : 0; }
void setScaleType(const Node *node, const char *type_) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->scale_type, type_); }

void setOnClick(const Node *node, ClickHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_click = handler; }
void setOnLongClick(const Node *node, ClickHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_long_click = handler; }
void setOnTouch(const Node *node, TouchHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_touch = handler; }
void setOnTextChanged(const Node *node, TextChangeHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_text_changed = handler; }
void setOnCheckedChange(const Node *node, CheckChangeHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_checked_change = handler; }
void setOnScroll(const Node *node, ScrollHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_scroll = handler; }
void setOnFocus(const Node *node, FocusHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_focus = handler; }
void clearOnClick(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_click = NULL; }
void clearOnTouch(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_touch = NULL; }
void clearOnTextChanged(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_text_changed = NULL; }

void runOnMainThread(void (*work)(void)) { if (work) work(); }
int64_t postFrame(void (*work)(void)) { if (work) work(); return g_next_token++; }
void cancelFrame(int64_t token) { (void)token; }
int64_t postDelayed(void (*work)(void), int64_t ms) { (void)ms; if (work) work(); return g_next_token++; }
void cancelDelayed(int64_t token) { (void)token; }
bool isMainThread(void) { return true; }

Node getRootView(void) { return root_node(); }
void setStatusBarColor(const Color *color) { if (color) g_status_bar_color = *color; }
void showKeyboard(const Node *node) {
    UiNode *n = node ? lookup(*node) : NULL;
    g_keyboard_visible = true;
    if (n) n->focused = true;
}
void hideKeyboard(void) { g_keyboard_visible = false; }
void ezAndroidSetScreenMetrics(int32_t width, int32_t height, float density) {
    g_screen_width = width > 0 ? width : 0;
    g_screen_height = height > 0 ? height : 0;
    g_screen_density = density > 0.0f ? density : 1.0f;
}
float getScreenDensity(void) { return g_screen_density; }
int32_t getScreenWidth(void) { return g_screen_width; }
int32_t getScreenHeight(void) { return g_screen_height; }

bool requestPermission(const char *perm) { (void)perm; return false; }
Dict requestPermissions(const StrList *perms) { return make_permission_dict(perms); }
const char *queryPermission(const char *perm) { (void)perm; return "denied"; }
