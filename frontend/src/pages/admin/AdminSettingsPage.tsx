import { Bell, Shield, Database, Mail, Globe, ChevronRight } from 'lucide-react';
import { Card, CardHeader } from '@/components/ui/Card';

const SETTING_SECTIONS = [
  {
    icon:  <Shield className="h-5 w-5 text-primary-600" />,
    title: 'Security',
    description: 'Manage access control, two-factor authentication, and session policies.',
    items: ['Password policy', 'MFA settings', 'Session timeout', 'IP allowlist'],
  },
  {
    icon:  <Bell className="h-5 w-5 text-warning-600" />,
    title: 'Notifications',
    description: 'Configure email and system alerts for KYC events.',
    items: ['Submission alerts', 'Review reminders', 'Rejection notifications', 'System alerts'],
  },
  {
    icon:  <Mail className="h-5 w-5 text-success-600" />,
    title: 'Email Templates',
    description: 'Customize automated email messages sent to applicants.',
    items: ['Approval email', 'Rejection email', 'Pending review email', 'Welcome email'],
  },
  {
    icon:  <Globe className="h-5 w-5 text-purple-600" />,
    title: 'Integrations',
    description: 'Connect with third-party services and APIs.',
    items: ['Webhook endpoints', 'API keys', 'OAuth providers', 'Data exports'],
  },
  {
    icon:  <Database className="h-5 w-5 text-neutral-600" />,
    title: 'Data & Retention',
    description: 'Configure data retention policies and compliance settings.',
    items: ['Retention period', 'GDPR compliance', 'Data anonymization', 'Audit log retention'],
  },
];

export function AdminSettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Settings</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Platform configuration and administrative preferences.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {SETTING_SECTIONS.map((section) => (
          <Card key={section.title}>
            <div className="flex items-start gap-4 mb-4">
              <div className="p-2.5 bg-neutral-50 rounded-xl border border-neutral-200">
                {section.icon}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-neutral-900">{section.title}</h3>
                <p className="text-xs text-neutral-500 mt-0.5">{section.description}</p>
              </div>
            </div>
            <ul className="space-y-1">
              {section.items.map((item) => (
                <li key={item}>
                  <button className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm text-neutral-700 hover:bg-neutral-50 transition-colors group">
                    <span>{item}</span>
                    <ChevronRight className="h-3.5 w-3.5 text-neutral-300 group-hover:text-neutral-500 transition-colors" />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader title="Platform Information" subtitle="Current system configuration" />
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
          {[
            { label: 'Version',      value: '1.0.0'            },
            { label: 'Environment',  value: 'Production'       },
            { label: 'Region',       value: 'US-East'          },
            { label: 'API Version',  value: 'v1'               },
            { label: 'Last Updated', value: 'Mar 2026'         },
            { label: 'Support',      value: 'admin@kyc.com'    },
          ].map((info) => (
            <div key={info.label} className="p-3 bg-neutral-50 rounded-lg">
              <p className="text-xs text-neutral-500">{info.label}</p>
              <p className="font-medium text-neutral-900 mt-0.5">{info.value}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
