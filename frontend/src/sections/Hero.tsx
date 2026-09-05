import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import gsap from 'gsap';
import { activateDemoMode } from '../lib/firebase';
import AuthModal from '../components/AuthModal';

const Hero: React.FC = () => {
  const heroRef = useRef<HTMLDivElement>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: 'power3.out', duration: 1 } });
      
      tl.from('.hero-badge', { opacity: 0, y: 20 })
        .from('.hero-title', { opacity: 0, y: 30 }, '-=0.6')
        .from('.hero-subtext', { opacity: 0, y: 30 }, '-=0.7')
        .from('.hero-buttons', { opacity: 0, y: 30 }, '-=0.8')
        .from('.hero-preview', { opacity: 0, scale: 0.95, y: 40 }, '-=0.8');
    }, heroRef);

    return () => ctx.revert();
  }, []);

  const handleDemoClick = async () => {
    setDemoLoading(true);
    const ok = await activateDemoMode();
    setDemoLoading(false);
    if (ok) window.location.href = '/ui';
    else setAuthOpen(true); // fallback to login if demo fails
  };

  return (
    <>
    <section ref={heroRef} className="pt-40 pb-20 px-6 overflow-hidden min-h-screen flex items-center">
      <div className="max-w-7xl mx-auto w-full">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left Content */}
          <div className="flex flex-col gap-8 max-w-2xl">
            <div className="hero-badge inline-flex items-center self-start px-4 py-1.5 rounded-full glass text-xs font-bold uppercase tracking-widest text-cyan-vibrant border border-cyan-vibrant/20">
              Next-Gen Wealth Intelligence
            </div>
            
            <h1 className="hero-title text-6xl md:text-8xl font-black tracking-tight leading-[1.05] text-white">
              Your AI <br />
              <span className="text-cyan-vibrant">Financial</span> Advisor
            </h1>
            
            <p className="hero-subtext text-lg md:text-xl text-slate-400 leading-relaxed font-medium">
              Transform your financial future with Copenny.ai. Our neural engine analyzes your transactions to deliver executive-grade intelligence and automated savings strategies.
            </p>
            
            <div className="hero-buttons flex flex-wrap gap-4 mt-4">
              <button
                onClick={handleDemoClick}
                disabled={demoLoading}
                className="bg-white text-black px-8 py-4 rounded-full font-bold flex items-center gap-2 hover:scale-105 active:scale-95 transition-all group disabled:opacity-70"
              >
                {demoLoading ? '⏳ Loading...' : <>Try Demo <ArrowRight className="group-hover:translate-x-1 transition-transform" size={20} /></>}
              </button>
              <button
                onClick={() => setAuthOpen(true)}
                className="border border-white/20 text-white px-8 py-4 rounded-full font-bold flex items-center gap-2 hover:bg-white/5 transition-all"
              >
                Get Started
              </button>
            </div>
          </div>

          {/* Right Preview */}
          <div className="hero-preview group relative">
            <div className="absolute -inset-1 bg-linear-to-r from-cyan-vibrant/20 to-transparent blur-3xl opacity-50 group-hover:opacity-100 transition-opacity" />
            <div className="relative glass rounded-[40px] p-8 border border-white/10 shadow-2xl">
              <div className="flex items-center justify-between mb-8">
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-slate-400 font-bold uppercase tracking-tighter">Current Savings</span>
                  <span className="text-3xl font-bold font-mono">₹45,280.00</span>
                </div>
                <div className="h-12 w-12 rounded-2xl glass flex items-center justify-center text-cyan-vibrant">
                  <ArrowRight className="-rotate-45" />
                </div>
              </div>
              
              {/* Fake Chart Placeholder */}
              <div className="space-y-4 mb-8">
                {[80, 40, 95, 60, 85].map((h, i) => (
                  <div key={i} className="flex flex-col gap-2">
                    <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase">
                      <span>Goal {i + 1}</span>
                      <span>{h}%</span>
                    </div>
                    <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-cyan-vibrant shadow-[0_0_10px_rgba(0,255,255,0.5)] rounded-full"
                        style={{ width: `${h}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-4 rounded-2xl bg-cyan-vibrant/5 border border-cyan-vibrant/10 flex items-center gap-4">
                <div className="h-3 w-3 rounded-full bg-cyan-vibrant animate-pulse" />
                <span className="text-sm font-medium text-slate-300 italic">"Co Penny is analyzing your spending patterns..."</span>
              </div>
            </div>
          </div>
        </div>
        {/* Engineering Strip */}
        <div className="mt-20 pt-8 border-t flex items-center gap-8" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(0,255,255,0.08)', border: '1px solid rgba(0,255,255,0.15)' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00FFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-0.5">Engineering</p>
              <p className="text-sm font-semibold text-white">Developed by <span style={{ color: '#ff4444', textShadow: '0 0 12px rgba(255,68,68,0.7)' }}>RedHack</span></p>
            </div>
          </div>
        </div>
      </div>
    </section>
    <AuthModal isOpen={authOpen} onClose={() => setAuthOpen(false)} defaultTab="register" />
    </>
  );
};

export default Hero;
