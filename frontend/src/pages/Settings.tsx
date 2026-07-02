import { useState, useEffect, useRef } from 'react';
import { useDirtyForm } from '@/hooks/useDirtyForm';
import { useUserService } from '@/services/userService';

import AvatarUpload from '@/components/common/AvatarUpload';
import ConfirmationModal from '@/components/common/ConfirmationModal';
import { Mail, Save, User as UserIcon, Sun, Moon } from 'lucide-react';

type ModalStep = 'none' | 'confirm' | 'bold';

export default function Settings() {
  const { useCurrentUser, useUpdateProfile } = useUserService();
  const { data: currentUser, isLoading } = useCurrentUser();
  const updateProfile = useUpdateProfile();

  const { formData, isDirty, resetOriginal, handleChange } = useDirtyForm({
    username: '',
    bio: '',
  });

  const [theme, setThemeState] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('theme');
    return saved === 'light' ? 'light' : 'dark';
  });

  // Modal two-step state machine: none → confirm → bold → apply
  const [modalStep, setModalStep] = useState<ModalStep>('none');
  const lightBtnRef = useRef<HTMLButtonElement>(null);

  // Apply theme to DOM and localStorage
  const applyTheme = (newTheme: 'dark' | 'light') => {
    setThemeState(newTheme);
    localStorage.setItem('theme', newTheme);
    if (newTheme === 'light') {
      document.documentElement.classList.remove('dark');
    } else {
      document.documentElement.classList.add('dark');
    }
  };

  // Sync state changes with the DOM element and localStorage
  const handleThemeChange = (newTheme: 'dark' | 'light') => {
    if (newTheme === 'light') {
      setModalStep('confirm');
      return;
    }
    applyTheme(newTheme);
  };

  const handleModalCancel = () => {
    setModalStep('none');
  };

  const handleModalConfirm = () => {
    if (modalStep === 'confirm') {
      // Move to step 2
      setModalStep('bold');
    } else if (modalStep === 'bold') {
      // Apply light mode and close
      setModalStep('none');
      applyTheme('light');
    }
  };

  // Bug 4 Fix: Use useEffect (not useState) to sync form when user data loads
  useEffect(() => {
    if (currentUser) {
      const values = {
        username: currentUser.username,
        bio: currentUser.bio || '',
      };
      resetOriginal(values);
    }
  }, [currentUser]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Guard: do nothing if the form hasn't changed
    if (!isDirty) return;
    
    try {
      await updateProfile.mutateAsync({
        username: formData.username.trim(),
        bio: formData.bio.trim() || undefined,
      });
      // Reset baseline so button disables again after a successful save
      resetOriginal();
    } catch (error) {
      // Error is handled by the mutation
    }
  };

  // handleChange is provided by useDirtyForm

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="card shadow-lg overflow-hidden transition-colors duration-200">
        {/* Main Content Form */}
        <div className="p-8">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h1>
            <p className="text-gray-600 dark:text-gray-455 mt-2">
              Manage your account settings and profile information
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Theme Controller */}
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-2xl p-6 border border-slate-100 dark:border-slate-800 transition-colors duration-200">
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                App Theme
              </label>
              <div className="grid grid-cols-2 gap-4">
                <button
                  type="button"
                  onClick={() => handleThemeChange('dark')}
                  className={`flex items-center justify-center space-x-2 p-3 rounded-xl border font-medium transition-all ${
                    theme === 'dark'
                      ? 'bg-slate-900 text-white border-slate-900 dark:bg-slate-800 dark:border-slate-700 dark:text-white shadow-sm'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50 dark:bg-slate-900 dark:text-slate-300 dark:border-slate-800'
                  }`}
                >
                  <Moon className="w-4 h-4" />
                  <span>Dark Mode</span>
                </button>
                <button
                  ref={lightBtnRef}
                  type="button"
                  onClick={() => handleThemeChange('light')}
                  className={`flex items-center justify-center space-x-2 p-3 rounded-xl border font-medium transition-all ${
                    theme === 'light'
                      ? 'bg-primary-600 text-white border-primary-600 shadow-sm'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50 dark:bg-slate-900 dark:text-slate-300 dark:border-slate-800'
                  }`}
                >
                  <Sun className="w-4 h-4" />
                  <span>Light Mode</span>
                </button>
              </div>
            </div>

            {/* Email (read-only) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Mail className="w-4 h-4 inline mr-1" />
                Email
              </label>
              <input
                type="email"
                value={currentUser?.email || ''}
                readOnly
                className="input bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-800 focus:ring-0 focus:border-slate-200"
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Email cannot be changed. Contact support if you need to update your email.
              </p>
            </div>

            {/* Username */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <UserIcon className="w-4 h-4 inline mr-1" />
                Username *
              </label>
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleChange}
                placeholder="Enter your username"
                className="input focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                required
                minLength={3}
                maxLength={30}
                pattern="^[a-zA-Z0-9_]+$"
                title="Username can only contain letters, numbers, and underscores"
              />
            </div>

            {/* Bio */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Bio
              </label>
              <textarea
                name="bio"
                value={formData.bio}
                onChange={handleChange}
                placeholder="Tell us about yourself..."
                className="textarea focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                rows={4}
                maxLength={500}
              />
              <div className="text-right text-sm text-gray-500 dark:text-gray-400 mt-1">
                {formData.bio.length}/500
              </div>
            </div>

            {/* Avatar Upload */}
            <div className="bg-slate-50 dark:bg-slate-800/40 rounded-2xl p-6 border border-slate-100 dark:border-slate-800 transition-colors duration-200">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-4 text-center">
                Profile Picture
              </label>
              <AvatarUpload 
                currentAvatarUrl={currentUser?.avatar_url}
              />
            </div>

            {/* Submit Button */}
            <div className="flex justify-end pt-6 border-t border-gray-200 dark:border-slate-800">
              <button
                type="submit"
                disabled={!isDirty || updateProfile.isPending}
                className="btn btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Save className="w-4 h-4" />
                <span>{updateProfile.isPending ? 'Saving...' : 'Save Changes'}</span>
              </button>
            </div>
          </form>
        </div>

        {/* Account Stats Footer Block */}
        <div className="bg-slate-50 dark:bg-slate-800/30 p-8 border-t border-slate-100 dark:border-slate-800/60 transition-colors duration-200">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">Account Statistics</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl p-4 shadow-sm transition-colors duration-200">
              <div className="text-2xl font-bold text-primary-600 dark:text-primary-400">{currentUser?.posts_count || 0}</div>
              <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">Posts</div>
            </div>
            <div className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl p-4 shadow-sm transition-colors duration-200">
              <div className="text-2xl font-bold text-primary-600 dark:text-primary-400">{currentUser?.followers_count || 0}</div>
              <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">Followers</div>
            </div>
            <div className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl p-4 shadow-sm transition-colors duration-200">
              <div className="text-2xl font-bold text-primary-600 dark:text-primary-400">{currentUser?.following_count || 0}</div>
              <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">Following</div>
            </div>
          </div>
        </div>
      </div>

      {/* Step 1: Confirmation Modal */}
      <ConfirmationModal
        isOpen={modalStep === 'confirm'}
        icon="🤔"
        title="Switch to Light Mode?"
        description={
          'Ah yes, violence against your eyes.\nLight mode is bright, bold, and your battery may never forgive you.\n\nAre you absolutely sure you want to continue?'
        }
        primaryAction="Yes, I'm Sure"
        secondaryAction="Cancel"
        onConfirm={handleModalConfirm}
        onCancel={handleModalCancel}
      />

      {/* Step 2: Bold Choice Modal */}
      <ConfirmationModal
        isOpen={modalStep === 'bold'}
        icon="😅"
        title="Bold Choice"
        description={
          'Your battery is officially judging you.\n\nHopefully your eyes survive the experience.'
        }
        primaryAction="Continue"
        onConfirm={handleModalConfirm}
        onCancel={handleModalCancel}
        primaryClassName="bg-blue-500 hover:bg-blue-400 text-white shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40"
      />
    </div>
  );
}