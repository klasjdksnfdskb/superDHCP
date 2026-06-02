import { ReactNode } from 'react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  trend?: { value: number; label: string };
  color?: string;
}

export default function StatCard({ title, value, subtitle, icon, trend, color }: StatCardProps) {
  return (
    <div className="card" style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>{title}</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: color || 'var(--text-primary)' }}>
            {typeof value === 'number' ? value.toLocaleString() : value}
          </div>
          {subtitle && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{subtitle}</div>
          )}
          {trend && (
            <div style={{ fontSize: 12, marginTop: 8, color: trend.value >= 0 ? 'var(--success)' : 'var(--danger)' }}>
              {trend.value >= 0 ? '↑' : '↓'} {Math.abs(trend.value)}% {trend.label}
            </div>
          )}
        </div>
        {icon && (
          <div style={{ opacity: 0.15, position: 'absolute', right: 16, top: 16 }}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}