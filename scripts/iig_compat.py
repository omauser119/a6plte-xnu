"""Keep Xcode 16 IIG output on XNU 8796's original, contiguous Mach RPC ABI."""
import re


def legacy_rpc(source):
    # 8796's IORPC has four fields. Its native Invoke/kernelDispatch routines
    # obtain content after the Mach descriptors via IORPCMessageFromMach().
    # New IIG emits an extra, separately cached content pointer instead.
    source = re.sub(r',\s*\.kernelContent\s*=\s*&buf\.msg\.content\.__hdr', '', source)
    source = re.sub(r'^\s*const struct \w+\s*\*\s*kernelContent;\n', '', source, flags=re.M)
    pattern = r'^(\s*)((?:const\s+)?\w+)\s*\*\s*(\w+)\s*=\s*rpc\.kernelContent;'

    def content(match):
        indent, kind, name = match.groups()
        return (f'{indent}{kind} * {name} = ({kind} *)'
                'IORPCMessageFromMach(rpc.message, false);')

    source = re.sub(pattern, content, source, flags=re.M)
    # CheckForWork uses the reply buffer as the returned one-way message.
    source = source.replace('message = rpc.kernelContent;',
                            'message = IORPCMessageFromMach(rpc.reply, false);')
    source = source.replace('replyMessage = rpc.rpc.kernelContent;',
                            'replyMessage = IORPCMessageFromMach(rpc.rpc.reply, false);')
    source = re.sub(r'^\s*rpc\.kernelContent = &msg->content\.__hdr;\n', '', source, flags=re.M)
    if 'kernelContent' in source:
        raise ValueError('Unrecognized IIG content-pointer syntax; preserve the 8796 ABI')
    return source
