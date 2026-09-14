import os.path

from langchain_core.tools import tool, ToolException
import  logging
from  tools.llm_tool import  call_llm
from  typing import  Dict,Any
from  tools.pine_cone_tool import search_menu_items_with_id
from  tools.amap_tool import check_delivery_range

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

def  load_prompt(tool_name:str)->str:
    """
    根据传入的工具名字 返回对应工具要用到的提示词模版内容（结构化指令）
    :param tool_name: 输入工具的名字
    :return:  提示词内容
    """
    try:
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        load_dir = project_dir + "\prompt\\" + f"{tool_name}.txt"

        with open(load_dir, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"加载提示词模版文件出错 {e}")
        return "请根据用户的当前输入问题,回答问题,生成结果"








@tool
def general_inquiry(query: str, context: str=None) -> str:
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
        # 1. 加载普通查询工具的提示词模版
        general_prompt=load_prompt("general_inquiry")

        # 2. 调用模型（对结果做一次优化 处理真正常规问的问题：模型回复常规查询）扩展（各种优化的记忆组件选择 ）
        # 从记忆组件中加载记忆组件中的对话 然后格式化处理 插入到context,作为模型回答本轮普通查询的上下文参考(用户体现更高) TODO
        full_query= f"用户当前的问题:{query}\n\n 上下文内容:{context}"  if  context else f"当前用户的问题:{query}"

        llm_response=call_llm(full_query,general_prompt)

        # 写入到记忆组件(对模型回复的结果在做清洗，洗涤当前业务用到的 越精炼且有参考意义越好) TODO

        # 3. 返回结果（工具的结果 最终结果）
        return  llm_response
    except Exception as  e:
        raise ToolException(f"调用general_inquiry工具失败,原因:{e}")



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
    menu_prompt=load_prompt("menu_inquiry")

    # 2. 调用模型
    # 2.1 根据输入的问题（格式后的问题） 检索向量数据库
    similar_result=search_menu_items_with_id(query)
    # 2.2 从向量数据库中获取检索到的菜品
    similar_items =similar_result['contents']
    menu_context="\n".join([f"- {item}" for item in similar_items]).strip()
    # 2.3 提供检索到菜品信息的上下文  TODO :继续携带上记忆组件的上下文
    full_query= f"当前用户输入的问题:{query}\n\n 提供的上下文内容:\n {menu_context}\n\n 请结合以上提供的信息,生成菜品信息的推荐" if  menu_context else  f"当前用户输入的问题:{query},结合一般性菜谱信息生成菜品信息的推荐"
    # 2.4 调用
    llm_response=call_llm(full_query,menu_prompt)

    # 3.返回模型结果

    return  {
        "recommendation":llm_response,
        "menu_ids": similar_result["ids"] # 菜品Id 从模型中在利用正则表达式提取
    }


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
        result = check_delivery_range(address, travel_mode)

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








if __name__ == '__main__':
    # 1. 测试加载提示模版内容
    # print("1.测试不同工具对应加载到的提示模版内容 ")
    # general_prompt=load_prompt("general_inquiry")
    #
    # print(f"加载到的提示词模版内容:{general_prompt}")
    # menu_prompt = load_prompt("menu_inquiry")
    #
    # print(f"加载到的提示词模版内容:{menu_prompt}")


    # 2.测试常规查询的工具调用
    # print("\n2.测试常规查询的工具调用")
    # llm_response=general_inquiry("请问你们餐厅的营业时间是多少")
    # print(f"常规查询工具调用后的结果:{llm_response}")

    # 3.测试菜品相关查询的工具调用
    print("\n3.测试菜品相关查询的工具调用")
    # llm_response1 = menu_inquiry("请帮我点川菜系列的菜品")
    # llm_response1 = menu_inquiry("请帮我点一份麻婆豆腐")
    # print(f"测试菜品相关查询的工具调用:{llm_response1}")

    # 测试菜品相关查询的工具调用:
    # {
    #  'recommendation': '您好！根据您的需求，我为您推荐了两款经典的川菜，相信您一定会喜欢。\n\n**一、麻婆豆腐（菜品ID：2）**\n- **价格**：¥18.00\n- **特色**：这道菜是四川的传统名菜，以嫩滑的豆腐为主料，搭配麻辣鲜香的汤汁，每一口都充满了浓郁的川味。它那独特的麻辣味道能够刺激味蕾，让人食欲大增，绝对是下饭神器。\n- **主要食材**：嫩豆腐、牛肉末、豆瓣酱、花椒等。牛肉末为这道菜增添了丰富的口感，而豆瓣酱和花椒则是麻辣风味的主要来源。\n- **烹饪方法**：采用烧炒的方式，使得豆腐吸收了汤汁的味道，同时保留了自身的嫩滑口感。\n- **营养与卡路里**：豆腐富含优质蛋白质、钙、铁等营养成分，有助于增强身体免疫力。不过，由于加入了牛肉末，所以它的热量相对较高，每100克约含90千卡左右。\n- **过敏原提醒**：该菜品含有大豆，如果您对大豆过敏，请谨慎选择。此外，它可能含有麸质，如果您需要避免麸质的食物，也请注意。\n\n**二、宫保鸡丁（菜品ID：1）**\n- **价格**：¥28.00\n- **特色**：这是一道经典的川菜，鸡肉丁与花生米相结合，酸甜微辣的口味层次分明，口感丰富。鸡肉的鲜嫩与花生米的香脆相得益彰，再配上青椒、红椒和葱段，色彩鲜艳，十分诱人。\n- **主要食材**：鸡胸肉、花生米、青椒、红椒、葱段等。鸡胸肉提供了丰富的蛋白质，而花生米则带来了香脆的口感和坚果的香气。\n- **烹饪方法**：通过爆炒的方式，使鸡肉充分吸收调料的味道，同时也保持了鸡肉的嫩滑和花生米的香脆。\n- **营养与卡路里**：鸡胸肉富含优质蛋白质、维生素B族等营养成分，有助于维持身体健康。但是，由于加入了花生米，其热量相对较高，每100克约含150千卡左右。\n- **过敏原提醒**：该菜品含有花生，如果您对花生过敏，请不要选择此菜。另外，它也可能含有麸质，如果您需要避免麸质的食物，也要注意。\n\n如果您想要体验正宗的川菜麻辣味，麻婆豆腐是个不错的选择；若您更倾向于酸甜微辣且口感丰富的菜肴，那么宫保鸡丁将是您的理想之选。希望这些推荐能帮助您找到满意的美食！',
    #  'menu_ids': ['2', '1']
    # }

    # 测试菜品相关查询的工具调用:{
    # 'recommendation': '您好！根据您的需求，我为您推荐我们的招牌麻婆豆腐。\n\n【麻婆豆腐】\n- **价格**：¥18.00\n- **特色**：这道菜是四川的传统名菜，选用嫩滑的豆腐作为主料，搭配精心调制的麻辣汤汁，每一口都能感受到豆腐的细腻与汤汁的浓郁麻辣，堪称下饭神器。\n- **口味**：麻辣鲜香，香气四溢，让人食欲大增。\n- **主要食材**：嫩豆腐、牛肉末、豆瓣酱、花椒等。\n- **烹饪方法**：采用烧炒的方式，让豆腐充分吸收汤汁的味道。\n- **营养价值**：豆腐富含植物蛋白，有助于补充身体所需的营养。\n- **过敏原提醒**：本菜品含有大豆，如果您对大豆过敏，请告知我们，我们可以为您提供其他适合的选择。\n\n这款麻婆豆腐是我们餐厅的经典菜肴，深受顾客的喜爱。它的口感独特，麻辣适中，非常适合喜欢川菜的朋友。如果您想要更丰富的菜品搭配，我们还可以为您推荐一些其他的配菜，如清炒时蔬或米饭，让您享受一顿美味又健康的餐食。\n\n希望您享用愉快！如果您还有其他需求或特殊要求，请随时告诉我们。',
    # 'menu_ids': ['2', '1']  # rag检索的菜品id
    # }













