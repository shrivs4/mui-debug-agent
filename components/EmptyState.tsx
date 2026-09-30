const EXAMPLES = [
  'CircularProgress renders as a white square in dark mode',
  'TextField inputMode prop doesn\'t reach the HTML input',
  'How do I change the border color of an outlined TextField?',
];

type Props = {
  onSelect: (question: string) => void;
};

export function EmptyState({ onSelect }: Props) {
  return (
    <div className="flex flex-col items-center justify-center gap-6 px-4 py-16">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-100">
          MUI Debug Agent
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Ask anything about Material UI bugs, props, or styling.
        </p>
      </div>
      <div className="flex w-full max-w-lg flex-col gap-2">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            onClick={() => onSelect(q)}
            className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 transition-colors hover:border-blue-300 hover:bg-blue-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-blue-600 dark:hover:bg-blue-950"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
