import { NextResponse } from 'next/server'

const ADMIN_USER = 'test'
const ADMIN_PASS = 'test123'
const SESSION_COOKIE = 'immo_session'
const SESSION_SECRET = 'immo-scouter-dashboard-secret-2024'

function createSessionToken(user: string): string {
  const payload = `${user}:${Date.now()}`
  return Buffer.from(payload).toString('base64')
}

export async function POST(request: Request) {
  const formData = await request.formData()
  const username = formData.get('username') as string
  const password = formData.get('password') as string
  const csrfToken = formData.get('csrfToken') as string

  if (!username || !password) {
    return NextResponse.redirect(new URL('/login?error=missing', request.url))
  }

  if (username !== ADMIN_USER || password !== ADMIN_PASS) {
    return NextResponse.redirect(new URL('/login?error=invalid', request.url))
  }

  const token = createSessionToken(username)
  const response = NextResponse.redirect(new URL('/dashboard', request.url))

  response.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: true,
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 30,
    path: '/',
  })

  return response
}

export async function GET(request: Request) {
  const cookies = request.headers.get('cookie') || ''
  const session = cookies.split(';').find(c => c.trim().startsWith(`${SESSION_COOKIE}=`))

  if (!session) {
    return NextResponse.json({ authenticated: false })
  }

  const token = session.split('=')[1]
  try {
    const decoded = Buffer.from(token, 'base64').toString('utf-8')
    const [user] = decoded.split(':')
    return NextResponse.json({ authenticated: true, user })
  } catch {
    return NextResponse.json({ authenticated: false })
  }
}