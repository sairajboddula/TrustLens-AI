import { useState } from 'react';
import { Lock, Bell, Eye, EyeOff } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import toast from 'react-hot-toast';
import { authService } from '@/services/auth.service';
import { Card, CardHeader } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

const passwordSchema = z
  .object({
    current_password:     z.string().min(1, 'Current password is required.'),
    new_password:         z.string().min(8, 'New password must be at least 8 characters.'),
    confirm_new_password: z.string().min(1, 'Please confirm your new password.'),
  })
  .refine((d) => d.new_password === d.confirm_new_password, {
    message: 'Passwords do not match.',
    path:    ['confirm_new_password'],
  });

type PasswordForm = z.infer<typeof passwordSchema>;

function ChangePasswordCard() {
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew,     setShowNew]     = useState(false);
  const [loading,     setLoading]     = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PasswordForm>({ resolver: zodResolver(passwordSchema) });

  const onSubmit = async (data: PasswordForm) => {
    setLoading(true);
    try {
      await authService.changePassword(data.current_password, data.new_password);
      toast.success('Password changed successfully.');
      reset();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to change password.';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader
        title="Change Password"
        subtitle="Update your account password. Use a strong, unique password."
      />
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Current Password"
          type={showCurrent ? 'text' : 'password'}
          autoComplete="current-password"
          error={errors.current_password?.message}
          rightElement={
            <button type="button" onClick={() => setShowCurrent((v) => !v)}>
              {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          }
          {...register('current_password')}
        />
        <Input
          label="New Password"
          type={showNew ? 'text' : 'password'}
          autoComplete="new-password"
          error={errors.new_password?.message}
          rightElement={
            <button type="button" onClick={() => setShowNew((v) => !v)}>
              {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          }
          {...register('new_password')}
        />
        <Input
          label="Confirm New Password"
          type="password"
          autoComplete="new-password"
          error={errors.confirm_new_password?.message}
          {...register('confirm_new_password')}
        />
        <div className="pt-1">
          <Button type="submit" loading={loading}>
            Update Password
          </Button>
        </div>
      </form>
    </Card>
  );
}

export function SettingsPage() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Settings</h1>
        <p className="mt-1 text-sm text-neutral-500">Manage your account preferences.</p>
      </div>

      <ChangePasswordCard />

      {/* Notification preferences (display-only for demo) */}
      <Card>
        <div className="flex items-center gap-3 mb-4">
          <Bell className="h-5 w-5 text-warning-600" />
          <h3 className="text-sm font-semibold text-neutral-900">Notification Preferences</h3>
        </div>
        <div className="space-y-3">
          {[
            { label: 'Email me when my KYC status changes',    checked: true  },
            { label: 'Email me when additional info is needed', checked: true  },
            { label: 'Marketing and platform updates',          checked: false },
          ].map((pref) => (
            <label key={pref.label} className="flex items-center justify-between py-2 cursor-pointer group">
              <span className="text-sm text-neutral-700">{pref.label}</span>
              <div
                className={`w-10 h-5 rounded-full transition-colors ${
                  pref.checked ? 'bg-primary-600' : 'bg-neutral-200'
                }`}
              >
                <div
                  className={`h-4 w-4 bg-white rounded-full m-0.5 transition-transform shadow-sm ${
                    pref.checked ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </div>
            </label>
          ))}
        </div>
        <p className="text-xs text-neutral-400 mt-3">
          Notification preference changes take effect immediately.
        </p>
      </Card>

      {/* Security info */}
      <Card>
        <div className="flex items-center gap-3 mb-4">
          <Lock className="h-5 w-5 text-primary-600" />
          <h3 className="text-sm font-semibold text-neutral-900">Security</h3>
        </div>
        <div className="space-y-3 text-sm text-neutral-600">
          <p>Your account is protected with secure JWT-based authentication. Tokens expire automatically.</p>
          <p>For security concerns or to request account deletion, please contact support.</p>
        </div>
      </Card>
    </div>
  );
}
