#!/usr/bin/env python3
"""Check the bounded no-passcode AKS state's DER wire representation."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
source=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "A6KeyStoreState.h"
int main(void) {
 unsigned char guarded[256];memset(guarded,0xa5,sizeof(guarded));
 unsigned n=a6_aks_extended_state(guarded+16,128);assert(n && n<=128);
 for(unsigned cap=0;cap<n;++cap) {
  unsigned char small[256];memset(small,0xa5,sizeof(small));
  assert(a6_aks_extended_state(small+16,cap)==0);
  for(unsigned i=0;i<sizeof(small);++i) assert(small[i]==0xa5);
 }
 assert(!a6_aks_extended_state(NULL,128));
 for(unsigned i=0;i<16;++i) assert(guarded[i]==0xa5);
 for(unsigned i=16+n;i<sizeof(guarded);++i) assert(guarded[i]==0xa5);
 fwrite(guarded+16,1,n,stdout);return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='aks-state-',dir=root/'artifacts') as tmp:
 tmp=Path(tmp);(tmp/'test.c').write_text(source)
 subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                 '-I'+str(root/'xnu/iokit/Kernel/arm'),str(tmp/'test.c'),'-o',str(tmp/'test')],check=True)
 data=subprocess.check_output([str(tmp/'test')])
assert data[0]==0x31 and data[1]==len(data)-2
fields={};encoded=[];pos=2
while pos<len(data):
 start=pos;assert data[pos]==0x30;end=pos+2+data[pos+1];pos+=2
 assert data[pos]==0x0c;n=data[pos+1];pos+=2
 key=data[pos:pos+n].decode();pos+=n
 assert data[pos:pos+2]==b'\x02\x01';pos+=2
 assert key not in fields;fields[key]=data[pos];pos+=1
 assert pos==end;encoded.append(data[start:end])
assert fields==dict(ss=4,sls=0,sb=0,sfa=0,sgs=0,sas=0,sgpe=0,srcd=0)
assert encoded==sorted(encoded), 'DER SET elements must be in canonical order'
print('AKS state: canonical DER, unlocked stub values and all buffer guards passed')
