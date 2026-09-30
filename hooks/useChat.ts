'use client';

import { useState, useCallback, useRef } from 'react';

export type Message = {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  question?: string;
};

type UseChatReturn = {
  messages: Message[];
  isLoading: boolean;
  isSlow: boolean;
  conversationId: string;
  sendMessage: (question: string) => Promise<void>;
  newChat: () => void;
  retry: (question: string) => void;
};

function newId() {
  return crypto.randomUUID();
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSlow, setIsSlow] = useState(false);
  const [conversationId, setConversationId] = useState(() => newId());
  const slowTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchAnswer = useCallback(
    async (question: string) => {
      setIsLoading(true);
      setIsSlow(false);

      slowTimerRef.current = setTimeout(() => setIsSlow(true), 8000);

      try {
        const res = await fetch('/api/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question, conversation_id: conversationId }),
        });

        const data = await res.json();

        if (!res.ok || data.error) {
          setMessages((prev) => [
            ...prev,
            {
              id: newId(),
              role: 'error',
              content: data.error ?? 'Something went wrong. Please try again.',
              question,
            },
          ]);
        } else {
          setMessages((prev) => [
            ...prev,
            { id: newId(), role: 'assistant', content: data.answer },
          ]);
        }
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: 'error',
            content: 'Network error — could not reach the server.',
            question,
          },
        ]);
      } finally {
        if (slowTimerRef.current) clearTimeout(slowTimerRef.current);
        setIsLoading(false);
        setIsSlow(false);
      }
    },
    [conversationId]
  );

  const sendMessage = useCallback(
    async (question: string) => {
      if (!question.trim() || isLoading) return;
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: 'user', content: question },
      ]);
      await fetchAnswer(question);
    },
    [isLoading, fetchAnswer]
  );

  const retry = useCallback(
    (question: string) => {
      // Remove last error message; user message is already in the thread
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === 'error') return prev.slice(0, -1);
        return prev;
      });
      fetchAnswer(question);
    },
    [fetchAnswer]
  );

  const newChat = useCallback(() => {
    if (slowTimerRef.current) clearTimeout(slowTimerRef.current);
    setMessages([]);
    setIsLoading(false);
    setIsSlow(false);
    setConversationId(newId());
  }, []);

  return { messages, isLoading, isSlow, conversationId, sendMessage, newChat, retry };
}
