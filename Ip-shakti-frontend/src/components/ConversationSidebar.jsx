export default function ConversationSidebar({
  auth,
  conversations,
  currentConversationId,
  historyLoading,
  historyError,
  sidebarOpen,
  isLoading,
  onStartNewChat,
  onLoadConversations,
  onOpenConversation,
  onLogout,
  onClose,
}) {
  return (
    <>
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close conversation menu"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-slate-950/25 md:hidden"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-[240px] shrink-0 flex-col overflow-hidden border-r border-slate-200 bg-white p-4 transition-transform md:static md:z-auto md:flex md:translate-x-0 ${
          sidebarOpen ? 'flex translate-x-0' : 'hidden -translate-x-full'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-2xl bg-emerald-700 text-sm font-bold tracking-wide text-white">
            IP
          </div>
          <div className="min-w-0">
            <p className="font-semibold tracking-tight text-slate-900">IP Shakti</p>
            <p className="truncate text-xs text-slate-500">Legal knowledge assistant</p>
          </div>
        </div>

        <button
          type="button"
          onClick={onStartNewChat}
          className="mt-6 flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-700 transition hover:border-emerald-700 hover:text-emerald-800"
        >
          <span className="text-lg leading-none">+</span>
          New conversation
        </button>

        <div className="mt-6 flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="flex items-center justify-between px-1">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
              Your conversations
            </p>
            {historyLoading && (
              <span className="text-xs text-slate-400" role="status">Loading</span>
            )}
          </div>
          {historyError && (
            <div className="mt-3 rounded-lg bg-red-50 p-3 text-xs leading-5 text-red-800" role="alert">
              <p>{historyError}</p>
              <button
                type="button"
                onClick={onLoadConversations}
                className="mt-1 font-semibold underline"
              >
                Try again
              </button>
            </div>
          )}
          <div className="mt-2 min-h-0 flex-1 space-y-1 overflow-hidden">
            {conversations.map((conversation) => {
              const firstPrompt = conversation.messages?.find(
                (message) => message.role === 'user',
              )?.content
              const title = firstPrompt
                ? firstPrompt.length > 42
                  ? `${firstPrompt.slice(0, 42)}…`
                  : firstPrompt
                : 'New conversation'

              return (
                <button
                  key={conversation.id}
                  type="button"
                  disabled={isLoading}
                  onClick={() => onOpenConversation(conversation)}
                  className={`w-full rounded-lg px-2.5 py-2 text-left text-sm transition disabled:opacity-50 ${
                    currentConversationId === conversation.id
                      ? 'bg-emerald-50 text-emerald-900'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  <span className="block truncate font-medium">{title}</span>
                  <span className="mt-1 block text-xs text-slate-400">
                    {conversation.createdAt
                      ? new Date(conversation.createdAt).toLocaleDateString()
                      : ''}
                  </span>
                </button>
              )
            })}
            {!historyLoading && conversations.length === 0 && !historyError && (
              <p className="px-2 py-3 text-xs leading-5 text-slate-400">
                Your saved conversations will appear here.
              </p>
            )}
          </div>
        </div>

        <div className="mt-3 border-t border-slate-100 pt-3">
          <p className="truncate text-sm font-medium text-slate-700">
            {auth.name || auth.email}
          </p>
          {auth.name && (
            <p className="mt-0.5 truncate text-xs text-slate-400">{auth.email}</p>
          )}
          <button
            type="button"
            onClick={onLogout}
            className="mt-3 text-sm font-medium text-slate-500 transition hover:text-red-700"
          >
            Log out
          </button>
        </div>
      </aside>
    </>
  )
}
