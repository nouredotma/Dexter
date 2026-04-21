import uuid

import pytest


@pytest.mark.asyncio
async def test_register(async_client):
    email = f"new-{uuid.uuid4().hex}@example.com"
    resp = await async_client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "full_name": "New User"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == email


@pytest.mark.asyncio
async def test_login(async_client, test_user):
    resp = await async_client.post(
        "/auth/token",
        json={"email": test_user.email, "password": "password123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body


@pytest.mark.asyncio
async def test_create_task(async_client, auth_headers):
    resp = await async_client.post(
        "/tasks/",
        headers=auth_headers,
        json={"prompt": "Say hello"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body


@pytest.mark.asyncio
async def test_get_task(async_client, auth_headers):
    created = await async_client.post("/tasks/", headers=auth_headers, json={"prompt": "hello"})
    task_id = created.json()["id"]

    resp = await async_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


@pytest.mark.asyncio
async def test_unauthorized(async_client):
    resp = await async_client.get("/tasks/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rate_limit(async_client, auth_headers):
    codes = []
    for _ in range(61):
        resp = await async_client.get("/tasks/", headers=auth_headers)
        codes.append(resp.status_code)

    assert 429 in codes
