import React from 'react';
import { Twitter, Linkedin, Instagram, ArrowUpRight } from 'lucide-react';

const Footer: React.FC = () => {
  const footerLinks = [
    {
      title: 'Product',
      links: [
        { label: 'Features', href: '#features' },
        { label: 'AI Advisor', href: '/ai-advisor' },
        { label: 'Pricing', href: '#pricing' },
        { label: 'Security', href: '/security' },
      ],
    },
    {
      title: 'Resources',
      links: [
        { label: 'Documentation', href: '/documentation' },
        { label: 'Community', href: '/community' },
        { label: 'Help Center', href: '/help' },
      ],
    },
    {
      title: 'Company',
      links: [
        { label: 'About Us', href: '/about' },
        { label: 'Careers', href: '/careers' },
        { label: 'Contact', href: '/contact' },
        { label: 'Privacy Policy', href: '/privacy' },
        { label: 'Terms of Service', href: '/terms' },
      ],
    },
  ];

  return (
    <footer className="py-20 px-6 border-t border-white/5 bg-slate-950/20 backdrop-blur-3xl">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-16 mb-20">
          {/* Brand Info */}
          <div className="lg:col-span-2 space-y-8">
            <a href="/" className="flex items-center gap-2 group">
              <img src="/static/iconcopenny.png" alt="Co Penny" className="h-10 w-auto object-contain transition-transform group-hover:scale-110" />
              <span className="text-white font-bold tracking-tight text-xl">copenny.ai</span>
            </a>
            <p className="text-slate-400 max-w-sm text-sm leading-relaxed">
              The executive-grade AI financial advisor that turns raw transaction data into actionable neural intelligence. Built for the modern master economy.
            </p>
            <div className="flex gap-4">
              <a href="#" className="h-10 w-10 rounded-xl glass flex items-center justify-center text-slate-400 hover:text-cyan-vibrant transition-colors">
                <Twitter size={18} />
              </a>
              <a href="#" className="h-10 w-10 rounded-xl glass flex items-center justify-center text-slate-400 hover:text-cyan-vibrant transition-colors">
                <Linkedin size={18} />
              </a>
              <a href="#" className="h-10 w-10 rounded-xl glass flex items-center justify-center text-slate-400 hover:text-cyan-vibrant transition-colors">
                <Instagram size={18} />
              </a>
            </div>
          </div>

          {/* Link Columns */}
          {footerLinks.map((column, idx) => (
            <div key={idx} className="space-y-6">
              <h4 className="text-white font-bold uppercase tracking-widest text-xs">{column.title}</h4>
              <ul className="space-y-4">
                {column.links.map((link, lIdx) => (
                  <li key={lIdx}>
                    <a href={link.href} className="text-sm text-slate-400 hover:text-white transition-colors flex items-center gap-1 group">
                      {link.label}
                      <ArrowUpRight size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="pt-8 border-t border-white/5 flex flex-col md:flex-row items-center justify-between gap-6 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
          <span>&copy; 2025 Copenny.ai. All rights reserved.</span>
          <div className="flex items-center gap-2">
            <span>Developed by</span>
            <span style={{ color: '#ff4444', textShadow: '0 0 12px rgba(255,68,68,0.7)' }} className="cursor-pointer">RedHack</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
