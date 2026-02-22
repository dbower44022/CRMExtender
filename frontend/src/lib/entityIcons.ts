import {
  Users,
  Building2,
  MessageSquare,
  Mail,
  Calendar,
  FolderKanban,
  Link2,
  StickyNote,
  type LucideIcon,
} from 'lucide-react'

export const ENTITY_ICONS: Record<string, LucideIcon> = {
  contact: Users,
  company: Building2,
  conversation: MessageSquare,
  communication: Mail,
  event: Calendar,
  project: FolderKanban,
  relationship: Link2,
  note: StickyNote,
}

export const ENTITY_LABELS: Record<string, string> = {
  contact: 'Contacts',
  company: 'Companies',
  conversation: 'Conversations',
  communication: 'Communications',
  event: 'Events',
  project: 'Projects',
  relationship: 'Relationships',
  note: 'Notes',
}
