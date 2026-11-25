import { useState } from 'react'
import { authenticate, getErrorMessage } from '../services/api.js'

export default function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const isRegistering = mode === 'register'

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      const endpoint = isRegistering ? '/api/register' : '/api/login'
      const payload = isRegistering
        ? { name: name.trim(), email: email.trim(), password }
        : { email: email.trim(), password }
      const data = await authenticate(endpoint, payload)

      if (!data?.accessToken) {
        throw new Error('The server did not return an access token.')
      }

      onAuthenticated(data)
    } catch (requestError) {
      if (isRegistering && requestError.response?.status === 409) {
        setError('An account with this email already exists. Log in or use a different email.')
      } else {
        setError(getErrorMessage(requestError))
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  function changeMode(nextMode) {
    setMode(nextMode)
    setError('')
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f7f8fa] px-3 py-5 text-slate-900 sm:px-6 sm:py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_18px_60px_rgba(15,23,42,0.09)] md:min-h-[620px] md:grid-cols-2">
        <section className="relative hidden flex-col justify-between overflow-hidden bg-emerald-800 p-10 text-white md:flex lg:p-14">
          <div className="absolute -right-24 -top-20 size-80 rounded-full border border-white/10" />
          <div className="absolute -right-10 -top-6 size-52 rounded-full border border-white/10" />
          <div className="relative flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-white/15 text-sm font-bold">IP</div>
            <span className="text-lg font-semibold tracking-tight">IP Shakti</span>
          </div>
          <div className="relative max-w-md py-12">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-100">
              Your legal knowledge assistant
            </p>
            <h2 className="mt-5 text-4xl font-semibold leading-tight tracking-tight lg:text-5xl">
              Know your rights. Protect what you create.
            </h2>
            <p className="mt-5 text-base leading-7 text-emerald-50/85">
              Explore intellectual property, Ayurveda, biodiversity, and regulatory guidance in one place.
            </p>
          </div>
          <p className="relative text-xs text-emerald-100/70">
            Clear, source-based information for your questions.
          </p>
        </section>

        <section className="flex min-w-0 items-center justify-center px-4 py-8 sm:px-8 sm:py-12 md:px-10 lg:px-14">
          <div className="w-full max-w-[400px]">
            <div className="mb-7 text-center md:mb-8">
              <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-emerald-700 text-base font-bold tracking-wide text-white md:hidden">
                IP
              </div>
              <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700 md:mt-0">
                {isRegistering ? 'Get started' : 'Welcome back'}
              </p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
                {isRegistering ? 'Create your account' : 'Log in to IP Shakti'}
              </h1>
              <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500">
                {isRegistering
                  ? 'Sign up to save and revisit your conversations.'
                  : 'Log in to continue your legal knowledge conversations.'}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {isRegistering && (
                <label className="block text-sm font-medium text-slate-700">
                  Name
                  <input
                    type="text"
                    autoComplete="name"
                    required
                    maxLength={200}
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    className="mt-2 w-full rounded-xl border border-slate-200 px-3.5 py-3 text-base font-normal outline-none transition placeholder:text-slate-400 focus:border-emerald-600 focus:ring-4 focus:ring-emerald-600/10"
                    placeholder="Your name"
                  />
                </label>
              )}
              <label className="block text-sm font-medium text-slate-700">
                Email
                <input
                  type="email"
                  autoComplete="email"
                  required
                  maxLength={320}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-200 px-3.5 py-3 text-base font-normal outline-none transition placeholder:text-slate-400 focus:border-emerald-600 focus:ring-4 focus:ring-emerald-600/10"
                  placeholder="you@example.com"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Password
                <input
                  type="password"
                  autoComplete={isRegistering ? 'new-password' : 'current-password'}
                  required
                  minLength={isRegistering ? 6 : 1}
                  maxLength={200}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-200 px-3.5 py-3 text-base font-normal outline-none transition placeholder:text-slate-400 focus:border-emerald-600 focus:ring-4 focus:ring-emerald-600/10"
                  placeholder={isRegistering ? '6–200 characters' : 'Your password'}
                />
              </label>

              {error && (
                <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm leading-5 text-red-800" role="alert">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="flex w-full items-center justify-center rounded-xl bg-emerald-700 px-4 py-3 text-base font-medium text-white transition hover:bg-emerald-800 disabled:cursor-wait disabled:opacity-60"
              >
                {isSubmitting ? 'Please wait...' : isRegistering ? 'Create account' : 'Log in'}
              </button>
              {isRegistering && (
                <p className="text-center text-xs text-slate-500">
                  Password must be 6–200 characters.
                </p>
              )}
            </form>

            <p className="mt-6 text-center text-sm text-slate-600">
              {isRegistering ? 'Already have an account?' : 'New to IP Shakti?'}{' '}
              <button
                type="button"
                onClick={() => changeMode(isRegistering ? 'login' : 'register')}
                className="font-semibold text-emerald-800 hover:text-emerald-950"
              >
                {isRegistering ? 'Log in' : 'Create an account'}
              </button>
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}
