// EzLang std/net/http 原生封装层
// 当前实现 HTTP/HTTPS 客户端和每连接 worker 服务端；TLS 后端不可用时 HTTPS 显式失败。

#include <stdbool.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef __has_include
#define __has_include(x) 0
#endif

#if defined(_WIN32)
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
typedef SOCKET ez_socket_t;
#define EZ_INVALID_SOCKET INVALID_SOCKET
#define ez_close_socket closesocket
#define EZ_SHUTDOWN_BOTH SD_BOTH
#else
#include <errno.h>
#include <netinet/in.h>
#include <netdb.h>
#include <pthread.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int ez_socket_t;
#define EZ_INVALID_SOCKET (-1)
#define ez_close_socket close
#define EZ_SHUTDOWN_BOTH SHUT_RDWR
#endif

#if !defined(_WIN32) && !defined(EZ_TARGET_ANDROID) && !defined(EZ_TARGET_IOS) && __has_include(<dlfcn.h>)
#define EZ_HTTP_HAS_OPENSSL_TLS 1
#include <dlfcn.h>
#else
#define EZ_HTTP_HAS_OPENSSL_TLS 0
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
    bool started;
    EzHttpRoute *routes;
    size_t route_count;
    size_t route_capacity;
#if defined(_WIN32)
    CRITICAL_SECTION worker_lock;
    CONDITION_VARIABLE worker_done;
#else
    pthread_mutex_t worker_lock;
    pthread_cond_t worker_done;
#endif
    int32_t active_workers;
    bool sync_ready;
} EzHttpServer;

typedef struct {
    EzHttpServer *server;
    ez_socket_t client;
} EzHttpClientWorker;

typedef struct {
    bool ok;
    HttpResponse value;
} OptHttpResponse;

typedef struct {
    char *host;
    char *host_header;
    char *path;
    char port[8];
    bool tls;
} EzUrlParts;

#if EZ_HTTP_HAS_OPENSSL_TLS
typedef struct ssl_st SSL;
typedef struct ssl_ctx_st SSL_CTX;
typedef struct ssl_method_st SSL_METHOD;
typedef struct x509_st X509;
typedef struct x509_store_ctx_st X509_STORE_CTX;
#endif

typedef struct {
    ez_socket_t sock;
#if EZ_HTTP_HAS_OPENSSL_TLS
    SSL_CTX *tls_ctx;
    SSL *tls_ssl;
#endif
    bool tls;
} EzHttpConnection;

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
static bool ez_send_all(ez_socket_t sock, const char *data, size_t len);

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

static bool ez_ascii_starts_with_ci(const char *text, const char *prefix) {
    if (!text || !prefix) return false;
    for (size_t i = 0; prefix[i] != '\0'; ++i) {
        if (text[i] == '\0' || ez_ascii_lower(text[i]) != prefix[i]) return false;
    }
    return true;
}

static size_t ez_http_scheme_len(const char *url, bool *tls) {
    if (tls) *tls = false;
    if (ez_ascii_starts_with_ci(url, "http://")) return strlen("http://");
    if (ez_ascii_starts_with_ci(url, "https://")) {
        if (tls) *tls = true;
        return strlen("https://");
    }
    return 0;
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
    if (!out) return false;
    *out = (EzUrlParts){0};
    bool tls = false;
    size_t prefix_len = ez_http_scheme_len(url, &tls);
    if (prefix_len == 0) return false;
    out->tls = tls;
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
    strcpy(out->port, tls ? "443" : "80");

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

#if EZ_HTTP_HAS_OPENSSL_TLS
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
} EzHttpTlsApi;

static EzHttpTlsApi ez_http_tls_api = {0};

static void *ez_http_dlsym_required(void *handle, const char *name, bool *ok) {
    void *symbol = dlsym(handle, name);
    if (!symbol) *ok = false;
    return symbol;
}

static void *ez_http_dlopen_first(const char *const *candidates) {
    for (size_t i = 0; candidates[i] != NULL; ++i) {
#if defined(EZ_HTTP_TEST_NO_OPENSSL_DLOPEN)
        void *handle = NULL;
#else
        void *handle = dlopen(candidates[i], RTLD_LAZY | RTLD_LOCAL);
#endif
        if (handle) return handle;
    }
    return NULL;
}

static void ez_http_tls_reset_failed(EzHttpTlsApi *api) {
    void *ssl_handle = api->ssl_handle;
    void *crypto_handle = api->crypto_handle;
    memset(api, 0, sizeof(*api));
    if (crypto_handle && crypto_handle != ssl_handle) dlclose(crypto_handle);
    if (ssl_handle) dlclose(ssl_handle);
    api->loaded = true;
}

static bool ez_http_load_tls(EzHttpTlsApi *api) {
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

    api->ssl_handle = ez_http_dlopen_first(ssl_candidates);
    api->crypto_handle = ez_http_dlopen_first(crypto_candidates);
    if (!api->ssl_handle || !api->crypto_handle) {
        ez_http_tls_reset_failed(api);
        return false;
    }

    bool ok = true;
    api->init_ssl = (EzOpenSslInitSslFn)dlsym(api->ssl_handle, "OPENSSL_init_ssl");
    api->tls_client_method = (EzOpenSslMethodFn)dlsym(api->ssl_handle, "TLS_client_method");
    api->sslv23_client_method = (EzOpenSslMethodFn)dlsym(api->ssl_handle, "SSLv23_client_method");
    api->ctx_new = (EzOpenSslCtxNewFn)ez_http_dlsym_required(api->ssl_handle, "SSL_CTX_new", &ok);
    api->ctx_free = (EzOpenSslCtxFreeFn)ez_http_dlsym_required(api->ssl_handle, "SSL_CTX_free", &ok);
    api->ctx_default_paths = (EzOpenSslCtxDefaultPathsFn)ez_http_dlsym_required(api->ssl_handle, "SSL_CTX_set_default_verify_paths", &ok);
    api->ctx_set_verify = (EzOpenSslCtxSetVerifyFn)ez_http_dlsym_required(api->ssl_handle, "SSL_CTX_set_verify", &ok);
    api->ssl_new = (EzOpenSslNewFn)ez_http_dlsym_required(api->ssl_handle, "SSL_new", &ok);
    api->ssl_free = (EzOpenSslFreeFn)ez_http_dlsym_required(api->ssl_handle, "SSL_free", &ok);
    api->ssl_set_fd = (EzOpenSslSetFdFn)ez_http_dlsym_required(api->ssl_handle, "SSL_set_fd", &ok);
    api->ssl_ctrl = (EzOpenSslCtrlFn)ez_http_dlsym_required(api->ssl_handle, "SSL_ctrl", &ok);
    api->ssl_get0_param = (EzOpenSslGet0ParamFn)ez_http_dlsym_required(api->ssl_handle, "SSL_get0_param", &ok);
    api->ssl_connect = (EzOpenSslConnectFn)ez_http_dlsym_required(api->ssl_handle, "SSL_connect", &ok);
    api->ssl_read = (EzOpenSslReadFn)ez_http_dlsym_required(api->ssl_handle, "SSL_read", &ok);
    api->ssl_write = (EzOpenSslWriteFn)ez_http_dlsym_required(api->ssl_handle, "SSL_write", &ok);
    api->ssl_shutdown = (EzOpenSslShutdownFn)ez_http_dlsym_required(api->ssl_handle, "SSL_shutdown", &ok);
    api->ssl_get_verify_result = (EzOpenSslVerifyResultFn)ez_http_dlsym_required(api->ssl_handle, "SSL_get_verify_result", &ok);
    api->param_set_host = (EzOpenSslParamSetHostFn)ez_http_dlsym_required(api->crypto_handle, "X509_VERIFY_PARAM_set1_host", &ok);
    api->param_set_ip = (EzOpenSslParamSetIpFn)ez_http_dlsym_required(api->crypto_handle, "X509_VERIFY_PARAM_set1_ip_asc", &ok);
    if ((!api->tls_client_method && !api->sslv23_client_method) || !ok) {
        ez_http_tls_reset_failed(api);
        return false;
    }
    api->available = true;
    return true;
}

static bool ez_http_tls_host_is_ip_literal(const char *host) {
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

static bool ez_http_tls_configure_verify(EzHttpTlsApi *api, SSL *ssl, const char *host) {
    if (!api || !ssl || !host || !host[0]) return false;
    X509_VERIFY_PARAM *param = api->ssl_get0_param(ssl);
    if (!param) return false;
    if (ez_http_tls_host_is_ip_literal(host)) return api->param_set_ip(param, host) == 1;
    return api->param_set_host(param, host, 0) == 1;
}

static bool ez_http_tls_start(EzHttpConnection *conn, const char *host) {
    EzHttpTlsApi *api = &ez_http_tls_api;
    if (!conn || conn->sock == EZ_INVALID_SOCKET || !ez_http_load_tls(api)) return false;
    if (api->init_ssl) api->init_ssl(0, NULL);
    const SSL_METHOD *method = api->tls_client_method ? api->tls_client_method() : api->sslv23_client_method();
    if (!method) return false;
    SSL_CTX *ctx = api->ctx_new(method);
    if (!ctx) return false;

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
    if (ok && !ez_http_tls_configure_verify(api, ssl, host)) ok = false;
    if (ok && !ez_http_tls_host_is_ip_literal(host)) {
        ok = api->ssl_ctrl(ssl, ssl_ctrl_set_tlsext_hostname, tlsext_nametype_host_name, (void *)host) > 0;
    }
    if (ok) ok = api->ssl_set_fd(ssl, (int)conn->sock) == 1;
    if (ok) ok = api->ssl_connect(ssl) == 1;
    if (ok) ok = api->ssl_get_verify_result(ssl) == 0;
    if (!ok) {
        if (ssl) api->ssl_free(ssl);
        api->ctx_free(ctx);
        return false;
    }
    conn->tls_ctx = ctx;
    conn->tls_ssl = ssl;
    conn->tls = true;
    return true;
}
#endif

static void ez_http_conn_close(EzHttpConnection *conn) {
    if (!conn) return;
#if EZ_HTTP_HAS_OPENSSL_TLS
    if (conn->tls_ssl) {
        EzHttpTlsApi *api = &ez_http_tls_api;
        if (api->ssl_shutdown) api->ssl_shutdown(conn->tls_ssl);
        if (api->ssl_free) api->ssl_free(conn->tls_ssl);
        conn->tls_ssl = NULL;
    }
    if (conn->tls_ctx) {
        EzHttpTlsApi *api = &ez_http_tls_api;
        if (api->ctx_free) api->ctx_free(conn->tls_ctx);
        conn->tls_ctx = NULL;
    }
#endif
    if (conn->sock != EZ_INVALID_SOCKET) {
        ez_close_socket(conn->sock);
        conn->sock = EZ_INVALID_SOCKET;
    }
    conn->tls = false;
}

static bool ez_http_conn_open(const EzUrlParts *parts, EzHttpConnection *conn) {
    if (!parts || !conn) return false;
    *conn = (EzHttpConnection){0};
    conn->sock = ez_http_connect(parts->host, parts->port);
    if (conn->sock == EZ_INVALID_SOCKET) return false;
    if (!parts->tls) return true;
#if EZ_HTTP_HAS_OPENSSL_TLS
    if (ez_http_tls_start(conn, parts->host)) return true;
#endif
    ez_http_conn_close(conn);
    return false;
}

static bool ez_http_conn_send_all(EzHttpConnection *conn, const char *data, size_t len) {
    if (!conn || conn->sock == EZ_INVALID_SOCKET) return false;
#if EZ_HTTP_HAS_OPENSSL_TLS
    if (conn->tls) {
        EzHttpTlsApi *api = &ez_http_tls_api;
        size_t sent = 0;
        while (sent < len) {
            size_t remaining = len - sent;
            int chunk = remaining > (size_t)INT_MAX ? INT_MAX : (int)remaining;
            int n = api->ssl_write(conn->tls_ssl, data + sent, chunk);
            if (n <= 0) return false;
            sent += (size_t)n;
        }
        return true;
    }
#endif
    return ez_send_all(conn->sock, data, len);
}

static int ez_http_conn_recv(EzHttpConnection *conn, uint8_t *buffer, size_t len) {
    if (!conn || conn->sock == EZ_INVALID_SOCKET || !buffer || len == 0) return -1;
#if EZ_HTTP_HAS_OPENSSL_TLS
    if (conn->tls) {
        EzHttpTlsApi *api = &ez_http_tls_api;
        int chunk = len > (size_t)INT_MAX ? INT_MAX : (int)len;
        return api->ssl_read(conn->tls_ssl, buffer, chunk);
    }
#endif
#if defined(_WIN32)
    return recv(conn->sock, (char *)buffer, (int)len, 0);
#else
    ssize_t n = recv(conn->sock, buffer, len, 0);
    if (n > INT_MAX) return INT_MAX;
    return (int)n;
#endif
}

static EzHttpServer *ez_server_from_value(const HttpServer *server) {
    if (!server || server->handle == 0) return NULL;
    return (EzHttpServer *)(uintptr_t)server->handle;
}

static bool ez_http_server_sync_init(EzHttpServer *server) {
    if (!server) return false;
#if defined(_WIN32)
    InitializeCriticalSection(&server->worker_lock);
    InitializeConditionVariable(&server->worker_done);
#else
    if (pthread_mutex_init(&server->worker_lock, NULL) != 0) return false;
    if (pthread_cond_init(&server->worker_done, NULL) != 0) {
        pthread_mutex_destroy(&server->worker_lock);
        return false;
    }
#endif
    server->sync_ready = true;
    return true;
}

static void ez_http_server_sync_destroy(EzHttpServer *server) {
    if (!server || !server->sync_ready) return;
#if defined(_WIN32)
    DeleteCriticalSection(&server->worker_lock);
#else
    pthread_cond_destroy(&server->worker_done);
    pthread_mutex_destroy(&server->worker_lock);
#endif
    server->sync_ready = false;
}

static void ez_http_worker_done(EzHttpServer *server) {
    if (!server || !server->sync_ready) return;
#if defined(_WIN32)
    EnterCriticalSection(&server->worker_lock);
    if (server->active_workers > 0) server->active_workers--;
    WakeAllConditionVariable(&server->worker_done);
    LeaveCriticalSection(&server->worker_lock);
#else
    pthread_mutex_lock(&server->worker_lock);
    if (server->active_workers > 0) server->active_workers--;
    pthread_cond_broadcast(&server->worker_done);
    pthread_mutex_unlock(&server->worker_lock);
#endif
}

static void ez_http_wait_workers(EzHttpServer *server) {
    if (!server || !server->sync_ready) return;
#if defined(_WIN32)
    EnterCriticalSection(&server->worker_lock);
    while (server->active_workers > 0) SleepConditionVariableCS(&server->worker_done, &server->worker_lock, INFINITE);
    LeaveCriticalSection(&server->worker_lock);
#else
    pthread_mutex_lock(&server->worker_lock);
    while (server->active_workers > 0) pthread_cond_wait(&server->worker_done, &server->worker_lock);
    pthread_mutex_unlock(&server->worker_lock);
#endif
}

static ez_socket_t ez_http_mark_started(EzHttpServer *server) {
    if (!server || !server->sync_ready) return EZ_INVALID_SOCKET;
#if defined(_WIN32)
    EnterCriticalSection(&server->worker_lock);
    server->started = true;
    server->running = true;
    ez_socket_t sock = server->sock;
    LeaveCriticalSection(&server->worker_lock);
#else
    pthread_mutex_lock(&server->worker_lock);
    server->started = true;
    server->running = true;
    ez_socket_t sock = server->sock;
    pthread_mutex_unlock(&server->worker_lock);
#endif
    return sock;
}

static ez_socket_t ez_http_take_listener(EzHttpServer *server, bool *was_running, bool *was_started) {
    if (was_running) *was_running = false;
    if (was_started) *was_started = false;
    if (!server || !server->sync_ready) return EZ_INVALID_SOCKET;
#if defined(_WIN32)
    EnterCriticalSection(&server->worker_lock);
    if (was_running) *was_running = server->running;
    if (was_started) *was_started = server->started;
    server->running = false;
    ez_socket_t sock = server->sock;
    server->sock = EZ_INVALID_SOCKET;
    LeaveCriticalSection(&server->worker_lock);
#else
    pthread_mutex_lock(&server->worker_lock);
    if (was_running) *was_running = server->running;
    if (was_started) *was_started = server->started;
    server->running = false;
    ez_socket_t sock = server->sock;
    server->sock = EZ_INVALID_SOCKET;
    pthread_mutex_unlock(&server->worker_lock);
#endif
    return sock;
}

static bool ez_http_server_running(EzHttpServer *server) {
    if (!server || !server->sync_ready) return false;
#if defined(_WIN32)
    EnterCriticalSection(&server->worker_lock);
    bool running = server->running;
    LeaveCriticalSection(&server->worker_lock);
#else
    pthread_mutex_lock(&server->worker_lock);
    bool running = server->running;
    pthread_mutex_unlock(&server->worker_lock);
#endif
    return running;
}

static bool ez_http_wait_readable(ez_socket_t sock) {
    fd_set read_fds;
    FD_ZERO(&read_fds);
    FD_SET(sock, &read_fds);
    struct timeval timeout;
    timeout.tv_sec = 0;
    timeout.tv_usec = 100000;
#if defined(_WIN32)
    int ready = select(0, &read_fds, NULL, NULL, &timeout);
#else
    int ready = select(sock + 1, &read_fds, NULL, NULL, &timeout);
#endif
    return ready > 0 && FD_ISSET(sock, &read_fds);
}

static void ez_http_server_free(EzHttpServer *server) {
    if (!server) return;
    ez_socket_t sock = ez_http_take_listener(server, NULL, NULL);
    if (sock != EZ_INVALID_SOCKET) ez_close_socket(sock);
    ez_http_wait_workers(server);
    ez_http_server_sync_destroy(server);
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

#if defined(_WIN32)
static DWORD WINAPI ez_http_client_worker(LPVOID arg) {
#else
static void *ez_http_client_worker(void *arg) {
#endif
    EzHttpClientWorker *worker = (EzHttpClientWorker *)arg;
    if (!worker) {
#if defined(_WIN32)
        return 0;
#else
        return NULL;
#endif
    }
    EzHttpServer *server = worker->server;
    ez_socket_t client = worker->client;
    free(worker);
    ez_http_handle_client(server, client);
    ez_close_socket(client);
    ez_http_worker_done(server);
#if defined(_WIN32)
    return 0;
#else
    return NULL;
#endif
}

static void ez_http_worker_add(EzHttpServer *server) {
    if (!server || !server->sync_ready) return;
#if defined(_WIN32)
    EnterCriticalSection(&server->worker_lock);
    server->active_workers++;
    LeaveCriticalSection(&server->worker_lock);
#else
    pthread_mutex_lock(&server->worker_lock);
    server->active_workers++;
    pthread_mutex_unlock(&server->worker_lock);
#endif
}

static bool ez_http_start_client_worker(EzHttpServer *server, ez_socket_t client) {
    if (!server || !server->sync_ready) return false;
    EzHttpClientWorker *worker = (EzHttpClientWorker *)malloc(sizeof(EzHttpClientWorker));
    if (!worker) return false;
    worker->server = server;
    worker->client = client;
    ez_http_worker_add(server);
#if defined(_WIN32)
    HANDLE thread = CreateThread(NULL, 0, ez_http_client_worker, worker, 0, NULL);
    if (!thread) {
        ez_http_worker_done(server);
        free(worker);
        return false;
    }
    CloseHandle(thread);
    return true;
#else
    pthread_attr_t attr;
    if (pthread_attr_init(&attr) != 0) {
        ez_http_worker_done(server);
        free(worker);
        return false;
    }
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
    pthread_t thread;
    int created = pthread_create(&thread, &attr, ez_http_client_worker, worker);
    pthread_attr_destroy(&attr);
    if (created != 0) {
        ez_http_worker_done(server);
        free(worker);
        return false;
    }
    return true;
#endif
}

static OptHttpResponse ez_http_fetch(const char *method, const char *url, const Dict *headers, const Blob *body) {
    int64_t body_size = 0;
    if (body) {
        if (!ez_blob_valid(body) || (uint64_t)body->size > (uint64_t)SIZE_MAX) return ez_http_none();
        body_size = body->size;
    }
    EzUrlParts parts = {0};
    if (!ez_parse_http_url(url, &parts)) return ez_http_none();
    EzHttpConnection conn = {0};
    if (!ez_http_conn_open(&parts, &conn)) {
        ez_url_parts_free(&parts);
        return ez_http_none();
    }

    const char *verb = method && method[0] ? method : "GET";
    size_t headers_len = ez_request_headers_len(headers);
    int req_len = snprintf(NULL, 0,
        "%s %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\nContent-Length: %lld\r\n",
        verb, parts.path, parts.host_header, (long long)body_size);
    if (req_len < 0) {
        ez_http_conn_close(&conn);
        ez_url_parts_free(&parts);
        return ez_http_none();
    }
    size_t request_size = (size_t)req_len + headers_len + 2;
    char *request = (char *)malloc(request_size + 1);
    if (!request) {
        ez_http_conn_close(&conn);
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

    bool ok = ez_http_conn_send_all(&conn, request, offset);
    if (ok && body_size > 0) ok = ez_http_conn_send_all(&conn, (const char *)body->data, (size_t)body_size);
    free(request);
    ez_url_parts_free(&parts);
    if (!ok) {
        ez_http_conn_close(&conn);
        return ez_http_none();
    }

    uint8_t *response = NULL;
    size_t response_len = 0;
    size_t response_cap = 0;
    uint8_t chunk[4096];
    for (;;) {
        int n = ez_http_conn_recv(&conn, chunk, sizeof(chunk));
        if (n < 0) {
            free(response);
            ez_http_conn_close(&conn);
            return ez_http_none();
        }
        if (n == 0) break;
        if (!ez_append_bytes(&response, &response_len, &response_cap, chunk, (size_t)n)) {
            free(response);
            ez_http_conn_close(&conn);
            return ez_http_none();
        }
    }
    ez_http_conn_close(&conn);
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
    if (port < 0 || port > 65535) return (HttpServer){0};
    EzHttpServer *server = (EzHttpServer *)calloc(1, sizeof(EzHttpServer));
    if (!server) return (HttpServer){0};
    const char *bind_host = host && host[0] ? host : "127.0.0.1";
    server->host = ez_strdup_range(bind_host, strlen(bind_host));
    server->port = port;
    server->sock = EZ_INVALID_SOCKET;
    if (!server->host || !ez_http_server_sync_init(server)) {
        ez_http_server_sync_destroy(server);
        free(server->host);
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
    ez_socket_t listener = ez_http_mark_started(server);
    while (listener != EZ_INVALID_SOCKET && ez_http_server_running(server)) {
        if (!ez_http_wait_readable(listener)) continue;
#if defined(_WIN32)
        ez_socket_t client = (ez_socket_t)accept(listener, NULL, NULL);
#else
        ez_socket_t client = accept(listener, NULL, NULL);
#endif
        if (client == EZ_INVALID_SOCKET) break;
        if (!ez_http_start_client_worker(server, client)) {
            ez_http_handle_client(server, client);
            ez_close_socket(client);
        }
    }
    ez_http_server_free(server);
    value->handle = 0;
}

void HttpServer_stop(HttpServer *value) {
    EzHttpServer *server = ez_server_from_value(value);
    if (!server) return;
    bool was_running = false;
    bool was_started = false;
    ez_socket_t sock = ez_http_take_listener(server, &was_running, &was_started);
    if (sock != EZ_INVALID_SOCKET) {
        shutdown(sock, EZ_SHUTDOWN_BOTH);
        ez_close_socket(sock);
    }
    if (was_running || was_started) {
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
