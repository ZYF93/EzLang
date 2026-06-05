// EzLang std/uri 原生封装层

#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    const char *scheme;
    const char *userInfo;
    const char *host;
    int32_t port;
    const char *path;
    const char *query;
    const char *fragment;
} UriParts;

typedef struct { bool ok; const char *value; } OptStr;
typedef struct { bool ok; int32_t value; } OptI32;
typedef struct { bool ok; UriParts value; } OptUriParts;

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

static bool ez_scheme_valid(const char *start, const char *end) {
    if (!start || start == end || !isalpha((unsigned char)*start)) return false;
    for (const char *p = start + 1; p < end; ++p) {
        unsigned char ch = (unsigned char)*p;
        if (!isalnum(ch) && ch != '+' && ch != '-' && ch != '.') return false;
    }
    return true;
}

static int ez_hex_value(char ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    return -1;
}

static bool ez_unreserved(unsigned char ch) {
    return isalnum(ch) || ch == '-' || ch == '.' || ch == '_' || ch == '~';
}

static char *ez_percent_encode(const char *s, bool query_mode) {
    if (!s) s = "";
    static const char hex[] = "0123456789ABCDEF";
    size_t len = strlen(s);
    char *out = (char *)malloc(len * 3 + 1);
    if (!out) return NULL;
    size_t offset = 0;
    for (size_t i = 0; i < len; ++i) {
        unsigned char ch = (unsigned char)s[i];
        if (ez_unreserved(ch)) {
            out[offset++] = (char)ch;
        } else if (query_mode && ch == ' ') {
            out[offset++] = '+';
        } else {
            out[offset++] = '%';
            out[offset++] = hex[ch >> 4];
            out[offset++] = hex[ch & 0x0F];
        }
    }
    out[offset] = '\0';
    return out;
}

static OptStr ez_percent_decode(const char *s, bool query_mode) {
    if (!s) s = "";
    size_t len = strlen(s);
    char *out = (char *)malloc(len + 1);
    if (!out) return (OptStr){false, NULL};
    size_t offset = 0;
    for (size_t i = 0; i < len; ++i) {
        char ch = s[i];
        if (query_mode && ch == '+') {
            out[offset++] = ' ';
            continue;
        }
        if (ch == '%') {
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
            out[offset++] = (char)((hi << 4) | lo);
            i += 2;
        } else {
            out[offset++] = ch;
        }
    }
    out[offset] = '\0';
    return (OptStr){true, out};
}

static OptStr ez_percent_decode_range(const char *start, size_t len, bool query_mode) {
    char *slice = ez_strdup_range(start, len);
    if (!slice) return (OptStr){false, NULL};
    OptStr decoded = ez_percent_decode(slice, query_mode);
    free(slice);
    return decoded;
}

static bool ez_query_key_matches(const char *start, size_t len, const char *key) {
    OptStr decoded = ez_percent_decode_range(start, len, true);
    if (!decoded.ok) return false;
    bool matched = strcmp(decoded.value ? decoded.value : "", key ? key : "") == 0;
    free((char *)decoded.value);
    return matched;
}

static char *ez_lower_range(const char *start, size_t len) {
    char *out = ez_strdup_range(start, len);
    if (!out) return NULL;
    for (size_t i = 0; i < len; ++i) out[i] = (char)tolower((unsigned char)out[i]);
    return out;
}

static OptUriParts ez_parse_uri(const char *url) {
    if (!url) return (OptUriParts){false, {0}};
    const char *p = url;
    const char *end = url + strlen(url);
    const char *scheme_end = NULL;
    for (const char *scan = p; scan < end; ++scan) {
        if (*scan == ':') {
            scheme_end = scan;
            break;
        }
        if (*scan == '/' || *scan == '?' || *scan == '#') break;
    }
    if (!scheme_end || !ez_scheme_valid(p, scheme_end)) return (OptUriParts){false, {0}};

    UriParts parts;
    parts.scheme = ez_lower_range(p, (size_t)(scheme_end - p));
    parts.userInfo = ez_strdup_safe("");
    parts.host = ez_strdup_safe("");
    parts.port = -1;
    parts.path = ez_strdup_safe("");
    parts.query = ez_strdup_safe("");
    parts.fragment = ez_strdup_safe("");
    p = scheme_end + 1;

    if (p + 1 < end && p[0] == '/' && p[1] == '/') {
        p += 2;
        const char *authority_start = p;
        while (p < end && *p != '/' && *p != '?' && *p != '#') p++;
        const char *authority_end = p;
        const char *host_start = authority_start;
        for (const char *scan = authority_start; scan < authority_end; ++scan) {
            if (*scan == '@') {
                free((char *)parts.userInfo);
                parts.userInfo = ez_strdup_range(authority_start, (size_t)(scan - authority_start));
                host_start = scan + 1;
            }
        }
        const char *host_end = authority_end;
        if (host_start < authority_end && *host_start == '[') {
            const char *close = memchr(host_start, ']', (size_t)(authority_end - host_start));
            if (!close) return (OptUriParts){false, {0}};
            host_end = close + 1;
            if (host_end < authority_end && *host_end == ':') {
                parts.port = atoi(host_end + 1);
            }
        } else {
            for (const char *scan = authority_end; scan > host_start; --scan) {
                if (*(scan - 1) == ':') {
                    host_end = scan - 1;
                    parts.port = atoi(scan);
                    break;
                }
            }
        }
        free((char *)parts.host);
        parts.host = ez_lower_range(host_start, (size_t)(host_end - host_start));
    }

    const char *path_start = p;
    while (p < end && *p != '?' && *p != '#') p++;
    free((char *)parts.path);
    parts.path = ez_strdup_range(path_start, (size_t)(p - path_start));
    if (p < end && *p == '?') {
        p++;
        const char *query_start = p;
        while (p < end && *p != '#') p++;
        free((char *)parts.query);
        parts.query = ez_strdup_range(query_start, (size_t)(p - query_start));
    }
    if (p < end && *p == '#') {
        p++;
        free((char *)parts.fragment);
        parts.fragment = ez_strdup_range(p, (size_t)(end - p));
    }
    return (OptUriParts){true, parts};
}

static char *ez_normalize_path(const char *path) {
    if (!path || !*path) return ez_strdup_safe("/");
    bool absolute = path[0] == '/';
    size_t cap = 16;
    size_t count = 0;
    char **parts = (char **)calloc(cap, sizeof(char *));
    if (!parts) return NULL;
    const char *p = path;
    while (*p) {
        while (*p == '/') p++;
        const char *start = p;
        while (*p && *p != '/') p++;
        size_t len = (size_t)(p - start);
        if (len == 0 || (len == 1 && start[0] == '.')) continue;
        if (len == 2 && start[0] == '.' && start[1] == '.') {
            if (count > 0 && strcmp(parts[count - 1], "..") != 0) {
                free(parts[--count]);
                parts[count] = NULL;
            } else if (!absolute) {
                if (count == cap) {
                    cap *= 2;
                    char **next = (char **)realloc(parts, cap * sizeof(char *));
                    if (!next) goto fail;
                    parts = next;
                }
                parts[count++] = ez_strdup_range(start, len);
            }
            continue;
        }
        if (count == cap) {
            cap *= 2;
            char **next = (char **)realloc(parts, cap * sizeof(char *));
            if (!next) goto fail;
            parts = next;
        }
        parts[count++] = ez_strdup_range(start, len);
        if (!parts[count - 1]) goto fail;
    }
    size_t out_len = absolute ? 1 : 0;
    for (size_t i = 0; i < count; ++i) out_len += strlen(parts[i]) + (i > 0 ? 1 : 0);
    if (out_len == 0) out_len = absolute ? 1 : 1;
    char *out = (char *)malloc(out_len + 1);
    if (!out) goto fail;
    size_t offset = 0;
    if (absolute) out[offset++] = '/';
    for (size_t i = 0; i < count; ++i) {
        if (i > 0) out[offset++] = '/';
        size_t len = strlen(parts[i]);
        memcpy(out + offset, parts[i], len);
        offset += len;
    }
    if (offset == 0) out[offset++] = absolute ? '/' : '.';
    out[offset] = '\0';
    for (size_t i = 0; i < count; ++i) free(parts[i]);
    free(parts);
    return out;
fail:
    for (size_t i = 0; i < count; ++i) free(parts[i]);
    free(parts);
    return NULL;
}

OptUriParts uriParse(const char *url) {
    return ez_parse_uri(url);
}

const char *uriBuild(const UriParts *parts) {
    if (!parts || !parts->scheme || !*parts->scheme) return ez_strdup_safe("");
    size_t len = strlen(parts->scheme) + strlen(parts->userInfo ? parts->userInfo : "") + strlen(parts->host ? parts->host : "") + strlen(parts->path ? parts->path : "") + strlen(parts->query ? parts->query : "") + strlen(parts->fragment ? parts->fragment : "") + 32;
    char *out = (char *)malloc(len);
    if (!out) return NULL;
    out[0] = '\0';
    strcat(out, parts->scheme);
    strcat(out, ":");
    if ((parts->host && *parts->host) || (parts->userInfo && *parts->userInfo)) {
        strcat(out, "//");
        if (parts->userInfo && *parts->userInfo) {
            strcat(out, parts->userInfo);
            strcat(out, "@");
        }
        if (parts->host) strcat(out, parts->host);
        if (parts->port >= 0) {
            char port_buf[16];
            snprintf(port_buf, sizeof(port_buf), ":%d", parts->port);
            strcat(out, port_buf);
        }
    }
    if (parts->path && *parts->path) {
        if ((parts->host && *parts->host) && parts->path[0] != '/') strcat(out, "/");
        strcat(out, parts->path);
    } else if (parts->host && *parts->host) {
        strcat(out, "/");
    }
    if (parts->query && *parts->query) {
        strcat(out, "?");
        strcat(out, parts->query);
    }
    if (parts->fragment && *parts->fragment) {
        strcat(out, "#");
        strcat(out, parts->fragment);
    }
    return out;
}

const char *uriNormalize(const char *url) {
    OptUriParts parsed = ez_parse_uri(url);
    if (!parsed.ok) return ez_strdup_safe("");
    char *normal_path = ez_normalize_path(parsed.value.path);
    if (normal_path) parsed.value.path = normal_path;
    return uriBuild(&parsed.value);
}

OptStr uriScheme(const char *url) {
    OptUriParts parsed = ez_parse_uri(url);
    return parsed.ok && parsed.value.scheme && *parsed.value.scheme ? (OptStr){true, parsed.value.scheme} : (OptStr){false, NULL};
}

OptStr uriHost(const char *url) {
    OptUriParts parsed = ez_parse_uri(url);
    return parsed.ok && parsed.value.host && *parsed.value.host ? (OptStr){true, parsed.value.host} : (OptStr){false, NULL};
}

OptI32 uriPort(const char *url) {
    OptUriParts parsed = ez_parse_uri(url);
    return parsed.ok && parsed.value.port >= 0 ? (OptI32){true, parsed.value.port} : (OptI32){false, 0};
}

const char *uriPath(const char *url) {
    OptUriParts parsed = ez_parse_uri(url);
    return parsed.ok ? parsed.value.path : ez_strdup_safe("");
}

OptStr uriQuery(const char *url) {
    OptUriParts parsed = ez_parse_uri(url);
    return parsed.ok && parsed.value.query && *parsed.value.query ? (OptStr){true, parsed.value.query} : (OptStr){false, NULL};
}

OptStr uriFragment(const char *url) {
    OptUriParts parsed = ez_parse_uri(url);
    return parsed.ok && parsed.value.fragment && *parsed.value.fragment ? (OptStr){true, parsed.value.fragment} : (OptStr){false, NULL};
}

const char *uriEncodeQuery(const char *s) { return ez_percent_encode(s, true); }
OptStr uriDecodeQuery(const char *s) { return ez_percent_decode(s, true); }
const char *uriEncodePathSegment(const char *s) { return ez_percent_encode(s, false); }
OptStr uriDecodePathSegment(const char *s) { return ez_percent_decode(s, false); }

OptStr uriQueryGet(const char *query, const char *key) {
    if (!query) query = "";
    if (!key) key = "";
    const char *p = query;
    while (*p) {
        const char *entry_start = p;
        while (*p && *p != '&') p++;
        const char *entry_end = p;
        const char *eq = memchr(entry_start, '=', (size_t)(entry_end - entry_start));
        const char *raw_key_end = eq ? eq : entry_end;
        if (ez_query_key_matches(entry_start, (size_t)(raw_key_end - entry_start), key)) {
            if (!eq) return (OptStr){true, ez_strdup_safe("")};
            return ez_percent_decode_range(eq + 1, (size_t)(entry_end - (eq + 1)), true);
        }
        if (*p == '&') p++;
    }
    return (OptStr){false, NULL};
}

const char *uriQuerySet(const char *query, const char *key, const char *value) {
    if (!query) query = "";
    if (!key) key = "";
    char *encoded_key = ez_percent_encode(key, true);
    char *encoded_value = ez_percent_encode(value, true);
    if (!encoded_key || !encoded_value) {
        free(encoded_key);
        free(encoded_value);
        return NULL;
    }
    size_t out_cap = strlen(query) + strlen(encoded_key) + strlen(encoded_value) + 4;
    char *out = (char *)malloc(out_cap);
    if (!out) {
        free(encoded_key);
        free(encoded_value);
        return NULL;
    }
    out[0] = '\0';
    bool replaced = false;
    const char *p = query;
    while (*p) {
        const char *entry_start = p;
        while (*p && *p != '&') p++;
        const char *entry_end = p;
        const char *eq = memchr(entry_start, '=', (size_t)(entry_end - entry_start));
        const char *raw_key_end = eq ? eq : entry_end;
        if (out[0] != '\0') strcat(out, "&");
        if (!replaced && ez_query_key_matches(entry_start, (size_t)(raw_key_end - entry_start), key)) {
            strcat(out, encoded_key);
            strcat(out, "=");
            strcat(out, encoded_value);
            replaced = true;
        } else {
            strncat(out, entry_start, (size_t)(entry_end - entry_start));
        }
        if (*p == '&') p++;
    }
    if (!replaced) {
        if (out[0] != '\0') strcat(out, "&");
        strcat(out, encoded_key);
        strcat(out, "=");
        strcat(out, encoded_value);
    }
    free(encoded_key);
    free(encoded_value);
    return out;
}
