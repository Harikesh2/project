import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, MessageCircle, MoreHorizontal, Edit, Trash2, Image as ImageIcon } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

import { PostWithUser } from '@/types';
import { usePostService } from '@/services/postService';
import { useUserService } from '@/services/userService';

import ImageUpload from './common/ImageUpload';

interface PostCardProps {
  post: PostWithUser;
}

export default function PostCard({ post }: PostCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(post.content);
  const [editedImageUrl, setEditedImageUrl] = useState(post.image_url || '');
  
  const { useToggleLike, useDeletePost, useUpdatePost } = usePostService();
  const { useCurrentUser } = useUserService();
  const { data: currentUser } = useCurrentUser();
  
  const toggleLike = useToggleLike();
  const deletePost = useDeletePost();
  const updatePost = useUpdatePost();

  const isOwner = currentUser?.user_id === post.user_id;

  const handleLike = () => {
    toggleLike.mutate(post.post_id);
  };

  const handleDelete = () => {
    if (window.confirm('Are you sure you want to delete this post?')) {
      deletePost.mutate(post.post_id);
    }
    setShowMenu(false);
  };

  const handleUpdate = () => {
    if (editedContent.trim() === '') return;
    updatePost.mutate(
      { 
        postId: post.post_id, 
        postData: { 
          content: editedContent.trim(),
          image_url: editedImageUrl.trim() || undefined
        } 
      },
      {
        onSuccess: () => {
          setIsEditing(false);
        },
      }
    );
  };

  const handleCancelEdit = () => {
    setEditedContent(post.content);
    setEditedImageUrl(post.image_url || '');
    setIsEditing(false);
  };

  return (
    <div className="card p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-3">
          <Link to={`/profile/${post.user.user_id}`}>
            <div className="avatar avatar-md">
              {post.user.avatar_url ? (
                <img
                  src={post.user.avatar_url}
                  alt={post.user.username}
                  className="w-full h-full object-cover rounded-full"
                />
              ) : (
                <span className="text-gray-600">
                  {post.user.username[0].toUpperCase()}
                </span>
              )}
            </div>
          </Link>
          <div>
            <Link
              to={`/profile/${post.user.user_id}`}
              className="font-medium text-gray-900 hover:text-primary-600"
            >
              {post.user.username}
            </Link>
            <p className="text-sm text-gray-500">
              {formatDistanceToNow(new Date(post.created_at), { addSuffix: true })}
            </p>
          </div>
        </div>

        {/* Menu */}
        {isOwner && !isEditing && (
          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-2 hover:bg-gray-100 rounded-full transition-colors"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
            
            {showMenu && (
              <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 z-10">
                <button
                  onClick={() => {
                    setIsEditing(true);
                    setEditedContent(post.content);
                    setEditedImageUrl(post.image_url || '');
                    setShowMenu(false);
                  }}
                  className="flex items-center space-x-2 w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                >
                  <Edit className="w-4 h-4" />
                  <span>Edit</span>
                </button>
                <button
                  onClick={handleDelete}
                  className="flex items-center space-x-2 w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Delete</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="mb-4">
        {isEditing ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Content</label>
              <textarea
                value={editedContent}
                onChange={(e) => setEditedContent(e.target.value)}
                className="input w-full min-h-[100px] py-2"
                placeholder="Edit your post..."
                autoFocus
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Update Photo
              </label>
              <ImageUpload 
                onUploadSuccess={(url) => setEditedImageUrl(url)}
                initialImageUrl={editedImageUrl}
              />
            </div>

            <div className="flex justify-end space-x-2 pt-2">
              <button
                onClick={handleCancelEdit}
                className="btn btn-secondary text-sm px-3 py-1.5"
                disabled={updatePost.isPending}
              >
                Cancel
              </button>
              <button
                onClick={handleUpdate}
                className="btn btn-primary text-sm px-3 py-1.5"
                disabled={updatePost.isPending || (editedContent.trim() === post.content && editedImageUrl === (post.image_url || ''))}
              >
                {updatePost.isPending ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        ) : (
          <>
            <p className="text-gray-900 whitespace-pre-wrap">{post.content}</p>
            
            {post.image_url && (
              <div className="mt-3">
                <img
                  src={post.image_url}
                  alt="Post image"
                  className="w-full max-h-96 object-cover rounded-lg"
                />
              </div>
            )}
          </>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
        <div className="flex items-center space-x-6">
          <button
            onClick={handleLike}
            className={`flex items-center space-x-2 transition-colors ${
              post.is_liked
                ? 'text-red-600 hover:text-red-700'
                : 'text-gray-600 hover:text-red-600'
            }`}
          >
            <Heart
              className={`w-5 h-5 ${post.is_liked ? 'fill-current' : ''}`}
            />
            <span className="text-sm font-medium">{post.likes_count}</span>
          </button>
          
          <Link
            to={`/post/${post.post_id}`}
            className="flex items-center space-x-2 text-gray-600 hover:text-primary-600 transition-colors"
          >
            <MessageCircle className="w-5 h-5" />
            <span className="text-sm font-medium">{post.comments_count}</span>
          </Link>
        </div>
      </div>

      {/* Click overlay to close menu */}
      {showMenu && (
        <div
          className="fixed inset-0 z-5"
          onClick={() => setShowMenu(false)}
        />
      )}
    </div>
  );
}