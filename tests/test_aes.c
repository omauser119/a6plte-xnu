#include "../xnu/libkern/crypto/a6plte_aes/aes.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned hex(char c) { return c >= 'a' ? (unsigned)(c-'a'+10) : (unsigned)(c-'0'); }
static void decode(unsigned char *out, const char *s) {
    assert(strlen(s)%2==0);
    for (size_t i=0; i<strlen(s)/2; ++i) out[i]=(unsigned char)(hex(s[2*i])*16+hex(s[2*i+1]));
}

int main(void) {
    /* NIST SP 800-38A, F.2.1 through F.2.6: four-block AES-CBC vectors. */
    const char *keys[]={
        "2b7e151628aed2a6abf7158809cf4f3c",
        "8e73b0f7da0e6452c810f32b809079e562f8ead2522c6b7b",
        "603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4"
    };
    const char *cipher[]={
        "7649abac8119b246cee98e9b12e9197d5086cb9b507219ee95db113a917678b2"
        "73bed6b8e3c1743b7116e69e222295163ff1caa1681fac09120eca307586e1a7",
        "4f021db243bc633d7178183a9fa071e8b4d9ada9ad7dedf4e5e738763f69145a"
        "571b242012fb7ae07fa9baac3df102e008b0e27988598881d920a9e64f5615cd",
        "f58c4c04d6e5f1ba779eabfb5f7bfbd69cfc4e967edb808d679f777bc6702c7d"
        "39f23369a9d9bacfa530e26304231461b2eb05e2c39be9fcda6c19078c6a9d1b"
    };
    unsigned char plain[64], expected[64], iv[16];
    decode(plain,"6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e51"
                 "30c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710");
    decode(iv,"000102030405060708090a0b0c0d0e0f");
    for (unsigned k=0; k<3; ++k) for (unsigned off=0; off<8; ++off) {
        unsigned char key[40]={0}, input[80], output[80], initial_iv[24];
        a6_legacy_aes_encrypt_ctx enc;
        a6_legacy_aes_decrypt_ctx dec;
        int bytes=16+8*(int)k;
        assert(strlen(keys[k])==(size_t)bytes*2 && strlen(cipher[k])==128);
        decode(key+off,keys[k]); decode(expected,cipher[k]);
        memcpy(input+off,plain,64); memcpy(initial_iv+off,iv,16);
        assert(a6_legacy_aes_encrypt_key(key+off,bytes,&enc)==aes_good);
        assert(a6_legacy_aes_decrypt_key(key+off,bytes*8,&dec)==aes_good);
        memset(output,0x5a,sizeof(output));
        assert(a6_legacy_aes_encrypt_cbc(input+off,initial_iv+off,4,output+off,&enc)==aes_good);
        if (memcmp(output+off,expected,64)) {
            fprintf(stderr,"AES-CBC mismatch: key bits %d, byte offset %u\n",bytes*8,off);
            for (unsigned i=0;i<64;++i) fprintf(stderr,"%02x",output[off+i]);
            fputc('\n',stderr);
        }
        assert(!memcmp(output+off,expected,64));
        for (unsigned i=0; i<off; ++i) assert(output[i]==0x5a);
        for (unsigned i=off+64; i<sizeof(output); ++i) assert(output[i]==0x5a);
        assert(!memcmp(initial_iv+off,iv,16));
        assert(a6_legacy_aes_decrypt_cbc(output+off,initial_iv+off,4,input+off,&dec)==aes_good);
        assert(!memcmp(input+off,plain,64));
        memcpy(input+off,plain,64);
        assert(a6_legacy_aes_encrypt_cbc(input+off,initial_iv+off,4,input+off,&enc)==aes_good);
        assert(!memcmp(input+off,expected,64));
        assert(a6_legacy_aes_decrypt_cbc(input+off,initial_iv+off,4,input+off,&dec)==aes_good);
        assert(!memcmp(input+off,plain,64));
        assert(a6_legacy_aes_encrypt_cbc(NULL,NULL,0,NULL,&enc)==aes_good);
        assert(a6_legacy_aes_decrypt_cbc(NULL,NULL,0,NULL,&dec)==aes_good);
    }
    /* FIPS 197, appendix C: ECB via one CBC block with a zero IV (TCP TFO). */
    const char *ecb[]={"69c4e0d86a7b0430d8cdb78070b4c55a","dda97ca4864cdfe06eaf70a0ec0d7191","8ea2b7ca516745bfeafc49904b496089"};
    for (unsigned k=0;k<3;++k) {
        unsigned char key[32],out[16];
        a6_legacy_aes_encrypt_ctx enc;
        a6_legacy_aes_decrypt_ctx dec;
        for(unsigned i=0;i<32;++i)key[i]=(unsigned char)i;
        decode(plain,"00112233445566778899aabbccddeeff");decode(expected,ecb[k]);
        assert(a6_legacy_aes_encrypt_key(key,16+8*(int)k,&enc)==aes_good);
        assert(a6_legacy_aes_decrypt_key(key,16+8*(int)k,&dec)==aes_good);
        assert(a6_legacy_aes_encrypt_cbc(plain,NULL,1,out,&enc)==aes_good);
        assert(!memcmp(out,expected,16));
        assert(a6_legacy_aes_decrypt_cbc(out,NULL,1,out,&dec)==aes_good);
        assert(!memcmp(out,plain,16));
        assert(a6_legacy_aes_encrypt_key(key,17,&enc)==aes_error);
        assert(a6_legacy_aes_decrypt_key(key,-1,&dec)==aes_error);
    }
    puts("PASS: Apple legacy AES, NIST CBC/ECB 128/192/256, byte alignment, in-place, IV and zero blocks");
}
