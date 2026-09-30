from agent.prompt import sub_agent_prompt
from tools.tavily_tools import internet_search

# 创建子智能体，使用字段形式
network_search_agent ={
    "name":sub_agent_prompt['tavily']['name'],
    "description":sub_agent_prompt['tavily']['description'],
    "system_prompt":sub_agent_prompt['tavily']['system_prompt'],
    "tools":[internet_search]
}