import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { NotificationService, Toast } from '../../services/notification.service';

@Component({
  selector: 'app-toast',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="toast-container">
      <div *ngFor="let t of toasts"
           class="toast"
           [class]="'toast toast-' + t.type"
           (click)="dismiss(t.id)">
        <span class="toast-icon">{{ icon(t.type) }}</span>
        <div class="toast-body">
          <span class="toast-title">{{ t.title }}</span>
          <span class="toast-msg">{{ t.message }}</span>
        </div>
        <span class="toast-close">&times;</span>
      </div>
    </div>
  `,
  styles: [`
    .toast-container {
      position: fixed;
      top: 56px;
      right: 16px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-width: 380px;
      pointer-events: none;
    }

    .toast {
      pointer-events: auto;
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 10px 14px;
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: 0 4px 14px rgba(0,0,0,0.10);
      cursor: pointer;
      animation: toast-in 0.25s ease;
      transition: opacity 0.2s ease;
    }

    .toast:hover { opacity: 0.85; }

    @keyframes toast-in {
      from { opacity: 0; transform: translateX(30px); }
      to   { opacity: 1; transform: translateX(0); }
    }

    .toast-info    { border-left: 3px solid var(--blue); }
    .toast-success { border-left: 3px solid var(--green); }
    .toast-warning { border-left: 3px solid var(--amber); }
    .toast-error   { border-left: 3px solid var(--red); }

    .toast-icon {
      font-size: 1rem;
      line-height: 1;
      flex-shrink: 0;
      margin-top: 2px;
    }
    .toast-info    .toast-icon { color: var(--blue); }
    .toast-success .toast-icon { color: var(--green); }
    .toast-warning .toast-icon { color: var(--amber); }
    .toast-error   .toast-icon { color: var(--red); }

    .toast-body {
      display: flex;
      flex-direction: column;
      gap: 2px;
      flex: 1;
      min-width: 0;
    }

    .toast-title {
      font-family: var(--font-mono);
      font-size: 0.68rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--silver-1);
    }

    .toast-msg {
      font-size: 0.78rem;
      color: var(--silver-2);
      line-height: 1.4;
      word-break: break-word;
    }

    .toast-close {
      font-size: 1rem;
      color: var(--silver-3);
      cursor: pointer;
      flex-shrink: 0;
      line-height: 1;
    }
  `],
})
export class ToastComponent implements OnInit, OnDestroy {
  toasts: Toast[] = [];
  private sub!: Subscription;

  constructor(private notif: NotificationService) {}

  ngOnInit(): void {
    this.sub = this.notif.toasts$.subscribe((t) => {
      this.toasts.push(t);
      setTimeout(() => this.dismiss(t.id), 6000);
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  dismiss(id: number): void {
    this.toasts = this.toasts.filter((t) => t.id !== id);
  }

  icon(type: string): string {
    switch (type) {
      case 'success': return '✓';
      case 'error':   return '✗';
      case 'warning': return '⚠';
      default:        return 'ℹ';
    }
  }
}
