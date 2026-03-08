import { Component, Input, OnChanges, SimpleChanges, AfterViewInit, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AnalyticsData } from '../../models/analytics.model';
import {
  Chart,
  BarController, BarElement, CategoryScale, LinearScale,
  PieController, ArcElement,
  LineController, LineElement, PointElement,
  Tooltip, Legend,
} from 'chart.js';

Chart.register(
  BarController, BarElement, CategoryScale, LinearScale,
  PieController, ArcElement,
  LineController, LineElement, PointElement,
  Tooltip, Legend
);

@Component({
  selector: 'app-analytics-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './analytics-panel.html',
  styleUrl: './analytics-panel.css',
})
export class AnalyticsPanelComponent implements OnChanges, AfterViewInit {
  @Input() analytics: AnalyticsData | null = null;

  @ViewChild('barCanvas') barCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('pieCanvas') pieCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('lineCanvas') lineCanvas!: ElementRef<HTMLCanvasElement>;

  private barChart: Chart | null = null;
  private pieChart: Chart | null = null;
  private lineChart: Chart | null = null;
  private viewReady = false;

  ngAfterViewInit(): void {
    this.viewReady = true;
    this.initCharts();
    if (this.analytics) this.updateCharts(this.analytics);
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['analytics'] && this.viewReady && this.analytics) {
      this.updateCharts(this.analytics);
    }
  }

  private initCharts(): void {
    this.barChart = new Chart(this.barCanvas.nativeElement, {
      type: 'bar',
      data: { labels: [], datasets: [{ label: 'Detections per Camera', data: [], backgroundColor: '#1a6fe8' }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
    });

    this.pieChart = new Chart(this.pieCanvas.nativeElement, {
      type: 'pie',
      data: {
        labels: [],
        datasets: [{ data: [], backgroundColor: ['#1a6fe8', '#087f3a', '#b45309', '#c0392b', '#0e7490', '#7c3aed'] }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    this.lineChart = new Chart(this.lineCanvas.nativeElement, {
      type: 'line',
      data: { labels: [], datasets: [{ label: 'Detections over time', data: [], borderColor: '#1a6fe8', fill: false, tension: 0.3 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
    });
  }

  private updateCharts(data: AnalyticsData): void {
    const camLabels = Object.keys(data.per_camera);
    const camData = camLabels.map(k => data.per_camera[k]);
    if (this.barChart) {
      this.barChart.data.labels = camLabels;
      this.barChart.data.datasets[0].data = camData;
      this.barChart.update();
    }

    const typeLabels = Object.keys(data.type_distribution);
    const typeData = typeLabels.map(k => data.type_distribution[k]);
    if (this.pieChart) {
      this.pieChart.data.labels = typeLabels;
      this.pieChart.data.datasets[0].data = typeData;
      this.pieChart.update();
    }

    const tl = data.timeline.slice(-20);
    if (this.lineChart) {
      this.lineChart.data.labels = tl.map(e => new Date(e.timestamp).toLocaleTimeString());
      this.lineChart.data.datasets[0].data = tl.map(e => e.detected_vehicles);
      this.lineChart.update();
    }
  }

  getCamValue(key: string): number {
    return this.analytics?.per_camera[key] ?? 0;
  }

  getCamKeys(): string[] {
    return Object.keys(this.analytics?.per_camera ?? {});
  }
}
