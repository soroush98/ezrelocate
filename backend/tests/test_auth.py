"""Unit tests for client-IP extraction."""

from types import SimpleNamespace

from app.services.auth import get_client_ip


def make_request(headers=None, client_host="1.2.3.4"):
    client = SimpleNamespace(host=client_host) if client_host is not None else None
    return SimpleNamespace(headers=headers or {}, client=client)


def test_prefers_leftmost_x_forwarded_for():
    req = make_request({"x-forwarded-for": "9.9.9.9, 10.0.0.1, 10.0.0.2"})
    assert get_client_ip(req) == "9.9.9.9"


def test_falls_back_to_fly_client_ip():
    req = make_request({"fly-client-ip": "5.5.5.5"})
    assert get_client_ip(req) == "5.5.5.5"


def test_x_forwarded_for_wins_over_fly_header():
    req = make_request({"x-forwarded-for": "9.9.9.9", "fly-client-ip": "5.5.5.5"})
    assert get_client_ip(req) == "9.9.9.9"


def test_falls_back_to_socket_peer():
    assert get_client_ip(make_request()) == "1.2.3.4"


def test_unknown_when_no_signal():
    assert get_client_ip(make_request(client_host=None)) == "unknown"
