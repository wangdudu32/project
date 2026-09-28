"""每条测试使用临时数据库，不读取个人密钥、不访问云端服务。"""
import os

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['AI_ENABLED'] = 'false'
os.environ['AMAP_ENABLED'] = 'false'
os.environ['PINECONE_ENABLED'] = 'false'

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api.main import app
from database import Base, get_db
from models import User
from security import hash_password
from seed import seed_menu


@pytest.fixture
def db_factory(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}', connect_args={'check_same_thread': False, 'timeout': 15})
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seed_menu(db)
        db.add(User(username='admin', password_hash=hash_password('adminpass123'), is_admin=True))
        db.commit()
    def session():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
    app.dependency_overrides[get_db] = session
    monkeypatch.setattr('tools.db_tool.SessionLocal', factory)
    monkeypatch.setattr('api.main.SessionLocal', factory)
    monkeypatch.setattr('api.main.init_db', lambda: None)
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def client(db_factory):
    # 不进入 lifespan，防止初始化默认数据库。
    client = TestClient(app, headers={'X-Requested-With': 'aimenu'})
    yield client
    client.close()


@pytest.fixture
def buyer(client):
    response = client.post('/auth/register', json={'username': 'buyer', 'password': 'buyerpass123'})
    assert response.status_code == 201
    return client


@pytest.fixture
def admin(db_factory):
    admin = TestClient(app, headers={'X-Requested-With': 'aimenu'})
    assert admin.post('/auth/login', json={'username': 'admin', 'password': 'adminpass123'}).status_code == 200
    yield admin
    admin.close()
