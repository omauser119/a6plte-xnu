#include "../xnu/iokit/Kernel/arm/A6HIDWire.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
struct hardware {
    uint32_t *regs[5];uint64_t now;
    uint8_t tx[16],rx[16],cmd,events[32][8],pon;
    unsigned tx_count,rx_count,rx_at,event_count,event_at;
    int reset_timeout,nack,cleanup_timeout,bad_boot,service_only,stale_service;
    uint64_t drain_until;
    unsigned pending_pauses,touch_enabled;
    uint64_t stop_until;
    unsigned early_resets;
    uint32_t core_error;
};
static const unsigned sizes[5]={0x100000,0x50000,0x1000,0x1000,0x800000};
static uint32_t read_reg(void *ctx,unsigned region,unsigned offset) {
    struct hardware *h=ctx;assert(region<5 && !(offset&3) && offset<sizes[region]);
    if(region==A6_INPUT_QUP && offset==0x18) {
        /* Aborting two STOPs leaves this model's sensor/bus stalled on the
         * third command, exactly exposing the reported cmd21/reg18/val40. */
        if(h->early_resets>=2)return 0x40;
        if(h->stale_service && h->now<h->drain_until)return (1u<<8)|(1u<<4);
        return (h->service_only?1u<<8:1u<<10)|(h->rx_at<h->rx_count?1u<<5:0);
    }
    if(region==A6_INPUT_QUP && offset==0x218) {
        uint32_t value=0;for(unsigned j=0;j<4 && h->rx_at<h->rx_count;++j)value|=(uint32_t)h->rx[h->rx_at++]<<(8*j);return value;
    }
    if(region==A6_INPUT_QUP && offset==0x404)return h->nack?8:
        h->regs[region][offset/4]|(h->now<h->stop_until?1u<<8:0);
    if(region==A6_INPUT_QUP && offset==0x1c)return h->core_error?h->core_error:h->regs[region][offset/4];
    if(region==A6_INPUT_TLMM && offset==59*0x1000+4)return h->event_at<h->event_count?0:1;
    return h->regs[region][offset/4];
}
static void execute(struct hardware *h) {
    unsigned n=h->regs[A6_INPUT_QUP][0x150/4]&0x7fffffff;
    if(h->tx_count<n || !n)return;
    assert(n<=8 && h->tx[0]==0x81);
    if(h->tx[1]==0x90) {
        assert(h->tx[2]==0x82 || h->tx[2]==0x83);assert(n==4+(unsigned)h->tx[3]);
        h->cmd=h->tx[4];
        if(h->tx[2]==0x83)h->stop_until=h->now+50;
        assert(h->cmd==0x52 || h->cmd==0x55 || h->cmd==0x21 || h->cmd==0x23 || h->cmd==0x30 || h->cmd==0x62 || h->cmd==0x10 || h->cmd==0x60);
        if(h->cmd==0x30) {assert(n==7 && h->tx[5]==1 && !h->tx[6]);h->touch_enabled=1;}
    } else {
        assert(n==4 && h->tx[1]==0x91 && h->tx[2]==0x87);
        unsigned bytes=h->tx[3];assert(bytes<=11 && h->regs[A6_INPUT_QUP][0x208/4]==((1u<<31)| (bytes+2)));
        memset(h->rx,0,sizeof(h->rx));h->rx[0]=0x85;h->rx[1]=(uint8_t)bytes;h->rx_count=bytes+2;h->rx_at=0;
        h->stop_until=h->now+50; /* byte visibility precedes completion of STOP */
        switch(h->cmd) {
        case 0x52:assert(bytes==3);h->rx[2]=0x76;h->rx[3]=1;h->rx[4]=1;break;
        case 0x55:assert(bytes==1);h->rx[2]=h->bad_boot?0x10:0x20;break;
        case 0x21:assert(bytes==1 && h->touch_enabled);h->rx[2]=0x80;break;
        case 0x23:assert(bytes==11);h->rx[2]=4;h->rx[3]=0x38;h->rx[4]=8;h->rx[5]=0xac;break;
        case 0x60:
            assert(bytes==8);
            if(h->event_at<h->event_count)memcpy(h->rx+2,h->events[h->event_at++],8);
            break;
        default:assert(0);
        }
    }
    h->tx_count=0;
}
static void write_reg(void *ctx,unsigned region,unsigned offset,uint32_t value) {
    struct hardware *h=ctx;assert(region<5 && !(offset&3) && offset<sizes[region]);
    assert(region!=A6_INPUT_SPMI); /* Never issue PMIC power/reset configuration writes. */
    if(region==A6_INPUT_OBSERVER) {
        assert(offset==3*0x8000 && value==((1u<<27)|(0x10u<<4)));
        h->regs[region][(offset+8)/4]=1;h->regs[region][(offset+0x18)/4]=h->pon;return;
    }
    if(region==A6_INPUT_TLMM)assert(offset==6*0x1000 || offset==7*0x1000 || offset==59*0x1000 || offset==85*0x1000 || offset==139*0x1000 || offset==139*0x1000+4);
    if(region==A6_INPUT_GCC) {
        assert(offset==0x45004 || offset==0x3004 || offset==0x3000 || offset==0x3010);
        if(offset==0x3000)value&=~1u;
    }
    if(region==A6_INPUT_QUP && (offset==0x1c || offset==0x404)) {
        h->regs[region][offset/4]&=~value;return; /* W1C error status */
    }
    h->regs[region][offset/4]=value;
    if(region==A6_INPUT_QUP) {
        if(offset==0x28)assert(!value); /* FIFO, not BAM service masking. */
        if(offset==0xc) { h->tx_count=h->rx_count=h->rx_at=0;h->regs[region][1]=h->reset_timeout?0:4; }
        if(offset==0x408 && value==1)h->regs[region][1]|=0x10;
        if(offset==4) {
            if(value==3 && h->now<h->drain_until)++h->pending_pauses;
            if(value==0 && h->now<h->stop_until)++h->early_resets;
            h->regs[region][1]=h->cleanup_timeout && value==0?0:value|4|0x10;
            if(value==1) {
                int output=h->tx_count && h->tx[1]==0x90;
                execute(h);
                if(h->stale_service && output)h->drain_until=h->now+40;
            }
        }
        if(offset==0x110)for(unsigned j=0;j<4;++j) {assert(h->tx_count<16);h->tx[h->tx_count++]=(uint8_t)(value>>(8*j));}
    }
}
static uint64_t time_us(void *ctx) { return ((struct hardware *)ctx)->now; }
static void delay(void *ctx,unsigned us) { ((struct hardware *)ctx)->now+=us; }
static void contact(uint8_t e[8],unsigned id,unsigned state,unsigned x,unsigned y,unsigned remaining) {
    memset(e,0,8);e[0]=(uint8_t)(state<<6|id<<2);e[1]=(uint8_t)(x>>4);e[2]=(uint8_t)(y>>4);
    e[3]=(uint8_t)((x&15)<<4|(y&15));e[4]=12;e[5]=9;e[6]=32;e[7]=(uint8_t)remaining;
}
int main(void) {
    struct hardware h={0};for(unsigned i=0;i<5;++i) {h.regs[i]=calloc(1,sizes[i]);assert(h.regs[i]);}
    h.regs[A6_INPUT_SPMI][0]=0x20010000;h.regs[A6_INPUT_SPMI][(0x800+3*4)/4]=8u<<8;
    h.regs[A6_INPUT_TLMM][(85*0x1000+4)/4]=1;
    struct a6_input s;struct a6_input_bus bus={&h,read_reg,write_reg,time_us,delay};
    /* A NACK left by an earlier transaction must be acknowledged before probe. */
    h.regs[A6_INPUT_QUP][0x404/4]=8;h.regs[A6_INPUT_QUP][0x1c/4]=4;
    int initial=a6_input_init(&s,&bus);
    if(initial)fprintf(stderr,"probe failure cmd %x reg %08x value %08x\n",s.command,s.error_register,s.error_value);
    assert(!initial && s.touch_ready && s.pon_ready && s.pon_channel==3 && !h.early_resets);
    h.service_only=1; /* No MAX_OUTPUT_DONE: FIFO completion uses SERVICE. */
    assert(!a6_input_init(&s,&bus) && s.touch_ready && !h.early_resets);
    h.stale_service=1;
    assert(!a6_input_init(&s,&bus) && s.touch_ready && !h.pending_pauses);
    assert(s.max_x==4095 && s.max_y==4095);
    contact(h.events[0],1,1,900,1500,1);contact(h.events[1],10,1,300,1000,0);h.event_count=2;
    assert(a6_input_poll(&s)==1 && s.changed==0x201 && s.fingers[0].active && s.fingers[9].active);
    uint8_t data[A6_HID_PACKET_MAX+16];memset(data,0xa5,sizeof(data));
    for(unsigned cap=0;cap<340;++cap) {assert(!a6_hid_touch_packet(data,cap,1,2,&s));for(unsigned j=0;j<sizeof(data);++j)assert(data[j]==0xa5);}
    assert(a6_hid_touch_packet(data,sizeof(data),0x1122334455667788,0x8877665544332211,&s)==340);
    struct a6_hid_header header;memcpy(&header,data,28);assert(header.timestamp==0x1122334455667788 && header.sender==0x8877665544332211 && header.count==3 && !header.attributes);
    struct a6_hid_digitizer d;memcpy(&d,data+28+104,104);
    assert(d.base.size==104 && d.base.type==11 && d.base.depth==1 && d.identity==1 && d.transducer==2);
    assert(d.x==900*65536/4095 && d.y==1500*65536/4095 && (d.base.options&(1u<<17)));
    for(unsigned i=340;i<sizeof(data);++i)assert(data[i]==0xa5);
    s.changed=0;contact(h.events[2],1,3,900,1500,0);h.event_count=3;
    assert(a6_input_poll(&s)==1 && !s.fingers[0].active && s.fingers[9].active);
    assert(a6_hid_touch_packet(data,sizeof(data),1,2,&s)==340);memcpy(&d,data+28+104,104);assert(!(d.base.options&(1u<<17)) && !d.pressure);
    /* All buttons require three matching samples. PON reads are read-only. */
    h.regs[A6_INPUT_TLMM][(85*0x1000+4)/4]=0;h.pon=3;
    assert(!a6_input_poll(&s));assert(!a6_input_poll(&s));assert(a6_input_poll(&s)==14 && s.buttons==7);
    for(unsigned key=0;key<3;++key) {
        assert(a6_hid_key_packet(data,sizeof(data),3,4,key,1)==60);
        struct a6_hid_key k;memcpy(&k,data+28,32);assert(k.base.type==3 && k.page==12 && k.down==1);
        assert(k.usage==(key==0?0xe9:key==1?0xea:0x30));
    }
    h.regs[A6_INPUT_TLMM][(85*0x1000+4)/4]=1;h.pon=0;
    assert(!a6_input_poll(&s));assert(!a6_input_poll(&s));assert(a6_input_poll(&s)==14 && !s.buttons);
    /* Bus failure releases contacts instead of leaving a stuck finger. */
    s.changed=0;h.nack=1;h.event_count=4;
    assert(a6_input_poll(&s)==1 && !s.fingers[9].active && s.changed==(1u<<9));h.nack=0;
    /* Invalid wire contact IDs and status events never index outside ten slots. */
    for(unsigned byte=0;byte<256;++byte) {uint8_t e[8]={(uint8_t)byte};a6_input_decode(&s,e);}
    uint32_t reg,value,cmd;
    h.core_error=4;h.cleanup_timeout=1;
    assert(a6_input_init(&s,&bus)==-1 && !s.touch_ready);
    a6_input_probe_status(&reg,&value,&cmd);
    assert(reg==0x0200001c && value==4 && cmd==0x60); /* Cleanup must not hide the FIFO error. */
    h.core_error=0;h.cleanup_timeout=0;h.bad_boot=1;
    assert(a6_input_init(&s,&bus)==-1 && !s.touch_ready);
    a6_input_probe_status(&reg,&value,&cmd);
    assert(reg==0x05000055 && value==0x10 && cmd==0x55);
    h.bad_boot=0;
    h.reset_timeout=1;h.event_count=h.event_at=0;uint64_t before=h.now;
    assert(a6_input_init(&s,&bus)==-1 && !s.touch_ready && h.now-before<160000);
    for(unsigned i=0;i<5;++i)free(h.regs[i]);
    puts("PASS: QUP FIFO service unmasked, stale SERVICE while output pending, delayed STOP, lagging DONE, sensor application startup order, repeated START/tagged FIFO, touch decode/slots/release, bounded timeout, read-only PON, button debounce and Apple HID wire bounds");
}
