import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Search as SearchIcon, Users, FileText, Loader2 } from 'lucide-react';

import { useUserService } from '@/services/userService';
import { usePostService } from '@/services/postService';
import PostCard from '@/components/PostCard';

export default function Search() {
  const [query, setQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'users' | 'posts'>('users');
  
  const { useSearchUsers } = useUserService();
  const { useSearchPosts } = usePostService();
  
  const { data: users, isLoading: usersLoading } = useSearchUsers(query, activeTab === 'users');
  const { data: posts, isLoading: postsLoading } = useSearchPosts(query, activeTab === 'posts');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Search Header */}
      <div className="card p-6 mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Search</h1>
        
        {/* Search Form */}
        <form onSubmit={handleSearch} className="mb-6">
          <div className="relative">
            <SearchIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for users or posts..."
              className="input pl-10"
            />
          </div>
        </form>

        {/* Tabs */}
        <div className="flex space-x-1 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setActiveTab('users')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'users'
                ? 'bg-white text-primary-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Users</span>
          </button>
          <button
            onClick={() => setActiveTab('posts')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'posts'
                ? 'bg-white text-primary-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Posts</span>
          </button>
        </div>
      </div>

      {/* Results */}
      <div className="space-y-6">
        {!query ? (
          <div className="text-center py-12">
            <SearchIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Start searching</h3>
            <p className="text-gray-600">
              Enter a search term to find users or posts
            </p>
          </div>
        ) : activeTab === 'users' ? (
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Users</h2>
            {usersLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-primary-600" />
              </div>
            ) : users && users.length > 0 ? (
              <div className="space-y-4">
                {users.map((user) => (
                  <div key={user.user_id} className="card p-4">
                    <div className="flex items-center space-x-4">
                      <Link to={`/profile/${user.user_id}`}>
                        <div className="avatar avatar-md">
                          {user.avatar_url ? (
                            <img
                              src={user.avatar_url}
                              alt={user.username}
                              className="w-full h-full object-cover rounded-full"
                            />
                          ) : (
                            <span className="text-gray-600">
                              {user.username[0].toUpperCase()}
                            </span>
                          )}
                        </div>
                      </Link>
                      <div className="flex-1">
                        <Link
                          to={`/profile/${user.user_id}`}
                          className="font-medium text-gray-900 hover:text-primary-600"
                        >
                          {user.username}
                        </Link>
                        {user.bio && (
                          <p className="text-sm text-gray-600 mt-1">{user.bio}</p>
                        )}
                        <p className="text-sm text-gray-500 mt-1">
                          {user.followers_count} followers
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Users className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-gray-600">No users found for "{query}"</p>
              </div>
            )}
          </div>
        ) : (
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Posts</h2>
            {postsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-primary-600" />
              </div>
            ) : posts && posts.length > 0 ? (
              <div className="space-y-6">
                {posts.map((post) => (
                  <PostCard key={post.post_id} post={post} />
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <FileText className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-gray-600">No posts found for "{query}"</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}