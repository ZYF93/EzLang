// EzLang std/path 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char ***pages;
    int64_t length;
    int64_t capacity;
    int64_t page_count;
} StrList;

typedef struct {
    const char *root;
    const char *dir;
    const char *base;
    const char *name;
    const char *ext;
} PathParts;

typedef struct {
    bool ok;
    const char *value;
} OptStr;

static char ez_native_sep(void) {
#if defined(_WIN32)
    return '\\';
#else
    return '/';
#endif
}

static bool ez_is_sep(char ch) {
    return ch == '/' || ch == '\\';
}

static bool ez_has_backslash(const char *text) {
    return text && strchr(text, '\\') != NULL;
}

static char ez_style_sep(const char *path) {
    return ez_has_backslash(path) ? '\\' : ez_native_sep();
}

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

static const char *ez_list_get(const StrList *items, int64_t index) {
    if (!items || index < 0 || index >= items->length || !items->pages || items->page_count <= 0) return "";
    int64_t page = index / 8;
    int64_t offset = index % 8;
    if (page >= items->page_count || !items->pages[page]) return "";
    return items->pages[page][offset] ? items->pages[page][offset] : "";
}

static bool ez_is_windows_drive(const char *path) {
    return path && ((path[0] >= 'A' && path[0] <= 'Z') || (path[0] >= 'a' && path[0] <= 'z')) && path[1] == ':';
}

static size_t ez_root_len(const char *path) {
    if (!path || !*path) return 0;
    if (ez_is_windows_drive(path)) {
        return ez_is_sep(path[2]) ? 3 : 2;
    }
    if (ez_is_sep(path[0]) && ez_is_sep(path[1])) {
        const char *p = path + 2;
        while (*p && !ez_is_sep(*p)) p++;
        if (ez_is_sep(*p)) {
            p++;
            while (*p && !ez_is_sep(*p)) p++;
        }
        return (size_t)(p - path);
    }
    return ez_is_sep(path[0]) ? 1 : 0;
}

static bool ez_path_is_abs_raw(const char *path) {
    if (!path || !*path) return false;
    if (ez_is_sep(path[0])) return true;
    return ez_is_windows_drive(path) && ez_is_sep(path[2]);
}

static bool ez_component_boundary(const char *path, size_t index) {
    return !path || path[index] == '\0' || ez_is_sep(path[index]);
}

static size_t ez_component_count(const char *path) {
    size_t count = 0;
    bool in_component = false;
    for (const char *p = path; p && *p; ++p) {
        if (ez_is_sep(*p)) {
            if (in_component) {
                count++;
                in_component = false;
            }
        } else {
            in_component = true;
        }
    }
    return in_component ? count + 1 : count;
}

static char *ez_append_part(char *out, size_t *len, size_t *cap, const char *part, size_t part_len, char sep) {
    if (*len + part_len + 2 > *cap) {
        while (*len + part_len + 2 > *cap) *cap *= 2;
        char *next = (char *)realloc(out, *cap);
        if (!next) {
            free(out);
            return NULL;
        }
        out = next;
    }
    if (*len > 0 && !ez_is_sep(out[*len - 1]) && part_len > 0) {
        out[(*len)++] = sep;
    }
    if (part_len > 0) {
        memcpy(out + *len, part, part_len);
        *len += part_len;
    }
    out[*len] = '\0';
    return out;
}

static char *ez_join_raw(const StrList *parts) {
    char sep = ez_native_sep();
    for (int64_t i = 0; parts && i < parts->length; ++i) {
        const char *part = ez_list_get(parts, i);
        if (ez_has_backslash(part)) {
            sep = '\\';
            break;
        }
    }

    size_t cap = 32;
    size_t len = 0;
    char *out = (char *)malloc(cap);
    if (!out) return NULL;
    out[0] = '\0';

    for (int64_t i = 0; parts && i < parts->length; ++i) {
        const char *part = ez_list_get(parts, i);
        if (!part || !*part) continue;
        size_t start = 0;
        size_t part_len = strlen(part);
        if (len > 0) {
            while (start < part_len && ez_is_sep(part[start])) start++;
        }
        out = ez_append_part(out, &len, &cap, part + start, part_len - start, sep);
        if (!out) return NULL;
    }
    return out;
}

static char *ez_normalize_raw(const char *path) {
    if (!path || !*path) return ez_strdup_safe(".");
    char sep = ez_style_sep(path);
    size_t root_len = ez_root_len(path);
    bool absolute = ez_path_is_abs_raw(path);
    char *root = ez_strdup_range(path, root_len);
    if (!root) return NULL;
    for (size_t i = 0; i < root_len; ++i) {
        if (ez_is_sep(root[i])) root[i] = sep;
    }

    size_t part_cap = 16;
    size_t part_count = 0;
    char **parts = (char **)calloc(part_cap, sizeof(char *));
    if (!parts) {
        free(root);
        return NULL;
    }

    const char *p = path + root_len;
    while (*p) {
        while (ez_is_sep(*p)) p++;
        const char *start = p;
        while (*p && !ez_is_sep(*p)) p++;
        size_t len = (size_t)(p - start);
        if (len == 0 || (len == 1 && start[0] == '.')) continue;
        if (len == 2 && start[0] == '.' && start[1] == '.') {
            if (part_count > 0 && strcmp(parts[part_count - 1], "..") != 0) {
                free(parts[--part_count]);
                parts[part_count] = NULL;
            } else if (!absolute) {
                if (part_count == part_cap) {
                    part_cap *= 2;
                    char **next = (char **)realloc(parts, part_cap * sizeof(char *));
                    if (!next) goto fail;
                    parts = next;
                }
                parts[part_count++] = ez_strdup_range(start, len);
            }
            continue;
        }
        if (part_count == part_cap) {
            part_cap *= 2;
            char **next = (char **)realloc(parts, part_cap * sizeof(char *));
            if (!next) goto fail;
            parts = next;
        }
        parts[part_count++] = ez_strdup_range(start, len);
        if (!parts[part_count - 1]) goto fail;
    }

    size_t cap = strlen(root) + 2;
    for (size_t i = 0; i < part_count; ++i) cap += strlen(parts[i]) + 1;
    char *out = (char *)malloc(cap);
    if (!out) goto fail;
    out[0] = '\0';
    strcat(out, root);
    size_t out_len = strlen(out);
    for (size_t i = 0; i < part_count; ++i) {
        if (out_len > 0 && !ez_is_sep(out[out_len - 1])) out[out_len++] = sep;
        strcpy(out + out_len, parts[i]);
        out_len += strlen(parts[i]);
    }
    if (out_len == 0) strcpy(out, ".");
    if (root_len == 1 && part_count == 0) {
        out[0] = sep;
        out[1] = '\0';
    }
    for (size_t i = 0; i < part_count; ++i) free(parts[i]);
    free(parts);
    free(root);
    return out;

fail:
    for (size_t i = 0; i < part_count; ++i) free(parts[i]);
    free(parts);
    free(root);
    return NULL;
}

static size_t ez_last_sep_index(const char *path, size_t len) {
    while (len > 0 && ez_is_sep(path[len - 1])) len--;
    while (len > 0) {
        if (ez_is_sep(path[len - 1])) return len - 1;
        len--;
    }
    return (size_t)-1;
}

static const char *ez_base_start(const char *path, size_t *base_len) {
    size_t len = path ? strlen(path) : 0;
    while (len > 1 && ez_is_sep(path[len - 1])) len--;
    size_t root_len = ez_root_len(path);
    if (len <= root_len) {
        *base_len = root_len;
        return path;
    }
    size_t sep_index = ez_last_sep_index(path, len);
    const char *start = sep_index == (size_t)-1 ? path : path + sep_index + 1;
    *base_len = (size_t)(path + len - start);
    return start;
}

static size_t ez_ext_offset(const char *base, size_t len) {
    if (!base || len == 0) return len;
    for (size_t i = len; i > 0; --i) {
        if (base[i - 1] == '.') {
            if (i == 1) return len;
            return i - 1;
        }
    }
    return len;
}

const char *pathSeparator(void) {
    char *out = (char *)malloc(2);
    if (!out) return NULL;
    out[0] = ez_native_sep();
    out[1] = '\0';
    return out;
}

const char *pathJoin(const StrList *parts) {
    char *joined = ez_join_raw(parts);
    if (!joined) return NULL;
    char *normalized = ez_normalize_raw(joined);
    free(joined);
    return normalized;
}

const char *pathNormalize(const char *path) {
    return ez_normalize_raw(path);
}

const char *pathDir(const char *path) {
    if (!path || !*path) return ez_strdup_safe(".");
    size_t len = strlen(path);
    while (len > 1 && ez_is_sep(path[len - 1])) len--;
    size_t root_len = ez_root_len(path);
    size_t sep_index = ez_last_sep_index(path, len);
    if (sep_index == (size_t)-1) return ez_strdup_safe(".");
    if (sep_index == 0) return ez_strdup_range(path, 1);
    if (sep_index < root_len) return ez_strdup_range(path, root_len);
    return ez_strdup_range(path, sep_index);
}

const char *pathBase(const char *path) {
    size_t len = 0;
    const char *base = ez_base_start(path ? path : "", &len);
    return ez_strdup_range(base, len);
}

const char *pathExt(const char *path) {
    size_t len = 0;
    const char *base = ez_base_start(path ? path : "", &len);
    size_t dot = ez_ext_offset(base, len);
    return dot < len ? ez_strdup_range(base + dot, len - dot) : ez_strdup_safe("");
}

bool pathIsAbs(const char *path) {
    return ez_path_is_abs_raw(path);
}

const char *pathRelative(const char *from, const char *to) {
    char *from_norm = ez_normalize_raw(from);
    char *to_norm = ez_normalize_raw(to);
    if (!from_norm || !to_norm) {
        free(from_norm);
        free(to_norm);
        return NULL;
    }
    if (ez_path_is_abs_raw(from_norm) != ez_path_is_abs_raw(to_norm)) {
        free(from_norm);
        return to_norm;
    }
    if (ez_is_windows_drive(from_norm) && ez_is_windows_drive(to_norm) &&
        (from_norm[0] | 32) != (to_norm[0] | 32)) {
        free(from_norm);
        return to_norm;
    }

    char sep = ez_style_sep(to_norm);
    size_t from_root = ez_root_len(from_norm);
    size_t to_root = ez_root_len(to_norm);
    size_t common = from_root > to_root ? from_root : to_root;
    while (from_norm[common] && to_norm[common] &&
           (from_norm[common] == to_norm[common] || (ez_is_sep(from_norm[common]) && ez_is_sep(to_norm[common])))) {
        common++;
    }
    if (!ez_component_boundary(from_norm, common) || !ez_component_boundary(to_norm, common)) {
        while (common > from_root && !ez_is_sep(from_norm[common - 1])) common--;
    }

    const char *from_tail = from_norm + common;
    while (ez_is_sep(*from_tail)) from_tail++;
    size_t up_count = ez_component_count(from_tail);

    const char *tail = to_norm + common;
    while (ez_is_sep(*tail)) tail++;
    size_t tail_len = strlen(tail);
    size_t cap = up_count * 3 + tail_len + 2;
    char *out = (char *)malloc(cap);
    if (!out) {
        free(from_norm);
        free(to_norm);
        return NULL;
    }
    size_t len = 0;
    for (size_t i = 0; i < up_count; ++i) {
        if (len > 0) out[len++] = sep;
        out[len++] = '.';
        out[len++] = '.';
    }
    if (tail_len > 0) {
        if (len > 0) out[len++] = sep;
        memcpy(out + len, tail, tail_len);
        len += tail_len;
    }
    if (len == 0) out[len++] = '.';
    out[len] = '\0';
    free(from_norm);
    free(to_norm);
    return out;
}

PathParts pathParse(const char *path) {
    if (!path) path = "";
    size_t root_len = ez_root_len(path);
    size_t base_len = 0;
    const char *base = ez_base_start(path, &base_len);
    size_t ext_off = ez_ext_offset(base, base_len);
    const char *base_end = base + base_len;
    const char *dir_end = base > path ? base - 1 : path;
    while (dir_end > path && ez_is_sep(*(dir_end - 1))) dir_end--;
    if ((size_t)(dir_end - path) < root_len) dir_end = path + root_len;
    return (PathParts){
        ez_strdup_range(path, root_len),
        ez_strdup_range(path, (size_t)(dir_end - path)),
        ez_strdup_range(base, base_len),
        ez_strdup_range(base, ext_off),
        ext_off < base_len ? ez_strdup_range(base + ext_off, (size_t)(base_end - base - ext_off)) : ez_strdup_safe(""),
    };
}

static bool ez_is_unreserved(unsigned char ch) {
    return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
           (ch >= '0' && ch <= '9') || ch == '-' || ch == '_' || ch == '.' || ch == '~' || ch == '/';
}

const char *pathToFileUrl(const char *path) {
    char *normalized = ez_normalize_raw(path);
    if (!normalized) return NULL;
    size_t cap = strlen(normalized) * 3 + 16;
    char *out = (char *)malloc(cap);
    if (!out) {
        free(normalized);
        return NULL;
    }
    strcpy(out, "file://");
    size_t len = strlen(out);
    if (!ez_path_is_abs_raw(normalized)) out[len++] = '/';
    for (const unsigned char *p = (const unsigned char *)normalized; *p; ++p) {
        unsigned char ch = *p == '\\' ? '/' : *p;
        if (ez_is_unreserved(ch)) {
            out[len++] = (char)ch;
        } else {
            static const char hex[] = "0123456789ABCDEF";
            out[len++] = '%';
            out[len++] = hex[ch >> 4];
            out[len++] = hex[ch & 15];
        }
    }
    out[len] = '\0';
    free(normalized);
    return out;
}

static int ez_hex_value(char ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    return -1;
}

OptStr pathFromFileUrl(const char *url) {
    const char *prefix = "file://";
    size_t prefix_len = strlen(prefix);
    if (!url || strncmp(url, prefix, prefix_len) != 0) return (OptStr){false, NULL};
    const char *src = url + prefix_len;
    char *out = (char *)malloc(strlen(src) + 1);
    if (!out) return (OptStr){false, NULL};
    size_t len = 0;
    for (size_t i = 0; src[i]; ++i) {
        if (src[i] == '%') {
            if (!src[i + 1] || !src[i + 2]) {
                free(out);
                return (OptStr){false, NULL};
            }
            int hi = ez_hex_value(src[i + 1]);
            int lo = ez_hex_value(src[i + 2]);
            if (hi < 0 || lo < 0) {
                free(out);
                return (OptStr){false, NULL};
            }
            out[len++] = (char)((hi << 4) | lo);
            i += 2;
        } else {
            out[len++] = src[i] == '/' ? ez_native_sep() : src[i];
        }
    }
    out[len] = '\0';
    return (OptStr){true, out};
}
