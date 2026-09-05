import re
import os

with open("c:\\Users\\sabih\\OneDrive\\Desktop\\CoPenny.Ai\\stitch_design.html", "r", encoding="utf-8") as f:
    text = f.read()

# Extract body
body_match = re.search(r'<body[^>]*>(.*?)</body>', text, re.DOTALL)
if not body_match:
    print("No body found")
    exit(1)

body = body_match.group(1)

# HTML to JSX transforms
body = body.replace('class=', 'className=')
body = body.replace('for=', 'htmlFor=')
body = body.replace('tabindex=', 'tabIndex=')

# Self-closing tags
body = re.sub(r'<img([^>]+?)(?<!/)>', r'<img\1 />', body)
body = re.sub(r'<br([^>]*?)(?<!/)>', r'<br\1 />', body)
body = re.sub(r'<hr([^>]*?)(?<!/)>', r'<hr\1 />', body)
body = re.sub(r'<input([^>]+?)(?<!/)>', r'<input\1 />', body)

# SVG attributes
attrs = ['viewBox', 'strokeWidth', 'strokeLinecap', 'strokeLinejoin', 'fillRule', 'clipRule']
for attr in attrs:
    body = re.sub(attr.lower() + r'=', attr + '=', body)

# Remove comments
body = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)

# Inline styles
def style_repl(m):
    css = m.group(1)
    rules = css.split(';')
    jsx_style = []
    for rule in rules:
        if ':' not in rule: continue
        k, v = rule.split(':', 1)
        k = k.strip()
        v = v.strip()
        parts = k.split('-')
        k_camel = parts[0] + ''.join(p.title() for p in parts[1:])
        jsx_style.append(f"{k_camel}: '{v}'")
    return "style={{" + ", ".join(jsx_style) + "}}"

body = re.sub(r'style="([^"]*)"', style_repl, body)

tsx_content = f"""import React, {{ useState }} from 'react';
import AuthModal from './components/AuthModal';

const StitchLanding: React.FC = () => {{
  const [authOpen, setAuthOpen] = useState(false);
  const [authTab, setAuthTab] = useState<'login' | 'register'>('login');
  
  const handleLogin = (e: React.MouseEvent) => {{
    e.preventDefault();
    setAuthTab('login');
    setAuthOpen(true);
  }};

  const handleRegister = (e: React.MouseEvent) => {{
    e.preventDefault();
    setAuthTab('register');
    setAuthOpen(true);
  }};

  return (
    <div className="bg-background-light dark:bg-background-dark text-slate-900 dark:text-slate-100 selection:bg-primary/30">
      <div onClick={{(e) => {{
        const target = e.target as HTMLElement;
        const text = target.textContent?.trim() || '';
        // Intercept clicks on links or buttons based on text
        if (target.tagName === 'A' || target.tagName === 'BUTTON' || target.closest('a') || target.closest('button')) {{
            if (text.includes('Sign In') || text.includes('Login') || target.closest('a')?.textContent?.includes('Sign In')) {{
                handleLogin(e);
            }}
            if (text.includes('Sign Up') || text.includes('Get Started') || target.closest('button')?.textContent?.includes('Get Started')) {{
                handleRegister(e);
            }}
        }}
      }}}}>
        {body}
      </div>
      <AuthModal isOpen={{authOpen}} onClose={{() => setAuthOpen(false)}} defaultTab={{authTab}} />
    </div>
  );
}};

export default StitchLanding;
"""

out_path = "c:\\Users\\sabih\\OneDrive\\Desktop\\CoPenny.Ai\\frontend\\src\\StitchLanding.tsx"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(tsx_content)

print(f"Successfully generated {out_path}")
