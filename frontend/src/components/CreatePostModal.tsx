import { useState } from 'react';
import { X } from 'lucide-react';
import { usePostService } from '@/services/postService';
import { useUserService } from '@/services/userService';
import ImageUpload from './common/ImageUpload';

interface CreatePostModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function CreatePostModal({ isOpen, onClose }: CreatePostModalProps) {
  const [content, setContent] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const { useCreatePost } = usePostService();
  const { useCurrentUser } = useUserService();
  const { data: currentUser } = useCurrentUser();
  const createPost = useCreatePost();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!content.trim()) return;

    try {
      await createPost.mutateAsync({
        content: content.trim(),
        image_url: imageUrl.trim() || undefined,
      });
      
      setContent('');
      setImageUrl('');
      onClose();
    } catch (error) {
      // Error is handled by the mutation
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-lg w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Create Post</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* User Info */}
          <div className="flex items-center space-x-3">
            <div className="avatar avatar-md">
              {currentUser?.avatar_url ? (
                <img
                  src={currentUser.avatar_url}
                  alt={currentUser.username}
                  className="w-full h-full object-cover rounded-full"
                />
              ) : (
                <span className="text-gray-600">
                  {currentUser?.username?.[0]?.toUpperCase() || 'U'}
                </span>
              )}
            </div>
            <div>
              <p className="font-medium text-gray-900">{currentUser?.username}</p>
            </div>
          </div>

          {/* Content */}
          <div>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="What's on your mind?"
              className="textarea min-h-[120px]"
              maxLength={2000}
              required
            />
            <div className="text-right text-sm text-gray-500 mt-1">
              {content.length}/2000
            </div>
          </div>

          {/* Image Upload */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Add Photo
            </label>
            <ImageUpload 
              onUploadSuccess={(url) => setImageUrl(url)}
              initialImageUrl={imageUrl}
            />
          </div>

          {/* Actions */}

          {/* Actions */}
          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!content.trim() || createPost.isPending}
              className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createPost.isPending ? 'Posting...' : 'Post'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}