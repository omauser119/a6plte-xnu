/* SPDX-License-Identifier: BSD-2-Clause */
#include "../xnu/bsd/dev/a6plte/storage.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct fake {
    uint8_t regs[256],ext[512],media[1024*512];
    uint64_t ticks;
    unsigned command,argument,position,commands,writes,flushes,busy;
    int fault;
};
static struct fake f;
static unsigned get(unsigned o,unsigned n) { unsigned v=0;for(unsigned i=0;i<n;++i)v|=(unsigned)f.regs[o+i]<<(8*i);return v; }
static void set(unsigned o,unsigned n,unsigned v) { for(unsigned i=0;i<n;++i)f.regs[o+i]=(uint8_t)(v>>(8*i)); }
static uint32_t read_reg(void *cookie,unsigned o,unsigned n) {
    assert(cookie==&f && o+n<=sizeof(f.regs));
    if(o!=32) return get(o,n);
    assert(n==4 && (f.command==8 || f.command==17) && f.position<512);
    uint8_t *p=f.command==8?f.ext:f.media+f.argument*512;
    unsigned v=(unsigned)p[f.position]|(unsigned)p[f.position+1]<<8|(unsigned)p[f.position+2]<<16|(unsigned)p[f.position+3]<<24;
    f.position+=4;if(f.position==512)set(48,2,get(48,2)|2);return v;
}
static void write_reg(void *cookie,unsigned o,unsigned n,uint32_t v) {
    assert(cookie==&f && o+n<=sizeof(f.regs));
    assert(o==4 || o==6 || o==8 || o==12 || o==14 || o==32 || o==46 || o==48 || o==50 || o==52 || o==54 || o==56 || o==58);
    if(o==48 || o==50) { set(o,n,get(o,n)&~v);return; }
    if(o==32) {
        assert(n==4 && f.command==24 && f.position<512 && f.argument<1024);
        uint8_t *p=f.media+f.argument*512+f.position;
        for(unsigned i=0;i<4;++i)p[i]=(uint8_t)(v>>(i*8));
        f.position+=4;if(f.position==512){++f.writes;if(f.fault!=5)set(48,2,get(48,2)|2);}return;
    }
    set(o,n,v);
    if(o!=14)return;
    f.command=v>>8;f.argument=get(8,4);f.position=0;++f.commands;
    assert(f.command==8 || f.command==13 || f.command==17 || f.command==24 || f.command==6);
    assert(!(get(12,2)&1)); /* No DMA, multi-block, stop or erase commands. */
    if(f.fault==1 && f.command==17)return; /* Command timeout. */
    if(f.fault==2 && f.command==17){set(48,2,0x8000);set(50,2,2);return;}
    set(16,4,0x900);set(48,2,1);
    if(f.fault==3 && f.command==24){set(16,4,0x80000900);return;}
    switch(f.command) {
    case 13:
        if(f.busy){--f.busy;set(16,4,7<<9);}break;
    case 8:set(48,2,1|0x20);break;
    case 17:
        assert(f.argument<1024);if(f.fault!=4)set(48,2,1|0x20);break;
    case 24:
        assert(f.argument<1024);set(48,2,1|0x10);f.busy=2;break;
    case 6:
        assert(f.argument==((3u<<24)|(32u<<16)|(1u<<8)));
        ++f.flushes;set(48,2,3);break;
    }
}
static uint64_t ticks(void *cookie) { assert(cookie==&f);f.ticks+=100;return f.ticks; }
static const struct a6_sdhci_ops ops={read_reg,write_reg,ticks};
static struct a6_emmc host;
static void fixture(void) {
    memset(&f,0,sizeof(f));set(44,2,7);set(41,1,1);set(40,1,0xa0);
    f.ext[192]=8;f.ext[213]=4; /* 1024 sectors. */
    host=(struct a6_emmc){.ops=&ops,.cookie=&f,.frequency=1000000,.rca=2};
}
int main(void) {
    uint8_t input[1025],output[1025];
    for(unsigned i=0;i<sizeof(input);++i)input[i]=(uint8_t)(i*17);
    fixture();assert(!a6_emmc_adopt(&host) && host.blocks==1024 && host.online);
    assert(get(40,1)==0xa0 && get(44,2)==7 && get(56,2)==0 && get(58,2)==0);
    assert(!a6_emmc_write(&host,1022,2,input+1));assert(f.writes==2 && !f.flushes);
    assert(!a6_emmc_read(&host,1022,2,output+1));assert(!memcmp(input+1,output+1,1024));
    assert(!a6_emmc_flush(&host));
    unsigned before=f.commands;
    assert(a6_emmc_write(&host,1023,2,input)==A6_IO_INVALID);
    assert(a6_emmc_read(&host,UINT64_MAX,1,output)==A6_IO_INVALID && f.commands==before);
    fixture();f.ext[33]=1;f.ext[249]=1;assert(!a6_emmc_adopt(&host));assert(!a6_emmc_flush(&host) && f.flushes==1);
    fixture();f.ext[179]=3;assert(a6_emmc_adopt(&host)==A6_IO_INVALID && !host.online);
    fixture();f.ext[61]=1;assert(a6_emmc_adopt(&host)==A6_IO_INVALID && !host.online);
    fixture();set(44,2,0);assert(a6_emmc_adopt(&host)==A6_IO_OFFLINE && !f.commands);
    for(int fault=1;fault<=5;++fault) {
        fixture();assert(!a6_emmc_adopt(&host));f.fault=fault;before=f.commands;
        int error=fault==3 || fault==5 ? a6_emmc_write(&host,20,1,input) : a6_emmc_read(&host,20,1,output);
        assert(error && !host.online && f.commands==before+1);
        assert(a6_emmc_read(&host,0,1,output)==A6_IO_OFFLINE && f.commands==before+1);
        if(fault==3)assert(!f.writes);
        if(fault==5)assert(f.writes==1 && !f.flushes); /* No ambiguous-write retry. */
    }
    puts("PASS: SDHCI PIO, inherited state, unaligned buffers, cache flush, bounds, CRC/R1/timeouts and no write retry");
}
