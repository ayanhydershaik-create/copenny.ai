import React from 'react';
import { Shield, Zap, TrendingUp, PieChart, Bell, Brain } from 'lucide-react';

const features = [
  {
    title: 'AI Spending Analysis',
    description: 'Real-time neural scanning of every transaction for deep behavioral insights.',
    icon: <Brain className="text-cyan-vibrant" size={24} />,
    large: true,
  },
  {
    title: 'Smart Alerts',
    description: 'Instant notifications for unusual activity or budget deviations.',
    icon: <Bell className="text-cyan-vibrant" size={24} />,
    large: false,
  },
  {
    title: 'Neural Forecasting',
    description: 'Predictive modeling of your future cash flow with 99.8% accuracy.',
    icon: <TrendingUp className="text-cyan-vibrant" size={24} />,
    large: false,
  },
  {
    title: 'Elite Security',
    description: 'Bank-grade encryption and privacy-first data handling at every layer.',
    icon: <Shield className="text-cyan-vibrant" size={24} />,
    large: false,
  },
  {
    title: 'Budget Optimization',
    description: 'Automated strategies to reduce waste and maximize your savings rate.',
    icon: <Zap className="text-cyan-vibrant" size={24} />,
    large: false,
  },
  {
    title: 'Wealth Visualization',
    description: 'Executive-level dashboards that turn raw data into actionable clarity.',
    icon: <PieChart className="text-cyan-vibrant" size={24} />,
    large: true,
  },
];

const Features: React.FC = () => {
  return (
    <section id="features" className="py-32 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-20 space-y-4">
          <h2 className="text-4xl md:text-5xl font-black tracking-tight text-white">
            Absolute <span style={{ color: '#00FFFF' }}>Intelligence</span>
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto text-lg">
            Powerful financial tools powered by advanced AI to give you total control over your money.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, idx) => (
            <div
              key={idx}
              style={{
                background: 'rgba(255,255,255,0.03)',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(255,255,255,0.05)',
                animationDelay: `${idx * 0.1}s`,
              }}
              className={`rounded-[32px] p-8 flex flex-col gap-6 hover:border-cyan-vibrant/30 transition-all duration-500 group relative overflow-hidden ${
                feature.large && idx === 0 ? 'lg:col-span-2' : ''
              } ${
                feature.large && idx === 5 ? 'lg:col-span-2' : ''
              }`}
            >
              <div className="absolute -right-20 -top-20 w-40 h-40 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition-opacity" style={{ background: 'rgba(0,255,255,0.05)' }} />
              
              <div className="h-14 w-14 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-all" style={{ background: 'rgba(0,255,255,0.08)' }}>
                {feature.icon}
              </div>
              
              <div>
                <h3 className="text-xl font-bold text-white mb-2 group-hover:text-cyan-vibrant transition-colors">
                  {feature.title}
                </h3>
                <p className="text-slate-400 text-sm leading-relaxed">
                  {feature.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Features;
