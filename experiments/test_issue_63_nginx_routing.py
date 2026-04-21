"""
Experiment/test: verify frontend-react/nginx.conf correctly maps the React
client's domain-style paths onto backend-monolith router prefixes.

Every frontend-facing URL below is run through the same location/rewrite
logic nginx applies at runtime (ordered blocks, first-match wins).  The
expected backend path is whatever FastAPI actually mounts.

Run:
    python experiments/test_issue_63_nginx_routing.py
"""

import re
import sys
from pathlib import Path

NGINX_CONF = Path(__file__).resolve().parent.parent / "frontend-react" / "nginx.conf"


def parse_nginx_rules(conf_text: str):
    """Extract (prefix, rewrite_pattern, rewrite_replacement, upstream) tuples
    from the nginx config.  Returns them in declaration order — nginx prefix
    matching picks the longest, but we encode the intent by writing the most
    specific blocks first and relying on the `break` inside rewrite to keep
    the first match's replacement."""
    blocks = re.findall(
        r"location\s+(\S+)\s*\{([^}]*)\}",
        conf_text,
        re.DOTALL,
    )
    rules = []
    for prefix, body in blocks:
        if not prefix.startswith("/api"):
            continue
        rw = re.search(r"rewrite\s+(\S+)\s+(\S+)\s+break", body)
        upstream_m = re.search(r"proxy_pass\s+\$(\w+)", body)
        rules.append(
            {
                "prefix": prefix,
                "rewrite_pattern": rw.group(1) if rw else None,
                "rewrite_replacement": rw.group(2) if rw else None,
                "upstream_var": upstream_m.group(1) if upstream_m else None,
            }
        )
    # Sort by prefix length desc — nginx's longest-prefix-match semantics.
    rules.sort(key=lambda r: len(r["prefix"]), reverse=True)
    return rules


def route(path: str, rules):
    """Simulate nginx: pick the longest matching prefix, then apply its
    rewrite rule if any."""
    for r in rules:
        if path.startswith(r["prefix"]):
            if r["rewrite_pattern"]:
                # Convert nginx backrefs ($1) to Python backrefs (\\1) before
                # running re.sub.
                replacement = re.sub(r"\$(\d+)", r"\\\1", r["rewrite_replacement"])
                new = re.sub(r["rewrite_pattern"], replacement, path)
            else:
                new = path
            return r["upstream_var"], new
    return None, path


# (frontend_url, expected_upstream, expected_backend_path_prefix)
CASES = [
    # Admin UI API
    ("/api/admin/health", "admin_upstream", "/api/admin/health"),
    ("/api/admin/purchases", "admin_upstream", "/api/admin/purchases"),
    # v1 auth (frontend api.js: loginUser / confirmLogin / register / refresh)
    ("/api/v1/auth/login", "monolith_upstream", "/auth/login"),
    ("/api/v1/auth/refresh", "monolith_upstream", "/auth/refresh"),
    # Other v1 endpoints preserve prefix
    ("/api/v1/chat/media/upload", "monolith_upstream", "/api/v1/chat/media/upload"),
    ("/api/v1/voting/sessions/abc", "monolith_upstream", "/api/v1/voting/sessions/abc"),
    ("/api/v1/categories", "monolith_upstream", "/api/v1/categories"),
    # /api/users/* kept intact (router prefix is /api/users)
    ("/api/users/123/", "monolith_upstream", "/api/users/123/"),
    ("/api/users/by_email/?email=x", "monolith_upstream", "/api/users/by_email/?email=x"),
    # /api/procurements/* → /purchases/*
    ("/api/procurements/?status=active", "monolith_upstream", "/purchases/?status=active"),
    ("/api/procurements/xyz/join/", "monolith_upstream", "/purchases/xyz/join/"),
    # Legacy chat → v1 chat
    ("/api/chat/messages/?procurement=1", "monolith_upstream", "/api/v1/chat/messages/?procurement=1"),
    ("/api/chat/notifications/?user_id=1", "monolith_upstream", "/api/v1/chat/notifications/?user_id=1"),
    # Payments → wallets
    ("/api/payments/pay1/status/", "monolith_upstream", "/wallets/pay1/status/"),
    # Generic strip (reputation, wallets, escrow, auth without /v1)
    ("/api/reputation/foo", "monolith_upstream", "/reputation/foo"),
    ("/api/escrow/bar", "monolith_upstream", "/escrow/bar"),
]


def main() -> int:
    rules = parse_nginx_rules(NGINX_CONF.read_text())
    failures = []
    for url, want_upstream, want_path in CASES:
        got_upstream, got_path = route(url, rules)
        ok = got_upstream == want_upstream and got_path == want_path
        tick = "OK " if ok else "FAIL"
        print(f"{tick} {url!r:55s} -> ({got_upstream}, {got_path!r})")
        if not ok:
            failures.append((url, want_upstream, want_path, got_upstream, got_path))
    if failures:
        print(f"\n{len(failures)} failure(s):")
        for f in failures:
            print(f"  {f[0]!r}")
            print(f"    expected: ({f[1]}, {f[2]!r})")
            print(f"    got:      ({f[3]}, {f[4]!r})")
        return 1
    print(f"\nAll {len(CASES)} routing assertions pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
