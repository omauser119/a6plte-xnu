#!/usr/bin/env python3
"""Exercise actual native surface geometry and its iOS 16 wire reply."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1];source=(root/'xnu/iokit/Kernel/arm/A6Surface.cpp').read_text()
def body(signature):
 start=source.index(signature);opening=source.index('{',start);end=opening+1;depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]+'\n'
fixture=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include <cstdio>
#define A6PLTE_SURFACE_MAX_DIM 16384
#define A6PLTE_SURFACE_MAX_ALLOC (256u<<20)
#define A6PLTE_SURFACE_ROW_ALIGN 64
#define A6PLTE_SURFACE_MAX_PLANES 20
#define A6PLTE_SURFACE_RESULT_SIZE 0xa68
#define A6PLTE_SURFACE_TIMESTAMPS 0x800
#define round_page(x) (((uint64_t)(x)+4095)&~UINT64_C(4095))
#define bzero(p,n) memset(p,0,n)
using IOReturn=int;
enum { kIOReturnSuccess=0,kIOReturnBadArgument=1,kIOReturnNoMemory=2 };
struct OSObject {virtual ~OSObject()=default;};
struct OSNumber:OSObject {uint64_t v;OSNumber(uint64_t n):v(n){} uint64_t unsigned64BitValue(){return v;}uint32_t unsigned32BitValue(){return v;}};
struct OSDictionary:OSObject {std::map<std::string,OSObject*> values;OSObject *getObject(const char*k){auto i=values.find(k);return i==values.end()?nullptr:i->second;}};
struct OSArray:OSObject {std::vector<OSObject*> objects;unsigned getCount(){return objects.size();}OSObject *getObject(unsigned n){return objects.at(n);}};
#define OSDynamicCast(T,o) dynamic_cast<T *>(o)
struct a6_surface_plane {uint32_t width=0,height=0,bytesPerRow=0,offset=0,size=0;uint16_t bytesPerElement=0;uint8_t elementWidth=0,elementHeight=0;};
struct A6Surface {uint32_t id=0,width=0,height=0,bytesPerRow=0,offset=0,pixelFormat=0,allocSize=0,cacheMode=0,planeCount=0,parentID=0;uint16_t bytesPerElement=0;uint8_t elementWidth=0,elementHeight=0;a6_surface_plane planes[20]={};};
struct Mapping {uint64_t value;uint64_t getAddress(){return value;}};
struct A6SurfaceRef {Mapping *data,*state;};
'''
for f in ('static uint32_t\na6_dict_u32(', 'static uint32_t\na6_div_up(', 'static uint32_t\na6_row_bytes(', 'static IOReturn\na6_surface_layout(', 'static void\nput32(', 'static void\nput64(', 'static void\na6_surface_fill_result('):fixture+=body(f)
fixture+=r'''
static uint32_t u32(const uint8_t*p,unsigned n){uint32_t v;memcpy(&v,p+n,4);return v;}
static uint64_t u64(const uint8_t*p,unsigned n){uint64_t v;memcpy(&v,p+n,8);return v;}
int main(){
 OSDictionary d;OSNumber width(1080),height(2220),format(0x42475241),bad(0x100000438ULL),bpe(0x10004),element(257),small(4),badrow(1),max(UINT32_MAX);
 d.values={{"IOSurfaceWidth",&width},{"IOSurfaceHeight",&height},{"IOSurfacePixelFormat",&format}};
 A6Surface s;assert(!a6_surface_layout(&s,&d));assert(s.width==1080 && s.height==2220 && s.bytesPerRow==4352 && s.allocSize==9662464);
 d.values["IOSurfaceWidth"]=&bad;assert(a6_surface_layout(&s,&d)==kIOReturnBadArgument);d.values["IOSurfaceWidth"]=&width;
 d.values["IOSurfaceBytesPerElement"]=&bpe;assert(a6_surface_layout(&s,&d)==kIOReturnBadArgument);d.values.erase("IOSurfaceBytesPerElement");
 d.values["IOSurfaceElementWidth"]=&element;assert(a6_surface_layout(&s,&d)==kIOReturnBadArgument);d.values.erase("IOSurfaceElementWidth");
 d.values["IOSurfaceBytesPerRow"]=&badrow;assert(a6_surface_layout(&s,&d)==kIOReturnBadArgument);d.values.erase("IOSurfaceBytesPerRow");
 d.values["IOSurfaceAllocSize"]=&small;assert(!a6_surface_layout(&s,&d) && s.allocSize==9662464);d.values.erase("IOSurfaceAllocSize"); // 0046 promotes an undersized allocation hint.
 OSArray planes;OSDictionary plane;plane.values={{"IOSurfacePlaneWidth",&width},{"IOSurfacePlaneHeight",&height},{"IOSurfacePlaneBytesPerElement",&small}};
 planes.objects={&plane};d.values["IOSurfacePlaneInfo"]=&planes;assert(!a6_surface_layout(&s,&d));
 plane.values["IOSurfacePlaneSize"]=&small;assert(a6_surface_layout(&s,&d)==kIOReturnBadArgument);plane.values.erase("IOSurfacePlaneSize");
 plane.values["IOSurfacePlaneOffset"]=&max;assert(a6_surface_layout(&s,&d)!=kIOReturnSuccess);plane.values.erase("IOSurfacePlaneOffset");
 planes.objects.resize(21,&plane);assert(a6_surface_layout(&s,&d)==kIOReturnBadArgument);
 d.values["IOSurfacePlaneInfo"]=&width;assert(!a6_surface_layout(&s,&d) && !s.planeCount);d.values.erase("IOSurfacePlaneInfo"); // 0046 ignores a non-array optional key.
 OSDictionary opaque;OSNumber page(4096);opaque.values["IOSurfaceAllocSize"]=&page;assert(!a6_surface_layout(&s,&opaque) && s.allocSize==4096);
 OSNumber large(128u<<20),over((256u<<20)+4096);opaque.values["IOSurfaceAllocSize"]=&large;assert(!a6_surface_layout(&s,&opaque) && s.allocSize==(128u<<20));
 opaque.values["IOSurfaceAllocSize"]=&over;assert(a6_surface_layout(&s,&opaque)==kIOReturnNoMemory);
 s=A6Surface{};assert(!a6_surface_layout(&s,&d));s.id=42;s.planeCount=20;
 for(unsigned i=0;i<20;++i)s.planes[i]={64,32,256,8192*i,8192,4,1,1};
 Mapping pixels{0x12340000},state{0x56780000};A6SurfaceRef ref{&pixels,&state};uint8_t out[0xa68+32];memset(out,0xa5,sizeof(out));
 a6_surface_fill_result(&s,&ref,out+16);
 assert(u64(out+16,0)==pixels.value && u64(out+16,8)==state.value && u64(out+16,16)==state.value+0x800);
 assert(u32(out+16,0x18)==42 && u32(out+16,0x20)==1080 && u32(out+16,0x24)==2220 && u32(out+16,0x30)==0x42475241);
 assert(u32(out+16,0x38)==20 && u32(out+16,0x68+19*0x80+0x0c)==19*8192);
 for(unsigned i=0;i<16;++i)assert(out[i]==0xa5 && out[16+0xa68+i]==0xa5);
 puts("PASS: actual iOS surface geometry and 0xa68 wire reply; narrowing/plane/range failures and all 20 plane result slots guarded");
}
'''
with tempfile.TemporaryDirectory(prefix='surface-abi-',dir=root/'artifacts') as directory:
 p=Path(directory);(p/'test.cpp').write_text(fixture)
 subprocess.run(['clang++','-std=c++17','-fsanitize=address,undefined','-Wall','-Wextra','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
