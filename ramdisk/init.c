/* SPDX-License-Identifier: BSD-2-Clause */
/* Initial native Darwin PID1 probe. Runtime libraries and Bash are later stages. */
#include <sys/syscall.h>
#include <sys/socket.h>
#include <sys/sockio.h>
#include <net/if.h>
#include <netinet/in.h>
#include "../xnu/bsd/sys/disk.h"
static long console=-1;
static char filebuf[512],release[64];
static long call(long number,long a,long b,long c,long d,long e,long f) {
    register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c;
    register long x3 __asm__("x3")=d,x4 __asm__("x4")=e,x5 __asm__("x5")=f;
    register long x16 __asm__("x16")=number;
    unsigned error;
    __asm__ volatile("svc #0x80\n cset %w1, cs"
        : "+r"(x0),"=r"(error),"+r"(x1)
        : "r"(x2),"r"(x3),"r"(x4),"r"(x5),"r"(x16) : "memory","cc");
    return error ? -x0 : x0;
}
static void output(const char *s,unsigned long n) {
    while(n) {
        long done=call(SYS_write,console,(long)s,n,0,0,0);
        if(done<=0) return;
        s+=done;n-=(unsigned long)done;
    }
}
static void text(const char *s) { unsigned long n=0;while(s[n])++n;output(s,n); }
static void number(unsigned long n) {
    char out[32];unsigned i=sizeof(out);
    do { out[--i]=(char)('0'+n%10);n/=10; } while(n);
    output(out+i,sizeof(out)-i);
}
static void network_address(struct sockaddr *out,unsigned value) {
    struct sockaddr_in *in=(struct sockaddr_in *)out;
    *in=(struct sockaddr_in){.sin_len=sizeof(*in),.sin_family=AF_INET};
    in->sin_addr.s_addr=__builtin_bswap32(value);
}
static void configure_network(void) {
    long socket=call(SYS_socket,AF_INET,SOCK_DGRAM,0,0,0,0);
    if (socket<0) { text("PID1: USB network socket failed\n");return; }
    struct ifaliasreq address;
    /* Freestanding PID1 has no Libc bzero; keep zeroing explicit/scalar. */
    volatile unsigned char *zero=(volatile unsigned char *)&address;
    for (unsigned i=0;i<sizeof(address);++i) zero[i]=0;
    address.ifra_name[0]='e';address.ifra_name[1]='n';address.ifra_name[2]='0';
    network_address(&address.ifra_addr,0xc0a83502); /* 192.168.53.2 */
    network_address(&address.ifra_broadaddr,0xc0a83503);
    network_address(&address.ifra_mask,0xfffffffc);
    long error=call(SYS_ioctl,socket,SIOCAIFADDR,(long)&address,0,0,0);
    if (!error) text("PID1: USB en0 configured 192.168.53.2/30\n");
    else { text("PID1: en0 address failed, errno ");number((unsigned long)-error);text("\n"); }
    call(SYS_close,socket,0,0,0,0,0);
}
__attribute__((noreturn)) void start(void) {
    console=call(SYS_open,(long)"/dev/console",2,0,0,0,0);
    if(console>=0) for(long fd=0;fd<3;++fd) call(SYS_dup2,console,fd,0,0,0,0);
    text("\nA6PLTE PID1: native ARM64 EL0 entered\nPID: ");
    number((unsigned long)call(SYS_getpid,0,0,0,0,0,0));text("\n");
    int mib[2]={1,2};unsigned long len=sizeof(release);
    if(call(SYS_sysctl,(long)mib,2,(long)release,(long)&len,0,0)==0) {
        text("Darwin release: ");
        if(len && len<=sizeof(release)) output(release,len-1);
        text("\n");
    }
    long file=call(SYS_open,(long)"/etc/a6plte-release",0,0,0,0,0);
    if(file>=0) {
        long n=call(SYS_read,file,(long)filebuf,sizeof(filebuf),0,0,0);
        if(n>0) { text("HFS+ root file read:\n");output(filebuf,(unsigned long)n); }
        else text("PID1: root file read failed\n");
        call(SYS_close,file,0,0,0,0,0);
    } else text("PID1: root file open failed\n");
    long storage=call(SYS_open,(long)"/dev/ra6userdata",0,0,0,0,0);
    if(storage>=0) {
        uint64_t blocks=0;uint32_t writable=0;
        if(!call(SYS_ioctl,storage,DKIOCGETBLOCKCOUNT,(long)&blocks,0,0,0)) {
            text("eMMC userdata: sectors ");number(blocks);text("\n");
        }
        if(!call(SYS_ioctl,storage,DKIOCISWRITABLE,(long)&writable,0,0,0)) {
            text("eMMC userdata: write interface ");text(writable?"enabled\n":"read only\n");
        }
        long n=call(SYS_read,storage,(long)filebuf,512,0,0,0);
        if(n==512) text("PID1: eMMC userdata sector read OK\n");
        else { text("PID1: eMMC userdata read failed ");number((unsigned long)-n);text("\n"); }
        call(SYS_close,storage,0,0,0,0,0);
    } else { text("PID1: userdata device unavailable, errno ");number((unsigned long)-storage);text("\n"); }
    configure_network();
    for(unsigned long beat=1;;++beat) {
        struct { long seconds;int microseconds,pad; } timeout={1,0,0};
        long result=call(SYS_select,0,0,0,0,(long)&timeout,0);
        if(result<0) {
            text("PID1: select failed, errno ");number((unsigned long)-result);text("\n");
            for(;;) call(SYS_select,0,0,0,0,0,0);
        }
        text("PID1: sleep/wakeup ");number(beat);
        unsigned services=0;unsigned long size=sizeof(services);
        static const char name[]="kern.a6plte_services";
        if (!call(SYS_sysctlbyname,(long)name,sizeof(name)-1,(long)&services,(long)&size,0,0)) {
            text(" / IO services ");number(services);
            if (services&16) text(" / watchdog timeout: no reset");
        }
        static const char usb_name[]="kern.a6plte_usb";
        unsigned usb=0;size=sizeof(usb);
        if (!call(SYS_sysctlbyname,(long)usb_name,sizeof(usb_name)-1,(long)&usb,(long)&size,0,0)) {
            text(" / USB ");number(usb);
        }
        text("\n");
    }
}
