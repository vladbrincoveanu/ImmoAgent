import NextAuth from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'

if (!process.env.NEXTAUTH_SECRET) {
  console.error('NEXTAUTH_SECRET is not set!')
}

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' }
      },
      async authorize(credentials: any) {
        if (credentials?.username === 'test' && credentials?.password === 'test123') {
          return { id: 'test-user-id', name: 'Test User', email: 'test@example.com', role: 'user' }
        }
        return null
      }
    })
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.role = (user as any).role
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as any).role = token.role
      }
      return session
    }
  },
  pages: {
    signIn: '/login',
    error: '/login'
  },
  session: {
    maxAge: 30 * 24 * 60 * 60 // 30 days
  }
})

export { handler as GET, handler as POST }