(function () {
  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const scoreNode = document.getElementById("score");
  const lifeNode = document.getElementById("life");
  const stateNode = document.getElementById("state");
  const startBtn = document.getElementById("start");
  const result = document.getElementById("result");
  const finalScore = document.getElementById("final-score");
  const finalLine = document.getElementById("final-line");
  const rankNode = document.getElementById("rank");
  const againBtn = document.getElementById("again");

  let width = 0;
  let height = 0;
  let dpr = 1;
  let raf = 0;
  let last = 0;
  let playing = false;
  let pressing = false;
  let score = 0;
  let life = 3;
  let speed = 178;
  let distance = 0;
  let hitFlash = 0;
  let clouds = [];
  let gates = [];
  let sparks = [];
  const rider = { x: 82, y: 240, vy: 0, rot: 0 };

  function resize() {
    const viewport = window.visualViewport;
    width = Math.max(1, Math.round(viewport?.width || window.innerWidth));
    height = Math.max(320, Math.round(viewport?.height || window.innerHeight));
    dpr = Math.min(2, window.devicePixelRatio || 1);
    document.documentElement.style.setProperty("--game-height", `${height}px`);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    rider.x = Math.max(74, width * 0.26);
  }

  function reset() {
    score = 0;
    life = 3;
    speed = 178;
    distance = 0;
    hitFlash = 0;
    rider.y = height * 0.52;
    rider.vy = 0;
    rider.rot = 0;
    gates = [];
    sparks = [];
    clouds = Array.from({ length: 11 }, (_, i) => ({
      x: Math.random() * width,
      y: 82 + Math.random() * (height - 160),
      s: 0.7 + Math.random() * 1.15,
      a: 0.16 + Math.random() * 0.24,
      drift: 10 + Math.random() * 20,
    }));
    for (let i = 0; i < 4; i += 1) addGate(width + i * 148);
    updateHud();
  }

  function start() {
    reset();
    playing = true;
    last = performance.now();
    result.classList.remove("show");
    document.body.classList.add("playing");
    stateNode.textContent = "按住上升，松手下坠";
  }

  function addGate(x) {
    const gap = clamp(154 - score * 1.8, 108, 154);
    const marginTop = 96;
    const marginBottom = 86;
    const centerY = marginTop + gap / 2 + Math.random() * Math.max(1, height - marginTop - marginBottom - gap);
    gates.push({
      x,
      w: 54,
      gap,
      top: centerY - gap / 2,
      bottom: centerY + gap / 2,
      passed: false,
      phase: Math.random() * Math.PI * 2,
    });
  }

  function update(dt) {
    if (!playing) return;
    const gravity = 760;
    const lift = pressing ? -1040 : 0;
    rider.vy += (gravity + lift) * dt;
    rider.vy = clamp(rider.vy, -430, 520);
    rider.y += rider.vy * dt;
    rider.rot += ((rider.vy / 520) * 0.78 - rider.rot) * Math.min(1, dt * 8);

    distance += speed * dt;
    speed = Math.min(280, speed + dt * 4.8);
    hitFlash = Math.max(0, hitFlash - dt);

    for (const cloud of clouds) {
      cloud.x -= cloud.drift * dt;
      if (cloud.x < -150) {
        cloud.x = width + 90;
        cloud.y = 80 + Math.random() * (height - 150);
      }
    }

    for (const gate of gates) {
      gate.x -= speed * dt;
      gate.phase += dt * 1.8;
      if (!gate.passed && gate.x + gate.w < rider.x - 18) {
        gate.passed = true;
        score += 1;
        burst(rider.x + 18, rider.y, "#fff7bf", 8);
        updateHud();
      }
      if (Math.abs(gate.x - rider.x) < gate.w * 0.5 + 22) {
        const outside = rider.y < gate.top + 18 || rider.y > gate.bottom - 18;
        if (outside && !gate.hit) {
          gate.hit = true;
          damage();
        }
      }
    }
    gates = gates.filter((gate) => gate.x > -80);
    while (gates.length < 4) addGate(Math.max(width + 90, gates[gates.length - 1].x + 148 + Math.random() * 38));

    if (rider.y < 36 || rider.y > height - 42) damage(true);
    rider.y = clamp(rider.y, 34, height - 40);

    sparks = sparks.filter((spark) => spark.life > 0);
    for (const spark of sparks) {
      spark.life -= dt;
      spark.x += spark.vx * dt;
      spark.y += spark.vy * dt;
    }
  }

  function damage(edge) {
    if (hitFlash > 0) return;
    hitFlash = 0.72;
    life -= 1;
    stateNode.textContent = edge ? "剑光擦过云壁" : "云门擦身";
    burst(rider.x, rider.y, "#ff7a68", 16);
    flashBody();
    updateHud();
    if (life <= 0) end();
  }

  function end() {
    playing = false;
    pressing = false;
    document.body.classList.remove("playing");
    finalScore.textContent = score;
    rankNode.textContent = score >= 18 ? "穿云真君" : score >= 10 ? "踏云剑客" : score >= 5 ? "新晋御剑" : "云外初试";
    finalLine.textContent = `本次穿过 ${score} 道云门，最高速度 ${Math.round(speed)}。`;
    result.classList.add("show");
  }

  function updateHud() {
    scoreNode.textContent = score;
    lifeNode.textContent = Math.max(0, life);
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);
    drawSky();
    drawClouds();
    drawGates();
    drawRider();
    drawSparks();
    drawVignette();
  }

  function drawSky() {
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, "#8be8ff");
    grad.addColorStop(0.44, "#5fbde8");
    grad.addColorStop(1, "#14345a");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);

    ctx.globalAlpha = 0.25;
    ctx.strokeStyle = "#fff7bf";
    ctx.lineWidth = 1;
    for (let y = 92; y < height; y += 58) {
      ctx.beginPath();
      for (let x = 0; x <= width; x += 18) {
        const wave = Math.sin((x + distance * 0.32) * 0.025 + y * 0.02) * 7;
        if (x === 0) ctx.moveTo(x, y + wave);
        else ctx.lineTo(x, y + wave);
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function drawClouds() {
    for (const cloud of clouds) {
      ctx.save();
      ctx.globalAlpha = cloud.a;
      ctx.fillStyle = "#ffffff";
      cloudBlob(cloud.x, cloud.y, cloud.s);
      ctx.restore();
    }
  }

  function cloudBlob(x, y, s) {
    ctx.beginPath();
    ctx.arc(x, y, 18 * s, 0, Math.PI * 2);
    ctx.arc(x + 22 * s, y - 10 * s, 24 * s, 0, Math.PI * 2);
    ctx.arc(x + 52 * s, y, 20 * s, 0, Math.PI * 2);
    ctx.arc(x + 28 * s, y + 10 * s, 19 * s, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawGates() {
    for (const gate of gates) {
      const glow = gate.passed ? 0.18 : 0.46 + Math.sin(gate.phase) * 0.12;
      drawGatePart(gate.x, 0, gate.w, gate.top, glow, true);
      drawGatePart(gate.x, gate.bottom, gate.w, height - gate.bottom, glow, false);
      ctx.save();
      ctx.globalAlpha = 0.28;
      ctx.strokeStyle = "#fff7bf";
      ctx.lineWidth = 3;
      ctx.setLineDash([7, 8]);
      ctx.beginPath();
      ctx.moveTo(gate.x, gate.top);
      ctx.lineTo(gate.x, gate.bottom);
      ctx.stroke();
      ctx.restore();
    }
  }

  function drawGatePart(x, y, w, h, glow, top) {
    const grad = ctx.createLinearGradient(x, y, x + w, y);
    grad.addColorStop(0, "rgba(255, 255, 255, 0)");
    grad.addColorStop(0.32, "rgba(255, 247, 191, 0.82)");
    grad.addColorStop(1, "rgba(141, 241, 255, 0.64)");
    ctx.fillStyle = grad;
    roundRect(x - w / 2, y + (top ? -14 : 0), w, h + 14, 18);
    ctx.fill();
    ctx.strokeStyle = `rgba(255, 247, 191, ${glow})`;
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.moveTo(x - w / 2 + 8, top ? y + h : y);
    ctx.lineTo(x + w / 2 - 8, top ? y + h : y);
    ctx.stroke();
  }

  function drawRider() {
    ctx.save();
    ctx.translate(rider.x, rider.y);
    ctx.rotate(rider.rot);
    ctx.shadowColor = "#fff7bf";
    ctx.shadowBlur = 18;

    ctx.strokeStyle = "#fff7bf";
    ctx.lineWidth = 5;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(-34, 8);
    ctx.lineTo(36, -3);
    ctx.stroke();

    ctx.fillStyle = "#fff2a4";
    ctx.beginPath();
    ctx.moveTo(46, -5);
    ctx.lineTo(28, -13);
    ctx.lineTo(31, 4);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = "rgba(255,255,255,0.68)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-42, 12);
    ctx.lineTo(-74, 22);
    ctx.stroke();

    ctx.fillStyle = "#10243a";
    ctx.beginPath();
    ctx.arc(-2, -15, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-2, -7);
    ctx.lineTo(-10, 5);
    ctx.lineTo(7, 2);
    ctx.stroke();
    ctx.restore();
  }

  function drawSparks() {
    for (const spark of sparks) {
      ctx.save();
      ctx.globalAlpha = Math.max(0, spark.life / spark.maxLife);
      ctx.fillStyle = spark.color;
      ctx.beginPath();
      ctx.arc(spark.x, spark.y, spark.r, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  }

  function drawVignette() {
    if (hitFlash > 0) {
      ctx.save();
      ctx.globalAlpha = Math.min(0.5, hitFlash);
      ctx.fillStyle = "#ff665a";
      ctx.fillRect(0, 0, width, height);
      ctx.restore();
    }
    const grad = ctx.createRadialGradient(width / 2, height / 2, Math.min(width, height) * 0.2, width / 2, height / 2, Math.max(width, height) * 0.72);
    grad.addColorStop(0, "rgba(255,255,255,0)");
    grad.addColorStop(1, "rgba(5,12,25,0.32)");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);
  }

  function burst(x, y, color, count) {
    for (let i = 0; i < count; i += 1) {
      const angle = (Math.PI * 2 * i) / count + Math.random() * 0.28;
      const force = 70 + Math.random() * 150;
      sparks.push({
        x,
        y,
        vx: Math.cos(angle) * force,
        vy: Math.sin(angle) * force,
        r: 2 + Math.random() * 2.2,
        color,
        life: 0.45 + Math.random() * 0.28,
        maxLife: 0.72,
      });
    }
  }

  function roundRect(x, y, w, h, r) {
    const radius = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + w - radius, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
    ctx.lineTo(x + w, y + h - radius);
    ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
    ctx.lineTo(x + radius, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function flashBody() {
    document.body.classList.remove("hit");
    void document.body.offsetWidth;
    document.body.classList.add("hit");
    window.setTimeout(() => document.body.classList.remove("hit"), 240);
  }

  function loop(now) {
    const dt = Math.min(0.04, (now - last) / 1000 || 0);
    last = now;
    update(dt);
    draw();
    raf = requestAnimationFrame(loop);
  }

  function setPress(value) {
    pressing = value;
  }

  window.addEventListener("resize", resize);
  window.addEventListener("orientationchange", resize);
  window.visualViewport?.addEventListener("resize", resize);
  window.visualViewport?.addEventListener("scroll", resize);
  window.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    setPress(true);
  });
  window.addEventListener("pointerup", () => setPress(false));
  window.addEventListener("pointercancel", () => setPress(false));
  startBtn.addEventListener("click", start);
  againBtn.addEventListener("click", start);

  resize();
  reset();
  last = performance.now();
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(loop);
})();
