import React from 'react';

export default function Skeleton({ lines = 3, className = '' }) {
  return (
    <div className={`skeleton ${className}`} aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="skeleton__line" style={{ width: `${92 - i * 14}%` }} />
      ))}
    </div>
  );
}
