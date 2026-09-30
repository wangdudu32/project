# 导入子智能体
import asyncio
import uuid

from deepagents import create_deep_agent
from langchain_core.messages import AIMessage

from agent.subagents.db_select_agent import db_select_agent
from agent.subagents.network_search_agent import network_search_agent
from agent.subagents.ragflow_select_agent import ragflow_select_agent
from api.context import set_thread_context, set_session_context, reset_session_context
from api.logger import AgentLogger, AgentLogCallbackHandler
# 导入主智能体的工具
from tools.markdown_tools import generate_markdown
from tools.pdf_tools import convert_md_to_pdf
from agent.prompt import main_agent_prompt
from pathlib import Path
from api.monitor import monitor

# 创建主智能体的方法
# 导入我们大模型对象
from agent.llm import  llm

# 创建深度代理的deepAgent
main_agent = create_deep_agent(
    model= llm,
    system_prompt= main_agent_prompt["system_prompt"],
    subagents=[db_select_agent, network_search_agent, ragflow_select_agent],
    tools=[generate_markdown, convert_md_to_pdf]
    # interrupt_on=[],
    # middleware=[],
    # store=[],
    # backend=[],
    # checkpointer=[],
    # skills=[],
)


# 1. 定义 project_root（项目根目录，自动获取当前文件所在目录的上层）
project_root = Path(__file__).parents[1].resolve()  # 核心：自动识别项目根目录
print(f"----------------project_root-----------------: {project_root}")

def _prepare_session_environment(thread_id: str):
    """准备会话目录并处理上传文件"""
    # 1. 定义会话的绝对输出路径 (示例: .../output/session_uuid)
    session_dir = project_root / "output" / f"session_{thread_id}"

    # 2. 创建目录，parents=True允许创建多级父目录，exist_ok=True若目录已存在不报错
    session_dir.mkdir(parents=True, exist_ok=True)

    # 3. 路径转为字符串并统一为 POSIX 风格 (即使用 '/' 分隔)，防止转义问题
    """
    POSIX（Portable Operating System Interface）是一套操作系统标准，旨在让程序在不同系统（Unix, Linux, macOS）之间兼容。

    - Windows 风格路径 ：使用反斜杠 \ 分隔。 
    - 例如： C:\Windows\System32
    - 痛点 ：只有 Windows 这么用，且容易产生转义问题。
    - POSIX 风格路径 ：使用正斜杠 / 分隔。
    - 例如： /usr/bin/python 或 C:/Windows/System32
    - 优点 ：Linux、macOS、Web URL、以及 现代 Windows API 全部都支持这种写法！
    总结 ：
    把路径统一转成 / （POSIX 风格），是为了：
    1. 防止大模型产生幻觉或解析错误 （最重要）。
    2. 跨平台兼容 （无论在 Mac 还是 Windows 上跑，路径格式看起来都一样）。
    3. 避免转义坑 （不用担心 \t 变成制表符）。
    """
    virtual_session_dir = str(session_dir).replace("\\", "/")

    # 4. 获取相对于项目根目录的路径 (示例: output/session_uuid)，用于提示词展示
    relative_session_dir = str(session_dir.relative_to(project_root)).replace("\\", "/")

    # 11. 返回四个关键变量供后续使用
    return session_dir, virtual_session_dir, relative_session_dir

def _process_stream_chunk(chunk, logger):
    """
    处理 Agent 流式输出与监控上报

    Args:
        chunk (dict): LangGraph 流式输出的增量状态字典，格式如 {"node_name": {"messages": [...]}}
        logger (AgentLogger): 用于记录日志的 Logger 实例
    """
    # 1. 记录原始 chunk 数据，便于调试
    logger.log_main_chunk(chunk)
    # 2. 遍历 chunk 中的每个节点状态 (通常是 agent 节点或 tool 节点)
    for node_name, state in chunk.items():
        # 3. 过滤无效状态或不包含消息的状态
        if not state or "messages" not in state: continue

        # 4. 获取当前节点更新的消息列表
        messages = state["messages"]
        if isinstance(messages, list) and messages:
            # 5. 获取最新一条消息 (通常是本次迭代产生的内容)
            last_msg = messages[-1]

            # 6. 处理 AI 消息 (AIMessage) -> 对应场景 A, C, D
            if isinstance(last_msg, AIMessage):
                # [场景 A & C] 如果包含工具调用 (tool_calls)
                # - 场景 A: 调用普通工具 (如 read_file_content)
                # - 场景 C: 调用子 Agent (工具名为 'task')
                if last_msg.tool_calls:
                    for tool in last_msg.tool_calls:
                        # 记录工具调用日志
                        logger.log_tool_call(tool['name'], tool['args'])
                        # [场景 C 特殊处理] 'task' 工具，上报子 Agent 状态
                        if tool['name'] == 'task':
                            monitor.report_assistant(
                                tool['args'].get('subagent_type', 'Agent'),
                                {"desc": tool['args'].get('description')}
                            )
                # [场景 D] 如果包含文本内容 (content) -> Agent 最终回复
                elif last_msg.content:
                    # 上报任务执行结果 (通常是 Agent 的回复)
                    monitor.report_task_result(last_msg.content)


# ====================== 核心执行逻辑 ======================
async def run_deep_agent(task_query: str, thread_id: str = None):
    """DeepAgents 核心执行入口"""
    # 1. 确保有唯一的会话 ID (thread_id)
    if not thread_id: thread_id = str(uuid.uuid4())
    print(f"--- Start Task: {task_query} (Thread: {thread_id}) ---")

    # 2. 准备会话环境 (创建目录、复制文件、生成路径信息)
    # session_dir: 物理绝对路径 (C:\...\session_xxx)
    # virtual_session_dir: 虚拟路径 (用于前端展示)
    # relative_session_dir: 相对路径 (./output/session_xxx)
    session_dir, virtual_session_dir, relative_session_dir = _prepare_session_environment(thread_id)

    # 3. 初始化上下文 (ContextVars) 与监控上报
    # 设置线程上下文，确保日志和工具能获取到当前 thread_id
    thread_token = set_thread_context(thread_id)
    # 设置会话上下文，确保工具 (如 read_file) 能知道当前物理工作目录
    session_token = set_session_context(str(session_dir))
    # 向前端监控系统上报当前的虚拟工作目录
    # 前端明确我们文件存储的具体的位置： virtual_session_dir 完整的字符串的地址 进行了 \\ -> /
    monitor.report_session_dir(virtual_session_dir)

    # 4. 配置日志系统 (Logger)
    # 初始化业务 Logger
    logger = AgentLogger(thread_id, project_root)
    # LangChain 运行时配置
    config = {
        "configurable": {"thread_id": thread_id},  # 传入 thread_id 用于 Checkpointer 记忆
        "callbacks": [AgentLogCallbackHandler(logger)]  # 注入回调处理器，拦截底层日志
    }

    # 5. 构建动态提示词 (Prompt Injection)
    # 将路径约束和文件信息动态注入到用户 Query 之后
    path_instruction = f"""
    【工作环境指令】
    工作目录: {relative_session_dir}

    规则：
    1. 新生成文件必须保存到工作目录：'{relative_session_dir}/filename'
    2. 使用相对路径，禁止使用绝对路径
    """

    # 6. 执行 Agent (流式驱动)
    try:
        # 帮我查询数据库信息，生成一个 md文件  -》
        async for chunk in main_agent.astream(
                {"messages": [{"role": "user", "content": task_query + path_instruction}]}, config=config):
            # 处理每一个流式块 (日志记录、监控上报)
            _process_stream_chunk(chunk, logger)
        return "Done"
    except Exception as e:
        # 7. 异常捕获与上报
        print(f"Error: {e}")
        monitor._emit("error", f"Execution failed: {e}")
        return f"Error: {e}"
    finally:
        # 8. 清理上下文 (资源释放)
        # 务必在 finally 中重置 ContextVars，防止上下文污染
        if 'session_token' in locals():
            reset_session_context(session_token, thread_token)


# ====================== 本地测试入口 ======================
if __name__ == "__main__":
    task = "查询数据库中的药品信息，生成一个pdf文件！"
    asyncio.run(run_deep_agent(task))