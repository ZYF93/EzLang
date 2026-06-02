// EzLang std/net/tcp 原生封装层
// 当前提供阻塞式本机 socket 基础能力；异步 flow 挂起和超时后续接入运行时。

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

typedef struct { int64_t handle; } TcpConn;
typedef struct { int64_t handle; } TcpListener;
typedef struct { int64_t handle; } UdpSocket;
typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { bool ok; TcpConn value; } OptTcpConn;
typedef struct { bool ok; TcpListener value; } OptTcpListener;
typedef struct { bool ok; UdpSocket value; } OptUdpSocket;
typedef struct { bool ok; Blob value; } OptBlob;

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

static int64_t ez_handle(ez_socket_t sock) {
    return (int64_t)sock;
}

static ez_socket_t ez_socket_from_handle(int64_t handle) {
    if (handle == 0) return EZ_INVALID_SOCKET;
    return (ez_socket_t)handle;
}

static OptBlob ez_none_blob(void) {
    return (OptBlob){false, {NULL, 0}};
}

static OptBlob ez_empty_blob(void) {
    return (OptBlob){true, {NULL, 0}};
}

static ez_socket_t ez_connect_socket(const char *host, int32_t port, int socktype) {
    if (!host || port < 0 || !ez_net_init()) return EZ_INVALID_SOCKET;
    char port_text[16];
    snprintf(port_text, sizeof(port_text), "%d", port);

    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = socktype;

    struct addrinfo *result = NULL;
    if (getaddrinfo(host, port_text, &hints, &result) != 0) return EZ_INVALID_SOCKET;
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

static ez_socket_t ez_bind_socket(const char *host, int32_t port, int socktype, bool listen_socket) {
    if (!host || port < 0 || !ez_net_init()) return EZ_INVALID_SOCKET;
    char port_text[16];
    snprintf(port_text, sizeof(port_text), "%d", port);

    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = socktype;
    hints.ai_flags = AI_PASSIVE;

    struct addrinfo *result = NULL;
    if (getaddrinfo(host[0] ? host : NULL, port_text, &hints, &result) != 0) return EZ_INVALID_SOCKET;
    ez_socket_t sock = EZ_INVALID_SOCKET;
    for (struct addrinfo *it = result; it; it = it->ai_next) {
        sock = (ez_socket_t)socket(it->ai_family, it->ai_socktype, it->ai_protocol);
        if (sock == EZ_INVALID_SOCKET) continue;
        int one = 1;
        setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, (const char *)&one, sizeof(one));
        if (bind(sock, it->ai_addr, (int)it->ai_addrlen) == 0) {
            if (!listen_socket || listen(sock, 16) == 0) break;
        }
        ez_close_socket(sock);
        sock = EZ_INVALID_SOCKET;
    }
    freeaddrinfo(result);
    return sock;
}

OptTcpConn tcpConnect(const char *host, int32_t port) {
    ez_socket_t sock = ez_connect_socket(host, port, SOCK_STREAM);
    if (sock == EZ_INVALID_SOCKET) return (OptTcpConn){false, {0}};
    return (OptTcpConn){true, {ez_handle(sock)}};
}

OptTcpListener tcpListen(const char *host, int32_t port) {
    ez_socket_t sock = ez_bind_socket(host, port, SOCK_STREAM, true);
    if (sock == EZ_INVALID_SOCKET) return (OptTcpListener){false, {0}};
    return (OptTcpListener){true, {ez_handle(sock)}};
}

OptUdpSocket udpBind(const char *host, int32_t port) {
    ez_socket_t sock = ez_bind_socket(host, port, SOCK_DGRAM, false);
    if (sock == EZ_INVALID_SOCKET) return (OptUdpSocket){false, {0}};
    return (OptUdpSocket){true, {ez_handle(sock)}};
}

OptTcpConn tcpAccept(const TcpListener *listener) {
    if (!listener || !ez_net_init()) return (OptTcpConn){false, {0}};
    ez_socket_t server = ez_socket_from_handle(listener->handle);
    if (server == EZ_INVALID_SOCKET) return (OptTcpConn){false, {0}};
    ez_socket_t client = (ez_socket_t)accept(server, NULL, NULL);
    if (client == EZ_INVALID_SOCKET) return (OptTcpConn){false, {0}};
    return (OptTcpConn){true, {ez_handle(client)}};
}

OptBlob tcpRead(const TcpConn *conn, int64_t maxBytes) {
    if (!conn || maxBytes < 0 || !ez_net_init()) return ez_none_blob();
    if (maxBytes == 0) return ez_empty_blob();
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return ez_none_blob();
    if (maxBytes > 1024 * 1024 * 16) maxBytes = 1024 * 1024 * 16;
    uint8_t *data = (uint8_t *)malloc((size_t)maxBytes);
    if (!data) return ez_none_blob();
#if defined(_WIN32)
    int got = recv(sock, (char *)data, (int)maxBytes, 0);
#else
    ssize_t got = recv(sock, data, (size_t)maxBytes, 0);
#endif
    if (got < 0) {
        free(data);
        return ez_none_blob();
    }
    if (got == 0) {
        free(data);
        return ez_empty_blob();
    }
    return (OptBlob){true, {data, (int64_t)got}};
}

int64_t tcpWrite(const TcpConn *conn, const Blob *data) {
    if (!conn || !data || !data->data || data->size < 0 || !ez_net_init()) return -1;
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return -1;
    int64_t written = 0;
    while (written < data->size) {
        int64_t remaining = data->size - written;
#if defined(_WIN32)
        int chunk = remaining > INT32_MAX ? INT32_MAX : (int)remaining;
        int n = send(sock, (const char *)data->data + written, chunk, 0);
#else
        size_t chunk = remaining > (int64_t)(1024 * 1024 * 16) ? (size_t)(1024 * 1024 * 16) : (size_t)remaining;
        ssize_t n = send(sock, data->data + written, chunk, 0);
#endif
        if (n <= 0) return written > 0 ? written : -1;
        written += (int64_t)n;
    }
    return written;
}

bool tcpClose(const TcpConn *conn) {
    if (!conn) return false;
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return false;
    return ez_close_socket(sock) == 0;
}

bool tcpListenerClose(const TcpListener *listener) {
    if (!listener) return false;
    ez_socket_t sock = ez_socket_from_handle(listener->handle);
    if (sock == EZ_INVALID_SOCKET) return false;
    return ez_close_socket(sock) == 0;
}

int64_t udpSend(const UdpSocket *socket_value, const char *host, int32_t port, const Blob *data) {
    if (!socket_value || !host || !data || !data->data || data->size < 0 || port < 0 || !ez_net_init()) return -1;
    ez_socket_t sock = ez_socket_from_handle(socket_value->handle);
    if (sock == EZ_INVALID_SOCKET) return -1;

    char port_text[16];
    snprintf(port_text, sizeof(port_text), "%d", port);
    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_DGRAM;
    struct addrinfo *result = NULL;
    if (getaddrinfo(host, port_text, &hints, &result) != 0) return -1;

    int64_t sent = -1;
    for (struct addrinfo *it = result; it; it = it->ai_next) {
        int64_t size = data->size;
#if defined(_WIN32)
        if (size > INT32_MAX) size = INT32_MAX;
        int n = sendto(sock, (const char *)data->data, (int)size, 0, it->ai_addr, (int)it->ai_addrlen);
#else
        ssize_t n = sendto(sock, data->data, (size_t)size, 0, it->ai_addr, it->ai_addrlen);
#endif
        if (n >= 0) {
            sent = (int64_t)n;
            break;
        }
    }
    freeaddrinfo(result);
    return sent;
}

OptBlob udpRecv(const UdpSocket *socket_value, int64_t maxBytes) {
    if (!socket_value || maxBytes < 0 || !ez_net_init()) return ez_none_blob();
    if (maxBytes == 0) return ez_empty_blob();
    ez_socket_t sock = ez_socket_from_handle(socket_value->handle);
    if (sock == EZ_INVALID_SOCKET) return ez_none_blob();
    if (maxBytes > 1024 * 1024 * 16) maxBytes = 1024 * 1024 * 16;
    uint8_t *data = (uint8_t *)malloc((size_t)maxBytes);
    if (!data) return ez_none_blob();
#if defined(_WIN32)
    int got = recvfrom(sock, (char *)data, (int)maxBytes, 0, NULL, NULL);
#else
    ssize_t got = recvfrom(sock, data, (size_t)maxBytes, 0, NULL, NULL);
#endif
    if (got < 0) {
        free(data);
        return ez_none_blob();
    }
    if (got == 0) {
        free(data);
        return ez_empty_blob();
    }
    return (OptBlob){true, {data, (int64_t)got}};
}

bool udpClose(const UdpSocket *socket_value) {
    if (!socket_value) return false;
    ez_socket_t sock = ez_socket_from_handle(socket_value->handle);
    if (sock == EZ_INVALID_SOCKET) return false;
    return ez_close_socket(sock) == 0;
}
