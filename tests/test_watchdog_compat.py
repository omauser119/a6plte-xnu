#!/usr/bin/env python3
"""Execute the native watchdogd replies and property handling under ASan/UBSan."""
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
source=(root/'xnu/iokit/Kernel/arm/A6PlatformServices.cpp').read_text()
def body(signature):
    start=source.index(signature);opening=source.index('{',start);end=opening+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]+'\n'

fixture=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include <initializer_list>
#define __unused __attribute__((unused))
#define OSDynamicCast(T,p) dynamic_cast<T *>(p)
#define bzero(p,n) memset(p,0,n)
using IOReturn=int;using IOByteCount=uint64_t;
enum {kIOReturnSuccess=0,kIOReturnBadArgument=1,kIOReturnNotPrivileged=2,
      kIOReturnUnsupported=3,kIOReturnMessageTooLarge=4,kIOReturnVMError=5};
enum {kIOExternalMethodScalarOutputCountMax=16,kIOClientPrivilegeAdministrator=1};
struct OSObject {virtual ~OSObject()=default;};
struct OSNumber:OSObject {uint64_t n;explicit OSNumber(uint64_t v):n(v){}uint64_t unsigned64BitValue(){return n;}uint32_t unsigned32BitValue(){return n;}};
struct OSDictionary:OSObject {};
static void *current_task(){return nullptr;}
static bool admin=true;
struct IOUserClient {
    bool terminated=false;
    void terminate(){terminated=true;}
    static IOReturn clientHasPrivilege(void *,unsigned p){assert(p==1);return admin?0:kIOReturnNotPrivileged;}
};
struct IOExternalMethodDispatch {};
struct IOMemoryDescriptor {
    uint64_t length;std::vector<uint8_t> bytes;unsigned writes=0;bool shortWrite=false;
    explicit IOMemoryDescriptor(unsigned n):length(n),bytes(n+16,0xa5){}
    uint64_t getLength(){return length;}
    uint64_t writeBytes(uint64_t off,const void *p,uint64_t n){
        assert(n<=64 && off<=length && n<=length-off && off+n<=bytes.size()-16);++writes;
        if(shortWrite)return n-1;
        memcpy(bytes.data()+8+off,p,n);return n;
    }
    void guards(){for(unsigned i=0;i<8;++i)assert(bytes[i]==0xa5 && bytes[bytes.size()-8+i]==0xa5);}
};
struct IOExternalMethodArguments {
    uint64_t *scalarOutput=nullptr;uint32_t scalarOutputCount=0;
    void *structureOutput=nullptr;uint32_t structureOutputSize=0;
    IOMemoryDescriptor *structureOutputDescriptor=nullptr;uint32_t structureOutputDescriptorSize=0;
};
class IOWatchdogUserClient:public IOUserClient {
public:
    IOReturn clientClose();
    IOReturn externalMethod(uint32_t,IOExternalMethodArguments *,IOExternalMethodDispatch *,OSObject *,void *);
};
class IOWatchdog {
public:
    uint32_t seconds=0;unsigned timerCalls=0;
    void setWatchDogTimer(uint32_t n){seconds=n;++timerCalls;}
    IOReturn setProperties(OSObject *);
};
'''
fixture+=body('IOReturn IOWatchdogUserClient::clientClose(')
fixture+=body('IOReturn IOWatchdogUserClient::externalMethod(')
fixture+=body('IOReturn IOWatchdog::setProperties(')
fixture+=r'''
static void untouched(const uint8_t *p,size_t n){for(size_t i=0;i<n;++i)assert(p[i]==0xa5);}
int main(){
    IOWatchdogUserClient client;
    for(unsigned sel:{0u,1u,2u,3u,4u,5u,9u})for(unsigned size:{0u,1u,7u,63u,64u,65u,4096u,65536u}){
        uint64_t scalars[18];memset(scalars,0xa5,sizeof(scalars));
        std::vector<uint8_t> out(size+16,0xa5);
        IOExternalMethodArguments a;a.scalarOutput=scalars+1;a.scalarOutputCount=16;
        a.structureOutput=out.data()+8;a.structureOutputSize=size;
        assert(client.externalMethod(sel,&a,nullptr,nullptr,nullptr)==0);
        assert(scalars[0]==0xa5a5a5a5a5a5a5a5ULL && scalars[17]==scalars[0]);
        for(unsigned i=1;i<17;++i)assert(!scalars[i]);
        for(unsigned i=0;i<size;++i)assert(!out[8+i]);
        untouched(out.data(),8);untouched(out.data()+8+size,8);
        assert(a.scalarOutputCount==16 && a.structureOutputSize==size);
        IOMemoryDescriptor d(size);a.structureOutputDescriptor=&d;
        assert(client.externalMethod(sel,&a,nullptr,nullptr,nullptr)==0);
        assert(d.writes==(size+63)/64 && a.structureOutputDescriptorSize==size);
        for(unsigned i=0;i<size;++i)assert(!d.bytes[8+i]);d.guards();
    }
    IOExternalMethodArguments a;
    assert(client.externalMethod(1,nullptr,nullptr,nullptr,nullptr)==kIOReturnBadArgument);
    for(unsigned sel:{6u,8u,10u,63u,UINT32_MAX})
        assert(client.externalMethod(sel,&a,nullptr,nullptr,nullptr)==kIOReturnUnsupported);
    a.scalarOutputCount=1;
    assert(client.externalMethod(1,&a,nullptr,nullptr,nullptr)==kIOReturnBadArgument);
    uint64_t scalar=0xabcdef;a.scalarOutput=&scalar;a.scalarOutputCount=17;
    assert(client.externalMethod(1,&a,nullptr,nullptr,nullptr)==kIOReturnBadArgument && scalar==0xabcdef);
    a.scalarOutputCount=0;a.structureOutputSize=1;
    assert(client.externalMethod(2,&a,nullptr,nullptr,nullptr)==kIOReturnBadArgument);
    a.structureOutputSize=65537;
    assert(client.externalMethod(2,&a,nullptr,nullptr,nullptr)==kIOReturnMessageTooLarge);
    IOMemoryDescriptor large(1);large.length=UINT64_MAX;a.structureOutputDescriptor=&large;
    assert(client.externalMethod(9,&a,nullptr,nullptr,nullptr)==kIOReturnMessageTooLarge && !large.writes);
    IOMemoryDescriptor shortOutput(65);shortOutput.shortWrite=true;a.structureOutputDescriptor=&shortOutput;
    assert(client.externalMethod(9,&a,nullptr,nullptr,nullptr)==kIOReturnVMError && shortOutput.writes==1);shortOutput.guards();
    IOWatchdog w;OSDictionary dictionary;OSNumber two(2),overflow(0x100000000ULL);OSObject unknown;
    assert(!w.setProperties(&dictionary) && !w.timerCalls);
    assert(!w.setProperties(&two) && w.seconds==2 && w.timerCalls==1);
    assert(w.setProperties(&overflow)==kIOReturnBadArgument && w.timerCalls==1);
    assert(w.setProperties(&unknown)==kIOReturnBadArgument && w.setProperties(nullptr)==kIOReturnBadArgument);
    admin=false;assert(w.setProperties(&two)==kIOReturnNotPrivileged);
    assert(w.setProperties(&dictionary)==kIOReturnNotPrivileged && w.timerCalls==1);
    assert(!client.clientClose() && client.terminated);
    puts("PASS: native watchdogd selectors, zero replies, short writes/guards, bounded check-ins, PMU dictionary, legacy timer privilege and close");
}
'''
with tempfile.TemporaryDirectory(prefix='watchdog-',dir=root/'artifacts') as directory:
    p=Path(directory);(p/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
