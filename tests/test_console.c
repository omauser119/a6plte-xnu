#include "../console/fb.h"
#include "../shim/fdt.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv) {
    assert(argc==2);
    for(unsigned fmt=1;fmt<=3;++fmt) {
        unsigned pixel=fmt==1?3:fmt==2?4:2;
        unsigned stride=109*pixel+7, bytes=stride*113;
        uint8_t *buf=malloc(bytes+128); memset(buf,0xa5,bytes+128);
        struct a6_fb f;
        assert(!a6_fb_init(&f,(uintptr_t)(buf+64),bytes,109,113,stride,fmt));
        a6_fb_clear(&f);
        for(unsigned n=0;n<100;++n) a6_fb_puts(&f,"LINE\t0123456789\rTEST\n");
        for(unsigned i=0;i<64;++i) assert(buf[i]==0xa5 && buf[bytes+64+i]==0xa5);
        assert(a6_fb_init(&f,(uintptr_t)(buf+64),1,109,113,stride,fmt));
        assert(a6_fb_init(&f,(uintptr_t)(buf+64),bytes,109,113,1,fmt));
        free(buf);
    }
    FILE *in=fopen(argv[1],"rb"); assert(in); fseek(in,0,SEEK_END); long size=ftell(in); rewind(in);
    uint8_t *blob=calloc(1,size); assert(fread(blob,1,size,in)==(size_t)size); fclose(in);
    struct platform p;
    /* fixture has a real RAM bank in place of the upstream bootloader-filled placeholder */
    assert(platform_parse(blob,&p)==0); assert(p.fb.width==1080 && p.fb.height==2220 && p.fb.stride==3240);
    uint64_t addr;
    assert(!platform_alloc(&p,0x1000000,0x200000,(struct range){0x80000000,0x100000},&addr));
    assert(addr>=0x80200000);
    blob[0]=0; assert(platform_parse(blob,&p)!=0); free(blob);
    puts("PASS: RGB888/XRGB8888/RGB565, scroll/wrap/padding/guards, FDT, RAM reservations");
}
