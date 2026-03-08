export interface CameraInfo {
  camera_id: string;
  hostname: string;
  ip_address: string;
  status: 'active' | 'offline';
  registered_at: string;
  last_seen: string;
}

export interface CameraRegisterRequest {
  camera_id: string;
  hostname: string;
  ip_address: string;
}

export interface CameraControlRequest {
  camera_id: string;
  command: 'start' | 'stop';
}
