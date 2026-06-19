import React, { useState, useRef } from 'react';
import { Camera, Loader2, X } from 'lucide-react';
import { useUserService } from '@/services/userService';

interface AvatarUploadProps {
  currentAvatarUrl?: string | null;
}

const AvatarUpload: React.FC<AvatarUploadProps> = ({ currentAvatarUrl }) => {
  const { useUploadAvatar } = useUserService();
  const uploadAvatar = useUploadAvatar();
  
  const [preview, setPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const MAX_SIZE = 2 * 1024 * 1024; // 2MB
  const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Local validation
    if (!ALLOWED_TYPES.includes(file.type)) {
      alert("Please select a valid image (JPG, PNG, or WEBP).");
      return;
    }
    if (file.size > MAX_SIZE) {
      alert("File size must be less than 2MB.");
      return;
    }

    // Show preview locally
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreview(reader.result as string);
    };
    reader.readAsDataURL(file);

    // Auto-upload
    try {
      await uploadAvatar.mutateAsync(file);
      setPreview(null); // Clear preview after successful upload as server data will refresh
    } catch (err) {
      setPreview(null);
    }
    
    // Clear input
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  const displayUrl = preview || currentAvatarUrl || `https://ui-avatars.com/api/?name=User&background=random`;

  return (
    <div className="flex flex-col items-center space-y-4">
      <div className="relative group">
        <div 
          className="w-32 h-32 rounded-full overflow-hidden border-4 border-white shadow-lg bg-gray-100 flex items-center justify-center cursor-pointer"
          onClick={triggerFileInput}
        >
          {uploadAvatar.isPending ? (
            <div className="absolute inset-0 bg-black/40 flex items-center justify-center z-10 transition-opacity">
              <Loader2 className="w-8 h-8 text-white animate-spin" />
            </div>
          ) : (
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 flex items-center justify-center z-10 transition-all duration-200">
              <Camera className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          )}
          
          <img 
            src={displayUrl} 
            alt="Avatar" 
            className={`w-full h-full object-cover transition-filter duration-300 ${uploadAvatar.isPending ? 'blur-sm' : ''}`}
          />
        </div>

        {preview && !uploadAvatar.isPending && (
          <button 
            onClick={() => setPreview(null)}
            className="absolute -top-1 -right-1 bg-red-500 text-white p-1 rounded-full shadow-md hover:bg-red-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        className="hidden"
      />
      
      <button
        type="button"
        onClick={triggerFileInput}
        className="text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors"
      >
        Change Profile Picture
      </button>
      
      <p className="text-xs text-gray-500 text-center">
        JPG, PNG or WEBP. Max 2MB.
      </p>
    </div>
  );
};

export default AvatarUpload;
