import io
import os
from pathlib import Path
import pytest
from verify_bins import check_strings, MAX_CHUNK, SW_VERSIONS

def _prior(data):
    out={'size':len(data)}
    for sw in SW_VERSIONS:
        sb=sw.encode('ascii');idx=data.find(sb)
        if idx>=0:
            ctx=data[max(0,idx-4):min(len(data),idx+len(sb)+20)]
            out[sw]=f'@0x{idx:05X} ['+''.join(chr(c) if 32<=c<127 else '.' for c in ctx)+']'
    return out

@pytest.mark.parametrize('offset',[0,1,MAX_CHUNK-27,MAX_CHUNK-6,MAX_CHUNK-1,MAX_CHUNK,MAX_CHUNK+1,MAX_CHUNK*2-3,MAX_CHUNK*2])
def test_first_match_at_every_boundary(tmp_path,offset):
    data=b'.'*offset+b'0110C6'+b'abc'*14
    f=tmp_path/'t.bin';f.write_bytes(data)
    assert check_strings(f)==_prior(data)

def test_multiple_mixed_case_markers_across_chunks(tmp_path):
    data=b'X'*MAX_CHUNK*2+b'430069 - SIEMENS'+b'A'*MAX_CHUNK+b'430069 MS45 Siemens 0110C6'
    f=tmp_path/'t.bin';f.write_bytes(data)
    assert check_strings(f)==_prior(data)

def test_missing_and_empty(tmp_path):
    f=tmp_path/'t.bin';f.write_bytes(b'')
    assert check_strings(f)=={'size':0}
    f.write_bytes(b'no-ids\0\x0f')
    assert check_strings(f)==_prior(f.read_bytes())

def test_large_stream_read_is_bounded(tmp_path,monkeypatch):
    f=tmp_path/'t.bin';f.write_bytes(b'A'*MAX_CHUNK*5+b'MSV70')
    original=Path.open
    class SafeRead:
        def __init__(self,underlying):self.f=underlying
        def __enter__(self):self.f.__enter__();return self
        def __exit__(self,*a):return self.f.__exit__(*a)
        def read(self,n=-1):
            assert n==MAX_CHUNK
            return self.f.read(n)
    def open_checked(self,*a,**kw):
        stream=original(self,*a,**kw)
        return SafeRead(stream) if self==f else stream
    monkeypatch.setattr(Path,'open',open_checked)
    r=check_strings(f)
    assert 'MSV70' in r

def test_symlink_rejected(tmp_path):
    f=tmp_path/'source.bin';f.write_bytes(b'MSV70')
    alias=tmp_path/'alias.bin'
    try:alias.symlink_to(f)
    except OSError:pytest.skip('symlink unavailable')
    with pytest.raises(ValueError,match='ordinary'):check_strings(alias)

def test_known_case_sensitive_names_preserved(tmp_path):
    data=b'MSV70 0110C6 Siemens SIEMENS'
    f=tmp_path/'t.bin';f.write_bytes(data)
    assert check_strings(f)==_prior(data)
