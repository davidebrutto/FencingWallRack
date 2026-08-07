<?php
declare(strict_types=1);
require __DIR__ . '/inc/bootstrap.php';
require __DIR__ . '/inc/layout.php';
$user = require_login();
ensure_photo_flag_override_column();
$error = null;
$flags = list_flags();

function render_flag_select(string $name, string $selected = ''): void
{
    global $flags;
    echo '<select class="flag-native-select" name="' . e($name) . '">';
    echo '<option value="" data-flag-url="">BANDIERA STANDARD</option>';
    foreach ($flags as $flag) {
        $code = (string) $flag['code'];
        $isSelected = $selected === $code ? ' selected' : '';
        echo '<option value="' . e($code) . '" data-flag-url="' . e((string) $flag['url']) . '"' . $isSelected . '>' . e($code) . '</option>';
    }
    echo '</select>';
}


if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $action = $_POST['action'] ?? '';
    if ($action === 'upload') {
        $file = $_FILES['photo'] ?? null;
        $athlete = trim((string) ($_POST['athlete_name'] ?? ''));
        $flagOverride = normalize_flag_override((string) ($_POST['flag_override'] ?? ''));
        if (!$file || $file['error'] !== UPLOAD_ERR_OK) {
            $error = upload_error_message((int) ($file['error'] ?? UPLOAD_ERR_NO_FILE));
        } elseif ($athlete === '') {
            $error = 'Inserisci il nome atleta.';
        } else {
            $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
            if (!in_array($ext, allowed_photo_ext(), true)) {
                $error = 'Formato foto non supportato.';
            } else {
                $base = safe_base_name($athlete, 'atleta');
                $filename = unique_filename(PHOTO_DIR, $base, '.' . $ext);
                if (move_uploaded_file($file['tmp_name'], PHOTO_DIR . '/' . $filename)) {
                    $stmt = db()->prepare('INSERT INTO photos (filename, athlete_name, normalized_name, flag_override, size_bytes, mime, uploaded_by) VALUES (?, ?, ?, ?, ?, ?, ?)');
                    $stmt->execute([$filename, $athlete, normalize_athlete_name($athlete), $flagOverride !== '' ? $flagOverride : null, (int) $file['size'], (string) $file['type'], (int) $user['id']]);
                    redirect_to('/photos.php');
                }
                $error = 'Impossibile salvare la foto.';
            }
        }
    }
    if ($action === 'rename') {
        $id = (int) ($_POST['id'] ?? 0);
        $athlete = trim((string) ($_POST['athlete_name'] ?? ''));
        $flagOverride = normalize_flag_override((string) ($_POST['flag_override'] ?? ''));
        $stmt = db()->prepare('SELECT * FROM photos WHERE id = ?');
        $stmt->execute([$id]);
        $photo = $stmt->fetch();
        if ($photo && $athlete !== '') {
            $ext = strtolower(pathinfo($photo['filename'], PATHINFO_EXTENSION));
            $base = safe_base_name($athlete, 'atleta');
            $newFilename = unique_filename(PHOTO_DIR, $base, '.' . $ext, $photo['filename']);
            if ($newFilename !== $photo['filename']) {
                rename(PHOTO_DIR . '/' . $photo['filename'], PHOTO_DIR . '/' . $newFilename);
            }
            db()->prepare('UPDATE photos SET filename = ?, athlete_name = ?, normalized_name = ?, flag_override = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?')
                ->execute([$newFilename, $athlete, normalize_athlete_name($athlete), $flagOverride !== '' ? $flagOverride : null, $id]);
        }
        redirect_to('/photos.php');
    }
    if ($action === 'delete') {
        $id = (int) ($_POST['id'] ?? 0);
        $stmt = db()->prepare('SELECT filename FROM photos WHERE id = ?');
        $stmt->execute([$id]);
        $photo = $stmt->fetch();
        if ($photo) {
            @unlink(PHOTO_DIR . '/' . $photo['filename']);
            db()->prepare('DELETE FROM photos WHERE id = ?')->execute([$id]);
        }
        redirect_to('/photos.php');
    }
}

$photos = db()->query('SELECT * FROM photos ORDER BY athlete_name ASC, id DESC')->fetchAll();
render_header('Foto atleti', $user);
echo '<section class="card"><h1>Foto atleti</h1>';
flash($error, 'error');
echo '<form method="post" enctype="multipart/form-data">';
echo '<input type="hidden" name="csrf" value="' . e(csrf_token()) . '"><input type="hidden" name="action" value="upload">';
echo '<label>Nome atleta come da seriale</label><input name="athlete_name" placeholder="BRUTTO D." required>';
echo '<label style="margin-top:12px">Bandiera per questo atleta</label>';
render_flag_select('flag_override');
echo '<small class="muted">BANDIERA STANDARD usa la nazione ricevuta dal protocollo. Una scelta diversa forza quella bandiera solo per questo atleta.</small>';
echo '<label style="margin-top:12px">Foto</label><input type="file" name="photo" accept=".jpg,.jpeg,.png,.webp" required>';
echo '<button class="btn" style="margin-top:12px" type="submit">Upload</button></form></section>';
echo '<section class="card"><div class="section-title-row"><h2>Foto caricate</h2><span class="muted" id="photoSearchCount">' . count($photos) . ' file</span></div>';
echo '<div class="search-box"><label for="photoSearch">Cerca foto</label><input id="photoSearch" type="search" placeholder="Cerca per nome atleta, riferimento, file o bandiera. Es: AR"><span class="muted">La ricerca filtra mentre scrivi e trova anche parti interne del testo.</span></div>';
echo '<div class="media-list" id="photoList">';
foreach ($photos as $photo) {
    $url = public_asset_url('photo', $photo['filename']);
    $flagOverride = (string) ($photo['flag_override'] ?? '');
    $flagLabel = $flagOverride !== '' ? $flagOverride : 'BANDIERA STANDARD';
    $searchText = implode(' ', [(string) $photo['athlete_name'], (string) $photo['normalized_name'], (string) $photo['filename'], $flagLabel]);
    echo '<div class="media-row" data-filter-row data-search="' . e($searchText) . '">';
    echo '<img class="photo-preview" src="' . e($url) . '" alt="' . e($photo['athlete_name']) . '">';
    echo '<div><strong>' . e($photo['athlete_name']) . '</strong><br><span class="muted">Chiave: ' . e($photo['normalized_name']) . '</span><br><span class="muted">Bandiera: <strong>' . e($flagLabel) . '</strong></span><br><code>' . e($photo['filename']) . '</code></div>';
    echo '<div class="actions">';
    echo '<form class="inline-form" method="post"><input type="hidden" name="csrf" value="' . e(csrf_token()) . '"><input type="hidden" name="action" value="rename"><input type="hidden" name="id" value="' . (int) $photo['id'] . '"><input type="text" name="athlete_name" value="' . e($photo['athlete_name']) . '">';
    render_flag_select('flag_override', $flagOverride);
    echo '<button class="btn">Salva</button></form>';
    echo '<form method="post" onsubmit="return confirm(\'Eliminare questa foto?\')"><input type="hidden" name="csrf" value="' . e(csrf_token()) . '"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="' . (int) $photo['id'] . '"><button class="btn btn-danger">Elimina</button></form>';
    echo '</div></div>';
}
if (!$photos) {
    echo '<p>Nessuna foto caricata.</p>';
}
echo '<p class="empty-filter-message" id="photoSearchEmpty" hidden>Nessuna foto trovata con questa ricerca.</p>';
echo '</div></section>';
echo <<<'HTML'
<script>
(() => {
  const input = document.getElementById('photoSearch');
  const rows = Array.from(document.querySelectorAll('#photoList [data-filter-row]'));
  const empty = document.getElementById('photoSearchEmpty');
  const count = document.getElementById('photoSearchCount');
  const normalize = (value) => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

  function applyFilter() {
    const query = normalize(input.value).trim();
    let visible = 0;
    for (const row of rows) {
      const text = normalize(row.dataset.search);
      const match = query === '' || text.includes(query);
      row.hidden = !match;
      if (match) visible += 1;
    }
    if (empty) empty.hidden = visible !== 0 || rows.length === 0;
    if (count) count.textContent = `${visible} di ${rows.length} file`;
  }

  function optionPayload(option) {
    return {
      value: option.value,
      label: option.textContent || 'BANDIERA STANDARD',
      url: option.dataset.flagUrl || '',
    };
  }

  function renderFlagFallback(container, label) {
    const fallback = document.createElement('span');
    fallback.className = 'flag-standard-icon';
    fallback.textContent = label || 'STD';
    container.appendChild(fallback);
  }

  function loadFlagImage(img) {
    if (!img || img.src || !img.dataset.src) return;
    img.src = img.dataset.src;
  }

  function renderFlagPreview(container, item, options = {}) {
    container.innerHTML = '';
    if (item.url) {
      const img = document.createElement('img');
      img.alt = item.label;
      img.loading = 'lazy';
      img.decoding = 'async';
      img.addEventListener('error', () => {
        img.remove();
        renderFlagFallback(container, item.label);
      }, { once: true });
      if (options.lazy) {
        img.dataset.src = item.url;
      } else {
        img.src = item.url;
      }
      container.appendChild(img);
    } else {
      renderFlagFallback(container, 'STD');
    }
    const label = document.createElement('span');
    label.textContent = item.label;
    container.appendChild(label);
  }

  function enhanceFlagSelect(select) {
    if (!select || select.dataset.enhanced === '1') return;
    select.dataset.enhanced = '1';

    const wrapper = document.createElement('div');
    wrapper.className = 'flag-picker';
    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'flag-picker-button';
    button.setAttribute('aria-expanded', 'false');
    wrapper.appendChild(button);

    const panel = document.createElement('div');
    panel.className = 'flag-picker-panel';
    panel.hidden = true;
    wrapper.appendChild(panel);

    const search = document.createElement('input');
    search.type = 'search';
    search.placeholder = 'Cerca bandiera';
    search.className = 'flag-picker-search';
    panel.appendChild(search);

    const list = document.createElement('div');
    list.className = 'flag-picker-list';
    panel.appendChild(list);

    const options = Array.from(select.options).map(optionPayload);
    const rowButtons = [];
    const lazyImages = [];
    const imageObserver = 'IntersectionObserver' in window
      ? new IntersectionObserver((entries) => {
          for (const entry of entries) {
            if (!entry.isIntersecting) continue;
            loadFlagImage(entry.target);
            imageObserver.unobserve(entry.target);
          }
        }, { root: list, rootMargin: '160px 0px' })
      : null;

    function updateButton() {
      const selected = optionPayload(select.options[select.selectedIndex] || select.options[0]);
      renderFlagPreview(button, selected);
    }

    function closePanel() {
      panel.hidden = true;
      button.setAttribute('aria-expanded', 'false');
    }

    function openPanel() {
      document.querySelectorAll('.flag-picker-panel').forEach((otherPanel) => {
        if (otherPanel !== panel) otherPanel.hidden = true;
      });
      panel.hidden = false;
      button.setAttribute('aria-expanded', 'true');
      search.focus();
      requestAnimationFrame(loadVisibleFlagImages);
    }

    function loadVisibleFlagImages() {
      const listRect = list.getBoundingClientRect();
      for (const img of lazyImages) {
        const row = img.closest('.flag-picker-option');
        if (img.src || (row && row.hidden)) continue;
        const rect = img.getBoundingClientRect();
        if (rect.bottom >= listRect.top - 160 && rect.top <= listRect.bottom + 160) {
          loadFlagImage(img);
        }
      }
    }

    function filterRows() {
      const query = normalize(search.value).trim();
      for (const row of rowButtons) {
        row.hidden = query !== '' && !normalize(row.dataset.label).includes(query);
      }
      requestAnimationFrame(loadVisibleFlagImages);
    }

    for (const item of options) {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'flag-picker-option';
      row.dataset.value = item.value;
      row.dataset.label = item.label;
      renderFlagPreview(row, item, { lazy: true });
      const lazyImage = row.querySelector('img[data-src]');
      if (lazyImage) lazyImages.push(lazyImage);
      row.addEventListener('click', () => {
        select.value = item.value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        updateButton();
        closePanel();
      });
      list.appendChild(row);
      rowButtons.push(row);
    }
    if (imageObserver) {
      lazyImages.forEach((img) => imageObserver.observe(img));
    }

    button.addEventListener('click', () => panel.hidden ? openPanel() : closePanel());
    search.addEventListener('input', filterRows);
    list.addEventListener('scroll', loadVisibleFlagImages, { passive: true });
    select.addEventListener('change', updateButton);
    document.addEventListener('click', (event) => {
      if (!wrapper.contains(event.target)) closePanel();
    });
    updateButton();
  }

  document.querySelectorAll('select.flag-native-select').forEach(enhanceFlagSelect);

  if (input) {
    input.addEventListener('input', applyFilter);
    applyFilter();
  }
})();
</script>
HTML;
render_footer();
