import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CameraInfo } from '../../models/camera.model';

@Component({
  selector: 'app-camera-status',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './camera-status.html',
  styleUrl: './camera-status.css',
})
export class CameraStatusComponent {
  @Input() cameras: CameraInfo[] = [];
}
