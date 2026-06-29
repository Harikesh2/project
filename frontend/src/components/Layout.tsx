import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, Search, User, Settings, PlusCircle, LogOut } from 'lucide-react';

import { useUserService } from '@/services/userService';
import CreatePostModal from './CreatePostModal';
import { useState } from 'react';

interface LayoutProps {
  children: ReactNode;
  onLogout: () => void;
}

export default function Layout({ children, onLogout }: LayoutProps) {
  const location = useLocation();
  const { useCurrentUser } = useUserService();
  const { data: currentUser } = useCurrentUser();
  const [showCreatePost, setShowCreatePost] = useState(false);

  // Get demo user if no current user
  const user = currentUser || JSON.parse(localStorage.getItem('demo_user') || '{}');

  const navigation = [
    { name: 'Home', href: '/', icon: Home },
    { name: 'Search', href: '/search', icon: Search },
    { name: 'Profile', href: `/profile/${user?.user_id}`, icon: User },
    { name: 'Settings', href: '/settings', icon: Settings },
  ];

  const isActive = (href: string) => {
    if (href === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(href);
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950 transition-colors duration-200">
      {/* Header */}
      <header className="bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-slate-800 sticky top-0 z-40 transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-lg">S</span>
              </div>
              <span className="text-xl font-bold text-gray-900 dark:text-white">Social</span>
              <span className="text-sm bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-300 px-2 py-1 rounded-full">DEMO</span>
            </Link>
 
            {/* Navigation */}
            <nav className="hidden md:flex space-x-8">
              {navigation.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={`flex items-center space-x-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive(item.href)
                        ? 'text-primary-600 dark:text-primary-400 bg-primary-50 dark:bg-primary-950/50'
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{item.name}</span>
                  </Link>
                );
              })}
            </nav>
 
            {/* Actions */}
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setShowCreatePost(true)}
                className="btn btn-primary flex items-center space-x-2"
              >
                <PlusCircle className="w-4 h-4" />
                <span className="hidden sm:inline">Post</span>
              </button>
              
              {/* Demo User Menu */}
              <div className="flex items-center space-x-3">
                <div className="avatar avatar-sm border border-gray-200 dark:border-slate-700">
                  {user?.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt={user.username}
                      className="w-full h-full object-cover rounded-full"
                    />
                  ) : (
                    <span className="text-gray-600 dark:text-gray-400">
                      {user?.username?.[0]?.toUpperCase() || 'D'}
                    </span>
                  )}
                </div>
                <button
                  onClick={onLogout}
                  className="text-gray-600 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                  title="Logout"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>
 
      {/* Mobile Navigation */}
      <nav className="md:hidden bg-white dark:bg-slate-900 border-t border-gray-200 dark:border-slate-800 fixed bottom-0 left-0 right-0 z-40 transition-colors duration-200">
        <div className="flex justify-around py-2">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex flex-col items-center space-y-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  isActive(item.href)
                    ? 'text-primary-600 dark:text-primary-400'
                    : 'text-gray-600 dark:text-gray-450 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </div>
      </nav>
 
      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-20 md:pb-8">
        {children}
      </main>
 
      {/* Create Post Modal */}
      {showCreatePost && (
        <CreatePostModal
          isOpen={showCreatePost}
          onClose={() => setShowCreatePost(false)}
        />
      )}
    </div>
  );
}