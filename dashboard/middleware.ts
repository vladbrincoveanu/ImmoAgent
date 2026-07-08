import { withAuth } from 'next-auth/middleware';

// Freemium funnel: keep friction low so people actually try the app.
// PUBLIC (no login): landing page, the /dashboard property grid, and all
// read APIs — this is the free sample. Pro-only data is already gated at the
// API layer (402 via gateProfile), so no auth wall is needed there.
// GATED (login required): the interactive map — the "wow" payoff we ask
// visitors to sign in for.
export default withAuth({
  pages: {
    signIn: '/sign-in',
  },
});

export const config = {
  matcher: [
    '/dashboard/map/:path*',
  ],
};
