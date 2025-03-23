import json

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


def load_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        SystemMessage("""
        Tu es un assistant spécialisé dans la gestion des demandes génériques des utilisateurs. 
        
        Format des réponses: 
        - Markdown
        
        Tonalité :
        - Humoristique
        
        """),
        MessagesPlaceholder("messages")
    ])
