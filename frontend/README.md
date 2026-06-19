# Social Media Frontend

React + TypeScript frontend for the social media platform.

## Prerequisites

- Node.js 18+
- Running backend API (default: http://localhost:8000)

## Setup

1. Copy environment file:
   ```powershell
   copy .env.example .env
   ```

2. Fill in `.env`:
   ```
   VITE_CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key
   VITE_API_BASE_URL=http://localhost:8000
   ```

3. Install dependencies and start the dev server:
   ```powershell
   npm install
   npm run dev
   ```

   App runs at http://localhost:5173

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |

## Features

- User authentication (Clerk)
- Create and view posts
- Like and comment
- User profiles and search
- Responsive design
