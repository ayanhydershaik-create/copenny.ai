// Co Penny Premium Animation Layer
// Powered by GSAP & ScrollTrigger

document.addEventListener('DOMContentLoaded', () => {
    // Register ScrollTrigger
    gsap.registerPlugin(ScrollTrigger);

    // 1. Initial Hero Load Animation
    const heroTl = gsap.timeline({
        defaults: { ease: "expo.out", duration: 1.5 }
    });

    heroTl
        .to(".reveal", {
            opacity: 1,
            y: 0,
            stagger: 0.15,
            delay: 0.5
        })
        .from(".sticky-nav", {
            y: -100,
            opacity: 0,
            duration: 1
        }, "-=1");

    // 2. Parallax Floating Cards
    gsap.to(".parallax-item", {
        y: (i, target) => -50 * parseFloat(target.dataset.speed || 1),
        scrollTrigger: {
            trigger: "main",
            start: "top top",
            end: "bottom top",
            scrub: true
        }
    });

    // 3. Section Reveal Animations
    const reveals = document.querySelectorAll('.reveal-on-scroll');
    reveals.forEach(el => {
        gsap.from(el, {
            opacity: 0,
            y: 50,
            duration: 1,
            scrollTrigger: {
                trigger: el,
                start: "top 85%",
                toggleActions: "play none none reverse"
            }
        });
    });

    // 4. Mesh Gradient Subtle Movement
    gsap.to(".mesh-gradient", {
        rotation: 360,
        duration: 120,
        repeat: -1,
        ease: "none"
    });

    // 5. Magnetic Button Effect (Optional/Subtle)
    const magneticBtns = document.querySelectorAll('.btn-premium');
    magneticBtns.forEach(btn => {
        btn.addEventListener('mousemove', (e) => {
            const rect = btn.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;

            gsap.to(btn, {
                x: x * 0.2,
                y: y * 0.2,
                duration: 0.4,
                ease: "power2.out"
            });
        });

        btn.addEventListener('mouseleave', () => {
            gsap.to(btn, {
                x: 0,
                y: 0,
                duration: 0.6,
                ease: "elastic.out(1, 0.3)"
            });
        });
    });
});
