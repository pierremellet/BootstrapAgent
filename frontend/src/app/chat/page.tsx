"use client"

import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { v4 as uuidv4 } from 'uuid';

interface ChatMessage {
  content: string;
  id: string;
  type: string;
  response_metadata: any;
  additional_kwargs: any;
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
  const [isSending, setIsSending] = useState<boolean>(false);
  const [sessionId, setSessionId] = useState<string>('');
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setSessionId(uuidv4());
  }, []);

  const handleSendMessage = async () => {
    if (input.trim()) {
      const humanMessage: ChatMessage = {
        content: input,
        id: new Date().toISOString(),
        type: "Human",
        additional_kwargs: {},
        response_metadata: {}
      };

      setMessages(old => [...old, humanMessage]);
      setIsSending(true);
      controllerRef.current = new AbortController();

      try {
        const response = await fetch(`http://localhost:8000/threads/${sessionId}/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ message: input }),
          signal: controllerRef.current.signal
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
                  return [...old, { content: payload['custom_event'], type: "custom_event", id: uuidv4(), response_metadata: {}, additional_kwargs: {} }];
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
        setIsSending(false);
      }
    }
  };

  const handleStopMessage = () => {
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    setIsSending(false);
  };

  return (
    <div className="flex flex-col w-full p-4">
      <MessageList messages={messages} />
      <div className="my-2 p-2 bg-gray-100 rounded-lg">
        <strong>Session ID:</strong> {sessionId}
      </div>
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
  const messageClass = message.type !== 'Human' ? 'bg-blue-200 mr-10' : 'bg-gray-200 ml-10';

  return (
    <div className={`p-2 mb-2 ${messageClass} rounded-lg`}>
      <p><strong>Type:</strong> {message.type}</p>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown><br />
      <p><strong>ID:</strong> {message.id}</p>
      <p><strong>response_metadata:</strong> {JSON.stringify(message.response_metadata)}</p>
      <p><strong>additional_kwargs:</strong> {JSON.stringify(message.additional_kwargs)}</p>
    </div>
  );
};

const ChatInput: React.FC<{
  input: string,
  setInput: React.Dispatch<React.SetStateAction<string>>,
  handleSendMessage: () => void,
  isSending: boolean,
  handleStopMessage: () => void
}> = ({ input, setInput, handleSendMessage, isSending, handleStopMessage }) => {

  const numberOfLines = input.split('\n').length;
  const maxLines = 10;
  const rows = numberOfLines > maxLines ? maxLines : numberOfLines;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter") {
      if (e.shiftKey) {
        setInput(prev => prev + "\n");
      } else {
        if (isSending) {
          handleStopMessage();
        } else {
          handleSendMessage();
        }
      }
      e.preventDefault();
    }
  };

  return (
    <div className="flex-shrink-0 flex">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        className="flex-1 p-2 border rounded-l-lg resize-none overflow-auto"
        placeholder="Type a message..."
        rows={rows}
        style={{
          maxHeight: '200px',
          overflowY: numberOfLines > maxLines ? 'auto' : 'hidden'
        }}
      />
      <button
        onClick={isSending ? handleStopMessage : handleSendMessage}
        className="p-2 bg-blue-500 text-white rounded-r-lg"
      >
        {isSending ? 'Stop' : 'Send'}
      </button>
    </div>
  );
};

export default ChatApp;