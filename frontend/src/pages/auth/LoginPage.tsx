import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Shield, Lock, Mail } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import type { LoginRequest } from '@/types';

// ─── Schema ───────────────────────────────────────────────────────────────────

const schema = z.object({
  email:    z.string().email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

type FormData = z.infer<typeof schema>;

// ─── Component ────────────────────────────────────────────────────────────────

export function LoginPage() {
  const { login, isAdmin } = useAuth();
  const navigate            = useNavigate();
  const location            = useLocation();
  const [showPass, setShowPass] = useState(false);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/dashboard';

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    try {
      await login(data as LoginRequest);
      const dest = isAdmin ? '/admin/dashboard' : from;
      navigate(dest, { replace: true });
      toast.success('Welcome back!');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string; message?: string } } })
          ?.response?.data?.detail ??
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        'Invalid email or password.';
      setError('root', { message: msg });
    }
  };

  return (
    <div className="min-h-screen flex bg-neutral-50">
      {/* Left panel – branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary-700 via-primary-600 to-brand-600 flex-col justify-between p-12">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-white/20 flex items-center justify-center">
            <Shield className="h-5 w-5 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-xl font-bold text-white">KYC Platform</span>
        </div>

        <div className="space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight">
            Secure Identity<br />Verification
          </h1>
          <p className="text-primary-200 text-lg leading-relaxed max-w-md">
            Verify your identity quickly and securely using our AI-powered KYC solution. Compliant, fast, and reliable.
          </p>

          <div className="grid grid-cols-3 gap-4 pt-4">
            {[
              { value: '99.9%', label: 'Uptime'    },
              { value: '<2min', label: 'Avg Review' },
              { value: 'SOC 2', label: 'Certified'  },
            ].map((stat) => (
              <div key={stat.label} className="bg-white/10 rounded-xl p-4 text-center">
                <p className="text-xl font-bold text-white">{stat.value}</p>
                <p className="text-xs text-primary-200 mt-1">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="text-primary-300 text-sm">
          &copy; {new Date().getFullYear()} KYC Platform. All rights reserved.
        </p>
      </div>

      {/* Right panel – form */}
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
            <h2 className="text-2xl font-bold text-neutral-900">Sign in to your account</h2>
            <p className="mt-1.5 text-sm text-neutral-500">
              Don't have an account?{' '}
              <Link to="/register" className="text-primary-600 font-medium hover:underline">
                Create one
              </Link>
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {/* Root error */}
            {errors.root && (
              <div className="p-3 bg-danger-50 border border-danger-200 rounded-xl text-sm text-danger-700">
                {errors.root.message}
              </div>
            )}

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

            <Input
              label="Password"
              type={showPass ? 'text' : 'password'}
              required
              autoComplete="current-password"
              placeholder="••••••••"
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

            <div className="flex items-center justify-end">
              <Link
                to="/forgot-password"
                className="text-sm text-primary-600 hover:underline font-medium"
              >
                Forgot password?
              </Link>
            </div>

            <Button
              type="submit"
              fullWidth
              size="lg"
              loading={isSubmitting}
            >
              Sign in
            </Button>
          </form>

          {/* Demo credentials hint */}
          <div className="mt-6 p-4 bg-neutral-100 rounded-xl text-xs text-neutral-500 space-y-1">
            <p className="font-medium text-neutral-600">Demo credentials</p>
            <p>Admin: admin@kyc.com / Admin@KYC2024!</p>
            <p>User:&nbsp; user@kyc.com &nbsp;/ User@KYC2024!</p>
          </div>
        </div>
      </div>
    </div>
  );
}
