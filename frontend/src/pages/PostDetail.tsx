import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, MessageCircle, Send, Trash2 } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

import { usePostService } from '@/services/postService';
import { useUserService } from '@/services/userService';
import PostCard from '@/components/PostCard';

export default function PostDetail() {
  const { postId } = useParams<{ postId: string }>();
  const [commentContent, setCommentContent] = useState('');
  
  const { usePost, usePostComments, useCreateComment, useDeleteComment } = usePostService();
  const { useCurrentUser } = useUserService();
  
  const { data: post, isLoading: postLoading } = usePost(postId!);
  const { data: comments, isLoading: commentsLoading } = usePostComments(postId!);
  const { data: currentUser } = useCurrentUser();
  
  const createComment = useCreateComment();
  const deleteComment = useDeleteComment();

  const handleSubmitComment = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!commentContent.trim() || !postId) return;

    try {
      await createComment.mutateAsync({
        postId,
        commentData: { content: commentContent.trim() }
      });
      setCommentContent('');
    } catch (error) {
      // Error is handled by the mutation
    }
  };

  const handleDeleteComment = (commentId: string) => {
    if (!postId) return;
    
    if (window.confirm('Are you sure you want to delete this comment?')) {
      deleteComment.mutate({ postId, commentId });
    }
  };

  if (postLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (!post) {
    return (
      <div className="text-center py-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Post Not Found</h2>
        <p className="text-gray-600 dark:text-slate-400">The post you're looking for doesn't exist.</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Post */}
      <PostCard post={post} />

      {/* Comments Section */}
      <div className="card p-6 transition-colors duration-200">
        <div className="flex items-center space-x-2 mb-6">
          <MessageCircle className="w-5 h-5 text-gray-600 dark:text-slate-400" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Comments ({comments?.length || 0})
          </h2>
        </div>

        {/* Add Comment Form */}
        <form onSubmit={handleSubmitComment} className="mb-6">
          <div className="flex space-x-3">
            <div className="avatar avatar-md border border-gray-200 dark:border-slate-800">
              {currentUser?.avatar_url ? (
                <img
                  src={currentUser.avatar_url}
                  alt={currentUser.username}
                  className="w-full h-full object-cover rounded-full"
                />
              ) : (
                <span className="text-gray-600 dark:text-slate-400">
                  {currentUser?.username?.[0]?.toUpperCase() || 'U'}
                </span>
              )}
            </div>
            <div className="flex-1">
              <textarea
                value={commentContent}
                onChange={(e) => setCommentContent(e.target.value)}
                placeholder="Write a comment..."
                className="textarea min-h-[80px]"
                maxLength={1000}
              />
              <div className="flex justify-between items-center mt-2">
                <span className="text-sm text-gray-500 dark:text-slate-400">
                  {commentContent.length}/1000
                </span>
                <button
                  type="submit"
                  disabled={!commentContent.trim() || createComment.isPending}
                  className="btn btn-primary btn-sm flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />
                  <span>{createComment.isPending ? 'Posting...' : 'Comment'}</span>
                </button>
              </div>
            </div>
          </div>
        </form>

        {/* Comments List */}
        {commentsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-primary-600" />
          </div>
        ) : comments && comments.length > 0 ? (
          <div className="space-y-4">
            {comments.map((comment) => (
              <div key={comment.comment_id} className="flex space-x-3">
                <Link to={`/profile/${comment.user.user_id}`}>
                  <div className="avatar avatar-md border border-gray-205 dark:border-slate-850">
                    {comment.user.avatar_url ? (
                      <img
                        src={comment.user.avatar_url}
                        alt={comment.user.username}
                        className="w-full h-full object-cover rounded-full"
                      />
                    ) : (
                      <span className="text-gray-600 dark:text-slate-400">
                        {comment.user.username[0].toUpperCase()}
                      </span>
                    )}
                  </div>
                </Link>
                <div className="flex-1">
                  <div className="bg-gray-50 dark:bg-slate-800/40 rounded-lg p-3 transition-colors duration-200">
                    <div className="flex items-center justify-between mb-1">
                      <Link
                        to={`/profile/${comment.user.user_id}`}
                        className="font-medium text-gray-900 dark:text-white hover:text-primary-600 dark:hover:text-primary-400 text-sm"
                      >
                        {comment.user.username}
                      </Link>
                      {currentUser?.user_id === comment.user_id && (
                        <button
                          onClick={() => handleDeleteComment(comment.comment_id)}
                          className="text-red-600 hover:text-red-750 p-1"
                          title="Delete comment"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    <p className="text-gray-900 dark:text-slate-100 text-sm whitespace-pre-wrap">
                      {comment.content}
                    </p>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-slate-500 mt-1 ml-3">
                    {formatDistanceToNow(new Date(comment.created_at), { addSuffix: true })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <MessageCircle className="w-8 h-8 text-gray-400 dark:text-slate-650 mx-auto mb-2" />
            <p className="text-gray-600 dark:text-slate-400">No comments yet. Be the first to comment!</p>
          </div>
        )}
      </div>
    </div>
  );
}