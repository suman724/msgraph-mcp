from msgraph_mcp.auth import generate_pkce_pair


def test_generate_pkce_pair():
    verifier, challenge = generate_pkce_pair()
    assert verifier
    assert challenge
    assert verifier != challenge
    assert len(verifier) >= 32
