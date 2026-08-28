import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from './api';
import { Post, PostWithUser, PostCreate, PostUpdate, CommentWithUser, CommentCreate } from '@/types';
import toast from 'react-hot-toast';

export const usePostService = () => {
  const api = useApi();
  const queryClient = useQueryClient();

  // Create post
  const useCreatePost = () => {
    return useMutation({
      mutationFn: async (postData: PostCreate): Promise<Post> => {
        const response = await api.post('/posts', postData);
        return response.data;
      },
      onSuccess: () => {
        // Invalidate feed and user posts
        queryClient.invalidateQueries({ queryKey: ['posts', 'feed'] });
        queryClient.invalidateQueries({ queryKey: ['posts', 'user'] });
        queryClient.invalidateQueries({ queryKey: ['user', 'me'] });
        toast.success('Post created successfully!');
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to create post');
      },
    });
  };

  // Get feed
  const useFeed = () => {
    return useQuery({
      queryKey: ['posts', 'feed'],
      queryFn: async (): Promise<PostWithUser[]> => {
        const response = await api.get('/posts/feed');
        return response.data;
      },
    });
  };

  // Get user posts
  const useUserPosts = (userId: string) => {
    return useQuery({
      queryKey: ['posts', 'user', userId],
      queryFn: async (): Promise<PostWithUser[]> => {
        const response = await api.get(`/posts/user/${userId}`);
        return response.data;
      },
      enabled: !!userId && userId !== 'undefined',
    });
  };

  // Get single post
  const usePost = (postId: string) => {
    return useQuery({
      queryKey: ['posts', postId],
      queryFn: async (): Promise<PostWithUser> => {
        const response = await api.get(`/posts/${postId}`);
        return response.data;
      },
      enabled: !!postId && postId !== 'undefined',
    });
  };

  // Update post
  const useUpdatePost = () => {
    return useMutation({
      mutationFn: async ({ postId, postData }: { postId: string; postData: PostUpdate }): Promise<Post> => {
        const response = await api.put(`/posts/${postId}`, postData);
        return response.data;
      },
      onSuccess: (data) => {
        // Invalidate relevant queries
        queryClient.invalidateQueries({ queryKey: ['posts', data.post_id] });
        queryClient.invalidateQueries({ queryKey: ['posts', 'feed'] });
        queryClient.invalidateQueries({ queryKey: ['posts', 'user'] });
        toast.success('Post updated successfully!');
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to update post');
      },
    });
  };

  // Delete post
  const useDeletePost = () => {
    return useMutation({
      mutationFn: async (postId: string): Promise<void> => {
        await api.delete(`/posts/${postId}`);
      },
      onSuccess: () => {
        // Invalidate relevant queries
        queryClient.invalidateQueries({ queryKey: ['posts', 'feed'] });
        queryClient.invalidateQueries({ queryKey: ['posts', 'user'] });
        queryClient.invalidateQueries({ queryKey: ['user', 'me'] });
        toast.success('Post deleted successfully!');
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to delete post');
      },
    });
  };

  // Toggle like post
  const useToggleLike = () => {
    return useMutation({
      mutationFn: async (postId: string): Promise<{ liked: boolean; success: boolean }> => {
        const response = await api.post(`/posts/${postId}/like`);
        return response.data;
      },
      onMutate: async (postId) => {
        // Optimistic update
        await queryClient.cancelQueries({ queryKey: ['posts'] });
        
        // Update feed
        queryClient.setQueryData(['posts', 'feed'], (old: PostWithUser[] | undefined) => {
          if (!old) return old;
          return old.map(post => 
            post.post_id === postId 
              ? { 
                  ...post, 
                  is_liked: !post.is_liked,
                  likes_count: post.is_liked ? post.likes_count - 1 : post.likes_count + 1
                }
              : post
          );
        });
        
        // Update single post
        queryClient.setQueryData(['posts', postId], (old: PostWithUser | undefined) => {
          if (!old) return old;
          return {
            ...old,
            is_liked: !old.is_liked,
            likes_count: old.is_liked ? old.likes_count - 1 : old.likes_count + 1
          };
        });
      },
      onError: () => {
        // Revert optimistic update
        queryClient.invalidateQueries({ queryKey: ['posts'] });
        toast.error('Failed to update like status');
      },
    });
  };

  // Search posts (RAG semantic search; empty query returns global feed)
  const useSearchPosts = (query: string, enabled: boolean = true) => {
    return useQuery({
      queryKey: ['posts', 'search', query],
      queryFn: async (): Promise<PostWithUser[]> => {
        const response = await api.get('/search/posts', {
          params: { q: query, limit: 20 }
        });
        return response.data;
      },
      enabled,
    });
  };

  // Get post comments
  const usePostComments = (postId: string) => {
    return useQuery({
      queryKey: ['posts', postId, 'comments'],
      queryFn: async (): Promise<CommentWithUser[]> => {
        const response = await api.get(`/posts/${postId}/comments`);
        return response.data;
      },
      enabled: !!postId && postId !== 'undefined',
    });
  };

  // Create comment
  const useCreateComment = () => {
    return useMutation({
      mutationFn: async ({ postId, commentData }: { postId: string; commentData: CommentCreate }) => {
        const response = await api.post(`/posts/${postId}/comments`, commentData);
        return response.data;
      },
      onSuccess: (_data, { postId }) => {
        // Invalidate comments and update post comments count
        queryClient.invalidateQueries({ queryKey: ['posts', postId, 'comments'] });
        queryClient.invalidateQueries({ queryKey: ['posts', postId] });
        queryClient.invalidateQueries({ queryKey: ['posts', 'feed'] });
        toast.success('Comment added successfully!');
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to add comment');
      },
    });
  };

  // Delete comment
  const useDeleteComment = () => {
    return useMutation({
      mutationFn: async ({ postId, commentId }: { postId: string; commentId: string }): Promise<void> => {
        await api.delete(`/posts/${postId}/comments/${commentId}`);
      },
      onSuccess: (_data, { postId }) => {
        // Invalidate comments and update post comments count
        queryClient.invalidateQueries({ queryKey: ['posts', postId, 'comments'] });
        queryClient.invalidateQueries({ queryKey: ['posts', postId] });
        queryClient.invalidateQueries({ queryKey: ['posts', 'feed'] });
        toast.success('Comment deleted successfully!');
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to delete comment');
      },
    });
  };

  return {
    useCreatePost,
    useFeed,
    useUserPosts,
    usePost,
    useUpdatePost,
    useDeletePost,
    useToggleLike,
    useSearchPosts,
    usePostComments,
    useCreateComment,
    useDeleteComment,
  };
};