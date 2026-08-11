(() => {
  const DEFAULT = {
    left_rim: 'd',
    left_face: 'f',
    right_face: 'j',
    right_rim: 'k'
  };

  const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = wsProtocol + '//' + location.host + '/ws';
  const USB_LOST_ICON = '/static/usb-lost.svg';
  const preloadedUsbLostIcon = new Image();
  preloadedUsbLostIcon.src = USB_LOST_ICON;
  const WIFI_LOST_ICON = '/static/wifi-lost.svg';
  const preloadedWifiLostIcon = new Image();
  preloadedWifiLostIcon.src = WIFI_LOST_ICON;
  const WIFI_RECONNECT_ICON = '/static/wifi-reconnect.svg';
  const preloadedWifiReconnectIcon = new Image();
  preloadedWifiReconnectIcon.src = WIFI_RECONNECT_ICON;
  const cachedIconUrls = {};
  const ICON_CACHE_NAME = 'bachitouch-icons-v1';

  function getCachedIconSrc(url) {
    return cachedIconUrls[url] || url;
  }

  function cacheIconResources(url) {
    if (!('caches' in window)) return;
    caches.open(ICON_CACHE_NAME).then((cache) => {
      cache.add(url).catch(() => {});
    }).catch(() => {});
    fetch(url, { cache: 'force-cache' }).then((response) => {
      if (!response.ok) return;
      return response.blob();
    }).then((blob) => {
      if (!blob) return;
      cachedIconUrls[url] = URL.createObjectURL(blob);
    }).catch(() => {});
  }

  // Attempt to proactively cache these icons so they'll be available when reconnect/disconnect happens.
  (function cacheConnectivityIcons() {
    const icons = [WIFI_RECONNECT_ICON, WIFI_LOST_ICON, USB_LOST_ICON];
    try {
      if ('caches' in window) {
        caches.open(ICON_CACHE_NAME).then((cache) => {
          cache.addAll(icons).catch(() => {
            icons.forEach((u) => cache.add(u).catch(() => {}));
          });
        }).catch(() => {/* ignore cache open errors */});
      }
    } catch (e) {
      // ignore
    }
    icons.forEach((u) => {
      try {
        const img = new Image();
        img.src = u;
      } catch (e) {}
      cacheIconResources(u);
    });
  })();
  let ws;
  let drumBounceTimer = null;
  let pendingTaps = [];
  let pingCount = 0;
  let lastPingMs = null;
  let pingTimer = null;
  let pingTimeout = null;
  let pingStart = 0;
  let wiredConnectionMode = false;
  let connectionState = 'connecting';
  const PING_INTERVAL = 1000;
  const PING_TIMEOUT = 5000;
  const MAX_PENDING_TAPS = 8;

  function connect() {
    setConnectionType();
    setConnectionStatus('connecting');
    ws = new WebSocket(wsUrl);
    window.ws = ws;
    ws.addEventListener('open', () => {
      setConnectionStatus('connected');
      sendMapping(loadMapping());
      flushQueuedTaps();
      startPingLoop();
    });
    ws.addEventListener('message', handleWsMessage);
    ws.addEventListener('close', () => {
      setConnectionStatus('disconnected');
      stopPingLoop();
      ws = null;
      setTimeout(connect, 1000);
    });
    ws.addEventListener('error', () => {
      setConnectionStatus('disconnected');
    });
  }

  function handleWsMessage(event) {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (e) {
      return;
    }

    if (data.type === 'pong') {
      pingCount += 1;
      lastPingMs = Math.round(performance.now() - pingStart);
      setPingStatus(lastPingMs);
      resetPingTimeout();
    }
  }

  function flushQueuedTaps() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    while (pendingTaps.length) {
      ws.send(JSON.stringify({ type: 'tap', control: pendingTaps.shift() }));
    }
  }

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
      return;
    }

    if (obj.type === 'tap') {
      if (pendingTaps.length < MAX_PENDING_TAPS) {
        pendingTaps.push(obj.control);
      }
    }
  }

  function setConnectionStatus(state) {
    connectionState = state;
    // Update connection state and UI chip only (legacy status elements removed)
    setConnectionType();
  }

  function getConnectionTypeInfo() {
    const host = location.hostname.toLowerCase();
    if (host === 'localhost' || host === '127.0.0.1' || host === '::1') {
      if (connectionState === 'disconnected' || connectionState === 'connecting') {
        return { icon: USB_LOST_ICON, label: 'USB Disconnected' };
      }
      return { icon: '/static/usb.svg', label: 'Wired' };
    }
    // Wireless: show human-friendly status in the chip label
    if (connectionState === 'connected') {
      return { icon: '/static/wifi.svg', label: 'Wireless' };
    }
    if (connectionState === 'connecting') {
      return { icon: WIFI_RECONNECT_ICON, label: 'Reconnecting' };
    }
    // disconnected
    return { icon: WIFI_LOST_ICON, label: 'Lost' };
  }

  function setConnectionType() {
    const typeChip = document.getElementById('connection-type');
    const icon = document.getElementById('connection-icon');
    const label = document.getElementById('connection-label');
    if (!typeChip || !icon || !label) return;

    const { icon: iconSrc, label: typeLabel } = getConnectionTypeInfo();
    icon.src = getCachedIconSrc(iconSrc);
    icon.alt = `${typeLabel || 'Wireless'} connection icon`;
    label.textContent = typeLabel;
    icon.classList.toggle('no-label', !typeLabel);

    const wiredMode = typeLabel === 'Wired' || typeLabel === 'USB Disconnected';
    wiredConnectionMode = wiredMode;
    // Mark chip as wireless or wired for CSS targeting
    typeChip.classList.toggle('wireless', !wiredMode);
    typeChip.classList.toggle('wired', wiredMode);
    typeChip.classList.toggle('usb-disconnected', (connectionState === 'disconnected' || connectionState === 'connecting') && wiredMode);
    typeChip.classList.toggle('wifi-disconnected', connectionState === 'disconnected' && !wiredMode);
    // Show yellow reconnecting state on the chip when trying to reconnect (only for wireless)
    typeChip.classList.toggle('connecting', connectionState === 'connecting' && !wiredMode);
    // Show connected styling when connected
    typeChip.classList.toggle('connected', connectionState === 'connected');
    // legacy status elements removed; connection chip is single source of truth
    updatePingLabel();
  }

  function updatePingLabel() {
    const pingEl = document.getElementById('ping-status');
    if (!pingEl) return;
    const host = location.hostname.toLowerCase();
    const isWiredMode = host === 'localhost' || host === '127.0.0.1' || host === '::1';
    // Hide the ping display whenever the connection is disconnected or wired mode is in a disconnect/reconnect state
    if (connectionState === 'disconnected' || (isWiredMode && connectionState === 'connecting')) {
      pingEl.style.display = 'none';
      pingEl.classList.remove('ping-good','ping-warn','ping-bad');
      return;
    }
    // Ensure ping element is visible when connection exists
    pingEl.style.display = '';

    if (wiredConnectionMode) {
      pingEl.textContent = lastPingMs == null ? '--' : `${lastPingMs} ms`;
    } else {
      pingEl.textContent = lastPingMs == null ? '--' : `${lastPingMs} ms`;
    }
    updatePingBorder(lastPingMs);
  }

  function setPingStatus(ms) {
    const pingEl = document.getElementById('ping-status');
    if (!pingEl) return;
    lastPingMs = ms;
    const host = location.hostname.toLowerCase();
    const isWiredMode = host === 'localhost' || host === '127.0.0.1' || host === '::1';
    // Hide ping immediately if the connection is disconnected or wired mode is reconnecting
    if (connectionState === 'disconnected' || (isWiredMode && connectionState === 'connecting')) {
      pingEl.style.display = 'none';
      pingEl.classList.remove('ping-good','ping-warn','ping-bad');
      return;
    }
    pingEl.style.display = '';
    if (wiredConnectionMode) {
      pingEl.textContent = ms == null ? '--' : `${ms} ms`;
    } else {
      pingEl.textContent = ms == null ? '--' : `${ms} ms`;
    }
    updatePingBorder(ms);
  }

  function updatePingBorder(ms) {
    const pingEl = document.getElementById('ping-status');
    if (!pingEl) return;
    // clear existing classes
    pingEl.classList.remove('ping-good','ping-warn','ping-urgent','ping-bad');
    if (connectionState === 'disconnected' || ms == null) {
      pingEl.style.setProperty('box-shadow', 'none', 'important');
      return;
    }
    if (ms < 35) pingEl.classList.add('ping-good');
    else if (ms < 60) pingEl.classList.add('ping-warn');
    else if (ms < 100) pingEl.classList.add('ping-urgent');
    else pingEl.classList.add('ping-bad');
    // Wired mode should not show the ping inner border
    if (wiredConnectionMode) {
      pingEl.style.setProperty('box-shadow', 'none', 'important');
    } else {
      pingEl.style.removeProperty('box-shadow');
    }
  }

  function startPingLoop() {
    stopPingLoop();
    resetPingTimeout();
    pingTimer = window.setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        pingStart = performance.now();
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, PING_INTERVAL);
  }

  function resetPingTimeout() {
    if (pingTimeout) {
      window.clearTimeout(pingTimeout);
    }
    pingTimeout = window.setTimeout(() => {
      setConnectionStatus('disconnected');
      setPingStatus(null);
    }, PING_TIMEOUT);
  }

  function stopPingLoop() {
    if (pingTimer) {
      window.clearInterval(pingTimer);
      pingTimer = null;
    }
    if (pingTimeout) {
      window.clearTimeout(pingTimeout);
      pingTimeout = null;
    }
  }

  function sendMapping(m) { send({ type: 'mapping', mappings: m }); }
  function sendTap(control) {
    send({ type: 'tap', control });
  }

  function loadMapping() {
    try {
      const raw = localStorage.getItem('taiko_mappings');
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return DEFAULT;
  }

  function saveMapping(m) { localStorage.setItem('taiko_mappings', JSON.stringify(m)); }
  function loadTouchZonePreview() {
    return localStorage.getItem('taiko_show_touch_zones') === 'true';
  }
  function saveTouchZonePreview(enabled) {
    localStorage.setItem('taiko_show_touch_zones', enabled ? 'true' : 'false');
  }
  function loadTouchZoneOpacity() {
    const raw = localStorage.getItem('taiko_touch_zone_opacity');
    const opacity = parseFloat(raw);
    if (!isNaN(opacity) && opacity >= 0.1 && opacity <= 0.8) {
      return opacity;
    }
    return 0.22;
  }
  function saveTouchZoneOpacity(value) {
    localStorage.setItem('taiko_touch_zone_opacity', value.toString());
  }
  function setTouchZoneOpacity(value) {
    document.documentElement.style.setProperty('--touch-zone-opacity', value.toString());
  }
  function setTouchZonePreview(enabled) {
    document.body.classList.toggle('show-touch-zones', enabled);
  }

  function loadMobileView() {
    return localStorage.getItem('taiko_mobile_view') === 'true';
  }
  function saveMobileView(enabled) {
    localStorage.setItem('taiko_mobile_view', enabled ? 'true' : 'false');
  }
  function setMobileView(enabled) {
    document.body.classList.toggle('mobile-view', enabled);
    const btnMobileView = document.getElementById('btn-mobile-view');
    if (btnMobileView) {
      btnMobileView.classList.toggle('active', enabled);
    }
  }

  function getSelectKeyLabel(control, mappings) {
    const rimControl = control === 'left_rim_shift' ? 'left_rim' : 'right_rim';
    return `SHIFT+${(mappings[rimControl] || DEFAULT[rimControl]).toUpperCase()}`;
  }

  function updateKeyOverlayLabels(mappings) {
    const overlayButtons = document.querySelectorAll('.key-overlay [data-control]');
    overlayButtons.forEach((button) => {
      const control = button.dataset.control;
      if (!control) return;
      if (control === 'left_rim_shift' || control === 'right_rim_shift') {
        button.textContent = getSelectKeyLabel(control, mappings);
      } else {
        button.textContent = (mappings[control] || DEFAULT[control]).toUpperCase();
      }
    });
  }

  function setMappingFields() {
    const mappings = loadMapping();
    ['left_rim', 'left_face', 'right_face', 'right_rim'].forEach((control) => {
      const el = document.getElementById('map-' + control.replace('_', '-'));
      if (el) el.value = (mappings[control] || DEFAULT[control]).toUpperCase();
    });
    const previewEnabled = loadTouchZonePreview();
    const previewToggle = document.getElementById('toggle-touch-zones');
    if (previewToggle) {
      previewToggle.checked = previewEnabled;
    }
    const opacity = loadTouchZoneOpacity();
    const opacityInput = document.getElementById('touch-zone-opacity');
    const opacityValue = document.getElementById('touch-zone-opacity-value');
    if (opacityInput) opacityInput.value = String(Math.round(opacity * 100));
    if (opacityValue) opacityValue.textContent = `${Math.round(opacity * 100)}%`;
    setTouchZoneOpacity(opacity);
    updateKeyOverlayLabels(mappings);
    const scale = loadScale();
    const scaleInput = document.getElementById('drum-scale');
    const scaleValue = document.getElementById('drum-scale-value');
    if (scaleInput) scaleInput.value = scale;
    if (scaleValue) scaleValue.textContent = `${Math.round(scale * 100)}%`;
    updateDrumScale(scale);
    setTouchZonePreview(previewEnabled);
  }

  function readMappingFields() {
    const mapping = {};
    ['left_rim', 'left_face', 'right_face', 'right_rim'].forEach((control) => {
      const el = document.getElementById('map-' + control.replace('_', '-'));
      let value = el?.value.trim() || DEFAULT[control];
      value = value.slice(0, 1).toUpperCase();
      mapping[control] = value.toLowerCase();
    });
    return mapping;
  }

  function loadScale() {
    const raw = localStorage.getItem('taiko_drum_scale');
    const scale = parseFloat(raw);
    if (!isNaN(scale) && scale >= 0.75 && scale <= 2.0) {
      return scale;
    }
    return 1;
  }

  function saveScale(scale) {
    localStorage.setItem('taiko_drum_scale', scale.toString());
  }

  function updateDrumScale(scale) {
    const drum = document.getElementById('drum');
    if (drum) {
      drum.style.setProperty('--drum-scale', scale);
    }
  }

  function triggerDrumBounce() {
    const drum = document.getElementById('drum');
    if (!drum) return;
    drum.classList.remove('bounce');
    if (drumBounceTimer) {
      window.clearTimeout(drumBounceTimer);
      drumBounceTimer = null;
    }
    void drum.offsetWidth;
    drum.classList.add('bounce');
    drumBounceTimer = window.setTimeout(() => {
      drum.classList.remove('bounce');
      drumBounceTimer = null;
    }, 40);
  }

  let keyOverlayTimer = null;

  function getDisplayedImageRect(drumImage) {
    if (!drumImage || !drumImage.naturalWidth || !drumImage.naturalHeight) return null;
    const drum = drumImage.parentElement;
    if (!drum) return null;

    const drumWidth = drum.clientWidth;
    const drumHeight = drum.clientHeight;
    const imageRatio = drumImage.naturalWidth / drumImage.naturalHeight;
    const drumRatio = drumWidth / drumHeight;

    let displayedWidth;
    let displayedHeight;
    if (drumRatio > imageRatio) {
      displayedHeight = drumHeight;
      displayedWidth = displayedHeight * imageRatio;
    } else {
      displayedWidth = drumWidth;
      displayedHeight = displayedWidth / imageRatio;
    }

    const offsetX = (drumWidth - displayedWidth) / 2;
    const offsetY = drumHeight - displayedHeight;
    return {
      left: offsetX,
      top: offsetY,
      width: displayedWidth,
      height: displayedHeight,
    };
  }

  function updateFaceZones() {
    const drum = document.getElementById('drum');
    const drumImage = document.getElementById('drum-image');
    const leftFace = document.querySelector('.touch-area.face.left');
    const rightFace = document.querySelector('.touch-area.face.right');
    if (!drum || !drumImage || !leftFace || !rightFace) return;

    const imageRect = getDisplayedImageRect(drumImage);
    if (!imageRect) return;

    const faceWidth = Math.round(imageRect.width * 0.46);
    const faceHeight = Math.round(imageRect.height * 0.99);
    const halfWidth = imageRect.width / 2;
    const bottomOffset = Math.round(imageRect.height - faceHeight);

    leftFace.style.left = `${Math.round(imageRect.left + halfWidth - faceWidth)}px`;
    leftFace.style.top = `${imageRect.top + bottomOffset}px`;
    leftFace.style.width = `${faceWidth}px`;
    leftFace.style.height = `${faceHeight}px`;
    leftFace.style.right = 'auto';

    rightFace.style.left = `${Math.round(imageRect.left + halfWidth)}px`;
    rightFace.style.top = `${imageRect.top + bottomOffset}px`;
    rightFace.style.width = `${faceWidth}px`;
    rightFace.style.height = `${faceHeight}px`;
    rightFace.style.right = 'auto';
  }

  function triggerKeyOverlayResponse(control) {
    const overlay = document.querySelector('.key-overlay');
    if (!overlay) return;
    let responseClass;
    if (control === 'left_rim') responseClass = 'left-rim-response';
    else if (control === 'right_rim') responseClass = 'right-rim-response';
    else if (control === 'left_face') responseClass = 'left-face-response';
    else responseClass = 'right-face-response';
    overlay.classList.remove('left-rim-response', 'right-rim-response', 'left-face-response', 'right-face-response');
    if (keyOverlayTimer) {
      window.clearTimeout(keyOverlayTimer);
      keyOverlayTimer = null;
    }
    void overlay.offsetWidth;
    overlay.classList.add(responseClass);
    keyOverlayTimer = window.setTimeout(() => {
      overlay.classList.remove('left-rim-response', 'right-rim-response', 'left-face-response', 'right-face-response');
      keyOverlayTimer = null;
    }, 120);
  }

  function setBackdropVisible(visible) {
    const backdrop = document.getElementById('panel-backdrop');
    if (!backdrop) return;
    backdrop.classList.toggle('hidden', !visible);
  }

  function closePanels() {
    document.getElementById('settings-panel').classList.add('hidden');
    document.getElementById('help-panel').classList.add('hidden');
    setBackdropVisible(false);
  }

  function togglePanel(panelId) {
    const settingsPanel = document.getElementById('settings-panel');
    const helpPanel = document.getElementById('help-panel');
    const isSettings = panelId === 'settings-panel';
    const target = isSettings ? settingsPanel : helpPanel;
    const other = isSettings ? helpPanel : settingsPanel;
    const opening = target.classList.contains('hidden');

    target.classList.toggle('hidden');
    other.classList.add('hidden');
    setBackdropVisible(opening);
  }

  function updateHideButtonState(hidden) {
    const buttonGroup = document.getElementById('button-group');
    const btnHide = document.getElementById('btn-hide');
    const btnMobileView = document.getElementById('btn-mobile-view');
    const btnFullscreen = document.getElementById('btn-fullscreen');
    const btnPause = document.getElementById('btn-pause');
    if (hidden) {
      buttonGroup.classList.add('hidden');
      if (btnMobileView) {
        btnMobileView.classList.add('hidden');
      }
      if (btnFullscreen) {
        btnFullscreen.classList.add('hidden');
      }
      if (btnPause) {
        btnPause.classList.add('compact');
      }
      if (btnHide) {
        btnHide.classList.add('compact');
      }
      const hideIcon = btnHide.querySelector('img');
      if (hideIcon) {
        hideIcon.src = '/static/show.svg';
        hideIcon.alt = 'Show UI';
      }
    } else {
      buttonGroup.classList.remove('hidden');
      if (btnMobileView) {
        btnMobileView.classList.remove('hidden');
      }
      if (btnFullscreen) {
        btnFullscreen.classList.remove('hidden');
      }
      if (btnPause) {
        btnPause.classList.remove('compact');
      }
      if (btnHide) {
        btnHide.classList.remove('compact');
      }
      const hideIcon = btnHide.querySelector('img');
      if (hideIcon) {
        hideIcon.src = '/static/hide.svg';
        hideIcon.alt = 'Hide UI';
      }
    }
  }

  function wireUI() {
    setMappingFields();

    document.getElementById('btn-settings').addEventListener('click', () => {
      togglePanel('settings-panel');
    });
    document.getElementById('btn-help').addEventListener('click', () => {
      togglePanel('help-panel');
    });
    document.getElementById('close-settings').addEventListener('click', () => {
      document.getElementById('settings-panel').classList.add('hidden');
      setBackdropVisible(false);
    });
    document.getElementById('close-help').addEventListener('click', () => {
      document.getElementById('help-panel').classList.add('hidden');
      setBackdropVisible(false);
    });
    document.getElementById('panel-backdrop').addEventListener('click', closePanels);
    document.getElementById('btn-hide').addEventListener('click', () => {
      const buttonGroup = document.getElementById('button-group');
      const hidden = !buttonGroup.classList.contains('hidden');
      updateHideButtonState(hidden);
    });

    const btnFullscreen = document.getElementById('btn-fullscreen');
    if (btnFullscreen) {
      const fullscreenSupported = !!(
        document.documentElement.requestFullscreen ||
        document.documentElement.webkitRequestFullscreen ||
        document.documentElement.msRequestFullscreen
      );

      if (!fullscreenSupported) {
        // Hide or disable fullscreen on platforms that don't support the Fullscreen API
        btnFullscreen.style.display = 'none';
        btnFullscreen.title = 'On iOS Safari: use Share → Add to Home Screen for fullscreen';
      } else {
        btnFullscreen.addEventListener('click', () => {
          const docEl = document.documentElement;
          const isFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement);
          if (!isFullscreen) {
            if (docEl.requestFullscreen) docEl.requestFullscreen().catch(() => {});
            else if (docEl.webkitRequestFullscreen) docEl.webkitRequestFullscreen();
            else if (docEl.msRequestFullscreen) docEl.msRequestFullscreen();
          } else {
            if (document.exitFullscreen) document.exitFullscreen().catch(() => {});
            else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
            else if (document.msExitFullscreen) document.msExitFullscreen();
          }
        });

        function updateFullscreenIcon() {
          if (!btnFullscreen) return;
          const fullscreenIcon = btnFullscreen.querySelector('img');
          if (!fullscreenIcon) return;
          const isFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement);
          if (isFullscreen) {
            fullscreenIcon.src = '/static/exitfullscreen.svg';
            fullscreenIcon.alt = 'Exit fullscreen';
          } else {
            fullscreenIcon.src = '/static/fullscreen.svg';
            fullscreenIcon.alt = 'Fullscreen';
          }
        }

        document.addEventListener('fullscreenchange', updateFullscreenIcon);
        document.addEventListener('webkitfullscreenchange', updateFullscreenIcon);
        document.addEventListener('MSFullscreenChange', updateFullscreenIcon);
      }
    }

    const btnMobileView = document.getElementById('btn-mobile-view');
    if (btnMobileView) {
      btnMobileView.addEventListener('click', () => {
        const enabled = !document.body.classList.contains('mobile-view');
        setMobileView(enabled);
        saveMobileView(enabled);
        window.requestAnimationFrame(updateFaceZones);
      });
    }

    document.getElementById('save-mapping').addEventListener('click', () => {
      const mapping = readMappingFields();
      const scale = parseFloat(document.getElementById('drum-scale').value) || 1;
      const previewEnabled = document.getElementById('toggle-touch-zones')?.checked ?? false;
      const opacityPercent = parseFloat(document.getElementById('touch-zone-opacity')?.value) || 22;
      const opacity = Math.min(Math.max(opacityPercent / 100, 0.1), 0.8);
      saveMapping(mapping);
      saveScale(scale);
      saveTouchZonePreview(previewEnabled);
      saveTouchZoneOpacity(opacity);
      updateDrumScale(scale);
      updateKeyOverlayLabels(mapping);
      setTouchZoneOpacity(opacity);
      setTouchZonePreview(previewEnabled);
      sendMapping(mapping);
      document.getElementById('settings-panel').classList.add('hidden');
    });

    const previewToggle = document.getElementById('toggle-touch-zones');
    if (previewToggle) {
      previewToggle.addEventListener('change', () => {
        setTouchZonePreview(previewToggle.checked);
      });
    }
    const opacityInput = document.getElementById('touch-zone-opacity');
    const opacityValue = document.getElementById('touch-zone-opacity-value');
    if (opacityInput && opacityValue) {
      opacityInput.addEventListener('input', () => {
        const percent = parseFloat(opacityInput.value) || 22;
        opacityValue.textContent = `${Math.round(percent)}%`;
        setTouchZoneOpacity(Math.min(Math.max(percent / 100, 0.1), 0.8));
      });
    }

    ['left_rim', 'left_face', 'right_face', 'right_rim'].forEach((control) => {
      const el = document.getElementById('map-' + control.replace('_', '-'));
      if (!el) return;
      el.addEventListener('input', () => {
        el.value = el.value.toUpperCase().slice(0, 1);
      });
    });

    document.getElementById('reset-defaults').addEventListener('click', () => {
      saveMapping(DEFAULT);
      saveScale(1);
      setMappingFields();
      sendMapping(DEFAULT);
    });

    const drumScaleInput = document.getElementById('drum-scale');
    const drumScaleDisplay = document.getElementById('drum-scale-value');
    if (drumScaleInput && drumScaleDisplay) {
      drumScaleInput.addEventListener('input', () => {
        const scale = parseFloat(drumScaleInput.value) || 1;
        drumScaleDisplay.textContent = `${Math.round(scale * 100)}%`;
        updateDrumScale(scale);
        updateFaceZones();
      });
    }

    window.addEventListener('resize', updateFaceZones);
    window.addEventListener('load', updateFaceZones);
    window.addEventListener('load', () => {
      setMobileView(loadMobileView());
    });
    window.addEventListener('contextmenu', (ev) => ev.preventDefault());
    window.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') {
        ev.preventDefault();
        sendTap('pause');
      }
    });

    function handleControlInput(ev) {
      const button = ev.currentTarget;
      const control = button.dataset.control;
      if (!control) return;
      ev.preventDefault();
      sendTap(control);
      triggerDrumBounce();
      triggerKeyOverlayResponse(control === 'left_rim_shift' ? 'left_rim' : control === 'right_rim_shift' ? 'right_rim' : control);
    }

    document.querySelectorAll('[data-control]').forEach((button) => {
      button.addEventListener('pointerdown', handleControlInput, { passive: false });
    });
    updateFaceZones();
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setConnectionType();
  }

  window.addEventListener('load', () => {
    wireUI();
    setConnectionType();
    connect();
  });
})();
