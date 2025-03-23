import asyncio
import datetime
from asyncio import WindowsSelectorEventLoopPolicy
from typing import Literal

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.constants import END
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, StreamWriter

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection, AsyncConnection

from prompt import load_prompt
from tools.jupyter_code_interpreter import jupyter_code_interpreter_tool

tools = [jupyter_code_interpreter_tool]

llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=5000).bind_tools(tools)
chat_prompt = load_prompt()
runnable = (chat_prompt | llm)


def node_call_llm(state: MessagesState, writer: StreamWriter) -> Command[Literal["__end__", "node_tool_calls"]]:
    llm_response = runnable.invoke(state)

    if llm_response.tool_calls is not None and len(llm_response.tool_calls) > 0:
        goto = "node_tool_calls"
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
    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
    }
    conn = await AsyncConnection.connect(DB_URI, **connection_kwargs)
    checkpointer = AsyncPostgresSaver(conn)
    chat_agent = graph.compile(checkpointer=checkpointer)
    return chat_agent
