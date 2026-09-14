# 点餐项目

## 

### 1. 定义模型调用相关业务

#### 1.1 新建llm_tool文件

> 模块作用：该模块提供了通用的llm调用方案，将llm调用进行封装,在后续调用时只需调用call_llm即可

##### ①  导入相关包

1. 导入加载环境变量相关包
2. 导入可运行组件相关包
3. 导入提示词相关包
4. 导入OpenAI模型相关包



llm_tool.py文件代码片段如下：

```python
from dotenv import load_dotenv
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
```



##### ② 加载环境变量

```python
load_dotenv()
```



##### ③ 定义模型调用方法

1. 定义相关变量获取模型配置（api_key、model、base_url）
2. 定义对话类型提示词模版对象
3. 定义模型实例对象
4. 定义可运行链
5. 执行可运行链获取响应
6. 提取模型响应结果，并返回



llm_tool.py文件代码片段如下：

```python

def  call_llm(user_query:str,instruction:str)->str:
    """
     调用大模型进行分析

     Args:
         user_query (str): 用户提示
         instruction (str): 系统指令

     Returns:
         str: 大模型的回复
     """
    try:
        # 模型信息配置
        api_key=os.getenv("DASHSCOPE_API_KEY")
        base_url=os.getenv("DASHSCOPE_API_BASE")
        model = os.getenv("LLM_QWEN2.5")
        
        # 创建模型提示模板对象
        prompt_template=ChatPromptTemplate.from_messages([
            ("system","{instruction}"),
            ("human","{user_query}"),
        ])
        # 定义模型
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        # 定义可运行的链
        chain={
          "instruction":RunnablePassthrough(),
          "user_query": RunnablePassthrough()
        }| prompt_template | llm
        # 执行链
        response=chain.invoke({"instruction":instruction,"user_query":user_query})
        return  response.content
    except Exception as e:
        return f"调用LLM时发生错误: {str(e)}"

```



#### 1.2  文件完整代码

```python
import os
from langchain_core.runnables import  RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import  logging
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)
def  call_llm(user_query:str,instruction:str)->str:
    """
     调用大模型进行分析

     Args:
         user_query (str): 用户提示
         instruction (str): 系统指令

     Returns:
         str: 大模型的回复
     """
    try:
        # 模型信息配置
        api_key=os.getenv("DASHSCOPE_API_KEY")
        base_url=os.getenv("DASHSCOPE_API_BASE")
        model = os.getenv("LLM_QWEN2.5")
        
        # 创建模型提示模板对象
        prompt_template=ChatPromptTemplate.from_messages([
            ("system","{instruction}"),
            ("human","{user_query}"),
        ])
        # 定义模型
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        # 定义可运行的链
        chain={
          "instruction":RunnablePassthrough(),
          "user_query": RunnablePassthrough()
        }| prompt_template | llm
        # 执行链
        response=chain.invoke({"instruction":instruction,"user_query":user_query})
        return  response.content
    except Exception as e:
        return f"调用LLM时发生错误: {str(e)}"

```



### 2. 定义工具集相关业务

#### 2.1 新建mcp.py文件

> 模块作用：该模块使用@tool装饰器注册三个主要工具：
>
> 1. 常规问询工具 - 处理一般性问题和对话
> 2. 菜品信息咨询工具 - 处理与菜品相关的查询
> 3. 配送范围检查工具-检查指定地址是否在配送范围内，并提供距离信息
>
> 工具调用LLM进行智能回复，并可以集成其他tools中的功能



##### ① 将文件目录添加到系统

1. 获取当前文件目录
2. 导入相关模块
3. 加载环境变量

> 作用：将项目的根目录添加到 Python 的模块搜索路径（`sys.path`）中，使得 Python 能够正确找到并导入项目中的自定义模块
>
> 假设场景：
>
> project/
> ├── src/
> │   ├── utils/
> │   │   └── helper.py    # 当前文件
> │   └── main.py          # 需要导入 utils 模块
> └── requirements.txt
>
> 如果在 `main.py` 中直接导入 `utils.helper`，Python 会报错 **`ModuleNotFoundError`**，因为默认情况下 `sys.path` 不包含项目根目录（`project/`）。
>
> 解决方案：添加如下代码



- 在 每个模块 开头添加完整的路径设置

```python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

```

- 整个项目都生效

```python
# 1. 创建 __init__.py 在项目根目录
# smart_dian_can/__init__.py
import sys
import os

# 自动设置路径
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
    
    
# 2. 创建 setup.py 在项目根目录
# setup.py
from setuptools import setup, find_packages

setup(
    name="smart_dian_can",
    version="0.1.0",
    description="智能点餐系统",
    packages=find_packages(),  # 自动发现所有包
    author="huzhongkui",
    author_email="2595753724@qq.com",
)

cd /path/to/smart_dian_can  # 进入项目根目录
pip install -e .
```



> 解释：
>
> 1. **`__file__`**
>    - 表示当前 Python 文件的路径（例如：`/home/user/project/src/utils/helper.py`）。
> 2. **`os.path.abspath(__file__)`**
>    - 将 `__file__` 转换为绝对路径（避免相对路径问题）
> 3. **`os.path.dirname()`**
>    - 第一次调用：返回当前文件所在目录的路径（如 `/home/user/project/src/utils`）。
>    - 第二次调用：返回上一级目录的路径（如 `/home/user/project/src`），即**项目根目录**（项目结构为标准的 `src` 结构）。
> 4. **`sys.path.append()`**
>    - 将计算出的项目根目录添加到 `sys.path`（Python 查找模块的路径列表）。



##### ② 定义加载提示词函数

1.  获取项目根目录下的prompt文件夹路径
2.  获取指定提示词模版文件
3.  返回提示词模版文件内容



mcp.py代码片段如下

```python
def load_prompt_template(template_name: str) -> str:
    """
    加载提示词模板
    
    Args:
        template_name: 模板文件名（不含扩展名）
        
    Returns:
        str: 提示词内容
    """
    try:
        # 获取项目根目录下的prompt文件夹路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompt_path = os.path.join(project_root, "prompt", f"{template_name}.txt")
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"警告：无法加载提示词模板 {template_name}: {e}")
        return "你是一个智能助手，请根据用户问题提供帮助。"

```



##### ③ 定义常规查询工具

1. 调用load_prompt_template函数，根据工具名字获取对应的提示词模版内容
2. 如果有上下文，添加上下文
3. 调用call_llm函数
4. 返回模型响应结果



mcp.py代码片段如下

```python
@tool
def general_inquiry(query: str, context: str) -> str:
    """
        常规问询工具

        处理用户的一般性问题，包括但不限于：
        - 餐厅介绍和服务信息
        - 营业时间和联系方式
        - 优惠活动和会员服务
        - 其他非菜品相关的咨询

        Args:
            query: 用户的问询内容
            context: 可选的上下文信息，用于提供更精准的回复

        Returns:
            str: 针对用户问询的智能回复

        Raises:
            ToolException: 当处理查询时发生错误
        """


    try:
        # 1. 加载提示词模版
        template=load_template("general_inquiry")

        # 2. 处理输入问题
        full_query=  f"当前提供的上下文:{context} \\n 用户问题: {query}"  if   context else f"用户问题: {query}"

        response = call_llm(full_query, template)

        return  response
    except Exception as e:
        raise ToolException(f"常规问询处理失败: {str(e)}")
```



##### ④ 定义菜品查询工具

1.  先通过语义搜索获取相关菜品信息和ID
2.  调用load_prompt_template函数，根据工具名字获取对应的提示词模版内容
3.  处理向量数据库检索到的内容，添加到提最终提示词模版中
4.  调用call_llm函数
5.  构建模型返回结果和检索菜品id的字典



mcp.py代码片段如下

```python
@tool
def menu_inquiry(query: str) -> Dict[str, Any]:
    """
    智能菜品咨询工具

    专门处理与菜品相关的所有查询，包括：
    - 菜品介绍和详细信息
    - 价格和营养信息
    - 菜品推荐和搭配建议
    - 过敏原和饮食限制相关问题
    - 菜品可用性和特色介绍

    该工具会自动通过语义搜索找到最相关的菜品信息，然后基于这些信息回答用户问题。

    Args:
        query: 用户关于菜品的具体问题

    Returns:
        Dict[str, Any]: 包含推荐建议和菜品ID的字典
        {
            "recommendation": "基于菜品信息的推荐建议",
            "menu_ids": ["菜品ID1", "菜品ID2"]
        }

    Raises:
        ToolException: 当处理菜品查询时发生错误
    """
    # 1.加载提示词模版
    try:
        template = load_template("menu_inquiry")

        # 2. 语义检索
        similar_result=search_menu_items_with_id(query,2)

        # 3.构建菜品的查询
        if similar_result["contents"]:
            menu_context="\n".join([f"- {content}" for content  in similar_result["contents"]])
            full_query=f"用户问题:{query}\\n 当前提供的菜品信息：\n{menu_context}\\n请基于以上菜品信息回答用户的问题."
        else:
            full_query = f"用户问题：{query}\n\n抱歉，没有找到相关的菜品信息,请基于一般菜谱回答用户问题."

        # 4. 调用模型
        response=call_llm(full_query,template)

        return {
            "recommendation": response,
            "menu_ids": similar_result["ids"]
        }
    except Exception as  e:
        raise ToolException(f"菜品咨询处理失败: {str(e)}")
```



##### ⑤ 定义配送范围检查工具

1. 获取配送模式
2. 调用配送检查功能
3. 构建配送信息查询结果



mcp.py代码片段如下

```python
@tool
def delivery_check_tool(address: str, travel_mode: str) -> str:
    """
    配送范围检查工具

    检查指定地址是否在配送范围内，并提供距离信息。

    Args:
        address: 配送地址
        travel_mode: 距离计算方式 (1=步行距离, 2=骑行距离, 3=驾车距离)

    Returns:
        str: 配送检查结果的格式化信息

    Raises:
        ToolException: 当配送检查失败时
    """

    # 调用配送检查功能
    try:
        result = check_delivery_range(address,travel_mode)

        MODE_MAPPING = {
            "1": "步行距离",
            "2": "骑行距离",
            "3": "驾车距离",

        }

        if result["status"] == "success":
            status_text = "✅ 可以配送" if result["in_range"] else "❌ 超出配送范围"

            response = f"""
        配送信息查询结果：
    
        配送地址：{result['formatted_address']}
        配送距离：{result['distance']}公里 ({MODE_MAPPING[travel_mode]})
        配送状态：{status_text}
                    """.strip()

        else:
            response = f"❌ 配送查询失败：{result['message']}"

        return response
    except  Exception as e:
        raise ToolException(f"配送检查失败: {str(e)}")
```

#### 2.2 测试功能

```python
if __name__ == "__main__":
    # 测试工具功能
    print("=" * 60)
    print("MCP工具测试")
    print("=" * 60)

    # 测试常规问询工具
    print("\n1. 测试常规问询工具:")
    try:
        result1 = general_inquiry.invoke({"query": "你们餐厅的营业时间是什么时候？", "context": ""})
        print(f"回复: {result1}")
    except Exception as e:
        print(f"错误: {e}")

    # 测试菜品咨询工具
    print("\n2. 测试智能菜品咨询工具:")
    try:
        result2 = menu_inquiry.invoke({"query": "推荐一些适合减肥的菜品"})
        print(f"推荐建议: {result2.get('recommendation', '无推荐')}")
        print(f"菜品ID: {result2.get('menu_ids', [])}")
    except Exception as e:
        print(f"错误: {e}")
    #
    # # 测试配送检查工具
    print("\n3. 测试配送检查工具:")
    try:
        result3 = delivery_check_tool.invoke({"address": "武汉大学", "travel_mode": "2"})
        print(f"回复: {result3}")
    except Exception as e:
        print(f"错误: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
```



#### 2.3 文件完整代码

```python

import os
from langchain.tools import tool
from langchain_core.tools import ToolException

from  tools.pine_cone_tool import  search_menu_items_with_id
from  tools.amap_tool import check_delivery_range
from typing import  Dict,Any

from  tools.llm_tool import call_llm
def   load_template(template_name:str):
    project_root = os.path.dirname(os.path.dirname(__file__))
    template_file=os.path.join(project_root,"prompt",f"{template_name}.txt")

    with open(template_file,"r",encoding="utf-8") as f:
        return f.read().strip()

@tool
def general_inquiry(query: str, context: str) -> str:
    """
        常规问询工具

        处理用户的一般性问题，包括但不限于：
        - 餐厅介绍和服务信息
        - 营业时间和联系方式
        - 优惠活动和会员服务
        - 其他非菜品相关的咨询

        Args:
            query: 用户的问询内容
            context: 可选的上下文信息，用于提供更精准的回复

        Returns:
            str: 针对用户问询的智能回复

        Raises:
            ToolException: 当处理查询时发生错误
        """


    try:
        # 1. 加载提示词模版
        template=load_template("general_inquiry")

        # 2. 处理输入问题
        full_query=  f"当前提供的上下文:{context} \\n 用户问题: {query}"  if   context else f"用户问题: {query}"

        response = call_llm(full_query, template)

        return  response
    except Exception as e:
        raise ToolException(f"常规问询处理失败: {str(e)}")


@tool
def menu_inquiry(query: str) -> Dict[str, Any]:
    """
    智能菜品咨询工具

    专门处理与菜品相关的所有查询，包括：
    - 菜品介绍和详细信息
    - 价格和营养信息
    - 菜品推荐和搭配建议
    - 过敏原和饮食限制相关问题
    - 菜品可用性和特色介绍

    该工具会自动通过语义搜索找到最相关的菜品信息，然后基于这些信息回答用户问题。

    Args:
        query: 用户关于菜品的具体问题

    Returns:
        Dict[str, Any]: 包含推荐建议和菜品ID的字典
        {
            "recommendation": "基于菜品信息的推荐建议",
            "menu_ids": ["菜品ID1", "菜品ID2"]
        }

    Raises:
        ToolException: 当处理菜品查询时发生错误
    """
    # 1.加载提示词模版
    try:
        template = load_template("menu_inquiry")

        # 2. 语义检索
        similar_result=search_menu_items_with_id(query,2)

        # 3.构建菜品的查询
        if similar_result["contents"]:
            menu_context="\n".join([f"- {content}" for content  in similar_result["contents"]])
            full_query=f"用户问题:{query}\\n 当前提供的菜品信息：\n{menu_context}\\n请基于以上菜品信息回答用户的问题."
        else:
            full_query = f"用户问题：{query}\n\n抱歉，没有找到相关的菜品信息,请基于一般菜谱回答用户问题."

        # 4. 调用模型
        response=call_llm(full_query,template)

        return {
            "recommendation": response,
            "menu_ids": similar_result["ids"]
        }
    except Exception as  e:
        raise ToolException(f"菜品咨询处理失败: {str(e)}")


@tool
def delivery_check_tool(address: str, travel_mode: str) -> str:
    """
    配送范围检查工具

    检查指定地址是否在配送范围内，并提供距离信息。

    Args:
        address: 配送地址
        travel_mode: 距离计算方式 (1=步行距离, 2=骑行距离, 3=驾车距离)

    Returns:
        str: 配送检查结果的格式化信息

    Raises:
        ToolException: 当配送检查失败时
    """

    # 调用配送检查功能
    try:
        result = check_delivery_range(address,travel_mode)

        MODE_MAPPING = {
            "1": "步行距离",
            "2": "骑行距离",
            "3": "驾车距离",

        }

        if result["status"] == "success":
            status_text = "✅ 可以配送" if result["in_range"] else "❌ 超出配送范围"

            response = f"""
        配送信息查询结果：
    
        配送地址：{result['formatted_address']}
        配送距离：{result['distance']}公里 ({MODE_MAPPING[travel_mode]})
        配送状态：{status_text}
                    """.strip()

        else:
            response = f"❌ 配送查询失败：{result['message']}"

        return response
    except  Exception as e:
        raise ToolException(f"配送检查失败: {str(e)}")


if __name__ == "__main__":
    # 测试工具功能
    print("=" * 60)
    print("MCP工具测试")
    print("=" * 60)

    # 测试常规问询工具
    print("\n1. 测试常规问询工具:")
    try:
        result1 = general_inquiry.invoke({"query": "你们餐厅的营业时间是什么时候？", "context": ""})
        print(f"回复: {result1}")
    except Exception as e:
        print(f"错误: {e}")

    # 测试菜品咨询工具
    print("\n2. 测试智能菜品咨询工具:")
    try:
        result2 = menu_inquiry.invoke({"query": "推荐一些适合减肥的菜品"})
        print(f"推荐建议: {result2.get('recommendation', '无推荐')}")
        print(f"菜品ID: {result2.get('menu_ids', [])}")
    except Exception as e:
        print(f"错误: {e}")
    #
    # # 测试配送检查工具
    print("\n3. 测试配送检查工具:")
    try:
        result3 = delivery_check_tool.invoke({"address": "武汉大学", "travel_mode": "2"})
        print(f"回复: {result3}")
    except Exception as e:
        print(f"错误: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
```



### 3. 定义业务主类

#### 3.1 新建service.py文件

> 模块作用：AiMenu 服务封装
>
> 简单封装两个核心功能：
>
> - smart_chat: 调用 Langchain_main
> - delivery_check: 调用 check_delivery_range

##### ① 定义smart_chat函数

```python
def smart_chat(user_query: str):
    """智能对话 - 调用 Langchain_main"""
    from Langchain.main import Langchain_main
    return Langchain_main(user_query)
```



##### ② 定义delivery_check函数

```python
def delivery_check(address: str, travel_mode: int = 3):
    """配送查询 - 调用 check_delivery_range"""
    from tools.amap_tool import check_delivery_range, DistanceMode
    
    # 模式映射
    modes = {1: DistanceMode.STRAIGHT, 2: DistanceMode.DRIVING, 3: DistanceMode.RIDING}
    mode = modes.get(travel_mode, DistanceMode.RIDING)
    
    return check_delivery_range(address, mode)
```

#### 3.2 业务完整代码

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiMenu 服务封装

简单封装两个核心功能：
- smart_chat: 调用 Langchain_main
- delivery_check: 调用 check_delivery_range
"""

import os
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def smart_chat(user_query: str):
    """智能对话 - 调用 Langchain_main"""
    from Langchain.main import Langchain_main
    return Langchain_main(user_query)

def delivery_check(address: str, travel_mode: int = 3):
    """配送查询 - 调用 check_delivery_range"""
    from tools.amap_tool import check_delivery_range, DistanceMode
    
    # 模式映射
    modes = {1: DistanceMode.STRAIGHT, 2: DistanceMode.DRIVING, 3: DistanceMode.RIDING}
    mode = modes.get(travel_mode, DistanceMode.RIDING)
    
    return check_delivery_range(address, mode)

if __name__ == "__main__":
    # 简单测试
    print("测试智能对话:")
    print(smart_chat("营业时间"))
    
    print("\n测试配送查询:")
    print(delivery_check("北京市海淀区清华大学"))

```

### 4. 定义业务统一入口

#### 4.1 新建main.py文件

> 模块作用：
>
> 智能点餐助手主程序，该程序构建了一个包含工具选择功能的LLM系统，能够：
>
> 1. 自动选择合适的工具（常规咨询、菜品推荐、配送检查）
> 2. 调用相应工具并返回结果
> 3. 提供自然、友好的对话体验

##### ① 将文件目录添加到系统

1. 获取当前文件目录
2. 导入相关模块
3. 加载环境变量

##### ② 定义智慧点餐类

1. 定义构造函数，配置模型api_key、工具映射字典、默认意图分析提示词模版（系统指令）
2. 定义意图分析函数，分析用户意图并选择工具
3. 定义工具执行函数
4. 定义对话函数

###### ① 意图分析提示词

```python
    # 意图分析系统指令
    self.intent_instruction = """你是一个智能餐厅助手的意图分析器。
    请分析用户问题，选择最合适的工具来处理：

    工具说明：
    1. general_inquiry: 处理餐厅常规咨询（营业时间、地址、电话、优惠活动等）
    2. menu_inquiry: 智能菜品推荐和咨询（推荐菜品、介绍菜品、询问菜品信息等）
    3. delivery_check_tool: 配送范围检查（查询某个地址是否在配送范围内）

    请只返回JSON格式：
    {
        "tool_name": "工具名称",
        "format_query": "处理后的用户问题"
    }

    示例：
    用户："你们几点营业？" -> {"tool_name": "general_inquiry", "format_query": "营业时间"}
    用户："推荐川菜系列的菜品" -> {"tool_name": "menu_inquiry", "format_query": "推荐川菜"}
    用户："能送到武汉大学吗？" -> {"tool_name": "delivery_check_tool", "format_query": "武汉大学"}"""

```

```python

# 改进的意图分析系统指令
self.intent_instruction = """你是一个智能餐厅助手的意图分析器。
请分析用户问题意图，并且选择最合适的工具来处理：

工具说明：
1. general_inquiry: 处理餐厅常规咨询（营业时间、地址、电话、优惠活动、预约等）
2. menu_inquiry: 处理智能菜品推荐和咨询（推荐菜品、介绍菜品、询问菜品信息、点餐等）
3. delivery_check_tool: 处理配送范围检查（查询某个地址是否在配送范围内、能否送达等）

你必须严格按照以下JSON格式返回，不要包含任何其他文字：
{
    "tool_name": "工具名称",
     "format_query": "处理后的用户问题"
}

正确示例：
用户："你们几点营业？" -> {"tool_name": "general_inquiry", "format_query": "营业时间"}
用户："推荐川菜系列的菜品" -> {"tool_name": "menu_inquiry", "format_query": "推荐川菜"}
用户："能送到武汉大学吗？" -> {"tool_name": "delivery_check_tool", "format_query": "武汉大学"}
用户："我想预约今晚的位置" -> {"tool_name": "general_inquiry", "format_query": "预约今晚位置"}
用户："有什么招牌菜推荐吗？" -> {"tool_name": "menu_inquiry", "format_query": "推荐招牌菜"}

重要规则：
- 只返回纯JSON，不要有任何额外字符和解释
- 确保JSON格式完全正确
- tool_name必须是以下之一：general_inquiry, menu_inquiry, delivery_check_tool
- format_query要简洁明了地概括用户问题

记住：如果你错误的选择工具，系统将会出现崩溃。"""
```



###### ② 意图分析函数

- 参数：user_query: 用户输入的问题 ，返回值：包含工具名称和处理后问题的字典
- 调用call_llm函数进行意图分析
- 解析模型响应数据
- 异常机制做兜底



main.py 代码片段如下：

```python
    def  analyze_intent(self,user_query:str)->Dict[str,str]:
        """
            意图分析
            :param user_query: 用户输入原始问题
            :return: 标准后的问题以及模型选择的工具名字
       """
        try:
            # 1. 调用模型
            response=call_llm(user_query,self.intent_instruction)

            try:
            # 2. 解析模型结果
                result=json.loads(response)
                if  result['tool_name'] in self.tools:
                    return  result
                else:
                    return {"tool": "general_inquiry", "query": user_query}
            except JSONDecodeError as e:

            # 3. 如果模型结果符符合预期使用降级方案做兜底
                logger.info("JSON反序列工具信息对象失败,尝试从响应中提取工具信息")
                if  "menu" in response.lower() or "菜品" in response or "推荐" in  response:
                    return {"tool_name":"menu_inquiry","format_query":user_query}
                elif "delivery" in  response.lower() or  "配送" in response or  "送到" in response:
                    return {"tool_name": "delivery_check_tool", "format_query": user_query}
                else:
                    return {"tool": "general_inquiry", "query": user_query}
        except Exception as e:
            logger.error(f"调用LLM进行意图分析出错,原因{e}")
            return {"tool": "general_inquiry", "query": user_query}
```



- 带重试修复和降级兜底处理机制

```python
    def analyse_intent(self, query: str, last_error: str) -> Dict[str, str]:
        """分析自然语言语义 返回工具信息"""

        try:
            instruction = self.intent_instruction
            if last_error:
                instruction += f"\n\n上次解析失败，错误信息：{last_error}\n请根据错误信息修正JSON格式，确保返回正确的JSON。"

            llm_json_str_response = invoke_llm(query, instruction)
            logger.info(f"模型原始响应: {llm_json_str_response}")

            # 尝试清理响应，移除可能的markdown代码块标记
            cleaned_response = self.clean_json_response(llm_json_str_response)

            structured_response = json.loads(cleaned_response)

            # 验证必需字段
            if not all(key in structured_response for key in ["tool_name", "format_query"]):
                raise JSONDecodeError("缺少必需字段", cleaned_response, 0)

            # 验证工具名称有效性
            if structured_response["tool_name"] not in self.tools:
                raise ValueError(f"无效的工具名称: {structured_response['tool_name']}")

            return structured_response

        except (JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON解析失败: {e}")
            raise e  # 将异常抛给上层处理重试

    def _clean_json_response(self, response: str) -> str:
        """
        清理JSON响应，移除可能的markdown代码块标记等
        """
        # 移除 ```json 和 ``` 标记
        if response.startswith('```json'):
            response = response[7:]
        if response.endswith('```'):
            response = response[:-3]

        # 移除首尾空白
        response = response.strip()

        # 如果响应以 { 开头但可能包含其他内容，尝试提取第一个完整的JSON对象
        start_idx = response.find('{')
        end_idx = response.rfind('}')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            response = response[start_idx:end_idx + 1]

        return response

    def analyse_intent_with_retry(self, query: str) -> Dict[str, str]:
        logger.info(f"分析用户意图: {query}")

        last_error = None
        for retry in range(self.max_retries):
            try:
                logger.info(f"意图分析第 {retry + 1} 次尝试")
                result = self.analyse_intent(query, last_error)
                logger.info(f"意图分析成功: {result}")
                return result
            except(JSONDecodeError, ValueError) as e:
                last_error = str(e)
                logger.warning(f"第 {retry + 1} 次尝试失败: {last_error}")

                if retry < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"经过 {self.max_retries} 次重试后仍然失败，使用兜底方案")

    def _fallback_intent_analysis(self, query: str) -> Dict[str, str]:
        """兜底意图分析"""
        logger.info("使用兜底意图分析")
        # 配送相关关键词
        delivery_keywords = ["配送", "送达", "送到", "送货", "外卖", "地址", "区域", "范围"]
        # 菜单相关关键词
        menu_keywords = ["菜单", "菜品", "推荐", "点餐", "招牌", "特色", "什么好吃", "有什么菜"]
        # 常规咨询关键词
        general_keywords = ["营业", "时间", "电话", "预约", "预订", "位置", "在哪", "多少钱", "优惠", "活动"]
        # 检查配送意图
        if any(keyword in query for keyword in delivery_keywords):

            return {"tool_name": "delivery_check_tool", "format_query": uses_query}

        # 检查菜单意图
        elif any(keyword in query for keyword in menu_keywords):
            return {"tool_name": "menu_inquiry", "format_query": query}

        # 默认常规咨询
        else:
            return {"tool_name": "general_inquiry", "format_query": query}

```



###### ③ 工具执行函数

- 参数：工具名称 、处理后的查询问题，返回值：工具执行结果
- 从工具映射表中，根据工具名，获取工具对象
- 根据工具名，判断调用对应工具实例方法
- 返回工具调用结果



main.py 代码片段如下：

```python
    def execute_tool(self,format_query:str,tool_name:str):
       """
          执行指定的工具
        
        Args:
            tool_name: 工具名称
            query: 查询内容
            
        Returns:
            工具执行结果
        """
        try:
            tool_func=self.tools["tool_name"]
            if tool_name=="general_inquiry":
                result=tool_func.invoke({"query": format_query})
            elif tool_name=="menu_inquiry":
                result = tool_func.invoke({"query": format_query})
            else:
                # delivery_check_tool需要address和travel_mode参数
                result = tool_func.invoke({"address": format_query, "travel_mode": "2"})
            return result
        except Exception as e:
            return f"工具执行出错 ({tool_name}): {str(e)}"
```



###### ④ 对话函数

- 参数：用户输入的原始问题，返回值：助手回复内容
- 调用analyze_intent函数，分析当前问题，选择工具
- 提取工具名称和增强后的查询
- 调用execute_tool函数，执行工具
- 返回结果



main.py代码片段如下

```python
 def  chat(self,user_query:str):
        """
        主要对话函数

        Args:
            user_query: 用户输入的问题

        Returns:
            智能助手的回复
        """

        print(f"用户问题:{user_query}")

        # 1.调用模型 进行意图分析 返回标准化后问题 以及选择的工具名字
        intent_result=self.analyze_intent(user_query)
        format_query = intent_result['format_query']
        tool_name=intent_result['tool_name']
        print(f"对应格式后要处理的问题：{format_query},以及对应的工具{tool_name}")


        # 2. 执行工具
        result=self.execute_tool(format_query,tool_name)
        print(f"工具{tool_name}执行完成")

        # 3. 返回工具结果
        return result
```



##### ③  定义主函数

1. 实例化智慧点餐类
2. 调用智慧点餐实例chat函数，进行聊天



main.py代码片段如下

```python
def  langchain_main(user_query:str):
    """调用"""
    try:
        # 1.初始化助手
        assistant=SmartRestaurantAssistant()

        # 2.调用聊天助手
        response=assistant.chat(user_query or "你们餐厅的营业时间是什么时候" ) # 默认测试查询

        print(f"\n🤖 助手回复: {response}")
        # 3.返回对话结果
        return response
    except Exception as e:
        error_msg = f"出现错误: {e}"
        print(error_msg)
        return error_msg
```



#### 4.2 测试业务功能

```python
if __name__ == "__main__":
    # 可以选择运行单次调用或测试模式
    Langchain_main()
```





#### 4.3 文件完整代码

```python
import json
from json import JSONDecodeError
from  typing import  Dict
import os
# from Langchain.mcp import general_inquiry, menu_inquiry, delivery_check_tool
from tools.llm_tool import call_llm
import  logging
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)
class  SmartRestaurantAssistant:

    def __init__(self):
        """初始化助手"""
        # 检查API密钥
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("请设置DASHSCOPE_API_KEY环境变量")

        # 工具映射
        self.tools = {
            "general_inquiry": "",
            "menu_inquiry": "",
            "delivery_check_tool": ""
        }

        # 意图分析系统指令
        self.intent_instruction = """你是一个智能餐厅助手的意图分析器。
    请分析用户问题，选择最合适的工具来处理：

    工具说明：
    1. general_inquiry: 处理餐厅常规咨询（营业时间、地址、电话、优惠活动等）
    2. menu_inquiry: 智能菜品推荐和咨询（推荐菜品、介绍菜品、询问菜品信息等）
    3. delivery_check_tool: 配送范围检查（查询某个地址是否在配送范围内）

    请只返回JSON格式：
    {
        "tool_name": "工具名称",
        "format_query": "处理后的用户问题"
    }

    示例：
    用户："你们几点营业？" -> {"tool_name": "general_inquiry", "format_query": "营业时间"}
    用户："推荐川菜系列的菜品" -> {"tool_name": "menu_inquiry", "format_query": "推荐川菜"}
    用户："能送到武汉大学吗？" -> {"tool_name": "delivery_check_tool", "format_query": "武汉大学"}"""




    def  analyze_intent(self,user_query:str)->Dict[str,str]:
        """
            意图分析
            :param user_query: 用户输入原始问题
            :return: 标准后的问题以及模型选择的工具名字
       """
        try:
            # 1. 调用模型
            response=call_llm(user_query,self.intent_instruction)

            try:
            # 2. 解析模型结果
                result=json.loads(response)
                if  result['tool_name'] in self.tools:
                    return  result
                else:
                    return {"tool": "general_inquiry", "query": user_query}
            except JSONDecodeError as e:

            # 3. 如果模型结果符符合预期使用降级方案做兜底
                logger.info("JSON反序列工具信息对象失败,尝试从响应中提取工具信息")
                if  "menu" in response.lower() or "菜品" in response or "推荐" in  response:
                    return {"tool_name":"menu_inquiry","format_query":user_query}
                elif "delivery" in  response.lower() or  "配送" in response or  "送到" in response:
                    return {"tool_name": "delivery_check_tool", "format_query": user_query}
                else:
                    return {"tool": "general_inquiry", "query": user_query}
        except Exception as e:
            logger.error(f"调用LLM进行意图分析出错,原因{e}")
            return {"tool": "general_inquiry", "query": user_query}

    def execute_tool(self,format_query:str,tool_name:str):
        """
        执行工具调用
        :param format_query: 格式后的问题
        :param tool_name:  选择工具的名字
        :return: 工具的执行结果
        """
        try:
            tool_func=self.tools["tool_name"]
            if tool_name=="general_inquiry":
                result=tool_func.invoke({"query": format_query})
            elif tool_name=="menu_inquiry":
                result = tool_func.invoke({"query": format_query})
            else:
                # delivery_check_tool需要address和travel_mode参数
                result = tool_func.invoke({"address": format_query, "travel_mode": "2"})
            return result
        except Exception as e:
            return f"工具执行出错 ({tool_name}): {str(e)}"

    def  chat(self,user_query:str):
        """
        主要对话函数

        Args:
            user_query: 用户输入的问题

        Returns:
            智能助手的回复
        """

        print(f"用户问题:{user_query}")

        # 1.调用模型 进行意图分析 返回标准化后问题 以及选择的工具名字
        intent_result=self.analyze_intent(user_query)
        format_query = intent_result['format_query']
        tool_name=intent_result['tool_name']
        print(f"对应格式后要处理的问题：{format_query},以及对应的工具{tool_name}")


        # 2. 执行工具
        result=self.execute_tool(format_query,tool_name)
        print(f"工具{tool_name}执行完成")

        # 3. 返回工具结果
        return result



def  langchain_main(user_query:str):
    """调用"""
    try:
        # 1.初始化助手
        assistant=SmartRestaurantAssistant()

        # 2.调用聊天助手
        response=assistant.chat(user_query or "你们餐厅的营业时间是什么时候" ) # 默认测试查询

        print(f"\n🤖 助手回复: {response}")
        # 3.返回对话结果
        return response
    except Exception as e:
        error_msg = f"出现错误: {e}"
        print(error_msg)
        return error_msg

if __name__ == "__main__":
    # 可以选择运行单次调用或测试模式
    langchain_main()

```

