// smallville_2026 web player — interactive timeline + loop + capture support.
// All dynamic text uses textContent (never innerHTML) to prevent XSS.

(async function () {
  const params = new URLSearchParams(location.search);
  const runName = params.get("run") || "cafe-morning-v2";
  const captureMode = params.get("capture") === "1";
  const autoplay = params.get("autoplay") !== "0";
  const loopEnabled = params.get("loop") !== "0";

  // --- helpers ---
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // --- load data ---
  let data;
  if (window.__embedded_data) {
    data = window.__embedded_data;
  } else {
    try {
      const res = await fetch(`data/${encodeURIComponent(runName)}/events.json`);
      if (!res.ok) throw new Error(res.statusText);
      data = await res.json();
    } catch (e) {
      const msg = el("div", null,
        "Could not load simulation data. " +
        "Build a standalone version: py scripts/build_standalone.py --run <name>, " +
        "or serve via: py -m http.server 8000 --directory web");
      msg.style.cssText = "padding:40px;color:#7d7a72;text-align:center;line-height:1.7";
      document.getElementById("events").appendChild(msg);
      return;
    }
  }

  document.getElementById("run-name").textContent =
    `${data.meta.run_name} \u2014 ${data.meta.world.name}`;

  const totalTicks = data.ticks.length;
  const personaById = Object.fromEntries(data.meta.personas.map((p) => [p.id, p]));
  const locById = Object.fromEntries(data.meta.locations.map((l) => [l.id, l]));

  // --- controls ---
  const btnPlay = document.getElementById("btn-play");
  const btnPrev = document.getElementById("btn-prev");
  const btnNext = document.getElementById("btn-next");
  const scrubber = document.getElementById("scrubber");
  const speedSel = document.getElementById("speed");
  scrubber.max = totalTicks - 1;
  scrubber.value = 0;

  let playing = false;
  let playTimer = null;
  let currentTick = -1;
  function getTickMs() { return parseInt(speedSel.value, 10); }

  // --- locations panel ---
  const locList = document.getElementById("locations-list");
  function initLocations() {
    locList.textContent = "";
    for (const loc of data.meta.locations) {
      const li = document.createElement("li");
      li.dataset.locId = loc.id;
      li.appendChild(el("div", "loc-name", loc.name));
      const occ = el("div", "occupants");
      occ.id = `occ-${loc.id}`;
      li.appendChild(occ);
      locList.appendChild(li);
    }
  }
  initLocations();

  function updateOccupants(tickData) {
    for (const loc of data.meta.locations) {
      const occEl = document.getElementById(`occ-${loc.id}`);
      if (occEl) occEl.textContent = "";
    }
    for (const p of tickData.personas) {
      const occEl = document.getElementById(`occ-${p.location}`);
      if (!occEl) continue;
      const span = el("span", null, personaById[p.id]?.icon || "\u{1F642}");
      span.title = `${personaById[p.id]?.name || p.id}: ${p.activity}`;
      occEl.appendChild(span);
    }
  }

  function formatTime(iso) {
    const d = new Date(iso);
    const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${days[d.getDay()]} ${hh}:${mm}`;
  }

  // --- render event row (XSS-safe: all text via textContent) ---
  function renderEvent(event, tickData) {
    const actor = personaById[event.actor];
    const icon = actor?.icon || "\u2022";
    const name = actor?.name || event.actor;
    const time = formatTime(tickData.time);
    const row = el("div", `event ${event.type}`);

    row.appendChild(el("div", "icon", icon));
    row.appendChild(el("div", "time", time));

    const body = el("div", "body");

    switch (event.type) {
      case "move": {
        const to = locById[event.to]?.name || event.to;
        body.appendChild(el("span", "name", name));
        body.appendChild(el("span", "kind", `\u2192 ${to}`));
        body.appendChild(document.createTextNode(event.text || ""));
        break;
      }
      case "chat": {
        const tgt = personaById[event.target]?.name || event.target;
        body.appendChild(el("span", "name", name));
        body.appendChild(el("span", "kind", `to ${tgt}`));
        body.appendChild(document.createTextNode(event.text));
        break;
      }
      case "reflect":
        body.appendChild(el("span", "name", name));
        body.appendChild(el("span", "kind", "reflects"));
        body.appendChild(document.createTextNode(event.text));
        break;
      case "speak_intent":
        return null;
      case "action":
      default:
        body.appendChild(el("span", "name", name));
        body.appendChild(document.createTextNode(event.text));
    }

    row.appendChild(body);
    return row;
  }

  // --- tick rendering ---
  const eventsEl = document.getElementById("events");
  let renderedUpTo = -1;

  function appendTick(i) {
    const tick = data.ticks[i];
    if (!tick) return;

    const divider = document.createElement("hr");
    divider.className = "tick-divider";
    eventsEl.appendChild(divider);
    eventsEl.appendChild(
      el("div", "tick-label", `\u2014 tick ${tick.tick} \u00b7 ${formatTime(tick.time)} \u2014`)
    );

    const hasChat = tick.events.some((e) => e.type === "chat");
    for (const event of tick.events) {
      if (event.type === "speak_intent" && hasChat) continue;
      const row = renderEvent(event, tick);
      if (row) eventsEl.appendChild(row);
    }

    updateOccupants(tick);
    renderedUpTo = i;
  }

  function updateHeader(i) {
    const tick = data.ticks[i];
    if (!tick) return;
    document.getElementById("sim-clock").textContent = formatTime(tick.time);
    document.getElementById("tick-indicator").textContent = `tick ${i + 1} / ${totalTicks}`;
    scrubber.value = i;
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      const tl = document.getElementById("timeline");
      tl.scrollTop = tl.scrollHeight;
    });
  }

  function goToTick(target) {
    if (target < 0) target = 0;
    if (target >= totalTicks) target = totalTicks - 1;
    if (target <= renderedUpTo) {
      eventsEl.textContent = "";
      initLocations();
      renderedUpTo = -1;
      for (let j = 0; j <= target; j++) appendTick(j);
    } else {
      for (let j = renderedUpTo + 1; j <= target; j++) appendTick(j);
    }
    currentTick = target;
    updateHeader(target);
    scrollToBottom();
  }

  function reset() {
    eventsEl.textContent = "";
    initLocations();
    renderedUpTo = -1;
    currentTick = -1;
    scrubber.value = 0;
  }

  // --- playback ---
  function stopPlayback() {
    playing = false;
    if (playTimer) clearTimeout(playTimer);
    playTimer = null;
    btnPlay.textContent = "\u25B6";
  }

  function startPlayback() {
    playing = true;
    btnPlay.textContent = "\u23F8";
    scheduleNext();
  }

  function scheduleNext() {
    if (!playing) return;
    playTimer = setTimeout(() => {
      const next = currentTick + 1;
      if (next >= totalTicks) {
        if (loopEnabled) {
          stopPlayback();
          setTimeout(() => { reset(); startPlayback(); }, 2000);
        } else {
          stopPlayback();
        }
        return;
      }
      goToTick(next);
      scheduleNext();
    }, getTickMs());
  }

  function togglePlay() {
    if (playing) stopPlayback();
    else { if (currentTick >= totalTicks - 1) reset(); startPlayback(); }
  }

  // --- control bindings ---
  btnPlay.addEventListener("click", togglePlay);
  btnPrev.addEventListener("click", () => { stopPlayback(); goToTick(Math.max(0, currentTick - 1)); });
  btnNext.addEventListener("click", () => { stopPlayback(); goToTick(Math.min(totalTicks - 1, currentTick + 1)); });
  scrubber.addEventListener("input", () => { stopPlayback(); goToTick(parseInt(scrubber.value, 10)); });
  speedSel.addEventListener("change", () => { if (playing) { clearTimeout(playTimer); scheduleNext(); } });

  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    switch (e.key) {
      case " ": e.preventDefault(); togglePlay(); break;
      case "ArrowLeft": e.preventDefault(); stopPlayback(); goToTick(Math.max(0, currentTick - 1)); break;
      case "ArrowRight": e.preventDefault(); stopPlayback(); goToTick(Math.min(totalTicks - 1, currentTick + 1)); break;
      case "Home": e.preventDefault(); stopPlayback(); reset(); goToTick(0); break;
      case "End": e.preventDefault(); stopPlayback(); goToTick(totalTicks - 1); break;
    }
  });

  // --- capture mode ---
  if (captureMode) {
    window.__sim_total_frames = totalTicks;
    window.__sim_tick_to = (i) => goToTick(i);
    window.__sim_ready = true;
    return;
  }

  if (autoplay) { goToTick(0); startPlayback(); }
  else goToTick(0);
})();
