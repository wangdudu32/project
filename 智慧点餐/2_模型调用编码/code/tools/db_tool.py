"""
1.建立数据库连接
2.查询MySQL中数据
3.提供检索数据的方法

"""
import os
import mysql.connector
import logging
from  typing import  List,Dict,Any
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)


class  DataBaseConnection:
    """数据库的连接上下文管理器类"""

    def  __init__(self):
        """初始化数据库的连接信息"""

        # 1. 定义MySQL中的配置信息（host  port  username  password database 数据库连接对象 游标对象）
        self.host=os.getenv("MYSQL_HOST","127.0.0.1")
        self.port=os.getenv("MYSQL_PORT","3306")
        self.username=os.getenv("MYSQL_USER_NAME","root")
        self.password=os.getenv("MYSQL_PASSWORD","root")
        self.database=os.getenv("MYSQL_DATABASE","menu")

        self.connection=None # 数据库连接对象
        self.cursor=None # 游标对象（执行sql 获取执行sql后的结果）



    def  initialize(self)->bool:
      """数据库的初始化方法 定义游标和数据库连接"""

      try:
          self.connection=mysql.connector.connect(
              host=self.host,
              port=self.port,
              user=self.username,
              password=self.password,
              database=self.database,
              charset="utf8mb4"
          )
          if  self.connection.is_connected():  # 数据库连接时激活的
              self.cursor=self.connection.cursor(dictionary=True)  # select  name from  user; {"name":"zs"}
              logger.info(f"成功连接到数据库: {self.database}")
              return  True
          else:
              logger.error(f"数据库连接不可用: {self.database}")
              return False
      except mysql.connector.Error as e:
          logger.error(f"数据库错误,异常原因 {e}")
          return False


    def   close_connection(self):
        """关闭数据库连接"""
        try:
                # 1. 关闭游标对象
            if self.cursor:
                self.cursor.close()  # 关闭游标
                self.cursor = None  # 防止下一次使用游标的时候出现错误

                # 2. 关闭数据库连接对象
            if self.connection and self.connection.is_connected():
                self.connection.close()
                self.connection = None  # 防止下一次使用数据库连接的时候出现错误
        except Exception as e:
            logger.error(f"关闭数据库出错,原因: {e}")
            raise

    def __enter__(self):
        """
        调用数据库连接初始化方法
        自动调用到的：实例DataBaseConnection()
        """
        if  self.initialize():
            logger.info("数据库初始化完毕")
            return self
        else:
            logger.error("数据库初始化失败")
            raise


    def __exit__(self, exc_type, exc_val, exc_tb):
        """关闭数据库连接 with中处理完毕 自动调用该方法"""

        try:
            if self.connection and self.connection.is_connected():
                self.close_connection()
                logger.info("关闭数据库连接成功")
        except Exception as e:
            logger.error(f"关闭数据库连接异常: {e}")
            raise






def  get_all_menu_items()->str:
    """
    查询数据库中所有的菜品信息
    :return: str: 每个菜品信息格式化后的一个大字符串
    """
    try:
        with DataBaseConnection() as  db:

            # 1.定义sql语句

             query_sql="""
             SELECT 
                    id, dish_name, price, description, category, 
                    spice_level, flavor, main_ingredients, cooking_method, 
                    is_vegetarian, allergens, is_available
                    FROM menu_items 
                    WHERE is_available = 1
                    ORDER BY category, dish_name
            
            """
             # 2.执行sql
             db.cursor.execute(query_sql)
             menu_items=db.cursor.fetchall()   # 字典列表
             if  not  menu_items:
               return  "当前查询菜品无数据"


             menu_strings=[]

             for  menu_item in  menu_items:
                # 3.格式化
                # 3.1 格式化菜品的描述
                description_text = menu_item.get('description', '') if menu_item.get('description', '').strip() else "未知描述"
                # 3.2 格式化菜品食材
                main_ingredients_text = menu_item.get('main_ingredients', '') if menu_item.get('main_ingredients','').strip() else "未知食材"
                # 3.3 格式化过敏食材
                allergens_text = menu_item.get('allergens', '') if menu_item.get('allergens', '').strip() else "无过敏原"

                # 3.4 处理辣度等级
                spice_level = {"0": "不辣", "1": "微辣", "2": "中辣", "3": "重辣"}
                spice_text = spice_level.get(menu_item["spice_level"], "未知辣度")
                # 3.5 处理是否是素食
                vegetarian_text = "是" if menu_item['is_vegetarian'] else "否"

                menu_string = f"菜品ID:{menu_item['id']}|菜品名称:{menu_item['dish_name']}|价格:¥{menu_item['price']:.2f}|菜品描述:{description_text}|分类:{menu_item['category']}|辣度:{spice_text}|口味:{menu_item['flavor']}|主要食材:{main_ingredients_text}|烹饪方法:{menu_item['cooking_method']}|素食:{vegetarian_text}|过敏原:{allergens_text}"

                menu_strings.append(menu_string)

             return "\n".join(menu_strings)
    except Exception as e:
        logger.error(f"查询格式化菜品信息失败,原因: {e}")
        return "查询失败"


def   get_menu_item_list()->List[Dict]:
    """
    查询菜品结构化信息
    :return:  List[Dict]:菜品结构化信息
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

            # 2.执行sql
            db.cursor.execute(query_sql)
            menu_items = db.cursor.fetchall()  # 字典列表

            if not menu_items:
                return []

            # 3.处理返回数据
            menu_item_list = []
            for menu_item in menu_items:
                # 辣度等级转换
                spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
                spice_text = spice_levels.get(menu_item['spice_level'], "未知")

                # 处理数据
                processed_item = {
                    "id": menu_item['id'],
                    "dish_name": menu_item['dish_name'],
                    "price": float(menu_item['price']),
                    "formatted_price": f"¥{menu_item['price']:.2f}",
                    "description": menu_item['description'] or "暂无描述",
                    "category": menu_item['category'],
                    "spice_level": menu_item['spice_level'],
                    "spice_text": spice_text,
                    "flavor": menu_item['flavor'] or "暂无口味",
                    "main_ingredients": menu_item['main_ingredients'] or "暂无主要食材",
                    "cooking_method": menu_item['cooking_method'] or "暂无烹饪方法",
                    "is_vegetarian": bool(menu_item['is_vegetarian']),
                    "vegetarian_text": "是" if menu_item['is_vegetarian'] else "否",
                    "allergens": menu_item['allergens'] if menu_item['allergens'] and menu_item[
                        'allergens'].strip() else "暂无过敏原",
                    "is_available": bool(menu_item['is_available'])
                }

                menu_item_list.append(processed_item)

            logger.info(f"已经成功查询到字典格式的菜品数量: {len(menu_item_list)}")
            return menu_item_list

    except Exception as e:
        logger.error(f"查询字典结构的菜品列表失败,原因: {e}")
        return  []


def get_menu_item_by_id(item_id: str) -> Dict[str, Any]:
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
            sql_query = """
            SELECT 
                id, dish_name, price, description, category, 
                spice_level, flavor, main_ingredients, cooking_method, 
                is_vegetarian, allergens, is_available
            FROM menu_items 
            WHERE id = %s AND is_available = 1
            """

            # 2. 执行查询语句
            db.cursor.execute(sql_query, (item_id,))

            # 3. 获取查询结果
            item = db.cursor.fetchone()
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
        return {}



def   get_menu_items_by_category()->Dict[str,Any]:
    """
        通过分类获取菜单项
       Returns:
           Dict[str,Any]: 以分类为键，菜品列表为值的字典
           {"川菜":["宫保鸡丁...","麻婆豆腐..."],"素食":["清炒时蔬...","蒜蓉西兰花..."]}
       """
    try:
        # 1. 查询所有菜品信息列表
        menu_item_list = get_menu_item_list()

        # 2.定义满足要求的字典结构
        menu_item_category={}
        for item in menu_item_list:
            category = item['category']
            if category not in menu_item_category:
                menu_item_category[category] = []
            menu_item_category[category].append(item)

        logger.info(f"根据分类查询菜品的类别数量:{len(menu_item_category)}")
        return    menu_item_category

    except Exception as  e:
        logger.error("根据分类查询菜品信息失败,原因: {e}")
        return {}


def  test_connection()->bool:
    """测试数据库连接"""

    try:
        with  DataBaseConnection() as  db:
            db.cursor.execute("select 1")
            result=db.cursor.fetchone()
            print(result)
            return  True
    except Exception as e:
        logger.error(f"数据库连接信息失败,原因: {e}")
        return  False


# 测试示例
if __name__ == '__main__':

    # 1.测试数据库连接
    print("1. 测试数据库连接")
    if test_connection():
        print("测试数据库连接成功")

    # 2. 测试查询MySQL中的所有菜品格式成大字符串的信息
    print("\n2. 测试大字符串格式的所有菜品信息")
    menu_items_str=get_all_menu_items()
    print(f"字符串结构的菜品信息: {menu_items_str}")


    # 3.测试查询MySQL中所有菜品的信息（字典结构）
    print("\n3. 测试查询MySQL中所有菜品的信息")
    menu_item_list=get_menu_item_list()

    for  index,item  in enumerate(menu_item_list,1):
        print(f"第{index}号的菜品,完整的字典结构的菜品信息是:{item}")


    # 4. 测试查询MySQL中根据菜品id的结构化菜品信息
    print("\n4. 测试查询MySQL中根据菜品id的结构化菜品信息")
    dish_ids=["1","2","3","4","5"]

    for  dish_id in dish_ids:
        item_dict=get_menu_item_by_id(dish_id)
        print(f"第{dish_id}号的菜品,完整的字典结构的菜品信息是:{item_dict}")

    print("\n5. 测试查询MySQL中根据菜品分类的结构化菜品信息")
    menu_item_category=get_menu_items_by_category()

    for index,menu_item in  enumerate(menu_item_category,1):
         menu_list=menu_item_category.get(menu_item)
         print(f"菜系：{index}对应的菜品列表下的菜品数据:{menu_list}")







