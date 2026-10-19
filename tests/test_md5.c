#include "../xnu/libkern/crypto/a6plte_md5.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void check(const unsigned char *digest, const char *hex) {
    char text[33];
    for(unsigned i=0;i<16;++i) snprintf(text+2*i,3,"%02x",digest[i]);
    assert(!strcmp(text,hex));
}
int main(void) {
    /* RFC 1321 MD5 test suite, including padding and block boundaries. */
    const char *in[]={"","a","abc","message digest","abcdefghijklmnopqrstuvwxyz",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        "12345678901234567890123456789012345678901234567890123456789012345678901234567890"};
    const char *out[]={"d41d8cd98f00b204e9800998ecf8427e","0cc175b9c0f1b6a831c399e269772661",
        "900150983cd24fb0d6963f7d28e17f72","f96b697d7cb7938d525a2f31aaf161d0",
        "c3fcd3d76192e4007dfb496cca67e13b","d174ab98d277d9f5a5611c2c9f419d9f",
        "57edf4a22be3c955ac49da2e2107b67a"};
    for(unsigned i=0;i<7;++i) for(unsigned off=0;off<8;++off) {
        unsigned char data[96],digest[32];
        MD5_CTX c;
        memset(digest,0xa5,sizeof(digest));
        memcpy(data+off,in[i],strlen(in[i]));
        a6_md5_init(&c);a6_md5_update(&c,data+off,(unsigned)strlen(in[i]));a6_md5_final(digest+off,&c);
        check(digest+off,out[i]);
        for(unsigned j=0;j<off;++j) assert(digest[j]==0xa5);
        for(unsigned j=off+16;j<sizeof(digest);++j) assert(digest[j]==0xa5);
        a6_md5_init(&c);
        for(unsigned j=0;j<strlen(in[i]);++j) a6_md5_update(&c,data+off+j,1);
        a6_md5_final(digest,&c);check(digest,out[i]);
    }
    unsigned char chunk[1000],digest[16];MD5_CTX c;
    memset(chunk,'a',sizeof(chunk));a6_md5_init(&c);
    for(unsigned i=0;i<1000;++i) a6_md5_update(&c,chunk,sizeof(chunk));
    a6_md5_final(digest,&c);check(digest,"7707d6ae4e027c70eea2a935c2296f21");
    puts("PASS: Apple legacy MD5, RFC 1321 vectors, scalar unaligned I/O, incremental and million-byte inputs");
}
