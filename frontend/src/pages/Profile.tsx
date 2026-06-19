import { useParams } from 'react-router-dom';
import { Loader2, Users, UserPlus, UserMinus, Calendar } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

import { useUserService } from '@/services/userService';
import { usePostService } from '@/services/postService';
import PostCard from '@/components/PostCard';

export default function Profile() {
  const { userId } = useParams<{ userId: string }>();
  const { useUserProfile, useCurrentUser, useToggleFollow } = useUserService();
  const { useUserPosts } = usePostService();
  
  const { data: currentUser } = useCurrentUser();
  const { data: profile, isLoading: profileLoading } = useUserProfile(userId!);
  const { data: posts, isLoading: postsLoading } = useUserPosts(userId!);
  const toggleFollow = useToggleFollow();

  const isOwnProfile = currentUser?.user_id === userId;

  const handleFollowToggle = () => {
    if (userId) {
      toggleFollow.mutate(userId);
    }
  };

  if (profileLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="text-center py-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">User Not Found</h2>
        <p className="text-gray-600">The user you're looking for doesn't exist.</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Profile Header */}
      <div className="card p-8 mb-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center space-y-4 sm:space-y-0 sm:space-x-6">
          {/* Avatar */}
          <div className="avatar avatar-xl">
            {profile.avatar_url ? (
              <img
                src={profile.avatar_url}
                alt={profile.username}
                className="w-full h-full object-cover rounded-full"
              />
            ) : (
              <span className="text-gray-600 text-3xl">
                {profile.username[0].toUpperCase()}
              </span>
            )}
          </div>

          {/* Profile Info */}
          <div className="flex-1">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{profile.username}</h1>
                <p className="text-gray-600 flex items-center mt-1">
                  <Calendar className="w-4 h-4 mr-1" />
                  Joined {formatDistanceToNow(new Date(profile.created_at), { addSuffix: true })}
                </p>
              </div>

              {/* Follow Button */}
              {!isOwnProfile && (
                <button
                  onClick={handleFollowToggle}
                  disabled={toggleFollow.isPending}
                  className={`btn flex items-center space-x-2 ${
                    profile.is_following
                      ? 'btn-outline text-red-600 border-red-300 hover:bg-red-50'
                      : 'btn-primary'
                  }`}
                >
                  {profile.is_following ? (
                    <>
                      <UserMinus className="w-4 h-4" />
                      <span>Unfollow</span>
                    </>
                  ) : (
                    <>
                      <UserPlus className="w-4 h-4" />
                      <span>Follow</span>
                    </>
                  )}
                </button>
              )}
            </div>

            {/* Bio */}
            {profile.bio && (
              <p className="text-gray-700 mb-4">{profile.bio}</p>
            )}

            {/* Stats */}
            <div className="flex items-center space-x-6 text-sm">
              <div className="flex items-center space-x-1">
                <span className="font-semibold text-gray-900">{profile.posts_count}</span>
                <span className="text-gray-600">Posts</span>
              </div>
              <div className="flex items-center space-x-1">
                <span className="font-semibold text-gray-900">{profile.followers_count}</span>
                <span className="text-gray-600">Followers</span>
              </div>
              <div className="flex items-center space-x-1">
                <span className="font-semibold text-gray-900">{profile.following_count}</span>
                <span className="text-gray-600">Following</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Posts Section */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">Posts</h2>
        </div>

        {postsLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
          </div>
        ) : posts && posts.length > 0 ? (
          posts.map((post) => (
            <PostCard key={post.post_id} post={post} />
          ))
        ) : (
          <div className="text-center py-12">
            <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No posts yet</h3>
            <p className="text-gray-600">
              {isOwnProfile 
                ? "You haven't posted anything yet. Share your first post!"
                : `${profile.username} hasn't posted anything yet.`
              }
            </p>
          </div>
        )}
      </div>
    </div>
  );
}