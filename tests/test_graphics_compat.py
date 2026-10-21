#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Execute the native 0046-compatible clients, zero replies and retained swap queue."""
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
surface=(root/'xnu/iokit/Kernel/arm/A6Surface.cpp').read_text()
fb=(root/'xnu/iokit/Kernel/arm/A6Framebuffer.cpp').read_text()
def body(source,signature):
    start=source.index(signature);opening=source.index('{',start);end=opening+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]+'\n'

fixture=r'''
#include "A6Scanout.h"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <vector>
#include <initializer_list>
#define __unused __attribute__((unused))
#define bzero(p,n) memset(p,0,n)
#define A6_SWAP_BYTES 0x46c
#define A6_LAYERS 4
#define A6_NOTIFY_TYPES 8
#define A6PLTE_SURFACE_ROW_ALIGN 64
#define OSSafeReleaseNULL(p) do {if(p){(p)->release();(p)=nullptr;}} while(0)
#define OSDynamicCast(T,p) dynamic_cast<T *>(p)
using IOReturn=int;using mach_port_name_t=uint32_t;
enum {kIOReturnSuccess=0,kIOReturnBadArgument=1,kIOReturnNoSpace=2,kIOReturnVMError=3,kIOReturnNotOpen=4,kIOReturnNotReady=5,kIOReturnNotFound=6};
enum {kA6SurfaceCreate=0,kA6SurfaceLookup=4,kA6SurfaceLimits=13,kA6SurfaceLookupFromPort=34,kA6SurfaceCreatePort=35};
struct OSObject {virtual ~OSObject()=default;virtual void release(){}};
struct IOExternalMethodDispatch {};
struct Descriptor {
 std::vector<uint8_t> data;unsigned writes=0;bool shortWrite=false;
 Descriptor(unsigned n):data(n,0xa5){}
 uint64_t getLength(){return data.size();}
 uint64_t writeBytes(uint64_t off,const void *p,uint64_t n){assert(off+n<=data.size());++writes;if(shortWrite)return 0;memcpy(data.data()+off,p,n);return n;}
};
struct IOExternalMethodArguments {
 uint32_t asyncWakePort=0,asyncReferenceCount=0;
 const uint64_t *scalarInput=nullptr;uint32_t scalarInputCount=0;
 const void *structureInput=nullptr;uint32_t structureInputSize=0;Descriptor *structureInputDescriptor=nullptr;
 uint64_t *scalarOutput=nullptr;uint32_t scalarOutputCount=0;
 void *structureOutput=nullptr;uint32_t structureOutputSize=0;Descriptor *structureOutputDescriptor=nullptr;uint32_t structureOutputDescriptorSize=0;
};
struct IOLock {bool held=false;};
static void IOLockLock(IOLock *l){assert(!l->held);l->held=true;}
static void IOLockUnlock(IOLock *l){assert(l->held);l->held=false;}
struct A6Surface:OSObject {
 unsigned refs=1;uint32_t planeCount=0,bytesPerElement=4,elementWidth=1,elementHeight=1,pixelFormat=A6_BGRA;
 void retain(){++refs;}void release()override{assert(refs>1);--refs;}
};
static A6Surface surfaces[4];
static A6Surface *a6_surface_copy(uint32_t id){if(id<1 || id>4)return nullptr;auto s=&surfaces[id-1];s->retain();return s;}
static bool a6_surface_get(A6Surface *){return true;}
struct IOUserClient {
 static IOReturn copyPortNameForObjectInTask(void *,OSObject *,mach_port_name_t *p){*p=42;return 0;}
 static IOReturn copyObjectForPortNameInTask(void *,mach_port_name_t,OSObject **p){*p=nullptr;return kIOReturnNotFound;}
};
static void a6_surf_log_once(const char *,uint32_t){}
class IOSurfaceRootUserClient {
public:
 void *fTask=nullptr;bool inactive=false;
 bool isInactive(){return inactive;}
 IOReturn create(IOExternalMethodArguments *){return kIOReturnBadArgument;}
 IOReturn returnSurface(A6Surface *,IOExternalMethodArguments *){return kIOReturnBadArgument;}
 IOReturn externalMethod(uint32_t,IOExternalMethodArguments *,IOExternalMethodDispatch *,OSObject *,void *);
};
class AppleCLCD {
public:
 IOLock lock,*fLock=&lock;A6Surface *fPending[4]={},*fSurface=&surfaces[0];
 uint8_t fRecord[A6_SWAP_BYTES]={};uint32_t fSubmitted=0;bool fDirty=false,fEligible=false,enabled=false;
 uint32_t sequence=0;unsigned waits=0;bool powered=true;
 uint32_t begin(){return ++sequence;}uint32_t width(){return 1080;}uint32_t height(){return 2220;}
 void enableDefault(){enabled=true;}void power(bool p){powered=p;}
 IOReturn wait(uint32_t){++waits;return kIOReturnBadArgument;}
 IOReturn submit(const uint8_t *,bool);
};
class IOMobileFramebufferUserClient:public IOUserClient {
public:
 AppleCLCD *fFB=nullptr;void *fTask=nullptr;bool fClosed=false,fEligible=true;
 uint64_t fFunc[A6_NOTIFY_TYPES]={},fRefcon[A6_NOTIFY_TYPES]={};
 bool isInactive(){return false;}
 IOReturn externalMethod(uint32_t,IOExternalMethodArguments *,IOExternalMethodDispatch *,OSObject *,void *);
};
'''
for signature in ('static void\nput32(', 'static IOReturn\na6_struct_out(', 'IOReturn a6_graphics_zero_reply(', 'IOReturn\nIOSurfaceRootUserClient::externalMethod('):
    fixture+=body(surface,signature)
for signature in ('static uint32_t get32(', 'IOReturn AppleCLCD::submit(', 'IOReturn IOMobileFramebufferUserClient::externalMethod('):
    fixture+=body(fb,signature)
fixture+=r'''
static void zeros(const uint8_t *p,unsigned n){for(unsigned i=0;i<n;++i)assert(!p[i]);}
static void guarded(const uint8_t *p,unsigned n){for(unsigned i=0;i<n;++i)assert(p[i]==0xa5);}
int main(){
 IOSurfaceRootUserClient surf;AppleCLCD display;IOMobileFramebufferUserClient client;client.fFB=&display;
 // 0046: optional selectors return zero values with original reply sizes.
 for(unsigned sel=0;sel<100;++sel){
  if(sel==0 || sel==4 || sel==13 || sel==34 || sel==35)continue;
  uint64_t out[4]={1,2,3,0xfeed};uint8_t bytes[48];memset(bytes,0xa5,sizeof(bytes));
  IOExternalMethodArguments a;a.scalarOutput=out;a.scalarOutputCount=3;a.structureOutput=bytes+8;a.structureOutputSize=32;
  assert(!surf.externalMethod(sel,&a,nullptr,nullptr,nullptr));
  assert(!out[0] && !out[1] && !out[2] && out[3]==0xfeed && a.scalarOutputCount==3 && a.structureOutputSize==32);
  zeros(bytes+8,32);guarded(bytes,8);guarded(bytes+40,8);
  if(sel==3 || sel==5 || sel==8 || sel==12 || sel==72)continue;
  memset(bytes,0xa5,sizeof(bytes));out[0]=out[1]=out[2]=1;
  assert(!client.externalMethod(sel,&a,nullptr,nullptr,nullptr));
  assert(a.scalarOutputCount==3 && a.structureOutputSize==32);zeros(bytes+8,32);
  guarded(bytes,8);guarded(bytes+40,8);
  if(sel==18)assert(out[0]==1);else if(sel==28)assert(out[0]==411);else assert(!out[0]);
  assert(!out[1] && !out[2] && out[3]==0xfeed);
 }
 // Out-of-line zeros are bounded by the requested length, not descriptor capacity.
 Descriptor desc(1032);IOExternalMethodArguments a;a.structureOutputDescriptor=&desc;a.structureOutputDescriptorSize=1025;
 assert(!surf.externalMethod(16,&a,nullptr,nullptr,nullptr));assert(desc.writes==5 && a.structureOutputDescriptorSize==1025);
 zeros(desc.data.data(),1025);guarded(desc.data.data()+1025,7);
 desc.shortWrite=true;assert(client.externalMethod(17,&a,nullptr,nullptr,nullptr)==kIOReturnVMError);
 a.structureOutputDescriptorSize=1033;assert(a6_graphics_zero_reply(&a)==kIOReturnNoSpace);
 Descriptor huge(65537);a.structureOutputDescriptor=&huge;a.structureOutputDescriptorSize=65537;
 assert(a6_graphics_zero_reply(&a)==kIOReturnNoSpace && !huge.writes);
 a={};a.structureOutputSize=4;assert(a6_graphics_zero_reply(&a)==kIOReturnBadArgument);
 a={};a.scalarOutputCount=1;assert(a6_graphics_zero_reply(&a)==kIOReturnBadArgument);
 // Native default surface requests are not limited to scalar layer zero.
 uint64_t out[3]={},input[4]={2,0,0,0};a={};a.scalarInput=input;a.scalarInputCount=1;a.scalarOutput=out;a.scalarOutputCount=3;
 assert(!client.externalMethod(3,&a,nullptr,nullptr,nullptr) && out[0]==42 && !out[1] && a.scalarOutputCount==3 && display.enabled);
 a={};assert(!client.externalMethod(6,&a,nullptr,nullptr,nullptr) && !display.waits);
 // SwapEnd is valid without Begin, with multiple Begins, and with an old token.
 uint8_t record[A6_SWAP_BYTES]={};put32(record,0x104,0x8000000f);put32(record,0x54,1);put32(record,0x58,0);put32(record,0x5c,999);put32(record,0x60,2);
 surfaces[1].pixelFormat=0xdeadbeef;
 a={};a.structureInput=record;a.structureInputSize=sizeof(record);
 assert(!client.externalMethod(5,&a,nullptr,nullptr,nullptr));
 assert(display.fSubmitted==1 && display.fDirty && display.fEligible && display.fPending[0]==&surfaces[0] && surfaces[0].refs==2);
 assert(!display.fPending[1] && !display.fPending[2] && !display.fPending[3] && surfaces[1].refs==1);
 for(unsigned i=0;i<2;++i){IOExternalMethodArguments b;b.scalarOutput=out;b.scalarOutputCount=1;assert(!client.externalMethod(4,&b,nullptr,nullptr,nullptr));}
 put32(record,0x50,0xfeed);assert(!client.externalMethod(5,&a,nullptr,nullptr,nullptr) && display.fSubmitted==2 && surfaces[0].refs==2);
 assert(!client.externalMethod(6,&a,nullptr,nullptr,nullptr) && !display.waits);
 a.structureInputSize=sizeof(record)-1;unsigned submitted=display.fSubmitted;
 assert(client.externalMethod(5,&a,nullptr,nullptr,nullptr)==kIOReturnBadArgument && display.fSubmitted==submitted);
 for(auto &s:display.fPending)OSSafeReleaseNULL(s);
 for(auto &s:surfaces)assert(s.refs==1);
 assert(!display.lock.held);
 puts("PASS: actual 0046 optional selectors, scalar/struct reply lengths, out-of-line zero bounds, default layers, asynchronous wait and token-independent retained SwapEnd");
}
'''
with tempfile.TemporaryDirectory(prefix='graphics-compat-',dir=root/'artifacts') as directory:
    p=Path(directory);(p/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++17','-fsanitize=address,undefined','-Wall','-Wextra','-Werror','-I'+str(root/'xnu/iokit/Kernel/arm'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
