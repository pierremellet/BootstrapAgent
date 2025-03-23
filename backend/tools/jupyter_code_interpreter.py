import base64
import json
import logging
import os
import shutil
import uuid
from time import sleep

import requests
import websocket
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.config import get_stream_writer
from websocket import WebSocket

# Constants
JUPYTER_KERNEL_HTTP_GATEWAY = os.getenv('JUPYER_KERNEL_HTTP_GATEWAY')
JUPYTER_KERNEL_WS_GATEWAY = os.getenv('JUPYER_KERNEL_WS_GATEWAY')


class JupyterClient:
    def __init__(self, base_dir: str, thread_id: str, http_server_endpoint: str):
        self.result = []
        self.kernel_id = None
        self.thread_id = thread_id
        self.base_dir = base_dir
        self.http_server_endpoint = http_server_endpoint

    def get_result(self) -> str:
        return "\n".join(self.result)

    def create_session(self):
        self._create_kernel()
        self._create_fs()

    def destroy_session(self):
        self._delete_fs()
        self._delete_kernel()

    def _delete_fs(self):
        fs_path = os.path.join(self.base_dir, self.thread_id)
        shutil.rmtree(fs_path)

    def _delete_kernel(self):
        requests.delete(f"{JUPYTER_KERNEL_HTTP_GATEWAY}/api/kernels/{self.kernel_id}")

    def _create_fs(self):
        if not os.path.isdir(self.base_dir):
            raise FileNotFoundError(f"Directory {self.base_dir} is missing")

        thread_fs_path = os.path.join(self.base_dir, self.thread_id)
        if not os.path.isdir(thread_fs_path):
            os.mkdir(thread_fs_path)

    def _create_kernel(self):
        try:
            response = requests.post(f"{JUPYTER_KERNEL_HTTP_GATEWAY}/api/kernels").json()
            self.kernel_id = response["id"]
            logging.info(f"Created new kernel with id: {self.kernel_id}")
        except requests.RequestException as e:
            self.result.append(f"Failed to create kernel: {e}")

    def exec_code(self, code: str):
        message = self._create_exec_message(code)

        self._wait_for_kernel_ready()

        ws = self._open_websocket(message)
        ws.run_forever()

    def _create_exec_message(self, code: str) -> dict:
        return {
            "header": {
                "username": "",
                "version": "5.0",
                "session": "",
                "msg_id": str(uuid.uuid4()),
                "msg_type": "execute_request"
            },
            "parent_header": {},
            "channel": "shell",
            "content": {
                "code": code,
                "silent": False,
                "store_history": True,
                "user_expressions": {},
                "allow_stdin": False
            },
            "metadata": {},
            "buffers": {}
        }

    def _wait_for_kernel_ready(self):
        while True:
            try:
                kernel_status = requests.get(
                    f"{JUPYTER_KERNEL_HTTP_GATEWAY}/api/kernels/{self.kernel_id}"
                ).json()
                if kernel_status["execution_state"] == "idle":
                    break
                logging.info(f"Waiting for Kernel {self.kernel_id}")
                sleep(1)
            except requests.RequestException as e:
                self.result.append(f"Failed to check kernel status: {e}")
                return

    def _open_websocket(self, message: dict) -> websocket.WebSocketApp:
        def on_open(ws):
            logging.info(f"Sending code for execution on kernel {self.kernel_id}")
            ws.send(json.dumps(message))

        def on_message(ws: WebSocket, message: str):
            self._handle_message(ws, json.loads(message))

        def on_error(ws: WebSocket, error: str):
            logging.error(f"WebSocket error for kernel {self.kernel_id}: {error}")
            ws.close()

        websocket.enableTrace(False)
        return websocket.WebSocketApp(
            f"{JUPYTER_KERNEL_WS_GATEWAY}/api/kernels/{self.kernel_id}/channels",
            on_open=on_open,
            on_error=on_error,
            on_message=on_message
        )

    def _handle_message(self, ws: WebSocket, event_message: dict):
        msg_type = event_message["msg_type"]

        if msg_type == "execute_result":
            self.result.append(event_message["content"]["data"]["text/plain"])
            ws.close()
        elif msg_type == "execute_reply":
            self.result.append(f"Code executed successfully")
            ws.close()
        elif msg_type == "error":
            ws.close()
            raise Exception(f"{json.dumps(event_message['content']['traceback'])}")
        elif msg_type == "display_data" and "image/png" in event_message["content"]["data"]:
            self._save_image(event_message["content"]["data"]["image/png"])

    def _save_image(self, image_data: str):
        image_data = base64.b64decode(image_data)
        image_path = f"{uuid.uuid4()}.png"
        with open(os.path.join(self.base_dir, self.thread_id, image_path), "wb") as fp:
            fp.write(image_data)
        self.result.append(
            f"Execution result is an image available at {self.http_server_endpoint}{self.thread_id}/{image_path}")


@tool
def jupyter_code_interpreter_tool(specification: str, runnableConfig: RunnableConfig) -> str:
    """
    Generates and executes Python code to respond to a natural language specification.

    :param specification: The specification to generate Python code from
    :return: Standard output of the code
    """
    code = None
    try:
        writer = get_stream_writer()
        writer({"custom_event": "Generating code 🖋️"})

        prompt = PromptTemplate.from_template("""
            You are an expert in generating Python code in response to a specification.

            Analyze the specification and produce optimized code to address it.
            The code should be in Python and can use the following frameworks:
            - requests
            - pandas
            - matplotlib

            The specification: '''{spec}'''

            Return directly executable Python code.
            Plain text format, no markdown attributes.
        """)

        code = (prompt | ChatOpenAI(model="gpt-4o-mini")).invoke(input={"spec": specification},
                                                                 config={
                                                                     "metadata" : {"display" : "none"}
                                                                 }).content

        writer({"custom_event": "Calling code interpreter 💻"})

        client = JupyterClient(
            base_dir="tmp",
            thread_id=runnableConfig["configurable"]["thread_id"],
            http_server_endpoint="http://localhost:8080/"
        )
        client.create_session()
        logging.debug(code)
        client.exec_code(code)
        writer({"custom_event": "Processing result 🔄"})
        result = client.get_result()
    except Exception as e:
        logging.error(e)
        return f"Calling code interpreter with arguments:\n\n{code}\n\nraised the following error:\n\n{type(e)}: {e}"

    return result
