import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const suggestions = [
  'What qualifies as an invention under Indian patent law?',
  'How can traditional knowledge be protected?',
  'Explain benefit-sharing under biodiversity law.',
]

export default function ChatMessages({
  messages,
  isLoading,
  error,
  messagesEndRef,
  onSendSuggestion,
}) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className="mx-auto flex min-h-full w-full max-w-4xl flex-col px-4 pb-8 pt-8 sm:px-8">
        {messages.length === 0 ? (
          <div className="my-auto flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-6 flex size-16 items-center justify-center rounded-3xl bg-emerald-100 text-2xl font-bold text-emerald-800">
              IP
            </div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-emerald-700">
              IP Shakti Sahayak
            </p>
            <h2 className="mt-3 max-w-xl text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
              How can I help you today?
            </h2>
            <p className="mt-4 max-w-lg text-base leading-7 text-slate-500">
              Get clear, source-based guidance on intellectual property, Ayurveda,
              biodiversity, and related regulations.
            </p>
            <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-3">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  disabled={isLoading}
                  onClick={() => onSendSuggestion(suggestion)}
                  className="rounded-xl border border-slate-200 bg-white p-4 text-left text-sm leading-5 text-slate-600 shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-md disabled:opacity-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-8">
            {messages.map((message, index) => (
              <article
                key={`${message.role}-${index}`}
                className={`flex gap-3 sm:gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {message.role !== 'user' && (
                  <div className="mt-1 flex size-9 shrink-0 items-center justify-center rounded-xl bg-emerald-700 text-[11px] font-bold text-white">
                    IP
                  </div>
                )}
                <div
                  className={
                    message.role === 'user'
                      ? 'max-w-[85%] rounded-2xl rounded-tr-md bg-emerald-800 px-4 py-3 text-[15px] leading-7 text-white sm:max-w-[75%]'
                      : 'markdown-body min-w-0 max-w-[calc(100%-3rem)] flex-1 pt-1 text-[15px] leading-7 text-slate-700'
                  }
                >
                  {message.role === 'assistant' ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {message.content}
                    </ReactMarkdown>
                  ) : (
                    message.content
                  )}
                </div>
              </article>
            ))}
            {isLoading && (
              <div className="flex items-center gap-3 text-sm text-slate-500" role="status">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-emerald-700 text-[11px] font-bold text-white">
                  IP
                </div>
                <span className="loading-dots">Preparing a helpful answer</span>
              </div>
            )}
            {error && (
              <div
                className="ml-12 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-800"
                role="alert"
              >
                <p className="font-semibold">The request could not be completed.</p>
                <p className="mt-1 break-words">{error}</p>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>
    </div>
  )
}
