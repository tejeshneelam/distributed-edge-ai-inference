import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { interval, Subscription, of } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { ApiService, ResultsSummary } from '../../services/api.service';

interface ObjectEntry {
  label: string;
  count: number;
  pct: number;
}

const ICON_MAP: Record<string, string> = {
  person: '🧑', car: '🚗', truck: '🚛', bus: '🚌', motorcycle: '🏍️',
  bicycle: '🚲', dog: '🐕', cat: '🐈', bird: '🐦', horse: '🐎',
  boat: '⛵', airplane: '✈️', train: '🚆', traffic_light: '🚦',
  stop_sign: '🛑', bench: '🪑', backpack: '🎒', umbrella: '☂️',
  handbag: '👜', suitcase: '🧳', bottle: '🍾', cup: '☕',
  chair: '🪑', couch: '🛋️', bed: '🛏️', laptop: '💻',
  cell_phone: '📱', tv: '📺', keyboard: '⌨️', mouse: '🖱️',
  book: '📖', clock: '🕐', knife: '🔪', fork: '🍴', spoon: '🥄',
};

@Component({
  selector: 'app-detection-summary',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './detection-summary.html',
  styleUrl: './detection-summary.css',
})
export class DetectionSummaryComponent implements OnInit, OnDestroy {
  entries: ObjectEntry[] = [];
  totalDetections = 0;
  totalFrames = 0;
  private sub!: Subscription;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.fetch();
    this.sub = interval(3000)
      .pipe(
        switchMap(() => this.api.getResultsSummary().pipe(catchError(() => of(null)))),
      )
      .subscribe((s) => this.update(s));
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  private fetch(): void {
    this.api.getResultsSummary().pipe(catchError(() => of(null)))
      .subscribe((s) => this.update(s));
  }

  private update(s: ResultsSummary | null): void {
    if (!s) return;
    this.totalDetections = s.total_detections;
    this.totalFrames = s.total_frames;
    const counts = s.object_counts ?? {};
    const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
    this.entries = Object.entries(counts)
      .map(([label, count]) => ({ label, count, pct: Math.round(100 * count / total) }))
      .sort((a, b) => b.count - a.count);
  }

  icon(label: string): string {
    return ICON_MAP[label.toLowerCase()] ?? '🔹';
  }

  barColor(i: number): string {
    const colors = [
      'var(--blue)', 'var(--green)', 'var(--amber)', 'var(--teal)',
      'var(--red)', '#7c3aed', '#db2777', '#0891b2',
    ];
    return colors[i % colors.length];
  }
}
