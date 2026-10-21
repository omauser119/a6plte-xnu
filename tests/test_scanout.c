#include "../xnu/iokit/Kernel/arm/A6Scanout.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t random32(void) {static uint32_t v=0x13579246;v^=v<<13;v^=v>>17;v^=v<<5;return v;}
int main(void) {
    uint8_t s[32]={0,0,255,255,0,255,0,255,255,0,0,255,255,255,255,255};
    uint8_t d[64];memset(d,0xa5,sizeof(d));
    struct a6_scanout source={s,16,2,2,8,A6_BGRA,0},target={d+16,16,2,2,8,1,0};
    struct a6_rect all={0,0,2,2};int nonblack=0;
    assert(a6_scanout_blit(&source,all,&target,all,0,&nonblack) && nonblack);
    const uint8_t expected[16]={255,0,0,0,255,0,0xa5,0xa5,0,0,255,255,255,255,0xa5,0xa5};
    assert(!memcmp(d+16,expected,16));
    for(unsigned i=0;i<16;++i)assert(d[i]==0xa5 && d[i+32]==0xa5);
    uint8_t scaled[4*4*4]={};struct a6_scanout big={scaled,sizeof(scaled),4,4,16,2,0};
    assert(a6_scanout_blit(&source,all,&big,(struct a6_rect){0,0,4,4},0,0));
    assert(scaled[2]==255 && scaled[6]==255 && scaled[9]==255 && scaled[15]==255);
    assert(scaled[32]==255 && scaled[40]==255 && scaled[41]==255 && scaled[42]==255);
    uint8_t red[4]={0,0,128,128},blue[4]={255,0,0,255};
    source=(struct a6_scanout){red,4,1,1,4,A6_BGRA,0};target=(struct a6_scanout){blue,4,1,1,4,2,0};
    assert(a6_scanout_blit(&source,(struct a6_rect){0,0,1,1},&target,(struct a6_rect){0,0,1,1},1,0));
    assert(blue[0]==127 && blue[1]==0 && blue[2]==128 && blue[3]==255);
    source.offset=UINT32_MAX;assert(!a6_scanout_valid(&source));source.offset=0;
    source.stride=UINT32_MAX;assert(!a6_scanout_valid(&source));source.stride=4;
    source.bytes=3;assert(!a6_scanout_valid(&source));source.bytes=4;
    assert(!a6_scanout_blit(&source,(struct a6_rect){0,0,0,1},&target,all,0,0));
    uint8_t input[16*16*4],output[32+16*16*4];memset(input,127,sizeof(input));
    for(unsigned n=0;n<10000;++n) {
        unsigned sw=1+random32()%16,sh=1+random32()%16,dw=1+random32()%16,dh=1+random32()%16;
        source=(struct a6_scanout){input,sizeof(input),sw,sh,sw*4,A6_RGBA,0};
        target=(struct a6_scanout){output+16,dw*dh*4,dw,dh,dw*4,2,0};
        memset(output,0xa5,sizeof(output));
        struct a6_rect a={(int32_t)(random32()%40)-20,(int32_t)(random32()%40)-20,(int32_t)(random32()%24),(int32_t)(random32()%24)};
        struct a6_rect b={(int32_t)(random32()%40)-20,(int32_t)(random32()%40)-20,(int32_t)(random32()%24),(int32_t)(random32()%24)};
        if(n%7==0)b.x=INT32_MIN;if(n%11==0)b.width=INT32_MAX;if(n%13==0)a.height=INT32_MAX;
        (void)a6_scanout_blit(&source,a,&target,b,n&1,0);
        for(unsigned i=0;i<16;++i)assert(output[i]==0xa5);
        for(unsigned i=16+dw*dh*4;i<sizeof(output);++i)assert(output[i]==0xa5);
    }
    puts("PASS: actual BGRA/RGB888 and XRGB scanout, scaling, premultiplied alpha, padding/guards, invalid metadata and 10000 extreme clipped rectangles");
}
