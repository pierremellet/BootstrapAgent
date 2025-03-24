import datetime
from typing import Literal

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.constants import END
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, StreamWriter
from psycopg import AsyncConnection

from prompt import load_prompt
from tools.jupyter_code_interpreter import jupyter_code_interpreter_tool
from tools.request_support import request_support_tool

tools = [jupyter_code_interpreter_tool, request_support_tool]

llm = ChatOpenAI(model="gpt-4o", max_tokens=8000).bind_tools(tools)
chat_prompt = load_prompt()
runnable = (chat_prompt | llm)


def node_call_llm(state: MessagesState, writer: StreamWriter) -> Command[Literal["__end__", "node_tool_calls"]]:
    writer({"custom_event": "Calling LLM 🤖"})

    llm_response = runnable.invoke(state)


    if llm_response.tool_calls is not None and len(llm_response.tool_calls) > 0:
        goto = "node_tool_calls"
        writer({"custom_event": f"Call tools"})

    else:
        writer({"timer": datetime.datetime.now().strftime("YYYY/MM/DD HH:mm:ss")})
        goto = END

    return Command(
        update={
            "messages": [llm_response]
        },
        goto=goto
    )


graph = StateGraph(MessagesState)
graph.add_node("node_call_llm", node_call_llm)
graph.add_node("node_tool_calls", ToolNode(tools))
graph.set_entry_point("node_call_llm")
graph.add_edge("node_tool_calls", "node_call_llm")


async def create_agent():
    DB_URI = "postgresql://postgres:admin@localhost:5432/postgres"
    conn: AsyncConnection = await AsyncConnection.connect(conninfo=DB_URI, autocommit=True, prepare_threshold=0)
    checkpointer = AsyncPostgresSaver(conn)
    await checkpointer.setup()
    chat_agent = graph.compile(checkpointer=checkpointer)
    return chat_agent
