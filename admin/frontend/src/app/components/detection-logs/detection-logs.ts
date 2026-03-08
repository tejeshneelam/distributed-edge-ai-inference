import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DetectionEvent } from '../../models/detection.model';

const MAX_LOGS = 200;
const VEHICLE_LABELS = new Set(['car', 'truck', 'bus', 'motorcycle', 'bicycle']);

@Component({
  selector: 'app-detection-logs',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './detection-logs.html',
  styleUrl: './detection-logs.css',
})
export class DetectionLogsComponent implements OnChanges {
  @Input() logs: DetectionEvent[] = [];

  dataSource: DetectionEvent[] = [];

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['logs']) {
      this.dataSource = [...this.logs].slice(0, MAX_LOGS);
    }
  }

  objectKeys(obj: Record<string, number> | undefined): string[] {
    if (!obj) return [];
    return Object.keys(obj).filter(k => (obj[k] ?? 0) > 0);
  }

  isVehicle(label: string): boolean {
    return VEHICLE_LABELS.has(label);
  }

  getUniqueTypes(types: string[]): { label: string; count: number }[] {
    if (!types || types.length === 0) return [];
    const counts = types.reduce<Record<string, number>>((acc, t) => {
      acc[t] = (acc[t] ?? 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts).map(([label, count]) => ({ label, count }));
  }
}
