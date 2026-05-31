export function decodeSession(cookieValue: string): { user: string } | null {
  try {
    const decoded = Buffer.from(cookieValue, 'base64').toString('utf-8')
    const [user] = decoded.split(':')
    return user ? { user } : null
  } catch {
    return null
  }
}

export function validateSession(cookieValue: string | undefined): boolean {
  if (!cookieValue) return false
  return decodeSession(cookieValue) !== null
}