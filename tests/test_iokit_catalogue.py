#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Validate the compiled built-in catalogue against the legacy OSUnserialize subset it uses."""
import ast
from pathlib import Path
import re
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]

class LegacyCatalogue:
    # XNU OSUnserialize.y permits letters, digits and '-' in bare strings;
    # class names containing '_' must be quoted. This is not XML/plistlib.
    token=re.compile(r"\s+|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|[A-Za-z][A-Za-z0-9-]*|[0-9]+:[0-9]+|[(){}=;,]")
    def __init__(self,text):
        self.tokens=[];pos=0
        while pos<len(text):
            m=self.token.match(text,pos)
            if not m: raise ValueError(f'invalid OSUnserialize token at {pos}')
            t=m.group();pos=m.end()
            if not t.isspace():self.tokens.append(t)
        self.pos=0
    def take(self,expected=None):
        if self.pos==len(self.tokens):raise ValueError('truncated catalogue')
        t=self.tokens[self.pos];self.pos+=1
        if expected is not None and t!=expected:raise ValueError(f'expected {expected}, got {t}')
        return t
    def value(self):
        t=self.take()
        if t=='(':
            values=[]
            if self.pos<len(self.tokens) and self.tokens[self.pos]==')':self.take();return values
            while True:
                values.append(self.value());sep=self.take()
                if sep==')':return values
                if sep!=',':raise ValueError('invalid array separator')
        if t=='{':
            values={}
            while self.pos<len(self.tokens) and self.tokens[self.pos]!='}':
                key=self.value();self.take('=');value=self.value();self.take(';')
                if not isinstance(key,str) or key in values:raise ValueError('invalid/duplicate key')
                values[key]=value
            self.take('}');return values
        if t[0] in "'\"":return ast.literal_eval(t)
        if t[0].isalpha():return t
        if ':' in t:
            value,bits=map(int,t.split(':'))
            if not 0<bits<=64 or value>=1<<bits:raise ValueError('invalid number width')
            return value
        raise ValueError('invalid value')
    def parse(self):
        result=self.value()
        if self.pos!=len(self.tokens):raise ValueError('trailing tokens')
        return result

def catalogue(a6):
    s=subprocess.check_output(['clang','-E','-P','-x','c++',f'-DA6PLTE={int(a6)}',str(ROOT/'xnu/iokit/KernelConfigTables.cpp')],text=True)
    s=s[s.index('=')+1:s.rindex(';')]
    return ''.join(ast.literal_eval(m.group()) for m in re.finditer(r'"(?:[^"\\]|\\.)*"',s))

class CatalogueTest(unittest.TestCase):
    def test_compiled_profiles_and_real_driver_names(self):
        for a6 in (False,True):
            rows=LegacyCatalogue(catalogue(a6)).parse()
            self.assertEqual(len(rows),5 if a6 else 1)
            drivers={r['IOClass']:r for r in rows}
            self.assertEqual(len(drivers),len(rows))
            self.assertEqual(drivers['IOPanicPlatform']['IOProbeScore'],0)
            for row in rows:self.assertIsInstance(row['IOProviderClass'],str)
            if a6:
                hfs=drivers['com_apple_filesystems_hfs']
                self.assertEqual(hfs['IOMatchCategory'],'com_apple_filesystems_hfs')
                self.assertEqual((hfs['IOProviderClass'],hfs['IOResourceMatch']),('IOResources','IOBSD'))
                self.assertEqual(drivers['A6PLTEPlatformExpert']['IONameMatch'],'samsung,a6plte')
                self.assertEqual(drivers['AppleCLCD']['IONameMatch'],'samsung,a6plte-display')
                self.assertEqual(drivers['AppleCLCD']['IOProviderClass'],'IOPlatformDevice')
                self.assertEqual(drivers['IOCoreSurfaceRoot']['IOProviderClass'],'IOResources')
                self.assertEqual(drivers['IOCoreSurfaceRoot']['IOMatchCategory'],'IOCoreSurfaceRoot')
    def test_rejects_device_regression_and_malformed_data(self):
        s=catalogue(True)
        for bad in (s.replace("'com_apple_filesystems_hfs'",'com_apple_filesystems_hfs'),s[:-1],s+' garbage',"({'IOClass'=One;'IOClass'=Two;})","({'IOProbeScore'=256:8;})"):
            with self.assertRaises(ValueError):LegacyCatalogue(bad).parse()

if __name__=='__main__':unittest.main()
