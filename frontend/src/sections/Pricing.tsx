import React from 'react';
import { Check, Zap, Crown, User } from 'lucide-react';

const tiers = [
  {
    name: 'Free',
    price: '₹0',
    description: 'Perfect for getting started with AI financial tracking.',
    features: ['Basic AI Processing', 'Neural Spend Category', '1 Bank Integration', 'Weekly Summaries'],
    icon: <User className="text-slate-400" size={24} />,
    popular: false,
  },
  {
    name: 'Pro',
    price: '₹1,000',
    description: 'Executive-grade tools for power users and small families.',
    features: ['Everything in Free', 'Predictive Cash Flow', 'Unlimited Integrations', 'Real-time Neural Alerts', 'AI Spending Coach'],
    icon: <Zap size={24} style={{ color: '#00FFFF' }} />,
    popular: true,
  },
  {
    name: 'Elite',
    price: '₹2,500',
    description: 'Full-spectrum wealth management for high-net-worth individuals.',
    features: ['Everything in Pro', 'White-glove Support', 'Tax Optimization Engine', 'Estate Planning Tools', 'Neural Investment Insights'],
    icon: <Crown className="text-purple-400" size={24} />,
    popular: false,
  },
];

interface PricingProps {
  onSelect?: (tier: string) => void;
  loading?: boolean;
}

const Pricing: React.FC<PricingProps> = ({ onSelect, loading }) => {
  return (
    <section id="pricing" className="py-32 px-6 relative overflow-hidden">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-20 space-y-4">
          <span style={{ color: '#00FFFF' }} className="font-bold uppercase tracking-widest text-xs">Investment Plans</span>
          <h2 className="text-5xl md:text-6xl font-black tracking-tight text-white">
            Simple <span style={{ color: '#00FFFF' }}>Pricing</span>.
          </h2>
          <p className="text-slate-400 max-w-xl mx-auto text-lg leading-relaxed">
            Choose the level of intelligence that fits your financial goals. No hidden fees.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 items-stretch">
          {tiers.map((tier, idx) => (
            <div
              key={idx}
              style={{
                background: tier.popular ? 'rgba(0,255,255,0.05)' : 'rgba(255,255,255,0.02)',
                border: tier.popular ? '1px solid rgba(0,255,255,0.3)' : '1px solid rgba(255,255,255,0.05)',
                backdropFilter: 'blur(20px)',
                boxShadow: tier.popular ? '0 30px 60px -12px rgba(0,255,255,0.1)' : 'none',
                transform: tier.popular ? 'translateY(-10px)' : 'none',
              }}
              className="relative rounded-[40px] p-10 flex flex-col hover:-translate-y-3 transition-all duration-500"
            >
              {tier.popular && (
                <div
                  className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 px-4 py-1.5 rounded-full text-xs font-black uppercase tracking-widest"
                  style={{ background: '#00FFFF', color: '#000', boxShadow: '0 0 20px rgba(0,255,255,0.4)' }}
                >
                  Most Popular
                </div>
              )}

              <div className="mb-8 flex items-center justify-between">
                <div className="h-14 w-14 rounded-2xl flex items-center justify-center" style={{ background: tier.popular ? 'rgba(0,255,255,0.2)' : 'rgba(255,255,255,0.05)' }}>
                  {tier.icon}
                </div>
                <span className="text-slate-500 font-bold uppercase tracking-widest text-xs">{tier.name}</span>
              </div>

              <div className="mb-8">
                <span className="text-5xl font-black text-white">{tier.price}</span>
                <span className="text-slate-500 ml-2 font-medium">/month</span>
              </div>

              <p className="text-slate-400 text-sm leading-relaxed mb-8">
                {tier.description}
              </p>

              <div className="space-y-4 mb-10 flex-1">
                {tier.features.map((feature, fIdx) => (
                  <div key={fIdx} className="flex items-center gap-3">
                    <div className="h-5 w-5 rounded-full flex items-center justify-center" style={{ background: tier.popular ? 'rgba(0,255,255,0.2)' : 'rgba(255,255,255,0.05)' }}>
                      <Check size={12} style={{ color: tier.popular ? '#00FFFF' : '#64748b' }} />
                    </div>
                    <span className="text-sm font-medium text-slate-300">{feature}</span>
                  </div>
                ))}
              </div>

              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onSelect && onSelect(tier.name.toLowerCase());
                }}
                disabled={loading}
                style={tier.popular ? {
                  background: '#00FFFF',
                  color: '#000',
                  boxShadow: '0 0 30px rgba(0,255,255,0.3)',
                } : {
                  background: 'rgba(255,255,255,0.05)',
                  color: '#fff',
                  border: '1px solid rgba(255,255,255,0.1)',
                }}
                className="w-full py-4 rounded-2xl font-bold transition-all hover:scale-105 active:scale-95 disabled:opacity-50"
              >
                {loading ? (
                  <span className="animate-spin inline-block w-5 h-5 border-2 border-black/30 border-t-black rounded-full" />
                ) : (
                  tier.name === 'Free' ? 'Get Started' : 'Upgrade to ' + tier.name
                )}
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Pricing;
