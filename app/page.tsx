'use client';

import { useEffect, useRef, useState, KeyboardEvent } from 'react';
import { useChat } from '@/hooks/useChat';
import { ChatMessage } from '@/components/ChatMessage';
import { TypingIndicator } from '@/components/TypingIndicator';
import { EmptyState } from '@/components/EmptyState';

export default function Home() {
  const { messages, isLoading, isSlow, sendMessage, newChat, retry } = useChat();
  const [input, setInput] = useState('');
  const threadRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when messages or loading state changes
  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const submit = () => {
    const q = input.trim();
    if (!q || isLoading) return;
    setInput('');
    sendMessage(q);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const isEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="flex h-screen flex-col bg-white dark:bg-gray-950">
      {/* Header */}
      <header className="flex shrink-0 items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-800">
        <h1 className="text-base font-semibold text-gray-900 dark:text-gray-100">
          MUI Debug Agent
        </h1>
        <button
          onClick={newChat}
          className="rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          New chat
        </button>
      </header>

      {/* Thread */}
      <div ref={threadRef} className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <EmptyState onSelect={(q) => { sendMessage(q); }} />
        ) : (
          <div className="mx-auto flex max-w-2xl flex-col gap-4 px-4 py-6">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} onRetry={retry} />
            ))}
            {isLoading && <TypingIndicator isSlow={isSlow} />}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-gray-200 px-4 py-3 dark:border-gray-800">
        <div className="mx-auto flex max-w-2xl items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={1}
            placeholder="Ask about an MUI bug or prop…"
            className="flex-1 resize-none rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500"
            style={{ maxHeight: '8rem', overflowY: 'auto' }}
          />
          <button
            onClick={submit}
            disabled={isLoading || !input.trim()}
            className="shrink-0 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
          >
            Send
          </button>
        </div>
        <p className="mx-auto mt-1.5 max-w-2xl text-center text-xs text-gray-400 dark:text-gray-600">
          Enter to send · Shift+Enter for newline
        </p>
      </div>
    </div>
  );
}
