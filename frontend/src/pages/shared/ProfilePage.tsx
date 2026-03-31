import { User, Mail, Phone, Calendar, Globe, Shield, Clock } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { Card, CardHeader } from '@/components/ui/Card';
import { formatDate, formatRelativeTime, getInitials } from '@/utils/format';

export function ProfilePage() {
  const { user } = useAuth();

  if (!user) return null;

  const fields = [
    { icon: <Mail    className="h-4 w-4" />, label: 'Email',        value: user.email                                         },
    { icon: <User    className="h-4 w-4" />, label: 'Username',     value: user.username                                      },
    { icon: <Phone   className="h-4 w-4" />, label: 'Phone',        value: user.phone_number ?? '—'                           },
    { icon: <Calendar className="h-4 w-4" />,label: 'Date of Birth',value: user.date_of_birth ? formatDate(user.date_of_birth) : '—' },
    { icon: <Globe   className="h-4 w-4" />, label: 'Nationality',  value: user.nationality ?? '—'                            },
    { icon: <Shield  className="h-4 w-4" />, label: 'Role',         value: user.role.charAt(0).toUpperCase() + user.role.slice(1) },
    { icon: <Clock   className="h-4 w-4" />, label: 'Member Since', value: formatDate(user.created_at)                        },
    { icon: <Clock   className="h-4 w-4" />, label: 'Last Login',   value: user.last_login_at ? formatRelativeTime(user.last_login_at) : '—' },
  ];

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Profile</h1>
        <p className="mt-1 text-sm text-neutral-500">Your account information and details.</p>
      </div>

      {/* Avatar card */}
      <Card>
        <div className="flex items-center gap-6">
          <div className="h-20 w-20 rounded-2xl bg-primary-600 flex items-center justify-center text-white text-2xl font-bold shrink-0">
            {getInitials(user.full_name)}
          </div>
          <div>
            <h2 className="text-xl font-bold text-neutral-900">{user.full_name}</h2>
            <p className="text-sm text-neutral-500">{user.email}</p>
            <div className="flex items-center gap-2 mt-2">
              <span
                className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                  user.status === 'active'
                    ? 'bg-success-100 text-success-700'
                    : 'bg-neutral-100 text-neutral-600'
                }`}
              >
                {user.status.charAt(0).toUpperCase() + user.status.slice(1)}
              </span>
              {user.is_email_verified && (
                <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-primary-100 text-primary-700">
                  Verified
                </span>
              )}
              <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-neutral-100 text-neutral-600 capitalize">
                {user.role}
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* Details */}
      <Card>
        <CardHeader title="Account Details" subtitle="Your personal information on file" />
        <dl className="space-y-4">
          {fields.map((f) => (
            <div
              key={f.label}
              className="flex items-center gap-4 py-3 border-b border-neutral-100 last:border-0"
            >
              <span className="text-neutral-400 shrink-0">{f.icon}</span>
              <dt className="w-32 text-sm text-neutral-500 shrink-0">{f.label}</dt>
              <dd className="text-sm font-medium text-neutral-900 flex-1 truncate">{f.value}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <p className="text-xs text-neutral-400 text-center">
        To update your profile information, please contact your administrator.
      </p>
    </div>
  );
}
