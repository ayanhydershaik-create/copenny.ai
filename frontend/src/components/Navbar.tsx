import React, { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { cn } from '../lib/utils';
import AuthModal from './AuthModal';

const Navbar: React.FC = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [authTab, setAuthTab] = useState<'login' | 'register'>('login');

  React.useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { name: 'Features', href: '#features' },
    { name: 'How It Works', href: '#how-it-works' },
    { name: 'Pricing', href: '#pricing' },
    { name: 'About', href: '/about' },
  ];

  const openLogin = () => { setAuthTab('login'); setAuthOpen(true); setIsMobileMenuOpen(false); };
  const openRegister = () => { setAuthTab('register'); setAuthOpen(true); setIsMobileMenuOpen(false); };

  return (
    <>
      <nav
        className={cn(
          'fixed top-6 left-1/2 -translate-x-1/2 w-[90%] max-w-7xl z-50 transition-all duration-300 rounded-full border border-white/5',
          isScrolled ? 'glass py-3 px-6' : 'bg-transparent py-4 px-8'
        )}
      >
        <div className="flex items-center justify-between">
          {/* Logo */}
          <a href="/" className="flex items-center gap-2 group">
            <img src="/static/iconcopenny.png" alt="Co Penny" className="h-10 w-auto object-contain transition-transform group-hover:scale-110" />
            <span className="text-white font-bold tracking-tight text-xl">copenny.ai</span>
          </a>

          {/* Desktop Links */}
          <div className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
              >
                {link.name}
              </a>
            ))}
            <div className="h-4 w-px bg-white/10" />
            <button
              onClick={openLogin}
              className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
            >
              Login
            </button>
            <button
              onClick={openRegister}
              className="bg-cyan-vibrant text-black px-6 py-2.5 rounded-full text-sm font-bold shadow-[0_0_20px_rgba(0,255,255,0.3)] hover:scale-105 active:scale-95 transition-all"
            >
              Get Started
            </button>
          </div>

          {/* Mobile Toggle */}
          <button
            className="md:hidden p-2 text-slate-400 hover:text-white transition-colors"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="absolute top-20 left-0 right-0 glass rounded-3xl p-6 flex flex-col gap-6 md:hidden animate-in fade-in slide-in-from-top-5">
            {navLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                className="text-lg font-medium text-slate-400"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                {link.name}
              </a>
            ))}
            <hr className="border-white/5" />
            <button onClick={openLogin} className="text-lg font-medium text-slate-400 text-left">
              Login
            </button>
            <button
              onClick={openRegister}
              className="bg-cyan-vibrant text-black px-6 py-4 rounded-full text-lg font-bold shadow-[0_0_20px_rgba(0,255,255,0.3)]"
            >
              Get Started
            </button>
          </div>
        )}
      </nav>

      {/* Auth Modal */}
      <AuthModal isOpen={authOpen} onClose={() => setAuthOpen(false)} defaultTab={authTab} />
    </>
  );
};

export default Navbar;
