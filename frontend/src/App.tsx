import { Routes, Route, Navigate } from 'react-router-dom';
import { SignedIn, SignedOut, ClerkLoading, RedirectToSignIn } from '@clerk/clerk-react';

import Layout from '@/components/Layout';
import Home from '@/pages/Home';
import Profile from '@/pages/Profile';
import Search from '@/pages/Search';
import PostDetail from '@/pages/PostDetail';
import Settings from '@/pages/Settings';
import CreateProfile from '@/pages/CreateProfile';

function App() {
  return (
    <>
      <ClerkLoading>
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      </ClerkLoading>

      <SignedIn>
        <div className="min-h-screen bg-gray-50">
          <Layout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/profile/:userId" element={<Profile />} />
              <Route path="/search" element={<Search />} />
              <Route path="/post/:postId" element={<PostDetail />} />
              <Route path="/settings" element={<Settings />} />
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