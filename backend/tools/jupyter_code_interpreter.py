import base64
import json
import logging
import os
import re
import shutil
import typing
import uuid
from time import sleep

import requests
import websocket
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field
from websocket import WebSocket

# Constants
JUPYTER_KERNEL_HTTP_GATEWAY = os.getenv('JUPYER_KERNEL_HTTP_GATEWAY')
JUPYTER_KERNEL_WS_GATEWAY = os.getenv('JUPYER_KERNEL_WS_GATEWAY')


class CodeExecResult(BaseModel):
    spec: typing.Optional[str] = Field(description="Le code", default=[])
    stdout: list[str] = Field(description="STDOUT", default=[])
    stderr: typing.Optional[list[str]] = Field(description="STDERR", default=[])
    output_files_url: typing.Optional[list[str]] = Field(description="Liste des fichiers", default=[])


class JupyterClient:
    def __init__(self, base_dir: str, thread_id: str, http_server_endpoint: str):
        self.result: CodeExecResult = CodeExecResult(stdout=[])
        self.kernel_id = None
        self.thread_id = thread_id
        self.base_dir = base_dir
        self.http_server_endpoint = http_server_endpoint
    def get_result(self) -> CodeExecResult:
        return self.result

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
        self.result.spec = code
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
        print(event_message)
        msg_type = event_message["msg_type"]

        if msg_type == "execute_result":
            self.result.stdout.append(event_message["content"]["data"]["text/plain"])
            ws.close()
        elif msg_type == "execute_reply":
            self.result.stdout.append(f"Code executed successfully")
            ws.close()
        elif msg_type == "error":
            self.result.stderr.append("\n".join([re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', x) for x in
                                                 event_message['content']['traceback']]))
            ws.close()
        elif msg_type == "stream":
            self.result.stdout.append(json.dumps(event_message['content']['text']))
        elif msg_type == "display_data" and "image/png" in event_message["content"]["data"]:
            image_path = self._save_file(event_message["content"]["data"]["image/png"], "png")
            self.result.output_files_url.append(f"{self.http_server_endpoint}{self.thread_id}/{image_path}")

    def _save_file(self, data: str, type: str) -> str:
        image_data = base64.b64decode(data)
        image_path = f"{uuid.uuid4()}.{type}"
        with open(os.path.join(self.base_dir, self.thread_id, image_path), "wb") as fp:
            fp.write(image_data)
        return image_path


@tool
def jupyter_code_interpreter_tool(
        code: typing.Annotated[str, "Le code Python à exécuter"],
        runnableConfig: RunnableConfig) -> str:
    """
    Cette fonction permet d'exécuter du code Python et de récupérer les résultats.

    **Contraintes :**

    - Le code doit être écrit en Python.
    - Les frameworks autorisés sont :
      - `requests` pour les requêtes HTTP.
      - `pandas` pour la manipulation et l'analyse de données.
      - `matplotlib` pour la création de visualisations.
    - Il est interdit de générer ou d'exécuter du code qui écrit des fichiers.
    - Le code doit retourner un résultat sur la sortie standard ou sur une sortie interactive.


    :param specification: Une description du besoin en langage naturelle qui servira à générer du code.
    :return: Un object json qui décrit le résultat de l'exécution du code et les URL des fichiers produits.
    La clé output_files_url contient la liste des fichiers en retour de l'exécution du code.
    La clé stdout contient la sortie standard du code.


    """
    try:
        writer = get_stream_writer()

        writer({"custom_event": "Calling code interpreter 💻"})

        client = JupyterClient(
            base_dir="tmp",
            thread_id=runnableConfig["configurable"]["thread_id"],
            http_server_endpoint="http://localhost:8080/"
        )

        writer({"custom_event": f"Execute code : \n{code}"})
        client.create_session()
        client.exec_code(code)
        writer({"custom_event": "Processing result 🔄"})
        result = client.get_result()
    except Exception as e:
        logging.error(e)
        return f"Calling code interpreter with arguments:\n\n{code}\n\nraised the following error:\n\n{type(e)}: {e}"

    print(result.model_dump_json(indent=3))
    return result.model_dump_json(indent=3) if len(result.stderr) == 0 else f"Erreur lors de l'exécution du code : \n {"\n".join(result.stderr)}"
