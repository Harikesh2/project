import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, MessageCircle, MoreHorizontal, Edit, Trash2 } from 'lucide-react';
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
  const [imageError, setImageError] = useState(false);
  
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

  const isEditDirty = editedContent.trim() !== post.content || editedImageUrl.trim() !== (post.image_url || '');

  const handleUpdate = () => {
    if (editedContent.trim() === '') return;
    if (!isEditDirty) return;
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
    <div className="card p-6 transition-colors duration-200">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-3">
          <Link to={`/profile/${post.user.user_id}`}>
            <div className="avatar avatar-md border border-gray-250 dark:border-slate-800">
              {post.user.avatar_url ? (
                <img
                  src={post.user.avatar_url}
                  alt={post.user.username}
                  className="w-full h-full object-cover rounded-full"
                />
              ) : (
                <span className="text-gray-600 dark:text-slate-400">
                  {post.user.username[0].toUpperCase()}
                </span>
              )}
            </div>
          </Link>
          <div>
            <Link
              to={`/profile/${post.user.user_id}`}
              className="font-medium text-gray-900 dark:text-white hover:text-primary-600 dark:hover:text-primary-400"
            >
              {post.user.username}
            </Link>
            <p className="text-sm text-gray-500 dark:text-slate-500">
              {formatDistanceToNow(new Date(post.created_at), { addSuffix: true })}
            </p>
          </div>
        </div>
 
        {/* Menu */}
        {isOwner && !isEditing && (
          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-2 hover:bg-gray-100 dark:hover:bg-slate-800 rounded-full transition-colors text-gray-650 dark:text-slate-400"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
            
            {showMenu && (
              <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-slate-900 rounded-lg shadow-lg border border-gray-200 dark:border-slate-800 z-10">
                <button
                  onClick={() => {
                    setIsEditing(true);
                    setEditedContent(post.content);
                    setEditedImageUrl(post.image_url || '');
                    setShowMenu(false);
                  }}
                  className="flex items-center space-x-2 w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800"
                >
                  <Edit className="w-4 h-4" />
                  <span>Edit</span>
                </button>
                <button
                  onClick={handleDelete}
                  className="flex items-center space-x-2 w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20"
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
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-350 mb-1">Content</label>
              <textarea
                value={editedContent}
                onChange={(e) => setEditedContent(e.target.value)}
                className="input w-full min-h-[100px] py-2"
                placeholder="Edit your post..."
                autoFocus
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-350 mb-2">
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
                disabled={updatePost.isPending || !isEditDirty}
              >
                {updatePost.isPending ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        ) : (
          <>
            <p className="text-gray-900 dark:text-slate-100 whitespace-pre-wrap">{post.content}</p>
            
            {post.image_url && (
              <div className="mt-3 w-full min-h-[200px] aspect-video rounded-lg bg-gray-100 dark:bg-slate-800 flex flex-col items-center justify-center border border-gray-200 dark:border-slate-800 overflow-hidden">
                {imageError ? (
                  <div className="flex flex-col items-center justify-center p-4 text-center">
                    <svg className="w-12 h-12 text-gray-400 dark:text-slate-600 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <span className="text-sm font-medium text-gray-500 dark:text-slate-400">Image not available</span>
                  </div>
                ) : (
                  <img
                    src={post.image_url}
                    alt="Post image"
                    className="w-full h-full object-cover"
                    onError={() => setImageError(true)}
                  />
                )}
              </div>
            )}
          </>
        )}
      </div>
 
      {/* Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-100 dark:border-slate-800">
        <div className="flex items-center space-x-6">
          <button
            onClick={handleLike}
            className={`flex items-center space-x-2 transition-colors ${
              post.is_liked
                ? 'text-red-650 hover:text-red-700'
                : 'text-gray-600 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-400'
            }`}
          >
            <Heart
              className={`w-5 h-5 ${post.is_liked ? 'fill-current' : ''}`}
            />
            <span className="text-sm font-medium">{post.likes_count}</span>
          </button>
          
          <Link
            to={`/post/${post.post_id}`}
            className="flex items-center space-x-2 text-gray-600 dark:text-slate-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
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