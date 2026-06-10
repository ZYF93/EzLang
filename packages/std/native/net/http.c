// EzLang std/net/http 原生封装层
// 当前实现明文 HTTP 客户端和基础阻塞式服务端；HTTPS 与完整网络运行时后续补齐。

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET ez_socket_t;
#define EZ_INVALID_SOCKET INVALID_SOCKET
#define ez_close_socket closesocket
#else
#include <errno.h>
#include <netinet/in.h>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int ez_socket_t;
#define EZ_INVALID_SOCKET (-1)
#define ez_close_socket close
#endif

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

typedef struct {
    char ***key_pages;
    char ***value_pages;
    int32_t count;
    int32_t capacity;
    int32_t page_count;
} Dict;

typedef struct {
    int32_t status;
    Dict headers;
    Blob body;
} HttpResponse;

typedef struct {
    const char *method;
    const char *url;
    Dict headers;
    Blob body;
} HttpRequest;

typedef struct {
    int64_t handle;
} HttpServer;

typedef HttpResponse (*RouteHandler)(const HttpRequest *req);

typedef struct {
    char *path;
    RouteHandler handler;
} EzHttpRoute;

typedef struct {
    char *host;
    int32_t port;
    ez_socket_t sock;
    bool running;
    EzHttpRoute *routes;
    size_t route_count;
    size_t route_capacity;
} EzHttpServer;

typedef struct {
    bool ok;
    HttpResponse value;
} OptHttpResponse;

typedef struct {
    char *host;
    char *host_header;
    char *path;
    char port[8];
} EzUrlParts;

static char *ez_strdup_range(const char *src, size_t len) {
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    if (len > 0 && src) memcpy(out, src, len);
    out[len] = '\0';
    return out;
}

static Dict ez_empty_headers(void) {
    return (Dict){0};
}

static const char *ez_dict_key_at(const Dict *dict, int32_t index);
static const char *ez_dict_value_at(const Dict *dict, int32_t index);
static bool ez_append_bytes(uint8_t **buffer, size_t *len, size_t *cap, const uint8_t *chunk, size_t chunk_len);

static void ez_free_headers(Dict *headers) {
    if (!headers || headers->count <= 0) return;
    for (int32_t i = 0; i < headers->count; ++i) {
        free((char *)ez_dict_key_at(headers, i));
        free((char *)ez_dict_value_at(headers, i));
    }
    for (int32_t page = 0; page < headers->page_count; ++page) {
        if (headers->key_pages) free(headers->key_pages[page]);
        if (headers->value_pages) free(headers->value_pages[page]);
    }
    free(headers->key_pages);
    free(headers->value_pages);
    *headers = ez_empty_headers();
}

static char *ez_trim_dup(const char *src, size_t len) {
    while (len > 0 && (*src == ' ' || *src == '\t')) {
        src++;
        len--;
    }
    while (len > 0 && (src[len - 1] == ' ' || src[len - 1] == '\t' || src[len - 1] == '\r')) len--;
    return ez_strdup_range(src, len);
}

static Dict ez_make_headers(char **keys, char **values, size_t count) {
    if (count == 0) return ez_empty_headers();
    size_t page_count = (count + 7) / 8;
    char ***key_pages = (char ***)calloc(page_count, sizeof(char **));
    char ***value_pages = (char ***)calloc(page_count, sizeof(char **));
    if (!key_pages || !value_pages) return ez_empty_headers();
    for (size_t page = 0; page < page_count; ++page) {
        key_pages[page] = (char **)calloc(8, sizeof(char *));
        value_pages[page] = (char **)calloc(8, sizeof(char *));
        if (!key_pages[page] || !value_pages[page]) continue;
        for (size_t slot = 0; slot < 8; ++slot) {
            size_t index = page * 8 + slot;
            if (index >= count) break;
            key_pages[page][slot] = keys[index];
            value_pages[page][slot] = values[index];
        }
    }
    return (Dict){key_pages, value_pages, (int32_t)count, (int32_t)(page_count * 8), (int32_t)page_count};
}

static const char *ez_dict_key_at(const Dict *dict, int32_t index) {
    if (!dict || index < 0 || index >= dict->count || !dict->key_pages) return NULL;
    int32_t page = index / 8;
    int32_t slot = index % 8;
    if (page >= dict->page_count || !dict->key_pages[page]) return NULL;
    return dict->key_pages[page][slot];
}

static const char *ez_dict_value_at(const Dict *dict, int32_t index) {
    if (!dict || index < 0 || index >= dict->count || !dict->value_pages) return NULL;
    int32_t page = index / 8;
    int32_t slot = index % 8;
    if (page >= dict->page_count || !dict->value_pages[page]) return NULL;
    return dict->value_pages[page][slot];
}

static char ez_ascii_lower(char ch) {
    return (ch >= 'A' && ch <= 'Z') ? (char)(ch - 'A' + 'a') : ch;
}

static bool ez_ascii_ieq(const char *left, const char *right) {
    if (!left || !right) return false;
    while (*left && *right) {
        if (ez_ascii_lower(*left) != ez_ascii_lower(*right)) return false;
        left++;
        right++;
    }
    return *left == '\0' && *right == '\0';
}

static bool ez_skip_request_header(const char *key) {
    return ez_ascii_ieq(key, "Host") || ez_ascii_ieq(key, "Connection") || ez_ascii_ieq(key, "Content-Length");
}

static size_t ez_request_headers_len(const Dict *headers) {
    if (!headers || headers->count <= 0) return 0;
    size_t total = 0;
    for (int32_t i = 0; i < headers->count; ++i) {
        const char *key = ez_dict_key_at(headers, i);
        const char *value = ez_dict_value_at(headers, i);
        if (!key || key[0] == '\0' || ez_skip_request_header(key)) continue;
        total += strlen(key) + 2 + strlen(value ? value : "") + 2;
    }
    return total;
}

static size_t ez_append_request_headers(char *request, size_t offset, size_t capacity, const Dict *headers) {
    if (!headers || headers->count <= 0) return offset;
    for (int32_t i = 0; i < headers->count; ++i) {
        const char *key = ez_dict_key_at(headers, i);
        const char *value = ez_dict_value_at(headers, i);
        if (!key || key[0] == '\0' || ez_skip_request_header(key)) continue;
        int written = snprintf(request + offset, capacity - offset, "%s: %s\r\n", key, value ? value : "");
        if (written < 0) return offset;
        offset += (size_t)written;
    }
    return offset;
}

static OptHttpResponse ez_http_none(void) {
    return (OptHttpResponse){false, {0}};
}

static bool ez_blob_valid(const Blob *body) {
    return body && body->size >= 0 && (body->size == 0 || body->data);
}

static int ez_utf8_char_width(unsigned char ch) {
    if (ch < 0x80) return 1;
    if (ch >= 0xC2 && ch <= 0xDF) return 2;
    if (ch >= 0xE0 && ch <= 0xEF) return 3;
    if (ch >= 0xF0 && ch <= 0xF4) return 4;
    return -1;
}

static bool ez_utf8_validate_len(const char *s, size_t len) {
    if (!s) return len == 0;
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

static void ez_url_parts_free(EzUrlParts *parts) {
    if (!parts) return;
    free(parts->host);
    free(parts->host_header);
    free(parts->path);
    parts->host = NULL;
    parts->host_header = NULL;
    parts->path = NULL;
}

static bool ez_http_has_scheme(const char *url) {
    const char *prefix = "http://";
    if (!url) return false;
    for (size_t i = 0; prefix[i] != '\0'; ++i) {
        if (url[i] == '\0' || ez_ascii_lower(url[i]) != prefix[i]) return false;
    }
    return true;
}

static bool ez_http_url_bytes_valid(const char *start, const char *end) {
    if (!start || !end || start > end) return false;
    for (const char *p = start; p < end; ++p) {
        unsigned char ch = (unsigned char)*p;
        if (ch <= 0x20 || ch == 0x7F) return false;
    }
    return true;
}

static bool ez_parse_http_port(const char *start, const char *end, char out[8]) {
    if (!start || !end || start >= end || !out) return false;
    int32_t value = 0;
    for (const char *p = start; p < end; ++p) {
        if (*p < '0' || *p > '9') return false;
        int32_t digit = (int32_t)(*p - '0');
        if (value > (65535 - digit) / 10) return false;
        value = value * 10 + digit;
    }
    snprintf(out, 8, "%d", (int)value);
    return true;
}

static char *ez_make_host_header(const char *host, const char *port, bool has_port) {
    if (!host || host[0] == '\0') return NULL;
    if (!has_port) return ez_strdup_range(host, strlen(host));
    size_t host_len = strlen(host);
    size_t port_len = strlen(port ? port : "");
    if (port_len == 0 || host_len > SIZE_MAX - port_len - 2) return NULL;
    char *out = (char *)malloc(host_len + port_len + 2);
    if (!out) return NULL;
    memcpy(out, host, host_len);
    out[host_len] = ':';
    memcpy(out + host_len + 1, port, port_len);
    out[host_len + port_len + 1] = '\0';
    return out;
}

static bool ez_parse_http_url(const char *url, EzUrlParts *out) {
    size_t prefix_len = strlen("http://");
    if (!out) return false;
    *out = (EzUrlParts){0};
    if (!ez_http_has_scheme(url)) return false;
    const char *host_start = url + prefix_len;
    const char *fragment_start = strchr(host_start, '#');
    const char *url_end = fragment_start ? fragment_start : url + strlen(url);
    const char *authority_end = host_start;
    while (authority_end < url_end && *authority_end != '/' && *authority_end != '?') authority_end++;
    if (authority_end == host_start || !ez_http_url_bytes_valid(host_start, authority_end)) return false;

    for (const char *scan = host_start; scan < authority_end; ++scan) {
        if (*scan == '@') host_start = scan + 1;
    }
    if (host_start >= authority_end) return false;

    bool has_port = false;
    char *host_for_header = NULL;
    strcpy(out->port, "80");

    if (*host_start == '[') {
        const char *close = memchr(host_start, ']', (size_t)(authority_end - host_start));
        if (!close || close == host_start + 1) return false;
        const char *after = close + 1;
        if (after < authority_end) {
            if (*after != ':' || !ez_parse_http_port(after + 1, authority_end, out->port)) return false;
            has_port = true;
        }
        out->host = ez_strdup_range(host_start + 1, (size_t)(close - host_start - 1));
        host_for_header = ez_strdup_range(host_start, (size_t)(close - host_start + 1));
    } else {
        const char *colon = NULL;
        for (const char *scan = host_start; scan < authority_end; ++scan) {
            if (*scan == '[' || *scan == ']') return false;
            if (*scan == ':') {
                if (colon) return false;
                colon = scan;
            }
        }
        const char *host_end = colon ? colon : authority_end;
        if (host_end == host_start) return false;
        if (colon) {
            if (!ez_parse_http_port(colon + 1, authority_end, out->port)) return false;
            has_port = true;
        }
        out->host = ez_strdup_range(host_start, (size_t)(host_end - host_start));
        host_for_header = ez_strdup_range(host_start, (size_t)(host_end - host_start));
    }
    if (!out->host || out->host[0] == '\0' || !host_for_header) goto fail;
    out->host_header = ez_make_host_header(host_for_header, out->port, has_port);
    free(host_for_header);
    host_for_header = NULL;
    if (!out->host_header) goto fail;

    if (authority_end < url_end && !ez_http_url_bytes_valid(authority_end, url_end)) goto fail;
    if (authority_end < url_end && *authority_end == '/') {
        out->path = ez_strdup_range(authority_end, (size_t)(url_end - authority_end));
    } else if (authority_end < url_end && *authority_end == '?') {
        size_t query_len = (size_t)(url_end - authority_end);
        out->path = (char *)malloc(query_len + 2);
        if (out->path) {
            out->path[0] = '/';
            memcpy(out->path + 1, authority_end, query_len);
            out->path[query_len + 1] = '\0';
        }
    } else {
        out->path = ez_strdup_range("/", 1);
    }
    if (out->path) return true;

fail:
    free(host_for_header);
    ez_url_parts_free(out);
    return false;
}

static bool ez_http_init_sockets(void) {
#if defined(_WIN32)
    static bool initialized = false;
    if (initialized) return true;
    WSADATA data;
    if (WSAStartup(MAKEWORD(2, 2), &data) != 0) return false;
    initialized = true;
#endif
    return true;
}

static ez_socket_t ez_http_connect(const char *host, const char *port) {
    if (!ez_http_init_sockets()) return EZ_INVALID_SOCKET;
    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    struct addrinfo *result = NULL;
    if (getaddrinfo(host, port, &hints, &result) != 0) return EZ_INVALID_SOCKET;
    ez_socket_t sock = EZ_INVALID_SOCKET;
    for (struct addrinfo *it = result; it; it = it->ai_next) {
        sock = (ez_socket_t)socket(it->ai_family, it->ai_socktype, it->ai_protocol);
        if (sock == EZ_INVALID_SOCKET) continue;
        if (connect(sock, it->ai_addr, (int)it->ai_addrlen) == 0) break;
        ez_close_socket(sock);
        sock = EZ_INVALID_SOCKET;
    }
    freeaddrinfo(result);
    return sock;
}

static EzHttpServer *ez_server_from_value(const HttpServer *server) {
    if (!server || server->handle == 0) return NULL;
    return (EzHttpServer *)(uintptr_t)server->handle;
}

static void ez_http_server_free(EzHttpServer *server) {
    if (!server) return;
    if (server->sock != EZ_INVALID_SOCKET) ez_close_socket(server->sock);
    for (size_t i = 0; i < server->route_count; ++i) free(server->routes[i].path);
    free(server->routes);
    free(server->host);
    free(server);
}

static ez_socket_t ez_http_listen_socket(const char *host, int32_t port) {
    if (!ez_http_init_sockets() || port < 0 || port > 65535) return EZ_INVALID_SOCKET;
    char port_text[16];
    snprintf(port_text, sizeof(port_text), "%d", (int)port);

    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_PASSIVE;

    struct addrinfo *result = NULL;
    const char *bind_host = (host && host[0]) ? host : NULL;
    if (getaddrinfo(bind_host, port_text, &hints, &result) != 0) return EZ_INVALID_SOCKET;

    ez_socket_t sock = EZ_INVALID_SOCKET;
    for (struct addrinfo *it = result; it; it = it->ai_next) {
        sock = (ez_socket_t)socket(it->ai_family, it->ai_socktype, it->ai_protocol);
        if (sock == EZ_INVALID_SOCKET) continue;
        int yes = 1;
        setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, (const char *)&yes, sizeof(yes));
        if (bind(sock, it->ai_addr, (int)it->ai_addrlen) == 0 && listen(sock, 16) == 0) break;
        ez_close_socket(sock);
        sock = EZ_INVALID_SOCKET;
    }
    freeaddrinfo(result);
    return sock;
}

static bool ez_send_all(ez_socket_t sock, const char *data, size_t len) {
    size_t sent = 0;
    while (sent < len) {
#if defined(_WIN32)
        int n = send(sock, data + sent, (int)(len - sent), 0);
#else
        ssize_t n = send(sock, data + sent, len - sent, 0);
#endif
        if (n <= 0) return false;
        sent += (size_t)n;
    }
    return true;
}

static bool ez_recv_into_buffer(ez_socket_t sock, uint8_t **buffer, size_t *len, size_t *cap) {
    uint8_t chunk[4096];
#if defined(_WIN32)
    int n = recv(sock, (char *)chunk, (int)sizeof(chunk), 0);
#else
    ssize_t n = recv(sock, chunk, sizeof(chunk), 0);
#endif
    if (n <= 0) return false;
    return ez_append_bytes(buffer, len, cap, chunk, (size_t)n);
}

static const uint8_t *ez_find_header_end(const uint8_t *data, size_t len) {
    if (!data) return NULL;
    for (size_t i = 0; i + 3 < len; ++i) {
        if (data[i] == '\r' && data[i + 1] == '\n' && data[i + 2] == '\r' && data[i + 3] == '\n') return data + i + 4;
    }
    return NULL;
}

static bool ez_append_bytes(uint8_t **buffer, size_t *len, size_t *cap, const uint8_t *chunk, size_t chunk_len) {
    if (*len + chunk_len > *cap) {
        size_t next_cap = *cap ? *cap : 4096;
        while (*len + chunk_len > next_cap) next_cap *= 2;
        uint8_t *next = (uint8_t *)realloc(*buffer, next_cap);
        if (!next) return false;
        *buffer = next;
        *cap = next_cap;
    }
    memcpy(*buffer + *len, chunk, chunk_len);
    *len += chunk_len;
    return true;
}

static Blob ez_response_body(uint8_t *response, size_t response_len) {
    uint8_t *body_start = NULL;
    for (size_t i = 0; i + 3 < response_len; ++i) {
        if (response[i] == '\r' && response[i + 1] == '\n' && response[i + 2] == '\r' && response[i + 3] == '\n') {
            body_start = response + i + 4;
            break;
        }
    }
    if (!body_start) return (Blob){NULL, 0};
    size_t body_len = response_len - (size_t)(body_start - response);
    uint8_t *body = body_len == 0 ? NULL : (uint8_t *)malloc(body_len);
    if (body_len > 0 && !body) return (Blob){NULL, 0};
    if (body_len > 0) memcpy(body, body_start, body_len);
    return (Blob){body, (int64_t)body_len};
}

static const uint8_t *ez_response_body_start(const uint8_t *response, size_t response_len) {
    if (!response) return NULL;
    for (size_t i = 0; i + 3 < response_len; ++i) {
        if (response[i] == '\r' && response[i + 1] == '\n' && response[i + 2] == '\r' && response[i + 3] == '\n') {
            return response + i + 4;
        }
    }
    return NULL;
}

static const char *ez_header_value_at(const Dict *headers, const char *name) {
    if (!headers || !name) return NULL;
    for (int32_t i = 0; i < headers->count; ++i) {
        const char *key = ez_dict_key_at(headers, i);
        if (ez_ascii_ieq(key, name)) return ez_dict_value_at(headers, i);
    }
    return NULL;
}

static bool ez_ascii_contains_word_ci(const char *text, const char *needle) {
    if (!text || !needle || needle[0] == '\0') return false;
    size_t nlen = strlen(needle);
    for (const char *it = text; *it; ++it) {
        size_t i = 0;
        while (i < nlen && it[i] && ez_ascii_lower(it[i]) == ez_ascii_lower(needle[i])) i++;
        if (i == nlen) return true;
    }
    return false;
}

static int ez_hex_value(uint8_t ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    return -1;
}

static bool ez_decode_chunked_body(const uint8_t *body, size_t body_len, Blob *out) {
    if (!out) return false;
    *out = (Blob){NULL, 0};
    size_t pos = 0;
    size_t out_len = 0;
    size_t out_cap = 0;
    uint8_t *data = NULL;
    for (;;) {
        uint64_t chunk_size = 0;
        bool saw_digit = false;
        while (pos < body_len) {
            uint8_t ch = body[pos++];
            if (ch == ';') {
                while (pos < body_len && body[pos] != '\r' && body[pos] != '\n') pos++;
                break;
            }
            if (ch == '\r' || ch == '\n') {
                pos--;
                break;
            }
            int digit = ez_hex_value(ch);
            if (digit < 0) {
                free(data);
                return false;
            }
            saw_digit = true;
            if (chunk_size > (UINT64_MAX - (uint64_t)digit) / 16) {
                free(data);
                return false;
            }
            chunk_size = chunk_size * 16 + (uint64_t)digit;
        }
        if (!saw_digit || pos >= body_len || body[pos++] != '\r' || pos >= body_len || body[pos++] != '\n') {
            free(data);
            return false;
        }
        if (chunk_size == 0) {
            out->data = data;
            out->size = (int64_t)out_len;
            return true;
        }
        if (chunk_size > SIZE_MAX || pos > body_len || (size_t)chunk_size > body_len - pos) {
            free(data);
            return false;
        }
        if (out_len > SIZE_MAX - (size_t)chunk_size) {
            free(data);
            return false;
        }
        size_t next_len = out_len + (size_t)chunk_size;
        if (next_len > out_cap) {
            size_t next_cap = out_cap ? out_cap : 4096;
            while (next_len > next_cap) next_cap *= 2;
            uint8_t *grown = (uint8_t *)realloc(data, next_cap);
            if (!grown) {
                free(data);
                return false;
            }
            data = grown;
            out_cap = next_cap;
        }
        memcpy(data + out_len, body + pos, (size_t)chunk_size);
        out_len = next_len;
        pos += (size_t)chunk_size;
        if (pos >= body_len || body[pos++] != '\r' || pos >= body_len || body[pos++] != '\n') {
            free(data);
            return false;
        }
    }
}

static Dict ez_response_headers(const uint8_t *response, size_t response_len) {
    if (!response || response_len == 0) return ez_empty_headers();
    const char *start = (const char *)response;
    const char *end = start + response_len;
    const char *line_end = memchr(start, '\n', (size_t)(end - start));
    if (!line_end) return ez_empty_headers();
    const char *line_start = line_end + 1;

    char **keys = NULL;
    char **values = NULL;
    size_t count = 0;
    size_t capacity = 0;
    while (line_start < end) {
        line_end = memchr(line_start, '\n', (size_t)(end - line_start));
        if (!line_end) break;
        size_t line_len = (size_t)(line_end - line_start);
        while (line_len > 0 && line_start[line_len - 1] == '\r') line_len--;
        if (line_len == 0) break;

        const char *colon = memchr(line_start, ':', line_len);
        if (colon && colon != line_start) {
            if (count == capacity) {
                size_t next_capacity = capacity ? capacity * 2 : 8;
                char **next_keys = (char **)realloc(keys, next_capacity * sizeof(char *));
                if (!next_keys) break;
                keys = next_keys;
                char **next_values = (char **)realloc(values, next_capacity * sizeof(char *));
                if (!next_values) break;
                values = next_values;
                capacity = next_capacity;
            }
            keys[count] = ez_trim_dup(line_start, (size_t)(colon - line_start));
            values[count] = ez_trim_dup(colon + 1, line_len - (size_t)(colon + 1 - line_start));
            if (keys[count] && values[count]) count++;
        }
        line_start = line_end + 1;
    }

    Dict result = ez_make_headers(keys, values, count);
    free(keys);
    free(values);
    return result;
}

static int32_t ez_response_status(const uint8_t *response, size_t response_len) {
    if (!response || response_len < 12) return 0;
    const char *text = (const char *)response;
    const char *space = memchr(text, ' ', response_len);
    if (!space || space + 4 > text + response_len) return 0;
    return (int32_t)strtol(space + 1, NULL, 10);
}

static int64_t ez_content_length_from_headers(const Dict *headers) {
    const char *value = ez_header_value_at(headers, "Content-Length");
    if (!value || value[0] == '\0') return 0;
    char *end = NULL;
    long long parsed = strtoll(value, &end, 10);
    if (!end || end == value || parsed < 0) return 0;
    return (int64_t)parsed;
}

static bool ez_read_http_request(ez_socket_t sock, uint8_t **out, size_t *out_len, size_t *header_len) {
    uint8_t *buffer = NULL;
    size_t len = 0;
    size_t cap = 0;
    const uint8_t *body_start = NULL;
    while (!body_start) {
        if (!ez_recv_into_buffer(sock, &buffer, &len, &cap)) {
            free(buffer);
            return false;
        }
        body_start = ez_find_header_end(buffer, len);
        if (len > 1024 * 1024) {
            free(buffer);
            return false;
        }
    }

    size_t headers_len = (size_t)(body_start - buffer);
    Dict headers = ez_response_headers(buffer, headers_len);
    int64_t body_len = ez_content_length_from_headers(&headers);
    ez_free_headers(&headers);
    if (body_len < 0 || (uint64_t)body_len > (uint64_t)SIZE_MAX) {
        free(buffer);
        return false;
    }
    while (len - headers_len < (size_t)body_len) {
        if (!ez_recv_into_buffer(sock, &buffer, &len, &cap)) {
            free(buffer);
            return false;
        }
        if (len > 16 * 1024 * 1024) {
            free(buffer);
            return false;
        }
    }
    *out = buffer;
    *out_len = len;
    *header_len = headers_len;
    return true;
}

static bool ez_parse_server_request(uint8_t *raw, size_t raw_len, size_t header_len, HttpRequest *out) {
    if (!raw || !out || header_len == 0 || header_len > raw_len) return false;
    char *text = (char *)raw;
    char *line_end = memchr(text, '\n', header_len);
    if (!line_end) return false;
    size_t line_len = (size_t)(line_end - text);
    if (line_len > 0 && text[line_len - 1] == '\r') line_len--;
    char *method_end = memchr(text, ' ', line_len);
    if (!method_end) return false;
    char *path_start = method_end + 1;
    size_t remaining = line_len - (size_t)(path_start - text);
    char *path_end = memchr(path_start, ' ', remaining);
    if (!path_end) return false;

    char *method = ez_strdup_range(text, (size_t)(method_end - text));
    char *url = ez_strdup_range(path_start, (size_t)(path_end - path_start));
    if (!method || !url) {
        free(method);
        free(url);
        return false;
    }
    Dict headers = ez_response_headers(raw, header_len);
    size_t body_size = raw_len - header_len;
    uint8_t *body = NULL;
    if (body_size > 0) {
        body = (uint8_t *)malloc(body_size);
        if (!body) {
            free(method);
            free(url);
            ez_free_headers(&headers);
            return false;
        }
        memcpy(body, raw + header_len, body_size);
    }
    *out = (HttpRequest){method, url, headers, {body, (int64_t)body_size}};
    return true;
}

static void ez_free_server_request(HttpRequest *req) {
    if (!req) return;
    free((char *)req->method);
    free((char *)req->url);
    ez_free_headers(&req->headers);
    free(req->body.data);
    *req = (HttpRequest){0};
}

static RouteHandler ez_http_find_route(EzHttpServer *server, const char *url) {
    if (!server || !url) return NULL;
    size_t path_len = strcspn(url, "?#");
    for (size_t i = 0; i < server->route_count; ++i) {
        const char *path = server->routes[i].path;
        if (path && strlen(path) == path_len && strncmp(path, url, path_len) == 0) return server->routes[i].handler;
    }
    return NULL;
}

static bool ez_skip_response_header(const char *key) {
    return ez_ascii_ieq(key, "Content-Length") || ez_ascii_ieq(key, "Connection");
}

static size_t ez_response_headers_len(const Dict *headers) {
    if (!headers || headers->count <= 0) return 0;
    size_t total = 0;
    for (int32_t i = 0; i < headers->count; ++i) {
        const char *key = ez_dict_key_at(headers, i);
        const char *value = ez_dict_value_at(headers, i);
        if (!key || key[0] == '\0' || ez_skip_response_header(key)) continue;
        total += strlen(key) + 2 + strlen(value ? value : "") + 2;
    }
    return total;
}

static size_t ez_append_response_headers(char *response, size_t offset, size_t capacity, const Dict *headers) {
    if (!headers || headers->count <= 0) return offset;
    for (int32_t i = 0; i < headers->count; ++i) {
        const char *key = ez_dict_key_at(headers, i);
        const char *value = ez_dict_value_at(headers, i);
        if (!key || key[0] == '\0' || ez_skip_response_header(key)) continue;
        int written = snprintf(response + offset, capacity - offset, "%s: %s\r\n", key, value ? value : "");
        if (written < 0) return offset;
        offset += (size_t)written;
    }
    return offset;
}

static bool ez_send_http_response(ez_socket_t sock, const HttpResponse *response) {
    HttpResponse fallback = {404, ez_empty_headers(), {(uint8_t *)"not found", 9}};
    const HttpResponse *value = response ? response : &fallback;
    int32_t status = value->status > 0 ? value->status : 200;
    int64_t body_size = 0;
    if (value->body.size > 0 && value->body.data) body_size = value->body.size;
    size_t headers_len = ez_response_headers_len(&value->headers);
    int prefix_len = snprintf(NULL, 0, "HTTP/1.1 %d OK\r\nConnection: close\r\nContent-Length: %lld\r\n",
        (int)status, (long long)body_size);
    if (prefix_len < 0) return false;
    size_t response_size = (size_t)prefix_len + headers_len + 2;
    char *head = (char *)malloc(response_size + 1);
    if (!head) return false;
    size_t offset = (size_t)snprintf(head, response_size + 1, "HTTP/1.1 %d OK\r\nConnection: close\r\nContent-Length: %lld\r\n",
        (int)status, (long long)body_size);
    offset = ez_append_response_headers(head, offset, response_size + 1, &value->headers);
    memcpy(head + offset, "\r\n", 2);
    offset += 2;
    head[offset] = '\0';
    bool ok = ez_send_all(sock, head, offset);
    free(head);
    if (ok && body_size > 0) ok = ez_send_all(sock, (const char *)value->body.data, (size_t)body_size);
    return ok;
}

static bool ez_http_handle_client(EzHttpServer *server, ez_socket_t client) {
    uint8_t *raw = NULL;
    size_t raw_len = 0;
    size_t header_len = 0;
    if (!ez_read_http_request(client, &raw, &raw_len, &header_len)) return false;
    HttpRequest req = {0};
    if (!ez_parse_server_request(raw, raw_len, header_len, &req)) {
        free(raw);
        return false;
    }
    RouteHandler handler = ez_http_find_route(server, req.url);
    HttpResponse response = {404, ez_empty_headers(), {(uint8_t *)"not found", 9}};
    if (handler) response = handler(&req);
    bool ok = ez_send_http_response(client, &response);
    ez_free_server_request(&req);
    free(raw);
    return ok;
}

static OptHttpResponse ez_http_fetch(const char *method, const char *url, const Dict *headers, const Blob *body) {
    int64_t body_size = 0;
    if (body) {
        if (!ez_blob_valid(body) || (uint64_t)body->size > (uint64_t)SIZE_MAX) return ez_http_none();
        body_size = body->size;
    }
    EzUrlParts parts = {0};
    if (!ez_parse_http_url(url, &parts)) return ez_http_none();
    ez_socket_t sock = ez_http_connect(parts.host, parts.port);
    if (sock == EZ_INVALID_SOCKET) {
        ez_url_parts_free(&parts);
        return ez_http_none();
    }

    const char *verb = method && method[0] ? method : "GET";
    size_t headers_len = ez_request_headers_len(headers);
    int req_len = snprintf(NULL, 0,
        "%s %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\nContent-Length: %lld\r\n",
        verb, parts.path, parts.host_header, (long long)body_size);
    if (req_len < 0) {
        ez_close_socket(sock);
        ez_url_parts_free(&parts);
        return ez_http_none();
    }
    size_t request_size = (size_t)req_len + headers_len + 2;
    char *request = (char *)malloc(request_size + 1);
    if (!request) {
        ez_close_socket(sock);
        ez_url_parts_free(&parts);
        return ez_http_none();
    }
    size_t offset = (size_t)snprintf(request, request_size + 1,
        "%s %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\nContent-Length: %lld\r\n",
        verb, parts.path, parts.host_header, (long long)body_size);
    offset = ez_append_request_headers(request, offset, request_size + 1, headers);
    memcpy(request + offset, "\r\n", 2);
    offset += 2;
    request[offset] = '\0';

    bool ok = ez_send_all(sock, request, offset);
    if (ok && body_size > 0) ok = ez_send_all(sock, (const char *)body->data, (size_t)body_size);
    free(request);
    ez_url_parts_free(&parts);
    if (!ok) {
        ez_close_socket(sock);
        return ez_http_none();
    }

    uint8_t *response = NULL;
    size_t response_len = 0;
    size_t response_cap = 0;
    uint8_t chunk[4096];
    for (;;) {
#if defined(_WIN32)
        int n = recv(sock, (char *)chunk, (int)sizeof(chunk), 0);
#else
        ssize_t n = recv(sock, chunk, sizeof(chunk), 0);
#endif
        if (n < 0) {
            free(response);
            ez_close_socket(sock);
            return ez_http_none();
        }
        if (n == 0) break;
        if (!ez_append_bytes(&response, &response_len, &response_cap, chunk, (size_t)n)) {
            free(response);
            ez_close_socket(sock);
            return ez_http_none();
        }
    }
    ez_close_socket(sock);
    if (!response || response_len == 0) {
        free(response);
        return ez_http_none();
    }

    int32_t status = ez_response_status(response, response_len);
    if (status == 0) {
        free(response);
        return ez_http_none();
    }
    Dict response_headers = ez_response_headers(response, response_len);
    Blob response_body = {NULL, 0};
    const char *transfer_encoding = ez_header_value_at(&response_headers, "Transfer-Encoding");
    if (ez_ascii_contains_word_ci(transfer_encoding, "chunked")) {
        const uint8_t *body_start = ez_response_body_start(response, response_len);
        if (!body_start || !ez_decode_chunked_body(body_start, response_len - (size_t)(body_start - response), &response_body)) {
            free(response);
            return ez_http_none();
        }
    } else {
        response_body = ez_response_body(response, response_len);
    }
    free(response);

    HttpResponse value = {status, response_headers, response_body};
    return (OptHttpResponse){true, value};
}

OptHttpResponse fetch(const char *url) {
    return ez_http_fetch("GET", url, NULL, NULL);
}

OptHttpResponse fetchEx(const HttpRequest *req) {
    if (!req) return ez_http_none();
    return ez_http_fetch(req->method, req->url, &req->headers, &req->body);
}

HttpServer createServer(const char *host, int32_t port) {
    EzHttpServer *server = (EzHttpServer *)calloc(1, sizeof(EzHttpServer));
    if (!server) return (HttpServer){0};
    const char *bind_host = host && host[0] ? host : "127.0.0.1";
    server->host = ez_strdup_range(bind_host, strlen(bind_host));
    server->port = port;
    server->sock = EZ_INVALID_SOCKET;
    if (!server->host) {
        free(server);
        return (HttpServer){0};
    }
    return (HttpServer){(int64_t)(uintptr_t)server};
}

void HttpServer_on(HttpServer *value, const char *path, RouteHandler handler) {
    EzHttpServer *server = ez_server_from_value(value);
    if (!server || !path || !handler) return;
    for (size_t i = 0; i < server->route_count; ++i) {
        if (server->routes[i].path && strcmp(server->routes[i].path, path) == 0) {
            server->routes[i].handler = handler;
            return;
        }
    }
    if (server->route_count == server->route_capacity) {
        size_t next_capacity = server->route_capacity ? server->route_capacity * 2 : 4;
        EzHttpRoute *next = (EzHttpRoute *)realloc(server->routes, next_capacity * sizeof(EzHttpRoute));
        if (!next) return;
        server->routes = next;
        server->route_capacity = next_capacity;
    }
    char *path_copy = ez_strdup_range(path, strlen(path));
    if (!path_copy) return;
    server->routes[server->route_count++] = (EzHttpRoute){path_copy, handler};
}

void HttpServer_start(HttpServer *value) {
    EzHttpServer *server = ez_server_from_value(value);
    if (!server) return;
    if (server->sock == EZ_INVALID_SOCKET) server->sock = ez_http_listen_socket(server->host, server->port);
    if (server->sock == EZ_INVALID_SOCKET) return;
    server->running = true;
    while (server->running) {
#if defined(_WIN32)
        ez_socket_t client = (ez_socket_t)accept(server->sock, NULL, NULL);
#else
        ez_socket_t client = accept(server->sock, NULL, NULL);
#endif
        if (client == EZ_INVALID_SOCKET) break;
        ez_http_handle_client(server, client);
        ez_close_socket(client);
    }
    ez_http_server_free(server);
    value->handle = 0;
}

void HttpServer_stop(HttpServer *value) {
    EzHttpServer *server = ez_server_from_value(value);
    if (!server) return;
    bool was_running = server->running;
    server->running = false;
    if (server->sock != EZ_INVALID_SOCKET) {
        ez_close_socket(server->sock);
        server->sock = EZ_INVALID_SOCKET;
    }
    if (was_running) {
        value->handle = 0;
        return;
    }
    ez_http_server_free(server);
    value->handle = 0;
}

const char *HttpResponse_text(const HttpResponse *value) {
    if (!value) return ez_strdup_range("", 0);
    int64_t size = value->body.size;
    if (size <= 0 || !value->body.data) return ez_strdup_range("", 0);
    if ((uint64_t)size > (uint64_t)SIZE_MAX) return ez_strdup_range("", 0);
    if (memchr(value->body.data, 0, (size_t)size)) return ez_strdup_range("", 0);
    if (!ez_utf8_validate_len((const char *)value->body.data, (size_t)size)) return ez_strdup_range("", 0);
    return ez_strdup_range((const char *)value->body.data, (size_t)size);
}
