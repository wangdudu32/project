from agent.prompt import sub_agent_prompt
from tools.sql_tools import list_sql_tables,get_table_data,execute_sql_query

db_select_agent = {
    "name":sub_agent_prompt['db']['name'],
    "description":sub_agent_prompt['db']['description'],
    "system_prompt":sub_agent_prompt['db']['system_prompt'],
    "tools":[list_sql_tables,get_table_data,execute_sql_query]
}