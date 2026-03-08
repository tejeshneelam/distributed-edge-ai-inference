import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatIconModule } from '@angular/material/icon';
import { CameraInfo } from '../../models/camera.model';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-camera-control',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatSelectModule,
    MatFormFieldModule,
    MatSnackBarModule,
    MatIconModule,
  ],
  templateUrl: './camera-control.html',
  styleUrl: './camera-control.css',
})
export class CameraControlComponent {
  @Input() cameras: CameraInfo[] = [];

  selectedCameraId = '';
  loading = false;

  constructor(private api: ApiService, private snack: MatSnackBar) {}

  send(command: 'start' | 'stop'): void {
    if (!this.selectedCameraId) {
      this.snack.open('Select a camera first', 'OK', { duration: 2500 });
      return;
    }
    this.loading = true;
    this.api.sendControl({ camera_id: this.selectedCameraId, command }).subscribe({
      next: () => {
        this.snack.open(`"${command}" sent to ${this.selectedCameraId}`, '✓', { duration: 2500 });
        this.loading = false;
      },
      error: () => {
        this.snack.open('Failed to send command', 'Retry', { duration: 3000 });
        this.loading = false;
      },
    });
  }
}
