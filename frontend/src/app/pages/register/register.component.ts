import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="auth-page">
      <div class="glow-orb orb-1"></div>
      <div class="glow-orb orb-2"></div>

      <div class="auth-card glass-panel">
        <div class="auth-header">
          <div class="brand-badge">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
            <span>DocuMind AI</span>
          </div>
          <h2>Create an account</h2>
          <p>Get started with AI-driven PDF analysis and semantic Q&A</p>
        </div>

        <form (ngSubmit)="onSubmit()" #regForm="ngForm">
          <div class="form-group">
            <label for="email">Email Address</label>
            <input
              type="email"
              id="email"
              name="email"
              class="form-control"
              [(ngModel)]="email"
              #emailModel="ngModel"
              required
              email
              placeholder="name@company.com"
            />
            <span class="form-error" *ngIf="emailModel.invalid && emailModel.touched">
              Please enter a valid email address.
            </span>
          </div>

          <div class="form-group">
            <label for="password">Password</label>
            <input
              type="password"
              id="password"
              name="password"
              class="form-control"
              [(ngModel)]="password"
              #passModel="ngModel"
              required
              minlength="8"
              placeholder="••••••••"
            />
            <span class="form-error" *ngIf="passModel.invalid && passModel.touched">
              Password must be at least 8 characters.
            </span>
          </div>

          <div class="form-group">
            <label for="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              class="form-control"
              [(ngModel)]="confirmPassword"
              #confirmModel="ngModel"
              required
              placeholder="••••••••"
            />
            <span class="form-error" *ngIf="confirmModel.touched && password !== confirmPassword">
              Passwords do not match.
            </span>
          </div>

          <button
            type="submit"
            class="btn btn-primary btn-block"
            [disabled]="regForm.invalid || password !== confirmPassword || isLoading"
          >
            <svg *ngIf="isLoading" class="spinner" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="2" x2="12" y2="6"></line>
              <line x1="12" y1="18" x2="12" y2="22"></line>
              <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
              <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
              <line x1="2" y1="12" x2="6" y2="12"></line>
              <line x1="18" y1="12" x2="22" y2="12"></line>
            </svg>
            <span>{{ isLoading ? 'Creating account...' : 'Create Account' }}</span>
          </button>
        </form>

        <div class="auth-footer">
          <span>Already have an account?</span>
          <a routerLink="/login">Sign in</a>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .auth-page {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      position: relative;
      overflow: hidden;
      background: radial-gradient(circle at 50% 10%, #1e1b4b 0%, var(--bg-primary) 70%);
    }

    .glow-orb {
      position: absolute;
      border-radius: 50%;
      filter: blur(100px);
      pointer-events: none;
      z-index: 0;
    }
    .orb-1 {
      width: 450px;
      height: 450px;
      top: 10%;
      left: 20%;
      background: rgba(99, 102, 241, 0.15);
    }
    .orb-2 {
      width: 350px;
      height: 350px;
      bottom: 10%;
      right: 25%;
      background: rgba(139, 92, 246, 0.12);
    }

    .auth-card {
      width: 100%;
      max-width: 440px;
      padding: 40px;
      position: relative;
      z-index: 1;
    }

    .auth-header {
      text-align: center;
      margin-bottom: 30px;

      .brand-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        background: rgba(99, 102, 241, 0.15);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: var(--radius-full);
        color: #a5b4fc;
        font-weight: 700;
        font-size: 13px;
        margin-bottom: 16px;
      }

      h2 {
        font-size: 26px;
        margin-bottom: 8px;
      }

      p {
        font-size: 14px;
      }
    }

    .btn-block {
      width: 100%;
      margin-top: 10px;
    }

    .auth-footer {
      display: flex;
      justify-content: center;
      gap: 6px;
      margin-top: 24px;
      font-size: 14px;
      color: var(--text-muted);

      a {
        font-weight: 600;
      }
    }
  `]
})
export class RegisterComponent {
  email = '';
  password = '';
  confirmPassword = '';
  isLoading = false;

  private authService = inject(AuthService);
  private toastService = inject(ToastService);
  private router = inject(Router);

  onSubmit() {
    if (!this.email || !this.password || this.password !== this.confirmPassword) return;

    this.isLoading = true;
    this.authService.register({
      email: this.email,
      password: this.password,
      confirmPassword: this.confirmPassword
    }).subscribe({
      next: () => {
        this.isLoading = false;
        this.toastService.success('Account created! Welcome to DocuMind AI.');
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.isLoading = false;
        const msg = err.error?.detail || err.error?.error || 'Registration failed.';
        this.toastService.error(msg);
      }
    });
  }
}
