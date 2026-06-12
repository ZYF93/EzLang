// EzLang std/regex 原生封装层

#include <stdbool.h>
#include <ctype.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32) || defined(EZ_REGEX_FORCE_PORTABLE)
#define EZ_REGEX_USE_PORTABLE 1
#else
#define EZ_REGEX_USE_PORTABLE 0
#endif

#if !EZ_REGEX_USE_PORTABLE
#include <regex.h>
#endif

typedef struct {
    char ***pages;
    int64_t length;
    int64_t capacity;
    int64_t page_count;
} StrList;

typedef struct {
    const char *pattern;
    int32_t flags;
    bool ok;
} Regex;

typedef struct {
    int64_t start;
    int64_t end;
    const char *text;
    StrList groups;
} RegexMatch;

typedef struct { bool ok; RegexMatch value; } OptRegexMatch;

#define EZ_REGEX_MAX_PATTERN_BYTES 4096
#define EZ_REGEX_MAX_GROUPS 64
#define EZ_REGEX_MAX_BOUNDED_REPEAT 1024

static char *ez_strdup_range(const char *src, size_t len) {
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    if (len > 0 && src) memcpy(out, src, len);
    out[len] = '\0';
    return out;
}

static char *ez_strdup_safe(const char *src) {
    if (!src) src = "";
    return ez_strdup_range(src, strlen(src));
}

static StrList ez_make_str_list(char **items, size_t count) {
    int64_t page_count = count == 0 ? 0 : (int64_t)((count + 7) / 8);
    char ***pages = page_count == 0 ? NULL : (char ***)calloc((size_t)page_count, sizeof(char **));
    if (page_count > 0 && !pages) return (StrList){0};
    for (int64_t page = 0; page < page_count; ++page) {
        pages[page] = (char **)calloc(8, sizeof(char *));
        if (!pages[page]) continue;
        for (int64_t offset = 0; offset < 8; ++offset) {
            size_t idx = (size_t)(page * 8 + offset);
            pages[page][offset] = idx < count ? items[idx] : NULL;
        }
    }
    return (StrList){pages, (int64_t)count, page_count * 8, page_count};
}

#if !EZ_REGEX_USE_PORTABLE
static int ez_regex_cflags(int32_t flags) {
    int cflags = REG_EXTENDED;
    if ((flags & 1) != 0) cflags |= REG_ICASE;
    if ((flags & 2) != 0) cflags |= REG_NEWLINE;
    return cflags;
}

static bool ez_regex_copy_class(const char *pattern, size_t len, size_t *index, char *out, size_t *offset) {
    size_t i = *index;
    out[(*offset)++] = pattern[i++];
    bool first = true;
    if (i < len && pattern[i] == '^') {
        out[(*offset)++] = pattern[i++];
    }
    while (i < len) {
        if (first && pattern[i] == ']') {
            out[(*offset)++] = pattern[i++];
            first = false;
            continue;
        }
        first = false;
        if (pattern[i] == '[' && i + 1 < len && (pattern[i + 1] == ':' || pattern[i + 1] == '.' || pattern[i + 1] == '=')) {
            char close = pattern[i + 1];
            out[(*offset)++] = pattern[i++];
            out[(*offset)++] = pattern[i++];
            while (i < len) {
                char ch = pattern[i];
                out[(*offset)++] = pattern[i++];
                if (ch == close && i < len && pattern[i] == ']') {
                    out[(*offset)++] = pattern[i++];
                    break;
                }
            }
            continue;
        }
        char ch = pattern[i];
        out[(*offset)++] = pattern[i++];
        if (ch == ']') {
            *index = i;
            return true;
        }
    }
    *index = i;
    return false;
}

static char *ez_regex_posix_pattern(const char *pattern) {
    if (!pattern) pattern = "";
    size_t len = strlen(pattern);
    if (len > (((size_t)-1) - 1) / 4) return NULL;
    char *out = (char *)malloc(len * 4 + 1);
    if (!out) return NULL;
    size_t offset = 0;
    for (size_t i = 0; i < len;) {
        char ch = pattern[i];
        if (ch == '\\') {
            out[offset++] = pattern[i++];
            if (i < len) out[offset++] = pattern[i++];
            continue;
        }
        if (ch == '[') {
            ez_regex_copy_class(pattern, len, &i, out, &offset);
            continue;
        }
        if (ch == '.') {
            out[offset++] = '[';
            out[offset++] = '^';
            out[offset++] = '\n';
            out[offset++] = ']';
            i++;
            continue;
        }
        out[offset++] = pattern[i++];
    }
    out[offset] = '\0';
    return out;
}
#endif

static bool ez_regex_is_global(const Regex *regex) {
    return regex && (regex->flags & 4) != 0;
}

static bool ez_regex_has_end_anchor(const char *pattern) {
    bool escaped = false;
    bool in_class = false;
    if (!pattern) return false;
    for (const char *p = pattern; *p; ++p) {
        if (escaped) {
            escaped = false;
            continue;
        }
        if (*p == '\\') {
            escaped = true;
            continue;
        }
        if (*p == '[') {
            in_class = true;
            continue;
        }
        if (*p == ']' && in_class) {
            in_class = false;
            continue;
        }
        if (*p == '$' && !in_class) return true;
    }
    return false;
}

typedef struct {
    bool has_variable_repeat;
    bool has_alternation;
} EzRegexRiskFrame;

typedef struct {
    bool exists;
    bool has_variable_repeat;
    bool has_alternation;
} EzRegexPendingAtom;

static void ez_regex_clear_pending(EzRegexPendingAtom *pending) {
    pending->exists = false;
    pending->has_variable_repeat = false;
    pending->has_alternation = false;
}

static void ez_regex_commit_pending(EzRegexRiskFrame *stack, size_t depth, EzRegexPendingAtom *pending) {
    if (!pending->exists || depth == 0) return;
    stack[depth - 1].has_variable_repeat = stack[depth - 1].has_variable_repeat || pending->has_variable_repeat;
    stack[depth - 1].has_alternation = stack[depth - 1].has_alternation || pending->has_alternation;
    ez_regex_clear_pending(pending);
}

static int ez_regex_parse_interval_limit(const char *pattern, size_t len, size_t start, size_t *end, bool *variable) {
    size_t i = start + 1;
    if (i >= len || !isdigit((unsigned char)pattern[i])) return 0;
    size_t min_value = 0;
    while (i < len && isdigit((unsigned char)pattern[i])) {
        size_t digit = (size_t)(pattern[i] - '0');
        if (min_value > (EZ_REGEX_MAX_BOUNDED_REPEAT - digit) / 10) return -1;
        min_value = min_value * 10 + digit;
        i++;
    }
    size_t max_value = min_value;
    bool has_max = true;
    if (i < len && pattern[i] == ',') {
        i++;
        if (i < len && pattern[i] == '}') {
            has_max = false;
        } else {
            if (i >= len || !isdigit((unsigned char)pattern[i])) return 0;
            max_value = 0;
            while (i < len && isdigit((unsigned char)pattern[i])) {
                size_t digit = (size_t)(pattern[i] - '0');
                if (max_value > (EZ_REGEX_MAX_BOUNDED_REPEAT - digit) / 10) return -1;
                max_value = max_value * 10 + digit;
                i++;
            }
        }
    }
    if (i >= len || pattern[i] != '}') return 0;
    if (has_max && max_value < min_value) return 0;
    *end = i + 1;
    *variable = !has_max || max_value != min_value;
    return 1;
}

static size_t ez_regex_skip_class(const char *pattern, size_t len, size_t start) {
    size_t i = start + 1;
    if (i < len && pattern[i] == '^') i++;
    if (i < len && pattern[i] == ']') i++;
    while (i < len) {
        if (pattern[i] == '\\' && i + 1 < len) {
            i += 2;
            continue;
        }
        if (pattern[i] == ']') return i + 1;
        i++;
    }
    return len;
}

static bool ez_regex_complexity_ok(const char *pattern) {
    if (!pattern) pattern = "";
    size_t len = strlen(pattern);
    if (len > EZ_REGEX_MAX_PATTERN_BYTES) return false;

    EzRegexRiskFrame stack[EZ_REGEX_MAX_GROUPS + 1];
    memset(stack, 0, sizeof(stack));
    size_t depth = 1;
    EzRegexPendingAtom pending = {0};

    for (size_t i = 0; i < len;) {
        char ch = pattern[i];
        if (ch == '\\') {
            ez_regex_commit_pending(stack, depth, &pending);
            pending = (EzRegexPendingAtom){true, false, false};
            i += (i + 1 < len) ? 2 : 1;
            continue;
        }
        if (ch == '[') {
            ez_regex_commit_pending(stack, depth, &pending);
            pending = (EzRegexPendingAtom){true, false, false};
            i = ez_regex_skip_class(pattern, len, i);
            continue;
        }
        if (ch == '(') {
            ez_regex_commit_pending(stack, depth, &pending);
            if (depth >= EZ_REGEX_MAX_GROUPS + 1) return false;
            memset(&stack[depth], 0, sizeof(stack[depth]));
            depth++;
            i++;
            continue;
        }
        if (ch == ')') {
            ez_regex_commit_pending(stack, depth, &pending);
            if (depth <= 1) {
                i++;
                continue;
            }
            EzRegexRiskFrame group = stack[--depth];
            pending = (EzRegexPendingAtom){true, group.has_variable_repeat, group.has_alternation};
            i++;
            continue;
        }
        if (ch == '|') {
            ez_regex_commit_pending(stack, depth, &pending);
            stack[depth - 1].has_alternation = true;
            i++;
            continue;
        }
        if (ch == '?' || ch == '*' || ch == '+') {
            if (!pending.exists) {
                i++;
                continue;
            }
            if (pending.has_variable_repeat || pending.has_alternation) return false;
            pending.has_variable_repeat = true;
            ez_regex_commit_pending(stack, depth, &pending);
            i++;
            continue;
        }
        if (ch == '{' && pending.exists) {
            size_t end = i;
            bool variable = false;
            int parsed = ez_regex_parse_interval_limit(pattern, len, i, &end, &variable);
            if (parsed < 0) return false;
            if (parsed > 0) {
                if (variable && (pending.has_variable_repeat || pending.has_alternation)) return false;
                if (variable) pending.has_variable_repeat = true;
                ez_regex_commit_pending(stack, depth, &pending);
                i = end;
                continue;
            }
        }
        ez_regex_commit_pending(stack, depth, &pending);
        pending = (EzRegexPendingAtom){true, false, false};
        i++;
    }
    ez_regex_commit_pending(stack, depth, &pending);
    return true;
}

static size_t ez_utf8_advance_one(const char *text) {
    unsigned char ch = (unsigned char)text[0];
    if (ch == 0) return 0;
    if (ch < 0x80) return 1;
    if (ch >= 0xC2 && ch <= 0xDF && (text[1] & 0xC0) == 0x80) return 2;
    if (ch >= 0xE0 && ch <= 0xEF && (text[1] & 0xC0) == 0x80 && (text[2] & 0xC0) == 0x80) return 3;
    if (ch >= 0xF0 && ch <= 0xF4 && (text[1] & 0xC0) == 0x80 && (text[2] & 0xC0) == 0x80 && (text[3] & 0xC0) == 0x80) return 4;
    return 1;
}

#if EZ_REGEX_USE_PORTABLE
typedef enum {
    EZ_RX_LITERAL,
    EZ_RX_DOT,
    EZ_RX_START,
    EZ_RX_END,
    EZ_RX_CLASS,
    EZ_RX_GROUP,
} EzRxNodeType;

typedef enum {
    EZ_RX_ONE,
    EZ_RX_OPTIONAL,
    EZ_RX_ZERO_OR_MORE,
    EZ_RX_ONE_OR_MORE,
    EZ_RX_BOUNDED,
} EzRxQuant;

typedef enum {
    EZ_RX_CLASS_LITERAL,
    EZ_RX_CLASS_RANGE,
    EZ_RX_CLASS_ALPHA,
    EZ_RX_CLASS_DIGIT,
    EZ_RX_CLASS_ALNUM,
    EZ_RX_CLASS_SPACE,
    EZ_RX_CLASS_LOWER,
    EZ_RX_CLASS_UPPER,
    EZ_RX_CLASS_WORD,
} EzRxClassKind;

typedef struct EzRxAlt EzRxAlt;

typedef struct {
    EzRxClassKind kind;
    unsigned char lo;
    unsigned char hi;
} EzRxClassItem;

typedef struct {
    bool negated;
    EzRxClassItem *items;
    size_t count;
    size_t capacity;
} EzRxClass;

typedef struct EzRxNode {
    EzRxNodeType type;
    EzRxQuant quant;
    unsigned char literal;
    EzRxClass cls;
    EzRxAlt *group;
    int group_index;
    size_t min_reps;
    size_t max_reps;
    bool has_max_reps;
} EzRxNode;

typedef struct {
    EzRxNode *nodes;
    size_t count;
    size_t capacity;
} EzRxSeq;

struct EzRxAlt {
    EzRxSeq *branches;
    size_t count;
    size_t capacity;
};

typedef struct {
    const char *cursor;
    int group_count;
    bool ok;
} EzRxParser;

typedef struct {
    int64_t start;
    int64_t end;
} EzRxCapture;

typedef struct {
    EzRxAlt root;
    int group_count;
    bool ok;
} EzRxCompiled;

typedef struct {
    const char *input;
    size_t length;
    int32_t flags;
    int group_count;
} EzRxContext;

static void ez_rx_free_alt(EzRxAlt *alt);

static void ez_rx_free_node(EzRxNode *node) {
    if (!node) return;
    free(node->cls.items);
    if (node->group) {
        ez_rx_free_alt(node->group);
        free(node->group);
    }
}

static void ez_rx_free_seq(EzRxSeq *seq) {
    if (!seq) return;
    for (size_t i = 0; i < seq->count; ++i) ez_rx_free_node(&seq->nodes[i]);
    free(seq->nodes);
    seq->nodes = NULL;
    seq->count = 0;
    seq->capacity = 0;
}

static void ez_rx_free_alt(EzRxAlt *alt) {
    if (!alt) return;
    for (size_t i = 0; i < alt->count; ++i) ez_rx_free_seq(&alt->branches[i]);
    free(alt->branches);
    alt->branches = NULL;
    alt->count = 0;
    alt->capacity = 0;
}

static bool ez_rx_push_node(EzRxSeq *seq, EzRxNode node) {
    if (seq->count == seq->capacity) {
        size_t next = seq->capacity ? seq->capacity * 2 : 8;
        EzRxNode *nodes = (EzRxNode *)realloc(seq->nodes, next * sizeof(EzRxNode));
        if (!nodes) return false;
        seq->nodes = nodes;
        seq->capacity = next;
    }
    seq->nodes[seq->count++] = node;
    return true;
}

static bool ez_rx_push_branch(EzRxAlt *alt, EzRxSeq seq) {
    if (alt->count == alt->capacity) {
        size_t next = alt->capacity ? alt->capacity * 2 : 4;
        EzRxSeq *branches = (EzRxSeq *)realloc(alt->branches, next * sizeof(EzRxSeq));
        if (!branches) return false;
        alt->branches = branches;
        alt->capacity = next;
    }
    alt->branches[alt->count++] = seq;
    return true;
}

static bool ez_rx_push_class_item(EzRxClass *cls, EzRxClassItem item) {
    if (cls->count == cls->capacity) {
        size_t next = cls->capacity ? cls->capacity * 2 : 8;
        EzRxClassItem *items = (EzRxClassItem *)realloc(cls->items, next * sizeof(EzRxClassItem));
        if (!items) return false;
        cls->items = items;
        cls->capacity = next;
    }
    cls->items[cls->count++] = item;
    return true;
}

static unsigned char ez_rx_ascii_lower(unsigned char ch) {
    return (ch >= 'A' && ch <= 'Z') ? (unsigned char)(ch + ('a' - 'A')) : ch;
}

static bool ez_rx_equal_char(unsigned char a, unsigned char b, int32_t flags) {
    if ((flags & 1) != 0) return ez_rx_ascii_lower(a) == ez_rx_ascii_lower(b);
    return a == b;
}

static unsigned char ez_rx_escaped_char(EzRxParser *parser) {
    unsigned char ch = (unsigned char)*parser->cursor;
    if (ch == 0) {
        parser->ok = false;
        return 0;
    }
    parser->cursor++;
    switch (ch) {
        case 'n': return '\n';
        case 'r': return '\r';
        case 't': return '\t';
        default: return ch;
    }
}

static bool ez_rx_is_quantifier_start(char ch) {
    return ch == '?' || ch == '*' || ch == '+' || ch == '{';
}

static bool ez_rx_parse_size(const char **cursor, size_t *out) {
    const unsigned char *p = (const unsigned char *)*cursor;
    if (!isdigit(*p)) return false;
    size_t value = 0;
    while (isdigit(*p)) {
        size_t digit = (size_t)(*p - '0');
        if (value > (((size_t)-1) - digit) / 10) return false;
        value = value * 10 + digit;
        p++;
    }
    *cursor = (const char *)p;
    *out = value;
    return true;
}

static bool ez_rx_parse_interval(EzRxParser *parser, size_t *min_reps, size_t *max_reps, bool *has_max_reps) {
    const char *cursor = parser->cursor;
    if (*cursor != '{') return false;
    cursor++;

    size_t min_value = 0;
    if (!ez_rx_parse_size(&cursor, &min_value)) return false;

    size_t max_value = min_value;
    bool has_max = true;
    if (*cursor == ',') {
        cursor++;
        if (*cursor == '}') {
            has_max = false;
            max_value = 0;
        } else if (!ez_rx_parse_size(&cursor, &max_value)) {
            return false;
        }
    }
    if (*cursor != '}') return false;
    if (has_max && max_value < min_value) return false;

    parser->cursor = cursor + 1;
    *min_reps = min_value;
    *max_reps = max_value;
    *has_max_reps = has_max;
    return true;
}

static bool ez_rx_posix_class(const char *name, size_t len, EzRxClassKind *kind) {
    if (len == 5 && strncmp(name, "alpha", len) == 0) *kind = EZ_RX_CLASS_ALPHA;
    else if (len == 5 && strncmp(name, "digit", len) == 0) *kind = EZ_RX_CLASS_DIGIT;
    else if (len == 5 && strncmp(name, "alnum", len) == 0) *kind = EZ_RX_CLASS_ALNUM;
    else if (len == 5 && strncmp(name, "space", len) == 0) *kind = EZ_RX_CLASS_SPACE;
    else if (len == 5 && strncmp(name, "lower", len) == 0) *kind = EZ_RX_CLASS_LOWER;
    else if (len == 5 && strncmp(name, "upper", len) == 0) *kind = EZ_RX_CLASS_UPPER;
    else if (len == 5 && strncmp(name, "blank", len) == 0) *kind = EZ_RX_CLASS_SPACE;
    else if (len == 4 && strncmp(name, "word", len) == 0) *kind = EZ_RX_CLASS_WORD;
    else return false;
    return true;
}

static unsigned char ez_rx_class_char(EzRxParser *parser) {
    if (*parser->cursor == '\\') {
        parser->cursor++;
        return ez_rx_escaped_char(parser);
    }
    unsigned char ch = (unsigned char)*parser->cursor;
    if (ch == 0) parser->ok = false;
    else parser->cursor++;
    return ch;
}

static EzRxClass ez_rx_parse_class(EzRxParser *parser) {
    EzRxClass cls = {0};
    parser->cursor++;
    if (*parser->cursor == '^') {
        cls.negated = true;
        parser->cursor++;
    }
    while (parser->ok && *parser->cursor && *parser->cursor != ']') {
        if (parser->cursor[0] == '[' && parser->cursor[1] == ':') {
            const char *name = parser->cursor + 2;
            const char *end = strstr(name, ":]");
            EzRxClassKind kind;
            if (!end || !ez_rx_posix_class(name, (size_t)(end - name), &kind)) {
                parser->ok = false;
                break;
            }
            if (!ez_rx_push_class_item(&cls, (EzRxClassItem){kind, 0, 0})) parser->ok = false;
            parser->cursor = end + 2;
            continue;
        }

        unsigned char lo = ez_rx_class_char(parser);
        if (!parser->ok) break;
        if (*parser->cursor == '-' && parser->cursor[1] != ']' && parser->cursor[1] != '\0') {
            parser->cursor++;
            unsigned char hi = ez_rx_class_char(parser);
            if (!parser->ok) break;
            if (hi < lo) {
                unsigned char tmp = lo;
                lo = hi;
                hi = tmp;
            }
            if (!ez_rx_push_class_item(&cls, (EzRxClassItem){EZ_RX_CLASS_RANGE, lo, hi})) parser->ok = false;
        } else {
            if (!ez_rx_push_class_item(&cls, (EzRxClassItem){EZ_RX_CLASS_LITERAL, lo, lo})) parser->ok = false;
        }
    }
    if (*parser->cursor != ']') parser->ok = false;
    else parser->cursor++;
    if (cls.count == 0) parser->ok = false;
    return cls;
}

static EzRxAlt ez_rx_parse_alt(EzRxParser *parser);

static EzRxNode ez_rx_parse_atom(EzRxParser *parser) {
    EzRxNode node;
    memset(&node, 0, sizeof(node));
    node.quant = EZ_RX_ONE;
    unsigned char ch = (unsigned char)*parser->cursor;
    if (ch == 0 || ch == ')' || ch == '|') {
        parser->ok = false;
        return node;
    }
    if (ch == '^') {
        parser->cursor++;
        node.type = EZ_RX_START;
    } else if (ch == '$') {
        parser->cursor++;
        node.type = EZ_RX_END;
    } else if (ch == '.') {
        parser->cursor++;
        node.type = EZ_RX_DOT;
    } else if (ch == '[') {
        node.type = EZ_RX_CLASS;
        node.cls = ez_rx_parse_class(parser);
    } else if (ch == '(') {
        parser->cursor++;
        node.type = EZ_RX_GROUP;
        node.group_index = ++parser->group_count;
        node.group = (EzRxAlt *)calloc(1, sizeof(EzRxAlt));
        if (!node.group) {
            parser->ok = false;
            return node;
        }
        *node.group = ez_rx_parse_alt(parser);
        if (*parser->cursor != ')') parser->ok = false;
        else parser->cursor++;
    } else if (ch == '\\') {
        parser->cursor++;
        node.type = EZ_RX_LITERAL;
        node.literal = ez_rx_escaped_char(parser);
    } else {
        parser->cursor++;
        node.type = EZ_RX_LITERAL;
        node.literal = ch;
    }

    if (!parser->ok) return node;
    if (*parser->cursor == '?' || *parser->cursor == '*' || *parser->cursor == '+') {
        char quant = *parser->cursor++;
        node.quant = quant == '?' ? EZ_RX_OPTIONAL : (quant == '*' ? EZ_RX_ZERO_OR_MORE : EZ_RX_ONE_OR_MORE);
        if (ez_rx_is_quantifier_start(*parser->cursor)) parser->ok = false;
    } else if (*parser->cursor == '{') {
        size_t min_reps = 0;
        size_t max_reps = 0;
        bool has_max_reps = false;
        if (!ez_rx_parse_interval(parser, &min_reps, &max_reps, &has_max_reps)) {
            parser->ok = false;
            return node;
        }
        node.quant = EZ_RX_BOUNDED;
        node.min_reps = min_reps;
        node.max_reps = max_reps;
        node.has_max_reps = has_max_reps;
        if (ez_rx_is_quantifier_start(*parser->cursor)) parser->ok = false;
    }
    return node;
}

static EzRxSeq ez_rx_parse_seq(EzRxParser *parser) {
    EzRxSeq seq = {0};
    while (parser->ok && *parser->cursor && *parser->cursor != ')' && *parser->cursor != '|') {
        EzRxNode node = ez_rx_parse_atom(parser);
        if (!parser->ok || !ez_rx_push_node(&seq, node)) {
            ez_rx_free_node(&node);
            parser->ok = false;
            break;
        }
    }
    return seq;
}

static EzRxAlt ez_rx_parse_alt(EzRxParser *parser) {
    EzRxAlt alt = {0};
    while (parser->ok) {
        EzRxSeq seq = ez_rx_parse_seq(parser);
        if (!parser->ok || !ez_rx_push_branch(&alt, seq)) {
            ez_rx_free_seq(&seq);
            parser->ok = false;
            break;
        }
        if (*parser->cursor != '|') break;
        parser->cursor++;
    }
    return alt;
}

static EzRxCompiled ez_rx_compile_pattern(const char *pattern) {
    EzRxParser parser = {pattern ? pattern : "", 0, true};
    EzRxCompiled compiled;
    memset(&compiled, 0, sizeof(compiled));
    compiled.root = ez_rx_parse_alt(&parser);
    compiled.group_count = parser.group_count;
    compiled.ok = parser.ok && *parser.cursor == '\0' && compiled.root.count > 0;
    if (!compiled.ok) ez_rx_free_alt(&compiled.root);
    return compiled;
}

static void ez_rx_free_compiled(EzRxCompiled *compiled) {
    if (!compiled) return;
    ez_rx_free_alt(&compiled->root);
    compiled->ok = false;
    compiled->group_count = 0;
}

static bool ez_rx_copy_captures(EzRxCapture *dst, const EzRxCapture *src, size_t slots) {
    if (slots == 0) return true;
    memcpy(dst, src, slots * sizeof(EzRxCapture));
    return true;
}

static void ez_rx_init_captures(EzRxCapture *captures, size_t slots) {
    for (size_t i = 0; i < slots; ++i) {
        captures[i].start = -1;
        captures[i].end = -1;
    }
}

static bool ez_rx_class_item_matches(EzRxClassItem item, unsigned char ch, int32_t flags) {
    unsigned char folded = (flags & 1) ? ez_rx_ascii_lower(ch) : ch;
    switch (item.kind) {
        case EZ_RX_CLASS_LITERAL:
            return ez_rx_equal_char(ch, item.lo, flags);
        case EZ_RX_CLASS_RANGE: {
            unsigned char lo = (flags & 1) ? ez_rx_ascii_lower(item.lo) : item.lo;
            unsigned char hi = (flags & 1) ? ez_rx_ascii_lower(item.hi) : item.hi;
            return folded >= lo && folded <= hi;
        }
        case EZ_RX_CLASS_ALPHA:
            return isalpha(ch) != 0;
        case EZ_RX_CLASS_DIGIT:
            return isdigit(ch) != 0;
        case EZ_RX_CLASS_ALNUM:
            return isalnum(ch) != 0;
        case EZ_RX_CLASS_SPACE:
            return isspace(ch) != 0;
        case EZ_RX_CLASS_LOWER:
            return islower(ch) != 0;
        case EZ_RX_CLASS_UPPER:
            return isupper(ch) != 0;
        case EZ_RX_CLASS_WORD:
            return isalnum(ch) || ch == '_';
    }
    return false;
}

static bool ez_rx_class_matches(const EzRxClass *cls, unsigned char ch, int32_t flags) {
    bool matched = false;
    for (size_t i = 0; i < cls->count; ++i) {
        if (ez_rx_class_item_matches(cls->items[i], ch, flags)) {
            matched = true;
            break;
        }
    }
    return cls->negated ? !matched : matched;
}

static bool ez_rx_match_alt(const EzRxAlt *alt, const EzRxContext *ctx, size_t pos, EzRxCapture *captures, size_t *out_pos);

static bool ez_rx_match_node_once(const EzRxNode *node, const EzRxContext *ctx, size_t pos, EzRxCapture *captures, size_t *out_pos) {
    if (node->type == EZ_RX_LITERAL) {
        if (pos >= ctx->length || !ez_rx_equal_char((unsigned char)ctx->input[pos], node->literal, ctx->flags)) return false;
        *out_pos = pos + 1;
        return true;
    }
    if (node->type == EZ_RX_DOT) {
        if (pos >= ctx->length || ctx->input[pos] == '\n') return false;
        *out_pos = pos + ez_utf8_advance_one(ctx->input + pos);
        return true;
    }
    if (node->type == EZ_RX_START) {
        if (pos == 0 || ((ctx->flags & 2) != 0 && pos > 0 && ctx->input[pos - 1] == '\n')) {
            *out_pos = pos;
            return true;
        }
        return false;
    }
    if (node->type == EZ_RX_END) {
        if (pos == ctx->length || ((ctx->flags & 2) != 0 && pos < ctx->length && ctx->input[pos] == '\n')) {
            *out_pos = pos;
            return true;
        }
        return false;
    }
    if (node->type == EZ_RX_CLASS) {
        if (pos >= ctx->length || !ez_rx_class_matches(&node->cls, (unsigned char)ctx->input[pos], ctx->flags)) return false;
        *out_pos = pos + 1;
        return true;
    }
    if (node->type == EZ_RX_GROUP) {
        size_t slots = (size_t)ctx->group_count + 1;
        EzRxCapture *scratch = (EzRxCapture *)malloc(slots * sizeof(EzRxCapture));
        if (!scratch) return false;
        ez_rx_copy_captures(scratch, captures, slots);
        size_t group_end = pos;
        bool ok = ez_rx_match_alt(node->group, ctx, pos, scratch, &group_end);
        if (ok) {
            scratch[node->group_index].start = (int64_t)pos;
            scratch[node->group_index].end = (int64_t)group_end;
            ez_rx_copy_captures(captures, scratch, slots);
            *out_pos = group_end;
        }
        free(scratch);
        return ok;
    }
    return false;
}

static bool ez_rx_match_seq(const EzRxSeq *seq, size_t index, const EzRxContext *ctx, size_t pos, EzRxCapture *captures, size_t *out_pos);

static bool ez_rx_match_repetition(const EzRxSeq *seq, size_t index, const EzRxContext *ctx, size_t pos, EzRxCapture *captures, size_t *out_pos, size_t min_reps, size_t max_reps, bool has_max_reps) {
    const EzRxNode *node = &seq->nodes[index];
    size_t slots = (size_t)ctx->group_count + 1;
    size_t cap = 8;
    size_t count = 1;
    size_t *positions = (size_t *)malloc(cap * sizeof(size_t));
    EzRxCapture *states = (EzRxCapture *)malloc(cap * slots * sizeof(EzRxCapture));
    if (!positions || !states) {
        free(positions);
        free(states);
        return false;
    }
    positions[0] = pos;
    ez_rx_copy_captures(states, captures, slots);

    while (!has_max_reps || count - 1 < max_reps) {
        EzRxCapture *prev_state = states + (count - 1) * slots;
        EzRxCapture *next_state = (EzRxCapture *)malloc(slots * sizeof(EzRxCapture));
        if (!next_state) break;
        ez_rx_copy_captures(next_state, prev_state, slots);
        size_t next_pos = positions[count - 1];
        bool ok = ez_rx_match_node_once(node, ctx, positions[count - 1], next_state, &next_pos);
        if (!ok) {
            free(next_state);
            break;
        }
        if (count == cap) {
            size_t next_cap = cap * 2;
            size_t *new_positions = (size_t *)realloc(positions, next_cap * sizeof(size_t));
            if (!new_positions) {
                free(next_state);
                free(positions);
                free(states);
                return false;
            }
            positions = new_positions;
            EzRxCapture *new_states = (EzRxCapture *)realloc(states, next_cap * slots * sizeof(EzRxCapture));
            if (!new_states) {
                free(next_state);
                free(positions);
                free(states);
                return false;
            }
            states = new_states;
            cap = next_cap;
        }
        positions[count] = next_pos;
        ez_rx_copy_captures(states + count * slots, next_state, slots);
        free(next_state);
        count++;
        if (next_pos == positions[count - 2]) break;
    }

    bool matched = false;
    for (size_t choice = count; choice-- > min_reps;) {
        EzRxCapture *choice_state = states + choice * slots;
        EzRxCapture *scratch = (EzRxCapture *)malloc(slots * sizeof(EzRxCapture));
        if (!scratch) continue;
        ez_rx_copy_captures(scratch, choice_state, slots);
        size_t tail_pos = positions[choice];
        if (ez_rx_match_seq(seq, index + 1, ctx, tail_pos, scratch, out_pos)) {
            ez_rx_copy_captures(captures, scratch, slots);
            matched = true;
            free(scratch);
            break;
        }
        free(scratch);
    }

    free(positions);
    free(states);
    return matched;
}

static bool ez_rx_match_seq(const EzRxSeq *seq, size_t index, const EzRxContext *ctx, size_t pos, EzRxCapture *captures, size_t *out_pos) {
    if (index >= seq->count) {
        *out_pos = pos;
        return true;
    }
    const EzRxNode *node = &seq->nodes[index];
    size_t slots = (size_t)ctx->group_count + 1;
    if (node->quant == EZ_RX_ZERO_OR_MORE) return ez_rx_match_repetition(seq, index, ctx, pos, captures, out_pos, 0, 0, false);
    if (node->quant == EZ_RX_ONE_OR_MORE) return ez_rx_match_repetition(seq, index, ctx, pos, captures, out_pos, 1, 0, false);
    if (node->quant == EZ_RX_BOUNDED) return ez_rx_match_repetition(seq, index, ctx, pos, captures, out_pos, node->min_reps, node->max_reps, node->has_max_reps);
    if (node->quant == EZ_RX_OPTIONAL) {
        EzRxCapture *scratch = (EzRxCapture *)malloc(slots * sizeof(EzRxCapture));
        if (scratch) {
            ez_rx_copy_captures(scratch, captures, slots);
            size_t next_pos = pos;
            if (ez_rx_match_node_once(node, ctx, pos, scratch, &next_pos) && ez_rx_match_seq(seq, index + 1, ctx, next_pos, scratch, out_pos)) {
                ez_rx_copy_captures(captures, scratch, slots);
                free(scratch);
                return true;
            }
            free(scratch);
        }
        return ez_rx_match_seq(seq, index + 1, ctx, pos, captures, out_pos);
    }

    EzRxCapture *scratch = (EzRxCapture *)malloc(slots * sizeof(EzRxCapture));
    if (!scratch) return false;
    ez_rx_copy_captures(scratch, captures, slots);
    size_t next_pos = pos;
    bool ok = ez_rx_match_node_once(node, ctx, pos, scratch, &next_pos) && ez_rx_match_seq(seq, index + 1, ctx, next_pos, scratch, out_pos);
    if (ok) ez_rx_copy_captures(captures, scratch, slots);
    free(scratch);
    return ok;
}

static bool ez_rx_match_alt(const EzRxAlt *alt, const EzRxContext *ctx, size_t pos, EzRxCapture *captures, size_t *out_pos) {
    size_t slots = (size_t)ctx->group_count + 1;
    for (size_t i = 0; i < alt->count; ++i) {
        EzRxCapture *scratch = (EzRxCapture *)malloc(slots * sizeof(EzRxCapture));
        if (!scratch) return false;
        ez_rx_copy_captures(scratch, captures, slots);
        size_t branch_end = pos;
        if (ez_rx_match_seq(&alt->branches[i], 0, ctx, pos, scratch, &branch_end)) {
            ez_rx_copy_captures(captures, scratch, slots);
            *out_pos = branch_end;
            free(scratch);
            return true;
        }
        free(scratch);
    }
    return false;
}

static bool ez_rx_search(const EzRxCompiled *compiled, const char *input, size_t start, EzRxCapture *captures, size_t *match_start, size_t *match_end, int32_t flags) {
    EzRxContext ctx = {input ? input : "", strlen(input ? input : ""), flags, compiled->group_count};
    size_t slots = (size_t)compiled->group_count + 1;
    if (start > ctx.length) return false;
    for (size_t pos = start; pos <= ctx.length;) {
        ez_rx_init_captures(captures, slots);
        size_t end = pos;
        if (ez_rx_match_alt(&compiled->root, &ctx, pos, captures, &end)) {
            captures[0].start = (int64_t)pos;
            captures[0].end = (int64_t)end;
            *match_start = pos;
            *match_end = end;
            return true;
        }
        if (pos == ctx.length) break;
        size_t step = ez_utf8_advance_one(ctx.input + pos);
        pos += step ? step : 1;
    }
    return false;
}

static bool ez_rx_pattern_valid(const char *pattern, int *group_count) {
    EzRxCompiled compiled = ez_rx_compile_pattern(pattern);
    bool ok = compiled.ok;
    if (group_count) *group_count = compiled.group_count;
    ez_rx_free_compiled(&compiled);
    return ok;
}

static OptRegexMatch ez_rx_find_portable(const Regex *regex, const char *input) {
    if (!input) input = "";
    if (!regex || !regex->pattern || !regex->ok) return (OptRegexMatch){false, {0}};
    EzRxCompiled compiled = ez_rx_compile_pattern(regex->pattern);
    if (!compiled.ok) return (OptRegexMatch){false, {0}};
    size_t slots = (size_t)compiled.group_count + 1;
    EzRxCapture *captures = (EzRxCapture *)malloc(slots * sizeof(EzRxCapture));
    if (!captures) {
        ez_rx_free_compiled(&compiled);
        return (OptRegexMatch){false, {0}};
    }
    size_t start = 0;
    size_t end = 0;
    bool ok = ez_rx_search(&compiled, input, 0, captures, &start, &end, regex->flags);
    if (!ok) {
        free(captures);
        ez_rx_free_compiled(&compiled);
        return (OptRegexMatch){false, {0}};
    }

    size_t capture_count = (size_t)compiled.group_count;
    char **groups = capture_count == 0 ? NULL : (char **)calloc(capture_count, sizeof(char *));
    if (capture_count > 0 && !groups) {
        free(captures);
        ez_rx_free_compiled(&compiled);
        return (OptRegexMatch){false, {0}};
    }
    for (size_t i = 0; i < capture_count; ++i) {
        EzRxCapture cap = captures[i + 1];
        groups[i] = cap.start >= 0 && cap.end >= cap.start ? ez_strdup_range(input + cap.start, (size_t)(cap.end - cap.start)) : ez_strdup_safe("");
    }
    RegexMatch match;
    match.start = (int64_t)start;
    match.end = (int64_t)end;
    match.text = ez_strdup_range(input + start, end - start);
    match.groups = ez_make_str_list(groups, capture_count);
    free(groups);
    free(captures);
    ez_rx_free_compiled(&compiled);
    return (OptRegexMatch){true, match};
}
#endif

#if !EZ_REGEX_USE_PORTABLE
static bool ez_compile(const Regex *regex, regex_t *compiled) {
    if (!regex || !regex->pattern || !regex->ok || !ez_regex_complexity_ok(regex->pattern)) return false;
    char *pattern = ez_regex_posix_pattern(regex->pattern);
    if (!pattern) return false;
    bool ok = regcomp(compiled, pattern, ez_regex_cflags(regex->flags)) == 0;
    free(pattern);
    return ok;
}
#endif

Regex regexCompile(const char *pattern, int32_t flags) {
    if (!pattern) pattern = "";
    bool safe = ez_regex_complexity_ok(pattern);
#if EZ_REGEX_USE_PORTABLE
    return (Regex){ez_strdup_safe(pattern), flags, safe && ez_rx_pattern_valid(pattern, NULL)};
#else
    regex_t compiled;
    char *native_pattern = ez_regex_posix_pattern(pattern);
    bool ok = safe && native_pattern && regcomp(&compiled, native_pattern, ez_regex_cflags(flags)) == 0;
    if (ok) regfree(&compiled);
    free(native_pattern);
    return (Regex){ez_strdup_safe(pattern), flags, ok};
#endif
}

bool regexIsValid(const Regex *regex) {
#if EZ_REGEX_USE_PORTABLE
    return regex && regex->ok && ez_regex_complexity_ok(regex->pattern) && ez_rx_pattern_valid(regex->pattern, NULL);
#else
    regex_t compiled;
    if (!ez_compile(regex, &compiled)) return false;
    regfree(&compiled);
    return true;
#endif
}

bool regexTest(const Regex *regex, const char *input) {
    if (!input) input = "";
#if EZ_REGEX_USE_PORTABLE
    OptRegexMatch found = ez_rx_find_portable(regex, input);
    return found.ok;
#else
    regex_t compiled;
    if (!ez_compile(regex, &compiled)) return false;
    int result = regexec(&compiled, input, 0, NULL, 0);
    regfree(&compiled);
    return result == 0;
#endif
}

static OptRegexMatch ez_find_impl(const Regex *regex, const char *input) {
    if (!input) input = "";
#if EZ_REGEX_USE_PORTABLE
    return ez_rx_find_portable(regex, input);
#else
    regex_t compiled;
    if (!ez_compile(regex, &compiled)) return (OptRegexMatch){false, {0}};
    size_t group_count = compiled.re_nsub + 1;
    regmatch_t *matches = (regmatch_t *)calloc(group_count, sizeof(regmatch_t));
    if (!matches) {
        regfree(&compiled);
        return (OptRegexMatch){false, {0}};
    }
    int result = regexec(&compiled, input, group_count, matches, 0);
    if (result != 0 || matches[0].rm_so < 0) {
        free(matches);
        regfree(&compiled);
        return (OptRegexMatch){false, {0}};
    }

    size_t capture_count = group_count > 0 ? group_count - 1 : 0;
    char **groups = capture_count == 0 ? NULL : (char **)calloc(capture_count, sizeof(char *));
    if (capture_count > 0 && !groups) {
        free(matches);
        regfree(&compiled);
        return (OptRegexMatch){false, {0}};
    }
    for (size_t i = 0; i < capture_count; ++i) {
        regmatch_t group = matches[i + 1];
        groups[i] = group.rm_so >= 0 ? ez_strdup_range(input + group.rm_so, (size_t)(group.rm_eo - group.rm_so)) : ez_strdup_safe("");
    }
    RegexMatch match;
    match.start = matches[0].rm_so;
    match.end = matches[0].rm_eo;
    match.text = ez_strdup_range(input + matches[0].rm_so, (size_t)(matches[0].rm_eo - matches[0].rm_so));
    match.groups = ez_make_str_list(groups, capture_count);
    free(groups);
    free(matches);
    regfree(&compiled);
    return (OptRegexMatch){true, match};
#endif
}

OptRegexMatch regexFind(const Regex *regex, const char *input) {
    return ez_find_impl(regex, input);
}

StrList regexFindAll(const Regex *regex, const char *input) {
    if (!input) input = "";
#if EZ_REGEX_USE_PORTABLE
    if (!regex || !regex->ok) return (StrList){0};
    EzRxCompiled compiled = ez_rx_compile_pattern(regex->pattern);
    if (!compiled.ok) return (StrList){0};
    size_t cap = 8;
    size_t count = 0;
    char **items = (char **)calloc(cap, sizeof(char *));
    size_t slots = (size_t)compiled.group_count + 1;
    EzRxCapture *captures = (EzRxCapture *)malloc(slots * sizeof(EzRxCapture));
    if (!items || !captures) {
        free(items);
        free(captures);
        ez_rx_free_compiled(&compiled);
        return (StrList){0};
    }
    size_t input_len = strlen(input);
    size_t cursor = 0;
    while (cursor <= input_len) {
        size_t start = 0;
        size_t end = 0;
        if (!ez_rx_search(&compiled, input, cursor, captures, &start, &end, regex->flags)) break;
        if (count == cap) {
            cap *= 2;
            char **next = (char **)realloc(items, cap * sizeof(char *));
            if (!next) break;
            items = next;
        }
        items[count++] = ez_strdup_range(input + start, end - start);
        if (end == start) {
            if (end >= input_len) break;
            cursor = end + ez_utf8_advance_one(input + end);
        } else {
            cursor = end;
        }
    }
    StrList result = ez_make_str_list(items, count);
    free(items);
    free(captures);
    ez_rx_free_compiled(&compiled);
    return result;
#else
    regex_t compiled;
    if (!ez_compile(regex, &compiled)) return (StrList){0};
    size_t cap = 8;
    size_t count = 0;
    char **items = (char **)calloc(cap, sizeof(char *));
    if (!items) {
        regfree(&compiled);
        return (StrList){0};
    }
    const char *input_start = input;
    const char *input_end = input + strlen(input);
    const char *cursor = input;
    while (cursor <= input_end) {
        regmatch_t match;
        int eflags = cursor == input_start ? 0 : REG_NOTBOL;
        if (regexec(&compiled, cursor, 1, &match, eflags) != 0 || match.rm_so < 0) break;
        if (count == cap) {
            cap *= 2;
            char **next = (char **)realloc(items, cap * sizeof(char *));
            if (!next) break;
            items = next;
        }
        items[count++] = ez_strdup_range(cursor + match.rm_so, (size_t)(match.rm_eo - match.rm_so));
        cursor += match.rm_eo;
        if (match.rm_so == match.rm_eo) {
            if (*cursor == '\0') break;
            cursor += ez_utf8_advance_one(cursor);
        }
    }
    StrList result = ez_make_str_list(items, count);
    free(items);
    regfree(&compiled);
    return result;
#endif
}

const char *regexReplace(const Regex *regex, const char *input, const char *replacement) {
    if (!input) input = "";
    if (!replacement) replacement = "";
#if EZ_REGEX_USE_PORTABLE
    if (!regex || !regex->ok) return ez_strdup_safe(input);
    EzRxCompiled compiled = ez_rx_compile_pattern(regex->pattern);
    if (!compiled.ok) return ez_strdup_safe(input);
    size_t input_len = strlen(input);
    size_t repl_len = strlen(replacement);
    size_t cap = input_len + repl_len + 1;
    char *out = (char *)malloc(cap);
    size_t slots = (size_t)compiled.group_count + 1;
    EzRxCapture *captures = (EzRxCapture *)malloc(slots * sizeof(EzRxCapture));
    if (!out || !captures) {
        free(out);
        free(captures);
        ez_rx_free_compiled(&compiled);
        return NULL;
    }

    bool replace_all = ez_regex_is_global(regex);
    bool replaced = false;
    bool last_match_was_final_zero_width = false;
    size_t cursor = 0;
    size_t out_len = 0;
    while (cursor <= input_len) {
        size_t start = 0;
        size_t end = 0;
        if (!ez_rx_search(&compiled, input, cursor, captures, &start, &end, regex->flags)) break;
        bool zero_width = start == end;
        bool final_zero_width = zero_width && end == input_len;
        size_t progress_len = replace_all && zero_width && end < input_len ? ez_utf8_advance_one(input + end) : 0;
        size_t need = out_len + (start - cursor) + repl_len + progress_len + (input_len - end) + 1;
        if (need > cap) {
            while (need > cap) cap *= 2;
            char *next = (char *)realloc(out, cap);
            if (!next) {
                free(out);
                free(captures);
                ez_rx_free_compiled(&compiled);
                return NULL;
            }
            out = next;
        }
        memcpy(out + out_len, input + cursor, start - cursor);
        out_len += start - cursor;
        memcpy(out + out_len, replacement, repl_len);
        out_len += repl_len;
        replaced = true;
        last_match_was_final_zero_width = final_zero_width;
        cursor = end;
        if (!replace_all) break;
        if (zero_width) {
            if (cursor >= input_len) break;
            size_t char_len = ez_utf8_advance_one(input + cursor);
            memcpy(out + out_len, input + cursor, char_len);
            out_len += char_len;
            cursor += char_len;
        }
    }

    if (replace_all && !last_match_was_final_zero_width && regex && ez_regex_has_end_anchor(regex->pattern)) {
        size_t need = out_len + (input_len - cursor) + repl_len + 1;
        if (need > cap) {
            char *next = (char *)realloc(out, need);
            if (!next) {
                free(out);
                free(captures);
                ez_rx_free_compiled(&compiled);
                return NULL;
            }
            out = next;
            cap = need;
        }
        memcpy(out + out_len, input + cursor, input_len - cursor);
        out_len += input_len - cursor;
        memcpy(out + out_len, replacement, repl_len);
        out_len += repl_len;
        cursor = input_len;
        replaced = true;
    }

    if (!replaced) {
        free(out);
        free(captures);
        ez_rx_free_compiled(&compiled);
        return ez_strdup_safe(input);
    }
    if (out_len + (input_len - cursor) + 1 > cap) {
        char *next = (char *)realloc(out, out_len + (input_len - cursor) + 1);
        if (!next) {
            free(out);
            free(captures);
            ez_rx_free_compiled(&compiled);
            return NULL;
        }
        out = next;
    }
    memcpy(out + out_len, input + cursor, input_len - cursor);
    out_len += input_len - cursor;
    out[out_len] = '\0';
    free(captures);
    ez_rx_free_compiled(&compiled);
    return out;
#else
    regex_t compiled;
    if (!ez_compile(regex, &compiled)) return ez_strdup_safe(input);

    size_t input_len = strlen(input);
    size_t repl_len = strlen(replacement);
    size_t cap = input_len + repl_len + 1;
    char *out = (char *)malloc(cap);
    if (!out) {
        regfree(&compiled);
        return NULL;
    }

    const char *input_start = input;
    const char *cursor = input;
    size_t out_len = 0;
    bool replaced = false;
    bool replace_all = ez_regex_is_global(regex);
    bool last_match_was_final_zero_width = false;
    while (*cursor) {
        regmatch_t match;
        int eflags = cursor == input_start ? 0 : REG_NOTBOL;
        if (regexec(&compiled, cursor, 1, &match, eflags) != 0 || match.rm_so < 0) break;

        size_t prefix_len = (size_t)match.rm_so;
        bool zero_width = match.rm_so == match.rm_eo;
        bool final_zero_width = zero_width && cursor[match.rm_eo] == '\0';
        size_t progress_len = replace_all && zero_width && cursor[match.rm_eo] != '\0' ? ez_utf8_advance_one(cursor + match.rm_eo) : 0;
        size_t need = out_len + prefix_len + repl_len + progress_len + strlen(cursor + match.rm_eo) + 1;
        if (need > cap) {
            while (need > cap) cap *= 2;
            char *next = (char *)realloc(out, cap);
            if (!next) {
                free(out);
                regfree(&compiled);
                return NULL;
            }
            out = next;
        }
        memcpy(out + out_len, cursor, prefix_len);
        out_len += prefix_len;
        memcpy(out + out_len, replacement, repl_len);
        out_len += repl_len;
        replaced = true;
        last_match_was_final_zero_width = final_zero_width;

        if (!replace_all) {
            cursor += match.rm_eo;
            break;
        }
        cursor += match.rm_eo;
        if (zero_width) {
            if (*cursor == '\0') break;
            size_t char_len = ez_utf8_advance_one(cursor);
            memcpy(out + out_len, cursor, char_len);
            out_len += char_len;
            cursor += char_len;
        }
    }

    if (replace_all && !last_match_was_final_zero_width) {
        if (ez_regex_has_end_anchor(regex->pattern)) {
            size_t tail_len = strlen(cursor);
            size_t need = out_len + tail_len + repl_len + 1;
            if (need > cap) {
                char *next = (char *)realloc(out, need);
                if (!next) {
                    free(out);
                    regfree(&compiled);
                    return NULL;
                }
                out = next;
                cap = need;
            }
            memcpy(out + out_len, cursor, tail_len);
            out_len += tail_len;
            memcpy(out + out_len, replacement, repl_len);
            out_len += repl_len;
            cursor += tail_len;
            replaced = true;
        }
    }

    if (!replaced) {
        free(out);
        regfree(&compiled);
        return ez_strdup_safe(input);
    }
    size_t tail_len = strlen(cursor);
    if (out_len + tail_len + 1 > cap) {
        char *next = (char *)realloc(out, out_len + tail_len + 1);
        if (!next) {
            free(out);
            regfree(&compiled);
            return NULL;
        }
        out = next;
    }
    memcpy(out + out_len, cursor, tail_len + 1);
    regfree(&compiled);
    return out;
#endif
}

StrList regexSplit(const Regex *regex, const char *input) {
    if (!input) input = "";
#if EZ_REGEX_USE_PORTABLE
    if (!regex || !regex->ok) {
        char *items[1] = {ez_strdup_safe(input)};
        return ez_make_str_list(items, 1);
    }
    EzRxCompiled compiled = ez_rx_compile_pattern(regex->pattern);
    if (!compiled.ok) {
        char *items[1] = {ez_strdup_safe(input)};
        return ez_make_str_list(items, 1);
    }
    size_t cap = 8;
    size_t count = 0;
    char **items = (char **)calloc(cap, sizeof(char *));
    size_t slots = (size_t)compiled.group_count + 1;
    EzRxCapture *captures = (EzRxCapture *)malloc(slots * sizeof(EzRxCapture));
    if (!items || !captures) {
        free(items);
        free(captures);
        ez_rx_free_compiled(&compiled);
        return (StrList){0};
    }
    size_t input_len = strlen(input);
    size_t cursor = 0;
    while (cursor <= input_len) {
        size_t start = 0;
        size_t end = 0;
        if (!ez_rx_search(&compiled, input, cursor, captures, &start, &end, regex->flags)) break;
        if (count == cap) {
            cap *= 2;
            char **next = (char **)realloc(items, cap * sizeof(char *));
            if (!next) break;
            items = next;
        }
        items[count++] = ez_strdup_range(input + cursor, start - cursor);
        if (end == start) {
            if (end >= input_len) {
                cursor = end;
                break;
            }
            cursor = end + ez_utf8_advance_one(input + end);
        } else {
            cursor = end;
        }
    }
    if (count == cap) {
        cap += 1;
        char **next = (char **)realloc(items, cap * sizeof(char *));
        if (next) items = next;
    }
    items[count++] = ez_strdup_safe(input + cursor);
    StrList result = ez_make_str_list(items, count);
    free(items);
    free(captures);
    ez_rx_free_compiled(&compiled);
    return result;
#else
    regex_t compiled;
    if (!ez_compile(regex, &compiled)) {
        char *items[1] = {ez_strdup_safe(input)};
        return ez_make_str_list(items, 1);
    }
    size_t cap = 8;
    size_t count = 0;
    char **items = (char **)calloc(cap, sizeof(char *));
    if (!items) {
        regfree(&compiled);
        return (StrList){0};
    }
    const char *input_start = input;
    const char *cursor = input;
    while (true) {
        regmatch_t match;
        int eflags = cursor == input_start ? 0 : REG_NOTBOL;
        int result = regexec(&compiled, cursor, 1, &match, eflags);
        if (result != 0 || match.rm_so < 0) break;
        if (count == cap) {
            cap *= 2;
            char **next = (char **)realloc(items, cap * sizeof(char *));
            if (!next) break;
            items = next;
        }
        items[count++] = ez_strdup_range(cursor, (size_t)match.rm_so);
        if (match.rm_eo > 0) {
            cursor += match.rm_eo;
        } else {
            cursor += match.rm_so;
            if (*cursor == '\0') break;
            cursor += ez_utf8_advance_one(cursor);
        }
        if (!*cursor) break;
    }
    if (count == cap) {
        cap += 1;
        char **next = (char **)realloc(items, cap * sizeof(char *));
        if (next) items = next;
    }
    items[count++] = ez_strdup_safe(cursor);
    StrList result = ez_make_str_list(items, count);
    free(items);
    regfree(&compiled);
    return result;
#endif
}
