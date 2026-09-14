import json
from json import JSONDecodeError
from typing import Dict
from  tools.llm_tool import call_llm
import  os
from  LangChain.mcp import delivery_check_tool,general_inquiry,menu_inquiry


from dotenv  import  load_dotenv
load_dotenv()


import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SmartRestaurantAssistant:
    """聊天助手类"""

    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("请设置DASHSCOPE_API_KEY环境变量")

        # 工具映射
        self.tools = {
            "general_inquiry": general_inquiry, # 工具对象
            "menu_inquiry": menu_inquiry, # 工具对象
            "delivery_check_tool": delivery_check_tool # 工具对象
        }

        # 意图分析系统指令
        self.intent_instruction = """你是一个智能餐厅助手的意图分析器。
            请分析用户问题意图，并且选择最合适的工具来处理：

            工具说明：
            1. general_inquiry: 处理餐厅常规咨询（营业时间、地址、电话、优惠活动等）
            2. menu_inquiry: 处理智能菜品推荐和咨询（推荐菜品、介绍菜品、询问菜品信息等）
            3. delivery_check_tool: 处理配送范围检查（查询某个地址是否在配送范围内）

            请只返回JSON格式：
            {
                "tool_name": "工具名称",
                "format_query": "处理后的用户问题"
            }

            示例：
            用户："你们几点营业？" -> {"tool_name": "general_inquiry", "format_query": "营业时间"}
            用户："推荐川菜系列的菜品" -> {"tool_name": "menu_inquiry", "format_query": "推荐川菜"}
            用户："能送到武汉大学吗？" -> {"tool_name": "delivery_check_tool", "format_query": "武汉大学"}
            
            记住:如果你错误的选择工具，你将会受到很严重的惩罚，系统出现崩溃。 
            """

    def analyze_intent(self, user_query: str) -> Dict[str, str]:
            """
            分析用户的意图 返回结构化的字典
            :param user_query:  用户的原始输入
            :return:  dict {"format_query":"我想点一份川菜","tool_name:"}
            """
            # 1.调用模型
            try:
                llm_jons_str_response = call_llm(user_query, self.intent_instruction)
                try:
                    # 2.处理模型的结果
                    structured_response = json.loads(llm_jons_str_response)
                    if structured_response['tool_name'] in self.tools:
                        return structured_response
                except JSONDecodeError as e:
                    logger.error(f"模型返回的内容格式：{llm_jons_str_response},JSON反序列化失败,原因{e}")
                    # 正则处理一下:最麻烦
                    # 3.默认处理做兜底(简单处理一下)
                    if "delivery" in llm_jons_str_response.lower() or "配送" in llm_jons_str_response or "送达" in llm_jons_str_response:
                        return {"tool_name": "delivery_check_tool", "format_query": user_query}  # 配送范围查询工具
                    elif "menu" in llm_jons_str_response.lower() or "推荐" in llm_jons_str_response or "菜品" in llm_jons_str_response:
                        return {"tool_name": "menu_inquiry", "format_query": user_query}  # 菜品查询工具
                    else:
                        return {"tool_name": "general_inquiry", "format_query": user_query}  # 普通查询工具
            except Exception as e:
                logger.error(f"意图分析失败,原因：{e}")
            return {"tool_name": "general_inquiry", "format_query": user_query}  # 普通查询工具



    def execute_tool(self, format_query: str, tool_name: str):
        """
        根据输入的问题 找到对应的工具执行
        :param format_query:  格式后的问题
        :param tool_name:  工具的名字
        :return: 工具的执行结果 （str  or  dict）
        """
        try:
            # 1. 获取工具对象
            tool_func=self.tools[tool_name]

            # 2.执行工具
            if  tool_name=="general_inquiry":
                tool_result=tool_func.invoke({"query":format_query,"context":''})
            elif tool_name=="menu_inquiry":
                tool_result=tool_func.invoke({"query":format_query})
            else:
                tool_result=tool_func.invoke({"address":format_query,"travel_mode":"2"})
            # 3. 返回工具的结果
            return  tool_result
        except Exception as  e:
            logger.error(f"执行工具出错,原因: {e}")
            return f"执行工具出错,原因: {e}"

    def chat(self, user_query: str):
        """聊天方法"""
        logger.info(f"用户输入的问题：{user_query},准备分析用户意图")

        # 1.结合用户的输入分析自然语言 提取到字典结构的数据{"format_query":"我想点一份川菜","tool_name"}=
        response = self.analyze_intent(user_query)
        format_query = response['format_query']
        tool_name = response['tool_name']

        # 2.执行工具
        logger.info(f"格式后的输入{format_query},准备执行选择到的工具:{tool_name}")

        result = self.execute_tool(format_query, tool_name)
        logger.info("工具执行完成")
        return result


def langchain_chat(user_query: str):
    """聊天入口"""

    # 1. 初始聊天助手实例
    print("开始使用智慧点餐小助手")
    assistant = SmartRestaurantAssistant()


    query = user_query or "请问你们餐厅的营业时间在什么时候"  # 默认查询值

    # 2. 调用聊天助手实例的聊天方法
    assistant_response=assistant.chat(query)
    print(f"助手的回复:{assistant_response}")
    # 3. 返回助手的回复内容
    return  assistant_response


# 测试
if __name__ == '__main__':
    pass

    # assistant = SmartRestaurantAssistant()
    # 1.意图分析的测试
    # analyze_result=assistant.analyze_intent("请问你们餐厅的营业时间在什么时候")
    # print(f"意图分析后的结果:{analyze_result}")

    # analyze_result1 = assistant.analyze_intent("请问武汉大学能不能配送到")
    # print(f"意图分析后的结果:{analyze_result1}")

    # analyze_result2 = assistant.analyze_intent("我想吃鲁系列的菜品，请你给我找一些川菜系列的菜品出来")
    # print(f"意图分析后的结果:{analyze_result2}")



    # 3.测试聊天
    # langchain_chat("请问你们餐厅的营业时间在什么时候")
    # langchain_chat("请问武汉大学能不能配送到")
    # langchain_chat("请问能不能配送到洪山区光谷天地")
    # langchain_chat("我想吃鲁系列的菜品，请你给我找一些川菜系列的菜品出来")
    # {
    # 'recommendation':
    # '您好！很高兴为您推荐我们餐厅的川菜系列菜品。根据您对川菜的兴趣，我为您挑选了两款非常经典的川菜，它们各有独特的风味和特点。\n\n###
    # 1. **麻婆豆腐**\n**价格**: ¥18.00  \n**特色**: 这道四川传统名菜以其嫩滑的豆腐和浓郁的麻辣汤汁而闻名，是下饭的绝佳选择。麻婆豆腐融合了麻辣鲜香的味道，每一口都充满了层次感。嫩豆腐与牛肉末、豆瓣酱、花椒等食材完美搭配，不仅味道诱人，还具有丰富的口感。  \n**烹饪方法**: 采用烧炒的方式，让豆腐充分吸收调料的香味，同时保持其嫩滑的质感。  \n**营养价值**: 麻婆豆腐富含优质蛋白质和钙，适合补充日常营养。不过需要注意的是，它含有大豆，如果您对大豆过敏，请谨慎食用。  \n**推荐理由**: 如果您喜欢麻辣口味，麻婆豆腐绝对是您的不二之选。它的价格实惠，性价比高，是川菜中的经典之作。\n\n###
    # 2. **宫保鸡丁**\n**价格**: ¥28.00  \n**特色**: 宫保鸡丁是一道经典川菜，鸡肉丁搭配花生米，酸甜微辣，口感丰富。这道菜的特点在于它的多层次口味，既有酸甜的调味，又有微微的辣味，非常适合喜欢多样化口味的食客。  \n**烹饪方法**: 使用爆炒的方式，确保鸡肉和花生米的鲜美口感。  \n**营养价值**: 宫保鸡丁富含优质蛋白质，适合健身或需要补充能量的人群。不过请注意，它含有花生，如果您对花生过敏，请避免食用。  \n**推荐理由**: 如果您喜欢口感丰富且带有酸甜微辣的菜肴，宫保鸡丁将是您的最佳选择。它不仅美味可口，还能满足您对经典川菜的期待。\n\n### 综合建议：\n如果您喜欢麻辣口味，可以尝试麻婆豆腐；如果您更倾向于酸甜微辣的口感，宫保鸡丁则是更好的选择。这两款川菜都是餐厅的招牌菜，无论您选择哪一道，都能体验到地道的川菜风味。\n\n希望这些建议对您有所帮助，祝您用餐愉快！如果还有其他问题或需求，请随时告诉我。',
    # 'menu_ids': ['2', '1']
    # }





