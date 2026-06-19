import axios from 'axios';
import api from './api';

export interface UploadResponse {
  url: string;
  filename: string;
  content_type: string;
  size: number;
}

export const uploadService = {
  /**
   * Uploads an image file to the backend
   * @param file The file to upload
   * @param onUploadProgress Optional callback to track upload progress
   */
  async uploadImage(
    file: File, 
    getToken: () => Promise<string | null>,
    onUploadProgress?: (progressEvent: any) => void
  ): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const token = await getToken();
    
    const response = await api.post<UploadResponse>('/upload-image', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
        'Authorization': `Bearer ${token}`
      },
      onUploadProgress,
    });

    return response.data;
  }
};
