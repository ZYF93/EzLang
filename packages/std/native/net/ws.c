// EzLang std/net/ws 原生封装层
#include <stdint.h>

typedef struct { int64_t handle; } WsConn;

WsConn *wsConnect(const char *url) { (void)url; return 0; }
