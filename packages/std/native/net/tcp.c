// EzLang std/net/tcp 原生封装层
#include <stdint.h>

typedef struct { int64_t handle; } TcpConn;
typedef struct { int64_t handle; } TcpListener;
typedef struct { int64_t handle; } UdpSocket;

TcpConn *tcpConnect(const char *host, int32_t port) { (void)host; (void)port; return 0; }
TcpListener *tcpListen(const char *host, int32_t port) { (void)host; (void)port; return 0; }
UdpSocket *udpBind(const char *host, int32_t port) { (void)host; (void)port; return 0; }
