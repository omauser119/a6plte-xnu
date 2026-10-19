#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Run the actual IOKit entitlement-query bodies against host provider fixtures."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(path, name, result):
    source = (ROOT / path).read_text()
    start = source.index('\n' + name + '(') + 1
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return result + '\n' + source[start:end] + '\n'


fixture = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
using boolean_t = bool;
using kern_return_t = int;
constexpr int KERN_SUCCESS = 0;
using proc_t = void *;
struct Task { proc_t proc; } user{&user}, kernel{nullptr}, no_proc{nullptr};
using task_t = Task *;
task_t kernel_task = &kernel;
task_t current_task() { return &user; }
proc_t get_bsdtask_info(task_t task) { return task->proc; }
int releases = 0, queries = 0, status = 1, object_kind = 0;
struct OSObject { virtual ~OSObject() = default; virtual void release() { ++releases; delete this; } };
struct OSNumber : OSObject { uint64_t unsigned64BitValue() { return 123456789; } };
struct OSString : OSObject { const char *text = "darwin"; };
struct OSFalse : OSObject { void release() override { ++releases; } } false_object;
OSObject *kOSBooleanFalse = &false_object;
#define OSDynamicCast(type, object) dynamic_cast<type *>(object)
#define OSSafeReleaseNULL(object) do { if (object) (object)->release(); (object) = nullptr; } while (0)
char *copyOSStringAsCString(OSString *s) { return s ? strdup(s->text) : nullptr; }
int boolean_query(proc_t proc, const char *name) {
    assert(proc == user.proc && name); ++queries; return status;
}
int string_query(proc_t proc, const char *name, const char *value) {
    assert(value); return boolean_query(proc, name);
}
int object_query(proc_t proc, const char *name, void **out) {
    int ret = boolean_query(proc, name);
    if (!ret) *out = object_kind == 0 ? static_cast<OSObject *>(new OSNumber) :
        object_kind == 1 ? static_cast<OSObject *>(new OSString) : kOSBooleanFalse;
    return ret;
}
struct Provider {
    struct {
        int (*queryEntitlementStringWithProc)(proc_t, const char *, const char *);
        int (*queryEntitlementBooleanWithProc)(proc_t, const char *);
        int (*copyEntitlementAsOSObjectWithProc)(proc_t, const char *, void **);
    } OSEntitlements;
} provider{{string_query, boolean_query, object_query}}, *amfi = nullptr;
struct IOUserClient { static OSObject *copyClientEntitlement(task_t, const char *); };
'''
names = (
    ('IOTaskHasStringEntitlement', 'boolean_t'),
    ('IOTaskHasEntitlement', 'boolean_t'),
    ('IOTaskGetEntitlement', 'char *'),
)
source = fixture + ''.join(function('xnu/iokit/bsddev/IOKitBSDInit.cpp', n, t) for n, t in names)
source += function('xnu/iokit/Kernel/IOUserClient.cpp', 'IOUserClient::copyClientEntitlement', 'OSObject *')
source += r'''
void denied(task_t task, const char *name) {
    assert(!IOTaskHasStringEntitlement(task, name, "value"));
    assert(!IOTaskHasEntitlement(task, name));
    assert(!IOTaskGetEntitlement(task, name));
    assert(!IOUserClient::copyClientEntitlement(task, name));
}
int main() {
#if A6PLTE
    denied(nullptr, "right"); // No provider, including the current-task path.
    Provider empty{};
    amfi = &empty;
    denied(&user, "right"); // Provider present, optional callbacks absent.
    assert(queries == 0);
#endif
    amfi = &provider;
    denied(&kernel, "right");
    denied(&no_proc, "right");
    denied(&user, nullptr);
    assert(queries == 0);
    denied(&user, "right"); // Provider denies every request.
    status = KERN_SUCCESS;
    assert(IOTaskHasEntitlement(nullptr, "right"));
    assert(IOTaskHasStringEntitlement(&user, "right", "value"));
    assert(!IOTaskGetEntitlement(&user, "right")); // Number isn't a string.
    object_kind = 1;
    char *text = IOTaskGetEntitlement(&user, "right");
    assert(text && !strcmp(text, "darwin")); free(text);
    OSObject *object = IOUserClient::copyClientEntitlement(&user, "right");
    assert(dynamic_cast<OSString *>(object)); object->release();
    assert(releases == 3);
    status = 1;
#if A6PLTE
    auto copy = provider.OSEntitlements.copyEntitlementAsOSObjectWithProc;
    provider.OSEntitlements.copyEntitlementAsOSObjectWithProc = nullptr;
    assert(!IOUserClient::copyClientEntitlement(&user, "right"));
    status = KERN_SUCCESS;
    provider.OSEntitlements.copyEntitlementAsOSObjectWithProc = copy;
#endif
}
'''
with tempfile.TemporaryDirectory(prefix='amfi-', dir=ROOT / 'artifacts') as temp:
    temp = Path(temp)
    (temp / 'queries.cpp').write_text(source)
    for a6 in (0, 1):
        binary = str(temp / f'queries-{a6}')
        subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-g', f'-DA6PLTE={a6}',
                        str(temp / 'queries.cpp'), '-o', binary], check=True)
        subprocess.run([binary], check=True)
print('IOKit entitlement queries: missing/partial provider denial and native provider dispatch passed')
