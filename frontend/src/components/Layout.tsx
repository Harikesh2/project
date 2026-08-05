import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, Search, Settings, Bell, PlusCircle, LogOut, MessageCircle, User } from 'lucide-react';
import { useClerk } from '@clerk/clerk-react';

import { useUserService } from '@/services/userService';
import { useNotificationService, useNotificationWs } from '@/services/notificationService';
import { useChatService, useChatWs } from '@/services/chatService';
import CreatePostModal from './CreatePostModal';
import ConfirmationModal from '@/components/common/ConfirmationModal';
import { useState, useRef, useEffect } from 'react';

interface LayoutProps {
  children: ReactNode;
  onLogout?: () => void;
}

export default function Layout({ children, onLogout }: LayoutProps) {
  const { signOut } = useClerk();
  const location = useLocation();
  const { useCurrentUser } = useUserService();
  const { data: currentUser } = useCurrentUser();
  const { useUnreadCount } = useNotificationService();
  const { data: unreadCount } = useUnreadCount();
  useNotificationWs();
  const { useChatUnreadCount } = useChatService();
  const { data: chatUnreadCount } = useChatUnreadCount();
  const [showCreatePost, setShowCreatePost] = useState(false);
  const [isAvatarMenuOpen, setIsAvatarMenuOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const avatarButtonRef = useRef<HTMLButtonElement>(null);

  // Close the avatar menu whenever the route changes
  useEffect(() => {
    setIsAvatarMenuOpen(false);
  }, [location.pathname]);

  // Close on Escape and return focus to the trigger button
  useEffect(() => {
    if (!isAvatarMenuOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsAvatarMenuOpen(false);
        avatarButtonRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isAvatarMenuOpen]);

  const handleLogout = onLogout
    ? () => {
        setIsAvatarMenuOpen(false);
        onLogout();
      }
    : () => {
        setIsAvatarMenuOpen(false);
        signOut();
      };

  // Get demo user if no current user
  const user = currentUser || JSON.parse(localStorage.getItem('demo_user') || '{}');

  useChatWs(user?.user_id);

  const navigation = [
    { name: 'Home', href: '/', icon: Home },
    { name: 'Search', href: '/search', icon: Search },
    { name: 'Chat', href: '/chats', icon: MessageCircle },
    { name: 'Notifications', href: '/notifications', icon: Bell },
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
                    <span className="relative">
                      <Icon className="w-4 h-4" />
                      {item.name === 'Notifications' && !isActive('/notifications') && (unreadCount?.count ?? 0) > 0 && (
                        <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[11px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 leading-none shadow-sm ring-2 ring-white dark:ring-slate-900">
                          {(unreadCount?.count ?? 0) > 9 ? '9+' : (unreadCount?.count ?? 0)}
                        </span>
                      )}
                      {item.name === 'Chat' && !isActive('/chats') && (chatUnreadCount?.count ?? 0) > 0 && (
                        <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[11px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 leading-none shadow-sm ring-2 ring-white dark:ring-slate-900">
                          {(chatUnreadCount?.count ?? 0) > 9 ? '9+' : (chatUnreadCount?.count ?? 0)}
                        </span>
                      )}
                    </span>
                    <span className="ml-1.5">{item.name}</span>
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
              <div className="relative flex items-center space-x-3">
                <button
                  ref={avatarButtonRef}
                  type="button"
                  onClick={() => setIsAvatarMenuOpen((v) => !v)}
                  aria-haspopup="menu"
                  aria-expanded={isAvatarMenuOpen}
                  aria-label="Open user menu"
                  className="avatar avatar-sm border border-gray-200 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded-full"
                >
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
                </button>

                {isAvatarMenuOpen && (
                  <>
                    {/* Sibling fixed overlay closes the menu on outside click (PostCard pattern) */}
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setIsAvatarMenuOpen(false)}
                    />
                    <div
                      role="menu"
                      aria-label="User menu"
                      className="absolute right-0 top-full mt-2 w-48 bg-white dark:bg-slate-900 rounded-lg shadow-lg border border-gray-200 dark:border-slate-800 z-50"
                    >
                      <Link
                        to={`/profile/${user?.user_id}`}
                        role="menuitem"
                        className="flex items-center space-x-2 w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 rounded-t-lg"
                      >
                        <User className="w-4 h-4" />
                        <span>View Profile</span>
                      </Link>
                      <Link
                        to="/settings"
                        role="menuitem"
                        className="flex items-center space-x-2 w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800"
                      >
                        <Settings className="w-4 h-4" />
                        <span>Account Settings</span>
                      </Link>
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setIsAvatarMenuOpen(false);
                          setShowLogoutConfirm(true);
                        }}
                        className="flex items-center space-x-2 w-full px-4 py-2 text-left text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 rounded-b-lg"
                      >
                        <LogOut className="w-4 h-4" />
                        <span>Log Out</span>
                      </button>
                    </div>
                  </>
                )}
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
                    <span className="relative">
                      <Icon className="w-5 h-5" />
                      {item.name === 'Notifications' && !isActive('/notifications') && (unreadCount?.count ?? 0) > 0 && (
                        <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[11px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 leading-none shadow-sm ring-2 ring-white dark:ring-slate-900">
                          {(unreadCount?.count ?? 0) > 9 ? '9+' : (unreadCount?.count ?? 0)}
                        </span>
                      )}
                      {item.name === 'Chat' && !isActive('/chats') && (chatUnreadCount?.count ?? 0) > 0 && (
                        <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[11px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 leading-none shadow-sm ring-2 ring-white dark:ring-slate-900">
                          {(chatUnreadCount?.count ?? 0) > 9 ? '9+' : (chatUnreadCount?.count ?? 0)}
                        </span>
                      )}
                    </span>
                    <span className="mt-0.5">{item.name}</span>
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

      {/* Log Out Confirmation */}
      <ConfirmationModal
        isOpen={showLogoutConfirm}
        icon="👋"
        title="Log out?"
        description="You'll need to sign back in to view your feed, posts, and messages."
        primaryAction="Log Out"
        secondaryAction="Cancel"
        primaryClassName="bg-red-500 hover:bg-red-400 text-white shadow-lg shadow-red-500/25 hover:shadow-red-500/40"
        onConfirm={() => {
          setShowLogoutConfirm(false);
          handleLogout();
        }}
        onCancel={() => setShowLogoutConfirm(false)}
      />
    </div>
  );
}