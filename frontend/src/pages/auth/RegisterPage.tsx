import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Shield, User, Mail, Lock } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { cn } from '@/utils/cn';
import type { RegisterRequest } from '@/types';

// ─── Schema ───────────────────────────────────────────────────────────────────

const schema = z
  .object({
    first_name:       z.string().min(1, 'First name is required').max(100),
    last_name:        z.string().min(1, 'Last name is required').max(100),
    email:            z.string().email('Please enter a valid email address'),
    password:         z.string().min(8, 'Password must be at least 8 characters'),
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: 'Passwords do not match',
    path:    ['confirm_password'],
  });

type FormData = z.infer<typeof schema>;

/** Generate a username slug from first + last name + random suffix. */
function generateUsername(firstName: string, lastName: string): string {
  const base = `${firstName}${lastName}`.toLowerCase().replace(/[^a-z0-9_-]/g, '');
  const suffix = Math.floor(Math.random() * 9000) + 1000;
  return `${base}${suffix}`;
}

// ─── Password strength ────────────────────────────────────────────────────────

function calcStrength(password: string): { score: number; label: string; color: string } {
  if (!password) return { score: 0, label: '',        color: '' };
  let score = 0;
  if (password.length >= 8)           score++;
  if (password.length >= 12)          score++;
  if (/[A-Z]/.test(password))         score++;
  if (/[0-9]/.test(password))         score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  const levels = [
    { label: 'Very Weak', color: 'bg-danger-500'  },
    { label: 'Weak',      color: 'bg-warning-500' },
    { label: 'Fair',      color: 'bg-yellow-400'  },
    { label: 'Good',      color: 'bg-success-400' },
    { label: 'Strong',    color: 'bg-success-600' },
  ];

  return { score, ...levels[score - 1] ?? levels[0] };
}

function PasswordStrength({ password }: { password: string }) {
  const { score, label, color } = calcStrength(password);
  if (!password) return null;

  return (
    <div className="space-y-1.5">
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className={cn(
              'h-1.5 flex-1 rounded-full transition-colors',
              i <= score ? color : 'bg-neutral-200',
            )}
          />
        ))}
      </div>
      <p className={cn('text-xs font-medium', score >= 4 ? 'text-success-600' : 'text-warning-600')}>
        {label}
      </p>
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function RegisterPage() {
  const { register: authRegister } = useAuth();
  const navigate = useNavigate();
  const [showPass,    setShowPass]    = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const password = watch('password', '');

  const onSubmit = async (data: FormData) => {
    try {
      const payload: RegisterRequest = {
        email:            data.email,
        username:         generateUsername(data.first_name, data.last_name),
        first_name:       data.first_name,
        last_name:        data.last_name,
        password:         data.password,
        confirm_password: data.confirm_password,
      };
      await authRegister(payload);
      navigate('/dashboard', { replace: true });
      toast.success('Account created! Welcome aboard.');
    } catch (err: unknown) {
      const errData = (err as { response?: { data?: { detail?: string; message?: string } } })?.response?.data;
      const msg = errData?.detail ?? errData?.message ?? 'Registration failed. Please try again.';
      setError('root', { message: String(msg) });
    }
  };

  return (
    <div className="min-h-screen flex bg-neutral-50">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary-700 via-primary-600 to-brand-600 flex-col justify-between p-12">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-white/20 flex items-center justify-center">
            <Shield className="h-5 w-5 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-xl font-bold text-white">KYC Platform</span>
        </div>

        <div className="space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight">
            Start Your<br />Verification Journey
          </h1>
          <p className="text-primary-200 text-lg leading-relaxed max-w-md">
            Create your account and complete KYC verification in minutes. Powered by advanced AI and secure document processing.
          </p>
          <ul className="space-y-3">
            {[
              'AI-powered document verification',
              'Real-time status tracking',
              'Bank-grade security & encryption',
              'Compliance with global KYC standards',
            ].map((item) => (
              <li key={item} className="flex items-center gap-3 text-primary-100 text-sm">
                <div className="h-5 w-5 rounded-full bg-white/20 flex items-center justify-center shrink-0">
                  <span className="text-white text-xs">✓</span>
                </div>
                {item}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-primary-300 text-sm">
          &copy; {new Date().getFullYear()} KYC Platform.
        </p>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="h-8 w-8 rounded-lg bg-primary-600 flex items-center justify-center">
              <Shield className="h-4 w-4 text-white" />
            </div>
            <span className="text-lg font-bold text-neutral-900">KYC Platform</span>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-neutral-900">Create your account</h2>
            <p className="mt-1.5 text-sm text-neutral-500">
              Already have an account?{' '}
              <Link to="/login" className="text-primary-600 font-medium hover:underline">
                Sign in
              </Link>
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {errors.root && (
              <div className="p-3 bg-danger-50 border border-danger-200 rounded-xl text-sm text-danger-700">
                {errors.root.message}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <Input
                label="First Name"
                required
                autoComplete="given-name"
                placeholder="John"
                leftElement={<User className="h-4 w-4" />}
                error={errors.first_name?.message}
                {...register('first_name')}
              />
              <Input
                label="Last Name"
                required
                autoComplete="family-name"
                placeholder="Doe"
                error={errors.last_name?.message}
                {...register('last_name')}
              />
            </div>

            <Input
              label="Email address"
              type="email"
              required
              autoComplete="email"
              placeholder="you@company.com"
              leftElement={<Mail className="h-4 w-4" />}
              error={errors.email?.message}
              {...register('email')}
            />

            <div className="space-y-2">
              <Input
                label="Password"
                type={showPass ? 'text' : 'password'}
                required
                autoComplete="new-password"
                placeholder="Min 8 characters"
                leftElement={<Lock className="h-4 w-4" />}
                rightElement={
                  <button
                    type="button"
                    onClick={() => setShowPass((v) => !v)}
                    className="text-neutral-400 hover:text-neutral-600"
                    tabIndex={-1}
                  >
                    {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                }
                error={errors.password?.message}
                {...register('password')}
              />
              <PasswordStrength password={password} />
            </div>

            <Input
              label="Confirm Password"
              type={showConfirm ? 'text' : 'password'}
              required
              autoComplete="new-password"
              placeholder="Re-enter password"
              leftElement={<Lock className="h-4 w-4" />}
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="text-neutral-400 hover:text-neutral-600"
                  tabIndex={-1}
                >
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
              error={errors.confirm_password?.message}
              {...register('confirm_password')}
            />

            <p className="text-xs text-neutral-400">
              By creating an account you agree to our{' '}
              <a href="#" className="text-primary-600 hover:underline">Terms of Service</a>
              {' '}and{' '}
              <a href="#" className="text-primary-600 hover:underline">Privacy Policy</a>.
            </p>

            <Button
              type="submit"
              fullWidth
              size="lg"
              loading={isSubmitting}
            >
              Create Account
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
