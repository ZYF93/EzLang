// EzLang 语言级最小运行时：flow sleep 与 race(pl) 原生调度。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#endif

typedef int32_t (*EzRaceI32Branch)(void);

typedef struct EzRaceI32Task {
    EzRaceI32Branch branch;
    int32_t result;
    bool done;
#if defined(_WIN32)
    HANDLE thread;
#else
    pthread_t thread;
#endif
} EzRaceI32Task;

typedef struct EzTaskI32 {
    EzRaceI32Branch branch;
    int32_t result;
#if defined(_WIN32)
    HANDLE thread;
#else
    pthread_t thread;
#endif
} EzTaskI32;

#if defined(_WIN32)
static DWORD WINAPI ez_race_i32_worker(LPVOID data) {
    EzRaceI32Task *task = (EzRaceI32Task *)data;
    task->result = task->branch ? task->branch() : 0;
    task->done = true;
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
    task->result = task->branch ? task->branch() : 0;
    task->done = true;
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

#if defined(_WIN32)
    for (int32_t i = 0; i < count; ++i) {
        tasks[i].branch = branches[i];
        tasks[i].thread = CreateThread(NULL, 0, ez_race_i32_worker, &tasks[i], 0, NULL);
        if (!tasks[i].thread) {
            tasks[i].result = branches[i] ? branches[i]() : 0;
            tasks[i].done = true;
        }
    }
    DWORD start = GetTickCount();
    int32_t winner = -1;
    while (winner < 0) {
        for (int32_t i = 0; i < count; ++i) {
            if (tasks[i].done) { winner = i; break; }
        }
        if (winner >= 0) break;
        if (timeout_ms > 0 && (int32_t)(GetTickCount() - start) >= timeout_ms) {
            if (timed_out) *timed_out = 1;
            break;
        }
        Sleep(1);
    }
    int32_t result = winner >= 0 ? tasks[winner].result : 0;
    for (int32_t i = 0; i < count; ++i) {
        if (!tasks[i].thread) continue;
        if (winner >= 0 && i != winner) TerminateThread(tasks[i].thread, 0);
        WaitForSingleObject(tasks[i].thread, INFINITE);
        CloseHandle(tasks[i].thread);
    }
#else
    for (int32_t i = 0; i < count; ++i) {
        tasks[i].branch = branches[i];
        if (pthread_create(&tasks[i].thread, NULL, ez_race_i32_worker, &tasks[i]) != 0) {
            tasks[i].result = branches[i] ? branches[i]() : 0;
            tasks[i].done = true;
        }
    }
    struct timespec start;
    clock_gettime(CLOCK_MONOTONIC, &start);
    int32_t winner = -1;
    while (winner < 0) {
        for (int32_t i = 0; i < count; ++i) {
            if (tasks[i].done) { winner = i; break; }
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
    int32_t result = winner >= 0 ? tasks[winner].result : 0;
    for (int32_t i = 0; i < count; ++i) {
        if (winner >= 0 && i != winner) pthread_cancel(tasks[i].thread);
        pthread_join(tasks[i].thread, NULL);
    }
#endif

    free(tasks);
    return result;
}
