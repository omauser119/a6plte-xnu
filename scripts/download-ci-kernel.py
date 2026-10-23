#!/usr/bin/env python3
"""Fetch a verified successful CI kernel using parallel HTTP ranges (no device I/O)."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,hashlib,io,json,subprocess,sys,urllib.request,urllib.error,zipfile

ROOT=Path(__file__).resolve().parents[1]
REPO='omauser119/a6plte-xnu'

def api(path):
    return json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/'+path]))

def validate_build(run,jobs=None,allow_pending_dependencies=False):
    if run['head_branch']!='xnu-8796':
        raise SystemExit('Refusing a different-branch build')
    if run['status']=='completed' and run['conclusion']=='success':
        return 'all CI jobs successful'
    if allow_pending_dependencies and run['status']=='in_progress' and run['conclusion'] is None:
        by_name={job['name']:job for job in jobs or []}
        required=('xnu-apple-clang','package-xnu')
        if all(by_name.get(n,{}).get('status')=='completed' and
               by_name[n].get('conclusion')=='success' for n in required):
            host=by_name.get('framebuffer-and-lk2nd',{})
            active=[step['name'] for step in host.get('steps',[]) if step['status']=='in_progress']
            if (host.get('status')=='in_progress' and host.get('conclusion') is None and
                len(active)==1 and active[0].startswith('Run sudo apt-get update && sudo apt-get install ')):
                return 'native and package jobs successful; host CI dependency installation pending'
    raise SystemExit('Refusing a failed or unverified build')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id',type=int)
    parser.add_argument('--allow-pending-host-dependencies',action='store_true',
        help='Require successful native and package jobs, allowing host CI to still be installing dependencies')
    args=parser.parse_args();run_id=args.run_id;run=api(f'actions/runs/{run_id}')
    jobs=api(f'actions/runs/{run_id}/jobs')['jobs'] if args.allow_pending_host_dependencies else None
    validation=validate_build(run,jobs,args.allow_pending_host_dependencies)
    artifact=next(a for a in api(f'actions/runs/{run_id}/artifacts')['artifacts'] if a['name']=='xnu-8796-linked-kernel')
    size=artifact['size_in_bytes'];digest=artifact.get('digest','')
    assert 0<size<64*1024*1024 and digest.startswith('sha256:')
    target=ROOT/'build'/('verified-'+run['head_sha'][:7])/'kernel';target.mkdir(parents=True,exist_ok=True)
    archive=target/'artifact.private.zip';content=archive.read_bytes() if archive.exists() else b''
    if hashlib.sha256(content).hexdigest()!=digest[7:]:
        token=subprocess.check_output(['gh','auth','token'],text=True).strip()
        request=urllib.request.Request(f'https://api.github.com/repos/{REPO}/actions/artifacts/{artifact["id"]}/zip',headers={'Authorization':'Bearer '+token})
        try:
            urllib.request.build_opener(NoRedirect).open(request,timeout=15)
            raise SystemExit('Expected archive redirect')
        except urllib.error.HTTPError as error:
            if error.code!=302:raise SystemExit('Archive API failed: '+str(error.code)) from None
            location=error.headers['Location'];error.close()
        assert urllib.parse.urlparse(location).scheme=='https'
        ranges=[(n,min(size-1,n+524287)) for n in range(0,size,524288)]
        def fetch(bounds):
            start,end=bounds
            for attempt in range(3):
                try:
                    request=urllib.request.Request(location,headers={'Range':f'bytes={start}-{end}'})
                    with urllib.request.urlopen(request,timeout=20) as response:
                        assert response.status==206 and response.headers['Content-Range'].startswith(f'bytes {start}-{end}/')
                        data=response.read(end-start+2)
                    assert len(data)==end-start+1
                    return start,data
                except (OSError,AssertionError):
                    if attempt==2:raise RuntimeError(f'Archive range {start} failed') from None
        chunks={}
        with ThreadPoolExecutor(max_workers=16) as pool:
            for future in as_completed([pool.submit(fetch,bounds) for bounds in ranges]):
                start,data=future.result();chunks[start]=data
        content=b''.join(chunks[start] for start,_ in ranges)
        assert len(content)==size and hashlib.sha256(content).hexdigest()==digest[7:],'Archive SHA256 mismatch'
        archive.write_bytes(content)
    with zipfile.ZipFile(io.BytesIO(content)) as bundle:
        assert bundle.namelist()==['kernel.a6plte'] and bundle.testzip() is None
        kernel=bundle.read('kernel.a6plte');assert len(kernel)<64*1024*1024
    (target/'kernel.a6plte').write_bytes(kernel)
    (target/'receipt.json').write_text(json.dumps({'run':run_id,'sha':run['head_sha'],'url':run['html_url'],
        'validation':validation,'artifact':artifact['id'],'archive_sha256':digest[7:],'kernel_sha256':hashlib.sha256(kernel).hexdigest()},indent=2)+'\n')
    print(target/'kernel.a6plte')
    print('PASS:',validation+'; source SHA, archive SHA256, exact file list and ZIP CRC')

if __name__=='__main__':main()
