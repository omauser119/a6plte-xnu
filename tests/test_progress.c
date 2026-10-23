/* Exercise the actual bounded history used by the device sampler. */
#include "../xnu/osfmk/arm64/a6plte_progress.h"
#include <assert.h>
#include <stdio.h>

static struct a6_progress_history history;
static struct a6_progress_sample snap={.pid=25,.tid=210,.wall_us=1000000,
    .cpu_us=50000,.pc=0x1000,.lr=0x2000,.sp=0x3000,.frames={0x4000,0x5000},
    .runnable=1,.stack_valid=1,.frame_count=2};
static void advance(unsigned cpu) {snap.wall_us+=10000000;snap.cpu_us+=cpu;}
int main(void) {
    struct a6_progress_result r=a6_progress_update(&history,&snap);
    assert(r.baseline && !strcmp(r.activity,"baseline") && !r.elapsed_us && !r.stack_repeats);
    advance(7500000);r=a6_progress_update(&history,&snap);
    assert(!r.baseline && r.elapsed_us==10000000 && r.cpu_delta_us==7500000);
    assert(!strcmp(r.activity,"cpu-active") && r.stack_repeats==1 && !r.wait_repeats);
    /* Running at the same saved PC/stack is an observation, not proof of a loop. */
    advance(1000000);r=a6_progress_update(&history,&snap);assert(r.stack_repeats==2);
    snap.frames[1]++;advance(2);r=a6_progress_update(&history,&snap);assert(!r.stack_repeats);
    advance(0);r=a6_progress_update(&history,&snap);
    assert(!strcmp(r.activity,"runnable-no-cpu") && !r.cpu_delta_us);
    snap.runnable=0;snap.waiting=1;snap.event=0x1234;snap.queue=0x5678;snap.hint=3;snap.state=9;
    advance(5);r=a6_progress_update(&history,&snap);assert(!strcmp(r.activity,"waiting") && !r.wait_repeats);
    advance(0);r=a6_progress_update(&history,&snap);assert(r.wait_repeats==1);
    advance(0);r=a6_progress_update(&history,&snap);assert(r.wait_repeats==2);
    snap.event++;advance(0);r=a6_progress_update(&history,&snap);assert(!r.wait_repeats);
    snap.queue++;advance(0);r=a6_progress_update(&history,&snap);assert(!r.wait_repeats);
    snap.hint++;advance(0);r=a6_progress_update(&history,&snap);assert(!r.wait_repeats);
    snap.continuation++;advance(0);r=a6_progress_update(&history,&snap);assert(!r.wait_repeats);
    snap.state++;advance(0);r=a6_progress_update(&history,&snap);assert(!r.wait_repeats);
    snap.waiting=0;advance(0);r=a6_progress_update(&history,&snap);
    assert(!r.wait_repeats && !strcmp(r.activity,"not-running"));
    snap.stack_valid=0;advance(0);r=a6_progress_update(&history,&snap);assert(!r.stack_repeats);
    advance(0);r=a6_progress_update(&history,&snap);assert(!r.stack_repeats);
    snap.stack_valid=1;advance(0);r=a6_progress_update(&history,&snap);assert(!r.stack_repeats);
    snap.stack_short=1;advance(0);r=a6_progress_update(&history,&snap);assert(!r.stack_repeats);
    advance(0);r=a6_progress_update(&history,&snap);assert(r.stack_repeats==1);
    /* Restarted PID must not inherit the old thread's deltas. */
    snap.tid++;advance(0);r=a6_progress_update(&history,&snap);assert(r.baseline);
    snap.pid=56;advance(0);r=a6_progress_update(&history,&snap);assert(r.baseline);
    snap.cpu_us=1;advance(0);r=a6_progress_update(&history,&snap);assert(r.baseline && !r.cpu_delta_us);
    struct a6_progress_sample old=snap;
    old.wall_us--;old.cpu_us=0;r=a6_progress_update(&history,&old);
    assert(r.baseline && !strcmp(r.activity,"out-of-order"));
    advance(50);r=a6_progress_update(&history,&snap);assert(!r.baseline && r.cpu_delta_us==50 && r.elapsed_us==10000000);
    r=a6_progress_update(&history,&snap);assert(r.baseline && !strcmp(r.activity,"out-of-order"));
    /* More threads than slots evict only bounded entries without aliasing IDs. */
    for(unsigned i=0;i<4*A6_PROGRESS_SLOTS;++i){
        snap.tid=10000+i;advance(1);r=a6_progress_update(&history,&snap);assert(r.baseline);
    }
    advance(10);r=a6_progress_update(&history,&snap);assert(!r.baseline && r.cpu_delta_us==10);
    snap.tid=210;snap.pid=25;advance(1);r=a6_progress_update(&history,&snap);assert(r.baseline);
    uint64_t stamp=history.stamp;
    snap.frame_count=A6_PROGRESS_FRAMES+1;r=a6_progress_update(&history,&snap);assert(r.baseline && history.stamp==stamp);
    snap.frame_count=0;snap.tid=0;r=a6_progress_update(&history,&snap);assert(r.baseline && history.stamp==stamp);
    puts("PASS: sampler CPU/wall deltas, exact saved stacks, repeated waits, unavailable/short stacks, restarts, stale snapshots and bounded history eviction");
}
