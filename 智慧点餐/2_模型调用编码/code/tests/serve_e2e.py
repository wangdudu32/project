"""浏览器测试专用服务：临时数据库、固定测试管理员、关闭外部服务。"""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == '__main__':
    with TemporaryDirectory(prefix='aimenu-e2e-') as folder:
        os.environ['DATABASE_URL'] = f"sqlite:///{Path(folder) / 'test.db'}"
        os.environ['AI_ENABLED'] = 'false'
        os.environ['PINECONE_ENABLED'] = 'false'
        os.environ['AMAP_ENABLED'] = 'false'
        os.environ['COOKIE_SECURE'] = 'false'
        from database import SessionLocal, init_db
        from models import User
        from security import hash_password
        import uvicorn

        init_db()
        with SessionLocal() as db:
            db.add(User(username='browser_admin', password_hash=hash_password('browser-admin-test'), is_admin=True))
            db.commit()
        uvicorn.run('api.main:app', host='127.0.0.1', port=8001)
