'use client';

import { useState, useCallback, useRef } from 'react';

export type Message = {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  question?: string;
};

type NdjsonEvent =
  | { type: 'status'; message: string }
  | { type: 'text'; delta: string }
  | { type: 'done' }
  | { type: 'error'; message: string };

type UseChatReturn = {
  messages: Message[];
  isLoading: boolean;
  isSlow: boolean;
  isWaiting: boolean;
  status: string | null;
  streamingId: string | null;
  conversationId: string;
  sendMessage: (question: string) => Promise<void>;
  newChat: () => void;
  retry: (question: string) => void;
};

function newId() {
  return crypto.randomUUID();
}

function parseNdjsonLine(line: string): NdjsonEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed) as NdjsonEvent;
  } catch {
    return null;
  }
}

// Split a buffered string + new chunk into complete lines and a leftover remainder.
function splitLines(buffer: string, chunk: string): { lines: string[]; remainder: string } {
  const combined = buffer + chunk;
  const parts = combined.split('\n');
  return { lines: parts.slice(0, -1), remainder: parts[parts.length - 1] };
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSlow, setIsSlow] = useState(false);
  const [isWaiting, setIsWaiting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState(() => newId());
  const slowTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchAnswer = useCallback(
    async (question: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setIsLoading(true);
      setIsSlow(false);
      setIsWaiting(true);
      setStatus(null);

      slowTimerRef.current = setTimeout(() => setIsSlow(true), 8000);

      try {
        const res = await fetch('/api/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question, conversation_id: conversationId }),
          signal: controller.signal,
        });

        if (controller.signal.aborted) return;

        const contentType = res.headers.get('content-type') ?? '';

        if (res.ok && contentType.includes('application/x-ndjson')) {
          const reader = res.body!.getReader();
          const decoder = new TextDecoder();
          let buffer = '';
          let assistantId: string | null = null;
          let firstEvent = true;

          const processLine = (line: string) => {
            const event = parseNdjsonLine(line);
            if (!event) return;

            // Clear the slow-server timer on the very first event of any kind.
            if (firstEvent) {
              if (slowTimerRef.current) clearTimeout(slowTimerRef.current);
              setIsSlow(false);
              firstEvent = false;
            }

            if (event.type === 'status') {
              setStatus(event.message);
            } else if (event.type === 'text') {
              setIsWaiting(false);
              setStatus(null);
              if (assistantId === null) {
                assistantId = newId();
                const id = assistantId;
                setStreamingId(id);
                setMessages((prev) => [...prev, { id, role: 'assistant', content: event.delta }]);
              } else {
                const id = assistantId;
                setMessages((prev) =>
                  prev.map((m) => (m.id === id ? { ...m, content: m.content + event.delta } : m))
                );
              }
            } else if (event.type === 'error') {
              setIsWaiting(false);
              setMessages((prev) => [
                ...prev,
                { id: newId(), role: 'error', content: event.message, question },
              ]);
            }
            // 'done' → nothing to do
          };

          try {
            while (true) {
              const { done, value } = await reader.read();
              if (controller.signal.aborted) {
                reader.cancel().catch(() => {});
                return;
              }
              if (done) {
                // Flush any remaining partial line.
                if (buffer) processLine(buffer);
                break;
              }
              const chunk = decoder.decode(value, { stream: true });
              const { lines, remainder } = splitLines(buffer, chunk);
              buffer = remainder;
              for (const line of lines) processLine(line);
            }
          } catch (err) {
            if (controller.signal.aborted) {
              reader.cancel().catch(() => {});
              return;
            }
            throw err;
          }
        } else {
          // Non-streaming fallback: pre-stream errors (401, 429, 502) or plain JSON.
          setIsWaiting(false);
          let data: { answer?: string; error?: string };
          if (contentType.includes('application/json')) {
            data = await res.json();
          } else {
            // Non-JSON body (e.g. Vercel 504 HTML page)
            data = { error: 'The server took too long to respond — please retry.' };
          }

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
              { id: newId(), role: 'assistant', content: data.answer! },
            ]);
          }
        }
      } catch {
        if (controller.signal.aborted) return;
        setIsWaiting(false);
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
        if (controller.signal.aborted) return;
        if (slowTimerRef.current) clearTimeout(slowTimerRef.current);
        setIsLoading(false);
        setIsSlow(false);
        setIsWaiting(false);
        setStatus(null);
        setStreamingId(null);
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
      // Remove last error message; user message is already in the thread.
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
    abortRef.current?.abort();
    if (slowTimerRef.current) clearTimeout(slowTimerRef.current);
    setMessages([]);
    setIsLoading(false);
    setIsSlow(false);
    setIsWaiting(false);
    setStatus(null);
    setStreamingId(null);
    setConversationId(newId());
  }, []);

  return { messages, isLoading, isSlow, isWaiting, status, streamingId, conversationId, sendMessage, newChat, retry };
}
