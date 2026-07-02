import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from './api';
import { User, UserProfile, UserCreate, UserUpdate, UserSearch, FollowWithUser } from '@/types';
import toast from 'react-hot-toast';

export const useUserService = () => {
  const api = useApi();
  const queryClient = useQueryClient();

  // Get current user profile
  const useCurrentUser = () => {
    return useQuery({
      queryKey: ['user', 'me'],
      queryFn: async (): Promise<User> => {
        const response = await api.get('/users/me');
        return response.data;
      },
      retry: false,
    });
  };

  // Create user profile (first time setup)
  const useCreateProfile = () => {
    return useMutation({
      mutationFn: async (userData: UserCreate): Promise<User> => {
        const response = await api.post('/users/me', userData);
        return response.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['user', 'me'] });
        toast.success('Profile created successfully!');
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to create profile');
      },
    });
  };

  // Update user profile
  const useUpdateProfile = () => {
    return useMutation({
      mutationFn: async (userData: UserUpdate): Promise<User> => {
        const response = await api.put('/users/me', userData);
        return response.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['user', 'me'] });
        toast.success('Profile updated successfully!');
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to update profile');
      },
    });
  };

  // Get user profile by ID
  const useUserProfile = (userId: string) => {
    return useQuery({
      queryKey: ['user', userId],
      queryFn: async (): Promise<UserProfile> => {
        const response = await api.get(`/users/${userId}`);
        return response.data;
      },
      enabled: !!userId && userId !== 'undefined',
    });
  };

  // Search users
  const useSearchUsers = (query: string, enabled: boolean = true) => {
    return useQuery({
      queryKey: ['users', 'search', query],
      queryFn: async (): Promise<UserSearch[]> => {
        const response = await api.get('/users/search', {
          params: { q: query, limit: 20 }
        });
        return response.data;
      },
      enabled: enabled && query.length > 0,
    });
  };

  // Follow/unfollow user
  const useToggleFollow = () => {
    return useMutation({
      mutationFn: async (userId: string): Promise<{ following: boolean; success: boolean }> => {
        const response = await api.post(`/users/${userId}/follow`);
        return response.data;
      },
      onSuccess: (data, userId) => {
        // Invalidate relevant queries
        queryClient.invalidateQueries({ queryKey: ['user', userId] });
        queryClient.invalidateQueries({ queryKey: ['user', 'me'] });
        queryClient.invalidateQueries({ queryKey: ['users', 'followers'] });
        queryClient.invalidateQueries({ queryKey: ['users', 'following'] });
        
        toast.success(data.following ? 'User followed!' : 'User unfollowed!');
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to update follow status');
      },
    });
  };

  // Update avatar
  const useUploadAvatar = () => {
    return useMutation({
      mutationFn: async (file: File): Promise<User> => {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await api.post('/users/me/avatar', formData);
        return response.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['user', 'me'] });
        toast.success('Avatar updated successfully!');
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to update avatar');
      },
    });
  };

  // Get user followers
  const useUserFollowers = (userId: string) => {
    return useQuery({
      queryKey: ['users', 'followers', userId],
      queryFn: async (): Promise<FollowWithUser[]> => {
        const response = await api.get(`/users/${userId}/followers`);
        return response.data;
      },
      enabled: !!userId && userId !== 'undefined',
    });
  };

  // Get user following
  const useUserFollowing = (userId: string) => {
    return useQuery({
      queryKey: ['users', 'following', userId],
      queryFn: async (): Promise<FollowWithUser[]> => {
        const response = await api.get(`/users/${userId}/following`);
        return response.data;
      },
      enabled: !!userId && userId !== 'undefined',
    });
  };

  return {
    useCurrentUser,
    useCreateProfile,
    useUpdateProfile,
    useUserProfile,
    useSearchUsers,
    useToggleFollow,
    useUploadAvatar,
    useUserFollowers,
    useUserFollowing,
  };
};