self.addEventListener("install", event => {
    console.log("Service Worker installed");
  });
  
  self.addEventListener("fetch", event => {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response("Offline mode: You're not connected to the internet.");
      })
    );
  });
  