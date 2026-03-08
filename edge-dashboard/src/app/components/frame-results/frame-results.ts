import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { interval, Subscription, of } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { ApiService, FrameResult } from '../../services/api.service';

@Component({
  selector: 'app-frame-results',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './frame-results.html',
  styleUrl: './frame-results.css',
})
export class FrameResultsComponent implements OnInit, OnDestroy {
  frames: FrameResult[] = [];
  private sub!: Subscription;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.sub = interval(5000)
      .pipe(
        switchMap(() => this.api.getResults().pipe(catchError(() => of(null))))
      )
      .subscribe((r) => { if (r) this.frames = r.frames; });

    this.api.getResults().pipe(catchError(() => of(null)))
      .subscribe((r) => { if (r) this.frames = r.frames; });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  detectedLabels(f: FrameResult): string[] {
    if (f.detections && f.detections.length > 0) {
      // Deduplicate with counts: ['car ×2', 'person']
      const counts: Record<string, number> = {};
      f.detections.forEach(d => counts[d.label] = (counts[d.label] || 0) + 1);
      return Object.entries(counts).map(([k, v]) => v > 1 ? `${k} ×${v}` : k);
    }
    const entries = Object.entries(f.object_counts);
    if (entries.length === 0) return ['—'];
    return entries.map(([k, v]) => v > 1 ? `${k} ×${v}` : k);
  }

  processingTime(f: FrameResult): string {
    return f.processing_time_ms != null
      ? `${f.processing_time_ms.toFixed(1)} ms`
      : '—';
  }
}
