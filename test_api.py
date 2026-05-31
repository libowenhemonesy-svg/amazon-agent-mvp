import os
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./amazon_agent.db"

from app.main import create_app
from fastapi.testclient import TestClient

app = create_app(database_url="sqlite+pysqlite:///./amazon_agent.db")
client = TestClient(app)

r = client.post('/api/chrome/submit', json={
    'title': 'Test Product',
    'price': '$29.99',
    'asin': 'B0TEST123'
})

print(f"Status: {r.status_code}")
print(f"Response: {r.text}")
