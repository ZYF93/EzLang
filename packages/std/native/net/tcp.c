// EzLang std/net/tcp 原生封装层
// 当前提供阻塞式本机 socket 基础能力；超时变体使用 select 做一次性等待；Linux/macOS 可动态加载 OpenSSL 提供 TCP TLS 客户端。

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef __has_include
#define __has_include(x) 0
#endif

#if defined(_WIN32)
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET ez_socket_t;
typedef int ez_socklen_t;
#define EZ_INVALID_SOCKET INVALID_SOCKET
#define ez_close_socket closesocket
#else
#include <fcntl.h>
#include <netdb.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
typedef int ez_socket_t;
typedef socklen_t ez_socklen_t;
#define EZ_INVALID_SOCKET (-1)
#define ez_close_socket close
#endif

#if !defined(_WIN32) && !defined(EZ_TARGET_ANDROID) && !defined(EZ_TARGET_IOS) && __has_include(<dlfcn.h>)
#define EZ_TCP_HAS_OPENSSL_TLS 1
#include <dlfcn.h>
#else
#define EZ_TCP_HAS_OPENSSL_TLS 0
#endif

typedef struct { int64_t handle; } TcpConn;
typedef struct { int64_t handle; } TcpTlsConn;
typedef struct { int64_t handle; } TcpListener;
typedef struct { int64_t handle; } UdpSocket;
typedef struct { uint8_t *data; int64_t size; } Blob;
typedef struct { Blob data; const char *host; int32_t port; } UdpPacket;
typedef struct { bool ok; TcpConn value; } OptTcpConn;
typedef struct { bool ok; TcpTlsConn value; } OptTcpTlsConn;
typedef struct { bool ok; TcpListener value; } OptTcpListener;
typedef struct { bool ok; UdpSocket value; } OptUdpSocket;
typedef struct { bool ok; Blob value; } OptBlob;
typedef struct { bool ok; UdpPacket value; } OptUdpPacket;

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

#if EZ_TCP_HAS_OPENSSL_TLS
typedef struct ssl_st SSL;
typedef struct ssl_ctx_st SSL_CTX;
typedef struct ssl_method_st SSL_METHOD;
typedef struct X509_VERIFY_PARAM_st X509_VERIFY_PARAM;
typedef int (*EzOpenSslInitSslFn)(uint64_t, const void *);
typedef const SSL_METHOD *(*EzOpenSslMethodFn)(void);
typedef SSL_CTX *(*EzOpenSslCtxNewFn)(const SSL_METHOD *);
typedef void (*EzOpenSslCtxFreeFn)(SSL_CTX *);
typedef int (*EzOpenSslCtxDefaultPathsFn)(SSL_CTX *);
typedef void (*EzOpenSslCtxSetVerifyFn)(SSL_CTX *, int, void *);
typedef SSL *(*EzOpenSslNewFn)(SSL_CTX *);
typedef void (*EzOpenSslFreeFn)(SSL *);
typedef int (*EzOpenSslSetFdFn)(SSL *, int);
typedef long (*EzOpenSslCtrlFn)(SSL *, int, long, void *);
typedef X509_VERIFY_PARAM *(*EzOpenSslGet0ParamFn)(SSL *);
typedef int (*EzOpenSslParamSetHostFn)(X509_VERIFY_PARAM *, const char *, size_t);
typedef int (*EzOpenSslParamSetIpFn)(X509_VERIFY_PARAM *, const char *);
typedef int (*EzOpenSslConnectFn)(SSL *);
typedef int (*EzOpenSslReadFn)(SSL *, void *, int);
typedef int (*EzOpenSslWriteFn)(SSL *, const void *, int);
typedef int (*EzOpenSslShutdownFn)(SSL *);
typedef long (*EzOpenSslVerifyResultFn)(const SSL *);

typedef struct {
    void *ssl_handle;
    void *crypto_handle;
    EzOpenSslInitSslFn init_ssl;
    EzOpenSslMethodFn tls_client_method;
    EzOpenSslMethodFn sslv23_client_method;
    EzOpenSslCtxNewFn ctx_new;
    EzOpenSslCtxFreeFn ctx_free;
    EzOpenSslCtxDefaultPathsFn ctx_default_paths;
    EzOpenSslCtxSetVerifyFn ctx_set_verify;
    EzOpenSslNewFn ssl_new;
    EzOpenSslFreeFn ssl_free;
    EzOpenSslSetFdFn ssl_set_fd;
    EzOpenSslCtrlFn ssl_ctrl;
    EzOpenSslGet0ParamFn ssl_get0_param;
    EzOpenSslParamSetHostFn param_set_host;
    EzOpenSslParamSetIpFn param_set_ip;
    EzOpenSslConnectFn ssl_connect;
    EzOpenSslReadFn ssl_read;
    EzOpenSslWriteFn ssl_write;
    EzOpenSslShutdownFn ssl_shutdown;
    EzOpenSslVerifyResultFn ssl_get_verify_result;
    bool loaded;
    bool available;
} EzTcpTlsApi;

typedef struct EzTcpTlsEntry {
    int64_t handle;
    ez_socket_t sock;
    SSL_CTX *ctx;
    SSL *ssl;
    struct EzTcpTlsEntry *next;
} EzTcpTlsEntry;

static EzTcpTlsApi ez_tcp_tls_api = {0};
static EzTcpTlsEntry *ez_tcp_tls_entries = NULL;
static int64_t ez_tcp_tls_next_handle = INT64_C(0x4000000000000000);

static void *ez_tcp_dlsym_required(void *handle, const char *name, bool *ok) {
    void *symbol = dlsym(handle, name);
    if (!symbol) *ok = false;
    return symbol;
}

static void *ez_tcp_dlopen_first(const char *const *candidates) {
    for (size_t i = 0; candidates[i] != NULL; ++i) {
#if defined(EZ_TCP_TEST_NO_OPENSSL_DLOPEN)
        void *handle = NULL;
#else
        void *handle = dlopen(candidates[i], RTLD_LAZY | RTLD_LOCAL);
#endif
        if (handle) return handle;
    }
    return NULL;
}

static void ez_tcp_tls_reset_failed(EzTcpTlsApi *api) {
    void *ssl_handle = api->ssl_handle;
    void *crypto_handle = api->crypto_handle;
    memset(api, 0, sizeof(*api));
    if (crypto_handle && crypto_handle != ssl_handle) dlclose(crypto_handle);
    if (ssl_handle) dlclose(ssl_handle);
    api->loaded = true;
}

static bool ez_tcp_load_tls(EzTcpTlsApi *api) {
    if (api->loaded) return api->available;
    api->loaded = true;

#if defined(__APPLE__)
    const char *ssl_candidates[] = {
        "/opt/homebrew/opt/openssl@3/lib/libssl.3.dylib",
        "/usr/local/opt/openssl@3/lib/libssl.3.dylib",
        "/opt/homebrew/lib/libssl.3.dylib",
        "/usr/local/lib/libssl.3.dylib",
        "libssl.3.dylib",
        "libssl.1.1.dylib",
        "libssl.dylib",
        NULL,
    };
    const char *crypto_candidates[] = {
        "/opt/homebrew/opt/openssl@3/lib/libcrypto.3.dylib",
        "/usr/local/opt/openssl@3/lib/libcrypto.3.dylib",
        "/opt/homebrew/lib/libcrypto.3.dylib",
        "/usr/local/lib/libcrypto.3.dylib",
        "libcrypto.3.dylib",
        "libcrypto.1.1.dylib",
        "libcrypto.dylib",
        NULL,
    };
#else
    const char *ssl_candidates[] = {
        "libssl.so.3",
        "libssl.so.1.1",
        "libssl.so",
        NULL,
    };
    const char *crypto_candidates[] = {
        "libcrypto.so.3",
        "libcrypto.so.1.1",
        "libcrypto.so",
        NULL,
    };
#endif

    api->ssl_handle = ez_tcp_dlopen_first(ssl_candidates);
    api->crypto_handle = ez_tcp_dlopen_first(crypto_candidates);
    if (!api->ssl_handle || !api->crypto_handle) {
        ez_tcp_tls_reset_failed(api);
        return false;
    }

    bool ok = true;
    api->init_ssl = (EzOpenSslInitSslFn)dlsym(api->ssl_handle, "OPENSSL_init_ssl");
    api->tls_client_method = (EzOpenSslMethodFn)dlsym(api->ssl_handle, "TLS_client_method");
    api->sslv23_client_method = (EzOpenSslMethodFn)dlsym(api->ssl_handle, "SSLv23_client_method");
    api->ctx_new = (EzOpenSslCtxNewFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_CTX_new", &ok);
    api->ctx_free = (EzOpenSslCtxFreeFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_CTX_free", &ok);
    api->ctx_default_paths = (EzOpenSslCtxDefaultPathsFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_CTX_set_default_verify_paths", &ok);
    api->ctx_set_verify = (EzOpenSslCtxSetVerifyFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_CTX_set_verify", &ok);
    api->ssl_new = (EzOpenSslNewFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_new", &ok);
    api->ssl_free = (EzOpenSslFreeFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_free", &ok);
    api->ssl_set_fd = (EzOpenSslSetFdFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_set_fd", &ok);
    api->ssl_ctrl = (EzOpenSslCtrlFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_ctrl", &ok);
    api->ssl_get0_param = (EzOpenSslGet0ParamFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_get0_param", &ok);
    api->ssl_connect = (EzOpenSslConnectFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_connect", &ok);
    api->ssl_read = (EzOpenSslReadFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_read", &ok);
    api->ssl_write = (EzOpenSslWriteFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_write", &ok);
    api->ssl_shutdown = (EzOpenSslShutdownFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_shutdown", &ok);
    api->ssl_get_verify_result = (EzOpenSslVerifyResultFn)ez_tcp_dlsym_required(api->ssl_handle, "SSL_get_verify_result", &ok);
    api->param_set_host = (EzOpenSslParamSetHostFn)ez_tcp_dlsym_required(api->crypto_handle, "X509_VERIFY_PARAM_set1_host", &ok);
    api->param_set_ip = (EzOpenSslParamSetIpFn)ez_tcp_dlsym_required(api->crypto_handle, "X509_VERIFY_PARAM_set1_ip_asc", &ok);
    if ((!api->tls_client_method && !api->sslv23_client_method) || !ok) {
        ez_tcp_tls_reset_failed(api);
        return false;
    }
    api->available = true;
    return true;
}

static bool ez_tcp_tls_host_is_ip_literal(const char *host) {
    if (!host || !host[0]) return false;
    if (strchr(host, ':')) return true;
    bool saw_dot = false;
    for (const char *p = host; *p; ++p) {
        if (*p == '.') {
            saw_dot = true;
            continue;
        }
        if (*p < '0' || *p > '9') return false;
    }
    return saw_dot;
}

static bool ez_tcp_tls_configure_verify(EzTcpTlsApi *api, SSL *ssl, const char *host) {
    if (!api || !ssl || !host || !host[0]) return false;
    X509_VERIFY_PARAM *param = api->ssl_get0_param(ssl);
    if (!param) return false;
    if (ez_tcp_tls_host_is_ip_literal(host)) return api->param_set_ip(param, host) == 1;
    return api->param_set_host(param, host, 0) == 1;
}

static EzTcpTlsEntry *ez_tcp_tls_entry_from_handle(int64_t handle) {
    for (EzTcpTlsEntry *entry = ez_tcp_tls_entries; entry; entry = entry->next) {
        if (entry->handle == handle) return entry;
    }
    return NULL;
}

static int64_t ez_tcp_tls_store(ez_socket_t sock, SSL_CTX *ctx, SSL *ssl) {
    EzTcpTlsEntry *entry = (EzTcpTlsEntry *)calloc(1, sizeof(EzTcpTlsEntry));
    if (!entry) return 0;
    entry->handle = ez_tcp_tls_next_handle++;
    if (entry->handle <= 0) entry->handle = ez_tcp_tls_next_handle = INT64_C(0x4000000000000000);
    entry->sock = sock;
    entry->ctx = ctx;
    entry->ssl = ssl;
    entry->next = ez_tcp_tls_entries;
    ez_tcp_tls_entries = entry;
    return entry->handle;
}

static void ez_tcp_tls_remove(EzTcpTlsEntry *target) {
    if (!target) return;
    EzTcpTlsEntry **link = &ez_tcp_tls_entries;
    while (*link && *link != target) link = &(*link)->next;
    if (*link == target) *link = target->next;
}
#endif

static OptBlob ez_none_blob(void) {
    return (OptBlob){false, {NULL, 0}};
}

static OptBlob ez_empty_blob(void) {
    return (OptBlob){true, {NULL, 0}};
}

static OptUdpPacket ez_none_udp_packet(void) {
    return (OptUdpPacket){false, {{NULL, 0}, NULL, 0}};
}

static bool ez_blob_valid(const Blob *data) {
    return data && data->size >= 0 && (data->size == 0 || data->data);
}

static bool ez_port_valid(int32_t port) {
    return port >= 0 && port <= 65535;
}

static int64_t ez_now_ms(void) {
#if defined(_WIN32)
    return (int64_t)GetTickCount64();
#else
    struct timeval tv;
    if (gettimeofday(&tv, NULL) != 0) return 0;
    return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
#endif
}

static int32_t ez_remaining_timeout_ms(int32_t timeout_ms, int64_t deadline_ms) {
    if (timeout_ms <= 0) return timeout_ms;
    int64_t remaining = deadline_ms - ez_now_ms();
    if (remaining <= 0) return 0;
    return remaining > INT32_MAX ? INT32_MAX : (int32_t)remaining;
}

static int ez_last_socket_error(void) {
#if defined(_WIN32)
    return WSAGetLastError();
#else
    return errno;
#endif
}

static bool ez_socket_connect_pending(int error) {
#if defined(_WIN32)
    return error == WSAEINPROGRESS || error == WSAEWOULDBLOCK || error == WSAEALREADY;
#else
    return error == EINPROGRESS || error == EWOULDBLOCK || error == EALREADY;
#endif
}

static bool ez_socket_would_block(int error) {
#if defined(_WIN32)
    return error == WSAEWOULDBLOCK;
#else
    return error == EWOULDBLOCK || error == EAGAIN;
#endif
}

static bool ez_socket_interrupted(int error) {
#if defined(_WIN32)
    return error == WSAEINTR;
#else
    return error == EINTR;
#endif
}

static bool ez_socket_set_nonblocking(ez_socket_t sock, bool enabled) {
#if defined(_WIN32)
    u_long mode = enabled ? 1UL : 0UL;
    return ioctlsocket(sock, FIONBIO, &mode) == 0;
#else
    int flags = fcntl(sock, F_GETFL, 0);
    if (flags < 0) return false;
    if (enabled) flags |= O_NONBLOCK;
    else flags &= ~O_NONBLOCK;
    return fcntl(sock, F_SETFL, flags) == 0;
#endif
}

static int ez_socket_pending_error(ez_socket_t sock) {
    int error = 0;
    ez_socklen_t len = (ez_socklen_t)sizeof(error);
    if (getsockopt(sock, SOL_SOCKET, SO_ERROR, (char *)&error, &len) != 0) return ez_last_socket_error();
    return error;
}

static int ez_wait_socket(ez_socket_t sock, bool want_read, bool want_write, int32_t timeout_ms) {
    if (sock == EZ_INVALID_SOCKET || timeout_ms < 0 || (!want_read && !want_write)) return -1;
#if !defined(_WIN32)
    if (sock < 0 || sock >= FD_SETSIZE) return -1;
#endif
    fd_set read_fds;
    fd_set write_fds;
    FD_ZERO(&read_fds);
    FD_ZERO(&write_fds);
    if (want_read) FD_SET(sock, &read_fds);
    if (want_write) FD_SET(sock, &write_fds);
    struct timeval timeout;
    timeout.tv_sec = timeout_ms / 1000;
    timeout.tv_usec = (timeout_ms % 1000) * 1000;
#if defined(_WIN32)
    int ready = select(0, want_read ? &read_fds : NULL, want_write ? &write_fds : NULL, NULL, &timeout);
#else
    int ready = select(sock + 1, want_read ? &read_fds : NULL, want_write ? &write_fds : NULL, NULL, &timeout);
#endif
    if (ready < 0 && ez_socket_interrupted(ez_last_socket_error())) return 0;
    if (ready < 0) return -1;
    if (ready == 0) return 0;
    return 1;
}

static ez_socket_t ez_connect_socket(const char *host, int32_t port, int socktype) {
    if (!host || !ez_port_valid(port) || !ez_net_init()) return EZ_INVALID_SOCKET;
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

static ez_socket_t ez_connect_socket_timeout(const char *host, int32_t port, int32_t timeout_ms) {
    if (!host || !ez_port_valid(port) || timeout_ms < 0 || !ez_net_init()) return EZ_INVALID_SOCKET;
    char port_text[16];
    snprintf(port_text, sizeof(port_text), "%d", port);

    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    struct addrinfo *result = NULL;
    if (getaddrinfo(host, port_text, &hints, &result) != 0) return EZ_INVALID_SOCKET;
    int64_t deadline_ms = timeout_ms > 0 ? ez_now_ms() + timeout_ms : 0;
    ez_socket_t sock = EZ_INVALID_SOCKET;
    for (struct addrinfo *it = result; it; it = it->ai_next) {
        int32_t remaining = ez_remaining_timeout_ms(timeout_ms, deadline_ms);
        if (timeout_ms > 0 && remaining <= 0) break;
        sock = (ez_socket_t)socket(it->ai_family, it->ai_socktype, it->ai_protocol);
        if (sock == EZ_INVALID_SOCKET) continue;
        if (!ez_socket_set_nonblocking(sock, true)) {
            ez_close_socket(sock);
            sock = EZ_INVALID_SOCKET;
            continue;
        }
        if (connect(sock, it->ai_addr, (int)it->ai_addrlen) == 0) {
            if (ez_socket_set_nonblocking(sock, false)) break;
            ez_close_socket(sock);
            sock = EZ_INVALID_SOCKET;
            continue;
        }
        if (ez_socket_connect_pending(ez_last_socket_error()) && ez_wait_socket(sock, false, true, remaining) > 0 && ez_socket_pending_error(sock) == 0) {
            if (ez_socket_set_nonblocking(sock, false)) break;
        }
        ez_close_socket(sock);
        sock = EZ_INVALID_SOCKET;
    }
    freeaddrinfo(result);
    return sock;
}

static ez_socket_t ez_bind_socket(const char *host, int32_t port, int socktype, bool listen_socket) {
    if (!host || !ez_port_valid(port) || !ez_net_init()) return EZ_INVALID_SOCKET;
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

OptTcpConn tcpConnectTimeout(const char *host, int32_t port, int32_t timeoutMs) {
    ez_socket_t sock = ez_connect_socket_timeout(host, port, timeoutMs);
    if (sock == EZ_INVALID_SOCKET) return (OptTcpConn){false, {0}};
    return (OptTcpConn){true, {ez_handle(sock)}};
}

OptTcpTlsConn tcpTlsConnect(const char *host, int32_t port) {
    if (!host || !ez_port_valid(port) || !ez_net_init()) return (OptTcpTlsConn){false, {0}};
#if EZ_TCP_HAS_OPENSSL_TLS
    EzTcpTlsApi *api = &ez_tcp_tls_api;
    if (!ez_tcp_load_tls(api)) return (OptTcpTlsConn){false, {0}};
    ez_socket_t sock = ez_connect_socket(host, port, SOCK_STREAM);
    if (sock == EZ_INVALID_SOCKET) return (OptTcpTlsConn){false, {0}};
    if (api->init_ssl) api->init_ssl(0, NULL);
    const SSL_METHOD *method = api->tls_client_method ? api->tls_client_method() : api->sslv23_client_method();
    if (!method) {
        ez_close_socket(sock);
        return (OptTcpTlsConn){false, {0}};
    }
    SSL_CTX *ctx = api->ctx_new(method);
    if (!ctx) {
        ez_close_socket(sock);
        return (OptTcpTlsConn){false, {0}};
    }
    const int ssl_verify_peer = 1;
    const int ssl_ctrl_set_tlsext_hostname = 55;
    const long tlsext_nametype_host_name = 0;
    SSL *ssl = NULL;
    bool ok = api->ctx_default_paths(ctx) == 1;
    if (ok) api->ctx_set_verify(ctx, ssl_verify_peer, NULL);
    if (ok) {
        ssl = api->ssl_new(ctx);
        ok = ssl != NULL;
    }
    if (ok && !ez_tcp_tls_configure_verify(api, ssl, host)) ok = false;
    if (ok && !ez_tcp_tls_host_is_ip_literal(host)) {
        ok = api->ssl_ctrl(ssl, ssl_ctrl_set_tlsext_hostname, tlsext_nametype_host_name, (void *)host) > 0;
    }
    if (ok) ok = api->ssl_set_fd(ssl, (int)sock) == 1;
    if (ok) ok = api->ssl_connect(ssl) == 1;
    if (ok) ok = api->ssl_get_verify_result(ssl) == 0;
    if (!ok) {
        if (ssl) api->ssl_free(ssl);
        api->ctx_free(ctx);
        ez_close_socket(sock);
        return (OptTcpTlsConn){false, {0}};
    }
    int64_t handle = ez_tcp_tls_store(sock, ctx, ssl);
    if (handle == 0) {
        if (api->ssl_shutdown) api->ssl_shutdown(ssl);
        api->ssl_free(ssl);
        api->ctx_free(ctx);
        ez_close_socket(sock);
        return (OptTcpTlsConn){false, {0}};
    }
    return (OptTcpTlsConn){true, {handle}};
#else
    return (OptTcpTlsConn){false, {0}};
#endif
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

OptTcpConn tcpAcceptTimeout(const TcpListener *listener, int32_t timeoutMs) {
    if (!listener || timeoutMs < 0 || !ez_net_init()) return (OptTcpConn){false, {0}};
    ez_socket_t server = ez_socket_from_handle(listener->handle);
    if (server == EZ_INVALID_SOCKET) return (OptTcpConn){false, {0}};
    int ready = ez_wait_socket(server, true, false, timeoutMs);
    if (ready <= 0) return (OptTcpConn){false, {0}};
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

OptBlob tcpReadTimeout(const TcpConn *conn, int64_t maxBytes, int32_t timeoutMs) {
    if (!conn || maxBytes < 0 || timeoutMs < 0 || !ez_net_init()) return ez_none_blob();
    if (maxBytes == 0) return ez_empty_blob();
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return ez_none_blob();
    int ready = ez_wait_socket(sock, true, false, timeoutMs);
    if (ready <= 0) return ez_none_blob();
    return tcpRead(conn, maxBytes);
}

int64_t tcpWrite(const TcpConn *conn, const Blob *data) {
    if (!conn || !ez_blob_valid(data) || !ez_net_init()) return -1;
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return -1;
    if (data->size == 0) return 0;
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

int64_t tcpWriteTimeout(const TcpConn *conn, const Blob *data, int32_t timeoutMs) {
    if (!conn || !ez_blob_valid(data) || timeoutMs < 0 || !ez_net_init()) return -1;
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return -1;
    if (data->size == 0) return 0;
    if (!ez_socket_set_nonblocking(sock, true)) return -1;
    int64_t deadline_ms = timeoutMs > 0 ? ez_now_ms() + timeoutMs : 0;
    int64_t written = 0;
    while (written < data->size) {
        int32_t remaining_ms = ez_remaining_timeout_ms(timeoutMs, deadline_ms);
        if (timeoutMs > 0 && remaining_ms <= 0) break;
        int ready = ez_wait_socket(sock, false, true, remaining_ms);
        if (ready <= 0) break;
        int64_t remaining = data->size - written;
#if defined(_WIN32)
        int chunk = remaining > INT32_MAX ? INT32_MAX : (int)remaining;
        int n = send(sock, (const char *)data->data + written, chunk, 0);
#else
        size_t chunk = remaining > (int64_t)(1024 * 1024 * 16) ? (size_t)(1024 * 1024 * 16) : (size_t)remaining;
        ssize_t n = send(sock, data->data + written, chunk, 0);
#endif
        if (n > 0) {
            written += (int64_t)n;
            continue;
        }
        int err = ez_last_socket_error();
        if (ez_socket_would_block(err) || ez_socket_interrupted(err)) continue;
        break;
    }
    bool restored = ez_socket_set_nonblocking(sock, false);
    if (!restored && written == 0) return -1;
    return written > 0 ? written : -1;
}

OptBlob tcpTlsRead(const TcpTlsConn *conn, int64_t maxBytes) {
    if (!conn || maxBytes < 0 || !ez_net_init()) return ez_none_blob();
    if (maxBytes == 0) return ez_empty_blob();
#if EZ_TCP_HAS_OPENSSL_TLS
    EzTcpTlsEntry *entry = ez_tcp_tls_entry_from_handle(conn->handle);
    if (!entry || !entry->ssl) return ez_none_blob();
    if (maxBytes > 1024 * 1024 * 16) maxBytes = 1024 * 1024 * 16;
    uint8_t *data = (uint8_t *)malloc((size_t)maxBytes);
    if (!data) return ez_none_blob();
    int chunk = maxBytes > INT_MAX ? INT_MAX : (int)maxBytes;
    int got = ez_tcp_tls_api.ssl_read(entry->ssl, data, chunk);
    if (got < 0) {
        free(data);
        return ez_none_blob();
    }
    if (got == 0) {
        free(data);
        return ez_empty_blob();
    }
    return (OptBlob){true, {data, (int64_t)got}};
#else
    return ez_none_blob();
#endif
}

int64_t tcpTlsWrite(const TcpTlsConn *conn, const Blob *data) {
    if (!conn || !ez_blob_valid(data) || !ez_net_init()) return -1;
    if (data->size == 0) return 0;
#if EZ_TCP_HAS_OPENSSL_TLS
    EzTcpTlsEntry *entry = ez_tcp_tls_entry_from_handle(conn->handle);
    if (!entry || !entry->ssl) return -1;
    int64_t written = 0;
    while (written < data->size) {
        int64_t remaining = data->size - written;
        int chunk = remaining > INT_MAX ? INT_MAX : (int)remaining;
        int n = ez_tcp_tls_api.ssl_write(entry->ssl, data->data + written, chunk);
        if (n <= 0) return written > 0 ? written : -1;
        written += (int64_t)n;
    }
    return written;
#else
    return -1;
#endif
}

bool tcpTlsClose(const TcpTlsConn *conn) {
    if (!conn) return false;
#if EZ_TCP_HAS_OPENSSL_TLS
    EzTcpTlsEntry *entry = ez_tcp_tls_entry_from_handle(conn->handle);
    if (!entry) return false;
    EzTcpTlsApi *api = &ez_tcp_tls_api;
    if (entry->ssl) {
        if (api->ssl_shutdown) api->ssl_shutdown(entry->ssl);
        if (api->ssl_free) api->ssl_free(entry->ssl);
        entry->ssl = NULL;
    }
    if (entry->ctx) {
        if (api->ctx_free) api->ctx_free(entry->ctx);
        entry->ctx = NULL;
    }
    bool closed = entry->sock != EZ_INVALID_SOCKET && ez_close_socket(entry->sock) == 0;
    ez_tcp_tls_remove(entry);
    free(entry);
    return closed;
#else
    return false;
#endif
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
    if (!socket_value || !host || !ez_blob_valid(data) || !ez_port_valid(port) || !ez_net_init()) return -1;
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
    const uint8_t empty_payload = 0;
    for (struct addrinfo *it = result; it; it = it->ai_next) {
        int64_t size = data->size;
#if defined(_WIN32)
        if (size > INT32_MAX) size = INT32_MAX;
        const char *payload = size == 0 ? (const char *)&empty_payload : (const char *)data->data;
        int n = sendto(sock, payload, (int)size, 0, it->ai_addr, (int)it->ai_addrlen);
#else
        const uint8_t *payload = size == 0 ? &empty_payload : data->data;
        ssize_t n = sendto(sock, payload, (size_t)size, 0, it->ai_addr, it->ai_addrlen);
#endif
        if (n >= 0) {
            sent = (int64_t)n;
            break;
        }
    }
    freeaddrinfo(result);
    return sent;
}

int64_t udpSendTimeout(const UdpSocket *socket_value, const char *host, int32_t port, const Blob *data, int32_t timeoutMs) {
    if (!socket_value || !host || !ez_blob_valid(data) || !ez_port_valid(port) || timeoutMs < 0 || !ez_net_init()) return -1;
    ez_socket_t sock = ez_socket_from_handle(socket_value->handle);
    if (sock == EZ_INVALID_SOCKET) return -1;
    int ready = ez_wait_socket(sock, false, true, timeoutMs);
    if (ready <= 0) return -1;
    return udpSend(socket_value, host, port, data);
}

OptUdpPacket udpRecvFrom(const UdpSocket *socket_value, int64_t maxBytes) {
    if (!socket_value || maxBytes < 0 || !ez_net_init()) return ez_none_udp_packet();
    if (maxBytes == 0) return (OptUdpPacket){true, {{NULL, 0}, NULL, 0}};
    ez_socket_t sock = ez_socket_from_handle(socket_value->handle);
    if (sock == EZ_INVALID_SOCKET) return ez_none_udp_packet();
    if (maxBytes > 1024 * 1024 * 16) maxBytes = 1024 * 1024 * 16;
    uint8_t *data = (uint8_t *)malloc((size_t)maxBytes);
    if (!data) return ez_none_udp_packet();
    struct sockaddr_storage addr;
    ez_socklen_t addr_len = (ez_socklen_t)sizeof(addr);
#if defined(_WIN32)
    int got = recvfrom(sock, (char *)data, (int)maxBytes, 0, (struct sockaddr *)&addr, &addr_len);
#else
    ssize_t got = recvfrom(sock, data, (size_t)maxBytes, 0, (struct sockaddr *)&addr, &addr_len);
#endif
    if (got < 0) {
        free(data);
        return ez_none_udp_packet();
    }
    if (got == 0) {
        free(data);
        data = NULL;
    }

    char host[NI_MAXHOST];
    char service[NI_MAXSERV];
    int info = getnameinfo((struct sockaddr *)&addr, addr_len, host, sizeof(host), service, sizeof(service), NI_NUMERICHOST | NI_NUMERICSERV);
    if (info != 0) {
        free(data);
        return ez_none_udp_packet();
    }
    char *host_copy = (char *)malloc(strlen(host) + 1);
    if (!host_copy) {
        free(data);
        return ez_none_udp_packet();
    }
    strcpy(host_copy, host);
    char *end = NULL;
    long port_value = strtol(service, &end, 10);
    if (!end || *end != '\0' || port_value < 0 || port_value > 65535) {
        free(host_copy);
        free(data);
        return ez_none_udp_packet();
    }
    return (OptUdpPacket){true, {{data, (int64_t)got}, host_copy, (int32_t)port_value}};
}

OptUdpPacket udpRecvFromTimeout(const UdpSocket *socket_value, int64_t maxBytes, int32_t timeoutMs) {
    if (!socket_value || maxBytes < 0 || timeoutMs < 0 || !ez_net_init()) return ez_none_udp_packet();
    if (maxBytes == 0) return (OptUdpPacket){true, {{NULL, 0}, NULL, 0}};
    ez_socket_t sock = ez_socket_from_handle(socket_value->handle);
    if (sock == EZ_INVALID_SOCKET) return ez_none_udp_packet();
    int ready = ez_wait_socket(sock, true, false, timeoutMs);
    if (ready <= 0) return ez_none_udp_packet();
    return udpRecvFrom(socket_value, maxBytes);
}

OptBlob udpRecv(const UdpSocket *socket_value, int64_t maxBytes) {
    OptUdpPacket packet = udpRecvFrom(socket_value, maxBytes);
    if (!packet.ok) return ez_none_blob();
    Blob data = packet.value.data;
    free((void *)packet.value.host);
    return (OptBlob){true, data};
}

OptBlob udpRecvTimeout(const UdpSocket *socket_value, int64_t maxBytes, int32_t timeoutMs) {
    OptUdpPacket packet = udpRecvFromTimeout(socket_value, maxBytes, timeoutMs);
    if (!packet.ok) return ez_none_blob();
    Blob data = packet.value.data;
    free((void *)packet.value.host);
    return (OptBlob){true, data};
}

bool udpClose(const UdpSocket *socket_value) {
    if (!socket_value) return false;
    ez_socket_t sock = ez_socket_from_handle(socket_value->handle);
    if (sock == EZ_INVALID_SOCKET) return false;
    return ez_close_socket(sock) == 0;
}
