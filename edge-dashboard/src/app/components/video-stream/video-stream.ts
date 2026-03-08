import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpEventType } from '@angular/common/http';
import { Subscription, interval, of } from 'rxjs';
import { switchMap, catchError, takeWhile } from 'rxjs/operators';
import { ApiService, JobStatus } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

@Component({
  selector: 'app-video-stream',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './video-stream.html',
  styleUrl: './video-stream.css',
})
export class VideoStreamComponent implements OnInit, OnDestroy {
  streamUrl = '';
  streamStatus: 'connecting' | 'live' | 'error' = 'connecting';

  uploadStatus: 'idle' | 'uploading' | 'done' | 'error' = 'idle';
  uploadProgress = 0;
  uploadMessage = '';
  isDragOver = false;

  /** Live tracking of the most recent upload job */
  activeJob: JobStatus | null = null;
  private jobSub?: Subscription;

  constructor(private api: ApiService, private notif: NotificationService) {}

  ngOnInit(): void {
    this.connect();
  }

  ngOnDestroy(): void {
    this.jobSub?.unsubscribe();
  }

  connect(): void {
    this.streamUrl = `${this.api.getVideoStreamUrl()}?t=${Date.now()}`;
    this.streamStatus = 'connecting';
  }

  onLoad(): void  { this.streamStatus = 'live'; }
  onError(): void { this.streamStatus = 'error'; }

  onDragOver(e: DragEvent): void { e.preventDefault(); this.isDragOver = true; }
  onDragLeave(): void { this.isDragOver = false; }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.isDragOver = false;
    const file = e.dataTransfer?.files[0];
    if (file) this.uploadFile(file);
  }

  onFileSelect(e: Event): void {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this.uploadFile(file);
    input.value = '';
  }

  uploadFile(file: File): void {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    const validExt = ['mp4','avi','mov','mkv','webm','flv'].includes(ext);
    if (!file.type.startsWith('video/') && !validExt) {
      this.uploadStatus = 'error';
      this.uploadMessage = 'Please select a video file (mp4, avi, mov, mkv, webm).';
      return;
    }

    this.uploadStatus = 'uploading';
    this.uploadProgress = 0;
    this.uploadMessage = `Uploading ${file.name}…`;
    this.activeJob = null;
    this.jobSub?.unsubscribe();

    this.api.uploadVideo(file).subscribe({
      next: (event: any) => {
        if (event.type === HttpEventType.UploadProgress && event.total) {
          this.uploadProgress = Math.round(100 * event.loaded / event.total);
        } else if (event.type === HttpEventType.Response) {
          const jobId: string = event.body?.job_id ?? '';
          this.uploadStatus = 'done';
          this.uploadMessage = `Queued — job ${jobId}`;
          this.notif.info('Job Queued', `${file.name} submitted — job ${jobId}`);
          this.connect();
          if (jobId) {
            this.pollJobStatus(jobId, file.name);
          }
        }
      },
      error: () => {
        this.uploadStatus = 'error';
        this.uploadMessage = 'Upload failed. Ensure the backend is running on port 8000.';
        this.notif.error('Upload Failed', 'Could not reach backend on port 8000.');
      },
    });
  }

  resetUpload(): void {
    this.uploadStatus = 'idle';
    this.uploadProgress = 0;
    this.uploadMessage = '';
    this.activeJob = null;
    this.jobSub?.unsubscribe();
  }

  /** Poll /jobs/{id} every 1s until terminal state */
  private pollJobStatus(jobId: string, filename: string): void {
    let notifiedProcessing = false;

    this.jobSub = interval(1000)
      .pipe(
        switchMap(() => this.api.getJob(jobId).pipe(catchError(() => of(null)))),
        takeWhile((job) => {
          if (!job) return true;  // keep polling on transient errors
          return job.status !== 'completed' && job.status !== 'failed';
        }, true),
      )
      .subscribe((job) => {
        if (!job) return;
        this.activeJob = job;

        if (job.status === 'processing' && !notifiedProcessing) {
          notifiedProcessing = true;
          this.uploadMessage = `Processing — ${job.total_frames} frames`;
          this.notif.info('Processing Started', `${filename} — ${job.total_frames} frames to analyse`);
        } else if (job.status === 'processing') {
          this.uploadMessage = `Processing — ${job.progress_pct}% (${job.processed_frames}/${job.total_frames})`;
        }

        if (job.status === 'completed') {
          this.uploadMessage = `✓ Completed — ${job.detections_found} detections in ${job.processed_frames} frames`;
          this.notif.success('Job Completed', `${filename} — ${job.detections_found} detections found`);
        } else if (job.status === 'failed') {
          this.uploadStatus = 'error';
          this.uploadMessage = `✗ Failed — ${job.error || 'unknown error'}`;
          this.notif.error('Job Failed', `${filename} — ${job.error || 'unknown error'}`);
        }
      });
  }

  /** Helper for template progress */
  get jobProgress(): number {
    return this.activeJob?.progress_pct ?? 0;
  }
}
