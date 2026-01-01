"""URL normalization utilities for duplicate detection."""

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

# Common tracking parameters to remove
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'ref', 'referrer', 'source', 'fbclid', 'gclid', 'msclkid',
    '_ga', '_gl', 'mc_cid', 'mc_eid', 'pk_campaign', 'pk_kwd'
}


def normalize_url(url: str) -> str:
    """
    Normalize URL for duplicate detection.

    - Convert domain to lowercase
    - Force https scheme
    - Remove trailing slashes
    - Remove tracking parameters
    - Sort query parameters

    Args:
        url: Raw URL string

    Returns:
        Normalized URL string (empty if malformed)
    """
    if not url:
        return ""

    parsed = urlparse(url.strip())

    # Validate URL has a domain
    if not parsed.netloc:
        return ""

    # Lowercase domain, force https
    netloc = parsed.netloc.lower()
    scheme = 'https' if parsed.scheme in ('http', 'https') else parsed.scheme

    # Normalize path: remove trailing slash, use empty string for root
    path = parsed.path.rstrip('/') or ''

    # Filter tracking params, sort remaining
    query = ''
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        clean = {k: v for k, v in params.items() if k not in TRACKING_PARAMS}
        if clean:
            query = urlencode(sorted(clean.items()), doseq=True)

    return urlunparse((scheme, netloc, path, '', query, ''))
