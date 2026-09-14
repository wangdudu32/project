"""
1.主要管理pinecone的 客户端和索引

2、像pinecone中同步数据

3、从pinecone中查询数据


"""
# 1.导入依赖
import  os
import  logging
from http.client import HTTPException
from  dotenv  import load_dotenv
import  re

from pinecone import Pinecone,ServerlessSpec
from typing import List, Any,Dict
import dashscope
from http import HTTPStatus
from  langchain_text_splitters import  CharacterTextSplitter

load_dotenv()



# 2.配置日志
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)


class PineconeVectorDB:
    """Pinecone向量数据库管理类"""

    def __init__(self):
        """pinecone的环境变量以及参数的初始化"""
        # 1. 配置环境变量
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.pinecone_env = os.getenv("PINECONE_ENV", "us-east-1")

        # 2.  配置向量数据库参数
        self.index_name = "menu-items2"  # 菜品索引名称
        self.model_name = "text-embedding-v4"  # DashScope嵌入模型(更好一些)
        self.dimension = 1536  # 向量维度 2048 主要处理图谱

        # 3. 初始化Pinecone连接和索引
        self.pc = None   # pinecone的客户端
        self.index = None  # pinecone的索引

    def initialize(self) -> bool:
        """
        初始化Pinecone连接和索引

        Returns:
            同步结果 bool (true:成功 false:失败)
        """
        try:
            # 1. 校验pinecone_api_key
            if not  self.pinecone_api_key:
                logger.error("PINE_CONE_API_KEY  IS  NOT  EXIST")
                return  False

            # 2. 创建pinecone的客户端
            self.pc=Pinecone(api_key=self.pinecone_api_key)

            # 3. 创建索引
            if  not  self.pc.has_index(self.index_name):
                self.pc.create_index(name=self.index_name,
                                     dimension=self.dimension,
                                     metric="cosine",
                                     spec=ServerlessSpec(
                                         cloud="aws",
                                         region=self.pinecone_env
                                     )
                                     )

            self.index=self.pc.Index(self.index_name)
            logger.info(f"向量数据库PineCone初始化客户端以及创建{self.index_name}索引成功")
            return  True
        except Exception as  e:
            logger.error(f"向量数据库PineCone初始化客户端以及创建索{self.index_name}引失败,原因: {e}")
            return  False

    def get_dashscope_embedding(self, text: str) -> list[Any] | Any:
        """
        使用DashScope生成文本向量

        Args:
            text:str:  输入的文本

        Returns:
            List[float]: 生成的向量
        """


        try:
            # 1.校验API_KEY
            if not  self.dashscope_api_key:
                logger.error("DASH_SCOPE_API_KEY  IS  NOT  EXIST")
                raise Exception("DASH_SCOPE_API_KEY IS  NOT  EXIST")

            # 2. 得到向量响应结果
            resp = dashscope.TextEmbedding.call(
                api_key=self.dashscope_api_key,
                model=self.model_name,
                input=[text],
                dimension=self.dimension,  # 指定向量维度（仅 text-embedding-v3及 text-embedding-v4支持该参数）
            )

            # 3. 获取文本向量后的结果
            if resp.status_code == HTTPStatus.OK:
                text_vectors=resp['output']['embeddings'][0]['embedding']
                return  text_vectors

            else :
                logger.error("文本向量化请求失败")
                return []
        except HTTPException as e:
            logger.error("请求文本向量失败,原因: {e}")
            return  []

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
            # 1.判断索引对象是否存在
            if not self.index and not self.initialize():
                return False
            # 2.判断clear_existing=True
            if clear_existing:
                self.clear_index_vector()

            # 3.查询MySQL中的数据（参与向量的数据）
            if not menu_data:
                # 3.1 查询数据库
                db_str_result = self._get_vector_data_from_db()
                # 3.2 判断
                if not self._is_valid_db_data(db_str_result):
                    return False

                # 3.3 切割
                texts = self._split_load_data(db_str_result)

                if not texts:
                    return False

                batch = []
                for line, text in enumerate(texts, 1):
                    # 3.4 向量化
                    text_vector = self.get_dashscope_embedding(text)
                    if not text_vector or len(text_vector) != self.dimension:
                        return False

                    # 3.5 批量处理
                    # 1) 行号
                    # 2) 向量数据
                    # 3) 元数据{content:向量之前的文本数据 dish_id:"菜品的id" line_number:"元数据的行号" type:"menu_item"}
                    line_number = f"menu_item_{line}"
                    metadata = {
                        "content": text,
                        "line_number": line,
                        "type": "menu_item",
                        "dish_id": f"菜品ID:{line}"
                    }
                    # 3.6 存储
                    batch.append((line_number, text_vector, metadata))

                    if len(batch) >= batch_size:
                        # 准备插入
                        self.index.upsert(vectors=batch)
                        batch = []  # 情况缓存区

                if batch:
                    self.index.upsert(vectors=batch)

                logger.info("成功将MySQL中的数据同步到PineCone向量数据库中")
                return True
            else:
                #  TODO
                pass
                return  True
        except Exception as e:
            logger.error(f"像向量数据库中同步数据失败,原因:{e}")
            return  False


    def  _split_load_data(self,split_str:str)->List[str]:
       """
        切割从数据库中加载到的有效数据
        :param:  db_str_result:str 要切割的内
        :return:
           切割后的字符串列表
       """
       # 1. 定义文本切割器
       # 1.1 切割查询到的数据
       text_spliter = CharacterTextSplitter(separator="\n", chunk_size=150, chunk_overlap=0, length_function=len)

       # 1.2 切分
       docs=text_spliter.create_documents([split_str])

       if  not docs:
           logger.error("分割后没有任何文档数据")
           return []

       # 1.3 处理
       final_docs=[]
       for  doc  in  docs:
           line=doc.page_content
           clear_text=line.strip()
           final_docs.append(clear_text)


       logger.info(f"切割器CharacterTextSplitter对源数据切割后得到的文档数：{len(docs)}")

       return  final_docs




    def  _is_valid_db_data(self,check_data:str)->bool:
        """
        校验从数据库中查询的数据
        :param check_data:  要检验的数据
        :return: 返回校验结果
        """

        # 1.校验空数据
        if  not  check_data:
            return  False

        # 2.校验无效数据
        is_valid_data=("查询失败","当前查询菜品无数据")

        return  not check_data.startswith(is_valid_data)


    def  _get_vector_data_from_db(self)->str:
        """从数据库中查询要向量的数据"""
        try:
            from  db_tool import  get_all_menu_items

            db_result=get_all_menu_items()
            return  db_result
        except Exception as e:
            logger.error(f"从数据库中查询数据失败,原因: {e}")
            return ""

    def   clear_index_vector(self)->bool:
        """
        删除pinecone数据库中索引下的所有向量
        :return:
        删除结果 bool (true:成功 false:失败)
        """

        # 1. 判断索引是否存在
        try:
            if not  self.index and not  self.initialize():
                return  False

            # 2. 删除
            # 2.1 判断是否要删除
            status=self.index.describe_index_stats()

            count=status.total_vector_count
            if count==0:
                return  True

            self.index.delete(delete_all=True)
            logger.info(f"删除向量数据库的索引下所有的向量数据成功")
            return  True
        except Exception as  e:
            logger.error(f"删除向量数据库的索引下所有的向量数据失败")
            return  False


    def  similar_search_menu_items(self,input:str,top_k:int=2 )->List[Dict[str,Any]]:
        """
        根据输入问题进行相似性查询
        :param input:  查询的问题
        :param top_k:  返回的结果数量
        :return:  满足查询问题的相似性结果
        """

        try:
            # 1. 判断索引是否存在
            if not self.index and not self.initialize():
                return []

            # 2. 判断输入问题
            if not input:
                return []

            # 3. 对问题进行向量化
            input_vector = self.get_dashscope_embedding(input)

            # 4. 判断
            if not input_vector or len(input_vector) != self.dimension:
                return []

            # 5. 检索
            similar_result = self.index.query(vector=input_vector, top_k=top_k, include_metadata=True)

            result = []
            for match in similar_result.matches:
                match_item = {
                    "id": match['id'],  # pinecone生成的记录id
                    "score": match['score'],  # 分数值
                    "content": match['metadata']['content'],
                    "line_number": match['metadata']['line_number']
                }

                result.append(match_item)

            return result

        except Exception as e:
            logger.error(f"从向量数据库中检索满足查询问题的结果失败,原因: {e}")
            return  []




vector_db=PineconeVectorDB()


def pinecone_connection() -> bool:
    """Pinecone连接"""
    return vector_db.initialize()


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


def search_menu_items(query: str, top_k: int = 2) -> List[str]:
    """
    根据查询搜索相关菜品

    Args:
        query: 查询文本
        top_k: 返回结果数量

    Returns:
        List[str]: 相关菜品信息列表
    """
    results = vector_db.similar_search_menu_items(query, top_k)
    return [item["content"] for item in results]




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

    # 1. 进行相似性检索
    match_items=vector_db.similar_search_menu_items(query,top_k)


    # 2. 处理数据
    ids=[]
    for  item  in  match_items:
        content=item['content']
        match=re.search(r"菜品ID:(\d+)",content)
        if match:
            id = match.group(1)
        else:
            id=item["id"]

        ids.append(id)

    # 3.返回
    return {
        "contents":[item['content'] for item in match_items],
        "ids":ids,
        "scores":[item['score'] for item in match_items]
    }




# 示例测试
if __name__ == '__main__':

    # 1.测试PineCone的客户端以及索引
    # print("1. 测试PineCone的客户端以及索引")
    # vector_db.initialize()
    #
    # # 2. 测试文本向量化
    # print("\n2. 测试DashScope的文本向量模型")
    # text_vector_list=vector_db.get_dashscope_embedding("今天武汉的天气不太好")
    # print(f"文本向量后列表的结果{text_vector_list}")
    #
    #
    # # 3. 删除指定的索引
    # delete_flag=vector_db.clear_index_vector()
    # print(f"删除索引{delete_flag}")
    #
    #
    # # 4. 测试数据的同步
    # print("\n4. 将MySQL数据同步到向量数据库中")
    # vector_db.upsert_menu_data()


    # 5. 测试数据的检索
    # print("\n5. 根据输入问题相似性检索")
    # match_item=vector_db.similar_search_menu_items("我想点一份清淡的素菜")
    #
    # if not match_item:
    #     print("没有查询到任何菜品数据")
    # else:
    #     for  item in match_item:
    #         print(f"查询到相似性文档内容:{item}")


    # 6.测试相似性检索（带id）

    item_dict=search_menu_items_with_id("我想点一份清淡的素菜",2)

    if  not item_dict:
        print("没有查询到任何菜品数据")
    else:
        print(f"检索到的带id的相似性菜品数据:{item_dict}")













































