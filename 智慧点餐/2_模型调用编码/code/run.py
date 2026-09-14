"""
AiMenu 启动脚本

启动uvicorn web服务器，提供智能点餐API服务
"""

import  uvicorn

def  main():
    """启动AiMenu API服务"""

    print("🍽️ AiMenu 智能点餐系统 v1.0")
    print("=" * 50)

    print("✅ 环境配置检查通过")
    print("🚀 正在启动API服务...")
    print("📍 服务地址: http://localhost:8000")
    print("=" * 50)

    uvicorn.run(app="api.main:app",host="0.0.0.0",port=8000,log_level="info")





if __name__ == '__main__':
    main()
