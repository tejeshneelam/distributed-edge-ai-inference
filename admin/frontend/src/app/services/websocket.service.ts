import { Injectable, OnDestroy } from '@angular/core';
import { Subject } from 'rxjs';

const WS_URL = 'ws://10.12.225.106:8001/ws/cameras';
const RECONNECT_DELAY_MS = 3000;

@Injectable({ providedIn: 'root' })
export class WebsocketService implements OnDestroy {
  readonly messages$ = new Subject<{ type: string; data: unknown }>();

  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private destroyed = false;

  constructor() {
    this.connect();
  }

  private connect(): void {
    if (this.destroyed) return;

    this.ws = new WebSocket(WS_URL);

    this.ws.onopen = () => {
      console.log('[WS] Connected to', WS_URL);
    };

    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        this.messages$.next(payload);
      } catch {
        // ignore malformed frames
      }
    };

    this.ws.onerror = (err) => {
      console.warn('[WS] Error', err);
    };

    this.ws.onclose = () => {
      console.log('[WS] Closed. Reconnecting in', RECONNECT_DELAY_MS, 'ms…');
      if (!this.destroyed) {
        this.reconnectTimer = setTimeout(() => this.connect(), RECONNECT_DELAY_MS);
      }
    };
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.messages$.complete();
  }
}
