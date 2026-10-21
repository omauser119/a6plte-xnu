#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Run the native default-surface presenter/timer against the real pixel converter."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'xnu/iokit/Kernel/arm/A6Framebuffer.cpp').read_text()

def body(signature):
    start = source.index(signature)
    opening = source.index('{', start)
    end, depth = opening + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'

fixture = r'''
#include "A6Scanout.h"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <initializer_list>
#define A6_SWAP_BYTES 0x46c
#define A6_LAYERS 4
#define A6_VSYNC_US 16667
struct OSObject {};
#define OSDynamicCast(T,p) static_cast<T *>(p)
#define OSSafeReleaseNULL(p) do {if(p){(p)->release();(p)=nullptr;}} while(0)
struct IOLock { bool held=false; };
static void IOLockLock(IOLock *l){assert(!l->held);l->held=true;}
static void IOLockUnlock(IOLock *l){assert(l->held);l->held=false;}
static void IOLockWakeup(IOLock *l,void *,bool){assert(l->held);}
static unsigned handed=0;static bool stopped=false;
static void a6_xnu_graphics_presented(){assert(!stopped);++handed;}
static int a6_xnu_graphics_stopped(){return stopped;}
static uint64_t mach_absolute_time(){return 123456;}
struct A6Surface {
 uint8_t pixels[24]={};unsigned refs=1;
 uint32_t allocSize=24,width=2,height=2,bytesPerRow=12;
 uintptr_t kernelAddress(){return (uintptr_t)pixels;}
 void retain(){++refs;}void release(){assert(refs>1);--refs;}
};
struct IOMobileFramebufferUserClient {void notify(const uint64_t *){assert(false);}};
struct Clients {unsigned getCount(){return 0;}void *getObject(unsigned){assert(false);return nullptr;}};
struct IOTimerEventSource {unsigned scheduled=0;void setTimeoutUS(unsigned us){assert(us==16667);++scheduled;}};
class AppleCLCD:public OSObject {
public:
 IOLock mainLock,presentLock,*fLock=&mainLock,*fPresentLock=&presentLock;
 A6Surface storage,*fSurface=&storage,*fPending[4]={};
 struct a6_scanout fScanout={};Clients clients,*fClients=&clients;
 bool fPowerOn=true,fDefaultActive=false,fDirectPresented=false,fRunning=true,fDirty=false,fEligible=false;
 uint32_t fSubmitted=0,fCompleted=0,fFlushTicks=6;uint64_t fTicks=0;
 uint8_t fRecord[A6_SWAP_BYTES]={};unsigned layerPresents=0;
 uint32_t width(){return 2;}uint32_t height(){return 2;}
 void present(const uint8_t *,A6Surface **,bool){++layerPresents;}
 void enableDefault();void presentDefault();static void tick(OSObject *,IOTimerEventSource *);
};
'''
for name in ('void AppleCLCD::enableDefault(', 'void AppleCLCD::presentDefault(', 'void AppleCLCD::tick('):
    fixture += body(name)
fixture += r'''
static void unchanged(const uint8_t *p,unsigned n){for(unsigned i=0;i<n;++i)assert(p[i]==0xa5);}
int main(){
 AppleCLCD fb;IOTimerEventSource timer;uint8_t panel[34];memset(panel,0xa5,sizeof(panel));
 fb.fScanout={panel+8,18,2,2,9,1,0};
 // No client, then an untouched default surface: neither may erase boot logs.
 fb.presentDefault();unchanged(panel,sizeof(panel));assert(!handed);
 fb.enableDefault();
 for(unsigned row=0;row<2;++row){
  fb.storage.pixels[row*12+3]=fb.storage.pixels[row*12+7]=255;
  memset(fb.storage.pixels+row*12+8,255,4); // Alpha/padding are not visible color.
 }
 for(unsigned i=0;i<6;++i)AppleCLCD::tick(&fb,&timer);
 unchanged(panel,sizeof(panel));assert(!handed && timer.scheduled==6);
 // A direct BGRA write reaches RGB888 without SwapBegin/SwapEnd.
 fb.storage.pixels[0]=0x33;fb.storage.pixels[1]=0x22;fb.storage.pixels[2]=0x11;
 for(unsigned i=0;i<5;++i)AppleCLCD::tick(&fb,&timer);
 unchanged(panel,sizeof(panel));assert(!handed);
 AppleCLCD::tick(&fb,&timer);
 assert(fb.fDirectPresented && handed==1 && !fb.fSubmitted);
 assert(panel[8]==0x11 && panel[9]==0x22 && panel[10]==0x33);
 for(unsigned row=0;row<2;++row)unchanged(panel+8+row*9+6,3);
 unchanged(panel,8);unchanged(panel+26,8);
 // Subsequent direct writes and black frames continue to scan out.
 fb.storage.pixels[0]=fb.storage.pixels[1]=fb.storage.pixels[2]=0;
 fb.presentDefault();assert(panel[8]==0 && panel[9]==0 && panel[10]==0 && handed==2);
 // A queued layer swap takes over; direct refresh must not overwrite it.
 fb.fSubmitted=17;fb.storage.pixels[0]=255;fb.fDirty=true;fb.fPending[0]=&fb.storage;
 for(unsigned i=0;i<6;++i)AppleCLCD::tick(&fb,&timer);
 assert(fb.layerPresents==1 && fb.fCompleted==17 && fb.storage.refs==1 && !fb.fDirty && handed==2);
 fb.presentDefault();assert(panel[8]==0 && panel[10]==0 && handed==2);
 fb.fSubmitted=0;fb.fPowerOn=false;fb.presentDefault();assert(handed==2);
 fb.fPowerOn=true;stopped=true;unsigned scheduled=timer.scheduled;
 AppleCLCD::tick(&fb,&timer);fb.presentDefault();assert(handed==2 && timer.scheduled==scheduled);
 stopped=false;fb.fDefaultActive=false;fb.presentDefault();assert(handed==2);
 // Invalid backing geometry fails before any store or console takeover.
 fb.fDefaultActive=true;fb.storage.bytesPerRow=UINT32_MAX;fb.presentDefault();assert(handed==2);
 assert(!fb.mainLock.held && !fb.presentLock.held);
 for(unsigned format: {1u,2u,A6_BGRA,A6_RGBA,A6_ARGB}){
  uint8_t p[16]={};unsigned b=format==1?3:4;
  a6_scanout s={p,sizeof(p),1,1,8,format,0};
  memset(p+b,255,sizeof(p)-b);
  if(b==4)p[format==A6_ARGB?0:3]=255;
  assert(!a6_scanout_nonblack(&s));p[format==A6_ARGB?1:0]=1;
  assert(a6_scanout_nonblack(&s));s.bytes=b-1;assert(!a6_scanout_nonblack(&s));
 }
 puts("PASS: actual default-surface scanout without SwapEnd, 10 Hz timer, RGB conversion, console handoff, black frames, layer takeover, panic/power and buffer guards");
}
'''
with tempfile.TemporaryDirectory(prefix='fb-default-', dir=root/'artifacts') as directory:
    p = Path(directory)
    (p/'test.cpp').write_text(fixture)
    flags = ['-fsanitize=address,undefined', '-Wall', '-Wextra', '-Werror']
    subprocess.run(['clang', '-std=c17', *flags, '-c', str(root/'xnu/iokit/Kernel/arm/A6Scanout.c'), '-o', str(p/'scanout.o')], check=True)
    subprocess.run(['clang++', '-std=c++17', *flags, '-I'+str(root/'xnu/iokit/Kernel/arm'), str(p/'test.cpp'), str(p/'scanout.o'), '-o', str(p/'test')], check=True)
    subprocess.run([str(p/'test')], check=True)
