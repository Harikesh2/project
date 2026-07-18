import { Routes, Route, Navigate } from 'react-router-dom';
import { SignedIn, SignedOut, ClerkLoading, RedirectToSignIn } from '@clerk/clerk-react';

import Layout from '@/components/Layout';
import Home from '@/pages/Home';
import Profile from '@/pages/Profile';
import Search from '@/pages/Search';
import PostDetail from '@/pages/PostDetail';
import Settings from '@/pages/Settings';
import CreateProfile from '@/pages/CreateProfile';
import Chats from '@/pages/Chats';
import Chat from '@/pages/Chat';

import { useEffect } from 'react';

function App() {
  useEffect(() => {
    // Platform defaults to dark mode unless 'light' is explicitly saved
    const savedTheme = localStorage.getItem('theme');
    const isLight = savedTheme === 'light';
    if (isLight) {
      document.documentElement.classList.remove('dark');
    } else {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark'); // Initialize if not set
    }
  }, []);

  return (
    <>
      <ClerkLoading>
        <div className="min-h-screen bg-gray-50 dark:bg-slate-950 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      </ClerkLoading>
 
      <SignedIn>
        <div className="min-h-screen bg-gray-50 dark:bg-slate-950 transition-colors duration-200">
          <Layout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/profile/:userId" element={<Profile />} />
              <Route path="/search" element={<Search />} />
              <Route path="/post/:postId" element={<PostDetail />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/chats" element={<Chats />} />
              <Route path="/chats/:conversationId" element={<Chat />} />
              <Route path="/create-profile" element={<CreateProfile />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        </div>
      </SignedIn>

      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
    </>
  );
}

export default App;