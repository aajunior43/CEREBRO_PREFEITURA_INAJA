/**
 * login.js — Autenticação da página de login
 * Integração com /api/auth/adm do backend Flask
 */

(function () {
  'use strict';

  // ── Elementos ──
  const form         = document.getElementById('login-form');
  const usuarioInput = document.getElementById('login-usuario');
  const senhaInput   = document.getElementById('login-senha');
  const toggleBtn    = document.getElementById('toggle-password');
  const eyeIcon      = document.getElementById('eye-icon');
  const eyeOffIcon   = document.getElementById('eye-off-icon');
  const loginBtn     = document.getElementById('login-btn');
  const btnText      = document.getElementById('login-btn-text');
  const btnIcon      = document.getElementById('login-btn-icon');
  const btnSpinner   = document.getElementById('login-btn-spinner');
  const errorBox     = document.getElementById('login-error');
  const errorText    = document.getElementById('login-error-text');

  // ── Estado ──
  let isSubmitting = false;

  // ── Toggle password visibility ──
  toggleBtn.addEventListener('click', () => {
    const isVisible = senhaInput.type === 'text';
    senhaInput.type = isVisible ? 'password' : 'text';
    eyeIcon.style.display   = isVisible ? 'block' : 'none';
    eyeOffIcon.style.display = isVisible ? 'none' : 'block';
    toggleBtn.title = isVisible ? 'Mostrar senha' : 'Ocultar senha';
  });

  // ── Remove error on input ──
  function clearError() {
    errorBox.style.display = 'none';
    senhaInput.classList.remove('error');
    usuarioInput.classList.remove('error');
  }

  usuarioInput.addEventListener('input', clearError);
  senhaInput.addEventListener('input', clearError);

  // ── Submit handler ──
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    const usuario = usuarioInput.value.trim();
    const senha   = senhaInput.value;

    if (!usuario) {
      showError('Informe o usuário');
      usuarioInput.classList.add('error');
      usuarioInput.focus();
      return;
    }

    if (!senha) {
      showError('Informe a senha');
      senhaInput.classList.add('error');
      senhaInput.focus();
      return;
    }

    setLoading(true);

    try {
      const res = await fetch('/api/auth/adm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario, senha }),
      });

      const data = await res.json();

      if (res.ok && data.ok) {
        // Sucesso — redireciona para a aplicação
        window.location.href = '/';
      } else {
        showError(data.error || 'Senha incorreta');
        senhaInput.classList.add('error');
        senhaInput.value = '';
        senhaInput.focus();
      }
    } catch (err) {
      showError('Erro de conexão. Tente novamente.');
      console.error('Login error:', err);
    } finally {
      setLoading(false);
    }
  });

  // ── Helpers ──
  function showError(msg) {
    errorText.textContent = msg;
    errorBox.style.display = 'flex';
  }

  function setLoading(loading) {
    isSubmitting = loading;
    loginBtn.disabled = loading;
    btnText.style.display   = loading ? 'none' : 'inline';
    btnIcon.style.display   = loading ? 'none' : 'block';
    btnSpinner.style.display = loading ? 'block' : 'none';
  }

  // ── Background canvas animation ──
  (function initCanvas() {
    const canvas = document.getElementById('login-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width, height, dots = [];
    const DOT_COUNT = 60;
    const CONNECTION_DIST = 120;

    function resize() {
      width  = canvas.width  = window.innerWidth;
      height = canvas.height = window.innerHeight;
      initDots();
    }

    function initDots() {
      dots = [];
      for (let i = 0; i < DOT_COUNT; i++) {
        dots.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.4,
          vy: (Math.random() - 0.5) * 0.4,
          r: Math.random() * 1.5 + 0.5,
          alpha: Math.random() * 0.4 + 0.1,
        });
      }
    }

    function draw() {
      ctx.clearRect(0, 0, width, height);

      // Update & draw dots
      for (const d of dots) {
        d.x += d.vx;
        d.y += d.vy;

        if (d.x < 0 || d.x > width)  d.vx *= -1;
        if (d.y < 0 || d.y > height) d.vy *= -1;

        ctx.beginPath();
        ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(59, 130, 246, ${d.alpha})`;
        ctx.fill();
      }

      // Draw connections
      for (let i = 0; i < dots.length; i++) {
        for (let j = i + 1; j < dots.length; j++) {
          const dx = dots[i].x - dots[j].x;
          const dy = dots[i].y - dots[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < CONNECTION_DIST) {
            const alpha = (1 - dist / CONNECTION_DIST) * 0.12;
            ctx.beginPath();
            ctx.moveTo(dots[i].x, dots[i].y);
            ctx.lineTo(dots[j].x, dots[j].y);
            ctx.strokeStyle = `rgba(99, 102, 241, ${alpha})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      requestAnimationFrame(draw);
    }

    window.addEventListener('resize', resize);
    resize();
    draw();
  })();

  // ── Floating particles ──
  (function initParticles() {
    const container = document.getElementById('login-particles');
    if (!container) return;

    const PARTICLE_COUNT = 15;

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const p = document.createElement('div');
      p.className = 'login-particle';
      p.style.left = `${Math.random() * 100}%`;
      p.style.animationDuration = `${8 + Math.random() * 12}s`;
      p.style.animationDelay = `${Math.random() * 10}s`;
      p.style.width = `${2 + Math.random() * 2}px`;
      p.style.height = p.style.width;
      p.style.opacity = `${0.2 + Math.random() * 0.4}`;
      container.appendChild(p);
    }
  })();

  // ── Focus no primeiro campo ──
  usuarioInput.focus();
})();
