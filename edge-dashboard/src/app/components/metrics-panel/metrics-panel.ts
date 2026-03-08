import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { interval, Subscription, of } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { ApiService, SystemMetrics } from '../../services/api.service';

@Component({
  selector: 'app-metrics-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './metrics-panel.html',
  styleUrl: './metrics-panel.css',
})
export class MetricsPanelComponent implements OnInit, OnDestroy {
  metrics: SystemMetrics | null = null;
  uptime = '—';
  private sub!: Subscription;
  private uptimeSub!: Subscription;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.sub = interval(2000)
      .pipe(
        switchMap(() => this.api.getMetrics().pipe(catchError(() => of(null))))
      )
      .subscribe((m) => { if (m) this.metrics = m; });

    this.api.getMetrics().pipe(catchError(() => of(null)))
      .subscribe((m) => { if (m) this.metrics = m; });

    this.uptimeSub = interval(1000).subscribe(() => this.updateUptime());
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.uptimeSub?.unsubscribe();
  }

  private updateUptime(): void {
    if (!this.metrics?.system_start_time) { this.uptime = '—'; return; }
    const elapsedMs = Date.now() - new Date(this.metrics.system_start_time).getTime();
    const totalSec = Math.max(0, Math.floor(elapsedMs / 1000));
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    this.uptime = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
}
