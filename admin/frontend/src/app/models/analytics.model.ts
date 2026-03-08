export interface AnalyticsData {
  total_vehicles: number;
  per_camera: Record<string, number>;
  type_distribution: Record<string, number>;
  timeline: TimelineEntry[];
}

export interface TimelineEntry {
  timestamp: string;
  camera_id: string;
  detected_vehicles: number;
  vehicle_types: string[];
}
