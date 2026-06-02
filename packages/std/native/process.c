// EzLang std/process 原生封装层
// 只面向外部程序调用；不暴露线程、锁等语言级并发底层原语。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if defined(__APPLE__)
#include <TargetConditionals.h>
#endif

#if !defined(_WIN32) && !defined(__ANDROID__) && !(defined(__APPLE__) && TARGET_OS_IPHONE)
#define EZ_PROCESS_SUPPORTED 1
#else
#define EZ_PROCESS_SUPPORTED 0
#endif

#if EZ_PROCESS_SUPPORTED
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#if defined(__APPLE__)
#include <mach-o/dyld.h>
#endif
#include <signal.h>
#include <stdio.h>
#include <sys/select.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

typedef struct {
    char ***pages;
    int64_t length;
    int64_t capacity;
    int64_t page_count;
} StrList;

typedef struct {
    const char *program;
    StrList args;
    const char *cwd;
    StrList env;
    Blob stdin;
} Command;

typedef struct {
    int64_t handle;
    int64_t pid;
} Process;

typedef struct {
    int32_t exitCode;
    Blob stdout;
    Blob stderr;
    bool ok;
} ProcessResult;

typedef struct { bool ok; Process value; } OptProcess;
typedef struct { bool ok; ProcessResult value; } OptProcessResult;
typedef struct { bool ok; const char *value; } OptStr;

static Blob ez_empty_blob(void) {
    return (Blob){NULL, 0};
}

static ProcessResult ez_process_result_empty(int32_t exit_code, bool ok) {
    return (ProcessResult){exit_code, ez_empty_blob(), ez_empty_blob(), ok};
}

static const char *ez_list_get(const StrList *items, int64_t index) {
    if (!items || index < 0 || index >= items->length || !items->pages || items->page_count <= 0) return "";
    int64_t page = index / 8;
    int64_t offset = index % 8;
    if (page >= items->page_count || !items->pages[page]) return "";
    return items->pages[page][offset] ? items->pages[page][offset] : "";
}

#if EZ_PROCESS_SUPPORTED
typedef struct {
    uint8_t *data;
    size_t length;
    size_t capacity;
} EzBuffer;

static bool ez_buffer_append(EzBuffer *buffer, const uint8_t *data, size_t size) {
    if (!buffer || !data || size == 0) return true;
    if (buffer->length + size < buffer->length) return false;
    if (buffer->length + size > buffer->capacity) {
        size_t next = buffer->capacity ? buffer->capacity : 4096;
        while (next < buffer->length + size) {
            if (next > ((size_t)-1) / 2) return false;
            next *= 2;
        }
        uint8_t *data_next = (uint8_t *)realloc(buffer->data, next);
        if (!data_next) return false;
        buffer->data = data_next;
        buffer->capacity = next;
    }
    memcpy(buffer->data + buffer->length, data, size);
    buffer->length += size;
    return true;
}

static Blob ez_buffer_to_blob(EzBuffer *buffer) {
    if (!buffer || buffer->length == 0) {
        free(buffer ? buffer->data : NULL);
        return ez_empty_blob();
    }
    uint8_t *exact = (uint8_t *)realloc(buffer->data, buffer->length);
    if (exact) buffer->data = exact;
    Blob out = {buffer->data, (int64_t)buffer->length};
    buffer->data = NULL;
    buffer->length = 0;
    buffer->capacity = 0;
    return out;
}

static char **ez_build_argv(const Command *command) {
    if (!command || !command->program || !*command->program) return NULL;
    int64_t argc = command->args.length;
    if (argc < 0 || argc > 1024 * 1024) return NULL;
    char **argv = (char **)calloc((size_t)argc + 2, sizeof(char *));
    if (!argv) return NULL;
    argv[0] = (char *)command->program;
    for (int64_t i = 0; i < argc; ++i) argv[i + 1] = (char *)ez_list_get(&command->args, i);
    argv[argc + 1] = NULL;
    return argv;
}

static void ez_apply_env(const StrList *env) {
    if (!env) return;
    for (int64_t i = 0; i < env->length; ++i) {
        const char *entry = ez_list_get(env, i);
        const char *eq = entry ? strchr(entry, '=') : NULL;
        if (!entry || !eq || eq == entry) continue;
        size_t key_len = (size_t)(eq - entry);
        char *key = (char *)malloc(key_len + 1);
        if (!key) continue;
        memcpy(key, entry, key_len);
        key[key_len] = '\0';
        setenv(key, eq + 1, 1);
        free(key);
    }
}

static void ez_child_exec(const Command *command, char **argv) {
    if (command->cwd && *command->cwd && chdir(command->cwd) != 0) _exit(127);
    ez_apply_env(&command->env);
    execvp(command->program, argv);
    _exit(127);
}

static bool ez_set_nonblock(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags < 0) return false;
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK) == 0;
}

static void ez_close_fd(int *fd) {
    if (fd && *fd >= 0) {
        close(*fd);
        *fd = -1;
    }
}

static int32_t ez_exit_code_from_status(int status) {
    if (WIFEXITED(status)) return (int32_t)WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return (int32_t)(128 + WTERMSIG(status));
    return -1;
}

static bool ez_read_available(int fd, EzBuffer *buffer, bool *open_flag) {
    uint8_t chunk[4096];
    while (true) {
        ssize_t n = read(fd, chunk, sizeof(chunk));
        if (n > 0) {
            if (!ez_buffer_append(buffer, chunk, (size_t)n)) return false;
            continue;
        }
        if (n == 0) {
            *open_flag = false;
            return true;
        }
        if (errno == EINTR) continue;
        if (errno == EAGAIN || errno == EWOULDBLOCK) return true;
        *open_flag = false;
        return true;
    }
}

static bool ez_write_available(int fd, const Blob *input, size_t *offset, bool *open_flag) {
    const uint8_t *data = input && input->data ? input->data : NULL;
    size_t size = input && input->size > 0 ? (size_t)input->size : 0;
    while (*offset < size) {
        ssize_t n = write(fd, data + *offset, size - *offset);
        if (n > 0) {
            *offset += (size_t)n;
            continue;
        }
        if (n == 0) return true;
        if (errno == EINTR) continue;
        if (errno == EAGAIN || errno == EWOULDBLOCK) return true;
        *open_flag = false;
        return true;
    }
    *open_flag = false;
    return true;
}

static OptProcessResult ez_exec_posix(const Command *command) {
    char **argv = ez_build_argv(command);
    if (!argv) return (OptProcessResult){false, {0}};

    int in_pipe[2] = {-1, -1};
    int out_pipe[2] = {-1, -1};
    int err_pipe[2] = {-1, -1};
    if (pipe(in_pipe) != 0 || pipe(out_pipe) != 0 || pipe(err_pipe) != 0) {
        ez_close_fd(&in_pipe[0]); ez_close_fd(&in_pipe[1]);
        ez_close_fd(&out_pipe[0]); ez_close_fd(&out_pipe[1]);
        ez_close_fd(&err_pipe[0]); ez_close_fd(&err_pipe[1]);
        free(argv);
        return (OptProcessResult){false, {0}};
    }

    pid_t pid = fork();
    if (pid < 0) {
        ez_close_fd(&in_pipe[0]); ez_close_fd(&in_pipe[1]);
        ez_close_fd(&out_pipe[0]); ez_close_fd(&out_pipe[1]);
        ez_close_fd(&err_pipe[0]); ez_close_fd(&err_pipe[1]);
        free(argv);
        return (OptProcessResult){false, {0}};
    }

    if (pid == 0) {
        dup2(in_pipe[0], STDIN_FILENO);
        dup2(out_pipe[1], STDOUT_FILENO);
        dup2(err_pipe[1], STDERR_FILENO);
        ez_close_fd(&in_pipe[0]); ez_close_fd(&in_pipe[1]);
        ez_close_fd(&out_pipe[0]); ez_close_fd(&out_pipe[1]);
        ez_close_fd(&err_pipe[0]); ez_close_fd(&err_pipe[1]);
        ez_child_exec(command, argv);
    }

    free(argv);
    ez_close_fd(&in_pipe[0]);
    ez_close_fd(&out_pipe[1]);
    ez_close_fd(&err_pipe[1]);
    ez_set_nonblock(in_pipe[1]);
    ez_set_nonblock(out_pipe[0]);
    ez_set_nonblock(err_pipe[0]);

    bool stdin_open = in_pipe[1] >= 0;
    bool stdout_open = out_pipe[0] >= 0;
    bool stderr_open = err_pipe[0] >= 0;
    size_t stdin_offset = 0;
    EzBuffer stdout_buf = {0};
    EzBuffer stderr_buf = {0};
    int status = 0;
    bool waited = false;
    bool failed = false;

    if (!command->stdin.data || command->stdin.size <= 0) {
        stdin_open = false;
        ez_close_fd(&in_pipe[1]);
    }

    while (stdout_open || stderr_open || stdin_open || !waited) {
        if (!waited) {
            pid_t w = waitpid(pid, &status, stdout_open || stderr_open || stdin_open ? WNOHANG : 0);
            if (w == pid) waited = true;
            else if (w < 0 && errno != EINTR) {
                failed = true;
                waited = true;
            }
        }

        fd_set readfds;
        fd_set writefds;
        FD_ZERO(&readfds);
        FD_ZERO(&writefds);
        int maxfd = -1;
        if (stdout_open) { FD_SET(out_pipe[0], &readfds); if (out_pipe[0] > maxfd) maxfd = out_pipe[0]; }
        if (stderr_open) { FD_SET(err_pipe[0], &readfds); if (err_pipe[0] > maxfd) maxfd = err_pipe[0]; }
        if (stdin_open) { FD_SET(in_pipe[1], &writefds); if (in_pipe[1] > maxfd) maxfd = in_pipe[1]; }

        if (maxfd < 0) continue;
        int ready = select(maxfd + 1, &readfds, &writefds, NULL, NULL);
        if (ready < 0) {
            if (errno == EINTR) continue;
            failed = true;
            break;
        }

        if (stdout_open && FD_ISSET(out_pipe[0], &readfds)) {
            if (!ez_read_available(out_pipe[0], &stdout_buf, &stdout_open)) { failed = true; stdout_open = false; }
            if (!stdout_open) ez_close_fd(&out_pipe[0]);
        }
        if (stderr_open && FD_ISSET(err_pipe[0], &readfds)) {
            if (!ez_read_available(err_pipe[0], &stderr_buf, &stderr_open)) { failed = true; stderr_open = false; }
            if (!stderr_open) ez_close_fd(&err_pipe[0]);
        }
        if (stdin_open && FD_ISSET(in_pipe[1], &writefds)) {
            if (!ez_write_available(in_pipe[1], &command->stdin, &stdin_offset, &stdin_open)) { failed = true; stdin_open = false; }
            if (!stdin_open) ez_close_fd(&in_pipe[1]);
        }
    }

    ez_close_fd(&in_pipe[1]);
    ez_close_fd(&out_pipe[0]);
    ez_close_fd(&err_pipe[0]);
    if (!waited) {
        while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
    }
    if (failed) {
        free(stdout_buf.data);
        free(stderr_buf.data);
        return (OptProcessResult){false, {0}};
    }

    int32_t exit_code = ez_exit_code_from_status(status);
    ProcessResult result = {exit_code, ez_buffer_to_blob(&stdout_buf), ez_buffer_to_blob(&stderr_buf), exit_code == 0};
    return (OptProcessResult){true, result};
}

static char *ez_strdup_safe(const char *src) {
    if (!src) src = "";
    size_t len = strlen(src);
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    memcpy(out, src, len + 1);
    return out;
}
#endif

OptProcessResult processExec(const Command *command) {
#if EZ_PROCESS_SUPPORTED
    return ez_exec_posix(command);
#else
    (void)command;
    return (OptProcessResult){false, {0}};
#endif
}

OptProcess processSpawn(const Command *command) {
#if EZ_PROCESS_SUPPORTED
    char **argv = ez_build_argv(command);
    if (!argv) return (OptProcess){false, {0}};
    pid_t pid = fork();
    if (pid < 0) {
        free(argv);
        return (OptProcess){false, {0}};
    }
    if (pid == 0) ez_child_exec(command, argv);
    free(argv);
    Process proc = {(int64_t)pid, (int64_t)pid};
    return (OptProcess){true, proc};
#else
    (void)command;
    return (OptProcess){false, {0}};
#endif
}

OptProcessResult processWait(const Process *process) {
#if EZ_PROCESS_SUPPORTED
    if (!process || process->pid <= 0) return (OptProcessResult){false, {0}};
    int status = 0;
    pid_t pid = (pid_t)process->pid;
    while (waitpid(pid, &status, 0) < 0) {
        if (errno == EINTR) continue;
        return (OptProcessResult){false, {0}};
    }
    int32_t exit_code = ez_exit_code_from_status(status);
    return (OptProcessResult){true, ez_process_result_empty(exit_code, exit_code == 0)};
#else
    (void)process;
    return (OptProcessResult){false, {0}};
#endif
}

bool processTerminate(const Process *process) {
#if EZ_PROCESS_SUPPORTED
    if (!process || process->pid <= 0) return false;
    return kill((pid_t)process->pid, SIGTERM) == 0;
#else
    (void)process;
    return false;
#endif
}

OptStr processCurrentPath(void) {
#if EZ_PROCESS_SUPPORTED && defined(__linux__)
    size_t cap = 4096;
    while (cap <= 1024 * 1024) {
        char *buf = (char *)malloc(cap + 1);
        if (!buf) return (OptStr){false, NULL};
        ssize_t n = readlink("/proc/self/exe", buf, cap);
        if (n < 0) {
            free(buf);
            return (OptStr){false, NULL};
        }
        if ((size_t)n < cap) {
            buf[n] = '\0';
            return (OptStr){true, buf};
        }
        free(buf);
        cap *= 2;
    }
    return (OptStr){false, NULL};
#elif EZ_PROCESS_SUPPORTED && defined(__APPLE__)
    uint32_t size = 0;
    _NSGetExecutablePath(NULL, &size);
    if (size == 0) size = 4096;
    char *buf = (char *)malloc((size_t)size + 1);
    if (!buf) return (OptStr){false, NULL};
    if (_NSGetExecutablePath(buf, &size) != 0) {
        char *next = (char *)realloc(buf, (size_t)size + 1);
        if (!next) {
            free(buf);
            return (OptStr){false, NULL};
        }
        buf = next;
        if (_NSGetExecutablePath(buf, &size) != 0) {
            free(buf);
            return (OptStr){false, NULL};
        }
    }
    buf[size] = '\0';
    char *resolved = realpath(buf, NULL);
    if (resolved) {
        free(buf);
        return (OptStr){true, resolved};
    }
    return (OptStr){true, buf};
#else
    return (OptStr){false, NULL};
#endif
}
