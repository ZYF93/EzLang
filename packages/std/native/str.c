// EzLang std/str 原生封装层

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

static bool ez_utf8_decode_at(const char *s, size_t len, size_t index, uint32_t *out, size_t *width_out) {
    if (!s || index >= len || !out || !width_out) return false;
    unsigned char ch = (unsigned char)s[index];
    int width = ez_utf8_char_width(ch);
    if (width < 0 || index + (size_t)width > len) return false;
    uint32_t cp = 0;
    if (width == 1) {
        cp = ch;
    } else if (width == 2) {
        unsigned char b1 = (unsigned char)s[index + 1];
        if ((b1 & 0xC0) != 0x80) return false;
        cp = ((uint32_t)(ch & 0x1F) << 6) | (uint32_t)(b1 & 0x3F);
    } else if (width == 3) {
        unsigned char b1 = (unsigned char)s[index + 1];
        unsigned char b2 = (unsigned char)s[index + 2];
        if ((b1 & 0xC0) != 0x80 || (b2 & 0xC0) != 0x80) return false;
        if (ch == 0xE0 && b1 < 0xA0) return false;
        if (ch == 0xED && b1 >= 0xA0) return false;
        cp = ((uint32_t)(ch & 0x0F) << 12) | ((uint32_t)(b1 & 0x3F) << 6) | (uint32_t)(b2 & 0x3F);
    } else {
        unsigned char b1 = (unsigned char)s[index + 1];
        unsigned char b2 = (unsigned char)s[index + 2];
        unsigned char b3 = (unsigned char)s[index + 3];
        if ((b1 & 0xC0) != 0x80 || (b2 & 0xC0) != 0x80 || (b3 & 0xC0) != 0x80) return false;
        if (ch == 0xF0 && b1 < 0x90) return false;
        if (ch == 0xF4 && b1 > 0x8F) return false;
        cp = ((uint32_t)(ch & 0x07) << 18) | ((uint32_t)(b1 & 0x3F) << 12)
            | ((uint32_t)(b2 & 0x3F) << 6) | (uint32_t)(b3 & 0x3F);
    }
    *out = cp;
    *width_out = (size_t)width;
    return true;
}

static bool ez_str_reserve(char **out, size_t *capacity, size_t needed) {
    if (!out || !capacity) return false;
    if (needed < *capacity) return true;
    size_t next = *capacity ? *capacity : 32;
    while (next <= needed) {
        if (next > ((size_t)-1) / 2) return false;
        next *= 2;
    }
    char *grown = (char *)realloc(*out, next);
    if (!grown) return false;
    *out = grown;
    *capacity = next;
    return true;
}

static bool ez_str_append_bytes(char **out, size_t *used, size_t *capacity, const char *src, size_t len) {
    if (!out || !used || !capacity || (!src && len > 0)) return false;
    if (len > ((size_t)-1) - *used - 1) return false;
    if (!ez_str_reserve(out, capacity, *used + len + 1)) return false;
    if (len > 0) memcpy(*out + *used, src, len);
    *used += len;
    (*out)[*used] = '\0';
    return true;
}

static bool ez_str_append_codepoint(char **out, size_t *used, size_t *capacity, uint32_t cp) {
    char buf[4];
    size_t len = 0;
    if (cp <= 0x7F) {
        buf[len++] = (char)cp;
    } else if (cp <= 0x7FF) {
        buf[len++] = (char)(0xC0 | (cp >> 6));
        buf[len++] = (char)(0x80 | (cp & 0x3F));
    } else if (cp <= 0xFFFF) {
        buf[len++] = (char)(0xE0 | (cp >> 12));
        buf[len++] = (char)(0x80 | ((cp >> 6) & 0x3F));
        buf[len++] = (char)(0x80 | (cp & 0x3F));
    } else if (cp <= 0x10FFFF) {
        buf[len++] = (char)(0xF0 | (cp >> 18));
        buf[len++] = (char)(0x80 | ((cp >> 12) & 0x3F));
        buf[len++] = (char)(0x80 | ((cp >> 6) & 0x3F));
        buf[len++] = (char)(0x80 | (cp & 0x3F));
    } else {
        return false;
    }
    return ez_str_append_bytes(out, used, capacity, buf, len);
}

typedef struct {
    uint32_t upper;
    uint32_t lower;
} EzCasePair;

static const EzCasePair EZ_LATIN_EXT_A_CASE_PAIRS[] = {
    {0x0100, 0x0101}, {0x0102, 0x0103}, {0x0104, 0x0105}, {0x0106, 0x0107},
    {0x0108, 0x0109}, {0x010A, 0x010B}, {0x010C, 0x010D}, {0x010E, 0x010F},
    {0x0110, 0x0111}, {0x0112, 0x0113}, {0x0114, 0x0115}, {0x0116, 0x0117},
    {0x0118, 0x0119}, {0x011A, 0x011B}, {0x011C, 0x011D}, {0x011E, 0x011F},
    {0x0120, 0x0121}, {0x0122, 0x0123}, {0x0124, 0x0125}, {0x0126, 0x0127},
    {0x0128, 0x0129}, {0x012A, 0x012B}, {0x012C, 0x012D}, {0x012E, 0x012F},
    {0x0132, 0x0133}, {0x0134, 0x0135}, {0x0136, 0x0137}, {0x0139, 0x013A},
    {0x013B, 0x013C}, {0x013D, 0x013E}, {0x013F, 0x0140}, {0x0141, 0x0142},
    {0x0143, 0x0144}, {0x0145, 0x0146}, {0x0147, 0x0148}, {0x014A, 0x014B},
    {0x014C, 0x014D}, {0x014E, 0x014F}, {0x0150, 0x0151}, {0x0152, 0x0153},
    {0x0154, 0x0155}, {0x0156, 0x0157}, {0x0158, 0x0159}, {0x015A, 0x015B},
    {0x015C, 0x015D}, {0x015E, 0x015F}, {0x0160, 0x0161}, {0x0162, 0x0163},
    {0x0164, 0x0165}, {0x0166, 0x0167}, {0x0168, 0x0169}, {0x016A, 0x016B},
    {0x016C, 0x016D}, {0x016E, 0x016F}, {0x0170, 0x0171}, {0x0172, 0x0173},
    {0x0174, 0x0175}, {0x0176, 0x0177}, {0x0178, 0x00FF}, {0x0179, 0x017A},
    {0x017B, 0x017C}, {0x017D, 0x017E}, {0x1E9E, 0x00DF},
};

static uint32_t ez_unicode_to_lower(uint32_t cp) {
    if (cp >= 'A' && cp <= 'Z') return cp + 0x20;
    if ((cp >= 0x00C0 && cp <= 0x00D6) || (cp >= 0x00D8 && cp <= 0x00DE)) return cp + 0x20;
    if (cp >= 0x0391 && cp <= 0x03A1) return cp + 0x20;
    if (cp >= 0x03A3 && cp <= 0x03AB) return cp + 0x20;
    if (cp >= 0x0400 && cp <= 0x040F) return cp + 0x50;
    if (cp >= 0x0410 && cp <= 0x042F) return cp + 0x20;
    for (size_t i = 0; i < sizeof(EZ_LATIN_EXT_A_CASE_PAIRS) / sizeof(EZ_LATIN_EXT_A_CASE_PAIRS[0]); ++i) {
        if (cp == EZ_LATIN_EXT_A_CASE_PAIRS[i].upper) return EZ_LATIN_EXT_A_CASE_PAIRS[i].lower;
    }
    return cp;
}

static uint32_t ez_unicode_to_upper(uint32_t cp) {
    if (cp >= 'a' && cp <= 'z') return cp - 0x20;
    if ((cp >= 0x00E0 && cp <= 0x00F6) || (cp >= 0x00F8 && cp <= 0x00FE)) return cp - 0x20;
    if (cp == 0x00FF) return 0x0178;
    if (cp >= 0x03B1 && cp <= 0x03C1) return cp - 0x20;
    if (cp == 0x03C2) return 0x03A3;
    if (cp >= 0x03C3 && cp <= 0x03CB) return cp - 0x20;
    if (cp >= 0x0450 && cp <= 0x045F) return cp - 0x50;
    if (cp >= 0x0430 && cp <= 0x044F) return cp - 0x20;
    for (size_t i = 0; i < sizeof(EZ_LATIN_EXT_A_CASE_PAIRS) / sizeof(EZ_LATIN_EXT_A_CASE_PAIRS[0]); ++i) {
        if (cp == EZ_LATIN_EXT_A_CASE_PAIRS[i].lower) return EZ_LATIN_EXT_A_CASE_PAIRS[i].upper;
    }
    return cp;
}

static const char *ez_unicode_case_convert(const char *s, bool upper) {
    if (!s) s = "";
    size_t len = strlen(s);
    char *out = NULL;
    size_t used = 0;
    size_t capacity = 0;
    size_t i = 0;
    while (i < len) {
        uint32_t cp = 0;
        size_t width = 0;
        if (!ez_utf8_decode_at(s, len, i, &cp, &width)) {
            if (!ez_str_append_bytes(&out, &used, &capacity, s + i, 1)) {
                free(out);
                return NULL;
            }
            i++;
            continue;
        }
        cp = upper ? ez_unicode_to_upper(cp) : ez_unicode_to_lower(cp);
        if (!ez_str_append_codepoint(&out, &used, &capacity, cp)) {
            free(out);
            return NULL;
        }
        i += width;
    }
    if (!out && !ez_str_append_bytes(&out, &used, &capacity, "", 0)) return NULL;
    return out;
}

static bool ez_unicode_is_space(uint32_t cp) {
    return cp == 0x0009 || cp == 0x000A || cp == 0x000B || cp == 0x000C || cp == 0x000D
        || cp == 0x0020 || cp == 0x0085 || cp == 0x00A0 || cp == 0x1680
        || (cp >= 0x2000 && cp <= 0x200A) || cp == 0x2028 || cp == 0x2029
        || cp == 0x202F || cp == 0x205F || cp == 0x3000;
}

static size_t ez_utf8_prev_offset(const char *s, size_t len, size_t end) {
    if (!s || end == 0 || end > len) return 0;
    size_t start = end - 1;
    while (start > 0 && ((unsigned char)s[start] & 0xC0) == 0x80) start--;
    uint32_t cp = 0;
    size_t width = 0;
    if (!ez_utf8_decode_at(s, len, start, &cp, &width) || start + width != end) return end - 1;
    return start;
}

static bool ez_utf8_scalar_at_span(const char *s, size_t len, size_t start, size_t end, uint32_t *out) {
    size_t width = 0;
    return ez_utf8_decode_at(s, len, start, out, &width) && start + width == end;
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
    if (data->size > 0 && memchr(data->data, 0, (size_t)data->size)) return (OptStr){false, NULL};
    if (!ez_utf8_validate_len((const char *)data->data, (size_t)data->size)) return (OptStr){false, NULL};
    return (OptStr){true, ez_strdup_range((const char *)data->data, (size_t)data->size)};
}

bool strEqual(const char *a, const char *b) {
    if (!a) a = "";
    if (!b) b = "";
    return strcmp(a, b) == 0;
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
    size_t len = strlen(s);
    size_t start = 0;
    while (start < len) {
        uint32_t cp = 0;
        size_t width = 0;
        if (!ez_utf8_decode_at(s, len, start, &cp, &width) || !ez_unicode_is_space(cp)) break;
        start += width;
    }
    size_t end = len;
    while (end > start) {
        size_t prev = ez_utf8_prev_offset(s, len, end);
        uint32_t cp = 0;
        if (!ez_utf8_scalar_at_span(s, len, prev, end, &cp) || !ez_unicode_is_space(cp)) break;
        end = prev;
    }
    return ez_strdup_range(s + start, end - start);
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
    return ez_unicode_case_convert(s, false);
}

const char *strToUpper(const char *s) {
    return ez_unicode_case_convert(s, true);
}
