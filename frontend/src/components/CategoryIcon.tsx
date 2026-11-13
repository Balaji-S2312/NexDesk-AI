import React from 'react';
import {
  AppWindow,
  HelpCircle,
  KeyRound,
  Mail,
  Monitor,
  ShieldAlert,
  Wifi,
} from 'lucide-react';
import { TicketCategoryValue } from '../types/ticket';

interface CategoryIconProps {
  category: TicketCategoryValue | string;
  className?: string;
}

export const CategoryIcon: React.FC<CategoryIconProps> = ({
  category,
  className = 'w-4 h-4 text-[#087E8B]',
}) => {
  switch (category) {
    case 'hardware':
      return <Monitor className={className} aria-hidden="true" />;
    case 'software':
      return <AppWindow className={className} aria-hidden="true" />;
    case 'network':
      return <Wifi className={className} aria-hidden="true" />;
    case 'access_management':
      return <KeyRound className={className} aria-hidden="true" />;
    case 'email':
      return <Mail className={className} aria-hidden="true" />;
    case 'security':
      return <ShieldAlert className={className} aria-hidden="true" />;
    default:
      return <HelpCircle className={className} aria-hidden="true" />;
  }
};
