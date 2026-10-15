import React from 'react';
import { Scale, ScanText, Search, Bot, MailCheck } from 'lucide-react';

const ICONS = {
  amount_rule: Scale,
  anti_evasion: ScanText,
  ollaya: Bot,
  delivery: MailCheck,
};

export default function StageIcon({ id, size = 22 }) {
  const Icon = ICONS[id] || Search;
  return <Icon size={size} strokeWidth={2.2} aria-hidden="true" />;
}
