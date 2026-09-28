"""初始化数据、创建管理员和同步向量。不会删除已有菜单或订单。"""
import argparse
from getpass import getpass

from sqlalchemy import select

from api.schemas import Credentials
from database import SessionLocal, init_db
from models import User
from security import hash_password
from seed import seed_menu


def main():
    parser = argparse.ArgumentParser(description="智慧点餐管理命令")
    parser.add_argument("command", choices=["init-db", "create-admin", "sync-menu"])
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()
    init_db()
    if args.command == "sync-menu":
        from tools.pine_cone_tool import sync_menu
        print(f"同步完成，共 {sync_menu()} 道菜品")
        return
    with SessionLocal() as db:
        if args.command == "init-db":
            added = seed_menu(db)
            print("数据库已初始化，示例菜单已添加" if added else "数据库已初始化，保留已有菜单")
        else:
            password = getpass("管理员密码（8 至 128 位）：")
            if password != getpass("再次输入密码："):
                raise ValueError("两次密码不一致")
            credentials = Credentials(username=args.username, password=password)
            username = credentials.username.lower()
            if db.scalar(select(User).where(User.username == username)):
                raise ValueError("用户名已存在，请使用新的管理员用户名")
            db.add(User(username=username, password_hash=hash_password(credentials.password), is_admin=True))
            db.commit()
            print(f"管理员 {username} 已创建")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # 外部 SDK 异常可能包含服务地址，避免直接输出密钥等连接信息。
        if isinstance(exc, (ValueError, RuntimeError)):
            print(f"操作失败：{exc}")
        else:
            print(f"操作失败（{type(exc).__name__}），请检查数据库和外部服务配置")
        raise SystemExit(1)
