import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { interval, Subscription, of } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { ApiService, AlertEvent } from '../../services/api.service';

@Component({
  selector: 'app-alerts-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './alerts-panel.html',
  styleUrl: './alerts-panel.css',
})
export class AlertsPanelComponent implements OnInit, OnDestroy {
  alerts: AlertEvent[] = [];
  private sub!: Subscription;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.sub = interval(3000)
      .pipe(
        switchMap(() => this.api.getAlerts().pipe(catchError(() => of(null))))
      )
      .subscribe((a) => { if (a) this.alerts = a.slice().reverse(); });

    this.api.getAlerts().pipe(catchError(() => of(null)))
      .subscribe((a) => { if (a) this.alerts = a.slice().reverse(); });
  }

  severityClass(a: AlertEvent): string {
    const lvl = (a.level ?? a.severity ?? a.alert_labels?.[0] ?? '').toLowerCase();
    if (lvl === 'critical' || lvl === 'error') return 'sev-red';
    if (lvl === 'warning' || lvl === 'warn') return 'sev-amber';
    return 'sev-blue';
  }

  formatTime(ts: string): string {
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch {
      return ts;
    }
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}
