// ez-ios-ui 原生句柄状态层。
// iOS 宿主可在此层替换为 UIKit 对象引用；当前实现维护可测试的 View 树与属性状态。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int32_t id; } Node;
typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { float r; float g; float b; float a; } Color;
typedef struct { float x; float y; float width; float height; } Rect;
typedef struct { float top; float left; float bottom; float right; } Insets;
typedef struct { bool ok; Node value; } OptNode;
typedef struct { char ***pages; int64_t length; int64_t capacity; int64_t page_count; } StrList;

typedef struct {
    const char *phase;
    float x;
    float y;
} TouchEvent;

typedef struct {
    const char *text;
    int32_t range;
} TextChangedEvent;

typedef void (*ActionHandler)(void);
typedef void (*TouchHandler)(const TouchEvent *event);
typedef void (*TextChangeHandler)(const TextChangedEvent *event);
typedef int32_t (*TableRowCount)(int32_t section);
typedef Node (*TableCreateCell)(const char *reuse_id);
typedef void (*TableBindCell)(const Node *cell, int32_t row, int32_t section);
typedef float (*TableCellHeight)(int32_t row, int32_t section);

typedef struct UiNode {
    int32_t id;
    char *kind;
    char *text;
    char *attributed_text;
    char *font_name;
    char *placeholder;
    char *access_label;
    char *image_url;
    char *image_name;
    char *system_image;
    char *button_title;
    char *button_image;
    int64_t image_blob_size;
    Rect frame;
    Rect bounds;
    Insets edge_insets;
    bool centered;
    float spacing;
    int32_t alignment;
    int32_t distribution;
    bool hidden;
    float alpha;
    bool user_interaction;
    bool clips_to_bounds;
    float corner_radius;
    float border_width;
    Color text_color;
    Color background_color;
    Color border_color;
    Color shadow_color;
    Color tint_color;
    Color switch_tint_color;
    Rect shadow_offset;
    float shadow_radius;
    float shadow_opacity;
    int32_t tag;
    float font_size;
    float font_weight;
    int32_t text_align;
    int32_t number_of_lines;
    int32_t line_break_mode;
    int32_t keyboard_type;
    bool secure_entry;
    int32_t return_key_type;
    int32_t content_mode;
    int32_t button_title_state;
    int32_t button_image_state;
    bool button_enabled;
    bool switch_on;
    float slider_value;
    float slider_min;
    float slider_max;
    bool animating;
    bool needs_layout;
    bool first_responder;
    int64_t segment_count;
    ActionHandler target_handler;
    int32_t target_event;
    TextChangeHandler on_text_changed;
    ActionHandler on_return;
    ActionHandler tap_handler;
    int32_t tap_count;
    ActionHandler long_press_handler;
    float long_press_duration;
    TouchHandler pan_handler;
    ActionHandler swipe_handler;
    int32_t swipe_direction;
    TableRowCount table_row_count;
    TableCreateCell table_create_cell;
    TableBindCell table_bind_cell;
    TableCellHeight table_cell_height;
    struct UiNode *parent;
    struct UiNode **children;
    int32_t child_count;
    int32_t child_capacity;
} UiNode;

static UiNode **g_nodes = NULL;
static int32_t g_capacity = 0;
static int32_t g_next_id = 1;
static UiNode *g_root = NULL;
static int64_t g_next_token = 1;
static float g_screen_width = 0.0f;
static float g_screen_height = 0.0f;
static float g_screen_scale = 1.0f;
static Insets g_safe_area_insets = {0, 0, 0, 0};
static float g_status_bar_height = 0.0f;

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

static char *plain_text_from_html(const char *html) {
    if (!html) html = "";
    size_t len = strlen(html);
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    size_t w = 0;
    bool in_tag = false;
    for (size_t i = 0; i < len; ++i) {
        char ch = html[i];
        if (in_tag) {
            if (ch == '>') in_tag = false;
            continue;
        }
        if (ch == '<') {
            in_tag = true;
            continue;
        }
        if (ch == '&') {
            if (strncmp(html + i, "&amp;", 5) == 0) { out[w++] = '&'; i += 4; continue; }
            if (strncmp(html + i, "&lt;", 4) == 0) { out[w++] = '<'; i += 3; continue; }
            if (strncmp(html + i, "&gt;", 4) == 0) { out[w++] = '>'; i += 3; continue; }
            if (strncmp(html + i, "&quot;", 6) == 0) { out[w++] = '"'; i += 5; continue; }
            if (strncmp(html + i, "&#39;", 5) == 0) { out[w++] = '\''; i += 4; continue; }
            if (strncmp(html + i, "&nbsp;", 6) == 0) { out[w++] = ' '; i += 5; continue; }
        }
        out[w++] = ch;
    }
    out[w] = '\0';
    return out;
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
    node->attributed_text = ez_ui_strdup("");
    node->font_name = ez_ui_strdup("");
    node->placeholder = ez_ui_strdup("");
    node->access_label = ez_ui_strdup("");
    node->image_url = ez_ui_strdup("");
    node->image_name = ez_ui_strdup("");
    node->system_image = ez_ui_strdup("");
    node->button_title = ez_ui_strdup("");
    node->button_image = ez_ui_strdup("");
    node->alpha = 1.0f;
    node->user_interaction = true;
    node->button_enabled = true;
    node->slider_max = 1.0f;
    g_nodes[id] = node;
    return (Node){id};
}

static Node root_node(void) {
    if (g_root) return (Node){g_root->id};
    Node root = store_node("UIWindowRootView");
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

static int32_t child_index(UiNode *parent, UiNode *child) {
    if (!parent || !child) return -1;
    for (int32_t i = 0; i < parent->child_count; ++i) {
        if (parent->children[i] == child) return i;
    }
    return -1;
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

static void move_child(UiNode *child, int32_t index) {
    if (!child || !child->parent) return;
    UiNode *parent = child->parent;
    detach(child);
    add_child_at(parent, child, index);
}

static void free_node(UiNode *node) {
    if (!node) return;
    while (node->child_count > 0) detach(node->children[node->child_count - 1]);
    detach(node);
    if (g_root == node) g_root = NULL;
    if (node->id > 0 && node->id < g_capacity) g_nodes[node->id] = NULL;
    free(node->children);
    free(node->kind);
    free(node->text);
    free(node->attributed_text);
    free(node->font_name);
    free(node->placeholder);
    free(node->access_label);
    free(node->image_url);
    free(node->image_name);
    free(node->system_image);
    free(node->button_title);
    free(node->button_image);
    free(node);
}

static const char *node_text(UiNode *node) { return node && node->text ? node->text : ""; }

Node createView(void) { return store_node("UIView"); }
Node createStackView(const char *axis) { (void)axis; return store_node("UIStackView"); }
Node createScrollView(void) { return store_node("UIScrollView"); }
Node createLabel(void) { return store_node("UILabel"); }
Node createTextField(void) { return store_node("UITextField"); }
Node createTextView(void) { return store_node("UITextView"); }
Node createButton(void) { return store_node("UIButton"); }
Node createSwitch(void) { return store_node("UISwitch"); }
Node createSlider(void) { return store_node("UISlider"); }
Node createSegmentControl(const StrList *segments) {
    Node node = store_node("UISegmentedControl");
    UiNode *n = lookup(node);
    if (n && segments) n->segment_count = segments->length;
    return node;
}
Node createStepper(void) { return store_node("UIStepper"); }
Node createActivityIndicator(void) { return store_node("UIActivityIndicatorView"); }
Node createImageView(void) { return store_node("UIImageView"); }
Node createTableView(void) { return store_node("UITableView"); }
Node createCollectionView(void) { return store_node("UICollectionView"); }
void destroyNode(const Node *node) { if (node) free_node(lookup(*node)); }

void addSubview(const Node *parent, const Node *child) { if (parent && child) add_child_at(lookup(*parent), lookup(*child), -1); }
void insertSubviewAt(const Node *parent, const Node *child, int32_t index) { if (parent && child) add_child_at(lookup(*parent), lookup(*child), index); }
void insertSubviewAbove(const Node *parent, const Node *child, const Node *ref) {
    UiNode *p = parent ? lookup(*parent) : NULL;
    UiNode *r = ref ? lookup(*ref) : NULL;
    int32_t index = child_index(p, r);
    if (parent && child) add_child_at(p, lookup(*child), index < 0 ? -1 : index + 1);
}
void insertSubviewBelow(const Node *parent, const Node *child, const Node *ref) {
    UiNode *p = parent ? lookup(*parent) : NULL;
    UiNode *r = ref ? lookup(*ref) : NULL;
    int32_t index = child_index(p, r);
    if (parent && child) add_child_at(p, lookup(*child), index < 0 ? 0 : index);
}
void removeFromSuperview(const Node *node) { if (node) detach(lookup(*node)); }
void bringToFront(const Node *node) {
    UiNode *n = node ? lookup(*node) : NULL;
    if (n && n->parent) move_child(n, n->parent->child_count - 1);
}
void sendToBack(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) move_child(n, 0); }
OptNode getSubviewAt(const Node *parent, int32_t index) {
    UiNode *p = parent ? lookup(*parent) : NULL;
    if (!p || index < 0 || index >= p->child_count) return (OptNode){false, {0}};
    return (OptNode){true, {p->children[index]->id}};
}
int32_t getSubviewCount(const Node *parent) { UiNode *p = parent ? lookup(*parent) : NULL; return p ? p->child_count : 0; }
OptNode getSuperview(const Node *node) {
    UiNode *n = node ? lookup(*node) : NULL;
    return n && n->parent ? (OptNode){true, {n->parent->id}} : (OptNode){false, {0}};
}
Node getRootView(void) { return root_node(); }
void setTableAdapter(const Node *table, TableRowCount rowCount, TableCreateCell createCell, TableBindCell bindCell, TableCellHeight cellHeight) {
    UiNode *n = table ? lookup(*table) : NULL;
    if (!n) return;
    n->table_row_count = rowCount;
    n->table_create_cell = createCell;
    n->table_bind_cell = bindCell;
    n->table_cell_height = cellHeight;
}

void setFrame(const Node *node, const Rect *rect) { UiNode *n = node ? lookup(*node) : NULL; if (n && rect) n->frame = *rect; }
Rect getFrame(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; return n ? n->frame : (Rect){0, 0, 0, 0}; }
void setBounds(const Node *node, const Rect *rect) { UiNode *n = node ? lookup(*node) : NULL; if (n && rect) n->bounds = *rect; }
Rect getBounds(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; return n ? n->bounds : (Rect){0, 0, 0, 0}; }
void pinToEdges(const Node *node, const Insets *insets) { UiNode *n = node ? lookup(*node) : NULL; if (n && insets) n->edge_insets = *insets; }
void centerInParent(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->centered = true; }
void setWidth(const Node *node, float width) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->frame.width = width; }
void setHeight(const Node *node, float height) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->frame.height = height; }
void sizeToFit(const Node *node) {
    UiNode *n = node ? lookup(*node) : NULL;
    if (!n) return;
    if (n->frame.width <= 0.0f) n->frame.width = (float)strlen(node_text(n));
    if (n->frame.height <= 0.0f) n->frame.height = n->font_size > 0.0f ? n->font_size : 1.0f;
}
void setSpacing(const Node *node, float spacing) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->spacing = spacing; }
void setAlignment(const Node *node, int32_t align) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->alignment = align; }
void setDistribution(const Node *node, int32_t dist) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->distribution = dist; }

void setText(const Node *node, const char *text) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->text, text); }
const char *getText(const Node *node) { return node_text(node ? lookup(*node) : NULL); }
void setAttributedText(const Node *node, const char *html) {
    UiNode *n = node ? lookup(*node) : NULL;
    if (!n) return;
    replace_string(&n->attributed_text, html);
    char *plain = plain_text_from_html(html);
    if (!plain) return;
    free(n->text);
    n->text = plain;
}
void setFont(const Node *node, const char *name, float size) { UiNode *n = node ? lookup(*node) : NULL; if (n) { replace_string(&n->font_name, name); n->font_size = size; } }
void setSystemFont(const Node *node, float size, float weight) { UiNode *n = node ? lookup(*node) : NULL; if (n) { replace_string(&n->font_name, ".SFUI"); n->font_size = size; n->font_weight = weight; } }
void setTextColor(const Node *node, const Color *color) { UiNode *n = node ? lookup(*node) : NULL; if (n && color) n->text_color = *color; }
void setTextAlign(const Node *node, int32_t align) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->text_align = align; }
void setNumberOfLines(const Node *node, int32_t count) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->number_of_lines = count; }
void setLineBreakMode(const Node *node, int32_t mode) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->line_break_mode = mode; }
void setPlaceholder(const Node *node, const char *text) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->placeholder, text); }
void setKeyboardType(const Node *node, int32_t type_) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->keyboard_type = type_; }
void setSecureEntry(const Node *node, bool secure) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->secure_entry = secure; }
void setReturnKeyType(const Node *node, int32_t type_) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->return_key_type = type_; }
void setBackgroundColor(const Node *node, const Color *color) { UiNode *n = node ? lookup(*node) : NULL; if (n && color) n->background_color = *color; }
void setAlpha(const Node *node, float alpha) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->alpha = alpha; }
void setHidden(const Node *node, bool hidden) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->hidden = hidden; }
void setUserInteraction(const Node *node, bool enabled) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->user_interaction = enabled; }
void setClipsToBounds(const Node *node, bool clips) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->clips_to_bounds = clips; }
void setCornerRadius(const Node *node, float radius) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->corner_radius = radius; }
void setBorderWidth(const Node *node, float width) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->border_width = width; }
void setBorderColor(const Node *node, const Color *color) { UiNode *n = node ? lookup(*node) : NULL; if (n && color) n->border_color = *color; }
void setShadow(const Node *node, const Color *color, const Rect *offset, float radius, float opacity) {
    UiNode *n = node ? lookup(*node) : NULL;
    if (!n) return;
    if (color) n->shadow_color = *color;
    if (offset) n->shadow_offset = *offset;
    n->shadow_radius = radius;
    n->shadow_opacity = opacity;
}
void setTag_(const Node *node, int32_t tag) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->tag = tag; }
int32_t getTag_(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; return n ? n->tag : 0; }
void setAccessLabel(const Node *node, const char *label) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->access_label, label); }
void layoutIfNeeded(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->needs_layout = false; }
void setNeedsLayout(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->needs_layout = true; }

void setImageUrl(const Node *node, const char *url) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->image_url, url); }
void setImageName(const Node *node, const char *name) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->image_name, name); }
void setSystemImage(const Node *node, const char *sfName) { UiNode *n = node ? lookup(*node) : NULL; if (n) replace_string(&n->system_image, sfName); }
void setImageBlob(const Node *node, const Blob *data) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->image_blob_size = data ? data->size : 0; }
void setContentMode(const Node *node, int32_t mode) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->content_mode = mode; }
void setTintColor(const Node *node, const Color *color) { UiNode *n = node ? lookup(*node) : NULL; if (n && color) n->tint_color = *color; }

void setButtonTitle(const Node *node, const char *title, int32_t state) { UiNode *n = node ? lookup(*node) : NULL; if (n) { replace_string(&n->button_title, title); n->button_title_state = state; } }
void setButtonImage(const Node *node, const char *name, int32_t state) { UiNode *n = node ? lookup(*node) : NULL; if (n) { replace_string(&n->button_image, name); n->button_image_state = state; } }
void setButtonEnabled(const Node *node, bool enabled) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->button_enabled = enabled; }
void setSwitchOn(const Node *node, bool on, bool animated) { (void)animated; UiNode *n = node ? lookup(*node) : NULL; if (n) n->switch_on = on; }
bool getSwitchOn(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; return n ? n->switch_on : false; }
void setSwitchTintColor(const Node *node, const Color *color) { UiNode *n = node ? lookup(*node) : NULL; if (n && color) n->switch_tint_color = *color; }
void setSliderValue(const Node *node, float value, bool animated) { (void)animated; UiNode *n = node ? lookup(*node) : NULL; if (n) n->slider_value = value; }
float getSliderValue(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; return n ? n->slider_value : 0.0f; }
void setSliderRange(const Node *node, float min, float max) { UiNode *n = node ? lookup(*node) : NULL; if (n) { n->slider_min = min; n->slider_max = max; } }
void startAnimating(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->animating = true; }
void stopAnimating(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->animating = false; }

void addTarget(const Node *node, int32_t event, ActionHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) { n->target_event = event; n->target_handler = handler; } }
void removeTarget(const Node *node, int32_t event) { UiNode *n = node ? lookup(*node) : NULL; if (n && n->target_event == event) n->target_handler = NULL; }
void setOnTextChanged(const Node *node, TextChangeHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_text_changed = handler; }
void setOnReturn(const Node *node, ActionHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->on_return = handler; }
void addTapGesture(const Node *node, int32_t taps, ActionHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) { n->tap_count = taps; n->tap_handler = handler; } }
void addLongPressGesture(const Node *node, float minDuration, ActionHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) { n->long_press_duration = minDuration; n->long_press_handler = handler; } }
void addPanGesture(const Node *node, TouchHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->pan_handler = handler; }
void addSwipeGesture(const Node *node, int32_t direction, ActionHandler handler) { UiNode *n = node ? lookup(*node) : NULL; if (n) { n->swipe_direction = direction; n->swipe_handler = handler; } }
void removeTapGesture(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->tap_handler = NULL; }
void becomeFirstResponder(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->first_responder = true; }
void resignFirstResponder(const Node *node) { UiNode *n = node ? lookup(*node) : NULL; if (n) n->first_responder = false; }

void runOnMainThread(void (*work)(void)) { if (work) work(); }
void postToMain(void (*work)(void)) { if (work) work(); }
int64_t postDelayed(void (*work)(void), double ms) { (void)ms; if (work) work(); return g_next_token++; }
void cancelDelayed(int64_t token) { (void)token; }
int64_t scheduleFrame(void (*work)(void)) { if (work) work(); return g_next_token++; }
void cancelFrame(int64_t token) { (void)token; }
bool isMainThread(void) { return true; }

void ezIosSetScreenMetrics(float width, float height, float scale, float safeTop, float safeLeft, float safeBottom, float safeRight, float statusBarHeight) {
    g_screen_width = width > 0.0f ? width : 0.0f;
    g_screen_height = height > 0.0f ? height : 0.0f;
    g_screen_scale = scale > 0.0f ? scale : 1.0f;
    g_safe_area_insets = (Insets){
        safeTop > 0.0f ? safeTop : 0.0f,
        safeLeft > 0.0f ? safeLeft : 0.0f,
        safeBottom > 0.0f ? safeBottom : 0.0f,
        safeRight > 0.0f ? safeRight : 0.0f,
    };
    g_status_bar_height = statusBarHeight > 0.0f ? statusBarHeight : 0.0f;
}
float getScreenWidth(void) { return g_screen_width; }
float getScreenHeight(void) { return g_screen_height; }
float getScreenScale(void) { return g_screen_scale; }
Insets getSafeAreaInsets(void) { return g_safe_area_insets; }
float getStatusBarHeight(void) { return g_status_bar_height; }

bool requestPermission(const char *perm) { (void)perm; return false; }
const char *queryPermission(const char *perm) { (void)perm; return "denied"; }
