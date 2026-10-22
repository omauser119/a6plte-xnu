#include "../shim/package.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static struct a6_xnu_package fixture(unsigned version) {
    struct a6_xnu_package h={.version=version,.header=64,.virt=0xfffffff007004000ULL,
        .entry=0xfffffff007004400ULL,.span=0x4000,.bytes=0x4000};
    memcpy(h.magic,version==1 ? "A6XNU01" : "A6XNU02",8);
    if(version==2) { h.flags=1; h.ramdisk_bytes=0x3000; h.bytes+=h.ramdisk_bytes; }
    return h;
}
static int parse(struct a6_xnu_package h,uint64_t size) {
    unsigned char data[65];struct a6_xnu_package out;
    memcpy(data+1,&h,64);
    return a6_package_parse(data+1,size,&out);
}
int main(void) {
    for(unsigned v=1;v<=2;++v) {
        struct a6_xnu_package h=fixture(v),bad;
        uint64_t size=h.bytes+64;
        assert(parse(h,size)==0);
        for(uint64_t n=0;n<64;++n) assert(parse(h,n)!=0);
        assert(parse(h,size-1)!=0 && parse(h,size+1)!=0);
#define BAD(field,value) do { bad=h;bad.field=(value);assert(parse(bad,size)!=0); } while(0)
        BAD(magic[0],'x');BAD(magic[7],'x');BAD(version,3);BAD(header,63);
        BAD(virt,0x4000);BAD(virt,h.virt+1);BAD(virt,0xffffffffffffc000ULL);
        BAD(entry,h.virt-4);BAD(entry,h.virt+h.span);BAD(entry,h.entry+1);
        BAD(span,0);BAD(span,0x1000);BAD(span,65*1024*1024);BAD(bytes,h.bytes+1);
        BAD(flags,2);BAD(ramdisk_bytes,1);
        if(v==1) { BAD(flags,1);BAD(ramdisk_bytes,0x4000); }
        else { BAD(flags,0);BAD(ramdisk_bytes,0);BAD(ramdisk_bytes,65*1024*1024); }
#undef BAD
        struct a6_xnu_layout l;
        assert(a6_package_layout(&h,0x50000000,0x10000000,&l)==0);
        assert(l.kernel==0x50004000 && (l.kernel&0x1fffff)==(h.virt&0x1fffff));
        assert(l.args==l.kernel+h.span && l.tree==l.args+0x4000);
        assert(l.donated==0x0fffc000 && l.top<=0x60000000 && !(l.top&0x3fff));
        if(v==2) assert(l.ramdisk==l.tree+0x10000 && l.top>=l.ramdisk+h.ramdisk_bytes);
        else assert(l.ramdisk==0);
        assert(a6_package_layout(&h,0x50000001,0x10000000,&l)!=0);
        assert(a6_package_layout(&h,UINT64_MAX-0xffff,0x10000000,&l)!=0);
        assert(a6_package_layout(&h,0x50000000,0x40000000,&l)==0);
        assert(l.kernel==0x50004000 && l.donated==0x3fffc000 && l.top<=0x90000000);
        assert(a6_package_layout(&h,0xc0000000,0x40000000,&l)==0);
        assert(l.kernel==0xc0004000 && l.kernel+l.donated==0x100000000ULL);
        assert(a6_package_layout(&h,0xc0200000,0x40000000,&l)!=0);
        assert(a6_package_layout(&h,0x50000000,A6_XNU_MAX_MEMORY+0x200000,&l)!=0);
        h.span=64*1024*1024;h.ramdisk_bytes=64*1024*1024;
        assert(a6_package_layout(&h,0x50000000,128*1024*1024,&l)!=0);
        assert(a6_package_layout(&h,0x50000000,256*1024*1024,&l)==0);
    }
    puts("PASS: kernel/ramdisk package ABI, corrupt headers, overflow, PA/VA alignment and reserved layout");
}
