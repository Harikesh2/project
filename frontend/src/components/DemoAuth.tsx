import { useState } from 'react';
import { User, Mail, Lock } from 'lucide-react';

interface DemoAuthProps {
  onLogin: (user: any) => void;
}

export default function DemoAuth({ onLogin }: DemoAuthProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleDemoLogin = async () => {
    setIsLoading(true);
    
    // Simulate API call
    setTimeout(() => {
      const demoUser = {
        user_id: 'demo_user_123',
        username: 'demo_user',
        email: 'demo@example.com',
        avatar_url: '',
        bio: 'This is a demo user for local development',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        followers_count: 42,
        following_count: 24,
        posts_count: 8
      };
      
      // Store demo token
      localStorage.setItem('demo_token', 'demo_token_123');
      localStorage.setItem('demo_user', JSON.stringify(demoUser));
      
      onLogin(demoUser);
      setIsLoading(false);
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <div className="w-16 h-16 bg-primary-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-2xl">S</span>
          </div>
          <h2 className="text-3xl font-bold text-gray-900">Social Media Demo</h2>
          <p className="mt-2 text-gray-600">
            Local development mode - no authentication required
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-md p-8 space-y-6">
          <div className="space-y-4">
            <div className="flex items-center space-x-3 p-3 bg-blue-50 rounded-lg">
              <User className="w-5 h-5 text-blue-600" />
              <div>
                <p className="font-medium text-blue-900">Demo User</p>
                <p className="text-sm text-blue-600">demo_user</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3 p-3 bg-green-50 rounded-lg">
              <Mail className="w-5 h-5 text-green-600" />
              <div>
                <p className="font-medium text-green-900">Email</p>
                <p className="text-sm text-green-600">demo@example.com</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3 p-3 bg-yellow-50 rounded-lg">
              <Lock className="w-5 h-5 text-yellow-600" />
              <div>
                <p className="font-medium text-yellow-900">Authentication</p>
                <p className="text-sm text-yellow-600">Bypassed for demo</p>
              </div>
            </div>
          </div>

          <button
            onClick={handleDemoLogin}
            disabled={isLoading}
            className="w-full btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Logging in...' : 'Enter Demo Mode'}
          </button>

          <div className="text-center">
            <p className="text-sm text-gray-500">
              This is a demo mode for local development.
              <br />
              In production, you would use Clerk authentication.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}