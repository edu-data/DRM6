/* =========================================================================
   DRM6 Survey - App Logic
   시간대별 일상 경험 조사: 활동기록 → 정서기록 → 인적사항
   ========================================================================= */

(function () {
  'use strict';

  var MIN_ACTIVITIES = 1;
  var MAX_ACTIVITIES = 5;
  var SUBMIT_TIMEOUT_MS = 15000;

  var TIME_BLOCKS = ['morning', 'afternoon', 'evening'];
  var TIME_BLOCK_LABELS = {
    morning: '오전·점심', afternoon: '오후', evening: '저녁'
  };
  var TIME_BLOCK_ICONS = {
    morning: '🌅', afternoon: '☀️', evening: '🌙'
  };
  var TIME_BLOCK_RANGES = {
    morning: '오전 8시 ~ 오후 1시',
    afternoon: '오후 1시 ~ 오후 6시',
    evening: '저녁 6시 ~ 11시'
  };

  // 전문교과는 교과시간 하위 과목으로 이동
  var TIME_OPTIONS = [
    '교과시간', '쉬는시간', '점심시간', '조종례시간', '학교방과후시간', '동아리시간', '상담시간',
    '학원시간', '아침시간(등교 전)',
    '저녁시간', '귀가후시간', '취침전', '기타'
  ];

  var SUBJECT_OPTIONS = [
    '국어', '수학', '영어', '사회/역사', '과학',
    '음악', '미술', '체육', '정보', '한국사',
    '제2외국어', '진로선택과목', '전문교과', '기타과목'
  ];

  var COMPANION_OPTIONS = [
    '혼자서', '교사와 함께', '친구와 함께', '선후배와 함께', '가족과 함께',
    '교사이외의 성인(학원강사포함)', '이웃/지인과 함께', '온라인 친구와 함께',
    'AI와 함께', '기타'
  ];

  var LOCATION_OPTIONS = [
    '교실', '교무실', '도서실', '운동장/체육관', '학원', '집', '기숙사',
    '카페/식당', '공원/야외', '종교시설(교회/성당/절 등)',
    '문화시설(영화관/공연장 등)', '교통수단(버스/지하철 등)',
    '스마트기기(컴퓨터포함)', '기타'
  ];

  var EMOTIONS = [
    {
      group: 'positive', label: '긍정 정서', icon: '😊', color: 'positive', items: [
        { key: 'emo_joyful', label: '즐거운' },
        { key: 'emo_happy', label: '행복한' },
        { key: 'emo_comfortable', label: '편안한' }
      ]
    },
    {
      group: 'negative', label: '부정 정서', icon: '😞', color: 'negative', items: [
        { key: 'emo_annoyed', label: '짜증나는' },
        { key: 'emo_negative', label: '부정적인' },
        { key: 'emo_lethargic', label: '무기력한' }
      ]
    },
    {
      group: 'meaning', label: '의미·가치', icon: '✨', color: 'meaning', items: [
        { key: 'emo_meaningful', label: '의미있는' },
        { key: 'emo_valuable', label: '가치있는' },
        { key: 'emo_satisfying', label: '만족할만한' }
      ]
    }
  ];

  var PLACEHOLDERS = {
    activity: {
      morning: '예: (9시~10시) 사회시간 모둠별 활동, 수행평가, 쉬는시간 친구들과 수다',
      afternoon: '예: (2시~3시) 진로탐색활동, 생기부기록 활동, 운동장에서 뛰어놀음',
      evening: '예: (7시~8시) 식사, 학원 수업, 가족과 대화'
    },
    reason: {
      morning: '예: 어려웠지만 친구와 같이 풀어서 재미있었다.',
      afternoon: '예: 새로운 활동을 해봐서 뿌듯했다.',
      evening: '예: 가족과 함께 식사하면서 편안했다.'
    }
  };

  // ── State ──
  var activities = {
    morning: [], afternoon: [], evening: []
  };
  var idCounters = { morning: 0, afternoon: 0, evening: 0 };
  var formData = { morning: {}, afternoon: {}, evening: {} };
  var currentIdx = { morning: 0, afternoon: 0, evening: 0 };
  var activeBlock = 'morning';

  // Emotion page state
  var emotionActivities = []; // flattened list: [{block, id, ...}]
  var emotionIdx = 0;
  var emotionData = {}; // keyed by block_id
  var emotionBlockIdx = 0; // which time block's emotions are being rated

  var isSubmitting = false;
  var isSubmitted = false;
  var lastPayload = null;
  var surveyStarted = false;
  var SESSION_KEY = 'drm6_survey_state';
  var DEMO_STORAGE_PREFIX = 'drm6_demo_';
  var savedDemographics = null;

  // Track which blocks have been visited (for tab restriction)
  var visitedBlocks = { morning: true, afternoon: false, evening: false };

  function saveToSession() {
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({
        activities: activities, idCounters: idCounters,
        formData: formData, emotionData: emotionData,
        currentIdx: currentIdx, activeBlock: activeBlock,
        surveyStarted: surveyStarted, visitedBlocks: visitedBlocks,
        phoneNumber: document.getElementById('phoneNumber') ? document.getElementById('phoneNumber').value : ''
      }));
    } catch (e) { /* quota exceeded */ }
  }

  function restoreFromSession() {
    try {
      var raw = sessionStorage.getItem(SESSION_KEY);
      if (!raw) return;
      var s = JSON.parse(raw);
      if (!s || !s.surveyStarted) return;
      activities = s.activities; idCounters = s.idCounters;
      formData = s.formData; emotionData = s.emotionData || {};
      currentIdx = s.currentIdx; activeBlock = s.activeBlock || 'morning';
      visitedBlocks = s.visitedBlocks || { morning: true, afternoon: false, evening: false };
      surveyStarted = true;
      if (s.phoneNumber) document.getElementById('phoneNumber').value = s.phoneNumber;
      updateTabCounts(); updateTabStates(); switchBlock(activeBlock);
      navigateTo('pageActivities');
      showToast('💾 이전 작성 내용을 복원했습니다.');
    } catch (e) { /* corrupted or unavailable */ }
  }

  function normalizePhone(p) { return p.replace(/[^0-9]/g, ''); }

  function loadDemographics(phone) {
    try {
      var raw = localStorage.getItem(DEMO_STORAGE_PREFIX + normalizePhone(phone));
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  function saveDemographicsToStorage(phone, demo) {
    try {
      localStorage.setItem(DEMO_STORAGE_PREFIX + normalizePhone(phone), JSON.stringify(demo));
    } catch (e) { /* ignore */ }
  }

  var $id = function (id) { return document.getElementById(id); };
  var pages = ['pageIntro', 'pageActivities', 'pageEmotion', 'pageDemo', 'completionScreen'];

  window.addEventListener('beforeunload', function (e) {
    if (surveyStarted && !isSubmitted) { e.preventDefault(); e.returnValue = ''; }
  });

  document.addEventListener('DOMContentLoaded', function () {
    $id('phoneNumber').addEventListener('input', formatPhoneNumber);

    // Intro
    $id('startSurveyBtn').addEventListener('click', function () {
      var phone = $id('phoneNumber').value.trim();
      if (!phone || phone.replace(/-/g, '').length < 10) {
        showToast('⚠️ 핸드폰 번호를 정확히 입력해 주세요.');
        $id('phoneNumber').classList.add('field-error');
        $id('phoneNumber').focus();
        return;
      }
      $id('phoneNumber').classList.remove('field-error');
      surveyStarted = true;
      // Check for saved demographics (repeat survey)
      savedDemographics = loadDemographics(phone);
      if (savedDemographics) {
        showToast('ℹ️ 이전에 입력한 인적사항이 자동 적용됩니다.');
      }
      // Add initial activity for each block
      TIME_BLOCKS.forEach(function (block) {
        if (activities[block].length === 0) addActivity(block);
      });
      visitedBlocks = { morning: true, afternoon: false, evening: false };
      updateTabStates();
      switchBlock('morning');
      navigateTo('pageActivities');
    });

    $id('phoneNumber').addEventListener('focus', function () { this.classList.remove('field-error'); });

    // Time tabs (restricted: only visited blocks)
    document.querySelectorAll('.time-tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        var targetBlock = tab.dataset.block;
        if (!visitedBlocks[targetBlock]) return; // can't jump to unvisited
        saveCurrentCard(activeBlock);
        switchBlock(targetBlock);
      });
    });

    // Activity nav - Morning
    $id('morningPrevBtn').addEventListener('click', function () { saveCurrentCard('morning'); moveCard('morning', -1); });
    $id('morningNextBtn').addEventListener('click', function () { saveCurrentCard('morning'); moveCard('morning', 1); });
    $id('addMorningBtn').addEventListener('click', function () { addActivity('morning'); });

    // Activity nav - Afternoon
    $id('afternoonPrevBtn').addEventListener('click', function () { saveCurrentCard('afternoon'); moveCard('afternoon', -1); });
    $id('afternoonNextBtn').addEventListener('click', function () { saveCurrentCard('afternoon'); moveCard('afternoon', 1); });
    $id('addAfternoonBtn').addEventListener('click', function () { addActivity('afternoon'); });

    // Activity nav - Evening
    $id('eveningPrevBtn').addEventListener('click', function () { saveCurrentCard('evening'); moveCard('evening', -1); });
    $id('eveningNextBtn').addEventListener('click', function () { saveCurrentCard('evening'); moveCard('evening', 1); });
    $id('addEveningBtn').addEventListener('click', function () { addActivity('evening'); });

    // ── Block-level sequential navigation (활동 기록) ──
    // Morning: ← 이전(인트로) | 다음: 오후 활동 기록 →
    $id('morningBackBtn').addEventListener('click', function () {
      saveCurrentCard('morning');
      navigateTo('pageIntro');
    });
    $id('morningNextBlockBtn').addEventListener('click', function () {
      saveCurrentCard('morning');
      if (activities['morning'].length < MIN_ACTIVITIES) {
        showToast('⚠️ 오전·점심 시간대에 최소 ' + MIN_ACTIVITIES + '개 활동을 입력해 주세요.');
        return;
      }
      if (!validateBlockActivities('morning')) return;
      visitedBlocks.afternoon = true;
      updateTabStates();
      switchBlock('afternoon');
    });

    // Afternoon: ← 오전·점심으로 | 다음: 저녁 활동 기록 →
    $id('afternoonBackBtn').addEventListener('click', function () {
      saveCurrentCard('afternoon');
      switchBlock('morning');
    });
    $id('afternoonNextBlockBtn').addEventListener('click', function () {
      saveCurrentCard('afternoon');
      if (activities['afternoon'].length < MIN_ACTIVITIES) {
        showToast('⚠️ 오후 시간대에 최소 ' + MIN_ACTIVITIES + '개 활동을 입력해 주세요.');
        return;
      }
      if (!validateBlockActivities('afternoon')) return;
      visitedBlocks.evening = true;
      updateTabStates();
      switchBlock('evening');
    });

    // Evening: ← 오후로 | 다음: 정서 기록 →
    $id('eveningBackBtn').addEventListener('click', function () {
      saveCurrentCard('evening');
      switchBlock('afternoon');
    });
    $id('eveningNextBlockBtn').addEventListener('click', function () {
      saveCurrentCard('evening');
      if (activities['evening'].length < MIN_ACTIVITIES) {
        showToast('⚠️ 저녁 시간대에 최소 ' + MIN_ACTIVITIES + '개 활동을 입력해 주세요.');
        return;
      }
      if (!validateBlockActivities('evening')) return;
      buildEmotionList();
      emotionBlockIdx = 0;
      navigateTo('pageEmotion');
      renderEmotionBlockView();
    });

    // ── Emotion nav (within block) ──
    $id('emotionPrevBtn').addEventListener('click', function () { saveEmotionCard(); moveEmotionInBlock(-1); });
    $id('emotionNextBtn').addEventListener('click', function () { saveEmotionCard(); moveEmotionInBlock(1); });

    // ── Emotion block-level navigation ──
    $id('emotionBackBlockBtn').addEventListener('click', function () {
      saveEmotionCard();
      if (emotionBlockIdx <= 0) {
        // Go back to activities (evening block)
        switchBlock('evening');
        navigateTo('pageActivities');
      } else {
        emotionBlockIdx--;
        renderEmotionBlockView();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });

    $id('emotionNextBlockBtn').addEventListener('click', function () {
      saveEmotionCard();
      // Validate current block's emotions
      if (!validateBlockEmotions(TIME_BLOCKS[emotionBlockIdx])) return;

      if (emotionBlockIdx >= TIME_BLOCKS.length - 1) {
        // Last block → go to demographics or submit
        if (savedDemographics) {
          handleComplete();
        } else {
          navigateTo('pageDemo');
        }
      } else {
        emotionBlockIdx++;
        renderEmotionBlockView();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });

    // Demo nav
    $id('backToEmotionBtn').addEventListener('click', function () {
      emotionBlockIdx = TIME_BLOCKS.length - 1;
      renderEmotionBlockView();
      navigateTo('pageEmotion');
    });
    $id('completeBtn').addEventListener('click', function () { handleComplete(); });

    // Restore saved progress
    restoreFromSession();
  });

  // ── Navigation ──
  function navigateTo(pageId) {
    if (isSubmitted && pageId !== 'completionScreen') return;
    pages.forEach(function (id) { var el = $id(id); if (el) el.classList.remove('active'); });
    var target = $id(pageId);
    if (target) target.classList.add('active');
    updateProgressBar(pageId);
    var pb = $id('progressBar');
    if (pageId === 'completionScreen') pb.classList.add('hide');
    else pb.classList.remove('hide');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function updateProgressBar(pageId) {
    var stepMap = { 'pageIntro': 1, 'pageActivities': 2, 'pageEmotion': 3, 'pageDemo': 4, 'completionScreen': 5 };
    var current = stepMap[pageId] || 1;
    document.querySelectorAll('.progress-step').forEach(function (step) {
      step.classList.remove('active', 'completed');
      var sd = step.dataset.step;
      if (!sd) return;
      if (sd.includes('-')) {
        var from = parseInt(sd.split('-')[0]);
        var line = step.querySelector('.progress-step__line');
        if (line) { if (from < current) line.classList.add('completed'); else line.classList.remove('completed'); }
        return;
      }
      var n = parseInt(sd);
      if (n === current) step.classList.add('active');
      else if (n < current) step.classList.add('completed');
    });
  }

  // ── Time Block Tabs ──
  function switchBlock(block) {
    activeBlock = block;
    document.querySelectorAll('.time-tab').forEach(function (t) { t.classList.remove('active'); });
    $id('tab' + capitalize(block)).classList.add('active');
    document.querySelectorAll('.time-block').forEach(function (b) { b.classList.remove('active'); });
    $id('block' + capitalize(block)).classList.add('active');
    renderCurrentCard(block);
    updateNavBar(block);
    updateAddButton(block);
  }

  function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  function updateTabCounts() {
    TIME_BLOCKS.forEach(function (block) {
      $id('count' + capitalize(block)).textContent = activities[block].length;
    });
  }

  // Update tab visual states (disable unvisited tabs)
  function updateTabStates() {
    TIME_BLOCKS.forEach(function (block) {
      var tab = $id('tab' + capitalize(block));
      if (!tab) return;
      if (visitedBlocks[block]) {
        tab.classList.remove('tab-disabled');
        tab.removeAttribute('aria-disabled');
      } else {
        tab.classList.add('tab-disabled');
        tab.setAttribute('aria-disabled', 'true');
      }
    });
  }

  // ── Activity Management ──
  function addActivity(block) {
    var list = activities[block];
    if (list.length >= MAX_ACTIVITIES) {
      showToast('⚠️ 최대 ' + MAX_ACTIVITIES + '개까지 입력할 수 있습니다.');
      return;
    }
    if (list.length > 0) saveCurrentCard(block);
    var id = ++idCounters[block];
    list.push({ id: id });
    currentIdx[block] = list.length - 1;
    renderCurrentCard(block);
    updateNavBar(block);
    updateAddButton(block);
    updateTabCounts();
    saveToSession();
  }

  function removeActivity(block, id) {
    var list = activities[block];
    if (list.length <= 0) return;
    var idx = list.findIndex(function (a) { return a.id === id; });
    if (idx === -1) return;
    list.splice(idx, 1);
    delete formData[block][id];
    if (currentIdx[block] >= list.length) currentIdx[block] = Math.max(0, list.length - 1);
    renderCurrentCard(block);
    updateNavBar(block);
    updateAddButton(block);
    updateTabCounts();
    saveToSession();
  }

  function moveCard(block, dir) {
    var list = activities[block];
    var ci = currentIdx[block];
    var newIdx = ci + dir;
    if (newIdx < 0 || newIdx >= list.length) return;
    currentIdx[block] = newIdx;
    renderCurrentCard(block);
    updateNavBar(block);
  }

  function updateNavBar(block) {
    var list = activities[block];
    var ci = currentIdx[block];
    $id(block + 'PrevBtn').disabled = ci <= 0;
    $id(block + 'NextBtn').disabled = ci >= list.length - 1;
    $id(block + 'ProgressText').textContent = list.length > 0 ? (ci + 1) + ' / ' + list.length : '0 / 0';
  }

  function updateAddButton(block) {
    var list = activities[block];
    var btn = $id('add' + capitalize(block) + 'Btn');
    if (btn) btn.disabled = list.length >= MAX_ACTIVITIES;
  }

  // ── Save / Restore Card Data ──
  function saveCurrentCard(block) {
    var list = activities[block];
    var ci = currentIdx[block];
    if (ci >= list.length || list.length === 0) return;
    var id = list[ci].id;
    var data = {};
    var prefix = block + '_';

    // Time (무슨 시간)
    var timeSel = document.getElementById(prefix + 'time_' + id);
    data.time = timeSel ? timeSel.value : '';
    var timeEtc = document.getElementById(prefix + 'time_' + id + '_etc');
    data.time_etc = (timeEtc && timeEtc.value) ? timeEtc.value : '';
    if (data.time === '교과시간') {
      var subSel = document.getElementById(prefix + 'time_' + id + '_subject');
      data.time_subject = subSel ? subSel.value : '';
    }

    // Companion
    var compSel = document.getElementById(prefix + 'companion_' + id);
    data.companion = compSel ? compSel.value : '';
    var compEtc = document.getElementById(prefix + 'companion_' + id + '_etc');
    data.companion_etc = (compEtc && compEtc.value) ? compEtc.value : '';

    // Location
    var locSel = document.getElementById(prefix + 'location_' + id);
    data.location = locSel ? locSel.value : '';
    var locEtc = document.getElementById(prefix + 'location_' + id + '_etc');
    data.location_etc = (locEtc && locEtc.value) ? locEtc.value : '';

    // Activity text
    data.activity = (document.getElementById(prefix + 'activity_' + id) || {}).value || '';
    // Reason
    data.reason = (document.getElementById(prefix + 'reason_' + id) || {}).value || '';

    formData[block][id] = data;
    saveToSession();
  }

  function restoreCardData(block, id) {
    var data = formData[block][id];
    if (!data) return;
    var prefix = block + '_';

    // Time
    var timeSel = document.getElementById(prefix + 'time_' + id);
    if (timeSel && data.time) {
      timeSel.value = data.time;
      if (data.time === '기타') {
        var etc = document.getElementById(prefix + 'time_' + id + '_etc');
        if (etc) { etc.style.display = 'block'; etc.value = data.time_etc || ''; }
      }
      if (data.time === '교과시간') {
        var sub = document.getElementById(prefix + 'time_' + id + '_subject');
        if (sub) { sub.style.display = 'block'; if (data.time_subject) sub.value = data.time_subject; }
      }
    }

    // Companion
    var compSel = document.getElementById(prefix + 'companion_' + id);
    if (compSel && data.companion) {
      compSel.value = data.companion;
      if (data.companion === '기타') {
        var ce = document.getElementById(prefix + 'companion_' + id + '_etc');
        if (ce) { ce.style.display = 'block'; ce.value = data.companion_etc || ''; }
      }
    }

    // Location
    var locSel = document.getElementById(prefix + 'location_' + id);
    if (locSel && data.location) {
      locSel.value = data.location;
      if (data.location === '기타') {
        var le = document.getElementById(prefix + 'location_' + id + '_etc');
        if (le) { le.style.display = 'block'; le.value = data.location_etc || ''; }
      }
    }

    // Activity
    var actEl = document.getElementById(prefix + 'activity_' + id);
    if (actEl && data.activity) actEl.value = data.activity;

    // Reason
    var reasonEl = document.getElementById(prefix + 'reason_' + id);
    if (reasonEl && data.reason) reasonEl.value = data.reason;
  }

  // ── Render Activity Card ──
  function renderCurrentCard(block) {
    var list = activities[block];
    var ci = currentIdx[block];
    var container = $id(block + 'List');
    container.innerHTML = '';

    if (ci >= list.length || list.length === 0) return;

    var a = list[ci];
    var id = a.id;
    var num = ci + 1;
    var prefix = block + '_';
    var fd = formData[block][id] || {};

    var card = document.createElement('div');
    card.className = 'activity-card activity-card--' + block;
    card.dataset.id = block + '-' + id;

    card.innerHTML =
      '<div class="activity-card__header">' +
      '<div class="activity-card__number">' +
      '<div class="activity-card__number-badge">' + num + '</div>' +
      '<span style="font-size:0.8rem; font-weight:600;">활동 ' + num + '</span>' +
      '</div>' +
      '<button class="activity-card__delete" type="button" title="삭제">✕</button>' +
      '</div>' +
      '<div class="activity-card__grid">' +
      '<div class="form-group full-width">' +
      '<label class="form-label">📝 일화 (기억에 남는 활동은?)</label>' +
      '<textarea class="form-textarea" id="' + prefix + 'activity_' + id + '" placeholder="' + (PLACEHOLDERS.activity[block] || '') + '" rows="2">' + escapeHtml(fd.activity || '') + '</textarea>' +
      '</div>' +
      '<div class="form-group">' +
      '<label class="form-label">⏰ 무슨 시간?</label>' +
      buildSelect(prefix + 'time_' + id, TIME_OPTIONS, fd.time || null) +
      '</div>' +
      '<div class="form-group">' +
      '<label class="form-label">👥 누구와?</label>' +
      buildSelect(prefix + 'companion_' + id, COMPANION_OPTIONS, fd.companion || null) +
      '</div>' +
      '<div class="form-group">' +
      '<label class="form-label">📍 어디서?</label>' +
      buildSelect(prefix + 'location_' + id, LOCATION_OPTIONS, fd.location || null) +
      '</div>' +
      '<div class="form-group">' +
      '<label class="form-label">💬 이유</label>' +
      '<textarea class="form-textarea" id="' + prefix + 'reason_' + id + '" placeholder="' + (PLACEHOLDERS.reason[block] || '') + '" rows="2" style="min-height:50px;">' + escapeHtml(fd.reason || '') + '</textarea>' +
      '</div>' +
      '</div>';

    container.appendChild(card);

    // Bind handlers
    bindSelectHandlers(card, block, id);
    card.querySelector('.activity-card__delete').addEventListener('click', function () { removeActivity(block, id); });

    // Auto-clear error
    card.addEventListener('change', function (e) {
      if (e.target.closest('.form-group')) {
        e.target.closest('.form-group').querySelectorAll('.field-error').forEach(function (el) { el.classList.remove('field-error'); });
      }
    });
    card.addEventListener('input', function (e) { if (e.target.classList.contains('field-error')) e.target.classList.remove('field-error'); });

    restoreCardData(block, id);
  }

  function bindSelectHandlers(card, block, id) {
    card.querySelectorAll('select.form-select').forEach(function (sel) {
      sel.addEventListener('change', function () {
        sel.classList.remove('field-error');
        var etcEl = document.getElementById(sel.id + '_etc');
        if (etcEl) etcEl.style.display = sel.value === '기타' ? 'block' : 'none';
        if (sel.id.indexOf('_time_') !== -1) {
          var subEl = document.getElementById(sel.id + '_subject');
          if (subEl) subEl.style.display = (sel.value === '교과시간') ? 'block' : 'none';
        }
      });
    });
  }

  function buildSelect(name, options, selectedValue) {
    var isTimeField = name.indexOf('_time_') !== -1;
    var opts = options.map(function (opt) {
      var selected = opt === selectedValue ? 'selected' : '';
      return '<option value="' + escapeHtml(opt) + '" ' + selected + '>' + escapeHtml(opt) + '</option>';
    }).join('');

    var html = '<select class="form-select" id="' + name + '">' +
      '<option value="">선택</option>' + opts + '</select>' +
      '<input type="text" class="form-input" id="' + name + '_etc" placeholder="직접 입력해 주세요" style="display:' + (selectedValue === '기타' ? 'block' : 'none') + '; margin-top:0.3rem; font-size:0.82rem;" />';

    if (isTimeField) {
      var showSubject = (selectedValue === '교과시간');
      var subOpts = SUBJECT_OPTIONS.map(function (s) {
        return '<option value="' + escapeHtml(s) + '">' + escapeHtml(s) + '</option>';
      }).join('');
      html += '<select class="form-select" id="' + name + '_subject" style="display:' + (showSubject ? 'block' : 'none') + '; margin-top:0.3rem; font-size:0.82rem;">' +
        '<option value="">과목 선택</option>' + subOpts + '</select>';
    }
    return html;
  }

  // ── Validation (Activity page) ──
  function validateBlockActivities(block) {
    var list = activities[block];
    var fd = formData[block];

    for (var i = 0; i < list.length; i++) {
      var id = list[i].id;
      var d = fd[id] || {};

      if (!d.activity || !d.activity.trim()) {
        switchBlock(block);
        currentIdx[block] = i; renderCurrentCard(block); updateNavBar(block);
        showToast('⚠️ ' + TIME_BLOCK_LABELS[block] + ' 활동 ' + (i + 1) + '의 내용을 입력해 주세요.');
        return false;
      }
      if (!d.time) {
        switchBlock(block);
        currentIdx[block] = i; renderCurrentCard(block); updateNavBar(block);
        showToast('⚠️ ' + TIME_BLOCK_LABELS[block] + ' 활동 ' + (i + 1) + '의 시간을 선택해 주세요.');
        return false;
      }
      if (d.time === '교과시간' && !d.time_subject) {
        switchBlock(block);
        currentIdx[block] = i; renderCurrentCard(block); updateNavBar(block);
        showToast('⚠️ ' + TIME_BLOCK_LABELS[block] + ' 활동 ' + (i + 1) + '의 교과시간 과목을 선택해 주세요.');
        return false;
      }
      if (!d.companion) {
        switchBlock(block);
        currentIdx[block] = i; renderCurrentCard(block); updateNavBar(block);
        showToast('⚠️ ' + TIME_BLOCK_LABELS[block] + ' 활동 ' + (i + 1) + '의 "누구와"를 선택해 주세요.');
        return false;
      }
      if (!d.location) {
        switchBlock(block);
        currentIdx[block] = i; renderCurrentCard(block); updateNavBar(block);
        showToast('⚠️ ' + TIME_BLOCK_LABELS[block] + ' 활동 ' + (i + 1) + '의 "어디서"를 선택해 주세요.');
        return false;
      }
    }
    return true;
  }

  // ── Emotion Page ──
  function buildEmotionList() {
    emotionActivities = [];
    TIME_BLOCKS.forEach(function (block) {
      activities[block].forEach(function (a, idx) {
        var fd = formData[block][a.id] || {};
        emotionActivities.push({
          block: block,
          id: a.id,
          num: idx + 1,
          activity: fd.activity || '(활동 내용 없음)',
          time: fd.time || ''
        });
      });
    });
    emotionIdx = 0;
  }

  // Get emotion activities for a specific block
  function getBlockEmotionActivities(block) {
    return emotionActivities.filter(function (ea) { return ea.block === block; });
  }

  // Get current block's emotion activities and current index within that block
  function getCurrentBlockEmotionInfo() {
    var block = TIME_BLOCKS[emotionBlockIdx];
    var blockActivities = getBlockEmotionActivities(block);
    // Find the global index of current emotionIdx within block activities
    var idxInBlock = 0;
    for (var i = 0; i < blockActivities.length; i++) {
      var globalIdx = emotionActivities.indexOf(blockActivities[i]);
      if (globalIdx === emotionIdx) { idxInBlock = i; break; }
    }
    return { block: block, activities: blockActivities, idxInBlock: idxInBlock };
  }

  // Render the emotion view for the current block
  function renderEmotionBlockView() {
    var block = TIME_BLOCKS[emotionBlockIdx];
    var blockActs = getBlockEmotionActivities(block);

    // Set emotionIdx to first activity in this block
    if (blockActs.length > 0) {
      emotionIdx = emotionActivities.indexOf(blockActs[0]);
    }

    // Update block header
    updateEmotionBlockHeader();
    renderEmotionCard();
    updateEmotionNavBar();
    updateEmotionBlockButtons();
  }

  function updateEmotionBlockHeader() {
    var block = TIME_BLOCKS[emotionBlockIdx];
    var headerEl = $id('emotionBlockHeader');
    if (headerEl) {
      headerEl.innerHTML =
        '<span class="emotion-block-indicator emotion-block-indicator--' + block + '">' +
        TIME_BLOCK_ICONS[block] + ' ' + TIME_BLOCK_LABELS[block] + ' 활동 정서 기록' +
        '<span class="emotion-block-step">(' + (emotionBlockIdx + 1) + '/' + TIME_BLOCKS.length + ' 시간대)</span>' +
        '</span>';
    }
  }

  function updateEmotionBlockButtons() {
    var backBtn = $id('emotionBackBlockBtn');
    var nextBtn = $id('emotionNextBlockBtn');

    // Back button label
    if (emotionBlockIdx <= 0) {
      backBtn.textContent = '← 활동 기록으로';
    } else {
      backBtn.textContent = '← ' + TIME_BLOCK_LABELS[TIME_BLOCKS[emotionBlockIdx - 1]] + ' 정서로';
    }

    // Next button label
    if (emotionBlockIdx >= TIME_BLOCKS.length - 1) {
      if (savedDemographics) {
        nextBtn.textContent = '✅ 설문 완료';
      } else {
        nextBtn.textContent = '다음: 인적사항 →';
      }
    } else {
      var nextBlock = TIME_BLOCKS[emotionBlockIdx + 1];
      nextBtn.textContent = '다음: ' + TIME_BLOCK_LABELS[nextBlock] + ' 활동 정서 →';
    }
  }

  function renderEmotionCard() {
    var container = $id('emotionContent');
    container.innerHTML = '';

    if (emotionActivities.length === 0) return;
    var ea = emotionActivities[emotionIdx];
    var key = ea.block + '_' + ea.id;
    var ed = emotionData[key] || {};

    // Activity header
    var headerHtml =
      '<div class="emotion-activity-header">' +
      '<span class="emotion-activity-header__badge emotion-activity-header__badge--' + ea.block + '">' +
      TIME_BLOCK_ICONS[ea.block] + ' ' + TIME_BLOCK_LABELS[ea.block] +
      '</span>' +
      '<span class="emotion-activity-header__text">' + escapeHtml(ea.activity) + '</span>' +
      '</div>';

    // Summary info
    var fd = formData[ea.block][ea.id] || {};
    var summaryHtml =
      '<div class="summary-card">' +
      (fd.time ? '<div class="summary-card__row"><span class="summary-card__label">⏰ 시간</span><span>' + escapeHtml(getDisplayTime(fd)) + '</span></div>' : '') +
      (fd.companion ? '<div class="summary-card__row"><span class="summary-card__label">👥 함께</span><span>' + escapeHtml(getDisplayVal(fd, 'companion')) + '</span></div>' : '') +
      (fd.location ? '<div class="summary-card__row"><span class="summary-card__label">📍 장소</span><span>' + escapeHtml(getDisplayVal(fd, 'location')) + '</span></div>' : '') +
      (fd.reason ? '<div class="summary-card__row"><span class="summary-card__label">💬 이유</span><span>' + escapeHtml(fd.reason) + '</span></div>' : '') +
      '</div>';

    // Emotion scales
    var emotionHtml =
      '<div class="emotion-section">' +
      '<div class="likert-hint"><span>1 = 전혀 아니다</span><span>7 = 매우 그렇다</span></div>' +
      EMOTIONS.map(function (group) {
        return '<div class="emotion-group emotion-group--' + group.color + '">' +
          '<div class="emotion-group__title emotion-group__title--' + group.color + '">' + group.icon + ' ' + group.label + '</div>' +
          group.items.map(function (emo) {
            var checkedVal = ed[emo.key] || '';
            return '<div class="likert-item">' +
              '<span class="likert-item__label">' + emo.label + '</span>' +
              '<div class="likert-scale-wrap">' +
              '<span class="likert-endpoint">전혀<br>아님</span>' +
              '<div class="likert-scale">' +
              [1, 2, 3, 4, 5, 6, 7].map(function (v) {
                var checked = (checkedVal == v) ? ' checked' : '';
                return '<label class="likert-radio"><input type="radio" name="emo_' + emo.key + '_' + key + '" value="' + v + '"' + checked + '><span>' + v + '</span></label>';
              }).join('') +
              '</div>' +
              '<span class="likert-endpoint">매우<br>그러함</span>' +
              '</div></div>';
          }).join('') +
          '</div>';
      }).join('') +
      '</div>';

    container.innerHTML = headerHtml + summaryHtml + emotionHtml;
  }

  function saveEmotionCard() {
    if (emotionActivities.length === 0) return;
    var ea = emotionActivities[emotionIdx];
    var key = ea.block + '_' + ea.id;
    var data = {};

    EMOTIONS.forEach(function (g) {
      g.items.forEach(function (emo) {
        var checked = document.querySelector('input[name="emo_' + emo.key + '_' + key + '"]:checked');
        data[emo.key] = checked ? checked.value : '';
      });
    });

    emotionData[key] = data;
    saveToSession();
  }

  // Move within current block's emotions only
  function moveEmotionInBlock(dir) {
    var block = TIME_BLOCKS[emotionBlockIdx];
    var blockActs = getBlockEmotionActivities(block);
    // Find current position within block
    var curBlockPos = -1;
    for (var i = 0; i < blockActs.length; i++) {
      if (emotionActivities.indexOf(blockActs[i]) === emotionIdx) { curBlockPos = i; break; }
    }
    var newBlockPos = curBlockPos + dir;
    if (newBlockPos < 0 || newBlockPos >= blockActs.length) return;
    emotionIdx = emotionActivities.indexOf(blockActs[newBlockPos]);
    renderEmotionCard();
    updateEmotionNavBar();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function updateEmotionNavBar() {
    var block = TIME_BLOCKS[emotionBlockIdx];
    var blockActs = getBlockEmotionActivities(block);
    var curBlockPos = -1;
    for (var i = 0; i < blockActs.length; i++) {
      if (emotionActivities.indexOf(blockActs[i]) === emotionIdx) { curBlockPos = i; break; }
    }
    $id('emotionPrevBtn').disabled = curBlockPos <= 0;
    $id('emotionNextBtn').disabled = curBlockPos >= blockActs.length - 1;
    $id('emotionProgressText').textContent = blockActs.length > 0
      ? (curBlockPos + 1) + ' / ' + blockActs.length
      : '0 / 0';
  }

  // Validate emotions for a specific time block
  function validateBlockEmotions(block) {
    var blockActs = getBlockEmotionActivities(block);
    for (var i = 0; i < blockActs.length; i++) {
      var ea = blockActs[i];
      var key = ea.block + '_' + ea.id;
      var ed = emotionData[key] || {};

      var missing = [];
      EMOTIONS.forEach(function (g) {
        g.items.forEach(function (emo) {
          if (!ed[emo.key]) missing.push(emo.label);
        });
      });

      if (missing.length > 0) {
        emotionIdx = emotionActivities.indexOf(ea);
        renderEmotionCard();
        updateEmotionNavBar();
        showToast('⚠️ ' + TIME_BLOCK_LABELS[ea.block] + ' 활동 ' + ea.num + '의 정서를 모두 응답해 주세요. (미응답: ' + missing.join(', ') + ')');
        return false;
      }
    }
    return true;
  }

  // ── Helper: display values ──
  function getDisplayTime(fd) {
    if (fd.time === '교과시간' && fd.time_subject) return fd.time + '(' + fd.time_subject + ')';
    if (fd.time === '기타' && fd.time_etc) return '기타: ' + fd.time_etc;
    return fd.time || '';
  }

  function getDisplayVal(fd, field) {
    if (fd[field] === '기타' && fd[field + '_etc']) return '기타: ' + fd[field + '_etc'];
    return fd[field] || '';
  }

  // ── Data Collection ──
  function collectAllActivities() {
    var result = [];
    TIME_BLOCKS.forEach(function (block) {
      activities[block].forEach(function (a, idx) {
        var fd = formData[block][a.id] || {};
        var ed = emotionData[block + '_' + a.id] || {};

        var data = {
          timeBlock: TIME_BLOCK_LABELS[block],
          activityNum: idx + 1,
          activity: fd.activity || '',
          time: getDisplayTime(fd),
          companion: getDisplayVal(fd, 'companion'),
          location: getDisplayVal(fd, 'location'),
          reason: fd.reason || ''
        };

        EMOTIONS.forEach(function (g) {
          g.items.forEach(function (emo) {
            data[emo.key] = ed[emo.key] ? parseInt(ed[emo.key]) : '';
          });
        });

        result.push(data);
      });
    });
    return result;
  }

  // ── Submit ──
  function handleComplete() {
    if (isSubmitting || isSubmitted) return;

    var demo;
    if (savedDemographics) {
      demo = savedDemographics;
    } else {
      var genderEl = document.querySelector('input[name="gender"]:checked');
      var locEl = $id('schoolLocation');
      var typeEl = $id('schoolType');
      var gradeEl = document.querySelector('input[name="grade"]:checked');
      var careerEl = document.querySelector('input[name="careerDecision"]:checked');

      var gender = genderEl ? genderEl.value : '';
      var schoolLocation = locEl ? locEl.value : '';
      var schoolType = typeEl ? typeEl.value : '';
      var grade = gradeEl ? gradeEl.value : '';
      var careerDecision = careerEl ? careerEl.value : '';

      if (!gender) { showToast('⚠️ 성별을 선택해 주세요.'); return; }
      if (!schoolLocation) { showToast('⚠️ 학교 소재지를 선택해 주세요.'); return; }
      if (!schoolType) { showToast('⚠️ 학교 유형을 선택해 주세요.'); return; }
      if (!grade) { showToast('⚠️ 학년을 선택해 주세요.'); return; }
      if (!careerDecision) { showToast('⚠️ 진로 결정 여부를 선택해 주세요.'); return; }

      demo = {
        gender: gender,
        schoolLocation: schoolLocation,
        schoolType: schoolType,
        grade: grade,
        careerDecision: careerDecision
      };
    }

    setSubmitButtonState(true);

    var allActivities = collectAllActivities();
    var phone = $id('phoneNumber').value.trim();
    var payload = {
      phoneNumber: phone,
      activities: allActivities,
      activityCounts: {
        morning: activities.morning.length,
        afternoon: activities.afternoon.length,
        evening: activities.evening.length
      },
      demographics: demo
    };

    lastPayload = payload;
    // Save demographics for future repeat surveys
    saveDemographicsToStorage(phone, demo);
    submitData(payload);
  }

  function showSubmitOverlay() {
    var overlay = $id('submitOverlay');
    if (overlay) overlay.classList.add('active');
  }

  function hideSubmitOverlay() {
    var overlay = $id('submitOverlay');
    if (overlay) overlay.classList.remove('active');
  }

  function submitData(payload) {
    isSubmitting = true;
    var statusEl = $id('submitStatus');
    statusEl.className = 'submit-status';
    statusEl.innerHTML = '<div class="submit-status__spinner"></div><span class="submit-status__text">응답을 제출하고 있습니다...</span>';
    showSubmitOverlay();

    var controller = new AbortController();
    var timeoutId = setTimeout(function () { controller.abort(); }, SUBMIT_TIMEOUT_MS);

    fetch(APP_CONFIG.GAS_URL, {
      method: 'POST', mode: 'no-cors',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload), signal: controller.signal
    }).then(function () {
      clearTimeout(timeoutId); isSubmitting = false; isSubmitted = true;
      try { sessionStorage.removeItem(SESSION_KEY); } catch (e) { }
      // 1단계: 오버레이에서 성공 메시지 표시
      statusEl.className = 'submit-status submit-status--success';
      statusEl.innerHTML = '<span style="font-size:1.2rem;">✅</span><span class="submit-status__text">응답이 성공적으로 제출되었습니다. 감사합니다!</span>';
      // 2단계: 2초 후 오버레이 닫고 완료 화면으로 전환
      setTimeout(function () {
        hideSubmitOverlay();
        navigateTo('completionScreen');
      }, 2000);
    }).catch(function (err) {
      clearTimeout(timeoutId); isSubmitting = false;
      var isTimeout = err.name === 'AbortError';
      statusEl.className = 'submit-status submit-status--error';
      statusEl.innerHTML = '<span style="font-size:1.2rem;">❌</span><span class="submit-status__text">' +
        (isTimeout ? '제출 시간이 초과되었습니다.' : '제출 중 오류가 발생했습니다.') + '</span>';
      var retryBtn = document.createElement('button');
      retryBtn.className = 'btn-retry'; retryBtn.textContent = '🔄 다시 시도';
      retryBtn.addEventListener('click', function () { if (lastPayload) submitData(lastPayload); });
      var closeBtn = document.createElement('button');
      closeBtn.className = 'btn-retry'; closeBtn.textContent = '← 돌아가기';
      closeBtn.style.marginLeft = '0.5rem';
      closeBtn.addEventListener('click', function () { hideSubmitOverlay(); setSubmitButtonState(false); });
      statusEl.appendChild(document.createElement('br'));
      statusEl.appendChild(retryBtn);
      statusEl.appendChild(closeBtn);
    });
  }

  function setSubmitButtonState(disabled) {
    var btn = $id('completeBtn');
    if (btn) {
      btn.disabled = disabled;
      if (disabled) btn.classList.add('is-loading');
      else btn.classList.remove('is-loading');
    }
  }

  // ── Helpers ──
  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function formatPhoneNumber(e) {
    var val = e.target.value.replace(/[^0-9]/g, '');
    if (val.length > 11) val = val.slice(0, 11);
    if (val.length > 7) val = val.slice(0, 3) + '-' + val.slice(3, 7) + '-' + val.slice(7);
    else if (val.length > 3) val = val.slice(0, 3) + '-' + val.slice(3);
    e.target.value = val;
  }

  var toastTimer;
  function showToast(msg) {
    var toast = $id('toast');
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, 3500);
  }

})();
