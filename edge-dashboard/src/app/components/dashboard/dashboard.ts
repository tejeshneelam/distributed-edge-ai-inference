import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { interval, Subscription } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { of } from 'rxjs';
import { MetricsPanelComponent } from '../metrics-panel/metrics-panel';
import { WorkerStatusComponent } from '../worker-status/worker-status';
import { VideoStreamComponent } from '../video-stream/video-stream';
import { FrameResultsComponent } from '../frame-results/frame-results';
import { AlertsPanelComponent } from '../alerts-panel/alerts-panel';
import { JobStatusComponent } from '../job-status/job-status';
import { DetectionSummaryComponent } from '../detection-summary/detection-summary';
import { ToastComponent } from '../toast/toast';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    MatIconModule,
    MetricsPanelComponent,
    WorkerStatusComponent,
    VideoStreamComponent,
    FrameResultsComponent,
    AlertsPanelComponent,
    JobStatusComponent,
    DetectionSummaryComponent,
    ToastComponent,
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class DashboardComponent implements OnInit, OnDestroy {
  sysOnline = true;
  clock = '--:--:--';
  private healthSub!: Subscription;
  private clockSub!: Subscription;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.healthSub = interval(5000)
      .pipe(
        switchMap(() =>
          this.api.getHealth().pipe(catchError(() => of(null)))
        )
      )
      .subscribe((h) => {
        this.sysOnline = h !== null && (h as any)?.status !== 'error';
      });

    this.updateClock();
    this.clockSub = interval(1000).subscribe(() => this.updateClock());
  }

  ngOnDestroy(): void {
    this.healthSub?.unsubscribe();
    this.clockSub?.unsubscribe();
  }

  private updateClock(): void {
    this.clock = new Date().toLocaleTimeString('en-GB', { hour12: false });
  }
}
