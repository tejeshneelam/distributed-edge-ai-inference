import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { interval, Subscription, of } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { ApiService, WorkerInfo } from '../../services/api.service';

@Component({
  selector: 'app-worker-status',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './worker-status.html',
  styleUrl: './worker-status.css',
})
export class WorkerStatusComponent implements OnInit, OnDestroy {
  workers: WorkerInfo[] = [];
  private sub!: Subscription;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.sub = interval(5000)
      .pipe(
        switchMap(() => this.api.getWorkers().pipe(catchError(() => of([]))))
      )
      .subscribe((w) => (this.workers = w));

    this.api.getWorkers().pipe(catchError(() => of([])))
      .subscribe((w) => (this.workers = w));
  }

  workerStatus(w: WorkerInfo): string {
    return w.status ?? (w.frames_processed > 0 ? 'active' : 'idle');
  }

  pendingDisplay(w: WorkerInfo): string {
    return w.pending_frames != null ? String(w.pending_frames) : '—';
  }

  capabilitiesDisplay(w: WorkerInfo): string {
    return (w.capabilities?.length) ? w.capabilities.join(', ') : '—';
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}
