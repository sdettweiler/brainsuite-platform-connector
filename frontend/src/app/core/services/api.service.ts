import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getScoringStatus(assetIds: string[]): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/scoring/status`, {
      params: new HttpParams().set('asset_ids', assetIds.join(',')),
    });
  }

  rescoreAsset(assetId: string): Observable<any> {
    return this.http.post<any>(`${this.base}/scoring/${assetId}/rescore`, {});
  }

  getScoreDetail(assetId: string): Observable<any> {
    return this.http.get<any>(`${this.base}/scoring/${assetId}`);
  }

  get<T>(path: string, params?: Record<string, any>): Observable<T> {
    let httpParams = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== null && v !== undefined) {
          if (Array.isArray(v)) {
            v.forEach(item => {
              httpParams = httpParams.append(k, String(item));
            });
          } else {
            httpParams = httpParams.set(k, String(v));
          }
        }
      });
    }
    return this.http.get<T>(`${this.base}${path}`, { params: httpParams });
  }

  post<T>(path: string, body: any): Observable<T> {
    return this.http.post<T>(`${this.base}${path}`, body);
  }

  patch<T>(path: string, body: any): Observable<T> {
    return this.http.patch<T>(`${this.base}${path}`, body);
  }

  delete<T>(path: string): Observable<T> {
    return this.http.delete<T>(`${this.base}${path}`);
  }

  put<T>(path: string, body: any): Observable<T> {
    return this.http.put<T>(`${this.base}${path}`, body);
  }

  download(path: string, body: any): Observable<Blob> {
    return this.http.post(`${this.base}${path}`, body, { responseType: 'blob' });
  }

  exportData(payload: any): Promise<Blob> {
    return this.http.post(`${this.base}/assets/export`, payload, { responseType: 'blob' }).toPromise() as Promise<Blob>;
  }

  getScoreTrend(params: { date_from: string; date_to: string; platforms?: string }): Observable<any> {
    return this.http.get(`${this.base}/dashboard/score-trend`, { params: params as any });
  }
}
