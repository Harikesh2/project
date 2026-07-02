/// <reference types="vite/client" />

interface ClerkSession {
  getToken: () => Promise<string | null>;
}

interface ClerkInstance {
  session?: ClerkSession;
}

interface Window {
  Clerk?: ClerkInstance;
}
