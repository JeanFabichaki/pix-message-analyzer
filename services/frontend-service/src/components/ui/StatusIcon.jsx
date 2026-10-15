import React from 'react';
import { Check, Minus, TriangleAlert, ZapOff } from 'lucide-react';

const MAP = {
  pass: Check,
  skip: Minus,
  detect: TriangleAlert,
  error: ZapOff,
};

export default function StatusIcon({ status, size = 18 }) {
  const Icon = MAP[status];
  if (!Icon) return null;
  return <Icon size={size} strokeWidth={2.6} aria-hidden="true" />;
}
