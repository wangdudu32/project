import os
from dotenv import load_dotenv
from api.monitor import monitor
from mysql.connector import connect, Error
from typing import Annotated, List
from langchain_core.tools import tool

load_dotenv()

# 加载配置文件方便后续使用
def get_db_config():
    """Get database configuration from environment variables."""
    #  key 不是随便写的！ 一会我们会使用mysql connection链接！ key = 创建链接的参数名！ 使用解构即可快速复制 **config
    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE"),
        "charset": os.getenv("MYSQL_CHARSET", "utf8mb4"),
        "collation": os.getenv("MYSQL_COLLATION", "utf8mb4_unicode_ci"),
        "autocommit": True,
        "sql_mode": os.getenv("MYSQL_SQL_MODE", "TRADITIONAL")
    }
    # 移除 None 值（核心必要操作）
    config = {k: v for k, v in config.items() if v is not None}

    # 补充：校验核心配置是否存在（可选但推荐）
    required_keys = ["user", "password", "database"]
    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        raise ValueError(f"缺失数据库核心配置：{', '.join(missing_keys)}")

    return config


# 定义查询数据库表名的工具  表名,表名,表名  get_sql_tables
@tool
def list_sql_tables()->str:
    """
    用于查询库中表名的工具！
    作用：后续的查询数据都需要先触发此工具，明确表名，避免错误查询！ a b c d f
    :return: 1. 有可用表 返回固定格式 可用表：表名1,表名2,表名3...  2.没有可用表，返回固定格式 没有可用表 3. 链接数据库失败 链接数据库失败：失败的原因
    """
    monitor.report_tool("list_sql_tables",{"get_sql_tables":"调用查询表名的工具，但是没有传入参数！！"})
    # 获取数据库的配置信息
    config = get_db_config()
    try:
        # 1.创建链接
        with connect(**config) as conn:
            # 2.创建cursor
            with conn.cursor() as cursor:
                # 3.执行sql语句
                cursor.execute("show tables;")
                # 4.获取返回结果
                # [(a,),(b,),(c,)]
                results = cursor.fetchall()
                # 5.结果拼接成需要的返回结果
                if results:
                    # 有  [a,b,c,d]
                    table_names = [result[0] for result in results ]
                    return f"可用表:{','.join(table_names)}"
                else:
                    # 没有
                    return f"没有可用表"
    except Error as e:
        return f"链接数据库失败：{str(e)}"


# table_names = get_sql_tables.invoke()
# print(table_names)

"""
【mysql.connector 核心 API 说明（针对 connect/cursor）】
1. connect 函数：
   - 作用：建立与 MySQL 数据库的连接，返回一个 Connection 对象；
   - 使用方式：connect(**config)，config 为包含 host/user/password 等的字典；
   - 上下文管理器：推荐用 with 语句（with connect(**config) as conn），自动关闭连接，避免资源泄露；
   - 核心属性/方法：
     - conn.cursor(): 创建游标对象（执行 SQL 的核心）；
     - conn.commit(): 提交事务（autocommit=True 时无需手动调用）；
     - conn.close(): 关闭连接（with 语句自动执行）。
2. cursor 游标对象：
   - 作用：执行 SQL 语句、获取查询结果的核心对象；
   - 创建方式：conn.cursor()；
   - 上下文管理器：with conn.cursor() as cursor，自动关闭游标；
   - 核心方法：
     - cursor.execute(sql): 执行单条 SQL 语句（如 SHOW TABLES/SELECT/INSERT）；
     - cursor.executemany(sql, params): 批量执行 SQL 语句（如批量插入）；
     - cursor.close(): 关闭游标（with 语句自动执行）。
3. 【重点】cursor 执行 DQL/DML 后的结果解析：
   ▶ DQL（数据查询语言，如 SELECT/SHOW）：查询类操作，返回「数据结果集」
     - 核心方法：
       1. cursor.fetchall(): 获取所有结果（返回列表，每个元素是元组，如 [(1, '张三'), (2, '李四')]）；
       2. cursor.fetchone(): 获取一条结果（返回元组，如 (1, '张三')，多次调用可遍历所有结果）；
       3. cursor.fetchmany(n): 获取前 n 条结果（返回列表）；
       4. cursor.column_names: 获取查询结果的列名（列表，如 ['id', 'name']）；
     - 解析技巧：将「列名 + 元组结果」转为字典（更易读），如 {'id': 1, 'name': '张三'}。
   ▶ DML（数据操作语言，如 INSERT/UPDATE/DELETE）：修改类操作，无「数据结果集」
     - 核心属性：
       1. cursor.rowcount: 返回受影响的行数（整数，如 INSERT 1 条返回 1，UPDATE 3 条返回 3）；
       2. cursor.lastrowid: INSERT 操作后，返回新增记录的自增 ID（仅对有自增主键的表有效）；
     - 解析技巧：通过 rowcount 判断操作是否生效，lastrowid 获取新增数据的主键。
4. 异常处理：
   - Error: mysql.connector 专属异常类，捕获所有数据库操作异常（如连接失败、SQL 语法错误）；
   - 推荐方式：try-except Error as e 捕获异常，返回友好提示。
"""

# 定义查询数据指定表的100条数据  表头 数,据  get_table_data
# 智能体 给我们传递一个对应的表名 （根据第一个工具查询确定的表名） 返回的结果 表格形式  第一行  id,name,age\n 1,张三,18 \n 2,李四，20 -》 查询100条
@tool
def get_table_data(table_name:str)->str:
    """
    明确表名了，根据表名查询表的一条数据！
    返回结果拼接成字符串表格形式
    :param table_name: 明确要查询的表名，表名需要通过 list_sql_tables确认后进行传递
    :return: 1.查询到数据 返回返回数据的模拟表格 2. 没有数据，没有数据 3. 报错，正常提示即可
    """
    monitor.report_tool("get_table_data", {"table_name": table_name})
    # 获取数据库配置
    config = get_db_config()
    # try确保报错捕捉
    try:
        # 创建链接
        with connect(**config) as conn:
            # 获取游标
            with conn.cursor() as cursor:
                sql = f'select * from {table_name} limit 100;'
                cursor.execute(sql)
                # 细节1：  cursor.description 查询结果的虚拟表的元数据 （DQL语句的查询列的信息 | DML DCL DDL -> description ->None）
                # 细节2： description =》 [(每个列的信息),(列名,长度，类型),()]
                column_names = [ desc[0] for desc in cursor.description]
                results = cursor.fetchall()
                # 列名拼接成虚拟表结果  , 隔开即可
                header_str = ",".join(column_names) # -> id,name,age\n
                # map(str,result) 列表或者元组数据映射承成对应类型！！ （1,张三,True） -》 map(str,（1,张三,True）) -> （'1','张三','True'） -> ['1','张三','True',]
                result_data = [ ','.join(map(str,result)) for result in results]
                data_str = '\n'.join(result_data)
                return header_str + '\n' + data_str
    except Error as e:
        return f"查询出现错误：{str(e)}"

@tool
def execute_sql_query(sql:str)->str:
    """
    传入自定义查询sql语句，进行复杂的查询（单表，或者多表场景）
    注意：自定义sql语句需要通过 list_sql_tables验证表名的正确，通过get_table_data验证表中列的信息！确保sql的正确！！
    :param sql: 传入的sql语句，需要进行校验处理
    :return: 查询返回的结果，结果使用虚拟表字符串处理
    """
    monitor.report_tool("execute_sql_query", {"sql": sql})
    # 获取数据库配置
    config = get_db_config()
    # try确保报错捕捉
    try:
        # 创建链接
        with connect(**config) as conn:
            # 获取游标
            with conn.cursor() as cursor:
                cursor.execute(sql)
                # 细节1：  cursor.description 查询结果的虚拟表的元数据 （DQL语句的查询列的信息 | DML DCL DDL -> description ->None）
                # 细节2： description =》 [(每个列的信息),(列名,长度，类型),()]
                column_names = [desc[0] for desc in cursor.description]
                results = cursor.fetchall()
                # 列名拼接成虚拟表结果  , 隔开即可
                header_str = ",".join(column_names)  # -> id,name,age\n
                # map(str,result) 列表或者元组数据映射承成对应类型！！ （1,张三,True） -》 map(str,（1,张三,True）) -> （'1','张三','True'） -> ['1','张三','True',]
                result_data = [','.join(map(str, result)) for result in results]
                data_str = '\n'.join(result_data)
                return header_str + '\n' + data_str
    except Error as e:
        return f"查询出现错误：{str(e)}"



# result = execute_sql_query("SELECT * FROM `inventory` it  join drugs dg on dg.drug_id = it.drug_id where it.drug_id = 200000")
# print(result)


# 定义执行自定义sql语句的工具   表头 数,据 execute_sql_query