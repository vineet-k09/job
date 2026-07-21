from src.utils.email_verifier import generate_email_permutations, verify_domain_mx, verify_email_syntax


def test_verify_email_syntax():
    assert verify_email_syntax("vineet@example.com") is True
    assert verify_email_syntax("john.doe@sub.domain.co.in") is True
    assert verify_email_syntax("invalid-email") is False
    assert verify_email_syntax("@missing-user.com") is False
    assert verify_email_syntax("missing-domain@") is False
    assert verify_email_syntax("") is False


def test_generate_email_permutations():
    perms = generate_email_permutations("Vineet Kushwaha", "google.com")
    assert "vineet.kushwaha@google.com" in perms
    assert "vineet@google.com" in perms
    assert "v.kushwaha@google.com" in perms
    assert "careers@google.com" in perms


def test_verify_domain_mx_real():
    # Real domain check
    assert verify_domain_mx("google.com") is True
    # Fake domain check
    assert verify_domain_mx("nonexistent-domain-xyz98765.com") is False
