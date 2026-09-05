import React, { useState } from 'react';
import { User, Rocket, CheckCircle2, ArrowRight } from 'lucide-react';

interface ProfileSelectionProps {
  onSelect: (persona: 'individual' | 'startup') => void;
  loading?: boolean;
}

const ProfileSelection: React.FC<ProfileSelectionProps> = ({ onSelect, loading }) => {
  const [selected, setSelected] = useState<'individual' | 'startup' | null>(null);

  const personas = [
    {
      id: 'individual' as const,
      title: 'Individual',
      subtitle: 'Personal Finance Advisor',
      description: 'Master your personal wealth with AI-driven insights and automated tracking.',
      features: ['Personal Wealth Building', 'Smart Budgeting', 'Individual Investment Insights'],
      icon: <User className="w-8 h-8" />,
      color: 'from-cyan-400 to-blue-500',
    },
    {
      id: 'startup' as const,
      title: 'Startup / Organization',
      subtitle: 'Scalable Growth Engine',
      description: 'Streamline business expenses, payroll, and predict burn rate with neural models.',
      features: ['Business Expense Tracking', 'Burn Rate Forecasting', 'Team Finance Analytics'],
      icon: <Rocket className="w-8 h-8" />,
      color: 'from-emerald-400 to-teal-500',
    }
  ];

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-[#090b14] relative overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyan-500/10 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-600/10 blur-[120px] rounded-full pointer-events-none" />

      <div className="max-w-4xl w-full z-10 space-y-12">
        <div className="text-center space-y-4">
          <h1 className="text-5xl md:text-6xl font-black text-white tracking-tight">
            Who are <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">you?</span>
          </h1>
          <p className="text-slate-400 text-lg max-w-xl mx-auto leading-relaxed">
            Tailor your Co Penny experience by choosing the persona that best describes your needs.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {personas.map((persona) => {
            const isSelected = selected === persona.id;
            return (
              <div
                key={persona.id}
                onClick={() => setSelected(persona.id)}
                className={`group relative p-8 rounded-[32px] border transition-all duration-500 cursor-pointer overflow-hidden ${
                  isSelected 
                    ? 'bg-white/5 border-cyan-400/50 shadow-[0_0_40px_rgba(34,211,238,0.15)] ring-1 ring-cyan-400/30' 
                    : 'bg-white/[0.02] border-white/5 hover:border-white/20 hover:bg-white/[0.04]'
                }`}
              >
                {/* Selection indicator */}
                <div className={`absolute top-6 right-6 transition-all duration-300 ${isSelected ? 'scale-100 opacity-100' : 'scale-0 opacity-0'}`}>
                  <CheckCircle2 className="w-6 h-6 text-cyan-400" />
                </div>

                <div className="space-y-6">
                  {/* Icon */}
                  <div className={`w-16 h-16 rounded-2xl flex items-center justify-center bg-gradient-to-br ${persona.color} p-4 text-black shadow-lg transition-transform duration-500 group-hover:scale-110`}>
                    {persona.icon}
                  </div>

                  <div>
                    <h3 className="text-2xl font-bold text-white group-hover:text-cyan-400 transition-colors">
                      {persona.title}
                    </h3>
                    <p className="text-sm font-semibold uppercase tracking-widest text-slate-500 mt-1">
                      {persona.subtitle}
                    </p>
                  </div>

                  <p className="text-slate-400 leading-relaxed">
                    {persona.description}
                  </p>

                  <ul className="space-y-3 pt-4 border-t border-white/5">
                    {persona.features.map((feature, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm text-slate-300">
                        <div className="w-1.5 h-1.5 rounded-full bg-cyan-400/50" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex justify-center pt-8">
          <button
            onClick={() => selected && onSelect(selected)}
            disabled={!selected || loading}
            className={`group px-12 py-5 rounded-2xl font-black text-xl uppercase tracking-widest transition-all flex items-center gap-3 disabled:opacity-30 disabled:cursor-not-allowed ${
              selected 
                ? 'bg-gradient-to-r from-cyan-400 to-blue-500 text-black shadow-[0_0_30px_rgba(34,211,238,0.4)] hover:scale-105 active:scale-95' 
                : 'bg-white/5 text-slate-500'
            }`}
          >
            {loading ? (
               <span className="animate-spin inline-block w-6 h-6 border-4 border-black/30 border-t-black rounded-full" />
            ) : (
              <>
                Confirm Selection
                <ArrowRight className="w-6 h-6 transition-transform group-hover:translate-x-1" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProfileSelection;
