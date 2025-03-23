// frontend/src/app/chat/page.tsx
"use client"

import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {v4 as uuidv4} from 'uuid';

interface ChatMessage {
  content: string;
  id: string;
  type: string;
  response_metadata: any;
}

const ChatApp: React.FC = () => {
  return (
    <div className="flex h-screen">
      <ChatWindow />
    </div>
  );
};

const ChatWindow: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState<string>('');
  const [isSending, setIsSending] = useState<boolean>(false); // State to track sending status
  const controllerRef = useRef<AbortController | null>(null); // Reference to AbortController

  const handleSendMessage = async () => {
    if (input.trim()) {
      const humanMessage: ChatMessage = {
        content: input,
        id: new Date().toISOString(),
        type: "Human",
        response_metadata: {}
      };

      setMessages(old => [...old, humanMessage]);
      setIsSending(true); // Update sending status
      controllerRef.current = new AbortController(); // Create a new AbortController

      try {
        const response = await fetch(`http://localhost:8000/threads/${uuidv4()}/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ message: input }),
          signal: controllerRef.current.signal // Pass signal to fetch
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

              const payload = JSON.parse(line);

              if (payload['type']) {

                setMessages(old => {
                  const existingMessageIndex = old.findIndex(msg => msg.id === payload.id);
                  if (existingMessageIndex !== -1) {
                    const updatedMessages = [...old];
                    if (!updatedMessages[existingMessageIndex].content.endsWith(payload.content)) {
                      updatedMessages[existingMessageIndex].content += payload.content;
                    }
                    return updatedMessages;
                  } else {
                    return [...old, { ...payload, type: payload.type }];
                  }
                });
              }

              if (payload['custom_event']) {

                setMessages(old => {
                    return [...old, { content: payload['custom_event'], type: "custom_event", id: uuidv4(), response_metadata: {} }];
               
                });
              }
            }
          });
        }

        setInput('');
      } catch (error: any) {
        if (error.name === 'AbortError') {
          console.log('Stream aborted.');
        } else {
          console.error('Error sending message:', error);
        }
      } finally {
        setIsSending(false); // Reset sending status
      }
    }
  };

  // Function to stop sending a message
  const handleStopMessage = () => {
    if (controllerRef.current) {
      controllerRef.current.abort(); // Abort the fetch request
    }
    setIsSending(false); // Reset sending status
  };

  return (
    <div className="flex flex-col w-full p-4">
      <MessageList messages={messages} />
      <ChatInput
        input={input}
        setInput={setInput}
        handleSendMessage={handleSendMessage}
        isSending={isSending}
        handleStopMessage={handleStopMessage}
      />
    </div>
  );
};

const MessageList: React.FC<{ messages: ChatMessage[] }> = ({ messages }) => {
  const endOfMessagesRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto mb-4">
      {messages.map((message) => (
        <Message key={message.id} message={message} />
      ))}
      <div ref={endOfMessagesRef} />
    </div>
  );
};

const Message: React.FC<{ message: ChatMessage }> = ({ message }) => {
  return (
    <div className="p-2 mb-2 bg-gray-200 rounded-lg">
      <p><strong>Type:</strong> {message.type}</p>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      <p><strong>ID:</strong> {message.id}</p>
      <p><strong>Metadata:</strong> {JSON.stringify(message.response_metadata)}</p>
    </div>
  );
};

const ChatInput: React.FC<{
  input: string,
  setInput: (input: string) => void,
  handleSendMessage: () => void,
  isSending: boolean,
  handleStopMessage: () => void
}> = ({ input, setInput, handleSendMessage, isSending, handleStopMessage }) => {

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      if (isSending) {
        handleStopMessage(); // Stop sending if isSending
      } else {
        handleSendMessage();
      }
    }
  };

  return (
    <div className="flex-shrink-0 flex">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        className="flex-1 p-2 border rounded-l-lg"
        placeholder="Type a message..."
      />
      <button
        onClick={isSending ? handleStopMessage : handleSendMessage}
        className="p-2 bg-blue-500 text-white rounded-r-lg"
      >
        {isSending ? 'Stop' : 'Send'} {/* Button text based on sending state */}
      </button>
    </div>
  );
};

export default ChatApp;