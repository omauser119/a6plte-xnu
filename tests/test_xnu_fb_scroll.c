#include "../xnu/pexpert/arm/a6plte/fb.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void check(unsigned format, unsigned bytes, unsigned pad, unsigned offset, unsigned rows)
{
    const unsigned width=53, height=36*rows+11, stride=width*bytes+pad;
    const size_t size=(size_t)stride*height, guard=64+offset, total=guard+size+64;
    unsigned char *actual=malloc(total), *expected=malloc(total);
    assert(actual && expected);
    for(size_t i=0;i<total;i++) actual[i]=(unsigned char)(i*37+19);
    memcpy(expected,actual,total);
    struct a6_fb fb;
    assert(!a6_fb_init(&fb,(uintptr_t)(actual+guard),size,width,height,stride,format));
    fb.x=1; fb.y=rows-1;
    const size_t line=36*stride, used=line*rows;
    for(unsigned repeat=0;repeat<3;repeat++) {
        memmove(expected+guard,expected+guard+line,used-line);
        memset(expected+guard+used-line,0,line);
        a6_fb_putc(&fb,'\n');
        assert(fb.x==0 && fb.y==rows-1);
        assert(!memcmp(actual,expected,total));
    }
    memset(expected+guard,0,size);
    a6_fb_clear(&fb);
    assert(!memcmp(actual,expected,total));
    assert(fb.x==0 && fb.y==0);
    free(actual);free(expected);
}

int main(void)
{
    for(unsigned offset=0;offset<8;offset++)
        for(unsigned pad=0;pad<9;pad++)
            for(unsigned rows=1;rows<=3;rows++) {
                check(A6_RGB888,3,pad,offset,rows);
                check(A6_XRGB8888,4,pad,offset,rows);
                check(A6_RGB565,2,pad,offset,rows);
            }
    puts("PASS: XNU framebuffer scroll/clear matches memmove; all alignments, tails, padding and guards");
}
