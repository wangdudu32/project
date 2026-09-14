"""
AiMenu FastAPI 接口

提供三个主要接口：
1. POST /chat - 智能对话接口
2. POST /delivery - 配送查询接口
3. GET /menu/list - 菜品列表接口
"""
from  pydantic import  BaseModel
from fastapi import FastAPI
from typing import Dict, Any,List,Optional
from serive.service import delivery_check,menu_lists,smart_chat
from tools.amap_tool import PathModeInput

# 请求数据模型
class DeliveryRequest(BaseModel):
    """配送查询请求"""
    address: str
    travel_mode: PathModeInput = "2"  # 1=步行, 2=骑电动车, 3=驾车


class ChatRequest(BaseModel):
    """智能对话请求"""
    query: str   # 输入的自然语言：我想查询川菜系列

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


class MenuListResponse(BaseModel):
    """菜品列表响应"""
    success: bool
    menu_items: List[dict] # 菜品列表
    count: int # 菜品数
    message: str # 响应消息提示

class ChatResponse(BaseModel):
    """智能对话响应"""
    success: bool # 成功失败表示
    query: str # 原始查询内容
    response: Optional[str] = None # 响应内容（如果是询问的是普通问题或者配送问题 response中就有模型的回复内容 recommendation没有数据）
    recommendation: Optional[str] = None # （如果是询问菜品推荐相关的问题 recommendation 就有模型推荐的内容 response中就有模型的回复内容 response）
    menu_ids: Optional[List[str]] = None # （如果是询问菜品推荐相关的问题 recommendation、menu_ids 都有模型推荐的内容（模型生成的推荐语言 推荐的菜品id列表）  response中就有模型的回复内容）


# 1. 定义FASTAPI实例
app = FastAPI(title="欢迎使用智慧点餐系统",
              description="智慧点餐系统提供三个主要接口智能对话接口、配送查询接口、菜品查询列表接口", version="v1.0")


# 2、指定跟路径测试前后端是否能够打通
@app.get(path="/")
def root() -> Dict[str, Any]:
    """测试前端访问根路径请求被处理"""

    return  {"message":"欢迎使用智慧点餐FastAPI框架","code":200}


# 3. 健康检查
@app.get(path="/healthy")
def root() -> Dict[str, Any]:
    """测试多路径请求访问的健康状态"""

    return  {"message":"多路径请求接收到","code":200,"status":"success"}


@app.post("/delivery", response_model=DeliveryResponse)
def delivery_endpoint(request: DeliveryRequest):
    """
    配送查询接口

    检查指定地址是否在配送范围内
    """


    # 1.调用查询范围的工具
    response=delivery_check(request.address,request.travel_mode)

    if response['status']=="success":
        return DeliveryResponse(
        success= True,
        in_range=response['in_range'],
        distance= response['distance'],
        duration=response['duration'],
        formatted_address= response['formatted_address'],
        message=response['message'],
        travel_mode=request.travel_mode,
        input_address= request.address
        )

    # 2.返回
    return   DeliveryResponse(
        success=False,
        in_range=False,
        distance=0.0,
        duration=0.0,
        formatted_address=request.address,
        message=response['message'],
        travel_mode=request.travel_mode,
        input_address=request.address
    )


@app.get("/menu/list", response_model=MenuListResponse)
def menu_list_endpoint():
    """
    菜品列表接口

    获取所有菜品的结构化信息，专为前端展示设计
    """

    # 1.查询所有的菜品列表
    response=menu_lists()


    # 2.封装返回
    if  not response:
        return MenuListResponse(
        success= False,
        menu_items=[],
        count=0,
        message="暂无任何菜品信息"
        )
    return MenuListResponse(
        success=True,
        menu_items=response,
        count=len(response),
        message=f"已查询到{len(response)}个菜品信息"
    )


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    智能对话接口

    接收用户问题，返回智能助手回复
    """
    # 1.调用聊天方法
    chat_response=smart_chat(request.query)   #  str  or  dict

    # 2.根据回复的内容，判断是推荐菜品的回复还是普通问题询问以及菜品推荐问题的询问 封装对应的ChatResponse对象
    if isinstance(chat_response,dict) and "recommendation" in chat_response and "menu_ids" in chat_response:
        return ChatResponse(
        success= True,
        query=request.query,
        recommendation=chat_response['recommendation'],
        menu_ids=chat_response['menu_ids']
        )
    else:
        return ChatResponse(
        success= True,
        query=request.query,
        response=chat_response
        )















