(function () {
  const currentScript = document.currentScript;
  const endpoint = currentScript && currentScript.getAttribute("data-endpoint")
    ? currentScript.getAttribute("data-endpoint")
    : "/api/visits";

  function getVisitorId() {
    const key = "issue266_visitor_id";
    const existing = localStorage.getItem(key);

    if (existing) {
      return existing;
    }

    const value = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + "-" + String(Math.random()).slice(2);
    localStorage.setItem(key, value);
    return value;
  }

  function getDevice() {
    const ua = navigator.userAgent;

    if (/tablet|ipad|playbook|silk/i.test(ua)) {
      return "tablet";
    }

    if (/mobi|android|iphone|ipod|blackberry|iemobile|opera mini/i.test(ua)) {
      return "mobile";
    }

    return "desktop";
  }

  async function getLocation() {
    try {
      const response = await fetch("https://ipapi.co/json/", { cache: "no-store" });

      if (!response.ok) {
        return {};
      }

      const data = await response.json();

      return {
        ip: data.ip || null,
        city: data.city || null
      };
    } catch (error) {
      return {};
    }
  }

  function send(payload) {
    const body = JSON.stringify(payload);

    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });

      if (navigator.sendBeacon(endpoint, blob)) {
        return;
      }
    }

    fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: body,
      keepalive: true
    }).catch(function () {});
  }

  async function track() {
    const location = await getLocation();

    send({
      visitor_id: getVisitorId(),
      ip: location.ip || null,
      city: location.city || null,
      device: getDevice(),
      user_agent: navigator.userAgent,
      page_url: window.location.href,
      referrer: document.referrer || null,
      visited_at: new Date().toISOString()
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", track);
  } else {
    track();
  }
})();
