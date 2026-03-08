import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CameraInfo, CameraRegisterRequest, CameraControlRequest } from '../models/camera.model';
import { AnalyticsData } from '../models/analytics.model';
import { DetectionEvent } from '../models/detection.model';

const BASE_URL = '';

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  getHealth(): Observable<{ status: string }> {
    return this.http.get<{ status: string }>(`${BASE_URL}/health`);
  }

  getCameras(): Observable<CameraInfo[]> {
    return this.http.get<CameraInfo[]>(`${BASE_URL}/cameras`);
  }

  registerCamera(payload: CameraRegisterRequest): Observable<CameraInfo> {
    return this.http.post<CameraInfo>(`${BASE_URL}/register-camera`, payload);
  }

  getAnalytics(): Observable<AnalyticsData> {
    return this.http.get<AnalyticsData>(`${BASE_URL}/analytics`);
  }

  postDetection(payload: DetectionEvent): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`${BASE_URL}/camera-detection`, payload);
  }

  sendControl(payload: CameraControlRequest): Observable<{ status: string; camera_id: string; command: string }> {
    return this.http.post<{ status: string; camera_id: string; command: string }>(
      `${BASE_URL}/camera-control`,
      payload
    );
  }
}
