(function () {
    "use strict";

    // ============================================
    // LOGIN BACKGROUND ANIMATION
    // Matrix-style rain + Geometric particles
    // Mouse-reactive interactive effects
    // ============================================

    const canvas = document.createElement("canvas");
    canvas.id = "loginBgCanvas";
    canvas.style.cssText =
        "position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;";
    document.body.insertBefore(canvas, document.body.firstChild);

    const ctx = canvas.getContext("2d");
    let W, H;
    let mouseX = -1000,
        mouseY = -1000;
    let animationId = null;

    // ---- Configuration ----
    const CONFIG = {
        // Matrix rain
        matrixChars:
            "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン",
        matrixFontSize: 14,
        matrixSpeed: 0.6,
        matrixFadeAlpha: 0.04,
        matrixColor: { r: 0, g: 255, b: 100 },

        // Floating particles
        particleCount: 80,
        particleMinSize: 1,
        particleMaxSize: 3,
        particleSpeed: 0.3,
        particleMouseRadius: 180,
        particleConnectionDist: 120,

        // Click ripple
        rippleMaxRadius: 200,
        rippleSpeed: 4,
        rippleFade: 0.015,

        // Geometric shapes
        shapeCount: 6,
        shapeRotateSpeed: 0.003,
    };

    // ---- Resize ----
    function resize() {
        W = canvas.width = window.innerWidth;
        H = canvas.height = window.innerHeight;
        initMatrixColumns();
    }

    // ---- Matrix Rain ----
    let columns = [];
    function initMatrixColumns() {
        const colCount = Math.ceil(W / CONFIG.matrixFontSize);
        columns = [];
        for (let i = 0; i < colCount; i++) {
            columns.push({
                x: i * CONFIG.matrixFontSize,
                y: Math.random() * H,
                speed: CONFIG.matrixSpeed + Math.random() * 0.5,
                chars: [],
                nextCharTime: 0,
            });
        }
    }

    function drawMatrixRain(time) {
        // Semi-transparent overlay for trail effect
        ctx.fillStyle = `rgba(15, 42, 36, ${CONFIG.matrixFadeAlpha})`;
        ctx.fillRect(0, 0, W, H);

        ctx.font = `${CONFIG.matrixFontSize}px 'Courier New', monospace`;

        for (let col of columns) {
            // Distance from mouse influences brightness
            const dx = col.x - mouseX;
            const dy = col.y - mouseY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const mouseInfluence = Math.max(
                0,
                1 - dist / CONFIG.particleMouseRadius
            );

            const r = CONFIG.matrixColor.r + mouseInfluence * 100;
            const g = CONFIG.matrixColor.g;
            const b = CONFIG.matrixColor.b + mouseInfluence * 155;
            const alpha = 0.5 + mouseInfluence * 0.5;

            ctx.fillStyle = `rgba(${Math.min(255, r)}, ${g}, ${Math.min(255, b)}, ${alpha})`;

            // Draw character
            const char = CONFIG.matrixChars.charAt(
                Math.floor(Math.random() * CONFIG.matrixChars.length)
            );
            ctx.fillText(char, col.x, col.y);

            // Bright head character
            if (mouseInfluence > 0.3) {
                ctx.fillStyle = `rgba(180, 255, 220, ${0.8 + mouseInfluence * 0.2})`;
                ctx.fillText(char, col.x, col.y);
                // Glow effect
                ctx.shadowColor = `rgba(0, 255, 150, 0.8)`;
                ctx.shadowBlur = 15;
                ctx.fillText(char, col.x, col.y);
                ctx.shadowBlur = 0;
            }

            col.y += col.speed * CONFIG.matrixFontSize * 0.4;
            if (col.y > H + 50) {
                col.y = -CONFIG.matrixFontSize * 2;
                col.speed = CONFIG.matrixSpeed + Math.random() * 0.5;
            }
        }
    }

    // ---- Floating Particles ----
    let particles = [];
    function initParticles() {
        particles = [];
        for (let i = 0; i < CONFIG.particleCount; i++) {
            particles.push(createParticle());
        }
    }

    function createParticle(x, y) {
        return {
            x: x !== undefined ? x : Math.random() * W,
            y: y !== undefined ? y : Math.random() * H,
            vx: (Math.random() - 0.5) * CONFIG.particleSpeed * 2,
            vy: (Math.random() - 0.5) * CONFIG.particleSpeed * 2,
            size:
                CONFIG.particleMinSize +
                Math.random() * (CONFIG.particleMaxSize - CONFIG.particleMinSize),
            alpha: 0.3 + Math.random() * 0.5,
            hue: 140 + Math.random() * 40, // green-cyan range
            pulsePhase: Math.random() * Math.PI * 2,
        };
    }

    function drawParticles(time) {
        for (let p of particles) {
            // Mouse attraction
            const dx = mouseX - p.x;
            const dy = mouseY - p.y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < CONFIG.particleMouseRadius && dist > 1) {
                const force = (CONFIG.particleMouseRadius - dist) / CONFIG.particleMouseRadius;
                p.vx += (dx / dist) * force * 0.08;
                p.vy += (dy / dist) * force * 0.08;
            }

            // Damping
            p.vx *= 0.98;
            p.vy *= 0.98;

            p.x += p.vx;
            p.y += p.vy;

            // Wrap around
            if (p.x < -10) p.x = W + 10;
            if (p.x > W + 10) p.x = -10;
            if (p.y < -10) p.y = H + 10;
            if (p.y > H + 10) p.y = -10;

            // Pulsing size
            const pulse = Math.sin(time * 0.002 + p.pulsePhase) * 0.5 + 0.5;
            const currentSize = p.size * (0.7 + pulse * 0.6);

            // Mouse proximity glow
            const proximity = dist < CONFIG.particleMouseRadius
                ? 1 - dist / CONFIG.particleMouseRadius
                : 0;
            const glowAlpha = p.alpha + proximity * 0.5;

            ctx.beginPath();
            ctx.arc(p.x, p.y, currentSize, 0, Math.PI * 2);
            ctx.fillStyle = `hsla(${p.hue + proximity * 60}, 80%, ${50 + proximity * 30}%, ${glowAlpha})`;
            ctx.fill();

            // Outer glow for close particles
            if (proximity > 0.3) {
                ctx.beginPath();
                ctx.arc(p.x, p.y, currentSize * 3, 0, Math.PI * 2);
                ctx.fillStyle = `hsla(${p.hue + 60}, 90%, 70%, ${proximity * 0.15})`;
                ctx.fill();
            }
        }

        // Draw connections
        drawConnections();
    }

    function drawConnections() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const a = particles[i];
                const b = particles[j];
                const dx = a.x - b.x;
                const dy = a.y - b.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < CONFIG.particleConnectionDist) {
                    const alpha =
                        (1 - dist / CONFIG.particleConnectionDist) * 0.15;

                    // Mouse proximity makes connections brighter
                    const midX = (a.x + b.x) / 2;
                    const midY = (a.y + b.y) / 2;
                    const mouseDist = Math.sqrt(
                        (midX - mouseX) ** 2 + (midY - mouseY) ** 2
                    );
                    const mouseBoost =
                        mouseDist < CONFIG.particleMouseRadius
                            ? (1 - mouseDist / CONFIG.particleMouseRadius) * 0.3
                            : 0;

                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.strokeStyle = `rgba(0, 255, 170, ${alpha + mouseBoost})`;
                    ctx.lineWidth = 0.5 + mouseBoost * 2;
                    ctx.stroke();
                }
            }
        }
    }

    // ---- Click Ripples ----
    let ripples = [];
    function addRipple(x, y) {
        // Matrix-style burst
        ripples.push({
            x: x,
            y: y,
            radius: 0,
            alpha: 1,
            type: "ring",
        });

        // Hex grid burst
        ripples.push({
            x: x,
            y: y,
            radius: 0,
            alpha: 0.8,
            type: "hex",
        });

        // Spawn extra particles at click point
        for (let i = 0; i < 12; i++) {
            const angle = (Math.PI * 2 * i) / 12;
            const speed = 2 + Math.random() * 3;
            const p = createParticle(x, y);
            p.vx = Math.cos(angle) * speed;
            p.vy = Math.sin(angle) * speed;
            p.size = 2 + Math.random() * 2;
            p.alpha = 0.9;
            p.hue = 160 + Math.random() * 60;
            particles.push(p);
        }

        // Remove excess particles
        while (particles.length > CONFIG.particleCount + 60) {
            particles.shift();
        }
    }

    function drawRipples() {
        for (let i = ripples.length - 1; i >= 0; i--) {
            const r = ripples[i];
            r.radius += CONFIG.rippleSpeed;
            r.alpha -= CONFIG.rippleFade;

            if (r.alpha <= 0) {
                ripples.splice(i, 1);
                continue;
            }

            if (r.type === "ring") {
                // Main ring
                ctx.beginPath();
                ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
                ctx.strokeStyle = `rgba(0, 255, 170, ${r.alpha * 0.6})`;
                ctx.lineWidth = 2;
                ctx.stroke();

                // Inner ring
                if (r.radius > 20) {
                    ctx.beginPath();
                    ctx.arc(r.x, r.y, r.radius * 0.6, 0, Math.PI * 2);
                    ctx.strokeStyle = `rgba(100, 255, 200, ${r.alpha * 0.3})`;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }

                // Glowing center
                const gradient = ctx.createRadialGradient(
                    r.x, r.y, 0,
                    r.x, r.y, r.radius * 0.3
                );
                gradient.addColorStop(0, `rgba(0, 255, 170, ${r.alpha * 0.4})`);
                gradient.addColorStop(1, `rgba(0, 255, 170, 0)`);
                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.arc(r.x, r.y, r.radius * 0.3, 0, Math.PI * 2);
                ctx.fill();
            } else if (r.type === "hex") {
                // Hexagonal expanding pattern
                const sides = 6;
                ctx.beginPath();
                for (let s = 0; s < sides; s++) {
                    const angle = (Math.PI * 2 * s) / sides - Math.PI / 6;
                    const hx = r.x + Math.cos(angle) * r.radius * 0.8;
                    const hy = r.y + Math.sin(angle) * r.radius * 0.8;
                    if (s === 0) ctx.moveTo(hx, hy);
                    else ctx.lineTo(hx, hy);
                }
                ctx.closePath();
                ctx.strokeStyle = `rgba(0, 200, 255, ${r.alpha * 0.4})`;
                ctx.lineWidth = 1.5;
                ctx.stroke();

                // Data scatter - small characters along the ripple
                if (r.radius > 15 && r.radius < CONFIG.rippleMaxRadius * 0.8) {
                    ctx.font = "10px 'Courier New', monospace";
                    for (let s = 0; s < sides; s++) {
                        const angle = (Math.PI * 2 * s) / sides;
                        const tx = r.x + Math.cos(angle) * r.radius;
                        const ty = r.y + Math.sin(angle) * r.radius;
                        const char = Math.random() > 0.5 ? "1" : "0";
                        ctx.fillStyle = `rgba(0, 255, 200, ${r.alpha * 0.6})`;
                        ctx.fillText(char, tx, ty);
                    }
                }
            }
        }
    }

    // ---- Geometric Floating Shapes ----
    let shapes = [];
    function initShapes() {
        shapes = [];
        for (let i = 0; i < CONFIG.shapeCount; i++) {
            shapes.push({
                x: Math.random() * W,
                y: Math.random() * H,
                vx: (Math.random() - 0.5) * 0.3,
                vy: (Math.random() - 0.5) * 0.3,
                size: 30 + Math.random() * 60,
                sides: Math.floor(Math.random() * 3) + 3, // 3-5 sides
                rotation: Math.random() * Math.PI * 2,
                rotationSpeed:
                    (Math.random() - 0.5) * CONFIG.shapeRotateSpeed * 2,
                alpha: 0.05 + Math.random() * 0.08,
                hue: 120 + Math.random() * 80,
            });
        }
    }

    function drawShapes(time) {
        for (let s of shapes) {
            s.x += s.vx;
            s.y += s.vy;
            s.rotation += s.rotationSpeed;

            // Wrap
            if (s.x < -s.size) s.x = W + s.size;
            if (s.x > W + s.size) s.x = -s.size;
            if (s.y < -s.size) s.y = H + s.size;
            if (s.y > H + s.size) s.y = -s.size;

            // Mouse interaction
            const dx = mouseX - s.x;
            const dy = mouseY - s.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const mouseProximity =
                dist < 250 ? (1 - dist / 250) : 0;

            const currentAlpha = s.alpha + mouseProximity * 0.15;
            const currentSize = s.size * (1 + mouseProximity * 0.3);

            // Accelerate rotation near mouse
            if (mouseProximity > 0) {
                s.rotation += s.rotationSpeed * mouseProximity * 5;
            }

            ctx.save();
            ctx.translate(s.x, s.y);
            ctx.rotate(s.rotation);

            // Draw polygon
            ctx.beginPath();
            for (let i = 0; i <= s.sides; i++) {
                const angle = (Math.PI * 2 * i) / s.sides;
                const px = Math.cos(angle) * currentSize;
                const py = Math.sin(angle) * currentSize;
                if (i === 0) ctx.moveTo(px, py);
                else ctx.lineTo(px, py);
            }
            ctx.closePath();
            ctx.strokeStyle = `hsla(${s.hue}, 70%, 60%, ${currentAlpha})`;
            ctx.lineWidth = 1 + mouseProximity * 1.5;
            ctx.stroke();

            // Inner wireframe
            ctx.beginPath();
            for (let i = 0; i < s.sides; i++) {
                const angle = (Math.PI * 2 * i) / s.sides;
                const px = Math.cos(angle) * currentSize;
                const py = Math.sin(angle) * currentSize;
                ctx.moveTo(0, 0);
                ctx.lineTo(px, py);
            }
            ctx.strokeStyle = `hsla(${s.hue}, 60%, 50%, ${currentAlpha * 0.5})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();

            ctx.restore();
        }
    }

    // ---- Mouse Trail ----
    let trail = [];
    const TRAIL_LENGTH = 20;

    function updateTrail() {
        trail.push({ x: mouseX, y: mouseY, time: Date.now() });
        if (trail.length > TRAIL_LENGTH) trail.shift();
    }

    function drawTrail() {
        if (trail.length < 2) return;

        for (let i = 1; i < trail.length; i++) {
            const t = trail[i];
            const prev = trail[i - 1];
            const progress = i / trail.length;

            ctx.beginPath();
            ctx.moveTo(prev.x, prev.y);
            ctx.lineTo(t.x, t.y);
            ctx.strokeStyle = `rgba(0, 255, 180, ${progress * 0.3})`;
            ctx.lineWidth = progress * 2;
            ctx.stroke();
        }

        // Cursor glow
        if (trail.length > 0) {
            const last = trail[trail.length - 1];
            const gradient = ctx.createRadialGradient(
                last.x, last.y, 0,
                last.x, last.y, 30
            );
            gradient.addColorStop(0, "rgba(0, 255, 180, 0.15)");
            gradient.addColorStop(1, "rgba(0, 255, 180, 0)");
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(last.x, last.y, 30, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    // ---- Scanline effect ----
    function drawScanlines(time) {
        const scanY = (time * 0.05) % H;
        const gradient = ctx.createLinearGradient(0, scanY - 2, 0, scanY + 2);
        gradient.addColorStop(0, "rgba(0, 255, 170, 0)");
        gradient.addColorStop(0.5, "rgba(0, 255, 170, 0.03)");
        gradient.addColorStop(1, "rgba(0, 255, 170, 0)");
        ctx.fillStyle = gradient;
        ctx.fillRect(0, scanY - 2, W, 4);
    }

    // ---- Corner HUD Elements ----
    function drawHUD(time) {
        ctx.font = "10px 'Courier New', monospace";
        ctx.fillStyle = "rgba(0, 255, 170, 0.15)";

        // Top-left status
        const statusLines = [
            `SYS://AUTH_PORTAL`,
            `STATUS: ACTIVE`,
            `NODES: ${particles.length}`,
            `LINKS: ONLINE`,
        ];
        statusLines.forEach((line, idx) => {
            ctx.fillText(line, 15, 25 + idx * 14);
        });

        // Bottom-right coordinates
        if (mouseX > 0 && mouseY > 0) {
            ctx.fillText(
                `X:${Math.round(mouseX)} Y:${Math.round(mouseY)}`,
                W - 130,
                H - 15
            );
        }

        // Blinking cursor effect (top-right)
        if (Math.floor(time / 500) % 2 === 0) {
            ctx.fillStyle = "rgba(0, 255, 170, 0.2)";
            ctx.fillRect(W - 25, 15, 8, 14);
        }
    }

    // ---- Main Animation Loop ----
    function animate(time) {
        // Matrix rain draws its own fade overlay
        drawMatrixRain(time);
        drawShapes(time);
        drawParticles(time);
        drawConnections();
        drawRipples();
        updateTrail();
        drawTrail();
        drawScanlines(time);
        drawHUD(time);

        animationId = requestAnimationFrame(animate);
    }

    // ---- Event Listeners ----
    window.addEventListener("resize", resize);

    document.addEventListener("mousemove", function (e) {
        mouseX = e.clientX;
        mouseY = e.clientY;
    });

    document.addEventListener("click", function (e) {
        // Don't interfere with form elements
        const tag = e.target.tagName.toLowerCase();
        if (
            tag === "input" ||
            tag === "button" ||
            tag === "select" ||
            tag === "textarea" ||
            tag === "a" ||
            tag === "label" ||
            e.target.closest(".login-container") ||
            e.target.closest("#eimzoModal")
        ) {
            // Still show visual effect but don't prevent interaction
        }
        addRipple(e.clientX, e.clientY);
    });

    document.addEventListener("mouseleave", function () {
        mouseX = -1000;
        mouseY = -1000;
        trail = [];
    });

    // Touch support
    document.addEventListener("touchmove", function (e) {
        if (e.touches.length > 0) {
            mouseX = e.touches[0].clientX;
            mouseY = e.touches[0].clientY;
        }
    });

    document.addEventListener("touchstart", function (e) {
        if (e.touches.length > 0) {
            addRipple(e.touches[0].clientX, e.touches[0].clientY);
        }
    });

    document.addEventListener("touchend", function () {
        mouseX = -1000;
        mouseY = -1000;
        trail = [];
    });

    // ---- Initialize ----
    resize();
    initParticles();
    initShapes();

    // Fill initial background
    ctx.fillStyle = "rgba(15, 42, 36, 1)";
    ctx.fillRect(0, 0, W, H);

    animate(0);

    // Clean up on page unload
    window.addEventListener("beforeunload", function () {
        if (animationId) cancelAnimationFrame(animationId);
    });
})();
