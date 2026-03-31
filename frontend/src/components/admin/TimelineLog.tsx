/**
 * TimelineLog
 *
 * Renders an ordered journey log / audit trail for a KYC case.
 * Shows each event with its type icon, title, detail, actor, and timestamp.
 */

import React from 'react';
import {
  Play,
  CheckCircle2,
  XCircle,
  AlertCircle,
  User,
  FileText,
  Zap,
  Clock,
} from 'lucide-react';
import { TimelineEvent } from '@/services/admin.service';

// ─── Helpers ────────────────────────────────────────────────────────────────

function eventIcon(eventType: string) {
  if (eventType.includes('STARTED')) return <Play className="w-3.5 h-3.5 text-blue-500" />;
  if (eventType.includes('COMPLETED')) return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />;
  if (eventType.includes('FAILED')) return <XCircle className="w-3.5 h-3.5 text-red-500" />;
  if (eventType === 'ADMIN_DECISION') return <User className="w-3.5 h-3.5 text-purple-500" />;
  if (eventType === 'REPORT_GENERATED') return <FileText className="w-3.5 h-3.5 text-teal-500" />;
  if (eventType === 'WORKFLOW_STARTED') return <Zap className="w-3.5 h-3.5 text-blue-500" />;
  if (eventType === 'ADMIN_NOTES_SAVED') return <FileText className="w-3.5 h-3.5 text-amber-500" />;
  return <AlertCircle className="w-3.5 h-3.5 text-neutral-400" />;
}

function eventColor(eventType: string) {
  if (eventType.includes('COMPLETED') || eventType === 'REPORT_GENERATED') return 'bg-emerald-50 border-emerald-200';
  if (eventType.includes('FAILED')) return 'bg-red-50 border-red-200';
  if (eventType.includes('STARTED') || eventType === 'WORKFLOW_STARTED') return 'bg-blue-50 border-blue-200';
  if (eventType === 'ADMIN_DECISION') return 'bg-purple-50 border-purple-200';
  return 'bg-neutral-50 border-neutral-200';
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

// ─── Component ───────────────────────────────────────────────────────────────

interface TimelineLogProps {
  events: TimelineEvent[];
  isLoading?: boolean;
}

export function TimelineLog({ events, isLoading }: TimelineLogProps) {
  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-neutral-200 p-5">
        <h3 className="font-semibold text-neutral-800 mb-3">Journey Log</h3>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="animate-pulse flex gap-3">
              <div className="w-6 h-6 bg-neutral-200 rounded-full flex-shrink-0" />
              <div className="flex-1 space-y-1">
                <div className="h-3 bg-neutral-200 rounded w-3/4" />
                <div className="h-2 bg-neutral-100 rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!events.length) {
    return (
      <div className="bg-white rounded-2xl border border-neutral-200 p-5">
        <h3 className="font-semibold text-neutral-800 mb-3">Journey Log</h3>
        <div className="text-center py-8 text-neutral-400">
          <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No events yet. Start the verification workflow.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <h3 className="font-semibold text-neutral-800 mb-4">Journey Log</h3>
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-2.5 top-0 bottom-0 w-0.5 bg-neutral-100" />

        <div className="space-y-3">
          {events.map((event, idx) => (
            <div key={event.id || idx} className="flex gap-3 relative">
              {/* Dot */}
              <div className={`flex-shrink-0 w-5 h-5 rounded-full border flex items-center justify-center z-10 bg-white ${eventColor(event.event_type)}`}>
                {eventIcon(event.event_type)}
              </div>

              {/* Content */}
              <div className={`flex-1 rounded-lg border p-2.5 text-xs ${eventColor(event.event_type)}`}>
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium text-neutral-800">{event.event_title}</span>
                  <span className="text-neutral-400 whitespace-nowrap flex-shrink-0">
                    {formatTime(event.occurred_at)}
                  </span>
                </div>
                {event.event_detail && (
                  <p className="mt-0.5 text-neutral-600 line-clamp-2">{event.event_detail}</p>
                )}
                {event.actor && (
                  <p className="mt-0.5 text-neutral-400 flex items-center gap-1">
                    <User className="w-2.5 h-2.5" />
                    {event.actor}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
