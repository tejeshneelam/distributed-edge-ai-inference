export interface DetectionEvent {
  camera_id: string;
  timestamp: string;
  detected_vehicles: number;
  vehicle_types: string[];
}
