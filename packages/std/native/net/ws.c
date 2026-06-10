// EzLang std/net/ws 原生封装层
// 当前实现 ws:// 握手、客户端掩码、分片重组和 ping/pong 控制帧；TLS 与异步挂起后续接入。

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#if defined(_WIN32)
#include <winsock2.h>
#include <ws2tcpip.h>
#include <bcrypt.h>
typedef SOCKET ez_socket_t;
#define EZ_INVALID_SOCKET INVALID_SOCKET
#define ez_close_socket closesocket
#else
#include <errno.h>
#include <fcntl.h>
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

enum { EZ_WS_MAX_MESSAGE = 16 * 1024 * 1024 };

typedef struct {
    char *host;
    char *host_header;
    char *path;
    char port[8];
} EzWsUrl;

typedef struct {
    bool fin;
    uint8_t opcode;
    bool masked;
    uint64_t length;
    uint8_t mask[4];
} EzWsFrameHeader;

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

static bool ez_blob_valid(const Blob *data) {
    return data && data->size >= 0 && (data->size == 0 || data->data);
}

static ez_socket_t ez_socket_from_handle(int64_t handle) {
    if (handle == 0) return EZ_INVALID_SOCKET;
    return (ez_socket_t)handle;
}

static void ez_ws_url_free(EzWsUrl *url) {
    if (!url) return;
    free(url->host);
    free(url->host_header);
    free(url->path);
    url->host = NULL;
    url->host_header = NULL;
    url->path = NULL;
}

static char ez_ascii_lower(char ch) {
    return (ch >= 'A' && ch <= 'Z') ? (char)(ch - 'A' + 'a') : ch;
}

static bool ez_ws_has_scheme(const char *url) {
    const char *prefix = "ws://";
    if (!url) return false;
    for (size_t i = 0; prefix[i] != '\0'; ++i) {
        if (url[i] == '\0' || ez_ascii_lower(url[i]) != prefix[i]) return false;
    }
    return true;
}

static bool ez_ws_url_bytes_valid(const char *start, const char *end) {
    if (!start || !end || start > end) return false;
    for (const char *p = start; p < end; ++p) {
        unsigned char ch = (unsigned char)*p;
        if (ch <= 0x20 || ch == 0x7F) return false;
    }
    return true;
}

static bool ez_parse_ws_port(const char *start, const char *end, char out[8]) {
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

static char *ez_make_ws_host_header(const char *host, const char *port, bool has_port) {
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

static bool ez_parse_ws_url(const char *url, EzWsUrl *out) {
    size_t prefix_len = strlen("ws://");
    if (!out) return false;
    *out = (EzWsUrl){0};
    if (!ez_ws_has_scheme(url)) return false;
    const char *host_start = url + prefix_len;
    const char *fragment_start = strchr(host_start, '#');
    const char *url_end = fragment_start ? fragment_start : url + strlen(url);
    const char *authority_end = host_start;
    while (authority_end < url_end && *authority_end != '/' && *authority_end != '?') authority_end++;
    if (authority_end == host_start || !ez_ws_url_bytes_valid(host_start, authority_end)) return false;

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
            if (*after != ':' || !ez_parse_ws_port(after + 1, authority_end, out->port)) return false;
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
            if (!ez_parse_ws_port(colon + 1, authority_end, out->port)) return false;
            has_port = true;
        }
        out->host = ez_strdup_range(host_start, (size_t)(host_end - host_start));
        host_for_header = ez_strdup_range(host_start, (size_t)(host_end - host_start));
    }
    if (!out->host || out->host[0] == '\0' || !host_for_header) goto fail;
    out->host_header = ez_make_ws_host_header(host_for_header, out->port, has_port);
    free(host_for_header);
    host_for_header = NULL;
    if (!out->host_header) goto fail;

    if (authority_end < url_end && !ez_ws_url_bytes_valid(authority_end, url_end)) goto fail;
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
    ez_ws_url_free(out);
    return false;
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

static bool ez_ws_system_random(uint8_t *data, size_t size) {
    if (size == 0) return true;
    if (!data) return false;
#if defined(_WIN32)
    return BCryptGenRandom(NULL, data, (ULONG)size, BCRYPT_USE_SYSTEM_PREFERRED_RNG) == 0;
#else
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd < 0) return false;
    size_t offset = 0;
    while (offset < size) {
        ssize_t n = read(fd, data + offset, size - offset);
        if (n > 0) {
            offset += (size_t)n;
            continue;
        }
        if (n < 0 && errno == EINTR) continue;
        close(fd);
        return false;
    }
    close(fd);
    return true;
#endif
}

static uint64_t ez_ws_mix_seed(uint64_t seed) {
    uint64_t z = seed + 0x9E3779B97F4A7C15ULL;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static uint64_t ez_ws_fallback_random(void) {
    static uint64_t state = 0;
    if (state == 0) {
        state = ez_ws_mix_seed((uint64_t)time(NULL) ^ (uint64_t)(uintptr_t)&state);
        if (state == 0) state = 0x9E3779B97F4A7C15ULL;
    }
    state ^= state >> 12;
    state ^= state << 25;
    state ^= state >> 27;
    return state * 0x2545F4914F6CDD1DULL;
}

static void ez_ws_random_bytes(uint8_t *data, size_t size) {
    if (!data || size == 0) return;
    if (ez_ws_system_random(data, size)) return;
    size_t offset = 0;
    while (offset < size) {
        uint64_t value = ez_ws_fallback_random();
        for (int i = 0; i < 8 && offset < size; ++i) data[offset++] = (uint8_t)(value >> (i * 8));
    }
}

static void ez_ws_random_mask(uint8_t mask[4]) {
    ez_ws_random_bytes(mask, 4);
}

static uint32_t ez_ws_rotl32(uint32_t value, unsigned int bits) {
    return (value << bits) | (value >> (32U - bits));
}

static uint32_t ez_ws_read_be32(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) |
           ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) |
           (uint32_t)bytes[3];
}

static void ez_ws_write_be32(uint8_t *out, uint32_t value) {
    out[0] = (uint8_t)(value >> 24);
    out[1] = (uint8_t)(value >> 16);
    out[2] = (uint8_t)(value >> 8);
    out[3] = (uint8_t)value;
}

static void ez_ws_write_be64(uint8_t *out, uint64_t value) {
    out[0] = (uint8_t)(value >> 56);
    out[1] = (uint8_t)(value >> 48);
    out[2] = (uint8_t)(value >> 40);
    out[3] = (uint8_t)(value >> 32);
    out[4] = (uint8_t)(value >> 24);
    out[5] = (uint8_t)(value >> 16);
    out[6] = (uint8_t)(value >> 8);
    out[7] = (uint8_t)value;
}

typedef struct {
    uint32_t state[5];
    uint64_t bit_len;
    uint8_t buffer[64];
    size_t buffer_len;
} EzWsSha1Ctx;

static void ez_ws_sha1_transform(EzWsSha1Ctx *ctx, const uint8_t block[64]) {
    uint32_t words[80];
    for (size_t i = 0; i < 16; ++i) words[i] = ez_ws_read_be32(block + i * 4);
    for (size_t i = 16; i < 80; ++i) words[i] = ez_ws_rotl32(words[i - 3] ^ words[i - 8] ^ words[i - 14] ^ words[i - 16], 1);

    uint32_t a = ctx->state[0];
    uint32_t b = ctx->state[1];
    uint32_t c = ctx->state[2];
    uint32_t d = ctx->state[3];
    uint32_t e = ctx->state[4];
    for (size_t i = 0; i < 80; ++i) {
        uint32_t f = 0;
        uint32_t k = 0;
        if (i < 20) {
            f = (b & c) | ((~b) & d);
            k = 0x5A827999U;
        } else if (i < 40) {
            f = b ^ c ^ d;
            k = 0x6ED9EBA1U;
        } else if (i < 60) {
            f = (b & c) | (b & d) | (c & d);
            k = 0x8F1BBCDCU;
        } else {
            f = b ^ c ^ d;
            k = 0xCA62C1D6U;
        }
        uint32_t temp = ez_ws_rotl32(a, 5) + f + e + k + words[i];
        e = d;
        d = c;
        c = ez_ws_rotl32(b, 30);
        b = a;
        a = temp;
    }
    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
}

static void ez_ws_sha1_init(EzWsSha1Ctx *ctx) {
    ctx->state[0] = 0x67452301U;
    ctx->state[1] = 0xEFCDAB89U;
    ctx->state[2] = 0x98BADCFEU;
    ctx->state[3] = 0x10325476U;
    ctx->state[4] = 0xC3D2E1F0U;
    ctx->bit_len = 0;
    ctx->buffer_len = 0;
}

static void ez_ws_sha1_update(EzWsSha1Ctx *ctx, const uint8_t *bytes, size_t size) {
    ctx->bit_len += (uint64_t)size << 3;
    while (size > 0) {
        size_t room = sizeof(ctx->buffer) - ctx->buffer_len;
        size_t take = size < room ? size : room;
        memcpy(ctx->buffer + ctx->buffer_len, bytes, take);
        ctx->buffer_len += take;
        bytes += take;
        size -= take;
        if (ctx->buffer_len == sizeof(ctx->buffer)) {
            ez_ws_sha1_transform(ctx, ctx->buffer);
            ctx->buffer_len = 0;
        }
    }
}

static void ez_ws_sha1_final(EzWsSha1Ctx *ctx, uint8_t out[20]) {
    ctx->buffer[ctx->buffer_len++] = 0x80;
    if (ctx->buffer_len > 56) {
        memset(ctx->buffer + ctx->buffer_len, 0, sizeof(ctx->buffer) - ctx->buffer_len);
        ez_ws_sha1_transform(ctx, ctx->buffer);
        ctx->buffer_len = 0;
    }
    memset(ctx->buffer + ctx->buffer_len, 0, 56 - ctx->buffer_len);
    ez_ws_write_be64(ctx->buffer + 56, ctx->bit_len);
    ez_ws_sha1_transform(ctx, ctx->buffer);
    for (size_t i = 0; i < 5; ++i) ez_ws_write_be32(out + i * 4, ctx->state[i]);
}

static bool ez_ws_base64_encode(const uint8_t *data, size_t size, char *out, size_t out_cap) {
    static const char table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    size_t out_len = ((size + 2) / 3) * 4;
    if (!out || out_cap <= out_len || (size > 0 && !data)) return false;
    size_t offset = 0;
    for (size_t i = 0; i < size; i += 3) {
        size_t remain = size - i;
        uint32_t value = ((uint32_t)data[i] << 16) |
                         (remain > 1 ? ((uint32_t)data[i + 1] << 8) : 0) |
                         (remain > 2 ? (uint32_t)data[i + 2] : 0);
        out[offset++] = table[(value >> 18) & 0x3F];
        out[offset++] = table[(value >> 12) & 0x3F];
        out[offset++] = remain > 1 ? table[(value >> 6) & 0x3F] : '=';
        out[offset++] = remain > 2 ? table[value & 0x3F] : '=';
    }
    out[offset] = '\0';
    return true;
}

static bool ez_ws_generate_key(char out[25]) {
    uint8_t nonce[16];
    ez_ws_random_bytes(nonce, sizeof(nonce));
    return ez_ws_base64_encode(nonce, sizeof(nonce), out, 25);
}

static bool ez_ws_expected_accept(const char *key, char out[29]) {
    static const char guid[] = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
    if (!key) return false;
    uint8_t digest[20];
    EzWsSha1Ctx ctx;
    ez_ws_sha1_init(&ctx);
    ez_ws_sha1_update(&ctx, (const uint8_t *)key, strlen(key));
    ez_ws_sha1_update(&ctx, (const uint8_t *)guid, strlen(guid));
    ez_ws_sha1_final(&ctx, digest);
    return ez_ws_base64_encode(digest, sizeof(digest), out, 29);
}

static bool ez_ws_find_header_end(const char *data, size_t size) {
    if (!data) return false;
    for (size_t i = 0; i + 3 < size; ++i) {
        if (data[i] == '\r' && data[i + 1] == '\n' && data[i + 2] == '\r' && data[i + 3] == '\n') return true;
    }
    return false;
}

static char *ez_ws_read_handshake_response(ez_socket_t sock) {
    size_t len = 0;
    size_t cap = 0;
    char *buffer = NULL;
    char chunk[1024];
    while (len <= 64 * 1024) {
#if defined(_WIN32)
        int n = recv(sock, chunk, (int)sizeof(chunk), 0);
#else
        ssize_t n = recv(sock, chunk, sizeof(chunk), 0);
#endif
        if (n <= 0) {
            free(buffer);
            return NULL;
        }
        size_t chunk_len = (size_t)n;
        if (len + chunk_len + 1 > cap) {
            size_t next_cap = cap ? cap : 2048;
            while (len + chunk_len + 1 > next_cap) next_cap *= 2;
            char *next = (char *)realloc(buffer, next_cap);
            if (!next) {
                free(buffer);
                return NULL;
            }
            buffer = next;
            cap = next_cap;
        }
        memcpy(buffer + len, chunk, chunk_len);
        len += chunk_len;
        buffer[len] = '\0';
        if (ez_ws_find_header_end(buffer, len)) return buffer;
    }
    free(buffer);
    return NULL;
}

static bool ez_ws_range_ieq(const char *start, const char *end, const char *value) {
    if (!start || !end || !value || start > end) return false;
    size_t len = (size_t)(end - start);
    if (strlen(value) != len) return false;
    for (size_t i = 0; i < len; ++i) {
        if (ez_ascii_lower(start[i]) != ez_ascii_lower(value[i])) return false;
    }
    return true;
}

static bool ez_ws_header_token_matches(const char *start, const char *end, const char *token) {
    if (!start || !end || !token || start > end) return false;
    const char *part = start;
    while (part <= end) {
        const char *comma = part;
        while (comma < end && *comma != ',') comma++;
        const char *value_start = part;
        const char *value_end = comma;
        while (value_start < value_end && (*value_start == ' ' || *value_start == '\t')) value_start++;
        while (value_end > value_start && (value_end[-1] == ' ' || value_end[-1] == '\t')) value_end--;
        if (ez_ws_range_ieq(value_start, value_end, token)) return true;
        if (comma == end) break;
        part = comma + 1;
    }
    return false;
}

static bool ez_ws_header_matches(const char *response, const char *name, const char *expected, bool token_match) {
    if (!response || !name || !expected) return false;
    const char *line = strstr(response, "\r\n");
    if (!line) return false;
    line += 2;
    size_t name_len = strlen(name);
    while (*line) {
        const char *line_end = strstr(line, "\r\n");
        if (!line_end) return false;
        if (line_end == line) return false;
        const char *colon = memchr(line, ':', (size_t)(line_end - line));
        if (colon && (size_t)(colon - line) == name_len && ez_ws_range_ieq(line, colon, name)) {
            const char *value_start = colon + 1;
            const char *value_end = line_end;
            while (value_start < value_end && (*value_start == ' ' || *value_start == '\t')) value_start++;
            while (value_end > value_start && (value_end[-1] == ' ' || value_end[-1] == '\t')) value_end--;
            if (token_match) return ez_ws_header_token_matches(value_start, value_end, expected);
            return (size_t)(value_end - value_start) == strlen(expected) && memcmp(value_start, expected, (size_t)(value_end - value_start)) == 0;
        }
        line = line_end + 2;
    }
    return false;
}

static bool ez_ws_status_is_101(const char *response) {
    if (!response || strncmp(response, "HTTP/", 5) != 0) return false;
    const char *line_end = strstr(response, "\r\n");
    if (!line_end) return false;
    const char *space = memchr(response, ' ', (size_t)(line_end - response));
    if (!space || space + 4 > line_end) return false;
    return space[1] == '1' && space[2] == '0' && space[3] == '1' && (space + 4 == line_end || space[4] == ' ' || space[4] == '\t');
}

static bool ez_ws_handshake_response_valid(ez_socket_t sock, const char *key) {
    char expected_accept[29];
    if (!ez_ws_expected_accept(key, expected_accept)) return false;
    char *response = ez_ws_read_handshake_response(sock);
    if (!response) return false;
    bool ok = ez_ws_status_is_101(response) &&
              ez_ws_header_matches(response, "Upgrade", "websocket", true) &&
              ez_ws_header_matches(response, "Connection", "Upgrade", true) &&
              ez_ws_header_matches(response, "Sec-WebSocket-Accept", expected_accept, false);
    free(response);
    return ok;
}

static bool ez_ws_send_frame(ez_socket_t sock, uint8_t opcode, const uint8_t *payload, uint64_t size, bool mask_payload) {
    uint8_t header[14];
    size_t header_len = 0;
    header[header_len++] = (uint8_t)(0x80 | (opcode & 0x0F));
    uint8_t mask_bit = mask_payload ? 0x80 : 0;
    if (size <= 125) {
        header[header_len++] = (uint8_t)(mask_bit | size);
    } else if (size <= 0xFFFF) {
        header[header_len++] = (uint8_t)(mask_bit | 126);
        header[header_len++] = (uint8_t)((size >> 8) & 0xFF);
        header[header_len++] = (uint8_t)(size & 0xFF);
    } else {
        header[header_len++] = (uint8_t)(mask_bit | 127);
        for (int shift = 56; shift >= 0; shift -= 8) {
            header[header_len++] = (uint8_t)((size >> shift) & 0xFF);
        }
    }

    uint8_t mask[4] = {0};
    if (mask_payload) {
        ez_ws_random_mask(mask);
        memcpy(header + header_len, mask, sizeof(mask));
        header_len += sizeof(mask);
    }
    if (!ez_send_all_bytes(sock, header, header_len)) return false;
    if (size == 0) return true;
    if (!payload) return false;
    if (!mask_payload) return ez_send_all_bytes(sock, payload, (size_t)size);

    uint8_t stack_buf[4096];
    uint8_t *buf = size <= sizeof(stack_buf) ? stack_buf : (uint8_t *)malloc((size_t)size);
    if (!buf) return false;
    for (uint64_t i = 0; i < size; ++i) buf[i] = payload[i] ^ mask[i % 4];
    bool ok = ez_send_all_bytes(sock, buf, (size_t)size);
    if (buf != stack_buf) free(buf);
    return ok;
}

static bool ez_ws_read_frame_header(ez_socket_t sock, EzWsFrameHeader *out) {
    uint8_t header[2];
    if (!out || !ez_recv_exact(sock, header, sizeof(header))) return false;
    memset(out, 0, sizeof(*out));
    out->fin = (header[0] & 0x80) != 0;
    out->opcode = header[0] & 0x0F;
    out->masked = (header[1] & 0x80) != 0;
    out->length = header[1] & 0x7F;
    if (out->length == 126) {
        uint8_t ext[2];
        if (!ez_recv_exact(sock, ext, sizeof(ext))) return false;
        out->length = ((uint64_t)ext[0] << 8) | ext[1];
    } else if (out->length == 127) {
        uint8_t ext[8];
        if (!ez_recv_exact(sock, ext, sizeof(ext))) return false;
        out->length = 0;
        for (int i = 0; i < 8; ++i) out->length = (out->length << 8) | ext[i];
    }
    if (out->masked && !ez_recv_exact(sock, out->mask, sizeof(out->mask))) return false;
    return true;
}

static bool ez_ws_read_payload(ez_socket_t sock, const EzWsFrameHeader *header, uint8_t *data) {
    if (!header) return false;
    if (header->length == 0) return true;
    if (!data || !ez_recv_exact(sock, data, (size_t)header->length)) return false;
    if (header->masked) {
        for (uint64_t i = 0; i < header->length; ++i) data[i] ^= header->mask[i % 4];
    }
    return true;
}

static bool ez_ws_discard_payload(ez_socket_t sock, const EzWsFrameHeader *header) {
    if (!header || header->length > EZ_WS_MAX_MESSAGE) return false;
    uint8_t stack_buf[512];
    uint64_t remaining = header->length;
    uint64_t offset = 0;
    while (remaining > 0) {
        size_t chunk = remaining > sizeof(stack_buf) ? sizeof(stack_buf) : (size_t)remaining;
        if (!ez_recv_exact(sock, stack_buf, chunk)) return false;
        if (header->masked) {
            for (size_t i = 0; i < chunk; ++i) stack_buf[i] ^= header->mask[(offset + i) % 4];
        }
        offset += chunk;
        remaining -= chunk;
    }
    return true;
}

static bool ez_ws_append_message(uint8_t **data, uint64_t *size, const uint8_t *chunk, uint64_t chunk_size, int64_t max_bytes) {
    if (!data || !size || chunk_size > EZ_WS_MAX_MESSAGE || *size > EZ_WS_MAX_MESSAGE - chunk_size) return false;
    uint64_t next_size = *size + chunk_size;
    if (next_size > (uint64_t)max_bytes) return false;
    uint8_t *next = (uint8_t *)realloc(*data, (size_t)(next_size ? next_size : 1));
    if (!next) return false;
    if (chunk_size > 0 && chunk) memcpy(next + *size, chunk, (size_t)chunk_size);
    *data = next;
    *size = next_size;
    return true;
}

static bool ez_ws_handle_control_frame(ez_socket_t sock, const EzWsFrameHeader *header) {
    if (!header || !header->fin || header->length > 125) return false;
    uint8_t payload[125];
    if (!ez_ws_read_payload(sock, header, payload)) return false;
    if (header->opcode == 0x9) {
        return ez_ws_send_frame(sock, 0xA, payload, header->length, true);
    }
    if (header->opcode == 0xA) return true;
    return false;
}

OptWsConn wsConnect(const char *url) {
    EzWsUrl parts = {0};
    if (!ez_parse_ws_url(url, &parts)) return ez_ws_none();
    ez_socket_t sock = ez_connect_socket(parts.host, parts.port);
    if (sock == EZ_INVALID_SOCKET) {
        ez_ws_url_free(&parts);
        return ez_ws_none();
    }

    char key[25];
    if (!ez_ws_generate_key(key)) {
        ez_close_socket(sock);
        ez_ws_url_free(&parts);
        return ez_ws_none();
    }

    int req_len = snprintf(NULL, 0,
        "GET %s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: %s\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n",
        parts.path, parts.host_header, key);
    if (req_len < 0) {
        ez_close_socket(sock);
        ez_ws_url_free(&parts);
        return ez_ws_none();
    }
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
        "Sec-WebSocket-Key: %s\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n",
        parts.path, parts.host_header, key);
    ez_ws_url_free(&parts);

    bool ok = ez_send_all(sock, request, (size_t)req_len) && ez_ws_handshake_response_valid(sock, key);
    free(request);
    if (!ok) {
        ez_close_socket(sock);
        return ez_ws_none();
    }
    return (OptWsConn){true, {(int64_t)sock}};
}

int64_t wsSend(const WsConn *conn, const Blob *data) {
    if (!conn || !ez_blob_valid(data) || !ez_net_init()) return -1;
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return -1;
    uint64_t size = (uint64_t)data->size;
    if (size > EZ_WS_MAX_MESSAGE) return -1;
    return ez_ws_send_frame(sock, 0x2, data->data, size, true) ? (int64_t)size : -1;
}

OptBlob wsRecv(const WsConn *conn, int64_t maxBytes) {
    if (!conn || maxBytes < 0 || !ez_net_init()) return ez_ws_none_blob();
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return ez_ws_none_blob();
    if ((uint64_t)maxBytes > EZ_WS_MAX_MESSAGE) maxBytes = EZ_WS_MAX_MESSAGE;

    uint8_t *message = NULL;
    uint64_t message_size = 0;
    bool receiving_message = false;
    for (;;) {
        EzWsFrameHeader header;
        if (!ez_ws_read_frame_header(sock, &header)) {
            free(message);
            return ez_ws_none_blob();
        }

        if (header.opcode == 0x8) {
            ez_ws_discard_payload(sock, &header);
            free(message);
            return ez_ws_empty_blob();
        }
        if (header.opcode == 0x9 || header.opcode == 0xA) {
            if (!ez_ws_handle_control_frame(sock, &header)) {
                free(message);
                return ez_ws_none_blob();
            }
            continue;
        }
        if (header.opcode != 0x0 && header.opcode != 0x1 && header.opcode != 0x2) {
            if (!ez_ws_discard_payload(sock, &header)) {
                free(message);
                return ez_ws_none_blob();
            }
            continue;
        }
        if (header.opcode == 0x0 && !receiving_message) {
            if (!ez_ws_discard_payload(sock, &header)) return ez_ws_none_blob();
            continue;
        }
        if ((header.opcode == 0x1 || header.opcode == 0x2) && receiving_message) {
            free(message);
            if (!ez_ws_discard_payload(sock, &header)) return ez_ws_none_blob();
            return ez_ws_none_blob();
        }
        if (header.length > EZ_WS_MAX_MESSAGE || message_size > EZ_WS_MAX_MESSAGE - header.length || message_size + header.length > (uint64_t)maxBytes) {
            free(message);
            if (!ez_ws_discard_payload(sock, &header)) return ez_ws_none_blob();
            return ez_ws_none_blob();
        }

        uint8_t *chunk = NULL;
        if (header.length > 0) {
            chunk = (uint8_t *)malloc((size_t)header.length);
            if (!chunk) {
                free(message);
                return ez_ws_none_blob();
            }
        }
        if (!ez_ws_read_payload(sock, &header, chunk)) {
            free(chunk);
            free(message);
            return ez_ws_none_blob();
        }
        if (!ez_ws_append_message(&message, &message_size, chunk, header.length, maxBytes)) {
            free(chunk);
            free(message);
            return ez_ws_none_blob();
        }
        free(chunk);

        receiving_message = !header.fin;
        if (header.fin) {
            if (message_size == 0) {
                free(message);
                return ez_ws_empty_blob();
            }
            return (OptBlob){true, {message, (int64_t)message_size}};
        }
    }
}

bool wsClose(const WsConn *conn) {
    if (!conn) return false;
    ez_socket_t sock = ez_socket_from_handle(conn->handle);
    if (sock == EZ_INVALID_SOCKET) return false;
    ez_ws_send_frame(sock, 0x8, NULL, 0, true);
    return ez_close_socket(sock) == 0;
}
