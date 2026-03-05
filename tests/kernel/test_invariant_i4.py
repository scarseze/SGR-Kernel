import asyncio
import hashlib
import os
import tempfile
import pytest
from hypothesis import given, settings, strategies as st
from core.artifacts import LocalArtifactStore, ArtifactRef

@pytest.mark.asyncio
@given(
    write_delay_ms=st.integers(min_value=0, max_value=20),
    read_delay_ms=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=100, deadline=None)
async def test_atomic_visibility(write_delay_ms, read_delay_ms):
    """
    TLA+ Invariant I4: Atomic Visibility
    Proves that a consumer NEVER reads partial data during concurrent write operations,
    because the artifact store uses an atomic OS-level rename (Two-Phase approach).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalArtifactStore(tmpdir)
        # Large payload to allow IO buffering and simulate slow network writes
        payload = b"A" * (1024 * 1024 * 5) # 5MB
        sha256 = hashlib.sha256(payload).hexdigest()
        
        # Construct the reference manually so readers can poll for its existence 
        # independently of the writer finishing
        ref = ArtifactRef(
            id=sha256,
            key="test_concurrent",
            uri=f"file://{os.path.join(tmpdir, sha256 + '.dat')}",
            size_bytes=len(payload),
            hash_sha256=sha256,
            content_type="application/octet-stream"
        )
        
        async def writer():
            await asyncio.sleep(write_delay_ms / 1000.0)
            # Use to_thread to allow true concurrency during synchronous IO
            await asyncio.to_thread(store.put, "test_concurrent", payload)
            
        async def reader():
            await asyncio.sleep(read_delay_ms / 1000.0)
            try:
                data = await asyncio.to_thread(store.get, ref)
                # INVARIANT I4: If we read it, it MUST be the full, uncorrupted data
                assert len(data) == len(payload)
                assert data == payload
                return "SUCCESS"
            except FileNotFoundError:
                # Perfectly fine: we tried to read before the atomic commit
                return "NOT_FOUND"
            except PermissionError:
                # Windows file locking: os.rename() temporarily locks the file.
                # This is NOT a partial read — the OS prevented access entirely.
                return "LOCKED"
            except ValueError as e:
                # INVARIANT I4 VIOLATION: Integrity check failed (partial read)
                return f"PARTIAL_READ: {e}"
            except Exception as e:
                return f"ERROR: {e}"
        
        # Run 1 writer and 10 concurrent consumers at random offsets
        tasks = [writer()] + [reader() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        reader_results = results[1:]
        for r in reader_results:
            assert not str(r).startswith("PARTIAL_READ"), "Violation of I4: Consumer read a partial file!"
            assert str(r) in ("SUCCESS", "NOT_FOUND", "LOCKED"), f"Unexpected error: {r}"
