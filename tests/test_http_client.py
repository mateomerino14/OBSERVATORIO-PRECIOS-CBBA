import httpx
import pytest

from observatory.http_client import (
    BACKOFF_BASE_SECONDS,
    MIN_DELAY_SECONDS,
    USER_AGENT,
    BotProtectionError,
    DisallowedByRobotsError,
    PoliteClient,
)

ROBOTS = "User-agent: *\nDisallow: /checkout\n"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(handler, clock: FakeClock, delay: float = 2.0) -> PoliteClient:
    return PoliteClient(
        delay_seconds=delay,
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        clock=clock.time,
    )


def test_identifies_itself_and_waits_between_requests() -> None:
    seen_agents = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_agents.append(request.headers["user-agent"])
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        return httpx.Response(200, text="ok")

    clock = FakeClock()
    client = make_client(handler, clock)

    client.get_text("https://tienda.test/a")
    client.get_text("https://tienda.test/b")

    assert set(seen_agents) == {USER_AGENT}
    assert clock.sleeps == [2.0, 2.0]


def test_delay_never_goes_below_project_minimum() -> None:
    client = PoliteClient(delay_seconds=0.1)
    assert client.delay_seconds == MIN_DELAY_SECONDS
    client.close()


def test_blocks_urls_disallowed_by_robots() -> None:
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(200, text=ROBOTS)

    client = make_client(handler, FakeClock())

    with pytest.raises(DisallowedByRobotsError):
        client.get_text("https://tienda.test/checkout/pago")
    assert requested == ["/robots.txt"]


def test_missing_robots_allows_everything() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="producto")

    assert make_client(handler, FakeClock()).get_text("https://tienda.test/x") == "producto"


def test_retries_transient_errors_with_backoff() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, text="listo")

    clock = FakeClock()
    client = make_client(handler, clock)

    assert client.get_text("https://tienda.test/x") == "listo"
    assert BACKOFF_BASE_SECONDS in clock.sleeps
    assert BACKOFF_BASE_SECONDS * 2 in clock.sleeps


def test_raises_on_client_errors_without_retrying() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        attempts["count"] += 1
        return httpx.Response(404)

    with pytest.raises(httpx.HTTPStatusError):
        make_client(handler, FakeClock()).get_text("https://tienda.test/no-existe")
    assert attempts["count"] == 1


def test_get_json_sends_query_params() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, json={"pagina": request.url.params["Pagina"]})

    client = make_client(handler, FakeClock())

    assert client.get_json("https://tienda.test/api", {"Pagina": 2}) == {"pagina": "2"}


def test_detects_bot_protection_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200, text="<title>302 Found</title><body><center>rdwr</center></body>"
        )

    with pytest.raises(BotProtectionError):
        make_client(handler, FakeClock()).get_text("https://tienda.test/categoria")


def test_normal_pages_with_bot_script_are_not_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text='<script>var __uzdbm_1 = "x";</script><h1>Abarrotes</h1>')

    assert "Abarrotes" in make_client(handler, FakeClock()).get_text("https://tienda.test/c")
