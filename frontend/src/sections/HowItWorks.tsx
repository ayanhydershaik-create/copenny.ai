import React from 'react';
import { MousePointer2, Cpu, LineChart } from 'lucide-react';

const steps = [
  {
    title: 'Connect & Upload',
    description: 'Securely link your accounts or upload statement files for processing.',
    icon: <MousePointer2 size={32} />,
  },
  {
    title: 'Neural Analysis',
    description: 'Our AI engine scans and categorizes every detail with robotic precision.',
    icon: <Cpu size={32} />,
  },
  {
    title: 'Wealth Roadmap',
    description: 'Receive personalized, actionable intelligence to grow your net worth.',
    icon: <LineChart size={32} />,
  },
];

const HowItWorks: React.FC = () => {
  return (
    <section id="how-it-works" className="py-24 px-6 relative overflow-hidden">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row items-end justify-between mb-20 gap-8">
          <div className="max-w-xl space-y-4">
            <span style={{ color: '#00FFFF' }} className="font-bold uppercase tracking-widest text-xs">The Process</span>
            <h2 className="text-4xl md:text-5xl font-black tracking-tight text-white leading-tight">
              From Data to <br />
              <span style={{ color: '#00FFFF' }}>Financial Freedom</span>
            </h2>
          </div>
          <p className="text-slate-400 max-w-sm text-lg font-medium">
            Three simple steps to unlock the full potential of your master economy.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-12 relative">
          {/* Connecting Line (Visible on desktop) */}
          <div className="hidden md:block absolute top-[60px] left-[15%] right-[15%] h-px" style={{ background: 'linear-gradient(to right, transparent, rgba(255,255,255,0.1), transparent)' }} />
          
          {steps.map((step, idx) => (
            <div key={idx} className="relative flex flex-col items-center text-center gap-6 group">
              <div 
                className="h-28 w-28 rounded-3xl border transition-transform duration-500 group-hover:scale-110 group-hover:rotate-3 flex items-center justify-center text-white"
                style={{
                  background: 'rgba(0,255,255,0.08)',
                  border: '1px solid rgba(0,255,255,0.15)',
                  boxShadow: '0 20px 60px -12px rgba(0,255,255,0.1)',
                }}
              >
                {step.icon}
              </div>
              
              <div className="space-y-3">
                <span style={{ color: '#00FFFF' }} className="font-black text-xs uppercase tracking-[0.2em]">Step 0{idx + 1}</span>
                <h3 className="text-2xl font-bold text-white group-hover:text-cyan-vibrant transition-colors">{step.title}</h3>
                <p className="text-slate-400 font-medium leading-relaxed max-w-[250px] mx-auto">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default HowItWorks;
