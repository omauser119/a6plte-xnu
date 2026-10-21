#!/usr/bin/env python3
"""Copy pinned upstream 0046, apply upstream 0068, then the explicit A6PLTE delta."""
from pathlib import Path
import argparse
import hashlib
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
VENDOR=ROOT/'vendor/ios-sweet'
FILES=('SweetSurface.h','SweetSurface.cpp','SweetFramebuffer.cpp')
HASHES={
    '0046-sweet-iosurface-iomfb.patch':'0f23986cf9861ad52a6a0986328fa83c9f0ec222d53dee2bce5921d79c90e5be',
    '0068-sweet-surface-lookup-cached.patch':'97a5b8a9414761cb9b9d2d666be46ffeb3629faa03185930dbf96a72e0bbf804',
}

def rename(text):
    return text.replace('SWEET','A6PLTE').replace('Sweet','A6').replace('sweet','a6')

def vendor(name):
    data=(VENDOR/name).read_bytes()
    if hashlib.sha256(data).hexdigest()!=HASHES[name]:
        raise SystemExit('Upstream patch checksum mismatch: '+name)
    return data.decode()

def install(destination):
    original=vendor('0046-sweet-iosurface-iomfb.patch')
    for name in FILES:
        section=original.split('+++ b/iokit/Kernel/arm/'+name+'\n',1)[1].split('--- ',1)[0]
        data=''.join(line[1:] for line in section.splitlines(keepends=True) if line.startswith('+'))
        target=destination/'iokit/Kernel/arm'/rename(name)
        if target.exists():
            raise SystemExit('Refusing to overwrite existing source: '+str(target))
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(rename(data))
    corrections=rename(vendor('0068-sweet-surface-lookup-cached.patch'))
    for patch in (corrections,(ROOT/'patches/0046-a6plte-adaptation.patch').read_text()):
        subprocess.run(['git','apply','--check','-'],cwd=destination,input=patch,text=True,check=True)
        subprocess.run(['git','apply','-'],cwd=destination,input=patch,text=True,check=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xnu',type=Path)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args();destination=args.xnu.resolve()
    if args.verify:
        with tempfile.TemporaryDirectory(prefix='verify-0046-') as temporary:
            copy=Path(temporary);install(copy)
            for name in FILES:
                relative=Path('iokit/Kernel/arm')/rename(name)
                if (copy/relative).read_bytes()!=(destination/relative).read_bytes():
                    raise SystemExit('Source differs from copied upstream + explicit adaptation: '+str(relative))
        print('PASS: native graphics sources exactly equal pinned 0046 + upstream 0068 + the A6PLTE adaptation patch')
    else:
        install(destination)

if __name__=='__main__':main()
