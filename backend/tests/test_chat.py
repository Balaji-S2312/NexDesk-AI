import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.database.init_db import DEMO_EMPLOYEE_EMAIL, DEMO_EMPLOYEE_PASSWORD
from app.services.llm.groq_client import GroqAuthenticationError, GroqClientError

client = TestClient(app)

@pytest.fixture
def auth_headers():
    res = client.post("/api/auth/login", json={
        "email": DEMO_EMPLOYEE_EMAIL,
        "password": DEMO_EMPLOYEE_PASSWORD
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_chat_requires_auth():
    res = client.post("/api/chat", json={"message": "Hello"})
    assert res.status_code == 403 or res.status_code == 401

def test_chat_blank_message_rejected(auth_headers):
    res = client.post("/api/chat", json={"message": "   "}, headers=auth_headers)
    assert res.status_code == 422

@pytest.mark.anyio
@patch("app.api.routes.chat.groq_client.chat_completion", new_callable=AsyncMock)
async def test_chat_successful_response(mock_chat, auth_headers):
    mock_chat.return_value = "To resolve VPN error 504, please flush your DNS cache by running ipconfig /flushdns."
    
    res = client.post("/api/chat", json={
        "message": "My VPN is not connecting with error 504"
    }, headers=auth_headers)
    
    assert res.status_code == 200
    data = res.json()
    assert "conversation_id" in data
    assert "flush your DNS cache" in data["response"]
    assert isinstance(data["sources"], list)
    assert isinstance(data["actions"], list)
    # Check that VPN source or create_ticket action was detected
    assert any(a["action_type"] == "create_ticket" for a in data["actions"])

@pytest.mark.anyio
@patch("app.api.routes.chat.groq_client.chat_completion", new_callable=AsyncMock)
async def test_chat_handles_unconfigured_api_key_gracefully(mock_chat, auth_headers):
    mock_chat.side_effect = GroqAuthenticationError("GROQ_API_KEY is not set.")
    
    res = client.post("/api/chat", json={
        "message": "I need help with my monitor."
    }, headers=auth_headers)
    
    assert res.status_code == 200
    data = res.json()
    assert "NexDesk AI Service Notice" in data["response"]
    assert "GROQ_API_KEY" in data["response"]

@pytest.mark.anyio
@patch("app.api.routes.chat.groq_client.chat_completion", new_callable=AsyncMock)
async def test_chat_conversation_continuity(mock_chat, auth_headers):
    mock_chat.return_value = "What operating system are you running?"
    
    # 1. First message
    res1 = client.post("/api/chat", json={
        "message": "My screen is flickering."
    }, headers=auth_headers)
    assert res1.status_code == 200
    conv_id = res1.json()["conversation_id"]
    
    # 2. Second message using existing conversation_id
    mock_chat.return_value = "For Windows 11, try updating your Thunderbolt dock firmware."
    res2 = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "message": "I am on Windows 11"
    }, headers=auth_headers)
    assert res2.status_code == 200
    assert res2.json()["conversation_id"] == conv_id
    assert "Thunderbolt dock" in res2.json()["response"]
