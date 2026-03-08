import { Injectable } from '@angular/core';
import { HttpClient, HttpRequest, HttpEvent } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface WorkerInfo {
  worker_id: string;
  host: string;
  port: number;
  hostname: string;
  ip_address: string;
  registered_at: string;
  frames_processed: number;
  status: 'active' | 'idle' | 'offline';
  pending_frames: number;
  capabilities: string[];
  avg_processing_ms: number;
}

export interface Detection {
  label: string;
  confidence: number;
  box: { x1: number; y1: number; x2: number; y2: number };
}

export interface FrameResult {
  frame_id: number;
  worker_id: string;
  detections: Detection[];
  object_counts: Record<string, number>;
  processing_time_ms: number;
  received_at: string;
  status?: 'pending' | 'completed' | 'failed';
  job_id?: string;
}

export interface AggregatedResults {
  total_frames_processed: number;
  total_detections: number;
  object_counts: Record<string, number>;
  frames: FrameResult[];
  worker_summary: Record<string, number>;
}

export interface ResultsSummary {
  total_frames: number;
  total_detections: number;
  object_counts: Record<string, number>;
  worker_summary: Record<string, number>;
}

export interface WorkerStatusSummary { total: number; active: number; idle: number; offline: number; }
export interface LatencyStats { avg_ms: number; p95_ms: number; samples: number; }

export interface SystemMetrics {
  number_of_workers: number;
  total_frames_processed: number;
  processing_fps: number;
  system_start_time: string;
  workers: WorkerStatusSummary;
  queue: Record<string, number>;
  latency_ms: LatencyStats;
  retry_count: number;
  dropped_count: number;
}

export interface AlertEvent {
  worker_id: string;
  frame_id: number;
  timestamp: string;
  detections: Detection[];
  alert_labels: string[];
  level?: string;
  severity?: string;
  message?: string;
}

export interface QueueStats {
  pending: number;
  inflight: number;
  retry_count: number;
  dropped_count: number;
}

export interface JobStatus {
  job_id: string;
  filename: string;
  size_bytes: number;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  submitted_at: string;
  started_at: string | null;
  completed_at: string | null;
  total_frames: number;
  processed_frames: number;
  detections_found: number;
  error: string | null;
  progress_pct: number;
}

export interface AdminAnalytics {
  total_vehicles: number;
  per_camera: Record<string, number>;
  type_distribution: Record<string, number>;
  timeline: { timestamp: string; camera_id: string; detected_vehicles: number }[];
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly base = 'http://localhost:8000';
  readonly adminBase = 'http://localhost:8001';

  constructor(private http: HttpClient) {}

  getHealth(): Observable<{ status: string }> {
    return this.http.get<{ status: string }>(`${this.base}/health`);
  }

  getWorkers(): Observable<WorkerInfo[]> {
    return this.http.get<WorkerInfo[]>(`${this.base}/workers`);
  }

  getResults(): Observable<AggregatedResults> {
    return this.http.get<AggregatedResults>(`${this.base}/results`);
  }

  getResultsSummary(): Observable<ResultsSummary> {
    return this.http.get<ResultsSummary>(`${this.base}/results/summary`);
  }

  getMetrics(): Observable<SystemMetrics> {
    return this.http.get<SystemMetrics>(`${this.base}/metrics`);
  }

  getQueueStats(): Observable<QueueStats> {
    return this.http.get<QueueStats>(`${this.base}/queue/stats`);
  }

  getAlerts(): Observable<AlertEvent[]> {
    return this.http.get<AlertEvent[]>(`${this.base}/alerts`);
  }

  getJobs(): Observable<JobStatus[]> {
    return this.http.get<JobStatus[]>(`${this.base}/jobs`);
  }

  getJob(jobId: string): Observable<JobStatus> {
    return this.http.get<JobStatus>(`${this.base}/jobs/${encodeURIComponent(jobId)}`);
  }

  getVideoStreamUrl(): string {
    return `${this.base}/video-stream`;
  }

  uploadVideo(file: File): Observable<HttpEvent<any>> {
    const form = new FormData();
    form.append('file', file, file.name);
    const req = new HttpRequest('POST', `${this.base}/upload-video`, form, {
      reportProgress: true,
    });
    return this.http.request(req);
  }

  getNetworkAnalytics(): Observable<AdminAnalytics> {
    return this.http.get<AdminAnalytics>(`${this.adminBase}/analytics`);
  }
}
