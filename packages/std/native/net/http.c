// EzLang std/net/http 原生封装层
// 当前实现明文 HTTP/1.0 客户端；HTTPS、服务端与完整 headers 映射后续补齐。

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

static int32_t ez_response_status(const uint8_t *response, size_t response_len) {
    if (!response || response_len < 12) return 0;
    const char *text = (const char *)response;
    const char *space = memchr(text, ' ', response_len);
    if (!space || space + 4 > text + response_len) return 0;
    return (int32_t)strtol(space + 1, NULL, 10);
}

static OptHttpResponse ez_http_fetch(const char *method, const char *url, const Blob *body) {
    EzUrlParts parts = {0};
    if (!ez_parse_http_url(url, &parts)) return ez_http_none();
    ez_socket_t sock = ez_http_connect(parts.host, parts.port);
    if (sock == EZ_INVALID_SOCKET) {
        ez_url_parts_free(&parts);
        return ez_http_none();
    }

    const char *verb = method && method[0] ? method : "GET";
    int body_size = body && body->data && body->size > 0 ? (int)body->size : 0;
    int req_len = snprintf(NULL, 0,
        "%s %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\nContent-Length: %d\r\n\r\n",
        verb, parts.path, parts.host, body_size);
    char *request = (char *)malloc((size_t)req_len + 1);
    if (!request) {
        ez_close_socket(sock);
        ez_url_parts_free(&parts);
        return ez_http_none();
    }
    snprintf(request, (size_t)req_len + 1,
        "%s %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\nContent-Length: %d\r\n\r\n",
        verb, parts.path, parts.host, body_size);

    bool ok = ez_send_all(sock, request, (size_t)req_len);
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
    Blob response_body = ez_response_body(response, response_len);
    free(response);
    if (status == 0) return ez_http_none();

    HttpResponse value = {status, ez_empty_headers(), response_body};
    return (OptHttpResponse){true, value};
}

OptHttpResponse fetch(const char *url) {
    return ez_http_fetch("GET", url, NULL);
}

OptHttpResponse fetchEx(const HttpRequest *req) {
    if (!req) return ez_http_none();
    return ez_http_fetch(req->method, req->url, &req->body);
}

HttpServer createServer(const char *host, int32_t port) {
    (void)host;
    (void)port;
    return (HttpServer){0};
}
