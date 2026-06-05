// EzLang std/process 原生封装层
// 只面向外部程序调用；不暴露线程、锁等语言级并发底层原语。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if defined(__APPLE__)
#include <TargetConditionals.h>
#endif

#if defined(_WIN32)
#include <windows.h>
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

#if defined(_WIN32)
typedef struct {
    uint8_t *data;
    size_t length;
    size_t capacity;
} EzWinBuffer;

typedef struct {
    char *data;
    size_t length;
    size_t capacity;
} EzWinText;

typedef struct {
    wchar_t *key;
    wchar_t *old_value;
    bool had_value;
} EzWinEnvBackup;

static bool ez_win_buffer_append(EzWinBuffer *buffer, const uint8_t *data, size_t size) {
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

static Blob ez_win_buffer_to_blob(EzWinBuffer *buffer) {
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

static bool ez_win_text_append(EzWinText *text, const char *data, size_t size) {
    if (!text || !data) return false;
    if (text->length + size + 1 < text->length) return false;
    if (text->length + size + 1 > text->capacity) {
        size_t next = text->capacity ? text->capacity : 64;
        while (next < text->length + size + 1) {
            if (next > ((size_t)-1) / 2) return false;
            next *= 2;
        }
        char *data_next = (char *)realloc(text->data, next);
        if (!data_next) return false;
        text->data = data_next;
        text->capacity = next;
    }
    memcpy(text->data + text->length, data, size);
    text->length += size;
    text->data[text->length] = '\0';
    return true;
}

static bool ez_win_text_append_char(EzWinText *text, char ch) {
    return ez_win_text_append(text, &ch, 1);
}

static bool ez_win_text_append_quoted(EzWinText *text, const char *arg) {
    if (!arg) arg = "";
    bool needs_quote = *arg == '\0';
    for (const char *p = arg; *p; ++p) {
        if (*p == ' ' || *p == '\t' || *p == '"') {
            needs_quote = true;
            break;
        }
    }
    if (!needs_quote) return ez_win_text_append(text, arg, strlen(arg));
    if (!ez_win_text_append_char(text, '"')) return false;
    size_t slash_count = 0;
    for (const char *p = arg; *p; ++p) {
        if (*p == '\\') {
            slash_count++;
            continue;
        }
        if (*p == '"') {
            for (size_t i = 0; i < slash_count * 2 + 1; ++i) {
                if (!ez_win_text_append_char(text, '\\')) return false;
            }
            slash_count = 0;
            if (!ez_win_text_append_char(text, '"')) return false;
            continue;
        }
        for (size_t i = 0; i < slash_count; ++i) {
            if (!ez_win_text_append_char(text, '\\')) return false;
        }
        slash_count = 0;
        if (!ez_win_text_append_char(text, *p)) return false;
    }
    for (size_t i = 0; i < slash_count * 2; ++i) {
        if (!ez_win_text_append_char(text, '\\')) return false;
    }
    return ez_win_text_append_char(text, '"');
}

static wchar_t *ez_win_utf8_to_wide(const char *value) {
    if (!value) value = "";
    int needed = MultiByteToWideChar(CP_UTF8, 0, value, -1, NULL, 0);
    if (needed <= 0) return NULL;
    wchar_t *out = (wchar_t *)malloc((size_t)needed * sizeof(wchar_t));
    if (!out) return NULL;
    if (MultiByteToWideChar(CP_UTF8, 0, value, -1, out, needed) <= 0) {
        free(out);
        return NULL;
    }
    return out;
}

static char *ez_win_wide_to_utf8(const wchar_t *value) {
    if (!value) value = L"";
    int needed = WideCharToMultiByte(CP_UTF8, 0, value, -1, NULL, 0, NULL, NULL);
    if (needed <= 0) return NULL;
    char *out = (char *)malloc((size_t)needed);
    if (!out) return NULL;
    if (WideCharToMultiByte(CP_UTF8, 0, value, -1, out, needed, NULL, NULL) <= 0) {
        free(out);
        return NULL;
    }
    return out;
}

static wchar_t *ez_win_command_line(const Command *command) {
    if (!command || !command->program || !*command->program) return NULL;
    EzWinText text = {0};
    if (!ez_win_text_append_quoted(&text, command->program)) {
        free(text.data);
        return NULL;
    }
    for (int64_t i = 0; i < command->args.length; ++i) {
        if (!ez_win_text_append_char(&text, ' ') || !ez_win_text_append_quoted(&text, ez_list_get(&command->args, i))) {
            free(text.data);
            return NULL;
        }
    }
    wchar_t *wide = ez_win_utf8_to_wide(text.data ? text.data : "");
    free(text.data);
    return wide;
}

static EzWinEnvBackup *ez_win_apply_env(const StrList *env, size_t *count_out) {
    if (count_out) *count_out = 0;
    if (!env || env->length <= 0) return NULL;
    EzWinEnvBackup *backups = (EzWinEnvBackup *)calloc((size_t)env->length, sizeof(EzWinEnvBackup));
    if (!backups) return NULL;
    size_t count = 0;
    for (int64_t i = 0; i < env->length; ++i) {
        const char *entry = ez_list_get(env, i);
        const char *eq = entry ? strchr(entry, '=') : NULL;
        if (!entry || !eq || eq == entry) continue;
        size_t key_len = (size_t)(eq - entry);
        char *key_utf8 = (char *)malloc(key_len + 1);
        if (!key_utf8) continue;
        memcpy(key_utf8, entry, key_len);
        key_utf8[key_len] = '\0';
        wchar_t *key = ez_win_utf8_to_wide(key_utf8);
        wchar_t *value = ez_win_utf8_to_wide(eq + 1);
        free(key_utf8);
        if (!key || !value) {
            free(key);
            free(value);
            continue;
        }
        DWORD old_size = GetEnvironmentVariableW(key, NULL, 0);
        wchar_t *old_value = NULL;
        bool had_value = old_size > 0;
        if (had_value) {
            old_value = (wchar_t *)malloc((size_t)old_size * sizeof(wchar_t));
            if (old_value) GetEnvironmentVariableW(key, old_value, old_size);
        }
        SetEnvironmentVariableW(key, value);
        free(value);
        backups[count++] = (EzWinEnvBackup){key, old_value, had_value};
    }
    if (count_out) *count_out = count;
    return backups;
}

static void ez_win_restore_env(EzWinEnvBackup *backups, size_t count) {
    if (!backups) return;
    for (size_t i = count; i > 0; --i) {
        EzWinEnvBackup *backup = &backups[i - 1];
        if (backup->key) SetEnvironmentVariableW(backup->key, backup->had_value ? backup->old_value : NULL);
        free(backup->key);
        free(backup->old_value);
    }
    free(backups);
}

static void ez_win_close_handle(HANDLE *handle) {
    if (handle && *handle && *handle != INVALID_HANDLE_VALUE) {
        CloseHandle(*handle);
        *handle = NULL;
    }
}

static bool ez_win_read_available(HANDLE handle, EzWinBuffer *buffer, bool *open_flag) {
    DWORD available = 0;
    if (!PeekNamedPipe(handle, NULL, 0, NULL, &available, NULL)) {
        *open_flag = false;
        return true;
    }
    while (available > 0) {
        uint8_t chunk[4096];
        DWORD to_read = available < sizeof(chunk) ? available : (DWORD)sizeof(chunk);
        DWORD read_size = 0;
        if (!ReadFile(handle, chunk, to_read, &read_size, NULL)) {
            *open_flag = false;
            return true;
        }
        if (read_size == 0) break;
        if (!ez_win_buffer_append(buffer, chunk, read_size)) return false;
        available -= read_size;
    }
    return true;
}

static bool ez_win_write_blob(HANDLE handle, const Blob *input) {
    const uint8_t *data = input && input->data ? input->data : NULL;
    size_t size = input && input->size > 0 ? (size_t)input->size : 0;
    size_t offset = 0;
    while (offset < size) {
        DWORD chunk = (DWORD)((size - offset) > 65536 ? 65536 : (size - offset));
        DWORD written = 0;
        if (!WriteFile(handle, data + offset, chunk, &written, NULL)) return false;
        if (written == 0) return false;
        offset += written;
    }
    return true;
}

static bool ez_win_create_process(const Command *command, STARTUPINFOW *startup, PROCESS_INFORMATION *info) {
    wchar_t *cmd = ez_win_command_line(command);
    wchar_t *cwd = command && command->cwd && *command->cwd ? ez_win_utf8_to_wide(command->cwd) : NULL;
    if (!cmd) {
        free(cwd);
        return false;
    }
    size_t env_count = 0;
    EzWinEnvBackup *env_backup = ez_win_apply_env(command ? &command->env : NULL, &env_count);
    BOOL ok = CreateProcessW(NULL, cmd, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, cwd, startup, info);
    ez_win_restore_env(env_backup, env_count);
    free(cmd);
    free(cwd);
    return ok != 0;
}

static OptProcessResult ez_exec_windows(const Command *command) {
    SECURITY_ATTRIBUTES attrs = {sizeof(SECURITY_ATTRIBUTES), NULL, TRUE};
    HANDLE stdin_read = NULL, stdin_write = NULL;
    HANDLE stdout_read = NULL, stdout_write = NULL;
    HANDLE stderr_read = NULL, stderr_write = NULL;
    if (!CreatePipe(&stdin_read, &stdin_write, &attrs, 0) ||
        !CreatePipe(&stdout_read, &stdout_write, &attrs, 0) ||
        !CreatePipe(&stderr_read, &stderr_write, &attrs, 0)) {
        ez_win_close_handle(&stdin_read); ez_win_close_handle(&stdin_write);
        ez_win_close_handle(&stdout_read); ez_win_close_handle(&stdout_write);
        ez_win_close_handle(&stderr_read); ez_win_close_handle(&stderr_write);
        return (OptProcessResult){false, {0}};
    }
    SetHandleInformation(stdin_write, HANDLE_FLAG_INHERIT, 0);
    SetHandleInformation(stdout_read, HANDLE_FLAG_INHERIT, 0);
    SetHandleInformation(stderr_read, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOW startup;
    PROCESS_INFORMATION info;
    memset(&startup, 0, sizeof(startup));
    memset(&info, 0, sizeof(info));
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = stdin_read;
    startup.hStdOutput = stdout_write;
    startup.hStdError = stderr_write;
    if (!ez_win_create_process(command, &startup, &info)) {
        ez_win_close_handle(&stdin_read); ez_win_close_handle(&stdin_write);
        ez_win_close_handle(&stdout_read); ez_win_close_handle(&stdout_write);
        ez_win_close_handle(&stderr_read); ez_win_close_handle(&stderr_write);
        return (OptProcessResult){false, {0}};
    }
    ez_win_close_handle(&stdin_read);
    ez_win_close_handle(&stdout_write);
    ez_win_close_handle(&stderr_write);
    ez_win_write_blob(stdin_write, command ? &command->stdin : NULL);
    ez_win_close_handle(&stdin_write);

    EzWinBuffer out = {0};
    EzWinBuffer err = {0};
    bool stdout_open = true;
    bool stderr_open = true;
    bool failed = false;
    while (stdout_open || stderr_open) {
        if (stdout_open && !ez_win_read_available(stdout_read, &out, &stdout_open)) failed = true;
        if (stderr_open && !ez_win_read_available(stderr_read, &err, &stderr_open)) failed = true;
        DWORD wait = WaitForSingleObject(info.hProcess, 10);
        if (wait == WAIT_OBJECT_0) {
            if (stdout_open) ez_win_read_available(stdout_read, &out, &stdout_open);
            if (stderr_open) ez_win_read_available(stderr_read, &err, &stderr_open);
            break;
        }
        if (wait == WAIT_FAILED) {
            failed = true;
            break;
        }
    }
    DWORD code = 1;
    GetExitCodeProcess(info.hProcess, &code);
    ez_win_close_handle(&stdout_read);
    ez_win_close_handle(&stderr_read);
    ez_win_close_handle(&info.hThread);
    ez_win_close_handle(&info.hProcess);
    if (failed) {
        free(out.data);
        free(err.data);
        return (OptProcessResult){false, {0}};
    }
    ProcessResult result = {(int32_t)code, ez_win_buffer_to_blob(&out), ez_win_buffer_to_blob(&err), code == 0};
    return (OptProcessResult){true, result};
}

static OptProcess ez_spawn_windows(const Command *command) {
    STARTUPINFOW startup;
    PROCESS_INFORMATION info;
    memset(&startup, 0, sizeof(startup));
    memset(&info, 0, sizeof(info));
    startup.cb = sizeof(startup);
    if (!ez_win_create_process(command, &startup, &info)) return (OptProcess){false, {0}};
    ez_win_close_handle(&info.hThread);
    Process proc = {(int64_t)(intptr_t)info.hProcess, (int64_t)info.dwProcessId};
    return (OptProcess){true, proc};
}
#endif

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
#if defined(_WIN32)
    return ez_exec_windows(command);
#elif EZ_PROCESS_SUPPORTED
    return ez_exec_posix(command);
#else
    (void)command;
    return (OptProcessResult){false, {0}};
#endif
}

OptProcess processSpawn(const Command *command) {
#if defined(_WIN32)
    return ez_spawn_windows(command);
#elif EZ_PROCESS_SUPPORTED
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
#if defined(_WIN32)
    if (!process || process->handle == 0) return (OptProcessResult){false, {0}};
    HANDLE handle = (HANDLE)(intptr_t)process->handle;
    DWORD wait = WaitForSingleObject(handle, INFINITE);
    if (wait != WAIT_OBJECT_0) return (OptProcessResult){false, {0}};
    DWORD code = 1;
    if (!GetExitCodeProcess(handle, &code)) return (OptProcessResult){false, {0}};
    CloseHandle(handle);
    return (OptProcessResult){true, ez_process_result_empty((int32_t)code, code == 0)};
#elif EZ_PROCESS_SUPPORTED
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
#if defined(_WIN32)
    if (!process || process->handle == 0) return false;
    HANDLE handle = (HANDLE)(intptr_t)process->handle;
    bool ok = TerminateProcess(handle, 1) != 0;
    CloseHandle(handle);
    return ok;
#elif EZ_PROCESS_SUPPORTED
    if (!process || process->pid <= 0) return false;
    return kill((pid_t)process->pid, SIGTERM) == 0;
#else
    (void)process;
    return false;
#endif
}

OptStr processCurrentPath(void) {
#if defined(_WIN32)
    DWORD cap = 260;
    while (cap <= 1024 * 1024) {
        wchar_t *buf = (wchar_t *)malloc((size_t)cap * sizeof(wchar_t));
        if (!buf) return (OptStr){false, NULL};
        DWORD n = GetModuleFileNameW(NULL, buf, cap);
        if (n == 0) {
            free(buf);
            return (OptStr){false, NULL};
        }
        if (n < cap - 1) {
            char *utf8 = ez_win_wide_to_utf8(buf);
            free(buf);
            return utf8 ? (OptStr){true, utf8} : (OptStr){false, NULL};
        }
        free(buf);
        cap *= 2;
    }
    return (OptStr){false, NULL};
#elif EZ_PROCESS_SUPPORTED && defined(__linux__)
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
