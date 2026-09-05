/**
 * Co Penny Dashboard Animations
 * Powered by GSAP & ScrollTrigger
 */

document.addEventListener('DOMContentLoaded', () => {
    // Register GSAP plugins (assuming they are loaded in index.html)
    // gsap.registerPlugin(ScrollTrigger);

    initDashboardAnimations();
});

function initDashboardAnimations() {
    // 1. Sidebar Slide-in
    gsap.from('#dashboardSidebar', {
        x: -100,
        opacity: 1, // Start at full opacity
        duration: 1.2,
        ease: 'expo.out',
        delay: 0.1
    });

    // 2. Top Header Reveal
    gsap.from('main > header', {
        y: -50,
        opacity: 1, // Start at full opacity
        duration: 1,
        ease: 'expo.out',
        delay: 0.3
    });

    // 3. Staggered reveal for current tab content
    revealActiveTab();

    // 4. Magnetic hover effect for buttons (premium touch)
    const premiumBtns = document.querySelectorAll('.nav-item, button[id$="Btn"], .card-hover');
    premiumBtns.forEach(btn => {
        btn.addEventListener('mousemove', (e) => {
            const rect = btn.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;

            gsap.to(btn, {
                x: x * 0.1,
                y: y * 0.1,
                duration: 0.4,
                ease: 'power2.out'
            });
        });

        btn.addEventListener('mouseleave', () => {
            gsap.to(btn, {
                x: 0,
                y: 0,
                duration: 0.6,
                ease: 'elastic.out(1, 0.3)'
            });
        });
    });

    // 5. Mesh Gradient Movement
    gsap.to('.mesh-gradient', {
        duration: 20,
        backgroundPosition: '100% 100%',
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut'
    });
}

function revealActiveTab() {
    const activeTab = document.querySelector('.tab-content:not(.hidden)');
    if (!activeTab) return;

    // Reveal children with .slide-up class
    const elements = activeTab.querySelectorAll('.slide-up');
    gsap.fromTo(elements,
        {
            y: 40,
            opacity: 0
        },
        {
            y: 0,
            opacity: 1,
            duration: 0.8,
            stagger: 0.1,
            ease: 'expo.out',
            clearProps: 'all' // important to not break layout after animation
        }
    );

    // Specifically for bento boxes/cards
    const cards = activeTab.querySelectorAll('.glass');
    gsap.fromTo(cards,
        {
            scale: 0.95,
            opacity: 0
        },
        {
            scale: 1,
            opacity: 1,
            duration: 1,
            stagger: 0.05,
            ease: 'expo.out',
            delay: 0.1,
            clearProps: 'all'
        }
    );
}

// Hook into the existing switchTab function to run reveals
const originalSwitchTab = window.switchTab;
window.switchTab = function (tabId) {
    if (typeof originalSwitchTab === 'function') {
        originalSwitchTab(tabId);
    }
    // Small delay to let the 'hidden' class be removed
    setTimeout(revealActiveTab, 50);
};
