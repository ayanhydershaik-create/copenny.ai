import React, { useEffect, useRef } from 'react';
import { ArrowRight } from 'lucide-react';
import gsap from 'gsap';

const CTA: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from('.cta-content', {
        opacity: 0,
        scale: 0.9,
        duration: 1,
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top 80%',
        },
      });
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={containerRef} className="py-32 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="cta-content relative glass rounded-[60px] p-16 md:p-32 overflow-hidden text-center border-white/10 shadow-[0_0_100px_rgba(0,255,255,0.05)] border">
          {/* Background Glow */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-linear-to-r from-cyan-vibrant/10 via-purple-500/10 to-transparent blur-[120px] pointer-events-none" />
          
          <div className="relative z-10 space-y-8">
            <h2 className="text-5xl md:text-7xl font-black tracking-tight text-white max-w-4xl mx-auto leading-tight">
              Ready to Master Your <br />
              <span className="text-cyan-vibrant">Financial Future</span>?
            </h2>
            
            <p className="text-slate-400 text-lg md:text-xl max-w-2xl mx-auto font-medium leading-relaxed">
              Join thousands of executive-grade investors who use Penny AI to predict, track, and optimize their wealth every single second.
            </p>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-6 mt-8">
              <button className="bg-cyan-vibrant text-black px-10 py-5 rounded-full font-black text-lg flex items-center gap-2 shadow-[0_0_40px_rgba(0,255,255,0.4)] hover:scale-105 active:scale-95 transition-all">
                Get Started Now <ArrowRight size={24} />
              </button>
              <button className="text-white font-bold text-lg hover:text-cyan-vibrant transition-colors">
                Contact Sales
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default CTA;
