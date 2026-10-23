#!/usr/bin/env python3
"""Exercise native scheduler snapshots and finite early sampling, without live stacks."""
from pathlib import Path
import re
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
native=(root/'xnu/osfmk/arm64/a6plte_diagnostics.c').read_text()
compat=(root/'xnu/bsd/dev/a6plte/compat.c').read_text()
thread=(root/'xnu/osfmk/kern/thread.h').read_text()
waitq=(root/'xnu/osfmk/kern/waitq.h').read_text()
def body(source,signature):
    start=source.index(signature);opening=source.index('{',start);end=opening+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]+'\n'

start=native.index('struct a6_wait_state {');end=native.index('};',start)+2
queue=re.search(r'typedef union \{\s*struct waitq\s+\*wq_q;.*?\} __waitq_transparent_union waitq_t;',waitq,re.S).group(0)
defines='\n'.join(re.search(r'^#define '+name+r'\s+.*$',thread,re.M).group(0) for name in ('TH_WAIT','TH_RUN','TH_SUSP','TH_UNINT'))
fixture=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include "kern/block_hint.h"
#define __waitq_transparent_union
#define __unused __attribute__((unused))
''' + queue + '\n' + defines + '\n' + native[start:end] + r'''
typedef unsigned spl_t;typedef unsigned wait_result_t;
typedef struct {int seconds,microseconds;} time_value_t;
static unsigned irq_level=7,locks=0,unlocks=0,terminated=0,iterations=0,sleeps=0,printed=0;
static unsigned display_reports;
static void a6_report_display(void){++display_reports;}
static int ticks[40];static const int hz=100,PZERO=0,PROC_ALLPROCLIST=1;
static char sample_names[128]="SpringBoard,backboardd";
typedef struct {
    uint64_t thread_id,wait_event;int state,sched_pri;unsigned block_hint;
    waitq_t waitq;void (*continuation)(void);int held;
} *thread_t;
static spl_t splsched(void){unsigned old=irq_level;irq_level=255;return old;}
static void thread_lock(thread_t t){assert(irq_level==255 && !t->held);t->held=1;++locks;}
static void thread_unlock(thread_t t){assert(irq_level==255 && t->held);t->held=0;++unlocks;t->wait_event=0;t->continuation=NULL;}
static void thread_read_times(thread_t t,time_value_t *u,time_value_t *s,time_value_t *r){assert(t->held && irq_level==255 && !r);*u=(time_value_t){2,300};*s=(time_value_t){1,400};}
static uint64_t mach_absolute_time(void){assert(irq_level==255);return 123456789000ULL;}
static void absolutetime_to_nanoseconds(uint64_t ticks,uint64_t *out){assert(irq_level==255);*out=ticks;}
static void splx(spl_t old){assert(locks==unlocks);irq_level=old;}
static int tsleep(void *chan,int priority,const char *name,int timeout){assert(chan && priority==PZERO && !strcmp(name,"a6sample") && sleeps<40);ticks[sleeps++]=timeout;return 0;}
static int sample_process(void *p,void *a){(void)p;(void)a;return 0;}
static void proc_iterate(unsigned flags,int (*callback)(void *,void *),void *a,void *b,void *c){assert(flags==PROC_ALLPROCLIST && callback==sample_process && !a && !b && !c);++iterations;}
static void thread_terminate_self(void){++terminated;}
static int sample_printf(const char *format,...){(void)format;assert(irq_level==7 && locks==unlocks);++printed;return 0;}
static void resume(void){}
enum {MACH_TRAP_TABLE_COUNT=128};
typedef struct {int (*mach_trap_function)(void *);} mach_trap_t;
static int mach_message(void *p){(void)p;return 0;}
static const mach_trap_t mach_trap_table[128]={[47]={mach_message}};
static const char * const mach_syscall_name_table[128]={[47]="mach_msg2_trap"};
static const int mach_trap_count=128;
'''
fixture+=body(native,'static void a6_capture_wait(')
fixture+=body(native,'static const char *a6_wait_kind(')
fixture+=body(native,'static const char *a6_last_trap(')
fixture+='#define printf sample_printf\n'+body(compat,'static void sample_thread(')+'#undef printf\n'
fixture+=r'''
int main(void){
    __typeof__(*(thread_t)0) t={.thread_id=0x123456789abcdef0ULL,.wait_event=0xdeadbeef,
        .state=TH_WAIT|TH_UNINT,.sched_pri=47,.block_hint=kThreadWaitPortReceive,
        .waitq={.wq_q=(struct waitq *)(uintptr_t)0x1234},.continuation=resume};
    struct a6_wait_state out={0};
    a6_capture_wait(&t,&out);
    assert(irq_level==7 && locks==1 && unlocks==1 && !t.held);
    assert(out.tid==0x123456789abcdef0ULL && out.event==0xdeadbeef && out.queue==0x1234);
    assert(out.state==(TH_WAIT|TH_UNINT) && out.priority==47 && out.hint==kThreadWaitPortReceive);
    assert(out.continuation==(uintptr_t)resume && !t.continuation && !t.wait_event);
    assert(out.cpu_us==3000700 && out.wall_us==123456789);
    assert(!strcmp(a6_wait_kind(TH_RUN,kThreadWaitKernelMutex),"runnable"));
    assert(!strcmp(a6_wait_kind(TH_SUSP,kThreadWaitKernelMutex),"stopped"));
    assert(!strcmp(a6_wait_kind(out.state,out.hint),"IPC-receive"));
    assert(!strcmp(a6_wait_kind(TH_WAIT,kThreadWaitKernelMutex),"kernel-mutex"));
    assert(!strcmp(a6_wait_kind(TH_WAIT,kThreadWaitPThreadMutex),"pthread-mutex"));
    assert(!strcmp(a6_wait_kind(TH_WAIT,kThreadWaitSemaphore),"semaphore"));
    for(unsigned hint=0;hint<=255;++hint)assert(a6_wait_kind(TH_WAIT,hint));
    assert(!strcmp(a6_wait_kind(TH_WAIT,255),"event"));
    uintptr_t function=0;
    assert(!strcmp(a6_last_trap((uint64_t)-47,&function),"mach_msg2_trap") && function==(uintptr_t)mach_message);
    for(unsigned x=0;x<128;++x){a6_last_trap(0-(uint64_t)x,&function);assert(function==(x==47?(uintptr_t)mach_message:0));}
    assert(!strcmp(a6_last_trap(0,&function),"BSD/user") && !function);
    assert(!strcmp(a6_last_trap(128,&function),"BSD/user") && !function);
    assert(!strcmp(a6_last_trap((uint64_t)-128,&function),"unknown") && !function);
    assert(!strcmp(a6_last_trap(1ULL<<63,&function),"unknown") && !function);
    sample_thread(NULL,0);
    assert(sleeps==40 && ticks[0]==5*hz && iterations==40 && printed==40 && terminated==1 && display_reports==40);
    for(unsigned i=1;i<40;++i)assert(ticks[i]==10*hz);
    sample_names[0]='-';sample_thread(NULL,0);
    assert(sleeps==40 && iterations==40 && printed==40 && terminated==2);
    puts("PASS: native wait snapshots preserve IRQ/thread-lock ordering, copy opaque scalars only, classify native hints and sample 40 times before/through startup");
}
'''
with tempfile.TemporaryDirectory(prefix='wait-sampler-',dir=root/'artifacts') as directory:
    p=Path(directory);(p/'test.c').write_text(fixture)
    subprocess.run(['clang','-std=gnu17','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g','-I'+str(root/'xnu/osfmk'),str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
