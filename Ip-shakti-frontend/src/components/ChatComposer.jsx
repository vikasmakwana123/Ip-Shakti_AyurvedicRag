export default function ChatComposer({
  query,
  textareaRef,
  isLoading,
  onChange,
  onKeyDown,
  onSubmit,
}) {
  return (
    <div className="shrink-0 bg-gradient-to-t from-[#f7f8fa] via-[#f7f8fa] to-transparent px-4 pb-5 pt-3 sm:px-8">
      <form
        onSubmit={onSubmit}
        className="mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white p-2 shadow-[0_8px_30px_rgba(15,23,42,0.07)] focus-within:border-emerald-400"
      >
        <label htmlFor="chat-input" className="sr-only">
          Ask a question
        </label>
        <textarea
          id="chat-input"
          ref={textareaRef}
          value={query}
          onChange={onChange}
          onKeyDown={onKeyDown}
          placeholder="Ask a question about IP law, Ayurveda, or regulation..."
          rows={2}
          disabled={isLoading}
          className="max-h-40 min-h-14 w-full resize-y border-0 bg-transparent px-3 py-2.5 text-[15px] leading-6 text-slate-800 outline-none placeholder:text-slate-400 disabled:opacity-60"
        />
        <div className="flex items-center justify-between px-2 pb-1">
          <p className="text-xs text-slate-400">
            Press Enter to send · Shift + Enter for a new line
          </p>
          <button
            type="submit"
            disabled={!query.trim() || isLoading}
            aria-label="Send message"
            className="flex size-10 items-center justify-center rounded-xl bg-emerald-700 text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
          >
            <svg viewBox="0 0 24 24" fill="none" className="size-5" aria-hidden="true">
              <path d="M12 19V5m0 0-6 6m6-6 6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </form>
      <p className="mx-auto mt-3 max-w-4xl text-center text-[11px] leading-5 text-slate-400">
        IP Shakti provides general information, not legal advice. Verify important matters with a qualified professional.
      </p>
    </div>
  )
}
