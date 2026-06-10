// EzLang 语言级最小运行时：flow sleep 与 race(pl) 原生调度。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#endif

typedef int32_t (*EzRaceI32Branch)(void);

typedef struct EzRuntimeLock {
    char *name;
    int32_t policy;
#if defined(_WIN32)
    CRITICAL_SECTION mutex;
    CONDITION_VARIABLE cond;
#else
    pthread_mutex_t mutex;
    pthread_cond_t cond;
#endif
    int32_t active_readers;
    bool writer_active;
    int32_t waiting_readers;
    int32_t waiting_writers;
    uint64_t next_ticket;
    uint64_t serving_ticket;
    int64_t earliest_writer_ns;
    struct EzRuntimeLock *next;
} EzRuntimeLock;

enum {
    EZ_LOCK_ORDERED = 0,
    EZ_LOCK_READ_PREFERRED = 1,
    EZ_LOCK_WRITE_PREFERRED = 2,
};

static const int64_t EZ_LOCK_WRITER_STARVE_NS = 1000000;

static EzRuntimeLock *ez_lock_table = NULL;

#if defined(_WIN32)
static SRWLOCK ez_lock_table_guard = SRWLOCK_INIT;

static char *ezrt_strdup(const char *s) {
    if (!s) s = "";
    size_t len = strlen(s) + 1;
    char *copy = (char *)malloc(len);
    if (copy) memcpy(copy, s, len);
    return copy;
}

static int64_t ezrt_now_ns(void) {
    return (int64_t)GetTickCount64() * 1000000;
}

static void ezrt_lock_init(EzRuntimeLock *lock) {
    InitializeCriticalSection(&lock->mutex);
    InitializeConditionVariable(&lock->cond);
}

static void ezrt_lock_mutex_lock(EzRuntimeLock *lock) { EnterCriticalSection(&lock->mutex); }
static void ezrt_lock_mutex_unlock(EzRuntimeLock *lock) { LeaveCriticalSection(&lock->mutex); }
static void ezrt_lock_wait(EzRuntimeLock *lock) { SleepConditionVariableCS(&lock->cond, &lock->mutex, INFINITE); }
static void ezrt_lock_wait_short(EzRuntimeLock *lock) { SleepConditionVariableCS(&lock->cond, &lock->mutex, 1); }
static void ezrt_lock_broadcast(EzRuntimeLock *lock) { WakeAllConditionVariable(&lock->cond); }

static EzRuntimeLock *ezrt_lock_lookup(const char *name, int32_t policy, bool create) {
    if (!name) name = "";
    AcquireSRWLockExclusive(&ez_lock_table_guard);
    EzRuntimeLock *cur = ez_lock_table;
    while (cur) {
        if (strcmp(cur->name, name) == 0) {
            if (policy != 0) {
                ezrt_lock_mutex_lock(cur);
                cur->policy = policy;
                ezrt_lock_broadcast(cur);
                ezrt_lock_mutex_unlock(cur);
            }
            ReleaseSRWLockExclusive(&ez_lock_table_guard);
            return cur;
        }
        cur = cur->next;
    }
    if (!create) {
        ReleaseSRWLockExclusive(&ez_lock_table_guard);
        return NULL;
    }
    EzRuntimeLock *lock = (EzRuntimeLock *)calloc(1, sizeof(EzRuntimeLock));
    if (!lock) {
        ReleaseSRWLockExclusive(&ez_lock_table_guard);
        return NULL;
    }
    lock->name = ezrt_strdup(name);
    lock->policy = policy;
    ezrt_lock_init(lock);
    lock->next = ez_lock_table;
    ez_lock_table = lock;
    ReleaseSRWLockExclusive(&ez_lock_table_guard);
    return lock;
}

#else
static pthread_mutex_t ez_lock_table_guard = PTHREAD_MUTEX_INITIALIZER;

static char *ezrt_strdup(const char *s) {
    if (!s) s = "";
    size_t len = strlen(s) + 1;
    char *copy = (char *)malloc(len);
    if (copy) memcpy(copy, s, len);
    return copy;
}

static int64_t ezrt_now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000000000 + ts.tv_nsec;
}

static void ezrt_lock_init(EzRuntimeLock *lock) {
    pthread_mutex_init(&lock->mutex, NULL);
    pthread_cond_init(&lock->cond, NULL);
}

static void ezrt_lock_mutex_lock(EzRuntimeLock *lock) { pthread_mutex_lock(&lock->mutex); }
static void ezrt_lock_mutex_unlock(EzRuntimeLock *lock) { pthread_mutex_unlock(&lock->mutex); }
static void ezrt_lock_wait(EzRuntimeLock *lock) { pthread_cond_wait(&lock->cond, &lock->mutex); }

static void ezrt_lock_wait_short(EzRuntimeLock *lock) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    ts.tv_nsec += 1000000;
    if (ts.tv_nsec >= 1000000000) {
        ts.tv_sec += 1;
        ts.tv_nsec -= 1000000000;
    }
    pthread_cond_timedwait(&lock->cond, &lock->mutex, &ts);
}

static void ezrt_lock_broadcast(EzRuntimeLock *lock) { pthread_cond_broadcast(&lock->cond); }

static EzRuntimeLock *ezrt_lock_lookup(const char *name, int32_t policy, bool create) {
    if (!name) name = "";
    pthread_mutex_lock(&ez_lock_table_guard);
    EzRuntimeLock *cur = ez_lock_table;
    while (cur) {
        if (strcmp(cur->name, name) == 0) {
            if (policy != 0) {
                ezrt_lock_mutex_lock(cur);
                cur->policy = policy;
                ezrt_lock_broadcast(cur);
                ezrt_lock_mutex_unlock(cur);
            }
            pthread_mutex_unlock(&ez_lock_table_guard);
            return cur;
        }
        cur = cur->next;
    }
    if (!create) {
        pthread_mutex_unlock(&ez_lock_table_guard);
        return NULL;
    }
    EzRuntimeLock *lock = (EzRuntimeLock *)calloc(1, sizeof(EzRuntimeLock));
    if (!lock) {
        pthread_mutex_unlock(&ez_lock_table_guard);
        return NULL;
    }
    lock->name = ezrt_strdup(name);
    lock->policy = policy;
    ezrt_lock_init(lock);
    lock->next = ez_lock_table;
    ez_lock_table = lock;
    pthread_mutex_unlock(&ez_lock_table_guard);
    return lock;
}

#endif

void __ezrt_lock_register(const char *name, int32_t policy) {
    (void)ezrt_lock_lookup(name, policy, true);
}

static bool ezrt_has_starved_writer(EzRuntimeLock *lock) {
    return lock->waiting_writers > 0 && lock->earliest_writer_ns > 0 &&
        ezrt_now_ns() - lock->earliest_writer_ns >= EZ_LOCK_WRITER_STARVE_NS;
}

static bool ezrt_can_read(EzRuntimeLock *lock, uint64_t ticket) {
    if (lock->writer_active) return false;
    if (lock->policy == EZ_LOCK_ORDERED) return ticket == lock->serving_ticket;
    if (lock->policy == EZ_LOCK_WRITE_PREFERRED) return lock->waiting_writers == 0;
    return !ezrt_has_starved_writer(lock);
}

static bool ezrt_can_write(EzRuntimeLock *lock, uint64_t ticket, int64_t requested_ns) {
    if (lock->writer_active || lock->active_readers > 0) return false;
    if (lock->policy == EZ_LOCK_ORDERED) return ticket == lock->serving_ticket;
    if (lock->policy == EZ_LOCK_WRITE_PREFERRED) return true;
    return lock->waiting_readers == 0 || ezrt_now_ns() - requested_ns >= EZ_LOCK_WRITER_STARVE_NS;
}

void __ezrt_lock_read_acquire(const char *name) {
    EzRuntimeLock *lock = ezrt_lock_lookup(name, 0, true);
    if (!lock) return;
    ezrt_lock_mutex_lock(lock);
    uint64_t ticket = 0;
    if (lock->policy == EZ_LOCK_ORDERED) ticket = lock->next_ticket++;
    lock->waiting_readers += 1;
    while (!ezrt_can_read(lock, ticket)) ezrt_lock_wait(lock);
    lock->waiting_readers -= 1;
    lock->active_readers += 1;
    if (lock->policy == EZ_LOCK_ORDERED) {
        lock->serving_ticket += 1;
        ezrt_lock_broadcast(lock);
    }
    ezrt_lock_mutex_unlock(lock);
}

void __ezrt_lock_read_release(const char *name) {
    EzRuntimeLock *lock = ezrt_lock_lookup(name, 0, false);
    if (!lock) return;
    ezrt_lock_mutex_lock(lock);
    if (lock->active_readers > 0) lock->active_readers -= 1;
    ezrt_lock_broadcast(lock);
    ezrt_lock_mutex_unlock(lock);
}

void __ezrt_lock_write_acquire(const char *name) {
    EzRuntimeLock *lock = ezrt_lock_lookup(name, 0, true);
    if (!lock) return;
    ezrt_lock_mutex_lock(lock);
    uint64_t ticket = 0;
    if (lock->policy == EZ_LOCK_ORDERED) ticket = lock->next_ticket++;
    int64_t requested_ns = ezrt_now_ns();
    lock->waiting_writers += 1;
    if (lock->earliest_writer_ns == 0 || requested_ns < lock->earliest_writer_ns) {
        lock->earliest_writer_ns = requested_ns;
    }
    while (!ezrt_can_write(lock, ticket, requested_ns)) {
        if (lock->policy == EZ_LOCK_READ_PREFERRED) ezrt_lock_wait_short(lock);
        else ezrt_lock_wait(lock);
    }
    lock->waiting_writers -= 1;
    if (lock->waiting_writers == 0) lock->earliest_writer_ns = 0;
    else if (lock->earliest_writer_ns == requested_ns) lock->earliest_writer_ns = ezrt_now_ns();
    lock->writer_active = true;
    if (lock->policy == EZ_LOCK_ORDERED) {
        lock->serving_ticket += 1;
        ezrt_lock_broadcast(lock);
    }
    ezrt_lock_mutex_unlock(lock);
}

void __ezrt_lock_write_release(const char *name) {
    EzRuntimeLock *lock = ezrt_lock_lookup(name, 0, false);
    if (!lock) return;
    ezrt_lock_mutex_lock(lock);
    lock->writer_active = false;
    ezrt_lock_broadcast(lock);
    ezrt_lock_mutex_unlock(lock);
}

typedef struct EzRaceI32Task {
    EzRaceI32Branch branch;
    struct EzRaceI32State *state;
    int32_t result;
    bool done;
    bool started;
#if defined(_WIN32)
    HANDLE thread;
#else
    pthread_t thread;
#endif
} EzRaceI32Task;

typedef struct EzRaceI32State {
#if defined(_WIN32)
    CRITICAL_SECTION mutex;
#else
    pthread_mutex_t mutex;
#endif
} EzRaceI32State;

typedef struct EzTaskI32 {
    EzRaceI32Branch branch;
    int32_t result;
#if defined(_WIN32)
    HANDLE thread;
#else
    pthread_t thread;
#endif
} EzTaskI32;

static void ez_race_i32_state_init(EzRaceI32State *state) {
#if defined(_WIN32)
    InitializeCriticalSection(&state->mutex);
#else
    pthread_mutex_init(&state->mutex, NULL);
#endif
}

static void ez_race_i32_state_destroy(EzRaceI32State *state) {
#if defined(_WIN32)
    DeleteCriticalSection(&state->mutex);
#else
    pthread_mutex_destroy(&state->mutex);
#endif
}

static void ez_race_i32_state_lock(EzRaceI32State *state) {
#if defined(_WIN32)
    EnterCriticalSection(&state->mutex);
#else
    pthread_mutex_lock(&state->mutex);
#endif
}

static void ez_race_i32_state_unlock(EzRaceI32State *state) {
#if defined(_WIN32)
    LeaveCriticalSection(&state->mutex);
#else
    pthread_mutex_unlock(&state->mutex);
#endif
}

static void ez_race_i32_task_finish(EzRaceI32Task *task, int32_t result) {
    ez_race_i32_state_lock(task->state);
    task->result = result;
    task->done = true;
    ez_race_i32_state_unlock(task->state);
}

static bool ez_race_i32_task_done(EzRaceI32Task *task) {
    bool done;
    ez_race_i32_state_lock(task->state);
    done = task->done;
    ez_race_i32_state_unlock(task->state);
    return done;
}

static int32_t ez_race_i32_task_result(EzRaceI32Task *task) {
    int32_t result;
    ez_race_i32_state_lock(task->state);
    result = task->result;
    ez_race_i32_state_unlock(task->state);
    return result;
}

#if defined(_WIN32)
static DWORD WINAPI ez_race_i32_worker(LPVOID data) {
    EzRaceI32Task *task = (EzRaceI32Task *)data;
    int32_t result = task->branch ? task->branch() : 0;
    ez_race_i32_task_finish(task, result);
    return 0;
}

static DWORD WINAPI ez_task_i32_worker(LPVOID data) {
    EzTaskI32 *task = (EzTaskI32 *)data;
    task->result = task->branch ? task->branch() : 0;
    return 0;
}

#else
static void *ez_race_i32_worker(void *data) {
    EzRaceI32Task *task = (EzRaceI32Task *)data;
    int32_t result = task->branch ? task->branch() : 0;
    ez_race_i32_task_finish(task, result);
    return NULL;
}

static void *ez_task_i32_worker(void *data) {
    EzTaskI32 *task = (EzTaskI32 *)data;
    task->result = task->branch ? task->branch() : 0;
    return NULL;
}

#endif

void *__ezrt_task_start_i32(EzRaceI32Branch branch) {
    EzTaskI32 *task = (EzTaskI32 *)calloc(1, sizeof(EzTaskI32));
    if (!task) return NULL;
    task->branch = branch;
#if defined(_WIN32)
    task->thread = CreateThread(NULL, 0, ez_task_i32_worker, task, 0, NULL);
    if (!task->thread) task->result = branch ? branch() : 0;
#else
    if (pthread_create(&task->thread, NULL, ez_task_i32_worker, task) != 0) {
        task->result = branch ? branch() : 0;
        task->thread = 0;
    }
#endif
    return task;
}

int32_t __ezrt_task_join_i32(void *handle) {
    EzTaskI32 *task = (EzTaskI32 *)handle;
    if (!task) return 0;
#if defined(_WIN32)
    if (task->thread) {
        WaitForSingleObject(task->thread, INFINITE);
        CloseHandle(task->thread);
    }
#else
    if (task->thread) pthread_join(task->thread, NULL);
#endif
    int32_t result = task->result;
    free(task);
    return result;
}

int32_t __ezrt_race_i32(EzRaceI32Branch *branches, int32_t count, int32_t timeout_ms, int32_t *timed_out) {
    if (timed_out) *timed_out = 0;
    if (!branches || count <= 0) return 0;

    EzRaceI32Task *tasks = (EzRaceI32Task *)calloc((size_t)count, sizeof(EzRaceI32Task));
    if (!tasks) return 0;
    EzRaceI32State state;
    ez_race_i32_state_init(&state);
    int32_t result = 0;

#if defined(_WIN32)
    for (int32_t i = 0; i < count; ++i) {
        tasks[i].branch = branches[i];
        tasks[i].state = &state;
        tasks[i].thread = CreateThread(NULL, 0, ez_race_i32_worker, &tasks[i], 0, NULL);
        tasks[i].started = tasks[i].thread != NULL;
        if (!tasks[i].thread) {
            ez_race_i32_task_finish(&tasks[i], branches[i] ? branches[i]() : 0);
        }
    }
    DWORD start = GetTickCount();
    int32_t winner = -1;
    while (winner < 0) {
        for (int32_t i = 0; i < count; ++i) {
            if (ez_race_i32_task_done(&tasks[i])) { winner = i; break; }
        }
        if (winner >= 0) break;
        if (timeout_ms > 0 && (int32_t)(GetTickCount() - start) >= timeout_ms) {
            if (timed_out) *timed_out = 1;
            break;
        }
        Sleep(1);
    }
    if (winner >= 0) result = ez_race_i32_task_result(&tasks[winner]);
    for (int32_t i = 0; i < count; ++i) {
        if (!tasks[i].started) continue;
        if (i != winner && !ez_race_i32_task_done(&tasks[i])) TerminateThread(tasks[i].thread, 0);
        WaitForSingleObject(tasks[i].thread, INFINITE);
        CloseHandle(tasks[i].thread);
    }
#else
    for (int32_t i = 0; i < count; ++i) {
        tasks[i].branch = branches[i];
        tasks[i].state = &state;
        if (pthread_create(&tasks[i].thread, NULL, ez_race_i32_worker, &tasks[i]) != 0) {
            ez_race_i32_task_finish(&tasks[i], branches[i] ? branches[i]() : 0);
        } else {
            tasks[i].started = true;
        }
    }
    struct timespec start;
    clock_gettime(CLOCK_MONOTONIC, &start);
    int32_t winner = -1;
    while (winner < 0) {
        for (int32_t i = 0; i < count; ++i) {
            if (ez_race_i32_task_done(&tasks[i])) { winner = i; break; }
        }
        if (winner >= 0) break;
        if (timeout_ms > 0) {
            struct timespec now;
            clock_gettime(CLOCK_MONOTONIC, &now);
            int64_t elapsed_ms = (int64_t)(now.tv_sec - start.tv_sec) * 1000 + (now.tv_nsec - start.tv_nsec) / 1000000;
            if (elapsed_ms >= timeout_ms) {
                if (timed_out) *timed_out = 1;
                break;
            }
        }
        usleep(1000);
    }
    if (winner >= 0) result = ez_race_i32_task_result(&tasks[winner]);
    for (int32_t i = 0; i < count; ++i) {
        if (!tasks[i].started) continue;
        if (i != winner && !ez_race_i32_task_done(&tasks[i])) pthread_cancel(tasks[i].thread);
        pthread_join(tasks[i].thread, NULL);
    }
#endif

    ez_race_i32_state_destroy(&state);
    free(tasks);
    return result;
}
