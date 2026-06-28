import createMiddleware from 'next-intl/middleware';
import { routing } from './routing';

export default createMiddleware(routing);

export const config = {
  matcher: [
    // Match all routes except api, _next, and static files
    '/((?!api|_next/static|_next/image|favicon\\.ico).*)',
  ],
};
