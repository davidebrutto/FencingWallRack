(() => {
  const modal = document.getElementById('athleteCamera');
  if (!modal || !navigator.mediaDevices?.getUserMedia) return;

  const video = document.getElementById('cameraVideo');
  const canvas = document.getElementById('cameraCanvas');
  const guide = modal.querySelector('.camera-guide');
  const title = document.getElementById('cameraTitle');
  const status = document.getElementById('cameraStatus');
  const error = document.getElementById('cameraError');
  const captureButton = document.getElementById('cameraCapture');
  const retakeButton = document.getElementById('cameraRetake');
  const useButton = document.getElementById('cameraUse');
  let stream = null;
  let activeForm = null;
  let opener = null;
  let requestId = 0;

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
    }
    video.pause();
    video.srcObject = null;
  }

  function showError(message) {
    error.textContent = message;
    error.hidden = false;
    status.textContent = '';
  }

  function closeCamera() {
    requestId += 1;
    stopCamera();
    modal.hidden = true;
    document.body.classList.remove('camera-open');
    activeForm = null;
    if (opener) opener.focus();
    opener = null;
  }

  async function startCamera() {
    const currentRequest = ++requestId;
    stopCamera();
    error.hidden = true;
    status.textContent = 'Apertura fotocamera...';
    video.hidden = false;
    canvas.hidden = true;
    guide.hidden = false;
    captureButton.hidden = false;
    captureButton.disabled = true;
    retakeButton.hidden = true;
    useButton.hidden = true;

    try {
      const opened = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 1600 } },
      });
      if (modal.hidden || currentRequest !== requestId) {
        opened.getTracks().forEach((track) => track.stop());
        return;
      }
      stream = opened;
      video.srcObject = stream;
      await video.play();
      if (modal.hidden || currentRequest !== requestId) return;
      captureButton.disabled = false;
      status.textContent = 'Posiziona il viso nell\'ovale, poi scatta.';
    } catch (exc) {
      if (currentRequest !== requestId) return;
      stopCamera();
      captureButton.disabled = true;
      const denied = exc.name === 'NotAllowedError' || exc.name === 'SecurityError';
      showError(denied
        ? 'Consenti l\'accesso alla fotocamera nelle impostazioni del browser, oppure scegli un file.'
        : 'Fotocamera non disponibile. Puoi comunque scegliere una foto dal telefono.');
    }
  }

  document.querySelectorAll('.camera-trigger').forEach((button) => {
    button.hidden = false;
    button.addEventListener('click', () => {
      activeForm = button.closest('form');
      opener = button;
      title.textContent = `Foto: ${button.dataset.athlete || 'atleta'}`;
      modal.hidden = false;
      document.body.classList.add('camera-open');
      modal.querySelector('[data-camera-close]').focus();
      startCamera();
    });
  });

  captureButton.addEventListener('click', () => {
    if (!stream || !video.videoWidth || !video.videoHeight) {
      showError('L\'anteprima non e ancora pronta. Riprova tra un momento.');
      return;
    }

    // Ritaglia la stessa area 4:5 mostrata nell'anteprima sotto la guida.
    const sourceRatio = video.videoWidth / video.videoHeight;
    const frameRatio = 4 / 5;
    const cropWidth = sourceRatio > frameRatio ? video.videoHeight * frameRatio : video.videoWidth;
    const cropHeight = sourceRatio > frameRatio ? video.videoHeight : video.videoWidth / frameRatio;
    canvas.width = 960;
    canvas.height = 1200;
    const context = canvas.getContext('2d');
    if (!context) {
      showError('Impossibile preparare la foto. Riprova o scegli un file.');
      return;
    }
    context.drawImage(video,
      (video.videoWidth - cropWidth) / 2, (video.videoHeight - cropHeight) / 2,
      cropWidth, cropHeight, 0, 0, canvas.width, canvas.height);
    stopCamera();
    video.hidden = true;
    guide.hidden = true;
    canvas.hidden = false;
    captureButton.hidden = true;
    retakeButton.hidden = false;
    useButton.hidden = false;
    status.textContent = 'Controlla la foto prima di sostituire quella dell\'atleta.';
    error.hidden = true;
  });

  retakeButton.addEventListener('click', startCamera);

  useButton.addEventListener('click', () => {
    if (!activeForm) return;
    useButton.disabled = true;
    status.textContent = 'Caricamento foto...';
    canvas.toBlob((blob) => {
      if (modal.hidden) return;
      try {
        if (!blob) throw new Error('Foto non disponibile');
        const input = activeForm.querySelector('input[name="replacement_photo"]');
        if (!input) throw new Error('Campo foto non disponibile. Ricarica la pagina.');
        const files = new DataTransfer();
        files.items.add(new File([blob], 'foto-atleta.jpg', { type: 'image/jpeg' }));
        input.files = files.files;
        if (input.files.length !== 1) throw new Error('Impossibile preparare la foto. Riprova o scegli un file.');

        // Invia il modulo esistente: il server gestisce risposta, errori e riduzione come per un file scelto.
        if (activeForm.requestSubmit) activeForm.requestSubmit();
        else activeForm.submit();
      } catch (exc) {
        useButton.disabled = false;
        showError(exc.message || 'Impossibile inviare la foto. Riprova o scegli un file.');
      }
    }, 'image/jpeg', 0.9);
  });

  modal.querySelector('[data-camera-close]').addEventListener('click', closeCamera);
  modal.addEventListener('click', (event) => {
    if (event.target === modal) closeCamera();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.hidden) closeCamera();
  });
  window.addEventListener('pagehide', stopCamera);
})();
