#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Execute native graphics replies, mode selection and notification ownership."""
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
surface=(root/'xnu/iokit/Kernel/arm/A6Surface.cpp').read_text()
fb=(root/'xnu/iokit/Kernel/arm/A6Framebuffer.cpp').read_text()
startup=fb[fb.index('bool\nAppleCLCD::start('):fb.index('void\nAppleCLCD::vsyncFired(')]
assert startup.index('if (!publishModes()) return false;') < startup.index('registerService();')
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
#include <map>
#include <string>
#include <initializer_list>
#define __unused __attribute__((unused))
#define bzero(p,n) memset(p,0,n)
#define A6_SWAP_BYTES 0x46c
#define A6_LAYERS 4
#define A6_NOTIFY_TYPES 8
#define A6PLTE_SURFACE_ROW_ALIGN 64
#define OSSafeReleaseNULL(p) do {if(p){(p)->release();(p)=nullptr;}} while(0)
#define OSDynamicCast(T,p) dynamic_cast<T *>(p)
using IOReturn=int;using mach_port_name_t=uint32_t;using mach_port_t=uint32_t;
using UInt32=uint32_t;using io_user_reference_t=uint64_t;using mach_vm_address_t=uint64_t;
using OSAsyncReference64=uint64_t[8];
#define MACH_PORT_NULL 0
#define kIOUserNotifyOptionCanDrop 1
enum {kIOReturnSuccess=0,kIOReturnBadArgument=1,kIOReturnNoSpace=2,kIOReturnVMError=3,kIOReturnNotOpen=4,kIOReturnNotReady=5,kIOReturnNotFound=6};
enum {kA6SurfaceCreate=0,kA6SurfaceLookup=4,kA6SurfaceLimits=13,kA6SurfaceLookupFromPort=34,kA6SurfaceCreatePort=35};
enum {kA6FBGetLayerDefaultSurface=3,kA6FBSwapBegin=4,kA6FBSwapEnd=5,kA6FBSwapWait=6,kA6FBGetID=7,kA6FBGetDisplaySize=8,kA6FBIsMainDisplay=18,kA6FBGetDotPitch=28,kA6FBNotifications=72,kA6FBGetCurrentAbsoluteTime=77,kA6FBGetBlock=79};
#define A6PLTE_FB_SWAP_REC_SIZE 0x46c
#define A6PLTE_FB_DOT_PITCH 411
#define A6PLTE_FB_NOTIFY_TYPES 8
#define A6PLTE_FB_TIMING_ID 1
#define A6PLTE_FB_COLOR_ID 1
#define A6PLTE_FB_REFRESH_HZ 60
static uint64_t mach_absolute_time(){return 0x123456789abcdef0ULL;}
static unsigned objects=0,operationCount=0,failAt=0;
static bool operation(){return ++operationCount!=failAt;}
struct OSObject {
 unsigned refs=1;OSObject(){++objects;}virtual ~OSObject(){--objects;}
 virtual void retain(){++refs;}virtual void release(){assert(refs);if(!--refs)delete this;}
};
struct OSNumber:OSObject {
 uint32_t value=0;
 static OSNumber *withNumber(uint64_t n,unsigned bits){assert(bits==32);if(!operation())return nullptr;auto p=new OSNumber;p->value=n;return p;}
};
struct OSBoolean:OSObject {};
static OSBoolean falseValue;static OSBoolean *kOSBooleanFalse=&falseValue;
struct OSDictionary:OSObject {
 std::map<std::string,OSObject *> data;
 static OSDictionary *withCapacity(unsigned){return operation()?new OSDictionary:nullptr;}
 bool setObject(const char *key,OSObject *p){assert(p);if(!operation())return false;p->retain();auto old=data.find(key);if(old!=data.end())old->second->release();data[key]=p;return true;}
 OSObject *getObject(const char *key){auto i=data.find(key);return i==data.end()?nullptr:i->second;}
 void removeObject(const char *key){auto i=data.find(key);if(i!=data.end()){i->second->release();data.erase(i);}}
 ~OSDictionary(){for(auto &item:data)item.second->release();}
};
struct OSArray:OSObject {
 std::vector<OSObject *> data;
 static OSArray *withCapacity(unsigned){return operation()?new OSArray:nullptr;}
 bool setObject(OSObject *p){assert(p);if(!operation())return false;p->retain();data.push_back(p);return true;}
 ~OSArray(){for(auto p:data)p->release();}
};
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
 void retain()override{++refs;}void release()override{assert(refs>1);--refs;}
};
static A6Surface surfaces[4];
static A6Surface *a6_surface_copy(uint32_t id){if(id<1 || id>4)return nullptr;auto s=&surfaces[id-1];s->retain();return s;}
static bool a6_surface_get(A6Surface *){return true;}
struct IOUserClient {
 static inline std::vector<mach_port_t> released;
 static inline uint64_t sent[8]={};static inline uint64_t payload[6]={};static inline unsigned sends=0;
 bool terminated=false;void terminate(){terminated=true;}
 static void releaseNotificationPort(mach_port_t p){assert(p);released.push_back(p);}
 static void setAsyncReference64(uint64_t *r,mach_port_t p,uint64_t fn,uint64_t cookie,void *){r[0]=p;r[1]=fn;r[2]=cookie;}
 static void sendAsyncResult64WithOptions(uint64_t *r,IOReturn ret,io_user_reference_t *v,uint32_t n,unsigned flags){assert(!ret && n==6 && flags==1);memcpy(sent,r,sizeof(sent));memcpy(payload,v,sizeof(payload));++sends;}
 static IOReturn copyPortNameForObjectInTask(void *,OSObject *,mach_port_name_t *p){*p=42;return 0;}
 static IOReturn copyObjectForPortNameInTask(void *,mach_port_name_t,OSObject **p){*p=nullptr;return kIOReturnNotFound;}
};
static void a6_surf_log_once(const char *,uint32_t){}
static mach_port_name_t a6_surface_port_in_task(A6Surface *,void *){return 42;}
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
 OSDictionary properties;
 bool setProperty(const char *k,OSObject *p){return properties.setObject(k,p);}
 void removeProperty(const char *k){properties.removeObject(k);}
 bool publishModes();
 IOLock lock,*fLock=&lock;A6Surface *fSurface=&surfaces[0];
 uint8_t fRecord[A6PLTE_FB_SWAP_REC_SIZE]={};uint32_t fWidth=1080,fHeight=2220,fSwapID=0;
 unsigned swaps=0;
 unsigned removed=0;void removeClient(void *){++removed;}
 void swap(const uint8_t *p){++swaps;memcpy(fRecord,p,sizeof(fRecord));}
};
class IOMobileFramebufferUserClient:public IOUserClient {
public:
 AppleCLCD *fFB=nullptr;void *fTask=nullptr;
 mach_port_t fPorts[A6PLTE_FB_NOTIFY_TYPES]={};uint32_t fPortMask=0;
 uint64_t fFunc[A6PLTE_FB_NOTIFY_TYPES]={},fRefcon[A6PLTE_FB_NOTIFY_TYPES]={};
 IOReturn externalMethod(uint32_t,IOExternalMethodArguments *,IOExternalMethodDispatch *,OSObject *,void *);
 IOReturn clientClose();IOReturn registerNotificationPort(mach_port_t,UInt32,io_user_reference_t);
 void notify(uint32_t,const uint64_t *,uint32_t);
};
'''
for signature in ('static void\nput32(', 'static IOReturn\na6_struct_out(', 'IOReturn\nIOSurfaceRootUserClient::externalMethod('):
    fixture+=body(surface,signature)
for signature in ('static bool\na6_fb_number(', 'bool\nAppleCLCD::publishModes(',
                  'IOReturn\nIOMobileFramebufferUserClient::externalMethod(',
                  'IOReturn\nIOMobileFramebufferUserClient::registerNotificationPort(',
                  'IOReturn\nIOMobileFramebufferUserClient::clientClose(',
                  'void\nIOMobileFramebufferUserClient::notify('):
    fixture+=body(fb,signature)
fixture+=r'''
static void zeros(const uint8_t *p,unsigned n){for(unsigned i=0;i<n;++i)assert(!p[i]);}
static void guarded(const uint8_t *p,unsigned n){for(unsigned i=0;i<n;++i)assert(p[i]==0xa5);}
int main(){
 IOSurfaceRootUserClient surf;AppleCLCD display;IOMobileFramebufferUserClient client;client.fFB=&display;
 for(unsigned sel=0;sel<100;++sel){
  if(sel==0 || sel==4 || sel==13 || sel==34 || sel==35)continue;
  uint64_t out[4]={1,2,3,0xfeed};uint8_t bytes[48];memset(bytes,0xa5,sizeof(bytes));
  IOExternalMethodArguments a;a.scalarOutput=out;a.scalarOutputCount=3;a.structureOutput=bytes+8;a.structureOutputSize=32;
  assert(!surf.externalMethod(sel,&a,nullptr,nullptr,nullptr));
  assert(!out[0] && !out[1] && !out[2] && out[3]==0xfeed && a.scalarOutputCount==3 && a.structureOutputSize==32);
  zeros(bytes+8,32);guarded(bytes,8);guarded(bytes+40,8);
  if(sel==3 || sel==5)continue;
  memset(bytes,0xa5,sizeof(bytes));out[0]=out[1]=out[2]=1;
  assert(!client.externalMethod(sel,&a,nullptr,nullptr,nullptr));
  assert(a.scalarOutputCount==3 && a.structureOutputSize==32);zeros(bytes+8,32);
  guarded(bytes,8);guarded(bytes+40,8);
  if(sel==8)assert(out[0]==1080 && out[1]==2220);
  else {if(sel==18)assert(out[0]==1);else if(sel==28)assert(out[0]==411);else if(sel==77)assert(out[0]==mach_absolute_time());else assert(!out[0]);assert(!out[1]);}
  assert(!out[2] && out[3]==0xfeed);
 }
 Descriptor desc(32);IOExternalMethodArguments a;a.structureOutputDescriptor=&desc;a.structureOutputDescriptorSize=32;
 assert(!surf.externalMethod(13,&a,nullptr,nullptr,nullptr) && a.structureOutputDescriptorSize==24);
 assert(desc.data[0]==63 && desc.data[4]==63 && desc.data[22]==1);guarded(desc.data.data()+24,8);
 uint64_t out[3]={},input[4]={2,0,0,0};a={};a.scalarInput=input;a.scalarInputCount=1;a.scalarOutput=out;a.scalarOutputCount=3;
 assert(!client.externalMethod(3,&a,nullptr,nullptr,nullptr) && out[0]==42 && !out[1] && a.scalarOutputCount==3);
 a={};assert(!client.externalMethod(6,&a,nullptr,nullptr,nullptr));
 uint8_t record[A6PLTE_FB_SWAP_REC_SIZE]={};record[0x50]=99;
 a={};a.structureInput=record;a.structureInputSize=sizeof(record);
 assert(!client.externalMethod(5,&a,nullptr,nullptr,nullptr) && display.swaps==1 && display.fRecord[0x50]==99);
 for(unsigned i=0;i<2;++i){IOExternalMethodArguments b;b.scalarOutput=out;b.scalarOutputCount=1;assert(!client.externalMethod(4,&b,nullptr,nullptr,nullptr) && out[0]==i+1);}
 assert(!client.externalMethod(5,&a,nullptr,nullptr,nullptr) && display.swaps==2);
 a.structureInputSize=sizeof(record)-1;
 assert(client.externalMethod(5,&a,nullptr,nullptr,nullptr)==kIOReturnBadArgument && display.swaps==2);
 a={};a.scalarInput=input;a.scalarInputCount=3;input[0]=0x1234;input[1]=0x5678;input[2]=5;
 assert(!client.externalMethod(72,&a,nullptr,nullptr,nullptr) && client.fFunc[5]==0x1234 && client.fRefcon[5]==0x5678);
 input[2]=8;assert(!client.externalMethod(72,&a,nullptr,nullptr,nullptr) && client.fFunc[5]==0x1234);
 // The current-mode identifiers must select an actual timing and color entry.
 unsigned live=objects;operationCount=0;assert(display.publishModes());unsigned modeOperations=operationCount;
 uint8_t mode[40];memset(mode,0xa5,sizeof(mode));a={};input[0]=0x40;a.scalarInput=input;a.scalarInputCount=1;
 a.structureOutput=mode+8;a.structureOutputSize=24;
 assert(!client.externalMethod(79,&a,nullptr,nullptr,nullptr) && a.structureOutputSize==24);
 uint32_t ids[3];memcpy(ids,mode+8,sizeof(ids));assert(!ids[0] && ids[1] && ids[2]);
 guarded(mode,8);guarded(mode+32,8);zeros(mode+20,12);
 auto timings=dynamic_cast<OSArray *>(display.properties.getObject("TimingElements"));
 auto colors=dynamic_cast<OSArray *>(display.properties.getObject("ColorElements"));
 assert(timings && colors && timings->data.size()==1 && colors->data.size()==1);
 auto timing=dynamic_cast<OSDictionary *>(timings->data[0]);auto color=dynamic_cast<OSDictionary *>(colors->data[0]);
 assert(dynamic_cast<OSNumber *>(timing->getObject("ID"))->value==ids[2]);
 assert(dynamic_cast<OSNumber *>(color->getObject("ID"))->value==ids[1] && timing->getObject("ColorModes")==colors);
 auto horizontal=dynamic_cast<OSDictionary *>(timing->getObject("HorizontalAttributes"));
 auto vertical=dynamic_cast<OSDictionary *>(timing->getObject("VerticalAttributes"));
 assert(dynamic_cast<OSNumber *>(horizontal->getObject("Active"))->value==1080);
 assert(dynamic_cast<OSNumber *>(vertical->getObject("Active"))->value==2220);
 assert(dynamic_cast<OSNumber *>(vertical->getObject("SyncRate"))->value==60u<<16);
 assert(dynamic_cast<OSNumber *>(color->getObject("Depth"))->value==8);
 display.removeProperty("TimingElements");display.removeProperty("ColorElements");assert(objects==live);
 // Every allocation/insertion failure rolls publication back and balances references.
 for(unsigned failure=1;failure<=modeOperations;++failure){
  operationCount=0;failAt=failure;assert(!display.publishModes());
  assert(display.properties.data.empty() && objects==live);
 }
 failAt=0;
 for(unsigned len=0;len<24;++len){memset(mode,0xa5,sizeof(mode));a.structureOutputSize=len;
  assert(!client.externalMethod(79,&a,nullptr,nullptr,nullptr));guarded(mode,8);guarded(mode+8+len,32-len);
  if(len<12)zeros(mode+8,len);else {memcpy(ids,mode+8,12);assert(ids[1]==1 && ids[2]==1);}
 }
 input[0]=0x41;a.structureOutputSize=24;assert(!client.externalMethod(79,&a,nullptr,nullptr,nullptr));zeros(mode+8,24);
 // Per-type ports cannot overwrite each other; legacy type-zero remains usable.
 uint64_t values[6]={1,2,3,4,5,6};client.fFunc[5]=0x1234;client.fRefcon[5]=0x5678;
 assert(!client.registerNotificationPort(100,0,0));client.notify(5,values,6);
 assert(IOUserClient::sends==1 && IOUserClient::sent[0]==100 && IOUserClient::sent[1]==0x1234 && IOUserClient::sent[2]==0x5678);
 assert(!client.registerNotificationPort(200,5,0));assert(!client.registerNotificationPort(300,1,0));
 client.notify(5,values,6);assert(IOUserClient::sends==2 && IOUserClient::sent[0]==200);
 assert(!memcmp(IOUserClient::payload,values,sizeof(values)));
 assert(!client.registerNotificationPort(0,5,0));assert(IOUserClient::released==std::vector<mach_port_t>{200});
 client.notify(5,values,6);assert(IOUserClient::sends==2); // explicitly disabled, not type-zero fallback
 assert(client.registerNotificationPort(400,8,0)==kIOReturnBadArgument);
 assert(!client.clientClose() && client.terminated && display.removed==1);
 assert(IOUserClient::released==std::vector<mach_port_t>({200,100,300}));
 assert(!display.lock.held);
 puts("PASS: native graphics mode selection, real clock, allocation/publication rollback, typed/legacy notification ports and right ownership; copied 0046 replies and swap compatibility");
}
'''
with tempfile.TemporaryDirectory(prefix='graphics-compat-',dir=root/'artifacts') as directory:
    p=Path(directory);(p/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++17','-fsanitize=address,undefined','-Wall','-Wextra','-Werror','-I'+str(root/'xnu/iokit/Kernel/arm'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
