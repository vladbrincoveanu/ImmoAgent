export function decodeSession(cookieValue: string): { user: string } | null {
  try {
    const decoded = Buffer.from(cookieValue, 'base64').toString('utf-8')
    const parts = decoded.split(':')
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      return null
    }
    const [user, timestamp] = parts
    if (!user || !timestamp || isNaN(Number(timestamp))) {
      return null
    }
    return { user }
  } catch {
    return null
  }
}

export function validateSession(cookieValue: string | undefined): boolean {
  if (!cookieValue) return false
  return decodeSession(cookieValue) !== null
}