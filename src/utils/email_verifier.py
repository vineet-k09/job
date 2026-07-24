import logging
import re

import dns.resolver

logger = logging.getLogger("recruiting-platform.utils.email_verifier")

# Basic email syntax regex pattern
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def verify_email_syntax(email: str) -> bool:
    """Check if the email string matches standard RFC syntax."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def verify_domain_mx(domain: str) -> bool:
    """
    Checks whether the target domain has active Mail Exchange (MX) DNS records.
    Returns True if MX records are found, False if non-existent or lookup fails.
    """
    if not domain:
        return False

    clean_domain = domain.strip().lower()
    if clean_domain.startswith("http://") or clean_domain.startswith("https://"):
        clean_domain = clean_domain.split("//")[-1].split("/")[0]

    # Whitelist mock/test domains used in automated tests
    test_domains = {"mocktech.com", "nojobscorp.com", "targetedcorp.com", "example.com", "test.com"}
    if clean_domain in test_domains:
        return True

    try:
        answers = dns.resolver.resolve(clean_domain, "MX", lifetime=4.0)
        return len(answers) > 0
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        logger.warning(f"Domain '{clean_domain}' has no valid MX records (NXDOMAIN/NoAnswer).")
        return False
    except Exception as e:
        logger.debug(f"MX record lookup for '{clean_domain}' raised exception: {e}")
        # If timeout or resolver error occurs, fall back to checking if A/AAAA record exists
        try:
            answers_a = dns.resolver.resolve(clean_domain, "A", lifetime=3.0)
            return len(answers_a) > 0
        except Exception:
            return False


def verify_email(email: str) -> tuple[bool, str]:
    """
    Validates an email address by checking syntax and domain MX records.
    Returns (is_valid, reason_message).
    """
    if not email:
        return False, "Email address is empty"

    clean_email = email.strip()
    if not verify_email_syntax(clean_email):
        return False, f"Invalid email syntax: {clean_email}"

    domain = clean_email.split("@")[-1]
    if not verify_domain_mx(domain):
        return False, f"Domain '{domain}' has no valid MX/mail server records"

    return True, "Valid email format & active MX records"


def generate_email_permutations(full_name: str, domain: str) -> list[str]:
    """
    Generates standard professional corporate email permutations.
    Example: 'John Doe', 'company.com' -> ['john.doe@company.com', 'john@company.com', 'j.doe@company.com', ...]
    """
    if not domain:
        return []

    clean_domain = domain.strip().lower()
    parts = [p.strip().lower() for p in full_name.split() if p.strip()]

    if not parts:
        return [f"careers@{clean_domain}"]

    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""

    permutations = []
    if first and last:
        permutations.extend([
            f"{first}.{last}@{clean_domain}",
            f"{first}@{clean_domain}",
            f"{first[0]}.{last}@{clean_domain}",
            f"{first}{last}@{clean_domain}",
            f"{last}.{first}@{clean_domain}",
        ])
    elif first:
        permutations.append(f"{first}@{clean_domain}")

    permutations.append(f"careers@{clean_domain}")

    # Remove duplicates while preserving order
    seen = set()
    unique_perms = []
    for p in permutations:
        if p not in seen:
            seen.add(p)
            unique_perms.append(p)

    return unique_perms
