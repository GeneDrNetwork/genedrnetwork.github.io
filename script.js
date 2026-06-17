const canvas = document.querySelector("#network-canvas");
const ctx = canvas ? canvas.getContext("2d") : null;
const pointer = { x: 0, y: 0, active: false };
let particles = [];
let width = 0;
let height = 0;
let animationFrame = 0;

const colors = ["#e0f8ff", "#bff3ea", "#dcd0ff", "#ffd5ef", "#d8f7c1", "#fff0a7"];

function resizeCanvas() {
  if (!canvas || !ctx) return;

  const bounds = canvas.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  width = bounds.width;
  height = bounds.height;
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  createParticles();
}

function createParticles() {
  const count = Math.min(46, Math.max(22, Math.floor((width * height) / 10500)));
  particles = Array.from({ length: count }, (_, index) => ({
    x: Math.random() * width,
    y: Math.random() * height,
    vx: (Math.random() - 0.5) * 0.18,
    vy: (Math.random() - 0.5) * 0.18,
    size: 1.4 + Math.random() * 2.2,
    color: colors[index % colors.length],
  }));
}

function draw() {
  if (!ctx) return;

  ctx.clearRect(0, 0, width, height);

  for (const particle of particles) {
    particle.x += particle.vx;
    particle.y += particle.vy;

    if (particle.x < -20) particle.x = width + 20;
    if (particle.x > width + 20) particle.x = -20;
    if (particle.y < -20) particle.y = height + 20;
    if (particle.y > height + 20) particle.y = -20;

    if (pointer.active) {
      const dx = pointer.x - particle.x;
      const dy = pointer.y - particle.y;
      const distance = Math.hypot(dx, dy);

      if (distance < 110) {
        particle.x -= dx * 0.0014;
        particle.y -= dy * 0.0014;
      }
    }
  }

  drawLinks();
  drawParticles();
  animationFrame = requestAnimationFrame(draw);
}

function drawLinks() {
  for (let i = 0; i < particles.length; i += 1) {
    for (let j = i + 1; j < particles.length; j += 1) {
      const a = particles[i];
      const b = particles[j];
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const distance = Math.hypot(dx, dy);

      if (distance < 112) {
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = `rgba(255, 255, 255, ${0.24 * (1 - distance / 112)})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }
  }
}

function drawParticles() {
  for (const particle of particles) {
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
    ctx.fillStyle = particle.color;
    ctx.globalAlpha = 0.62;
    ctx.fill();
    ctx.globalAlpha = 1;
  }
}

function updatePointer(event) {
  if (!canvas) return;

  const bounds = canvas.getBoundingClientRect();
  pointer.x = event.clientX - bounds.left;
  pointer.y = event.clientY - bounds.top;
  pointer.active = true;
}

if (canvas && ctx) {
  window.addEventListener("resize", resizeCanvas);
  canvas.addEventListener("pointermove", updatePointer);
  canvas.addEventListener("pointerleave", () => {
    pointer.active = false;
  });

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    resizeCanvas();
    drawLinks();
    drawParticles();
  } else {
    resizeCanvas();
    draw();
  }
}

window.addEventListener("beforeunload", () => {
  cancelAnimationFrame(animationFrame);
});
