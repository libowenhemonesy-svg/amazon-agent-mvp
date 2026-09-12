from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.deps import init_session_factory
from app.routes.chrome import router


def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'chrome.db'}")
    Base.metadata.create_all(engine)
    init_session_factory(sessionmaker(bind=engine))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def payload():
    return {
        "asin": "B0ABC12345", "title": "测试商品", "price": "$19.99", "rating": "4.6 out of 5", "review_count": "1,234 ratings",
        "bullets": ["第一条"], "reviews": [], "image": "https://images-na.ssl-images-amazon.com/test.jpg",
        "url": "https://www.amazon.com/dp/B0ABC12345"
    }


def test_chrome_product_capture_and_list(tmp_path):
    with client(tmp_path) as app:
        response = app.post("/api/chrome/submit", json=payload())
        assert response.status_code == 201
        product = response.json()["product"]
        assert product["asin"] == "B0ABC12345"
        assert product["price"] == 19.99
        assert product["rating"] == 4.6
        assert product["review_count"] == 1234
        assert product["marketplace"] == "US"
        assert app.get("/api/chrome/products").json()["products"][0]["id"] == product["id"]


def test_chrome_capture_rejects_non_amazon_url(tmp_path):
    data = payload() | {"url": "https://example.com/dp/B0ABC12345"}
    with client(tmp_path) as app:
        assert app.post("/api/chrome/submit", json=data).status_code == 422


def test_chrome_capture_rejects_invalid_asin(tmp_path):
    data = payload() | {"asin": "not-an-asin"}
    with client(tmp_path) as app:
        assert app.post("/api/chrome/submit", json=data).status_code == 422
