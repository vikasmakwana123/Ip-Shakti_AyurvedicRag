export default function ChatHeader({ onToggleSidebar, onStartNewChat }) {
  return (
    <header className="flex h-[72px] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label="Open conversation menu"
          className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-600 md:hidden"
        >
          <svg viewBox="0 0 24 24" fill="none" className="size-5" aria-hidden="true">
            <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </button>
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold text-slate-800">
            IPR Knowledge Assistant
          </h1>
          <p className="mt-0.5 hidden text-xs text-slate-500 sm:block">
            Ask about intellectual property and regulation
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={onStartNewChat}
        className="shrink-0 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
      >
        New chat
      </button>
    </header>
  )
}
