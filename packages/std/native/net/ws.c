// EzLang std/net/ws 原生封装层
// 当前实现 ws:// 握手和基础单帧消息收发；wss、分片和异步挂起后续补齐。

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
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int ez_socket_t;
#define EZ_INVALID_SOCKET (-1)
#define ez_close_socket close
#endif

typedef struct { int64_t handle; } WsConn;
typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { bool ok; WsConn value; } OptWsConn;
typedef struct { bool ok; Blob value; } OptBlob;

typedef struct {
    char *host;
    char *path;
    char port[8];
} EzWsUrl;

static char *ez_strdup_range(const char *src, size_t len) {
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    if (len > 0 && src) memcpy(out, src, len);
    out[len] = '\0';
    return out;
}

static OptWsConn ez_ws_none(void) {
    return (OptWsConn){false, {0}};
}

static OptBlob ez_ws_none_blob(void) {
    return (OptBlob){false, {NULL, 0}};
}

static OptBlob ez_ws_empty_blob(void) {
    return (OptBlob){true, {NULL, 0}};
}

static ez_socket_t ez_socket_from_handle(int64_t handle) {
    if (handle == 0) return EZ_INVALID_SOCKET;
    return (ez_socket_t)handle;
}

static void ez_ws_url_free(EzWsUrl *url) {
    if (!url) return;
    free(url->host);
    free(url->path);
    url->host = NULL;
    url->path = NULL;
}

static bool ez_parse_ws_url(const char *url, EzWsUrl *out) {
    const char *prefix = "ws://";
    size_t prefix_len = strlen(prefix);
    if (!url || strncmp(url, prefix, prefix_len) != 0) return false;
    const char *host_start = url + prefix_len;
    const char *path_start = strchr(host_start, '/');
    const char *host_end = path_start ? path_start : url + strlen(url);
    if (host_end == host_start) return false;
    const char *colon = memchr(host_start, ':', (size_t)(host_end - host_start));
    if (colon) {
        if (colon + 1 == host_end || (size_t)(host_end - colon - 1) >= sizeof(out->port)) return false;
        out->host = ez_strdup_range(host_start, (size_t)(colon - host_start));
        memcpy(out->port, colon + 1, (size_t)(host_end - colon - 1));
        out->port[host_end - colon - 1] = '\0';
    } else {
        out->host = ez_strdup_range(host_start, (size_t)(host_end - host_start));
        strcpy(out->port, "80");
    }
    if (!out->host || out->host[0] == '\0') return false;
    out->path = path_start ? ez_strdup_range(path_start, strlen(path_start)) : ez_strdup_range("/", 1);
    return out->path != NULL;
}

static bool ez_net_init(void) {
#if defined(_WIN32)
    static bool initialized = false;
    if (initialized) return true;
    WSADATA data;
    if (WSAStartup(MAKEWORD(2, 2), &data) != 0) return false;
    initialized = true;
#endif
    return true;
}

static ez_socket_t ez_connect_socket(const char *host, const char *port) {
    if (!ez_net_init()) return EZ_INVALID_SOCKET;
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

static bool ez_send_all_bytes(ez_socket_t sock, const uint8_t *data, size_t len) {
    return ez_send_all(sock, (const char *)data, len);
}

static bool ez_recv_exact(ez_socket_t sock, uint8_t *data, size_t len) {
    size_t got = 0;
    while (got < len) {
#if defined(_WIN32)
        int n = recv(sock, (char *)data + got, (int)(len - got), 0);
#else
        ssize_t n = recv(sock, data + got, len - got, 0);
#endif
        if (n <= 0) return false;
        got += (size_t)n;
    }
    return true;
}

static bool ez_recv_contains_101(ez_socket_t sock) {
    char buffer[1024];
#if defined(_WIN32)
    int n = recv(sock, buffer, (int)sizeof(buffer) - 1, 0);
#else
    ssize_t n = recv(sock, buffer, sizeof(buffer) - 1, 0);
#endif
    if (n <= 0) return false;
    buffer[n] = '\0';
    return strncmp(buffer, "HTTP/1.1 101", 12) == 0 || strncmp(buffer, "HTTP/1.0 101", 12) == 0;
}

OptWsConn wsConnect(const char *url) {
    EzWsUrl parts = {0};
    if (!ez_parse_ws_url(url, &parts)) return ez_ws_none();
    ez_socket_t sock = ez_connect_socket(parts.host, parts.port);
    if (sock == EZ_INVALID_SOCKET) {
        ez_ws_url_free(&parts);
        return ez_ws_none();
    }

    int req_len = snprintf(NULL, 0,
        "GET %s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n",
        parts.path, parts.host);
    char *request = (char *)malloc((size_t)req_len + 1);
    if (!request) {
        ez_close_socket(sock);
        ez_ws_url_free(&parts);
        return ez_ws_none();
    }
    snprintf(request, (size_t)req_len + 1,
        "GET %s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n",
        parts.path, parts.host);
    ez_ws_url_free(&parts);

    bool ok = ez_send_all(sock, request, (size_t)req_len) && ez_recv_contains_101(sock);
    free(request);
    if (!ok) {
        ez_close_socket(sock);
        return ez_ws_none();
    }
    return (OptWsConn){true, {(int64_t)sock}};
}

int64_t wsSend(const WsConn *conn, const Blob *data) {
    if (!conn || !data || data->size < 0 || !ez_net_init()) return -1;
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return -1;
    uint64_t size = (uint64_t)data->size;
    if (size > 1024 * 1024 * 16) return -1;

    uint8_t header[14];
    size_t header_len = 0;
    header[header_len++] = 0x82; // FIN + binary frame
    if (size <= 125) {
        header[header_len++] = (uint8_t)(0x80 | size);
    } else if (size <= 0xFFFF) {
        header[header_len++] = 0x80 | 126;
        header[header_len++] = (uint8_t)((size >> 8) & 0xFF);
        header[header_len++] = (uint8_t)(size & 0xFF);
    } else {
        header[header_len++] = 0x80 | 127;
        for (int shift = 56; shift >= 0; shift -= 8) {
            header[header_len++] = (uint8_t)((size >> shift) & 0xFF);
        }
    }

    uint8_t mask[4] = {0x12, 0x34, 0x56, 0x78};
    memcpy(header + header_len, mask, sizeof(mask));
    header_len += sizeof(mask);
    if (!ez_send_all_bytes(sock, header, header_len)) return -1;

    if (size == 0) return 0;
    uint8_t stack_buf[4096];
    uint8_t *buf = size <= sizeof(stack_buf) ? stack_buf : (uint8_t *)malloc((size_t)size);
    if (!buf) return -1;
    for (uint64_t i = 0; i < size; i++) {
        buf[i] = data->data[i] ^ mask[i % 4];
    }
    bool ok = ez_send_all_bytes(sock, buf, (size_t)size);
    if (buf != stack_buf) free(buf);
    return ok ? (int64_t)size : -1;
}

OptBlob wsRecv(const WsConn *conn, int64_t maxBytes) {
    if (!conn || maxBytes < 0 || !ez_net_init()) return ez_ws_none_blob();
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return ez_ws_none_blob();

    uint8_t header[2];
    if (!ez_recv_exact(sock, header, sizeof(header))) return ez_ws_none_blob();
    uint8_t opcode = header[0] & 0x0F;
    bool masked = (header[1] & 0x80) != 0;
    uint64_t len = header[1] & 0x7F;
    if (len == 126) {
        uint8_t ext[2];
        if (!ez_recv_exact(sock, ext, sizeof(ext))) return ez_ws_none_blob();
        len = ((uint64_t)ext[0] << 8) | ext[1];
    } else if (len == 127) {
        uint8_t ext[8];
        if (!ez_recv_exact(sock, ext, sizeof(ext))) return ez_ws_none_blob();
        len = 0;
        for (int i = 0; i < 8; i++) len = (len << 8) | ext[i];
    }
    uint8_t mask[4] = {0};
    if (masked && !ez_recv_exact(sock, mask, sizeof(mask))) return ez_ws_none_blob();
    if (len > (uint64_t)maxBytes || len > 1024 * 1024 * 16) return ez_ws_none_blob();
    if (opcode == 0x8) return ez_ws_empty_blob();
    if (opcode != 0x1 && opcode != 0x2) return ez_ws_none_blob();
    if (len == 0) return ez_ws_empty_blob();

    uint8_t *data = (uint8_t *)malloc((size_t)len);
    if (!data) return ez_ws_none_blob();
    if (!ez_recv_exact(sock, data, (size_t)len)) {
        free(data);
        return ez_ws_none_blob();
    }
    if (masked) {
        for (uint64_t i = 0; i < len; i++) data[i] ^= mask[i % 4];
    }
    return (OptBlob){true, {data, (int64_t)len}};
}

bool wsClose(const WsConn *conn) {
    if (!conn) return false;
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return false;
    uint8_t close_frame[6] = {0x88, 0x80, 0x12, 0x34, 0x56, 0x78};
    ez_send_all_bytes(sock, close_frame, sizeof(close_frame));
    return ez_close_socket(sock) == 0;
}
