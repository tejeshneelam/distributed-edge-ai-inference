export interface CameraAlertEvent {
  camera_id: string;
  worker_id: string;
  frame_id: number;
  timestamp: string;
  alert_labels: string[];
  level: string;
  message: string;
}
