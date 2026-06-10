// EzLang std/fmt 原生封装层

#include <ctype.h>
#include <errno.h>
#include <float.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
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

typedef struct { bool ok; int32_t value; } OptI32;
typedef struct { bool ok; int64_t value; } OptI64;
typedef struct { bool ok; double value; } OptF64;
typedef struct { bool ok; Blob value; } OptBlob;
typedef struct { bool ok; const char *value; } OptStr;

static int ez_hex_value(char ch);

static char *ez_strdup_range(const char *src, size_t len) {
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    if (len > 0) memcpy(out, src, len);
    out[len] = '\0';
    return out;
}

static char *ez_strdup_safe(const char *src) {
    if (!src) src = "";
    return ez_strdup_range(src, strlen(src));
}

static const char *ez_list_get(const StrList *args, int64_t index) {
    if (!args || index < 0 || index >= args->length || args->page_count <= 0 || !args->pages) return "";
    int64_t page = index / 8;
    int64_t offset = index % 8;
    if (page >= args->page_count || !args->pages[page]) return "";
    return args->pages[page][offset] ? args->pages[page][offset] : "";
}

const char *toString_I32(int32_t value) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%d", value);
    return ez_strdup_safe(buffer);
}

const char *toString_I8(int8_t value) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%d", (int)value);
    return ez_strdup_safe(buffer);
}

const char *toString_I64(int64_t value) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%lld", (long long)value);
    return ez_strdup_safe(buffer);
}

const char *toString_U8(uint8_t value) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%u", (unsigned)value);
    return ez_strdup_safe(buffer);
}

const char *toString_U32(uint32_t value) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%u", value);
    return ez_strdup_safe(buffer);
}

const char *toString_U64(uint64_t value) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%llu", (unsigned long long)value);
    return ez_strdup_safe(buffer);
}

const char *toString_F32(float value) {
    char buffer[64];
    snprintf(buffer, sizeof(buffer), "%.9g", value);
    return ez_strdup_safe(buffer);
}

const char *toString_F64(double value) {
    char buffer[64];
    snprintf(buffer, sizeof(buffer), "%.17g", value);
    return ez_strdup_safe(buffer);
}

const char *toString_I1(bool value) {
    return ez_strdup_safe(value ? "true" : "false");
}

const char *toString_Str(const char *value) {
    return ez_strdup_safe(value);
}

static bool ez_parse_is_digit(char ch) {
    return ch >= '0' && ch <= '9';
}

static int ez_parse_utf8_width(unsigned char ch) {
    if (ch < 0x80) return 1;
    if (ch >= 0xC2 && ch <= 0xDF) return 2;
    if (ch >= 0xE0 && ch <= 0xEF) return 3;
    if (ch >= 0xF0 && ch <= 0xF4) return 4;
    return -1;
}

static bool ez_parse_utf8_decode_at(const char *s, size_t len, size_t index, uint32_t *out, size_t *width_out) {
    if (!s || index >= len || !out || !width_out) return false;
    unsigned char ch = (unsigned char)s[index];
    int width = ez_parse_utf8_width(ch);
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

static bool ez_parse_unicode_is_space(uint32_t cp) {
    return cp == 0x0009 || cp == 0x000A || cp == 0x000B || cp == 0x000C || cp == 0x000D ||
           cp == 0x0020 || cp == 0x0085 || cp == 0x00A0 || cp == 0x1680 ||
           (cp >= 0x2000 && cp <= 0x200A) || cp == 0x2028 || cp == 0x2029 ||
           cp == 0x202F || cp == 0x205F || cp == 0x3000;
}

static size_t ez_parse_utf8_prev_offset(const char *s, size_t len, size_t end) {
    if (!s || end == 0 || end > len) return 0;
    size_t start = end - 1;
    while (start > 0 && ((unsigned char)s[start] & 0xC0) == 0x80) start--;
    uint32_t cp = 0;
    size_t width = 0;
    if (!ez_parse_utf8_decode_at(s, len, start, &cp, &width) || start + width != end) return end - 1;
    return start;
}

static bool ez_parse_trim_span(const char *s, const char **start, size_t *len) {
    if (!s || !start || !len) return false;
    size_t total = strlen(s);
    size_t begin = 0;
    while (begin < total) {
        uint32_t cp = 0;
        size_t width = 0;
        if (!ez_parse_utf8_decode_at(s, total, begin, &cp, &width) || !ez_parse_unicode_is_space(cp)) break;
        begin += width;
    }
    size_t end = total;
    while (end > begin) {
        size_t prev = ez_parse_utf8_prev_offset(s, total, end);
        uint32_t cp = 0;
        size_t width = 0;
        if (!ez_parse_utf8_decode_at(s, total, prev, &cp, &width) || prev + width != end || !ez_parse_unicode_is_space(cp)) break;
        end = prev;
    }
    *start = s + begin;
    *len = end - begin;
    return true;
}

static bool ez_parse_decimal_i64_span(const char *s, size_t len, int64_t *out) {
    if (!s || len == 0 || !out) return false;
    size_t i = 0;
    bool negative = false;
    if (s[i] == '+' || s[i] == '-') {
        negative = s[i] == '-';
        i++;
        if (i == len) return false;
    }
    uint64_t limit = negative ? (uint64_t)INT64_MAX + UINT64_C(1) : (uint64_t)INT64_MAX;
    uint64_t magnitude = 0;
    for (; i < len; ++i) {
        if (!ez_parse_is_digit(s[i])) return false;
        uint64_t digit = (uint64_t)(s[i] - '0');
        if (magnitude > (limit - digit) / 10u) return false;
        magnitude = magnitude * 10u + digit;
    }
    if (negative) {
        *out = magnitude == (uint64_t)INT64_MAX + UINT64_C(1) ? INT64_MIN : -(int64_t)magnitude;
    } else {
        *out = (int64_t)magnitude;
    }
    return true;
}

OptI32 parseInt(const char *s) {
    if (!s) return (OptI32){false, 0};
    const char *text = NULL;
    size_t len = 0;
    int64_t value = 0;
    if (!ez_parse_trim_span(s, &text, &len) || !ez_parse_decimal_i64_span(text, len, &value)) return (OptI32){false, 0};
    if (value < INT32_MIN || value > INT32_MAX) return (OptI32){false, 0};
    return (OptI32){true, (int32_t)value};
}

OptI64 parseI64(const char *s) {
    if (!s) return (OptI64){false, 0};
    const char *text = NULL;
    size_t len = 0;
    int64_t value = 0;
    if (!ez_parse_trim_span(s, &text, &len) || !ez_parse_decimal_i64_span(text, len, &value)) return (OptI64){false, 0};
    return (OptI64){true, (int64_t)value};
}

static bool ez_parse_f64_number_span(const char *s, size_t len) {
    if (!s || len == 0) return false;
    size_t i = 0;
    if (s[i] == '+' || s[i] == '-') {
        i++;
        if (i == len) return false;
    }
    bool has_digit = false;
    while (i < len && ez_parse_is_digit(s[i])) {
        has_digit = true;
        i++;
    }
    if (i < len && s[i] == '.') {
        i++;
        while (i < len && ez_parse_is_digit(s[i])) {
            has_digit = true;
            i++;
        }
    }
    if (!has_digit) return false;
    if (i < len && (s[i] == 'e' || s[i] == 'E')) {
        i++;
        if (i < len && (s[i] == '+' || s[i] == '-')) i++;
        if (i == len || !ez_parse_is_digit(s[i])) return false;
        while (i < len && ez_parse_is_digit(s[i])) i++;
    }
    return i == len;
}

OptF64 parseF64(const char *s) {
    if (!s) return (OptF64){false, 0.0};
    const char *start = NULL;
    size_t len = 0;
    if (!ez_parse_trim_span(s, &start, &len)) return (OptF64){false, 0.0};
    if (!ez_parse_f64_number_span(start, len)) return (OptF64){false, 0.0};

    char *copy = ez_strdup_range(start, len);
    if (!copy) return (OptF64){false, 0.0};
    errno = 0;
    char *end = NULL;
    double value = strtod(copy, &end);
    bool ok = end && *end == '\0' && isfinite(value);
    free(copy);
    return ok ? (OptF64){true, value} : (OptF64){false, 0.0};
}

const char *format(const char *template, const StrList *args) {
    if (!template) return ez_strdup_safe("");
    size_t cap = strlen(template) + 32;
    char *out = (char *)malloc(cap);
    if (!out) return NULL;
    size_t len = 0;
    int64_t arg_index = 0;

    for (const char *p = template; *p; ++p) {
        const char *piece = NULL;
        char literal[2] = {*p, '\0'};
        char fallback[3] = {'\0', '\0', '\0'};
        if (*p == '{' && p[1] == '}') {
            piece = ez_list_get(args, arg_index++);
            ++p;
        } else if (*p == '{' && p[1] == '{') {
            piece = "{";
            ++p;
        } else if (*p == '}' && p[1] == '}') {
            piece = "}";
            ++p;
        } else if (*p == '%' && p[1] != '\0') {
            char spec = *++p;
            if (spec == '%') {
                piece = "%";
            } else if (spec == 's' || spec == 'd' || spec == 'f') {
                piece = ez_list_get(args, arg_index++);
            } else {
                fallback[0] = '%';
                fallback[1] = spec;
                piece = fallback;
            }
        } else {
            piece = literal;
        }

        size_t piece_len = strlen(piece);
        if (len + piece_len + 1 > cap) {
            while (len + piece_len + 1 > cap) cap *= 2;
            char *next = (char *)realloc(out, cap);
            if (!next) {
                free(out);
                return NULL;
            }
            out = next;
        }
        memcpy(out + len, piece, piece_len);
        len += piece_len;
        out[len] = '\0';
    }
    return out;
}

static const char EZ_B64[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

const char *b64Encode(const Blob *data) {
    if (!data || data->size < 0 || (data->size > 0 && !data->data)) return ez_strdup_safe("");
    size_t len = (size_t)data->size;
    if (len > (((size_t)-1) / 4) * 3 - 2) return ez_strdup_safe("");
    size_t out_len = ((len + 2) / 3) * 4;
    char *out = (char *)malloc(out_len + 1);
    if (!out) return ez_strdup_safe("");

    size_t i = 0;
    size_t j = 0;
    while (i < len) {
        uint32_t a = i < len ? data->data[i++] : 0;
        uint32_t b = i < len ? data->data[i++] : 0;
        uint32_t c = i < len ? data->data[i++] : 0;
        uint32_t triple = (a << 16) | (b << 8) | c;
        out[j++] = EZ_B64[(triple >> 18) & 0x3F];
        out[j++] = EZ_B64[(triple >> 12) & 0x3F];
        out[j++] = EZ_B64[(triple >> 6) & 0x3F];
        out[j++] = EZ_B64[triple & 0x3F];
    }
    size_t padding = (3 - (len % 3)) % 3;
    for (size_t k = 0; k < padding; ++k) out[out_len - 1 - k] = '=';
    out[out_len] = '\0';
    return out;
}

static int ez_b64_value(char ch) {
    if (ch >= 'A' && ch <= 'Z') return ch - 'A';
    if (ch >= 'a' && ch <= 'z') return ch - 'a' + 26;
    if (ch >= '0' && ch <= '9') return ch - '0' + 52;
    if (ch == '+') return 62;
    if (ch == '/') return 63;
    return -1;
}

static bool ez_b64_is_valid_input(const char *s, size_t len, size_t *padding) {
    if (len % 4 != 0) return false;
    *padding = 0;
    if (len > 0 && s[len - 1] == '=') (*padding)++;
    if (len > 1 && s[len - 2] == '=') (*padding)++;
    if (*padding > 2) return false;
    for (size_t i = 0; i < len; ++i) {
        bool is_padding = s[i] == '=';
        if (is_padding) {
            if (i < len - *padding) return false;
        } else if (ez_b64_value(s[i]) < 0) {
            return false;
        }
    }
    return true;
}

OptBlob b64Decode(const char *s) {
    if (!s) return (OptBlob){false, {0}};
    size_t in_len = strlen(s);
    size_t padding = 0;
    if (!ez_b64_is_valid_input(s, in_len, &padding)) return (OptBlob){false, {0}};
    size_t out_len = (in_len / 4) * 3 - padding;
    uint8_t *out = (uint8_t *)malloc(out_len ? out_len : 1);
    if (!out) return (OptBlob){false, {0}};

    size_t j = 0;
    for (size_t i = 0; i < in_len; i += 4) {
        int vals[4];
        for (int k = 0; k < 4; ++k) {
            vals[k] = s[i + k] == '=' ? 0 : ez_b64_value(s[i + k]);
            if (vals[k] < 0) {
                free(out);
                return (OptBlob){false, {0}};
            }
        }
        uint32_t triple = ((uint32_t)vals[0] << 18) | ((uint32_t)vals[1] << 12) | ((uint32_t)vals[2] << 6) | (uint32_t)vals[3];
        if (j < out_len) out[j++] = (uint8_t)((triple >> 16) & 0xFF);
        if (j < out_len) out[j++] = (uint8_t)((triple >> 8) & 0xFF);
        if (j < out_len) out[j++] = (uint8_t)(triple & 0xFF);
    }
    return (OptBlob){true, {out, (int64_t)out_len}};
}

const char *jsonStringify_I32(int32_t value) { return toString_I32(value); }
const char *jsonStringify_I8(int8_t value) { return toString_I8(value); }
const char *jsonStringify_I64(int64_t value) { return toString_I64(value); }
const char *jsonStringify_U8(uint8_t value) { return toString_U8(value); }
const char *jsonStringify_U32(uint32_t value) { return toString_U32(value); }
const char *jsonStringify_U64(uint64_t value) { return toString_U64(value); }
const char *jsonStringify_F32(float value) {
    return isfinite(value) ? toString_F32(value) : ez_strdup_safe("null");
}
const char *jsonStringify_F64(double value) {
    return isfinite(value) ? toString_F64(value) : ez_strdup_safe("null");
}
const char *jsonStringify_I1(bool value) { return toString_I1(value); }

const char *jsonStringify_Str(const char *value) {
    if (!value) value = "";
    size_t cap = strlen(value) * 6 + 3;
    char *out = (char *)malloc(cap);
    if (!out) return NULL;
    size_t len = 0;
    out[len++] = '"';
    static const char hex[] = "0123456789ABCDEF";
    for (const unsigned char *p = (const unsigned char *)value; *p; ++p) {
        if (*p == '"' || *p == '\\') {
            out[len++] = '\\';
            out[len++] = (char)*p;
        } else if (*p == '\b') {
            out[len++] = '\\';
            out[len++] = 'b';
        } else if (*p == '\f') {
            out[len++] = '\\';
            out[len++] = 'f';
        } else if (*p == '\n') {
            out[len++] = '\\';
            out[len++] = 'n';
        } else if (*p == '\r') {
            out[len++] = '\\';
            out[len++] = 'r';
        } else if (*p == '\t') {
            out[len++] = '\\';
            out[len++] = 't';
        } else if (*p < 0x20) {
            out[len++] = '\\';
            out[len++] = 'u';
            out[len++] = '0';
            out[len++] = '0';
            out[len++] = hex[*p >> 4];
            out[len++] = hex[*p & 0xF];
        } else {
            out[len++] = (char)*p;
        }
    }
    out[len++] = '"';
    out[len] = '\0';
    return out;
}

static bool ez_json_hex4(const char *s, uint32_t *value) {
    uint32_t out = 0;
    for (int i = 0; i < 4; ++i) {
        int digit = ez_hex_value(s[i]);
        if (digit < 0) return false;
        out = (out << 4) | (uint32_t)digit;
    }
    *value = out;
    return true;
}

static bool ez_json_append_utf8(char *out, size_t *j, uint32_t cp) {
    if (cp <= 0x7F) {
        out[(*j)++] = (char)cp;
    } else if (cp <= 0x7FF) {
        out[(*j)++] = (char)(0xC0 | (cp >> 6));
        out[(*j)++] = (char)(0x80 | (cp & 0x3F));
    } else if (cp >= 0xD800 && cp <= 0xDFFF) {
        return false;
    } else if (cp <= 0xFFFF) {
        out[(*j)++] = (char)(0xE0 | (cp >> 12));
        out[(*j)++] = (char)(0x80 | ((cp >> 6) & 0x3F));
        out[(*j)++] = (char)(0x80 | (cp & 0x3F));
    } else if (cp <= 0x10FFFF) {
        out[(*j)++] = (char)(0xF0 | (cp >> 18));
        out[(*j)++] = (char)(0x80 | ((cp >> 12) & 0x3F));
        out[(*j)++] = (char)(0x80 | ((cp >> 6) & 0x3F));
        out[(*j)++] = (char)(0x80 | (cp & 0x3F));
    } else {
        return false;
    }
    return true;
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

static bool ez_contains_nul_byte(const void *data, size_t len) {
    return len > 0 && memchr(data, 0, len) != NULL;
}

static bool ez_json_trim_span(const char *s, const char **start, size_t *len) {
    if (!s || !start || !len) return false;
    const char *begin = s;
    while (*begin && isspace((unsigned char)*begin)) begin++;
    const char *end = begin + strlen(begin);
    while (end > begin && isspace((unsigned char)end[-1])) end--;
    *start = begin;
    *len = (size_t)(end - begin);
    return true;
}

static bool ez_json_is_digit(char ch) {
    return ch >= '0' && ch <= '9';
}

static bool ez_json_number_span(const char *s, size_t len, bool allow_fraction_exp) {
    if (!s || len == 0) return false;
    size_t i = 0;
    if (s[i] == '-') {
        i++;
        if (i == len) return false;
    }
    if (s[i] == '0') {
        i++;
    } else if (s[i] >= '1' && s[i] <= '9') {
        do {
            i++;
        } while (i < len && ez_json_is_digit(s[i]));
    } else {
        return false;
    }
    if (i < len && s[i] == '.') {
        if (!allow_fraction_exp) return false;
        i++;
        if (i == len || !ez_json_is_digit(s[i])) return false;
        while (i < len && ez_json_is_digit(s[i])) i++;
    }
    if (i < len && (s[i] == 'e' || s[i] == 'E')) {
        if (!allow_fraction_exp) return false;
        i++;
        if (i < len && (s[i] == '+' || s[i] == '-')) i++;
        if (i == len || !ez_json_is_digit(s[i])) return false;
        while (i < len && ez_json_is_digit(s[i])) i++;
    }
    return i == len;
}

static bool ez_json_parse_integer_value(const char *s, size_t len, int64_t *out) {
    if (!ez_json_number_span(s, len, true) || !out) return false;
    char *digits = (char *)malloc(len + 1);
    if (!digits) return false;

    size_t i = 0;
    bool negative = false;
    if (s[i] == '-') {
        negative = true;
        i++;
    }

    size_t digit_len = 0;
    do {
        digits[digit_len++] = s[i++];
    } while (i < len && ez_json_is_digit(s[i]));

    int64_t frac_len = 0;
    if (i < len && s[i] == '.') {
        i++;
        while (i < len && ez_json_is_digit(s[i])) {
            digits[digit_len++] = s[i++];
            frac_len++;
        }
    }

    int64_t exponent = 0;
    if (i < len && (s[i] == 'e' || s[i] == 'E')) {
        i++;
        bool exp_negative = false;
        if (i < len && (s[i] == '+' || s[i] == '-')) {
            exp_negative = s[i] == '-';
            i++;
        }
        while (i < len && ez_json_is_digit(s[i])) {
            if (exponent < 1000000) exponent = exponent * 10 + (s[i] - '0');
            i++;
        }
        if (exp_negative) exponent = -exponent;
    }

    size_t first = 0;
    while (first < digit_len && digits[first] == '0') first++;
    if (first == digit_len) {
        free(digits);
        *out = 0;
        return true;
    }

    int64_t scale = exponent - frac_len;
    size_t integer_end = digit_len;
    if (scale < 0) {
        uint64_t trim = (uint64_t)(-scale);
        size_t significant_len = digit_len - first;
        if (trim >= significant_len) {
            free(digits);
            return false;
        }
        for (uint64_t n = 0; n < trim; ++n) {
            if (digits[digit_len - 1 - (size_t)n] != '0') {
                free(digits);
                return false;
            }
        }
        integer_end = digit_len - (size_t)trim;
        scale = 0;
    }

    uint64_t limit = negative ? (uint64_t)INT64_MAX + 1u : (uint64_t)INT64_MAX;
    uint64_t magnitude = 0;
    for (size_t n = first; n < integer_end; ++n) {
        uint64_t digit = (uint64_t)(digits[n] - '0');
        if (magnitude > (limit - digit) / 10u) {
            free(digits);
            return false;
        }
        magnitude = magnitude * 10u + digit;
    }
    for (int64_t n = 0; n < scale; ++n) {
        if (magnitude > limit / 10u) {
            free(digits);
            return false;
        }
        magnitude *= 10u;
    }
    free(digits);

    if (negative) {
        *out = magnitude == (uint64_t)INT64_MAX + 1u ? INT64_MIN : -(int64_t)magnitude;
    } else {
        *out = (int64_t)magnitude;
    }
    return true;
}

static bool ez_json_parse_unsigned_integer_value(const char *s, size_t len, uint64_t *out) {
    if (!ez_json_number_span(s, len, true) || !out || s[0] == '-') return false;
    char *digits = (char *)malloc(len + 1);
    if (!digits) return false;

    size_t i = 0;
    size_t digit_len = 0;
    do {
        digits[digit_len++] = s[i++];
    } while (i < len && ez_json_is_digit(s[i]));

    int64_t frac_len = 0;
    if (i < len && s[i] == '.') {
        i++;
        while (i < len && ez_json_is_digit(s[i])) {
            digits[digit_len++] = s[i++];
            frac_len++;
        }
    }

    int64_t exponent = 0;
    if (i < len && (s[i] == 'e' || s[i] == 'E')) {
        i++;
        bool exp_negative = false;
        if (i < len && (s[i] == '+' || s[i] == '-')) {
            exp_negative = s[i] == '-';
            i++;
        }
        while (i < len && ez_json_is_digit(s[i])) {
            if (exponent < 1000000) exponent = exponent * 10 + (s[i] - '0');
            i++;
        }
        if (exp_negative) exponent = -exponent;
    }

    size_t first = 0;
    while (first < digit_len && digits[first] == '0') first++;
    if (first == digit_len) {
        free(digits);
        *out = 0;
        return true;
    }

    int64_t scale = exponent - frac_len;
    size_t integer_end = digit_len;
    if (scale < 0) {
        uint64_t trim = (uint64_t)(-scale);
        size_t significant_len = digit_len - first;
        if (trim >= significant_len) {
            free(digits);
            return false;
        }
        for (uint64_t n = 0; n < trim; ++n) {
            if (digits[digit_len - 1 - (size_t)n] != '0') {
                free(digits);
                return false;
            }
        }
        integer_end = digit_len - (size_t)trim;
        scale = 0;
    }

    uint64_t magnitude = 0;
    for (size_t n = first; n < integer_end; ++n) {
        uint64_t digit = (uint64_t)(digits[n] - '0');
        if (magnitude > (UINT64_MAX - digit) / 10u) {
            free(digits);
            return false;
        }
        magnitude = magnitude * 10u + digit;
    }
    for (int64_t n = 0; n < scale; ++n) {
        if (magnitude > UINT64_MAX / 10u) {
            free(digits);
            return false;
        }
        magnitude *= 10u;
    }
    free(digits);

    *out = magnitude;
    return true;
}

int32_t jsonParse_I32(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    int64_t value = 0;
    if (!ez_json_trim_span(s, &text, &len) || !ez_json_parse_integer_value(text, len, &value)) return 0;
    if (value < INT32_MIN || value > INT32_MAX) return 0;
    return (int32_t)value;
}

int8_t jsonParse_I8(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    int64_t value = 0;
    if (!ez_json_trim_span(s, &text, &len) || !ez_json_parse_integer_value(text, len, &value)) return 0;
    if (value < INT8_MIN || value > INT8_MAX) return 0;
    return (int8_t)value;
}

int64_t jsonParse_I64(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    int64_t value = 0;
    if (!ez_json_trim_span(s, &text, &len) || !ez_json_parse_integer_value(text, len, &value)) return 0;
    return value;
}

uint32_t jsonParse_U32(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    uint64_t value = 0;
    if (!ez_json_trim_span(s, &text, &len) || !ez_json_parse_unsigned_integer_value(text, len, &value)) return 0;
    if (value > UINT32_MAX) return 0;
    return (uint32_t)value;
}

uint8_t jsonParse_U8(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    uint64_t value = 0;
    if (!ez_json_trim_span(s, &text, &len) || !ez_json_parse_unsigned_integer_value(text, len, &value)) return 0;
    if (value > UINT8_MAX) return 0;
    return (uint8_t)value;
}

uint64_t jsonParse_U64(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    uint64_t value = 0;
    if (!ez_json_trim_span(s, &text, &len) || !ez_json_parse_unsigned_integer_value(text, len, &value)) return 0;
    return value;
}

float jsonParse_F32(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len) || !ez_json_number_span(text, len, true)) return 0.0f;
    char *copy = ez_strdup_range(text, len);
    if (!copy) return 0.0f;
    errno = 0;
    char *end = NULL;
    float value = strtof(copy, &end);
    bool ok = errno == 0 && end && *end == '\0' && isfinite(value);
    free(copy);
    return ok ? value : 0.0f;
}

double jsonParse_F64(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len) || !ez_json_number_span(text, len, true)) return 0.0;
    char *copy = ez_strdup_range(text, len);
    if (!copy) return 0.0;
    errno = 0;
    char *end = NULL;
    double value = strtod(copy, &end);
    bool ok = errno == 0 && end && *end == '\0' && isfinite(value);
    free(copy);
    return ok ? value : 0.0;
}

bool jsonParse_I1(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len)) return false;
    if (len == 4 && memcmp(text, "true", 4) == 0) return true;
    if (len == 5 && memcmp(text, "false", 5) == 0) return false;
    return false;
}

bool __ez_json_valid_I32(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    int64_t value = 0;
    return ez_json_trim_span(s, &text, &len) && ez_json_parse_integer_value(text, len, &value)
        && value >= INT32_MIN && value <= INT32_MAX;
}

bool __ez_json_valid_I8(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    int64_t value = 0;
    return ez_json_trim_span(s, &text, &len) && ez_json_parse_integer_value(text, len, &value)
        && value >= INT8_MIN && value <= INT8_MAX;
}

bool __ez_json_valid_I64(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    int64_t value = 0;
    return ez_json_trim_span(s, &text, &len) && ez_json_parse_integer_value(text, len, &value);
}

bool __ez_json_valid_U32(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    uint64_t value = 0;
    return ez_json_trim_span(s, &text, &len) && ez_json_parse_unsigned_integer_value(text, len, &value)
        && value <= UINT32_MAX;
}

bool __ez_json_valid_U8(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    uint64_t value = 0;
    return ez_json_trim_span(s, &text, &len) && ez_json_parse_unsigned_integer_value(text, len, &value)
        && value <= UINT8_MAX;
}

bool __ez_json_valid_U64(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    uint64_t value = 0;
    return ez_json_trim_span(s, &text, &len) && ez_json_parse_unsigned_integer_value(text, len, &value);
}

bool __ez_json_valid_F32(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len) || !ez_json_number_span(text, len, true)) return false;
    char *copy = ez_strdup_range(text, len);
    if (!copy) return false;
    errno = 0;
    char *end = NULL;
    float value = strtof(copy, &end);
    bool ok = errno == 0 && end && *end == '\0' && isfinite(value);
    free(copy);
    return ok;
}

bool __ez_json_valid_F64(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len) || !ez_json_number_span(text, len, true)) return false;
    char *copy = ez_strdup_range(text, len);
    if (!copy) return false;
    errno = 0;
    char *end = NULL;
    double value = strtod(copy, &end);
    bool ok = errno == 0 && end && *end == '\0' && isfinite(value);
    free(copy);
    return ok;
}

bool __ez_json_valid_Bool(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len)) return false;
    return (len == 4 && memcmp(text, "true", 4) == 0) || (len == 5 && memcmp(text, "false", 5) == 0);
}

static char *ez_json_parse_string_span(const char *text, size_t len, bool *ok) {
    if (ok) *ok = false;
    if (!text || len < 2 || text[0] != '"' || text[len - 1] != '"') return ez_strdup_safe("");
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    size_t j = 0;
    for (size_t i = 1; i + 1 < len; ++i) {
        unsigned char ch = (unsigned char)text[i];
        if (ch < 0x20) {
            free(out);
            return ez_strdup_safe("");
        }
        if (text[i] == '\\') {
            if (++i >= len - 1) {
                free(out);
                return ez_strdup_safe("");
            }
            char esc = text[i];
            if (esc == '"' || esc == '\\' || esc == '/') {
                out[j++] = esc;
            } else if (esc == 'b') {
                out[j++] = '\b';
            } else if (esc == 'f') {
                out[j++] = '\f';
            } else if (esc == 'n') {
                out[j++] = '\n';
            } else if (esc == 'r') {
                out[j++] = '\r';
            } else if (esc == 't') {
                out[j++] = '\t';
            } else if (esc == 'u') {
                if (i + 4 >= len) {
                    free(out);
                    return ez_strdup_safe("");
                }
                uint32_t cp = 0;
                if (!ez_json_hex4(text + i + 1, &cp)) {
                    free(out);
                    return ez_strdup_safe("");
                }
                i += 4;
                if (cp >= 0xD800 && cp <= 0xDBFF) {
                    if (i + 6 >= len || text[i + 1] != '\\' || text[i + 2] != 'u') {
                        free(out);
                        return ez_strdup_safe("");
                    }
                    uint32_t low = 0;
                    if (!ez_json_hex4(text + i + 3, &low) || low < 0xDC00 || low > 0xDFFF) {
                        free(out);
                        return ez_strdup_safe("");
                    }
                    cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00);
                    i += 6;
                }
                if (!ez_json_append_utf8(out, &j, cp)) {
                    free(out);
                    return ez_strdup_safe("");
                }
            } else {
                free(out);
                return ez_strdup_safe("");
            }
        } else {
            out[j++] = text[i];
        }
    }
    out[j] = '\0';
    if (ez_contains_nul_byte(out, j)) {
        free(out);
        return ez_strdup_safe("");
    }
    if (ok) *ok = true;
    return out;
}

static bool ez_json_scan_ws(const char *text, size_t len, size_t *index) {
    if (!text || !index || *index > len) return false;
    while (*index < len && isspace((unsigned char)text[*index])) (*index)++;
    return true;
}

static bool ez_json_scan_string_value(const char *text, size_t len, size_t *index) {
    if (!text || !index || *index >= len || text[*index] != '"') return false;
    size_t i = *index + 1;
    while (i < len) {
        unsigned char ch = (unsigned char)text[i];
        if (ch < 0x20) return false;
        if (text[i] == '"') {
            *index = i + 1;
            return true;
        }
        if (text[i] != '\\') {
            i++;
            continue;
        }
        if (++i >= len) return false;
        char esc = text[i];
        if (esc == '"' || esc == '\\' || esc == '/' || esc == 'b' || esc == 'f' || esc == 'n' || esc == 'r' || esc == 't') {
            i++;
            continue;
        }
        if (esc != 'u' || i + 4 >= len) return false;
        uint32_t cp = 0;
        if (!ez_json_hex4(text + i + 1, &cp)) return false;
        i += 5;
        if (cp >= 0xD800 && cp <= 0xDBFF) {
            if (i + 5 >= len || text[i] != '\\' || text[i + 1] != 'u') return false;
            uint32_t low = 0;
            if (!ez_json_hex4(text + i + 2, &low) || low < 0xDC00 || low > 0xDFFF) return false;
            i += 6;
        } else if (cp >= 0xDC00 && cp <= 0xDFFF) {
            return false;
        }
    }
    return false;
}

static bool ez_json_scan_literal(const char *text, size_t len, size_t *index, const char *literal) {
    size_t literal_len = strlen(literal);
    if (!text || !index || *index > len || literal_len > len - *index) return false;
    if (memcmp(text + *index, literal, literal_len) != 0) return false;
    *index += literal_len;
    return true;
}

static bool ez_json_scan_value(const char *text, size_t len, size_t *index);

static bool ez_json_scan_array_value(const char *text, size_t len, size_t *index) {
    if (!text || !index || *index >= len || text[*index] != '[') return false;
    (*index)++;
    if (!ez_json_scan_ws(text, len, index)) return false;
    if (*index < len && text[*index] == ']') {
        (*index)++;
        return true;
    }
    while (*index < len) {
        if (!ez_json_scan_value(text, len, index)) return false;
        if (!ez_json_scan_ws(text, len, index)) return false;
        if (*index < len && text[*index] == ',') {
            (*index)++;
            if (!ez_json_scan_ws(text, len, index)) return false;
            continue;
        }
        if (*index < len && text[*index] == ']') {
            (*index)++;
            return true;
        }
        return false;
    }
    return false;
}

static bool ez_json_scan_object_value(const char *text, size_t len, size_t *index) {
    if (!text || !index || *index >= len || text[*index] != '{') return false;
    (*index)++;
    if (!ez_json_scan_ws(text, len, index)) return false;
    if (*index < len && text[*index] == '}') {
        (*index)++;
        return true;
    }
    while (*index < len) {
        if (!ez_json_scan_string_value(text, len, index)) return false;
        if (!ez_json_scan_ws(text, len, index) || *index >= len || text[*index] != ':') return false;
        (*index)++;
        if (!ez_json_scan_value(text, len, index)) return false;
        if (!ez_json_scan_ws(text, len, index)) return false;
        if (*index < len && text[*index] == ',') {
            (*index)++;
            if (!ez_json_scan_ws(text, len, index)) return false;
            continue;
        }
        if (*index < len && text[*index] == '}') {
            (*index)++;
            return true;
        }
        return false;
    }
    return false;
}

static bool ez_json_scan_number_value(const char *text, size_t len, size_t *index) {
    if (!text || !index || *index >= len) return false;
    size_t start = *index;
    size_t i = start;
    if (text[i] == '-') i++;
    if (i >= len) return false;
    if (text[i] == '0') {
        i++;
    } else if (text[i] >= '1' && text[i] <= '9') {
        while (i < len && ez_json_is_digit(text[i])) i++;
    } else {
        return false;
    }
    if (i < len && text[i] == '.') {
        i++;
        if (i >= len || !ez_json_is_digit(text[i])) return false;
        while (i < len && ez_json_is_digit(text[i])) i++;
    }
    if (i < len && (text[i] == 'e' || text[i] == 'E')) {
        i++;
        if (i < len && (text[i] == '+' || text[i] == '-')) i++;
        if (i >= len || !ez_json_is_digit(text[i])) return false;
        while (i < len && ez_json_is_digit(text[i])) i++;
    }
    if (!ez_json_number_span(text + start, i - start, true)) return false;
    *index = i;
    return true;
}

static bool ez_json_scan_value(const char *text, size_t len, size_t *index) {
    if (!ez_json_scan_ws(text, len, index) || *index >= len) return false;
    char ch = text[*index];
    if (ch == '"') return ez_json_scan_string_value(text, len, index);
    if (ch == '{') return ez_json_scan_object_value(text, len, index);
    if (ch == '[') return ez_json_scan_array_value(text, len, index);
    if (ch == 't') return ez_json_scan_literal(text, len, index, "true");
    if (ch == 'f') return ez_json_scan_literal(text, len, index, "false");
    if (ch == 'n') return ez_json_scan_literal(text, len, index, "null");
    if (ch == '-' || ez_json_is_digit(ch)) return ez_json_scan_number_value(text, len, index);
    return false;
}

bool __ez_json_valid_object(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len) || len == 0 || text[0] != '{') return false;
    size_t index = 0;
    if (!ez_json_scan_object_value(text, len, &index)) return false;
    if (!ez_json_scan_ws(text, len, &index)) return false;
    return index == len;
}

bool __ez_json_valid_array(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len) || len == 0 || text[0] != '[') return false;
    size_t index = 0;
    if (!ez_json_scan_array_value(text, len, &index)) return false;
    if (!ez_json_scan_ws(text, len, &index)) return false;
    return index == len;
}

bool __ez_json_valid_value(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len) || len == 0) return false;
    size_t index = 0;
    if (!ez_json_scan_value(text, len, &index)) return false;
    if (!ez_json_scan_ws(text, len, &index)) return false;
    return index == len;
}

bool __ez_json_valid_null(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    return ez_json_trim_span(s, &text, &len) && len == 4 && memcmp(text, "null", 4) == 0;
}

int64_t __ez_json_array_length(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len) || len == 0 || text[0] != '[') return -1;
    size_t index = 1;
    int64_t count = 0;
    if (!ez_json_scan_ws(text, len, &index)) return -1;
    if (index < len && text[index] == ']') {
        index++;
        return ez_json_scan_ws(text, len, &index) && index == len ? 0 : -1;
    }
    while (index < len) {
        if (!ez_json_scan_value(text, len, &index)) return -1;
        count++;
        if (!ez_json_scan_ws(text, len, &index)) return -1;
        if (index < len && text[index] == ',') {
            index++;
            if (!ez_json_scan_ws(text, len, &index)) return -1;
            continue;
        }
        if (index < len && text[index] == ']') {
            index++;
            return ez_json_scan_ws(text, len, &index) && index == len ? count : -1;
        }
        return -1;
    }
    return -1;
}

const char *__ez_json_array_item(const char *s, int64_t wanted) {
    const char *text = NULL;
    size_t len = 0;
    if (wanted < 0 || !ez_json_trim_span(s, &text, &len) || len == 0 || text[0] != '[') return NULL;
    size_t index = 1;
    int64_t count = 0;
    if (!ez_json_scan_ws(text, len, &index)) return NULL;
    if (index < len && text[index] == ']') return NULL;
    while (index < len) {
        size_t value_start = index;
        if (!ez_json_scan_value(text, len, &index)) return NULL;
        size_t value_end = index;
        if (count == wanted) return ez_strdup_range(text + value_start, value_end - value_start);
        count++;
        if (!ez_json_scan_ws(text, len, &index)) return NULL;
        if (index < len && text[index] == ',') {
            index++;
            if (!ez_json_scan_ws(text, len, &index)) return NULL;
            continue;
        }
        if (index < len && text[index] == ']') return NULL;
        return NULL;
    }
    return NULL;
}

int64_t __ez_json_object_field_count(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    if (!ez_json_trim_span(s, &text, &len) || len == 0 || text[0] != '{') return -1;
    size_t index = 1;
    int64_t count = 0;
    if (!ez_json_scan_ws(text, len, &index)) return -1;
    if (index < len && text[index] == '}') {
        index++;
        return ez_json_scan_ws(text, len, &index) && index == len ? 0 : -1;
    }
    while (index < len) {
        if (!ez_json_scan_string_value(text, len, &index)) return -1;
        if (!ez_json_scan_ws(text, len, &index) || index >= len || text[index] != ':') return -1;
        index++;
        if (!ez_json_scan_value(text, len, &index)) return -1;
        count++;
        if (!ez_json_scan_ws(text, len, &index)) return -1;
        if (index < len && text[index] == ',') {
            index++;
            if (!ez_json_scan_ws(text, len, &index)) return -1;
            continue;
        }
        if (index < len && text[index] == '}') {
            index++;
            return ez_json_scan_ws(text, len, &index) && index == len ? count : -1;
        }
        return -1;
    }
    return -1;
}

const char *__ez_json_object_field(const char *s, const char *key) {
    const char *text = NULL;
    size_t len = 0;
    if (!key || !ez_json_trim_span(s, &text, &len) || len == 0 || text[0] != '{') return NULL;
    size_t index = 1;
    size_t found_start = 0;
    size_t found_len = 0;
    bool found = false;
    if (!ez_json_scan_ws(text, len, &index)) return NULL;
    if (index < len && text[index] == '}') return NULL;
    while (index < len) {
        size_t key_start = index;
        if (!ez_json_scan_string_value(text, len, &index)) return NULL;
        size_t key_len = index - key_start;
        bool key_ok = false;
        char *decoded_key = ez_json_parse_string_span(text + key_start, key_len, &key_ok);
        bool key_matches = key_ok && decoded_key && strcmp(decoded_key, key) == 0;
        free(decoded_key);

        if (!ez_json_scan_ws(text, len, &index) || index >= len || text[index] != ':') return NULL;
        index++;
        if (!ez_json_scan_ws(text, len, &index)) return NULL;
        size_t value_start = index;
        if (!ez_json_scan_value(text, len, &index)) return NULL;
        size_t value_end = index;
        if (key_matches) {
            found_start = value_start;
            found_len = value_end - value_start;
            found = true;
        }
        if (!ez_json_scan_ws(text, len, &index)) return NULL;
        if (index < len && text[index] == ',') {
            index++;
            if (!ez_json_scan_ws(text, len, &index)) return NULL;
            continue;
        }
        if (index < len && text[index] == '}') {
            index++;
            if (!ez_json_scan_ws(text, len, &index) || index != len) return NULL;
            return found ? ez_strdup_range(text + found_start, found_len) : NULL;
        }
        return NULL;
    }
    return NULL;
}

const char *__ez_json_object_key_at(const char *s, int64_t wanted) {
    const char *text = NULL;
    size_t len = 0;
    if (wanted < 0 || !ez_json_trim_span(s, &text, &len) || len == 0 || text[0] != '{') return NULL;
    size_t index = 1;
    int64_t count = 0;
    if (!ez_json_scan_ws(text, len, &index)) return NULL;
    if (index < len && text[index] == '}') return NULL;
    while (index < len) {
        size_t key_start = index;
        if (!ez_json_scan_string_value(text, len, &index)) return NULL;
        size_t key_len = index - key_start;
        bool key_ok = false;
        char *decoded_key = ez_json_parse_string_span(text + key_start, key_len, &key_ok);
        if (!ez_json_scan_ws(text, len, &index) || index >= len || text[index] != ':') {
            free(decoded_key);
            return NULL;
        }
        index++;
        if (!ez_json_scan_ws(text, len, &index)) {
            free(decoded_key);
            return NULL;
        }
        if (!ez_json_scan_value(text, len, &index)) {
            free(decoded_key);
            return NULL;
        }
        if (count == wanted) {
            if (!key_ok || !decoded_key) {
                free(decoded_key);
                return NULL;
            }
            return decoded_key;
        }
        free(decoded_key);
        count++;
        if (!ez_json_scan_ws(text, len, &index)) return NULL;
        if (index < len && text[index] == ',') {
            index++;
            if (!ez_json_scan_ws(text, len, &index)) return NULL;
            continue;
        }
        if (index < len && text[index] == '}') return NULL;
        return NULL;
    }
    return NULL;
}

const char *__ez_json_object_value_at(const char *s, int64_t wanted) {
    const char *text = NULL;
    size_t len = 0;
    if (wanted < 0 || !ez_json_trim_span(s, &text, &len) || len == 0 || text[0] != '{') return NULL;
    size_t index = 1;
    int64_t count = 0;
    if (!ez_json_scan_ws(text, len, &index)) return NULL;
    if (index < len && text[index] == '}') return NULL;
    while (index < len) {
        if (!ez_json_scan_string_value(text, len, &index)) return NULL;
        if (!ez_json_scan_ws(text, len, &index) || index >= len || text[index] != ':') return NULL;
        index++;
        if (!ez_json_scan_ws(text, len, &index)) return NULL;
        size_t value_start = index;
        if (!ez_json_scan_value(text, len, &index)) return NULL;
        size_t value_end = index;
        if (count == wanted) return ez_strdup_range(text + value_start, value_end - value_start);
        count++;
        if (!ez_json_scan_ws(text, len, &index)) return NULL;
        if (index < len && text[index] == ',') {
            index++;
            if (!ez_json_scan_ws(text, len, &index)) return NULL;
            continue;
        }
        if (index < len && text[index] == '}') return NULL;
        return NULL;
    }
    return NULL;
}

bool __ez_json_valid_Str(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    bool ok = false;
    if (!ez_json_trim_span(s, &text, &len)) return false;
    char *parsed = ez_json_parse_string_span(text, len, &ok);
    free(parsed);
    return ok;
}

const char *jsonParse_Str(const char *s) {
    const char *text = NULL;
    size_t len = 0;
    bool ok = false;
    if (!ez_json_trim_span(s, &text, &len)) return ez_strdup_safe("");
    char *parsed = ez_json_parse_string_span(text, len, &ok);
    if (!parsed) return NULL;
    if (!ok) {
        free(parsed);
        return ez_strdup_safe("");
    }
    return parsed;
}

Blob msgpackEncode_I32(int32_t value) {
    uint8_t *out = (uint8_t *)malloc(5);
    if (!out) return (Blob){0};
    out[0] = 0xD2;
    out[1] = (uint8_t)((uint32_t)value >> 24);
    out[2] = (uint8_t)((uint32_t)value >> 16);
    out[3] = (uint8_t)((uint32_t)value >> 8);
    out[4] = (uint8_t)value;
    return (Blob){out, 5};
}

Blob msgpackEncode_I8(int8_t value) {
    uint8_t *out = (uint8_t *)malloc(2);
    if (!out) return (Blob){0};
    out[0] = 0xD0;
    out[1] = (uint8_t)value;
    return (Blob){out, 2};
}

Blob msgpackEncode_I64(int64_t value) {
    uint8_t *out = (uint8_t *)malloc(9);
    if (!out) return (Blob){0};
    out[0] = 0xD3;
    for (int i = 0; i < 8; ++i) out[i + 1] = (uint8_t)((uint64_t)value >> (56 - i * 8));
    return (Blob){out, 9};
}

Blob msgpackEncode_U32(uint32_t value) {
    uint8_t *out = (uint8_t *)malloc(5);
    if (!out) return (Blob){0};
    out[0] = 0xCE;
    out[1] = (uint8_t)(value >> 24);
    out[2] = (uint8_t)(value >> 16);
    out[3] = (uint8_t)(value >> 8);
    out[4] = (uint8_t)value;
    return (Blob){out, 5};
}

Blob msgpackEncode_U8(uint8_t value) {
    uint8_t *out = (uint8_t *)malloc(2);
    if (!out) return (Blob){0};
    out[0] = 0xCC;
    out[1] = value;
    return (Blob){out, 2};
}

Blob msgpackEncode_U64(uint64_t value) {
    uint8_t *out = (uint8_t *)malloc(9);
    if (!out) return (Blob){0};
    out[0] = 0xCF;
    for (int i = 0; i < 8; ++i) out[i + 1] = (uint8_t)(value >> (56 - i * 8));
    return (Blob){out, 9};
}

Blob msgpackEncode_F32(float value) {
    uint8_t *out = (uint8_t *)malloc(5);
    if (!out) return (Blob){0};
    uint32_t bits = 0;
    memcpy(&bits, &value, sizeof(bits));
    out[0] = 0xCA;
    for (int i = 0; i < 4; ++i) out[i + 1] = (uint8_t)(bits >> (24 - i * 8));
    return (Blob){out, 5};
}

Blob msgpackEncode_F64(double value) {
    uint8_t *out = (uint8_t *)malloc(9);
    if (!out) return (Blob){0};
    uint64_t bits = 0;
    memcpy(&bits, &value, sizeof(bits));
    out[0] = 0xCB;
    for (int i = 0; i < 8; ++i) out[i + 1] = (uint8_t)(bits >> (56 - i * 8));
    return (Blob){out, 9};
}

Blob msgpackEncode_I1(bool value) {
    uint8_t *out = (uint8_t *)malloc(1);
    if (!out) return (Blob){0};
    out[0] = value ? 0xC3 : 0xC2;
    return (Blob){out, 1};
}

Blob msgpackEncode_Str(const char *value) {
    if (!value) value = "";
    size_t len = strlen(value);
    size_t header_len = len <= 31 ? 1 : len <= 0xFF ? 2 : len <= 0xFFFF ? 3 : 5;
    uint8_t *out = (uint8_t *)malloc(header_len + len);
    if (!out) return (Blob){0};
    if (len <= 31) {
        out[0] = (uint8_t)(0xA0 | len);
    } else if (len <= 0xFF) {
        out[0] = 0xD9;
        out[1] = (uint8_t)len;
    } else if (len <= 0xFFFF) {
        out[0] = 0xDA;
        out[1] = (uint8_t)(len >> 8);
        out[2] = (uint8_t)len;
    } else {
        out[0] = 0xDB;
        out[1] = (uint8_t)(len >> 24);
        out[2] = (uint8_t)(len >> 16);
        out[3] = (uint8_t)(len >> 8);
        out[4] = (uint8_t)len;
    }
    memcpy(out + header_len, value, len);
    return (Blob){out, (int64_t)(header_len + len)};
}

static size_t ez_msgpack_str_header_len(size_t len) {
    return len <= 31 ? 1 : len <= 0xFF ? 2 : len <= 0xFFFF ? 3 : 5;
}

static bool ez_msgpack_write_str_header(uint8_t *out, size_t len, size_t *pos) {
    if (!out || !pos) return false;
    if (len <= 31) {
        out[(*pos)++] = (uint8_t)(0xA0 | len);
    } else if (len <= 0xFF) {
        out[(*pos)++] = 0xD9;
        out[(*pos)++] = (uint8_t)len;
    } else if (len <= 0xFFFF) {
        out[(*pos)++] = 0xDA;
        out[(*pos)++] = (uint8_t)(len >> 8);
        out[(*pos)++] = (uint8_t)len;
    } else if (len <= UINT32_MAX) {
        out[(*pos)++] = 0xDB;
        out[(*pos)++] = (uint8_t)(len >> 24);
        out[(*pos)++] = (uint8_t)(len >> 16);
        out[(*pos)++] = (uint8_t)(len >> 8);
        out[(*pos)++] = (uint8_t)len;
    } else {
        return false;
    }
    return true;
}

static bool ez_msgpack_add_size(size_t *total, size_t add) {
    if (!total || add > SIZE_MAX - *total) return false;
    *total += add;
    return true;
}

Blob __ez_msgpack_encode_map(int64_t count, const char **keys, const Blob *values) {
    if (count < 0 || count > UINT32_MAX) return (Blob){0};
    if (count > 0 && (!keys || !values)) return (Blob){0};

    size_t map_count = (size_t)count;
    size_t header_len = map_count <= 15 ? 1 : map_count <= 0xFFFF ? 3 : 5;
    size_t total = header_len;
    for (size_t i = 0; i < map_count; ++i) {
        const char *key = keys[i] ? keys[i] : "";
        size_t key_len = strlen(key);
        if (!ez_msgpack_add_size(&total, ez_msgpack_str_header_len(key_len))) return (Blob){0};
        if (!ez_msgpack_add_size(&total, key_len)) return (Blob){0};
        if (values[i].size < 0) return (Blob){0};
        if (values[i].size > 0 && !values[i].data) return (Blob){0};
        if (!ez_msgpack_add_size(&total, (size_t)values[i].size)) return (Blob){0};
    }

    uint8_t *out = (uint8_t *)malloc(total);
    if (!out) return (Blob){0};
    size_t pos = 0;
    if (map_count <= 15) {
        out[pos++] = (uint8_t)(0x80 | map_count);
    } else if (map_count <= 0xFFFF) {
        out[pos++] = 0xDE;
        out[pos++] = (uint8_t)(map_count >> 8);
        out[pos++] = (uint8_t)map_count;
    } else {
        out[pos++] = 0xDF;
        out[pos++] = (uint8_t)(map_count >> 24);
        out[pos++] = (uint8_t)(map_count >> 16);
        out[pos++] = (uint8_t)(map_count >> 8);
        out[pos++] = (uint8_t)map_count;
    }

    for (size_t i = 0; i < map_count; ++i) {
        const char *key = keys[i] ? keys[i] : "";
        size_t key_len = strlen(key);
        if (!ez_msgpack_write_str_header(out, key_len, &pos)) {
            free(out);
            return (Blob){0};
        }
        if (key_len > 0) memcpy(out + pos, key, key_len);
        pos += key_len;
        if (values[i].size > 0) memcpy(out + pos, values[i].data, (size_t)values[i].size);
        pos += (size_t)values[i].size;
    }
    return (Blob){out, (int64_t)total};
}

Blob __ez_msgpack_encode_map_raw(int64_t count, const Blob *keys, const Blob *values) {
    if (count < 0 || count > UINT32_MAX) return (Blob){0};
    if (count > 0 && (!keys || !values)) return (Blob){0};

    size_t map_count = (size_t)count;
    size_t header_len = map_count <= 15 ? 1 : map_count <= 0xFFFF ? 3 : 5;
    size_t total = header_len;
    for (size_t i = 0; i < map_count; ++i) {
        if (keys[i].size <= 0 || !keys[i].data) return (Blob){0};
        if (values[i].size < 0) return (Blob){0};
        if (values[i].size > 0 && !values[i].data) return (Blob){0};
        if (!ez_msgpack_add_size(&total, (size_t)keys[i].size)) return (Blob){0};
        if (!ez_msgpack_add_size(&total, (size_t)values[i].size)) return (Blob){0};
    }

    uint8_t *out = (uint8_t *)malloc(total ? total : 1);
    if (!out) return (Blob){0};
    size_t pos = 0;
    if (map_count <= 15) {
        out[pos++] = (uint8_t)(0x80 | map_count);
    } else if (map_count <= 0xFFFF) {
        out[pos++] = 0xDE;
        out[pos++] = (uint8_t)(map_count >> 8);
        out[pos++] = (uint8_t)map_count;
    } else {
        out[pos++] = 0xDF;
        out[pos++] = (uint8_t)(map_count >> 24);
        out[pos++] = (uint8_t)(map_count >> 16);
        out[pos++] = (uint8_t)(map_count >> 8);
        out[pos++] = (uint8_t)map_count;
    }

    for (size_t i = 0; i < map_count; ++i) {
        memcpy(out + pos, keys[i].data, (size_t)keys[i].size);
        pos += (size_t)keys[i].size;
        if (values[i].size > 0) memcpy(out + pos, values[i].data, (size_t)values[i].size);
        pos += (size_t)values[i].size;
    }
    return (Blob){out, (int64_t)total};
}

Blob __ez_msgpack_encode_array(int64_t count, const Blob *values) {
    if (count < 0 || count > UINT32_MAX) return (Blob){0};
    if (count > 0 && !values) return (Blob){0};

    size_t array_count = (size_t)count;
    size_t header_len = array_count <= 15 ? 1 : array_count <= 0xFFFF ? 3 : 5;
    size_t total = header_len;
    for (size_t i = 0; i < array_count; ++i) {
        if (values[i].size < 0) return (Blob){0};
        if (values[i].size > 0 && !values[i].data) return (Blob){0};
        if (!ez_msgpack_add_size(&total, (size_t)values[i].size)) return (Blob){0};
    }

    uint8_t *out = (uint8_t *)malloc(total ? total : 1);
    if (!out) return (Blob){0};
    size_t pos = 0;
    if (array_count <= 15) {
        out[pos++] = (uint8_t)(0x90 | array_count);
    } else if (array_count <= 0xFFFF) {
        out[pos++] = 0xDC;
        out[pos++] = (uint8_t)(array_count >> 8);
        out[pos++] = (uint8_t)array_count;
    } else {
        out[pos++] = 0xDD;
        out[pos++] = (uint8_t)(array_count >> 24);
        out[pos++] = (uint8_t)(array_count >> 16);
        out[pos++] = (uint8_t)(array_count >> 8);
        out[pos++] = (uint8_t)array_count;
    }

    for (size_t i = 0; i < array_count; ++i) {
        if (values[i].size > 0) memcpy(out + pos, values[i].data, (size_t)values[i].size);
        pos += (size_t)values[i].size;
    }
    return (Blob){out, (int64_t)total};
}

static uint16_t ez_msgpack_read_u16(const uint8_t *bytes) {
    return ((uint16_t)bytes[0] << 8) | (uint16_t)bytes[1];
}

static uint32_t ez_msgpack_read_u32(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) | ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static uint64_t ez_msgpack_read_u64(const uint8_t *bytes) {
    uint64_t value = 0;
    for (int i = 0; i < 8; ++i) value = (value << 8) | bytes[i];
    return value;
}

static bool ez_msgpack_need(size_t size, size_t index, size_t need) {
    return index <= size && need <= size - index;
}

static bool ez_msgpack_str_span_at(const uint8_t *bytes, size_t size, size_t index, size_t *payload_start, size_t *payload_len, size_t *next) {
    if (!bytes || index >= size || !payload_start || !payload_len || !next) return false;
    uint8_t tag = bytes[index];
    size_t header_len = 0;
    size_t len = 0;
    if ((tag & 0xE0) == 0xA0) {
        header_len = 1;
        len = tag & 0x1F;
    } else if (tag == 0xD9 && ez_msgpack_need(size, index, 2)) {
        header_len = 2;
        len = bytes[index + 1];
    } else if (tag == 0xDA && ez_msgpack_need(size, index, 3)) {
        header_len = 3;
        len = ez_msgpack_read_u16(bytes + index + 1);
    } else if (tag == 0xDB && ez_msgpack_need(size, index, 5)) {
        header_len = 5;
        uint32_t raw_len = ez_msgpack_read_u32(bytes + index + 1);
        len = (size_t)raw_len;
    } else {
        return false;
    }
    if (!ez_msgpack_need(size, index + header_len, len)) return false;
    *payload_start = index + header_len;
    *payload_len = len;
    *next = index + header_len + len;
    return true;
}

static bool ez_msgpack_skip_value_depth(const uint8_t *bytes, size_t size, size_t *index, int depth) {
    if (!bytes || !index || *index >= size || depth > 64) return false;
    size_t start = *index;
    uint8_t tag = bytes[start];

    if (tag <= 0x7F || tag >= 0xE0 || (tag >= 0xC0 && tag <= 0xC3)) {
        *index = start + 1;
        return true;
    }
    if ((tag & 0xE0) == 0xA0) {
        size_t payload_start = 0, payload_len = 0, next = 0;
        if (!ez_msgpack_str_span_at(bytes, size, start, &payload_start, &payload_len, &next)) return false;
        *index = next;
        return true;
    }
    if ((tag & 0xF0) == 0x90) {
        *index = start + 1;
        uint32_t count = tag & 0x0F;
        for (uint32_t i = 0; i < count; ++i) {
            if (!ez_msgpack_skip_value_depth(bytes, size, index, depth + 1)) return false;
        }
        return true;
    }
    if ((tag & 0xF0) == 0x80) {
        *index = start + 1;
        uint32_t count = tag & 0x0F;
        for (uint32_t i = 0; i < count; ++i) {
            if (!ez_msgpack_skip_value_depth(bytes, size, index, depth + 1)) return false;
            if (!ez_msgpack_skip_value_depth(bytes, size, index, depth + 1)) return false;
        }
        return true;
    }

    size_t fixed_size = 0;
    switch (tag) {
        case 0xCC: case 0xD0: fixed_size = 2; break;
        case 0xCD: case 0xD1: fixed_size = 3; break;
        case 0xCA: case 0xCE: case 0xD2: fixed_size = 5; break;
        case 0xCB: case 0xCF: case 0xD3: fixed_size = 9; break;
        case 0xD4: fixed_size = 3; break;
        case 0xD5: fixed_size = 4; break;
        case 0xD6: fixed_size = 6; break;
        case 0xD7: fixed_size = 10; break;
        case 0xD8: fixed_size = 18; break;
        default: break;
    }
    if (fixed_size > 0) {
        if (!ez_msgpack_need(size, start, fixed_size)) return false;
        *index = start + fixed_size;
        return true;
    }

    if (tag == 0xC4 || tag == 0xC7 || tag == 0xD9) {
        if (!ez_msgpack_need(size, start, 2)) return false;
        size_t len = bytes[start + 1];
        size_t extra = tag == 0xC7 ? 1 : 0;
        if (!ez_msgpack_need(size, start + 2, extra + len)) return false;
        *index = start + 2 + extra + len;
        return true;
    }
    if (tag == 0xC5 || tag == 0xC8 || tag == 0xDA) {
        if (!ez_msgpack_need(size, start, 3)) return false;
        size_t len = ez_msgpack_read_u16(bytes + start + 1);
        size_t extra = tag == 0xC8 ? 1 : 0;
        if (!ez_msgpack_need(size, start + 3, extra + len)) return false;
        *index = start + 3 + extra + len;
        return true;
    }
    if (tag == 0xC6 || tag == 0xC9 || tag == 0xDB) {
        if (!ez_msgpack_need(size, start, 5)) return false;
        size_t len = (size_t)ez_msgpack_read_u32(bytes + start + 1);
        size_t extra = tag == 0xC9 ? 1 : 0;
        if (!ez_msgpack_need(size, start + 5, extra + len)) return false;
        *index = start + 5 + extra + len;
        return true;
    }
    if (tag == 0xDC || tag == 0xDD) {
        size_t header_len = tag == 0xDC ? 3 : 5;
        if (!ez_msgpack_need(size, start, header_len)) return false;
        uint32_t count = tag == 0xDC ? ez_msgpack_read_u16(bytes + start + 1) : ez_msgpack_read_u32(bytes + start + 1);
        *index = start + header_len;
        for (uint32_t i = 0; i < count; ++i) {
            if (!ez_msgpack_skip_value_depth(bytes, size, index, depth + 1)) return false;
        }
        return true;
    }
    if (tag == 0xDE || tag == 0xDF) {
        size_t header_len = tag == 0xDE ? 3 : 5;
        if (!ez_msgpack_need(size, start, header_len)) return false;
        uint32_t count = tag == 0xDE ? ez_msgpack_read_u16(bytes + start + 1) : ez_msgpack_read_u32(bytes + start + 1);
        *index = start + header_len;
        for (uint32_t i = 0; i < count; ++i) {
            if (!ez_msgpack_skip_value_depth(bytes, size, index, depth + 1)) return false;
            if (!ez_msgpack_skip_value_depth(bytes, size, index, depth + 1)) return false;
        }
        return true;
    }
    return false;
}

static bool ez_msgpack_skip_value(const uint8_t *bytes, size_t size, size_t *index) {
    return ez_msgpack_skip_value_depth(bytes, size, index, 0);
}

static bool ez_msgpack_single_value(const Blob *data) {
    if (!data || data->size <= 0 || !data->data) return false;
    size_t index = 0;
    size_t size = (size_t)data->size;
    return ez_msgpack_skip_value(data->data, size, &index) && index == size;
}

static bool ez_msgpack_map_header(const Blob *data, size_t *index, uint32_t *count) {
    if (!data || data->size <= 0 || !data->data || !index || !count) return false;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    uint8_t tag = bytes[0];
    if ((tag & 0xF0) == 0x80) {
        *index = 1;
        *count = tag & 0x0F;
        return true;
    }
    if (tag == 0xDE && size >= 3) {
        *index = 3;
        *count = ez_msgpack_read_u16(bytes + 1);
        return true;
    }
    if (tag == 0xDF && size >= 5) {
        *index = 5;
        *count = ez_msgpack_read_u32(bytes + 1);
        return true;
    }
    return false;
}

static bool ez_msgpack_array_header(const Blob *data, size_t *index, uint32_t *count) {
    if (!data || data->size <= 0 || !data->data || !index || !count) return false;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    uint8_t tag = bytes[0];
    if ((tag & 0xF0) == 0x90) {
        *index = 1;
        *count = tag & 0x0F;
        return true;
    }
    if (tag == 0xDC && size >= 3) {
        *index = 3;
        *count = ez_msgpack_read_u16(bytes + 1);
        return true;
    }
    if (tag == 0xDD && size >= 5) {
        *index = 5;
        *count = ez_msgpack_read_u32(bytes + 1);
        return true;
    }
    return false;
}

static bool ez_msgpack_validate_top_array(const Blob *data, uint32_t *count_out) {
    size_t index = 0;
    uint32_t count = 0;
    if (!ez_msgpack_array_header(data, &index, &count)) return false;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    for (uint32_t i = 0; i < count; ++i) {
        if (!ez_msgpack_skip_value(bytes, size, &index)) return false;
    }
    if (index != size) return false;
    if (count_out) *count_out = count;
    return true;
}

bool __ez_msgpack_valid_array(const Blob *data) {
    return ez_msgpack_validate_top_array(data, NULL);
}

bool __ez_msgpack_valid_value(const Blob *data) {
    if (!data || data->size <= 0 || !data->data) return false;
    size_t index = 0;
    if (!ez_msgpack_skip_value(data->data, (size_t)data->size, &index)) return false;
    return index == (size_t)data->size;
}

bool __ez_msgpack_valid_nil(const Blob *data) {
    return data && data->size == 1 && data->data && data->data[0] == 0xC0;
}

int64_t __ez_msgpack_array_length(const Blob *data) {
    uint32_t count = 0;
    if (!ez_msgpack_validate_top_array(data, &count)) return -1;
    return (int64_t)count;
}

Blob __ez_msgpack_array_item(const Blob *data, int64_t wanted) {
    Blob missing = {NULL, -1};
    if (wanted < 0 || !data || data->size <= 0 || !data->data) return missing;
    size_t index = 0;
    uint32_t count = 0;
    if (!ez_msgpack_array_header(data, &index, &count) || (uint64_t)wanted >= count) return missing;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    for (uint32_t i = 0; i < count; ++i) {
        size_t value_start = index;
        if (!ez_msgpack_skip_value(bytes, size, &index)) return missing;
        if (i == (uint32_t)wanted) return (Blob){(uint8_t *)(bytes + value_start), (int64_t)(index - value_start)};
    }
    return missing;
}

static bool ez_msgpack_validate_top_map(const Blob *data, uint32_t *count_out) {
    size_t index = 0;
    uint32_t count = 0;
    if (!ez_msgpack_map_header(data, &index, &count)) return false;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    for (uint32_t i = 0; i < count; ++i) {
        size_t key_start = 0, key_len = 0, next = 0;
        if (!ez_msgpack_str_span_at(bytes, size, index, &key_start, &key_len, &next)) return false;
        if (ez_contains_nul_byte(bytes + key_start, key_len)) return false;
        if (!ez_utf8_validate_len((const char *)(bytes + key_start), key_len)) return false;
        index = next;
        if (!ez_msgpack_skip_value(bytes, size, &index)) return false;
    }
    if (index != size) return false;
    if (count_out) *count_out = count;
    return true;
}

bool __ez_msgpack_valid_map(const Blob *data) {
    return ez_msgpack_validate_top_map(data, NULL);
}

static bool ez_msgpack_validate_top_map_any(const Blob *data, uint32_t *count_out) {
    size_t index = 0;
    uint32_t count = 0;
    if (!ez_msgpack_map_header(data, &index, &count)) return false;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    for (uint32_t i = 0; i < count; ++i) {
        if (!ez_msgpack_skip_value(bytes, size, &index)) return false;
        if (!ez_msgpack_skip_value(bytes, size, &index)) return false;
    }
    if (index != size) return false;
    if (count_out) *count_out = count;
    return true;
}

bool __ez_msgpack_valid_map_any(const Blob *data) {
    return ez_msgpack_validate_top_map_any(data, NULL);
}

int64_t __ez_msgpack_map_field_count(const Blob *data) {
    uint32_t count = 0;
    if (!ez_msgpack_validate_top_map_any(data, &count)) return -1;
    return (int64_t)count;
}

Blob __ez_msgpack_map_field(const Blob *data, const char *key) {
    Blob missing = {NULL, -1};
    if (!data || data->size <= 0 || !data->data || !key) return missing;
    size_t index = 0;
    uint32_t count = 0;
    if (!ez_msgpack_map_header(data, &index, &count)) return missing;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    size_t key_match_len = strlen(key);
    size_t found_start = 0;
    size_t found_len = 0;
    bool found = false;
    for (uint32_t i = 0; i < count; ++i) {
        size_t key_start = 0, key_len = 0, next = 0;
        if (!ez_msgpack_str_span_at(bytes, size, index, &key_start, &key_len, &next)) return missing;
        if (ez_contains_nul_byte(bytes + key_start, key_len)) return missing;
        if (!ez_utf8_validate_len((const char *)(bytes + key_start), key_len)) return missing;
        bool key_matches = key_len == key_match_len && memcmp(bytes + key_start, key, key_len) == 0;
        index = next;
        size_t value_start = index;
        if (!ez_msgpack_skip_value(bytes, size, &index)) return missing;
        if (key_matches) {
            found_start = value_start;
            found_len = index - value_start;
            found = true;
        }
    }
    if (index != size || !found) return missing;
    return (Blob){(uint8_t *)(bytes + found_start), (int64_t)found_len};
}

const char *__ez_msgpack_map_key_at(const Blob *data, int64_t wanted) {
    if (wanted < 0 || !data || data->size <= 0 || !data->data) return NULL;
    size_t index = 0;
    uint32_t count = 0;
    if (!ez_msgpack_map_header(data, &index, &count) || (uint64_t)wanted >= count) return NULL;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    for (uint32_t i = 0; i < count; ++i) {
        size_t key_start = 0, key_len = 0, next = 0;
        if (!ez_msgpack_str_span_at(bytes, size, index, &key_start, &key_len, &next)) return NULL;
        if (ez_contains_nul_byte(bytes + key_start, key_len)) return NULL;
        if (!ez_utf8_validate_len((const char *)(bytes + key_start), key_len)) return NULL;
        index = next;
        size_t value_start = index;
        if (!ez_msgpack_skip_value(bytes, size, &index)) return NULL;
        if (i == (uint32_t)wanted) return ez_strdup_range((const char *)(bytes + key_start), key_len);
        (void)value_start;
    }
    return NULL;
}

Blob __ez_msgpack_map_key_blob_at(const Blob *data, int64_t wanted) {
    Blob missing = {NULL, -1};
    if (wanted < 0 || !data || data->size <= 0 || !data->data) return missing;
    size_t index = 0;
    uint32_t count = 0;
    if (!ez_msgpack_map_header(data, &index, &count) || (uint64_t)wanted >= count) return missing;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    for (uint32_t i = 0; i < count; ++i) {
        size_t key_start = index;
        if (!ez_msgpack_skip_value(bytes, size, &index)) return missing;
        size_t key_end = index;
        if (!ez_msgpack_skip_value(bytes, size, &index)) return missing;
        if (i == (uint32_t)wanted) return (Blob){(uint8_t *)(bytes + key_start), (int64_t)(key_end - key_start)};
    }
    return missing;
}

Blob __ez_msgpack_map_value_at(const Blob *data, int64_t wanted) {
    Blob missing = {NULL, -1};
    if (wanted < 0 || !data || data->size <= 0 || !data->data) return missing;
    size_t index = 0;
    uint32_t count = 0;
    if (!ez_msgpack_map_header(data, &index, &count) || (uint64_t)wanted >= count) return missing;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    for (uint32_t i = 0; i < count; ++i) {
        if (!ez_msgpack_skip_value(bytes, size, &index)) return missing;
        size_t value_start = index;
        if (!ez_msgpack_skip_value(bytes, size, &index)) return missing;
        if (i == (uint32_t)wanted) return (Blob){(uint8_t *)(bytes + value_start), (int64_t)(index - value_start)};
    }
    return missing;
}

static int64_t ez_msgpack_i64_from_u64(uint64_t raw) {
    if (raw <= (uint64_t)INT64_MAX) return (int64_t)raw;
    return -1 - (int64_t)(UINT64_MAX - raw);
}

static int64_t ez_msgpack_i32_from_u32(uint32_t raw) {
    if (raw <= (uint32_t)INT32_MAX) return (int64_t)raw;
    return -1 - (int64_t)(UINT32_MAX - raw);
}

static bool ez_msgpack_decode_integer(const Blob *data, int64_t *out) {
    if (!data || data->size <= 0 || !data->data || !out) return false;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    uint8_t tag = bytes[0];
    if (tag <= 0x7F) {
        *out = tag;
        return true;
    }
    if (tag >= 0xE0) {
        *out = (int8_t)tag;
        return true;
    }
    if (tag == 0xCC && size == 2) {
        *out = bytes[1];
        return true;
    }
    if (tag == 0xCD && size == 3) {
        *out = ez_msgpack_read_u16(bytes + 1);
        return true;
    }
    if (tag == 0xCE && size == 5) {
        *out = ez_msgpack_read_u32(bytes + 1);
        return true;
    }
    if (tag == 0xCF && size == 9) {
        uint64_t raw = ez_msgpack_read_u64(bytes + 1);
        if (raw > (uint64_t)INT64_MAX) return false;
        *out = (int64_t)raw;
        return true;
    }
    if (tag == 0xD0 && size == 2) {
        *out = (int8_t)bytes[1];
        return true;
    }
    if (tag == 0xD1 && size == 3) {
        *out = (int16_t)ez_msgpack_read_u16(bytes + 1);
        return true;
    }
    if (tag == 0xD2 && size == 5) {
        *out = ez_msgpack_i32_from_u32(ez_msgpack_read_u32(bytes + 1));
        return true;
    }
    if (tag == 0xD3 && size == 9) {
        *out = ez_msgpack_i64_from_u64(ez_msgpack_read_u64(bytes + 1));
        return true;
    }
    return false;
}

static bool ez_msgpack_decode_unsigned_integer(const Blob *data, uint64_t *out) {
    if (!data || data->size <= 0 || !data->data || !out) return false;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    uint8_t tag = bytes[0];
    if (tag <= 0x7F) {
        *out = tag;
        return true;
    }
    if (tag == 0xCC && size == 2) {
        *out = bytes[1];
        return true;
    }
    if (tag == 0xCD && size == 3) {
        *out = ez_msgpack_read_u16(bytes + 1);
        return true;
    }
    if (tag == 0xCE && size == 5) {
        *out = ez_msgpack_read_u32(bytes + 1);
        return true;
    }
    if (tag == 0xCF && size == 9) {
        *out = ez_msgpack_read_u64(bytes + 1);
        return true;
    }
    return false;
}

bool __ez_msgpack_valid_I32(const Blob *data) {
    int64_t value = 0;
    return ez_msgpack_decode_integer(data, &value) && value >= INT32_MIN && value <= INT32_MAX;
}

bool __ez_msgpack_valid_I8(const Blob *data) {
    int64_t value = 0;
    return ez_msgpack_decode_integer(data, &value) && value >= INT8_MIN && value <= INT8_MAX;
}

bool __ez_msgpack_valid_I64(const Blob *data) {
    int64_t value = 0;
    return ez_msgpack_decode_integer(data, &value);
}

bool __ez_msgpack_valid_U32(const Blob *data) {
    uint64_t value = 0;
    return ez_msgpack_decode_unsigned_integer(data, &value) && value <= UINT32_MAX;
}

bool __ez_msgpack_valid_U8(const Blob *data) {
    uint64_t value = 0;
    return ez_msgpack_decode_unsigned_integer(data, &value) && value <= UINT8_MAX;
}

bool __ez_msgpack_valid_U64(const Blob *data) {
    uint64_t value = 0;
    return ez_msgpack_decode_unsigned_integer(data, &value);
}

bool __ez_msgpack_valid_F32(const Blob *data) {
    if (data && data->size == 5 && data->data && data->data[0] == 0xCA) {
        uint32_t bits = ez_msgpack_read_u32(data->data + 1);
        float value = 0.0f;
        memcpy(&value, &bits, sizeof(value));
        return isfinite(value);
    }
    if (data && data->size == 9 && data->data && data->data[0] == 0xCB) {
        uint64_t bits = ez_msgpack_read_u64(data->data + 1);
        double value = 0.0;
        memcpy(&value, &bits, sizeof(value));
        return isfinite(value) && value <= FLT_MAX && value >= -FLT_MAX;
    }
    return false;
}

bool __ez_msgpack_valid_F64(const Blob *data) {
    if (data && data->size == 5 && data->data && data->data[0] == 0xCA) {
        uint32_t bits = ez_msgpack_read_u32(data->data + 1);
        float value = 0.0f;
        memcpy(&value, &bits, sizeof(value));
        return isfinite(value);
    }
    if (data && data->size == 9 && data->data && data->data[0] == 0xCB) {
        uint64_t bits = ez_msgpack_read_u64(data->data + 1);
        double value = 0.0;
        memcpy(&value, &bits, sizeof(value));
        return isfinite(value);
    }
    return false;
}

bool __ez_msgpack_valid_Bool(const Blob *data) {
    return data && data->size == 1 && data->data && (data->data[0] == 0xC2 || data->data[0] == 0xC3);
}

bool __ez_msgpack_valid_Str(const Blob *data) {
    if (!data || data->size <= 0 || !data->data) return false;
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    size_t payload_start = 0;
    size_t len = 0;
    size_t next = 0;
    if (!ez_msgpack_str_span_at(bytes, size, 0, &payload_start, &len, &next) || next != size) return false;
    if (ez_contains_nul_byte(bytes + payload_start, len)) return false;
    return ez_utf8_validate_len((const char *)(bytes + payload_start), len);
}

int32_t msgpackDecode_I32(const Blob *data) {
    int64_t value = 0;
    if (!ez_msgpack_decode_integer(data, &value)) return 0;
    if (value < INT32_MIN || value > INT32_MAX) return 0;
    return (int32_t)value;
}

int8_t msgpackDecode_I8(const Blob *data) {
    int64_t value = 0;
    if (!ez_msgpack_decode_integer(data, &value)) return 0;
    if (value < INT8_MIN || value > INT8_MAX) return 0;
    return (int8_t)value;
}

int64_t msgpackDecode_I64(const Blob *data) {
    int64_t value = 0;
    return ez_msgpack_decode_integer(data, &value) ? value : 0;
}

uint32_t msgpackDecode_U32(const Blob *data) {
    uint64_t value = 0;
    if (!ez_msgpack_decode_unsigned_integer(data, &value) || value > UINT32_MAX) return 0;
    return (uint32_t)value;
}

uint8_t msgpackDecode_U8(const Blob *data) {
    uint64_t value = 0;
    if (!ez_msgpack_decode_unsigned_integer(data, &value) || value > UINT8_MAX) return 0;
    return (uint8_t)value;
}

uint64_t msgpackDecode_U64(const Blob *data) {
    uint64_t value = 0;
    return ez_msgpack_decode_unsigned_integer(data, &value) ? value : 0;
}

float msgpackDecode_F32(const Blob *data) {
    if (data && data->size == 5 && data->data && data->data[0] == 0xCA) {
        uint32_t bits = ez_msgpack_read_u32(data->data + 1);
        float value = 0.0f;
        memcpy(&value, &bits, sizeof(value));
        return value;
    }
    if (data && data->size == 9 && data->data && data->data[0] == 0xCB) {
        uint64_t bits = ez_msgpack_read_u64(data->data + 1);
        double value = 0.0;
        memcpy(&value, &bits, sizeof(value));
        if (!isfinite(value) || value > FLT_MAX || value < -FLT_MAX) return 0.0f;
        return (float)value;
    }
    return 0.0f;
}

double msgpackDecode_F64(const Blob *data) {
    if (data && data->size == 5 && data->data && data->data[0] == 0xCA) {
        uint32_t bits = ez_msgpack_read_u32(data->data + 1);
        float value = 0.0f;
        memcpy(&value, &bits, sizeof(value));
        return (double)value;
    }
    if (data && data->size == 9 && data->data && data->data[0] == 0xCB) {
        uint64_t bits = ez_msgpack_read_u64(data->data + 1);
        double value = 0.0;
        memcpy(&value, &bits, sizeof(value));
        return value;
    }
    return 0.0;
}

bool msgpackDecode_I1(const Blob *data) {
    if (!data || data->size != 1 || !data->data) return false;
    return data->data[0] == 0xC3;
}

const char *msgpackDecode_Str(const Blob *data) {
    if (!data || data->size <= 0 || !data->data) return ez_strdup_safe("");
    const uint8_t *bytes = data->data;
    size_t size = (size_t)data->size;
    size_t header_len = 0;
    size_t len = 0;
    if ((bytes[0] & 0xE0) == 0xA0) {
        header_len = 1;
        len = bytes[0] & 0x1F;
    } else if (bytes[0] == 0xD9 && size >= 2) {
        header_len = 2;
        len = bytes[1];
    } else if (bytes[0] == 0xDA && size >= 3) {
        header_len = 3;
        len = ((size_t)bytes[1] << 8) | bytes[2];
    } else if (bytes[0] == 0xDB && size >= 5) {
        header_len = 5;
        len = ((size_t)bytes[1] << 24) | ((size_t)bytes[2] << 16) | ((size_t)bytes[3] << 8) | bytes[4];
    } else {
        return ez_strdup_safe("");
    }
    if (header_len + len != size) return ez_strdup_safe("");
    if (ez_contains_nul_byte(bytes + header_len, len)) return ez_strdup_safe("");
    if (!ez_utf8_validate_len((const char *)(bytes + header_len), len)) return ez_strdup_safe("");
    return ez_strdup_range((const char *)(bytes + header_len), len);
}

static bool ez_is_unreserved(unsigned char ch) {
    return isalnum(ch) || ch == '-' || ch == '_' || ch == '.' || ch == '~';
}

const char *urlEncode(const char *s) {
    if (!s) return ez_strdup_safe("");
    size_t len = strlen(s);
    char *out = (char *)malloc(len * 3 + 1);
    if (!out) return NULL;
    size_t j = 0;
    static const char hex[] = "0123456789ABCDEF";
    for (size_t i = 0; i < len; ++i) {
        unsigned char ch = (unsigned char)s[i];
        if (ez_is_unreserved(ch)) {
            out[j++] = (char)ch;
        } else {
            out[j++] = '%';
            out[j++] = hex[ch >> 4];
            out[j++] = hex[ch & 0xF];
        }
    }
    out[j] = '\0';
    return out;
}

static int ez_hex_value(char ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    return -1;
}

OptStr urlDecode(const char *s) {
    if (!s) return (OptStr){false, NULL};
    size_t len = strlen(s);
    char *out = (char *)malloc(len + 1);
    if (!out) return (OptStr){false, NULL};
    size_t j = 0;
    for (size_t i = 0; i < len; ++i) {
        if (s[i] == '%') {
            if (i + 2 >= len) {
                free(out);
                return (OptStr){false, NULL};
            }
            int hi = ez_hex_value(s[i + 1]);
            int lo = ez_hex_value(s[i + 2]);
            if (hi < 0 || lo < 0) {
                free(out);
                return (OptStr){false, NULL};
            }
            unsigned char byte = (unsigned char)((hi << 4) | lo);
            if (byte == 0) {
                free(out);
                return (OptStr){false, NULL};
            }
            out[j++] = (char)byte;
            i += 2;
        } else {
            out[j++] = s[i];
        }
    }
    out[j] = '\0';
    if (!ez_utf8_validate_len(out, j)) {
        free(out);
        return (OptStr){false, NULL};
    }
    return (OptStr){true, out};
}
