#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Run copied 0046/0056 layer copying and the A6 RGB888 adapter with actual pixels."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
source=(root/'xnu/iokit/Kernel/arm/A6Framebuffer.cpp').read_text()
def body(signature):
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
#include <cstdlib>
#define A6PLTE_FB_SWAP_REC_SIZE 0x46c
#define A6PLTE_FB_LAYERS 4
#define A6PLTE_FB_VSYNC_US 16667
#define A6PLTE_FB_NOTIFY_VSYNC 5
#define OSSafeReleaseNULL(p) do{if(p){(p)->release();(p)=nullptr;}}while(0)
struct OSObject {};
struct IOLock {bool held=false;};
static void IOLockLock(IOLock *p){assert(!p->held);p->held=true;}
static void IOLockUnlock(IOLock *p){assert(p->held);p->held=false;}
static bool stopped=false,failAllocation=false;static unsigned handed=0;
static int a6_xnu_graphics_stopped(){return stopped;}
static void a6_xnu_graphics_presented(){assert(!stopped);++handed;}
static uint64_t mach_absolute_time(){return 0x123456789abcdef0ULL;}
static void *IOMallocData(unsigned n){return failAllocation?nullptr:malloc(n);}
static void IOFreeData(void *p,unsigned){free(p);}
struct Memory {uint64_t getLength(){return 24;}};
struct A6Surface {
 uint8_t storage[40];Memory backing,*memory=&backing;unsigned refs=1;
 uint32_t width=2,height=2,bytesPerRow=12,allocSize=24,offset=0,bytesPerElement=4,elementWidth=1,elementHeight=1;
 A6Surface(){memset(storage,0xa5,sizeof(storage));memset(storage+8,0,24);}
 uintptr_t kernelAddress(){return (uintptr_t)(storage+8);}
 void retain(){++refs;}void release(){assert(refs>1);--refs;}
};
static A6Surface front,layer;
static A6Surface *a6_surface_copy(uint32_t id){A6Surface *p=id==1?&front:id==2?&layer:nullptr;if(p)p->retain();return p;}
struct IOMobileFramebufferUserClient {
 unsigned calls=0;uint64_t values[6]={};
 void notify(unsigned type,const uint64_t *v,unsigned n){assert(type==5 && n==6);++calls;memcpy(values,v,sizeof(values));}
};
struct Clients {unsigned n=0;void *client=nullptr;unsigned getCount(){return n;}void *getObject(unsigned i){assert(i<n);return client;}};
struct IOTimerEventSource {unsigned scheduled=0;void setTimeoutUS(unsigned us){assert(us==16667);++scheduled;}};
class AppleCLCD:public OSObject {
public:
 IOLock lock,*fLock=&lock;Clients clients,*fClients=&clients;
 A6Surface *fSurface=&front;uintptr_t fPixels=front.kernelAddress();
 uint32_t fWidth=2,fHeight=2,fRowBytes=12,fFlushTicks=6;
 uint64_t fVsyncCount=0;bool fDirty=false,fGUIClient=false,fConsolePaused=false;
 uint8_t fPending[A6PLTE_FB_SWAP_REC_SIZE]={};a6_scanout fPanel={};
 void swap(const uint8_t *);void present(const uint8_t *);void scanout();
 static void vsyncFired(OSObject *,IOTimerEventSource *);
};
'''
fixture+='\n#include "A6FramebufferDiagnostics.h"\n'+source[source.index('static uint64_t a6_fb_counters'): source.index('enum {\n\tkA6FBGetLayerDefaultSurface')]
for name in ('static uint32_t\nget32(', 'void\nAppleCLCD::swap(', 'void\nAppleCLCD::present(', 'void\nAppleCLCD::scanout(', 'void\nAppleCLCD::vsyncFired('):fixture+=body(name)
fixture+=r'''
static void put(uint8_t *p,unsigned n,uint32_t v){memcpy(p+n,&v,4);}
static void unchanged(const uint8_t *p,unsigned n){for(unsigned i=0;i<n;++i)assert(p[i]==0xa5);}
int main(){
 AppleCLCD fb;IOTimerEventSource timer;uint8_t panel[34];memset(panel,0xa5,sizeof(panel));
 fb.fPanel={panel+8,18,2,2,9,1,0};
 for(unsigned i=0;i<6;++i)AppleCLCD::vsyncFired(&fb,&timer);
 unchanged(panel,sizeof(panel));assert(!handed && timer.scheduled==6);
 a6_fb_snapshot status={};a6_framebuffer_snapshot(&status);
 assert(status.value[A6_FB_VSYNC]==6 && !status.value[A6_FB_PRESENTED] && !status.value[A6_FB_SWAP]);
 fb.fGUIClient=true;
 for(unsigned row=0;row<2;++row){front.storage[8+row*12+3]=255;front.storage[8+row*12+7]=255;memset(front.storage+8+row*12+8,255,4);}
 for(unsigned i=0;i<6;++i)AppleCLCD::vsyncFired(&fb,&timer);
 unchanged(panel,sizeof(panel));assert(!handed); // alpha and stride padding are not a frame
 front.storage[8]=0x33;front.storage[9]=0x22;front.storage[10]=0x11;
 for(unsigned i=0;i<5;++i)AppleCLCD::vsyncFired(&fb,&timer);
 unchanged(panel,sizeof(panel));
 AppleCLCD::vsyncFired(&fb,&timer);
 assert(fb.fConsolePaused && handed==1 && panel[8]==0x11 && panel[9]==0x22 && panel[10]==0x33);
 a6_framebuffer_snapshot(&status);
 assert(status.value[A6_FB_PRESENTED]==handed && status.value[A6_FB_NONBLACK]==1);
 // Exercise copied upstream swap/present with a bounded real layer buffer.
 uint8_t rec[0x46c]={};put(rec,0x104,1);put(rec,0x54,2);put(rec,0xc4+8,2);put(rec,0xc4+12,2);
 layer.storage[8]=0x99;layer.storage[9]=0x88;layer.storage[10]=0x77;
 fb.swap(rec);assert(fb.fDirty && panel[8]==0x11);
 failAllocation=true;
 for(unsigned i=0;i<6;++i)AppleCLCD::vsyncFired(&fb,&timer);
 assert(fb.fDirty && panel[8]==0x11); // queue survives failed timer-record allocation
 failAllocation=false;
 for(unsigned i=0;i<6;++i)AppleCLCD::vsyncFired(&fb,&timer);
 assert(!fb.fDirty && panel[8]==0x77 && panel[9]==0x88 && panel[10]==0x99 && layer.refs==1);
 a6_framebuffer_snapshot(&status);
 assert(status.value[A6_FB_SWAP]==1 && status.value[A6_FB_LAYER_COPY]==1 && status.value[A6_FB_PRESENTED]==handed);
 // Empty IDs, unknown IDs and clipped rectangles cannot read or write beyond storage.
 put(rec,0x54,999);fb.present(rec);put(rec,0x54,0);fb.present(rec);
 put(rec,0x54,2);put(rec,0xc4,INT32_MAX);fb.present(rec);
 put(rec,0xc4,0);put(rec,0x64,INT32_MAX);fb.present(rec);
 for(unsigned row=0;row<2;++row)unchanged(panel+8+row*9+6,3);
 unchanged(panel,8);unchanged(panel+26,8);unchanged(front.storage,8);unchanged(front.storage+32,8);
 unchanged(layer.storage,8);unchanged(layer.storage+32,8);
 // Direct default-surface writes stay visible even after previous layer swaps.
 memset(front.storage+8,0,24);fb.scanout();assert(!panel[8] && !panel[9] && !panel[10]);
 // Native vsync ABI: timestamp, presented timestamp, counter, each split low/high.
 IOMobileFramebufferUserClient client;fb.clients.n=1;fb.clients.client=&client;fb.fVsyncCount=0xffffffffULL;
 AppleCLCD::vsyncFired(&fb,&timer);
 uint64_t expected[6]={0x9abcdef0,0x12345678,0x9abcdef0,0x12345678,0,1};
 assert(client.calls==1 && !memcmp(client.values,expected,sizeof(expected)));
 a6_framebuffer_snapshot(&status);a6_fb_snapshot beforeStats=status;
 stopped=true;unsigned before=timer.scheduled;front.storage[8]=255;
 fb.scanout();fb.present(rec);AppleCLCD::vsyncFired(&fb,&timer);
 assert(timer.scheduled==before && !panel[10] && !fb.lock.held && layer.refs==1);
 a6_framebuffer_snapshot(&status);assert(!memcmp(&status,&beforeStats,sizeof(status)));
 puts("PASS: copied 0046 layer copy + 0056 queue, real vsync payload, A6 RGB888 conversion, direct default refresh, console handoff, allocation failure, clipping/guards and panic stop");
}
'''
with tempfile.TemporaryDirectory(prefix='copied-fb-',dir=root/'artifacts') as directory:
 p=Path(directory);(p/'test.cpp').write_text(fixture);flags=['-fsanitize=address,undefined','-Wall','-Wextra','-Werror']
 subprocess.run(['clang','-std=c17',*flags,'-c',str(root/'xnu/iokit/Kernel/arm/A6Scanout.c'),'-o',str(p/'scanout.o')],check=True)
 subprocess.run(['clang++','-std=c++17',*flags,'-I'+str(root/'xnu/iokit/Kernel/arm'),str(p/'test.cpp'),str(p/'scanout.o'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
