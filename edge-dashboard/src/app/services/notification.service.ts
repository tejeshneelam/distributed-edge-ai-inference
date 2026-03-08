import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

export interface Toast {
  id: number;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
}

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private _id = 0;
  readonly toasts$ = new Subject<Toast>();

  info(title: string, message: string): void {
    this.toasts$.next({ id: ++this._id, type: 'info', title, message });
  }

  success(title: string, message: string): void {
    this.toasts$.next({ id: ++this._id, type: 'success', title, message });
  }

  warning(title: string, message: string): void {
    this.toasts$.next({ id: ++this._id, type: 'warning', title, message });
  }

  error(title: string, message: string): void {
    this.toasts$.next({ id: ++this._id, type: 'error', title, message });
  }
}
