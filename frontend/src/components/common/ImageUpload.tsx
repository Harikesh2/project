import React, { useState, useRef, useEffect } from 'react';
import { uploadService } from '../../services/uploadService';
import { useAuth } from '@clerk/clerk-react';
import { X } from 'lucide-react';

interface ImageUploadProps {
  onUploadSuccess: (url: string) => void;
  label?: string;
  initialImageUrl?: string;
}

const ImageUpload: React.FC<ImageUploadProps> = ({ onUploadSuccess, label = "Upload Image", initialImageUrl = "" }) => {
  const { getToken } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(initialImageUrl || null);
  const [progress, setProgress] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const MAX_SIZE = 2 * 1024 * 1024; // 2MB
  const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];

  useEffect(() => {
    if (initialImageUrl) {
      setPreview(initialImageUrl);
    } else if (!file) {
      setPreview(null);
    }
  }, [initialImageUrl, file]);

  const validateFile = (selectedFile: File) => {
    if (!ALLOWED_TYPES.includes(selectedFile.type)) {
      setError("Please select a valid image (JPG, PNG, or WEBP).");
      return false;
    }
    if (selectedFile.size > MAX_SIZE) {
      setError("File size must be less than 2MB.");
      return false;
    }
    return true;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const selectedFile = e.target.files?.[0];
    
    if (selectedFile) {
      if (validateFile(selectedFile)) {
        setFile(selectedFile);
        const objectUrl = URL.createObjectURL(selectedFile);
        setPreview(objectUrl);
      } else {
        setFile(null);
        setPreview(initialImageUrl || null);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    }
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    // Revoke object URL if we created one
    if (preview && preview.startsWith('blob:')) {
      URL.revokeObjectURL(preview);
    }
    
    setFile(null);
    setPreview(null);
    onUploadSuccess('');
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleUpload = async () => {
    if (!file) return;

    setLoading(true);
    setProgress(0);
    setError(null);

    try {
      const response = await uploadService.uploadImage(
        file, 
        () => getToken(),
        (progressEvent) => {
          const percentCompleted = progressEvent.total
            ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
            : 0;
          setProgress(percentCompleted);
        }
      );
      
      onUploadSuccess(response.url);
      setFile(null);
      // Keep the preview of the newly uploaded cloud URL
      setPreview(response.url);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err: unknown) {
      console.error("Upload error:", err);
      const message = err instanceof Error ? err.message : "Failed to upload image. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Cleanup object URL on unmount
  useEffect(() => {
    return () => {
      if (preview && preview.startsWith('blob:')) {
        URL.revokeObjectURL(preview);
      }
    };
  }, [preview]);

  return (
    <div className="flex flex-col space-y-4 w-full max-w-md p-4 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 transition-all duration-300">
      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</label>
      
      <div className="relative group">
        <input
          type="file"
          accept="image/*"
          ref={fileInputRef}
          onChange={handleFileChange}
          className="hidden"
          id="image-upload-input"
        />
        {preview ? (
          <div className="relative w-full h-40 rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
            <img src={preview} alt="Preview" className="w-full h-full object-cover" />
            <button
              type="button"
              onClick={handleRemove}
              className="absolute top-2 right-2 p-1.5 bg-gray-900/60 hover:bg-gray-900/80 text-white rounded-full transition-colors backdrop-blur-sm"
              title="Remove image"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <label
            htmlFor="image-upload-input"
            className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors bg-gray-50 dark:bg-gray-900 overflow-hidden"
          >
            <div className="flex flex-col items-center justify-center pt-5 pb-6">
              <svg className="w-8 h-8 mb-4 text-gray-500 dark:text-gray-400" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 20 16">
                <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 13h3a3 3 0 0 0 0-6h-.025A5.56 5.56 0 0 0 16 6.5 5.5 5.5 0 0 0 5.207 5.021C5.137 5.017 5.071 5 5 5a4 4 0 0 0 0 8h2.167M10 15V6m0 0L8 8m2-2l2 2"/>
              </svg>
              <p className="mb-2 text-sm text-gray-500 dark:text-gray-400"><span className="font-semibold">Click to upload</span> or drag and drop</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">JPG, PNG or WEBP (Max 2MB)</p>
            </div>
          </label>
        )}
      </div>

      {error && (
        <div className="mt-2 text-sm text-red-500 bg-red-50 dark:bg-red-900/20 p-2 rounded border border-red-200 dark:border-red-800">
          {error}
        </div>
      )}

      {loading && (
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
          <div 
            className="bg-indigo-600 h-2.5 rounded-full transition-all duration-300" 
            style={{ width: `${progress}%` }}
          ></div>
          <p className="text-xs text-center mt-1 text-gray-500">{progress}% uploaded</p>
        </div>
      )}

      <button
        onClick={handleUpload}
        disabled={!file || loading}
        className={`w-full py-2 px-4 rounded-lg font-medium text-white transition-all duration-200 ${
          !file || loading 
            ? 'bg-gray-400 cursor-not-allowed' 
            : 'bg-indigo-600 hover:bg-indigo-700 shadow-md hover:shadow-lg active:scale-95'
        }`}
      >
        {loading ? (
          <span className="flex items-center justify-center">
            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Uploading...
          </span>
        ) : "Upload To Cloud"}
      </button>
    </div>
  );
};

export default ImageUpload;
