import { useUserService } from '@/services/userService';

import AvatarUpload from '@/components/common/AvatarUpload';
import { Camera, Mail, Save, User as UserIcon } from 'lucide-react';

export default function Settings() {
  const { useCurrentUser, useUpdateProfile } = useUserService();
  const { data: currentUser, isLoading } = useCurrentUser();
  const updateProfile = useUpdateProfile();

  const [formData, setFormData] = useState({
    username: currentUser?.username || '',
    bio: currentUser?.bio || '',
  });

  // Update form data when user data loads
  useState(() => {
    if (currentUser) {
      setFormData({
        username: currentUser.username,
        bio: currentUser.bio || '',
      });
    }
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      await updateProfile.mutateAsync({
        username: formData.username.trim(),
        bio: formData.bio.trim() || undefined,
      });
    } catch (error) {
      // Error is handled by the mutation
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="card p-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-600 mt-2">
            Manage your account settings and profile information
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Email (read-only) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Mail className="w-4 h-4 inline mr-1" />
              Email
            </label>
            <input
              type="email"
              value={currentUser?.email || ''}
              disabled
              className="input bg-gray-50 text-gray-500"
            />
            <p className="text-sm text-gray-500 mt-1">
              Email cannot be changed. Contact support if you need to update your email.
            </p>
          </div>

          {/* Username */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <UserIcon className="w-4 h-4 inline mr-1" />
              Username *
            </label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="Enter your username"
              className="input"
              required
              minLength={3}
              maxLength={30}
              pattern="^[a-zA-Z0-9_]+$"
              title="Username can only contain letters, numbers, and underscores"
            />
          </div>

          {/* Bio */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Bio
            </label>
            <textarea
              name="bio"
              value={formData.bio}
              onChange={handleChange}
              placeholder="Tell us about yourself..."
              className="textarea"
              rows={4}
              maxLength={500}
            />
            <div className="text-right text-sm text-gray-500 mt-1">
              {formData.bio.length}/500
            </div>
          </div>

          {/* Avatar Upload */}
          <div className="bg-gray-50 rounded-xl p-6 border border-gray-100">
            <label className="block text-sm font-medium text-gray-700 mb-4 text-center">
              Profile Picture
            </label>
            <AvatarUpload 
              currentAvatarUrl={currentUser?.avatar_url}
            />
          </div>

          {/* Submit Button */}

          {/* Submit Button */}
          <div className="flex justify-end pt-6 border-t border-gray-200">
            <button
              type="submit"
              disabled={updateProfile.isPending}
              className="btn btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save className="w-4 h-4" />
              <span>{updateProfile.isPending ? 'Saving...' : 'Save Changes'}</span>
            </button>
          </div>
        </form>

        {/* Account Stats */}
        <div className="mt-8 pt-8 border-t border-gray-200">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Account Statistics</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-primary-600">{currentUser?.posts_count || 0}</div>
              <div className="text-sm text-gray-600">Posts</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-primary-600">{currentUser?.followers_count || 0}</div>
              <div className="text-sm text-gray-600">Followers</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-primary-600">{currentUser?.following_count || 0}</div>
              <div className="text-sm text-gray-600">Following</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}