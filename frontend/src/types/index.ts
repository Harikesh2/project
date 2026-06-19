// User types
export interface User {
  user_id: string;
  username: string;
  email: string;
  avatar_url?: string;
  bio?: string;
  created_at: string;
  updated_at: string;
  followers_count: number;
  following_count: number;
  posts_count: number;
}

export interface UserProfile extends User {
  is_following?: boolean;
  is_followed_by?: boolean;
}

export interface UserSearch {
  user_id: string;
  username: string;
  avatar_url?: string;
  bio?: string;
  followers_count: number;
}

export interface UserCreate {
  username: string;
  email: string;
  avatar_url?: string;
  bio?: string;
}

export interface UserUpdate {
  username?: string;
  avatar_url?: string;
  bio?: string;
}

// Post types
export interface Post {
  post_id: string;
  user_id: string;
  content: string;
  image_url?: string;
  created_at: string;
  updated_at: string;
  likes_count: number;
  comments_count: number;
}

export interface PostWithUser extends Post {
  user: UserSearch;
  is_liked?: boolean;
}

export interface PostCreate {
  content: string;
  image_url?: string;
}

export interface PostUpdate {
  content?: string;
  image_url?: string;
}

// Comment types
export interface Comment {
  comment_id: string;
  post_id: string;
  user_id: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface CommentWithUser extends Comment {
  user: UserSearch;
}

export interface CommentCreate {
  content: string;
}

// Follow types
export interface Follow {
  follower_id: string;
  following_id: string;
  created_at: string;
}

export interface FollowWithUser extends Follow {
  user: UserSearch;
}

// API Response types
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  has_more: boolean;
  last_key?: string;
}

// Form types
export interface LoginForm {
  email: string;
  password: string;
}

export interface SignUpForm {
  email: string;
  password: string;
  username: string;
}

export interface PostForm {
  content: string;
  image_url?: string;
}

export interface CommentForm {
  content: string;
}

export interface ProfileForm {
  username: string;
  bio?: string;
  avatar_url?: string;
}