/* SPDX-License-Identifier: BSD-2-Clause */
#include "../xnu/bsd/dev/a6plte/usb_dwc3.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct mock {
    uint32_t registers[16384];struct a6_usb_dma *dma;uint64_t clock;
    unsigned producer,stuck,error_command,links,up,received,length;
    uint8_t packet[1514];
};
static uint32_t read_reg(void *cookie,unsigned r) { struct mock *m=cookie;assert(r<0x10000 && r%4==0);return m->registers[r/4]; }
static void write_reg(void *cookie,unsigned r,uint32_t v) {
    struct mock *m=cookie;assert(r<0x10000 && r%4==0);
    if (r==0xc40c || r==0xc41c) { assert(v<=m->registers[r/4]);m->registers[r/4]-=v;return; }
    if (r==0xc704) {
        m->registers[0xc70c/4]=(m->registers[0xc70c/4]&7) | ((v&(1u<<31))?0:1u<<22);
        v&=~(1u<<30);
    }
    if (r>=0xc80c && r<=0xc85c && (r-0xc80c)%16==0 && !m->stuck) {
        unsigned ep=(r-0xc80c)/16,cmd=v&15;
        v&=~(1u<<10);
        if (cmd==6) {
            assert(m->registers[(r-4)/4]==0);assert((m->registers[(r-8)/4]&15)==0);
            /* Real 2.70a trace: initial SETUP before RUN_STOP returns index 0. */
            if (m->registers[0xc704/4]&(1u<<31)) v|=(ep+1)<<16;
        }
        if (cmd==m->error_command) v|=1u<<12;
    }
    m->registers[r/4]=v;
}
static uint64_t ticks(void *cookie) { return ++((struct mock *)cookie)->clock; }
static uint64_t physical(void *cookie,const void *pointer) {
    struct mock *m=cookie;uintptr_t p=(uintptr_t)pointer,b=(uintptr_t)m->dma;
    assert(p>=b && p<b+sizeof(*m->dma));return 0x50000000+(p-b);
}
static void sync_dma(void *cookie,void *pointer,unsigned length,unsigned direction) {
    struct mock *m=cookie;uintptr_t p=(uintptr_t)pointer,b=(uintptr_t)m->dma;
    assert(p>=b && p+length>=p && p+length<=b+sizeof(*m->dma));assert(direction<=2);
}
static void receive(void *cookie,const uint8_t *p,unsigned n) {
    struct mock *m=cookie;assert(n<=sizeof(m->packet));memcpy(m->packet,p,n);m->length=n;++m->received;
}
static void link_changed(void *cookie,int up) { struct mock *m=cookie;++m->links;m->up=up; }
static const struct a6_usb_ops ops={read_reg,write_reg,ticks,physical,sync_dma,receive,link_changed,NULL};
static void initialize(struct mock *m,struct a6_dwc3 *d) {
    memset(m,0,sizeof(*m));m->dma=aligned_alloc(4096,sizeof(*m->dma));assert(m->dma);memset(m->dma,0,sizeof(*m->dma));
    m->registers[0xc120/4]=0x5533260a;m->registers[0xc14c/4]=16<<12;m->registers[0xc308/4]=256;
    m->registers[0xc70c/4]=1u<<22;
    *d=(struct a6_dwc3){.ops=&ops,.cookie=m,.dma=m->dma,.frequency=1000};
}
static void event(struct mock *m,struct a6_dwc3 *d,uint32_t e) {
    assert(m->registers[0xc40c/4]<=4092);
    m->dma->events[m->producer/4]=e;m->producer=(m->producer+4)%4096;m->registers[0xc40c/4]+=4;
    a6_dwc3_poll(d);
}
static void complete(struct mock *m,struct a6_dwc3 *d,unsigned ep,unsigned remaining,unsigned condition) {
    assert(d->active[ep]);m->dma->trb[ep].size=remaining | condition<<28;m->dma->trb[ep].control&=~1u;
    event(m,d,ep<<1 | 1u<<6);
}
static void control(struct mock *m,struct a6_dwc3 *d,unsigned type,unsigned request,unsigned value,unsigned index,unsigned length) {
    uint8_t p[8]={(uint8_t)type,(uint8_t)request,(uint8_t)value,(uint8_t)(value>>8),(uint8_t)index,(uint8_t)(index>>8),(uint8_t)length,(uint8_t)(length>>8)};
    memcpy(m->dma->setup,p,8);complete(m,d,0,0,0);
    if (length) complete(m,d,1,0,0);
    unsigned ep=length?!(type&0x80):1;
    event(m,d,ep<<1 | 3u<<6 | 2u<<12);
    assert(d->active[ep]);complete(m,d,ep,0,0);
}
static void descriptor_tests(void) {
    struct a6_ecm s={.high_speed=1};struct a6_usb_reply r;
    uint8_t p[8]={0x80,6,0,2,0,0,255,0};
    assert(!a6_ecm_setup(&s,p,&r) && r.length==80);
    unsigned endpoints=0,interfaces=0;
    for (unsigned off=0;off<r.length;) {
        unsigned n=r.data[off];assert(n>=2 && n<=r.length-off);
        if (r.data[off+1]==5) { ++endpoints;unsigned ep=r.data[off+2];if (ep!=0x81) assert(r.data[off+4]==0 && r.data[off+5]==2); }
        if (r.data[off+1]==4) ++interfaces;
        off+=n;
    }
    assert(endpoints==3 && interfaces==3);
    s.high_speed=0;assert(!a6_ecm_setup(&s,p,&r));assert(r.data[47]==16 && r.data[70]==64 && !r.data[71]);
    p[3]=7;assert(!a6_ecm_setup(&s,p,&r));assert(r.data[1]==7 && r.data[70]==0 && r.data[71]==2);
    p[2]=4;p[3]=3;p[4]=9;p[5]=4;assert(!a6_ecm_setup(&s,p,&r) && r.length==26);
    assert(r.data[0]==26 && r.data[2]=='0' && r.data[3]==0);
    p[0]=0;p[1]=9;p[2]=1;p[3]=p[4]=p[5]=p[6]=0;assert(a6_ecm_setup(&s,p,&r));
    s.address=7;assert(!a6_ecm_setup(&s,p,&r));assert(!s.configuration && r.next.configuration==1);
    /* Exhaustive type/request fuzz plus wide field variations: no reply overrun. */
    uint64_t seed=123456789;
    for (unsigned i=0;i<100000;++i) {
        for (unsigned j=0;j<8;++j) { seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;p[j]=(uint8_t)seed; }
        s.address=(uint8_t)(i%128);s.configuration=i%2;s.alternate=i%2;
        if (!a6_ecm_setup(&s,p,&r)) assert(r.length<=256 && r.length<=(unsigned)(p[6] | p[7]<<8));
    }
    uint8_t out[18];memset(out,0xcc,sizeof(out));assert(a6_ecm_notification(out+1,16,1,1)==16);
    assert(out[0]==0xcc && out[17]==0xcc && out[1]==0xa1 && out[2]==0x2a);
    assert(!a6_ecm_notification(out,7,0,1));
}
int main(void) {
    descriptor_tests();struct mock m;struct a6_dwc3 d;initialize(&m,&d);
    assert(!a6_dwc3_start(&d) && d.active[0] && d.online);
    assert(d.resource[0]==0);
    assert(m.registers[0xc408/4]==(4096u | 1u<<31));
    control(&m,&d,0x80,6,0x100,0,18);assert(d.active[0]);
    { /* Logical state changes only after the status completion event. */
        uint8_t p[8]={0,5,7,0,0,0,0,0};memcpy(m.dma->setup,p,8);complete(&m,&d,0,0,0);
        assert(d.ecm.address==0 && d.reply.next.address==7);
        event(&m,&d,1u<<1 | 3u<<6 | 2u<<12);assert(d.ecm.address==0 && d.active[1]);
        complete(&m,&d,1,0,0);
    }
    assert(d.ecm.address==7 && (m.registers[0xc700/4]&0x3f8)==7<<3);
    control(&m,&d,0,9,1,0,0);assert(d.ecm.configuration && !a6_ecm_link(&d.ecm));
    control(&m,&d,1,11,1,1,0);assert(m.up && d.active[4] && d.active[3]);
    for (unsigned i=0;i<64;++i) m.dma->rx[i]=(uint8_t)i;
    complete(&m,&d,4,2048-64,0);assert(m.received==1 && m.length==64 && !memcmp(m.packet,m.dma->rx,64) && d.active[4]);
    uint8_t packet[1515]={0};assert(!a6_dwc3_send(&d,packet,512));assert(d.tx_pending);
    complete(&m,&d,5,0,0);assert(d.active[5] && !d.queued[5] && d.tx_pending);
    complete(&m,&d,5,0,0);assert(!d.tx_pending && d.tx_packets==1);
    assert(a6_dwc3_send(&d,packet,1515));
    complete(&m,&d,3,0,0);assert(d.active[3] && d.queued[3]==16);complete(&m,&d,3,0,0);assert(!d.notify_pending);
    control(&m,&d,2,3,0,2,0);assert(d.ecm.halted==2 && !d.active[4]);
    control(&m,&d,2,1,0,2,0);assert(!d.ecm.halted && d.active[4]);
    control(&m,&d,0x21,0x43,0x0c,0,0);assert(d.ecm.filter==0x0c);
    memset(m.dma->setup,0xff,8);complete(&m,&d,0,0,0);assert(d.online && d.active[0]);
    event(&m,&d,1u | 1u<<8);assert(!m.up && !d.ecm.configuration && !d.ecm.address && d.active[0]);
    /* Wrap the event ring without acknowledging or reading beyond its extent. */
    for (unsigned i=0;i<2000;++i) event(&m,&d,1u | 3u<<8);
    assert(d.online && d.event_offset==m.producer);
    m.registers[0xc40c/4]=3;a6_dwc3_poll(&d);assert(!d.online && d.errors);
    free(m.dma);
    initialize(&m,&d);m.stuck=1;assert(a6_dwc3_start(&d) && !d.online && d.errors);assert(m.clock<1000);free(m.dma);
    initialize(&m,&d);m.error_command=1;assert(a6_dwc3_start(&d) && !d.online);free(m.dma);
    puts("PASS: CDC-ECM descriptors/control bounds, 100000 fuzz cases, DWC3 EP0/bulk/ZLP, cache spans, stalls, reset, ring wrap, command errors and bounded timeout");
}
