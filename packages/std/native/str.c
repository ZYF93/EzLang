// EzLang std/str 原生封装层

#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

typedef struct {
    char ***pages;
    int64_t length;
    int64_t capacity;
    int64_t page_count;
} StrList;

typedef struct {
    bool ok;
    const char *value;
} OptStr;

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

static int ez_utf8_char_width(unsigned char ch) {
    if (ch < 0x80) return 1;
    if (ch >= 0xC2 && ch <= 0xDF) return 2;
    if (ch >= 0xE0 && ch <= 0xEF) return 3;
    if (ch >= 0xF0 && ch <= 0xF4) return 4;
    return -1;
}

static bool ez_utf8_validate_len(const char *s, size_t len) {
    if (!s) return true;
    size_t i = 0;
    while (i < len) {
        unsigned char ch = (unsigned char)s[i];
        int width = ez_utf8_char_width(ch);
        if (width < 0 || i + (size_t)width > len) return false;
        if (width == 2) {
            unsigned char b1 = (unsigned char)s[i + 1];
            if ((b1 & 0xC0) != 0x80) return false;
        } else if (width == 3) {
            unsigned char b1 = (unsigned char)s[i + 1];
            unsigned char b2 = (unsigned char)s[i + 2];
            if ((b1 & 0xC0) != 0x80 || (b2 & 0xC0) != 0x80) return false;
            if (ch == 0xE0 && b1 < 0xA0) return false;
            if (ch == 0xED && b1 >= 0xA0) return false;
        } else if (width == 4) {
            unsigned char b1 = (unsigned char)s[i + 1];
            unsigned char b2 = (unsigned char)s[i + 2];
            unsigned char b3 = (unsigned char)s[i + 3];
            if ((b1 & 0xC0) != 0x80 || (b2 & 0xC0) != 0x80 || (b3 & 0xC0) != 0x80) return false;
            if (ch == 0xF0 && b1 < 0x90) return false;
            if (ch == 0xF4 && b1 > 0x8F) return false;
        }
        i += (size_t)width;
    }
    return true;
}

static size_t ez_utf8_byte_offset(const char *s, size_t len, int64_t char_index) {
    if (char_index <= 0) return 0;
    size_t i = 0;
    int64_t count = 0;
    while (i < len && count < char_index) {
        int width = ez_utf8_char_width((unsigned char)s[i]);
        if (width < 0 || i + (size_t)width > len) width = 1;
        i += (size_t)width;
        count++;
    }
    return i;
}

int64_t strByteLen(const char *s) {
    return s ? (int64_t)strlen(s) : 0;
}

int64_t strCharLen(const char *s) {
    if (!s) return 0;
    size_t len = strlen(s);
    size_t i = 0;
    int64_t count = 0;
    while (i < len) {
        int width = ez_utf8_char_width((unsigned char)s[i]);
        if (width < 0 || i + (size_t)width > len) width = 1;
        i += (size_t)width;
        count++;
    }
    return count;
}

bool strIsEmpty(const char *s) {
    return !s || s[0] == '\0';
}

bool strIsValidUtf8(const char *s) {
    return ez_utf8_validate_len(s, s ? strlen(s) : 0);
}

const char *strSliceBytes(const char *s, int64_t start, int64_t end) {
    if (!s) s = "";
    size_t len = strlen(s);
    if (start < 0) start = 0;
    if (end < start) end = start;
    if ((size_t)start > len) start = (int64_t)len;
    if ((size_t)end > len) end = (int64_t)len;
    return ez_strdup_range(s + start, (size_t)(end - start));
}

const char *strSliceChars(const char *s, int64_t start, int64_t end) {
    if (!s) s = "";
    size_t len = strlen(s);
    if (start < 0) start = 0;
    if (end < start) end = start;
    size_t byte_start = ez_utf8_byte_offset(s, len, start);
    size_t byte_end = ez_utf8_byte_offset(s, len, end);
    return ez_strdup_range(s + byte_start, byte_end - byte_start);
}

OptStr strCharAt(const char *s, int64_t index) {
    if (!s || index < 0) return (OptStr){false, NULL};
    size_t len = strlen(s);
    size_t start = ez_utf8_byte_offset(s, len, index);
    if (start >= len) return (OptStr){false, NULL};
    size_t end = ez_utf8_byte_offset(s, len, index + 1);
    return (OptStr){true, ez_strdup_range(s + start, end - start)};
}

Blob strToBytes(const char *s) {
    if (!s) return (Blob){NULL, 0};
    size_t len = strlen(s);
    uint8_t *data = len == 0 ? NULL : (uint8_t *)malloc(len);
    if (len > 0 && !data) return (Blob){NULL, 0};
    if (len > 0) memcpy(data, s, len);
    return (Blob){data, (int64_t)len};
}

OptStr strFromBytes(const Blob *data) {
    if (!data || data->size < 0 || (data->size > 0 && !data->data)) return (OptStr){false, NULL};
    if (!ez_utf8_validate_len((const char *)data->data, (size_t)data->size)) return (OptStr){false, NULL};
    return (OptStr){true, ez_strdup_range((const char *)data->data, (size_t)data->size)};
}

bool strContains(const char *s, const char *needle) {
    if (!s) s = "";
    if (!needle) needle = "";
    return strstr(s, needle) != NULL;
}

bool strStartsWith(const char *s, const char *prefix) {
    if (!s) s = "";
    if (!prefix) prefix = "";
    size_t len = strlen(prefix);
    return strncmp(s, prefix, len) == 0;
}

bool strEndsWith(const char *s, const char *suffix) {
    if (!s) s = "";
    if (!suffix) suffix = "";
    size_t s_len = strlen(s);
    size_t suffix_len = strlen(suffix);
    return suffix_len <= s_len && memcmp(s + s_len - suffix_len, suffix, suffix_len) == 0;
}

int64_t strIndexOf(const char *s, const char *needle) {
    if (!s) s = "";
    if (!needle) needle = "";
    char *found = strstr((char *)s, needle);
    return found ? (int64_t)(found - s) : -1;
}

StrList strSplit(const char *s, const char *sep) {
    if (!s) s = "";
    if (!sep || sep[0] == '\0') {
        size_t len = strlen(s);
        size_t count = (size_t)strCharLen(s);
        char **items = count == 0 ? NULL : (char **)calloc(count, sizeof(char *));
        if (count > 0 && !items) return (StrList){0};
        size_t i = 0;
        size_t item = 0;
        while (i < len && item < count) {
            int width = ez_utf8_char_width((unsigned char)s[i]);
            if (width < 0 || i + (size_t)width > len) width = 1;
            items[item++] = ez_strdup_range(s + i, (size_t)width);
            i += (size_t)width;
        }
        StrList result = ez_make_str_list(items, count);
        free(items);
        return result;
    }

    size_t sep_len = strlen(sep);
    size_t count = 1;
    const char *p = s;
    while ((p = strstr(p, sep)) != NULL) {
        count++;
        p += sep_len;
    }
    char **items = (char **)calloc(count, sizeof(char *));
    if (!items) return (StrList){0};
    size_t item = 0;
    const char *start = s;
    while ((p = strstr(start, sep)) != NULL) {
        items[item++] = ez_strdup_range(start, (size_t)(p - start));
        start = p + sep_len;
    }
    items[item++] = ez_strdup_safe(start);
    StrList result = ez_make_str_list(items, item);
    free(items);
    return result;
}

const char *strJoin(const StrList *parts, const char *sep) {
    if (!sep) sep = "";
    size_t sep_len = strlen(sep);
    size_t len = 1;
    for (int64_t i = 0; parts && i < parts->length; ++i) {
        len += strlen(ez_list_get(parts, i));
        if (i > 0) len += sep_len;
    }
    char *out = (char *)malloc(len);
    if (!out) return NULL;
    out[0] = '\0';
    size_t offset = 0;
    for (int64_t i = 0; parts && i < parts->length; ++i) {
        if (i > 0 && sep_len > 0) {
            memcpy(out + offset, sep, sep_len);
            offset += sep_len;
        }
        const char *part = ez_list_get(parts, i);
        size_t part_len = strlen(part);
        memcpy(out + offset, part, part_len);
        offset += part_len;
    }
    out[offset] = '\0';
    return out;
}

const char *strTrim(const char *s) {
    if (!s) s = "";
    const char *start = s;
    while (*start && isspace((unsigned char)*start)) start++;
    const char *end = s + strlen(s);
    while (end > start && isspace((unsigned char)*(end - 1))) end--;
    return ez_strdup_range(start, (size_t)(end - start));
}

const char *strReplace(const char *s, const char *old, const char *new_value) {
    if (!s) s = "";
    if (!old || old[0] == '\0') return ez_strdup_safe(s);
    if (!new_value) new_value = "";
    size_t old_len = strlen(old);
    size_t new_len = strlen(new_value);
    size_t count = 0;
    const char *p = s;
    while ((p = strstr(p, old)) != NULL) {
        count++;
        p += old_len;
    }
    size_t source_len = strlen(s);
    size_t out_len = new_len >= old_len
        ? source_len + count * (new_len - old_len)
        : source_len - count * (old_len - new_len);
    char *out = (char *)malloc(out_len + 1);
    if (!out) return NULL;
    size_t offset = 0;
    const char *start = s;
    while ((p = strstr(start, old)) != NULL) {
        size_t chunk = (size_t)(p - start);
        memcpy(out + offset, start, chunk);
        offset += chunk;
        memcpy(out + offset, new_value, new_len);
        offset += new_len;
        start = p + old_len;
    }
    strcpy(out + offset, start);
    return out;
}

const char *strToLower(const char *s) {
    char *out = ez_strdup_safe(s);
    if (!out) return NULL;
    for (char *p = out; *p; ++p) *p = (char)tolower((unsigned char)*p);
    return out;
}

const char *strToUpper(const char *s) {
    char *out = ez_strdup_safe(s);
    if (!out) return NULL;
    for (char *p = out; *p; ++p) *p = (char)toupper((unsigned char)*p);
    return out;
}
