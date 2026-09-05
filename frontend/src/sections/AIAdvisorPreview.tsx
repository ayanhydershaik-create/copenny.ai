import React from 'react';
import { Sparkles, MessageSquare, ShieldCheck, Zap } from 'lucide-react';

const AIAdvisorPreview: React.FC = () => {
  return (
    <section className="py-32 px-6 relative">
      <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-20 items-center">
        {/* Left: Chat Simulation */}
        <div className="relative">
          <div className="absolute -inset-4 rounded-full blur-[100px]" style={{ background: 'rgba(0,255,255,0.05)' }} />
          <div
            className="relative rounded-[40px] p-8 shadow-2xl space-y-6"
            style={{ background: 'rgba(255,255,255,0.03)', backdropFilter: 'blur(24px)', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            <div className="flex items-center gap-3 border-b pb-6" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
              <div className="h-10 w-10 rounded-full flex items-center justify-center" style={{ background: 'rgba(0,255,255,0.15)', color: '#00FFFF' }}>
                <Sparkles size={20} />
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-bold text-white leading-none">Penny AI</span>
                <span className="font-black uppercase tracking-widest mt-1 text-[10px]" style={{ color: '#00FFFF' }}>Live Intelligence</span>
              </div>
            </div>

            <div className="space-y-4 h-[360px] overflow-y-auto pr-2">
              <div className="flex justify-end">
                <div className="p-4 rounded-2xl rounded-tr-none max-w-[80%]" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <p className="text-sm text-slate-300">How much did I spend on dining out this month compared to last?</p>
                </div>
              </div>

              <div className="flex justify-start">
                <div className="p-5 rounded-2xl rounded-tl-none max-w-[90%]" style={{ background: 'rgba(0,255,255,0.04)', border: '1px solid rgba(0,255,255,0.15)', backdropFilter: 'blur(8px)' }}>
                  <p className="text-sm text-white leading-relaxed">
                    You've spent <span className="font-bold" style={{ color: '#00FFFF' }}>₹12,450</span> on dining this month. That's a <span className="text-red-400 font-bold">14% decrease</span> from last month! 📉
                    <br /><br />
                    I noticed most of this came from weekend brunches. Based on your current trend, you could save an additional <span className="font-bold" style={{ color: '#00FFFF' }}>₹3,000</span> if you skip one more dining event this week.
                  </p>
                </div>
              </div>

              <div className="flex justify-end">
                <div className="p-4 rounded-2xl rounded-tr-none max-w-[80%]" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <p className="text-sm text-slate-300">Great! Adjust my budget to reflect that.</p>
                </div>
              </div>

              <div className="flex justify-start">
                <div className="p-5 rounded-2xl rounded-tl-none max-w-[90%]" style={{ background: 'rgba(74,222,128,0.04)', border: '1px solid rgba(74,222,128,0.2)' }}>
                  <div className="flex items-center gap-2 mb-2 text-green-400">
                    <ShieldCheck size={16} />
                    <span className="text-[10px] font-black uppercase tracking-widest">Budget Optimized</span>
                  </div>
                  <p className="text-sm text-white leading-relaxed">
                    Done! I've reallocated that savings goal to your <span className="text-green-400 font-bold">Retirement Fund</span>. You are now on track to reach your annual goal 2 months earlier. 🚀
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4 rounded-2xl p-4" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.05)' }}>
              <div className="flex-1 text-slate-500 text-sm">Ask Penny anything...</div>
              <div className="h-10 w-10 rounded-xl flex items-center justify-center shadow-lg" style={{ background: '#00FFFF', color: '#000' }}>
                <Zap size={20} />
              </div>
            </div>
          </div>
        </div>

        {/* Right: Copy Content */}
        <div className="space-y-10">
          <div className="space-y-4">
            <span style={{ color: '#00FFFF' }} className="font-bold uppercase tracking-widest text-xs">Conversational Intelligence</span>
            <h2 className="text-5xl md:text-6xl font-black tracking-tight text-white leading-[1.1]">
              Meet Penny. <br />
              <span style={{ color: '#00FFFF' }}>The Brain</span> <br />
              Behind Your Money.
            </h2>
          </div>

          <div className="grid sm:grid-cols-2 gap-8">
            <div className="space-y-4">
              <div className="h-12 w-12 rounded-2xl flex items-center justify-center" style={{ background: 'rgba(0,255,255,0.1)', color: '#00FFFF' }}>
                <MessageSquare size={24} />
              </div>
              <h3 className="text-xl font-bold text-white">Natural Insights</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                No more complex spreadsheets. Just ask questions and get instant, human-like financial advice.
              </p>
            </div>
            <div className="space-y-4">
              <div className="h-12 w-12 rounded-2xl flex items-center justify-center" style={{ background: 'rgba(0,255,255,0.1)', color: '#00FFFF' }}>
                <ShieldCheck size={24} />
              </div>
              <h3 className="text-xl font-bold text-white">Privacy First</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                Your data is processed using local-first neural models and industry-leading encryption protocols.
              </p>
            </div>
          </div>

          <button
            className="px-8 py-4 rounded-full font-bold hover:opacity-80 transition-opacity"
            style={{ border: '1px solid rgba(0,255,255,0.2)', color: '#00FFFF', background: 'rgba(0,255,255,0.04)' }}
          >
            See Penny in Action
          </button>
        </div>
      </div>
    </section>
  );
};

export default AIAdvisorPreview;
