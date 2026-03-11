import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CameraAlertEvent } from '../../models/alert.model';

@Component({
  selector: 'app-alerts-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './alerts-panel.html',
  styleUrl: './alerts-panel.css',
})
export class AlertsPanelComponent {
  @Input() alerts: CameraAlertEvent[] = [];

  severityClass(a: CameraAlertEvent): string {
    const lvl = (a.level ?? '').toLowerCase();
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
}
