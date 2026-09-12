/**
 * VisionVoice — Web Command Center & Real-Time Telemetry Frontend Logic.
 * Full Website Application with WebRTC Webcam, Voice Orb, Karaoke Subtitles & Multi-Speed Audio.
 */

// Global State
let currentTelemetry = null;
let lastLogId = 0;
let isVisualizerRunning = false;
let webcamStream = null;
let isWebcamActive = true;
let isMicListening = false;
let speechRecognition = null;
let localBooksCache = [];
let playbackSpeed = 1.0;

// DOM Elements
const statusBadge = document.getElementById('status-badge');
const statusText = document.getElementById('status-text');
const globalLangSelect = document.getElementById('global-lang-select');
const globalModeSelect = document.getElementById('global-mode-select');
const uptimeDisplay = document.getElementById('uptime-display');
const cameraFeed = document.getElementById('live-camera-feed');
const webcamVideo = document.getElementById('browser-webcam-video');
const snapshotCanvas = document.getElementById('snapshot-canvas');
const camModeBadge = document.getElementById('cam-mode-badge');
const hudGuidanceText = document.getElementById('hud-guidance-text');
const hudAlignmentStatus = document.getElementById('hud-alignment-status');
const karaokeText = document.getElementById('karaoke-text');
const karaokeIndex = document.getElementById('karaoke-index');
const readingBookPill = document.getElementById('reading-book-pill');
const sentenceFlowList = document.getElementById('sentence-flow-list');
const sentenceCountBadge = document.getElementById('sentence-count-badge');
const volumeSlider = document.getElementById('volume-slider');
const volumeLabel = document.getElementById('volume-label');
const btnPlayPause = document.getElementById('btn-ctrl-playpause');
const audioWaveformCanvas = document.getElementById('audio-waveform');
const logsConsole = document.getElementById('system-logs-console');
const cameraDropzone = document.getElementById('camera-dropzone');
const voiceOrb = document.getElementById('voice-assistant-orb');
const voiceStatusBanner = document.getElementById('voice-status-banner');

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initTabNavigation();
  initHeroActions();
  initWebcam();
  initPhotoUpload();
  initPlaybackControls();
  initSpeedControls();
  initStudio();
  initVoiceSimulator();
  initDiagnostics();
  initKeyboardShortcuts();
  initWaveformVisualizer();

  // Load local books cache
  try {
    const saved = localStorage.getItem('visionvoice_books');
    if (saved) localBooksCache = JSON.parse(saved);
  } catch (e) {}

  // Periodic telemetry polling
  pollTelemetry();
  setInterval(pollTelemetry, 850);

  pollLogs();
  setInterval(pollLogs, 1500);

  // Initial loads for library and gallery
  loadBooks();
  loadGallery();
});

// Toast Helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  if (type === 'error') toast.style.borderColor = 'var(--accent-rose)';
  if (type === 'success') toast.style.borderColor = 'var(--accent-emerald)';
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// 1. Tab Navigation & Hero Quick Actions
function switchTab(targetId) {
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabButtons.forEach(b => {
    if (b.getAttribute('data-tab') === targetId) {
      b.classList.add('active');
    } else {
      b.classList.remove('active');
    }
  });

  tabContents.forEach(c => {
    if (c.id === targetId) {
      c.classList.add('active');
    } else {
      c.classList.remove('active');
    }
  });

  if (targetId === 'tab-library') loadBooks();
  if (targetId === 'tab-gallery') loadGallery();
}

function initTabNavigation() {
  const tabButtons = document.querySelectorAll('.tab-btn');
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');
      switchTab(targetId);
    });
  });

  const brandBtn = document.getElementById('nav-brand-btn');
  if (brandBtn) {
    brandBtn.addEventListener('click', () => {
      switchTab('tab-station');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }
}

function initHeroActions() {
  const heroBtnScan = document.getElementById('hero-btn-scan');
  const heroBtnUpload = document.getElementById('hero-btn-upload');
  const heroBtnVoice = document.getElementById('hero-btn-voice');
  const heroBtnStudio = document.getElementById('hero-btn-studio');
  const fileInput = document.getElementById('book-image-upload');

  if (heroBtnScan) {
    heroBtnScan.addEventListener('click', () => {
      switchTab('tab-station');
      triggerScanAndRead();
    });
  }

  if (heroBtnUpload && fileInput) {
    heroBtnUpload.addEventListener('click', () => {
      switchTab('tab-station');
      fileInput.click();
    });
  }

  if (heroBtnVoice) {
    heroBtnVoice.addEventListener('click', () => {
      switchTab('tab-voice');
      const btnMic = document.getElementById('btn-toggle-mic');
      if (btnMic && !isMicListening) btnMic.click();
    });
  }

  if (heroBtnStudio) {
    heroBtnStudio.addEventListener('click', () => {
      switchTab('tab-studio');
    });
  }
}

// 2. Browser Webcam Integration
async function initWebcam() {
  const btnToggleWebcam = document.getElementById('btn-toggle-webcam');

  async function startWebcam() {
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false
        });
        webcamStream = stream;
        webcamVideo.srcObject = stream;
        webcamVideo.style.display = 'block';
        if (cameraFeed) cameraFeed.style.display = 'none';
        isWebcamActive = true;
        if (camModeBadge) camModeBadge.textContent = 'DEVICE WEBCAM';
        if (hudAlignmentStatus) hudAlignmentStatus.textContent = 'Live Webcam Active';
        showToast('Device webcam connected successfully', 'success');
      }
    } catch (err) {
      console.warn('Webcam permission denied or unavailable, using cloud sample feed:', err);
      fallbackToSampleFeed();
    }
  }

  function fallbackToSampleFeed() {
    isWebcamActive = false;
    if (webcamStream) {
      webcamStream.getTracks().forEach(t => t.stop());
      webcamStream = null;
    }
    webcamVideo.style.display = 'none';
    if (cameraFeed) {
      cameraFeed.style.display = 'block';
      cameraFeed.src = `/api/camera/snapshot?t=${Date.now()}`;
    }
    if (camModeBadge) camModeBadge.textContent = 'CLOUD FEED';
    if (hudAlignmentStatus) hudAlignmentStatus.textContent = 'Sample Feed Active';
  }

  if (btnToggleWebcam) {
    btnToggleWebcam.addEventListener('click', () => {
      if (isWebcamActive) {
        fallbackToSampleFeed();
        showToast('Switched to Cloud Sample Feed', 'info');
      } else {
        startWebcam();
      }
    });
  }

  // Attempt to start webcam automatically on first load
  startWebcam();
}

// 3. Photo Upload & Drag-and-Drop
function initPhotoUpload() {
  const fileInput = document.getElementById('book-image-upload');
  const btnUpload = document.getElementById('btn-upload-photo');
  const dropzone = cameraDropzone;

  if (btnUpload && fileInput) {
    btnUpload.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (file) {
        await processUploadedFile(file);
      }
    });
  }

  if (dropzone) {
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('drag-over');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('drag-over');
    });

    dropzone.addEventListener('drop', async (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        await processUploadedFile(e.dataTransfer.files[0]);
      }
    });
  }
}

async function processUploadedFile(file) {
  const btnScan = document.getElementById('btn-scan-read');
  btnScan.disabled = true;
  btnScan.innerHTML = '<span>⏳</span> Processing Uploaded Image...';
  if (cameraDropzone) cameraDropzone.classList.add('scanning');
  showToast(`Uploading ${file.name} for OCR scanning...`, 'info');

  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target_lang', globalLangSelect.value);

    const res = await fetch('/api/ocr/image', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast(`Scan complete: ${data.sentence_count} sentences extracted (${data.detected_language.name})`, 'success');
      handleScanResult(data);
    } else {
      showToast(data.detail || 'Failed to scan uploaded image', 'error');
    }
  } catch (err) {
    showToast('Upload OCR failed: ' + err.message, 'error');
  } finally {
    btnScan.disabled = false;
    btnScan.innerHTML = '<span>🔘</span> SCAN & READ BOOK [SPACE]';
    if (cameraDropzone) cameraDropzone.classList.remove('scanning');
  }
}

// 4. In-Browser Audio Player & Multi-Speed Control
let browserAudio = null;
let lastSpokenSentence = "";
let availableBrowserVoices = [];

if (typeof window !== 'undefined' && window.speechSynthesis) {
  window.speechSynthesis.onvoiceschanged = () => {
    availableBrowserVoices = window.speechSynthesis.getVoices();
  };
}

function initSpeedControls() {
  const speedChips = document.querySelectorAll('.speed-chip');
  speedChips.forEach(chip => {
    chip.addEventListener('click', () => {
      speedChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      playbackSpeed = parseFloat(chip.getAttribute('data-speed') || '1.0');
      showToast(`Playback speed: ${playbackSpeed}x`, 'info');
    });
  });
}

function playSpeechInBrowser(text, lang = 'en', force = false) {
  if (!text || !text.trim()) return;
  if (!force && text === lastSpokenSentence) return;
  lastSpokenSentence = text;

  stopBrowserSpeech();

  const vol = Math.max(0.1, Math.min(1.0, parseInt(volumeSlider.value || 80, 10) / 100));
  const audioUrl = `/api/tts/synthesize?text=${encodeURIComponent(text)}&lang=${encodeURIComponent(lang)}&t=${Date.now()}`;

  browserAudio = new Audio();
  browserAudio.src = audioUrl;
  browserAudio.volume = vol;
  browserAudio.playbackRate = playbackSpeed;

  const playPromise = browserAudio.play();
  if (playPromise !== undefined) {
    playPromise.catch(() => {
      speakViaWebSpeechAPI(text, lang, vol);
    });
  }
}

function speakViaWebSpeechAPI(text, lang = 'en', volume = 0.8) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();

  const utter = new SpeechSynthesisUtterance(text);
  const langMap = {
    'en': 'en-US',
    'ta': 'ta-IN',
    'hi': 'hi-IN',
    'kn': 'kn-IN',
    'te': 'te-IN',
    'ml': 'ml-IN'
  };
  utter.lang = langMap[lang] || 'en-US';
  utter.volume = volume;
  utter.rate = playbackSpeed;
  utter.pitch = 1.0;

  if (availableBrowserVoices.length === 0) {
    availableBrowserVoices = window.speechSynthesis.getVoices();
  }

  const matchingVoice = availableBrowserVoices.find(v => v.lang.toLowerCase().startsWith(lang.toLowerCase())) ||
                        availableBrowserVoices.find(v => v.lang.includes('en'));
  if (matchingVoice) {
    utter.voice = matchingVoice;
  }

  window.speechSynthesis.speak(utter);
}

function stopBrowserSpeech() {
  if (browserAudio) {
    try {
      browserAudio.pause();
      browserAudio.currentTime = 0;
      browserAudio = null;
    } catch (e) {}
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

// 5. Real-Time Telemetry Polling
async function pollTelemetry() {
  try {
    const res = await fetch('/api/state');
    if (!res.ok) return;
    const data = await res.json();
    currentTelemetry = data;

    // Status Badge
    statusText.textContent = data.status;
    statusBadge.className = 'status-pill';
    if (data.status === 'READY') {
      statusBadge.classList.remove('status-busy', 'status-error');
    } else if (data.status === 'READING' || data.status === 'PROCESSING' || data.status === 'CAPTURING') {
      statusBadge.classList.add('status-busy');
    } else if (data.status === 'ERROR') {
      statusBadge.classList.add('status-error');
    }

    // Camera Overlay
    const cameraOffOverlay = document.getElementById('camera-off-overlay');
    const btnToggleCam = document.getElementById('btn-toggle-camera');
    if (data.camera_enabled === false) {
      if (cameraOffOverlay) cameraOffOverlay.style.display = 'flex';
      if (btnToggleCam) btnToggleCam.innerHTML = '<span>📷</span> Turn On';
    } else {
      if (cameraOffOverlay) cameraOffOverlay.style.display = 'none';
      if (btnToggleCam) btnToggleCam.innerHTML = '<span>📷</span> Turn Off';
    }

    // Uptime
    uptimeDisplay.textContent = data.uptime;

    // Selectors
    if (document.activeElement !== globalLangSelect) {
      globalLangSelect.value = data.preferred_language;
    }
    if (document.activeElement !== globalModeSelect) {
      globalModeSelect.value = data.reading_mode;
    }

    // Guidance HUD
    if (data.last_guidance) {
      hudGuidanceText.textContent = data.last_guidance;
    }

    // Book & Active Sentence
    readingBookPill.textContent = `Book: ${data.current_book_id || 'None'} (p.${data.current_page})`;

    if (data.active_speaking_sentence) {
      karaokeText.textContent = data.active_speaking_sentence;
      karaokeText.classList.remove('empty-state');
      playSpeechInBrowser(data.active_speaking_sentence, data.preferred_language);
    } else if (!data.is_reading && data.total_sentences === 0) {
      karaokeText.textContent = 'Place a book in the camera view or upload an image and click "Scan & Read Book" to begin reading.';
      karaokeText.classList.add('empty-state');
    }

    karaokeIndex.textContent = `Sentence: ${data.current_sentence_idx} / ${data.total_sentences}`;
    sentenceCountBadge.textContent = `${data.total_sentences} sentences`;

    // Highlight active sentence item
    updateActiveSentenceHighlight(data.current_sentence_idx);

    // Play/Pause icon
    if (data.is_reading && data.status !== 'PAUSED') {
      btnPlayPause.textContent = '⏸';
      btnPlayPause.title = 'Pause Reading';
    } else {
      btnPlayPause.textContent = '▶';
      btnPlayPause.title = 'Resume Reading';
    }

    // Volume
    if (document.activeElement !== volumeSlider) {
      volumeSlider.value = data.volume;
      volumeLabel.textContent = `${data.volume}%`;
    }

  } catch (err) {
    console.warn('Telemetry poll note:', err);
  }
}

function updateActiveSentenceHighlight(activeIdx) {
  const items = document.querySelectorAll('.sentence-item');
  items.forEach((item, idx) => {
    if (idx + 1 === activeIdx) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });
}

// 6. Playback Controls & Listeners
function initPlaybackControls() {
  globalLangSelect.addEventListener('change', async () => {
    const lang = globalLangSelect.value;
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preferred_language: lang })
    });
    showToast(`Preferred language set to ${lang.toUpperCase()}`, 'success');
  });

  globalModeSelect.addEventListener('change', async () => {
    const mode = globalModeSelect.value;
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reading_mode: mode })
    });
    showToast(`Reading mode set to ${mode.toUpperCase()}`, 'success');
  });

  volumeSlider.addEventListener('input', () => {
    volumeLabel.textContent = `${volumeSlider.value}%`;
  });
  volumeSlider.addEventListener('change', async () => {
    const vol = parseInt(volumeSlider.value, 10);
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ volume: vol })
    });
  });

  const btnToggleCam = document.getElementById('btn-toggle-camera');
  const btnTurnOnCam = document.getElementById('btn-turn-on-camera');

  async function toggleCameraState() {
    try {
      const res = await fetch('/api/camera/toggle', { method: 'POST' });
      const data = await res.json();
      const isEnabled = data.camera_enabled;
      showToast(isEnabled ? 'Camera turned ON' : 'Camera turned OFF', 'info');
      pollTelemetry();
    } catch (err) {
      showToast('Camera toggle failed: ' + err.message, 'error');
    }
  }

  if (btnToggleCam) btnToggleCam.addEventListener('click', toggleCameraState);
  if (btnTurnOnCam) btnTurnOnCam.addEventListener('click', toggleCameraState);

  const btnScan = document.getElementById('btn-scan-read');
  btnScan.addEventListener('click', triggerScanAndRead);

  btnPlayPause.addEventListener('click', async () => {
    if (currentTelemetry && currentTelemetry.is_reading && currentTelemetry.status !== 'PAUSED') {
      stopBrowserSpeech();
      await fetch('/api/playback/pause', { method: 'POST' });
    } else {
      if (currentTelemetry && currentTelemetry.active_speaking_sentence) {
        playSpeechInBrowser(currentTelemetry.active_speaking_sentence, currentTelemetry.preferred_language);
      }
      await fetch('/api/playback/resume', { method: 'POST' });
    }
  });

  document.getElementById('btn-ctrl-prev').addEventListener('click', async () => {
    stopBrowserSpeech();
    await fetch('/api/playback/prev', { method: 'POST' });
  });

  document.getElementById('btn-ctrl-next').addEventListener('click', async () => {
    stopBrowserSpeech();
    await fetch('/api/playback/next', { method: 'POST' });
  });

  document.getElementById('btn-ctrl-repeat').addEventListener('click', async () => {
    if (currentTelemetry && currentTelemetry.active_speaking_sentence) {
      lastSpokenSentence = "";
      playSpeechInBrowser(currentTelemetry.active_speaking_sentence, currentTelemetry.preferred_language, true);
    }
    await fetch('/api/playback/repeat', { method: 'POST' });
  });

  document.getElementById('btn-ctrl-stop').addEventListener('click', async () => {
    stopBrowserSpeech();
    await fetch('/api/playback/stop', { method: 'POST' });
  });

  document.getElementById('btn-refresh-stream').addEventListener('click', () => {
    if (cameraFeed) cameraFeed.src = `/api/camera/snapshot?t=${Date.now()}`;
    showToast('Feed refreshed');
  });
}

// 7. Trigger Scan Flow (From Webcam or Cloud Sample)
async function triggerScanAndRead() {
  const btnScan = document.getElementById('btn-scan-read');
  btnScan.disabled = true;
  btnScan.innerHTML = '<span>⏳</span> Processing Scan & OCR...';
  if (cameraDropzone) cameraDropzone.classList.add('scanning');
  showToast('Scanning page & extracting text...', 'info');

  try {
    let base64Frame = null;

    if (isWebcamActive && webcamVideo && webcamVideo.videoWidth) {
      snapshotCanvas.width = webcamVideo.videoWidth;
      snapshotCanvas.height = webcamVideo.videoHeight;
      const ctx = snapshotCanvas.getContext('2d');
      ctx.drawImage(webcamVideo, 0, 0);
      base64Frame = snapshotCanvas.toDataURL('image/jpeg', 0.85);
    }

    const formData = new FormData();
    if (base64Frame) {
      formData.append('image_base64', base64Frame);
    }
    formData.append('sample_key', globalLangSelect.value);
    formData.append('target_lang', globalLangSelect.value);

    const res = await fetch('/api/camera/scan', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast(`Extracted ${data.sentence_count} sentences (${data.detected_language.name})`, 'success');
      handleScanResult(data);
    } else {
      showToast(data.detail || 'Scan failed', 'error');
    }
  } catch (err) {
    showToast('Failed to trigger scan: ' + err.message, 'error');
  } finally {
    btnScan.disabled = false;
    btnScan.innerHTML = '<span>🔘</span> SCAN & READ BOOK [SPACE]';
    if (cameraDropzone) cameraDropzone.classList.remove('scanning');
  }
}

function handleScanResult(data) {
  renderSentenceList(data.sentences);

  const bookRecord = {
    book_id: data.book_id,
    detected_lang: data.detected_language.lang,
    last_page: data.page,
    last_sentence_idx: 1,
    sample_words: (data.original_text || '').split(' ').slice(0, 8),
    created_str: new Date().toLocaleString()
  };

  const existingIdx = localBooksCache.findIndex(b => b.book_id === data.book_id);
  if (existingIdx >= 0) {
    localBooksCache[existingIdx] = bookRecord;
  } else {
    localBooksCache.unshift(bookRecord);
  }

  try {
    localStorage.setItem('visionvoice_books', JSON.stringify(localBooksCache));
  } catch (e) {}

  if (data.sentences && data.sentences.length > 0) {
    playSpeechInBrowser(data.sentences[0], data.reading_language, true);
  }
}

function renderSentenceList(sentences) {
  sentenceFlowList.innerHTML = '';
  if (!sentences || sentences.length === 0) {
    sentenceFlowList.innerHTML = '<div style="color: var(--text-dim); font-size: 0.82rem; padding: 0.5rem;">No active sentences.</div>';
    return;
  }

  sentences.forEach((s, idx) => {
    const item = document.createElement('div');
    item.className = 'sentence-item' + (idx === 0 ? ' active' : '');
    item.innerHTML = `
      <span class="sentence-num">[${idx + 1}]</span>
      <span style="flex: 1;">${s}</span>
      <span style="font-size: 0.75rem; color: var(--accent-cyan); opacity: 0.8;">🔊</span>
    `;
    item.addEventListener('click', () => {
      document.querySelectorAll('.sentence-item').forEach(el => el.classList.remove('active'));
      item.classList.add('active');
      playSpeechInBrowser(s, globalLangSelect.value, true);
    });
    sentenceFlowList.appendChild(item);
  });
}

// 8. Multilingual Studio
function initStudio() {
  const sampleBtns = document.querySelectorAll('.sample-btn');
  const inputText = document.getElementById('studio-input-text');
  const targetSelect = document.getElementById('studio-target-lang');
  const translatedText = document.getElementById('studio-translated-text');
  const detectedBadge = document.getElementById('studio-detected-badge');
  const btnRun = document.getElementById('btn-studio-run');
  const btnSpeak = document.getElementById('btn-studio-speak');

  const sampleTexts = {
    en: "VisionVoice is an intelligent assistive reading device designed for physical books. It combines computer vision, real-time alignment analysis, and multilingual OCR into a standalone assistant.",
    ta: "விஷன்வாய்ஸ் என்பது அச்சிடப்பட்ட புத்தகங்களை கைகள் இல்லாமல் வாசிக்க உதவும் ஒரு அறிவார்ந்த வாசிப்பு சாதனமாகும். இது கணினி பார்வை மற்றும் பலமொழி எழுத்துணர்தல் தொழில்நுட்பங்களை ஒருங்கிணைக்கிறது.",
    hi: "विज़नवॉइस एक बुद्धिमान सहायक पठन उपकरण है जो भौतिक पुस्तकों को बिना हाथ लगाए पढ़ने की सुविधा प्रदान करता है। यह कंप्यूटर विज़न और बहुभाषी ओसीआर को जोड़ता है।",
    kn: "ವಿಷನ್-ವಾಯ್ಸ್ ಒಂದು ಬುದ್ಧಿವಂತ ಸಹಾಯಕ ಓದುವ ಸಾಧನವಾಗಿದ್ದು, ಭೌತಿಕ ಪುಸ್ತಕಗಳನ್ನು ಓದಲು ಸಹಾಯ ಮಾಡುತ್ತದೆ.",
    te: "విజన్ వాయిస్ అనేది భౌతిక పుస్తకాల కోసం రూపొందించబడిన ఒక స్మార్ట్ పఠన సహాయక పరికరం.",
    ml: "വിഷൻ വോയ്സ് എന്നത് പുസ്തകങ്ങൾ എളുപ്പത്തിൽ വായിക്കാൻ സഹായിക്കുന്ന ഒരു സ്മാർട്ട് വായനാ സഹായിയാണ്."
  };

  sampleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const code = btn.getAttribute('data-sample');
      inputText.value = sampleTexts[code] || '';
      runStudioTranslation();
    });
  });

  async function runStudioTranslation() {
    const text = inputText.value.trim();
    if (!text) return;
    const target = targetSelect.value;

    btnRun.disabled = true;
    btnRun.innerHTML = '<span>⏳</span> Processing...';

    try {
      const formData = new URLSearchParams();
      formData.append('custom_text', text);
      formData.append('target_lang', target);

      const res = await fetch('/api/ocr/custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        detectedBadge.textContent = `${data.detected_script.name} (${data.detected_script.lang}) [${Math.round(data.detected_script.confidence * 100)}%]`;
        translatedText.value = data.translated_text;
      }
    } catch (err) {
      showToast('Studio translation error: ' + err.message, 'error');
    } finally {
      btnRun.disabled = false;
      btnRun.innerHTML = '<span>⚡</span> Run Script Detection & Translate';
    }
  }

  btnRun.addEventListener('click', runStudioTranslation);

  btnSpeak.addEventListener('click', async () => {
    const text = translatedText.value.trim();
    if (!text) return;
    const target = targetSelect.value;
    playSpeechInBrowser(text, target, true);
    showToast(`Playing speech in ${target.toUpperCase()}`, 'success');
  });
}

// 9. Book Memory Library
async function loadBooks() {
  const container = document.getElementById('books-cards-container');
  try {
    const res = await fetch('/api/books');
    const data = await res.json();
    container.innerHTML = '';

    const allBooks = (data.books || []).concat(localBooksCache);
    const uniqueBooks = [];
    const seenIds = new Set();
    for (const b of allBooks) {
      if (!seenIds.has(b.book_id)) {
        seenIds.add(b.book_id);
        uniqueBooks.push(b);
      }
    }

    if (uniqueBooks.length === 0) {
      container.innerHTML = '<div style="color: var(--text-dim); padding: 1rem;">No saved books found. Scan a book to create persistent bookmarks!</div>';
      return;
    }

    uniqueBooks.forEach(b => {
      const card = document.createElement('div');
      card.className = 'book-card' + (b.book_id === (currentTelemetry ? currentTelemetry.current_book_id : '') ? ' active-book' : '');

      const words = (b.sample_words || []).slice(0, 6).map(w => `<span class="keyword-pill">${w}</span>`).join('');

      card.innerHTML = `
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
            <div style="font-weight: 700; font-size: 1.05rem; color: #fff;">${b.book_id}</div>
            <span class="book-tag">${(b.detected_lang || 'en').toUpperCase()}</span>
          </div>
          <div class="book-meta-row" style="margin-bottom: 0.25rem;">
            <span>Last Read Page:</span>
            <span style="color: var(--accent-cyan); font-weight: 600;">Page ${b.last_page || 1}</span>
          </div>
          <div class="book-meta-row" style="margin-bottom: 0.5rem;">
            <span>Sentence Bookmark:</span>
            <span style="color: var(--text-main);">#${b.last_sentence_idx || 0}</span>
          </div>
          <div class="book-keywords-cloud">${words}</div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-subtle); padding-top: 0.75rem;">
          <button class="btn btn-secondary btn-resume-book" data-id="${b.book_id}" style="padding: 0.25rem 0.65rem; font-size: 0.75rem; color: var(--accent-cyan);">Resume 📖</button>
          <button class="btn btn-secondary btn-delete-book" data-id="${b.book_id}" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; color: var(--accent-rose);">Delete</button>
        </div>
      `;

      container.appendChild(card);
    });

    // Delete buttons
    document.querySelectorAll('.btn-delete-book').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        localBooksCache = localBooksCache.filter(b => b.book_id !== id);
        try {
          localStorage.setItem('visionvoice_books', JSON.stringify(localBooksCache));
        } catch (e) {}
        await fetch(`/api/books/${id}`, { method: 'DELETE' });
        showToast(`Book ${id} deleted`, 'info');
        loadBooks();
      });
    });

    // Resume buttons
    document.querySelectorAll('.btn-resume-book').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        switchTab('tab-station');
        showToast(`Resumed book: ${id}`, 'success');
      });
    });

  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-rose);">Failed to load books: ${err.message}</div>`;
  }
}

// 10. Page Capture Gallery
async function loadGallery() {
  const container = document.getElementById('gallery-container');
  try {
    const res = await fetch('/api/captures?limit=24');
    const data = await res.json();
    container.innerHTML = '';

    if (!data.captures || data.captures.length === 0) {
      container.innerHTML = '<div style="color: var(--text-dim); padding: 1rem;">No captured pages yet. Press Scan on the live station to capture!</div>';
      return;
    }

    data.captures.forEach(cap => {
      const item = document.createElement('div');
      item.className = 'gallery-item';
      item.innerHTML = `
        <img class="gallery-img" src="${cap.url}" alt="${cap.filename}" loading="lazy">
        <div class="gallery-overlay">
          <span>${cap.filename.slice(0, 16)}...</span>
          <span>${cap.size_kb} KB</span>
        </div>
      `;
      item.addEventListener('click', () => window.open(cap.url, '_blank'));
      container.appendChild(item);
    });

  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-rose);">Failed to load gallery: ${err.message}</div>`;
  }
}

// 11. Voice Assistant Orb & Real Browser Mic Input
function initVoiceSimulator() {
  const simInput = document.getElementById('voice-sim-input');
  const btnSim = document.getElementById('btn-sim-voice');
  const btnMic = document.getElementById('btn-toggle-mic');
  const micIcon = document.getElementById('mic-icon');
  const micStatusText = document.getElementById('mic-status-text');
  const chips = document.querySelectorAll('.voice-chip');

  async function sendVoiceSim(utterance) {
    if (!utterance) return;
    try {
      const res = await fetch('/api/voice/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ utterance })
      });
      const data = await res.json();
      showToast(`Parsed: [${data.parsed_command}] -> ${data.action_result}`, 'success');

      if (data.parsed_command === 'wake_word') {
        playSpeechInBrowser("VisionVoice is ready. What would you like to read?", globalLangSelect.value, true);
      } else if (data.parsed_command === 'start_reading') {
        playSpeechInBrowser("Starting page capture and reading.", globalLangSelect.value, true);
        triggerScanAndRead();
      } else if (data.parsed_command === 'stop_reading') {
        stopBrowserSpeech();
      }

      pollLogs();
    } catch (err) {
      showToast('Voice simulation failed: ' + err.message, 'error');
    }
  }

  // Real Browser Microphone Listening
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRec && btnMic) {
    speechRecognition = new SpeechRec();
    speechRecognition.continuous = true;
    speechRecognition.interimResults = false;
    speechRecognition.lang = 'en-US';

    speechRecognition.onresult = (e) => {
      const transcript = e.results[e.results.length - 1][0].transcript.trim();
      showToast(`Heard: "${transcript}"`, 'info');
      sendVoiceSim(transcript);
    };

    speechRecognition.onerror = (e) => {
      console.warn('Speech recognition event:', e.error);
    };

    speechRecognition.onend = () => {
      if (isMicListening) {
        try { speechRecognition.start(); } catch (e) {}
      }
    };

    function toggleMic() {
      if (!isMicListening) {
        try {
          speechRecognition.start();
          isMicListening = true;
          if (micIcon) micIcon.textContent = '🔴';
          if (micStatusText) micStatusText.textContent = 'Listening (Mic Active)';
          if (voiceOrb) voiceOrb.classList.add('listening');
          if (voiceStatusBanner) voiceStatusBanner.textContent = 'Listening... Say "Hey VisionVoice" or "Start reading"';
          showToast('Microphone activated. Say "Hey VisionVoice" or "Start reading"', 'success');
        } catch (e) {
          showToast('Mic start error: ' + e.message, 'error');
        }
      } else {
        isMicListening = false;
        speechRecognition.stop();
        if (micIcon) micIcon.textContent = '🎙️';
        if (micStatusText) micStatusText.textContent = 'Start Mic Listening';
        if (voiceOrb) voiceOrb.classList.remove('listening');
        if (voiceStatusBanner) voiceStatusBanner.textContent = 'Voice Assistant Ready • Click orb or speak';
        showToast('Microphone deactivated', 'info');
      }
    }

    btnMic.addEventListener('click', toggleMic);
    if (voiceOrb) voiceOrb.addEventListener('click', toggleMic);
  } else if (btnMic) {
    btnMic.addEventListener('click', () => {
      showToast('SpeechRecognition not supported in this browser. Use simulation below.', 'info');
    });
  }

  btnSim.addEventListener('click', () => {
    sendVoiceSim(simInput.value.trim());
    simInput.value = '';
  });

  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      sendVoiceSim(chip.getAttribute('data-cmd'));
    });
  });

  document.getElementById('btn-clear-logs').addEventListener('click', () => {
    logsConsole.innerHTML = '';
  });
}

// 12. Poll Logs Stream
async function pollLogs() {
  try {
    const res = await fetch('/api/events?limit=40');
    const data = await res.json();
    if (!data.events || data.events.length === 0) return;

    logsConsole.innerHTML = '';
    data.events.forEach(evt => {
      const entry = document.createElement('div');
      entry.className = `log-entry ${evt.level || 'info'}`;
      entry.innerHTML = `
        <span class="log-time">${evt.timestamp}</span>
        <span class="log-cat">[${evt.category}]</span>
        <span class="log-msg">${evt.message}</span>
      `;
      logsConsole.appendChild(entry);
    });
    logsConsole.scrollTop = logsConsole.scrollHeight;
  } catch (err) {
    console.warn('Logs poll note:', err);
  }
}

// 13. Diagnostics Runner
function initDiagnostics() {
  const btnRun = document.getElementById('btn-run-diag');
  const container = document.getElementById('diag-cards-container');

  btnRun.addEventListener('click', async () => {
    btnRun.disabled = true;
    btnRun.innerHTML = '<span>⏳</span> Testing Subsystems...';

    try {
      const res = await fetch('/api/diagnostics/run');
      const data = await res.json();
      container.innerHTML = '';

      Object.entries(data.results).forEach(([name, r]) => {
        const card = document.createElement('div');
        card.className = 'diag-card';
        const isPass = r.pass;
        card.innerHTML = `
          <div class="diag-info">
            <div class="diag-name">${name}</div>
            <div class="diag-detail">${r.detail || (isPass ? 'Operational' : 'Failed')}</div>
          </div>
          <span class="diag-badge ${isPass ? 'pass' : 'fail'}">${isPass ? 'PASS' : 'FAIL'}</span>
        `;
        container.appendChild(card);
      });

      showToast(`Diagnostics Completed: ${data.summary}`, 'info');
    } catch (err) {
      showToast('Diagnostics runner failed: ' + err.message, 'error');
    } finally {
      btnRun.disabled = false;
      btnRun.innerHTML = '<span>⚡</span> Run Full Self-Test Suite';
    }
  });
}

// 14. Keyboard Shortcuts
function initKeyboardShortcuts() {
  window.addEventListener('keydown', (e) => {
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;

    if (e.code === 'Space') {
      e.preventDefault();
      triggerScanAndRead();
    } else if (e.key === 'p' || e.key === 'P') {
      btnPlayPause.click();
    } else if (e.key === 'n' || e.key === 'N') {
      document.getElementById('btn-ctrl-next').click();
    } else if (e.key === 'r' || e.key === 'R') {
      document.getElementById('btn-ctrl-repeat').click();
    }
  });
}

// 15. Waveform Canvas Visualizer
function initWaveformVisualizer() {
  const canvas = audioWaveformCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let phase = 0;

  function draw() {
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    const isReading = currentTelemetry && currentTelemetry.is_reading && currentTelemetry.status !== 'PAUSED';
    const amplitude = isReading ? h * 0.35 : 3;

    ctx.lineWidth = 2;
    ctx.strokeStyle = isReading ? '#00f2fe' : '#334155';
    ctx.beginPath();

    for (let x = 0; x < w; x++) {
      const y = h / 2 + Math.sin(x * 0.04 + phase) * amplitude * Math.sin(x * 0.01);
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    phase += isReading ? 0.15 : 0.02;
    requestAnimationFrame(draw);
  }

  draw();
}
