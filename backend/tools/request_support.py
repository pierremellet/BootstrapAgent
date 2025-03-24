import os
from typing import Annotated

from label_studio_sdk.client import LabelStudio
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState


@tool
def request_support_tool(
        user_request: Annotated[str, "La raison précise de la demande de support"],
        state: Annotated[dict, InjectedState]
) -> str:
    """
    Permet de faire une demande de support lorsque tu ne sais pas quoi répondre ou que tu rencontres un incident.

    Demander l'approbation de l'utilisateur avant d'utiliser cette fonction.

    :param user_request: Résum" de la conversation pour laquelle tu n'as pas de réponse à apporter
    :return: des informations sur la demande de support
    """

    ls = LabelStudio(base_url=os.getenv("LABEL_STUDIO_URL"), api_key=os.getenv("LABEL_STUDIO_API_KEY"))
    task = ls.tasks.create(
        project=1,
        data={
            'user_request': user_request,
            'messages': [{
                "author": m.type,
                "text": m.content
            }
                for m in state['messages']]
        }
    )

    return f"Demande réalisée : http://localhost:8091/projects/1/data?tab=7&task={task.id}"
