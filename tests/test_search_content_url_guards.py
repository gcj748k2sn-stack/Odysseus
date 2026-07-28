import ipaddress

import pytest

from services.search import content as service_content


@pytest.mark.parametrize("module", [service_content])
@pytest.mark.parametrize("url", [
    "http://printer.local/",
    "http://nas.lan/",
    "http://admin.internal/",
    "http://service.intranet/",
    "http://[::ffff:169.254.169.254]/latest/meta-data/",
    "http://224.0.0.1/",
    "http://[ff02::1]/",
    "http://[::]/",
])
def test_search_content_url_guard_blocks_internal_names_and_address_classes(module, url):
    assert module._public_http_url(url) is False


@pytest.mark.parametrize("module", [service_content])
def test_search_content_url_guard_blocks_dns_to_multicast(monkeypatch, module):
    monkeypatch.setattr(
        module,
        "_resolve_hostname_ips",
        lambda host: [ipaddress.ip_address("224.0.0.1")],
    )

    assert module._public_http_url("https://example.test/page") is False


@pytest.mark.parametrize("module", [service_content])
def test_search_content_url_guard_still_allows_public_ip(module):
    assert module._public_http_url("https://93.184.216.34/") is True


# ── Local-first opt-in (WEB_FETCH_BLOCK_PRIVATE_IPS) ────────────────────────
#
# Odysseus is local-first: fetching your own ESP32, NAS or dev server on the
# LAN is an intended use. The opt-in relaxes loopback/RFC-1918/ULA and the
# internal-sounding hostname suffixes — and nothing else. The cloud
# instance-metadata range is the credential-exfil vector and stays blocked
# whatever the setting.

_GATED = [
    "http://127.0.0.1:5500/martha9_local.html",
    "http://localhost:5500/index.html",
    "http://192.168.1.42/",          # ESP32 on the LAN
    "http://10.0.0.5/",
    "http://172.20.1.9/",
    "http://[::1]:8080/",
]

# Hostname forms, kept separate because resolving them needs a stubbed
# resolver — the sandbox has no mDNS and the result would otherwise depend
# on whatever LAN the suite happens to run on.
_GATED_HOSTNAMES = [
    "http://martha.local/",
    "http://nas.lan/",
    "http://admin.internal/",
    "http://service.intranet/",
]

_ALWAYS_BLOCKED = [
    "http://169.254.169.254/latest/meta-data/",       # AWS/GCP metadata
    "http://[::ffff:169.254.169.254]/latest/meta-data/",
    "http://metadata.google.internal/",
    "http://metadata/",
    "http://224.0.0.1/",                              # multicast
    "http://[ff02::1]/",
    "http://[::]/",                                   # unspecified
    "http://0.0.0.0/",
    "file:///etc/passwd",                             # non-http scheme
]


@pytest.mark.parametrize("url", _GATED)
def test_private_targets_blocked_by_default(url):
    assert service_content._public_http_url(url) is False


@pytest.mark.parametrize("url", _GATED)
def test_private_targets_reachable_with_opt_in(url):
    assert service_content._public_http_url(url, allow_private=True) is True


@pytest.mark.parametrize("url", _GATED_HOSTNAMES)
def test_internal_hostnames_blocked_by_default(monkeypatch, url):
    monkeypatch.setattr(
        service_content,
        "_resolve_hostname_ips",
        lambda host: [ipaddress.ip_address("192.168.1.42")],
    )
    assert service_content._public_http_url(url) is False


@pytest.mark.parametrize("url", _GATED_HOSTNAMES)
def test_internal_hostnames_reachable_with_opt_in(monkeypatch, url):
    monkeypatch.setattr(
        service_content,
        "_resolve_hostname_ips",
        lambda host: [ipaddress.ip_address("192.168.1.42")],
    )
    assert service_content._public_http_url(url, allow_private=True) is True


@pytest.mark.parametrize("url", _ALWAYS_BLOCKED)
def test_hard_blocked_targets_ignore_the_opt_in(url):
    assert service_content._public_http_url(url, allow_private=False) is False
    assert service_content._public_http_url(url, allow_private=True) is False


@pytest.mark.parametrize("raw,expected", [
    (None, False),        # unset -> strict
    ("true", False),
    ("True", False),
    ("1", False),
    ("anything-else", False),
    ("false", True),
    ("False", True),
    ("0", True),
    ("no", True),
    ("off", True),
    ("  FALSE  ", True),
])
def test_env_knob_parsing(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("WEB_FETCH_BLOCK_PRIVATE_IPS", raising=False)
    else:
        monkeypatch.setenv("WEB_FETCH_BLOCK_PRIVATE_IPS", raw)
    assert service_content._private_targets_allowed() is expected


def test_env_knob_is_read_per_call_not_at_import(monkeypatch):
    """A running instance must pick up a changed environment."""
    monkeypatch.setenv("WEB_FETCH_BLOCK_PRIVATE_IPS", "true")
    assert service_content._private_targets_allowed() is False
    monkeypatch.setenv("WEB_FETCH_BLOCK_PRIVATE_IPS", "false")
    assert service_content._private_targets_allowed() is True


def test_dns_resolution_to_private_ip_follows_the_same_gate(monkeypatch):
    """A public-looking hostname resolving into RFC-1918 is gated, not free."""
    monkeypatch.setattr(
        service_content,
        "_resolve_hostname_ips",
        lambda host: [ipaddress.ip_address("192.168.1.42")],
    )
    assert service_content._public_http_url("http://martha.example/") is False
    assert service_content._public_http_url(
        "http://martha.example/", allow_private=True
    ) is True


def test_dns_resolution_to_metadata_ip_is_never_allowed(monkeypatch):
    """DNS pointing at the metadata range stays blocked under the opt-in."""
    monkeypatch.setattr(
        service_content,
        "_resolve_hostname_ips",
        lambda host: [ipaddress.ip_address("169.254.169.254")],
    )
    assert service_content._public_http_url(
        "http://innocent.example/", allow_private=True
    ) is False


def test_public_targets_unaffected_by_the_opt_in():
    for allow in (False, True):
        assert service_content._public_http_url(
            "https://93.184.216.34/", allow_private=allow
        ) is True
