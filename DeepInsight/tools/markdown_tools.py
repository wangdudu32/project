import logging
from pathlib import Path

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated
from langchain_core.tools import tool
from api.monitor import monitor
from api.context import get_session_context
from utils.path_utils import resolve_path


# Markdown生成工具
@tool
def generate_markdown(
        content: str,
        filename: str,
        path: str =""
):
    """
    将文本内容写到markdown的工具！
    :param content: 要写入md的文本内容
    :param filename: 要生成md的文件名字，注意文件名字可能没有.md后缀！
    :param path: 生成文件的文件夹路径
    :return: 生成成功，文件地址拼接进来即可
    """
    monitor.report_tool("generate_markdown",{"content":content,"filename":filename,"path":path})
    # 1. 检查 filename 后缀名是不是 .md 不是追加一下
    if not filename.endswith(".md"):
        filename += ".md"
    # 2. path 检查他是不是空或者.  是 filename就是要生成完成地址 不是  path + filename
    if not path or path == '.':
        # 没有指定写的文件夹
        # path 没有指定 或者 无效指定 .
        full_file_path = filename
    else:
        # 有效指定 path 有值
        full_file_path = str( Path(path) / filename )
    # 3. 获取当前会话对应的根文件夹 每次会话生成的文件必须处于当前会话的文件夹，防止错乱
    # /a/b/info.md
    # 获取当前会话对应根地址，所有的存储到到此处
    # session_dir = session /a/b/info.md
    session_dir = get_session_context()
    # 4. 将会话文件夹 和 path + filename 结合到一起  session-xxxx / path / filename
    abs_file = resolve_path(full_file_path,session_dir) # 返回最终存储位置的字符串
    abs_file_path = Path(abs_file)
    # 5. 查看最终文件的上一层文件夹是否存在，不存在创建好文件夹
    asb_file_path_parent = abs_file_path.parent  # 获取他父目录
    if not asb_file_path_parent.exists():
        asb_file_path_parent.mkdir(parents=True,exist_ok=True)
    # 6. 将文本内容写到对应的文件中即可即可
    abs_file_path.write_text(content,encoding="utf-8")
    # 7. 返回结果
    return f"已经将内容写到：{abs_file_path} 文件中!"


if __name__ == "__main__":
    # ========== 核心：覆盖get_session_context的返回值（仅测试时生效） ==========
    # 不用Mock，直接重新定义这个函数，给session_dir赋值！
    def get_session_context():
        """测试专用：给session_dir配置固定初始化值"""
        return "./test_session_123"  # 你要的session_dir初始化值，随便改

    # ========== 极简测试逻辑（只传path/filename，session_dir已初始化） ==========
    test_content = "# 测试文档\n这是给session_dir配置固定值后的测试内容"
    test_filename = "测试文件"  # 无.md后缀，测试自动补全
    test_path = "sub_dir"       # 相对路径

    # 调用生成函数
    print("===== 开始测试（session_dir已配置为：./test_session_123） =====")
    result = generate_markdown.invoke({
        "content": test_content,
        "filename": test_filename,
        "path": test_path
    })

    # 验证结果
    print(f"\n调用结果：{result}")
    if "已成功生成" in result:
        file_path = Path(result.split("'")[1])
        print(f"✅ 验证：文件 {file_path} {'存在' if file_path.exists() else '不存在'}")