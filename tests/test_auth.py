def test_login_page(client):
    r = client.get('/login')
    assert r.status_code == 200
    assert b'Sign in' in r.data


def test_login_success(client):
    r = client.post('/login', data={'username': 'testadmin', 'password': 'testpass123'}, follow_redirects=True)
    assert r.status_code == 200
    assert b'Dashboard' in r.data or b'Check In' in r.data


def test_login_failure(client):
    r = client.post('/login', data={'username': 'testadmin', 'password': 'wrong'}, follow_redirects=True)
    assert b'Invalid' in r.data


def test_protected_route(client):
    r = client.get('/')
    assert r.status_code == 302  # redirect to login


def test_dashboard_authenticated(auth_client):
    r = auth_client.get('/')
    assert r.status_code == 200
