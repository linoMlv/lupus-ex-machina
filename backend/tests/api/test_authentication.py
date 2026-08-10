"""Getting in, and being kept out (J8.1, D-045, D-098).

One password and one cookie: a private application with a single user, where
accounts and tokens would be machinery for nobody. The password is compared in
constant time, and an application nobody gave a password to lets nobody in —
a default that keeps a door shut is the one worth having.
"""

from fastapi.testclient import TestClient

from lupus_ex_machina.api.session import SESSION_COOKIE
from lupus_ex_machina.app import create_app
from lupus_ex_machina.config import Settings

PASSWORD = "ouvre-toi"


def guarded() -> TestClient:
    """A client of an application that has a password and a signing key."""
    return TestClient(create_app(Settings(password=PASSWORD, secret_key="clef-de-signature")))


def let_in() -> TestClient:
    """A client that has already got the password right."""
    client = guarded()
    client.post("/api/session", json={"password": PASSWORD})
    return client


def test_the_right_password_opens_a_session() -> None:
    client = guarded()

    response = client.post("/api/session", json={"password": PASSWORD})

    assert response.status_code == 204
    assert client.cookies.get(SESSION_COOKIE), "and it hands back the cookie that says so"


def test_the_wrong_password_opens_nothing() -> None:
    client = guarded()

    response = client.post("/api/session", json={"password": "au-hasard"})

    assert response.status_code == 401
    assert client.cookies.get(SESSION_COOKIE) is None


def test_a_protected_route_is_refused_without_a_session() -> None:
    assert guarded().get("/api/session").status_code == 401


def test_a_protected_route_answers_once_the_session_is_open() -> None:
    assert let_in().get("/api/session").status_code == 200


def test_a_cookie_the_client_made_up_is_worth_nothing() -> None:
    """The signature is what makes the difference, not the presence of a cookie."""
    client = guarded()
    client.cookies.set(SESSION_COOKIE, "9999999999.pas-une-signature")

    assert client.get("/api/session").status_code == 401


def test_an_application_without_a_password_lets_nobody_in() -> None:
    """Forgetting to set one must shut the door, never open it (D-090's habit)."""
    client = TestClient(create_app(Settings(secret_key="clef-de-signature")))

    assert client.post("/api/session", json={"password": ""}).status_code == 401
    assert client.get("/api/session").status_code == 401


def test_a_session_is_given_up_when_it_is_handed_back() -> None:
    client = let_in()

    assert client.delete("/api/session").status_code == 204
    assert client.get("/api/session").status_code == 401


def test_the_health_probe_stays_open() -> None:
    """The container HEALTHCHECK has no cookie, and never will."""
    assert guarded().get("/health").status_code == 200
