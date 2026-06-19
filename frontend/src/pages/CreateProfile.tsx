import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '@clerk/clerk-react';
import { User, Mail } from 'lucide-react';

import { useUserService } from '@/services/userService';

export default function CreateProfile() {
  const navigate = useNavigate();
  const { user: clerkUser } = useUser();
  const { useCreateProfile } = useUserService();
  const createProfile = useCreateProfile();

  const [formData, setFormData] = useState({
    username: '',
    bio: '',
    avatar_url: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!clerkUser?.primaryEmailAddress?.emailAddress) {
      return;
    }

    try {
      await createProfile.mutateAsync({
        username: formData.username.trim(),
        email: clerkUser.primaryEmailAddress.emailAddress,
        bio: formData.bio.trim() || undefined,
        avatar_url: formData.avatar_url.trim() || undefined,
      });
      
      navigate('/');
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

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <div className="w-16 h-16 bg-primary-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-2xl">S</span>
          </div>
          <h2 className="text-3xl font-bold text-gray-900">Create Your Profile</h2>
          <p className="mt-2 text-gray-600">
            Let's set up your profile to get started
          </p>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-6">
          <div className="space-y-4">
            {/* Email (read-only) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <Mail className="w-4 h-4 inline mr-1" />
                Email
              </label>
              <input
                type="email"
                value={clerkUser?.primaryEmailAddress?.emailAddress || ''}
                disabled
                className="input bg-gray-50 text-gray-500"
              />
            </div>

            {/* Username */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <User className="w-4 h-4 inline mr-1" />
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
                Bio (optional)
              </label>
              <textarea
                name="bio"
                value={formData.bio}
                onChange={handleChange}
                placeholder="Tell us about yourself..."
                className="textarea"
                rows={3}
                maxLength={500}
              />
              <div className="text-right text-sm text-gray-500 mt-1">
                {formData.bio.length}/500
              </div>
            </div>

            {/* Avatar URL */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Avatar URL (optional)
              </label>
              <input
                type="url"
                name="avatar_url"
                value={formData.avatar_url}
                onChange={handleChange}
                placeholder="https://example.com/avatar.jpg"
                className="input"
              />
            </div>

            {/* Avatar Preview */}
            {formData.avatar_url && (
              <div className="flex justify-center">
                <div className="avatar avatar-xl">
                  <img
                    src={formData.avatar_url}
                    alt="Avatar preview"
                    className="w-full h-full object-cover rounded-full"
                    onError={() => setFormData(prev => ({ ...prev, avatar_url: '' }))}
                  />
                </div>
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={!formData.username.trim() || createProfile.isPending}
            className="w-full btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {createProfile.isPending ? 'Creating Profile...' : 'Create Profile'}
          </button>
        </form>
      </div>
    </div>
  );
}