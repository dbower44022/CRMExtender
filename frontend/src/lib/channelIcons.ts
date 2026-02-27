import {
  Mail,
  MessageCircle,
  Phone,
  Video,
  Users,
  StickyNote,
  type LucideIcon,
} from 'lucide-react'

export const CHANNEL_ICONS: Record<string, LucideIcon> = {
  email: Mail,
  sms: MessageCircle,
  phone: Phone,
  phone_manual: Phone,
  video: Video,
  video_manual: Video,
  in_person: Users,
  note: StickyNote,
}

export const CHANNEL_LABELS: Record<string, string> = {
  email: 'Email',
  sms: 'SMS',
  phone: 'Phone Call',
  phone_manual: 'Phone Call',
  video: 'Video Call',
  video_manual: 'Video Call',
  in_person: 'In Person',
  note: 'Note',
}

/** Full descriptive labels used only in the Full View Identity Card */
export const CHANNEL_TYPE_LABELS: Record<string, string> = {
  email: 'Email Communication',
  sms: 'Text Communication',
  phone: 'Phone Call',
  phone_manual: 'Phone Call',
  video: 'Video Call',
  video_manual: 'Video Call',
  in_person: 'In-Person Meeting',
  note: 'Note',
}
