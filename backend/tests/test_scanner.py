import pytest
import asyncio
from scanner import _probe_groups

@pytest.mark.asyncio
async def test_probe_groups_loading():
    # Test that the scanner correctly loads base probes
    groups = await _probe_groups()
    
    assert len(groups) == 8
    categories = [cat for cat, probes in groups]
    assert "CONTENT_INJECTION" in categories
    assert "DIRECT_INJECTION" in categories
    assert "DATA_EXFILTRATION" in categories
    
    # Ensure there are actually probes in every group
    total_probes = 0
    for cat, probes in groups:
        assert isinstance(probes, list)
        assert len(probes) > 0
        total_probes += len(probes)
    assert total_probes >= 50
