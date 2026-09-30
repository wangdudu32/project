import  yaml
from pathlib import Path

# 1. 定义一个提示词文件的方法（yaml），将内部的参数转成字典
def load_prompt(prompt_file):
    """
    传入提示词对应yaml文件的位置
    :param prompt_file: 提示词yaml配置的path
    :return: 返回解析后的字典类型
    """
    with open(prompt_file,"r" , encoding="utf-8") as f:
        return yaml.safe_load(f)

# 2. 拼接提示词的文件的位置
root_path = Path(__file__).parents[1]

prompt_file = root_path / "prompt" / "prompts.yml"

# 3. 调用方法或者主和子提示词对应字典进行备用
yaml_content = load_prompt(prompt_file)

main_agent_prompt = yaml_content["main_agent"]
sub_agent_prompt = yaml_content["sub_agents"]

print(f"主加载提示词的文件内容：{main_agent_prompt}")
print(f"子加载提示词的文件内容：{sub_agent_prompt}")