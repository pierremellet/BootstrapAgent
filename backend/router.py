import asyncio
import json

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from agent import create_agent

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

router = APIRouter()
agent = asyncio.run(create_agent())


class ChatRequest(BaseModel):
    message: str


@router.get("/threads")
async def get_threads():
    return [{"id": 1, "title": "Premier thread"}, {"id": 2, "title": "Deuxième thread"}]


async def response_generator(thread_id, request: ChatRequest):
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    async for event in agent.astream({
        "messages": [HumanMessage(request.message)]
    }, config=config, stream_mode=["messages", "custom"]):

        type = event[0]
        payload = event[1]

        if type == "messages":
            yield payload[0].model_dump_json() + "\n"

        if type == "custom":
            yield json.dumps(payload) + "\n"


@router.post("/threads/{thread_id}/stream")
async def invoke_agent(thread_id: str, request: ChatRequest) -> StreamingResponse:
    try:
        return StreamingResponse(response_generator(thread_id, request), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
