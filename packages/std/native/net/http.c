// EzLang std/net/http 原生封装层
#include <stdint.h>

typedef struct { int32_t status; void *headers; void *body; } HttpResponse;
typedef struct { const char *method; const char *url; void *headers; void *body; } HttpRequest;
typedef struct { int64_t handle; } HttpServer;

HttpResponse *fetch(const char *url) { (void)url; return 0; }
HttpResponse *fetchEx(HttpRequest req) { (void)req.url; return 0; }
HttpServer createServer(const char *host, int32_t port) { (void)host; (void)port; return (HttpServer){0}; }
