## 1、创建如下项目结构

### ①.新建api的package

### ②.新建agent的package

### ③.新建tools的package

### ④.新建service的package

### ⑤.新建prompt的目录

### ⑥.新建run.py

### ⑦.新建.env文件

### ⑧.新建requirement.txt文件

项目结构如下：







## 2、搭建Web服务

### 2.1 定义web应用实例

1.在api包下的main.py中定义FastAPI实例

2.在api包下的main.py中定义页面访问入口请求

```python
from fastapi import FastAPI
# 创建FastAPI应用
app = FastAPI(
    title="AiMenu智能点餐系统",
    description="智能餐厅助手API，提供智能对话、配送查询和菜品列表服务",
    version="2.0.0"
)

@app.get("/")
async def root():
    """根路径"""
    return {"message": "欢迎使用AiMenu智能点餐系统API"}

```



### 2.2 定义web服务器

1.在run.py中定义run方法

2.在run方法中定义web服务器实例

```python
import uvicorn
def main():
    """启动AiMenu API服务"""
    
    print("🍽️ AiMenu 智能点餐系统 v2.0")
    print("=" * 50)
    
    print("✅ 环境配置检查通过")
    print("🚀 正在启动API服务...")
    print("📍 服务地址: http://localhost:8000")
    print("📖 API文档: http://localhost:8000/docs")
    print("=" * 50)
    
    # 启动服务
    try:
        uvicorn.run(
            "api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,  # 开发模式，文件变化时自动重启
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == "__main__":
    main()

```

### 2.3 测试服务可用性

1.打开浏览器输入：http://127.0.0.1:8001/

2.页面结果：



### 2.4 定义数据模型

1.定义聊天请求数据模型

```python
class ChatRequest(BaseModel):
    """智能对话请求"""
    query: str
```

2.定义配送查询请求数据模型

```python
class DeliveryRequest(BaseModel):
    """配送查询请求"""
    address: str
    travel_mode: PathModeInput = "2"  # 1=步行, 2=骑电动车, 3=驾车
```

3.定义聊天响应数据模型

```python
# 响应模型
class ChatResponse(BaseModel):
    """智能对话响应"""
    success: bool # 成功失败表示
    query: str # 原始查询内容
    response: Optional[str] = None # 响应内容
    recommendation: Optional[str] = None # 推荐内容
    menu_ids: Optional[List[str]] = None # 推荐的菜品id
```

4.定义配送查询响应数据模型

```python
# 响应数据模型
class DeliveryResponse(BaseModel):
    """配送查询响应"""
    success: bool  # 成功(True) or 失败的标识（False）
    in_range: bool #  配送是否在配送范围内(True False)
    distance: float # 配送距离(公里 km)
    formatted_address: str # 格式化地址
    duration:float # 配送时间（秒）
    message: str  # (前端要展示的配送完整消息内容)
    travel_mode: PathModeInput # 配送模式 (1:步行 2:骑电动车 3:驾车)
    input_address: str # 输入原始内容

```

5.定义菜品列表响应数据模型

```python
class MenuListResponse(BaseModel):
    """菜品列表响应"""
    success: bool
    menu_items: List[dict] # 菜品列表
    count: int # 菜品数
    message: str # 响应消息提示
```

### 2.5 定义web路由请求接口

#### 1.定义健康检测接口

```python
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "service": "AiMenu API"}
```



#### 2.定义聊天请求接口

```python
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    智能对话接口
    
    接收用户问题，返回智能助手回复
    """
    try:
        # 调用智能对话服务
        result = smart_chat(request.query)
        
        # 处理不同类型的返回值
        if isinstance(result, dict) and "recommendation" in result and "menu_ids" in result:
            # 菜品推荐返回
            return ChatResponse(
                success=True,
                query=request.query,
                recommendation=result["recommendation"],
                menu_ids=result["menu_ids"]
            )
        else:
            # 普通文本回复
            return ChatResponse(
                success=True,
                query=request.query,
                response=str(result)
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"智能对话服务失败: {str(e)}"
        )

```

#### 3.定义配送查询请求接口

```python
@app.post("/delivery", response_model=DeliveryResponse)
async def delivery_endpoint(request: DeliveryRequest):
    """
    配送查询接口
    
    检查指定地址是否在配送范围内
    """
    try:
        # 调用配送查询服务
        result = delivery_check(request.address, request.travel_mode)
        
        if result["status"] == "success":
            return DeliveryResponse(
                success=True,
                in_range=result["in_range"],
                distance=result["distance"],
                formatted_address=result["formatted_address"],
                message=result["message"],
                travel_mode=request.travel_mode,
                input_address=request.address
            )
        else:
            return DeliveryResponse(
                success=False,
                in_range=False,
                distance=0.0,
                formatted_address=request.address,
                message=result["message"],
                travel_mode=request.travel_mode,
                input_address=request.address
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"配送查询服务失败: {str(e)}"
        )
```

#### 4.定义菜品列表查询请求接口

```python

@app.get("/menu/list", response_model=MenuListResponse)
async def menu_list_endpoint():
    """
    菜品列表接口
    
    获取所有菜品的结构化信息，专为前端展示设计
    """
    try:
        # 获取结构化数据
        structured_data = get_menu_items_list()
        
        # 检查是否获取到有效数据
        if not structured_data:
            return MenuListResponse(
                success=False,
                menu_items=[],
                count=0,
                message="当前没有可用的菜品信息"
            )
        
        # 计算菜品数量
        menu_count = len(structured_data)
        
        return MenuListResponse(
            success=True,
            menu_items=structured_data,
            count=menu_count,
            message=f"成功获取 {menu_count} 个菜品信息"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"菜品列表服务失败: {str(e)}"
        )

```

#### 5.测试查询菜品列表接口

```python
if __name__ == "__main__":
    # 运行测试
    test_success = test_menu_list_api()
    
    if test_success:
        print("\n🚀 启动API服务...")
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("\n❌ 测试失败，请检查配置") 
```

#### 6.完整文件代码

main.py文件代码

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiMenu FastAPI 接口

提供三个主要接口：
1. POST /chat - 智能对话接口
2. POST /delivery - 配送查询接口
3. GET /menu/list - 菜品列表接口
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any, Dict, Union
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入服务
from service.service import smart_chat, delivery_check
from tools.db_tool import get_menu_items_list

# 创建FastAPI应用
app = FastAPI(
    title="AiMenu智能点餐系统",
    description="智能餐厅助手API，提供智能对话、配送查询和菜品列表服务",
    version="2.0.0"
)

# 请求模型
class ChatRequest(BaseModel):
    """智能对话请求"""
    query: str
    
class DeliveryRequest(BaseModel):
    """配送查询请求"""
    address: str
    travel_mode: Optional[int] = 3  # 1=直线, 2=驾车, 3=骑行

# 响应模型
class ChatResponse(BaseModel):
    """智能对话响应"""
    success: bool
    query: str
    response: Optional[str] = None
    recommendation: Optional[str] = None
    menu_ids: Optional[List[str]] = None
    
class DeliveryResponse(BaseModel):
    """配送查询响应"""
    success: bool
    in_range: bool
    distance: float
    formatted_address: str
    message: str
    travel_mode: int
    input_address: str

class MenuListResponse(BaseModel):
    """菜品列表响应"""
    success: bool
    menu_items: List[dict]
    count: int
    message: str

@app.get("/")
async def root():
    """根路径"""
    return {"message": "欢迎使用AiMenu智能点餐系统API"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    智能对话接口
    
    接收用户问题，返回智能助手回复
    """
    try:
        # 调用智能对话服务
        result = smart_chat(request.query)
        
        # 处理不同类型的返回值
        if isinstance(result, dict) and "recommendation" in result and "menu_ids" in result:
            # 菜品推荐返回
            return ChatResponse(
                success=True,
                query=request.query,
                recommendation=result["recommendation"],
                menu_ids=result["menu_ids"]
            )
        else:
            # 普通文本回复
            return ChatResponse(
                success=True,
                query=request.query,
                response=str(result)
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"智能对话服务失败: {str(e)}"
        )

@app.post("/delivery", response_model=DeliveryResponse)
async def delivery_endpoint(request: DeliveryRequest):
    """
    配送查询接口
    
    检查指定地址是否在配送范围内
    """
    try:
        # 调用配送查询服务
        result = delivery_check(request.address, request.travel_mode)
        
        if result["status"] == "success":
            return DeliveryResponse(
                success=True,
                in_range=result["in_range"],
                distance=result["distance"],
                formatted_address=result["formatted_address"],
                message=result["message"],
                travel_mode=request.travel_mode,
                input_address=request.address
            )
        else:
            return DeliveryResponse(
                success=False,
                in_range=False,
                distance=0.0,
                formatted_address=request.address,
                message=result["message"],
                travel_mode=request.travel_mode,
                input_address=request.address
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"配送查询服务失败: {str(e)}"
        )

@app.get("/menu/list", response_model=MenuListResponse)
async def menu_list_endpoint():
    """
    菜品列表接口
    
    获取所有菜品的结构化信息，专为前端展示设计
    """
    try:
        # 获取结构化数据
        structured_data = get_menu_items_list()
        
        # 检查是否获取到有效数据
        if not structured_data:
            return MenuListResponse(
                success=False,
                menu_items=[],
                count=0,
                message="当前没有可用的菜品信息"
            )
        
        # 计算菜品数量
        menu_count = len(structured_data)
        
        return MenuListResponse(
            success=True,
            menu_items=structured_data,
            count=menu_count,
            message=f"成功获取 {menu_count} 个菜品信息"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"菜品列表服务失败: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "service": "AiMenu API"}

# 测试主函数
def test_menu_list_api():
    """测试菜品列表接口功能"""
    print("=" * 60)
    print("菜品列表API测试（纯净版）")
    print("=" * 60)
    
    try:
        # 导入数据库工具
        from tools.db_tool import get_menu_items_list
        
        print("\n1. 测试结构化数据查询...")
        structured_data = get_menu_items_list()
        
        if structured_data:
            print(f"✅ 结构化数据查询成功")
            print(f"📊 菜品数量: {len(structured_data)}")
            
            # 显示第一个菜品的详细信息
            if len(structured_data) > 0:
                first_item = structured_data[0]
                print(f"\n📋 第一个菜品详情:")
                print(f"   - ID: {first_item['id']}")
                print(f"   - 名称: {first_item['dish_name']}")
                print(f"   - 价格: {first_item['formatted_price']}")
                print(f"   - 分类: {first_item['category']}")
                print(f"   - 辣度: {first_item['spice_text']}")
                print(f"   - 素食: {first_item['vegetarian_text']}")
                
            # 显示所有分类（统计用）
            categories_set = set(item['category'] for item in structured_data)
            print(f"\n📁 包含分类: {', '.join(categories_set)}")
        else:
            print("❌ 结构化数据查询失败")
            return False
            
        print("\n2. 模拟API响应...")
        # 模拟构建API响应
        api_response = {
            "success": True,
            "menu_items": structured_data,
            "count": len(structured_data),
            "message": f"成功获取 {len(structured_data)} 个菜品信息"
        }
        
        print(f"✅ API响应构建成功")
        print(f"🔍 响应结构:")
        print(f"   - success: {api_response['success']}")
        print(f"   - count: {api_response['count']}")
        print(f"   - message: {api_response['message']}")
        print(f"   - menu_items: {len(api_response['menu_items'])} 个菜品")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 菜品列表API测试完成")
    print("=" * 60)
    return True

if __name__ == "__main__":
    # 运行测试
    test_success = test_menu_list_api()
    
    if test_success:
        print("\n🚀 启动API服务...")
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("\n❌ 测试失败，请检查配置") 
```



## 3、定义业务工具

### 3.1 定义MySQL业务工具

#### 3.1.1 新建db_tool文件

> 模块作用：该模块提供MySQL数据库连接和查询功能，专门用于查询menu数据库中的menu_items表的全部信息

##### ①  定义数据库连接类

1. 定义初始化函数，配置数据库信息(数据库地址、端口、用户名、密码、数据库、连接、游标)
2. 定义连接函数，初始化数据库连接对象和游标对象
3. 定义关闭数据库连接函数，关闭数据库库连接
4.  定义上下文管理器入口函数，用于调用数据库连接函数库
5.  定义上下文管理器出口函数，用于调用关闭数据连接函数库



db.tool.py文件代码片段如下：

```python
class  DataBaseConnection:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.host = os.getenv("MYSQL_HOST", "localhost")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD", "root")
        self.database = os.getenv("MYSQL_DATABASE", "menu")


    def    connect(self)-> bool:
        """建立数据库连接"""
      
        try:
            self.connection=mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4"
            )
            if self.connection.is_connected():
               self.cursor = self.connection.cursor(dictionary=True)
               logger.info(f"已成功建立数据库连接,数据库: {self.database}")
               return True
            else:
                logger.error(f"数据库连接关闭,数据库: {self.database}")
                return False

        except mysql.connector.Error as e:
            logger.error(f"数据库连接错误,异常原因 {e}")
            return False

    def dis_connect(self):
        """关闭数据库连接"""
        
        try:
            # 1. 关闭游标
            if self.cursor:
                self.cursor.close()
                self.cursor = None  # 重置为None，避免再次调用时出错

            # 2. 关闭连接
            if self.connection and self.connection.is_connected():
                self.connection.close()
                logger.info(f"已成功关闭数据库连接,数据库: {self.database}")
                self.connection = None  # 重置为None  ，避免再次调用时出错

        except mysql.connector.Error as e:
            logger.error(f"关闭数据库连接错误,异常原因 {e}")
            # 这里可以选择抛出异常或只是记录日志
            raise  # 如果要严格处理，可以抛出

    def __enter__(self):
        """定义上下文管理器__enter__方法"""

        if  self.connect():
            return self
        else:
            raise Exception("无法建立数据库连接")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """定义上下文管理器__exit__方法"""
        self.dis_connect()  # 直接调用，不检查返回值
        # __exit__ 不应该抛出新的异常，除非要覆盖原来的异常

```



##### ② 定义查询菜品列表函数

> 作用：查询menu_items（菜品）表的所有菜品信息，并且将每条记录拼接成完整字符串，最后合并为一个大字符串返回。向量数据库使用。

1. 获取数据库对象
2. 定义查询菜品SQL语句
3. 执行SQL获取结果
4. 遍历结果，处理菜品记录，合并所有菜品信息拼接成的完整字符串



db.tool.py文件代码片段如下：

```python
def get_all_menu_items() -> str:
    """
     获取所有菜单项
    Returns:
        str: 菜单项列表 所有菜品信息拼接成的完整字符串
    """

    try:
        with DataBaseConnection() as db:
            
            # 1. 定义查询语句
            query_sql = """
              SELECT 
                    id, dish_name, price, description, category, 
                    spice_level, flavor, main_ingredients, cooking_method, 
                    is_vegetarian, allergens, is_available
                FROM menu_items 
                WHERE is_available = 1
                ORDER BY category, dish_name
            """
            
            # 2. 执行查询语句
            db.cursor.execute(query_sql)

            # 3. 获取查询结果
            menu_items = db.cursor.fetchall()

            if not menu_items:
                return "当前没有找到任何菜品信息"

            # 4. 格式化输出
            menu_strings = []
            for item in menu_items:
                # 4.1 处理字符串类型的值
                # 菜品描述处理
                description_text = item.get('description', '') if item.get('description', '').strip() else "未知描述"
                # 过敏原处理
                allergens_text = item.get('allergens', '') if item.get('allergens', '').strip() else "无过敏原"
                # 处理主要食材
                main_ingredients_text = item.get('main_ingredients', '') if item.get('main_ingredients',
                                                                                     '').strip() else "未知食材"

                # 4.2 处理数字类型的值
                # 辣度转换
                spice_level = {"0": "不辣", "1": "微辣", "2": "中辣", "3": "重辣"}
                spice_text = spice_level.get(item["spice_level"], "未知辣度")

                # 4.3 处理布尔类型的值
                #  是否素食转换
                vegetarian_text = "是" if item['is_vegetarian'] else "否"

                # 4.4 拼接每个菜品的完整信息字符串
                menu_string = f"菜品ID:{item['id']}|菜品名称:{item['dish_name']}|价格:¥{item['price']:.2f}|菜品描述:{description_text}|分类:{item['category']}|辣度:{spice_text}|口味:{item['flavor']}|主要食材:{main_ingredients_text}|烹饪方法:{item['cooking_method']}|素食:{vegetarian_text}|过敏原:{allergens_text}"
                menu_strings.append(menu_string)

            # 将所有菜品信息用换行符连接成一个大字符串
            all_menu_info = "\n".join(menu_strings)
            logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_strings)}个")
            return all_menu_info
    except Exception as e:
        logger.error(f"查询菜品信息失败: {e}")
        return "查询菜品信息失败"

```



##### ③ 定义查询菜品字典函数

> 作用：查询menu_items（菜品）表的所有菜品信息，返回结构化的字典列表

1. 获取数据库对象
2.  定义查询菜品SQL语句
3. 执行SQL获取结果
4. 遍历结果，处理菜品记录，格式化为字典



db.tool.py文件代码片段如下：

```python
def  get_menu_items_list()->List[dict]:
    """
     获取所有菜单项
    Returns:
    List[dict]: 菜品信息的字典列表，每个字典包含完整的菜品信息
    """

    try:
        with DataBaseConnection() as db:
            
            # 1. 定义查询语句
            query_sql = """
                        SELECT 
                            id, dish_name, price, description, category, 
                            spice_level, flavor, main_ingredients, cooking_method, 
                            is_vegetarian, allergens, is_available
                        FROM menu_items 
                        WHERE is_available = 1
                        ORDER BY category, dish_name
                        """
            
            # 2. 执行查询语句
            db.cursor.execute(query_sql)
            
            # 3. 获取查询结果
            menu_items_result=db.cursor.fetchall()

            if  not  menu_items_result:
                logger.error(f"查询菜品信息失败: 没有找到任何菜品信息")
                return []

            # 4. 格式化输出
            menu_items = []
            for item in menu_items_result:
                # 辣度等级转换
                spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
                spice_text = spice_levels.get(item['spice_level'], "未知")

                # 处理数据
                processed_item = {
                    "id": item['id'],
                    "dish_name": item['dish_name'],
                    "price": float(item['price']),
                    "formatted_price": f"¥{item['price']:.2f}",
                    "description": item['description'] or "暂无描述",
                    "category": item['category'],
                    "spice_level": item['spice_level'],
                    "spice_text": spice_text,
                    "flavor": item['flavor'] or "暂无口味",
                    "main_ingredients": item['main_ingredients'] or "暂无主要食材",
                    "cooking_method": item['cooking_method'] or "暂无烹饪方法",
                    "is_vegetarian": bool(item['is_vegetarian']),
                    "vegetarian_text": "是" if item['is_vegetarian'] else "否",
                    "allergens": item['allergens'] if item['allergens'] and item['allergens'].strip() else "暂无过敏原",
                    "is_available": bool(item['is_available'])
                }
                menu_items.append(processed_item)

            logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_items)}个,并结构化菜品信息")
            return menu_items
    except Exception as e:
        logger.error(f"查询菜品结构化信息失败: {e}")
        return []
```



##### ④ 定义分类查询菜品函数

> 作用：按分类获取菜品信息，返回以分类为键的字典结构

1. 调用查询菜品函数
2. 构建分类字典结构



db.tool.py文件代码片段如下：

```python
def get_menu_items_by_category()->Dict[str,Any]:
    """
     通过分类获取菜单项
         Dict[str,Any]: 以分类为键，菜品列表为值的字典
    """

    try:
        # 1. 获取所有菜单项
        menu_items = get_menu_items_list()
        if  not   menu_items:
            logger.error("查询菜品信息失败")
            return {}

        # 2. 按照分类分组
        menu_items_by_category = {}
        for item in menu_items:
            category = item['category']
            if category not in menu_items_by_category:
                menu_items_by_category[category] = []
            menu_items_by_category[category].append(item)

        logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_items)}个,并已按分类分组")
        return  menu_items_by_category


    except Exception as e:
        logger.error(f"根据分类查询菜品信息失败: {e}")
        return {}

```



##### ⑤ 定义菜品id查询菜品函数

> 作用：根据菜品ID获取单个菜品信息

1. 获取数据库对象
2.  定义根据id查询菜品SQL语句
3. 执行SQL获取结果
4. 遍历结果，处理菜品记录，格式化为字典



db.tool.py文件代码片段如下：

```python
def  get_menu_item_by_id(item_id:str)->Dict[str,Any]:
    """
     通过ID获取菜单项
    Args:
        item_id: 菜品id

    Returns:
        Dict[str,Any]: 菜品信息的字典，包含完整的菜品信息
    """
    try:
        with DataBaseConnection() as db:
            
            # 1. 定义查询语句
            sql_query="""
            SELECT 
                id, dish_name, price, description, category, 
                spice_level, flavor, main_ingredients, cooking_method, 
                is_vegetarian, allergens, is_available
            FROM menu_items 
            WHERE id = %s AND is_available = 1
            """
            
            # 2. 执行查询语句
            db.cursor.execute(sql_query,(item_id,))

            # 3. 获取查询结果
            item=db.cursor.fetchone()
            if not item:
                logger.error(f"查询菜品ID{item_id}信息失败")
                return {}
                # 辣度等级转换
            spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
            spice_text = spice_levels.get(item['spice_level'], "未知")

            # 4. 处理数据
            processed_item = {
                "id": item['id'],
                "dish_name": item['dish_name'],
                "price": float(item['price']),
                "formatted_price": f"¥{item['price']:.2f}",
                "description": item['description'] or "暂无描述",
                "category": item['category'],
                "spice_level": item['spice_level'],
                "spice_text": spice_text,
                "flavor": item['flavor'] or "暂无口味",
                "main_ingredients": item['main_ingredients'] or "暂无主要食材",
                "cooking_method": item['cooking_method'] or "暂无烹饪方法",
                "is_vegetarian": bool(item['is_vegetarian']),
                "vegetarian_text": "是" if item['is_vegetarian'] else "否",
                "allergens": item['allergens'] if item['allergens'] and item['allergens'].strip() else "暂无过敏原",
                "is_available": bool(item['is_available'])
            }

            logger.info(f"已成功查询到菜品ID{item_id}信息")
            return processed_item

    except Exception as e:
        logger.error(f"查询菜品ID{item_id}信息失败: {e}")
        return  {}
```



##### ⑥ MySQL业务完整代码

```python

"""
数据库查询工具模块

该模块提供MySQL数据库连接和查询功能，
专门用于查询menu数据库中的menu_items表的全部信息
"""
from typing import List, Dict, Any
import mysql.connector
import logging
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataBaseConnection:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.host = os.getenv("MYSQL_HOST", "localhost")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD", "root")
        self.database = os.getenv("MYSQL_DATABASE", "menu")

    def connect(self) -> bool:

        """建立数据库连接"""

        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4"
            )
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(dictionary=True)
                logger.info(f"已成功建立数据库连接,数据库: {self.database}")
                return True
            else:
                logger.error(f"数据库连接关闭,数据库: {self.database}")
                return False

        except mysql.connector.Error as e:
            logger.error(f"数据库连接错误,异常原因 {e}")
            return False

    def dis_connect(self):
        """关闭数据库连接"""
        try:
            # 1. 关闭游标
            if self.cursor:
                self.cursor.close()
                self.cursor = None  # 重置为None，避免再次调用时出错

            # 2. 关闭连接
            if self.connection and self.connection.is_connected():
                self.connection.close()
                logger.info(f"已成功关闭数据库连接,数据库: {self.database}")
                self.connection = None  # 重置为None  ，避免再次调用时出错

        except mysql.connector.Error as e:
            logger.error(f"关闭数据库连接错误,异常原因 {e}")
            # 这里可以选择抛出异常或只是记录日志
            raise  # 如果要严格处理，可以抛出

    def __enter__(self):

        """定义上下文管理器__enter__方法"""

        if self.connect():
            return self
        else:
            raise Exception("无法建立数据库连接")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """定义上下文管理器__exit__方法"""
        self.dis_connect()  # 直接调用，不检查返回值
        # __exit__ 不应该抛出新的异常，除非要覆盖原来的异常


def get_all_menu_items() -> str:
    """
     获取所有菜单项
    Returns:
        str: 菜单项列表 所有菜品信息拼接成的完整字符串
    """

    try:
        with DataBaseConnection() as db:

            # 1. 定义查询语句
            query_sql = """
              SELECT 
                    id, dish_name, price, description, category, 
                    spice_level, flavor, main_ingredients, cooking_method, 
                    is_vegetarian, allergens, is_available
                FROM menu_items 
                WHERE is_available = 1
                ORDER BY category, dish_name
            """

            # 2. 执行查询语句
            db.cursor.execute(query_sql)

            # 3. 获取查询结果
            menu_items = db.cursor.fetchall()

            if not menu_items:
                return "当前没有找到任何菜品信息"

            # 3. 格式化输出
            menu_strings = []
            for item in menu_items:
                # 3.1 处理字符串类型的值
                # 菜品描述处理
                description_text = item.get('description', '') if item.get('description', '').strip() else "未知描述"
                # 过敏原处理
                allergens_text = item.get('allergens', '') if item.get('allergens', '').strip() else "无过敏原"
                # 处理主要食材
                main_ingredients_text = item.get('main_ingredients', '') if item.get('main_ingredients',
                                                                                     '').strip() else "未知食材"

                # 3.2 处理数字类型的值
                # 辣度转换
                spice_level = {"0": "不辣", "1": "微辣", "2": "中辣", "3": "重辣"}
                spice_text = spice_level.get(item["spice_level"], "未知辣度")

                # 3.3 处理布尔类型的值
                #  是否素食转换
                vegetarian_text = "是" if item['is_vegetarian'] else "否"

                # 3.4 拼接每个菜品的完整信息字符串
                menu_string = f"菜品ID:{item['id']}|菜品名称:{item['dish_name']}|价格:¥{item['price']:.2f}|菜品描述:{description_text}|分类:{item['category']}|辣度:{spice_text}|口味:{item['flavor']}|主要食材:{main_ingredients_text}|烹饪方法:{item['cooking_method']}|素食:{vegetarian_text}|过敏原:{allergens_text}"
                menu_strings.append(menu_string)

            # 将所有菜品信息用换行符连接成一个大字符串
            all_menu_info = "\n".join(menu_strings)
            logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_strings)}个")
            return all_menu_info
    except Exception as e:
        logger.error(f"查询菜品信息失败: {e}")
        return "查询菜品信息失败"


def  get_menu_items_list()->List[dict]:
    """
     获取所有菜单项
    Returns:
    List[dict]: 菜品信息的字典列表，每个字典包含完整的菜品信息
    """

    try:
        with DataBaseConnection() as db:

            # 1. 定义查询语句
            query_sql = """
                        SELECT 
                            id, dish_name, price, description, category, 
                            spice_level, flavor, main_ingredients, cooking_method, 
                            is_vegetarian, allergens, is_available
                        FROM menu_items 
                        WHERE is_available = 1
                        ORDER BY category, dish_name
                        """

            # 2. 执行查询语句
            db.cursor.execute(query_sql)

            # 3. 获取查询结果
            menu_items_result=db.cursor.fetchall()

            if  not  menu_items_result:
                logger.error(f"查询菜品信息失败: 没有找到任何菜品信息")
                return []

            # 4. 格式化输出
            menu_items = []
            for item in menu_items_result:
                # 辣度等级转换
                spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
                spice_text = spice_levels.get(item['spice_level'], "未知")

                # 处理数据
                processed_item = {
                    "id": item['id'],
                    "dish_name": item['dish_name'],
                    "price": float(item['price']),
                    "formatted_price": f"¥{item['price']:.2f}",
                    "description": item['description'] or "暂无描述",
                    "category": item['category'],
                    "spice_level": item['spice_level'],
                    "spice_text": spice_text,
                    "flavor": item['flavor'] or "暂无口味",
                    "main_ingredients": item['main_ingredients'] or "暂无主要食材",
                    "cooking_method": item['cooking_method'] or "暂无烹饪方法",
                    "is_vegetarian": bool(item['is_vegetarian']),
                    "vegetarian_text": "是" if item['is_vegetarian'] else "否",
                    "allergens": item['allergens'] if item['allergens'] and item['allergens'].strip() else "暂无过敏原",
                    "is_available": bool(item['is_available'])
                }
                menu_items.append(processed_item)

            logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_items)}个,并结构化菜品信息")
            return menu_items
    except Exception as e:
        logger.error(f"查询菜品结构化信息失败: {e}")
        return []

def  get_menu_item_by_id(item_id:str)->Dict[str,Any]:
    """
     通过ID获取菜单项
    Args:
        item_id: 菜品id

    Returns:
        Dict[str,Any]: 菜品信息的字典，包含完整的菜品信息
    """
    try:
        with DataBaseConnection() as db:

            # 1. 定义查询语句
            sql_query="""
            SELECT 
                id, dish_name, price, description, category, 
                spice_level, flavor, main_ingredients, cooking_method, 
                is_vegetarian, allergens, is_available
            FROM menu_items 
            WHERE id = %s AND is_available = 1
            """

            # 2. 执行查询语句
            db.cursor.execute(sql_query,(item_id,))

            # 3. 获取查询结果
            item=db.cursor.fetchone()
            if not item:
                logger.error(f"查询菜品ID{item_id}信息失败")
                return {}
                # 辣度等级转换
            spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
            spice_text = spice_levels.get(item['spice_level'], "未知")

            # 4. 处理数据
            processed_item = {
                "id": item['id'],
                "dish_name": item['dish_name'],
                "price": float(item['price']),
                "formatted_price": f"¥{item['price']:.2f}",
                "description": item['description'] or "暂无描述",
                "category": item['category'],
                "spice_level": item['spice_level'],
                "spice_text": spice_text,
                "flavor": item['flavor'] or "暂无口味",
                "main_ingredients": item['main_ingredients'] or "暂无主要食材",
                "cooking_method": item['cooking_method'] or "暂无烹饪方法",
                "is_vegetarian": bool(item['is_vegetarian']),
                "vegetarian_text": "是" if item['is_vegetarian'] else "否",
                "allergens": item['allergens'] if item['allergens'] and item['allergens'].strip() else "暂无过敏原",
                "is_available": bool(item['is_available'])
            }

            logger.info(f"已成功查询到菜品ID{item_id}信息")
            return processed_item

    except Exception as e:
        logger.error(f"查询菜品ID{item_id}信息失败: {e}")
        return  {}


def get_menu_items_by_category()->Dict[str,Any]:
    """
     通过分类获取菜单项
    Returns:
        Dict[str,Any]: 以分类为键，菜品列表为值的字典
    """

    try:
        # 1. 获取所有菜单项
        menu_items = get_menu_items_list()
        if  not   menu_items:
            logger.error("查询菜品信息失败")
            return {}

        # 2. 按照分类分组
        menu_items_by_category = {}
        for item in menu_items:
            category = item['category']
            if category not in menu_items_by_category:
                menu_items_by_category[category] = []
            menu_items_by_category[category].append(item)

        logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_items)}个,并已按分类分组")
        return  menu_items_by_category


    except Exception as e:
        logger.error(f"根据分类查询菜品信息失败: {e}")
        return {}

```



#### 3.1.2 测试各个功能

##### ① 测试数据库连接

##### ② 测试查询所有菜品

##### ③ 测试查询菜品字典

##### ④ 测试分类查询菜品

##### ⑤ 测试根据id查询菜品

##### ⑥ 测试业务完整代码

```python

def data_base_connection_test():
    """使用上下文管理器"""

    """使用上下文管理器"""
    try:
        with DataBaseConnection() as db:
            db.cursor.execute("SELECT 1")
            result = db.cursor.fetchone()

            if result:
                logger.info(f"数据库查询成功,结果: {result}")
                return True
            else:
                logger.error("数据库查询失败")
                return False

    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
        return False


if __name__ == '__main__':

    # 测试连接
    print("\n1. 测试数据库连接...")
    if data_base_connection_test():
        print("数据库操作成功")


    print("\n2. 测试获取所有菜单项...")
    results=get_all_menu_items()
    if results and not  results.startswith("查询菜品信息失败") or not  results.startswith("当前没有"):
        results = results.split("\n")
        for index,menu_item in enumerate(results,1):
            print(f"{index}号菜品'字符串'结构完整信息: {menu_item}")

    print("\n3. 测试获取所有菜单项列表...")
    results=get_menu_items_list()
    if results:
        for index,menu_item in enumerate(results,1):
            print(f"{index}号菜品'字典'结构完整信息: {menu_item}")


    print("\n4. 测试通过ID获取菜单项...")
    test_item_ids=["1","2","3","4","5"]
    if results:
        for index,item_id in enumerate(test_item_ids,1):
            print(f"{index}号ID菜品'字典'结构完整信息: {get_menu_item_by_id(item_id)}")

    print("\n5. 测试通过分类获取菜单项...")
    results = get_menu_items_by_category()
    if results:
        for category, menu_items in results.items():
            print(f"\n{'='*60}")
            print(f"分类: {category}")
            print(f"菜品数量: {len(menu_items)}个")
            print(f"{'=' * 60}")
            for index, menu_item in enumerate(menu_items, 1):
                print(f"{index}号菜品.完整信息{menu_item}")

```



#### 3.1.3 文件完整代码

```python
from typing import List, Dict, Any
import mysql.connector
import logging
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataBaseConnection:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.host = os.getenv("MYSQL_HOST", "localhost")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD", "root")
        self.database = os.getenv("MYSQL_DATABASE", "menu")

    def connect(self) -> bool:

        """建立数据库连接"""

        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4"
            )
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(dictionary=True)
                logger.info(f"已成功建立数据库连接,数据库: {self.database}")
                return True
            else:
                logger.error(f"数据库连接关闭,数据库: {self.database}")
                return False

        except mysql.connector.Error as e:
            logger.error(f"数据库连接错误,异常原因 {e}")
            return False

    def dis_connect(self):
        """关闭数据库连接"""
        try:
            # 1. 关闭游标
            if self.cursor:
                self.cursor.close()
                self.cursor = None  # 重置为None，避免再次调用时出错

            # 2. 关闭连接
            if self.connection and self.connection.is_connected():
                self.connection.close()
                logger.info(f"已成功关闭数据库连接,数据库: {self.database}")
                self.connection = None  # 重置为None  ，避免再次调用时出错

        except mysql.connector.Error as e:
            logger.error(f"关闭数据库连接错误,异常原因 {e}")
            # 这里可以选择抛出异常或只是记录日志
            raise  # 如果要严格处理，可以抛出

    def __enter__(self):

        """定义上下文管理器__enter__方法"""

        if self.connect():
            return self
        else:
            raise Exception("无法建立数据库连接")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """定义上下文管理器__exit__方法"""
        self.dis_connect()  # 直接调用，不检查返回值
        # __exit__ 不应该抛出新的异常，除非要覆盖原来的异常


def get_all_menu_items() -> str:
    """
     获取所有菜单项
    Returns:
        str: 菜单项列表 所有菜品信息拼接成的完整字符串
    """

    try:
        with DataBaseConnection() as db:

            # 1. 定义查询语句
            query_sql = """
              SELECT 
                    id, dish_name, price, description, category, 
                    spice_level, flavor, main_ingredients, cooking_method, 
                    is_vegetarian, allergens, is_available
                FROM menu_items 
                WHERE is_available = 1
                ORDER BY category, dish_name
            """

            # 2. 执行查询语句
            db.cursor.execute(query_sql)

            # 3. 获取查询结果
            menu_items = db.cursor.fetchall()

            if not menu_items:
                return "当前没有找到任何菜品信息"

            # 3. 格式化输出
            menu_strings = []
            for item in menu_items:
                # 3.1 处理字符串类型的值
                # 菜品描述处理
                description_text = item.get('description', '') if item.get('description', '').strip() else "未知描述"
                # 过敏原处理
                allergens_text = item.get('allergens', '') if item.get('allergens', '').strip() else "无过敏原"
                # 处理主要食材
                main_ingredients_text = item.get('main_ingredients', '') if item.get('main_ingredients',
                                                                                     '').strip() else "未知食材"

                # 3.2 处理数字类型的值
                # 辣度转换
                spice_level = {"0": "不辣", "1": "微辣", "2": "中辣", "3": "重辣"}
                spice_text = spice_level.get(item["spice_level"], "未知辣度")

                # 3.3 处理布尔类型的值
                #  是否素食转换
                vegetarian_text = "是" if item['is_vegetarian'] else "否"

                # 3.4 拼接每个菜品的完整信息字符串
                menu_string = f"菜品ID:{item['id']}|菜品名称:{item['dish_name']}|价格:¥{item['price']:.2f}|菜品描述:{description_text}|分类:{item['category']}|辣度:{spice_text}|口味:{item['flavor']}|主要食材:{main_ingredients_text}|烹饪方法:{item['cooking_method']}|素食:{vegetarian_text}|过敏原:{allergens_text}"
                menu_strings.append(menu_string)

            # 将所有菜品信息用换行符连接成一个大字符串
            all_menu_info = "\n".join(menu_strings)
            logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_strings)}个")
            return all_menu_info
    except Exception as e:
        logger.error(f"查询菜品信息失败: {e}")
        return "查询菜品信息失败"


def  get_menu_items_list()->List[dict]:
    """
     获取所有菜单项
    Returns:
    List[dict]: 菜品信息的字典列表，每个字典包含完整的菜品信息
    """

    try:
        with DataBaseConnection() as db:

            # 1. 定义查询语句
            query_sql = """
                        SELECT 
                            id, dish_name, price, description, category, 
                            spice_level, flavor, main_ingredients, cooking_method, 
                            is_vegetarian, allergens, is_available
                        FROM menu_items 
                        WHERE is_available = 1
                        ORDER BY category, dish_name
                        """

            # 2. 执行查询语句
            db.cursor.execute(query_sql)

            # 3. 获取查询结果
            menu_items_result=db.cursor.fetchall()

            if  not  menu_items_result:
                logger.error(f"查询菜品信息失败: 没有找到任何菜品信息")
                return []

            # 4. 格式化输出
            menu_items = []
            for item in menu_items_result:
                # 辣度等级转换
                spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
                spice_text = spice_levels.get(item['spice_level'], "未知")

                # 处理数据
                processed_item = {
                    "id": item['id'],
                    "dish_name": item['dish_name'],
                    "price": float(item['price']),
                    "formatted_price": f"¥{item['price']:.2f}",
                    "description": item['description'] or "暂无描述",
                    "category": item['category'],
                    "spice_level": item['spice_level'],
                    "spice_text": spice_text,
                    "flavor": item['flavor'] or "暂无口味",
                    "main_ingredients": item['main_ingredients'] or "暂无主要食材",
                    "cooking_method": item['cooking_method'] or "暂无烹饪方法",
                    "is_vegetarian": bool(item['is_vegetarian']),
                    "vegetarian_text": "是" if item['is_vegetarian'] else "否",
                    "allergens": item['allergens'] if item['allergens'] and item['allergens'].strip() else "暂无过敏原",
                    "is_available": bool(item['is_available'])
                }
                menu_items.append(processed_item)

            logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_items)}个,并结构化菜品信息")
            return menu_items
    except Exception as e:
        logger.error(f"查询菜品结构化信息失败: {e}")
        return []

def  get_menu_item_by_id(item_id:str)->Dict[str,Any]:
    """
     通过ID获取菜单项
    Args:
        item_id: 菜品id

    Returns:
        Dict[str,Any]: 菜品信息的字典，包含完整的菜品信息
    """
    try:
        with DataBaseConnection() as db:

            # 1. 定义查询语句
            sql_query="""
            SELECT 
                id, dish_name, price, description, category, 
                spice_level, flavor, main_ingredients, cooking_method, 
                is_vegetarian, allergens, is_available
            FROM menu_items 
            WHERE id = %s AND is_available = 1
            """

            # 2. 执行查询语句
            db.cursor.execute(sql_query,(item_id,))

            # 3. 获取查询结果
            item=db.cursor.fetchone()
            if not item:
                logger.error(f"查询菜品ID{item_id}信息失败")
                return {}
                # 辣度等级转换
            spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
            spice_text = spice_levels.get(item['spice_level'], "未知")

            # 4. 处理数据
            processed_item = {
                "id": item['id'],
                "dish_name": item['dish_name'],
                "price": float(item['price']),
                "formatted_price": f"¥{item['price']:.2f}",
                "description": item['description'] or "暂无描述",
                "category": item['category'],
                "spice_level": item['spice_level'],
                "spice_text": spice_text,
                "flavor": item['flavor'] or "暂无口味",
                "main_ingredients": item['main_ingredients'] or "暂无主要食材",
                "cooking_method": item['cooking_method'] or "暂无烹饪方法",
                "is_vegetarian": bool(item['is_vegetarian']),
                "vegetarian_text": "是" if item['is_vegetarian'] else "否",
                "allergens": item['allergens'] if item['allergens'] and item['allergens'].strip() else "暂无过敏原",
                "is_available": bool(item['is_available'])
            }

            logger.info(f"已成功查询到菜品ID{item_id}信息")
            return processed_item

    except Exception as e:
        logger.error(f"查询菜品ID{item_id}信息失败: {e}")
        return  {}


def get_menu_items_by_category()->Dict[str,Any]:
    """
     通过分类获取菜单项
    Returns:
        Dict[str,Any]: 以分类为键，菜品列表为值的字典
    """

    try:
        # 1. 获取所有菜单项
        menu_items = get_menu_items_list()
        if  not   menu_items:
            logger.error("查询菜品信息失败")
            return {}

        # 2. 按照分类分组
        menu_items_by_category = {}
        for item in menu_items:
            category = item['category']
            if category not in menu_items_by_category:
                menu_items_by_category[category] = []
            menu_items_by_category[category].append(item)

        logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_items)}个,并已按分类分组")
        return  menu_items_by_category


    except Exception as e:
        logger.error(f"根据分类查询菜品信息失败: {e}")
        return {}




def data_base_connection_test():
    """使用上下文管理器"""

    """使用上下文管理器"""
    try:
        with DataBaseConnection() as db:
            db.cursor.execute("SELECT 1")
            result = db.cursor.fetchone()

            if result:
                logger.info(f"数据库查询成功,结果: {result}")
                return True
            else:
                logger.error("数据库查询失败")
                return False

    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
        return False


if __name__ == '__main__':

    # 测试连接
    print("\n1. 测试数据库连接...")
    if data_base_connection_test():
        print("数据库操作成功")


    print("\n2. 测试获取所有菜单项...")
    results=get_all_menu_items()
    if results and not  results.startswith("查询菜品信息失败") or not  results.startswith("当前没有"):
        results = results.split("\n")
        for index,menu_item in enumerate(results,1):
            print(f"{index}号菜品'字符串'结构完整信息: {menu_item}")

    print("\n3. 测试获取所有菜单项列表...")
    results=get_menu_items_list()
    if results:
        for index,menu_item in enumerate(results,1):
            print(f"{index}号菜品'字典'结构完整信息: {menu_item}")


    print("\n4. 测试通过ID获取菜单项...")
    test_item_ids=["1","2","3","4","5"]
    if results:
        for index,item_id in enumerate(test_item_ids,1):
            print(f"{index}号ID菜品'字典'结构完整信息: {get_menu_item_by_id(item_id)}")

    print("\n5. 测试通过分类获取菜单项...")
    results = get_menu_items_by_category()
    if results:
        for category, menu_items in results.items():
            print(f"\n{'='*60}")
            print(f"分类: {category}")
            print(f"菜品数量: {len(menu_items)}个")
            print(f"{'=' * 60}")
            for index, menu_item in enumerate(menu_items, 1):
                print(f"{index}号菜品.完整信息{menu_item}")

```



### 3.2 定义向量数据库业务工具

> 向量数据库选择：Pinecone

#### 3.2.1 新建pinecone_tool文件

> 模块作用：该模块提供Pinecone向量数据库的连接和操作功能，用于存储和查询菜品信息的向量化数据，支持语义搜索

##### ① 定义向量数据库类

1. 定义构造函数，配置pinecone信息(key、服务器地址、索引名称、嵌入模型、维度、各个组件实例)
2. 定义初始化函数，初始化Pinecone连接、索引
3. 定义DashScope生成文本向量函数，返回嵌入模型向量结果
4.  定义将MySQL菜品数据批量插入向量数据库函数
5. 定义从数据库获取菜单函数（类的内部使用）
6. 定义验证菜单数据有效性（类的内部使用）
7. 定义文本分割函数（类的内部使用）
8. 定义根据查询文本搜索相似的菜品函数
9. 定义删除向量数据库所有菜品向量数据函数



pinecone_tool.py文件代码片段如下：

```python
class PineconeVectorDB:
    """Pinecone向量数据库管理类"""

    def __init__(self):
        """初始化Pinecone连接配置"""
        # 1. 配置环境变量
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.pinecone_env = os.getenv("PINECONE_ENV", "us-east-1")

        # 2.  配置向量数据库参数
        self.index_name = "menu-items1"  # 菜品索引名称
        self.model_name = "text-embedding-v4"  # DashScope嵌入模型
        self.dimension = 1536  # 向量维度

        # 3. 初始化Pinecone连接和索引
        self.pc = None
        self.index = None



    def initialize(self) -> bool:
        """
        初始化Pinecone连接和索引

        Returns:
            同步结果 bool (true:成功 false:失败)
        """
        try:
            # 1. 初始化Pinecone客户端
            if not self.pinecone_api_key:
                return False

            # 2. 初始化DashScope客户端
            self.pc = Pinecone(api_key=self.pinecone_api_key)

            # 3. 创建或连接索引
            if not self.pc.has_index(self.index_name):
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=self.pinecone_env
                    )
                )

            # 4. 获取索引对象
            self.index = self.pc.Index(self.index_name)
            return True

        except Exception as e:
            logger.error(f"初始化Pinecone连接失败,原因: {e}")
            return False

    def get_dashscope_embedding(self, text: str) -> List[float]:
        """
        使用DashScope生成文本向量

        Args:
            text:str:  输入的文本

        Returns:
            List[float]: 生成的向量
        """
        try:

            #  1. 初始化DashScope客户端 指定嵌入模型名称和维度
            resp = dashscope.TextEmbedding.call(
                model=self.model_name,
                input=text,
                dimension=self.dimension
            )

            # 2. 判断响应状态码是否为200
            if resp.status_code == 200:
                embedding = resp["output"]["embeddings"][0]["embedding"]
                return embedding
            else:
                return []

        except Exception as e:
            logger.error(f"生成文本向量失败,原因: {e}")
            return []

    def upsert_menu_data(self, menu_data: str = None, batch_size: int = 100, clear_existing: bool = True) -> bool:
        """
         菜品数据批量插入方法

        Args:
            menu_data:str:  菜品数据字符串
            batch_size:int: 批量大小
            clear_existing:bool: 是否清除现有pinecone中向量数据

        Returns:
            同步结果 bool (true:成功 false:失败)
        """
        try:
            # 1. 初始化检查
            if not self.index and not self.initialize():
                return False

            # 2. 清除现有数据
            if clear_existing:
                self.delete_all_items_vector_data()

            # 3.读取数据库数据
            if menu_data is None:
                menu_data = self._get_menu_data_from_db()
                if not self._is_valid_menu_data(menu_data):
                    return False

            # 4. 切割加载数据
            lines = self._split_menu_data(menu_data)
            if not lines:
                return False

            # 5. 批量处理
            batch = []
            for line_num, line in enumerate(lines, 1):

                # 5.1  获取每一个文档向量
                vector = self.get_dashscope_embedding(line)

                # 5.2  判断向量是否有效
                if vector and len(vector) == self.dimension:

                    # 5.3  构建向量元数据
                    metadata = {
                        "content": line,
                        "line_number": line_num,
                        "type": "menu_item",
                    }
                    record_id = f"menu_{line_num}"

                    # 5.4  添加到批量列表
                    batch.append((record_id, vector, metadata))

                    #  5.5  批量同步到Pinecone
                    if len(batch) >= batch_size:
                        self.index.upsert(vectors=batch)
                        batch = []

            # 处理不够以及剩余数据
            if batch:
                self.index.upsert(vectors=batch)
            return True

        except Exception as e:
            logger.error(f"批量同步数据失败,原因: {e}")
            return False


    def _get_menu_data_from_db(self) -> str:
        """
        从数据库获取菜单数据

        Returns:
            str: 菜品数据字符串
        """
        try:
            from db_tool import get_all_menu_items
            return get_all_menu_items()
        except Exception as e:
            logger.error(f"获取菜单数据失败,原因: {e}")
            return ""

    def _is_valid_menu_data(self, menu_data: str) -> bool:
        """
        验证菜单数据有效性

        Args:
            menu_data:  str:  菜品数据字符串

        Returns:
            验证结果 bool: 有效性
        """
        if not menu_data:
            return False
        invalid_prefixes = ("当前没有", "查询失败")
        return not menu_data.startswith(invalid_prefixes)


    def _split_menu_data(self, menu_data: str) -> List[str]:
        """
         文本分割逻辑

        Args:
            menu_data: str:  菜品数据字符串

        Returns:
            List[str]: 分割后的文本列表
        """
        try:
            # 1. 定义文本分割器
            text_splitter = CharacterTextSplitter(
                separator="\n",  # 按\n分割
                chunk_size=150,  # 每个块的最大字符数
                chunk_overlap=0,  # 块之间的重叠字符数
                length_function=len
            )

            #  2. 分割文本
            dcos = text_splitter.create_documents(texts=[menu_data])
            final_dcos = []

            # 3. 处理分割结果
            for doc in dcos:
                line = doc.page_content.strip()
                final_dcos.append(line)
            return final_dcos
        except  Exception as e:
            logger.error(f"文本分割失败,原因: {e}")
            return []

    def   similar_search_items(self,query:str,top_k:int=2)-> list[Any] | list[dict[str, Any]] | None:
        """
         根据查询文本搜索相似的菜品

        Args:
            query:str: 输入的查询文本
            top_k:int: 返回的结果数量

        Returns:
            List[Dict[str,Any]] or List[Any]: 包含相似菜品信息的列表

        """
        try:
            # 1. 判断向量数据库是否初始化
            if  not self.index and not self.initialize():
                    return  []

            # 2. 获取查询文本的向量
            query_vector=self.get_dashscope_embedding(query)
            if not query_vector or len(query_vector)!= self.dimension :
                return  []

            # 3. 向量检索
            result=self.index.query(vector=query_vector,top_k=top_k,include_metadata=True)

            # 4. 处理结果
            similar_result=[]
            for  item  in  result['matches']:
               match_item={
                   "id": item['id'],
                   "score":item['score'],
                   "content":item['metadata']['content'],
                   "line_number":item['metadata']['line_number']
               }
               similar_result.append(match_item)
            return  similar_result
        except Exception as e:
            logger.error(f"查询向量库索引: {self.index}向量数据失败,原因：{e}")
            return  []


    def   delete_all_items_vector_data(self)->bool:
        """
        删除向量数据库所有向量数据

        Returns:
            删除结果 bool: (true:成功 false:失败)
        """

        try:
            # 1. 判断向量数据库是否初始化
            if  not  self.index and not self.initialize():
                    return  False

            # 2. 获取所有索引信息
            stats=self.index.describe_index_stats()
            count=stats.total_vector_count

            if  count==0:
                return True

            # 4. 删除所有向量数据
            self.index.delete(delete_all=True)
            return  True
        except Exception as e:
            logger.error(f"删除向量库索引: {self.index}向量数据失败: 原因：{e}")
            return  False

```

##### ② 定义pinecone全局实例

```python
vector_db = PineconeVectorDB()
```



##### ③ 定义初始化函数

> 作用：初始化Pinecone连接和索引，用于外部模块直接导入使用

- 调用pinecone全局实例的initialize函数

pinecone_tool.py文件代码片段如下：

```python
def pinecone_connection() -> bool:
    """测试Pinecone连接"""
    return vector_db.initialize()
```



##### ④ 定义数据同步函数

> 作用：将菜品数据输入到Pinecone向量数据库，用于外部模块直接导入使用

- 调用pinecone全局实例的upsert_menu_data函数



pinecone_tool.py文件代码片段如下：

```python
def pinecone_input(menu_data: str = None, clear_existing: bool = True) -> bool:
    """
    将菜品数据输入到Pinecone向量数据库
    
    Args:
        menu_data: 菜品数据字符串，每行一个菜品的完整信息。如果为None，则从数据库获取
        clear_existing: 是否在插入前清除现有数据，默认为True
        
    Returns:
        bool: 是否输入成功
    """
    return vector_db.upsert_menu_data(menu_data, clear_existing=clear_existing)
```



##### ⑤  定义搜索相关菜品函数

> 作用：根据查询搜索相关菜品，用于外部模块直接导入使用

- 调用pinecone全局实例的search_similar_items函数



pinecone_tool.py文件代码片段如下：

```python
def search_menu_items(query: str, top_k: int = 2) -> List[str]:
    """
    根据查询搜索相关菜品
    
    Args:
        query: 查询文本
        top_k: 返回结果数量
        
    Returns:
        List[str]: 相关菜品信息列表
    """
    results = vector_db.search_similar_items(query, top_k)
    return [item["content"] for item in results]
```



##### ⑥ 定义搜索相关菜品信息函数

> 作用：根据查询搜索相关菜品，返回包含菜品内容列表和真实菜品ID列表以及分数值的字典，用于外部模块直接导入使用

- 调用pinecone全局实例的similar_search_items函数
- 提取菜品id
- 处理数据，构建返回数据结构字典



pinecone_tool.py文件代码片段如下：

```python
def search_menu_items_with_id(query: str, top_k: int = 2) -> Dict[str, Any]:
    """
     根据查询文本搜索相似的菜品
    Args:
        query: str: 查询文本
        top_k: int: 返回的结果数量

    Returns:
        Dict[str,Any]:包含菜品内容列表和真实菜品ID列表的字典
        {
            "contents": [菜品内容列表],
            "ids": [真实菜品ID列表],
            "scores": [相似度分数列表]
        }
    """

    try:
        import re

        #  1. 查询相似性菜品信息
        similar_result = vector_db.similar_search_items(query=query, top_k=top_k)

        if not similar_result:
            return {}

        # 2. 处理相似性检索结果
        item_ids = []
        for item in similar_result:
            content = item['content']
            match = re.search(r'菜品ID:(\d+)', content)
            if match:
                item_ids.append(match.group(1))
            else:
                item_ids.append(item["id"])

        # 3. 返回结果
        return {
            "contents": [item['content'] for item in similar_result],
            "ids": item_ids,
            "scores": [item['score'] for item in similar_result]
        }
    except Exception as e:
        logger.error(f"查询相似性菜品信息带id失败: {e}")
        return {}

```







##### ⑦  Pinecone业务完整代码

```python

"""
Pinecone向量数据库工具模块

该模块提供Pinecone向量数据库的连接和操作功能，
用于存储和查询菜品信息的向量化数据，支持语义搜索
"""

import os
import dashscope
from typing import List, Dict, Any
from pinecone import Pinecone
from pinecone.models import ServerlessSpec
from langchain.text_splitter import CharacterTextSplitter

from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PineconeVectorDB:
    """Pinecone向量数据库管理类"""

    def __init__(self):
        """初始化Pinecone连接配置"""
        # 1. 配置环境变量
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.pinecone_env = os.getenv("PINECONE_ENV", "us-east-1")

        # 2.  配置向量数据库参数
        self.index_name = "menu-items1"  # 菜品索引名称
        self.model_name = "text-embedding-v4"  # DashScope嵌入模型
        self.dimension = 1536  # 向量维度

        # 3. 初始化Pinecone连接和索引
        self.pc = None
        self.index = None



    def initialize(self) -> bool:
        """
        初始化Pinecone连接和索引

        Returns:
            同步结果 bool (true:成功 false:失败)
        """
        try:
            # 1. 初始化Pinecone客户端
            if not self.pinecone_api_key:
                return False

            # 2. 初始化DashScope客户端
            self.pc = Pinecone(api_key=self.pinecone_api_key)

            # 3. 创建或连接索引
            if not self.pc.has_index(self.index_name):
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=self.pinecone_env
                    )
                )

            # 4. 获取索引对象
            self.index = self.pc.Index(self.index_name)
            return True

        except Exception as e:
            logger.error(f"初始化Pinecone连接失败,原因: {e}")
            return False

    def get_dashscope_embedding(self, text: str) -> List[float]:
        """
        使用DashScope生成文本向量

        Args:
            text:str:  输入的文本

        Returns:
            List[float]: 生成的向量
        """
        try:

            #  1. 初始化DashScope客户端 指定嵌入模型名称和维度
            resp = dashscope.TextEmbedding.call(
                model=self.model_name,
                input=text,
                dimension=self.dimension
            )

            # 2. 判断响应状态码是否为200
            if resp.status_code == 200:
                embedding = resp["output"]["embeddings"][0]["embedding"]
                return embedding
            else:
                return []

        except Exception as e:
            logger.error(f"生成文本向量失败,原因: {e}")
            return []

    def upsert_menu_data(self, menu_data: str = None, batch_size: int = 100, clear_existing: bool = True) -> bool:
        """
         菜品数据批量插入方法

        Args:
            menu_data:str:  菜品数据字符串
            batch_size:int: 批量大小
            clear_existing:bool: 是否清除现有pinecone中向量数据

        Returns:
            同步结果 bool (true:成功 false:失败)
        """
        try:
            # 1. 初始化检查
            if not self.index and not self.initialize():
                return False

            # 2. 清除现有数据
            if clear_existing:
                self.delete_all_items_vector_data()

            # 3.读取数据库数据
            if menu_data is None:
                menu_data = self._get_menu_data_from_db()
                if not self._is_valid_menu_data(menu_data):
                    return False

            # 4. 切割加载数据
            lines = self._split_menu_data(menu_data)
            if not lines:
                return False

            # 5. 批量处理
            batch = []
            for line_num, line in enumerate(lines, 1):

                # 5.1  获取每一个文档向量
                vector = self.get_dashscope_embedding(line)

                # 5.2  判断向量是否有效
                if vector and len(vector) == self.dimension:

                    # 5.3  构建向量元数据
                    metadata = {
                        "content": line,
                        "line_number": line_num,
                        "type": "menu_item",
                    }
                    record_id = f"menu_{line_num}"

                    # 5.4  添加到批量列表
                    batch.append((record_id, vector, metadata))

                    #  5.5  批量同步到Pinecone
                    if len(batch) >= batch_size:
                        self.index.upsert(vectors=batch)
                        batch = []

            # 处理不够以及剩余数据
            if batch:
                self.index.upsert(vectors=batch)
            return True

        except Exception as e:
            logger.error(f"批量同步数据失败,原因: {e}")
            return False


    def _get_menu_data_from_db(self) -> str:
        """
        从数据库获取菜单数据

        Returns:
            str: 菜品数据字符串
        """
        try:
            from db_tool import get_all_menu_items
            return get_all_menu_items()
        except Exception as e:
            logger.error(f"获取菜单数据失败,原因: {e}")
            return ""

    def _is_valid_menu_data(self, menu_data: str) -> bool:
        """
        验证菜单数据有效性

        Args:
            menu_data:  str:  菜品数据字符串

        Returns:
            验证结果 bool: 有效性
        """
        if not menu_data:
            return False
        invalid_prefixes = ("当前没有", "查询失败")
        return not menu_data.startswith(invalid_prefixes)


    def _split_menu_data(self, menu_data: str) -> List[str]:
        """
         文本分割逻辑

        Args:
            menu_data: str:  菜品数据字符串

        Returns:
            List[str]: 分割后的文本列表
        """
        try:
            # 1. 定义文本分割器
            text_splitter = CharacterTextSplitter(
                separator="\n",  # 按\n分割
                chunk_size=150,  # 每个块的最大字符数
                chunk_overlap=0,  # 块之间的重叠字符数
                length_function=len
            )

            #  2. 分割文本
            dcos = text_splitter.create_documents(texts=[menu_data])
            final_dcos = []

            # 3. 处理分割结果
            for doc in dcos:
                line = doc.page_content.strip()
                final_dcos.append(line)
            return final_dcos
        except  Exception as e:
            logger.error(f"文本分割失败,原因: {e}")
            return []

    def   similar_search_items(self,query:str,top_k:int=2)-> list[Any] | list[dict[str, Any]] | None:
        """
         根据查询文本搜索相似的菜品

        Args:
            query:str: 输入的查询文本
            top_k:int: 返回的结果数量

        Returns:
            List[Dict[str,Any]] or List[Any]: 包含相似菜品信息的列表

        """
        try:
            # 1. 判断向量数据库是否初始化
            if  not self.index and not self.initialize():
                    return  []

            # 2. 获取查询文本的向量
            query_vector=self.get_dashscope_embedding(query)
            if not query_vector or len(query_vector)!= self.dimension :
                return  []

            # 3. 向量检索
            result=self.index.query(vector=query_vector,top_k=top_k,include_metadata=True)

            # 4. 处理结果
            similar_result=[]
            for  item  in  result['matches']:
               match_item={
                   "id": item['id'],
                   "score":item['score'],
                   "content":item['metadata']['content'],
                   "line_number":item['metadata']['line_number']
               }
               similar_result.append(match_item)
            return  similar_result
        except Exception as e:
            logger.error(f"查询向量库索引: {self.index}向量数据失败,原因：{e}")
            return  []


    def   delete_all_items_vector_data(self)->bool:
        """
        删除向量数据库所有向量数据

        Returns:
            删除结果 bool: (true:成功 false:失败)
        """

        try:
            # 1. 判断向量数据库是否初始化
            if  not  self.index and not self.initialize():
                    return  False

            # 2. 获取所有索引信息
            stats=self.index.describe_index_stats()
            count=stats.total_vector_count

            if  count==0:
                return True

            # 4. 删除所有向量数据
            self.index.delete(delete_all=True)
            return  True
        except Exception as e:
            logger.error(f"删除向量库索引: {self.index}向量数据失败: 原因：{e}")
            return  False


# 全局实例
vector_db = PineconeVectorDB()

def pinecone_connection() -> bool:
    """
     连接Pinecone向量数据库

    Returns:
        bool: 是否连接成功 true:成功 false:失败
    """
    return vector_db.initialize()


def sync_pinecone_data_from_database() -> bool:
    """
     从数据库同步数据到Pinecone向量数据库
    Returns:
        bool: 是否同步成功 true:成功 false:失败

    """
    return vector_db.upsert_menu_data(menu_data=None, clear_existing=True)


def search_menu_items_with_id(query: str, top_k: int = 2) -> Dict[str, Any]:
    """
     根据查询文本搜索相似的菜品
    Args:
        query: str: 查询文本
        top_k: int: 返回的结果数量

    Returns:
        Dict[str,Any]:包含菜品内容列表和真实菜品ID列表的字典
        {
            "contents": [菜品内容列表],
            "ids": [真实菜品ID列表],
            "scores": [相似度分数列表]
        }
    """

    try:
        import re

        #  1. 查询相似性菜品信息
        similar_result = vector_db.similar_search_items(query=query, top_k=top_k)

        if not similar_result:
            return {}

        # 2. 处理相似性检索结果
        item_ids = []
        for item in similar_result:
            content = item['content']
            match = re.search(r'菜品ID:(\d+)', content)
            if match:
                item_ids.append(match.group(1))
            else:
                item_ids.append(item["id"])

        # 3. 返回结果
        return {
            "contents": [item['content'] for item in similar_result],
            "ids": item_ids,
            "scores": [item['score'] for item in similar_result]
        }
    except Exception as e:
        logger.error(f"查询相似性菜品信息带id失败: {e}")
        return {}



```



#### 3.2.2 测试各个功能

##### ① 测试PineCone连接

##### ② 测试数据同步

##### ③ 测试查询相似性菜品信息

##### ④ 测试查询相似性菜品信息带id

##### ⑤ 测试业务完整代码

```python
    # 1. 测试Pinecone连接
    print("\n1.测试Pinecone连接...")
    if  pinecone_connection():
         print("Pinecone连接成功...")

    # 2. 测试执行数据同步：删除现有数据并从数据库重新上传
    print("\n2.测试正在同步数据...")
    sync_result=sync_pinecone_data_from_database()
    if  sync_result:
         print("数据同步成功...")


    # 3. 测试查询相似性菜品信息
    print("\n3.测试查询相似性菜品信息...")
    similar_search_result=vector_db.similar_search_items(query="我想点川菜",top_k=2)

    if similar_search_result:
       for item in similar_search_result:
           print(f"相似菜品: {item['content']}，相似度: {item['score']}")

    #  4. 测试查询相似性菜品信息带id
    print("\n4.测试查询相似性菜品信息带id...")
    similar_search_result=search_menu_items_with_id(query="我想点川菜",top_k=2)
    if  similar_search_result:
         print(f"相似菜品: {similar_search_result['contents']}，相似度: {similar_search_result['scores'],}，真实ID: {similar_search_result['ids']}")

```



#### 3.2.3 文件完整代码

```python

"""
Pinecone向量数据库工具模块

该模块提供Pinecone向量数据库的连接和操作功能，
用于存储和查询菜品信息的向量化数据，支持语义搜索
"""

import os
import dashscope
from typing import List, Dict, Any
from pinecone import Pinecone
from pinecone.models import ServerlessSpec
from langchain.text_splitter import CharacterTextSplitter

from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PineconeVectorDB:
    """Pinecone向量数据库管理类"""

    def __init__(self):
        """初始化Pinecone连接配置"""
        # 1. 配置环境变量
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.pinecone_env = os.getenv("PINECONE_ENV", "us-east-1")

        # 2.  配置向量数据库参数
        self.index_name = "menu-items1"  # 菜品索引名称
        self.model_name = "text-embedding-v4"  # DashScope嵌入模型
        self.dimension = 1536  # 向量维度

        # 3. 初始化Pinecone连接和索引
        self.pc = None
        self.index = None



    def initialize(self) -> bool:
        """
        初始化Pinecone连接和索引

        Returns:
            同步结果 bool (true:成功 false:失败)
        """
        try:
            # 1. 初始化Pinecone客户端
            if not self.pinecone_api_key:
                return False

            # 2. 初始化DashScope客户端
            self.pc = Pinecone(api_key=self.pinecone_api_key)

            # 3. 创建或连接索引
            if not self.pc.has_index(self.index_name):
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=self.pinecone_env
                    )
                )

            # 4. 获取索引对象
            self.index = self.pc.Index(self.index_name)
            return True

        except Exception as e:
            logger.error(f"初始化Pinecone连接失败,原因: {e}")
            return False

    def get_dashscope_embedding(self, text: str) -> List[float]:
        """
        使用DashScope生成文本向量

        Args:
            text:str:  输入的文本

        Returns:
            List[float]: 生成的向量
        """
        try:

            #  1. 初始化DashScope客户端 指定嵌入模型名称和维度
            resp = dashscope.TextEmbedding.call(
                model=self.model_name,
                input=text,
                dimension=self.dimension
            )

            # 2. 判断响应状态码是否为200
            if resp.status_code == 200:
                embedding = resp["output"]["embeddings"][0]["embedding"]
                return embedding
            else:
                return []

        except Exception as e:
            logger.error(f"生成文本向量失败,原因: {e}")
            return []

    def upsert_menu_data(self, menu_data: str = None, batch_size: int = 100, clear_existing: bool = True) -> bool:
        """
         菜品数据批量插入方法

        Args:
            menu_data:str:  菜品数据字符串
            batch_size:int: 批量大小
            clear_existing:bool: 是否清除现有pinecone中向量数据

        Returns:
            同步结果 bool (true:成功 false:失败)
        """
        try:
            # 1. 初始化检查
            if not self.index and not self.initialize():
                return False

            # 2. 清除现有数据
            if clear_existing:
                self.delete_all_items_vector_data()

            # 3.读取数据库数据
            if menu_data is None:
                menu_data = self._get_menu_data_from_db()
                if not self._is_valid_menu_data(menu_data):
                    return False

            # 4. 切割加载数据
            lines = self._split_menu_data(menu_data)
            if not lines:
                return False

            # 5. 批量处理
            batch = []
            for line_num, line in enumerate(lines, 1):

                # 5.1  获取每一个文档向量
                vector = self.get_dashscope_embedding(line)

                # 5.2  判断向量是否有效
                if vector and len(vector) == self.dimension:

                    # 5.3  构建向量元数据
                    metadata = {
                        "content": line,
                        "line_number": line_num,
                        "type": "menu_item",
                    }
                    record_id = f"menu_{line_num}"

                    # 5.4  添加到批量列表
                    batch.append((record_id, vector, metadata))

                    #  5.5  批量同步到Pinecone
                    if len(batch) >= batch_size:
                        self.index.upsert(vectors=batch)
                        batch = []

            # 处理不够以及剩余数据
            if batch:
                self.index.upsert(vectors=batch)
            return True

        except Exception as e:
            logger.error(f"批量同步数据失败,原因: {e}")
            return False


    def _get_menu_data_from_db(self) -> str:
        """
        从数据库获取菜单数据

        Returns:
            str: 菜品数据字符串
        """
        try:
            from db_tool import get_all_menu_items
            return get_all_menu_items()
        except Exception as e:
            logger.error(f"获取菜单数据失败,原因: {e}")
            return ""

    def _is_valid_menu_data(self, menu_data: str) -> bool:
        """
        验证菜单数据有效性

        Args:
            menu_data:  str:  菜品数据字符串

        Returns:
            验证结果 bool: 有效性
        """
        if not menu_data:
            return False
        invalid_prefixes = ("当前没有", "查询失败")
        return not menu_data.startswith(invalid_prefixes)


    def _split_menu_data(self, menu_data: str) -> List[str]:
        """
         文本分割逻辑

        Args:
            menu_data: str:  菜品数据字符串

        Returns:
            List[str]: 分割后的文本列表
        """
        try:
            # 1. 定义文本分割器
            text_splitter = CharacterTextSplitter(
                separator="\n",  # 按\n分割
                chunk_size=150,  # 每个块的最大字符数
                chunk_overlap=0,  # 块之间的重叠字符数
                length_function=len
            )

            #  2. 分割文本
            dcos = text_splitter.create_documents(texts=[menu_data])
            final_dcos = []

            # 3. 处理分割结果
            for doc in dcos:
                line = doc.page_content.strip()
                final_dcos.append(line)
            return final_dcos
        except  Exception as e:
            logger.error(f"文本分割失败,原因: {e}")
            return []

    def   similar_search_items(self,query:str,top_k:int=2)-> list[Any] | list[dict[str, Any]] | None:
        """
         根据查询文本搜索相似的菜品

        Args:
            query:str: 输入的查询文本
            top_k:int: 返回的结果数量

        Returns:
            List[Dict[str,Any]] or List[Any]: 包含相似菜品信息的列表

        """
        try:
            # 1. 判断向量数据库是否初始化
            if  not self.index and not self.initialize():
                    return  []

            # 2. 获取查询文本的向量
            query_vector=self.get_dashscope_embedding(query)
            if not query_vector or len(query_vector)!= self.dimension :
                return  []

            # 3. 向量检索
            result=self.index.query(vector=query_vector,top_k=top_k,include_metadata=True)

            # 4. 处理结果
            similar_result=[]
            for  item  in  result['matches']:
               match_item={
                   "id": item['id'],
                   "score":item['score'],
                   "content":item['metadata']['content'],
                   "line_number":item['metadata']['line_number']
               }
               similar_result.append(match_item)
            return  similar_result
        except Exception as e:
            logger.error(f"查询向量库索引: {self.index}向量数据失败,原因：{e}")
            return  []


    def   delete_all_items_vector_data(self)->bool:
        """
        删除向量数据库所有向量数据

        Returns:
            删除结果 bool: (true:成功 false:失败)
        """

        try:
            # 1. 判断向量数据库是否初始化
            if  not  self.index and not self.initialize():
                    return  False

            # 2. 获取所有索引信息
            stats=self.index.describe_index_stats()
            count=stats.total_vector_count

            if  count==0:
                return True

            # 4. 删除所有向量数据
            self.index.delete(delete_all=True)
            return  True
        except Exception as e:
            logger.error(f"删除向量库索引: {self.index}向量数据失败: 原因：{e}")
            return  False


# 全局实例
vector_db = PineconeVectorDB()

def pinecone_connection() -> bool:
    """
     连接Pinecone向量数据库

    Returns:
        bool: 是否连接成功 true:成功 false:失败
    """
    return vector_db.initialize()


def sync_pinecone_data_from_database() -> bool:
    """
     从数据库同步数据到Pinecone向量数据库
    Returns:
        bool: 是否同步成功 true:成功 false:失败

    """
    return vector_db.upsert_menu_data(menu_data=None, clear_existing=True)


def search_menu_items_with_id(query: str, top_k: int = 2) -> Dict[str, Any]:
    """
     根据查询文本搜索相似的菜品
    Args:
        query: str: 查询文本
        top_k: int: 返回的结果数量

    Returns:
        Dict[str,Any]:包含菜品内容列表和真实菜品ID列表的字典
        {
            "contents": [菜品内容列表],
            "ids": [真实菜品ID列表],
            "scores": [相似度分数列表]
        }
    """

    try:
        import re

        #  1. 查询相似性菜品信息
        similar_result = vector_db.similar_search_items(query=query, top_k=top_k)

        if not similar_result:
            return {}

        # 2. 处理相似性检索结果
        item_ids = []
        for item in similar_result:
            content = item['content']
            match = re.search(r'菜品ID:(\d+)', content)
            if match:
                item_ids.append(match.group(1))
            else:
                item_ids.append(item["id"])

        # 3. 返回结果
        return {
            "contents": [item['content'] for item in similar_result],
            "ids": item_ids,
            "scores": [item['score'] for item in similar_result]
        }
    except Exception as e:
        logger.error(f"查询相似性菜品信息带id失败: {e}")
        return {}


if __name__ == "__main__":


    # 1. 测试Pinecone连接
    print("\n1.测试Pinecone连接...")
    if  pinecone_connection():
         print("Pinecone连接成功...")

    # 2. 测试执行数据同步：删除现有数据并从数据库重新上传
    print("\n2.测试正在同步数据...")
    sync_result=sync_pinecone_data_from_database()
    if  sync_result:
         print("数据同步成功...")


    # 3. 测试查询相似性菜品信息
    print("\n3.测试查询相似性菜品信息...")
    similar_search_result=vector_db.similar_search_items(query="我想点川菜",top_k=2)

    if similar_search_result:
       for item in similar_search_result:
           print(f"相似菜品: {item['content']}，相似度: {item['score']}")

    #  4. 测试查询相似性菜品信息带id
    print("\n4.测试查询相似性菜品信息带id...")
    similar_search_result=search_menu_items_with_id(query="我想点川菜",top_k=2)
    if  similar_search_result:
         print(f"相似菜品: {similar_search_result['contents']}，相似度: {similar_search_result['scores'],}，真实ID: {similar_search_result['ids']}")

```





### 3.3 定义高德地图业务工具

#### 3.3.1 新建amap_tool文件

> 模块作用：该模块提供根据三种路径（步行、骑行、驾车）的配送距离查询

##### ① 定义配置管理类

- 功能：统一配置环境变量

amap_tool.py文件代码片段如下：

```python
@dataclass
class Config:
    API_KEY: str = os.getenv("AMAP_API_KEY")
    MERCHANT_LONGITUDE: str = os.getenv("MERCHANT_LONGITUDE", "114.401934")
    MERCHANT_LATITUDE: str = os.getenv("MERCHANT_LATITUDE", "30.465295")
    DELIVERY_RADIUS: int = int(os.getenv("DELIVERY_RADIUS", "2500"))
    DEFAULT_PATH_MODE: PathModeInput = os.getenv("DEFAULT_PATH_MODE", "2")  # 默认使用2(bicycling)

    def __post_init__(self):
        if not self.API_KEY:
            raise ValueError("AMAP_API_KEY 环境变量未设置")

```





##### ② 定义工具转换类

- 定义路径模式转换工具类 功能：将外部输入的路径模式 -> 内部使用的路径模式


amap_tool.py文件代码片段如下：

```python
# 路径模式转换工具
class PathModeConverter:
    """路径模式转换工具类"""

    # 映射关系  外部输入的路径模式 -> 内部使用的路径模式
    MODE_MAPPING = {
        "1": "walking",
        "2": "bicycling",
        "3": "driving",

    }


    @classmethod
    def to_mode(cls, mode_input: Union[PathModeInput]) -> PathMode:
        """将输入的模式转换为内部使用的模式"""

        if mode_input in cls.MODE_MAPPING:
            return cls.MODE_MAPPING[mode_input]
        else:
            raise ValueError(f"不支持的路径模式: {mode_input}，支持的模式: {list(cls.MODE_MAPPING.keys())}")


```



##### ③ 定义发送请求函数

- 定义重试机制的会话请求函数 功能：发送请求支持重试

- 定义安全发送请求的函数 功能：发送HTTPS以及HTTP请求



amap_tool.py文件代码片段如下：

```python
def create_session_with_retries():
    """创建带重试机制的requests会话"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def safe_request(base_url: str, params: dict) -> Optional[Dict]:
    """安全的HTTP请求，处理重试和SSL降级"""
    session = create_session_with_retries()
    try:
        response = session.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.SSLError:
        try:
            http_url = base_url.replace("https://", "http://")
            response = session.get(http_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RequestException(f"HTTP请求失败: {e}")
    except requests.exceptions.RequestException as e:
        raise RequestException(f"HTTPS请求失败: {e}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"JSON解析错误: {e}")
```



##### ④ 定义地理编码函数

- 功能：将地址转换为坐标



amap_tool.py文件代码片段如下：

```python

def geocode_address(address: str) -> Dict[str,Any]:
    """
    地理编码功能 将地址转换为坐标

    Args:
       address: 用户输入要查询的地址

    Returns:
        Dict: 地理编码结果 包含格式化后的地址、经纬度

   """
    try:
        if not config.API_KEY:
            raise  ValueError("API_KEY不存在")

        # 1. 构建请求URL
        base_url = "https://restapi.amap.com/v3/geocode/geo"

        #  2. 构建请求参数
        params = {
            "key": config.API_KEY,
            "address": address,
            "output": "JSON"
        }

        # 3. 发送请求并处理响应
        response_data = safe_request(base_url, params)
        if response_data["status"] == "1" and int(response_data["count"]) > 0:
            geocodes = response_data["geocodes"]
            if geocodes and len(geocodes) > 0:
                return {
                    "formatted_address" : geocodes[0]["formatted_address"],
                    "location": geocodes[0]["location"],
                    "status":"success"
                }

        return {
            "status": "fail",
            "message":"高德地图地理坐标解析失败"
        }
    except Exception as e:
        logger.error(f"高德地图地理坐标解析失败,原因:{e}")
        raise

```



##### ⑤  定义计算起终点距离函数

- 功能：三种不同的路径模式计算两个地点之间的距离和预计时间



amap_tool.py文件代码片段如下：

```python

def calculate_distance(origin_location: str, destination_location: str,
                       path_mode_input: PathModeInput = "2") -> Dict[str,Any]:
    """
    不同的路径模式计算两个地点之间的距离和预计时间

    Args:
        origin_location: 起点经纬度
        destination_location:  终点经纬度
        path_mode_input:  路径模式，1:步行，2:骑行，3:驾车

    Returns:
        Dict: 路径结果，包含路径模式、距离、预计时间等

    """
    try:

        if not config.API_KEY:
            raise ValueError("AMAP_API_KEY不存在")
        # 1. 转换外部输入路径模式为内部使用的路径模式
        path_mode = PathModeConverter.to_mode(path_mode_input)

        # 2. 根据路径模式构建不同的请求URL
        endpoints = {
            "walking": "https://restapi.amap.com/v5/direction/walking",
            "bicycling": "https://restapi.amap.com/v5/direction/electrobike",
            "driving": "https://restapi.amap.com/v5/direction/driving"
        }

        # 3. 构建请求参数
        params = {
            "key": config.API_KEY,
            "origin": origin_location,
            "destination": destination_location,
        }

        # 4. 根据路径模式添加不同的参数
        if path_mode == "driving":
            params["show_fields"] = "cost"

        # 5. 发送请求并处理响应
        response = safe_request(endpoints[path_mode], params)
        if response.get("status") == "1":
            path = response["route"]["paths"][0]
            duration = int(path["duration"]) if path_mode == "bicycling" else int(path["cost"]["duration"])
            return {
                "distance":int(path["distance"]),
                "duration":duration,
                "status":"success"
            }

        return {
            "status":"success",
            "message":"高德地图距离解析失败"

        }
    except Exception as e:
        logger.error(f"高德地图距离解析失败,原因:{e}")
        raise


```



##### ⑧ 定义地址是否在配送范围内函数

- 功能：检查目标地址是否在配送范围内

```python
def check_delivery_range(address: str, path_mode_input: PathModeInput =  None) -> Dict[str,Any]:
    """检查地址是否在配送范围内

    Args:
        address: 用户输入的地址

        path_mode_input: 路径模式，支持 "1"(walking), "2"(bicycling), "3"(driving)。如果为None则使用配置的默认模式

    Returns:
          包含检查结果的 Dict 对象
    """

    try:
        # 1. 使用传入的模式或默认模式
        if path_mode_input is None:
            path_mode_input = config.DEFAULT_PATH_MODE

        # 2. 地理编码获取经纬度
        geocode_result = geocode_address(address)
        if   geocode_result['status']!="success":
           logger.error("地理位置编码失败")
           return  geocode_result

        # 3. 计算距离
        origin_location = f"{config.MERCHANT_LONGITUDE},{config.MERCHANT_LATITUDE}"
        distance_result = calculate_distance(origin_location, geocode_result['location'], path_mode_input)
        if  distance_result['status']!="success":
            return distance_result

        # 4. 检查是否在配送范围内 并返回结果
        in_range = distance_result['distance'] <= config.DELIVERY_RADIUS
        distance_km = round(distance_result['distance'] / 1000, 2)
        return {
            "status": "success",
            "in_range":in_range,
            "distance":distance_km,
            "duration":distance_result['duration'],
            "formatted_address":geocode_result['formatted_address'],
            "message": (
                f"配送地址：{geocode_result['formatted_address']}\n"
                f"配送距离：{distance_km:.2f}公里\n"
                f"配送状态：{'在配送范围内' if in_range else '超出配送范围'}"
            )
        }
    except Exception as e:
       raise
```

⑨：高德地图业务完整代码

```python
import requests
from typing import Dict, Optional, Literal, Union, Any
import json
from requests import RequestException
import os
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3 import Retry
from dataclasses import dataclass
import logging
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 类型定义
PathMode = Literal["walking", "bicycling", "driving"]
PathModeInput = Literal["1", "2", "3"]  # 外部输入的路径模式



# 配置管理
@dataclass
class Config:
    API_KEY: str = os.getenv("AMAP_API_KEY")
    MERCHANT_LONGITUDE: str = os.getenv("MERCHANT_LONGITUDE", "114.401934")
    MERCHANT_LATITUDE: str = os.getenv("MERCHANT_LATITUDE", "30.465295")
    DELIVERY_RADIUS: int = int(os.getenv("DELIVERY_RADIUS", "2500"))
    DEFAULT_PATH_MODE: PathModeInput = os.getenv("DEFAULT_PATH_MODE", "2")  # 默认使用2(bicycling)

    def __post_init__(self):
        if not self.API_KEY:
            raise ValueError("AMAP_API_KEY 环境变量未设置")


config = Config()


# 路径模式转换工具
class PathModeConverter:
    """路径模式转换工具类"""

    # 映射关系  外部输入的路径模式 -> 内部使用的路径模式
    MODE_MAPPING = {
        "1": "walking",
        "2": "bicycling",
        "3": "driving",

    }

    @classmethod
    def to_mode(cls, mode_input: PathModeInput) -> PathMode:
        """将输入的模式转换为内部使用的模式"""

        if mode_input in cls.MODE_MAPPING:
            return cls.MODE_MAPPING[mode_input]
        else:
            raise ValueError(f"不支持的路径模式: {mode_input}，支持的模式: {list(cls.MODE_MAPPING.keys())}")



def create_session_with_retries():
    """创建带重试机制的requests会话"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def safe_request(base_url: str, params: dict) -> Optional[Dict]:
    """安全的HTTP请求，处理重试和SSL降级"""
    session = create_session_with_retries()
    try:
        response = session.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.SSLError:
        try:
            http_url = base_url.replace("https://", "http://")
            response = session.get(http_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RequestException(f"HTTP请求失败: {e}")
    except requests.exceptions.RequestException as e:
        raise RequestException(f"HTTPS请求失败: {e}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"JSON解析错误: {e}") from e




def geocode_address(address: str) -> Dict[str,Any]:
    """
    地理编码功能 将地址转换为坐标

    Args:
       address: 用户输入要查询的地址

    Returns:
        Dict: 地理编码结果 包含格式化后的地址、经纬度

   """
    try:
        if not config.API_KEY:
            raise  ValueError("API_KEY不存在")

        # 1. 构建请求URL
        base_url = "https://restapi.amap.com/v3/geocode/geo"

        #  2. 构建请求参数
        params = {
            "key": config.API_KEY,
            "address": address,
            "output": "JSON"
        }

        # 3. 发送请求并处理响应
        response_data = safe_request(base_url, params)
        if response_data["status"] == "1" and int(response_data["count"]) > 0:
            geocodes = response_data["geocodes"]
            if geocodes and len(geocodes) > 0:
                return {
                    "formatted_address" : geocodes[0]["formatted_address"],
                    "location": geocodes[0]["location"],
                    "status":"success"
                }

        return {
            "status": "fail",
            "message":"高德地图地理坐标解析失败"
        }
    except Exception as e:
        logger.error(f"高德地图地理坐标解析失败,原因:{e}")
        raise


def calculate_distance(origin_location: str, destination_location: str,
                       path_mode_input: PathModeInput = "2") -> Dict[str,Any]:
    """
    不同的路径模式计算两个地点之间的距离和预计时间

    Args:
        origin_location: 起点经纬度
        destination_location:  终点经纬度
        path_mode_input:  路径模式，1:步行，2:骑行，3:驾车

    Returns:
        Dict: 路径结果，包含路径模式、距离、预计时间等

    """
    try:

        if not config.API_KEY:
            raise ValueError("AMAP_API_KEY不存在")
        # 1. 转换外部输入路径模式为内部使用的路径模式
        path_mode = PathModeConverter.to_mode(path_mode_input)

        # 2. 根据路径模式构建不同的请求URL
        endpoints = {
            "walking": "https://restapi.amap.com/v5/direction/walking",
            "bicycling": "https://restapi.amap.com/v5/direction/electrobike",
            "driving": "https://restapi.amap.com/v5/direction/driving"
        }

        # 3. 构建请求参数
        params = {
            "key": config.API_KEY,
            "origin": origin_location,
            "destination": destination_location,
        }

        # 4. 根据路径模式添加不同的参数
        if path_mode == "driving":
            params["show_fields"] = "cost"

        # 5. 发送请求并处理响应
        response = safe_request(endpoints[path_mode], params)
        if response.get("status") == "1":
            path = response["route"]["paths"][0]
            duration = int(path["duration"]) if path_mode == "bicycling" else int(path["cost"]["duration"])
            return {
                "distance":int(path["distance"]),
                "duration":duration,
                "status":"success"
            }

        return {
            "status":"success",
            "message":"高德地图距离解析失败"

        }
    except Exception as e:
        logger.error(f"高德地图距离解析失败,原因:{e}")
        raise



def check_delivery_range(address: str, path_mode_input: PathModeInput =  None) -> Dict[str,Any]:
    """检查地址是否在配送范围内

    Args:
        address: 用户输入的地址

        path_mode_input: 路径模式，支持 "1"(walking), "2"(bicycling), "3"(driving)。如果为None则使用配置的默认模式

    Returns:
          包含检查结果的 Dict 对象
    """

    try:
        # 1. 使用传入的模式或默认模式
        if path_mode_input is None:
            path_mode_input = config.DEFAULT_PATH_MODE

        # 2. 地理编码获取经纬度
        geocode_result = geocode_address(address)
        if   geocode_result['status']!="success":
           logger.error("地理位置编码失败")
           return  geocode_result

        # 3. 计算距离
        origin_location = f"{config.MERCHANT_LONGITUDE},{config.MERCHANT_LATITUDE}"
        distance_result = calculate_distance(origin_location, geocode_result['location'], path_mode_input)
        if  distance_result['status']!="success":
            return distance_result

        # 4. 检查是否在配送范围内 并返回结果
        in_range = distance_result['distance'] <= config.DELIVERY_RADIUS
        distance_km = round(distance_result['distance'] / 1000, 2)
        return {
            "status": "success",
            "in_range":in_range,
            "distance":distance_km,
            "duration":distance_result['duration'],
            "formatted_address":geocode_result['formatted_address'],
            "message": (
                f"配送地址：{geocode_result['formatted_address']}\n"
                f"配送距离：{distance_km:.2f}公里\n"
                f"配送状态：{'在配送范围内' if in_range else '超出配送范围'}"
            )
        }
    except Exception as e:
       raise


```

#### 3.3.2 测试各个功能

##### ① 测试步行模式配送范围

##### ② 测试骑行模式配送范围

##### ③ 测试驾车模式配送范围



##### ⑤ 测试业务完整代码

```python
# 使用示例
if __name__ == "__main__":
    # 不同模式的使用
    pass
    test_address = "武汉市洪山区光谷天地" #  测试地址
    print("\n=== 测试不同路径模式 ===")
    # 测试步行模式 (1)
    print("\n1. 步行模式测试:")
    result1 = check_delivery_range(test_address, "1")
    minutes = result1['duration'] // 60
    seconds = result1['duration'] % 60
    print(f"步行模式距离: {result1['distance']}公里 时间: {result1['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result1['message']}")
    
    # 测试骑行模式 (2)
    print("\n2. 骑行模式测试:")
    result2 = check_delivery_range(test_address, "2")
    minutes = result1['duration'] // 60
    seconds = result1['duration'] % 60
    print(f"步行模式距离: {result2['distance']}公里 时间: {result2['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result2['message']}")

    # 测试驾车模式 (3)
    print("\n3. 驾车模式测试:")
    result3 = check_delivery_range(test_address, "3")
    minutes = result3['duration'] // 60
    seconds = result3['duration'] % 60
    print(f"步行模式距离: {result3['distance']}公里 时间: {result3['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result3['message']}")
```



#### 3.3.3 文件完整代码

```python
import requests
from typing import Dict, Optional, Literal, Union, Any
import json
from requests import RequestException
import os
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3 import Retry
from dataclasses import dataclass
import logging
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 类型定义
PathMode = Literal["walking", "bicycling", "driving"]
PathModeInput = Literal["1", "2", "3"]  # 外部输入的路径模式



# 配置管理
@dataclass
class Config:
    API_KEY: str = os.getenv("AMAP_API_KEY")
    MERCHANT_LONGITUDE: str = os.getenv("MERCHANT_LONGITUDE", "114.401934")
    MERCHANT_LATITUDE: str = os.getenv("MERCHANT_LATITUDE", "30.465295")
    DELIVERY_RADIUS: int = int(os.getenv("DELIVERY_RADIUS", "2500"))
    DEFAULT_PATH_MODE: PathModeInput = os.getenv("DEFAULT_PATH_MODE", "2")  # 默认使用2(bicycling)

    def __post_init__(self):
        if not self.API_KEY:
            raise ValueError("AMAP_API_KEY 环境变量未设置")


config = Config()


# 路径模式转换工具
class PathModeConverter:
    """路径模式转换工具类"""

    # 映射关系  外部输入的路径模式 -> 内部使用的路径模式
    MODE_MAPPING = {
        "1": "walking",
        "2": "bicycling",
        "3": "driving",

    }

    @classmethod
    def to_mode(cls, mode_input: PathModeInput) -> PathMode:
        """将输入的模式转换为内部使用的模式"""

        if mode_input in cls.MODE_MAPPING:
            return cls.MODE_MAPPING[mode_input]
        else:
            raise ValueError(f"不支持的路径模式: {mode_input}，支持的模式: {list(cls.MODE_MAPPING.keys())}")



def create_session_with_retries():
    """创建带重试机制的requests会话"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def safe_request(base_url: str, params: dict) -> Optional[Dict]:
    """安全的HTTP请求，处理重试和SSL降级"""
    session = create_session_with_retries()
    try:
        response = session.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.SSLError:
        try:
            http_url = base_url.replace("https://", "http://")
            response = session.get(http_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RequestException(f"HTTP请求失败: {e}")
    except requests.exceptions.RequestException as e:
        raise RequestException(f"HTTPS请求失败: {e}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"JSON解析错误: {e}") from e




def geocode_address(address: str) -> Dict[str,Any]:
    """
    地理编码功能 将地址转换为坐标

    Args:
       address: 用户输入要查询的地址

    Returns:
        Dict: 地理编码结果 包含格式化后的地址、经纬度

   """
    try:
        if not config.API_KEY:
            raise  ValueError("API_KEY不存在")

        # 1. 构建请求URL
        base_url = "https://restapi.amap.com/v3/geocode/geo"

        #  2. 构建请求参数
        params = {
            "key": config.API_KEY,
            "address": address,
            "output": "JSON"
        }

        # 3. 发送请求并处理响应
        response_data = safe_request(base_url, params)
        if response_data["status"] == "1" and int(response_data["count"]) > 0:
            geocodes = response_data["geocodes"]
            if geocodes and len(geocodes) > 0:
                return {
                    "formatted_address" : geocodes[0]["formatted_address"],
                    "location": geocodes[0]["location"],
                    "status":"success"
                }

        return {
            "status": "fail",
            "message":"高德地图地理坐标解析失败"
        }
    except Exception as e:
        logger.error(f"高德地图地理坐标解析失败,原因:{e}")
        raise


def calculate_distance(origin_location: str, destination_location: str,
                       path_mode_input: PathModeInput = "2") -> Dict[str,Any]:
    """
    不同的路径模式计算两个地点之间的距离和预计时间

    Args:
        origin_location: 起点经纬度
        destination_location:  终点经纬度
        path_mode_input:  路径模式，1:步行，2:骑行，3:驾车

    Returns:
        Dict: 路径结果，包含路径模式、距离、预计时间等

    """
    try:

        if not config.API_KEY:
            raise ValueError("AMAP_API_KEY不存在")
        # 1. 转换外部输入路径模式为内部使用的路径模式
        path_mode = PathModeConverter.to_mode(path_mode_input)

        # 2. 根据路径模式构建不同的请求URL
        endpoints = {
            "walking": "https://restapi.amap.com/v5/direction/walking",
            "bicycling": "https://restapi.amap.com/v5/direction/electrobike",
            "driving": "https://restapi.amap.com/v5/direction/driving"
        }

        # 3. 构建请求参数
        params = {
            "key": config.API_KEY,
            "origin": origin_location,
            "destination": destination_location,
        }

        # 4. 根据路径模式添加不同的参数
        if path_mode == "driving":
            params["show_fields"] = "cost"

        # 5. 发送请求并处理响应
        response = safe_request(endpoints[path_mode], params)
        if response.get("status") == "1":
            path = response["route"]["paths"][0]
            duration = int(path["duration"]) if path_mode == "bicycling" else int(path["cost"]["duration"])
            return {
                "distance":int(path["distance"]),
                "duration":duration,
                "status":"success"
            }

        return {
            "status":"success",
            "message":"高德地图距离解析失败"

        }
    except Exception as e:
        logger.error(f"高德地图距离解析失败,原因:{e}")
        raise



def check_delivery_range(address: str, path_mode_input: PathModeInput =  None) -> Dict[str,Any]:
    """检查地址是否在配送范围内

    Args:
        address: 用户输入的地址

        path_mode_input: 路径模式，支持 "1"(walking), "2"(bicycling), "3"(driving)。如果为None则使用配置的默认模式

    Returns:
          包含检查结果的 Dict 对象
    """

    try:
        # 1. 使用传入的模式或默认模式
        if path_mode_input is None:
            path_mode_input = config.DEFAULT_PATH_MODE

        # 2. 地理编码获取经纬度
        geocode_result = geocode_address(address)
        if   geocode_result['status']!="success":
           logger.error("地理位置编码失败")
           return  geocode_result

        # 3. 计算距离
        origin_location = f"{config.MERCHANT_LONGITUDE},{config.MERCHANT_LATITUDE}"
        distance_result = calculate_distance(origin_location, geocode_result['location'], path_mode_input)
        if  distance_result['status']!="success":
            return distance_result

        # 4. 检查是否在配送范围内 并返回结果
        in_range = distance_result['distance'] <= config.DELIVERY_RADIUS
        distance_km = round(distance_result['distance'] / 1000, 2)
        return {
            "status": "success",
            "in_range":in_range,
            "distance":distance_km,
            "duration":distance_result['duration'],
            "formatted_address":geocode_result['formatted_address'],
            "message": (
                f"配送地址：{geocode_result['formatted_address']}\n"
                f"配送距离：{distance_km:.2f}公里\n"
                f"配送状态：{'在配送范围内' if in_range else '超出配送范围'}"
            )
        }
    except Exception as e:
       raise


# 使用示例
if __name__ == "__main__":
    # 不同模式的使用
    pass
    test_address = "武汉市洪山区光谷天地" #  测试地址
    print("\n=== 测试不同路径模式 ===")
    # 测试步行模式 (1)
    print("\n1. 步行模式测试:")
    result1 = check_delivery_range(test_address, "1")
    minutes = result1['duration'] // 60
    seconds = result1['duration'] % 60
    print(f"步行模式距离: {result1['distance']}公里 时间: {result1['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result1['message']}")
    
    # 测试骑行模式 (2)
    print("\n2. 骑行模式测试:")
    result2 = check_delivery_range(test_address, "2")
    minutes = result1['duration'] // 60
    seconds = result1['duration'] % 60
    print(f"步行模式距离: {result2['distance']}公里 时间: {result2['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result2['message']}")

    # 测试驾车模式 (3)
    print("\n3. 驾车模式测试:")
    result3 = check_delivery_range(test_address, "3")
    minutes = result3['duration'] // 60
    seconds = result3['duration'] % 60
    print(f"步行模式距离: {result3['distance']}公里 时间: {result3['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result3['message']}")
```



