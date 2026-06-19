import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

import { usePostService } from '@/services/postService';
import { useUserService } from '@/services/userService';
import PostCard from '@/components/PostCard';

export default function Home() {
  const navigate = useNavigate();
  const { useFeed } = usePostService();
  const { useCurrentUser } = useUserService();
  
  const { data: currentUser, isLoading: userLoading } = useCurrentUser();
  const { data: posts, isLoading: postsLoading, error } = useFeed();

  // Redirect to profile creation if user doesn't exist
  useEffect(() => {
    if (!userLoading && !currentUser && error?.response?.status === 404) {
      navigate('/create-profile');
    }
  }, [currentUser, userLoading, error, navigate]);

  if (userLoading || postsLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (!posts || posts.length === 0) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="text-center py-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Welcome to Social!</h2>
          <p className="text-gray-600 mb-8">
            Your feed is empty. Start by following some users or create your first post!
          </p>
          <div className="space-y-4">
            <button
              onClick={() => navigate('/search')}
              className="btn btn-primary"
            >
              Find People to Follow
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Your Feed</h1>
        <p className="text-gray-600 mt-2">
          Latest posts from people you follow
        </p>
      </div>

      {posts.map((post) => (
        <PostCard key={post.post_id} post={post} />
      ))}
    </div>
  );
}