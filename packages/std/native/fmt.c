// EzLang std/fmt 原生封装层

#include <ctype.h>
#include <errno.h>
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

const char *toString_I64(int64_t value) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%lld", (long long)value);
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

OptI32 parseInt(const char *s) {
    if (!s) return (OptI32){false, 0};
    errno = 0;
    char *end = NULL;
    long value = strtol(s, &end, 10);
    while (end && isspace((unsigned char)*end)) end++;
    if (errno != 0 || end == s || (end && *end != '\0')) return (OptI32){false, 0};
    if (value < INT32_MIN || value > INT32_MAX) return (OptI32){false, 0};
    return (OptI32){true, (int32_t)value};
}

OptI64 parseI64(const char *s) {
    if (!s) return (OptI64){false, 0};
    errno = 0;
    char *end = NULL;
    long long value = strtoll(s, &end, 10);
    while (end && isspace((unsigned char)*end)) end++;
    if (errno != 0 || end == s || (end && *end != '\0')) return (OptI64){false, 0};
    return (OptI64){true, (int64_t)value};
}

OptF64 parseF64(const char *s) {
    if (!s) return (OptF64){false, 0.0};
    errno = 0;
    char *end = NULL;
    double value = strtod(s, &end);
    while (end && isspace((unsigned char)*end)) end++;
    if (errno != 0 || end == s || (end && *end != '\0') || !isfinite(value)) return (OptF64){false, 0.0};
    return (OptF64){true, value};
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
    if (!data || data->size < 0 || (data->size > 0 && !data->data)) return NULL;
    size_t len = (size_t)data->size;
    size_t out_len = ((len + 2) / 3) * 4;
    char *out = (char *)malloc(out_len + 1);
    if (!out) return NULL;

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

OptBlob b64Decode(const char *s) {
    if (!s) return (OptBlob){false, {0}};
    size_t in_len = strlen(s);
    if (in_len % 4 != 0) return (OptBlob){false, {0}};
    size_t padding = 0;
    if (in_len > 0 && s[in_len - 1] == '=') padding++;
    if (in_len > 1 && s[in_len - 2] == '=') padding++;
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
const char *jsonStringify_I64(int64_t value) { return toString_I64(value); }
const char *jsonStringify_F64(double value) { return toString_F64(value); }
const char *jsonStringify_I1(bool value) { return toString_I1(value); }

const char *jsonStringify_Str(const char *value) {
    if (!value) value = "";
    size_t cap = strlen(value) * 2 + 3;
    char *out = (char *)malloc(cap);
    if (!out) return NULL;
    size_t len = 0;
    out[len++] = '"';
    for (const char *p = value; *p; ++p) {
        if (*p == '"' || *p == '\\') {
            out[len++] = '\\';
            out[len++] = *p;
        } else if (*p == '\n') {
            out[len++] = '\\';
            out[len++] = 'n';
        } else {
            out[len++] = *p;
        }
    }
    out[len++] = '"';
    out[len] = '\0';
    return out;
}

int32_t jsonParse_I32(const char *s) {
    OptI32 parsed = parseInt(s);
    return parsed.ok ? parsed.value : 0;
}

int64_t jsonParse_I64(const char *s) {
    OptI64 parsed = parseI64(s);
    return parsed.ok ? parsed.value : 0;
}

double jsonParse_F64(const char *s) {
    OptF64 parsed = parseF64(s);
    return parsed.ok ? parsed.value : 0.0;
}

bool jsonParse_I1(const char *s) {
    if (!s) return false;
    if (strcmp(s, "true") == 0) return true;
    if (strcmp(s, "false") == 0) return false;
    return false;
}

const char *jsonParse_Str(const char *s) {
    if (!s) return ez_strdup_safe("");
    size_t len = strlen(s);
    if (len < 2 || s[0] != '"' || s[len - 1] != '"') return ez_strdup_safe("");
    char *out = (char *)malloc(len - 1);
    if (!out) return NULL;
    size_t j = 0;
    for (size_t i = 1; i + 1 < len; ++i) {
        if (s[i] == '\\' && i + 1 < len - 1) {
            char esc = s[++i];
            out[j++] = esc == 'n' ? '\n' : esc;
        } else {
            out[j++] = s[i];
        }
    }
    out[j] = '\0';
    return out;
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

Blob msgpackEncode_I64(int64_t value) {
    uint8_t *out = (uint8_t *)malloc(9);
    if (!out) return (Blob){0};
    out[0] = 0xD3;
    for (int i = 0; i < 8; ++i) out[i + 1] = (uint8_t)((uint64_t)value >> (56 - i * 8));
    return (Blob){out, 9};
}

int32_t msgpackDecode_I32(const Blob *data) {
    if (data && data->size == 5 && data->data && data->data[0] == 0xD2) {
        uint32_t value = ((uint32_t)data->data[1] << 24) | ((uint32_t)data->data[2] << 16) | ((uint32_t)data->data[3] << 8) | data->data[4];
        return (int32_t)value;
    }
    return 0;
}

int64_t msgpackDecode_I64(const Blob *data) {
    if (data && data->size == 9 && data->data && data->data[0] == 0xD3) {
        uint64_t value = 0;
        for (int i = 0; i < 8; ++i) value = (value << 8) | data->data[i + 1];
        return (int64_t)value;
    }
    return 0;
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
            out[j++] = (char)((hi << 4) | lo);
            i += 2;
        } else {
            out[j++] = s[i];
        }
    }
    out[j] = '\0';
    return (OptStr){true, out};
}
