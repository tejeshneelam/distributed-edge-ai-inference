import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { interval, Subscription, of } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { ApiService, JobStatus } from '../../services/api.service';

@Component({
  selector: 'app-job-status',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './job-status.html',
  styleUrl: './job-status.css',
})
export class JobStatusComponent implements OnInit, OnDestroy {
  jobs: JobStatus[] = [];
  private sub!: Subscription;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.sub = interval(2000)
      .pipe(
        switchMap(() => this.api.getJobs().pipe(catchError(() => of([]))))
      )
      .subscribe((j) => (this.jobs = j));

    this.api.getJobs().pipe(catchError(() => of([])))
      .subscribe((j) => (this.jobs = j));
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  statusClass(s: string): string {
    switch (s) {
      case 'completed': return 'st-green';
      case 'processing': return 'st-blue';
      case 'queued': return 'st-amber';
      case 'failed': return 'st-red';
      default: return 'st-silver';
    }
  }

  formatTime(ts: string | null): string {
    if (!ts) return '—';
    try {
      return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch {
      return ts;
    }
  }

  duration(job: JobStatus): string {
    const start = job.started_at ?? job.submitted_at;
    const end = job.completed_at ?? new Date().toISOString();
    const ms = new Date(end).getTime() - new Date(start).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  fileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }
}
