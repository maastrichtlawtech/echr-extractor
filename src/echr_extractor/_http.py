"""Shared HTTP defaults for HUDOC requests."""

# HUDOC's Cloudflare policy rejects Requests' default ``python-requests``
# user agent with a challenge response.  A browser-compatible user agent is
# sufficient for both the JSON query API and document-conversion endpoint.
HUDOC_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
}
