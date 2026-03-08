import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { interval, Subscription } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { WebsocketService } from '../../services/websocket.service';
import { CameraInfo } from '../../models/camera.model';
import { AnalyticsData } from '../../models/analytics.model';
import { DetectionEvent } from '../../models/detection.model';

import { CameraStatusComponent } from '../camera-status/camera-status';
import { AnalyticsPanelComponent } from '../analytics-panel/analytics-panel';
import { DetectionLogsComponent } from '../detection-logs/detection-logs';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    MatIconModule,
    CameraStatusComponent,
    AnalyticsPanelComponent,
    DetectionLogsComponent,
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class DashboardComponent implements OnInit, OnDestroy {
  sysOnline = false;
  clock = '--:--:--';

  cameras: CameraInfo[] = [];
  analytics: AnalyticsData | null = null;
  logs: DetectionEvent[] = [];

  private subs: Subscription[] = [];

  constructor(private api: ApiService, private ws: WebsocketService) {}

  ngOnInit(): void {
    // Health check
    this.subs.push(
      interval(5000).pipe(
        switchMap(() => this.api.getHealth().pipe(catchError(() => of(null))))
      ).subscribe(h => { this.sysOnline = h !== null; })
    );

    // Poll cameras every 5s
    this.subs.push(
      interval(5000).pipe(
        switchMap(() => this.api.getCameras().pipe(catchError(() => of([]))))
      ).subscribe((cams: CameraInfo[]) => { this.cameras = cams; })
    );

    // Poll analytics every 5s
    this.subs.push(
      interval(5000).pipe(
        switchMap(() => this.api.getAnalytics().pipe(catchError(() => of(null))))
      ).subscribe(a => { if (a) this.analytics = a; })
    );

    // Initial fetches (no need to wait for first interval tick)
    this.api.getCameras().pipe(catchError(() => of([]))).subscribe((c: CameraInfo[]) => { this.cameras = c; });
    this.api.getAnalytics().pipe(catchError(() => of(null))).subscribe(a => {
      if (a) {
        this.analytics = a;
        // Pre-populate logs from stored timeline so data shows immediately on reload
        if (a.timeline && a.timeline.length > 0) {
          this.logs = [...a.timeline].reverse().map(e => ({
            camera_id: e.camera_id,
            timestamp: e.timestamp,
            detected_vehicles: e.detected_vehicles,
            vehicle_types: e.vehicle_types,
            object_counts: (e as any).object_counts ?? {},
          }));
        }
      }
    });
    this.api.getHealth().pipe(catchError(() => of(null))).subscribe(h => { this.sysOnline = h !== null; });

    // Real-time WS events
    this.subs.push(
      this.ws.messages$.subscribe(msg => this.handleWsMessage(msg))
    );

    // Clock
    this.updateClock();
    this.subs.push(interval(1000).subscribe(() => this.updateClock()));
  }

  ngOnDestroy(): void {
    this.subs.forEach(s => s.unsubscribe());
  }

  private handleWsMessage(msg: { type: string; data: unknown }): void {
    if (msg.type === 'detection') {
      const event = msg.data as DetectionEvent;
      // Prepend newest, cap at 200
      this.logs = [event, ...this.logs].slice(0, 200);
      // Refresh analytics from server to avoid double-counting from optimistic updates
      this.api.getAnalytics().pipe(catchError(() => of(null))).subscribe(a => {
        if (a) this.analytics = a;
      });
    }
  }

  private updateClock(): void {
    this.clock = new Date().toLocaleTimeString('en-GB', { hour12: false });
  }
}
