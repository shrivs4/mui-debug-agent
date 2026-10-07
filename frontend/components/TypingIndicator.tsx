type Props = {
  isSlow: boolean;
};

export function TypingIndicator({ isSlow }: Props) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[75%] rounded-2xl rounded-tl-sm bg-gray-100 px-4 py-3 dark:bg-gray-800">
        <div className="flex items-center gap-1">
          <span className="size-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]" />
          <span className="size-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]" />
          <span className="size-2 animate-bounce rounded-full bg-gray-400" />
        </div>
        {isSlow && (
          <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            Waking the server — the first request can take up to a minute.
          </p>
        )}
      </div>
    </div>
  );
}
