#!/usr/bin/env python3
"""Execute the shipped GUI exit formatter and native kcdata parser under sanitizers."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
source=(root/'xnu/bsd/kern/kern_exit.c').read_text()
start=source.index('static void\na6_display_gui_exit(')
opening=source.index('{',start);end=opening+1;depth=1
while depth:
    depth+=(source[end]=='{')-(source[end]=='}');end+=1
fixture=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include "kern/kcdata.h"
typedef struct reason { uint32_t osr_namespace;uint64_t osr_code,osr_flags;void *osr_kcd_buf;uint32_t osr_bufsize;} *os_reason_t;
typedef struct proc { char p_comm[32];int pid;os_reason_t p_exit_reason;} *proc_t;
static int proc_pid(proc_t p){return p->pid;}
static char displayed[2048];static unsigned calls;
void a6_xnu_diagnostic_message(const char *text){assert(strlen(text)<sizeof(displayed));strcpy(displayed,text);++calls;}
'''+source[start:end]+r'''
int main(void){
    struct reason reason={.osr_namespace=6,.osr_code=0x123456789ULL,.osr_flags=0x80};
    struct proc p={.p_comm="SpringBoard",.pid=25,.p_exit_reason=&reason};
    a6_display_gui_exit(&p,6);
    assert(strstr(displayed,"SpringBoard[25]") && strstr(displayed,"signal=6"));
    assert(strstr(displayed,"namespace=6 code=0x123456789 flags=0x80"));
    assert(strstr(displayed,"description: not supplied"));
    p.p_exit_reason=NULL;a6_display_gui_exit(&p,0x100);
    assert(strstr(displayed,"signal=0 exit_status=1") && strstr(displayed,"reason_present=0"));
    p.p_exit_reason=&reason;
    /* Deliberately unterminated description at the end of the allocation. */
    for(unsigned n=0;n<1100;++n){
        size_t bytes=2*sizeof(struct kcdata_item)+n;
        unsigned char *data=calloc(1,bytes);assert(data);
        struct kcdata_item *begin=(void*)data,*item=(void*)(data+sizeof(*begin));
        begin->type=KCDATA_BUFFER_BEGIN_OS_REASON;
        item->type=EXIT_REASON_USER_DESC;item->size=n;
        memset(item->data,'X',n);
        reason.osr_kcd_buf=data;reason.osr_bufsize=bytes;
        a6_display_gui_exit(&p,9);
        assert(strstr(displayed,n?"description: XXX":"description: empty description") || n<3);
        if(n>512)assert(strlen(displayed)<896);
        /* Invalid header/length and missing item must never walk off-buffer. */
        reason.osr_bufsize=bytes-1;a6_display_gui_exit(&p,9);
        assert(strstr(displayed,"missing or invalid description"));
        reason.osr_bufsize=bytes;item->type=0x1234;a6_display_gui_exit(&p,9);
        assert(strstr(displayed,"missing or invalid description"));
        free(data);
    }
    unsigned char data[64]={0};struct kcdata_item *begin=(void*)data,*item=(void*)(data+16);
    begin->type=KCDATA_BUFFER_BEGIN_OS_REASON;item->type=EXIT_REASON_USER_DESC;item->size=32;
    memcpy(item->data,"real failure\ntext\033",18);
    reason.osr_kcd_buf=data;reason.osr_bufsize=sizeof(data);
    a6_display_gui_exit(&p,6);assert(strstr(displayed,"description: real failure text "));
    strcpy(p.p_comm,"backboardd");a6_display_gui_exit(&p,5);assert(strstr(displayed,"backboardd[25]"));
    unsigned prior=calls;strcpy(p.p_comm,"unrelated");a6_display_gui_exit(&p,6);assert(calls==prior);
    puts("PASS: native GUI reason parser bounds, missing/malformed/unterminated descriptions, 64-bit reason and target filtering");
}
'''
# The authoritative reason is printed before optional scans and crash delivery.
prepare=source[source.index('\nproc_prepareexit(proc_t'):]
assert prepare.index('a6_display_gui_exit(p, rv)') < prepare.index('a6_crash_process(p, WTERMSIG(rv))') < prepare.index('task_exception_notify(')
with tempfile.TemporaryDirectory(dir=root/'artifacts',prefix='gui-exit-') as d:
    path=Path(d);(path/'test.c').write_text(fixture)
    subprocess.run(['clang','-std=gnu17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(root/'xnu/osfmk'),str(path/'test.c'),'-o',str(path/'test')],check=True)
    subprocess.run([str(path/'test')],check=True)
