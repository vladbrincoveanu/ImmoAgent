import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { validateSession } from './lib/auth'

const SESSION_COOKIE = 'immo_session'

export function middleware(request: NextRequest) {
  const session = request.cookies.get(SESSION_COOKIE)

  if (!validateSession(session?.value)) {
    const url = request.nextUrl.clone()
    if (request.nextUrl.pathname.startsWith('/dashboard')) {
      url.pathname = '/login'
      return NextResponse.redirect(url)
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*']
}