// EzLang std/net/http 原生封装层
// 当前实现明文 HTTP/1.0 客户端；HTTPS 与完整网络运行时后续补齐。
// HTTP 服务端明确不支持：createServer 返回 handle = 0。

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

enum { EZ_HTTP_SERVER_UNSUPPORTED_HANDLE = 0 };

typedef struct {
    bool ok;
    HttpResponse value;
} OptHttpResponse;

typedef struct {
    char *host;
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

static void ez_url_parts_free(EzUrlParts *parts) {
    if (!parts) return;
    free(parts->host);
    free(parts->path);
    parts->host = NULL;
    parts->path = NULL;
}

static bool ez_parse_http_url(const char *url, EzUrlParts *out) {
    const char *prefix = "http://";
    size_t prefix_len = strlen(prefix);
    if (!url || strncmp(url, prefix, prefix_len) != 0) return false;
    const char *host_start = url + prefix_len;
    const char *path_start = strchr(host_start, '/');
    const char *host_end = path_start ? path_start : url + strlen(url);
    if (host_end == host_start) return false;

    const char *port_start = NULL;
    const char *colon = memchr(host_start, ':', (size_t)(host_end - host_start));
    if (colon) {
        port_start = colon + 1;
        if (port_start == host_end || (size_t)(host_end - port_start) >= sizeof(out->port)) return false;
        out->host = ez_strdup_range(host_start, (size_t)(colon - host_start));
        memcpy(out->port, port_start, (size_t)(host_end - port_start));
        out->port[host_end - port_start] = '\0';
    } else {
        out->host = ez_strdup_range(host_start, (size_t)(host_end - host_start));
        strcpy(out->port, "80");
    }
    if (!out->host || out->host[0] == '\0') return false;
    out->path = path_start ? ez_strdup_range(path_start, strlen(path_start)) : ez_strdup_range("/", 1);
    return out->path != NULL;
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

static OptHttpResponse ez_http_fetch(const char *method, const char *url, const Dict *headers, const Blob *body) {
    EzUrlParts parts = {0};
    if (!ez_parse_http_url(url, &parts)) return ez_http_none();
    ez_socket_t sock = ez_http_connect(parts.host, parts.port);
    if (sock == EZ_INVALID_SOCKET) {
        ez_url_parts_free(&parts);
        return ez_http_none();
    }

    const char *verb = method && method[0] ? method : "GET";
    int64_t body_size = body && body->data && body->size > 0 ? body->size : 0;
    size_t headers_len = ez_request_headers_len(headers);
    int req_len = snprintf(NULL, 0,
        "%s %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\nContent-Length: %lld\r\n",
        verb, parts.path, parts.host, (long long)body_size);
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
        verb, parts.path, parts.host, (long long)body_size);
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
    Blob response_body = ez_response_body(response, response_len);
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
    (void)host;
    (void)port;
    return (HttpServer){EZ_HTTP_SERVER_UNSUPPORTED_HANDLE};
}

const char *HttpResponse_text(const HttpResponse *value) {
    if (!value) return ez_strdup_range("", 0);
    int64_t size = value->body.size;
    if (size <= 0 || !value->body.data) return ez_strdup_range("", 0);
    return ez_strdup_range((const char *)value->body.data, (size_t)size);
}
