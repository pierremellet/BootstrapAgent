"use client"

import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown'; // Import de react-markdown
import remarkGfm from 'remark-gfm'; // Import de remark-gfm pour le support de GFM

// Interface pour représenter un message
interface ChatMessage {
  content: string;
  id: string;
  type: string; // Ajout d'un type pour le message
  response_metadata: any; // Vous pouvez spécifier un type plus précis si nécessaire
}

// Composant principal de l'application
const ChatApp: React.FC = () => {
  return (
    <div className="flex h-screen">
      <ChatWindow />
    </div>
  );
};

// Fenêtre de chat
const ChatWindow: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState<string>('');

  const handleSendMessage = async () => {
    if (input.trim()) {
      const humanMessage: ChatMessage = {
        content: input,
        id: new Date().toISOString(), // Utilisation d'un identifiant unique
        type: "Human", // Type défini comme "Human"
        response_metadata: {}
      };

      // Ajout du message humain au tableau des messages
      setMessages(old => [...old, humanMessage]);

      try {
        const response = await fetch("http://localhost:8000/threads/12Z34/stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ message: input }),
        });

        if (!response.body) {
          throw new Error("Pas de corps de réponse");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });

          chunk.split("\n").forEach(line => {
            if (line !== "") {
              const payload = JSON.parse(line) as ChatMessage;
              setMessages(old => {
                const existingMessageIndex = old.findIndex(msg => msg.id === payload.id);

                if (existingMessageIndex !== -1) {
                  const updatedMessages = [...old];
                  if (!updatedMessages[existingMessageIndex].content.endsWith(payload.content)) {
                    updatedMessages[existingMessageIndex].content += payload.content; // Concatenation
                  }
                  return updatedMessages;

                } else {
                  return [...old, { ...payload, type: payload.type }];
                }
              });
            }
          });
        }

        setInput('');
      } catch (error) {
        console.error('Error sending message:', error);
      }
    }
  };

  return (
    <div className="flex flex-col w-full p-4">
      <MessageList messages={messages} />
      <ChatInput input={input} setInput={setInput} handleSendMessage={handleSendMessage} />
    </div>
  );
};

// Liste des messages
const MessageList: React.FC<{ messages: ChatMessage[] }> = ({ messages }) => {
  const endOfMessagesRef = useRef<HTMLDivElement | null>(null);

  // Scroll vers le bas quand de nouveaux messages sont ajoutés
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto mb-4">
      {messages.map((message) => (
        <Message key={message.id} message={message} />
      ))}
      <div ref={endOfMessagesRef} /> {/* Une référence pour faire défiler vers le bas */}
    </div>
  );
};

// Composant de message individuel
const Message: React.FC<{ message: ChatMessage }> = ({ message }) => {
  return (
    <div className="p-2 mb-2 bg-gray-200 rounded-lg">
      <p><strong>Type:</strong> {message.type}</p>
      {/* Rendu du contenu avec react-markdown */}
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      <p><strong>ID:</strong> {message.id}</p>
      <p><strong>Metadata:</strong> {JSON.stringify(message.response_metadata)}</p>
    </div>
  );
};

// Entrée de texte pour le chat
const ChatInput: React.FC<{ input: string, setInput: (input: string) => void, handleSendMessage: () => void }> = ({ input, setInput, handleSendMessage }) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSendMessage();
    }
  };

  return (
    <div className="flex-shrink-0 flex">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown} // Ajout de l'événement onKeyDown
        className="flex-1 p-2 border rounded-l-lg"
        placeholder="Type a message..."
      />
      <button onClick={handleSendMessage} className="p-2 bg-blue-500 text-white rounded-r-lg">
        Send
      </button>
    </div>
  );
};

export default ChatApp;