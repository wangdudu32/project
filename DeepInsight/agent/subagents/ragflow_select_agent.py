from agent.prompt import sub_agent_prompt
from tools.ragflow_tools import  ragflow_chat_list,create_ask_delete


ragflow_select_agent ={
    "name":sub_agent_prompt['ragflow']['name'],
    "description":sub_agent_prompt['ragflow']['description'],
    "system_prompt":sub_agent_prompt['ragflow']['system_prompt'],
    "tools":[ragflow_chat_list,create_ask_delete]
}